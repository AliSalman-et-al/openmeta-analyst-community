#!/usr/bin/env python3
"""Create the canonical named-input provenance for a direct macOS R build."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from inspect_macos_deployment import DIRECT_BUILD_INPUT_MEMBERS


def record(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ValueError(f"required direct-build input is absent: {path}")
    return {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size": path.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qualification-root", type=Path, required=True)
    parser.add_argument("--ppm-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--bridge", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.qualification_root
    names = {
        "adapter_script": root / "embedded-r-adapter.py",
        "pre_normalization_audit": root / "direct-r-pre-normalization-audit.json",
        "normalized_adapter_map": root / "direct-r-adapter.json",
        "host_r_isolation_script": root / "macos-host-r-isolation.sh",
        "pyinstaller_toc_preflight": root / "verify-macos-r-pyinstaller-toc.py",
        "pyinstaller_toc_preflight_report": root
        / "macos-r-pyinstaller-toc-preflight.json",
        "explicit_r_toc": root / "direct-r-toc.json",
        "rpy2_api_build": root / "rpy2-api-build.json",
        "pre_sign_native_graph": root / "pre-sign-native-graph.json",
        "post_sign_native_inventory": root / "post-sign-native-inventory.json",
        "signing_inventory": root / "ad-hoc-signing-inventory.json",
        "ppm_archive_inventory": root / "ppm-archive-inventory.json",
        "hsroc_source_archive": root / "HSROC_2.1.9.tar.gz",
        "rcmetar_source_archive": root / "RCMetaR-0.2.0-source.tar.gz",
        "r_runtime_profile": root / "embedded-r-runtime-profile.json",
        "runtime_probe": root / "runtime-probe.json",
        "runtime_stdout": root / "runtime-probe.stdout.log",
        "runtime_stderr": root / "runtime-probe.stderr.log",
        "deployment_manifest": root / "deployment-manifest.json",
        "smoke_evidence": root / "packaged-smoke.json",
        "smoke_log": root / "packaged-smoke.log",
        "smoke_stdout": root / "packaged-smoke.stdout.log",
        "smoke_stderr": root / "packaged-smoke.stderr.log",
        "hang_trace": root / "packaged-smoke.hang-trace.log",
        "launchservices_marker": root / "launchservices-completion.json",
        "launchservices_stdout": root / "launchservices.stdout.log",
        "launchservices_stderr": root / "launchservices.stderr.log",
        "runner_environment": root / "runner-environment.json",
        "official_r_signature": root / "official-r-signature.json",
        "surface_125_stdout": root / "packaged-surface-125.stdout.log",
        "surface_125_stderr": root / "packaged-surface-125.stderr.log",
        "surface_150_stdout": root / "packaged-surface-150.stdout.log",
        "surface_150_stderr": root / "packaged-surface-150.stderr.log",
        "surface_175_stdout": root / "packaged-surface-175.stdout.log",
        "surface_175_stderr": root / "packaged-surface-175.stderr.log",
    }
    if set(names) != set(DIRECT_BUILD_INPUT_MEMBERS):
        raise ValueError("provenance input map drifted from validator")

    def ppm(path: Path) -> dict[str, object]:
        relative = str(path.relative_to(args.ppm_root))
        package, version = path.name.rsplit(".", 1)[0].rsplit("_", 1)
        return {
            "path": relative,
            "package": package,
            "version": version,
            "archive_url": "https://packagemanager.posit.co/cran/2026-07-16/bin/macosx/big-sur-x86_64/contrib/4.6/"
            + relative,
            **record(path),
        }

    archives = [
        ppm(path) for path in sorted(args.ppm_root.rglob("*")) if path.is_file()
    ]
    if not archives:
        raise ValueError("PPM archive inventory is empty")
    (root / "ppm-archive-inventory.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "repository": "https://packagemanager.posit.co/cran/2026-07-16",
                "archives": archives,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    inputs = {key: record(path) for key, path in names.items()}
    hsroc, rcmetar = names["hsroc_source_archive"], names["rcmetar_source_archive"]
    payload = {
        "schema_version": 1,
        "kind": "rc-metastudio-direct-macos-target-build",
        "target": "macos-x64",
        "source_commit": args.source_commit,
        "official_r": {
            "url": "https://cloud.r-project.org/bin/macosx/big-sur-x86_64/base/R-4.6.1-x86_64.pkg",
            "sha256": "612bb00cb4c627721d6d80b0f5224227c0fcdefb4a5b6c917511480361c16571",
        },
        "ppm_snapshot": "https://packagemanager.posit.co/cran/2026-07-16",
        "ppm_archives": archives,
        "hsroc_source_exception": {
            "name": "HSROC",
            "version": "2.1.9",
            "install_type": "source",
            "url": "https://cran.r-project.org/src/contrib/Archive/HSROC/HSROC_2.1.9.tar.gz",
            "sha256": "5476fa76d7723717e203925a1da442813e3645790ef9b633a145cbc04a08b874",
            "archive": record(hsroc),
        },
        "rcmetar_source": {
            "name": "RCMetaR",
            "version": "0.2.0",
            "url": "https://github.com/ResearchConsultancy/rc-metastudio/tree/"
            + args.source_commit
            + "/r/RCMetaR",
            "source_commit": args.source_commit,
            "archive_sha256": record(rcmetar)["sha256"],
            "archive": record(rcmetar),
        },
        "rpy2_api_bridge_source_sha256": record(args.bridge)["sha256"],
        "inputs": inputs,
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
