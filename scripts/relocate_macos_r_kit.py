#!/usr/bin/env python3
"""Relocate a profiled official R framework into a self-contained kit tree."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess

from scripts.qt6_macos_feasibility_impl import is_macho_candidate


def dependencies(path: Path) -> list[str]:
    output = subprocess.run(
        ["otool", "-L", str(path)], capture_output=True, text=True, check=True
    ).stdout
    return [line.strip().split(" (", 1)[0] for line in output.splitlines()[1:]]


def install_id(path: Path) -> str | None:
    output = subprocess.run(
        ["otool", "-D", str(path)], capture_output=True, text=True, check=False
    )
    lines = output.stdout.splitlines()[1:]
    return lines[0].strip() if lines else None


def source_relative(value: str, version: str) -> Path | None:
    prefixes = (
        "/Library/Frameworks/R.framework/Resources/",
        f"/Library/Frameworks/R.framework/Versions/{version}/Resources/",
    )
    for prefix in prefixes:
        if value.startswith(prefix):
            return Path(value[len(prefix) :])
    if value in {
        "/Library/Frameworks/R.framework/R",
        f"/Library/Frameworks/R.framework/Versions/{version}/R",
    }:
        return Path("../R")
    for prefix, destination in (
        ("/opt/R/", Path("vendor/opt-R")),
        ("/usr/local/gfortran/", Path("vendor/usr-local-gfortran")),
    ):
        if value.startswith(prefix):
            return destination / value[len(prefix) :]
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--framework", type=Path, required=True)
    parser.add_argument("--source-resources", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    framework = args.framework.resolve()
    resources = (framework / "Resources").resolve()
    for _ in range(24):
        changed = False
        binaries = [
            path
            for path in framework.rglob("*")
            if path.is_file() and not path.is_symlink() and is_macho_candidate(path)
        ]
        for binary in binaries:
            binary_install_id = install_id(binary)
            for dependency in dependencies(binary):
                if dependency.startswith("/opt/X11/"):
                    raise RuntimeError(
                        f"profiled R kit retains forbidden X11 dependency: {binary}: {dependency}"
                    )
                relative = source_relative(dependency, args.version)
                if relative is None:
                    if dependency.startswith("/") and not dependency.startswith(
                        ("/usr/lib/", "/System/Library/")
                    ):
                        raise RuntimeError(
                            f"unsupported external R dependency: {dependency}"
                        )
                    continue
                target = (resources / relative).resolve()
                if not target.exists():
                    source = Path(dependency)
                    if not source.exists():
                        raise RuntimeError(
                            f"external R dependency is missing: {dependency}"
                        )
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    changed = True
                replacement = "@loader_path/" + os.path.relpath(target, binary.parent)
                operation = "-id" if dependency == binary_install_id else "-change"
                command = ["install_name_tool", operation]
                if operation == "-change":
                    command.append(dependency)
                command.extend([replacement, str(binary)])
                subprocess.run(command, check=True)
        if not changed:
            break
    else:
        raise RuntimeError("R dependency relocation did not converge")
    for binary in [
        path
        for path in framework.rglob("*")
        if path.is_file() and not path.is_symlink() and is_macho_candidate(path)
    ]:
        for dependency in dependencies(binary):
            if dependency.startswith(
                ("/opt/", "/usr/local/", "/Library/Frameworks/R.framework/")
            ):
                raise RuntimeError(
                    f"relocated R kit retains external dependency: {dependency}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

