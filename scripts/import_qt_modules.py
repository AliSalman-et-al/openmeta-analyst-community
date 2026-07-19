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


ISOLATED_IMPORT_BOOTSTRAP = """
import importlib, importlib.util, os, pathlib, sys
root, generated, relative = sys.argv[1:4]
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['RCMS_STUB_BACKEND'] = '1'
os.environ.pop('RCMS_REQUIRE_IN_PROCESS_RPY2', None)
sys.path[:0] = [root + '/scripts', root + '/src/rc_metastudio', root + '/src']
import meta_py_r_backend
backend = meta_py_r_backend.install_meta_py_r_backend()
if not getattr(backend, '_oma_stub_backend', False):
    raise RuntimeError('Qt warnings audit did not install the stub analysis backend')
if sys.modules.get('rc_metastudio.meta_py_r') is not backend:
    raise RuntimeError('Qt warnings audit did not register the package stub backend')
if sys.modules.get('meta_py_r') is not backend:
    raise RuntimeError('Qt warnings audit did not register the legacy stub alias')
from rc_metastudio.qt6_ui import prepare_generated_ui_imports
prepare_generated_ui_imports()
import rc_metastudio.qt6_resources as resources
resources.ensure_application_resources()
path = pathlib.Path(root, relative)
if relative.startswith('scripts/'):
    name = '_rcms_qt_warnings_audit_' + path.stem
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError('cannot create isolated import spec for ' + relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
else:
    importlib.import_module(path.stem)
if any(name == 'rpy2' or name.startswith('rpy2.') for name in sys.modules):
    raise RuntimeError('Qt warnings audit initialized the real rpy2 backend')
print('RCMS_QT_WARNINGS_AUDIT_IMPORTED=' + relative, flush=True)
"""


def _success_marker(relative: str) -> str:
    return "RCMS_QT_WARNINGS_AUDIT_IMPORTED=" + relative


def import_modules(root: Path, build_root: Path) -> list[dict[str, object]]:
    root = root.resolve()
    build_root = build_root.resolve()
    generated = build_root / "generated/rc_metastudio"
    results: list[dict[str, object]] = []
    for path in discover_handwritten_qt_files(root):
        relative = path.relative_to(root).as_posix()
        completed = subprocess.run(
            [
                sys.executable,
                "-W",
                "error",
                "-c",
                ISOLATED_IMPORT_BOOTSTRAP,
                str(root),
                str(generated),
                relative,
            ],
            cwd=root,
            env={**os.environ, "PYTHONWARNINGS": "error", "RCMS_QT6_BUILD_ROOT": str(build_root)},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        returncode = completed.returncode
        stderr = completed.stderr.strip()
        if returncode == 0 and _success_marker(relative) not in completed.stdout.splitlines():
            returncode = 1
            stderr = (
                stderr + "\n" if stderr else ""
            ) + "isolated import exited before its success marker"
        results.append(
            {
                "module": relative,
                "returncode": returncode,
                "stderr": stderr,
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
