"""Tests for cd-actions/load-config/scripts/generate_matrix.py."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
import yaml

# Make the script importable and ensure it can find cd-actions/lib.
SCRIPT_DIR = Path(__file__).parent.parent / "load-config" / "scripts"
LIB_DIR = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(LIB_DIR))

from generate_matrix import generate_matrix
from generate_matrix import generate_hpc_sync_tag_matrix

os.environ.setdefault("GITHUB_ACTION_PATH", str(Path(__file__).parent.parent / "load-config"))


FIXTURES = Path(__file__).parent / "fixtures"


def _load_config(name: str) -> dict:
    with open(FIXTURES / name) as f:
        return yaml.safe_load(f)


def _find_item(matrix: dict, name: str) -> dict:
    for item in matrix["include"]:
        if item["name"] == name:
            return item
    raise KeyError(name)


class TestGenerateMatrixBasic:
    def test_conda_defaults_and_overrides(self):
        config = _load_config("cd-config-basic.yml")
        matrix = generate_matrix(config)
        item = _find_item(matrix, "conda-build")

        # Defaults from cd-actions/defaults.yml
        assert item["conda_dir"] == "./conda"
        # common_config merged channels
        assert item["channels"] == "ecmwf"
        assert item["conda_build_args"] == "--no-anaconda-upload"
        assert item["skip_installation_test"] == "true"
        assert item["conda_platform"] == "linux-64"
        assert item["runner"] == ["self-hosted", "platform-builder"]
        assert item["container"] == ""

    def test_conda_multi_platform_expansion(self):
        config = {
            "builds": [
                {
                    "name": "conda",
                    "type": "conda",
                    "config": {
                        "platforms": ["linux-64", "linux-aarch64", "osx-arm64"],
                    },
                }
            ]
        }
        matrix = generate_matrix(config)

        assert [item["name"] for item in matrix["include"]] == [
            "conda-linux-64",
            "conda-linux-aarch64",
            "conda-osx-arm64",
        ]
        assert [item["conda_platform"] for item in matrix["include"]] == [
            "linux-64",
            "linux-aarch64",
            "osx-arm64",
        ]
        assert matrix["include"][0]["runner"] == ["self-hosted", "platform-builder"]
        assert matrix["include"][1]["runner"] == "platform-builder-ubuntu-2404-arm64-000"
        assert matrix["include"][2]["runner"] == ["self-hosted", "macos", "arm64"]

    def test_conda_default_channels_include_public_nexus(self):
        config = {
            "builds": [
                {
                    "name": "conda",
                    "type": "conda",
                    "config": {},
                }
            ]
        }
        matrix = generate_matrix(config)
        # TEMPORARY: forward prod nexus -> test nexus (revert me)
        assert (
            matrix["include"][0]["channels"]
            == "conda-forge\nhttps://nexus-test.ecmwf.int/repository/conda-ecmwf-public"
        )

    def test_conda_platform_alias_can_override_conda_target(self):
        config = {
            "builds": [
                {
                    "name": "conda",
                    "type": "conda",
                    "config": {"platforms": ["linux-aarch64-public"]},
                }
            ]
        }
        matrix = generate_matrix(config)
        item = matrix["include"][0]

        assert item["name"] == "conda"
        assert item["conda_platform_key"] == "linux-aarch64-public"
        assert item["conda_platform"] == "linux-aarch64"
        assert item["runner"] == "ubuntu-24.04-arm"
        assert item["setup_conda"] is True

    def test_conda_multi_platform_alias_name_keeps_requested_platform(self):
        config = {
            "builds": [
                {
                    "name": "conda",
                    "type": "conda",
                    "config": {"platforms": ["linux-64", "linux-aarch64-public"]},
                }
            ]
        }
        matrix = generate_matrix(config)

        assert [item["name"] for item in matrix["include"]] == [
            "conda-linux-64",
            "conda-linux-aarch64-public",
        ]
        assert [item["conda_platform"] for item in matrix["include"]] == [
            "linux-64",
            "linux-aarch64",
        ]

    def test_conda_duplicate_platforms_are_deduplicated(self):
        config = {
            "builds": [
                {
                    "name": "conda",
                    "type": "conda",
                    "config": {"platforms": ["linux-64", "linux-aarch64", "linux-64"]},
                }
            ]
        }
        matrix = generate_matrix(config)
        assert [item["conda_platform"] for item in matrix["include"]] == [
            "linux-64",
            "linux-aarch64",
        ]

    def test_unsupported_conda_platform_fails(self):
        config = {
            "builds": [
                {"name": "bad", "type": "conda", "config": {"platforms": ["linux-ppc64le"]}}
            ]
        }
        with pytest.raises(SystemExit):
            generate_matrix(config)

    def test_python_pypi(self):
        config = _load_config("cd-config-basic.yml")
        matrix = generate_matrix(config)
        item = _find_item(matrix, "python-pypi-build")

        assert item["working_directory"] == "./python"
        assert item["env_vars"] == "CTEST_PARALLEL_LEVEL=8\nFOO=bar"
        assert item["buildargs"] == ""

    def test_hpc(self):
        config = _load_config("cd-config-basic.yml")
        matrix = generate_matrix(config)
        item = _find_item(matrix, "hpc-build")

        # Per-build platform overrides common_config
        assert item["platform"] == "intel-2025.0.1"
        # common_config self_test: false
        assert item["self_test"] == "false"
        assert item["cmake_options"] == "-DENABLE_TESTS=ON\n-DCMAKE_BUILD_TYPE=Release"
        assert (
            item["dependency_cmake_options"]
            == "-Decmwf/eckit=-DENABLE_TESTS=ON,-DENABLE_BUILD_TOOLS=OFF"
        )
        assert json.loads(item["stages"]) == [
            {"name": "py312", "modules": ["python3/3.12"]}
        ]
        assert item["runner"] == ["self-hosted", "linux", "hpc"]

    def test_tarball(self):
        config = _load_config("cd-config-basic.yml")
        matrix = generate_matrix(config)
        item = _find_item(matrix, "tarball-build")

        assert item["confluence_space"] == "MAGP"
        assert item["confluence_page_title"] == "Releases"
        assert item["ecbuild_version"] == ""
        assert item["cmake_options"] == ""

    def test_system_package(self):
        config = _load_config("cd-config-basic.yml")
        matrix = generate_matrix(config)
        item = _find_item(matrix, "debian-system-package")

        assert item["os"] == "debian-12"
        assert (
            item["container"]
            == "eccr.ecmwf.int/platform-builder/platform-builder:debian-12"
        )
        assert item["package_deps"] == "libfoo, libbar"
        assert item["cmake_options"] == "-DENABLE_TESTS=OFF"
        assert item["build_type"] == "Debug"
        assert item["nexus_token_secret_prod"] == "NEXUS_REPO_UPLOAD_TOKEN"
        assert item["nexus_url_secret_prod"] == "NEXUS_REPO_URL_DEBIAN_12"
        assert item["nexus_token_secret_test"] == "NEXUS_TEST_REPO_UPLOAD_TOKEN"
        assert item["nexus_url_secret_test"] == "NEXUS_TEST_REPO_URL_DEBIAN_12"
        assert item["runner"] == ["self-hosted", "platform-builder-docker-xl"]


class TestGenerateMatrixSystemPackage:
    def test_platform_resolution(self):
        config = _load_config("cd-config-system-package.yml")
        matrix = generate_matrix(config)

        debian = _find_item(matrix, "debian-11-build")
        assert debian["os"] == "debian-11"
        assert debian["nexus_token_secret_prod"] == "NEXUS_REPO_UPLOAD_TOKEN"

        ubuntu = _find_item(matrix, "ubuntu-2204-build")
        assert ubuntu["os"] == "ubuntu-22.04"
        assert ubuntu["nexus_token_secret_prod"] == ""
        assert ubuntu["nexus_url_secret_prod"] == ""

        rocky = _find_item(matrix, "rocky-9-build")
        assert rocky["os"] == "rocky-9.7"

    def test_unknown_os_fails(self):
        config = {
            "builds": [
                {"name": "bad", "type": "system-package", "config": {"os": "unknown-os"}}
            ]
        }
        with pytest.raises(SystemExit):
            generate_matrix(config)


class TestGenerateMatrixHpcStaged:
    def test_stages_serialization(self):
        config = _load_config("cd-config-hpc-staged.yml")
        matrix = generate_matrix(config)
        item = _find_item(matrix, "hpc-staged-build")

        stages = json.loads(item["stages"])
        assert len(stages) == 2
        assert stages[0]["name"] == "py312"
        assert stages[0]["modules"] == ["python3/3.12", "boost/1.87"]
        assert stages[0]["cmake_options"] == {"Python3_ROOT": "/path/to/python"}
        assert stages[1]["name"] == "py313"


def _hpc_build(name: str, **config) -> dict:
    return {"name": name, "type": "hpc", "config": config}


class TestHpcSyncTagMatrix:
    @pytest.fixture(autouse=True)
    def _repo_env(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPOSITORY", "ecmwf/test-repo")

    def _sync_tag_matrix(self, config: dict) -> dict:
        return generate_hpc_sync_tag_matrix(generate_matrix(config))

    def test_multi_compiler_builds_dedupe_to_one_entry(self):
        config = _load_config("cd-config-hpc-multi-compiler.yml")
        matrix = self._sync_tag_matrix(config)

        assert len(matrix["include"]) == 1
        entry = matrix["include"][0]
        assert entry["name"] == "sync-tag-test-repo-aa-batch"
        assert entry["runner"] == ["self-hosted", "linux", "hpc"]
        assert entry["module_name"] == ""
        assert entry["site"] == "aa-batch"
        assert entry["module_tag_name"] == ""
        assert entry["sync_module"] == "true"
        assert entry["tag_module"] == "true"
        assert entry["queue"] == ""
        assert entry["workdir"] == ""
        assert entry["output_dir"] == ""

    def test_submission_options_are_carried_through(self):
        config = {
            "builds": [
                _hpc_build("a", queue="deploy", workdir="/w", output_dir="/o"),
            ]
        }
        matrix = self._sync_tag_matrix(config)

        assert len(matrix["include"]) == 1
        entry = matrix["include"][0]
        assert entry["queue"] == "deploy"
        assert entry["workdir"] == "/w"
        assert entry["output_dir"] == "/o"

    def test_submission_options_keep_first_builds_values_on_dedup(self):
        config = {
            "builds": [
                _hpc_build("a", queue="deploy"),
                _hpc_build("b", queue="ng", workdir="/w"),
            ]
        }
        matrix = self._sync_tag_matrix(config)

        assert len(matrix["include"]) == 1
        entry = matrix["include"][0]
        assert entry["queue"] == "deploy"
        assert entry["workdir"] == ""

    def test_distinct_modules_and_sites_get_separate_entries(self):
        config = {
            "builds": [
                _hpc_build("a", module_name="mod-a"),
                _hpc_build("b", module_name="mod-b"),
                _hpc_build("c", site="ab-batch"),
            ]
        }
        matrix = self._sync_tag_matrix(config)

        assert [(e["module_name"], e["site"]) for e in matrix["include"]] == [
            ("mod-a", "aa-batch"),
            ("mod-b", "aa-batch"),
            ("", "ab-batch"),
        ]

    def test_explicit_repo_module_name_dedupes_with_default(self):
        config = {
            "builds": [
                _hpc_build("a", module_name="test-repo"),
                _hpc_build("b"),
            ]
        }
        matrix = self._sync_tag_matrix(config)

        assert len(matrix["include"]) == 1
        assert matrix["include"][0]["module_name"] == ""

    def test_repo_module_name_is_stripped_before_deduplication(self):
        config = {
            "builds": [
                _hpc_build("a", module_name=" test-repo "),
                _hpc_build("b"),
            ]
        }
        matrix = self._sync_tag_matrix(config)

        assert len(matrix["include"]) == 1
        assert matrix["include"][0]["module_name"] == ""

    def test_flags_are_or_merged_across_builds(self):
        config = {
            "builds": [
                _hpc_build("a", sync_module=True, tag_module=False),
                _hpc_build("b", sync_module=False, tag_module=True),
            ]
        }
        matrix = self._sync_tag_matrix(config)

        assert len(matrix["include"]) == 1
        entry = matrix["include"][0]
        assert entry["sync_module"] == "true"
        assert entry["tag_module"] == "true"

    def test_builds_with_sync_and_tag_disabled_are_excluded(self):
        config = {
            "builds": [_hpc_build("a", sync_module=False, tag_module=False)]
        }
        matrix = self._sync_tag_matrix(config)

        assert matrix["include"] == []

    def test_distinct_tag_names_get_separate_entries(self):
        config = {
            "builds": [
                _hpc_build("a", module_tag_name="rc"),
                _hpc_build("b"),
            ]
        }
        matrix = self._sync_tag_matrix(config)

        assert [(e["name"], e["module_tag_name"]) for e in matrix["include"]] == [
            ("sync-tag-test-repo-aa-batch-rc", "rc"),
            ("sync-tag-test-repo-aa-batch", ""),
        ]

    def test_explicit_new_tag_is_preserved(self):
        config = {"builds": [_hpc_build("a", module_tag_name="new")]}
        matrix = self._sync_tag_matrix(config)

        assert len(matrix["include"]) == 1
        entry = matrix["include"][0]
        assert entry["name"] == "sync-tag-test-repo-aa-batch-new"
        assert entry["module_tag_name"] == "new"

    def test_tag_name_is_stripped_before_deduplication(self):
        config = {
            "builds": [
                _hpc_build("a", module_tag_name=" new "),
                _hpc_build("b", module_tag_name="new"),
            ]
        }
        matrix = self._sync_tag_matrix(config)

        assert len(matrix["include"]) == 1
        entry = matrix["include"][0]
        assert entry["name"] == "sync-tag-test-repo-aa-batch-new"
        assert entry["module_tag_name"] == "new"

    def test_explicit_new_tag_does_not_dedupe_with_empty(self):
        config = {
            "builds": [
                _hpc_build("a", module_tag_name="new"),
                _hpc_build("b"),
            ]
        }
        matrix = self._sync_tag_matrix(config)

        assert len(matrix["include"]) == 2
        assert [entry["module_tag_name"] for entry in matrix["include"]] == [
            "new",
            "",
        ]

    def test_non_hpc_builds_produce_empty_matrix(self):
        config = {
            "builds": [{"name": "conda", "type": "conda", "config": {}}]
        }
        matrix = self._sync_tag_matrix(config)

        assert matrix["include"] == []


class TestUnsupportedBuildType:
    def test_unsupported_type_fails(self):
        config = {
            "builds": [
                {"name": "bad", "type": "unknown-type", "config": {}}
            ]
        }
        with pytest.raises(SystemExit):
            generate_matrix(config)
