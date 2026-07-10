"""Tests for build-package-with-config build configuration merging."""

import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from build_config import apply_os_overrides, pop_python_version  # noqa: E402


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
