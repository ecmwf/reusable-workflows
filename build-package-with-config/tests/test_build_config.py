"""Tests for build-package-with-config build configuration merging."""

import json
import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from build_config import (
    apply_os_overrides,
    main_merge_config,
    main_parse_repository,
    merge_dependencies,
    parse_repository,
    pop_python_version,
)  # noqa: E402


def test_no_overrides_key_is_noop():
    config = {"dependencies": "ecmwf/ecbuild", "python_version": "3.11"}

    assert apply_os_overrides(config, "rocky-8.6") == {
        "dependencies": "ecmwf/ecbuild",
        "python_version": "3.11",
    }


def test_matching_override_shallow_merges_over_base():
    config = {
        "dependencies": "ecmwf/ecbuild",
        "python_version": "3.11",
        "cmake_options": "-DENABLE_TESTS=ON",
        "overrides": {"rocky-8.6": {"python_version": "3.10"}},
    }

    assert apply_os_overrides(config, "rocky-8.6") == {
        "dependencies": "ecmwf/ecbuild",
        "python_version": "3.10",
        "cmake_options": "-DENABLE_TESTS=ON",
    }


def test_override_can_add_new_key():
    config = {
        "python_version": "3.11",
        "overrides": {"macos-13-arm": {"cmake_options": "-DENABLE_TESTS=OFF"}},
    }

    assert apply_os_overrides(config, "macos-13-arm") == {
        "python_version": "3.11",
        "cmake_options": "-DENABLE_TESTS=OFF",
    }


def test_non_matching_sections_are_dropped():
    config = {
        "python_version": "3.11",
        "overrides": {"rocky-8.6": {"python_version": "3.10"}},
    }

    assert apply_os_overrides(config, "ubuntu-22.04") == {"python_version": "3.11"}


def test_empty_matrix_os_matches_nothing():
    config = {
        "python_version": "3.11",
        "overrides": {"rocky-8.6": {"python_version": "3.10"}},
    }

    assert apply_os_overrides(config, "") == {"python_version": "3.11"}


def test_null_overrides_treated_as_absent():
    assert apply_os_overrides({"overrides": None, "parallel": 8}, "rocky-8.6") == {
        "parallel": 8
    }


def test_null_os_section_is_noop():
    config = {"python_version": "3.11", "overrides": {"rocky-8.6": None}}

    assert apply_os_overrides(config, "rocky-8.6") == {"python_version": "3.11"}


@pytest.mark.parametrize("value", ["rocky-8.6", ["rocky-8.6"], 3])
def test_overrides_must_be_a_mapping(value):
    with pytest.raises(ValueError, match="overrides"):
        apply_os_overrides({"overrides": value}, "rocky-8.6")


@pytest.mark.parametrize("matrix_os", ["rocky-8.6", "ubuntu-22.04"])
def test_os_sections_must_be_mappings(matrix_os):
    with pytest.raises(ValueError, match="overrides"):
        apply_os_overrides({"overrides": {"rocky-8.6": "3.10"}}, matrix_os)


@pytest.mark.parametrize("os_name", ["", 3.14])
def test_override_keys_must_be_nonempty_strings(os_name):
    with pytest.raises(ValueError, match="overrides"):
        apply_os_overrides({"overrides": {os_name: {"python_version": "3.10"}}}, "rocky-8.6")


def test_nested_overrides_rejected():
    config = {"overrides": {"rocky-8.6": {"overrides": {"rocky-8.6": {}}}}}

    with pytest.raises(ValueError, match="nested"):
        apply_os_overrides(config, "rocky-8.6")


@pytest.mark.parametrize("config", [{}, {"python_version": None}, {"python_version": ""}])
def test_missing_none_or_empty_python_version_means_system(config):
    assert pop_python_version(config) == ""
    assert "python_version" not in config


def test_quoted_python_version_is_returned_stripped():
    config = {"python_version": " 3.10 "}

    assert pop_python_version(config) == "3.10"
    assert "python_version" not in config


@pytest.mark.parametrize("value", [3.1, 3.11, 3])
def test_unquoted_python_version_fails_clearly(value):
    with pytest.raises(ValueError, match="quoted"):
        pop_python_version({"python_version": value})


