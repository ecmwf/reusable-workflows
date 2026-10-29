#!/usr/bin/env python3
"""Acquire conda index lock and wait for completion"""

import argparse
import json
import os
import re
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
# Used when the action's own ref is unknown or is a commit SHA (dispatch needs a branch or tag)
FALLBACK_LOCK_REF = "v2"
CHANNELS = ("test", "production")


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


def _usable_ref(ref):
    """A dispatch ref must be a branch or tag name, not empty and not a commit SHA."""
    ref = (ref or "").strip()
    if not ref or re.fullmatch(r"[0-9a-fA-F]{40}", ref):
        return None
    return ref


def resolve_lock_ref(lock_ref=None, action_path=None):
    """Pick the reusable-workflows ref to dispatch conda-index-lock.yml at.

    The lock workflow must come from the same ref as this action, since they
    agree on the dispatch inputs. github.action_ref can be empty inside
    composite actions, so fall back to the ref in the action's checkout path
    (.../_actions/ecmwf/reusable-workflows/<ref>/cd-actions/conda), then to v2.
    """
    ref = _usable_ref(lock_ref) or _usable_ref(os.environ.get("GITHUB_ACTION_REF"))
    if ref:
        return ref
    action_path = action_path if action_path is not None else os.environ.get("GITHUB_ACTION_PATH", "")
    marker = f"/_actions/{LOCK_REPO}/"
    if marker in action_path:
        rest = action_path.split(marker, 1)[1]
        if "/cd-actions/" in rest:
            ref = _usable_ref(rest.split("/cd-actions/", 1)[0])
            if ref:
                return ref
    return FALLBACK_LOCK_REF


def build_dispatch_payload(lock_ref, channel, artifact_name, caller_run_id, caller_repo, dispatch_id):
    """Dispatch payload for conda-index-lock.yml. It never carries credentials."""
    return {
        "ref": lock_ref,
        "inputs": {
            "channel": channel,
            "package_artifact_name": artifact_name,
            "caller_run_id": caller_run_id,
            "caller_repo": caller_repo,
            "dispatch_id": dispatch_id,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True, choices=CHANNELS)
    parser.add_argument("--artifact-name", required=True)
    parser.add_argument("--caller-run-id", required=True)
    parser.add_argument("--caller-repo", required=True)
    parser.add_argument("--lock-ref", default=None, help="reusable-workflows ref to dispatch the lock workflow at (default: this action's ref)")
    args = parser.parse_args()

    # Read from the environment so the PAT never appears on a command line
    gh_pat = os.environ.get("GH_PAT", "")
    if not gh_pat:
        print("Error: GH_PAT is not set", file=sys.stderr)
        sys.exit(1)
    lock_ref = resolve_lock_ref(args.lock_ref)

    print("=" * 50)
    print("Conda Index Lock Acquisition")
    print("=" * 50)
    print(f"Caller: {args.caller_repo} (run {args.caller_run_id})")
    print(f"Artifact: {args.artifact_name}")
    print(f"Channel: {args.channel}")
    print(f"Lock workflow: {LOCK_REPO}/{LOCK_WORKFLOW}@{lock_ref}")
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
        data=build_dispatch_payload(
            lock_ref, args.channel, args.artifact_name, args.caller_run_id, args.caller_repo, dispatch_id
        ),
        token=gh_pat,
    )

    time.sleep(5)  # Wait for workflow to appear

    # Find the exact workflow run for this dispatch. Matrix cells can dispatch this
    # workflow concurrently, so creation time alone is not a safe discriminator.
    run_id = None

    for _ in range(60):
        run_id = find_dispatched_run(dispatch_id, start_time, gh_pat)
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
        data = gh_api_request(f"/repos/{LOCK_REPO}/actions/runs/{run_id}", token=gh_pat)

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
