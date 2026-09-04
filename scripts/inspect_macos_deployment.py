#!/usr/bin/env python3
"""Fail-closed inspection and evidence for target-native macOS packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import stat
import subprocess
import sys
from typing import TypeGuard, cast
import unicodedata
import zipfile

from rc_metastudio.macos_macho import (
    MachOError,
    architectures,
    is_macho_candidate,
)
from rc_metastudio.r_runtime import macos_r_framework_version
from rc_metastudio.macos_r_profile_schema import (
    ProfileSchemaError,
    validate_profile_evidence,
)


EXPECTED_VERSIONS = {
    "python": "3.11.9",
    "pyqt6": "6.11.0",
    "qt": "6.11.1",
    "sip": "13.11.1",
    "sip_runtime": "6.15.2",
    "r": "4.6.1",
    "rpy2": "3.6.7",
    "pyinstaller": "6.21.0",
}
EXPECTED_SUMMARY_SHA256_BY_SAMPLE = {
    "amino.rcms": "d37d0aa920c9ae2397b1c44d3fbe9f91d5d89b61fad43ced991148f2e51245d0",
    "BCG.rcms": "2cb1cb0b867b7280a8843f633a9a040f7810d4c9e0ab91ff6333d8110fc41933",
}
EXPECTED_SUMMARY_SHA256 = EXPECTED_SUMMARY_SHA256_BY_SAMPLE["BCG.rcms"]
MAX_FILES = 25_000
MAX_BYTES = 3_000_000_000
MAX_ARCHIVE_MEMBERS = 30_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 3_000_000_000
PORTABLE_FORBIDDEN = set('<>:"/\\|?*')
TARGET_CONTRACTS = {
    "macos-arm64": {"architecture": "arm64", "minimum_macos": "14.0"},
}
TARGET_RUNNERS = {
    "macos-arm64": {"architecture": "ARM64", "label": "macos-15"},
}
DIRECT_R_MARKER_RELATIVE = Path("Contents/Resources/direct-r-spike.marker")
DIRECT_R_MARKER_SHA256 = (
    "bff2ab12435dd85693745bfd390e12b97ad7fecf284a05b1b339425d40ca720f"
)
DIRECT_R_OFFICIAL_INPUTS = {
    "macos-arm64": {
        "url": "https://cloud.r-project.org/bin/macosx/sonoma-arm64/base/R-4.6.1-arm64.pkg",
        "sha256": "67f6eea4ced4ce48f0a0d4fa3a1cac43d1859a05a88993ee3dff7c52e7edbc4b",
    },
}
DIRECT_R_PPM_SNAPSHOT = "https://packagemanager.posit.co/cran/2026-07-16"
DIRECT_BUILD_INPUT_MEMBERS = {
    "adapter_script": "qualification/embedded-r-adapter.py",
    "pre_normalization_audit": "qualification/direct-r-pre-normalization-audit.json",
    "normalized_adapter_map": "qualification/direct-r-adapter.json",
    "host_r_isolation_script": "qualification/macos-host-r-isolation.sh",
    "pyinstaller_toc_preflight": "qualification/verify-macos-r-pyinstaller-toc.py",
    "pyinstaller_toc_preflight_report": "qualification/macos-r-pyinstaller-toc-preflight.json",
    "explicit_r_toc": "qualification/direct-r-toc.json",
    "rpy2_api_build": "qualification/rpy2-api-build.json",
    "pre_sign_native_graph": "qualification/pre-sign-native-graph.json",
    "post_sign_native_inventory": "qualification/post-sign-native-inventory.json",
    "signing_inventory": "qualification/ad-hoc-signing-inventory.json",
    "ppm_archive_inventory": "qualification/ppm-archive-inventory.json",
    "rcmetar_source_archive": "qualification/RCMetaR-0.2.0-source.tar.gz",
    "r_runtime_profile": "qualification/embedded-r-runtime-profile.json",
    "runtime_probe": "qualification/runtime-probe.json",
    "runtime_stdout": "qualification/runtime-probe.stdout.log",
    "runtime_stderr": "qualification/runtime-probe.stderr.log",
    "deployment_manifest": "qualification/deployment-manifest.json",
    "smoke_evidence": "qualification/packaged-smoke.json",
    "smoke_log": "qualification/packaged-smoke.log",
    "smoke_stdout": "qualification/packaged-smoke.stdout.log",
    "smoke_stderr": "qualification/packaged-smoke.stderr.log",
    "hang_trace": "qualification/packaged-smoke.hang-trace.log",
    "launchservices_marker": "qualification/launchservices-completion.json",
    "launchservices_stdout": "qualification/launchservices.stdout.log",
    "launchservices_stderr": "qualification/launchservices.stderr.log",
    "runner_environment": "qualification/runner-environment.json",
    "official_r_signature": "qualification/official-r-signature.json",
    "surface_125_stdout": "qualification/packaged-surface-125.stdout.log",
    "surface_125_stderr": "qualification/packaged-surface-125.stderr.log",
    "surface_150_stdout": "qualification/packaged-surface-150.stdout.log",
    "surface_150_stderr": "qualification/packaged-surface-150.stderr.log",
    "surface_175_stdout": "qualification/packaged-surface-175.stdout.log",
    "surface_175_stderr": "qualification/packaged-surface-175.stderr.log",
}


class MacOSDeploymentInspectionError(RuntimeError):
    """Raised when an assembled macOS package is not self-consistent."""


def _macos_version(value: str) -> tuple[int, int, int]:
    try:
        parts = tuple(int(part) for part in value.split("."))
    except ValueError as exc:
        raise MacOSDeploymentInspectionError(
            f"invalid macOS deployment version: {value}"
        ) from exc
    if not 1 <= len(parts) <= 3 or any(part < 0 for part in parts):
        raise MacOSDeploymentInspectionError(
            f"invalid macOS deployment version: {value}"
        )
    padded = (*parts, *(0 for _ in range(3 - len(parts))))
    return padded[0], padded[1], padded[2]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mapping_or_empty(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        return {}
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            return {}
        result[key] = item
    return result


def _int_or_default(value: object, default: int) -> int:
    return value if isinstance(value, int) else default


def _float_or_default(value: object, default: float) -> float:
    return float(value) if isinstance(value, (int, float)) else default


def _strings_or_empty(value: object) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return []
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            return []
        result.append(item)
    return result


def _valid_r_kit_derivation(
    manifest: dict[str, object], derivation: dict[str, object], target: str
) -> bool:
    manifest_records = manifest.get("files")
    if not isinstance(manifest_records, list):
        return False
    manifest_files = {
        record.get("path"): record
        for value in manifest_records
        for record in [_mapping_or_empty(value)]
        if record.get("kind") == "file"
    }
    source_group = _mapping_or_empty(derivation.get("source"))
    pre_sign_group = _mapping_or_empty(derivation.get("pre_sign"))
    final_group = _mapping_or_empty(derivation.get("final"))
    transformations = _mapping_or_empty(derivation.get("transformations"))
    for name in ("api_bridge", "r_shared_library"):
        source = _mapping_or_empty(source_group.get(name))
        pre_sign = _mapping_or_empty(pre_sign_group.get(name))
        final = _mapping_or_empty(final_group.get(name))
        transformation = _mapping_or_empty(transformations.get(name))
        pre_sign_is_derived = pre_sign.get("sha256") == source.get("sha256") or (
            name == "api_bridge"
            and transformation.get("kind") == "mach-o-load-command-relocation"
            and _mapping_or_empty(transformation.get("source")).get("sha256")
            == source.get("sha256")
            and _mapping_or_empty(transformation.get("output")).get("sha256")
            == pre_sign.get("sha256")
            and bool(transformation.get("changes"))
        )
        if not (
            manifest_files.get(source.get("path"), {}).get("sha256")
            == source.get("sha256")
            and pre_sign_is_derived
            and final.get("path") == pre_sign.get("path")
            and pre_sign.get("signing_identity")
            and final.get("signing_identity")
        ):
            return False
    return derivation.get("schema_version") == 1 and derivation.get("target") == target


def validate_r_delivery_identity(
    app_root: Path,
    runtime_probe: dict[str, object],
    *,
    target: str,
    architecture: str,
    source_commit: str,
) -> dict[str, object]:
    """Validate one, and only one, packaged R delivery identity."""
    marker_path = app_root / DIRECT_R_MARKER_RELATIVE
    marker_present = marker_path.is_file()
    probe_r = _mapping_or_empty(runtime_probe.get("r"))
    probe_rpy2 = _mapping_or_empty(runtime_probe.get("rpy2"))
    probe_direct = probe_r.get("direct_spike") is True
    kit_root = app_root / "Contents" / "Resources" / "r-integration-kit"
    kit_manifest_path = kit_root / "manifest.json"
    derivation_path = kit_root / "derivation.json"

    if marker_present != probe_direct:
        raise MacOSDeploymentInspectionError(
            "direct R spike marker and frozen runtime probe disagree"
        )

    if probe_direct:
        if kit_root.exists():
            raise MacOSDeploymentInspectionError(
                "deployment mixes direct R spike and integration-kit identities"
            )
        marker_sha256 = sha256_file(marker_path)
        if marker_sha256 != DIRECT_R_MARKER_SHA256:
            raise MacOSDeploymentInspectionError(
                "direct R spike marker differs from the non-release marker"
            )
        return {
            "direct_r_build": {
                "kind": "target-native-macos-r",
                "source_commit": source_commit,
                "runtime_probe_sha256": _canonical_json_sha256(runtime_probe),
                "marker": {
                    "path": DIRECT_R_MARKER_RELATIVE.as_posix(),
                    "sha256": marker_sha256,
                },
                "official_r": DIRECT_R_OFFICIAL_INPUTS[target],
                "ppm_snapshot": DIRECT_R_PPM_SNAPSHOT,
            }
        }

    try:
        kit_manifest = _mapping_or_empty(
            json.loads(kit_manifest_path.read_text(encoding="utf-8"))
        )
        derivation = _mapping_or_empty(
            json.loads(derivation_path.read_text(encoding="utf-8"))
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise MacOSDeploymentInspectionError(
            "macOS deployment lacks its R integration-kit manifest"
        ) from exc
    if not (
        kit_manifest.get("kind") == "rc-metastudio-r-integration-kit"
        and kit_manifest.get("target") == target
        and kit_manifest.get("architecture") == architecture
        and kit_manifest.get("cffi_mode") == "API"
        and len(str(kit_manifest.get("kit_sha256", ""))) == 64
        and derivation.get("kit_sha256") == kit_manifest.get("kit_sha256")
        and derivation.get("target") == target
        and _valid_r_kit_derivation(kit_manifest, derivation, target)
        and _mapping_or_empty(_mapping_or_empty(derivation.get("final")).get("api_bridge")).get("sha256")
        == probe_rpy2.get("api_bridge_sha256")
        and _mapping_or_empty(_mapping_or_empty(derivation.get("final")).get("r_shared_library")).get("sha256")
        == probe_r.get("shared_library_sha256")
    ):
        raise MacOSDeploymentInspectionError(
            "macOS R integration-kit identity is invalid"
        )
    return {
        "r_integration_kit": {
            "path": "Contents/Resources/r-integration-kit/manifest.json",
            "sha256": sha256_file(kit_manifest_path),
            "kit_sha256": kit_manifest["kit_sha256"],
            "derivation_sha256": sha256_file(derivation_path),
        }
    }


def validate_archive_root_name(value: str) -> str:
    if (
        not value
        or value in {".", ".."}
        or value[-1:] in {" ", "."}
        or unicodedata.normalize("NFC", value) != value
        or any(char in PORTABLE_FORBIDDEN or ord(char) < 32 for char in value)
        or value.split(".", 1)[0].casefold()
        in {
            "con",
            "prn",
            "aux",
            "nul",
            *(f"com{i}" for i in range(1, 10)),
            *(f"lpt{i}" for i in range(1, 10)),
        }
    ):
        raise MacOSDeploymentInspectionError(
            f"archive root must be one portable directory name: {value!r}"
        )
    return value


def macho_architectures(path: Path) -> list[str]:
    try:
        return architectures(path)
    except MachOError as exc:
        raise MacOSDeploymentInspectionError(str(exc)) from exc


def require_macho_architecture(path: Path, architecture: str) -> list[str]:
    architectures = macho_architectures(path)
    if architectures != [architecture]:
        raise MacOSDeploymentInspectionError(
            f"Mach-O payload must be {architecture}-only: {path} ({architectures})"
        )
    return architectures


def _is_macho(path: Path) -> bool:
    try:
        return is_macho_candidate(path)
    except OSError as exc:
        raise MacOSDeploymentInspectionError(
            f"cannot classify packaged native payload {path}: {exc}"
        ) from exc


def _resolved_inside(path: Path, root: Path) -> Path:
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise MacOSDeploymentInspectionError(
            f"packaged symlink escapes the app bundle: {path}"
        ) from exc
    return resolved


def _relative(path: Path, root: Path) -> str:
    value = path.relative_to(root).as_posix()
    if (
        not value
        or "\\" in value
        or "\0" in value
        or unicodedata.normalize("NFC", value) != value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise MacOSDeploymentInspectionError(f"non-canonical deployment path: {value}")
    return value


def _dependencies(path: Path) -> list[str]:
    if sys.platform != "darwin":
        return []
    completed = subprocess.run(
        ["otool", "-L", str(path)], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise MacOSDeploymentInspectionError(
            f"otool could not inspect {path}: {completed.stderr.strip()}"
        )
    dependencies = [
        line.strip().split(" (", 1)[0] for line in completed.stdout.splitlines()[1:]
    ]
    for dependency in dependencies:
        if dependency.startswith("/") and not dependency.startswith(
            ("/usr/lib/", "/System/Library/")
        ):
            raise MacOSDeploymentInspectionError(
                f"Mach-O payload retains a non-system absolute dependency: {path}: {dependency}"
            )
    return dependencies


def _minimum_macos_from_load_commands(output: str) -> str | None:
    command = None
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line.startswith("cmd "):
            command = line.split(None, 1)[1]
        elif command == "LC_BUILD_VERSION" and line.startswith("minos "):
            return line.split(None, 1)[1]
        elif command == "LC_VERSION_MIN_MACOSX" and line.startswith("version "):
            return line.split(None, 1)[1]
    return None


def _macho_load_metadata(path: Path) -> dict:
    if sys.platform != "darwin":
        return {
            "install_id": None,
            "rpaths": [],
            "uuid": None,
            "text_section_sha256": None,
            "minimum_macos": None,
        }
    completed = subprocess.run(
        ["otool", "-l", str(path)], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise MacOSDeploymentInspectionError(
            f"otool could not read Mach-O load commands for {path}"
        )
    command = None
    install_id = None
    rpaths: list[str] = []
    uuid = None
    minimum_macos = _minimum_macos_from_load_commands(completed.stdout)
    sections: list[dict[str, str]] = []
    section: dict[str, str] | None = None
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if line.startswith("Load command ") and section is not None:
            sections.append(section)
            section = None
        if line == "Section":
            if section is not None:
                sections.append(section)
            section = {}
            continue
        if section is not None and line.startswith(
            ("sectname ", "segname ", "size ", "offset ")
        ):
            key, value = line.split(None, 1)
            section[key] = value
        if line.startswith("cmd "):
            command = line.split(None, 1)[1]
        elif command == "LC_ID_DYLIB" and line.startswith("name "):
            install_id = line[5:].split(" (offset ", 1)[0]
        elif command == "LC_RPATH" and line.startswith("path "):
            rpaths.append(line[5:].split(" (offset ", 1)[0])
        elif command == "LC_UUID" and line.startswith("uuid "):
            uuid = line.split(None, 1)[1].lower()
    if section is not None:
        sections.append(section)
    text_sections = [
        item
        for item in sections
        if item.get("sectname") == "__text" and item.get("segname") == "__TEXT"
    ]
    if len(text_sections) != 1:
        raise MacOSDeploymentInspectionError(
            f"Mach-O payload has no unique __TEXT,__text section: {path}"
        )
    text_section = text_sections[0]
    try:
        offset = int(text_section["offset"], 0)
        size = int(text_section["size"], 0)
        with path.open("rb") as stream:
            stream.seek(offset)
            payload = stream.read(size)
    except (KeyError, OSError, ValueError) as exc:
        raise MacOSDeploymentInspectionError(
            f"cannot hash Mach-O __TEXT,__text section: {path}"
        ) from exc
    if len(payload) != size or size <= 0:
        raise MacOSDeploymentInspectionError(
            f"Mach-O __TEXT,__text section is empty or truncated: {path}"
        )
    return {
        "install_id": install_id,
        "rpaths": sorted(set(rpaths)),
        "uuid": uuid,
        "minimum_macos": minimum_macos,
        "text_section_sha256": hashlib.sha256(payload).hexdigest(),
    }


def _resolve_token_base(
    value: str, *, loader: Path, executable_dir: Path
) -> Path | None:
    if value == "@loader_path":
        return loader
    if value.startswith("@loader_path/"):
        return loader / value[len("@loader_path/") :]
    if value == "@executable_path":
        return executable_dir
    if value.startswith("@executable_path/"):
        return executable_dir / value[len("@executable_path/") :]
    if value.startswith("/"):
        return Path(value)
    return None


def validate_dependency_graph(
    native_records: list[dict],
    *,
    app_root: Path,
    executable_relative: str = "Contents/MacOS/RCMetaStudio",
    architecture: str = "arm64",
) -> None:
    root = app_root.resolve()
    executable_dir = (root / executable_relative).parent
    by_resolved, _ = _index_native_records(native_records, root)
    executable_records = [
        record
        for record in native_records
        if record.get("path") == executable_relative
    ]
    if len(executable_records) != 1:
        raise MacOSDeploymentInspectionError("dependency graph has no unique packaged executable")
    executable_rpaths = executable_records[0].get("rpaths", [])
    for record in native_records:
        _validate_record_dependencies(
            record,
            by_resolved,
            executable_dir,
            executable_rpaths,
            architecture,
            root,
        )


def _index_native_records(native_records: list[dict], root: Path):
    by_resolved: dict[Path, dict] = {}
    identities: dict[str, str] = {}
    for record in native_records:
        path = (root / record["path"]).resolve()
        if path in by_resolved:
            raise MacOSDeploymentInspectionError(
                f"duplicate native payload resolves to {path}"
            )
        by_resolved[path] = record
        identity = record.get("install_id")
        if identity:
            if identity in identities:
                raise MacOSDeploymentInspectionError(
                    f"duplicate Mach-O install identity {identity}: "
                    f"{identities[identity]}, {record['path']}"
                )
            identities[identity] = record["path"]
    return by_resolved, identities


def _validate_record_dependencies(
    record,
    by_resolved,
    executable_dir,
    executable_rpaths,
    architecture,
    root,
):
    loader = (root / record["path"]).resolve().parent
    for dependency in record.get("dependencies", []):
        _validate_record_dependency(
            record,
            dependency,
            by_resolved,
            executable_dir,
            executable_rpaths,
            architecture,
            loader,
        )


def _validate_record_dependency(
    record,
    dependency,
    by_resolved,
    executable_dir,
    executable_rpaths,
    architecture,
    loader,
):
    if dependency == record.get("install_id") or dependency.startswith(
        ("/usr/lib/", "/System/Library/")
    ):
        return
    candidates = _dependency_candidates(
        dependency, record, loader, executable_dir, executable_rpaths
    )
    matches = {path for path in candidates if path in by_resolved}
    if len(matches) != 1:
        raise MacOSDeploymentInspectionError(
            f"Mach-O dependency for {record['path']} does not resolve uniquely: "
            f"{dependency} ({sorted(str(path) for path in matches)})"
        )
    target = by_resolved[next(iter(matches))]
    if target.get("architectures") != [architecture]:
        raise MacOSDeploymentInspectionError(
            f"Mach-O dependency target is not {architecture}-only: {target['path']}"
        )


def _dependency_candidates(
    dependency, record, loader, executable_dir, executable_rpaths
):
    direct = _resolve_token_base(dependency, loader=loader, executable_dir=executable_dir)
    if direct is not None:
        return {direct.resolve()}
    if not dependency.startswith("@rpath/"):
        raise MacOSDeploymentInspectionError(f"unsupported Mach-O dependency token for {record['path']}: {dependency}")
    suffix = dependency[len("@rpath/") :]
    declarations = [
        *((rpath, loader) for rpath in record.get("rpaths", [])),
        *((rpath, executable_dir) for rpath in executable_rpaths),
    ]
    candidates = set()
    for rpath, declaring_loader in dict.fromkeys(declarations):
        base = _resolve_token_base(rpath, loader=declaring_loader, executable_dir=executable_dir)
        if base is not None:
            candidates.add((base / suffix).resolve())
    return candidates


def inspect_unsigned_native_graph(app_root: Path, *, target: str = "macos-arm64") -> dict:
    app_root = app_root.resolve(strict=True)
    architecture = TARGET_CONTRACTS[target]["architecture"]
    native_records = []
    for current, directories, filenames in os.walk(app_root, followlinks=False):
        current_path = Path(current)
        directories[:] = [
            name for name in directories if not (current_path / name).is_symlink()
        ]
        for name in filenames:
            path = current_path / name
            if path.is_symlink() or not _is_macho(path):
                continue
            record = {
                "path": _relative(path, app_root),
                "sha256": sha256_file(path),
                "architectures": require_macho_architecture(path, architecture),
                "dependencies": _dependencies(path),
                **_macho_load_metadata(path),
            }
            native_records.append(record)
    if not native_records:
        raise MacOSDeploymentInspectionError("unsigned app has no Mach-O payload")
    validate_dependency_graph(
        native_records, app_root=app_root, architecture=architecture
    )
    return {
        "schema_version": 1,
        "target": target,
        "architecture": architecture,
        "native_file_count": len(native_records),
        "native_files": sorted(native_records, key=lambda record: record["path"]),
    }


def validate_locked_qt_inventory(
    deployed_qt_records: list[dict],
    *,
    locked_qt_root: Path,
    architecture: str = "arm64",
) -> list[dict]:
    expected: list[dict] = []
    for deployed in deployed_qt_records:
        relative = deployed["qt_relative_path"]
        source = locked_qt_root / relative
        if not source.is_file() or not _is_macho(source):
            raise MacOSDeploymentInspectionError(
                f"deployed Qt native payload has no locked-wheel source: {relative}"
            )
        source_architectures = require_macho_architecture(source, architecture)
        source_metadata = _macho_load_metadata(source)
        if (
            source_architectures != deployed.get("architectures")
            or not source_metadata.get("uuid")
            or source_metadata.get("uuid") != deployed.get("uuid")
            or source_metadata.get("text_section_sha256")
            != deployed.get("text_section_sha256")
        ):
            raise MacOSDeploymentInspectionError(
                f"deployed Qt payload differs from the locked wheel identity: {relative}"
            )
        expected.append(
            {
                "path": relative,
                "source_sha256": sha256_file(source),
                "source_uuid": source_metadata["uuid"],
                "text_section_sha256": source_metadata["text_section_sha256"],
                "deployed_sha256": deployed["sha256"],
                "architectures": source_architectures,
            }
        )
    return sorted(expected, key=lambda item: item["path"])


def _canonical_json_sha256(value: object) -> str:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(payload).hexdigest()


def _codesign_observation(app_root: Path) -> dict:
    if sys.platform != "darwin":
        return {"verified": False, "runtime": False, "entitlements": {}}
    verified = subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", str(app_root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if verified.returncode != 0:
        raise MacOSDeploymentInspectionError(
            f"replaceable ad-hoc code signature verification failed: {verified.stderr}"
        )
    details = subprocess.run(
        ["codesign", "-d", "--verbose=4", str(app_root)],
        capture_output=True,
        text=True,
        check=False,
    )
    detail_text = details.stdout + details.stderr
    if details.returncode != 0:
        raise MacOSDeploymentInspectionError(
            "app bundle signature details are unreadable"
        )
    runtime = "runtime" in detail_text.lower()
    entitlements = subprocess.run(
        ["codesign", "-d", "--entitlements", ":-", str(app_root)],
        capture_output=True,
        check=False,
    )
    entitlement_payload = entitlements.stdout.strip()
    parsed_entitlements: dict = {}
    if entitlement_payload:
        try:
            parsed = plistlib.loads(entitlement_payload)
        except Exception as exc:
            raise MacOSDeploymentInspectionError(
                "app bundle entitlements are not a valid property list"
            ) from exc
        if not isinstance(parsed, dict):
            raise MacOSDeploymentInspectionError(
                "app bundle entitlements must be a dictionary"
            )
        parsed_entitlements = parsed
    if parsed_entitlements:
        raise MacOSDeploymentInspectionError(
            f"unreviewed hardened-runtime entitlements are present: {sorted(parsed_entitlements)}"
        )
    return {"verified": True, "runtime": runtime, "entitlements": {}}


def _normalize_runtime_path(value: object) -> Path:
    return Path(str(value)).resolve()


def _validate_python_probe(probe: dict, executable: Path, frameworks: Path, architecture: str) -> None:
    python = probe.get("python", {})
    if (
        probe.get("frozen") is not True
        or python.get("version") != EXPECTED_VERSIONS["python"]
        or str(python.get("architecture", "")).lower() != architecture
        or _normalize_runtime_path(python.get("executable")) != executable
        or _normalize_runtime_path(python.get("bundle_root")) != frameworks
    ):
        raise MacOSDeploymentInspectionError(
            "frozen Python probe does not match the app bundle"
        )


def _validate_qt_probe(probe: dict, frameworks: Path) -> None:
    qt = probe.get("qt", {})
    plugin_path = _normalize_runtime_path(qt.get("plugins_path"))
    library_paths = {
        _normalize_runtime_path(item) for item in qt.get("library_paths", [])
    }
    valid = _qt_probe_versions_ok(qt) and (
        _qt_probe_paths_ok(qt, plugin_path, library_paths, frameworks)
    )
    if not valid:
        raise MacOSDeploymentInspectionError(
            "frozen Qt probe does not match the Cocoa deployment"
        )


def _qt_probe_versions_ok(qt: dict) -> bool:
    return (
        qt.get("pyqt_version") == EXPECTED_VERSIONS["pyqt6"]
        and qt.get("compiled_qt_version") == "6.11.0"
        and qt.get("runtime_qt_version") == EXPECTED_VERSIONS["qt"]
        and qt.get("sip_runtime_version") == EXPECTED_VERSIONS["sip_runtime"]
        and qt.get("platform_plugin") == "cocoa"
    )


def _qt_probe_paths_ok(
    qt: dict, plugin_path: Path, library_paths: set[Path], frameworks: Path
) -> bool:
    return (
        plugin_path.is_relative_to(frameworks)
        and plugin_path in library_paths
        and qt.get("scale_factor_environment") is None
        and float(qt.get("baseline_device_pixel_ratio", 0)) > 0
        and float(qt.get("baseline_logical_dpi", 0)) > 0
    )


def _validate_rpy2_probe(probe: dict, frameworks: Path) -> None:
    rpy2 = probe.get("rpy2", {})
    expected = {
        "distribution_version": EXPECTED_VERSIONS["rpy2"],
        "cffi_mode": "API",
        "rinterface_distribution_version": "3.6.6",
        "robjects_distribution_version": "3.6.5",
        "loaded_cffi_mode": "API",
        "api_bridge_loaded": True,
    }
    observed = {key: rpy2.get(key) for key in expected}
    valid = observed == expected and _valid_sha256(rpy2.get("api_bridge_sha256"))
    valid = valid and _normalize_runtime_path(
        rpy2.get("api_bridge_path")
    ).is_relative_to(frameworks)
    if not valid:
        raise MacOSDeploymentInspectionError("frozen rpy2 probe differs from the lock")


def _validate_project_schema_probe(probe: dict) -> None:
    expected = {
        "version": 1,
        "validated_members": ["manifest.json", "project.json", "state.json"],
    }
    if probe.get("project_schemas") != expected:
        raise MacOSDeploymentInspectionError("frozen project schemas are incomplete")


def _validate_r_probe(probe: dict, app_root: Path, frameworks: Path) -> None:
    expected_r_home = app_root / "Contents/Frameworks/R.framework/Resources"
    expected_r_library = expected_r_home / "library"
    r = probe.get("r", {})
    r_libraries = {_normalize_runtime_path(item) for item in r.get("library_paths", [])}
    direct_spike = r.get("direct_spike") is True
    valid_identity = (
        r.get("kit_sha256") is None
        if direct_spike
        else _valid_sha256(r.get("kit_sha256"))
    )
    valid = _r_probe_versions_ok(r) and _r_probe_paths_ok(
        r, expected_r_home, expected_r_library, r_libraries, frameworks
    ) and valid_identity
    if not valid:
        raise MacOSDeploymentInspectionError(
            "frozen R probe does not use the bundled runtime"
        )
    _validate_r_product_profile(r)


def _r_probe_versions_ok(r: dict) -> bool:
    return (
        r.get("version") == EXPECTED_VERSIONS["r"]
        and r.get("lc_numeric") == "C"
        and _valid_sha256(r.get("shared_library_sha256"))
    )


def _r_probe_paths_ok(
    r: dict, expected_r_home: Path, expected_r_library: Path,
    r_libraries: set[Path], frameworks: Path
) -> bool:
    return (
        _normalize_runtime_path(r.get("home")) == expected_r_home.resolve()
        and
        _normalize_runtime_path(r.get("configured_home")) == expected_r_home.resolve()
        and _normalize_runtime_path(r.get("configured_library"))
        == expected_r_library.resolve()
        and expected_r_library.resolve() in r_libraries
        and _normalize_runtime_path(r.get("shared_library_path")).is_relative_to(
            frameworks
        )
    )


def _validate_r_product_profile(r: dict) -> None:
    policy = r.get("macos_product_profile")
    png = policy.get("default_png", {}) if isinstance(policy, dict) else {}
    valid = _r_profile_flags_ok(policy, png) and _r_profile_png_ok(png)
    if not valid:
        raise MacOSDeploymentInspectionError(
            "frozen R probe lacks the macOS Quartz product-profile evidence"
        )


def _r_profile_flags_ok(policy: object, png: dict[str, object]) -> bool:
    size = png.get("size")
    return (
        _string_keyed_dict(policy)
        and policy.get("tcltk_available") is False
        and policy.get("tcltk_loaded") is False
        and policy.get("aqua") is True
        and policy.get("bitmap_type") == "quartz"
        and isinstance(size, int)
        and size > 0
    )


def _r_profile_png_ok(png: dict[str, object]) -> bool:
    return _valid_sha256(png.get("sha256"))


def _validate_runtime_probe(
    probe: dict, app_root: Path, *, architecture: str = "arm64"
) -> None:
    executable = app_root / "Contents/MacOS/RCMetaStudio"
    frameworks = app_root / "Contents/Frameworks"
    _validate_python_probe(probe, executable, frameworks, architecture)
    _validate_qt_probe(probe, frameworks)
    _validate_rpy2_probe(probe, frameworks)
    _validate_project_schema_probe(probe)
    _validate_r_probe(probe, app_root, frameworks)


def validate_signing_inventory(
    inventory: object, *, native_paths: set[str], app_root: Path | None = None
) -> dict:
    if not isinstance(inventory, dict):
        raise MacOSDeploymentInspectionError("signing inventory must be an object")
    typed_inventory = cast(dict[str, object], inventory)
    expected_keys = {
        "schema_version",
        "app",
        "identity",
        "native_files",
        "nested_bundles",
        "verification",
    }
    native_files = typed_inventory.get("native_files")
    nested_bundles = _strings_or_empty(typed_inventory.get("nested_bundles"))
    verification = typed_inventory.get("verification")
    if (
        set(typed_inventory) != expected_keys
        or typed_inventory.get("schema_version") != 1
        or typed_inventory.get("app") != "RCMetaStudio.app"
        or typed_inventory.get("identity") != "ad-hoc"
        or not isinstance(native_files, list)
        or not all(isinstance(item, str) for item in native_files)
        or len(native_files) != len(set(native_files))
        or set(native_files) != native_paths
        or len(nested_bundles) != len(set(nested_bundles))
        or verification != {"individual_strict": True, "outer_deep_strict": True}
    ):
        raise MacOSDeploymentInspectionError(
            "signing inventory differs from the authoritative native deployment"
        )
    for relative in nested_bundles:
        path = Path(relative)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise MacOSDeploymentInspectionError(
                "signing inventory has an unsafe bundle path"
            )
        if app_root is not None and not (app_root / path).is_dir():
            raise MacOSDeploymentInspectionError(
                "signing inventory names a missing bundle"
            )
    return typed_inventory


def validate_r_framework_inventory(
    records: object, *, delivery_kind: str, architecture: str
) -> None:
    """Require the canonical, concrete R framework payload and alias topology."""
    if delivery_kind not in {"integration-kit", "direct-spike"}:
        raise MacOSDeploymentInspectionError("R framework delivery kind is invalid")
    if not isinstance(records, list) or not all(
        isinstance(item, dict) for item in records
    ):
        raise MacOSDeploymentInspectionError(
            "R framework inventory is not a record list"
        )
    typed_records = cast(list[dict[str, object]], records)
    by_path = {record.get("path"): record for record in typed_records}
    framework = "Contents/Frameworks/R.framework"
    if delivery_kind == "direct-spike":
        current_record = by_path.get(f"{framework}/Versions/Current", {})
        framework_version = current_record.get("link_target")
        if (
            not isinstance(framework_version, str)
            or framework_version in {"", ".", ".."}
            or "/" in framework_version
            or "\\" in framework_version
        ):
            raise MacOSDeploymentInspectionError(
                "official R framework Versions/Current target is invalid"
            )
    else:
        try:
            framework_version = macos_r_framework_version(EXPECTED_VERSIONS["r"])
        except ValueError as exc:
            raise MacOSDeploymentInspectionError(
                "locked R version cannot name its framework"
            ) from exc
    version_root = f"{framework}/Versions/{framework_version}"
    resources = f"{version_root}/Resources"
    required_files = {
        f"{resources}/bin/Rscript",
        f"{resources}/library/RCMetaR/DESCRIPTION",
        f"{resources}/Info.plist",
    }
    native_paths = [f"{version_root}/R"]
    if delivery_kind == "direct-spike":
        native_paths.extend(
            [f"{resources}/bin/Rscript.real", f"{resources}/bin/exec/R"]
        )
    if delivery_kind == "direct-spike":
        launcher = by_path.get(f"{resources}/bin/R", {})
        if (
            launcher.get("kind") != "file"
            or "architectures" in launcher
            or not _int_or_default(launcher.get("mode"), 0) & 0o111
            or launcher.get("shebang") != "#!/bin/sh"
        ):
            raise MacOSDeploymentInspectionError(
                "official R framework bin/R is not its executable shell front-end"
            )
    required_files.update(native_paths)
    for path in required_files:
        if by_path.get(path, {}).get("kind") != "file":
            raise MacOSDeploymentInspectionError(
                f"R framework is missing its concrete versioned member: {path}"
            )
    for native_path in native_paths:
        r_executable = by_path[native_path]
        if (
            r_executable.get("architectures") != [architecture]
            or not _int_or_default(r_executable.get("mode"), 0) & 0o111
        ):
            raise MacOSDeploymentInspectionError(
                "R framework native executable target is not in the Mach-O inventory"
            )
    expected_links: dict[str, tuple[str, str]] = {
        f"{framework}/Versions/Current": (
            framework_version,
            version_root,
        ),
        f"{framework}/Resources": (
            "Versions/Current/Resources",
            resources,
        ),
    }
    if delivery_kind == "direct-spike":
        expected_links.update(
            {
                f"{framework}/R": (
                    "Versions/Current/R",
                    f"{version_root}/R",
                ),
                f"{resources}/R": (
                    "bin/R",
                    f"{resources}/bin/R",
                ),
                f"{resources}/lib/libR.dylib": (
                    "../../R",
                    f"{version_root}/R",
                ),
            }
        )
    else:
        expected_links[f"{framework}/R"] = (
            "Versions/Current/R",
            f"{version_root}/R",
        )
        expected_links[f"{resources}/lib/libR.dylib"] = (
            "../../R",
            f"{version_root}/R",
        )
    for path, (target, resolved) in expected_links.items():
        record = by_path.get(path, {})
        if (
            record.get("kind") != "symlink"
            or record.get("link_target") != target
            or record.get("resolved_path") != resolved
        ):
            raise MacOSDeploymentInspectionError(
                f"R framework alias is missing or noncanonical: {path}"
            )


def validate_rpy2_api_payload(records: object) -> None:
    """Require the API bridge and reject all ABI-mode fallback payloads."""
    if not isinstance(records, list) or not all(
        isinstance(item, dict) for item in records
    ):
        raise MacOSDeploymentInspectionError("rpy2 inventory is not a record list")
    typed_records = cast(list[dict[str, object]], records)
    if _has_abi_bridge(typed_records):
        raise MacOSDeploymentInspectionError(
            "deployment contains the forbidden rpy2 ABI-mode fallback bridge"
        )
    api_native = _matching_rpy2_records(typed_records, "_rinterface_cffi_api")
    if len(api_native) != 1:
        raise MacOSDeploymentInspectionError(
            "deployment must contain exactly one rpy2 API-mode bridge"
        )
    api_support = _matching_rpy2_records(
        typed_records, "/rpy2/rinterface_lib/_bufferprotocol"
    )
    if len(api_support) != 1:
        raise MacOSDeploymentInspectionError(
            "deployment must contain exactly one rpy2 API bridge support extension"
        )


def _has_abi_bridge(records: list[dict[str, object]]) -> bool:
    return any(
        "_rinterface_cffi_abi" in str(record.get("path", "")).lower()
        for record in records
    )


def _matching_rpy2_records(
    records: list[dict[str, object]], marker: str
) -> list[dict[str, object]]:
    return [
        record
        for record in records
        if "architectures" in record
        and marker in str(record.get("path", "")).lower()
    ]


def _validate_deployment_contract(
    app_root: Path,
    versions: dict[str, str],
    source_commit: str,
    minimum_macos: str,
) -> tuple[dict, Path]:
    if versions != EXPECTED_VERSIONS:
        raise MacOSDeploymentInspectionError(f"locked stack mismatch: {versions}")
    if not _valid_source_commit(source_commit):
        raise MacOSDeploymentInspectionError(
            "source commit must be a full lowercase Git SHA"
        )
    info_path = app_root / "Contents/Info.plist"
    executable = app_root / "Contents/MacOS/RCMetaStudio"
    if not info_path.is_file() or not executable.is_file():
        raise MacOSDeploymentInspectionError(
            "app bundle is missing Info.plist or CFBundleExecutable"
        )
    with info_path.open("rb") as stream:
        info = plistlib.load(stream)
    if not _valid_bundle_info(info, minimum_macos):
        raise MacOSDeploymentInspectionError(
            f"Info.plist is not the qualified macOS {minimum_macos} bundle contract"
        )
    return info, executable


def _valid_source_commit(source_commit: str) -> bool:
    return len(source_commit) == 40 and all(
        char in "0123456789abcdef" for char in source_commit
    )


def _valid_bundle_info(info: dict, minimum_macos: str) -> bool:
    return (
        info.get("CFBundleExecutable") == "RCMetaStudio"
        and info.get("CFBundleIdentifier") == "org.researchconsultancy.rc-metastudio"
        and info.get("LSMinimumSystemVersion") == minimum_macos
        and info.get("NSHighResolutionCapable") is True
    )


def _inventory_symlink(path: Path, app_root: Path) -> dict:
    resolved = _resolved_inside(path, app_root)
    stat_result = path.lstat()
    return {
        "path": _relative(path, app_root),
        "kind": "symlink",
        "size": stat_result.st_size,
        "mode": stat.S_IMODE(stat_result.st_mode),
        "link_target": os.readlink(path),
        "resolved_path": _relative(resolved, app_root),
    }


def _inventory_file(
    path: Path,
    app_root: Path,
    architecture: str,
    minimum_macos: str,
    r_delivery_kind: str,
) -> tuple[dict, bool]:
    record = {
        "path": _relative(path, app_root),
        "kind": "file",
        "size": path.stat().st_size,
        "mode": stat.S_IMODE(path.stat().st_mode),
        "sha256": sha256_file(path),
    }
    direct_r_launcher = (
        app_root / "Contents/Frameworks/R.framework/Resources/bin/R"
    )
    if r_delivery_kind == "direct-spike" and path.resolve() == direct_r_launcher.resolve():
        with path.open("rb") as stream:
            record["shebang"] = (
                stream.readline(128).decode("ascii", errors="replace").rstrip()
            )
    if not _is_macho(path):
        return record, False
    record["architectures"] = require_macho_architecture(path, architecture)
    record["dependencies"] = _dependencies(path)
    record.update(_macho_load_metadata(path))
    minimum = record.get("minimum_macos")
    if minimum is None or _macos_version(str(minimum)) > _macos_version(minimum_macos):
        raise MacOSDeploymentInspectionError(
            f"Mach-O deployment target exceeds {minimum_macos}: "
            f"{record['path']}={minimum}"
        )
    return record, True


def _collect_deployment_inventory(
    app_root: Path,
    architecture: str,
    minimum_macos: str,
    r_delivery_kind: str,
) -> tuple[list[dict], list[dict], int]:
    records: list[dict] = []
    native_records: list[dict] = []
    folded: dict[str, str] = {}
    total_bytes = 0
    for current, directories, filenames in os.walk(app_root, followlinks=False):
        directory_records, directory_bytes = _inventory_directory(
            Path(current), directories, filenames, app_root, architecture,
            minimum_macos, r_delivery_kind, folded,
        )
        records.extend(directory_records)
        native_records.extend(
            record for record in directory_records if "architectures" in record
        )
        total_bytes += directory_bytes
        if len(records) > MAX_FILES or total_bytes > MAX_BYTES:
            raise MacOSDeploymentInspectionError(
                "deployment exceeds its bounded inventory"
            )
    return records, native_records, total_bytes


def _inventory_directory(
    current_path: Path,
    directories: list[str],
    filenames: list[str],
    app_root: Path,
    architecture: str,
    minimum_macos: str,
    r_delivery_kind: str,
    folded: dict[str, str],
) -> tuple[list[dict], int]:
    records: list[dict] = []
    total_bytes = 0
    for name in list(directories):
        path = current_path / name
        if path.is_symlink():
            directories.remove(name)
            record = _inventory_symlink(path, app_root)
            records.append(record)
            total_bytes += record["size"]
    for name in filenames:
        path = current_path / name
        relative = _relative(path, app_root)
        key = relative.casefold()
        if key in folded:
            raise MacOSDeploymentInspectionError(
                "deployment contains duplicate/case-colliding paths: "
                f"{folded[key]}, {relative}"
            )
        folded[key] = relative
        if path.is_symlink():
            record = _inventory_symlink(path, app_root)
            is_native = False
        else:
            record, is_native = _inventory_file(
                path, app_root, architecture, minimum_macos, r_delivery_kind
            )
        records.append(record)
        total_bytes += record["size"]
    return records, total_bytes


def _validate_qt_root_locations(native_records: list[dict], qt_root: str) -> None:
    for record in native_records:
        path = record["path"]
        lowered = path.lower()
        if _is_qt_payload_path(lowered, path) and not path.startswith(qt_root + "/"):
            raise MacOSDeploymentInspectionError(
                f"deployment contains a second or displaced Qt payload: {path}"
            )


def _is_qt_payload_path(lowered: str, path: str) -> bool:
    return (
        "/pyqt6/qt6/" in lowered
        or (".framework/versions/" in lowered and "/qt" in lowered)
        or ("/plugins/" in lowered and Path(path).name.lower().startswith("libq"))
        or Path(path).name.lower().startswith("libqt6")
    )


def _validate_qt_deployment(
    records: list[dict],
    native_records: list[dict],
    r_delivery_kind: str,
    architecture: str,
) -> tuple[str, dict[str, str], list[str]]:
    lowered_paths = [record["path"].lower() for record in records]
    validate_r_framework_inventory(
        records, delivery_kind=r_delivery_kind, architecture=architecture
    )
    validate_rpy2_api_payload(records)
    if any(
        any(
            token in path
            for token in ("pyqt5", "pyside2", "pyside6", "shiboken6", "qt5")
        )
        for path in lowered_paths
    ):
        raise MacOSDeploymentInspectionError(
            "deployment contains a legacy or alternate Qt binding"
        )
    plugin_paths, tls_plugins = _find_qt_plugins(native_records)
    qt_roots = {
        path.split("/plugins/", 1)[0]
        for path in [*plugin_paths.values(), *tls_plugins]
    }
    if len(qt_roots) != 1 or not next(iter(qt_roots)).endswith("/PyQt6/Qt6"):
        raise MacOSDeploymentInspectionError(
            "deployment does not have one authoritative PyQt6 Qt root"
        )
    qt_root = next(iter(qt_roots))
    _validate_qt_root_locations(native_records, qt_root)
    return qt_root, plugin_paths, tls_plugins


def _find_qt_plugins(
    native_records: list[dict],
) -> tuple[dict[str, str], list[str]]:
    required_plugins = {
        "cocoa": "/plugins/platforms/libqcocoa.dylib",
        "jpeg": "/plugins/imageformats/libqjpeg.dylib",
        "svg_image": "/plugins/imageformats/libqsvg.dylib",
        "svg_icon": "/plugins/iconengines/libqsvgicon.dylib",
    }
    plugin_paths: dict[str, str] = {}
    for label, suffix in required_plugins.items():
        matches = [record["path"] for record in native_records if _plugin_matches(record, suffix)]
        if len(matches) != 1:
            raise MacOSDeploymentInspectionError(
                f"required {label} Qt plugin count is {len(matches)}, expected one"
            )
        plugin_paths[label] = matches[0]
    tls_plugins = [
        record["path"]
        for record in native_records
        if _is_tls_plugin(record)
    ]
    if not tls_plugins:
        raise MacOSDeploymentInspectionError("deployment contains no Qt TLS plugin")
    return plugin_paths, tls_plugins


def _plugin_matches(record: dict, suffix: str) -> bool:
    return record["path"].lower().endswith(suffix)


def _is_tls_plugin(record: dict) -> bool:
    path = record["path"].lower()
    return "/plugins/tls/" in path and path.endswith(".dylib")


def _deployment_result(
    records: list[dict],
    native_records: list[dict],
    total_bytes: int,
    target: str,
    source_commit: str,
    minimum_macos: str,
    versions: dict[str, str],
    r_delivery_identity: dict,
    qt_root: str,
    plugin_paths: dict[str, str],
    tls_plugins: list[str],
    locked_qt_inventory: list[dict],
    runtime_probe: dict,
    signing_inventory_path: Path,
    signing_inventory: dict,
    codesign: dict,
) -> dict:
    records.sort(key=lambda item: item["path"])
    return {
        "schema_version": 1,
        "target": target,
        "source_commit": source_commit,
        "minimum_macos": minimum_macos,
        "stack": versions,
        **r_delivery_identity,
        "qt_dependency_collector": "PyInstaller",
        "architecture": TARGET_CONTRACTS[target]["architecture"],
        "app_bundle": {
            "bundle_identifier": "org.researchconsultancy.rc-metastudio",
            "executable": "Contents/MacOS/RCMetaStudio",
            "normal_entry_point": True,
            "codesign": codesign,
            "hardened_runtime_signing_compatible": (
                codesign["verified"] and not codesign["entitlements"]
            ),
        },
        "qt": {
            "root": qt_root,
            "plugins": plugin_paths,
            "tls_plugins": sorted(tls_plugins),
            "locked_native_inventory": locked_qt_inventory,
        },
        "runtime_probe_canonical_sha256": _canonical_json_sha256(runtime_probe),
        "signing_inventory": {
            "path": "qualification/ad-hoc-signing-inventory.json",
            "sha256": sha256_file(signing_inventory_path),
            "identity": signing_inventory["identity"],
            "native_files": signing_inventory["native_files"],
            "nested_bundles": signing_inventory["nested_bundles"],
        },
        "inventory": {
            "file_count": len(records),
            "total_bytes": total_bytes,
            "native_file_count": len(native_records),
            "files": records,
        },
    }


def inspect_deployment(
    app_root: Path,
    *,
    versions: dict[str, str],
    source_commit: str,
    runtime_probe: dict,
    locked_qt_root: Path,
    signing_inventory_path: Path,
    target: str = "macos-arm64",
) -> dict:
    app_root = app_root.resolve()
    contract = TARGET_CONTRACTS[target]
    architecture = contract["architecture"]
    minimum_macos = contract["minimum_macos"]
    info, executable = _validate_deployment_contract(
        app_root, versions, source_commit, minimum_macos
    )
    _validate_runtime_probe(runtime_probe, app_root, architecture=architecture)
    r_delivery_identity = validate_r_delivery_identity(
        app_root,
        runtime_probe,
        target=target,
        architecture=architecture,
        source_commit=source_commit,
    )
    r_delivery_kind = (
        "direct-spike"
        if "direct_r_build" in r_delivery_identity
        else "integration-kit"
    )
    records, native_records, total_bytes = _collect_deployment_inventory(
        app_root, architecture, minimum_macos, r_delivery_kind
    )
    qt_root, plugin_paths, tls_plugins = _validate_qt_deployment(
        records, native_records, r_delivery_kind, architecture
    )
    if not native_records or require_macho_architecture(executable, architecture) != [
        architecture
    ]:
        raise MacOSDeploymentInspectionError(
            "deployment has no qualified native executable"
        )
    validate_dependency_graph(
        native_records, app_root=app_root, architecture=architecture
    )
    deployed_qt_records = [
        {**record, "qt_relative_path": record["path"][len(qt_root) + 1 :]}
        for record in native_records
        if record["path"].startswith(qt_root + "/")
    ]
    locked_qt_inventory = validate_locked_qt_inventory(
        deployed_qt_records,
        locked_qt_root=locked_qt_root.resolve(),
        architecture=architecture,
    )
    codesign = _codesign_observation(app_root)
    signing_inventory = validate_signing_inventory(
        json.loads(signing_inventory_path.read_text(encoding="utf-8")),
        native_paths={record["path"] for record in native_records},
        app_root=app_root,
    )
    return _deployment_result(
        records,
        native_records,
        total_bytes,
        target,
        source_commit,
        minimum_macos,
        versions,
        r_delivery_identity,
        qt_root,
        plugin_paths,
        tls_plugins,
        locked_qt_inventory,
        runtime_probe,
        signing_inventory_path,
        signing_inventory,
        codesign,
    )


def finalize_smoke_evidence(
    path: Path,
    log_path: Path,
    launchservices_marker: Path | None = None,
    *,
    require_direct_teardown: bool = False,
    persist: bool = True,
) -> dict:
    evidence = json.loads(path.read_text(encoding="utf-8"))
    log_text = log_path.read_text(encoding="utf-8")
    _validate_smoke_basics(evidence, log_text)
    _validate_launchservices_marker(launchservices_marker)
    validate_packaged_workflow_evidence(evidence)
    _validate_teardown_trace(log_text, require_direct_teardown)
    scale_records = evidence.get("scales", [])
    executed_scales = [
        str(record.get("requested"))
        for record in scale_records
        if isinstance(record, dict)
    ]
    if require_direct_teardown:
        validate_macos_surface_records(scale_records)
    _validate_surface_gate(executed_scales, launchservices_marker, require_direct_teardown)
    evidence["execution"] = {
        "automation_exit_code": 0,
        "surface_scale_exit_codes": {scale: 0 for scale in executed_scales},
        "post_close_marker": True,
        "launchservices_completion_marker": launchservices_marker is not None,
        "clean_exit": True,
        "direct_teardown_trace": require_direct_teardown,
    }
    if persist:
        path.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return evidence


def _validate_smoke_basics(evidence: dict, log_text: str) -> None:
    if evidence.get("failures") or evidence.get("surface_progress"):
        raise MacOSDeploymentInspectionError(
            "packaged automation contains failed native observations"
        )
    if "packaged-workflow:post-close" not in log_text:
        raise MacOSDeploymentInspectionError(
            "packaged automation did not emit its post-close marker"
        )


def _validate_launchservices_marker(marker_path: Path | None) -> None:
    if marker_path is None:
        return
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    valid = (
        marker.get("schema_version") == 1
        and marker.get("platform_plugin") == "cocoa"
        and marker.get("project") == "BCG.rcms"
        and marker.get("post_close") is True
        and isinstance(marker.get("pid"), int)
    )
    if not valid:
        raise MacOSDeploymentInspectionError(
            "normal LaunchServices app entry did not produce its completion marker"
        )


def _validate_teardown_trace(log_text: str, required: bool) -> None:
    if not required:
        return
    markers = (
        "packaged-workflow:teardown:close:start",
        "packaged-workflow:teardown:close:return",
        "packaged-workflow:teardown:deferred-delete:complete",
        "packaged-workflow:teardown:top-level-windows:none",
        "packaged-workflow:teardown:app-quit:start",
        "packaged-workflow:teardown:app-quit:return",
        "packaged-workflow:post-close",
        "packaged-workflow:return",
        "packaged-workflow:process-exit:0",
    )
    positions = [log_text.find(marker) for marker in markers]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        raise MacOSDeploymentInspectionError(
            "direct packaged automation lacks an ordered clean-teardown trace"
        )


def _validate_surface_gate(
    executed_scales: list[str], marker_path: Path | None, required: bool
) -> None:
    if required and (
        executed_scales != ["1.25", "1.50", "1.75"] or marker_path is None
    ):
        raise MacOSDeploymentInspectionError(
            "direct packaged automation lacks the required surface or LaunchServices gates"
        )


def validate_packaged_workflow_evidence(evidence: dict) -> None:
    workflows = evidence.get("workflows", {})
    locale_variants = workflows.get("locale_variants", [])
    sample_projects = workflows.get("sample_projects", {})
    sample_records = sample_projects.get("projects", [])
    expected_summary = EXPECTED_SUMMARY_SHA256_BY_SAMPLE.get(
        workflows.get("converted_sample")
    )
    valid = (
        _workflow_header_valid(evidence, workflows, expected_summary)
        and _workflow_locale_valid(workflows, locale_variants, expected_summary)
        and _workflow_samples_valid(sample_projects, sample_records)
    )
    if not valid:
        raise MacOSDeploymentInspectionError(
            "packaged workflow result evidence is incomplete"
        )


def _workflow_header_valid(
    evidence: dict, workflows: dict, expected_summary: str | None
) -> bool:
    required = (
        "automation_entry_point",
        "representative_edit",
        "real_r_analysis",
        "result_text",
        "save_reopen",
        "analysis_after_reopen",
    )
    return all(
        (
            evidence.get("passed") is True,
            not evidence.get("failures"),
            all(workflows.get(key) is True for key in required),
            workflows.get("converted_sample") == "BCG.rcms",
            expected_summary is not None,
            workflows.get("expected_normalized_summary_sha256") == expected_summary,
            workflows.get("normalized_summary_sha256") == expected_summary,
            _valid_sha256(workflows.get("raw_summary_sha256")),
            _valid_sha256_map(workflows.get("svg_sha256")),
        )
    )


def _workflow_locale_valid(
    workflows: dict, locale_variants: list, expected_summary: str | None
) -> bool:
    if [item.get("locale") for item in locale_variants] != ["en_US", "de_DE"]:
        return False
    return all(
        item.get("normalized_summary_sha256") == expected_summary
        and item.get("raw_summary_sha256") == workflows.get("raw_summary_sha256")
        for item in locale_variants
    )


def _workflow_samples_valid(sample_projects: dict, sample_records: object) -> bool:
    return _sample_manifest_valid(sample_projects) and _sample_records_valid(
        sample_records
    )


def _sample_manifest_valid(sample_projects: dict) -> bool:
    return sample_projects.get("passed") is True and _valid_sha256(
        sample_projects.get("manifest_sha256")
    )


def _sample_records_valid(sample_records: object) -> bool:
    if not isinstance(sample_records, list) or not sample_records:
        return False
    typed_records = _typed_sample_records(cast(list[object], sample_records))
    if typed_records is None:
        return False
    projects = {item.get("project") for item in typed_records}
    return len(projects) == len(typed_records) and all(
        _valid_sample_record(item) for item in typed_records
    )


def _typed_sample_records(
    sample_records: list[object],
) -> list[dict[str, object]] | None:
    typed_records: list[dict[str, object]] = []
    for item in sample_records:
        if not _string_keyed_dict(item):
            return None
        typed_records.append(item)
    return typed_records


def _valid_sample_record(item: object) -> bool:
    if not _string_keyed_dict(item):
        return False
    project = item.get("project")
    return (
        isinstance(project, str)
        and project.endswith(".rcms")
        and _valid_sha256(item.get("sha256"))
        and _valid_sha256(item.get("semantic_sha256"))
        and item.get("opened_in_packaged_application") is True
    )


def _validate_direct_manifest_identity(payload: dict, target: str) -> str:
    if not _valid_direct_manifest_header(payload, target):
        raise MacOSDeploymentInspectionError(
            "direct-build manifest has the wrong identity or target"
        )
    source_commit = payload.get("source_commit", "")
    valid_commit = (
        isinstance(source_commit, str)
        and len(source_commit) == 40
        and all(character in "0123456789abcdef" for character in source_commit)
    )
    if not valid_commit:
        raise MacOSDeploymentInspectionError(
            "direct-build manifest has an invalid source commit"
        )
    official_r = payload.get("official_r")
    if not _valid_direct_upstream(payload, official_r, target):
        raise MacOSDeploymentInspectionError(
            "direct-build manifest has invalid locked upstream inputs"
        )
    return source_commit


def _valid_direct_manifest_header(payload: dict, target: str) -> bool:
    return (
        payload.get("schema_version") == 1
        and payload.get("kind") == "rc-metastudio-direct-macos-target-build"
        and payload.get("target") == target
    )


def _valid_direct_upstream(payload: dict, official_r: object, target: str) -> bool:
    return (
        isinstance(official_r, dict)
        and official_r == DIRECT_R_OFFICIAL_INPUTS[target]
        and payload.get("ppm_snapshot") == DIRECT_R_PPM_SNAPSHOT
        and _valid_sha256(payload.get("rpy2_api_bridge_source_sha256"))
    )


def _validate_direct_input_inventory(payload: dict) -> tuple[dict, list[dict]]:
    inputs = payload.get("inputs")
    if not isinstance(inputs, dict) or set(inputs) != set(DIRECT_BUILD_INPUT_MEMBERS):
        raise MacOSDeploymentInspectionError(
            "direct-build manifest has no complete hashed input inventory"
        )
    ppm_archives = payload.get("ppm_archives")
    if not isinstance(ppm_archives, list) or not ppm_archives:
        raise MacOSDeploymentInspectionError(
            "direct-build manifest has no PPM archive inventory"
        )
    records = [*inputs.values(), *ppm_archives]
    for record in records:
        if not _valid_direct_record(record):
            raise MacOSDeploymentInspectionError(
                "direct-build manifest contains an invalid input record"
            )
    return inputs, ppm_archives


def _valid_direct_record(record: object) -> bool:
    if not _string_keyed_dict(record) or not _valid_sha256(record.get("sha256")):
        return False
    size = record.get("size")
    return isinstance(size, int) and not isinstance(size, bool) and size >= 0


def _validate_direct_ppm_records(ppm_archives: list[dict]) -> None:
    seen_paths: set[str] = set()
    for record in ppm_archives:
        _validate_one_ppm_record(record, seen_paths)


def _validate_one_ppm_record(record: dict, seen_paths: set[str]) -> None:
    path = record.get("path")
    if not _valid_ppm_path(path, seen_paths):
        raise MacOSDeploymentInspectionError(
            "direct-build manifest contains an invalid PPM archive path"
        )
    path = cast(str, path)
    seen_paths.add(path.casefold())
    if not _valid_ppm_metadata(
        record.get("package"),
        record.get("version"),
        record.get("archive_url"),
        path,
    ):
        raise MacOSDeploymentInspectionError(
            "direct-build PPM archive lacks package, version, or authoritative URL"
        )


def _valid_ppm_path(path: object, seen_paths: set[str]) -> bool:
    return (
        isinstance(path, str)
        and bool(path)
        and "\\" not in path
        and not path.startswith("/")
        and all(part not in {"", ".", ".."} for part in path.split("/"))
        and path.casefold() not in seen_paths
    )


def _valid_ppm_metadata(
    package: object, version: object, archive_url: object, path: str
) -> bool:
    return (
        isinstance(package, str)
        and bool(package)
        and isinstance(version, str)
        and bool(version)
        and isinstance(archive_url, str)
        and archive_url.startswith(DIRECT_R_PPM_SNAPSHOT + "/")
        and archive_url.endswith("/" + path)
    )


def _validate_rcmetar_provenance(payload: dict, source_commit: str, inputs: dict) -> None:
    rcmetar = payload.get("rcmetar_source")
    if not _valid_rcmetar_source(rcmetar, source_commit):
        raise MacOSDeploymentInspectionError(
            "direct-build manifest has invalid RCMetaR source provenance"
        )
    archive = rcmetar.get("archive")
    if not _valid_direct_archive_record(archive):
        raise MacOSDeploymentInspectionError(
            "direct-build manifest has an invalid source archive record"
        )
    if archive != inputs["rcmetar_source_archive"]:
        raise MacOSDeploymentInspectionError(
            "direct-build source archives differ from their embedded input records"
        )


def _valid_rcmetar_source(
    rcmetar: object, source_commit: str
) -> TypeGuard[dict[str, object]]:
    if not _string_keyed_dict(rcmetar):
        return False
    archive = rcmetar.get("archive")
    return (
        rcmetar.get("name") == "RCMetaR"
        and rcmetar.get("version") == "0.2.0"
        and rcmetar.get("url")
        == "https://github.com/ResearchConsultancy/rc-metastudio/tree/"
        + source_commit
        + "/r/RCMetaR"
        and rcmetar.get("source_commit") == source_commit
        and _valid_sha256(rcmetar.get("archive_sha256"))
        and _string_keyed_dict(archive)
        and archive.get("sha256") == rcmetar.get("archive_sha256")
    )


def _valid_direct_archive_record(archive: object) -> bool:
    if not _string_keyed_dict(archive):
        return False
    size = archive.get("size")
    return (
        _valid_sha256(archive.get("sha256"))
        and isinstance(size, int)
        and not isinstance(size, bool)
        and size > 0
    )


def validate_direct_build_manifest(payload: dict, *, target: str) -> dict:
    source_commit = _validate_direct_manifest_identity(payload, target)
    inputs, ppm_archives = _validate_direct_input_inventory(payload)
    _validate_direct_ppm_records(ppm_archives)
    _validate_rcmetar_provenance(payload, source_commit, inputs)
    return payload


def validate_direct_build_runner(runner: dict, *, target: str) -> None:
    architecture = TARGET_CONTRACTS[target]["architecture"]
    if not _is_native_runner(runner, architecture):
        raise MacOSDeploymentInspectionError(
            f"direct-build runner is not native {target}"
        )
    if runner.get("github_actions") == "true":
        _validate_hosted_runner(runner, target)
    elif runner.get("github_actions") not in ("false", False):
        raise MacOSDeploymentInspectionError(
            "direct-build runner has invalid github_actions state"
        )


def _is_native_runner(runner: dict, architecture: str) -> bool:
    required_fields = (
        ("schema_version", 1),
        ("runner_os", "macOS"),
        ("uname_system", "Darwin"),
        ("uname_machine", architecture),
        ("python_machine", architecture),
    )
    return all(
        runner.get(field) == expected for field, expected in required_fields
    ) and all(
        _non_empty_text(runner.get(field))
        for field in ("macos_version", "macos_build")
    )


def _non_empty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _validate_hosted_runner(runner: dict, target: str) -> None:
    expected = TARGET_RUNNERS[target]
    if (
        runner.get("runner_arch") != expected["architecture"]
        or runner.get("runner_label") != expected["label"]
        or not runner.get("runner_image")
    ):
        raise MacOSDeploymentInspectionError(
            f"hosted direct-build runner does not match {target}"
        )


def validate_direct_build_archive_inputs(
    bundle: zipfile.ZipFile,
    *,
    prefix: str,
    names: list[str],
    manifest: dict,
    target: str,
) -> None:
    _validate_archive_input_members(bundle, prefix, names, manifest)
    runner = _read_and_validate_archive_provenance(
        bundle, prefix, names, manifest, target
    )
    validate_direct_build_runner(runner, target=target)


def _validate_archive_input_members(
    bundle: zipfile.ZipFile, prefix: str, names: list[str], manifest: dict
) -> None:
    for label, relative in DIRECT_BUILD_INPUT_MEMBERS.items():
        member = prefix + relative
        if member not in names:
            raise MacOSDeploymentInspectionError(
                f"ZIP lacks direct-build input member: {member}"
            )
        payload = bundle.read(member)
        expected = manifest["inputs"][label]
        if (
            len(payload) != expected["size"]
            or hashlib.sha256(payload).hexdigest() != expected["sha256"]
        ):
            raise MacOSDeploymentInspectionError(
                f"ZIP direct-build input differs from its manifest: {member}"
            )


def _read_and_validate_archive_provenance(
    bundle: zipfile.ZipFile,
    prefix: str,
    names: list[str],
    manifest: dict,
    target: str,
) -> dict:
    runner = json.loads(
        bundle.read(prefix + DIRECT_BUILD_INPUT_MEMBERS["runner_environment"])
    )
    signature = json.loads(
        bundle.read(prefix + DIRECT_BUILD_INPUT_MEMBERS["official_r_signature"])
    )
    _validate_official_signature(signature)
    ppm_inventory = json.loads(
        bundle.read(prefix + DIRECT_BUILD_INPUT_MEMBERS["ppm_archive_inventory"])
    )
    preflight = json.loads(
        bundle.read(
            prefix + DIRECT_BUILD_INPUT_MEMBERS["pyinstaller_toc_preflight_report"]
        )
    )
    _validate_preflight(preflight, manifest, target)
    _validate_ppm_inventory(ppm_inventory, manifest)
    _validate_ppm_archives(bundle, names, prefix, manifest)
    return runner


def _validate_official_signature(signature: dict) -> None:
    if not _signature_identity_valid(signature) or not _signature_text_valid(signature):
        raise MacOSDeploymentInspectionError(
            "official R package signature evidence is invalid"
        )


def _signature_identity_valid(signature: dict) -> bool:
    return (
        signature.get("schema_version") == 1
        and signature.get("status") == 0
        and signature.get("team_id") == "VZLD955F6P"
        and isinstance(signature.get("signer"), str)
        and "Developer ID Installer:" in signature["signer"]
        and isinstance(signature.get("certificate"), str)
        and bool(signature.get("certificate"))
    )


def _signature_text_valid(signature: dict) -> bool:
    return (
        isinstance(signature.get("status_line"), str)
        and signature["status_line"].lower().startswith("signed")
        and isinstance(signature.get("stdout"), str)
        and isinstance(signature.get("stderr"), str)
        and "VZLD955F6P" in signature["stdout"]
    )


def _validate_preflight(preflight: dict, manifest: dict, target: str) -> None:
    expected = {
        "schema_version": 1,
        "source_commit": manifest["source_commit"],
        "pyinstaller_version": "6.21.0",
        "system": "Darwin",
        "machine": TARGET_CONTRACTS[target]["architecture"],
        "aliases": {
            "Versions/Current": "4.6-arm64",
            "Resources": "Versions/Current/Resources",
            "R": "Versions/Current/R",
            "Versions/4.6-arm64/R": "Resources/lib/libR.dylib",
            "Versions/4.6-arm64/Resources/R": "bin/R",
        },
        "passed": True,
    }
    if preflight != expected:
        raise MacOSDeploymentInspectionError(
            "embedded PyInstaller TOC preflight differs from direct-build provenance"
        )


def _validate_ppm_inventory(ppm_inventory: dict, manifest: dict) -> None:
    expected = {
        "schema_version": 1,
        "repository": DIRECT_R_PPM_SNAPSHOT,
        "archives": manifest["ppm_archives"],
    }
    if ppm_inventory != expected:
        raise MacOSDeploymentInspectionError(
            "embedded PPM archive inventory differs from direct-build provenance"
        )


def _validate_ppm_archives(
    bundle: zipfile.ZipFile, names: list[str], prefix: str, manifest: dict
) -> None:
    for record in manifest["ppm_archives"]:
        member = prefix + "qualification/ppm-archives/" + record["path"]
        if member not in names:
            raise MacOSDeploymentInspectionError(
                f"ZIP lacks retained PPM archive: {member}"
            )
        payload = bundle.read(member)
        valid = (
            len(payload) == record["size"]
            and hashlib.sha256(payload).hexdigest() == record["sha256"]
        )
        if not valid:
            raise MacOSDeploymentInspectionError(
                f"ZIP retained PPM archive differs from provenance: {member}"
            )


def _validate_zip_member(info: zipfile.ZipInfo, prefix: str, folded: dict[str, str]) -> None:
    name = info.filename
    if info.flag_bits & 0x1:
        raise MacOSDeploymentInspectionError(f"ZIP contains an encrypted member: {name}")
    _validate_zip_name(name, prefix)
    _validate_zip_mode(info)
    key = name.casefold()
    if key in folded:
        raise MacOSDeploymentInspectionError(
            f"ZIP contains duplicate/case-colliding members: {folded[key]}, {name}"
        )
    folded[key] = name


def _validate_zip_name(name: str, prefix: str) -> None:
    relative = name[len(prefix) :].rstrip("/")
    if not _valid_zip_prefix(name, prefix):
        raise MacOSDeploymentInspectionError(f"ZIP contains a non-normalized member: {name}")
    if not _valid_zip_relative(relative, name, prefix):
        raise MacOSDeploymentInspectionError(
            f"ZIP contains traversal or empty components: {name}"
        )


def _valid_zip_prefix(name: str, prefix: str) -> bool:
    return (
        "\\" not in name
        and not name.startswith("/")
        and unicodedata.normalize("NFC", name) == name
        and name.startswith(prefix)
    )


def _valid_zip_relative(relative: str, name: str, prefix: str) -> bool:
    if name == prefix:
        return True
    return bool(relative) and not any(
        part in {"", ".", ".."} for part in relative.split("/")
    )


def _validate_zip_mode(info: zipfile.ZipInfo) -> None:
    name = info.filename
    unix_mode = info.external_attr >> 16
    if info.is_dir() and unix_mode and not stat.S_ISDIR(unix_mode):
        raise MacOSDeploymentInspectionError(
            f"ZIP directory has a non-directory mode: {name}"
        )
    if not info.is_dir() and not (stat.S_ISREG(unix_mode) or stat.S_ISLNK(unix_mode)):
        raise MacOSDeploymentInspectionError(f"ZIP member has an unsafe file mode: {name}")


def _validate_zip_members(
    infos: list[zipfile.ZipInfo], prefix: str
) -> list[str]:
    folded: dict[str, str] = {}
    for info in infos:
        _validate_zip_member(info, prefix, folded)
    return [item.filename for item in infos if not item.is_dir()]


def _hash_embedded_files(
    bundle: zipfile.ZipFile,
    names: list[str],
    prefix: str,
    embedded_files: dict[str, Path],
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative, source in embedded_files.items():
        member = prefix + relative
        archived_payload = bundle.read(member) if member in names else None
        matches = archived_payload == source.read_bytes()
        if relative == "qualification/direct-r-build-manifest.json":
            matches = archived_payload is not None
        if not matches:
            raise MacOSDeploymentInspectionError(
                f"ZIP qualification input is missing or changed: {member}"
            )
        if archived_payload is None:
            raise MacOSDeploymentInspectionError(f"ZIP qualification input is missing: {member}")
        hashes[relative] = hashlib.sha256(archived_payload).hexdigest()
    return hashes


def _validate_archive_inventory(
    bundle: zipfile.ZipFile,
    names: list[str],
    prefix: str,
    deployment: dict,
    signing_path: Path,
    target: str,
    direct_manifest: dict | None,
) -> None:
    _validate_archive_identity(deployment, target, direct_manifest)
    records = deployment.get("inventory", {}).get("files", [])
    if not isinstance(records, list) or not records:
        raise MacOSDeploymentInspectionError("deployment manifest has no archive inventory")
    app_prefix = prefix + "RCMetaStudio.app/"
    if not _archive_members_match(names, app_prefix, records):
        raise MacOSDeploymentInspectionError("ZIP app members differ from the inspected inventory")
    info_by_name = {item.filename: item for item in bundle.infolist()}
    for record in records:
        _validate_archive_record(bundle, info_by_name, app_prefix, record)
    signing = _validate_archive_signing(
        deployment, records, signing_path, prefix, names
    )
    _validate_archive_delivery(deployment, records, target)


def _archive_members_match(
    names: list[str], app_prefix: str, records: list[dict]
) -> bool:
    app_members = {
        name[len(app_prefix) :] for name in names if name.startswith(app_prefix)
    }
    return app_members == {record.get("path") for record in records}


def _validate_archive_identity(
    deployment: dict, target: str, direct_manifest: dict | None
) -> None:
    if deployment.get("target") != target:
        raise MacOSDeploymentInspectionError(
            "deployment manifest target differs from the archive target"
        )
    if direct_manifest is not None and deployment.get("source_commit") != direct_manifest.get(
        "source_commit"
    ):
        raise MacOSDeploymentInspectionError(
            "direct-build source commit differs from deployment evidence"
        )


def _validate_archive_signing(
    deployment: dict,
    records: list[dict],
    signing_path: Path,
    prefix: str,
    names: list[str],
) -> dict:
    signing = validate_signing_inventory(
        json.loads(signing_path.read_text(encoding="utf-8")),
        native_paths={record["path"] for record in records if "architectures" in record},
    )
    if not _signing_record_matches(
        deployment.get("signing_inventory", {}), signing, signing_path
    ):
        raise MacOSDeploymentInspectionError(
            "deployment manifest does not authenticate the signing inventory"
        )
    for relative in signing["nested_bundles"]:
        bundle_prefix = prefix + "RCMetaStudio.app/" + relative.rstrip("/") + "/"
        if not any(name.startswith(bundle_prefix) for name in names):
            raise MacOSDeploymentInspectionError(
                "ZIP signing inventory names a missing nested bundle"
            )
    return signing


def _validate_archive_record(
    bundle: zipfile.ZipFile,
    info_by_name: dict[str, zipfile.ZipInfo],
    app_prefix: str,
    record: dict,
) -> None:
    member = app_prefix + record["path"]
    info = info_by_name[member]
    mode = info.external_attr >> 16
    if record.get("kind") == "symlink":
        _validate_archive_symlink(bundle, member, mode, record)
        return
    _validate_archive_file(bundle, member, mode, record)


def _validate_archive_symlink(
    bundle: zipfile.ZipFile, member: str, mode: int, record: dict
) -> None:
    valid = (
        stat.S_ISLNK(mode)
        and stat.S_IMODE(mode) == record.get("mode")
        and bundle.read(member).decode("utf-8") == record.get("link_target")
    )
    if not valid:
        raise MacOSDeploymentInspectionError(
            f"ZIP symlink differs from inventory: {member}"
        )


def _validate_archive_file(
    bundle: zipfile.ZipFile, member: str, mode: int, record: dict
) -> None:
    digest = hashlib.sha256()
    size = 0
    with bundle.open(member) as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    valid = (
        not stat.S_ISLNK(mode)
        and size == record.get("size")
        and stat.S_IMODE(mode) == record.get("mode")
        and digest.hexdigest() == record.get("sha256")
    )
    if not valid:
        raise MacOSDeploymentInspectionError(f"ZIP file differs from inventory: {member}")


def _signing_record_matches(signing_record: dict, signing: dict, path: Path) -> bool:
    return (
        signing_record.get("path") == "qualification/ad-hoc-signing-inventory.json"
        and signing_record.get("sha256") == sha256_file(path)
        and signing_record.get("identity") == signing["identity"]
        and signing_record.get("native_files") == signing["native_files"]
        and signing_record.get("nested_bundles") == signing["nested_bundles"]
    )


def _validate_archive_delivery(deployment: dict, records: list[dict], target: str) -> None:
    if deployment.get("target") not in TARGET_CONTRACTS:
        return
    has_kit = isinstance(deployment.get("r_integration_kit"), dict)
    has_direct = isinstance(deployment.get("direct_r_build"), dict)
    if has_kit == has_direct:
        raise MacOSDeploymentInspectionError(
            "deployment manifest must name exactly one R delivery identity"
        )
    validate_r_framework_inventory(
        records,
        delivery_kind="direct-spike" if has_direct else "integration-kit",
        architecture=TARGET_CONTRACTS[target]["architecture"],
    )


def _validate_archive_manifests(
    bundle: zipfile.ZipFile,
    names: list[str],
    prefix: str,
    embedded_files: dict[str, Path],
    target: str,
) -> None:
    direct_path = embedded_files.get("qualification/direct-r-build-manifest.json")
    direct_manifest = None
    if direct_path is not None:
        direct_manifest = validate_direct_build_manifest(
            json.loads(bundle.read(prefix + "qualification/direct-r-build-manifest.json")),
            target=target,
        )
        validate_direct_build_archive_inputs(
            bundle, prefix=prefix, names=names, manifest=direct_manifest, target=target
        )
    manifest_path = embedded_files.get("qualification/deployment-manifest.json")
    signing_path = embedded_files.get("qualification/ad-hoc-signing-inventory.json")
    if manifest_path is None or signing_path is None:
        raise MacOSDeploymentInspectionError(
            "ZIP inspection requires deployment and signing inventories"
        )
    deployment = json.loads(manifest_path.read_text(encoding="utf-8"))
    _validate_archive_inventory(
        bundle, names, prefix, deployment, signing_path, target, direct_manifest
    )


def inspect_archive(
    archive: Path,
    *,
    archive_root_name: str,
    embedded_files: dict[str, Path],
    target: str = "macos-arm64",
) -> dict:
    validate_archive_root_name(archive_root_name)
    prefix = archive_root_name + "/"
    with zipfile.ZipFile(archive) as bundle:
        infos = bundle.infolist()
        if len(infos) > MAX_ARCHIVE_MEMBERS:
            raise MacOSDeploymentInspectionError("ZIP exceeds the member-count bound")
        if sum(item.file_size for item in infos) > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise MacOSDeploymentInspectionError(
                "ZIP exceeds the uncompressed-byte bound"
            )
        names = _validate_zip_members(infos, prefix)
        embedded_hashes = _hash_embedded_files(
            bundle, names, prefix, embedded_files
        )
        _validate_archive_manifests(bundle, names, prefix, embedded_files, target)
    return {
        "schema_version": 1,
        "target": target,
        "archive_root": archive_root_name,
        "archive_sha256": sha256_file(archive),
        "member_count": len(infos),
        "embedded_sha256": dict(sorted(embedded_hashes.items())),
    }


def _valid_sha256_map(value: object) -> bool:
    return (
        isinstance(value, dict)
        and bool(value)
        and all(
            isinstance(item, str)
            and len(item) == 64
            and all(char in "0123456789abcdef" for char in item)
            for item in value.values()
        )
    )


def _valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _string_keyed_dict(value: object) -> TypeGuard[dict[str, object]]:
    return isinstance(value, dict) and all(isinstance(key, str) for key in value)


def _contains_expected_hashes(actual: object, expected: dict[str, str]) -> bool:
    if not _string_keyed_dict(actual):
        return False
    return all(actual.get(path) == digest for path, digest in expected.items())


def validate_macos_surface_records(scales: object) -> None:
    if not isinstance(scales, list) or not all(
        isinstance(item, dict) for item in scales
    ):
        raise MacOSDeploymentInspectionError("macOS surface scales are incomplete")
    typed_scales = cast(list[dict[str, object]], scales)
    if [item.get("requested") for item in typed_scales] != ["1.25", "1.50", "1.75"]:
        raise MacOSDeploymentInspectionError("macOS surface scales are incomplete")
    for item in typed_scales:
        if not _surface_item_valid(item):
            raise MacOSDeploymentInspectionError(
                f"macOS packaged surface evidence is incomplete at {item.get('requested')}"
            )


def _surface_item_valid(item: dict[str, object]) -> bool:
    menu = _mapping_or_empty(item.get("native_menu", {}))
    file_dialog = _mapping_or_empty(item.get("native_file_dialog", {}))
    critical_dialog = _mapping_or_empty(item.get("critical_dialog", {}))
    accessibility = _mapping_or_empty(item.get("accessibility", {}))
    return (
        _surface_basic_controls(item, menu, file_dialog)
        and _surface_critical_dialog(critical_dialog)
        and _surface_accessibility(accessibility)
        and _surface_scale_values(item)
    )


def _surface_basic_controls(
    item: dict[str, object], menu: dict[str, object], file_dialog: dict[str, object]
) -> bool:
    return (
        item.get("platform_plugin") == "cocoa"
        and item.get("locale") == "de_DE"
        and all(item.get(key) is True for key in ("clipboard", "binary_resources"))
        and _surface_menu_valid(menu)
        and _surface_file_dialog_valid(file_dialog)
    )


def _surface_menu_valid(menu: dict[str, object]) -> bool:
    return (
        menu.get("is_native") is True
        and _int_or_default(menu.get("menu_count"), 0) >= 1
        and _int_or_default(menu.get("action_count"), 0) >= 1
    )


def _surface_file_dialog_valid(file_dialog: dict[str, object]) -> bool:
    return all(
        (
            file_dialog.get("dont_use_native_dialog") is False,
            file_dialog.get("window_modality") == "WindowModal",
            file_dialog.get("visible_before_cancel") is True,
            file_dialog.get("cancel_requested") is True,
            file_dialog.get("finished_signal") is True,
            file_dialog.get("rejected_signal") is True,
            file_dialog.get("result") == file_dialog.get("rejected_value") == 0,
            file_dialog.get("timed_out") is False,
            file_dialog.get("timeout_ms") == 10_000,
        )
    )


def _surface_critical_dialog(critical: dict[str, object]) -> bool:
    return all(
        (
            critical.get("dont_use_native_dialog") is False,
            critical.get("application_dont_use_native_dialogs") is False,
            critical.get("dont_show_on_screen_before_show") is False,
            critical.get("dont_show_on_screen_after_show") is True,
            critical.get("native_helper_active") is True,
            critical.get("window_modality") == "WindowModal",
            critical.get("visible_before_close") is True,
            critical.get("critical_icon") is True,
            critical.get("finished_signal") is True,
            critical.get("result") == critical.get("accepted_value") == 1,
            critical.get("timed_out") is False,
            critical.get("timeout_ms") == 5_000,
        )
    )


def _surface_accessibility(accessibility: dict[str, object]) -> bool:
    native = _mapping_or_empty(accessibility.get("native", {}))
    return all(
        (
            accessibility.get("focus_before") == "packagedAccessibilityControl",
            accessibility.get("focus_after_tab") == "packagedKeyboardTraversalTarget",
            accessibility.get("accessible_name") == "Packaged accessibility control",
            accessibility.get("accessible_description")
            == "Verifies packaged Qt accessibility metadata.",
            native.get("is_ignored") is False,
            native.get("exposed") is True,
            native.get("role") == "AXButton",
            native.get("title") == "Packaged accessibility control",
            native.get("description") == "Verifies packaged Qt accessibility metadata.",
            native.get("source") == "accessibility-tree",
            native.get("bridge") == "accessibilityAttributeValue:AXChildren",
            native.get("bridge_supported") is True,
            _int_or_default(native.get("root_count"), 0) >= 1,
        )
    )


def _surface_scale_values(item: dict[str, object]) -> bool:
    cleanup = _mapping_or_empty(item.get("cleanup", {}))
    image_formats = _strings_or_empty(item.get("image_formats", []))
    return all(
        (
            cleanup.get("close_accepted") is True,
            cleanup.get("window_visible") is False,
            bool(item.get("available_styles")),
            bool(item.get("active_style")),
            bool(item.get("tls_backends")),
            {"jpeg", "svg"} <= set(image_formats),
            abs(_float_or_default(item.get("qt_scale_factor"), 0) - _float_or_default(item.get("requested"), -1))
            < 1e-9,
            _float_or_default(item.get("baseline_device_pixel_ratio"), 0) > 0,
            abs(
                _float_or_default(item.get("expected_device_pixel_ratio"), 0)
                - _float_or_default(item.get("baseline_device_pixel_ratio"), 0)
                * _float_or_default(item.get("requested"), -1)
            )
            < 1e-9,
            abs(
                _float_or_default(item.get("device_pixel_ratio"), 0)
                - _float_or_default(item.get("expected_device_pixel_ratio"), -1)
            )
            <= _float_or_default(item.get("dpr_tolerance"), -1),
        )
    )


def _validate_extracted_qualification(
    extracted_probe_path: Path,
    extracted_deployment_path: Path,
    extracted_smoke_path: Path,
    extracted_smoke_log: Path,
    extracted_marker: Path,
    target: str,
) -> tuple[dict, dict, dict]:
    extracted_probe = json.loads(extracted_probe_path.read_text(encoding="utf-8"))
    extracted_deployment = json.loads(
        extracted_deployment_path.read_text(encoding="utf-8")
    )
    extracted_smoke = finalize_smoke_evidence(
        extracted_smoke_path,
        extracted_smoke_log,
        extracted_marker,
        require_direct_teardown=True,
        persist=False,
    )
    complete = (
        extracted_smoke.get("passed") is True
        and extracted_deployment.get("target") == target
        and extracted_probe.get("r")
    )
    if not complete:
        raise MacOSDeploymentInspectionError(
            "extracted ZIP qualification evidence is incomplete"
        )
    return extracted_probe, extracted_deployment, extracted_smoke


def _validate_extracted_deployment(
    deployment: dict,
    extracted_probe: dict,
    extracted_deployment: dict,
    target: str,
) -> None:
    contract = TARGET_CONTRACTS[target]
    valid = (
        _extracted_stack_matches(extracted_deployment, target, contract)
        and _extracted_source_matches(extracted_deployment, deployment)
        and extracted_deployment.get("runtime_probe_canonical_sha256")
        == _canonical_json_sha256(extracted_probe)
    )
    if not valid:
        raise MacOSDeploymentInspectionError(
            "extracted ZIP deployment does not authenticate its canonical runtime probe"
        )


def _extracted_stack_matches(
    extracted_deployment: dict, target: str, contract: dict
) -> bool:
    return (
        extracted_deployment.get("schema_version") == 1
        and extracted_deployment.get("target") == target
        and extracted_deployment.get("architecture") == contract["architecture"]
        and extracted_deployment.get("stack") == EXPECTED_VERSIONS
        and extracted_deployment.get("qt_dependency_collector") == "PyInstaller"
    )


def _extracted_source_matches(extracted_deployment: dict, deployment: dict) -> bool:
    source_commit = extracted_deployment.get("source_commit")
    return (
        isinstance(source_commit, str)
        and len(source_commit) == 40
        and source_commit == deployment.get("source_commit")
    )


def _validate_qualification_artifacts(
    deployment: dict,
    smoke: dict,
    archive_report: dict,
    archive: Path,
    signing_inventory: Path,
    expected_embedded: dict[str, str],
    target: str,
    architecture: str,
) -> None:
    signing = deployment.get("signing_inventory", {})
    if not _qualification_deployment_valid(
        deployment, signing, target, architecture, signing_inventory
    ):
        raise MacOSDeploymentInspectionError(
            "macOS packaged qualification evidence is incomplete"
        )
    if not _qualification_archive_valid(
        smoke, archive_report, archive, target, expected_embedded
    ):
        raise MacOSDeploymentInspectionError(
            "macOS packaged qualification evidence is incomplete"
        )


def _qualification_deployment_valid(
    deployment: dict,
    signing: dict,
    target: str,
    architecture: str,
    signing_inventory: Path,
) -> bool:
    return (
        deployment.get("target") == target
        and deployment.get("stack") == EXPECTED_VERSIONS
        and deployment.get("architecture") == architecture
        and deployment.get("qt_dependency_collector") == "PyInstaller"
        and signing.get("path") == "qualification/ad-hoc-signing-inventory.json"
        and signing.get("sha256") == sha256_file(signing_inventory)
    )


def _qualification_archive_valid(
    smoke: dict,
    archive_report: dict,
    archive: Path,
    target: str,
    expected_embedded: dict[str, str],
) -> bool:
    return (
        smoke.get("execution", {}).get("clean_exit") is True
        and smoke.get("execution", {}).get("launchservices_completion_marker") is True
        and archive_report.get("target") == target
        and archive_report.get("archive_sha256") == sha256_file(archive)
        and _contains_expected_hashes(
            archive_report.get("embedded_sha256", {}), expected_embedded
        )
    )


def _validate_profile(path: Path, architecture: str) -> None:
    profile = json.loads(path.read_text(encoding="utf-8"))
    try:
        validate_profile_evidence(
            profile,
            expected_r_version=EXPECTED_VERSIONS["r"],
            expected_architecture=architecture,
        )
    except ProfileSchemaError as exc:
        raise MacOSDeploymentInspectionError(
            "embedded R profile evidence is incomplete"
        ) from exc


def _qualification_hashes(
    deployment_manifest: Path,
    signing_inventory: Path,
    runtime_probe: Path,
    r_runtime_profile: Path,
    direct_build_manifest: Path,
    smoke_evidence: Path,
    smoke_log: Path,
    launchservices_marker: Path,
    smoke_stdout: Path,
    smoke_stderr: Path,
    hang_trace: Path,
) -> dict[str, str]:
    return {
        "qualification/deployment-manifest.json": sha256_file(deployment_manifest),
        "qualification/ad-hoc-signing-inventory.json": sha256_file(signing_inventory),
        "qualification/runtime-probe.json": sha256_file(runtime_probe),
        "qualification/embedded-r-runtime-profile.json": sha256_file(r_runtime_profile),
        "qualification/direct-r-build-manifest.json": sha256_file(direct_build_manifest),
        "qualification/packaged-smoke.json": sha256_file(smoke_evidence),
        "qualification/packaged-smoke.log": sha256_file(smoke_log),
        "qualification/launchservices-completion.json": sha256_file(launchservices_marker),
        "qualification/packaged-smoke.stdout.log": sha256_file(smoke_stdout),
        "qualification/packaged-smoke.stderr.log": sha256_file(smoke_stderr),
        "qualification/packaged-smoke.hang-trace.log": sha256_file(hang_trace),
    }


def write_qualification_evidence(
    *,
    archive: Path,
    deployment_manifest: Path,
    smoke_evidence: Path,
    smoke_log: Path,
    smoke_stdout: Path,
    smoke_stderr: Path,
    hang_trace: Path,
    runtime_probe: Path,
    r_runtime_profile: Path,
    direct_build_manifest: Path,
    extracted_runtime_probe: Path,
    extracted_deployment_manifest: Path,
    extracted_smoke_evidence: Path,
    extracted_smoke_log: Path,
    extracted_smoke_stdout: Path,
    extracted_smoke_stderr: Path,
    extracted_hang_trace: Path,
    extracted_launchservices_marker: Path,
    launchservices_marker: Path,
    archive_inspection: Path,
    signing_inventory: Path,
    output: Path,
    target: str = "macos-arm64",
) -> dict:
    deployment = json.loads(deployment_manifest.read_text(encoding="utf-8"))
    extracted_probe, extracted_deployment, extracted_smoke = _validate_extracted_qualification(
        extracted_runtime_probe,
        extracted_deployment_manifest,
        extracted_smoke_evidence,
        extracted_smoke_log,
        extracted_launchservices_marker,
        target,
    )
    _validate_extracted_deployment(
        deployment, extracted_probe, extracted_deployment, target
    )
    architecture = TARGET_CONTRACTS[target]["architecture"]
    _validate_profile(r_runtime_profile, architecture)
    smoke = finalize_smoke_evidence(
        smoke_evidence,
        smoke_log,
        launchservices_marker,
        require_direct_teardown=True,
        persist=False,
    )
    archive_report = json.loads(archive_inspection.read_text(encoding="utf-8"))
    validate_direct_build_manifest(
        json.loads(direct_build_manifest.read_text(encoding="utf-8")), target=target
    )
    expected_embedded = _qualification_hashes(
        deployment_manifest,
        signing_inventory,
        runtime_probe,
        r_runtime_profile,
        direct_build_manifest,
        smoke_evidence,
        smoke_log,
        launchservices_marker,
        smoke_stdout,
        smoke_stderr,
        hang_trace,
    )
    _validate_qualification_artifacts(
        deployment,
        smoke,
        archive_report,
        archive,
        signing_inventory,
        expected_embedded,
        target,
        architecture,
    )
    evidence = {
        "schema_version": 1,
        "target": target,
        "passed": True,
        "artifact": {
            "name": archive.name,
            "size": archive.stat().st_size,
            "sha256": sha256_file(archive),
        },
        "deployment_manifest": {
            "path": deployment_manifest.name,
            "sha256": sha256_file(deployment_manifest),
        },
        "signing_inventory": {
            "path": "qualification/ad-hoc-signing-inventory.json",
            "sha256": sha256_file(signing_inventory),
        },
        "runtime_probe": {
            "path": runtime_probe.name,
            "sha256": sha256_file(runtime_probe),
        },
        "embedded_r_runtime_profile": {
            "path": r_runtime_profile.name,
            "sha256": sha256_file(r_runtime_profile),
        },
        "direct_r_build": {
            "path": direct_build_manifest.name,
            "sha256": sha256_file(direct_build_manifest),
        },
        "extracted_zip_qualification": {
            "runtime_probe": {
                "path": extracted_runtime_probe.name,
                "sha256": sha256_file(extracted_runtime_probe),
            },
            "deployment_manifest": {
                "path": extracted_deployment_manifest.name,
                "sha256": sha256_file(extracted_deployment_manifest),
            },
            "smoke_evidence": {
                "path": extracted_smoke_evidence.name,
                "sha256": sha256_file(extracted_smoke_evidence),
            },
            "logs": [
                {"path": path.name, "sha256": sha256_file(path)}
                for path in (
                    extracted_smoke_log,
                    extracted_smoke_stdout,
                    extracted_smoke_stderr,
                    extracted_hang_trace,
                )
            ],
            "launchservices_completion": {
                "path": extracted_launchservices_marker.name,
                "sha256": sha256_file(extracted_launchservices_marker),
            },
        },
        "smoke_evidence": {
            "path": smoke_evidence.name,
            "sha256": sha256_file(smoke_evidence),
        },
        "archive_inspection": {
            "path": archive_inspection.name,
            "sha256": sha256_file(archive_inspection),
        },
        "logs": [
            {
                "path": path.name,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in (smoke_log, smoke_stdout, smoke_stderr, hang_trace)
        ],
        "launchservices_completion": {
            "path": launchservices_marker.name,
            "sha256": sha256_file(launchservices_marker),
        },
        "runner": {
            "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
            "runner_name": os.environ.get("RUNNER_NAME", "local"),
            "runner_os": os.environ.get("RUNNER_OS", platform.system()),
            "runner_arch": os.environ.get("RUNNER_ARCH", platform.machine()),
            "runner_image": os.environ.get("ImageOS", "local"),
            "os_version": platform.mac_ver()[0] or platform.version(),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return evidence


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    validate_root = commands.add_parser("validate-root")
    validate_root.add_argument("--archive-root-name", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--app-root", type=Path, required=True)
    inspect.add_argument("--output", type=Path, required=True)
    inspect.add_argument("--source-commit", required=True)
    inspect.add_argument("--runtime-probe", type=Path, required=True)
    inspect.add_argument("--signing-inventory", type=Path, required=True)
    inspect.add_argument("--locked-qt-root", type=Path, required=True)
    inspect.add_argument(
        "--target", choices=sorted(TARGET_CONTRACTS), default="macos-arm64"
    )
    for name in EXPECTED_VERSIONS:
        inspect.add_argument(
            f"--{name.replace('_', '-')}-version", dest=f"{name}_version", required=True
        )
    finalize = commands.add_parser("finalize-smoke")
    finalize.add_argument("--smoke-evidence", type=Path, required=True)
    finalize.add_argument("--smoke-log", type=Path, required=True)
    finalize.add_argument("--launchservices-marker", type=Path)
    finalize.add_argument("--require-direct-teardown", action="store_true")
    archive = commands.add_parser("archive")
    archive.add_argument("--archive", type=Path, required=True)
    archive.add_argument("--archive-root-name", required=True)
    archive.add_argument(
        "--target", choices=sorted(TARGET_CONTRACTS), default="macos-arm64"
    )
    for name in (
        "deployment_manifest",
        "runtime_probe",
        "runtime_stdout",
        "runtime_stderr",
        "smoke_evidence",
        "smoke_log",
        "smoke_stdout",
        "smoke_stderr",
        "hang_trace",
        "signing_inventory",
        "r_runtime_profile",
    ):
        archive.add_argument(f"--{name.replace('_', '-')}", type=Path, required=True)
    archive.add_argument("--launchservices-marker", type=Path)
    archive_identity = archive.add_mutually_exclusive_group(required=True)
    archive_identity.add_argument("--r-integration-kit-manifest", type=Path)
    archive_identity.add_argument("--direct-build-manifest", type=Path)
    archive.add_argument("--output", type=Path, required=True)
    native_graph = commands.add_parser("native-graph")
    native_graph.add_argument("--app", type=Path, required=True)
    native_graph.add_argument(
        "--target", choices=tuple(TARGET_CONTRACTS), default="macos-arm64"
    )
    native_graph.add_argument("--output", type=Path, required=True)
    evidence = commands.add_parser("evidence")
    evidence.add_argument(
        "--target", choices=sorted(TARGET_CONTRACTS), default="macos-arm64"
    )
    for name in (
        "archive",
        "deployment_manifest",
        "runtime_probe",
        "smoke_evidence",
        "smoke_log",
        "smoke_stdout",
        "smoke_stderr",
        "hang_trace",
        "launchservices_marker",
        "archive_inspection",
        "signing_inventory",
        "r_runtime_profile",
        "extracted_runtime_probe",
        "extracted_deployment_manifest",
        "extracted_smoke_evidence",
        "extracted_smoke_log",
        "extracted_smoke_stdout",
        "extracted_smoke_stderr",
        "extracted_hang_trace",
        "extracted_launchservices_marker",
        "output",
    ):
        evidence.add_argument(f"--{name.replace('_', '-')}", type=Path, required=True)
    evidence.add_argument("--direct-build-manifest", type=Path, required=True)
    return parser


def _dispatch_validate_root(args: argparse.Namespace) -> None:
    validate_archive_root_name(args.archive_root_name)


def _dispatch_inspect(args: argparse.Namespace) -> None:
    versions = {
        name: getattr(args, f"{name}_version") for name in EXPECTED_VERSIONS
    }
    result = inspect_deployment(
        args.app_root,
        versions=versions,
        source_commit=args.source_commit,
        runtime_probe=json.loads(args.runtime_probe.read_text(encoding="utf-8")),
        locked_qt_root=args.locked_qt_root,
        signing_inventory_path=args.signing_inventory,
        target=args.target,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _dispatch_finalize(args: argparse.Namespace) -> None:
    finalize_smoke_evidence(
        args.smoke_evidence,
        args.smoke_log,
        args.launchservices_marker,
        require_direct_teardown=args.require_direct_teardown,
    )


def _dispatch_native_graph(args: argparse.Namespace) -> None:
    result = inspect_unsigned_native_graph(args.app, target=args.target)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _archive_embedded_files(args: argparse.Namespace) -> dict[str, Path]:
    embedded = {
        "qualification/deployment-manifest.json": args.deployment_manifest,
        "qualification/ad-hoc-signing-inventory.json": args.signing_inventory,
        "qualification/runtime-probe.json": args.runtime_probe,
        "qualification/runtime-probe.stdout.log": args.runtime_stdout,
        "qualification/runtime-probe.stderr.log": args.runtime_stderr,
        "qualification/embedded-r-runtime-profile.json": args.r_runtime_profile,
        "qualification/packaged-smoke.json": args.smoke_evidence,
        "qualification/packaged-smoke.log": args.smoke_log,
        "qualification/packaged-smoke.stdout.log": args.smoke_stdout,
        "qualification/packaged-smoke.stderr.log": args.smoke_stderr,
        "qualification/packaged-smoke.hang-trace.log": args.hang_trace,
    }
    marker = args.launchservices_marker
    if marker is not None:
        embedded["qualification/launchservices-completion.json"] = marker
    direct_manifest = args.direct_build_manifest
    if direct_manifest is not None:
        embedded["qualification/direct-r-build-manifest.json"] = direct_manifest
    else:
        embedded["qualification/r-integration-kit-manifest.json"] = (
            args.r_integration_kit_manifest
        )
    return embedded


def _dispatch_archive(args: argparse.Namespace) -> None:
    result = inspect_archive(
        args.archive,
        archive_root_name=args.archive_root_name,
        target=args.target,
        embedded_files=_archive_embedded_files(args),
    )
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _dispatch_evidence(args: argparse.Namespace) -> None:
    names = (
        "archive",
        "deployment_manifest",
        "runtime_probe",
        "smoke_evidence",
        "smoke_log",
        "smoke_stdout",
        "smoke_stderr",
        "hang_trace",
        "launchservices_marker",
        "archive_inspection",
        "signing_inventory",
        "output",
        "r_runtime_profile",
        "direct_build_manifest",
        "extracted_runtime_probe",
        "extracted_deployment_manifest",
        "extracted_smoke_evidence",
        "extracted_smoke_log",
        "extracted_smoke_stdout",
        "extracted_smoke_stderr",
        "extracted_hang_trace",
        "extracted_launchservices_marker",
    )
    write_qualification_evidence(
        target=args.target,
        **{name: getattr(args, name) for name in names},
    )


def _dispatch_command(args: argparse.Namespace) -> None:
    handlers = {
        "validate-root": _dispatch_validate_root,
        "inspect": _dispatch_inspect,
        "finalize-smoke": _dispatch_finalize,
        "native-graph": _dispatch_native_graph,
        "archive": _dispatch_archive,
        "evidence": _dispatch_evidence,
    }
    handlers[args.command](args)


def main() -> int:
    args = _build_parser().parse_args()
    try:
        _dispatch_command(args)
    except (
        MacOSDeploymentInspectionError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"macOS deployment inspection failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
