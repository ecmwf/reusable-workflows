"""Characterization tests for the HPC pipeline using ecmwf/ecflow's config.

The fixture is ecflow's .github/cd-config.yml at 6b4cd3f2e3b85e13eb583130b20
(the "Release 5.17.0" build, GHA run 26879024300). Golden files are generated
from this repository's current code via ``pytest --update-goldens`` and act as
the contract for behavior-preserving refactors: a refactor commit must never
need to regenerate them.

The aa-batch golden was sanity-checked once against the run's job log
(job 79330129318): module load lines, stage markers, git fetch of the pinned
sha, install prefix, and sbatch directives all match the logged preview. A
byte-diff against that log is NOT valid — the HPC scripts have changed since
the run was rendered.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from conftest import import_script
from hpc_pipeline import render_hpc_job

FIXTURES = Path(__file__).parent / "fixtures" / "ecflow"
GOLDEN = FIXTURES / "golden"

# Release context of the reference run (run 26879024300, "Release 5.17.0").
ECFLOW_REPOSITORY = "ecmwf/ecflow"
ECFLOW_REF_NAME = "5.17.0"
ECFLOW_SHA = "6b4cd3f2e3b85e13eb583130b20ae52d8ce3a0a1"

generate_matrix = import_script(
    "load-config", "generate_matrix", "generate_matrix_script_hpc"
).generate_matrix


def _ecflow_matrix(action_env) -> dict:
    action_env("load-config")
    with open(FIXTURES / "cd-config.yml") as f:
        config = yaml.safe_load(f)
    return generate_matrix(config)


def _matrix_item(matrix: dict, name: str) -> dict:
    for item in matrix["include"]:
        if item["name"] == name:
            return item
    raise KeyError(name)


def _assert_or_update(path: Path, actual: str, update: bool) -> None:
    if update:
        path.write_text(actual)
    else:
        assert path.exists(), (
            f"golden file {path.name} missing — generate it with --update-goldens"
        )
        assert actual == path.read_text(), (
            f"output differs from golden {path.name}; if the change is "
            "intentional, regenerate with --update-goldens"
        )


def test_ecflow_matrix_golden(action_env, update_goldens):
    matrix = _ecflow_matrix(action_env)
    actual = json.dumps(matrix, indent=2) + "\n"
    _assert_or_update(GOLDEN / "matrix.json", actual, update_goldens)


# (variant, build name, dry_run) — is_prerelease is false for a 5.17.0 release.
HPC_VARIANTS = [
    ("aa-batch", "ecflow-hpc", "false"),
    ("ag-batch", "ecflow-hpc-ag", "false"),
    ("aa-batch-dry-run", "ecflow-hpc", "true"),
]


@pytest.mark.parametrize(
    "variant,build_name,dry_run", HPC_VARIANTS, ids=[v[0] for v in HPC_VARIANTS]
)
def test_ecflow_hpc_template_golden(
    variant, build_name, dry_run, action_env, update_goldens, tmp_path, monkeypatch
):
    matrix = _ecflow_matrix(action_env)
    item = _matrix_item(matrix, build_name)

    # generate_template probes for bundle.yml in the cwd; run from a clean dir
    # like the real action does from a fresh checkout without one.
    monkeypatch.chdir(tmp_path)

    template, sbatch = render_hpc_job(
        item,
        ref_name=ECFLOW_REF_NAME,
        sha=ECFLOW_SHA,
        dry_run=dry_run,
        is_prerelease="false",
        repository=ECFLOW_REPOSITORY,
        workdir=tmp_path,
    )

    _assert_or_update(GOLDEN / f"hpc-{variant}.template.sh", template, update_goldens)
    _assert_or_update(GOLDEN / f"hpc-{variant}.sbatch", sbatch + "\n", update_goldens)
