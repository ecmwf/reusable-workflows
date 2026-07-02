"""Tests for cd-actions/detect-release-type/scripts/detect.py."""

from __future__ import annotations

from conftest import import_script

detect = import_script("detect-release-type", "detect", "detect_release_type_script")

DEPLOYMENT_REGEX = r"^\d+\.\d+\.\d+$"
PRERELEASE_REGEX = r"^\d+\.\d+\.\d+-rc\d+$"


def _detect(ref_name: str, dry_run: str = "false") -> dict[str, str]:
    return detect.detect_release_type(
        ref_name, DEPLOYMENT_REGEX, PRERELEASE_REGEX, dry_run
    )


def test_deployment_tag():
    assert _detect("5.17.0") == {
        "ref_name": "5.17.0",
        "is_dry_run": "false",
        "is_prerelease": "false",
    }


def test_prerelease_tag():
    result = _detect("5.17.0-rc1")
    assert result["is_dry_run"] == "false"
    assert result["is_prerelease"] == "true"


def test_unmatched_ref_is_dry_run():
    result = _detect("feature/foo")
    assert result["is_dry_run"] == "true"
    assert result["is_prerelease"] == "false"


def test_deployment_takes_precedence_over_prerelease():
    # A ref matching both regexes classifies as a standard release.
    result = detect.detect_release_type("1.2.3", r"^\d+", r"^\d+\.\d+\.\d+$", "false")
    assert result["is_prerelease"] == "false"
    assert result["is_dry_run"] == "false"


def test_forced_dry_run_overrides_deployment():
    result = _detect("5.17.0", dry_run="true")
    assert result["is_dry_run"] == "true"
    assert result["is_prerelease"] == "false"


def test_main_writes_outputs(monkeypatch, github_output):
    monkeypatch.setenv("INPUT_REF_NAME", "5.17.0")
    monkeypatch.setenv("INPUT_DRY_RUN", "false")
    monkeypatch.setenv("DEPLOYMENT_REGEX", DEPLOYMENT_REGEX)
    monkeypatch.setenv("PRERELEASE_REGEX", PRERELEASE_REGEX)
    detect.main()
    assert github_output.read() == {
        "ref_name": "5.17.0",
        "is_dry_run": "false",
        "is_prerelease": "false",
    }
