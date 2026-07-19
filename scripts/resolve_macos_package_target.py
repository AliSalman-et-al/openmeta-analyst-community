#!/usr/bin/env python3
"""Resolve the shared target-native macOS packaging contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shlex
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "config" / "macos-package-targets.json"
REQUIRED_TARGET_FIELDS = {
    "delivery_target",
    "machine",
    "runner",
    "artifact",
    "qt_arch",
    "qt_sdk_arch",
    "r_component_identifier",
    "r_url",
    "r_sha256",
}


class TargetError(RuntimeError):
    pass


def load_target(name: str, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise TargetError("unsupported macOS package target manifest")
    targets = manifest.get("targets")
    if not isinstance(targets, dict) or name not in targets:
        raise TargetError(f"unknown macOS package target: {name}")
    target = targets[name]
    if not isinstance(target, dict) or set(target) != REQUIRED_TARGET_FIELDS:
        raise TargetError(f"incomplete macOS package target: {name}")
    if target["delivery_target"] != f"macos-{name}":
        raise TargetError(f"delivery target does not match architecture: {name}")
    if target["machine"] not in {"x86_64", "arm64"}:
        raise TargetError(f"unsupported machine for macOS package target: {name}")
    if not str(target["r_url"]).startswith("https://cloud.r-project.org/"):
        raise TargetError("official R package must use the authenticated CRAN origin")
    sha256 = target["r_sha256"]
    if sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", str(sha256)):
        raise TargetError(f"invalid R package SHA-256 for target: {name}")
    return {
        "architecture": name,
        "r_version": manifest["r_version"],
        "minimum_macos": manifest["minimum_macos"],
        **target,
    }


def shell_lines(target: dict[str, object]) -> str:
    return "\n".join(
        f"{key}={shlex.quote('' if value is None else str(value))}"
        for key, value in target.items()
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("architecture", choices=("x64", "arm64"))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--format", choices=("json", "shell"), default="json")
    args = parser.parse_args()
    try:
        target = load_target(args.architecture, args.manifest)
    except (OSError, json.JSONDecodeError, TargetError) as exc:
        parser.error(str(exc))
    if args.format == "shell":
        print(shell_lines(target))
    else:
        json.dump(target, sys.stdout, indent=2, sort_keys=True)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
