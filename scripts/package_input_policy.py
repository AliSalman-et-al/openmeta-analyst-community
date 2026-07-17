#!/usr/bin/env python3
"""Classify direct Windows/macOS release-package qualification inputs."""

from __future__ import annotations

import argparse
import fnmatch
import sys


PACKAGE_INPUT_PATTERNS = (
    ".github/workflows/fast-verification.yml",
    ".github/workflows/package-target.yml",
    ".github/workflows/release-candidate.yml",
    "packaging/*",
    "pyproject.toml",
    "uv.lock",
    "sample_projects/*",
    "r/*",
    "src/*",
    "tests/packaging/*",
    "tests/python/fast/test_qt6_cutover_finalization.py",
    "tests/python/fast/test_qt6_build_slice.py",
    "tests/python/fast/test_project_format.py",
    "tests/python/fast/test_qt_text_boundaries.py",
    "tests/python/gui/test_metaform_automation_launch.py",
    "scripts/build-windows-package.ps1",
    "scripts/test-bounded-package-process.ps1",
    "scripts/package-windows.ps1",
    "scripts/inspect_windows_deployment.py",
    "scripts/build-macos-package.sh",
    "scripts/package-macos.sh",
    "scripts/inspect_macos_deployment.py",
    "scripts/sign_macos_app.py",
    "scripts/sign-notarize-macos-package.sh",
    "scripts/qt6_macos_feasibility.py",
    "scripts/run_bounded_process.py",
    "scripts/package_input_policy.py",
    "scripts/install-r-deps.R",
    "scripts/r_binary_policy.R",
    "scripts/r_dependency_policy.py",
    "scripts/build_qt6.py",
    "scripts/verify_package_release.py",
    "scripts/verify_rcmetar_r_stack.py",
    "scripts/resolve_package_ci_metadata.py",
    "scripts/validate_adaptive_layout_evidence.py",
    "scripts/validate_test_taxonomy.py",
    "scripts/delivery.py",
    "docs/verification/RCMetaR-r-dependencies.json",
    "docs/verification/test-taxonomy.json",
    "delivery/targets.json",
)


def requires_package_qualification(paths: list[str]) -> bool:
    return any(
        fnmatch.fnmatchcase(path.replace("\\", "/"), pattern)
        for path in paths
        for pattern in PACKAGE_INPUT_PATTERNS
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    paths = [line.strip() for line in sys.stdin if line.strip()]
    print("true" if requires_package_qualification(paths) else "false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
