"""Tests for the cd-actions/system-package helper scripts."""

from __future__ import annotations

import pytest

from conftest import import_script

cpack_overrides = import_script(
    "system-package", "generate_cpack_overrides", "sp_generate_cpack_overrides"
)
check_version = import_script("system-package", "check_version", "sp_check_version")
docker_image = import_script(
    "system-package", "determine_docker_image", "sp_determine_docker_image"
)


class TestCmakeEscape:
    def test_escapes_special_characters(self):
        assert cpack_overrides.cmake_escape('a\\b"c;d') == 'a\\\\b\\"c\\;d'


class TestBuildOverrideLines:
    def test_deb_full(self):
        lines = cpack_overrides.build_override_lines(
            {
                "CPACK_GENERATOR": "DEB",
                "INPUT_PACKAGE_DEPS": "libfoo, libbar",
                "INPUT_DESCRIPTION": "A package",
                "INPUT_LICENSE": "Apache-2.0",
                "INPUT_MAINTAINER": "software@ecmwf.int",
                "INPUT_VENDOR": "ECMWF",
                "INPUT_HOMEPAGE_URL": "https://example.org",
                "INPUT_INSTALL_PREFIX": "/opt/ecmwf",
                "INPUT_DEB_SECTION": "science",
                "INPUT_DEB_PRIORITY": "optional",
            }
        )
        assert lines == [
            'set(CPACK_DEBIAN_PACKAGE_DEPENDS "libfoo, libbar" CACHE STRING "" FORCE)',
            'set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "A package" CACHE STRING "" FORCE)',
            'set(CPACK_RPM_PACKAGE_LICENSE "Apache-2.0" CACHE STRING "" FORCE)',
            'set(CPACK_DEBIAN_PACKAGE_MAINTAINER "software@ecmwf.int" CACHE STRING "" FORCE)',
            'set(CPACK_DEBIAN_PACKAGE_SECTION "science" CACHE STRING "" FORCE)',
            'set(CPACK_DEBIAN_PACKAGE_PRIORITY "optional" CACHE STRING "" FORCE)',
            'set(CPACK_DEBIAN_PACKAGE_SHLIBDEPS ON CACHE BOOL "" FORCE)',
            'set(CPACK_PACKAGE_VENDOR "ECMWF" CACHE STRING "" FORCE)',
            'set(CPACK_RPM_PACKAGE_VENDOR "ECMWF" CACHE STRING "" FORCE)',
            'set(CPACK_PACKAGE_HOMEPAGE_URL "https://example.org" CACHE STRING "" FORCE)',
            'set(CPACK_RPM_PACKAGE_URL "https://example.org" CACHE STRING "" FORCE)',
            'set(CPACK_PACKAGING_INSTALL_PREFIX "/opt/ecmwf" CACHE STRING "" FORCE)',
        ]

    def test_rpm_specific_lines(self):
        lines = cpack_overrides.build_override_lines(
            {
                "CPACK_GENERATOR": "RPM",
                "INPUT_PACKAGE_DEPS": "foo",
                "INPUT_RPM_GROUP": "Applications",
            }
        )
        assert (
            'set(CPACK_RPM_PACKAGE_REQUIRES "foo" CACHE STRING "" FORCE)' in lines
        )
        assert (
            'set(CPACK_RPM_SPEC_MORE_DEFINE "%global __brp_check_rpaths %{nil}" CACHE STRING "" FORCE)'
            in lines
        )
        assert (
            'set(CPACK_RPM_PACKAGE_GROUP "Applications" CACHE STRING "" FORCE)' in lines
        )
        assert not any("DEBIAN" in line for line in lines)

    def test_description_falls_back_to_repo_description(self):
        lines = cpack_overrides.build_override_lines(
            {"CPACK_GENERATOR": "RPM", "REPO_DESCRIPTION": "From GitHub"}
        )
        assert (
            'set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "From GitHub" CACHE STRING "" FORCE)'
            in lines
        )

    def test_noassertion_license_dropped(self):
        lines = cpack_overrides.build_override_lines(
            {"CPACK_GENERATOR": "RPM", "REPO_LICENSE_SPDX": "NOASSERTION"}
        )
        assert not any("LICENSE" in line for line in lines)

    def test_homepage_falls_back_to_repo_url(self):
        lines = cpack_overrides.build_override_lines(
            {"CPACK_GENERATOR": "RPM", "REPO_URL": "https://github.com/ecmwf/example"}
        )
        assert (
            'set(CPACK_PACKAGE_HOMEPAGE_URL "https://github.com/ecmwf/example" CACHE STRING "" FORCE)'
            in lines
        )

    def test_values_are_cmake_escaped(self):
        lines = cpack_overrides.build_override_lines(
            {"CPACK_GENERATOR": "DEB", "INPUT_DESCRIPTION": 'say "hi"; ok'}
        )
        assert (
            'set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "say \\"hi\\"\\; ok" CACHE STRING "" FORCE)'
            in lines
        )

    def test_main_writes_file_and_output(self, monkeypatch, tmp_path, github_output):
        monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
        monkeypatch.setenv("CPACK_GENERATOR", "DEB")
        monkeypatch.setenv("INPUT_PACKAGE_DEPS", "libfoo")
        monkeypatch.setenv("INPUT_MAINTAINER", "software@ecmwf.int")
        for var in (
            "INPUT_DESCRIPTION",
            "REPO_DESCRIPTION",
            "INPUT_LICENSE",
            "REPO_LICENSE_SPDX",
            "INPUT_VENDOR",
            "INPUT_HOMEPAGE_URL",
            "REPO_URL",
            "INPUT_INSTALL_PREFIX",
            "INPUT_DEB_SECTION",
            "INPUT_DEB_PRIORITY",
            "INPUT_RPM_GROUP",
        ):
            monkeypatch.delenv(var, raising=False)

        cpack_overrides.main()

        overrides_file = tmp_path / "cpack-overrides.cmake"
        assert github_output.read()["overrides_file"] == str(overrides_file)
        assert overrides_file.read_text() == (
            'set(CPACK_DEBIAN_PACKAGE_DEPENDS "libfoo" CACHE STRING "" FORCE)\n'
            'set(CPACK_DEBIAN_PACKAGE_MAINTAINER "software@ecmwf.int" CACHE STRING "" FORCE)\n'
            'set(CPACK_DEBIAN_PACKAGE_SHLIBDEPS ON CACHE BOOL "" FORCE)\n'
        )


