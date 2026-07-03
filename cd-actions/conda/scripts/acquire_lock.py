#!/usr/bin/env python3
"""Acquire conda index lock and wait for completion"""

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# Configuration
LOCK_REPO = "ecmwf/reusable-workflows"
LOCK_WORKFLOW = "conda-index-lock.yml"
MAX_WAIT = 1800  # 30 minutes
POLL_INTERVAL = 10  # seconds
GITHUB_API = "https://api.github.com"
RUNS_PER_PAGE = 100


def gh_api_request(endpoint, method="GET", data=None, token=None):
    """Make GitHub API request"""
    url = f"{GITHUB_API}{endpoint}"
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request(url, headers=headers, method=method)
    if data:
        req.data = json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req) as response:
            body = response.read().decode("utf-8")
            # 204 No Content responses have no body
            if not body:
                return None
            return json.loads(body)
    except HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise Exception(f"GitHub API error {e.code}: {error_body}") from e


def find_dispatched_run(dispatch_id, start_time, token):
    """Find a dispatched workflow run, paging back through its creation window."""
    earliest_created = start_time - 30
    page = 1

    while True:
        runs = gh_api_request(
            f"/repos/{LOCK_REPO}/actions/workflows/{LOCK_WORKFLOW}/runs"
            f"?event=workflow_dispatch&per_page={RUNS_PER_PAGE}&page={page}",
            token=token,
        ).get("workflow_runs", [])

        if not runs:
            return None

        for run in runs:
            created = datetime.fromisoformat(
                run["created_at"].replace("Z", "+00:00")
            ).timestamp()
            if created < earliest_created:
                return None

            title = run.get("display_title") or run.get("name") or ""
            if dispatch_id in title:
                return run["id"]

        if len(runs) < RUNS_PER_PAGE:
            return None

        page += 1


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

    dispatch_id = f"{args.caller_repo.replace('/', '-')}-{args.caller_run_id}-{args.artifact_name}-{uuid.uuid4().hex[:12]}"
    expected_title_fragment = f"{args.artifact_name} from {args.caller_repo}#{args.caller_run_id} ({dispatch_id})"

    # Dispatch workflow
    print("Dispatching lock workflow...")
    print(f"Dispatch ID: {dispatch_id}")
    start_time = datetime.now(timezone.utc).timestamp()
    gh_api_request(
        f"/repos/{LOCK_REPO}/actions/workflows/{LOCK_WORKFLOW}/dispatches",
        method="POST",
        data={
            "ref": "cd-actions-tests-config-refactor",
            "inputs": {
                "nexus_url": args.nexus_url,
                "nexus_token": args.nexus_token,
                "package_artifact_name": args.artifact_name,
                "caller_run_id": args.caller_run_id,
                "caller_repo": args.caller_repo,
                "dispatch_id": dispatch_id,
            },
        },
        token=args.gh_pat,
    )

    time.sleep(5)  # Wait for workflow to appear

    # Find the exact workflow run for this dispatch. Matrix cells can dispatch this
    # workflow concurrently, so creation time alone is not a safe discriminator.
    run_id = None

    for _ in range(60):
        run_id = find_dispatched_run(dispatch_id, start_time, args.gh_pat)
        if run_id:
            break
        time.sleep(2)

    if not run_id:
        print(f"Error: Could not find dispatched workflow run for dispatch ID {dispatch_id}")
        print(f"Expected run name to contain: {expected_title_fragment}")
        sys.exit(1)

    print(f"Found workflow run: {run_id}")
    print(f"URL: https://github.com/{LOCK_REPO}/actions/runs/{run_id}")
    print()

    # Wait for completion
    elapsed = 0
    interval = POLL_INTERVAL

    while elapsed < MAX_WAIT:
        data = gh_api_request(f"/repos/{LOCK_REPO}/actions/runs/{run_id}", token=args.gh_pat)

        status = data["status"]
        conclusion = data.get("conclusion")

        print(
            f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] "
            f"Status: {status}, Conclusion: {conclusion} (elapsed: {elapsed}s)"
        )

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
