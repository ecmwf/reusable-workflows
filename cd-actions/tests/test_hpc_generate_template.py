"""Unit tests for cd-actions/hpc/scripts/generate_template.py internals."""

from __future__ import annotations

import pytest

from conftest import import_script

generate_template = import_script("hpc", "generate_template", "hpc_generate_template")

BASE_ENV = {
    "GITHUB_REPOSITORY": "ecmwf/example",
    "INPUT_REF_NAME": "1.0.0",
    "STEP_CONFIG_COMPILER": "gnu-14.2.0",
    "STEP_CONFIG_COMPILER_MODULES": "gcc/14.2.0",
    "STEP_CONFIG_INSTALL_PREFIX": "/usr/local/apps/example/1.0.0",
    "STEP_CONFIG_BASE_INSTALL_PREFIX": "/usr/local/apps/example/1.0.0",
}


def _inputs(**env):
    return generate_template.read_inputs({**BASE_ENV, **env})


class TestSplitRepoRef:
    def test_full_spec(self):
        assert generate_template.split_repo_ref("owner/repo@ref") == (
            "owner",
            "repo",
            "ref",
        )

    def test_defaults(self):
        assert generate_template.split_repo_ref("repo") == ("ecmwf", "repo", "main")


class TestBuildPackagesDependencies:
    def test_dependency_cmake_options_keyed_by_repo_spec(self):
        inputs = _inputs(
            INPUT_DEPENDENCIES="ecmwf/eckit@develop\nmetkit",
            INPUT_DEPENDENCY_CMAKE_OPTIONS="ecmwf/eckit=-DENABLE_TESTS=OFF,-DFOO=BAR",
        )
        packages = generate_template.build_packages(inputs, use_ecbundle=False)

        eckit = packages[0]
        assert eckit["name"] == "eckit"
        assert eckit["owner"] == "ecmwf"
        assert eckit["ref"] == "develop"
        assert eckit["type"] == "dependency"
        assert eckit["prefix"] == "${TMPDIR}/deps/eckit"
        assert eckit["cmake_options"] == ["-DENABLE_TESTS=OFF", "-DFOO=BAR"]

        metkit = packages[1]
        assert metkit["owner"] == "ecmwf"
        assert metkit["ref"] == "main"
        assert metkit["cmake_options"] == []

    def test_options_require_exact_repo_spec_key(self):
        # The lookup key is the dependency spec without @ref — a bare name in
        # dependency_cmake_options does not match an owner-qualified dependency.
        inputs = _inputs(
            INPUT_DEPENDENCIES="ecmwf/eckit",
            INPUT_DEPENDENCY_CMAKE_OPTIONS="eckit=-DENABLE_TESTS=OFF",
        )
        packages = generate_template.build_packages(inputs, use_ecbundle=False)
        assert packages[0]["cmake_options"] == []

    def test_bare_dependency_matches_bare_key(self):
        inputs = _inputs(
            INPUT_DEPENDENCIES="eckit@develop",
            INPUT_DEPENDENCY_CMAKE_OPTIONS="eckit=-DENABLE_TESTS=OFF",
        )
        packages = generate_template.build_packages(inputs, use_ecbundle=False)
        assert packages[0]["cmake_options"] == ["-DENABLE_TESTS=OFF"]


class TestBuildPackagesMainSelection:
    def test_cmake_main_package_by_default(self):
        packages = generate_template.build_packages(_inputs(), use_ecbundle=False)
        assert [p["type"] for p in packages] == ["main"]
        assert packages[0]["ref"] == "1.0.0"

    def test_sha_used_as_ref_when_present(self):
        packages = generate_template.build_packages(
            _inputs(INPUT_SHA="abc123"), use_ecbundle=False
        )
        assert packages[0]["ref"] == "abc123"

    def test_python_version_switches_to_python_main(self):
        packages = generate_template.build_packages(
            _inputs(INPUT_PYTHON_VERSION="3.12"), use_ecbundle=False
        )
        assert [p["type"] for p in packages] == ["main-python"]

    def test_staged_build_keeps_cmake_main_alongside_python(self):
        inputs = _inputs(
            INPUT_PYTHON_VERSION="3.12",
            INPUT_STAGES='[{"name": "py312"}]',
        )
        packages = generate_template.build_packages(inputs, use_ecbundle=False)
        assert [p["type"] for p in packages] == ["main", "main-python"]

    def test_python_dependencies_precede_python_main(self):
        inputs = _inputs(
            INPUT_PYTHON_VERSION="3.12",
            INPUT_PYTHON_DEPENDENCIES="ecmwf/pyflow@develop",
        )
        packages = generate_template.build_packages(inputs, use_ecbundle=False)
        assert [p["type"] for p in packages] == ["dependency-python", "main-python"]
        assert packages[0]["name"] == "pyflow"

    def test_ecbundle_single_package(self):
        packages = generate_template.build_packages(_inputs(), use_ecbundle=True)
        assert [p["type"] for p in packages] == ["ecbundle"]
        assert "install_command" not in packages[0]


class TestReadInputs:
    def test_install_lib_dir_prepends_cmake_option(self):
        inputs = _inputs(
            INPUT_CMAKE_OPTIONS="-DENABLE_TESTS=ON",
            INPUT_INSTALL_LIB_DIR="lib64",
        )
        assert inputs.cmake_options == ["-DINSTALL_LIB_DIR=lib64", "-DENABLE_TESTS=ON"]

    def test_scalar_defaults_fill_blank_inputs(self):
        inputs = _inputs(INPUT_PARALLEL="", INPUT_QUEUE="", INPUT_NTASKS="")
        assert inputs.parallel == "64"
        assert inputs.ntasks == "1"
        assert inputs.queue == "nf"

    def test_site_empty_string_is_preserved(self):
        # INPUT_SITE uses .get() without an `or` fallback: an explicitly empty
        # site stays empty rather than defaulting.
        assert _inputs(INPUT_SITE="").site == ""
        assert _inputs().site == "aa-batch"


class TestNormalizeStages:
    def test_cmake_options_dict_rendered(self):
        stages = [{"cmake_options": {"ENABLE_TESTS": True, "-DFOO": "bar"}}]
        generate_template.normalize_stages(stages)
        assert stages[0]["name"] == "stage-0"
        assert stages[0]["cmake_options"] == ["-DENABLE_TESTS=ON", "-DFOO=bar"]
        assert stages[0]["install_command"] == ""

    def test_non_dict_cmake_options_dropped(self):
        stages = [{"name": "s", "cmake_options": "-DFOO=bar"}]
        generate_template.normalize_stages(stages)
        assert stages[0]["cmake_options"] == []
