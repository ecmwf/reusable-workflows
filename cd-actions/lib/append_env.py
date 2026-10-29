#!/usr/bin/env python3
"""Append validated KEY=value lines from $ENV_LINES to $GITHUB_ENV.

Each non-empty line must be a plain KEY=value assignment. Names that change how
later steps or the runner behave (PATH, LD_*, GITHUB_*, ...) are refused.
"""

from __future__ import annotations

import os
import re
import sys

NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
DENIED_NAMES = {"PATH", "BASH_ENV", "ENV", "NODE_OPTIONS"}
DENIED_PREFIXES = ("LD_", "GITHUB_", "RUNNER_", "ACTIONS_")


def validate_lines(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if not NAME_RE.match(line):
            raise ValueError(f"Invalid environment line (expected KEY=value): {line.split('=', 1)[0]!r}")
        name = line.split("=", 1)[0]
        if name.upper() in DENIED_NAMES or name.upper().startswith(DENIED_PREFIXES):
            raise ValueError(f"Setting {name} through env vars is not allowed")
        lines.append(line)
    return lines


def main() -> int:
    try:
        lines = validate_lines(os.environ.get("ENV_LINES", ""))
    except ValueError as e:
        print(f"::error::{e}", file=sys.stderr)
        return 1
    with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as f:
        for line in lines:
            f.write(f"{line}\n")
            print(f"Set {line.split('=', 1)[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
