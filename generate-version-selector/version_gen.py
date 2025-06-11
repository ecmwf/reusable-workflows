#! /usr/bin/env python

import requests
import json
import os
import re
import argparse
import sys


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
    API_URL = f"{prefix}/s/api/v2/files/{args.path}"
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
    data: dict = resp.json()

    regex = re.compile(r"^(?:master|main|develop|latest|stable|\d+\.\d+\.\d+)$")
    versions = [
        {
            "name": x["path"],
            "version": x["path"],
            "url": f"{prefix}/{args.path}/{x['path']}",
        }
        for x in data["files"]
        if regex.match(x["path"])
    ]
    resp = requests.put(
        f"{API_URL}/versions.json",
        files={"file": json.dumps(versions).encode("utf-8")},
        headers=headers,
        timeout=30,
    )
    if resp.status_code != 200:
        print(
            f"::error::Uploading versions.json failed with {resp.status_code}: {resp.reason}"
        )


if __name__ == "__main__":
    main()
