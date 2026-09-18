"""Exact-commit CI gate. Uses gh authentication; never checks out CI-run code."""
import json
import os
import re
import subprocess
import time
from urllib.parse import quote


def select_run(runs, sha, repository, events, branches):
    eligible = [
        run for run in runs
        if run['head_sha'] == sha
        and run['event'] in events
        and run['head_branch'] in branches
        and (run.get('head_repository') or {}).get('full_name') == repository
    ]
    # Never fall back to an older green run when a newer run failed or is pending.
    return max(eligible, key=lambda run: run['id'], default=None)


def verdict(run):
    if run is None or run['status'] != 'completed':
        return False
    if run['conclusion'] != 'success':
        raise RuntimeError(f"CI concluded {run['conclusion']}: {run['html_url']}")
    return True


def main():
    sha = os.environ['CI_SOURCE_SHA']
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('source_sha must be a full commit SHA')
    repository = os.environ['GITHUB_REPOSITORY']
    events = set(filter(None, os.environ['CI_ALLOWED_EVENTS'].split(',')))
    branches = set(filter(None, os.environ['CI_ALLOWED_BRANCHES'].split(',')))
    if not events or not branches:
        raise ValueError('Explicit allowed events and branches are required')
    timeout = int(os.environ['CI_TIMEOUT_SECONDS'])
    if not 1 <= timeout <= 7200:
        raise ValueError('timeout_seconds must be between 1 and 7200')
    deadline = time.monotonic() + timeout
    workflow = quote(os.environ['CI_WORKFLOW'], safe='')
    endpoint = f'repos/{repository}/actions/workflows/{workflow}/runs?head_sha={sha}&per_page=100'
    while True:
        result = subprocess.run(
            ['gh', 'api', '--paginate', '--slurp', endpoint],
            check=True, capture_output=True, text=True, timeout=60,
        )
        runs = [run for page in json.loads(result.stdout) for run in page['workflow_runs']]
        run = select_run(runs, sha, repository, events, branches)
        if verdict(run):
            url = run['html_url']
            with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
                output.write(f'run_url={url}\n')
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
                summary.write(f'### CI gate passed\n\nSource: `{sha}`\n\nValidated by: {url}\n')
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(f'No completed successful eligible CI run for {sha} before timeout')
        print(f'Waiting for CI for {sha}: {run["html_url"] if run else "no eligible run yet"}', flush=True)
        time.sleep(min(30, remaining))


if __name__ == '__main__':
    main()
