#!/usr/bin/env python3
"""Relocate a kit rpy2 API bridge for its concrete final app location."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dependencies(path: Path) -> list[str]:
    completed = subprocess.run(
        ["otool", "-L", str(path)], capture_output=True, text=True, check=True
    )
    return [
        line.strip().split(" (", 1)[0] for line in completed.stdout.splitlines()[1:]
    ]


def resolve_loader_dependency(owner: Path, dependency: str) -> Path | None:
    prefix = "@loader_path/"
    if not dependency.startswith(prefix):
        return None
    return (owner.parent / dependency[len(prefix) :]).resolve(strict=True)


def relocate(
    source_bridge: Path,
    destination_bridge: Path,
    source_r: Path,
    destination_r: Path,
) -> dict[str, object]:
    source_bridge = source_bridge.resolve(strict=True)
    destination_bridge = destination_bridge.resolve(strict=True)
    source_r = source_r.resolve(strict=True)
    destination_r = destination_r.resolve(strict=True)
    source_sha256 = sha256(source_bridge)
    if sha256(destination_bridge) != source_sha256:
        raise ValueError(
            "destination API bridge does not match the authenticated kit source"
        )
    matches = [
        dependency
        for dependency in dependencies(source_bridge)
        if resolve_loader_dependency(source_bridge, dependency) == source_r
    ]
    if len(matches) != 1:
        raise ValueError(
            "authenticated API bridge must have exactly one kit-owned libR load"
        )
    old = matches[0]
    new = "@loader_path/" + os.path.relpath(destination_r, destination_bridge.parent)
    subprocess.run(
        ["install_name_tool", "-change", old, new, str(destination_bridge)], check=True
    )
    observed = dependencies(destination_bridge)
    if old in observed or observed.count(new) != 1:
        raise ValueError(
            "final API bridge libR load command was not relocated exactly once"
        )
    if resolve_loader_dependency(destination_bridge, new) != destination_r:
        raise ValueError(
            "final API bridge libR load does not resolve to the app-owned runtime"
        )
    return {
        "schema_version": 1,
        "kind": "mach-o-load-command-relocation",
        "source": {"path": str(source_bridge), "sha256": source_sha256},
        "output": {
            "path": str(destination_bridge),
            "sha256": sha256(destination_bridge),
        },
        "changes": [{"old": old, "new": new, "resolved_path": str(destination_r)}],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-bridge", type=Path, required=True)
    parser.add_argument("--destination-bridge", type=Path, required=True)
    parser.add_argument("--source-r", type=Path, required=True)
    parser.add_argument("--destination-r", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    evidence = relocate(
        args.source_bridge, args.destination_bridge, args.source_r, args.destination_r
    )
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"rpy2 API bridge relocation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
