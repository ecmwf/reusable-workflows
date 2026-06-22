"""Unit tests for cd-actions/lib/cd_helpers.py."""

import os
import tempfile
from pathlib import Path

import pytest

import sys

# Make the shared helper module importable from the tests directory.
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from cd_helpers import (  # noqa: E402
    bool_to_str,
    dict_to_cmake_args,
    dict_to_env_lines,
    list_to_comma_separated,
    list_to_line_separated,
    load_yaml,
)


class TestBoolToStr:
    def test_true_bool(self):
        assert bool_to_str(True, "flag") == "true"

    def test_false_bool(self):
        assert bool_to_str(False, "flag") == "false"

    def test_true_string(self):
        assert bool_to_str("true", "flag") == "true"
        assert bool_to_str("True", "flag") == "true"
        assert bool_to_str("1", "flag") == "true"
        assert bool_to_str("yes", "flag") == "true"

    def test_false_string(self):
        assert bool_to_str("false", "flag") == "false"
        assert bool_to_str("False", "flag") == "false"
        assert bool_to_str("0", "flag") == "false"
        assert bool_to_str("no", "flag") == "false"

    def test_invalid_type(self):
        with pytest.raises(ValueError, match="flag must be a bool"):
            bool_to_str(42, "flag")


class TestListToLineSeparated:
    def test_list(self):
        assert list_to_line_separated(["a", "b", "c"], "items") == "a\nb\nc"

    def test_string_passthrough(self):
        assert list_to_line_separated("a\nb", "items") == "a\nb"

    def test_invalid_type(self):
        with pytest.raises(ValueError, match="items must be a list"):
            list_to_line_separated(42, "items")


class TestListToCommaSeparated:
    def test_list(self):
        assert list_to_comma_separated(["a", "b", "c"], "items") == "a,b,c"

    def test_string_passthrough(self):
        assert list_to_comma_separated("a,b", "items") == "a,b"

    def test_invalid_type(self):
        with pytest.raises(ValueError, match="items must be a list"):
            list_to_comma_separated(42, "items")


class TestDictToEnvLines:
    def test_dict(self):
        assert dict_to_env_lines({"A": "1", "B": "2"}, "env") == "A=1\nB=2"

    def test_empty_value_emits_bare_key(self):
        assert dict_to_env_lines({"A": ""}, "env") == "A"

    def test_string_passthrough(self):
        assert dict_to_env_lines("A=1\nB=2", "env") == "A=1\nB=2"

    def test_invalid_type(self):
        with pytest.raises(ValueError, match="env must be a dict"):
            dict_to_env_lines(42, "env")


class TestDictToCmakeArgs:
    def test_dict(self):
        assert (
            dict_to_cmake_args({"ENABLE_TESTS": True, "CMAKE_BUILD_TYPE": "Release"}, "opts")
            == "-DENABLE_TESTS=ON\n-DCMAKE_BUILD_TYPE=Release"
        )

    def test_prefixed_key(self):
        assert dict_to_cmake_args({"-DFOO": "bar"}, "opts") == "-DFOO=bar"

    def test_empty_value(self):
        assert dict_to_cmake_args({"FOO": ""}, "opts") == "-DFOO"

    def test_bool_values(self):
        assert dict_to_cmake_args({"ON_OPT": True, "OFF_OPT": False}, "opts") == "-DON_OPT=ON\n-DOFF_OPT=OFF"

    def test_string_passthrough(self):
        assert dict_to_cmake_args("-DFOO=bar", "opts") == "-DFOO=bar"

    def test_invalid_type(self):
        with pytest.raises(ValueError, match="opts must be a dict"):
            dict_to_cmake_args(42, "opts")


class TestLoadYaml:
    def test_load_yaml(self, tmp_path):
        path = tmp_path / "test.yml"
        path.write_text("key: value\nlist:\n  - one\n  - two\n")
        assert load_yaml(path) == {"key": "value", "list": ["one", "two"]}
