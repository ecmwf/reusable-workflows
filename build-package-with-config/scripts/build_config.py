"""Helpers for merging the build-package-with-config build configuration."""

import json
import os
import sys

import yaml


def parse_repository(repository):
    """Split a ``packageName:owner/repo@ref`` repository input into (repo, ref)."""
    if ":" in repository:
        _, repository = repository.split(":")
    repo, ref = repository.split("@")
    if repo.count("/") > 1:
        owner, repo, _ = repo.split("/", maxsplit=2)
        repo = f"{owner}/{repo}"
    return repo, ref


def _parse_override_key(key):
    """Normalize an ``overrides`` key into a (compiler, os) pattern tuple.

    Bare keys are matrix.os names; ``<compiler>@<os>`` keys may use ``*`` as
    either segment to match any value.
    """
    if not isinstance(key, str) or not key:
        raise ValueError(
            "`overrides` keys in build config must be non-empty strings, "
            "either `<os>` or `<compiler>@<os>`"
        )
    if "@" in key:
        compiler, _, os_name = key.partition("@")
        if "@" in os_name or not compiler or not os_name:
            raise ValueError(
                "`overrides` key %r in build config must be `<os>` or `<compiler>@<os>`,"
                " with `*` as a wildcard segment" % key
            )
    else:
        compiler, os_name = "*", key
    if compiler == "*" and os_name == "*":
        raise ValueError(
            "`overrides` key %r in build config matches every job, "
            "move its entries into the base config instead" % key
        )
    return compiler, os_name


def apply_overrides(config, matrix_os, matrix_compiler):
    """Shallow-merge the ``overrides`` sections matching the matrix job into config."""
    overrides = config.pop("overrides", None)
    if overrides is None:
        return config
    if not isinstance(overrides, dict):
        raise ValueError(
            "`overrides` in build config must be a mapping of `<os>` or "
            "`<compiler>@<os>` keys to config mappings"
        )
    sections = {}
    for key, section in overrides.items():
        pattern = _parse_override_key(key)
        if pattern in sections:
            raise ValueError(
                "`overrides` keys %r and `%s@%s` in build config are the same pattern"
                % (key, *pattern)
            )
        if section is not None and not isinstance(section, dict):
            raise ValueError(
                "`overrides` section for %r in build config must be a mapping of config keys"
                % key
            )
        if section and "overrides" in section:
            raise ValueError("nested `overrides` are not supported in build config")
        sections[pattern] = section or {}

    def specificity(pattern):
        compiler, os_name = pattern
        return (os_name != "*") * 2 + (compiler != "*")

    matched = [
        pattern
        for pattern in sections
        if pattern[0] in ("*", matrix_compiler) and pattern[1] in ("*", matrix_os)
    ]
    for pattern in sorted(matched, key=specificity):
        config.update(sections[pattern])
    return config


def pop_python_version(config):
    """Pop python_version from config, requiring a quoted string value."""
    value = config.pop("python_version", "")
    if value is None or value == "":
        return ""
    if not isinstance(value, str):
        raise ValueError(
            'python_version in build config must be a quoted string, e.g. "3.10" (got %r)'
            % value
        )
    return value.strip()


def merge_dependencies(config_deps, input_deps):
    """Merge dependency lists in ``owner/repo@ref`` format, input entries winning."""
    deps = {}
    for line in config_deps.splitlines() + input_deps.splitlines():
        repo, *refs = line.split("@")
        deps[repo] = refs[0] if refs else ""
    return "\n".join(f"{k}@{v}" if v else k for k, v in deps.items())


def main_parse_repository():
    repo, ref = parse_repository(os.environ["INPUT_REPOSITORY"])
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        print("repo", repo, sep="=", file=f)
        print("ref", ref, sep="=", file=f)


def main_merge_config():
    inputs = yaml.safe_load(os.environ.get("INPUT_BUILD_PACKAGE_INPUTS", "")) or {}
    token = os.environ.get("INPUT_GITHUB_TOKEN", "")
    if token:
        inputs["github_token"] = token
    print("Inputs:\n", yaml.dump(inputs, sort_keys=False), sep="")

    config_path = os.environ.get("INPUT_BUILD_CONFIG", "")
    if not config_path:
        config = {}
    else:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        config_key = os.environ.get("INPUT_BUILD_CONFIG_KEY", "")
        if config_key:
            config = config[config_key]
        print("Config file:\n", yaml.dump(config, sort_keys=False), sep="")

    matrix_os = os.environ.get("MATRIX_OS", "")
    matrix_compiler = os.environ.get("MATRIX_COMPILER", "")
    config = apply_overrides(config, matrix_os, matrix_compiler)

    input_deps = os.environ.get("INPUT_BUILD_DEPENDENCIES", "")
    if input_deps:
        config["dependencies"] = merge_dependencies(
            config.get("dependencies", ""), input_deps
        )

    config_python_version = pop_python_version(config)
    python_version = os.environ.get("INPUT_PYTHON_VERSION", "") or config_python_version
    config_requirements = config.pop("python_requirements", "") or ""
    python_requirements = (
        os.environ.get("INPUT_PYTHON_REQUIREMENTS", "") or config_requirements
    )

    combined = {**config, **inputs}
    combined["self_coverage"] = os.environ.get("SELF_COVERAGE", "false")

    if python_version or python_requirements:
        combined["cmake_options"] = (
            f'{combined.get("cmake_options", "")}'
            " -DPython3_EXECUTABLE=$RUNNER_TEMP/bpvenv/bin/python"
        )

    print("Combined inputs:\n", yaml.dump(combined, sort_keys=False), sep="")

    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        print("config<<EOF", file=f)
        print(json.dumps(combined, separators=(",", ":")), file=f)
        print("EOF", file=f)
        print(f"python_version={python_version}", file=f)
        print(f"python_requirements={python_requirements}", file=f)


def main(argv):
    commands = {
        "parse-repository": main_parse_repository,
        "merge-config": main_merge_config,
    }
    if len(argv) != 2 or argv[1] not in commands:
        print(f"usage: {argv[0]} {{{'|'.join(commands)}}}", file=sys.stderr)
        raise SystemExit(2)
    commands[argv[1]]()


if __name__ == "__main__":
    main(sys.argv)
