"""Tests for cd-actions/conda/scripts/acquire_lock.py."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

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
