#!/usr/bin/env python3
"""Generate a Homebrew formula (.rb) file from structured inputs.

This script is used by the brew CD action to create new formulas
when they don't yet exist in the tap repository.
"""

import argparse
import json
import re
import sys
import textwrap


def formula_class_name(name: str) -> str:
    """Convert a formula name to a Ruby CamelCase class name.

    Examples:
        eckit -> Eckit
        my-formula -> MyFormula
        odc -> Odc
        atlas_utils -> AtlasUtils
    """
    return re.sub(r"(?:^|[-_])(.)", lambda m: m.group(1).upper(), name)


def ruby_escape(s: str) -> str:
    """Escape a string for use inside Ruby double quotes."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def indent(text: str, spaces: int) -> str:
    """Indent each line of text by the given number of spaces."""
    prefix = " " * spaces
    return "\n".join(prefix + line if line.strip() else "" for line in text.splitlines())


def generate_dependencies(deps: dict, uses_from_macos: list) -> list[str]:
    """Convert structured dependency dict to Ruby depends_on lines.

    Format rules:
        null/empty value -> depends_on "name"
        string value     -> depends_on "name" => :value
        list value       -> depends_on "name" => [:tag1, :tag2]
    """
    lines = []

    for name, tags in deps.items():
        if tags is None or tags == "":
            lines.append(f'depends_on "{name}"')
        elif isinstance(tags, str):
            lines.append(f'depends_on "{name}" => :{tags}')
        elif isinstance(tags, list):
            if len(tags) == 1:
                lines.append(f'depends_on "{name}" => :{tags[0]}')
            else:
                tag_list = ", ".join(f":{t}" for t in tags)
                lines.append(f'depends_on "{name}" => [{tag_list}]')

    for name in uses_from_macos:
        lines.append(f'uses_from_macos "{name}"')

    return lines


def generate_formula(args: argparse.Namespace) -> str:
    """Generate the complete formula Ruby source code."""
    class_name = formula_class_name(args.formula_name)

    # Decode JSON-encoded inputs
    dependencies = json.loads(args.dependencies_json) if args.dependencies_json else {}
    uses_from_macos = json.loads(args.uses_from_macos_json) if args.uses_from_macos_json else []
    install_block = json.loads(args.install_json) if args.install_json else ""
    test_block = json.loads(args.test_json) if args.test_json else ""

    if not install_block:
        print("Error: install block is required for new formulas", file=sys.stderr)
        sys.exit(1)
    if not test_block:
        print("Error: test block is required for new formulas", file=sys.stderr)
        sys.exit(1)

    # Optional blocks
    head_block = json.loads(args.head_json) if args.head_json else ""
    post_install_block = json.loads(args.post_install_json) if args.post_install_json else ""
    caveats_text = args.caveats or ""
    conflicts = json.loads(args.conflicts_json) if args.conflicts_json else []

    # Build formula sections
    sections = []

    # Header metadata
    sections.append(f'class {class_name} < Formula')
    sections.append(f'  desc "{ruby_escape(args.desc)}"')
    sections.append(f'  homepage "{ruby_escape(args.homepage)}"')
    sections.append(f'  url "{ruby_escape(args.url)}"')
    sections.append(f'  sha256 "{args.sha256}"')
    sections.append(f'  version "{ruby_escape(args.version)}"')
    if args.license:
        sections.append(f'  license "{ruby_escape(args.license)}"')

    # Head block (development version)
    if head_block:
        sections.append("")
        sections.append(indent(head_block.rstrip(), 2))

    # Livecheck
    if args.livecheck == "auto":
        sections.append("")
        sections.append("  livecheck do")
        sections.append(f'    url "{ruby_escape(args.homepage)}/tags"')
        sections.append(r'    regex(/^v?(\d(?:\.\d+)+)$/i)')
        sections.append("  end")
    elif args.livecheck and args.livecheck != "false":
        livecheck_block = json.loads(args.livecheck)
        sections.append("")
        sections.append("  livecheck do")
        sections.append(indent(livecheck_block.rstrip(), 4))
        sections.append("  end")

    # Dependencies
    dep_lines = generate_dependencies(dependencies, uses_from_macos)
    if dep_lines:
        sections.append("")
        for line in dep_lines:
            sections.append(f"  {line}")

    # Conflicts
    if conflicts:
        sections.append("")
        for conflict in conflicts:
            sections.append(f'  conflicts_with "{ruby_escape(conflict)}"')

    # Install method
    sections.append("")
    sections.append("  def install")
    sections.append(indent(install_block.rstrip(), 4))
    sections.append("  end")

    # Post-install method
    if post_install_block:
        sections.append("")
        sections.append("  def post_install")
        sections.append(indent(post_install_block.rstrip(), 4))
        sections.append("  end")

    # Caveats method
    if caveats_text:
        sections.append("")
        sections.append("  def caveats")
        sections.append("    <<~EOS")
        sections.append(indent(caveats_text.rstrip(), 6))
        sections.append("    EOS")
        sections.append("  end")

    # Test block
    sections.append("")
    sections.append("  test do")
    sections.append(indent(test_block.rstrip(), 4))
    sections.append("  end")

    # Close class
    sections.append("end")

    return "\n".join(sections) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Generate a Homebrew formula file")

    # Required args
    parser.add_argument("--formula-name", required=True, help="Formula name (e.g., eckit)")
    parser.add_argument("--url", required=True, help="Source tarball URL")
    parser.add_argument("--sha256", required=True, help="SHA256 hash of the tarball")
    parser.add_argument("--version", required=True, help="Version string")

    # Auto-injected metadata
    parser.add_argument("--desc", default="", help="Formula description")
    parser.add_argument("--homepage", default="", help="Homepage URL")
    parser.add_argument("--license", default="", help="SPDX license identifier")

    # Dependencies
    parser.add_argument("--dependencies-json", default="{}", help="JSON-encoded dependency dict")
    parser.add_argument("--uses-from-macos-json", default="[]", help="JSON-encoded uses_from_macos list")

    # Code blocks (JSON-encoded strings)
    parser.add_argument("--install-json", default="", help="JSON-encoded install block (Ruby code)")
    parser.add_argument("--test-json", default="", help="JSON-encoded test block (Ruby code)")

    # Optional
    parser.add_argument("--livecheck", default="auto", help='"auto", "false", or JSON-encoded custom block')
    parser.add_argument("--head-json", default="", help="JSON-encoded head block")
    parser.add_argument("--post-install-json", default="", help="JSON-encoded post_install block")
    parser.add_argument("--caveats", default="", help="Caveats text")
    parser.add_argument("--conflicts-json", default="[]", help="JSON-encoded conflicts list")
    parser.add_argument("--output", required=True, help="Output file path")

    args = parser.parse_args()

    formula_source = generate_formula(args)

    with open(args.output, "w") as f:
        f.write(formula_source)

    print(f"Generated formula: {args.output}")
    print(f"Class: {formula_class_name(args.formula_name)}")
    print(f"Version: {args.version}")


if __name__ == "__main__":
    main()
