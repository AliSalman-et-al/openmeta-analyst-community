#!/usr/bin/env python3
"""Resolve an official architecture-native R.framework from an expanded installer."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import xml.etree.ElementTree as ET


IDENTIFIER = "org.R-project.arm64.R.fw.pkg"
INSTALL_LOCATION = "/Library/Frameworks"
LOCKED_VERSION = "4.6.1"
MAX_PACKAGE_INFO_FILES = 128
MAX_PACKAGE_INFO_BYTES = 64 * 1024
MAX_XML_DEPTH = 8
MAX_FIELD_LENGTH = 256
MAX_DIAGNOSTICS = 12
MAX_DIAGNOSTIC_CHARS = 2048


def resolve_framework(
    expanded_root: Path,
    expected_version: str | None = None,
    expected_identifier: str = IDENTIFIER,
) -> Path:
    if expanded_root.is_symlink():
        raise RuntimeError("expanded installer root must not be a symlink")
    root = expanded_root.resolve(strict=True)
    candidates: list[Path] = []
    diagnostics: list[str] = []
    omitted = 0
    package_infos: list[Path] = []
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        # Package payloads can contain the normal R.framework symlink topology.
        # They are not component metadata, so never descend into them.
        for directory in list(directories):
            path = current_path / directory
            if directory in {"Payload", "Scripts"}:
                directories.remove(directory)
            elif path.is_symlink():
                directories.remove(directory)
                if directory.endswith(".pkg"):
                    raise RuntimeError(
                        "expanded installer contains a symlinked component directory"
                    )
        package_infos.extend(
            Path(current) / name for name in filenames if name == "PackageInfo"
        )
        if len(package_infos) > MAX_PACKAGE_INFO_FILES:
            raise RuntimeError("expanded installer exceeds PackageInfo file bound")
    for package_info in sorted(package_infos):
        if package_info.is_symlink():
            raise RuntimeError("expanded installer contains a symlinked PackageInfo")
        if package_info.stat().st_size > MAX_PACKAGE_INFO_BYTES:
            raise RuntimeError("PackageInfo exceeds byte bound")
        try:
            depth = 0
            root_tag = None
            attributes: dict[str, str] | None = None
            for event, element in ET.iterparse(package_info, events=("start", "end")):
                if event == "start":
                    depth += 1
                    if depth > MAX_XML_DEPTH:
                        raise RuntimeError("PackageInfo exceeds XML depth bound")
                    if root_tag is None:
                        root_tag, attributes = element.tag, dict(element.attrib)
                else:
                    depth -= 1
        except (ET.ParseError, OSError) as exc:
            raise RuntimeError(f"unreadable PackageInfo: {package_info}") from exc
        if root_tag != "pkg-info" or attributes is None:
            raise RuntimeError("PackageInfo root must be pkg-info")
        identifier = attributes.get("identifier", "")
        location = attributes.get("install-location", "")
        version = attributes.get("version", "")
        if any(
            len(value) > MAX_FIELD_LENGTH for value in (identifier, location, version)
        ):
            raise RuntimeError(
                "PackageInfo identifier or install-location exceeds length bound"
            )
        diagnostic = f"{identifier or '<none>'}@{location or '<none>'}"
        joined_size = sum(map(len, diagnostics)) + 2 * len(diagnostics)
        if (
            len(diagnostics) < MAX_DIAGNOSTICS
            and joined_size + len(diagnostic) <= MAX_DIAGNOSTIC_CHARS - 64
        ):
            diagnostics.append(diagnostic)
        else:
            omitted += 1
        if identifier != expected_identifier or location != INSTALL_LOCATION:
            continue
        if expected_version is not None and version != expected_version:
            raise RuntimeError(
                f"official R framework component version mismatch: expected {expected_version}, found {version or '<missing>'}"
            )
        component = package_info.parent.resolve(strict=True)
        if not component.is_relative_to(root):
            raise RuntimeError(
                f"R framework component escapes expanded root: {component}"
            )
        payload = component / "Payload"
        framework = payload / "R.framework"
        if payload.is_symlink() or framework.is_symlink() or not framework.is_dir():
            raise RuntimeError(
                "official R framework component lacks a safe Payload/R.framework"
            )
        resolved = framework.resolve(strict=True)
        if not resolved.is_relative_to(component):
            raise RuntimeError(
                f"R.framework payload escapes its component: {framework}"
            )
        candidates.append(resolved)
    if len(candidates) != 1:
        detail = ", ".join(diagnostics) or "no PackageInfo files"
        if omitted:
            detail += f"; {omitted} additional component(s) omitted"
        raise RuntimeError(
            f"expected exactly one official R framework component; found {len(candidates)} ({detail})"
        )
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expanded-root", type=Path, required=True)
    parser.add_argument("--expected-version", default=LOCKED_VERSION)
    parser.add_argument("--identifier", default=IDENTIFIER)
    args = parser.parse_args()
    print(resolve_framework(args.expanded_root, args.expected_version, args.identifier))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
