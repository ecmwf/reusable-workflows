"""Unit tests for cd-actions/hpc/scripts/parse_config.py."""

from __future__ import annotations

import json
import os

import pytest

from conftest import import_script

parse_config = import_script("hpc", "parse_config", "hpc_parse_config")

BASE_ENV = {
    "INPUT_PLATFORM": "gnu-14.2.0",
    "INPUT_REF_NAME": "1.0.0",
    "GITHUB_REPOSITORY": "ecmwf/example",
}


@pytest.fixture(autouse=True)
def _clean_env(action_env, monkeypatch):
    action_env("hpc")
    for key in list(os.environ):
        if key.startswith(("INPUT_", "STEP_CONFIG_")):
            monkeypatch.delenv(key, raising=False)


def _run(monkeypatch, github_output, **env) -> dict[str, str]:
    for key, value in {**BASE_ENV, **env}.items():
        monkeypatch.setenv(key, value)
    parse_config.main()
    return github_output.read()


class TestCompilerResolution:
    def test_gnu(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output, INPUT_PLATFORM="gnu-8.5.0")
        assert result["compiler"] == "gnu-8.5.0"
        assert result["compiler_cc"] == "gcc"
        assert result["compiler_cxx"] == "g++"
        assert result["compiler_fc"] == "gfortran"
        assert result["compiler_modules"] == "gcc/8.5.0"

    def test_nvidia(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output, INPUT_PLATFORM="nvidia-24.11")
        assert result["compiler"] == "nvidia-24.11"
        assert result["compiler_modules"] == "prgenv/nvidia,nvidia/24.11"

    def test_amd_alias(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output, INPUT_PLATFORM="amd-4.0.0")
        assert result["compiler"] == "aocc-4.0.0"

    def test_unknown_platform_fails(self, monkeypatch, github_output):
        with pytest.raises(SystemExit):
            _run(monkeypatch, github_output, INPUT_PLATFORM="clang-17")


class TestInstallPrefix:
    def test_default(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output)
        assert result["install_prefix"] == "/usr/local/apps/example/1.0.0"
        assert result["base_install_prefix"] == "/usr/local/apps/example/1.0.0"

    def test_ref_name_slashes_sanitized(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output, INPUT_REF_NAME="feature/x")
        assert result["install_prefix"] == "/usr/local/apps/example/feature-x"

    def test_module_name_overrides_repo_name(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output, INPUT_MODULE_NAME="mytool")
        assert result["install_prefix"] == "/usr/local/apps/mytool/1.0.0"

    def test_explicit_prefix_passthrough(self, monkeypatch, github_output):
        result = _run(
            monkeypatch, github_output, INPUT_INSTALL_PREFIX="/custom/prefix"
        )
        assert result["install_prefix"] == "/custom/prefix"

    def test_compiler_specific_suffix(self, monkeypatch, github_output):
        result = _run(
            monkeypatch,
            github_output,
            INPUT_PLATFORM="gnu-8.5.0",
            INPUT_PREFIX_COMPILER_SPECIFIC="true",
        )
        assert result["install_prefix"] == "/usr/local/apps/example/1.0.0/GNU/8.5"
        assert result["base_install_prefix"] == "/usr/local/apps/example/1.0.0"

    def test_usr_local_apps_too_shallow_fails(self, monkeypatch, github_output):
        with pytest.raises(SystemExit):
            _run(monkeypatch, github_output, INPUT_INSTALL_PREFIX="/usr/local/apps/foo")

    def test_usr_local_apps_traversal_fails(self, monkeypatch, github_output):
        with pytest.raises(SystemExit):
            _run(
                monkeypatch,
                github_output,
                INPUT_INSTALL_PREFIX="/usr/local/apps/foo/1.0/../..",
            )


class TestDryRunInstall:
    def test_dry_run_install_uses_scratch(self, monkeypatch, github_output):
        result = _run(
            monkeypatch,
            github_output,
            INPUT_DRY_RUN="true",
            INPUT_DRY_RUN_INSTALL="true",
        )
        assert result["install_prefix"] == "${SCRATCH}/dry-run-install/example/1.0.0"

    def test_dry_run_install_prefix_override(self, monkeypatch, github_output):
        result = _run(
            monkeypatch,
            github_output,
            INPUT_DRY_RUN="true",
            INPUT_DRY_RUN_INSTALL="true",
            INPUT_DRY_RUN_INSTALL_PREFIX="$SCRATCH/test-install",
        )
        assert result["install_prefix"] == "$SCRATCH/test-install"

    def test_dry_run_without_install_keeps_prefix(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output, INPUT_DRY_RUN="true")
        assert result["install_prefix"] == "/usr/local/apps/example/1.0.0"

    def test_dry_run_install_ignored_outside_dry_run(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output, INPUT_DRY_RUN_INSTALL="true")
        assert result["install_prefix"] == "/usr/local/apps/example/1.0.0"


class TestModuleTagName:
    def test_default(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output)
        assert result["module_tag_name"] == "new"

    def test_empty_falls_back_to_new(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output, INPUT_MODULE_TAG_NAME="  ")
        assert result["module_tag_name"] == "new"

    def test_valid_passthrough(self, monkeypatch, github_output):
        result = _run(
            monkeypatch, github_output, INPUT_MODULE_TAG_NAME="release-candidate.1"
        )
        assert result["module_tag_name"] == "release-candidate.1"

    def test_invalid_characters_fail(self, monkeypatch, github_output):
        with pytest.raises(SystemExit):
            _run(monkeypatch, github_output, INPUT_MODULE_TAG_NAME="bad/name")


class TestDoSync:
    def test_default_is_true(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output)
        assert result["do_sync"] == "true"

    def test_dry_run_disables_sync(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output, INPUT_DRY_RUN="true")
        assert result["do_sync"] == "false"

    def test_sync_module_false_disables_sync(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output, INPUT_SYNC_MODULE="false")
        assert result["do_sync"] == "false"

    def test_ag_batch_never_syncs(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output, INPUT_SITE="ag-batch")
        assert result["do_sync"] == "false"


class TestUseStaged:
    def test_no_stages(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output)
        assert result["use_staged"] == "false"

    def test_empty_stages_list(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output, INPUT_STAGES="[]")
        assert result["use_staged"] == "false"

    def test_invalid_json_ignored(self, monkeypatch, github_output):
        result = _run(monkeypatch, github_output, INPUT_STAGES="not json")
        assert result["use_staged"] == "false"

    def test_stages_enable_staged_build(self, monkeypatch, github_output):
        stages = json.dumps([{"name": "py312", "modules": ["python3/3.12"]}])
        result = _run(monkeypatch, github_output, INPUT_STAGES=stages)
        assert result["use_staged"] == "true"
