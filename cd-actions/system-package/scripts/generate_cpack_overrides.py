#!/usr/bin/env python3
"""Generate a CPack overrides file from package metadata inputs."""

from __future__ import annotations

import os
from typing import Mapping


def cmake_escape(s):
    """Escape backslashes, double-quotes, and semicolons for CMake strings."""
    return s.replace('\\', '\\\\').replace('"', '\\"').replace(';', '\\;')


def build_override_lines(env: Mapping[str, str]) -> list[str]:
    """Build the CPack cache override lines for the requested generator."""
    cpack_generator = env.get('CPACK_GENERATOR', '')
    package_deps = env.get('INPUT_PACKAGE_DEPS', '').strip()
    description = env.get('INPUT_DESCRIPTION', '').strip()

    if not description:
        description = env.get('REPO_DESCRIPTION', '').strip()

    license = env.get('INPUT_LICENSE', '').strip()
    if not license:
        license = env.get('REPO_LICENSE_SPDX', '').strip()
    if license == 'NOASSERTION':
        license = ''

    maintainer = env.get('INPUT_MAINTAINER', '').strip()
    vendor = env.get('INPUT_VENDOR', '').strip()

    homepage_url = env.get('INPUT_HOMEPAGE_URL', '').strip()
    if not homepage_url:
        homepage_url = env.get('REPO_URL', '')

    install_prefix = env.get('INPUT_INSTALL_PREFIX', '').strip()
    deb_section = env.get('INPUT_DEB_SECTION', '').strip()
    deb_priority = env.get('INPUT_DEB_PRIORITY', '').strip()
    rpm_group = env.get('INPUT_RPM_GROUP', '').strip()

    if cpack_generator == 'DEB':
        deps_var = 'CPACK_DEBIAN_PACKAGE_DEPENDS'
    else:
        deps_var = 'CPACK_RPM_PACKAGE_REQUIRES'

    lines = []

    if package_deps:
        lines.append(f'set({deps_var} "{cmake_escape(package_deps)}" CACHE STRING "" FORCE)')
        print(f"Package deps ({deps_var}): {package_deps}")

    if description:
        lines.append(f'set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "{cmake_escape(description)}" CACHE STRING "" FORCE)')
        print(f"Description: {description}")
    else:
        print("Description: (none)")

    if license:
        lines.append(f'set(CPACK_RPM_PACKAGE_LICENSE "{cmake_escape(license)}" CACHE STRING "" FORCE)')
        print(f"License: {license}")
    else:
        print("License: (none)")

    # DEB-specific options
    if cpack_generator == 'DEB':
        lines.append(f'set(CPACK_DEBIAN_PACKAGE_MAINTAINER "{cmake_escape(maintainer)}" CACHE STRING "" FORCE)')
        print(f"Maintainer: {maintainer}")
        if deb_section:
            lines.append(f'set(CPACK_DEBIAN_PACKAGE_SECTION "{cmake_escape(deb_section)}" CACHE STRING "" FORCE)')
            print(f"DEB Section: {deb_section}")
        if deb_priority:
            lines.append(f'set(CPACK_DEBIAN_PACKAGE_PRIORITY "{cmake_escape(deb_priority)}" CACHE STRING "" FORCE)')
            print(f"DEB Priority: {deb_priority}")
        lines.append('set(CPACK_DEBIAN_PACKAGE_SHLIBDEPS ON CACHE BOOL "" FORCE)')

    # RPM-specific options
    if cpack_generator == 'RPM':
        lines.append('set(CPACK_RPM_SPEC_MORE_DEFINE "%global __brp_check_rpaths %{nil}" CACHE STRING "" FORCE)')
        if rpm_group:
            lines.append(f'set(CPACK_RPM_PACKAGE_GROUP "{cmake_escape(rpm_group)}" CACHE STRING "" FORCE)')
            print(f"RPM Group: {rpm_group}")

    # Common metadata
    if vendor:
        lines.append(f'set(CPACK_PACKAGE_VENDOR "{cmake_escape(vendor)}" CACHE STRING "" FORCE)')
        lines.append(f'set(CPACK_RPM_PACKAGE_VENDOR "{cmake_escape(vendor)}" CACHE STRING "" FORCE)')
        print(f"Vendor: {vendor}")

    if homepage_url:
        lines.append(f'set(CPACK_PACKAGE_HOMEPAGE_URL "{cmake_escape(homepage_url)}" CACHE STRING "" FORCE)')
        lines.append(f'set(CPACK_RPM_PACKAGE_URL "{cmake_escape(homepage_url)}" CACHE STRING "" FORCE)')
        print(f"Homepage URL: {homepage_url}")

    if install_prefix:
        lines.append(f'set(CPACK_PACKAGING_INSTALL_PREFIX "{cmake_escape(install_prefix)}" CACHE STRING "" FORCE)')
        print(f"Install Prefix: {install_prefix}")

    return lines


def main():
    lines = build_override_lines(os.environ)

    overrides_file = os.path.join(os.environ['RUNNER_TEMP'], 'cpack-overrides.cmake')
    with open(overrides_file, 'w') as f:
        for line in lines:
            f.write(line + '\n')

    print(f"Wrote {len(lines)} overrides to {overrides_file}")

    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write(f"overrides_file={overrides_file}\n")


if __name__ == "__main__":
    main()
