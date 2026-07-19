#!/usr/bin/env python3
"""Normalize a NUL-delimited Mach-O inventory to one required architecture."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from typing import Sequence


class MachONormalizationError(RuntimeError):
    """Raised when a Mach-O cannot be proven thin for the requested architecture."""


def _run_lipo(arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["lipo", *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MachONormalizationError(
            f"lipo failed for {arguments[-1]}: {exc}"
        ) from exc


def _architectures(path: Path) -> tuple[str, ...]:
    completed = _run_lipo(["-archs", str(path)])
    architectures = tuple(completed.stdout.split())
    if not architectures or any(not item.strip() for item in architectures):
        raise MachONormalizationError(f"lipo returned no architectures for {path}")
    return architectures


def normalize_macho(path: Path, *, architecture: str = "x86_64") -> None:
    """Atomically thin one universal Mach-O and verify its exact final slice."""
    path = Path(path)
    architectures = _architectures(path)
    if architectures == (architecture,):
        return
    if architecture not in architectures:
        raise MachONormalizationError(
            f"Mach-O has no {architecture} slice: {path} ({architectures})"
        )

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.thin-", dir=path.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        _run_lipo(["-thin", architecture, str(path), "-output", str(temporary)])
        temporary_architectures = _architectures(temporary)
        if temporary_architectures != (architecture,):
            raise MachONormalizationError(
                "lipo produced a non-thin temporary Mach-O: "
                f"{path} ({temporary_architectures})"
            )
        os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

    final_architectures = _architectures(path)
    if final_architectures != (architecture,):
        raise MachONormalizationError(
            f"thinned Mach-O is not exactly {architecture}: {path} ({final_architectures})"
        )


def normalize_manifest(manifest: Path, *, architecture: str = "x86_64") -> int:
    """Normalize and verify every path in a NUL-delimited manifest."""
    payload = Path(manifest).read_bytes()
    raw_paths = [item for item in payload.split(b"\0") if item]
    if not raw_paths:
        raise MachONormalizationError("Mach-O manifest is empty")
    for raw_path in raw_paths:
        normalize_macho(Path(os.fsdecode(raw_path)), architecture=architecture)
    return len(raw_paths)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--architecture", default="x86_64")
    args = parser.parse_args()
    try:
        count = normalize_manifest(args.manifest, architecture=args.architecture)
    except (MachONormalizationError, OSError) as exc:
        parser.error(str(exc))
    print(f"Normalized and verified {count} Mach-O files as {args.architecture}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
