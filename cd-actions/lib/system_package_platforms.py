"""Shared system-package platform resolution helpers."""

from __future__ import annotations

from typing import Any

CONTAINER_IMAGE_TEMPLATE = "eccr.ecmwf.int/platform-builder/platform-builder:{os_id}"


class UnknownSystemPackagePlatform(ValueError):
    """Raised when an OS alias is not present in the platform config."""

    def __init__(self, os_alias: str, supported: str):
        self.os_alias = os_alias
        self.supported = supported
        super().__init__(
            f"Unknown system-package platform '{os_alias}'. Supported: {supported}"
        )


def resolve_system_package_platform(
    os_alias: str, platforms_config: dict[str, Any]
) -> dict[str, str]:
    """Resolve an OS alias to its container image and Nexus secret names."""
    if os_alias not in platforms_config:
        supported = ", ".join(sorted(platforms_config.keys()))
        raise UnknownSystemPackagePlatform(os_alias, supported)

    platform = platforms_config[os_alias]
    os_id = platform["os"]
    return {
        "container": CONTAINER_IMAGE_TEMPLATE.format(os_id=os_id),
        "os": os_id,
        "nexus_token_secret_prod": platform.get("nexus_token_secret_prod", ""),
        "nexus_url_secret_prod": platform.get("nexus_url_secret_prod", ""),
        "nexus_token_secret_test": platform["nexus_token_secret_test"],
        "nexus_url_secret_test": platform["nexus_url_secret_test"],
    }
