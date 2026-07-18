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
from typing import Any, cast
import unicodedata
import zipfile

from rc_metastudio.qt6_macos_feasibility import (
    EvidenceError,
    _archs,
    is_macho_candidate,
)
from rc_metastudio.r_runtime import macos_r_framework_version


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
EXPECTED_SUMMARY_SHA256 = (
    "78294820c83cd94c19dfdca8c24b6a96cdc8b6f1319a5cd1bedffacde73851e2"
)
MAX_FILES = 25_000
MAX_BYTES = 3_000_000_000
MAX_ARCHIVE_MEMBERS = 30_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 3_000_000_000
PORTABLE_FORBIDDEN = set('<>:"/\\|?*')
TARGET_CONTRACTS = {
    "macos-x64": {"architecture": "x86_64", "minimum_macos": "13.0"},
    "macos-arm64": {"architecture": "arm64", "minimum_macos": "14.0"},
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


def _valid_r_kit_derivation(manifest, derivation, target):
    manifest_files = {
        record.get("path"): record
        for record in manifest.get("files", [])
        if record.get("kind") == "file"
    }
    for name in ("api_bridge", "r_shared_library"):
        source = derivation.get("source", {}).get(name, {})
        pre_sign = derivation.get("pre_sign", {}).get(name, {})
        final = derivation.get("final", {}).get(name, {})
        transformation = derivation.get("transformations", {}).get(name)
        pre_sign_is_derived = pre_sign.get("sha256") == source.get("sha256") or (
            name == "api_bridge"
            and isinstance(transformation, dict)
            and transformation.get("kind") == "mach-o-load-command-relocation"
            and transformation.get("source", {}).get("sha256") == source.get("sha256")
            and transformation.get("output", {}).get("sha256") == pre_sign.get("sha256")
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
        return _archs(path)
    except EvidenceError as exc:
        raise MacOSDeploymentInspectionError(str(exc)) from exc


def require_macho_architecture(path: Path, architecture: str) -> list[str]:
    architectures = macho_architectures(path)
    if architectures != [architecture]:
        raise MacOSDeploymentInspectionError(
            f"Mach-O payload must be {architecture}-only: {path} ({architectures})"
        )
    return architectures


def require_x64_macho(path: Path) -> list[str]:
    """Retain the named Intel helper for existing callers and focused tests."""
    return require_macho_architecture(path, "x86_64")


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
    architecture: str = "x86_64",
) -> None:
    root = app_root.resolve()
    executable_dir = (root / executable_relative).parent
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

    executable_records = [
        record for record in native_records if record.get("path") == executable_relative
    ]
    if len(executable_records) != 1:
        raise MacOSDeploymentInspectionError(
            "dependency graph has no unique packaged executable"
        )
    executable_rpaths = executable_records[0].get("rpaths", [])

    for record in native_records:
        loader = (root / record["path"]).resolve().parent
        for dependency in record.get("dependencies", []):
            if dependency == record.get("install_id"):
                continue
            if dependency.startswith(("/usr/lib/", "/System/Library/")):
                continue
            candidates: set[Path] = set()
            direct = _resolve_token_base(
                dependency, loader=loader, executable_dir=executable_dir
            )
            if direct is not None:
                candidates.add(direct.resolve())
            elif dependency.startswith("@rpath/"):
                suffix = dependency[len("@rpath/") :]
                rpath_declarations = [
                    *((rpath, loader) for rpath in record.get("rpaths", [])),
                    *((rpath, executable_dir) for rpath in executable_rpaths),
                ]
                for rpath, declaring_loader in dict.fromkeys(rpath_declarations):
                    base = _resolve_token_base(
                        rpath,
                        loader=declaring_loader,
                        executable_dir=executable_dir,
                    )
                    if base is not None:
                        candidates.add((base / suffix).resolve())
            else:
                raise MacOSDeploymentInspectionError(
                    f"unsupported Mach-O dependency token for {record['path']}: {dependency}"
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


def validate_locked_qt_inventory(
    deployed_qt_records: list[dict],
    *,
    locked_qt_root: Path,
    architecture: str = "x86_64",
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
            f"hardened ad-hoc code signature verification failed: {verified.stderr}"
        )
    details = subprocess.run(
        ["codesign", "-d", "--verbose=4", str(app_root)],
        capture_output=True,
        text=True,
        check=False,
    )
    detail_text = details.stdout + details.stderr
    if details.returncode != 0 or "runtime" not in detail_text.lower():
        raise MacOSDeploymentInspectionError(
            "app bundle signature does not carry the hardened-runtime flag"
        )
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
    return {"verified": True, "runtime": True, "entitlements": {}}


def _normalize_runtime_path(value: object) -> Path:
    return Path(str(value)).resolve()


def _validate_runtime_probe(
    probe: dict, app_root: Path, *, architecture: str = "x86_64"
) -> None:
    executable = app_root / "Contents/MacOS/RCMetaStudio"
    frameworks = app_root / "Contents/Frameworks"
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
    qt = probe.get("qt", {})
    plugin_path = _normalize_runtime_path(qt.get("plugins_path"))
    library_paths = {
        _normalize_runtime_path(item) for item in qt.get("library_paths", [])
    }
    if (
        qt.get("pyqt_version") != EXPECTED_VERSIONS["pyqt6"]
        or qt.get("compiled_qt_version") != "6.11.0"
        or qt.get("runtime_qt_version") != EXPECTED_VERSIONS["qt"]
        or qt.get("sip_runtime_version") != EXPECTED_VERSIONS["sip_runtime"]
        or qt.get("platform_plugin") != "cocoa"
        or not plugin_path.is_relative_to(frameworks)
        or plugin_path not in library_paths
        or qt.get("scale_factor_environment") is not None
        or float(qt.get("baseline_device_pixel_ratio", 0)) <= 0
        or float(qt.get("baseline_logical_dpi", 0)) <= 0
    ):
        raise MacOSDeploymentInspectionError(
            "frozen Qt probe does not match the Cocoa deployment"
        )
    rpy2 = probe.get("rpy2", {})
    if not (
        {
            key: rpy2.get(key)
            for key in (
                "distribution_version",
                "rinterface_distribution_version",
                "robjects_distribution_version",
                "cffi_mode",
                "loaded_cffi_mode",
                "api_bridge_loaded",
            )
        }
        == {
            "distribution_version": EXPECTED_VERSIONS["rpy2"],
            "cffi_mode": "API",
            "rinterface_distribution_version": "3.6.6",
            "robjects_distribution_version": "3.6.5",
            "loaded_cffi_mode": "API",
            "api_bridge_loaded": True,
        }
        and _valid_sha256(rpy2.get("api_bridge_sha256"))
        and _normalize_runtime_path(rpy2.get("api_bridge_path")).is_relative_to(
            frameworks
        )
    ):
        raise MacOSDeploymentInspectionError("frozen rpy2 probe differs from the lock")
    if probe.get("project_schemas") != {
        "version": 1,
        "validated_members": ["manifest.json", "project.json", "state.json"],
    }:
        raise MacOSDeploymentInspectionError("frozen project schemas are incomplete")
    expected_r_home = app_root / "Contents/Frameworks/R.framework/Resources"
    expected_r_library = expected_r_home / "library"
    r = probe.get("r", {})
    r_libraries = {_normalize_runtime_path(item) for item in r.get("library_paths", [])}
    if (
        r.get("version") != EXPECTED_VERSIONS["r"]
        or _normalize_runtime_path(r.get("home")) != expected_r_home.resolve()
        or _normalize_runtime_path(r.get("configured_home"))
        != expected_r_home.resolve()
        or _normalize_runtime_path(r.get("configured_library"))
        != expected_r_library.resolve()
        or expected_r_library.resolve() not in r_libraries
        or r.get("lc_numeric") != "C"
        or not _valid_sha256(r.get("shared_library_sha256"))
        or not _normalize_runtime_path(r.get("shared_library_path")).is_relative_to(
            frameworks
        )
        or not _valid_sha256(r.get("kit_sha256"))
    ):
        raise MacOSDeploymentInspectionError(
            "frozen R probe does not use the bundled runtime"
        )
    policy = r.get("macos_product_profile")
    png = policy.get("default_png", {}) if isinstance(policy, dict) else {}
    if not (
        isinstance(policy, dict)
        and policy.get("tcltk_available") is False
        and policy.get("tcltk_loaded") is False
        and policy.get("aqua") is True
        and policy.get("bitmap_type") == "quartz"
        and isinstance(png.get("size"), int)
        and png["size"] > 0
        and _valid_sha256(png.get("sha256"))
    ):
        raise MacOSDeploymentInspectionError(
            "frozen R probe lacks the macOS Quartz product-profile evidence"
        )


def validate_signing_inventory(
    inventory: object, *, native_paths: set[str], app_root: Path | None = None
) -> dict:
    if not isinstance(inventory, dict):
        raise MacOSDeploymentInspectionError("signing inventory must be an object")
    typed_inventory = cast(dict[str, Any], inventory)
    expected_keys = {
        "schema_version",
        "app",
        "identity",
        "native_files",
        "nested_bundles",
        "verification",
    }
    native_files = typed_inventory.get("native_files")
    nested_bundles = typed_inventory.get("nested_bundles")
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
        or not isinstance(nested_bundles, list)
        or not all(isinstance(item, str) for item in nested_bundles)
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


def validate_r_framework_inventory(records: object) -> None:
    """Require the canonical, concrete R framework payload and alias topology."""
    if not isinstance(records, list) or not all(
        isinstance(item, dict) for item in records
    ):
        raise MacOSDeploymentInspectionError(
            "R framework inventory is not a record list"
        )
    typed_records = cast(list[dict[str, Any]], records)
    by_path = {record.get("path"): record for record in typed_records}
    try:
        framework_version = macos_r_framework_version(EXPECTED_VERSIONS["r"])
    except ValueError as exc:
        raise MacOSDeploymentInspectionError(
            "locked R version cannot name its framework"
        ) from exc
    framework = "Contents/Frameworks/R.framework"
    version_root = f"{framework}/Versions/{framework_version}"
    resources = f"{version_root}/Resources"
    required_files = {
        f"{resources}/bin/Rscript",
        f"{resources}/library/RCMetaR/DESCRIPTION",
        f"{resources}/Info.plist",
        f"{version_root}/R",
    }
    for path in required_files:
        if by_path.get(path, {}).get("kind") != "file":
            raise MacOSDeploymentInspectionError(
                f"R framework is missing its concrete versioned member: {path}"
            )
    r_executable = by_path[f"{version_root}/R"]
    if (
        "architectures" not in r_executable
        or not int(r_executable.get("mode", 0)) & 0o111
    ):
        raise MacOSDeploymentInspectionError(
            "R framework native executable target is not in the Mach-O inventory"
        )
    expected_links = {
        f"{framework}/Versions/Current": (
            framework_version,
            version_root,
        ),
        f"{framework}/Resources": (
            "Versions/Current/Resources",
            resources,
        ),
        f"{resources}/lib/libR.dylib": (
            "../../R",
            f"{version_root}/R",
        ),
        f"{framework}/R": (
            "Versions/Current/R",
            f"{version_root}/R",
        ),
    }
    for path, (target, resolved) in expected_links.items():
        record = by_path.get(path, {})
        if (
            record.get("kind") != "symlink"
            or record.get("mode") != 0o777
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
    typed_records = cast(list[dict[str, Any]], records)
    if any(
        "_rinterface_cffi_abi" in str(record.get("path", "")).lower()
        for record in typed_records
    ):
        raise MacOSDeploymentInspectionError(
            "deployment contains the forbidden rpy2 ABI-mode fallback bridge"
        )
    api_native = [
        record
        for record in typed_records
        if "architectures" in record
        and "_rinterface_cffi_api" in str(record.get("path", "")).lower()
    ]
    if len(api_native) != 1:
        raise MacOSDeploymentInspectionError(
            "deployment must contain exactly one rpy2 API-mode bridge"
        )
    api_support = [
        record
        for record in typed_records
        if "architectures" in record
        and "/rpy2/rinterface_lib/_bufferprotocol"
        in str(record.get("path", "")).lower()
    ]
    if len(api_support) != 1:
        raise MacOSDeploymentInspectionError(
            "deployment must contain exactly one rpy2 API bridge support extension"
        )


def inspect_deployment(
    app_root: Path,
    *,
    versions: dict[str, str],
    source_commit: str,
    runtime_probe: dict,
    locked_qt_root: Path,
    signing_inventory_path: Path,
    target: str = "macos-x64",
) -> dict:
    app_root = app_root.resolve()
    contract = TARGET_CONTRACTS[target]
    architecture = contract["architecture"]
    minimum_macos = contract["minimum_macos"]
    if versions != EXPECTED_VERSIONS:
        raise MacOSDeploymentInspectionError(f"locked stack mismatch: {versions}")
    if len(source_commit) != 40 or any(
        char not in "0123456789abcdef" for char in source_commit
    ):
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
    if (
        info.get("CFBundleExecutable") != "RCMetaStudio"
        or info.get("CFBundleIdentifier") != "org.researchconsultancy.rc-metastudio"
        or info.get("LSMinimumSystemVersion") != minimum_macos
        or info.get("NSHighResolutionCapable") is not True
    ):
        raise MacOSDeploymentInspectionError(
            f"Info.plist is not the qualified macOS {minimum_macos} bundle contract"
        )
    _validate_runtime_probe(runtime_probe, app_root, architecture=architecture)

    records: list[dict] = []
    folded: dict[str, str] = {}
    total_bytes = 0
    native_records: list[dict] = []
    for current, directories, filenames in os.walk(app_root, followlinks=False):
        current_path = Path(current)
        for name in list(directories):
            path = current_path / name
            if path.is_symlink():
                directories.remove(name)
                relative = _relative(path, app_root)
                resolved = _resolved_inside(path, app_root)
                record = {
                    "path": relative,
                    "kind": "symlink",
                    "size": path.lstat().st_size,
                    "mode": stat.S_IMODE(path.lstat().st_mode),
                    "link_target": os.readlink(path),
                    "resolved_path": _relative(resolved, app_root),
                }
                records.append(record)
                total_bytes += record["size"]
        for name in filenames:
            path = current_path / name
            relative = _relative(path, app_root)
            key = relative.casefold()
            if key in folded:
                raise MacOSDeploymentInspectionError(
                    f"deployment contains duplicate/case-colliding paths: {folded[key]}, {relative}"
                )
            folded[key] = relative
            if path.is_symlink():
                resolved = _resolved_inside(path, app_root)
                record = {
                    "path": relative,
                    "kind": "symlink",
                    "size": path.lstat().st_size,
                    "mode": stat.S_IMODE(path.lstat().st_mode),
                    "link_target": os.readlink(path),
                    "resolved_path": _relative(resolved, app_root),
                }
            else:
                size = path.stat().st_size
                record = {
                    "path": relative,
                    "kind": "file",
                    "size": size,
                    "mode": stat.S_IMODE(path.stat().st_mode),
                    "sha256": sha256_file(path),
                }
                if _is_macho(path):
                    record["architectures"] = require_macho_architecture(
                        path, architecture
                    )
                    record["dependencies"] = _dependencies(path)
                    record.update(_macho_load_metadata(path))
                    minimum = record.get("minimum_macos")
                    if minimum is None or _macos_version(str(minimum)) > _macos_version(
                        minimum_macos
                    ):
                        raise MacOSDeploymentInspectionError(
                            f"Mach-O deployment target exceeds {minimum_macos}: {relative}={minimum}"
                        )
                    native_records.append(record)
            records.append(record)
            total_bytes += record["size"]
            if len(records) > MAX_FILES or total_bytes > MAX_BYTES:
                raise MacOSDeploymentInspectionError(
                    "deployment exceeds its bounded inventory"
                )

    lowered_paths = [record["path"].lower() for record in records]
    validate_r_framework_inventory(records)
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
    required_plugins = {
        "cocoa": "/plugins/platforms/libqcocoa.dylib",
        "jpeg": "/plugins/imageformats/libqjpeg.dylib",
        "svg_image": "/plugins/imageformats/libqsvg.dylib",
        "svg_icon": "/plugins/iconengines/libqsvgicon.dylib",
    }
    plugin_paths: dict[str, str] = {}
    for label, suffix in required_plugins.items():
        matches = [
            record["path"]
            for record in native_records
            if record["path"].lower().endswith(suffix)
        ]
        if len(matches) != 1:
            raise MacOSDeploymentInspectionError(
                f"required {label} Qt plugin count is {len(matches)}, expected one"
            )
        plugin_paths[label] = matches[0]
    tls_plugins = [
        record["path"]
        for record in native_records
        if "/plugins/tls/" in record["path"].lower()
        and record["path"].lower().endswith(".dylib")
    ]
    if not tls_plugins:
        raise MacOSDeploymentInspectionError("deployment contains no Qt TLS plugin")
    qt_roots = {
        path.split("/plugins/", 1)[0] for path in [*plugin_paths.values(), *tls_plugins]
    }
    if len(qt_roots) != 1 or not next(iter(qt_roots)).endswith("/PyQt6/Qt6"):
        raise MacOSDeploymentInspectionError(
            "deployment does not have one authoritative PyQt6 Qt root"
        )
    qt_root = next(iter(qt_roots))
    for record in native_records:
        path = record["path"]
        lowered = path.lower()
        qt_like = (
            "/pyqt6/qt6/" in lowered
            or (".framework/versions/" in lowered and "/qt" in lowered)
            or ("/plugins/" in lowered and Path(path).name.lower().startswith("libq"))
            or Path(path).name.lower().startswith("libqt6")
        )
        if qt_like and not path.startswith(qt_root + "/"):
            raise MacOSDeploymentInspectionError(
                f"deployment contains a second or displaced Qt payload: {path}"
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
    deployed_qt_records = []
    for record in native_records:
        if record["path"].startswith(qt_root + "/"):
            deployed_qt_records.append(
                {**record, "qt_relative_path": record["path"][len(qt_root) + 1 :]}
            )
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
    kit_manifest_path = (
        app_root / "Contents" / "Resources" / "r-integration-kit" / "manifest.json"
    )
    derivation_path = (
        app_root / "Contents" / "Resources" / "r-integration-kit" / "derivation.json"
    )
    try:
        kit_manifest = json.loads(kit_manifest_path.read_text(encoding="utf-8"))
        derivation = json.loads(derivation_path.read_text(encoding="utf-8"))
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
        and derivation.get("final", {}).get("api_bridge", {}).get("sha256")
        == runtime_probe.get("rpy2", {}).get("api_bridge_sha256")
        and derivation.get("final", {}).get("r_shared_library", {}).get("sha256")
        == runtime_probe.get("r", {}).get("shared_library_sha256")
    ):
        raise MacOSDeploymentInspectionError(
            "macOS R integration-kit identity is invalid"
        )

    records.sort(key=lambda item: item["path"])
    return {
        "schema_version": 1,
        "target": target,
        "source_commit": source_commit,
        "minimum_macos": minimum_macos,
        "stack": versions,
        "r_integration_kit": {
            "path": "Contents/Resources/r-integration-kit/manifest.json",
            "sha256": sha256_file(kit_manifest_path),
            "kit_sha256": kit_manifest["kit_sha256"],
            "derivation_sha256": sha256_file(derivation_path),
        },
        "qt_dependency_collector": "PyInstaller",
        "architecture": architecture,
        "app_bundle": {
            "bundle_identifier": info["CFBundleIdentifier"],
            "executable": "Contents/MacOS/RCMetaStudio",
            "normal_entry_point": True,
            "codesign": codesign,
            "hardened_runtime_signing_compatible": codesign["runtime"],
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


def finalize_smoke_evidence(
    path: Path, log_path: Path, launchservices_marker: Path | None = None
) -> dict:
    evidence = json.loads(path.read_text(encoding="utf-8"))
    if evidence.get("failures") or evidence.get("surface_progress"):
        raise MacOSDeploymentInspectionError(
            "packaged automation contains failed native observations"
        )
    if "packaged-workflow:post-close" not in log_path.read_text(encoding="utf-8"):
        raise MacOSDeploymentInspectionError(
            "packaged automation did not emit its post-close marker"
        )
    if launchservices_marker is not None:
        marker = json.loads(launchservices_marker.read_text(encoding="utf-8"))
        if (
            marker.get("schema_version") != 1
            or marker.get("platform_plugin") != "cocoa"
            or marker.get("project") != "amino.rcms"
            or marker.get("post_close") is not True
            or not isinstance(marker.get("pid"), int)
        ):
            raise MacOSDeploymentInspectionError(
                "normal LaunchServices app entry did not produce its completion marker"
            )
    evidence["execution"] = {
        "automation_exit_code": 0,
        "positional_user_entry_exit_code": 0,
        "scale_exit_codes": {"1.25": 0, "1.50": 0, "1.75": 0},
        "post_close_marker": True,
        "launchservices_completion_marker": launchservices_marker is not None,
        "clean_exit": True,
    }
    path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return evidence


def inspect_archive(
    archive: Path,
    *,
    archive_root_name: str,
    embedded_files: dict[str, Path],
    target: str = "macos-x64",
) -> dict:
    validate_archive_root_name(archive_root_name)
    prefix = archive_root_name + "/"
    with zipfile.ZipFile(archive) as bundle:
        infos = bundle.infolist()
        if len(infos) > MAX_ARCHIVE_MEMBERS:
            raise MacOSDeploymentInspectionError("ZIP exceeds the member-count bound")
        total_uncompressed = sum(item.file_size for item in infos)
        if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise MacOSDeploymentInspectionError(
                "ZIP exceeds the uncompressed-byte bound"
            )
        names = [item.filename for item in infos if not item.is_dir()]
        folded: dict[str, str] = {}
        for info in infos:
            name = info.filename
            if info.flag_bits & 0x1:
                raise MacOSDeploymentInspectionError(
                    f"ZIP contains an encrypted member: {name}"
                )
            if (
                "\\" in name
                or name.startswith("/")
                or unicodedata.normalize("NFC", name) != name
                or not name.startswith(prefix)
            ):
                raise MacOSDeploymentInspectionError(
                    f"ZIP contains a non-normalized member: {name}"
                )
            relative = name[len(prefix) :].rstrip("/")
            if name != prefix and (
                not relative
                or any(part in {"", ".", ".."} for part in relative.split("/"))
            ):
                raise MacOSDeploymentInspectionError(
                    f"ZIP contains traversal or empty components: {name}"
                )
            key = name.casefold()
            if key in folded:
                raise MacOSDeploymentInspectionError(
                    f"ZIP contains duplicate/case-colliding members: {folded[key]}, {name}"
                )
            folded[key] = name
            unix_mode = info.external_attr >> 16
            if info.is_dir():
                if unix_mode and not stat.S_ISDIR(unix_mode):
                    raise MacOSDeploymentInspectionError(
                        f"ZIP directory has a non-directory mode: {name}"
                    )
            elif not (stat.S_ISREG(unix_mode) or stat.S_ISLNK(unix_mode)):
                raise MacOSDeploymentInspectionError(
                    f"ZIP member has an unsafe file mode: {name}"
                )
        embedded_hashes = {}
        for relative, source in embedded_files.items():
            member = prefix + relative
            if member not in names or bundle.read(member) != source.read_bytes():
                raise MacOSDeploymentInspectionError(
                    f"ZIP qualification input is missing or changed: {member}"
                )
            embedded_hashes[relative] = hashlib.sha256(bundle.read(member)).hexdigest()
        manifest_path = embedded_files.get("qualification/deployment-manifest.json")
        signing_path = embedded_files.get("qualification/ad-hoc-signing-inventory.json")
        if manifest_path is None or signing_path is None:
            raise MacOSDeploymentInspectionError(
                "ZIP inspection requires deployment and signing inventories"
            )
        if manifest_path is not None:
            deployment = json.loads(manifest_path.read_text(encoding="utf-8"))
            if deployment.get("target") != target:
                raise MacOSDeploymentInspectionError(
                    "deployment manifest target differs from the archive target"
                )
            records = deployment.get("inventory", {}).get("files", [])
            if not isinstance(records, list) or not records:
                raise MacOSDeploymentInspectionError(
                    "deployment manifest has no archive inventory"
                )
            app_prefix = prefix + "RCMetaStudio.app/"
            app_members = {
                name[len(app_prefix) :] for name in names if name.startswith(app_prefix)
            }
            expected_members = {record.get("path") for record in records}
            if app_members != expected_members:
                raise MacOSDeploymentInspectionError(
                    "ZIP app members differ from the inspected inventory"
                )
            info_by_name = {item.filename: item for item in bundle.infolist()}
            for record in records:
                member = app_prefix + record["path"]
                info = info_by_name[member]
                mode = info.external_attr >> 16
                if record.get("kind") == "symlink":
                    payload = bundle.read(member)
                    if (
                        not stat.S_ISLNK(mode)
                        or stat.S_IMODE(mode) != record.get("mode")
                        or payload.decode("utf-8") != record.get("link_target")
                    ):
                        raise MacOSDeploymentInspectionError(
                            f"ZIP symlink differs from inventory: {member}"
                        )
                else:
                    digest = hashlib.sha256()
                    size = 0
                    with bundle.open(member) as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            size += len(chunk)
                            digest.update(chunk)
                    if (
                        stat.S_ISLNK(mode)
                        or size != record.get("size")
                        or stat.S_IMODE(mode) != record.get("mode")
                        or digest.hexdigest() != record.get("sha256")
                    ):
                        raise MacOSDeploymentInspectionError(
                            f"ZIP file differs from inventory: {member}"
                        )
            signing = validate_signing_inventory(
                json.loads(signing_path.read_text(encoding="utf-8")),
                native_paths={
                    record["path"] for record in records if "architectures" in record
                },
            )
            signing_record = deployment.get("signing_inventory", {})
            signing_sha256 = sha256_file(signing_path)
            if (
                signing_record.get("path")
                != "qualification/ad-hoc-signing-inventory.json"
                or signing_record.get("sha256") != signing_sha256
                or signing_record.get("identity") != signing["identity"]
                or signing_record.get("native_files") != signing["native_files"]
                or signing_record.get("nested_bundles") != signing["nested_bundles"]
            ):
                raise MacOSDeploymentInspectionError(
                    "deployment manifest does not authenticate the signing inventory"
                )
            if deployment.get("target") in TARGET_CONTRACTS:
                validate_r_framework_inventory(records)
            for relative in signing["nested_bundles"]:
                bundle_prefix = (
                    prefix + "RCMetaStudio.app/" + relative.rstrip("/") + "/"
                )
                if not any(name.startswith(bundle_prefix) for name in names):
                    raise MacOSDeploymentInspectionError(
                        "ZIP signing inventory names a missing nested bundle"
                    )
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


def validate_macos_surface_records(scales: object) -> None:
    if not isinstance(scales, list) or not all(
        isinstance(item, dict) for item in scales
    ):
        raise MacOSDeploymentInspectionError("macOS surface scales are incomplete")
    typed_scales = cast(list[dict[str, Any]], scales)
    if [item.get("requested") for item in typed_scales] != ["1.25", "1.50", "1.75"]:
        raise MacOSDeploymentInspectionError("macOS surface scales are incomplete")
    for item in typed_scales:
        menu = item.get("native_menu", {})
        file_dialog = item.get("native_file_dialog", {})
        critical_dialog = item.get("critical_dialog", {})
        cleanup = item.get("cleanup", {})
        accessibility = item.get("accessibility", {})
        native_accessibility = accessibility.get("native", {})
        if not (
            item.get("platform_plugin") == "cocoa"
            and all(item.get(key) is True for key in ("clipboard", "binary_resources"))
            and menu.get("is_native") is True
            and int(menu.get("menu_count", 0)) >= 1
            and int(menu.get("action_count", 0)) >= 1
            and file_dialog.get("dont_use_native_dialog") is False
            and file_dialog.get("window_modality") == "WindowModal"
            and file_dialog.get("visible_before_cancel") is True
            and file_dialog.get("cancel_requested") is True
            and file_dialog.get("finished_signal") is True
            and file_dialog.get("rejected_signal") is True
            and file_dialog.get("result") == file_dialog.get("rejected_value") == 0
            and file_dialog.get("timed_out") is False
            and file_dialog.get("timeout_ms") == 10_000
            and critical_dialog.get("dont_use_native_dialog") is False
            and critical_dialog.get("application_dont_use_native_dialogs") is False
            and critical_dialog.get("dont_show_on_screen_before_show") is False
            and critical_dialog.get("dont_show_on_screen_after_show") is True
            and critical_dialog.get("native_helper_active") is True
            and critical_dialog.get("window_modality") == "WindowModal"
            and critical_dialog.get("visible_before_close") is True
            and critical_dialog.get("critical_icon") is True
            and critical_dialog.get("finished_signal") is True
            and critical_dialog.get("result")
            == critical_dialog.get("accepted_value")
            == 1
            and critical_dialog.get("timed_out") is False
            and critical_dialog.get("timeout_ms") == 5_000
            and accessibility.get("focus_before") == "packagedAccessibilityControl"
            and accessibility.get("focus_after_tab")
            == "packagedKeyboardTraversalTarget"
            and accessibility.get("accessible_name") == "Packaged accessibility control"
            and accessibility.get("accessible_description")
            == "Verifies packaged Qt accessibility metadata."
            and native_accessibility.get("is_ignored") is False
            and native_accessibility.get("exposed") is True
            and native_accessibility.get("role") == "AXButton"
            and native_accessibility.get("title") == "Packaged accessibility control"
            and native_accessibility.get("description")
            == "Verifies packaged Qt accessibility metadata."
            and native_accessibility.get("source") == "accessibility-tree"
            and native_accessibility.get("bridge")
            == "accessibilityAttributeValue:AXChildren"
            and native_accessibility.get("bridge_supported") is True
            and int(native_accessibility.get("root_count", 0)) >= 1
            and cleanup.get("close_accepted") is True
            and cleanup.get("window_visible") is False
            and item.get("available_styles")
            and item.get("active_style")
            and item.get("tls_backends")
            and {"jpeg", "svg"} <= set(item.get("image_formats", []))
            and abs(
                float(item.get("qt_scale_factor", 0)) - float(item.get("requested", -1))
            )
            < 1e-9
            and float(item.get("baseline_device_pixel_ratio", 0)) > 0
            and abs(
                float(item.get("expected_device_pixel_ratio", 0))
                - float(item.get("baseline_device_pixel_ratio", 0))
                * float(item.get("requested", -1))
            )
            < 1e-9
            and abs(
                float(item.get("device_pixel_ratio", 0))
                - float(item.get("expected_device_pixel_ratio", -1))
            )
            <= float(item.get("dpr_tolerance", -1))
        ):
            raise MacOSDeploymentInspectionError(
                f"macOS packaged surface evidence is incomplete at {item.get('requested')}"
            )


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
    r_integration_kit_manifest: Path,
    launchservices_marker: Path,
    archive_inspection: Path,
    signing_inventory: Path,
    output: Path,
    target: str = "macos-x64",
) -> dict:
    contract = TARGET_CONTRACTS[target]
    architecture = contract["architecture"]
    deployment = json.loads(deployment_manifest.read_text(encoding="utf-8"))
    profile = json.loads(r_runtime_profile.read_text(encoding="utf-8"))
    expected_profile_paths = [
        "library/grDevices/libs/cairo.so",
        "library/tcltk",
        "modules/R_X11.so",
        "modules/R_de.so",
    ]
    if not (
        profile.get("schema_version") == 1
        and profile.get("policy")
        == "official-cran-r-with-optional-x11-tcl-surfaces-removed"
        and profile.get("hard_dependency_fields") == ["Depends", "Imports", "LinkingTo"]
        and _valid_sha256(profile.get("dependency_manifest", {}).get("sha256"))
        and "tcltk"
        not in {
            str(name).casefold() for name in profile.get("hard_dependency_closure", [])
        }
        and profile.get("source_framework", {}).get("version") == EXPECTED_VERSIONS["r"]
        and profile.get("source_framework", {}).get("expected_architecture")
        == architecture
        and profile.get("source_framework", {})
        .get("canonical_macho", {})
        .get("relative_path")
        == "lib/libR.dylib"
        and profile.get("source_framework", {})
        .get("canonical_macho", {})
        .get("architectures")
        == [architecture]
        and profile.get("source_framework", {})
        .get("executable_macho", {})
        .get("relative_path")
        == "bin/exec/R"
        and profile.get("source_framework", {})
        .get("executable_macho", {})
        .get("architectures")
        == [architecture]
        and profile.get("source_framework", {}).get("launcher", {}).get("relative_path")
        == "bin/R"
        and profile.get("source_framework", {}).get("launcher", {}).get("kind")
        == "script"
        and _valid_sha256(
            profile.get("source_framework", {}).get("launcher", {}).get("sha256")
        )
        and _valid_sha256(
            profile.get("source_framework", {}).get("source_tree_identity_sha256")
        )
        and _valid_sha256(
            profile.get("source_framework", {}).get("pre_profile_tree_identity_sha256")
        )
        and profile.get("post_profile_exclusions") == expected_profile_paths
        and [
            entry.get("relative_path") for entry in profile.get("excluded_surfaces", [])
        ]
        == [
            "library/tcltk",
            "modules/R_X11.so",
            "modules/R_de.so",
            "library/grDevices/libs/cairo.so",
        ]
    ):
        raise MacOSDeploymentInspectionError(
            "embedded R profile evidence is incomplete"
        )
    smoke = json.loads(smoke_evidence.read_text(encoding="utf-8"))
    archive_report = json.loads(archive_inspection.read_text(encoding="utf-8"))
    workflows = smoke.get("workflows", {})
    scales = smoke.get("scales", [])
    log_text = smoke_log.read_text(encoding="utf-8")
    required_markers = {
        "packaged-runtime-probe:passed",
        "packaged-workflow:shell-created",
        "packaged-workflow:paint:complete",
        "packaged-workflow:project-exercise:complete",
        "packaged-workflow:evidence-written",
        "packaged-workflow:post-close",
        "startup-project:normal-entry-point-passed",
        "packaged-surface:scale-1.25-passed",
        "packaged-surface:scale-1.50-passed",
        "packaged-surface:scale-1.75-passed",
    }
    expected_embedded = {
        "qualification/deployment-manifest.json": sha256_file(deployment_manifest),
        "qualification/ad-hoc-signing-inventory.json": sha256_file(signing_inventory),
        "qualification/runtime-probe.json": sha256_file(runtime_probe),
        "qualification/embedded-r-runtime-profile.json": sha256_file(r_runtime_profile),
        "qualification/r-integration-kit-manifest.json": sha256_file(
            r_integration_kit_manifest
        ),
        "qualification/packaged-smoke.json": sha256_file(smoke_evidence),
        "qualification/packaged-smoke.log": sha256_file(smoke_log),
        "qualification/launchservices-completion.json": sha256_file(
            launchservices_marker
        ),
        "qualification/packaged-smoke.stdout.log": sha256_file(smoke_stdout),
        "qualification/packaged-smoke.stderr.log": sha256_file(smoke_stderr),
        "qualification/packaged-smoke.hang-trace.log": sha256_file(hang_trace),
    }
    validate_macos_surface_records(scales)
    locale_variants = workflows.get("locale_variants", [])
    if not (
        deployment.get("target") == target
        and deployment.get("stack") == EXPECTED_VERSIONS
        and deployment.get("architecture") == architecture
        and deployment.get("qt_dependency_collector") == "PyInstaller"
        and deployment.get("signing_inventory", {}).get("path")
        == "qualification/ad-hoc-signing-inventory.json"
        and deployment.get("signing_inventory", {}).get("sha256")
        == sha256_file(signing_inventory)
        and smoke.get("passed") is True
        and not smoke.get("failures")
        and not smoke.get("surface_progress")
        and all(
            workflows.get(key) is True
            for key in (
                "automation_entry_point",
                "representative_edit",
                "real_r_analysis",
                "result_text",
                "save_reopen",
                "analysis_after_reopen",
            )
        )
        and workflows.get("converted_sample") == "amino.rcms"
        and workflows.get("expected_normalized_summary_sha256")
        == EXPECTED_SUMMARY_SHA256
        and workflows.get("normalized_summary_sha256") == EXPECTED_SUMMARY_SHA256
        and _valid_sha256(workflows.get("raw_summary_sha256"))
        and _valid_sha256_map(workflows.get("svg_sha256"))
        and [item.get("locale") for item in locale_variants] == ["en_US", "de_DE"]
        and all(
            item.get("normalized_summary_sha256") == EXPECTED_SUMMARY_SHA256
            and item.get("raw_summary_sha256") == workflows.get("raw_summary_sha256")
            for item in locale_variants
        )
        and smoke.get("execution", {}).get("clean_exit") is True
        and smoke.get("execution", {}).get("launchservices_completion_marker") is True
        and required_markers <= set(log_text.splitlines())
        and archive_report.get("target") == target
        and archive_report.get("archive_sha256") == sha256_file(archive)
        and archive_report.get("embedded_sha256") == expected_embedded
    ):
        raise MacOSDeploymentInspectionError(
            "macOS packaged qualification evidence is incomplete"
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
        "r_integration_kit": {
            "path": r_integration_kit_manifest.name,
            "sha256": sha256_file(r_integration_kit_manifest),
            "kit_sha256": json.loads(
                r_integration_kit_manifest.read_text(encoding="utf-8")
            )["kit_sha256"],
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


def main() -> int:
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
        "--target", choices=sorted(TARGET_CONTRACTS), default="macos-x64"
    )
    for name in EXPECTED_VERSIONS:
        inspect.add_argument(
            f"--{name.replace('_', '-')}-version", dest=f"{name}_version", required=True
        )
    finalize = commands.add_parser("finalize-smoke")
    finalize.add_argument("--smoke-evidence", type=Path, required=True)
    finalize.add_argument("--smoke-log", type=Path, required=True)
    finalize.add_argument("--launchservices-marker", type=Path)
    archive = commands.add_parser("archive")
    archive.add_argument("--archive", type=Path, required=True)
    archive.add_argument("--archive-root-name", required=True)
    archive.add_argument(
        "--target", choices=sorted(TARGET_CONTRACTS), default="macos-x64"
    )
    for name in (
        "deployment_manifest",
        "runtime_probe",
        "smoke_evidence",
        "smoke_log",
        "smoke_stdout",
        "smoke_stderr",
        "hang_trace",
        "launchservices_marker",
        "signing_inventory",
        "r_runtime_profile",
        "r_integration_kit_manifest",
    ):
        archive.add_argument(f"--{name.replace('_', '-')}", type=Path, required=True)
    archive.add_argument("--output", type=Path, required=True)
    evidence = commands.add_parser("evidence")
    evidence.add_argument(
        "--target", choices=sorted(TARGET_CONTRACTS), default="macos-x64"
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
        "r_integration_kit_manifest",
        "output",
    ):
        evidence.add_argument(f"--{name.replace('_', '-')}", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "validate-root":
            validate_archive_root_name(args.archive_root_name)
        elif args.command == "inspect":
            versions = {
                name: getattr(args, f"{name}_version") for name in EXPECTED_VERSIONS
            }
            result = inspect_deployment(
                args.app_root,
                versions=versions,
                source_commit=args.source_commit,
                runtime_probe=json.loads(
                    args.runtime_probe.read_text(encoding="utf-8")
                ),
                locked_qt_root=args.locked_qt_root,
                signing_inventory_path=args.signing_inventory,
                target=args.target,
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        elif args.command == "finalize-smoke":
            finalize_smoke_evidence(
                args.smoke_evidence, args.smoke_log, args.launchservices_marker
            )
        elif args.command == "archive":
            result = inspect_archive(
                args.archive,
                archive_root_name=args.archive_root_name,
                target=args.target,
                embedded_files={
                    "qualification/deployment-manifest.json": args.deployment_manifest,
                    "qualification/ad-hoc-signing-inventory.json": args.signing_inventory,
                    "qualification/runtime-probe.json": args.runtime_probe,
                    "qualification/embedded-r-runtime-profile.json": args.r_runtime_profile,
                    "qualification/r-integration-kit-manifest.json": args.r_integration_kit_manifest,
                    "qualification/packaged-smoke.json": args.smoke_evidence,
                    "qualification/packaged-smoke.log": args.smoke_log,
                    "qualification/packaged-smoke.stdout.log": args.smoke_stdout,
                    "qualification/packaged-smoke.stderr.log": args.smoke_stderr,
                    "qualification/packaged-smoke.hang-trace.log": args.hang_trace,
                    "qualification/launchservices-completion.json": args.launchservices_marker,
                },
            )
            args.output.write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        else:
            write_qualification_evidence(
                target=args.target,
                **{
                    name: getattr(args, name)
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
                        "output",
                        "r_runtime_profile",
                        "r_integration_kit_manifest",
                    )
                },
            )
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
