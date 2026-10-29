"""Tests for cd-actions/conda/scripts/acquire_lock.py."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPT_DIR = Path(__file__).parent.parent / "conda" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import acquire_lock  # noqa: E402


def _run(run_id: int, created_at: str, title: str = "other dispatch") -> dict:
    return {
        "id": run_id,
        "created_at": created_at,
        "display_title": title,
    }


def test_find_dispatched_run_paginates(monkeypatch):
    start_time = datetime(2026, 7, 2, tzinfo=timezone.utc).timestamp()
    created_at = "2026-07-02T00:00:01Z"
    first_page = [_run(run_id, created_at) for run_id in range(100)]
    second_page = [_run(1234, created_at, "index requested-dispatch-id")]
    requested_endpoints = []

    def fake_request(endpoint, token=None):
        requested_endpoints.append(endpoint)
        if endpoint.endswith("&page=1"):
            return {"workflow_runs": first_page}
        if endpoint.endswith("&page=2"):
            return {"workflow_runs": second_page}
        raise AssertionError(f"Unexpected endpoint: {endpoint}")

    monkeypatch.setattr(acquire_lock, "gh_api_request", fake_request)

    run_id = acquire_lock.find_dispatched_run(
        "requested-dispatch-id", start_time, "token"
    )

    assert run_id == 1234
    assert len(requested_endpoints) == 2
    assert all("event=workflow_dispatch" in endpoint for endpoint in requested_endpoints)
    assert all("per_page=100" in endpoint for endpoint in requested_endpoints)


def test_find_dispatched_run_stops_before_dispatch_window(monkeypatch):
    start_time = datetime(2026, 7, 2, tzinfo=timezone.utc).timestamp()
    page = [_run(run_id, "2026-07-01T23:59:29Z") for run_id in range(100)]
    request_count = 0

    def fake_request(endpoint, token=None):
        nonlocal request_count
        request_count += 1
        return {"workflow_runs": page}

    monkeypatch.setattr(acquire_lock, "gh_api_request", fake_request)

    run_id = acquire_lock.find_dispatched_run("missing-dispatch-id", start_time, "token")

    assert run_id is None
    assert request_count == 1


SECRET_WORDS = ("token", "password", "secret", "credential", "user")


def test_dispatch_payload_has_no_secret_looking_keys():
    payload = acquire_lock.build_dispatch_payload("v2", "test", "1-conda", "1", "ecmwf/eckit", "id")

    keys = set(payload) | set(payload["inputs"])
    assert not [k for k in keys if any(word in k.lower() for word in SECRET_WORDS)]
    assert payload["inputs"]["channel"] == "test"


def test_main_dispatches_at_lock_ref_without_credentials(monkeypatch):
    requests = []

    def fake_request(endpoint, method="GET", data=None, token=None):
        requests.append((endpoint, method, data, token))
        if method == "POST":
            return None
        return {"status": "completed", "conclusion": "success"}

    monkeypatch.setattr(acquire_lock, "gh_api_request", fake_request)
    monkeypatch.setattr(acquire_lock, "find_dispatched_run", lambda *args: 99)
    monkeypatch.setattr(acquire_lock.time, "sleep", lambda _: None)
    monkeypatch.setenv("GH_PAT", "gh-pat-value")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "acquire_lock.py",
            "--channel", "test",
            "--artifact-name", "123-conda",
            "--caller-run-id", "123",
            "--caller-repo", "ecmwf/eckit",
            "--lock-ref", "hotfix/cd-v2-hardening",
        ],
    )

    with pytest.raises(SystemExit) as exit_info:
        acquire_lock.main()

    assert exit_info.value.code == 0
    dispatch = [r for r in requests if r[1] == "POST"]
    assert len(dispatch) == 1
    _, _, data, token = dispatch[0]
    assert data["ref"] == "hotfix/cd-v2-hardening"
    assert token == "gh-pat-value"
    assert "gh-pat-value" not in str(data)
    assert set(data["inputs"]) == {"channel", "package_artifact_name", "caller_run_id", "caller_repo", "dispatch_id"}


def test_main_rejects_unknown_channel(monkeypatch):
    monkeypatch.setenv("GH_PAT", "x")
    monkeypatch.setattr(
        sys,
        "argv",
        ["acquire_lock.py", "--channel", "prod", "--artifact-name", "1-c", "--caller-run-id", "1", "--caller-repo", "ecmwf/x"],
    )

    with pytest.raises(SystemExit) as exit_info:
        acquire_lock.main()

    assert exit_info.value.code == 2


@pytest.mark.parametrize(
    "lock_ref, env_ref, action_path, expected",
    [
        ("v2.100", "", "", "v2.100"),
        ("", "v2", "", "v2"),
        ("", "", "/runner/_work/_actions/ecmwf/reusable-workflows/hotfix/cd-v2-hardening/cd-actions/conda", "hotfix/cd-v2-hardening"),
        # A commit SHA cannot be dispatched at, so fall back to v2
        ("0123456789abcdef0123456789abcdef01234567", "", "", "v2"),
        ("", "", "/runner/_work/_actions/ecmwf/reusable-workflows/0123456789abcdef0123456789abcdef01234567/cd-actions/conda", "v2"),
        ("", "", "/home/runner/work/reusable-workflows/reusable-workflows/cd-actions/conda", "v2"),
        ("", "", "", "v2"),
    ],
)
def test_resolve_lock_ref(monkeypatch, lock_ref, env_ref, action_path, expected):
    monkeypatch.setenv("GITHUB_ACTION_REF", env_ref)

    assert acquire_lock.resolve_lock_ref(lock_ref, action_path) == expected


def test_conda_index_lock_takes_no_credentials_as_inputs():
    workflow = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "conda-index-lock.yml").read_text())
    # PyYAML reads the "on" key as True
    inputs = (workflow.get("on") or workflow[True])["workflow_dispatch"]["inputs"]

    assert not [name for name in inputs if any(word in name.lower() for word in ("token", "password", "secret", "url"))]
    assert inputs["channel"]["options"] == ["test", "production"]
    assert workflow["permissions"] == {"contents": "read"}
    steps = workflow["jobs"]["index"]["steps"]
    assert [step["name"] for step in steps[:2]] == ["Check CD kill switch", "Validate request"]
    assert any("::add-mask::" in (step.get("run") or "") for step in steps)
