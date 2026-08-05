#!/usr/bin/env python3

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import warnings

from seedemu.compiler import Platform
from seedemu.core import ImageRef
from seedemu.testing import ComposeRuntimeTest

from base_image import AMD_IMAGE, ARM_IMAGE, compile_emulator


def docker_from_lines(output: Path) -> set[str]:
    dummy_dir = output / "dummies"
    if not dummy_dir.is_dir():
        return set()
    return {
        path.read_text(encoding="utf-8").strip()
        for path in dummy_dir.iterdir()
        if path.is_file()
    }


def compile_without_resource_warnings(
    output: Path,
    platform: Platform,
    image_refs,
) -> None:
    working_directory = Path.cwd()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            compile_emulator(output, platform, image_refs=image_refs)
    finally:
        os.chdir(working_directory)


def main() -> int:
    test = ComposeRuntimeTest(__file__)

    host = test.require_service(150, "host")
    if host:
        test.exec_check(
            "A14 explicit base-image container is usable",
            host,
            "test -r /etc/os-release",
        )

    amd_from = "FROM {}".format(AMD_IMAGE)
    generated = docker_from_lines(test.example_dir / "output")
    test.structural_check(
        "AMD64 compile selects the AMD64 image",
        amd_from in generated,
        "expected {} in generated Docker inputs".format(amd_from),
    )

    format_checks_passed = (
        str(ImageRef.parse("registry.example:5000/team/node:v1"))
        == "registry.example:5000/team/node:v1"
        and str(ImageRef.parse("team/node")) == "team/node:latest"
        and str(ImageRef("team/node", digest="sha256:abc"))
        == "team/node@sha256:abc"
    )
    test.structural_check(
        "Image references preserve tags, digests, and registry ports",
        format_checks_passed,
        "parsed image references have the expected string form",
    )

    invalid_references_rejected = True
    for factory in (
        lambda: ImageRef("team/node"),
        lambda: ImageRef("team/node", tag="v1", digest="sha256:abc"),
        lambda: ImageRef("team/node", tag=1),
    ):
        try:
            factory()
        except (TypeError, ValueError):
            continue
        invalid_references_rejected = False
    test.structural_check(
        "Invalid image references are rejected",
        invalid_references_rejected,
        "tag and digest validation completed",
    )

    with TemporaryDirectory() as temporary:
        output = Path(temporary) / "arm"
        try:
            compile_without_resource_warnings(
                output,
                Platform.ARM64,
                (AMD_IMAGE, ARM_IMAGE),
            )
            arm_selected = "FROM {}".format(ARM_IMAGE) in docker_from_lines(output)
            message = "ARM64 compile completed"
        except Exception as error:
            arm_selected = False
            message = str(error)
        test.structural_check(
            "ARM64 compile selects the ARM64 image",
            arm_selected,
            message,
        )

    with TemporaryDirectory() as temporary:
        try:
            compile_without_resource_warnings(
                Path(temporary) / "missing-platform",
                Platform.AMD64,
                (ARM_IMAGE,),
            )
        except ValueError as error:
            missing_platform_rejected = "none matches platform amd64" in str(error)
            message = str(error)
        except Exception as error:
            missing_platform_rejected = False
            message = str(error)
        else:
            missing_platform_rejected = False
            message = "compile unexpectedly succeeded"
        test.structural_check(
            "Missing platform variants fail clearly",
            missing_platform_rejected,
            message,
        )

    with TemporaryDirectory() as temporary:
        output = Path(temporary) / "legacy"
        try:
            compile_without_resource_warnings(output, Platform.AMD64, ())
            legacy_fallback_works = bool(docker_from_lines(output))
            message = "legacy BaseSystem compile completed"
        except Exception as error:
            legacy_fallback_works = False
            message = str(error)
        test.structural_check(
            "Nodes without ImageRef keep the BaseSystem fallback",
            legacy_fallback_works,
            message,
        )

    test.write_summary("a14-base-image-runtime-test.json")
    return test.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
