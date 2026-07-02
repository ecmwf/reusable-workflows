"""Unit tests for cd-actions/lib/conda_platforms.py."""

from __future__ import annotations

import pytest

from conftest import CD_ACTIONS_DIR
from conda_platforms import (
    conda_platform_matrix_entries,
    load_conda_platforms_config,
    matrix_summary_rows,
    parse_conda_platforms,
    validate_conda_platforms,
)

PLATFORM_CONFIG = {
    "linux-64": {"runner": ["self-hosted", "platform-builder"], "setup_conda": False},
    "osx-arm64": {"runner": ["self-hosted", "macos", "arm64"], "setup_conda": True},
    "linux-aarch64-public": {
        "runner": "ubuntu-24.04-arm",
        "conda_platform": "linux-aarch64",
    },
}


class TestParseCondaPlatforms:
    def test_none_uses_default(self):
        assert parse_conda_platforms(None) == ["linux-64"]

    def test_empty_string_uses_default(self):
        assert parse_conda_platforms("  ") == ["linux-64"]

    def test_list_passthrough(self):
        assert parse_conda_platforms(["linux-64", "osx-arm64"]) == [
            "linux-64",
            "osx-arm64",
        ]

    def test_line_separated_string(self):
        assert parse_conda_platforms("linux-64\nosx-arm64") == [
            "linux-64",
            "osx-arm64",
        ]

    def test_yaml_flow_list_string(self):
        assert parse_conda_platforms("[linux-64, osx-arm64]") == [
            "linux-64",
            "osx-arm64",
        ]

    def test_duplicates_removed(self):
        assert parse_conda_platforms(["linux-64", "osx-arm64", "linux-64"]) == [
            "linux-64",
            "osx-arm64",
        ]

    def test_blank_items_dropped(self):
        assert parse_conda_platforms(["", "linux-64", "  "]) == ["linux-64"]

    def test_invalid_type_fails(self):
        with pytest.raises(ValueError, match="list or line-separated string"):
            parse_conda_platforms(42)


class TestValidateCondaPlatforms:
    def test_valid(self):
        assert validate_conda_platforms(["linux-64"], PLATFORM_CONFIG) == ["linux-64"]

    def test_unsupported_fails(self):
        with pytest.raises(ValueError, match="Unsupported Conda platform 'linux-ppc64le'"):
            validate_conda_platforms(["linux-ppc64le"], PLATFORM_CONFIG)


class TestMatrixEntries:
    def test_single_platform_keeps_name(self):
        entries = conda_platform_matrix_entries("pkg", ["linux-64"], PLATFORM_CONFIG)
        assert len(entries) == 1
        assert entries[0]["name"] == "pkg"
        assert entries[0]["conda_platform"] == "linux-64"
        assert entries[0]["setup_conda"] is False

    def test_multi_platform_suffixes_names(self):
        entries = conda_platform_matrix_entries(
            "pkg", ["linux-64", "osx-arm64"], PLATFORM_CONFIG
        )
        assert [e["name"] for e in entries] == ["pkg-linux-64", "pkg-osx-arm64"]

    def test_alias_resolves_conda_platform(self):
        entries = conda_platform_matrix_entries(
            "pkg", ["linux-aarch64-public"], PLATFORM_CONFIG
        )
        assert entries[0]["conda_platform_key"] == "linux-aarch64-public"
        assert entries[0]["conda_platform"] == "linux-aarch64"
        assert entries[0]["setup_conda"] is True  # default when unspecified


class TestMatrixSummaryRows:
    def test_rows(self):
        entries = conda_platform_matrix_entries("pkg", ["linux-64"], PLATFORM_CONFIG)
        rows = matrix_summary_rows({"include": entries})
        assert rows == [
            {
                "name": "pkg",
                "conda_platform_key": "linux-64",
                "conda_platform": "linux-64",
                "runner": '["self-hosted", "platform-builder"]',
                "artifact_name": "<run-id>-pkg",
            }
        ]


class TestLoadCondaPlatformsConfig:
    def test_loads_repo_config(self):
        config = load_conda_platforms_config(
            CD_ACTIONS_DIR / "config" / "platforms-conda.yml"
        )
        assert "linux-64" in config

    def test_non_mapping_fails(self, tmp_path):
        path = tmp_path / "bad.yml"
        path.write_text("- just\n- a\n- list\n")
        with pytest.raises(ValueError, match="must be a mapping"):
            load_conda_platforms_config(path)
