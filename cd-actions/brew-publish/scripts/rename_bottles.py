#!/usr/bin/env python3
"""Rename Homebrew bottle files from local_filename to the canonical filename.

Homebrew's `brew bottle --json` produces files with local_filename (using double
dashes) that need to be renamed to the canonical filename format for upload.
"""

import argparse
import glob
import json
import os
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="Rename Homebrew bottle files")
    parser.add_argument("--dir", required=True, help="Directory containing bottle JSON and tar.gz files")
    return parser.parse_args()


def main():
    args = parse_args()
    bottle_dir = args.dir

    json_files = glob.glob(os.path.join(bottle_dir, "*.bottle.json"))
    if not json_files:
        print(f"No bottle JSON files found in {bottle_dir}")
        sys.exit(0)

    for json_file in json_files:
        print(f"Processing: {json_file}")
        with open(json_file) as f:
            data = json.load(f)

        for formula_name, formula_data in data.items():
            bottle_info = formula_data.get("bottle", {})
            tags = bottle_info.get("tags", {})

            for tag, tag_info in tags.items():
                local_filename = tag_info.get("local_filename", "")
                canonical_filename = tag_info.get("filename", "")

                if not local_filename or not canonical_filename:
                    print(f"  Skipping tag {tag}: missing filename info")
                    continue

                if local_filename == canonical_filename:
                    print(f"  {tag}: filenames match, no rename needed")
                    continue

                src = os.path.join(bottle_dir, local_filename)
                dst = os.path.join(bottle_dir, canonical_filename)

                if os.path.exists(src):
                    os.rename(src, dst)
                    print(f"  Renamed: {local_filename} -> {canonical_filename}")
                else:
                    print(f"  WARNING: Source file not found: {src}")


if __name__ == "__main__":
    main()
