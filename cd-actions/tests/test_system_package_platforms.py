"""Unit tests for cd-actions/lib/system_package_platforms.py."""

from __future__ import annotations

import pytest

from system_package_platforms import (
    UnknownSystemPackagePlatform,
    resolve_system_package_platform,
)

CONFIG = {
    "debian-12": {
        "os": "debian-12",
        "nexus_token_secret_prod": "NEXUS_REPO_UPLOAD_TOKEN",
        "nexus_url_secret_prod": "NEXUS_REPO_URL_DEBIAN_12",
        "nexus_token_secret_test": "NEXUS_TEST_REPO_UPLOAD_TOKEN",
        "nexus_url_secret_test": "NEXUS_TEST_REPO_URL_DEBIAN_12",
    },
    "rocky-9": {
        "os": "rocky-9.7",
        "nexus_token_secret_test": "NEXUS_TEST_REPO_UPLOAD_TOKEN",
        "nexus_url_secret_test": "NEXUS_TEST_REPO_URL_ROCKY_9",
    },
}


def test_full_resolution():
    resolved = resolve_system_package_platform("debian-12", CONFIG)
    assert resolved == {
        "container": "eccr.ecmwf.int/platform-builder/platform-builder:debian-12",
        "os": "debian-12",
        "nexus_token_secret_prod": "NEXUS_REPO_UPLOAD_TOKEN",
        "nexus_url_secret_prod": "NEXUS_REPO_URL_DEBIAN_12",
        "nexus_token_secret_test": "NEXUS_TEST_REPO_UPLOAD_TOKEN",
        "nexus_url_secret_test": "NEXUS_TEST_REPO_URL_DEBIAN_12",
    }


def test_alias_resolves_to_real_os_id():
    resolved = resolve_system_package_platform("rocky-9", CONFIG)
    assert resolved["os"] == "rocky-9.7"
    assert (
        resolved["container"]
        == "eccr.ecmwf.int/platform-builder/platform-builder:rocky-9.7"
    )


def test_missing_prod_secrets_default_to_empty():
    resolved = resolve_system_package_platform("rocky-9", CONFIG)
    assert resolved["nexus_token_secret_prod"] == ""
    assert resolved["nexus_url_secret_prod"] == ""


def test_unknown_alias_raises_with_sorted_supported_list():
    with pytest.raises(UnknownSystemPackagePlatform) as excinfo:
        resolve_system_package_platform("unknown-os", CONFIG)
    assert excinfo.value.os_alias == "unknown-os"
    assert excinfo.value.supported == "debian-12, rocky-9"
