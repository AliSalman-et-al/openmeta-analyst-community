#!/usr/bin/env python3
"""Build, verify, and consume immutable target-native R/rpy2 integration kits."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any, cast
from urllib.parse import urlparse


SCHEMA_VERSION = 1
R_VERSION = "4.6.1"
RPY2_VERSION = "3.6.7"
RPY2_RINTERFACE_VERSION = "3.6.6"
RPY2_ROBJECTS_VERSION = "3.6.5"
PYTHON_VERSION = "3.11.9"
TARGETS = {
    "windows-x64": ("Windows", "x86_64", None),
    "macos-arm64": ("Darwin", "arm64", "14.0"),
}
OFFICIAL_R_URLS = {
    "windows-x64": "https://cloud.r-project.org/bin/windows/base/R-4.6.1-win.exe",
    "macos-arm64": "https://cloud.r-project.org/bin/macosx/sonoma-arm64/base/R-4.6.1-arm64.pkg",
}
WINDOWS_R_SHA256 = "c5424c40cd70ef85765a55d2ff96bb602b5f30ed536938ff004f14db5db3c2df"
WINDOWS_R_SIGNER_SUBJECT = "CN=Martyn Plummer, O=Martyn Plummer, S=West Midlands, C=GB"
WINDOWS_R_SIGNER_THUMBPRINT = "f356fc6cd245d722f4a82697473da5995cb42975"
PPM_CONTRIB_PATHS = {
    "windows-x64": "bin/windows/contrib/4.6",
    "macos-arm64": "bin/macosx/sonoma-arm64/contrib/4.6",
}
PPM_REPOSITORY = "https://packagemanager.posit.co/cran/2026-07-16"
WINDOWS_SYSTEM_DLLS = {
    "advapi32.dll",
    "bcrypt.dll",
    "cfgmgr32.dll",
    "comctl32.dll",
    "comdlg32.dll",
    "crypt32.dll",
    "cryptbase.dll",
    "dnsapi.dll",
    "dwmapi.dll",
    "gdi32.dll",
    "imm32.dll",
    "iphlpapi.dll",
    "kernel32.dll",
    "msvcrt.dll",
    "ncrypt.dll",
    "netapi32.dll",
    "normaliz.dll",
    "ntdll.dll",
    "ole32.dll",
    "oleaut32.dll",
    "powrprof.dll",
    "propsys.dll",
    "psapi.dll",
    "rpcrt4.dll",
    "secur32.dll",
    "setupapi.dll",
    "shell32.dll",
    "shlwapi.dll",
    "ucrtbase.dll",
    "user32.dll",
    "userenv.dll",
    "version.dll",
    "winhttp.dll",
    "wininet.dll",
    "winmm.dll",
    "wldap32.dll",
    "ws2_32.dll",
}
FORBIDDEN_NATIVE_PREFIXES = (
    "/opt/x11/",
    "/opt/r/",
    "/opt/homebrew/",
    "/usr/local/",
    "/users/",
    "/private/tmp/",
    "/tmp/",
    "c:\\users\\",
    "c:\\build\\",
    "c:\\conda\\",
)


class KitError(RuntimeError):
    """Raised when an integration kit violates its immutable contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            records.append(
                {"path": relative, "kind": "symlink", "target": os.readlink(path)}
            )
        elif path.is_file():
            records.append(
                {
                    "path": relative,
                    "kind": "file",
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return records


def canonical_digest(manifest: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in manifest.items() if key != "kit_sha256"}
    payload = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _macos_version(value: str) -> tuple[int, int, int]:
    try:
        parts = tuple(int(part) for part in value.split("."))
    except ValueError as exc:
        raise KitError(f"invalid macOS deployment version: {value}") from exc
    if not 1 <= len(parts) <= 3 or any(part < 0 for part in parts):
        raise KitError(f"invalid macOS deployment version: {value}")
    padded = (*parts, *(0 for _ in range(3 - len(parts))))
    return padded[0], padded[1], padded[2]


def _verified_https(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username


def _declares_license_file(value: object) -> bool:
    normalized = " ".join(str(value).casefold().split())
    return "file license" in normalized or "file licence" in normalized


def _valid_license_files(value: object, *, declared_license: object) -> bool:
    if not isinstance(value, list):
        return False
    records: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            return False
        record = cast(dict[str, Any], item)
        path = record.get("path")
        if not (
            isinstance(path, str)
            and path
            and not Path(path).is_absolute()
            and ".." not in Path(path).parts
            and _valid_sha256(record.get("sha256"))
        ):
            return False
        records.append(record)
    return not _declares_license_file(declared_license) or any(
        Path(record["path"]).name.casefold() in {"license", "licence"}
        for record in records
    )


def _valid_official_r(record: dict[str, Any], target: str) -> bool:
    if record.get("url") != OFFICIAL_R_URLS[target]:
        return False
    if target == "windows-x64":
        return (
            record.get("sha256") == WINDOWS_R_SHA256
            and record.get("signature_identity") == WINDOWS_R_SIGNER_SUBJECT
            and str(record.get("signer_thumbprint", "")).casefold()
            == WINDOWS_R_SIGNER_THUMBPRINT
            and record.get("signature_status") == "Valid"
            and record.get("timestamped") is True
            and record.get("artifact_type") == "installer"
        )
    return (
        _valid_sha256(record.get("sha256"))
        and "VZLD955F6P" in str(record.get("signature_identity"))
        and record.get("artifact_type") == "pkg"
    )


def load_provenance(path: Path, target: str, bridge: Path) -> dict[str, Any]:
    provenance = json.loads(path.read_text(encoding="utf-8"))
    official_r = provenance.get("official_r", {})
    ppm = provenance.get("ppm_packages", [])
    source_packages = provenance.get("source_packages", [])
    rpy2 = provenance.get("rpy2", {})
    rpy2_archives = rpy2.get("source_archives", [])
    if not (
        provenance.get("schema_version") == 1
        and provenance.get("target") == target
        and _valid_official_r(official_r, target)
        and isinstance(ppm, list)
        and ppm
        and isinstance(source_packages, list)
        and source_packages
        and rpy2.get("version") == RPY2_VERSION
        and rpy2.get("sdist_distribution") == "rpy2-rinterface"
        and rpy2.get("sdist_version") == RPY2_RINTERFACE_VERSION
        and rpy2.get("robjects_version") == RPY2_ROBJECTS_VERSION
        and _verified_https(rpy2.get("sdist_url"))
        and urlparse(str(rpy2.get("sdist_url"))).hostname == "files.pythonhosted.org"
        and _valid_sha256(rpy2.get("sdist_sha256"))
        and _valid_sha256(rpy2.get("build_log_sha256"))
        and rpy2.get("toolchain")
        and rpy2.get("license")
        and isinstance(rpy2_archives, list)
        and rpy2.get("bridge_sha256") == sha256_file(bridge)
    ):
        raise KitError("integration-kit provenance manifest is incomplete or invalid")
    expected_rpy2_archives = {
        "rpy2": "3.6.7",
        "rpy2-rinterface": RPY2_RINTERFACE_VERSION,
        "rpy2-robjects": RPY2_ROBJECTS_VERSION,
    }
    if {
        str(record.get("distribution")): str(record.get("version"))
        for record in rpy2_archives
        if isinstance(record, dict)
    } != expected_rpy2_archives:
        raise KitError("rpy2 split source archive provenance is incomplete")
    for record in rpy2_archives:
        if not (
            _verified_https(record.get("url"))
            and urlparse(str(record.get("url"))).hostname == "files.pythonhosted.org"
            and _valid_sha256(record.get("sha256"))
            and _valid_license_files(
                record.get("license_files"), declared_license="file LICENSE"
            )
        ):
            raise KitError("rpy2 split source archive license provenance is invalid")
    rinterface_archive = next(
        record
        for record in rpy2_archives
        if record.get("distribution") == "rpy2-rinterface"
    )
    if rpy2.get("sdist_url") != rinterface_archive.get("url") or rpy2.get(
        "sdist_sha256"
    ) != rinterface_archive.get("sha256"):
        raise KitError("rpy2 API bridge source differs from retained rinterface sdist")
    for record in ppm:
        if not (
            record.get("name")
            and record.get("version")
            and record.get("package_type") in {"win.binary", "mac.binary"}
            and str(record.get("url", "")).startswith(
                f"{PPM_REPOSITORY}/{PPM_CONTRIB_PATHS[target]}/"
            )
            and _valid_sha256(record.get("sha256"))
            and _valid_license_files(
                record.get("license_files"), declared_license=record.get("license")
            )
            and record.get("license")
            and record.get("license") != "unknown"
        ):
            raise KitError("PPM archive provenance is incomplete or invalid")
    source_names = {record.get("name") for record in source_packages}
    if "RCMetaR" not in source_names:
        raise KitError("RCMetaR source provenance is required")
    for record in source_packages:
        if not (
            _verified_https(record.get("url"))
            and _valid_sha256(record.get("sha256"))
            and _valid_sha256(record.get("build_log_sha256"))
            and record.get("toolchain")
            and record.get("package_type") == "source"
            and record.get("version")
            and record.get("license")
        ):
            raise KitError("source-package provenance is incomplete or invalid")
    return provenance


def installed_package_inventory(library: Path) -> list[dict[str, str]]:
    packages: list[dict[str, str]] = []
    for package in sorted(item for item in library.iterdir() if item.is_dir()):
        description = package / "DESCRIPTION"
        if not description.is_file():
            continue
        fields: dict[str, str] = {}
        active: str | None = None
        for line in description.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            if line[:1].isspace() and active:
                fields[active] += " " + line.strip()
            elif ":" in line:
                active, value = line.split(":", 1)
                fields[active] = value.strip()
            else:
                active = None
        package_payload = json.dumps(
            files(package), sort_keys=True, separators=(",", ":")
        ).encode()
        packages.append(
            {
                "name": fields.get("Package", package.name),
                "version": fields.get("Version", "unknown"),
                "license": fields.get("License", "unknown"),
                "priority": fields.get("Priority", ""),
                "installed_content_sha256": hashlib.sha256(package_payload).hexdigest(),
            }
        )
    return packages


def validate_installed_provenance(
    installed: list[dict[str, str]], provenance: dict[str, Any]
) -> None:
    claims = provenance["ppm_packages"] + provenance["source_packages"]
    by_name: dict[str, dict[str, Any]] = {}
    for record in claims:
        name = str(record["name"])
        if name in by_name:
            raise KitError(f"package provenance contains duplicate identity: {name}")
        by_name[name] = record
    installed_by_name = {record["name"]: record for record in installed}
    for name, claim in by_name.items():
        observed = installed_by_name.get(name)
        if observed is None or observed["version"] != claim["version"]:
            raise KitError(
                f"installed package differs from provenance: {name}={observed and observed['version']}"
            )
    unclaimed = sorted(
        record["name"]
        for record in installed
        if record.get("priority") not in {"base", "recommended"}
        and record["name"] not in by_name
    )
    if unclaimed:
        raise KitError(
            "installed package lacks exact provenance: " + ", ".join(unclaimed)
        )


def copy_source_payload(
    source_root: Path, provenance: dict[str, Any], destination: Path
) -> list[dict[str, str]]:
    claims = [
        {
            "name": record["name"],
            "version": record["version"],
            "sha256": record["sha256"],
        }
        for record in provenance["source_packages"]
        if record.get("name") == "RCMetaR"
    ]
    claims.extend(
        {
            "name": record["distribution"],
            "version": record["version"],
            "sha256": record["sha256"],
        }
        for record in provenance["rpy2"]["source_archives"]
    )
    candidates = [path for path in source_root.iterdir() if path.is_file()]
    by_hash: dict[str, list[Path]] = {}
    for path in candidates:
        by_hash.setdefault(sha256_file(path), []).append(path)
    if len(candidates) != len(claims):
        raise KitError("source payload must contain exactly the retained archives")
    destination.mkdir()
    records = []
    for claim in claims:
        matches = by_hash.get(str(claim["sha256"]), [])
        if len(matches) != 1:
            raise KitError(f"source payload is missing or ambiguous: {claim['name']}")
        source = matches[0]
        target = destination / source.name
        if target.exists():
            raise KitError(f"source payload filename collision: {source.name}")
        shutil.copy2(source, target)
        records.append(
            {
                "name": str(claim["name"]),
                "version": str(claim["version"]),
                "path": f"source-archives/{target.name}",
                "sha256": str(claim["sha256"]),
            }
        )
    return sorted(records, key=lambda record: record["name"])


def copy_license_inventory(runtime: Path, library: Path, destination: Path) -> None:
    """Retain redistributable license texts beside immutable source evidence."""
    destination.mkdir()
    candidates = ("COPYRIGHTS", "COPYING", "COPYING.LIB", "LICENSE", "LICENCE")
    for runtime_root in (runtime, runtime / "Resources"):
        for name in candidates:
            source = runtime_root / name
            if source.is_file():
                shutil.copy2(source, destination / f"R-{name}")
    for package in sorted(item for item in library.iterdir() if item.is_dir()):
        for name in candidates:
            source = package / name
            if source.is_file():
                package_destination = destination / package.name
                package_destination.mkdir(exist_ok=True)
                shutil.copy2(source, package_destination / name)
    if not any(path.name.startswith("R-") for path in destination.iterdir()):
        raise KitError("bundled R runtime does not carry its license payload")
    python_licenses = destination / "python"
    copied_python_licenses = 0
    for distribution_name in ("rpy2", "rpy2-rinterface", "rpy2-robjects"):
        distribution = importlib.metadata.distribution(distribution_name)
        candidates = [
            item
            for item in (distribution.files or [])
            if Path(str(item)).name.casefold() in {"license", "licence", "copying"}
        ]
        if not candidates:
            continue
        target = python_licenses / distribution_name
        target.mkdir(parents=True)
        for item in candidates:
            source = Path(str(distribution.locate_file(item)))
            if not source.is_file():
                raise KitError(
                    f"{distribution_name} license payload is missing: {item}"
                )
            shutil.copy2(source, target / source.name)
            copied_python_licenses += 1
    if not copied_python_licenses:
        raise KitError("rpy2 distributions do not carry a license payload")


def require_api_bridge(path: Path) -> None:
    name = path.name.lower()
    if "_rinterface_cffi_api" not in name or "_rinterface_cffi_abi" in name:
        raise KitError(f"rpy2 bridge must be API-only: {path}")
    if not path.is_file():
        raise KitError(f"rpy2 API bridge is missing: {path}")


def relocate_macos_api_bridge(output: Path, bridge: Path) -> None:
    completed = subprocess.run(
        ["otool", "-L", str(bridge)], capture_output=True, text=True, check=True
    )
    for dependency in [
        line.strip().split(" (", 1)[0] for line in completed.stdout.splitlines()[1:]
    ]:
        if "/R.framework/" not in dependency:
            continue
        if dependency.endswith("/R"):
            target = output / "runtime" / "R"
        elif "/Resources/" in dependency:
            suffix = dependency.split("/Resources/", 1)[1]
            target = output / "runtime" / "Resources" / suffix
        else:
            raise KitError(f"unsupported rpy2 R framework dependency: {dependency}")
        if not target.exists():
            raise KitError(
                f"rpy2 API bridge dependency is absent from kit runtime: {target}"
            )
        replacement = "@loader_path/" + os.path.relpath(
            target.resolve(), bridge.parent.resolve()
        )
        subprocess.run(
            ["install_name_tool", "-change", dependency, replacement, str(bridge)],
            check=True,
        )


def _owner(relative: str) -> str:
    return relative.split("/", 1)[0]


def _windows_system_import(name: str) -> bool:
    lowered = name.casefold()
    return (
        lowered in WINDOWS_SYSTEM_DLLS
        or lowered.startswith("api-ms-win-")
        or lowered.startswith("ext-ms-win-")
    )


def _macos_metadata(path: Path) -> tuple[str | None, list[str], str | None, str]:
    install_id_output = subprocess.run(
        ["otool", "-D", str(path)], capture_output=True, text=True, check=False
    )
    install_id_lines = install_id_output.stdout.splitlines()[1:]
    install_id = install_id_lines[0].strip() if install_id_lines else None
    load = subprocess.run(
        ["otool", "-l", str(path)], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    rpaths: list[str] = []
    minimum_os: str | None = None
    for index, line in enumerate(load):
        stripped = line.strip()
        if stripped == "cmd LC_RPATH" and index + 2 < len(load):
            value = load[index + 2].strip()
            if value.startswith("path "):
                rpaths.append(value[5:].split(" (offset", 1)[0])
        if stripped in {"cmd LC_BUILD_VERSION", "cmd LC_VERSION_MIN_MACOSX"}:
            for candidate in load[index + 1 : index + 8]:
                value = candidate.strip()
                if value.startswith(("minos ", "version ")):
                    minimum_os = value.split()[1]
                    break
    signing = subprocess.run(
        ["codesign", "-dvv", str(path)], capture_output=True, text=True, check=False
    )
    signing_text = signing.stdout + signing.stderr
    identity = next(
        (
            line.split("=", 1)[1]
            for line in signing_text.splitlines()
            if line.startswith("Identifier=")
        ),
        "unsigned",
    )
    return install_id, sorted(set(rpaths)), minimum_os, identity


def _resolve_windows_closure(records: list[dict[str, Any]]) -> None:
    by_name: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_name.setdefault(Path(record["path"]).name.casefold(), []).append(record)
    for record in records:
        resolutions = []
        for import_record in record.pop("_imports"):
            name = import_record["name"]
            if _windows_system_import(name):
                resolutions.append({**import_record, "resolution": "system"})
                continue
            matches = by_name.get(name.casefold(), [])
            if len(matches) != 1:
                raise KitError(
                    f"Windows native import is unresolved or ambiguous: {record['path']} -> {name}"
                )
            resolutions.append(
                {
                    **import_record,
                    "resolution": "kit",
                    "resolved_path": matches[0]["path"],
                    "resolved_sha256": matches[0]["sha256"],
                }
            )
        record["imports"] = resolutions


def _resolve_macos_closure(records: list[dict[str, Any]], root: Path) -> None:
    by_path = {(root / record["path"]).resolve(): record for record in records}
    by_install_id: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if record.get("install_id"):
            by_install_id.setdefault(str(record["install_id"]), []).append(record)
    for record in records:
        loader = (root / record["path"]).resolve().parent
        resolutions = []
        for dependency in record.pop("_imports"):
            lowered = dependency.casefold()
            if lowered.startswith(FORBIDDEN_NATIVE_PREFIXES):
                raise KitError(f"forbidden external Mach-O dependency: {dependency}")
            if dependency.startswith(("/usr/lib/", "/System/Library/")):
                resolutions.append({"name": dependency, "resolution": "system"})
                continue
            candidates: list[dict[str, Any]] = []
            if dependency.startswith("@loader_path/"):
                resolved = (loader / dependency[len("@loader_path/") :]).resolve()
                if resolved in by_path:
                    candidates.append(by_path[resolved])
            elif dependency.startswith("@rpath/"):
                suffix = dependency[len("@rpath/") :]
                for rpath in record.get("rpaths", []):
                    if rpath.startswith("@loader_path/"):
                        resolved = (
                            loader / rpath[len("@loader_path/") :] / suffix
                        ).resolve()
                        if resolved in by_path:
                            candidates.append(by_path[resolved])
                candidates.extend(by_install_id.get(dependency, []))
            else:
                candidates.extend(by_install_id.get(dependency, []))
            unique = {item["path"]: item for item in candidates}
            if len(unique) != 1:
                raise KitError(
                    f"Mach-O dependency is unresolved or ambiguous: {record['path']} -> {dependency}"
                )
            resolved_record = next(iter(unique.values()))
            resolutions.append(
                {
                    "name": dependency,
                    "resolution": "kit",
                    "resolved_path": resolved_record["path"],
                    "resolved_sha256": resolved_record["sha256"],
                }
            )
        record["imports"] = resolutions


def native_dependency_inventory(
    root: Path, target: str, architecture: str
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(
        item for item in root.rglob("*") if item.is_file() and not item.is_symlink()
    ):
        relative = path.relative_to(root).as_posix()
        if relative.startswith("python/uv-cache/"):
            continue
        if target.startswith("windows-") and path.suffix.lower() in {
            ".exe",
            ".dll",
            ".pyd",
        }:
            import pefile

            try:
                pe = pefile.PE(str(path), fast_load=True)
                pe.parse_data_directories(
                    directories=[
                        pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
                        pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"],
                    ]
                )
            except pefile.PEFormatError as exc:
                raise KitError(
                    f"native Windows payload is not valid PE: {relative}"
                ) from exc
            machine = pe.FILE_HEADER.Machine
            if machine != 0x8664:
                raise KitError(
                    f"native Windows payload is not x86_64: {relative}=0x{machine:04x}"
                )
            imports = [
                {"name": entry.dll.decode("ascii", errors="strict"), "kind": "normal"}
                for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])
            ]
            imports.extend(
                {"name": entry.dll.decode("ascii", errors="strict"), "kind": "delay"}
                for entry in getattr(pe, "DIRECTORY_ENTRY_DELAY_IMPORT", [])
            )
            records.append(
                {
                    "path": relative,
                    "owner": _owner(relative),
                    "sha256": sha256_file(path),
                    "architecture": "x86_64",
                    "_imports": sorted(
                        imports, key=lambda item: (item["name"], item["kind"])
                    ),
                }
            )
        elif target.startswith("macos-"):
            from scripts.qt6_macos_feasibility_impl import is_macho_candidate

            if not is_macho_candidate(path):
                continue
            completed = subprocess.run(
                ["otool", "-L", str(path)], capture_output=True, text=True, check=False
            )
            if completed.returncode:
                raise KitError(f"otool could not inspect Mach-O candidate: {relative}")
            archs = subprocess.run(
                ["lipo", "-archs", str(path)],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.split()
            if archs != [architecture]:
                raise KitError(
                    f"native macOS payload is not thin {architecture}: {relative}={archs}"
                )
            imports = [
                line.strip().split(" (", 1)[0]
                for line in completed.stdout.splitlines()[1:]
            ]
            install_id, rpaths, minimum_os, signing_identity = _macos_metadata(path)
            target_minimum = TARGETS[target][2]
            if (
                minimum_os is None
                or target_minimum is None
                or _macos_version(minimum_os) > _macos_version(target_minimum)
            ):
                raise KitError(
                    f"Mach-O deployment target exceeds {TARGETS[target][2]}: {relative}={minimum_os}"
                )
            records.append(
                {
                    "path": relative,
                    "owner": _owner(relative),
                    "sha256": sha256_file(path),
                    "architecture": architecture,
                    "install_id": install_id,
                    "rpaths": rpaths,
                    "minimum_macos": minimum_os,
                    "signing_identity": signing_identity,
                    "_imports": imports,
                }
            )
    if target.startswith("windows-"):
        _resolve_windows_closure(records)
        r_dlls = [
            record
            for record in records
            if Path(record["path"]).name.casefold() == "r.dll"
        ]
        if len(r_dlls) != 1:
            raise KitError("kit must contain exactly one canonical R.dll")
    else:
        _resolve_macos_closure(records, root)
        shared_r = [
            record
            for record in records
            if (
                record["path"].endswith("/lib/libR.dylib")
                or (
                    "/Versions/" in record["path"]
                    and "/Resources/" not in record["path"]
                    and record["path"].endswith("/R")
                )
            )
        ]
        if len({record["sha256"] for record in shared_r}) != 1:
            raise KitError("kit must contain one canonical macOS libR identity")
    return records


def build(args: argparse.Namespace) -> dict[str, Any]:
    target = args.target
    if not _valid_sha256(args.package_lock_sha256):
        raise KitError("package lock SHA256 must be lowercase hexadecimal")
    if not (
        len(args.source_commit) == 40
        and all(character in "0123456789abcdef" for character in args.source_commit)
    ):
        raise KitError("source commit must be a full lowercase Git SHA")
    expected_system, architecture, minimum_os = TARGETS[target]
    if platform.system() != expected_system:
        raise KitError(f"{target} kit must be built natively on {expected_system}")
    observed_machine = platform.machine().lower()
    accepted = {"x86_64": {"x86_64", "amd64"}, "arm64": {"arm64", "aarch64"}}
    if observed_machine not in accepted[architecture]:
        raise KitError(
            f"{target} kit requires {architecture}, found {observed_machine}"
        )
    if platform.python_version() != PYTHON_VERSION:
        raise KitError(
            f"integration kit requires Python {PYTHON_VERSION}, found {platform.python_version()}"
        )
    if importlib.metadata.version("rpy2") != RPY2_VERSION:
        raise KitError(
            "installed rpy2 distribution differs from the integration-kit lock"
        )
    if (
        importlib.metadata.version("rpy2-rinterface") != RPY2_RINTERFACE_VERSION
        or importlib.metadata.version("rpy2-robjects") != RPY2_ROBJECTS_VERSION
    ):
        raise KitError("installed rpy2 components differ from the integration-kit lock")
    runtime = args.runtime.resolve(strict=True)
    library = args.library.resolve(strict=True)
    bridge = args.api_bridge.resolve(strict=True)
    require_api_bridge(bridge)
    provenance = load_provenance(args.provenance_manifest, target, bridge)
    rcmetar = next(
        record
        for record in provenance["source_packages"]
        if record.get("name") == "RCMetaR"
    )
    expected_rcmetar_url = (
        "https://github.com/AliSalman-et-al/rc-metastudio/archive/"
        f"{args.source_commit}.tar.gz"
    )
    if rcmetar.get("url") != expected_rcmetar_url:
        raise KitError("RCMetaR source provenance does not match the builder commit")
    if not library.is_relative_to(runtime):
        raise KitError("private R library must be inside the staged runtime")
    library_relative = library.relative_to(runtime).as_posix()
    r_home = library.parent
    rscript = (
        r_home / "bin" / ("Rscript.exe" if target.startswith("windows-") else "Rscript")
    )
    completed = subprocess.run(
        [str(rscript), "--vanilla", "-e", "cat(as.character(getRversion()))"],
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "R_HOME": str(r_home),
            "R_LIBS": str(library),
            "R_LIBS_USER": str(library),
        },
    )
    if completed.returncode or completed.stdout.strip() != R_VERSION:
        raise KitError(
            f"staged R runtime differs from {R_VERSION}: {completed.stderr.strip()}"
        )
    output = args.output.resolve()
    if output.exists():
        raise KitError(f"integration-kit output already exists: {output}")
    (output / "runtime").parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(runtime, output / "runtime", symlinks=True)
    (output / "bridge").mkdir()
    shutil.copy2(bridge, output / "bridge" / bridge.name)
    if target.startswith("macos-"):
        relocate_macos_api_bridge(output, output / "bridge" / bridge.name)
    provenance["rpy2"]["built_bridge_sha256"] = provenance["rpy2"]["bridge_sha256"]
    provenance["rpy2"]["bridge_sha256"] = sha256_file(output / "bridge" / bridge.name)
    source_payload = copy_source_payload(
        args.source_payload.resolve(strict=True), provenance, output / "source-archives"
    )
    uv_cache = args.uv_cache.resolve(strict=True)
    if not uv_cache.is_dir() or not any(path.is_file() for path in uv_cache.rglob("*")):
        raise KitError("integration kit requires a populated producer uv cache")
    if sha256_file(args.uv_lock.resolve(strict=True)) != args.uv_lock_sha256:
        raise KitError("producer uv.lock differs from its declared SHA256")
    (output / "python").mkdir()
    shutil.copytree(uv_cache, output / "python" / "uv-cache", symlinks=True)
    if target.startswith("windows-"):
        python_dll = Path(sys.base_prefix) / "python311.dll"
        if not python_dll.is_file():
            raise KitError("Windows kit producer cannot locate python311.dll")
        (output / "native").mkdir()
        shutil.copy2(python_dll, output / "native" / python_dll.name)
        for runtime_name in (
            "vcruntime140.dll",
            "vcruntime140_1.dll",
            "msvcp140.dll",
        ):
            direct = [
                root / runtime_name
                for root in (Path(sys.base_prefix), Path(sys.prefix))
                if (root / runtime_name).is_file()
            ]
            candidates = direct or [
                path
                for root in {Path(sys.base_prefix), Path(sys.prefix)}
                for path in root.rglob(runtime_name)
                if path.is_file()
            ]
            by_hash = {sha256_file(path): path for path in candidates}
            if len(by_hash) != 1:
                raise KitError(
                    f"Windows kit producer needs one unambiguous app-local {runtime_name}"
                )
            source = next(iter(by_hash.values()))
            shutil.copy2(source, output / "native" / runtime_name)
    copied_library = output / "runtime" / library_relative
    copy_license_inventory(output / "runtime", copied_library, output / "licenses")
    (output / "licenses" / "README.txt").write_text(
        "Copied license texts are retained here; package metadata is in sources.json.\n",
        encoding="utf-8",
    )
    installed_packages = installed_package_inventory(library)
    validate_installed_provenance(installed_packages, provenance)
    sources = {
        "provenance": provenance,
        "package_lock_sha256": args.package_lock_sha256,
        "installed_packages": installed_packages,
        "source_payload": source_payload,
        "builder": {"source_commit": args.source_commit, "runner": platform.platform()},
    }
    (output / "sources.json").write_text(
        json.dumps(sources, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if target.startswith("macos-"):
        if args.runtime_profile is None or not args.runtime_profile.is_file():
            raise KitError("macOS integration kit requires runtime-profile evidence")
        (output / "evidence").mkdir()
        shutil.copy2(args.runtime_profile, output / "evidence" / "runtime-profile.json")
    native_dependencies = native_dependency_inventory(output, target, architecture)
    (output / "native-dependencies.json").write_text(
        json.dumps(
            {"schema_version": 1, "target": target, "records": native_dependencies},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "rc-metastudio-r-integration-kit",
        "target": target,
        "architecture": architecture,
        "minimum_os": minimum_os,
        "versions": {
            "r": R_VERSION,
            "python": PYTHON_VERSION,
            "rpy2": RPY2_VERSION,
            "rpy2_rinterface": RPY2_RINTERFACE_VERSION,
            "rpy2_robjects": RPY2_ROBJECTS_VERSION,
        },
        "cffi_mode": "API",
        "runtime_path": "runtime",
        "library_path": f"runtime/{library_relative}",
        "api_bridge_path": f"bridge/{bridge.name}",
        "python_environment": {
            "uv_cache_path": "python/uv-cache",
            "uv_lock_sha256": args.uv_lock_sha256,
        },
        "files": [],
    }
    manifest["files"] = files(output)
    manifest["kit_sha256"] = canonical_digest(manifest)
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def verify_content(
    root: Path,
    *,
    target: str | None = None,
    uv_lock: Path | None = None,
    expected_kit_sha256: str | None = None,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_target = manifest.get("target")
    target_contract = TARGETS.get(str(manifest_target))
    if not (
        manifest.get("schema_version") == SCHEMA_VERSION
        and manifest.get("kind") == "rc-metastudio-r-integration-kit"
        and manifest.get("target") in TARGETS
        and manifest.get("cffi_mode") == "API"
        and manifest.get("versions")
        == {
            "r": R_VERSION,
            "python": PYTHON_VERSION,
            "rpy2": RPY2_VERSION,
            "rpy2_rinterface": RPY2_RINTERFACE_VERSION,
            "rpy2_robjects": RPY2_ROBJECTS_VERSION,
        }
        and manifest.get("kit_sha256") == canonical_digest(manifest)
        and (
            expected_kit_sha256 is None
            or manifest.get("kit_sha256") == expected_kit_sha256
        )
        and (target is None or manifest.get("target") == target)
        and target_contract is not None
        and manifest.get("architecture") == target_contract[1]
        and manifest.get("minimum_os") == target_contract[2]
        and _valid_sha256(manifest.get("python_environment", {}).get("uv_lock_sha256"))
        and manifest.get("python_environment", {}).get("uv_cache_path")
        == "python/uv-cache"
    ):
        raise KitError("integration-kit manifest identity is invalid")
    expected = {item["path"]: item for item in manifest.get("files", [])}
    observed = {
        item["path"]: item for item in files(root) if item["path"] != "manifest.json"
    }
    if expected != observed:
        raise KitError("integration-kit content differs from its manifest")
    if not any(path.is_file() for path in (root / "python" / "uv-cache").rglob("*")):
        raise KitError("integration-kit authenticated uv cache is empty")
    if (
        uv_lock is not None
        and sha256_file(uv_lock.resolve(strict=True))
        != manifest["python_environment"]["uv_lock_sha256"]
    ):
        raise KitError("consumer uv.lock differs from the authenticated producer lock")
    return manifest


def verify(root: Path, *, target: str | None = None) -> dict[str, Any]:
    root = root.resolve(strict=True)
    manifest = verify_content(root, target=target)
    manifest_target = manifest["target"]
    observed = {
        item["path"]: item for item in files(root) if item["path"] != "manifest.json"
    }
    bridge = root / str(manifest["api_bridge_path"])
    require_api_bridge(bridge)
    if any("_rinterface_cffi_abi" in path.lower() for path in observed):
        raise KitError("integration kit contains a forbidden ABI bridge")
    if (
        str(manifest_target).startswith("macos-")
        and not (root / "evidence" / "runtime-profile.json").is_file()
    ):
        raise KitError("macOS integration-kit runtime profile is missing")
    sources = json.loads((root / "sources.json").read_text(encoding="utf-8"))
    if not (
        len(str(sources.get("package_lock_sha256", ""))) == 64
        and sources.get("provenance", {}).get("rpy2", {}).get("version") == RPY2_VERSION
        and sources.get("provenance", {}).get("rpy2", {}).get("bridge_sha256")
        == sha256_file(bridge)
        and isinstance(sources.get("installed_packages"), list)
        and isinstance(sources.get("source_payload"), list)
        and len(sources.get("source_payload", [])) == 4
    ):
        raise KitError("integration-kit source provenance is incomplete")
    validate_installed_provenance(sources["installed_packages"], sources["provenance"])
    required_source_hashes = {
        record["sha256"]
        for record in sources["provenance"]["source_packages"]
        if record.get("name") == "RCMetaR"
    } | {
        record["sha256"] for record in sources["provenance"]["rpy2"]["source_archives"]
    }
    observed_source_hashes = set()
    for record in sources["source_payload"]:
        source = root / str(record.get("path", ""))
        if not source.is_file() or sha256_file(source) != record.get("sha256"):
            raise KitError("retained source archive payload is missing or changed")
        observed_source_hashes.add(record["sha256"])
    if observed_source_hashes != required_source_hashes:
        raise KitError("retained source archives differ from provenance")
    expected_native = json.loads(
        (root / "native-dependencies.json").read_text(encoding="utf-8")
    )
    if not (
        expected_native.get("schema_version") == 1
        and expected_native.get("target") == manifest_target
        and expected_native.get("records")
        == native_dependency_inventory(
            root, str(manifest_target), str(manifest["architecture"])
        )
    ):
        raise KitError("integration-kit native dependency inventory is invalid")
    return manifest


def consume(args: argparse.Namespace) -> dict[str, Any]:
    manifest = verify(args.kit, target=args.target)
    destination = args.destination.resolve()
    if destination.exists():
        raise KitError(f"integration-kit destination already exists: {destination}")
    shutil.copytree(args.kit.resolve(), destination, symlinks=True)
    verify(destination, target=args.target)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build")
    build_parser.add_argument("--target", choices=sorted(TARGETS), required=True)
    build_parser.add_argument("--runtime", type=Path, required=True)
    build_parser.add_argument("--library", type=Path, required=True)
    build_parser.add_argument("--api-bridge", type=Path, required=True)
    build_parser.add_argument("--output", type=Path, required=True)
    build_parser.add_argument("--provenance-manifest", type=Path, required=True)
    build_parser.add_argument("--runtime-profile", type=Path)
    build_parser.add_argument("--package-lock-sha256", required=True)
    build_parser.add_argument("--source-commit", required=True)
    build_parser.add_argument("--uv-cache", type=Path, required=True)
    build_parser.add_argument("--uv-lock", type=Path, required=True)
    build_parser.add_argument("--uv-lock-sha256", required=True)
    build_parser.add_argument("--source-payload", type=Path, required=True)
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--kit", type=Path, required=True)
    verify_parser.add_argument("--target", choices=sorted(TARGETS))
    content_parser = commands.add_parser("verify-content")
    content_parser.add_argument("--kit", type=Path, required=True)
    content_parser.add_argument("--target", choices=sorted(TARGETS), required=True)
    content_parser.add_argument("--uv-lock", type=Path, required=True)
    content_parser.add_argument("--expected-kit-sha256", required=True)
    consume_parser = commands.add_parser("consume")
    consume_parser.add_argument("--kit", type=Path, required=True)
    consume_parser.add_argument("--target", choices=sorted(TARGETS), required=True)
    consume_parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "build":
            result = build(args)
        elif args.command == "verify":
            result = verify(args.kit, target=args.target)
        elif args.command == "verify-content":
            result = verify_content(
                args.kit,
                target=args.target,
                uv_lock=args.uv_lock,
                expected_kit_sha256=args.expected_kit_sha256,
            )
        else:
            result = consume(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, KitError) as exc:
        print(f"R integration-kit error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

