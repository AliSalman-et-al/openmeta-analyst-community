#!/usr/bin/env python3
"""Run the invariant verification contract for every release package target."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_TEST_PATHS = (
    "tests/packaging/contract",
    "tests/python/fast/test_qt6_cutover_finalization.py",
    "tests/python/fast/test_qt6_build_slice.py",
    "tests/python/fast/test_project_format.py",
    "tests/python/fast/test_qt_text_boundaries.py",
)


def run(command: list[str]) -> None:
    print("[package-release] " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def run_qt6_pytest(paths: tuple[str, ...]) -> None:
    bootstrap = (
        "import sys; "
        "from rc_metastudio.qt6_ui import prepare_generated_ui_imports; "
        "prepare_generated_ui_imports(); "
        "import pytest; raise SystemExit(pytest.main(sys.argv[1:]))"
    )
    run([sys.executable, "-c", bootstrap, *paths])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the shared Windows/macOS release-package verification contract."
    )
    parser.add_argument("--rscript", required=True)
    parser.add_argument("--r-library-cache-root", required=True)
    args = parser.parse_args(argv)

    missing = [path for path in PACKAGE_TEST_PATHS if not (ROOT / path).exists()]
    if missing:
        raise FileNotFoundError(
            f"package verification names missing test paths: {missing}"
        )

    qt6_build_root = ROOT / "build/package-release-qt6"
    run(
        [
            sys.executable,
            "scripts/build_qt6.py",
            "generate",
            "--build-root",
            str(qt6_build_root),
        ]
    )
    os.environ["RCMS_QT6_BUILD_ROOT"] = str(qt6_build_root)
    generated_package = qt6_build_root / "generated/rc_metastudio"
    generated_forms = generated_package / "forms"
    os.environ["PYTHONPATH"] = os.pathsep.join(
        [
            str(generated_package),
            str(generated_forms),
            os.environ.get("PYTHONPATH", ""),
        ]
    )

    run([sys.executable, "scripts/validate_test_taxonomy.py", "--strict"])
    run_qt6_pytest(PACKAGE_TEST_PATHS)
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
