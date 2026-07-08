#! /usr/bin/env python

import requests
import json
import os
import re
import argparse
import sys


def join_url(*parts):
    """Join URL/path segments with a single '/', dropping empty segments
    (e.g. an empty --path) so no double slashes are produced."""
    return "/".join(p.strip("/") for p in parts if p)


def parse_cli_args():
    parser = argparse.ArgumentParser(exit_on_error=False)
    parser.add_argument("--path", required=True)
    parser.add_argument("--space", required=True)
    parser.add_argument("--name", required=True)
    try:
        return parser.parse_args()
    except Exception as e:
        print(f"::error::Error calling version_gen.py: {e}")
        sys.exit(1)


def main():
    """
    This short program will list all directories non- recursively on a path in
    sites.ecmwf and generate a 'versions.json' from all paths that match a
    version number X.X.X or one of the following names: master, main, develop.

    The resulting versions.json is then uploaded to the same path that has been
    scanned. This versions.json is supposed to be read by sphinx-version selector
    to populate the version selection drop-down menu.

    Example:
    When scanning the below layout with 'documentation' as path a corresponding
    version.json will be created

    Layout:
    my_documentation
    ├── 1.0.0
    ├── 1.0.1
    ├── 1.0.2
    ├── 1.1.0
    ├── pull-requests # <= this path will be ignored
    ├── develop
    └── main

    version.json:
    {
        {"name": "1.0.0", "version": "1.0.0", "url": "sites.ecmwf.int/<space>/<name>/<path>/1.0.0"},
        {"name": "1.0.1", "version": "1.0.1", "url": "sites.ecmwf.int/<space>/<name>/<path>/1.0.1"},
        {"name": "1.0.2", "version": "1.0.2", "url": "sites.ecmwf.int/<space>/<name>/<path>/1.0.2"},
        {"name": "1.1.0", "version": "1.1.0", "url": "sites.ecmwf.int/<space>/<name>/<path>/1.1.0"},
        {"name": "develop", "version": "develop", "url": "sites.ecmwf.int/<space>/<name>/<path>/develop"},
        {"name": "master", "version": "master", "url": "sites.ecmwf.int/<space>/<name>/<path>/master"},
    }
    """
    args = parse_cli_args()

    prefix = f"https://sites.ecmwf.int/{args.space}/{args.name}"
    API_URL = join_url(prefix, "s/api/v2/files", args.path)
    headers = {
        "accept": "*/*",
        "Authorization": f"Bearer {os.environ['SITES_TOKEN']}",
    }
    resp = requests.get(
        API_URL,
        headers=headers,
        timeout=30,
        params={"list": "true", "limit": "64000", "type": "d"},
    )
    if resp.status_code != 200:
        print(
            f"::error::Error calling {API_URL} failed with {resp.status_code}: {resp.reason}"
        )
        sys.exit(1)

    try:
        data: dict = resp.json()
    except ValueError as e:
        print(
            f"::error::Failed to decode JSON response from {API_URL}: {e}. "
            f"Response was: {resp.text[:500]}"
        )
        sys.exit(1)

    if "files" not in data:
        print(
            f"::error::Unexpected response from {API_URL}: missing 'files' key. "
            f"Response was: {json.dumps(data)[:500]}"
        )
        sys.exit(1)

    regex = re.compile(r"^(?:master|main|develop|latest|stable|\d+\.\d+\.\d+)$")
    versions = [
        {
            "name": x["path"],
            "version": x["path"],
            "url": join_url(prefix, args.path, x["path"]),
        }
        for x in data["files"]
        if regex.match(x["path"])
    ]

    if not versions:
        scanned = [x.get("path") for x in data["files"]]
        preview = scanned[:50]
        suffix = "" if len(scanned) <= 50 else f" (showing first 50 of {len(scanned)})"
        print(
            f"::error::No directories under '{args.path}' matched the expected version "
            f"naming pattern, refusing to overwrite versions.json. "
            f"Directories found{suffix}: {preview}"
        )
        sys.exit(1)

    print(f"Generated versions.json:\n{json.dumps(versions, indent=2)}")

    resp = requests.put(
        join_url(API_URL, "versions.json"),
        files={"file": json.dumps(versions).encode("utf-8")},
        headers=headers,
        timeout=30,
    )
    if resp.status_code != 200:
        print(
            f"::error::Uploading versions.json failed with {resp.status_code}: {resp.reason}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
