#!/usr/bin/env python3
"""Generate an HPC module sync/tag template."""

import os
import re
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader


def validate_module_tag_name(raw_tag_name):
    raw_tag_name = raw_tag_name.strip()
    if not raw_tag_name:
        return "new"
    if re.match(r"^[A-Za-z0-9._-]+$", raw_tag_name):
        return raw_tag_name
    print(f"::error::module_tag_name '{raw_tag_name}' contains invalid characters. Allowed: [A-Za-z0-9._-]")
    sys.exit(1)


def resolve_sync_tag_options(
    *,
    site,
    module_name,
    ref_name,
    sync_module,
    tag_module,
    module_tag_name,
    is_prerelease,
    dry_run,
    hpc_config,
    build_name="",
):
    sync_clusters_map = hpc_config["sync_clusters"]
    sync_clusters = sync_clusters_map.get(site, sync_clusters_map.get("aa-batch", []))
    do_sync = not dry_run and sync_module and site != "ag-batch" and bool(sync_clusters)

    tag_clusters = hpc_config.get("tag_clusters", {}).get(site, None)
    if tag_module and tag_clusters is None:
        print(f"::error::Site '{site}' not found in tag_clusters in hpc.yml. Cannot tag.")
        sys.exit(1)

    if tag_clusters and not do_sync:
        tag_clusters = [c for c in tag_clusters if c not in sync_clusters]

    release_allowed = not dry_run and not is_prerelease
    do_tag = tag_module and release_allowed and bool(tag_clusters)

    if do_tag:
        if "/" in ref_name:
            print(f"::error::ref_name '{ref_name}' contains '/' which is not allowed for module tagging")
            sys.exit(1)
        if not re.match(r"^[A-Za-z0-9._-]+$", ref_name):
            print(f"::error::ref_name '{ref_name}' contains invalid characters for module tagging. Allowed: [A-Za-z0-9._-]")
            sys.exit(1)
        if not re.match(r"^[A-Za-z0-9._+/-]+$", module_name):
            print(f"::error::module_name '{module_name}' contains invalid characters for tagging. Allowed: [A-Za-z0-9._+/-]")
            sys.exit(1)

    return {
        "build_name": build_name,
        "module_name": module_name,
        "ref_name": ref_name,
        "module_tag_name": module_tag_name,
        "sync_clusters": sync_clusters,
        "sync_module": do_sync,
        "do_tag": do_tag,
        "tag_clusters": tag_clusters or [],
    }


def make_jinja_env(action_dir):
    jinja_env = Environment(
        loader=FileSystemLoader([action_dir / "templates", action_dir.parent / "hpc" / "templates"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    jinja_env.filters["strip_d_prefix"] = lambda s: s[2:] if s.startswith("-D") else s
    return jinja_env


def main():
    action_dir = Path(os.environ["GITHUB_ACTION_PATH"])
    with open(action_dir.parent / "defaults.yml") as f:
        defaults = yaml.safe_load(f)["hpc"]

    with open(action_dir.parent / "hpc" / "config" / "hpc.yml") as f:
        hpc_config = yaml.safe_load(f)

    dry_run = os.environ.get("INPUT_DRY_RUN", "false") == "true"
    is_prerelease = os.environ.get("INPUT_IS_PRERELEASE", "false") == "true"
    sync_module = os.environ.get("INPUT_SYNC_MODULE", "true") == "true"
    tag_module = os.environ.get("INPUT_TAG_MODULE", "true") == "true"
    site = os.environ.get("INPUT_SITE", "").strip() or defaults["site"]
    queue = os.environ.get("INPUT_QUEUE", "").strip() or defaults["queue"]
    ref_name = os.environ["INPUT_REF_NAME"]
    build_name = os.environ.get("INPUT_NAME", "").strip()
    repository = os.environ["GITHUB_REPOSITORY"]
    module_name = os.environ.get("INPUT_MODULE_NAME", "").strip() or repository.split("/")[-1]
    module_tag_name = validate_module_tag_name(os.environ.get("INPUT_MODULE_TAG_NAME", "new"))

    ci_options = resolve_sync_tag_options(
        site=site,
        module_name=module_name,
        ref_name=ref_name,
        sync_module=sync_module,
        tag_module=tag_module,
        module_tag_name=module_tag_name,
        is_prerelease=is_prerelease,
        dry_run=dry_run,
        hpc_config=hpc_config,
        build_name=build_name,
    )
    do_run = ci_options["sync_module"] or ci_options["do_tag"]

    rendered = ""
    sbatch = ""
    if do_run:
        jinja_env = make_jinja_env(action_dir)
        rendered = jinja_env.get_template("sync-tag-job.jinja").render(ci_options=ci_options)
        sbatch_template = jinja_env.from_string(
            "{% from 'sbatch.jinja' import sbatch_options with context %}{{ sbatch_options() }}"
        )
        sbatch = sbatch_template.render(site=site, queue=queue, ntasks=1, parallel=2, gpus="").strip()

    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write(f"do_run={'true' if do_run else 'false'}\n")
        f.write("template<<EOF\n")
        f.write(rendered)
        f.write("\nEOF\n")
        f.write("sbatch_options<<SBATCH_EOF\n")
        f.write(sbatch)
        f.write("\nSBATCH_EOF\n")

    print(f"Site: {site}")
    print(f"Module: {module_name} @ {ref_name}")
    print(f"Do sync: {ci_options['sync_module']}")
    print(f"Do tag: {ci_options['do_tag']}")
    if do_run:
        print("Generated template:")
        print(rendered)
        print("\nSBATCH options:")
        print(sbatch)
    else:
        print("Nothing to do: sync and tag are disabled, dry-run, or unsupported on this site")


if __name__ == "__main__":
    main()
