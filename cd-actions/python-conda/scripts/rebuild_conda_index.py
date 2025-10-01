#!/usr/bin/env python3

import argparse
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urljoin

import requests

STANDARD_ARCHS = ["linux-64", "osx-64", "osx-arm64", "win-64", "noarch"]


def parse_auth(auth: str) -> tuple[str, str] | None:
    """Parse username:password auth string."""
    if not auth:
        return None
    if ":" in auth:
        username, password = auth.split(":", 1)
        return (username, password)
    return None


def fetch_cache_db(nexus_url: str, auth: str, arch: str, dest_dir: Path) -> bool:
    """Fetch cache.db for a specific architecture from Nexus."""
    cache_url = urljoin(nexus_url, f"{arch}/.cache/cache.db")
    cache_path = dest_dir / arch / ".cache" / "cache.db"
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Fetching {cache_url}...")
    try:
        response = requests.get(cache_url, auth=parse_auth(auth), timeout=30)
        response.raise_for_status()
        cache_path.write_bytes(response.content)
        print(f"  ✓ Downloaded cache.db for {arch}")
        return True
    except requests.RequestException:
        print(f"  ℹ No existing cache.db for {arch} (will create new)")
        return False


def discover_remote_architectures(
    nexus_url: str, auth_tuple: tuple[str, str] | None
) -> list[str]:
    """Discover all available architectures in the remote Nexus repository."""
    available_archs = []

    print("Discovering available architectures in remote repository...")
    for arch in STANDARD_ARCHS:
        repodata_url = urljoin(nexus_url, f"{arch}/repodata.json")
        try:
            response = requests.head(repodata_url, auth=auth_tuple, timeout=10)
            if response.status_code == 200:
                available_archs.append(arch)
                print(f"  ✓ Found {arch}")
        except requests.RequestException:
            pass

    if not available_archs:
        print("  ℹ No existing architectures found in remote (new repository)")

    return available_archs


def prepare_directory_structure(
    packages: list[Path],
    nexus_url: str,
    auth_tuple: tuple[str, str] | None,
    work_dir: Path,
) -> list[str]:
    """Prepare directory structure with cache.db files and packages."""
    package_architectures = set()
    for package in packages:
        arch = package.parent.name
        if arch in STANDARD_ARCHS:
            package_architectures.add(arch)

    if not package_architectures:
        print(
            "Error: Could not detect architectures from package paths", file=sys.stderr
        )
        print(f"Expected packages to be in one of: {STANDARD_ARCHS}", file=sys.stderr)
        sys.exit(1)

    print(f"Detected architectures in packages: {sorted(package_architectures)}")

    remote_architectures = discover_remote_architectures(nexus_url, auth_tuple)

    all_architectures = set(package_architectures) | set(remote_architectures)
    print(f"Total architectures to process: {sorted(all_architectures)}")

    print("\nFetching cache.db files...")
    auth_str = f"{auth_tuple[0]}:{auth_tuple[1]}" if auth_tuple else ""
    for arch in sorted(all_architectures):
        fetch_cache_db(nexus_url, auth_str, arch, work_dir)

    print("\nCopying packages...")
    for package in packages:
        arch = package.parent.name
        dest = work_dir / arch / package.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"  Copying {package.name} to {arch}/")
        shutil.copy2(package, dest)

    return sorted(all_architectures)


