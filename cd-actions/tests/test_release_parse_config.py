"""Tests for cd-actions/release/scripts/parse_release_config.py."""

from __future__ import annotations

from conftest import import_script

parse_release_config = import_script(
    "release", "parse_release_config", "release_parse_config"
)


def test_defaults():
    outputs = parse_release_config.parse_release_config(
        "release:\n  enabled: true\n", "1.0.0"
    )
    assert outputs == {
        "release_name": "Release 1.0.0",
        "release_body": "## Changes\nSee the changelog for details.",
        "prerelease": "false",
        "draft": "false",
        "make_latest": "true",
    }


def test_explicit_values():
    config = """
release:
  enabled: true
  config:
    name: My Release
    body: |
      Line one
      Line two
    prerelease: true
    draft: true
"""
    outputs = parse_release_config.parse_release_config(config, "1.0.0")
    assert outputs["release_name"] == "My Release"
    assert outputs["release_body"] == "Line one\nLine two\n"
    assert outputs["prerelease"] == "true"
    assert outputs["draft"] == "true"


def test_make_latest_boolean_quirk():
    # An explicit YAML boolean is passed through without normalization and
    # renders as Python's str(True). Kept verbatim from the inline original.
    config = "release:\n  config:\n    make_latest: true\n"
    outputs = parse_release_config.parse_release_config(config, "1.0.0")
    assert outputs["make_latest"] is True


def test_main_writes_multiline_body_heredoc(monkeypatch, github_output):
    monkeypatch.setenv(
        "INPUT_CONFIG",
        "release:\n  config:\n    body: |\n      first\n      second\n",
    )
    monkeypatch.setenv("INPUT_REF_NAME", "2.0.0")
    parse_release_config.main()
    outputs = github_output.read()
    assert outputs["release_name"] == "Release 2.0.0"
    assert outputs["release_body"] == "first\nsecond\n"
    assert outputs["make_latest"] == "true"
