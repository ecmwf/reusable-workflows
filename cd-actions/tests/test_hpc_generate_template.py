"""Tests for cd-actions/hpc/scripts/generate_template.py (python environment setup)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ACTION_DIR = Path(__file__).parent.parent / "hpc"

# Load by path under a unique module name: cd-actions/hpc-sync-tag has a script with the same file name.
_SPEC = importlib.util.spec_from_file_location("hpc_generate_template", ACTION_DIR / "scripts" / "generate_template.py")
assert _SPEC is not None and _SPEC.loader is not None
hpc_generate_template = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(hpc_generate_template)


def _run_main(tmp_path, monkeypatch, **env) -> str:
    """Run main() with the given INPUT_* variables and return the rendered build template."""
    output_file = tmp_path / "github-output"
    # Run in an empty directory so that no bundle.yml is auto-detected
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_ACTION_PATH", str(ACTION_DIR))
    monkeypatch.setenv("GITHUB_REPOSITORY", "ecmwf/test-repo")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
    monkeypatch.setenv("INPUT_REF_NAME", "main")
    monkeypatch.setenv("STEP_CONFIG_COMPILER", "gnu")
    monkeypatch.setenv("STEP_CONFIG_COMPILER_MODULES", "prgenv/gnu,gcc")
    monkeypatch.setenv("STEP_CONFIG_INSTALL_PREFIX", "/install/prefix")
    monkeypatch.setenv("STEP_CONFIG_BASE_INSTALL_PREFIX", "/install")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    hpc_generate_template.main()
    output = output_file.read_text()
    return output.split("template<<EOF\n", 1)[1].split("\nEOF\n", 1)[0]


class TestCondaEnvFile:
    def test_env_file_without_python_version_uses_python_path(self, tmp_path, monkeypatch):
        script = _run_main(tmp_path, monkeypatch, INPUT_CONDA_ENV_FILE="environment.yml")

        # Python path was taken (not the CMake main package)
        assert "Setup Conda environment from environment.yml" in script
        assert "ecbuild" not in script
        assert "conda env create -y -p ${TMPDIR}/env_test-repo -f ${TMPDIR}/test-repo/environment.yml" in script
        assert "conda activate ${TMPDIR}/env_test-repo" in script
        assert "pip install pytest pytest-cov build" in script
        assert "python -m build --sdist" in script
        assert "python=" not in script
        assert "conda install" not in script
        assert "uv venv" not in script
        assert "uv pip" not in script

    def test_env_file_with_conda_deps_installs_them_on_top(self, tmp_path, monkeypatch):
        script = _run_main(
            tmp_path,
            monkeypatch,
            INPUT_CONDA_ENV_FILE="environment.yml",
            INPUT_CONDA_DEPS="rust\ncmake",
            INPUT_PYTHON_VERSION="3.11",
        )

        assert "conda env create -y -p " in script
        assert "conda install -y rust cmake -c conda-forge" in script
        assert "python=" not in script
        assert script.index("conda env create") < script.index("conda install")
        assert "uv venv" not in script

    def test_conda_deps_only_is_unchanged(self, tmp_path, monkeypatch):
        script = _run_main(tmp_path, monkeypatch, INPUT_CONDA_DEPS="rust", INPUT_PYTHON_VERSION="3.11")

        assert '::group::Setup Conda environment"' in script
        assert "conda create -y -p " in script
        assert "conda install -y python=3.11 rust -c conda-forge" in script
        assert "pip install pytest pytest-cov build" in script
        assert "conda env create" not in script
        assert "uv venv" not in script

    def test_neither_uses_uv(self, tmp_path, monkeypatch):
        script = _run_main(tmp_path, monkeypatch, INPUT_PYTHON_VERSION="3.11")

        assert "uv venv --python 3.11" in script
        assert "uv pip install pytest pytest-cov build" in script
        assert "conda" not in script

    def test_neither_and_no_python_version_is_cmake_build(self, tmp_path, monkeypatch):
        script = _run_main(tmp_path, monkeypatch)

        assert "ecbuild" in script
        assert "uv venv" not in script
        assert "conda env create" not in script

    @pytest.mark.parametrize("env_file", ["environment.yml", ""])
    def test_python_main_package_classification(self, tmp_path, monkeypatch, env_file):
        script = _run_main(tmp_path, monkeypatch, INPUT_CONDA_ENV_FILE=env_file)

        assert ("ecbuild" not in script) == bool(env_file)
