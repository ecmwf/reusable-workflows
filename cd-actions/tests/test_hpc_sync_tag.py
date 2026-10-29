"""Tests for cd-actions/hpc-sync-tag/scripts/generate_template.py."""

from __future__ import annotations

import os
import subprocess
import sys
import time
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

    @pytest.mark.parametrize(
        "override",
        [
            {"ref_name": "release-$(touch${IFS}/tmp/cd-injected)"},
            {"module_name": "eckit`id`"},
            {"build_name": 'eckit"; id; "'},
        ],
    )
    def test_shell_unsafe_names_fail_even_without_tagging(self, override):
        with pytest.raises(SystemExit):
            _options(dry_run=True, **override)

    def test_branch_ref_with_slash_is_allowed_for_dry_runs(self):
        options = _options(dry_run=True, ref_name="feature/cd-v3", build_name="eckit gnu 8.5")

        assert options["do_tag"] is False


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


class TestLockOptions:
    def test_defaults(self):
        lock = generate_template.resolve_lock_options(owner="me")

        assert lock["root"] == "$HOME/.cd-locks"
        assert lock["timeout"] == 1800
        assert lock["stale_minutes"] == 120

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("", "$HOME/.cd-locks"),
            ("~/locks", "$HOME/locks"),
            ("$HOME/a/b/", "$HOME/a/b"),
            ("/scratch/cd-locks", "/scratch/cd-locks"),
        ],
    )
    def test_valid_lock_roots(self, raw, expected):
        assert generate_template.validate_lock_root(raw) == expected

    @pytest.mark.parametrize(
        "raw", ["relative/path", "/tmp/$(id)", "/tmp/a b", "/tmp/../etc", "$HOMEX/a", '/tmp/"x"']
    )
    def test_invalid_lock_roots_fail(self, raw):
        with pytest.raises(SystemExit):
            generate_template.validate_lock_root(raw)

    @pytest.mark.parametrize("raw", ["0", "-5", "ten", "1.5"])
    def test_invalid_timeout_fails(self, raw):
        with pytest.raises(SystemExit):
            generate_template.resolve_lock_options(timeout=raw, owner="me")

    def test_owner_cannot_break_out_of_quotes(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPOSITORY", "ecmwf/eckit")
        monkeypatch.setenv("GITHUB_RUN_ID", "42")
        monkeypatch.setenv("GITHUB_JOB", "sync'; rm -rf /; echo '")

        owner = generate_template.lock_owner_from_env()

        assert "'" not in owner and ";" not in owner
        assert "repo=ecmwf/eckit" in owner
        assert "https://github.com/ecmwf/eckit/actions/runs/42/attempts/1" in owner

    def test_rendered_job_takes_the_lock_before_sync_and_tag(self):
        rendered = _render(_options())

        assert 'cd_lock_root="$HOME/.cd-locks"' in rendered
        assert 'until mkdir "$cd_lock_dir"' in rendered
        assert "trap cd_lock_release EXIT" in rendered
        assert "$cd_lock_root/DISABLED" in rendered
        assert rendered.index("trap cd_lock_release EXIT") < rendered.index("Synchronize module")
        # The rendered job is rendered again by build-package-hpc, so it must not contain Jinja syntax
        assert not any(d in rendered for d in ("{{", "{%", "{#"))

    def test_main_passes_lock_inputs(self, tmp_path, monkeypatch):
        output = TestMain()._run_main(
            tmp_path,
            monkeypatch,
            INPUT_LOCK_ROOT="/scratch/locks",
            INPUT_LOCK_TIMEOUT="60",
            INPUT_LOCK_STALE_MINUTES="5",
        )
        template = TestMain._extract(output, "template", "EOF")

        assert 'cd_lock_root="/scratch/locks"' in template
        assert "cd_lock_timeout=60" in template
        assert "cd_lock_stale_minutes=5" in template


class TestLockScript:
    """Run the rendered lock snippet in bash against a temporary lock root."""

    @staticmethod
    def _script(root, payload, owner="job", timeout=30, stale_minutes=120):
        lock = generate_template.resolve_lock_options(
            root=str(root), timeout=str(timeout), stale_minutes=str(stale_minutes), owner=owner, poll=1
        )
        template = JINJA_ENV.from_string("{% from 'lock.jinja' import acquire_lock %}{{ acquire_lock(lock) }}\n")
        return template.render(lock=lock) + "\n" + payload + "\n"

    @staticmethod
    def _run(script, **kwargs):
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60, **kwargs)

    def test_concurrent_runs_serialise(self, tmp_path):
        root = tmp_path / "locks"
        log = tmp_path / "log"
        procs = []
        for name in ("a", "b"):
            payload = f'echo "start {name}" >> "{log}"; sleep 2; echo "end {name}" >> "{log}"'
            procs.append(
                subprocess.Popen(["bash", "-c", self._script(root, payload, owner=name)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            )
        for proc in procs:
            assert proc.wait(timeout=60) == 0, proc.stdout.read()

        lines = log.read_text().split()
        events = [" ".join(lines[i : i + 2]) for i in range(0, len(lines), 2)]
        assert len(events) == 4
        # Each start is directly followed by its own end
        assert events[0].replace("start", "end") == events[1]
        assert events[2].replace("start", "end") == events[3]
        assert not (root / "modulemgr").exists()

    def test_stale_lock_is_broken(self, tmp_path):
        root = tmp_path / "locks"
        lock_dir = root / "modulemgr"
        lock_dir.mkdir(parents=True)
        (lock_dir / "owner").write_text("old run\n")
        old = time.time() - 3 * 3600
        os.utime(lock_dir, (old, old))

        result = self._run(self._script(root, "echo payload-ran", stale_minutes=1))

        assert result.returncode == 0, result.stdout + result.stderr
        assert "Breaking stale lock" in result.stdout
        assert "payload-ran" in result.stdout
        assert not lock_dir.exists()

    def test_other_owners_lock_is_kept(self, tmp_path):
        root = tmp_path / "locks"
        lock_dir = root / "modulemgr"
        lock_dir.mkdir(parents=True)
        (lock_dir / "owner").write_text("someone else\n")

        result = self._run(self._script(root, "echo payload-ran", timeout=2))

        assert result.returncode == 1
        assert "Timed out" in result.stdout
        assert "payload-ran" not in result.stdout
        assert (lock_dir / "owner").read_text() == "someone else\n"

    def test_lock_taken_over_by_another_owner_is_not_removed_on_exit(self, tmp_path):
        root = tmp_path / "locks"
        lock_dir = root / "modulemgr"
        # Simulate our lock being broken as stale and re-acquired by another job
        payload = f'echo "someone else" > "{lock_dir}/owner"'

        result = self._run(self._script(root, payload))

        assert result.returncode == 0, result.stdout + result.stderr
        assert (lock_dir / "owner").read_text() == "someone else\n"

    def test_disabled_file_stops_the_job(self, tmp_path):
        root = tmp_path / "locks"
        root.mkdir()
        (root / "DISABLED").write_text("incident 123\n")

        result = self._run(self._script(root, "echo payload-ran"))

        assert result.returncode == 1
        assert "disabled" in result.stdout
        assert "incident 123" in result.stdout
        assert "payload-ran" not in result.stdout
        assert not (root / "modulemgr").exists()

    def test_disabled_while_waiting_stops_the_job_after_acquiring(self, tmp_path):
        root = tmp_path / "locks"
        lock_dir = root / "modulemgr"
        lock_dir.mkdir(parents=True)
        (lock_dir / "owner").write_text("other job\n")
        # The other job finishes and an admin disables CD while we wait
        holder = subprocess.Popen(["bash", "-c", f'sleep 2; echo stop > "{root}/DISABLED"; rm -rf "{lock_dir}"'])

        result = self._run(self._script(root, "echo payload-ran"))
        holder.wait()

        assert result.returncode == 1
        assert "disabled while waiting" in result.stdout
        assert "payload-ran" not in result.stdout
        assert not lock_dir.exists()
