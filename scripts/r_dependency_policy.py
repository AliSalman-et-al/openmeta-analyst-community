"""Load and emit the manifest-owned native R binary dependency policy."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


POLICY_REPOSITORY = "https://packagemanager.posit.co/cran/2026-07-16"
EXPECTED_R_VERSION = "4.6.1"
EXPECTED_PLATFORMS = {
    "windows-x64": ("Windows", "x86_64", "win.binary", "bin/windows/contrib/4.6"),
    "macos-x64": (
        "Darwin",
        "x86_64",
        "mac.binary.big-sur-x86_64",
        "bin/macosx/big-sur-x86_64/contrib/4.6",
    ),
    "macos-arm64": (
        "Darwin",
        "aarch64",
        "mac.binary.sonoma-arm64",
        "bin/macosx/sonoma-arm64/contrib/4.6",
    ),
}
HSROC = {
    "name": "HSROC",
    "version": "2.1.9",
    "url": "https://cran.r-project.org/src/contrib/Archive/HSROC/HSROC_2.1.9.tar.gz",
    "sha256": "5476fa76d7723717e203925a1da442813e3645790ef9b633a145cbc04a08b874",
    "dependencies": ["lattice", "coda", "MASS", "MCMCpack"],
    "install_type": "source",
    "repos": None,
    "dependencies_install": False,
}


class PolicyError(ValueError):
    """Raised when the dependency manifest does not encode the release policy."""


def load_policy(manifest_path: Path) -> dict:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyError(f"cannot read R dependency policy: {exc}") from exc

    if manifest.get("schema_version") != 2:
        raise PolicyError("R dependency policy requires manifest schema_version 2")
    runtime = manifest.get("target_runtime")
    if not isinstance(runtime, dict) or runtime.get("r") != EXPECTED_R_VERSION:
        raise PolicyError(f"R dependency policy requires R {EXPECTED_R_VERSION}")
    if runtime.get("cran_policy") != "dated-native-binary-only":
        raise PolicyError("normal R packages must use dated-native-binary-only")

    policy = manifest.get("binary_package_policy")
    if not isinstance(policy, dict):
        raise PolicyError("binary_package_policy must be an object")
    if policy.get("provider") != "Posit Public Package Manager":
        raise PolicyError(
            "normal R package provider must be Posit Public Package Manager"
        )
    if policy.get("repository") != POLICY_REPOSITORY:
        raise PolicyError(f"normal R package repository must be {POLICY_REPOSITORY}")
    if policy.get("snapshot") != "2026-07-16":
        raise PolicyError("normal R package snapshot must be 2026-07-16")
    if (
        policy.get("normal_install_type") != "binary"
        or policy.get("source_fallback") is not False
    ):
        raise PolicyError(
            "normal R packages must be binary-only without source fallback"
        )
    if policy.get("install_options") != {
        "install.packages.check.source": "no",
        "install.packages.compile.from.source": "never",
    }:
        raise PolicyError(
            "binary install options must disable source checks and compilation"
        )

    platforms = policy.get("platforms")
    if not isinstance(platforms, dict) or set(platforms) != set(EXPECTED_PLATFORMS):
        raise PolicyError(
            "binary package platforms must be Windows x64 and both macOS architectures"
        )
    for target, expected in EXPECTED_PLATFORMS.items():
        record = platforms.get(target)
        actual = (
            (
                record.get("system"),
                record.get("r_arch"),
                record.get("pkg_type"),
                record.get("contrib_path"),
            )
            if isinstance(record, dict)
            else None
        )
        if actual != expected:
            raise PolicyError(f"invalid native binary mapping for {target}: {actual!r}")

    exceptions = policy.get("source_exceptions")
    if exceptions != [HSROC]:
        raise PolicyError("HSROC 2.1.9 must be the sole pinned source exception")

    dependency_records = [
        *manifest.get("direct_RCMetaR_dependencies", []),
        *manifest.get("app_r_bundle_dependencies", []),
    ]
    declared_normal_packages = {
        record["name"]
        for record in dependency_records
        if isinstance(record, dict) and record.get("source") == "cran"
    }
    normal_packages = policy.get("required_normal_packages")
    if (
        not isinstance(normal_packages, list)
        or len(normal_packages) != 57
        or len(set(normal_packages)) != 57
        or not all(isinstance(name, str) and name for name in normal_packages)
    ):
        raise PolicyError(
            "required_normal_packages must contain 57 unique package names"
        )
    if not declared_normal_packages <= set(normal_packages):
        raise PolicyError(
            "every manifest CRAN dependency must be in required_normal_packages"
        )
    normal_packages = sorted(normal_packages)
    runtime_packages = sorted(
        record["name"]
        for record in dependency_records
        if isinstance(record, dict)
        and record.get("source") in {"base-runtime", "recommended"}
        and record.get("name") != "R"
    )
    direct_hsroc = [
        record
        for record in manifest.get("direct_RCMetaR_dependencies", [])
        if isinstance(record, dict) and record.get("name") == "HSROC"
    ]
    if len(direct_hsroc) != 1 or direct_hsroc[0].get("source") != "cran-archive":
        raise PolicyError(
            "HSROC source exception must match the direct dependency manifest"
        )
    if direct_hsroc[0].get("installed_version") != HSROC["version"]:
        raise PolicyError("HSROC manifest version does not match the source exception")

    direct_meta = [
        record
        for record in manifest.get("direct_RCMetaR_dependencies", [])
        if isinstance(record, dict) and record.get("name") == "meta"
    ]
    if len(direct_meta) != 1 or direct_meta[0].get("source") != "cran":
        raise PolicyError("meta 8.5-0 must be the direct RCMetaR CRAN runtime root")
    if direct_meta[0].get("installed_version") != "8.5-0":
        raise PolicyError("direct RCMetaR meta runtime must be pinned to 8.5-0")
    for package in ("metabook", "CompQuadForm"):
        direct = [
            record
            for record in manifest.get("direct_RCMetaR_dependencies", [])
            if isinstance(record, dict) and record.get("name") == package
        ]
        closure = [
            record
            for record in manifest.get("app_r_bundle_dependencies", [])
            if isinstance(record, dict) and record.get("name") == package
        ]
        if direct or len(closure) != 1 or closure[0].get("source") != "cran":
            raise PolicyError(f"{package} must remain transitive app closure only")

    return {
        "repository": policy["repository"],
        "provider": policy["provider"],
        "snapshot": policy["snapshot"],
        "r_version": runtime["r"],
        "platforms": platforms,
        "normal_packages": normal_packages,
        "runtime_packages": runtime_packages,
        "source_exception": exceptions[0],
    }


def _dcf_value(value: str) -> str:
    if "\n" in value or "\r" in value or value.startswith((" ", "\t")):
        raise PolicyError(f"value cannot be represented as one DCF field: {value!r}")
    return value


def emit_dcf(policy: dict) -> str:
    fields = {
        "Repository": policy["repository"],
        "Provider": policy["provider"],
        "Snapshot": policy["snapshot"],
        "R-Version": policy["r_version"],
        "Normal-Packages": ",".join(policy["normal_packages"]),
        "Runtime-Packages": ",".join(policy["runtime_packages"]),
    }
    for target, record in policy["platforms"].items():
        prefix = target.replace("-", "_")
        fields[f"{prefix}-System"] = record["system"]
        fields[f"{prefix}-R-Arch"] = record["r_arch"]
        fields[f"{prefix}-Pkg-Type"] = record["pkg_type"]
        fields[f"{prefix}-Contrib-Path"] = record["contrib_path"]
    exception = policy["source_exception"]
    fields.update(
        {
            "Source-Exception-Name": exception["name"],
            "Source-Exception-Version": exception["version"],
            "Source-Exception-URL": exception["url"],
            "Source-Exception-SHA256": exception["sha256"],
            "Source-Exception-Dependencies": ",".join(exception["dependencies"]),
        }
    )
    return (
        "\n".join(f"{key}: {_dcf_value(str(value))}" for key, value in fields.items())
        + "\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--sha256", type=Path)
    parser.add_argument("--emit-dcf", action="store_true")
    args = parser.parse_args(argv)
    if args.sha256 is not None:
        print(hashlib.sha256(args.sha256.read_bytes()).hexdigest())
        return 0
    if args.manifest is None or not args.emit_dcf:
        parser.error("--manifest and --emit-dcf are required unless --sha256 is used")
    try:
        print(emit_dcf(load_policy(args.manifest)), end="")
    except PolicyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
