# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased (CD v2 hardening)

### Security

- `conda-index-lock.yml` no longer takes the Nexus URL or token as `workflow_dispatch` inputs. It takes a `channel` (`test` or `production`), reads the URL from `cd-actions/conda/config/nexus.yml` at its own ref and the credentials from the `NEXUS_CONDA_UPLOAD_*` / `NEXUS_TEST_CONDA_UPLOAD_*` org secrets, and masks them. It validates `caller_repo`, `caller_run_id` and `package_artifact_name` first, and indexes `production` only for caller runs on a tag whose commit matches the run. It also honours the CD kill switch.
- `cd-actions/conda` no longer has `nexus_token` / `nexus_test_token` inputs and dispatches the lock workflow at its own ref (`v2` when that is unknown or a SHA). The `cd-conda.yml` inputs of the same name are kept but ignored.
- No `${{ }}` expressions in `run:` blocks of the CD actions and workflows: values reach scripts through `env:`. A test enforces this.
- `env_vars` / `env` lines written to `GITHUB_ENV` must be `KEY=value`; `PATH`, `LD_*`, `BASH_ENV`, `ENV`, `NODE_OPTIONS`, `GITHUB_*`, `RUNNER_*` and `ACTIONS_*` are refused.
- `main-cd.yml` passes no PyPI or Nexus upload credentials to dry runs.
- `hpc-sync-tag` refuses `ref_name`, `module_name` and `build_name` values with shell-special characters for every release type, not only when tagging.

### Added

- CD kill switch: every CD workflow fails at its first job when the `CD_KILL_SWITCH` variable is `on` (showing `CD_KILL_SWITCH_REASON`); `hpc-sync-tag` refuses to run while `<lock_root>/DISABLED` exists on the HPC.
- `hpc-sync-tag` takes a cross-repo lock (`<lock_root>/modulemgr`, new inputs `lock_root`, `lock_timeout`, `lock_stale_minutes`) around `modulemgr` and `software-sync`. A stale lock is broken by one waiter only, the holder keeps the lock fresh while it runs, and the `DISABLED` file is checked again after the lock is taken.
- `cd-actions/RUNBOOK.md`.

### Changed

- `buildargs` (`cd-pypi.yml`, `cd-actions/python-pypi`) is split like shell words (quotes respected) but never executed.
- Conda packages keep going to test Nexus on purpose until production conda repositories exist; the comments now say so.

## [v1.2.0](https://github.com/ecmwf/reusable-workflows/compare/v1.1.0...v1.2.0)

### Commits

- Added NPM lock file. [`227a14b`](https://github.com/ecmwf/reusable-workflows/commit/227a14b58a35657489970493fcd583dee9964d0d)
- Added sample for the sync workflow. [`fc71224`](https://github.com/ecmwf/reusable-workflows/commit/fc712243de0d2b7c5dd55200506188c025b1ee00)
- Merge tag 'v1.1.0' into develop [`f57eff8`](https://github.com/ecmwf/reusable-workflows/commit/f57eff8329d4a2aaee1b9ea4ff2486c72191ee10)

## [v1.1.0](https://github.com/ecmwf/reusable-workflows/compare/v1...v1.1.0) - 2021-11-30

## [v1](https://github.com/ecmwf/reusable-workflows/compare/v1.0.0...v1) - 2021-11-30

### Commits

- Switched to externally managed Github workflow schema. [`1af0190`](https://github.com/ecmwf/reusable-workflows/commit/1af0190889f3b834b0235f1a3cd3b0f3f5e970b8)
- Added sync workflow. [`81b1847`](https://github.com/ecmwf/reusable-workflows/commit/81b1847a56adbf38fa709c0bb402e495c69e724e)
- Fixed ref names. [`4afe587`](https://github.com/ecmwf/reusable-workflows/commit/4afe5875e504f0431e41d6c9bd2b88c848e7566c)

## v1.0.0 - 2021-11-29

### Commits

- Added support for linting workflows. [`8671720`](https://github.com/ecmwf/reusable-workflows/commit/8671720573276b31c19b77c242b0d7cdd5ebc736)
- Initial commit. [`454a07d`](https://github.com/ecmwf/reusable-workflows/commit/454a07df5d4459e67ca1a41e389489315b23b473)
- Added CI workflow for NodeJS-based projects. [`1b49089`](https://github.com/ecmwf/reusable-workflows/commit/1b49089bac61310719fa5ea54f78b0d6b45f0601)