class TestCheckVersion:
    def _run(self, monkeypatch, tmp_path, tag: str):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("INPUT_REF_NAME", tag)
        check_version.main()

    def test_version_file_match(self, monkeypatch, tmp_path):
        (tmp_path / "VERSION").write_text("1.2.3\n")
        self._run(monkeypatch, tmp_path, "1.2.3")

    def test_version_file_mismatch(self, monkeypatch, tmp_path):
        (tmp_path / "VERSION").write_text("1.2.3\n")
        with pytest.raises(SystemExit):
            self._run(monkeypatch, tmp_path, "1.2.4")

    def test_cmakelists_fallback(self, monkeypatch, tmp_path):
        (tmp_path / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.16)\nproject(example VERSION 2.0.1 LANGUAGES C)\n"
        )
        self._run(monkeypatch, tmp_path, "2.0.1")

    def test_no_version_anywhere(self, monkeypatch, tmp_path):
        with pytest.raises(SystemExit):
            self._run(monkeypatch, tmp_path, "1.0.0")


class TestDockerImageForOs:
    def test_rocky_maps_to_rockylinux(self):
        assert (
            docker_image.docker_image_for_os("rocky-9.7", "")
            == "eccr.ecmwf.int/docker-hub-proxy/rockylinux/rockylinux:9.7"
        )

    def test_debian_uses_library_prefix(self):
        assert (
            docker_image.docker_image_for_os("debian-12", "")
            == "eccr.ecmwf.int/docker-hub-proxy/library/debian:12"
        )

    def test_versionless_os(self):
        assert (
            docker_image.docker_image_for_os("fedora", "")
            == "eccr.ecmwf.int/docker-hub-proxy/library/fedora"
        )

    def test_explicit_image_wins(self):
        assert (
            docker_image.docker_image_for_os("rocky-9.7", "registry.local/img:1")
            == "registry.local/img:1"
        )

    def test_main_writes_output(self, monkeypatch, github_output):
        monkeypatch.setenv("INPUT_OS", "ubuntu-22.04")
        monkeypatch.delenv("INPUT_INSTALL_TEST_OS_IMAGE", raising=False)
        docker_image.main()
        assert (
            github_output.read()["docker_image"]
            == "eccr.ecmwf.int/docker-hub-proxy/library/ubuntu:22.04"
        )
