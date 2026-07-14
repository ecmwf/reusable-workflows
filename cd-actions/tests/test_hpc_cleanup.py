"""Render-and-execute tests for the HPC install cleanup macro."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader


TEMPLATE_DIR = Path(__file__).parent.parent / "hpc" / "templates"
JINJA_ENV = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    trim_blocks=True,
    lstrip_blocks=True,
)
JINJA_ENV.filters["strip_d_prefix"] = (
    lambda value: value[2:] if value.startswith("-D") else value
)
CLEAN_TEMPLATE = JINJA_ENV.from_string(
    "{% from 'environment.jinja' import clean_install_dir with context %}"
    "{{ clean_install_dir(package) }}"
)
CMAKE_TEMPLATE = JINJA_ENV.from_string(
    "{% from 'cmake.jinja' import cmake_package with context %}"
    "{{ cmake_package(package) }}"
)
ECBUNDLE_TEMPLATE = JINJA_ENV.from_string(
    "{% from 'ecbundle.jinja' import ecbundle_workflow with context %}"
    "{{ ecbundle_workflow(package) }}"
)


def _render_cleanup(prefix: Path, *, explicit: bool = False) -> str:
    return CLEAN_TEMPLATE.render(
        package={"name": "test-package", "prefix": str(prefix), "type": "main"},
        ci_options={
            "clean_before_install": explicit,
            "dry_run": True,
            "dry_run_install": True,
            "skip_install": False,
        },
    )


def _run_cleanup(
    prefix: Path,
    *,
    scratch: Path | str | None = None,
    tmpdir: Path | str | None = None,
    explicit: bool = False,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("SCRATCH", None)
    env.pop("TMPDIR", None)
    if scratch is not None:
        env["SCRATCH"] = str(scratch)
    if tmpdir is not None:
        env["TMPDIR"] = str(tmpdir)

    return subprocess.run(
        ["bash", "-e", "-o", "pipefail"],
        input=_render_cleanup(prefix, explicit=explicit),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def _render_ecbundle_workflow(
    *,
    self_test: bool = False,
    skip_install: bool = False,
    ctest_options: list[str] | None = None,
) -> str:
    return ECBUNDLE_TEMPLATE.render(
        package={
            "name": "test-bundle",
            "owner": "test-owner",
            "repo": "test-bundle",
            "ref": "main",
            "type": "ecbundle",
            "prefix": "${SCRATCH}/dry-run-install/test-bundle/main",
            "cmake_options": [],
            "ctest_options": ctest_options or [],
            "modules": [],
            "cache_key": "unused",
            "subdir": "",
        },
        ci_options={
            "workdir": "${TMPDIR}",
            "parallel": 4,
            "cpus_per_task": 4,
            "self_test": self_test,
            "skip_install": skip_install,
            "dry_run": skip_install,
            "dry_run_install": False,
            "clean_before_install": False,
        },
        github={"user": "test-user", "token": "test-token"},
        generic_modules=[],
        env=[],
    )


def _render_cmake_package(*, ecbundle: bool) -> str:
    return CMAKE_TEMPLATE.render(
        package={
            "name": "test-package",
            "owner": "test-owner",
            "repo": "test-package",
            "ref": "main",
            "type": "main",
            "prefix": "${SCRATCH}/dry-run-install/test-package/main",
            "cmake_options": [],
            "ctest_options": [],
            "modules": [],
            "cache_key": "unused",
            "subdir": "",
            "install_command": "",
        },
        ci_options={
            "workdir": "${TMPDIR}",
            "force_build": False,
            "hpc_config": {"enable_cache": False},
            "ecbundle": ecbundle,
            "cpus_per_task": 4,
            "skip_install": False,
            "self_test": False,
            "clean_before_install": False,
            "dry_run": True,
            "dry_run_install": True,
        },
        github={"user": "test-user", "token": "test-token"},
        generic_modules=[],
        env=[],
    )


def _populate_install(prefix: Path) -> None:
    prefix.mkdir(parents=True)
    (prefix / "regular-file").write_text("regular\n")
    (prefix / ".hidden-file").write_text("hidden\n")
    hidden_dir = prefix / ".hidden-directory"
    hidden_dir.mkdir()
    (hidden_dir / "nested-file").write_text("nested\n")


def test_automatic_cleanup_canonicalizes_symlinked_scratch(tmp_path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    scratch_link = tmp_path / "scratch-link"
    scratch_link.symlink_to(scratch, target_is_directory=True)
    prefix = scratch_link / "install"
    _populate_install(prefix)

    result = _run_cleanup(prefix, scratch=scratch_link)

    assert result.returncode == 0, result.stderr
    assert prefix.is_dir()
    assert list(prefix.iterdir()) == []


def test_automatic_cleanup_canonicalizes_dot_dot_in_scratch(tmp_path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    prefix = scratch / "install"
    _populate_install(prefix)
    (tmp_path / "unused").mkdir()
    noncanonical_scratch = tmp_path / "unused" / ".." / "scratch"

    result = _run_cleanup(prefix, scratch=noncanonical_scratch)

    assert result.returncode == 0, result.stderr
    assert prefix.is_dir()
    assert list(prefix.iterdir()) == []


def test_automatic_cleanup_rejects_target_outside_scratch(tmp_path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    prefix = tmp_path / "outside" / "install"
    _populate_install(prefix)

    result = _run_cleanup(prefix, scratch=scratch)

    assert result.returncode != 0
    assert "not under $SCRATCH" in result.stdout
    assert (prefix / "regular-file").is_file()
    assert (prefix / ".hidden-file").is_file()
    assert (prefix / ".hidden-directory").is_dir()


def test_automatic_cleanup_rejects_scratch_root_itself(tmp_path):
    scratch = tmp_path / "scratch"
    _populate_install(scratch)

    result = _run_cleanup(scratch, scratch=scratch)

    assert result.returncode != 0
    assert "not under $SCRATCH" in result.stdout
    assert (scratch / "regular-file").is_file()


@pytest.mark.parametrize("root_variable", ["TMPDIR", "SCRATCH"])
def test_explicit_cleanup_canonicalizes_environment_roots(tmp_path, root_variable):
    root = tmp_path / root_variable.lower()
    root.mkdir()
    root_link = tmp_path / f"{root_variable.lower()}-link"
    root_link.symlink_to(root, target_is_directory=True)
    prefix = root_link / "install"
    _populate_install(prefix)
    kwargs = {root_variable.lower(): root_link}

    result = _run_cleanup(prefix, explicit=True, **kwargs)

    assert result.returncode == 0, result.stderr
    assert prefix.is_dir()
    assert list(prefix.iterdir()) == []


@pytest.mark.parametrize(
    ("available_root", "unresolvable_root"),
    [("tmpdir", "scratch"), ("scratch", "tmpdir")],
)
def test_explicit_cleanup_ignores_unresolvable_optional_root(
    tmp_path, available_root, unresolvable_root
):
    root = tmp_path / available_root
    root.mkdir()
    prefix = root / "install"
    _populate_install(prefix)
    kwargs = {
        available_root: root,
        unresolvable_root: tmp_path / f"missing-{unresolvable_root}",
    }

    result = _run_cleanup(prefix, explicit=True, **kwargs)

    assert result.returncode == 0, result.stderr
    assert prefix.is_dir()
    assert list(prefix.iterdir()) == []


def test_explicit_cleanup_rejects_target_outside_available_roots(tmp_path):
    prefix = tmp_path / "outside" / "install"
    _populate_install(prefix)

    result = _run_cleanup(
        prefix,
        explicit=True,
        tmpdir=tmp_path / "missing-tmpdir",
        scratch=tmp_path / "missing-scratch",
    )

    assert result.returncode != 0
    assert "not under /usr/local/apps" in result.stdout
    assert (prefix / "regular-file").is_file()
    assert (prefix / ".hidden-file").is_file()
    assert (prefix / ".hidden-directory").is_dir()


def test_cleanup_rejects_unresolvable_required_root(tmp_path):
    prefix = tmp_path / "install"
    _populate_install(prefix)
    missing_scratch = tmp_path / "missing-scratch"

    result = _run_cleanup(prefix, scratch=missing_scratch)

    assert result.returncode != 0
    assert "could not resolve $SCRATCH" in result.stdout
    assert (prefix / "regular-file").is_file()


def test_legacy_ecbundle_cleanup_precedes_combined_build_and_install():
    rendered = _render_cmake_package(ecbundle=True)

    cleanup = rendered.index("Cleaning before install: test-package")
    build_and_install = rendered.index("ecbundle build --install")

    assert cleanup < build_and_install
    assert rendered.count("Cleaning before install: test-package") == 1


def test_standard_cmake_cleanup_remains_between_build_and_install():
    rendered = _render_cmake_package(ecbundle=False)

    build = rendered.index("time cmake --build .")
    cleanup = rendered.index("Cleaning before install: test-package")
    install = rendered.index("time cmake --install .")

    assert build < cleanup < install
    assert rendered.count("Cleaning before install: test-package") == 1


def test_ecbundle_workflow_orders_build_test_and_install():
    rendered = _render_ecbundle_workflow(
        self_test=True, ctest_options=["--output-on-failure", "-j4"]
    )

    build = rendered.index('ecbundle-build "${ECBUNDLE_BUILD_ARGS[@]}"')
    test = rendered.index("time ctest")
    install = rendered.index('ecbundle-build --install "${ECBUNDLE_BUILD_ARGS[@]}"')

    assert build < test < install
    # ctest options are passed through verbatim
    assert "--output-on-failure -j4" in rendered
    # ctest runs from the top of the bundle build tree
    assert "cd ${TMPDIR}/builds\ntime ctest" in rendered


def test_ecbundle_workflow_omits_test_step_when_self_test_disabled():
    rendered = _render_ecbundle_workflow(self_test=False)

    assert "time ctest" not in rendered
    assert 'ecbundle-build "${ECBUNDLE_BUILD_ARGS[@]}"' in rendered
    assert 'ecbundle-build --install "${ECBUNDLE_BUILD_ARGS[@]}"' in rendered


def test_ecbundle_workflow_defaults_to_output_on_failure_when_ctest_options_unset():
    rendered = _render_ecbundle_workflow(self_test=True)

    # No ctest_options supplied => default --output-on-failure is injected
    assert "time ctest --output-on-failure" in rendered


def test_ecbundle_workflow_user_ctest_options_replace_the_default():
    rendered = _render_ecbundle_workflow(
        self_test=True, ctest_options=["-j8", "--stop-on-failure"]
    )

    # User-supplied options fully replace the default; --output-on-failure
    # is not silently appended.
    assert "time ctest -j8 --stop-on-failure" in rendered
    assert "--output-on-failure" not in rendered


def test_ecbundle_workflow_still_tests_when_install_is_skipped():
    rendered = _render_ecbundle_workflow(self_test=True, skip_install=True)

    build = rendered.index('ecbundle-build "${ECBUNDLE_BUILD_ARGS[@]}"')
    test = rendered.index("time ctest")

    assert build < test
    # No install invocation, and the dry-run message is emitted instead
    assert 'ecbundle-build --install "${ECBUNDLE_BUILD_ARGS[@]}"' not in rendered
    assert "Dry run: skipping ecbundle install" in rendered
