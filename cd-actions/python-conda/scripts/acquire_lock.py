#!/usr/bin/env python3
"""Acquire conda index lock and wait for completion"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

# Configuration
LOCK_REPO = "ecmwf/reusable-workflows"
LOCK_WORKFLOW = "conda-index-lock.yml"
MAX_WAIT = 1800  # 30 minutes
POLL_INTERVAL = 10  # seconds


def gh(args):
    """Run gh CLI command"""
    result = subprocess.run(
        ["gh"] + args,
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nexus-url", required=True)
    parser.add_argument("--nexus-token", required=True)
    parser.add_argument("--artifact-name", required=True)
    parser.add_argument("--caller-run-id", required=True)
    parser.add_argument("--caller-repo", required=True)
    parser.add_argument("--gh-pat", required=True)
    args = parser.parse_args()

    # Set GH_TOKEN for all gh commands
    os.environ["GH_TOKEN"] = args.gh_pat

    print("=" * 50)
    print("Conda Index Lock Acquisition")
    print("=" * 50)
    print(f"Caller: {args.caller_repo} (run {args.caller_run_id})")
    print(f"Artifact: {args.artifact_name}")
    print(f"Nexus: {args.nexus_url}")
    print()

    # Dispatch workflow
    print("Dispatching lock workflow...")
    gh([
        "workflow", "run", LOCK_WORKFLOW,
        "--repo", LOCK_REPO,
        "--ref", "main",
        "-f", f"nexus_url={args.nexus_url}",
        "-f", f"nexus_token={args.nexus_token}",
        "-f", f"package_artifact_name={args.artifact_name}",
        "-f", f"caller_run_id={args.caller_run_id}",
        "-f", f"caller_repo={args.caller_repo}",
        "-f", f"gh_pat={args.gh_pat}",
    ])

    time.sleep(5)  # Wait for workflow to appear

    # Find the workflow run
    start_time = datetime.now(timezone.utc).timestamp()
    run_id = None

    for _ in range(30):
        runs = json.loads(gh([
            "run", "list",
            "--repo", LOCK_REPO,
            "--workflow", LOCK_WORKFLOW,
            "--limit", "5",
            "--json", "databaseId,createdAt"
        ]))

        for run in runs:
            created = datetime.fromisoformat(run["createdAt"].replace("Z", "+00:00")).timestamp()
            if created >= start_time - 30:
                run_id = run["databaseId"]
                break

        if run_id:
            break
        time.sleep(1)

    if not run_id:
        print("Error: Could not find dispatched workflow run")
        sys.exit(1)

    print(f"Found workflow run: {run_id}")
    print(f"URL: https://github.com/{LOCK_REPO}/actions/runs/{run_id}")
    print()

    # Wait for completion
    elapsed = 0
    interval = POLL_INTERVAL

    while elapsed < MAX_WAIT:
        data = json.loads(gh([
            "run", "view", str(run_id),
            "--repo", LOCK_REPO,
            "--json", "status,conclusion"
        ]))

        status = data["status"]
        conclusion = data.get("conclusion")

        print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] "
              f"Status: {status}, Conclusion: {conclusion} (elapsed: {elapsed}s)")

        if status == "completed":
            print()
            if conclusion == "success":
                print("✓ Conda indexing successful")
                sys.exit(0)
            else:
                print(f"✗ Failed with conclusion: {conclusion}")
                sys.exit(1)

        time.sleep(interval)
        elapsed += interval
        interval = min(int(interval * 1.5), 60)  # Exponential backoff, max 60s

    print(f"\n✗ Timeout after {MAX_WAIT}s")
    sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
