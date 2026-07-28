"""Tests for cd-actions/hpc-sync-tag/scripts/generate_template.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

# Make the script importable.
SCRIPT_DIR = Path(__file__).parent.parent / "hpc-sync-tag" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import generate_template
from generate_template import (
    make_jinja_env,
    resolve_sync_tag_options,
    validate_module_tag_name,
)


ACTION_DIR = Path(__file__).parent.parent / "hpc-sync-tag"
# Use the real cluster maps so drift between hpc.yml and these tests is caught
HPC_CONFIG = yaml.safe_load(
    (Path(__file__).parent.parent / "hpc-sync-tag" / "config" / "hpc.yml").read_text()
)
JINJA_ENV = make_jinja_env(ACTION_DIR)


def _options(**overrides):
    kwargs = {
        "site": "aa-batch",
        "module_name": "eckit",
        "ref_name": "1.2.3",
        "sync_module": True,
        "tag_module": True,
        "module_tag_name": "new",
        "is_prerelease": False,
        "dry_run": False,
        "hpc_config": HPC_CONFIG,
    }
    kwargs.update(overrides)
    return resolve_sync_tag_options(**kwargs)


def _render(ci_options) -> str:
    return JINJA_ENV.get_template("sync-tag-job.jinja").render(ci_options=ci_options)


class TestResolveSyncTagOptions:
    def test_release_at_aa_batch_syncs_and_tags(self):
        options = _options()

        assert options["sync_module"] is True
        assert options["do_tag"] is True
        assert options["sync_clusters"] == ["ab", "ac", "ad"]
        assert options["tag_clusters"] == ["aa", "ab", "ac", "ad"]

    def test_dry_run_disables_sync_and_tag(self):
        options = _options(dry_run=True)

        assert options["sync_module"] is False
        assert options["do_tag"] is False

    def test_prerelease_syncs_but_does_not_tag(self):
        options = _options(is_prerelease=True)

        assert options["sync_module"] is True
        assert options["do_tag"] is False

    def test_ag_batch_tags_locally_without_sync(self):
        options = _options(site="ag-batch")

        assert options["sync_module"] is False
        assert options["do_tag"] is True
        assert options["tag_clusters"] == ["ag"]

    def test_lumi_has_nothing_to_do(self):
        options = _options(site="lumi")

        assert options["sync_module"] is False
        assert options["do_tag"] is False

    def test_sync_disabled_tags_only_local_cluster(self):
        # Without sync, tagging is restricted to clusters not served by sync
        options = _options(sync_module=False)

        assert options["sync_module"] is False
        assert options["do_tag"] is True
        assert options["tag_clusters"] == ["aa"]

    def test_unknown_site_with_tagging_fails(self):
        with pytest.raises(SystemExit):
            _options(site="zz-batch")

    def test_unknown_site_without_tagging_falls_back_to_default_sync_clusters(self):
        options = _options(site="zz-batch", tag_module=False)

        assert options["sync_module"] is True
        assert options["sync_clusters"] == ["ab", "ac", "ad"]

    def test_ref_name_with_slash_fails_when_tagging(self):
        with pytest.raises(SystemExit):
            _options(ref_name="feature/foo")

    def test_ref_name_with_slash_allowed_when_not_tagging(self):
        options = _options(ref_name="feature/foo", tag_module=False)

        assert options["sync_module"] is True
        assert options["do_tag"] is False

    def test_invalid_module_name_fails_when_tagging(self):
        with pytest.raises(SystemExit):
            _options(module_name="bad name")


class TestValidateModuleTagName:
    def test_empty_defaults_to_new(self):
        assert validate_module_tag_name("") == "new"
        assert validate_module_tag_name("  ") == "new"

    def test_valid_name_is_stripped(self):
        assert validate_module_tag_name(" v2 ") == "v2"

    def test_invalid_characters_fail(self):
        with pytest.raises(SystemExit):
            validate_module_tag_name("new tag!")


class TestRenderTemplate:
    def test_release_renders_one_sync_and_one_tag_block(self):
        rendered = _render(_options())

        assert rendered.count("Synchronize module") == 1
        assert rendered.count("Tag module") == 1
        # Exact command shapes from finalize.jinja
        assert "modulemgr -v -f sync eckit" in rendered
        assert (
            "/home/deploy/software-sync/bin/software-sync -s local -t ab,ac,ad -p eckit"
            in rendered
        )
        assert "modulemgr -v -f -m ab,ac,ad sync eckit" in rendered
        assert 'modulemgr -m "aa,ab,ac,ad" -f -v tag "eckit" "1.2.3" "new"' in rendered

    def test_prerelease_renders_sync_only(self):
        rendered = _render(_options(is_prerelease=True))

        assert "Synchronize module" in rendered
        assert "Tag module" not in rendered

    def test_ag_batch_renders_tag_only_on_local_cluster(self):
        rendered = _render(_options(site="ag-batch"))

        assert "Synchronize module" not in rendered
        assert 'modulemgr -m "ag" -f -v tag "eckit" "1.2.3" "new"' in rendered


class TestMain:
    def _run_main(self, tmp_path, monkeypatch, **env):
        output_file = tmp_path / "github-output"
        monkeypatch.setenv("GITHUB_ACTION_PATH", str(ACTION_DIR))
        monkeypatch.setenv("GITHUB_REPOSITORY", "ecmwf/test-repo")
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
        monkeypatch.setenv("INPUT_REF_NAME", "1.2.3")
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        generate_template.main()
        return output_file.read_text()

    @staticmethod
    def _extract(output: str, name: str, delimiter: str) -> str:
        return output.split(f"{name}<<{delimiter}\n", 1)[1].split(f"\n{delimiter}\n", 1)[0]

    def test_release_end_to_end(self, tmp_path, monkeypatch):
        output = self._run_main(tmp_path, monkeypatch)

        assert "do_run=true\n" in output
        template = self._extract(output, "template", "EOF")
        # module_name falls back to the repository name
        assert "modulemgr -v -f sync test-repo" in template
        assert 'modulemgr -m "aa,ab,ac,ad" -f -v tag "test-repo" "1.2.3" "new"' in template
        sbatch = self._extract(output, "sbatch_options", "SBATCH_EOF")
        assert "# TROIKA queue=nf" in sbatch
        assert "#SBATCH --ntasks=1" in sbatch

    def test_dry_run_end_to_end(self, tmp_path, monkeypatch):
        output = self._run_main(tmp_path, monkeypatch, INPUT_DRY_RUN="true")

        assert "do_run=false\n" in output
        assert self._extract(output, "template", "EOF") == ""
