"""Tests for install prefix resolution in cd-actions/hpc/scripts/parse_config.py."""

from __future__ import annotations

import sys
from pathlib import Path

ACTION_DIR = Path(__file__).parent.parent / "hpc"
sys.path.insert(0, str(ACTION_DIR / "scripts"))

import parse_config


def _install_prefix(monkeypatch, tmp_path, **inputs) -> str:
    output = tmp_path / "github_output"
    env = {
        "GITHUB_ACTION_PATH": str(ACTION_DIR),
        "GITHUB_OUTPUT": str(output),
        "GITHUB_REPOSITORY": "ecmwf/eckit",
        "INPUT_PLATFORM": "gnu-15.2.0",
        "INPUT_REF_NAME": "develop",
    }
    env.update({f"INPUT_{key.upper()}": value for key, value in inputs.items()})
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    parse_config.main()

    outputs = dict(line.split("=", 1) for line in output.read_text().splitlines())
    return outputs["install_prefix"]


def test_default_prefix_uses_ref(monkeypatch, tmp_path):
    assert _install_prefix(monkeypatch, tmp_path) == "/usr/local/apps/eckit/develop"


def test_nightly_prefix(monkeypatch, tmp_path):
    assert _install_prefix(monkeypatch, tmp_path, nightly="true") == "/usr/local/apps/eckit/nightly"


def test_explicit_prefix_wins_over_nightly(monkeypatch, tmp_path):
    prefix = _install_prefix(
        monkeypatch, tmp_path, nightly="true", install_prefix="/usr/local/apps/eckit/versions/nightly/1.2.3"
    )

    assert prefix == "/usr/local/apps/eckit/versions/nightly/1.2.3"


def test_nightly_dry_run_install_stays_in_scratch(monkeypatch, tmp_path):
    prefix = _install_prefix(monkeypatch, tmp_path, nightly="true", dry_run="true", dry_run_install="true")

    assert prefix == "${SCRATCH}/dry-run-install/eckit/develop"
