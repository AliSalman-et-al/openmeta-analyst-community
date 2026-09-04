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
from typing import cast
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


def _record_string(record: dict[str, object], key: str, label: str) -> str:
    value = record.get(key)
    if not isinstance(value, str):
        raise KitError(f"{label} is missing its {key} string")
    return value


def _record_strings(record: dict[str, object], key: str, label: str) -> list[str]:
    value = record.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise KitError(f"{label} is missing its {key} string list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise KitError(f"{label} is missing its {key} string list")
        result.append(item)
    return result


def _record_list(
    record: dict[str, object], key: str, label: str
) -> list[dict[str, object]]:
    value = record.get(key)
    if not isinstance(value, list):
        raise KitError(f"{label} is missing its {key} record list")
    result: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise KitError(f"{label} has a malformed {key} record")
        result.append({str(name): field for name, field in item.items()})
    return result


def _record_mapping(
    record: dict[str, object], key: str, label: str
) -> dict[str, object]:
    value = record.get(key)
    if not isinstance(value, dict):
        raise KitError(f"{label} is missing its {key} object")
    result: dict[str, object] = {}
    for name, field in value.items():
        if not isinstance(name, str):
            raise KitError(f"{label} has a malformed {key} object")
        result[name] = field
    return result


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise KitError(f"{label} must be an object")
    result: dict[str, object] = {}
    for name, field in value.items():
        if not isinstance(name, str):
            raise KitError(f"{label} has a non-string key")
        result[name] = field
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files(root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
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


def canonical_digest(manifest: dict[str, object]) -> str:
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


def _license_record(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    record = {key: field for key, field in value.items() if isinstance(key, str)}
    if len(record) != len(value):
        return None
    if not _license_path_valid(record):
        return None
    return record


def _license_path_valid(record: dict[str, object]) -> bool:
    path = record.get("path")
    if not isinstance(path, str) or not path:
        return False
    relative = Path(path)
    if relative.is_absolute() or ".." in relative.parts:
        return False
    return _valid_sha256(record.get("sha256"))


def _license_records(value: object) -> list[dict[str, object]] | None:
    if not isinstance(value, list):
        return None
    records: list[dict[str, object]] = []
    for item in value:
        record = _license_record(item)
        if record is None:
            return None
        records.append(record)
    return records


def _valid_license_files(value: object, *, declared_license: object) -> bool:
    records = _license_records(value)
    if records is None:
        return False
    if not _declares_license_file(declared_license):
        return True
    return any(
        Path(_record_string(record, "path", "license record")).name.casefold()
        in {"license", "licence"}
        for record in records
    )


def _valid_official_r(record: dict[str, object], target: str) -> bool:
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


def _read_provenance(path: Path) -> dict[str, object]:
    return _mapping(json.loads(path.read_text(encoding="utf-8")), "provenance manifest")


def _provenance_sections(
    provenance: dict[str, object],
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, object],
    list[dict[str, object]],
]:
    official_r = _record_mapping(provenance, "official_r", "provenance")
    ppm = _record_list(provenance, "ppm_packages", "provenance")
    source_packages = _record_list(provenance, "source_packages", "provenance")
    rpy2 = _record_mapping(provenance, "rpy2", "provenance")
    rpy2_archives = _record_list(rpy2, "source_archives", "rpy2 provenance")
    return official_r, ppm, source_packages, rpy2, rpy2_archives


def _validate_provenance_identity(
    provenance: dict[str, object],
    target: str,
    bridge: Path,
    official_r: dict[str, object],
    ppm: list[dict[str, object]],
    source_packages: list[dict[str, object]],
    rpy2: dict[str, object],
    rpy2_archives: list[dict[str, object]],
) -> None:
    valid_rpy2 = _valid_rpy2_identity(rpy2, bridge)
    valid_manifest = all(
        (
            provenance.get("schema_version") == 1,
            provenance.get("target") == target,
            _valid_official_r(official_r, target),
            bool(ppm),
            bool(source_packages),
            valid_rpy2,
            bool(rpy2_archives),
        )
    )
    if not valid_manifest:
        raise KitError("integration-kit provenance manifest is incomplete or invalid")


def _valid_rpy2_identity(rpy2: dict[str, object], bridge: Path) -> bool:
    return all(
        (
            rpy2.get("version") == RPY2_VERSION,
            rpy2.get("sdist_distribution") == "rpy2-rinterface",
            rpy2.get("sdist_version") == RPY2_RINTERFACE_VERSION,
            rpy2.get("robjects_version") == RPY2_ROBJECTS_VERSION,
            _verified_https(rpy2.get("sdist_url")),
            urlparse(str(rpy2.get("sdist_url"))).hostname == "files.pythonhosted.org",
            _valid_sha256(rpy2.get("sdist_sha256")),
            _valid_sha256(rpy2.get("build_log_sha256")),
            bool(rpy2.get("toolchain")),
            bool(rpy2.get("license")),
            rpy2.get("bridge_sha256") == sha256_file(bridge),
        )
    )


def _validate_rpy2_archives(
    rpy2: dict[str, object], archives: list[dict[str, object]]
) -> None:
    expected_rpy2_archives = {
        "rpy2": "3.6.7",
        "rpy2-rinterface": RPY2_RINTERFACE_VERSION,
        "rpy2-robjects": RPY2_ROBJECTS_VERSION,
    }
    observed_archives = {
        str(record.get("distribution")): str(record.get("version"))
        for record in archives
    }
    if observed_archives != expected_rpy2_archives:
        raise KitError("rpy2 split source archive provenance is incomplete")
    for record in archives:
        if not _valid_rpy2_archive(record):
            raise KitError("rpy2 split source archive license provenance is invalid")
    rinterface_archive = _rinterface_archive(archives)
    if not _rinterface_matches(rpy2, rinterface_archive):
        raise KitError("rpy2 API bridge source differs from retained rinterface sdist")


def _rinterface_archive(archives: list[dict[str, object]]) -> dict[str, object]:
    return next(
        record for record in archives if record.get("distribution") == "rpy2-rinterface"
    )


def _rinterface_matches(rpy2: dict[str, object], archive: dict[str, object]) -> bool:
    return all(
        (
            rpy2.get("sdist_url") == archive.get("url"),
            rpy2.get("sdist_sha256") == archive.get("sha256"),
        )
    )


def _valid_rpy2_archive(record: dict[str, object]) -> bool:
    return all(
        (
            _verified_https(record.get("url")),
            urlparse(str(record.get("url"))).hostname == "files.pythonhosted.org",
            _valid_sha256(record.get("sha256")),
            _valid_license_files(
                record.get("license_files"), declared_license="file LICENSE"
            ),
        )
    )


def _validate_ppm_packages(ppm: list[dict[str, object]], target: str) -> None:
    for record in ppm:
        if not _valid_ppm_package(record, target):
            raise KitError("PPM archive provenance is incomplete or invalid")


def _valid_ppm_package(record: dict[str, object], target: str) -> bool:
    return all(
        (
            bool(record.get("name")),
            bool(record.get("version")),
            record.get("package_type") in {"win.binary", "mac.binary"},
            str(record.get("url", "")).startswith(
                f"{PPM_REPOSITORY}/{PPM_CONTRIB_PATHS[target]}/"
            ),
            _valid_sha256(record.get("sha256")),
            _valid_license_files(
                record.get("license_files"), declared_license=record.get("license")
            ),
            bool(record.get("license")),
            record.get("license") != "unknown",
        )
    )


def _validate_source_packages(source_packages: list[dict[str, object]]) -> None:
    source_names = {record.get("name") for record in source_packages}
    if "RCMetaR" not in source_names:
        raise KitError("RCMetaR source provenance is required")
    for record in source_packages:
        if not _valid_source_package(record):
            raise KitError("source-package provenance is incomplete or invalid")


def _valid_source_package(record: dict[str, object]) -> bool:
    return all(
        (
            _verified_https(record.get("url")),
            _valid_sha256(record.get("sha256")),
            _valid_sha256(record.get("build_log_sha256")),
            bool(record.get("toolchain")),
            record.get("package_type") == "source",
            bool(record.get("version")),
            bool(record.get("license")),
        )
    )


def load_provenance(path: Path, target: str, bridge: Path) -> dict[str, object]:
    provenance = _read_provenance(path)
    official_r, ppm, source_packages, rpy2, archives = _provenance_sections(provenance)
    _validate_provenance_identity(
        provenance, target, bridge, official_r, ppm, source_packages, rpy2, archives
    )
    _validate_rpy2_archives(rpy2, archives)
    _validate_ppm_packages(ppm, target)
    _validate_source_packages(source_packages)
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


def _provenance_claims_by_name(
    provenance: dict[str, object],
) -> dict[str, dict[str, object]]:
    claims = _record_list(provenance, "ppm_packages", "provenance") + _record_list(
        provenance, "source_packages", "provenance"
    )
    by_name: dict[str, dict[str, object]] = {}
    for record in claims:
        name = str(record["name"])
        if name in by_name:
            raise KitError(f"package provenance contains duplicate identity: {name}")
        by_name[name] = record
    return by_name


def _validate_claimed_packages(
    installed: list[dict[str, str]], claims: dict[str, dict[str, object]]
) -> None:
    installed_by_name = {record["name"]: record for record in installed}
    for name, claim in claims.items():
        observed = installed_by_name.get(name)
        if observed is None or observed["version"] != claim["version"]:
            raise KitError(
                f"installed package differs from provenance: {name}={observed and observed['version']}"
            )


def _unclaimed_installed_packages(
    installed: list[dict[str, str]], claims: dict[str, dict[str, object]]
) -> list[str]:
    unclaimed = sorted(
        record["name"]
        for record in installed
        if record.get("priority") not in {"base", "recommended"}
        and record["name"] not in claims
    )
    return unclaimed


def validate_installed_provenance(
    installed: list[dict[str, str]], provenance: dict[str, object]
) -> None:
    claims = _provenance_claims_by_name(provenance)
    _validate_claimed_packages(installed, claims)
    unclaimed = _unclaimed_installed_packages(installed, claims)
    if unclaimed:
        raise KitError(
            "installed package lacks exact provenance: " + ", ".join(unclaimed)
        )


def _source_payload_claims(provenance: dict[str, object]) -> list[dict[str, object]]:
    claims = [
        {
            "name": record["name"],
            "version": record["version"],
            "sha256": record["sha256"],
        }
        for record in _record_list(provenance, "source_packages", "provenance")
        if record.get("name") == "RCMetaR"
    ]
    claims.extend(
        {
            "name": record["distribution"],
            "version": record["version"],
            "sha256": record["sha256"],
        }
        for record in _record_list(
            _record_mapping(provenance, "rpy2", "provenance"),
            "source_archives",
            "rpy2 provenance",
        )
    )
    return claims


def _source_payload_by_hash(
    source_root: Path,
) -> tuple[list[Path], dict[str, list[Path]]]:
    candidates = [path for path in source_root.iterdir() if path.is_file()]
    by_hash: dict[str, list[Path]] = {}
    for path in candidates:
        by_hash.setdefault(sha256_file(path), []).append(path)

    return candidates, by_hash


def _copy_source_claim(
    claim: dict[str, object], matches: list[Path], destination: Path
) -> dict[str, str]:
    name = str(claim["name"])
    if len(matches) != 1:
        raise KitError(f"source payload is missing or ambiguous: {name}")
    source = matches[0]
    target = destination / source.name
    if target.exists():
        raise KitError(f"source payload filename collision: {source.name}")
    shutil.copy2(source, target)
    return {
        "name": name,
        "version": str(claim["version"]),
        "path": f"source-archives/{target.name}",
        "sha256": str(claim["sha256"]),
    }


def copy_source_payload(
    source_root: Path, provenance: dict[str, object], destination: Path
) -> list[dict[str, str]]:
    claims = _source_payload_claims(provenance)
    candidates, by_hash = _source_payload_by_hash(source_root)
    if len(candidates) != len(claims):
        raise KitError("source payload must contain exactly the retained archives")
    destination.mkdir()
    records = []
    for claim in claims:
        records.append(
            _copy_source_claim(
                claim, by_hash.get(str(claim["sha256"]), []), destination
            )
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


def _resolve_windows_closure(records: list[dict[str, object]]) -> None:
    by_name: dict[str, list[dict[str, object]]] = {}
    for record in records:
        by_name.setdefault(
            Path(_record_string(record, "path", "native record")).name.casefold(), []
        ).append(record)
    for record in records:
        resolutions = []
        for import_record in _record_list(record, "_imports", "native record"):
            name = _record_string(import_record, "name", "native import")
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


def _resolve_macos_closure(records: list[dict[str, object]], root: Path) -> None:
    by_path = {
        (root / _record_string(record, "path", "native record")).resolve(): record
        for record in records
    }
    by_install_id: dict[str, list[dict[str, object]]] = {}
    for record in records:
        if record.get("install_id"):
            by_install_id.setdefault(str(record["install_id"]), []).append(record)
    for record in records:
        record["imports"] = _macos_record_resolutions(
            record, root, by_path, by_install_id
        )


def _macos_record_resolutions(
    record: dict[str, object],
    root: Path,
    by_path: dict[Path, dict[str, object]],
    by_install_id: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    loader = (root / _record_string(record, "path", "native record")).resolve().parent
    return [
        _macos_dependency_resolution(record, dependency, loader, by_path, by_install_id)
        for dependency in _record_strings(record, "_imports", "native record")
    ]


def _macos_dependency_resolution(
    record: dict[str, object],
    dependency: str,
    loader: Path,
    by_path: dict[Path, dict[str, object]],
    by_install_id: dict[str, list[dict[str, object]]],
) -> dict[str, object]:
    if dependency.casefold().startswith(FORBIDDEN_NATIVE_PREFIXES):
        raise KitError(f"forbidden external Mach-O dependency: {dependency}")
    if dependency.startswith(("/usr/lib/", "/System/Library/")):
        return {"name": dependency, "resolution": "system"}
    candidates = _macos_dependency_candidates(
        record, dependency, loader, by_path, by_install_id
    )
    unique = {item["path"]: item for item in candidates}
    if len(unique) != 1:
        raise KitError(
            f"Mach-O dependency is unresolved or ambiguous: {record['path']} -> {dependency}"
        )
    resolved = next(iter(unique.values()))
    return {
        "name": dependency,
        "resolution": "kit",
        "resolved_path": resolved["path"],
        "resolved_sha256": resolved["sha256"],
    }


def _macos_dependency_candidates(
    record: dict[str, object],
    dependency: str,
    loader: Path,
    by_path: dict[Path, dict[str, object]],
    by_install_id: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    if dependency.startswith("@loader_path/"):
        resolved = (loader / dependency[len("@loader_path/") :]).resolve()
        return [by_path[resolved]] if resolved in by_path else []
    if dependency.startswith("@rpath/"):
        suffix = dependency[len("@rpath/") :]
        candidates = [
            by_path[resolved]
            for rpath in _record_strings(record, "rpaths", "native record")
            if rpath.startswith("@loader_path/")
            for resolved in [
                (loader / rpath[len("@loader_path/") :] / suffix).resolve()
            ]
            if resolved in by_path
        ]
        candidates.extend(by_install_id.get(dependency, []))
        return candidates
    return list(by_install_id.get(dependency, []))


def _windows_native_record(path: Path, relative: str) -> dict[str, object]:
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
        raise KitError(f"native Windows payload is not valid PE: {relative}") from exc
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
    return {
        "path": relative,
        "owner": _owner(relative),
        "sha256": sha256_file(path),
        "architecture": "x86_64",
        "_imports": sorted(imports, key=lambda item: (item["name"], item["kind"])),
    }


def _macos_native_record(
    path: Path, relative: str, target: str, architecture: str
) -> dict[str, object] | None:
    from scripts.qt6_macos_feasibility_impl import is_macho_candidate

    if not is_macho_candidate(path):
        return None
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
    install_id, rpaths, minimum_os, signing_identity = _macos_metadata(path)
    target_minimum = TARGETS[target][2]
    if (
        minimum_os is None
        or target_minimum is None
        or _macos_version(minimum_os) > _macos_version(target_minimum)
    ):
        raise KitError(
            f"Mach-O deployment target exceeds {target_minimum}: {relative}={minimum_os}"
        )
    return {
        "path": relative,
        "owner": _owner(relative),
        "sha256": sha256_file(path),
        "architecture": architecture,
        "install_id": install_id,
        "rpaths": rpaths,
        "minimum_macos": minimum_os,
        "signing_identity": signing_identity,
        "_imports": [
            line.strip().split(" (", 1)[0] for line in completed.stdout.splitlines()[1:]
        ],
    }


def _native_records(
    root: Path, target: str, architecture: str
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in _native_paths(root):
        relative = path.relative_to(root).as_posix()
        if relative.startswith("python/uv-cache/"):
            continue
        record = _native_record(path, relative, target, architecture)
        if record is None:
            continue
        records.append(record)
    return records


def _native_paths(root: Path) -> list[Path]:
    return sorted(
        item for item in root.rglob("*") if item.is_file() and not item.is_symlink()
    )


def _native_record(
    path: Path, relative: str, target: str, architecture: str
) -> dict[str, object] | None:
    if target.startswith("windows-"):
        if path.suffix.lower() not in {".exe", ".dll", ".pyd"}:
            return None
        return _windows_native_record(path, relative)
    return _macos_native_record(path, relative, target, architecture)


def _validate_windows_inventory(records: list[dict[str, object]]) -> None:
    _resolve_windows_closure(records)
    r_dlls = [
        record
        for record in records
        if Path(_record_string(record, "path", "native record")).name.casefold()
        == "r.dll"
    ]
    if len(r_dlls) != 1:
        raise KitError("kit must contain exactly one canonical R.dll")


def _validate_macos_inventory(root: Path, records: list[dict[str, object]]) -> None:
    _resolve_macos_closure(records, root)
    shared_r = [
        record
        for record in records
        if _record_string(record, "path", "native record").endswith("/lib/libR.dylib")
        or (
            "/Versions/" in _record_string(record, "path", "native record")
            and "/Resources/" not in _record_string(record, "path", "native record")
            and _record_string(record, "path", "native record").endswith("/R")
        )
    ]
    if len({record["sha256"] for record in shared_r}) != 1:
        raise KitError("kit must contain one canonical macOS libR identity")


def native_dependency_inventory(
    root: Path, target: str, architecture: str
) -> list[dict[str, object]]:
    records = _native_records(root, target, architecture)
    if target.startswith("windows-"):
        _validate_windows_inventory(records)
    else:
        _validate_macos_inventory(root, records)
    return records


def _validate_build_target(
    target: str, source_commit: str, package_lock_sha256: str
) -> tuple[str, str, str | None]:
    if not _valid_sha256(package_lock_sha256):
        raise KitError("package lock SHA256 must be lowercase hexadecimal")
    if len(source_commit) != 40 or any(
        character not in "0123456789abcdef" for character in source_commit
    ):
        raise KitError("source commit must be a full lowercase Git SHA")
    expected_system, architecture, minimum_os = TARGETS[target]
    if platform.system() != expected_system:
        raise KitError(f"{target} kit must be built natively on {expected_system}")
    accepted = {"x86_64": {"x86_64", "amd64"}, "arm64": {"arm64", "aarch64"}}
    if platform.machine().lower() not in accepted[architecture]:
        raise KitError(
            f"{target} kit requires {architecture}, found {platform.machine().lower()}"
        )
    if platform.python_version() != PYTHON_VERSION:
        raise KitError(
            f"integration kit requires Python {PYTHON_VERSION}, found {platform.python_version()}"
        )
    return expected_system, architecture, minimum_os


def _validate_rpy2_installation() -> None:
    if importlib.metadata.version("rpy2") != RPY2_VERSION:
        raise KitError(
            "installed rpy2 distribution differs from the integration-kit lock"
        )
    components = (
        ("rpy2-rinterface", RPY2_RINTERFACE_VERSION),
        ("rpy2-robjects", RPY2_ROBJECTS_VERSION),
    )
    if any(importlib.metadata.version(name) != version for name, version in components):
        raise KitError("installed rpy2 components differ from the integration-kit lock")


def _build_inputs(
    args: argparse.Namespace, target: str
) -> tuple[Path, Path, Path, dict[str, object], str]:
    runtime = args.runtime.resolve(strict=True)
    library = args.library.resolve(strict=True)
    bridge = args.api_bridge.resolve(strict=True)
    require_api_bridge(bridge)
    provenance = load_provenance(args.provenance_manifest, target, bridge)
    rcmetar = next(
        record
        for record in _record_list(provenance, "source_packages", "provenance")
        if record.get("name") == "RCMetaR"
    )
    expected_url = f"https://github.com/AliSalman-et-al/rc-metastudio/archive/{args.source_commit}.tar.gz"
    if rcmetar.get("url") != expected_url:
        raise KitError("RCMetaR source provenance does not match the builder commit")
    if not library.is_relative_to(runtime):
        raise KitError("private R library must be inside the staged runtime")
    return runtime, library, bridge, provenance, library.relative_to(runtime).as_posix()


def _validate_staged_r_version(runtime: Path, library: Path, target: str) -> None:
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


def _copy_windows_python_runtime(output: Path) -> None:
    python_dll = Path(sys.base_prefix) / "python311.dll"
    if not python_dll.is_file():
        raise KitError("Windows kit producer cannot locate python311.dll")
    native = output / "native"
    native.mkdir()
    shutil.copy2(python_dll, native / python_dll.name)
    for runtime_name in ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"):
        shutil.copy2(_windows_runtime_source(runtime_name), native / runtime_name)


def _windows_runtime_source(runtime_name: str) -> Path:
    roots = (Path(sys.base_prefix), Path(sys.prefix))
    direct = _direct_runtime_candidates(roots, runtime_name)
    candidates = direct or _all_runtime_candidates(roots, runtime_name)
    by_hash = {sha256_file(path): path for path in candidates}
    if len(by_hash) != 1:
        raise KitError(
            f"Windows kit producer needs one unambiguous app-local {runtime_name}"
        )
    return next(iter(by_hash.values()))


def _direct_runtime_candidates(
    roots: tuple[Path, ...], runtime_name: str
) -> list[Path]:
    return [root / runtime_name for root in roots if (root / runtime_name).is_file()]


def _all_runtime_candidates(roots: tuple[Path, ...], runtime_name: str) -> list[Path]:
    return [
        path
        for root in set(roots)
        for path in root.rglob(runtime_name)
        if path.is_file()
    ]


def _copy_python_cache(args: argparse.Namespace, output: Path) -> None:
    uv_cache = args.uv_cache.resolve(strict=True)
    if not uv_cache.is_dir() or not any(path.is_file() for path in uv_cache.rglob("*")):
        raise KitError("integration kit requires a populated producer uv cache")
    if sha256_file(args.uv_lock.resolve(strict=True)) != args.uv_lock_sha256:
        raise KitError("producer uv.lock differs from its declared SHA256")
    python_root = output / "python"
    python_root.mkdir()
    shutil.copytree(uv_cache, python_root / "uv-cache", symlinks=True)


def _write_sources(
    output: Path,
    args: argparse.Namespace,
    provenance: dict[str, object],
    payload: list[dict[str, str]],
    installed: list[dict[str, str]],
) -> None:
    sources = {
        "provenance": provenance,
        "package_lock_sha256": args.package_lock_sha256,
        "installed_packages": installed,
        "source_payload": payload,
        "builder": {"source_commit": args.source_commit, "runner": platform.platform()},
    }
    (output / "sources.json").write_text(
        json.dumps(sources, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_native_inventory(output: Path, target: str, architecture: str) -> None:
    records = native_dependency_inventory(output, target, architecture)
    (output / "native-dependencies.json").write_text(
        json.dumps(
            {"schema_version": 1, "target": target, "records": records},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _build_manifest(
    output: Path,
    target: str,
    architecture: str,
    minimum_os: str | None,
    library_relative: str,
    bridge: Path,
    args: argparse.Namespace,
) -> dict[str, object]:
    manifest: dict[str, object] = {
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
        "files": files(output),
    }
    manifest["kit_sha256"] = canonical_digest(manifest)
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def build(args: argparse.Namespace) -> dict[str, object]:
    target = args.target
    _, architecture, minimum_os = _validate_build_target(
        target, args.source_commit, args.package_lock_sha256
    )
    _validate_rpy2_installation()
    runtime, library, bridge, provenance, library_relative = _build_inputs(args, target)
    _validate_staged_r_version(runtime, library, target)
    output = args.output.resolve()
    if output.exists():
        raise KitError(f"integration-kit output already exists: {output}")
    (output / "runtime").parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(runtime, output / "runtime", symlinks=True)
    (output / "bridge").mkdir()
    shutil.copy2(bridge, output / "bridge" / bridge.name)
    if target.startswith("macos-"):
        relocate_macos_api_bridge(output, output / "bridge" / bridge.name)
    rpy2 = _record_mapping(provenance, "rpy2", "provenance")
    rpy2["built_bridge_sha256"] = rpy2["bridge_sha256"]
    rpy2["bridge_sha256"] = sha256_file(output / "bridge" / bridge.name)
    source_payload = copy_source_payload(
        args.source_payload.resolve(strict=True), provenance, output / "source-archives"
    )
    _copy_python_cache(args, output)
    if target.startswith("windows-"):
        _copy_windows_python_runtime(output)
    copied_library = output / "runtime" / library_relative
    copy_license_inventory(output / "runtime", copied_library, output / "licenses")
    (output / "licenses" / "README.txt").write_text(
        "Copied license texts are retained here; package metadata is in sources.json.\n",
        encoding="utf-8",
    )
    installed_packages = installed_package_inventory(library)
    validate_installed_provenance(installed_packages, provenance)
    _write_sources(output, args, provenance, source_payload, installed_packages)
    if target.startswith("macos-"):
        if args.runtime_profile is None or not args.runtime_profile.is_file():
            raise KitError("macOS integration kit requires runtime-profile evidence")
        (output / "evidence").mkdir()
        shutil.copy2(args.runtime_profile, output / "evidence" / "runtime-profile.json")
    _write_native_inventory(output, target, architecture)
    return _build_manifest(
        output, target, architecture, minimum_os, library_relative, bridge, args
    )


def _manifest_versions_valid(manifest: dict[str, object]) -> bool:
    return manifest.get("versions") == {
        "r": R_VERSION,
        "python": PYTHON_VERSION,
        "rpy2": RPY2_VERSION,
        "rpy2_rinterface": RPY2_RINTERFACE_VERSION,
        "rpy2_robjects": RPY2_ROBJECTS_VERSION,
    }


def _manifest_environment_valid(manifest: dict[str, object]) -> bool:
    environment = manifest.get("python_environment")
    if not isinstance(environment, dict):
        return False
    environment = {str(key): value for key, value in environment.items()}
    return (
        _valid_sha256(environment.get("uv_lock_sha256"))
        and environment.get("uv_cache_path") == "python/uv-cache"
    )


def _manifest_identity_valid(
    manifest: dict[str, object], target: str | None, expected_kit_sha256: str | None
) -> bool:
    manifest_target = manifest.get("target")
    target_contract = TARGETS.get(str(manifest_target))
    return all(
        (
            manifest.get("schema_version") == SCHEMA_VERSION,
            manifest.get("kind") == "rc-metastudio-r-integration-kit",
            manifest.get("target") in TARGETS,
            manifest.get("cffi_mode") == "API",
            _manifest_versions_valid(manifest),
            manifest.get("kit_sha256") == canonical_digest(manifest),
            expected_kit_sha256 is None
            or manifest.get("kit_sha256") == expected_kit_sha256,
            target is None or manifest.get("target") == target,
            target_contract is not None,
            target_contract is not None
            and manifest.get("architecture") == target_contract[1],
            target_contract is not None
            and manifest.get("minimum_os") == target_contract[2],
            _manifest_environment_valid(manifest),
        )
    )


def _verify_manifest_files(root: Path, manifest: dict[str, object]) -> None:
    expected = {
        item["path"]: item for item in _record_list(manifest, "files", "manifest")
    }
    observed = {
        item["path"]: item for item in files(root) if item["path"] != "manifest.json"
    }
    if expected != observed:
        raise KitError("integration-kit content differs from its manifest")


def _verify_uv_cache(
    root: Path, uv_lock: Path | None, manifest: dict[str, object]
) -> None:
    if not any(path.is_file() for path in (root / "python" / "uv-cache").rglob("*")):
        raise KitError("integration-kit authenticated uv cache is empty")
    if uv_lock is not None:
        environment = _record_mapping(manifest, "python_environment", "manifest")
        if sha256_file(uv_lock.resolve(strict=True)) != environment["uv_lock_sha256"]:
            raise KitError(
                "consumer uv.lock differs from the authenticated producer lock"
            )


def verify_content(
    root: Path,
    *,
    target: str | None = None,
    uv_lock: Path | None = None,
    expected_kit_sha256: str | None = None,
) -> dict[str, object]:
    root = root.resolve(strict=True)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not _manifest_identity_valid(
        manifest, target, expected_kit_sha256
    ):
        raise KitError("integration-kit manifest identity is invalid")
    _verify_manifest_files(root, manifest)
    _verify_uv_cache(root, uv_lock, manifest)
    return manifest


def _verify_bridge_and_profile(root: Path, manifest: dict[str, object]) -> Path:
    bridge = root / str(manifest["api_bridge_path"])
    require_api_bridge(bridge)
    observed_paths = {
        _record_string(item, "path", "integration-kit record") for item in files(root)
    }
    if any("_rinterface_cffi_abi" in path.lower() for path in observed_paths):
        raise KitError("integration kit contains a forbidden ABI bridge")
    if (
        str(manifest["target"]).startswith("macos-")
        and not (root / "evidence" / "runtime-profile.json").is_file()
    ):
        raise KitError("macOS integration-kit runtime profile is missing")
    return bridge


def _verify_source_provenance(root: Path, bridge: Path) -> dict[str, object]:
    sources = _mapping(
        json.loads((root / "sources.json").read_text(encoding="utf-8")), "sources"
    )
    provenance = _mapping(sources.get("provenance"), "source provenance")
    rpy2 = _mapping(provenance.get("rpy2"), "rpy2 provenance")
    payload = sources.get("source_payload")
    if not all(
        (
            len(str(sources.get("package_lock_sha256", ""))) == 64,
            isinstance(rpy2, dict),
            isinstance(rpy2, dict) and rpy2.get("version") == RPY2_VERSION,
            isinstance(rpy2, dict) and rpy2.get("bridge_sha256") == sha256_file(bridge),
            isinstance(sources.get("installed_packages"), list),
            isinstance(payload, list),
            isinstance(payload, list) and len(payload) == 4,
        )
    ):
        raise KitError("integration-kit source provenance is incomplete")
    installed = cast(
        list[dict[str, str]], _record_list(sources, "installed_packages", "sources")
    )
    validate_installed_provenance(installed, provenance)
    return sources


def _verify_source_payload(root: Path, sources: dict[str, object]) -> None:
    provenance = _mapping(sources.get("provenance"), "source provenance")
    source_packages = _record_list(provenance, "source_packages", "source provenance")
    rpy2 = _record_mapping(provenance, "rpy2", "source provenance")
    archives = _record_list(rpy2, "source_archives", "rpy2 provenance")
    required = {
        record["sha256"]
        for record in source_packages
        if record.get("name") == "RCMetaR"
    } | {record["sha256"] for record in archives}
    observed: set[object] = set()
    for record in _record_list(sources, "source_payload", "sources"):
        source = root / str(record.get("path", ""))
        if not source.is_file() or sha256_file(source) != record.get("sha256"):
            raise KitError("retained source archive payload is missing or changed")
        observed.add(record["sha256"])
    if observed != required:
        raise KitError("retained source archives differ from provenance")


def _verify_native_inventory(root: Path, manifest: dict[str, object]) -> None:
    expected_native = json.loads(
        (root / "native-dependencies.json").read_text(encoding="utf-8")
    )
    target = str(manifest["target"])
    if not (
        expected_native.get("schema_version") == 1
        and expected_native.get("target") == target
        and expected_native.get("records")
        == native_dependency_inventory(root, target, str(manifest["architecture"]))
    ):
        raise KitError("integration-kit native dependency inventory is invalid")


def verify(root: Path, *, target: str | None = None) -> dict[str, object]:
    root = root.resolve(strict=True)
    manifest = verify_content(root, target=target)
    bridge = _verify_bridge_and_profile(root, manifest)
    sources = _verify_source_provenance(root, bridge)
    _verify_source_payload(root, sources)
    _verify_native_inventory(root, manifest)
    return manifest


def consume(args: argparse.Namespace) -> dict[str, object]:
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