def run_conda_index(work_dir: Path, update_cache: bool = True) -> None:
    """Run conda_index with specified options."""
    cmd = [sys.executable, "-m", "conda_index", str(work_dir)]
    if update_cache:
        cmd.append("--update-cache")
    else:
        cmd.append("--no-update-cache")
    cmd.extend(["--channeldata", "--no-rss"])

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("Error running conda_index:", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    print(result.stdout)


def remove_index_files(work_dir: Path) -> None:
    """Remove all generated index files (HTML and JSON)."""
    print("Removing generated index files...")

    for pattern in ["*.json", "*.html"]:
        for file in work_dir.glob(pattern):
            print(f"  Removing {file.relative_to(work_dir)}")
            file.unlink()

    for arch_dir in work_dir.iterdir():
        if arch_dir.is_dir() and arch_dir.name != ".cache":
            for pattern in ["*.json", "*.html"]:
                for file in arch_dir.glob(pattern):
                    print(f"  Removing {file.relative_to(work_dir)}")
                    file.unlink()


def update_cache_db_stages(work_dir: Path, architectures: list[str]) -> None:
    """Update SQLite cache.db to change stage from 'indexed' to 'fs'."""
    print("Updating cache.db stages...")

    for arch in architectures:
        db_path = work_dir / arch / ".cache" / "cache.db"
        if not db_path.exists():
            print(f"  Warning: {db_path} does not exist, skipping")
            continue

        print(f"  Updating {arch}/.cache/cache.db")
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO stat (path, stage, mtime, size, sha256, md5, last_modified, etag)
                SELECT path, 'fs', mtime, size, sha256, md5, last_modified, etag
                FROM stat
                WHERE stage = 'indexed'
            """)
            rows_affected = cursor.rowcount
            conn.commit()
            print(f"    Updated {rows_affected} entries")


def upload_to_nexus(
    work_dir: Path,
    nexus_url: str,
    auth_tuple: tuple[str, str] | None,
    architectures: list[str],
    dry_run: bool = False,
) -> None:
    """Upload packages and index files to Nexus."""
    print("\nUploading to Nexus...")

    def upload_file(local_path: Path, remote_url: str) -> bool:
        """Upload a single file to Nexus."""
        if dry_run:
            print(
                f"  [DRY RUN] Would upload {local_path.relative_to(work_dir)} to {remote_url}"
            )
            return True

        try:
            with open(local_path, "rb") as f:
                response = requests.put(
                    remote_url, data=f, auth=auth_tuple, timeout=300
                )
                response.raise_for_status()
            print(f"  ✓ Uploaded {local_path.relative_to(work_dir)}")
            return True
        except requests.RequestException as e:
            print(f"  Error uploading {local_path.name}: {e}", file=sys.stderr)
            return False

    print("\nUploading packages...")
    for arch in architectures:
        arch_dir = work_dir / arch
        if not arch_dir.exists():
            continue

        for package in list(arch_dir.glob("*.tar.bz2")) + list(
            arch_dir.glob("*.conda")
        ):
            remote_url = urljoin(nexus_url, f"{arch}/{package.name}")
            if not upload_file(package, remote_url):
                sys.exit(1)

    print("\nUploading index files...")

    for arch in architectures:
        arch_dir = work_dir / arch
        if not arch_dir.exists():
            continue

        for json_file in arch_dir.glob("*.json"):
            remote_url = urljoin(nexus_url, f"{arch}/{json_file.name}")
            if not upload_file(json_file, remote_url):
                sys.exit(1)

        index_html = arch_dir / "index.html"
        if index_html.exists():
            remote_url = urljoin(nexus_url, f"{arch}/index.html")
            if not upload_file(index_html, remote_url):
                sys.exit(1)

        cache_db = arch_dir / ".cache" / "cache.db"
        if cache_db.exists():
            remote_url = urljoin(nexus_url, f"{arch}/.cache/cache.db")
            if not upload_file(cache_db, remote_url):
                sys.exit(1)

    for json_file in work_dir.glob("*.json"):
        remote_url = urljoin(nexus_url, json_file.name)
        if not upload_file(json_file, remote_url):
            sys.exit(1)

    index_html = work_dir / "index.html"
    if index_html.exists():
        remote_url = urljoin(nexus_url, "index.html")
        if not upload_file(index_html, remote_url):
            sys.exit(1)

    print("\n✓ All files uploaded successfully!")


def find_packages(search_dir: Path) -> list[Path]:
    """Find all conda packages in the specified directory."""
    packages = []
    packages.extend(search_dir.rglob("*.tar.bz2"))
    packages.extend(search_dir.rglob("*.conda"))
    return sorted(packages)


def main():
    parser = argparse.ArgumentParser(
        description="Rebuild conda repository index using conda_index"
    )
    parser.add_argument(
        "--package-dir",
        required=True,
        type=Path,
        help="Directory to search for conda packages",
    )
    parser.add_argument(
        "--nexus-url",
        required=True,
        help="Base URL of the Nexus conda repository",
    )
    parser.add_argument(
        "--nexus-token",
        help="Nexus authentication token (format: username:password)",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        help="Working directory (default: create temp directory)",
    )
    parser.add_argument(
        "--keep-work-dir",
        action="store_true",
        help="Keep working directory after completion",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not upload files to Nexus",
    )

    args = parser.parse_args()

    print(f"Searching for packages in: {args.package_dir}")
    if not args.package_dir.exists():
        print(f"Error: Directory not found: {args.package_dir}", file=sys.stderr)
        sys.exit(1)

    packages = find_packages(args.package_dir)
    if not packages:
        print(f"Error: No conda packages found in {args.package_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(packages)} package(s):")
    for pkg in packages:
        print(f"  - {pkg.relative_to(args.package_dir)}")

    nexus_url = args.nexus_url.rstrip("/") + "/"

    if args.work_dir:
        work_dir = args.work_dir
        work_dir.mkdir(parents=True, exist_ok=True)
        cleanup = False
    else:
        work_dir = Path(tempfile.mkdtemp(prefix="conda-index-"))
        cleanup = not args.keep_work_dir

    auth_tuple = parse_auth(args.nexus_token or "")

    try:
        print(f"Working directory: {work_dir}\n")

        print("=== Step 1: Preparing directory structure ===")
        architectures = prepare_directory_structure(
            packages, nexus_url, auth_tuple, work_dir
        )

        print("\n=== Step 2: First conda_index run (update cache) ===")
        run_conda_index(work_dir, update_cache=True)

        print("\n=== Step 3: Removing generated index files ===")
        remove_index_files(work_dir)

        print("\n=== Step 4: Second conda_index run (update cache) ===")
        run_conda_index(work_dir, update_cache=True)

        print("\n=== Step 5: Updating cache.db stages ===")
        update_cache_db_stages(work_dir, architectures)

        print("\n=== Step 6: Final conda_index run (no cache update) ===")
        run_conda_index(work_dir, update_cache=False)

        print("\n=== Step 7: Uploading to Nexus ===")
        upload_to_nexus(work_dir, nexus_url, auth_tuple, architectures, args.dry_run)

        print(f"\n{'=' * 50}")
        print("SUCCESS: Conda index rebuilt and uploaded!")
        print(f"{'=' * 50}")

    finally:
        if cleanup:
            print(f"\nCleaning up working directory: {work_dir}")
            shutil.rmtree(work_dir)
        elif not args.work_dir:
            print(f"\nWorking directory preserved: {work_dir}")


if __name__ == "__main__":
    main()
