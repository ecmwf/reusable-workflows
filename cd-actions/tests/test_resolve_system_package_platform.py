"""Tests for cd-actions/resolve-system-package-platform/scripts/resolve.py."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).parent.parent / "resolve-system-package-platform" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

os.environ.setdefault(
    "GITHUB_ACTION_PATH",
    str(Path(__file__).parent.parent / "resolve-system-package-platform"),
)

import resolve  # noqa: E402


class TestResolvePlatform:
    def _run(self, os_input: str) -> dict[str, str]:
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            output_path = f.name
        os.environ["INPUT_OS"] = os_input
        os.environ["GITHUB_OUTPUT"] = output_path
        try:
            resolve.main()
            result = {}
            with open(output_path) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line:
                        key, value = line.split("=", 1)
                        result[key] = value
            return result
        finally:
            os.unlink(output_path)

    def test_debian_12(self):
        result = self._run("debian-12")
        assert result["os"] == "debian-12"
        assert (
            result["container"]
            == "eccr.ecmwf.int/platform-builder/platform-builder:debian-12"
        )
        assert result["nexus_token_secret_prod"] == "NEXUS_REPO_UPLOAD_TOKEN"
        assert result["nexus_url_secret_prod"] == "NEXUS_REPO_URL_DEBIAN_12"
        assert result["nexus_token_secret_test"] == "NEXUS_TEST_REPO_UPLOAD_TOKEN"
        assert result["nexus_url_secret_test"] == "NEXUS_TEST_REPO_URL_DEBIAN_12"

    def test_ubuntu_2204_test_only(self):
        result = self._run("ubuntu-22.04")
        assert result["os"] == "ubuntu-22.04"
        assert result["nexus_token_secret_prod"] == ""
        assert result["nexus_url_secret_prod"] == ""
        assert result["nexus_token_secret_test"] == "NEXUS_TEST_REPO_UPLOAD_TOKEN"

    def test_rocky_9_alias(self):
        result = self._run("rocky-9")
        assert result["os"] == "rocky-9.7"

    def test_unknown_os(self):
        os.environ["INPUT_OS"] = "unknown-os"
        os.environ["GITHUB_OUTPUT"] = "/dev/null"
        with pytest.raises(SystemExit):
            resolve.main()
