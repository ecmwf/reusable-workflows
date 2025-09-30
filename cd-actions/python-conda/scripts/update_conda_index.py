#!/usr/bin/env python3

import argparse
import hashlib
import json
import sys
import tarfile
from pathlib import Path
from typing import Any, Dict

from packaging.version import parse as parse_version


def extract_package_info(package_path: Path) -> Dict[str, Any]:
    print(f"Extracting metadata from: {package_path}")

    metadata = {}
    with tarfile.open(package_path, "r:bz2") as tar:
        try:
            index_member = tar.getmember("info/index.json")
            index_file = tar.extractfile(index_member)

            if index_file is None:
                raise ValueError("Could not read info/index.json from package")

            metadata = json.load(index_file)

            metadata["size"] = package_path.stat().st_size
        except KeyError:
            print(
                f"Error: info/index.json not found in {package_path}", file=sys.stderr
            )
            raise

    md5_hash = hashlib.md5()
    sha256_hash = hashlib.sha256()

    with open(package_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5_hash.update(chunk)
            sha256_hash.update(chunk)

    metadata["md5"] = md5_hash.hexdigest()
    metadata["sha256"] = sha256_hash.hexdigest()

    return metadata


def update_channeldata(
    channeldata_path: Path, package_info: Dict[str, Any], subdir: str
) -> Dict[str, Any]:
    if channeldata_path.exists():
        print(f"Loading existing channeldata from: {channeldata_path}")
        with open(channeldata_path, "r") as f:
            channeldata = json.load(f)
    else:
        print("Creating new channeldata")
        channeldata = {"channeldata_version": 1, "packages": {}, "subdirs": []}

    if "packages" not in channeldata:
        channeldata["packages"] = {}
    if "subdirs" not in channeldata:
        channeldata["subdirs"] = []

    if subdir not in channeldata["subdirs"]:
        channeldata["subdirs"].append(subdir)
        channeldata["subdirs"].sort()

    package_name = package_info.get("name")
    if not package_name:
        print("Warning: Package name not found in metadata")
        return channeldata

    if package_name not in channeldata["packages"]:
        channeldata["packages"][package_name] = {
            "name": package_name,
            "subdirs": [],
            "version": package_info.get("version", ""),
        }

    pkg_entry = channeldata["packages"][package_name]

    current_version = pkg_entry.get("version", "")
    new_version = package_info.get("version", "")
    if new_version and (
        not current_version
        or parse_version(new_version) > parse_version(current_version)
    ):
        pkg_entry["version"] = new_version

    if "subdirs" not in pkg_entry:
        pkg_entry["subdirs"] = []
    if subdir not in pkg_entry["subdirs"]:
        pkg_entry["subdirs"].append(subdir)
        pkg_entry["subdirs"].sort()

    for field in ["description", "summary", "license", "doc_url", "dev_url", "home"]:
        if field in package_info and package_info[field]:
            pkg_entry[field] = package_info[field]

    print(f"Updated channeldata for package: {package_name}")

    return channeldata


def update_repodata(
    repodata_path: Path, package_path: Path, subdir: str
) -> Dict[str, Any]:
    if repodata_path.exists():
        print(f"Loading existing repodata from: {repodata_path}")
        with open(repodata_path, "r") as f:
            repodata = json.load(f)
    else:
        print(f"Creating new repodata for: {subdir}")
        repodata = {
            "info": {"subdir": subdir},
            "packages": {},
            "packages.conda": {},
            "removed": [],
            "repodata_version": 1,
        }

    if "packages" not in repodata:
        repodata["packages"] = {}
    if "packages.conda" not in repodata:
        repodata["packages.conda"] = {}
    if "removed" not in repodata:
        repodata["removed"] = []

    package_info = extract_package_info(package_path)
    package_filename = package_path.name

    if package_filename.endswith(".conda"):
        repodata["packages.conda"][package_filename] = package_info
        print(f"Added/updated package in packages.conda: {package_filename}")
    else:
        repodata["packages"][package_filename] = package_info
        print(f"Added/updated package in packages: {package_filename}")

    return repodata


def main():
    parser = argparse.ArgumentParser(
        description="Update conda repository index with a new package"
    )
    parser.add_argument(
        "package", type=Path, help="Path to the conda package (.tar.bz2 or .conda)"
    )
    parser.add_argument(
        "--repodata-dir",
        type=Path,
        default=Path("."),
        help="Directory containing repodata.json files (default: current directory)",
    )
    parser.add_argument(
        "--subdir",
        help="Subdirectory name (e.g., linux-64, osx-64, noarch). If not provided, will be detected from package path",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for updated repodata.json (default: same as repodata-dir)",
    )

    args = parser.parse_args()

    if not args.package.exists():
        print(f"Error: Package not found: {args.package}", file=sys.stderr)
        sys.exit(1)

    subdir = args.subdir
    if not subdir:
        parent_dir = args.package.parent.name
        if parent_dir in ["linux-64", "osx-64", "osx-arm64", "win-64", "noarch"]:
            subdir = parent_dir
        else:
            print(
                "Error: Could not detect subdir from package path. Please specify --subdir",
                file=sys.stderr,
            )
            sys.exit(1)

    print(f"Processing package for subdir: {subdir}")

    repodata_path = args.repodata_dir / subdir / "repodata.json"
    output_dir = args.output_dir if args.output_dir else args.repodata_dir
    output_path = output_dir / subdir / "repodata.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        repodata = update_repodata(repodata_path, args.package, subdir)

        print(f"Writing updated repodata to: {output_path}")
        with open(output_path, "w") as f:
            json.dump(repodata, f, indent=2, sort_keys=True)

        repodata_from_packages_path = output_path.parent / "repodata_from_packages.json"
        print(f"Writing repodata_from_packages.json to: {repodata_from_packages_path}")
        with open(repodata_from_packages_path, "w") as f:
            json.dump(repodata, f, indent=2, sort_keys=True)

        package_info = extract_package_info(args.package)

        channeldata_path = args.repodata_dir / "channeldata.json"
        channeldata_output_path = output_dir / "channeldata.json"

        channeldata = update_channeldata(channeldata_path, package_info, subdir)

        print(f"Writing updated channeldata to: {channeldata_output_path}")
        with open(channeldata_output_path, "w") as f:
            json.dump(channeldata, f, indent=2, sort_keys=True)

        print(f"\nSuccess! Updated index for {args.package.name}")
        print(
            f"Package count in '{subdir}/packages': {len(repodata.get('packages', {}))}"
        )
        print(
            f"Package count in '{subdir}/packages.conda': {len(repodata.get('packages.conda', {}))}"
        )
        print(f"Total packages in channeldata: {len(channeldata.get('packages', {}))}")
        print(f"Subdirs in channeldata: {channeldata.get('subdirs', [])}")

    except Exception as e:
        print(f"Error updating repodata: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
