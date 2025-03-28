# reusable-workflows

[![Changelog](https://img.shields.io/github/package-json/v/ecmwf/reusable-workflows)](CHANGELOG.md)
[![Build Status](https://img.shields.io/github/actions/workflow/status/ecmwf/reusable-workflows/test.yml?branch=main)](https://github.com/ecmwf/reusable-workflows/actions/workflows/test.yml)
[![Licence](https://img.shields.io/github/license/ecmwf/reusable-workflows)](https://github.com/ecmwf/reusable-workflows/blob/develop/LICENSE)

A collection of [reusable GitHub workflows] for ECMWF repositories.

## Workflows

- [ci.yml](#ciyml): Continuous Integration workflow for ecbuild/CMake-based projects
- [ci-hpc.yml](#ci-hpcyml): Continuous Integration workflow for ecbuild/CMake-based projects on HPC
- [ci-python.yml](#ci-pythonyml): Continuous Integration and Continuous Deployment workflow for Python-based projects
- [ci-node.yml](#ci-nodeyml): Continuous Integration workflow for NodeJS-based projects
- [docs.yml](#docsyml): Workflow for testing Sphinx-based documentation
- [qa-precommit-run.yml](#qa-precommit): Runs the pre-commit hooks on all files server-side as a QA drop-in.
- [qa-pytest-pyproject.yml](#qa-pytest-pyproject): Runs pytest after a `pyproject.toml` install with a markdown report.
- [sync.yml](#syncyml): Workflow for syncing a Git repository

[Samples]

## Supported Operating Systems

- Linux
- macOS

## ci.yml

### Usage

```yaml
jobs:
  # Calls a reusable CI workflow to build & test current repository.
  #   It will pull in all needed dependencies and produce a code coverage report on success.
  #   In case the job fails, a message will be posted to a Microsoft Teams channel.
  ci:
    name: ci
    uses: ecmwf/reusable-workflows/.github/workflows/ci.yml@v1
    with:
      codecov_upload: true
      notify_teams: true
      build_package_inputs: |
        dependencies: |
          ecmwf/ecbuild
          ecmwf/eckit
        dependency_branch: develop
    secrets:
      incoming_webhook: ${{ secrets.MS_TEAMS_INCOMING_WEBHOOK }}
```

### Inputs

#### `skip_matrix_jobs`

A list of matrix jobs to skip. Job names should be the full form of `<compiler>@<platform>`.
**Default:** `''`
**Type:** `string`

#### `deps_cache_key`

Dependency cache key to restore from. Note that the key should be platform agnostic, as the `<compiler>@<platform>` suffix will be automatically appended. Upon extraction, a file called `.env` from the cache root directory will be loaded into the build environment, if it exists.
**Default:** `''`
**Type:** `string`

#### `deps_cache_path`

Optional dependency cache path to restore to, falls back to `${{ runner.temp }}/deps`. Will be considered only if [deps_cache_key](#deps_cache_key) is supplied.
**Default:** `''`
**Type:** `string`

#### `codecov_upload`

Whether to generate and upload code coverage to [codecov service] for main branches.
**Default:** `false`
**Type:** `boolean`

#### `notify_teams`

Whether to notify about workflow status via Microsoft Teams. Note that you must supply [incoming_webhook](#incoming_webhook) secret if you switch on this feature.
**Default:** `false`
**Type:** `boolean`

#### `repository`

The source repository name, in case it differs from the current one. Repository names should follow the standard Github `owner/name` format.
**Default:** `${{ github.repository }}`
**Type:** `string`

#### `ref`

The source repository reference, in case it differs from the current one.
**Default:** `${{ github.ref }}`
**Type:** `string`

#### `build_package_inputs`

Optional [inputs for the build-package] action, provided as a YAML object value.
**Default:** `''`
**Type:** `string`

### Secrets

#### `incoming_webhook`

Public URL of the Microsoft Teams incoming webhook. To get the value, make sure that channel in Teams has the appropriate connector set up. It will only be used if [notify_teams](#notify_teams) input is switched on.
**Example:** `https://webhook.office.com/webhookb2/...`

## ci-hpc.yml

### Usage

```yaml
jobs:
  ci-hpc:
    name: ci-hpc
    uses: ecmwf/reusable-workflows/.github/workflows/ci-hpc.yml@v2
    with:
      name-prefix: metkit-
      build-inputs: |
        --package: ecmwf/metkit@develop
        --modules: |
          ecbuild
          ninja
        --dependencies: |
          ecmwf/eccodes@develop
          ecmwf/eckit@develop
        --parallel: 64
    secrets: inherit\
```

### Inputs

#### `name-prefix`

Job name prefix. Usually the package name. Suitable when building multiple packages within one workflow to easily differentiate between them.
**Default:** `''`
**Type:** `string`

#### `build-inputs`

Inputs for `build-package-hpc` action.
**Default:** `''`
**Type:** `string`

#### `dev-runner`

Whether to build using development runner which contains latest version of `build-package-hpc`.
**Default:** `''`
**Type:** `string`

## ci-python.yml

### Usage

```yaml
jobs:
  # Calls a reusable CI workflow to qa, test & deploy the current repository.
  #   It will pull in all needed dependencies and produce a code coverage report on success.
  #   If all checks were successful and a new release tag pushed, the package will be published on PyPI.
  #   In case the job fails, a message will be posted to a Microsoft Teams channel.
  ci:
    name: ci
    uses: ecmwf/reusable-workflows/.github/workflows/ci-python.yml@v1
    with:
      codecov_upload: true
      notify_teams: true
      build_package_inputs: |
        dependencies: |
          ecmwf/ecbuild
          ecmwf/eckit
          ecmwf/odc
        dependency_branch: develop
        self_build: false
    secrets:
      pypi_username: ${{ secrets.PYPI_USERNAME }}
      pypi_password: ${{ secrets.PYPI_PASSWORD }}
      incoming_webhook: ${{ secrets.MS_TEAMS_INCOMING_WEBHOOK }}
```

### Inputs

#### `skip_matrix_jobs`

A list of matrix jobs to skip. Job names should be the full form of `<compiler>@<platform>`.
**Default:** `''`
**Type:** `string`

#### `codecov_upload`

Whether to generate and upload code coverage to [codecov service] for main branches.
**Default:** `false`
**Type:** `boolean`

#### `notify_teams`

Whether to notify about workflow status via Microsoft Teams. Note that you must supply [incoming_webhook](#incoming_webhook-1) secret if you switch on this feature.
**Default:** `false`
**Type:** `boolean`

#### `python_version`

The version of Python binary to use.
**Default:** `'3.9'`
**Type:** `ring`

#### `repository`

The source repository name. Repository names should follow the standard Github `owner/name` format.
**Default:** `${{ github.repository }}`
**Type:** `string`

#### `ref`

The source repository reference.
**Default:** `${{ github.ref }}`
**Type:** `string`

#### `build_package_inputs`

Optional [inputs for the build-package] action, provided as a YAML object value.
**Default:** `''`
**Type:** `string`

### Secrets

#### `pypi_username`

Username of the PyPI account. The account must have sufficient permissions to deploy the current project.
**Example:** `MyUsername`

#### `pypi_password`

Password of the PyPI account.
**Example:** `MyPassword`

#### `incoming_webhook`

Public URL of the Microsoft Teams incoming webhook. To get the value, make sure that channel in Teams has the appropriate connector set up. It will only be used if [notify_teams](#notify_teams-1) input is switched on.
**Example:** `https://webhook.office.com/webhookb2/...`

## ci-node.yml

### Usage

```yaml
jobs:
  # Calls a reusable CI NodeJS workflow to qa & test & deploy the current repository.
  #   It will install dependencies and produce a code coverage report on success.
  #   In case the job fails, a message will be posted to a Microsoft Teams channel.
  ci:
    name: ci
    uses: ecmwf/reusable-workflows/.github/workflows/ci-node.yml@v1
    with:
      codecov_upload: true
      notify_teams: true
    secrets:
      incoming_webhook: ${{ secrets.MS_TEAMS_INCOMING_WEBHOOK }}
```

### Inputs

#### `skip_matrix_jobs`

A list of matrix jobs to skip. Job names should be the form of `<platform>`.
**Default:** `''`
**Type:** `string`

#### `codecov_upload`

Whether to generate and upload code coverage to [codecov service] for main branches.
**Default:** `false`
**Type:** `boolean`

#### `notify_teams`

Whether to notify about workflow status via Microsoft Teams. Note that you must supply [incoming_webhook](#incoming_webhook-2) secret if you switch on this feature.
**Default:** `false`
**Type:** `boolean`

#### `self_build`

Whether to build from currently checked out repository or not.
**Default:** `true`
**Type:** `boolean`

#### `self_test`

Whether to run tests from currently checked out repository or not.
**Default:** `true`
**Type:** `boolean`

#### `node_version`

The version of NodeJS interpreter to use.
**Default:** `'16'`
**Type:** `string`

#### `repository`

The source repository name. Repository names should follow the standard Github `owner/name` format.
**Default:** `${{ github.repository }}`
**Type:** `string`

#### `ref`

The source repository reference.
**Default:** `${{ github.ref }}`
**Type:** `string`

### Secrets

#### `incoming_webhook`

Public URL of the Microsoft Teams incoming webhook. To get the value, make sure that channel in Teams has the appropriate connector set up. It will only be used if [notify_teams](#notify_teams-2) input is switched on.
**Example:** `https://webhook.office.com/webhookb2/...`

## docs.yml

### Usage

```yaml
jobs:
  # Calls a reusable CI workflow to build & check the documentation in the current repository.
  #   It will install required system dependencies and test Read the Docs build process.
  docs:
    name: docs
    uses: ecmwf/reusable-workflows/.github/workflows/docs.yml@v1
    with:
      system_dependencies: doxygen pandoc
```

### Inputs

#### `requirements_path`

Path of the `requirements.txt` file which includes all dependencies needed for building of the documentation, relative to the repository root.
**Default:** `docs/requirements.txt`
**Type:** `string`

#### `docs_path`

Path of the documentation directory, relative to the repository root.
**Default:** `docs`
**Type:** `string`

#### `system_dependencies`

Optional list of system dependencies to install via `apt` command, separated by spaces. Note that each dependency must be available via standard Ubuntu 20.04 package repositories.
**Default:** `''`
**Type:** `string`

#### `python_version`

The version of Python binary to use.
**Default:** `'3.9'`
**Type:** `ring`

#### `repository`

The source repository name, in case it differs from the current one. Repository names should follow the standard Github `owner/name` format.
**Default:** `${{ github.repository }}`
**Type:** `string`

#### `ref`

The source repository reference, in case it differs from the current one.
**Default:** `${{ github.ref }}`
**Type:** `string`

## qa-precommit

### Usage

```yaml
on:
  push:
  pull_request_target:
    types: [opened, synchronize, reopened]

jobs:
  quality:
    uses: ecmwf/reusable-workflows/.github/workflows/qa-precommit-run.yml@v2
    with:
      skip_hooks: "no-commit-to-branch"
```

### Inputs

#### `python-version`

Optional, pin to use a specific Python version
**Default:** `'3.x'`
**Type:** `string`
**Example:** `'3.9'`

#### `skip-hooks`

Optional, a comma-separated string of pre-commit hooks to skip.
**Default:** `''`
**Type:** `string`
**Example:** `'no-commit-to-branch,black'`

## qa-pytest-pyproject

### Usage

```yaml
on:
  push:
  pull_request_target:
    types: [opened, synchronize, reopened]

jobs:
  checks:
    strategy:
      matrix:
        python-version: ["3.9", "3.10"]
    uses: ecmwf/reusable-workflows/.github/workflows/qa-pytest-pyproject.yml@v2
    with:
      python-version: ${{ matrix.python-version }}
```

### Inputs

#### `python-version`

Optional, the version of Python binary to use.

**Default:** `'3.x'`
**Type:** `string`
**Example:** `'3.9'`

#### `optional-dependencies`

Optional, optional dependencies to install from package to be tested.

**Default:** `'all,tests'`
**Type:** `string`
**Example:** `dev,tests,third_dependency_group`

#### `install-dependencies`

Optional, perform or skip dependency installation.

This enables the external installation of dependencies.

**Default:** `true`
**Type:** `boolean`
**Example:** `false`

#### `skip-tests`

Optional, the pytest marks to pass to the `-m` command flag.

Expands in `pytest -v -m "${{ inputs.skip-tests }}"` to coordinate marked tests.

**Default:** `''`
**Type:** `string`
**Example:** `'no gpu'`

#### `job-summary`

**Default:** `false`
**Type:** `boolean`
**Example:** `true`

#### `emoji`

**Default:** `true`
**Type:** `boolean`
**Example:** `false`

#### `custom-pytest`

**Default:** `'pytest'`
**Type:** `string`
**Example:** `'poetry run pytest'`

## sync.yml

### Usage

```yaml
# Controls when the workflow will run
on:
  # Trigger the workflow on all pushes
  push:
    branches:
      - "**"
    tags:
      - "**"

  # Trigger the workflow when a branch or tag is deleted
  delete: ~

jobs:
  # Calls a reusable CI workflow to sync the current with a remote repository.
  #   It will correctly handle addition of any new and removal of existing Git objects.
  sync:
    name: sync
    uses: ecmwf/reusable-workflows/.github/workflows/sync.yml@v1
    secrets:
      target_repository: ${{ secrets.BITBUCKET_REPOSITORY }}
      target_username: ${{ secrets.BITBUCKET_USERNAME }}
      target_token: ${{ secrets.BITBUCKET_PAT }}
```

### Inputs

#### `sync_repository_inputs`

Optional [inputs for the sync-repository] action, provided as a YAML object value. Note that some values may be overwritten by provided secrets with same name.
**Default:** `''`
**Type:** `string`

### Secrets

#### `source_token`

The user access token with read access to the source repository, must be URL-encoded.
**Default:** `github.token`
**Example:** `...`

#### `target_repository`

**Required** The name of the target repository.
**Example:** `project-name/repo-name`

#### `target_username`

**Required** The user login with write access to the target repository, must be URL-encoded.
**Example:** `user`

#### `target_token`

**Required** The user access token with write access to the target repository, must be URL-encoded.
**Example:** `...`

## label-pr.yml

Manages labels on public pull requests. `contributor` label is added when a PR from public fork is opened. Removes label `approved-for-ci` when pull request HEAD changes.

### Usage

```yaml
on:
  # trigger the pull request is opened or pushed to
  pull_request_target:
    types: [opened, synchronize]

jobs:
  label:
    uses: ecmwf/reusable-workflows/.github/workflows/pr-label.yml@v2
```

## Development

### Install Dependencies

```
npm install
```

### Lint Code

```
npm run lint
```

## Licence

This software is licensed under the terms of the Apache License Version 2.0 which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.

In applying this licence, ECMWF does not waive the privileges and immunities granted to it by virtue of its status as an intergovernmental organisation nor does it submit to any jurisdiction.

[reusable GitHub workflows]: https://docs.github.com/en/actions/learn-github-actions/reusing-workflows
[Samples]: https://github.com/ecmwf/reusable-workflows/tree/develop/samples
[codecov service]: https://codecov.io
[inputs for the build-package]: https://github.com/ecmwf/build-package#inputs
[inputs for the sync-repository]: https://github.com/ecmwf/sync-repository#inputs
