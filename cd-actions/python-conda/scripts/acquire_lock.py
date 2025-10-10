#!/usr/bin/env python3
"""Acquire conda index lock and wait for completion"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# Configuration
LOCK_REPO = "ecmwf/reusable-workflows"
LOCK_WORKFLOW = "conda-index-lock.yml"
MAX_WAIT = 1800  # 30 minutes
POLL_INTERVAL = 10  # seconds
GITHUB_API = "https://api.github.com"


def gh_api_request(endpoint, method="GET", data=None, token=None):
    """Make GitHub API request"""
    url = f"{GITHUB_API}{endpoint}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request(url, headers=headers, method=method)
    if data:
        req.data = json.dumps(data).encode('utf-8')
        req.add_header('Content-Type', 'application/json')

    try:
        with urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as e:
        error_body = e.read().decode('utf-8')
        raise Exception(f"GitHub API error {e.code}: {error_body}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nexus-url", required=True)
    parser.add_argument("--nexus-token", required=True)
    parser.add_argument("--artifact-name", required=True)
    parser.add_argument("--caller-run-id", required=True)
    parser.add_argument("--caller-repo", required=True)
    parser.add_argument("--gh-pat", required=True)
    args = parser.parse_args()

    print("=" * 50)
    print("Conda Index Lock Acquisition")
    print("=" * 50)
    print(f"Caller: {args.caller_repo} (run {args.caller_run_id})")
    print(f"Artifact: {args.artifact_name}")
    print(f"Nexus: {args.nexus_url}")
    print()

    # Dispatch workflow
    print("Dispatching lock workflow...")
    gh_api_request(
        f"/repos/{LOCK_REPO}/actions/workflows/{LOCK_WORKFLOW}/dispatches",
        method="POST",
        data={
            "ref": "cd-actions",
            "inputs": {
                "nexus_url": args.nexus_url,
                "nexus_token": args.nexus_token,
                "package_artifact_name": args.artifact_name,
                "caller_run_id": args.caller_run_id,
                "caller_repo": args.caller_repo,
            }
        },
        token=args.gh_pat
    )

    time.sleep(5)  # Wait for workflow to appear

    # Find the workflow run
    start_time = datetime.now(timezone.utc).timestamp()
    run_id = None

    for _ in range(30):
        runs = gh_api_request(
            f"/repos/{LOCK_REPO}/actions/workflows/{LOCK_WORKFLOW}/runs?per_page=5",
            token=args.gh_pat
        )

        for run in runs.get("workflow_runs", []):
            created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00")).timestamp()
            if created >= start_time - 30:
                run_id = run["id"]
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
        data = gh_api_request(
            f"/repos/{LOCK_REPO}/actions/runs/{run_id}",
            token=args.gh_pat
        )

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
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
