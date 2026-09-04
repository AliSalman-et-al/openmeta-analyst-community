#!/usr/bin/env python3
"""Classify direct Windows/macOS release-package qualification inputs."""

from __future__ import annotations

import argparse
import fnmatch
import sys


PACKAGE_INPUT_PATTERNS = (
    ".github/workflows/fast-verification.yml",
    ".github/workflows/package-windows.yml",
    ".github/workflows/package-target.yml",
    ".github/workflows/package-verification.yml",
    ".github/workflows/candidate.yml",
    ".github/workflows/community-release-candidate.yml",
    ".github/workflows/macos-trusted-release-candidate.yml",
    ".github/workflows/notarization-status.yml",
    ".github/workflows/promote.yml",
    "packaging/*",
    "pyproject.toml",
    "uv.lock",
    "sample_projects/*",
    "r/*",
    "src/*",
    "tests/packaging/*",
    "tests/python/fast/test_qt6_build_slice.py",
    "tests/python/fast/test_project_format.py",
    "tests/python/fast/test_qt_text_boundaries.py",
    "tests/python/gui/test_main_window_automation_launch.py",
    "scripts/build-windows-package.ps1",
    "scripts/test-bounded-package-process.ps1",
    "scripts/package-windows.ps1",
    "scripts/inspect_windows_deployment.py",
    "scripts/build-macos-package.sh",
    "scripts/build_macos_direct_provenance.py",
    "scripts/configure_macos_r_launchers.py",
    "config/macos-package-targets.json",
    "scripts/macos_pkg_signature.py",
    "scripts/profile_macos_embedded_r_runtime.py",
    "scripts/relocate_macos_r_runtime.sh",
    "scripts/resolve_macos_r_framework_component.py",
    "scripts/resolve_macos_package_target.py",
    "scripts/macos_embedded_r_adapter.py",
    "scripts/macos_host_r_isolation.sh",
    "scripts/verify_macos_r_pyinstaller_toc.py",
    "scripts/package-macos.sh",
    "scripts/inspect_macos_deployment.py",
    "scripts/normalize_macos_macho.py",
    "scripts/sign_macos_app.py",
    "scripts/sign-notarize-macos-artifact.sh",
    "scripts/qt6_macos_feasibility.py",
    "scripts/run_bounded_process.py",
    "scripts/package_input_policy.py",
    "scripts/install-r-deps.R",
    "scripts/analysis-smoke-test.R",
    "scripts/install-rcmetar-source.R",
    "scripts/r_binary_policy.R",
    "scripts/r_dependency_policy.py",
    "scripts/build_qt6.py",
    "scripts/verify_rcmetar_r_stack.py",
    "scripts/verify_reitsma_visual_qa.R",
    "scripts/r_verification_support.py",
    "scripts/validate_rcmetar_r_manifests.py",
    "scripts/verify_golden_compatibility.py",
    "scripts/assemble_packaged_smoke_evidence.py",
    "scripts/resolve_package_ci_metadata.py",
    "scripts/source_provenance.py",
    "scripts/test-package-download-retry.ps1",
    "scripts/validate_adaptive_layout_evidence.py",
    "scripts/delivery.py",
    "config/r-dependencies.json",
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
