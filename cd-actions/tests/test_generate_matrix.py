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

os.environ.setdefault("GITHUB_ACTION_PATH", str(Path(__file__).parent.parent / "load-config"))

from generate_matrix import generate_matrix  # noqa: E402


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
        assert item["runner"] == ["self-hosted", "platform-builder"]
        assert item["container"] == ""

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


class TestUnsupportedBuildType:
    def test_unsupported_type_fails(self):
        config = {
            "builds": [
                {"name": "bad", "type": "unknown-type", "config": {}}
            ]
        }
        with pytest.raises(SystemExit):
            generate_matrix(config)
