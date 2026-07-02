#!/usr/bin/env python3
"""Map an OS id to the Docker image used for the package install test."""

from __future__ import annotations

import os

# Map OS names that differ from their Docker Hub image name.
IMAGE_NAME_MAP = {
    'rocky': 'rockylinux/rockylinux',
}


def docker_image_for_os(os_id: str, explicit_image: str) -> str:
    """Return the install-test image: the explicit one, or a docker-hub-proxy ref."""
    if explicit_image:
        return explicit_image

    # Parse "<name>-<version>" from the os input.
    name, _, version = os_id.partition('-')
    image_name = IMAGE_NAME_MAP.get(name, name)
    is_library = '/' not in image_name
    docker_ref = f"{image_name}:{version}" if version else image_name

    return f"eccr.ecmwf.int/docker-hub-proxy/{'library/' if is_library else ''}{docker_ref}"


def main():
    os_id = os.environ.get('INPUT_OS', '')
    docker_image = docker_image_for_os(
        os_id, os.environ.get('INPUT_INSTALL_TEST_OS_IMAGE', '')
    )

    if docker_image:
        print(f"Mapped OS '{os_id}' to Docker image '{docker_image}'")
    else:
        print(f"::warning::No Docker image mapping for OS '{os_id}', skipping install test")

    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write(f"docker_image={docker_image}\n")


if __name__ == "__main__":
    main()
