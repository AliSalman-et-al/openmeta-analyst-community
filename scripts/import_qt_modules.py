"""Import every handwritten PyQt6 module with Python warnings fatal."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from rc_metastudio.qt6_cutover import (
    discover_application_qt_modules,
    discover_handwritten_qt_files,
)


def import_modules(root: Path, build_root: Path) -> list[dict[str, object]]:
    root = root.resolve()
    build_root = build_root.resolve()
    generated = build_root / "generated/rc_metastudio"
    bootstrap = """
import importlib, os, sys
root, generated, module = sys.argv[1:4]
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('RCMS_STUB_BACKEND', '1')
sys.path[:0] = [root + '/src/rc_metastudio', root + '/src']
from rc_metastudio.qt6_ui import prepare_generated_ui_imports
prepare_generated_ui_imports()
import rc_metastudio.qt6_resources as resources
resources.ensure_application_resources()
importlib.import_module(module)
"""
    results: list[dict[str, object]] = []
    for path in discover_application_qt_modules(root):
        completed = subprocess.run(
            [sys.executable, "-W", "error", "-c", bootstrap, str(root), str(generated), path.stem],
            cwd=root,
            env={**os.environ, "PYTHONWARNINGS": "error", "RCMS_QT6_BUILD_ROOT": str(build_root)},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        results.append(
            {
                "module": path.relative_to(root).as_posix(),
                "returncode": completed.returncode,
                "stderr": completed.stderr.strip(),
            }
        )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--build-root", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--list", action="store_true", help="print all Qt-bearing type-check inputs")
    parser.add_argument("--list-imports", action="store_true", help="print importable application modules")
    args = parser.parse_args(argv)
    if args.list:
        for path in discover_handwritten_qt_files(args.root):
            print(path.relative_to(args.root.resolve()).as_posix())
        return 0
    if args.list_imports:
        for path in discover_application_qt_modules(args.root):
            print(path.relative_to(args.root.resolve()).as_posix())
        return 0
    if args.build_root is None or args.report is None:
        parser.error("--build-root and --report are required unless --list is used")
    results = import_modules(args.root, args.build_root)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({"schema_version": 1, "modules": results}, indent=2) + "\n", encoding="utf-8")
    failures = [result for result in results if result["returncode"] != 0]
    if failures:
        for failure in failures:
            print(f"{failure['module']}: {failure['stderr']}", file=sys.stderr)
        return 1
    print(f"Imported {len(results)} handwritten Qt modules with warnings fatal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
