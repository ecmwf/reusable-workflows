"""Guard against script injection: no ${{ }} expressions inside run: blocks.

Inputs, outputs, matrix values and secrets must reach scripts through env:,
where they are data, not code. Only expressions that the runner controls are
allowed inline.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent.parent

_spec = importlib.util.spec_from_file_location("append_env", REPO_ROOT / "cd-actions" / "lib" / "append_env.py")
append_env = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(append_env)

ALLOWED_EXPRESSIONS = {"github.action_path", "runner.temp"}
EXPRESSION_RE = re.compile(r"\$\{\{\s*(.*?)\s*\}\}", re.DOTALL)

WORKFLOWS = REPO_ROOT / ".github" / "workflows"
SCANNED_FILES = sorted(
    {
        *(REPO_ROOT / "cd-actions").glob("**/action.yml"),
        REPO_ROOT / "ci-hpc-generic" / "action.yml",
        WORKFLOWS / "main-cd.yml",
        *WORKFLOWS.glob("cd-*.yml"),
        WORKFLOWS / "conda-index-lock.yml",
        WORKFLOWS / "create-package.yml",
    }
)


def _steps(doc):
    runs = doc.get("runs") or {}
    yield from runs.get("steps") or []
    for job in (doc.get("jobs") or {}).values():
        yield from job.get("steps") or []


def _violations(path: Path) -> list[str]:
    doc = yaml.safe_load(path.read_text())
    found = []
    for step in _steps(doc):
        script = step.get("run")
        if not script:
            continue
        for expression in EXPRESSION_RE.findall(script):
            if expression not in ALLOWED_EXPRESSIONS:
                found.append(f"{step.get('name') or step.get('id') or '<unnamed>'}: ${{{{ {expression} }}}}")
    return found


@pytest.mark.parametrize("path", SCANNED_FILES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_no_expressions_in_run_blocks(path):
    assert _violations(path) == []


def test_scanner_finds_expressions(tmp_path):
    action = tmp_path / "action.yml"
    action.write_text(
        "runs:\n"
        "  using: composite\n"
        "  steps:\n"
        "    - name: bad\n"
        "      shell: python3 {0}\n"
        "      run: |\n"
        "        x = '''${{ inputs.config }}'''\n"
        "        y = '${{ github.action_path }}'\n"
    )

    assert _violations(action) == ["bad: ${{ inputs.config }}"]


class TestAppendEnv:
    def test_valid_lines(self):
        assert append_env.validate_lines("FOO=1\n\n  BAR=a b=c  \n_X=\n") == ["FOO=1", "BAR=a b=c", "_X="]

    @pytest.mark.parametrize(
        "text",
        [
            "PATH=/evil",
            "LD_PRELOAD=/x.so",
            "BASH_ENV=/x",
            "ENV=/x",
            "NODE_OPTIONS=--require=/x",
            "GITHUB_TOKEN=x",
            "RUNNER_TEMP=/x",
            "ACTIONS_RUNTIME_TOKEN=x",
            "path=/evil",
            "1FOO=x",
            "FOO BAR=x",
            "FOO<<EOF",
            "FOO",
            "-x=1",
        ],
    )
    def test_rejected_lines(self, text):
        with pytest.raises(ValueError):
            append_env.validate_lines(text)

    def test_main_appends_to_github_env(self, tmp_path, monkeypatch):
        github_env = tmp_path / "github-env"
        monkeypatch.setenv("GITHUB_ENV", str(github_env))
        monkeypatch.setenv("ENV_LINES", "FOO=1\nBAR=2")

        assert append_env.main() == 0
        assert github_env.read_text() == "FOO=1\nBAR=2\n"

    def test_main_writes_nothing_on_invalid_line(self, tmp_path, monkeypatch):
        github_env = tmp_path / "github-env"
        monkeypatch.setenv("GITHUB_ENV", str(github_env))
        monkeypatch.setenv("ENV_LINES", "FOO=1\nPATH=/evil")

        assert append_env.main() == 1
        assert not github_env.exists()
