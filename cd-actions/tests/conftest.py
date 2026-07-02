"""Shared fixtures and helpers for cd-actions tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

CD_ACTIONS_DIR = Path(__file__).resolve().parent.parent
LIB_DIR = CD_ACTIONS_DIR / "lib"

# Shared library modules (cd_helpers, conda_platforms, ...) are imported by
# name from the scripts under test; make them resolvable for the whole suite.
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))


def import_script(action: str, script: str, alias: str):
    """Import cd-actions/<action>/scripts/<script>.py under a unique alias.

    Several scripts share a basename (parse_config.py, resolve.py), so a plain
    sys.path import would silently return whichever module loaded first.
    Modules that read GITHUB_ACTION_PATH at import time need it set before
    calling this.
    """
    path = CD_ACTIONS_DIR / action / "scripts" / f"{script}.py"
    # Scripts import sibling modules (e.g. hpc_common); when run for real,
    # their own directory is sys.path[0].
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


def parse_github_output(text: str) -> dict[str, str]:
    """Parse a GITHUB_OUTPUT file: key=value lines and key<<DELIM heredocs."""
    outputs: dict[str, str] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        before_marker = line.split("<<", 1)[0] if "<<" in line else None
        if before_marker is not None and "=" not in before_marker:
            delimiter = line.split("<<", 1)[1]
            block: list[str] = []
            i += 1
            while i < len(lines) and lines[i] != delimiter:
                block.append(lines[i])
                i += 1
            if i >= len(lines):
                raise ValueError(f"unterminated heredoc for output {before_marker!r}")
            outputs[before_marker] = "\n".join(block)
        elif "=" in line:
            key, value = line.split("=", 1)
            outputs[key] = value
        i += 1
    return outputs


class GithubOutput:
    """Handle for the temp file behind the GITHUB_OUTPUT env var."""

    def __init__(self, path: Path):
        self.path = path

    def read(self) -> dict[str, str]:
        return parse_github_output(self.path.read_text())

    def raw(self) -> str:
        return self.path.read_text()

    def clear(self) -> None:
        self.path.write_text("")


def pytest_addoption(parser):
    parser.addoption(
        "--update-goldens",
        action="store_true",
        default=False,
        help="Rewrite golden fixture files with the current output",
    )


@pytest.fixture
def update_goldens(request) -> bool:
    return request.config.getoption("--update-goldens")


@pytest.fixture
def github_output(tmp_path, monkeypatch) -> GithubOutput:
    """Provide a temp GITHUB_OUTPUT file and a parser for its contents."""
    path = tmp_path / "github_output"
    path.touch()
    monkeypatch.setenv("GITHUB_OUTPUT", str(path))
    return GithubOutput(path)


@pytest.fixture
def action_env(monkeypatch):
    """Point GITHUB_ACTION_PATH at a cd-actions/<action> directory."""

    def _set(action: str) -> None:
        monkeypatch.setenv("GITHUB_ACTION_PATH", str(CD_ACTIONS_DIR / action))

    return _set
