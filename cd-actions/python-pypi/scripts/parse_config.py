#!/usr/bin/env python3
"""Parse Python PyPI build configuration."""

import json
import os
import sys


def main():
    working_directory = os.environ.get("INPUT_WORKING_DIRECTORY", "./")
    buildargs = os.environ.get("INPUT_BUILDARGS", "")
    env_vars_json = os.environ.get("INPUT_ENV_VARS", "").strip()

    # Parse env_vars JSON
    try:
        env_vars = json.loads(env_vars_json) if env_vars_json else {}
    except json.JSONDecodeError as e:
        print(f"Failed to parse env_vars JSON: {e}")
        sys.exit(1)

    testpypi_input = os.environ.get("INPUT_TESTPYPI", "false")
    testpypi = testpypi_input == "true"

    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write(f"working_directory={working_directory}\n")
        f.write(f"buildargs={buildargs}\n")
        f.write(f"testpypi={str(testpypi).lower()}\n")

        # Handle env_vars as multiline output
        if env_vars:
            f.write("env_vars<<EOF\n")
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")
            f.write("EOF\n")

    print(f"Working directory: {working_directory}")
    print(f"Build args: {buildargs}")
    print(f"Test PyPI: {str(testpypi).lower()}")
    if env_vars:
        print(f"Env vars: {list(env_vars.keys())}")


if __name__ == "__main__":
    main()
