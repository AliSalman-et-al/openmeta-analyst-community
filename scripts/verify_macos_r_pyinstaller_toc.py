#!/usr/bin/env python3
"""Prove PyInstaller 6.21 preserves the explicit CRAN R.framework TOC."""

from __future__ import annotations

import argparse
import importlib.util
from importlib import metadata
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
ALIASES = {
    "Versions/Current": "4.6-x86_64",
    "Resources": "Versions/Current/Resources",
    "R": "Versions/Current/R",
    "Versions/4.6-x86_64/R": "Resources/lib/libR.dylib",
    "Versions/4.6-x86_64/Resources/R": "bin/R",
}


def load_adapter():
    location = ROOT / "scripts/macos_embedded_r_adapter.py"
    spec = importlib.util.spec_from_file_location("rcms_embedded_r_adapter", location)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load embedded-R adapter")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if sys.platform != "darwin":
        print("macOS-only PyInstaller TOC preflight skipped")
        return 0
    with tempfile.TemporaryDirectory(prefix="rcms-r-toc-") as raw:
        work = Path(raw)
        framework = work / "source/R.framework"
        resources = framework / "Versions/4.6-x86_64/Resources"
        (resources / "lib").mkdir(parents=True)
        (resources / "bin").mkdir()
        (resources / "lib/libR.dylib").write_bytes(b"fixture-libR\n")
        launcher = resources / "bin/R"
        launcher.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        launcher.chmod(0o755)
        for relative, target in ALIASES.items():
            link = framework / relative
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(target, target_is_directory=relative in {"Versions/Current", "Resources"})
        toc_path = work / "toc.json"
        toc_path.write_text(
            json.dumps({"entries": load_adapter().explicit_toc(framework)}),
            encoding="utf-8",
        )
        entry = work / "entry.py"
        entry.write_text("print('fixture')\n", encoding="utf-8")
        spec = work / "fixture.spec"
        spec.write_text(
            "\n".join(
                (
                    "# -*- mode: python ; coding: utf-8 -*-",
                    "import json, os",
                    "from pathlib import Path",
                    "entries=json.loads(Path(os.environ['RCMS_FIXTURE_TOC']).read_text())['entries']",
                    f"a=Analysis([{str(entry)!r}], pathex=[], binaries=[], datas=[], hiddenimports=[], hookspath=[], hooksconfig={{}}, runtime_hooks=[], excludes=[], noarchive=False, optimize=0)",
                    "a.datas.extend((e['destination'], e['source'], e['type']) for e in entries)",
                    "pyz=PYZ(a.pure)",
                    "exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='Fixture',console=True,target_arch='x86_64',codesign_identity=None,entitlements_file=None)",
                    "coll=COLLECT(exe,a.binaries,a.datas,name='Fixture')",
                    "app=BUNDLE(coll,name='Fixture.app',bundle_identifier='org.rcms.fixture',target_arch='x86_64',codesign_identity=None,entitlements_file=None)",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        environment = {**os.environ, "RCMS_FIXTURE_TOC": str(toc_path)}
        subprocess.run(
            [
                sys.executable,
                "-m",
                "PyInstaller",
                "--clean",
                "--noconfirm",
                "--distpath",
                str(work / "dist"),
                "--workpath",
                str(work / "build"),
                str(spec),
            ],
            cwd=ROOT,
            env=environment,
            check=True,
        )
        bundled = work / "dist/Fixture.app/Contents/Frameworks/R.framework"
        observed = {
            relative: os.readlink(bundled / relative) for relative in ALIASES
        }
        if observed != ALIASES:
            raise RuntimeError(f"PyInstaller changed CRAN R aliases: {observed}")
        for relative in ALIASES:
            (bundled / relative).resolve(strict=True).relative_to(bundled.resolve())
        lib_r = list((work / "dist/Fixture.app").rglob("libR.dylib"))
        expected = bundled / "Versions/4.6-x86_64/Resources/lib/libR.dylib"
        if len(lib_r) != 1 or lib_r[0] != expected:
            raise RuntimeError(f"PyInstaller produced a duplicate/cross-topology libR: {lib_r}")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "source_commit": subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=ROOT,
                        check=True,
                        capture_output=True,
                        text=True,
                    ).stdout.strip(),
                    "pyinstaller_version": metadata.version("PyInstaller"),
                    "system": platform.system(),
                    "machine": platform.machine(),
                    "aliases": ALIASES,
                    "passed": True,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    print("macOS PyInstaller explicit R.framework TOC preflight passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