def test_overridden_unquoted_python_version_fails_clearly():
    config = {
        "python_version": "3.11",
        "overrides": {"rocky-8.6": {"python_version": 3.1}},
    }
    apply_os_overrides(config, "rocky-8.6")

    with pytest.raises(ValueError, match="quoted"):
        pop_python_version(config)


@pytest.mark.parametrize(
    ("repository", "expected"),
    [
        ("ecbuild:ecmwf/ecbuild@develop", ("ecmwf/ecbuild", "develop")),
        ("ecmwf/ecbuild@3.8.0", ("ecmwf/ecbuild", "3.8.0")),
        ("ecmwf/ecbuild/some/subdir@main", ("ecmwf/ecbuild", "main")),
        ("ecmwf/ecbuild@", ("ecmwf/ecbuild", "")),
    ],
)
def test_parse_repository(repository, expected):
    assert parse_repository(repository) == expected


def test_merge_dependencies_input_overrides_config_by_repo():
    merged = merge_dependencies(
        "ecmwf/ecbuild@develop\necmwf/eckit@develop",
        "ecmwf/eckit@feature/x",
    )

    assert merged == "ecmwf/ecbuild@develop\necmwf/eckit@feature/x"


def test_merge_dependencies_appends_new_entries():
    merged = merge_dependencies("ecmwf/ecbuild@develop", "ecmwf/eckit@develop")

    assert merged == "ecmwf/ecbuild@develop\necmwf/eckit@develop"


def test_merge_dependencies_keeps_refless_entries_bare():
    merged = merge_dependencies("ecmwf/ecbuild@develop", "ecmwf/ecbuild")

    assert merged == "ecmwf/ecbuild"


def test_merge_dependencies_with_empty_config():
    assert merge_dependencies("", "ecmwf/eckit@develop") == "ecmwf/eckit@develop"


def _read_github_output(path):
    outputs = {}
    lines = path.read_text().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.endswith("<<EOF"):
            key = line[: -len("<<EOF")]
            value_lines = []
            i += 1
            while lines[i] != "EOF":
                value_lines.append(lines[i])
                i += 1
            outputs[key] = "\n".join(value_lines)
        else:
            key, value = line.split("=", 1)
            outputs[key] = value
        i += 1
    return outputs


def _run_merge_config(monkeypatch, tmp_path, **env):
    defaults = {
        "INPUT_BUILD_PACKAGE_INPUTS": "",
        "INPUT_GITHUB_TOKEN": "",
        "INPUT_BUILD_CONFIG": "",
        "INPUT_BUILD_CONFIG_KEY": "",
        "INPUT_BUILD_DEPENDENCIES": "",
        "INPUT_PYTHON_VERSION": "",
        "INPUT_PYTHON_REQUIREMENTS": "",
        "MATRIX_OS": "",
        "SELF_COVERAGE": "false",
    }
    defaults.update(env)
    output_path = tmp_path / "github_output"
    defaults["GITHUB_OUTPUT"] = str(output_path)
    for key, value in defaults.items():
        monkeypatch.setenv(key, value)

    main_merge_config()

    outputs = _read_github_output(output_path)
    outputs["config"] = json.loads(outputs["config"])
    return outputs


def test_main_parse_repository_writes_outputs(monkeypatch, tmp_path):
    output_path = tmp_path / "github_output"
    monkeypatch.setenv("INPUT_REPOSITORY", "ecbuild:ecmwf/ecbuild@develop")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))

    main_parse_repository()

    assert _read_github_output(output_path) == {
        "repo": "ecmwf/ecbuild",
        "ref": "develop",
    }


def test_merge_config_without_config_file(monkeypatch, tmp_path):
    outputs = _run_merge_config(
        monkeypatch,
        tmp_path,
        INPUT_BUILD_PACKAGE_INPUTS="self_build: false",
        INPUT_GITHUB_TOKEN="token123",
    )

    assert outputs["config"] == {
        "self_build": False,
        "github_token": "token123",
        "self_coverage": "false",
    }
    assert outputs["python_version"] == ""
    assert outputs["python_requirements"] == ""


