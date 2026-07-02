"""Unit tests for cd-actions/conda/scripts/parse_config.py."""

from __future__ import annotations

import os
import shutil

import pytest

from conftest import CD_ACTIONS_DIR, import_script

parse_config = import_script("conda", "parse_config", "conda_parse_config")

PROD_NEXUS_URL = "https://nexus.ecmwf.int/repository/conda-ecmwf-public"
TEST_NEXUS_URL = "https://nexus-test.ecmwf.int/repository/conda-ecmwf-public"


@pytest.fixture(autouse=True)
def _clean_env(action_env, monkeypatch):
    action_env("conda")
    for key in list(os.environ):
        if key.startswith("INPUT_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def unforced_config_dir(tmp_path, monkeypatch):
    """A config dir whose nexus-conda.yml has no TEMPORARY force_test flag."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    shutil.copy(CD_ACTIONS_DIR / "config" / "defaults.yml", config_dir / "defaults.yml")
    (config_dir / "nexus-conda.yml").write_text(
        f"production:\n  url: {PROD_NEXUS_URL}\ntest:\n  url: {TEST_NEXUS_URL}\n"
    )
    monkeypatch.setenv("CD_ACTIONS_CONFIG_DIR", str(config_dir))
    return config_dir


def _run(monkeypatch, github_output, **env) -> dict[str, str]:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    parse_config.main()
    return github_output.read()


class TestDefaults:
    def test_paths_derive_from_default_conda_dir(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output)
        assert result["meta_file"] == "./.cd/conda/meta.yaml"
        assert result["output_folder"] == "./.cd/conda/build"
        assert result["artifact_pattern"] == (
            "./.cd/conda/build/**/*.tar.bz2\n./.cd/conda/build/**/*.conda"
        )

    def test_default_channels_use_test_nexus(self, monkeypatch, github_output):
        # TEMPORARY: forward prod nexus -> test nexus (revert me)
        result = _run(monkeypatch, github_output)
        assert result["channels"] == f"-c conda-forge -c {TEST_NEXUS_URL}"
        assert result["channels_csv"] == f"conda-forge,{TEST_NEXUS_URL}"

    def test_default_platform(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output)
        assert result["platform"] == "linux-64"

    def test_empty_platform_falls_back(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output, INPUT_PLATFORM="")
        assert result["platform"] == "linux-64"

    def test_custom_conda_dir(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output, INPUT_CONDA_DIR="./conda")
        assert result["meta_file"] == "./conda/meta.yaml"
        assert result["output_folder"] == "./conda/build"


class TestChannels:
    def test_custom_channels(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output, INPUT_CHANNELS="ecmwf\nconda-forge")
        assert result["channels"] == "-c ecmwf -c conda-forge"
        assert result["channels_csv"] == "ecmwf,conda-forge"

    def test_blank_lines_ignored(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output, INPUT_CHANNELS="ecmwf\n\n  \n")
        assert result["channels"] == "-c ecmwf"


class TestCondaBuildArgs:
    def test_no_anaconda_upload_always_appended(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output)
        assert result["conda_build_args"] == "--no-anaconda-upload"

    def test_deduplicated_and_appended_last(self, monkeypatch, github_output):
        result = _run(
            monkeypatch,
            github_output,
            INPUT_CONDA_BUILD_ARGS="--foo --no-anaconda-upload\n--bar",
        )
        assert result["conda_build_args"] == "--foo --bar --no-anaconda-upload"

    def test_multiline_args_with_values(self, monkeypatch, github_output):
        result = _run(
            monkeypatch,
            github_output,
            INPUT_CONDA_BUILD_ARGS="-m .cd/conda/common.yaml\n-m .cd/conda/py312.yaml",
        )
        assert result["conda_build_args"] == (
            "-m .cd/conda/common.yaml -m .cd/conda/py312.yaml --no-anaconda-upload"
        )


class TestNexusSelection:
    def test_force_test_nexus_flag(self, monkeypatch, github_output):
        # TEMPORARY: force_test in config/nexus-conda.yml forwards prod ->
        # test regardless of the input. Pins the current forwarding behavior.
        result = _run(
            monkeypatch,
            github_output,
            INPUT_TEST_NEXUS="false",
            INPUT_NEXUS_TEST_TOKEN="test-token",
        )
        assert result["nexus_url"] == TEST_NEXUS_URL
        assert result["nexus_token"] == "test-token"

    def test_default_is_production_without_force(
        self, monkeypatch, github_output, unforced_config_dir
    ):
        result = _run(monkeypatch, github_output, INPUT_NEXUS_TOKEN="prod-token")
        assert result["nexus_url"] == PROD_NEXUS_URL
        assert result["nexus_token"] == "prod-token"

    def test_test_nexus(self, monkeypatch, github_output, unforced_config_dir):
        result = _run(
            monkeypatch,
            github_output,
            INPUT_TEST_NEXUS="true",
            INPUT_NEXUS_TEST_TOKEN="test-token",
        )
        assert result["nexus_url"] == TEST_NEXUS_URL
        assert result["nexus_token"] == "test-token"

    def test_empty_test_nexus_means_production(
        self, monkeypatch, github_output, unforced_config_dir
    ):
        result = _run(monkeypatch, github_output, INPUT_TEST_NEXUS="")
        assert result["nexus_url"] == PROD_NEXUS_URL


class TestDefaultsFallback:
    def test_empty_inputs_fall_back_to_defaults_yml(self, monkeypatch, github_output):
        result = _run(
            monkeypatch,
            github_output,
            INPUT_CONDA_DIR="",
            INPUT_CHANNELS="",
            INPUT_CONDA_BUILD_ARGS="",
        )
        assert result["meta_file"] == "./.cd/conda/meta.yaml"
        assert result["channels_csv"] == f"conda-forge,{TEST_NEXUS_URL}"
        assert result["conda_build_args"] == "--no-anaconda-upload"
