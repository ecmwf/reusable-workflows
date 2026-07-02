"""Tests for cd-actions/resolve-conda-platforms/scripts/resolve.py."""

from __future__ import annotations

import json
import os

import pytest

from conftest import import_script

# The script resolves ACTION_PATH at import time; its __file__-based fallback
# is only correct if GITHUB_ACTION_PATH is not set to something else.
assert "GITHUB_ACTION_PATH" not in os.environ or os.environ[
    "GITHUB_ACTION_PATH"
].endswith("resolve-conda-platforms")
resolve = import_script("resolve-conda-platforms", "resolve", "resolve_conda_platforms")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in ("INPUT_NAME", "INPUT_PLATFORMS"):
        monkeypatch.delenv(key, raising=False)


def _run(monkeypatch, github_output, **env) -> dict:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    resolve.main()
    return json.loads(github_output.read()["matrix"])


def test_default_platform(monkeypatch, github_output):
    matrix = _run(monkeypatch, github_output)
    assert matrix == {
        "include": [
            {
                "name": "conda",
                "type": "conda",
                "conda_platform_key": "linux-64",
                "conda_platform": "linux-64",
                "runner": ["self-hosted", "platform-builder"],
                "setup_conda": False,
                "container": "",
            }
        ]
    }


def test_multi_platform_suffixes_names(monkeypatch, github_output):
    matrix = _run(
        monkeypatch,
        github_output,
        INPUT_NAME="mypackage",
        INPUT_PLATFORMS="linux-64\nosx-arm64",
    )
    assert [entry["name"] for entry in matrix["include"]] == [
        "mypackage-linux-64",
        "mypackage-osx-arm64",
    ]
    assert matrix["include"][1]["runner"] == ["self-hosted", "macos", "arm64"]
    assert matrix["include"][1]["setup_conda"] is True


def test_public_alias_maps_to_real_conda_platform(monkeypatch, github_output):
    matrix = _run(monkeypatch, github_output, INPUT_PLATFORMS="linux-aarch64-public")
    entry = matrix["include"][0]
    assert entry["conda_platform_key"] == "linux-aarch64-public"
    assert entry["conda_platform"] == "linux-aarch64"
    assert entry["runner"] == "ubuntu-24.04-arm"
    assert entry["setup_conda"] is True


def test_unsupported_platform_fails(monkeypatch, github_output):
    monkeypatch.setenv("INPUT_PLATFORMS", "linux-ppc64le")
    with pytest.raises(SystemExit):
        resolve.main()