def test_merge_config_combines_config_key_section_with_inputs(monkeypatch, tmp_path):
    config_file = tmp_path / "build-config.yml"
    config_file.write_text(
        "ci:\n"
        "  cmake_options: -DENABLE_TESTS=ON\n"
        "  dependencies: ecmwf/ecbuild@develop\n"
        '  python_version: "3.11"\n'
        "  overrides:\n"
        "    rocky-8.6:\n"
        '      python_version: "3.10"\n'
    )

    outputs = _run_merge_config(
        monkeypatch,
        tmp_path,
        INPUT_BUILD_CONFIG=str(config_file),
        INPUT_BUILD_CONFIG_KEY="ci",
        MATRIX_OS="rocky-8.6",
        INPUT_BUILD_PACKAGE_INPUTS="cmake_options: -DENABLE_TESTS=OFF",
        SELF_COVERAGE="true",
    )

    assert outputs["python_version"] == "3.10"
    assert outputs["config"] == {
        "dependencies": "ecmwf/ecbuild@develop",
        "cmake_options": (
            "-DENABLE_TESTS=OFF -DPython3_EXECUTABLE=$RUNNER_TEMP/bpvenv/bin/python"
        ),
        "self_coverage": "true",
    }


def test_merge_config_without_config_key_uses_whole_file(monkeypatch, tmp_path):
    config_file = tmp_path / "build-config.yml"
    config_file.write_text("parallel: 8\n")

    outputs = _run_merge_config(
        monkeypatch, tmp_path, INPUT_BUILD_CONFIG=str(config_file)
    )

    assert outputs["config"] == {"parallel": 8, "self_coverage": "false"}


def test_merge_config_input_dependencies_take_precedence(monkeypatch, tmp_path):
    config_file = tmp_path / "build-config.yml"
    config_file.write_text(
        "dependencies: |\n"
        "  ecmwf/ecbuild@develop\n"
        "  ecmwf/eckit@develop\n"
    )

    outputs = _run_merge_config(
        monkeypatch,
        tmp_path,
        INPUT_BUILD_CONFIG=str(config_file),
        INPUT_BUILD_DEPENDENCIES="ecmwf/eckit@feature/x",
    )

    assert outputs["config"]["dependencies"] == (
        "ecmwf/ecbuild@develop\necmwf/eckit@feature/x"
    )


def test_merge_config_python_version_input_beats_config(monkeypatch, tmp_path):
    config_file = tmp_path / "build-config.yml"
    config_file.write_text('python_version: "3.11"\n')

    outputs = _run_merge_config(
        monkeypatch,
        tmp_path,
        INPUT_BUILD_CONFIG=str(config_file),
        INPUT_PYTHON_VERSION="3.12",
    )

    assert outputs["python_version"] == "3.12"
    assert "python_version" not in outputs["config"]


def test_merge_config_python_requirements_adds_cmake_option(monkeypatch, tmp_path):
    config_file = tmp_path / "build-config.yml"
    config_file.write_text("python_requirements: requirements.txt\n")

    outputs = _run_merge_config(
        monkeypatch, tmp_path, INPUT_BUILD_CONFIG=str(config_file)
    )

    assert outputs["python_requirements"] == "requirements.txt"
    assert outputs["config"]["cmake_options"] == (
        " -DPython3_EXECUTABLE=$RUNNER_TEMP/bpvenv/bin/python"
    )
    assert "python_requirements" not in outputs["config"]


def test_merge_config_requirements_input_beats_config_and_pops_key(
    monkeypatch, tmp_path
):
    config_file = tmp_path / "build-config.yml"
    config_file.write_text("python_requirements: requirements.txt\n")

    outputs = _run_merge_config(
        monkeypatch,
        tmp_path,
        INPUT_BUILD_CONFIG=str(config_file),
        INPUT_PYTHON_REQUIREMENTS="ci-requirements.txt",
    )

    assert outputs["python_requirements"] == "ci-requirements.txt"
    assert "python_requirements" not in outputs["config"]
