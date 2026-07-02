"""Tests for cd-actions/resolve-system-package-platform/scripts/resolve.py."""

from __future__ import annotations

import pytest

from conftest import import_script

resolve = import_script(
    "resolve-system-package-platform", "resolve", "resolve_system_package_platform"
)


@pytest.fixture(autouse=True)
def _action_env(action_env):
    action_env("resolve-system-package-platform")


class TestResolvePlatform:
    def _run(self, monkeypatch, github_output, os_input: str) -> dict[str, str]:
        monkeypatch.setenv("INPUT_OS", os_input)
        resolve.main()
        return github_output.read()

    def test_debian_12(self, monkeypatch, github_output):
        result = self._run(monkeypatch, github_output, "debian-12")
        assert result["os"] == "debian-12"
        assert (
            result["container"]
            == "eccr.ecmwf.int/platform-builder/platform-builder:debian-12"
        )
        assert result["nexus_token_secret_prod"] == "NEXUS_REPO_UPLOAD_TOKEN"
        assert result["nexus_url_secret_prod"] == "NEXUS_REPO_URL_DEBIAN_12"
        assert result["nexus_token_secret_test"] == "NEXUS_TEST_REPO_UPLOAD_TOKEN"
        assert result["nexus_url_secret_test"] == "NEXUS_TEST_REPO_URL_DEBIAN_12"

    def test_ubuntu_2204_test_only(self, monkeypatch, github_output):
        result = self._run(monkeypatch, github_output, "ubuntu-22.04")
        assert result["os"] == "ubuntu-22.04"
        assert result["nexus_token_secret_prod"] == ""
        assert result["nexus_url_secret_prod"] == ""
        assert result["nexus_token_secret_test"] == "NEXUS_TEST_REPO_UPLOAD_TOKEN"

    def test_rocky_9_alias(self, monkeypatch, github_output):
        result = self._run(monkeypatch, github_output, "rocky-9")
        assert result["os"] == "rocky-9.7"

    def test_unknown_os(self, monkeypatch, github_output):
        monkeypatch.setenv("INPUT_OS", "unknown-os")
        with pytest.raises(SystemExit):
            resolve.main()
