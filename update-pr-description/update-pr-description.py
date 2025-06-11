#!/usr/bin/env python
import argparse
import os
import re
import sys
import textwrap
from typing import Final

import requests


# ──────────────────────────────────────────────────────────────────────────────
API_ROOT: Final[str] = "https://api.github.com"
# ──────────────────────────────────────────────────────────────────────────────


def compile_block_regex(marker: str) -> re.Pattern[str]:
    """Return a compiled DOTALL regex that captures whatever lies in between
    the marker lines *including* newlines."""
    start = f"<!-- {marker}_BEGIN -->"
    end = f"<!-- {marker}_END -->"
    return re.compile(
        rf"{re.escape(start)}(.*?){re.escape(end)}",
        flags=re.DOTALL,
    )


def get_pr_body(
    owner: str, repo: str, pr_number: int, session: requests.Session, timeout: int
) -> str:
    url = f"{API_ROOT}/repos/{owner}/{repo}/pulls/{pr_number}"
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json().get("body") or ""


def build_new_body(
    existing: str, payload: str, marker: str, regex: re.Pattern[str]
) -> str:
    start = f"<!-- {marker}_BEGIN -->"
    end = f"<!-- {marker}_END -->"
    block = f"{start}\n{payload}\n{end}"
    if regex.search(existing):
        return regex.sub(block, existing)
    sep = "\n\n" if existing.strip() else ""
    return existing + sep + block


def update_pr_body(
    owner: str,
    repo: str,
    pr_number: int,
    body: str,
    session: requests.Session,
    timeout: int,
) -> None:
    url = f"{API_ROOT}/repos/{owner}/{repo}/pulls/{pr_number}"
    response = session.patch(url, json={"body": body}, timeout=timeout)
    response.raise_for_status()


def parse_cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Updates PR-Description with a custom payload, e.g. link to doc")
    parser.add_argument(
        "--repo", required=True, help="owner/repo, e.g. octocat/Hello-World"
    )
    parser.add_argument("--pr", type=int, required=True, help="Pull-request number")
    parser.add_argument(
        "--payload", required=True, help="Text/Markdown to hide between markers"
    )
    parser.add_argument(
        "--marker", default="MARKER", help="Opening marker line for the hidden block"
    )
    parser.add_argument(
        "--timeout", type=int, default=15, help="HTTP timeout (seconds)"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_cli()
    token = os.getenv("GITHUB_TOKEN")
    if token is None:
        sys.exit("Error: GITHUB_TOKEN environment variable is not set.")

    owner, repo = args.repo.split("/", maxsplit=1)

    regex = compile_block_regex(args.marker)

    with requests.Session() as session:
        session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

        current = get_pr_body(owner, repo, args.pr, session, args.timeout)
        updated = build_new_body(
            existing=current,
            payload=args.payload,
            marker=args.marker,
            regex=regex,
        )

        if updated == current:
            print("No update: payload already present and identical.")
            return

        update_pr_body(owner, repo, args.pr, updated, session, args.timeout)
        print(f"PR #{args.pr} description updated successfully.")


if __name__ == "__main__":
    main()
