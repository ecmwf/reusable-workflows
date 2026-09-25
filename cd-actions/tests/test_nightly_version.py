"""Tests for cd-actions/lib/nightly_version.py."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

LIB_DIR = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from nightly_version import commit_stamp, current_version, next_version, nightly_version


def _git(repo: Path, *args: str, date: str = "2026-09-24T02:03:00Z") -> str:
    env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    return subprocess.check_output(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args], env=env, text=True
    ).strip()


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "release")
    _git(tmp_path, "tag", "2.48.0")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "work")
    return tmp_path


@pytest.mark.parametrize(
    ("current", "expected"),
    [("2.49.0", "2.49.1"), ("6.0.0.0", "6.0.0.1"), ("v1.2", "1.3"), ("1.9.9\n", "1.9.10")],
)
def test_next_version_bumps_last_number(current, expected):
    assert next_version(current) == expected


def test_next_version_rejects_non_numeric():
    with pytest.raises(ValueError):
        next_version("develop")


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        ("system", "2.49.1~nightly.20260924020300.gabc1234"),
        ("python", "2.49.1.dev20260924020300"),
        ("conda", "2.49.1.dev20260924020300"),
    ],
)
def test_nightly_version_formats(style, expected):
    assert nightly_version("2.49.0", "20260924020300", "abc1234", style) == expected


def test_current_version_prefers_version_file(repo):
    (repo / "VERSION").write_text("2.49.0\n")

    assert current_version(str(repo)) == "2.49.0"


def test_current_version_falls_back_to_nearest_tag(repo):
    assert current_version(str(repo)) == "2.48.0"


def test_commit_stamp_uses_commit_time_in_utc(repo):
    _git(repo, "commit", "-q", "--allow-empty", "-m", "late", date="2026-09-24T23:30:05+02:00")

    stamp, sha = commit_stamp(str(repo))

    assert stamp == "20260924213005"
    assert sha == _git(repo, "rev-parse", "--short=7", "HEAD")
