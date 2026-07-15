#!/usr/bin/env python3
"""Run the invariant verification contract for every release package target."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_TEST_PATHS = (
    "tests/packaging/contract",
    "tests/python/fast/test_pyqt5_verification_path.py",
    "tests/python/fast/test_pyqt5_generated_ui_imports.py",
    "tests/python/fast/test_project_pickle_migration.py",
    "tests/python/fast/test_qt_text_boundaries.py",
)


def run(command: list[str]) -> None:
    print("[package-release] " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the shared Windows/macOS release-package verification contract."
    )
    parser.add_argument("--rscript", required=True)
    parser.add_argument("--r-library-cache-root", required=True)
    args = parser.parse_args(argv)

    run([sys.executable, "scripts/validate_test_taxonomy.py", "--strict"])
    run([sys.executable, "-m", "pytest", *PACKAGE_TEST_PATHS])
    run(
        [
            sys.executable,
            "scripts/verify_rcmetar_r_stack.py",
            "--rscript",
            args.rscript,
            "--r-library-cache-root",
            args.r_library_cache_root,
        ]
    )
    print("[package-release] Shared package verification complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
