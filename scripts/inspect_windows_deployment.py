"""Fail-closed inspection and evidence generation for the Windows x64 package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import struct
import sys
import unicodedata
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import TypeGuard, cast


PE_X64_MACHINE = 0x8664
NATIVE_SUFFIXES = {".dll", ".exe", ".pyd"}
REQUIRED_PLUGINS = {
    "platforms": {"qwindows.dll"},
    "imageformats": {"qico.dll", "qjpeg.dll", "qsvg.dll"},
    "iconengines": {"qsvgicon.dll"},
    "styles": {"qmodernwindowsstyle.dll"},
    "tls": {"qschannelbackend.dll"},
}
REQUIRED_QT_LIBRARIES = {
    "qt6core.dll",
    "qt6gui.dll",
    "qt6network.dll",
    "qt6svg.dll",
    "qt6svgwidgets.dll",
    "qt6widgets.dll",
}
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
EXPECTED_SUMMARY_SHA256 = EXPECTED_SUMMARY_SHA256_BY_SAMPLE["amino.rcms"]
FORBIDDEN_GENERATED_SOURCE_SUFFIXES = {".py", ".pyc", ".pyo", ".ui", ".qrc"}
FORBIDDEN_BINDINGS = ("pyqt5", "pyside2", "pyside6", "qtpy")
REQUIRED_PROJECT_SCHEMAS = {
    "manifest.schema.json",
    "project.schema.json",
    "state.schema.json",
}
WINDOWS_SYSTEM_DLLS = {
    "advapi32.dll",
    "authz.dll",
    "bcrypt.dll",
    "bcryptprimitives.dll",
    "cfgmgr32.dll",
    "comctl32.dll",
    "comdlg32.dll",
    "crypt32.dll",
    "cryptbase.dll",
    "credui.dll",
    "d2d1.dll",
    "d3d11.dll",
    "d3d12.dll",
    "dnsapi.dll",
    "d3d9.dll",
    "dbghelp.dll",
    "dwrite.dll",
    "dwmapi.dll",
    "dxgi.dll",
    "gdi32.dll",
    "gdiplus.dll",
    "imagehlp.dll",
    "imm32.dll",
    "icuuc.dll",
    "iphlpapi.dll",
    "kernel32.dll",
    "msvcrt.dll",
    "ncrypt.dll",
    "netapi32.dll",
    "normaliz.dll",
    "mpr.dll",
    "msimg32.dll",
    "ntdll.dll",
    "ole32.dll",
    "oleaut32.dll",
    "pdh.dll",
    "powrprof.dll",
    "propsys.dll",
    "psapi.dll",
    "rpcrt4.dll",
    "secur32.dll",
    "setupapi.dll",
    "shell32.dll",
    "shlwapi.dll",
    "ucrtbase.dll",
    "uiautomationcore.dll",
    "usp10.dll",
    "uxtheme.dll",
    "user32.dll",
    "userenv.dll",
    "version.dll",
    "winhttp.dll",
    "wininet.dll",
    "winmm.dll",
    "wtsapi32.dll",
    "wldap32.dll",
    "ws2_32.dll",
}


class DeploymentInspectionError(RuntimeError):
    """Raised when a package violates the Windows deployment contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _valid_source_provenance(value: object, source_commit: str) -> bool:
    if not _string_keyed_dict(value):
        return False
    return (
        value.get("schema_version") == 1
        and value.get("head_sha") == source_commit
        and value.get("working_tree") in {"clean", "dirty"}
        and _valid_sha256(value.get("worktree_sha256"))
    )


def pe_machine(path: Path) -> int:
    with path.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise DeploymentInspectionError(f"native file has no PE header: {path}")
        stream.seek(0x3C)
        raw_offset = stream.read(4)
        if len(raw_offset) != 4:
            raise DeploymentInspectionError(
                f"native file has a truncated DOS header: {path}"
            )
        pe_offset = struct.unpack("<I", raw_offset)[0]
        stream.seek(pe_offset)
        if stream.read(4) != b"PE\0\0":
            raise DeploymentInspectionError(f"native file has no PE signature: {path}")
        raw_machine = stream.read(2)
        if len(raw_machine) != 2:
            raise DeploymentInspectionError(
                f"native file has a truncated PE header: {path}"
            )
        return struct.unpack("<H", raw_machine)[0]


def _is_windows_system_import(name: str) -> bool:
    lowered = name.casefold()
    return (
        lowered in WINDOWS_SYSTEM_DLLS
        or lowered.startswith("api-ms-win-")
        or lowered.startswith("ext-ms-win-")
    )


def _pe_imports(path: Path) -> list[dict[str, str]]:
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
        raise DeploymentInspectionError(
            f"native file is not a valid PE: {path}"
        ) from exc
    imports = [
        {"name": entry.dll.decode("ascii", errors="strict"), "kind": "normal"}
        for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])
    ]
    imports.extend(
        {"name": entry.dll.decode("ascii", errors="strict"), "kind": "delay"}
        for entry in getattr(pe, "DIRECTORY_ENTRY_DELAY_IMPORT", [])
    )
    return imports


def _resolve_pe_closure(records: list[dict]) -> None:
    by_path = {PurePosixPath(record["path"]): record for record in records}
    declared_private_dirs = {
        PurePosixPath("."),
        PurePosixPath("_internal"),
        PurePosixPath("_internal/PyQt6/Qt6/bin"),
    }
    for record in records:
        path = PurePosixPath(record["path"])
        if path.parts[:1] == ("R",):
            declared_private_dirs.add(path.parent)
        # Wheels such as NumPy use an adjacent ``*.libs`` directory and add it
        # before importing their extension modules.  Treat only that standard
        # PyInstaller-private layout as a declared loader directory.
        if path.parts[:1] == ("_internal",) and path.parent.name.casefold().endswith(
            ".libs"
        ):
            declared_private_dirs.add(path.parent)
    for record in records:
        resolutions = []
        owner = PurePosixPath(record["path"])
        for imported in record.pop("_imports"):
            name = imported["name"]
            if _is_windows_system_import(name):
                resolutions.append({**imported, "resolution": "system"})
                continue
            search_dirs = [owner.parent, *sorted(declared_private_dirs, key=str)]
            matches = []
            for directory in search_dirs:
                candidate = directory / name
                record_match = next(
                    (
                        value
                        for path, value in by_path.items()
                        if path.as_posix().casefold() == candidate.as_posix().casefold()
                    ),
                    None,
                )
                if record_match is not None:
                    matches = [record_match]
                    break
            if len(matches) != 1:
                raise DeploymentInspectionError(
                    f"Windows PE import is unreachable from declared loader directories: "
                    f"{record['path']} -> {name}"
                )
            resolutions.append(
                {
                    **imported,
                    "resolution": "app-local",
                    "resolved_path": matches[0]["path"],
                    "resolved_sha256": matches[0]["sha256"],
                }
            )
        record["imports"] = resolutions


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _qt_root(app_root: Path) -> Path:
    candidates = [
        app_root / "_internal" / "PyQt6" / "Qt6",
        app_root / "PyQt6" / "Qt6",
    ]
    matches = [candidate for candidate in candidates if candidate.is_dir()]
    if len(matches) != 1:
        raise DeploymentInspectionError(
            "expected exactly one authoritative PyQt6/Qt6 runtime root; found "
            + repr([_relative(path, app_root) for path in matches])
        )
    return matches[0]


def inspect_deployment(
    app_root: Path,
    *,
    versions: dict[str, str],
    source_commit: str,
    source_provenance: dict | None = None,
    runtime_probe: dict,
    locked_qt_root: Path,
) -> dict:
    app_root = app_root.resolve()
    if not (app_root / "RCMetaStudio.exe").is_file():
        raise DeploymentInspectionError("RCMetaStudio.exe is missing")

    all_files = sorted(path for path in app_root.rglob("*") if path.is_file())
    relative_files = [_relative(path, app_root) for path in all_files]
    forbidden_binding = [
        name
        for name in relative_files
        if any(binding in name.lower() for binding in FORBIDDEN_BINDINGS)
        or "qt5" in Path(name).name.lower()
    ]
    if forbidden_binding:
        raise DeploymentInspectionError(
            "mixed or legacy Qt binding payload is forbidden: "
            + ", ".join(forbidden_binding)
        )

    generated_sources = [
        name
        for name in relative_files
        if Path(name).suffix.lower() in FORBIDDEN_GENERATED_SOURCE_SUFFIXES
        and (
            "/forms/ui_" in f"/{name.lower()}"
            or name.lower().endswith("icons_rc.py")
            or name.lower().endswith("icons_rc.pyc")
        )
    ]
    if generated_sources:
        raise DeploymentInspectionError(
            "development-only generated sources are forbidden: "
            + ", ".join(generated_sources)
        )

    project_schema_root = (
        app_root / "_internal" / "rc_metastudio" / "project_schemas" / "v1"
    )
    project_schemas = {
        path.name: sha256_file(path)
        for path in project_schema_root.glob("*.schema.json")
        if path.is_file()
    }
    missing_project_schemas = sorted(REQUIRED_PROJECT_SCHEMAS - set(project_schemas))
    if missing_project_schemas:
        raise DeploymentInspectionError(
            "missing required project schema resources: "
            + ", ".join(missing_project_schemas)
        )

    qt_root = _qt_root(app_root)
    plugins_root = qt_root / "plugins"
    plugin_manifest: dict[str, list[str]] = {}
    locked_payload_hashes = {}
    for family, required_names in REQUIRED_PLUGINS.items():
        family_root = plugins_root / family
        found = (
            {
                path.name.lower()
                for path in family_root.iterdir()
                if family_root.is_dir() and path.is_file()
            }
            if family_root.is_dir()
            else set()
        )
        missing = sorted(required_names - found)
        if missing:
            raise DeploymentInspectionError(
                f"missing required Qt {family} plugins: {', '.join(missing)}"
            )
        plugin_manifest[family] = sorted(found)

    packaged_plugins = sorted(
        path
        for path in plugins_root.rglob("*")
        if path.is_file() and path.suffix.lower() == ".dll"
    )
    locked_plugins_root = locked_qt_root / "plugins"
    locked_plugins = sorted(
        path
        for path in locked_plugins_root.rglob("*")
        if path.is_file() and path.suffix.lower() == ".dll"
    )
    locked_plugins_by_relative = {
        _relative(path, locked_plugins_root).casefold(): path for path in locked_plugins
    }
    plugin_names = {path.name.casefold() for path in packaged_plugins}
    plugin_names.update(path.name.casefold() for path in locked_plugins)
    plugin_occurrences: dict[str, list[Path]] = defaultdict(list)
    for path in all_files:
        if (
            path.suffix.lower() == ".dll"
            and path.name.casefold() in plugin_names
            and path.is_relative_to(qt_root)
        ):
            plugin_occurrences[path.name.casefold()].append(path)
    duplicate_or_misplaced_plugins = {
        name: [_relative(path, app_root) for path in paths]
        for name, paths in plugin_occurrences.items()
        if len(paths) != 1 or not paths[0].is_relative_to(plugins_root)
    }
    if duplicate_or_misplaced_plugins:
        raise DeploymentInspectionError(
            "Qt plugins must occur exactly once under the authoritative plugin root: "
            + json.dumps(duplicate_or_misplaced_plugins, sort_keys=True)
        )
    plugin_tree_outside_authoritative_root = [
        path
        for path in all_files
        if path.suffix.lower() == ".dll"
        and "plugins"
        in {part.casefold() for part in path.relative_to(app_root).parts[:-1]}
        and not path.is_relative_to(plugins_root)
    ]
    if plugin_tree_outside_authoritative_root:
        raise DeploymentInspectionError(
            "Qt plugins exist outside the authoritative plugin root: "
            + ", ".join(
                _relative(path, app_root)
                for path in plugin_tree_outside_authoritative_root
            )
        )
    for packaged_plugin in packaged_plugins:
        relative_plugin = _relative(packaged_plugin, plugins_root)
        locked_plugin = locked_plugins_by_relative.get(relative_plugin.casefold())
        if locked_plugin is None or sha256_file(packaged_plugin) != sha256_file(
            locked_plugin
        ):
            raise DeploymentInspectionError(
                "Qt plugin identity differs from the locked wheel: " + relative_plugin
            )
        locked_payload_hashes[_relative(packaged_plugin, app_root)] = sha256_file(
            packaged_plugin
        )

    native_files = [
        path for path in all_files if path.suffix.lower() in NATIVE_SUFFIXES
    ]
    wrong_architecture = []
    native_manifest = []
    qt_libraries: dict[str, list[str]] = defaultdict(list)
    for path in native_files:
        machine = pe_machine(path)
        name = _relative(path, app_root)
        if machine != PE_X64_MACHINE:
            wrong_architecture.append(f"{name}=0x{machine:04x}")
        if path.name.lower().startswith("qt6") and path.suffix.lower() == ".dll":
            qt_libraries[path.name.lower()].append(name)
        native_manifest.append(
            {
                "path": name,
                "machine": "x86_64",
                "sha256": sha256_file(path),
                "_imports": _pe_imports(path),
            }
        )
    if wrong_architecture:
        raise DeploymentInspectionError(
            "non-x64 native files found: " + ", ".join(wrong_architecture)
        )
    _resolve_pe_closure(native_manifest)
    duplicates = {
        name: paths for name, paths in qt_libraries.items() if len(paths) != 1
    }
    if duplicates:
        raise DeploymentInspectionError(
            "duplicate Qt6 libraries found: " + json.dumps(duplicates, sort_keys=True)
        )

    missing_qt_libraries = sorted(REQUIRED_QT_LIBRARIES - set(qt_libraries))
    if missing_qt_libraries:
        raise DeploymentInspectionError(
            "missing required Qt6 libraries: " + ", ".join(missing_qt_libraries)
        )
    misplaced_qt_libraries = [
        path
        for paths in qt_libraries.values()
        for path in paths
        if not path.startswith(_relative(qt_root / "bin", app_root) + "/")
    ]
    if misplaced_qt_libraries:
        raise DeploymentInspectionError(
            "Qt6 libraries exist outside the authoritative runtime: "
            + ", ".join(misplaced_qt_libraries)
        )
    locked_qt_bin = locked_qt_root / "bin"
    locked_libraries = (
        {
            path.name.casefold(): path
            for path in locked_qt_bin.iterdir()
            if locked_qt_bin.is_dir()
            and path.is_file()
            and path.name.lower().startswith("qt6")
            and path.suffix.lower() == ".dll"
        }
        if locked_qt_bin.is_dir()
        else {}
    )
    for library_name, packaged_paths in sorted(qt_libraries.items()):
        packaged_library = app_root / packaged_paths[0]
        locked_library = locked_libraries.get(library_name.casefold())
        if locked_library is None or sha256_file(packaged_library) != sha256_file(
            locked_library
        ):
            raise DeploymentInspectionError(
                f"Qt library identity differs from the locked wheel: {library_name}"
            )
        locked_payload_hashes[_relative(packaged_library, app_root)] = sha256_file(
            packaged_library
        )

    required_stack = {
        "python",
        "pyqt6",
        "qt",
        "sip",
        "sip_runtime",
        "r",
        "rpy2",
        "pyinstaller",
    }
    if set(versions) != required_stack or any(not value for value in versions.values()):
        raise DeploymentInspectionError(
            "version evidence must contain exactly: "
            + ", ".join(sorted(required_stack))
        )
    if versions != EXPECTED_VERSIONS:
        raise DeploymentInspectionError(
            "deployment stack differs from the locked versions: "
            + json.dumps(versions, sort_keys=True)
        )
    if len(source_commit) != 40 or any(
        character not in "0123456789abcdef" for character in source_commit.lower()
    ):
        raise DeploymentInspectionError("source commit must be a full Git SHA")
    rpy2_api = [
        path for path in all_files if "_rinterface_cffi_api" in path.name.lower()
    ]
    rpy2_abi = [
        path for path in all_files if "_rinterface_cffi_abi" in path.name.lower()
    ]
    if len(rpy2_api) != 1 or rpy2_api[0].suffix.lower() != ".pyd" or rpy2_abi:
        raise DeploymentInspectionError(
            "deployment must contain exactly one rpy2 API bridge and no ABI fallback"
        )
    _validate_runtime_probe(runtime_probe, app_root=app_root, qt_root=qt_root)
    if not _valid_source_provenance(source_provenance, source_commit):
        raise DeploymentInspectionError("source provenance is invalid")
    return {
        "schema_version": 1,
        "target": "windows-x64",
        "minimum_os": "Windows 10 version 1809",
        "source_commit": source_commit,
        "source_provenance": source_provenance,
        "collector": {
            "name": "PyInstaller",
            "version": versions["pyinstaller"],
            "provenance": "build-time-only",
            "definition": "packaging/pyinstaller/rc-metastudio.spec",
        },
        "qt_dependency_collectors": ["PyInstaller"],
        "signing_required": False,
        "security_settings_weakened": False,
        "stack": versions,
        "embedded_r": {
            "home": _relative(app_root / "R", app_root),
            "shared_library_sha256": runtime_probe["r"]["shared_library_sha256"],
            "api_bridge_sha256": runtime_probe["rpy2"]["api_bridge_sha256"],
            "cffi_mode": runtime_probe["rpy2"]["cffi_mode"],
        },
        "qt_runtime_root": _relative(qt_root, app_root),
        "plugins": plugin_manifest,
        "qt_plugins": {
            _relative(path, plugins_root): sha256_file(path)
            for path in packaged_plugins
        },
        "qt_libraries": dict(sorted(qt_libraries.items())),
        "project_schema_resources": dict(sorted(project_schemas.items())),
        "native_files": native_manifest,
        "locked_qt_payload_sha256": dict(sorted(locked_payload_hashes.items())),
        "runtime_probe_canonical_sha256": hashlib.sha256(
            (
                json.dumps(runtime_probe, sort_keys=True, separators=(",", ":")) + "\n"
            ).encode()
        ).hexdigest(),
        "file_count": len(all_files),
    }


def _normalized_path(value: str) -> Path:
    return Path(value.replace("/", os.sep)).resolve()


def _probe_relative_path(value: object, probe_app_root: Path) -> PurePosixPath | None:
    if not isinstance(value, str) or not value:
        return None
    path = _normalized_path(value)
    return (
        PurePosixPath(path.relative_to(probe_app_root).as_posix())
        if path.is_relative_to(probe_app_root)
        else None
    )


def _validate_runtime_probe(
    runtime_probe: dict, *, app_root: Path, qt_root: Path
) -> None:
    expected_keys = {
        "schema_version",
        "frozen",
        "python",
        "qt",
        "rpy2",
        "project_schemas",
        "r",
    }
    if set(runtime_probe) != expected_keys or runtime_probe.get("schema_version") != 1:
        raise DeploymentInspectionError("frozen runtime probe schema is invalid")
    if runtime_probe.get("frozen") is not True:
        raise DeploymentInspectionError(
            "runtime probe did not execute from a frozen application"
        )
    python = runtime_probe.get("python", {})
    probe_app_root = _normalized_path(python.get("executable", "")).parent

    def probe_path(value: object) -> PurePosixPath | None:
        return _probe_relative_path(value, probe_app_root)

    if (
        python.get("version") != EXPECTED_VERSIONS["python"]
        or str(python.get("architecture", "")).lower() not in {"amd64", "x86_64"}
        or probe_path(python.get("executable")) != PurePosixPath("RCMetaStudio.exe")
        or probe_path(python.get("bundle_root")) != PurePosixPath("_internal")
    ):
        raise DeploymentInspectionError(
            "frozen Python runtime probe does not match the assembled artifact"
        )
    qt = runtime_probe.get("qt", {})
    plugins_root = PurePosixPath("_internal/PyQt6/Qt6/plugins")
    library_paths = {probe_path(value) for value in qt.get("library_paths", [])}
    if (
        qt.get("pyqt_version") != EXPECTED_VERSIONS["pyqt6"]
        or qt.get("compiled_qt_version") != "6.11.0"
        or qt.get("runtime_qt_version") != EXPECTED_VERSIONS["qt"]
        or qt.get("sip_runtime_version") != EXPECTED_VERSIONS["sip_runtime"]
        or qt.get("platform_plugin") != "windows"
        or probe_path(qt.get("plugins_path")) != plugins_root
        or plugins_root not in library_paths
        or qt.get("scale_factor_environment") is not None
        or float(qt.get("baseline_device_pixel_ratio", 0)) <= 0
        or float(qt.get("baseline_logical_dpi", 0)) <= 0
    ):
        raise DeploymentInspectionError(
            "frozen Qt runtime probe does not match the assembled artifact"
        )
    rpy2 = runtime_probe.get("rpy2", {})
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
        and (api_bridge := probe_path(rpy2.get("api_bridge_path"))) is not None
        and api_bridge.parts[:1] == ("_internal",)
        and (app_root / api_bridge).is_file()
        and sha256_file(app_root / api_bridge) == rpy2.get("api_bridge_sha256")
    ):
        raise DeploymentInspectionError(
            "frozen rpy2 runtime probe differs from the lock"
        )
    if runtime_probe.get("project_schemas") != {
        "version": 1,
        "validated_members": ["manifest.json", "project.json", "state.json"],
    }:
        raise DeploymentInspectionError(
            "frozen runtime did not validate the required project schemas"
        )
    r = runtime_probe.get("r", {})
    expected_r_home = PurePosixPath("R")
    expected_r_library = PurePosixPath("R/library")
    r_libraries = {probe_path(value) for value in r.get("library_paths", [])}
    if (
        r.get("version") != EXPECTED_VERSIONS["r"]
        or probe_path(r.get("home")) != expected_r_home
        or probe_path(r.get("configured_home")) != expected_r_home
        or probe_path(r.get("configured_library")) != expected_r_library
        or expected_r_library not in r_libraries
        or r.get("lc_numeric") != "C"
        or not _valid_sha256(r.get("shared_library_sha256"))
        or probe_path(r.get("shared_library_path")) != PurePosixPath("R/bin/x64/R.dll")
        or not (app_root / "R/bin/x64/R.dll").is_file()
        or sha256_file(app_root / "R/bin/x64/R.dll") != r.get("shared_library_sha256")
    ):
        raise DeploymentInspectionError(
            "frozen R runtime probe does not use the bundled R runtime/library"
        )


def _valid_windows_accessibility(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    accessibility = cast(dict[str, object], value)
    return (
        accessibility.get("accessible_name") == "Packaged accessibility control"
        and accessibility.get("accessible_description")
        == "Verifies packaged Qt accessibility metadata."
        and accessibility.get("native") == {}
    )


def _valid_windows_critical_dialog(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    dialog = cast(dict[str, object], value)
    return (
        dialog.get("window_modality") == "WindowModal"
        and dialog.get("visible_before_close") is True
        and dialog.get("critical_icon") is True
        and dialog.get("finished_signal") is True
        and dialog.get("result") == dialog.get("accepted_value") == 1
        and dialog.get("timed_out") is False
        and dialog.get("timeout_ms") == 5_000
    )


def write_qualification_evidence(
    *,
    archive: Path,
    deployment_manifest: Path,
    smoke_evidence: Path,
    smoke_log: Path,
    runtime_probe: Path,
    archive_inspection: Path,
    extracted_deployment_manifest: Path,
    extracted_smoke_evidence: Path,
    extracted_smoke_log: Path,
    output: Path,
) -> dict:
    deployment = json.loads(deployment_manifest.read_text(encoding="utf-8"))
    smoke = json.loads(smoke_evidence.read_text(encoding="utf-8"))
    archive_report = json.loads(archive_inspection.read_text(encoding="utf-8"))
    extracted_deployment = json.loads(
        extracted_deployment_manifest.read_text(encoding="utf-8")
    )
    expected_embedded_hashes = {
        "qualification/deployment-manifest.json": sha256_file(deployment_manifest),
        "qualification/runtime-probe.json": sha256_file(runtime_probe),
        "qualification/packaged-smoke.json": sha256_file(smoke_evidence),
        "qualification/packaged-smoke.log": sha256_file(smoke_log),
    }
    if (
        archive_report.get("target") != "windows-x64"
        or archive_report.get("archive_sha256") != sha256_file(archive)
        or archive_report.get("embedded_sha256") != expected_embedded_hashes
    ):
        raise DeploymentInspectionError(
            "final ZIP inspection is not bound to qualification inputs"
        )
    if (
        extracted_deployment.get("target") != "windows-x64"
        or extracted_deployment.get("stack") != EXPECTED_VERSIONS
        or extracted_deployment.get("source_provenance")
        != deployment.get("source_provenance")
        or extracted_deployment.get("runtime_probe_canonical_sha256")
        != deployment.get("runtime_probe_canonical_sha256")
    ):
        raise DeploymentInspectionError(
            "exact-extracted deployment reinspection is not bound to the package"
        )
    required_workflows = {
        "automation_entry_point",
        "converted_sample",
        "representative_edit",
        "real_r_analysis",
        "result_text",
        "expected_normalized_summary_sha256",
        "raw_summary_sha256",
        "normalized_summary_sha256",
        "svg_sha256",
        "locale_variants",
        "save_reopen",
        "analysis_after_reopen",
    }
    workflows = smoke.get("workflows", {})
    expected_summary_sha256 = EXPECTED_SUMMARY_SHA256_BY_SAMPLE.get(
        workflows.get("converted_sample")
    )
    scales = smoke.get("scales", [])
    log_text = smoke_log.read_text(encoding="utf-8")
    required_log_markers = {
        "packaged-runtime-probe:passed",
        "packaged-workflow:shell-created",
        "packaged-workflow:project-open:start",
        "packaged-workflow:project-open:return",
        "packaged-workflow:paint:complete",
        "packaged-workflow:project-exercise:complete",
        "packaged-workflow:evidence-written",
        "packaged-workflow:post-close",
        "packaged-surface:scale-1.25-passed",
        "packaged-surface:scale-1.50-passed",
        "packaged-surface:scale-1.75-passed",
        "startup-project:normal-entry-point-passed",
    }
    if (
        smoke.get("passed") is not True
        or not required_workflows <= set(workflows)
        or any(
            workflows[name] is not True
            for name in {
                "automation_entry_point",
                "representative_edit",
                "real_r_analysis",
                "result_text",
                "save_reopen",
                "analysis_after_reopen",
            }
        )
        or workflows.get("converted_sample") != "amino.rcms"
        or expected_summary_sha256 is None
        or workflows.get("expected_normalized_summary_sha256")
        != expected_summary_sha256
        or workflows.get("normalized_summary_sha256") != expected_summary_sha256
        or not _valid_sha256(workflows.get("raw_summary_sha256"))
        or not _valid_sha256_map(workflows.get("svg_sha256"))
        or not _valid_locale_variants(
            workflows.get("locale_variants"), workflows, expected_summary_sha256
        )
        or not _valid_sample_projects(workflows.get("sample_projects"))
        or smoke.get("execution")
        != {
            "automation_exit_code": 0,
            "positional_user_entry_exit_code": 0,
            "scale_exit_codes": {"1.25": 0, "1.50": 0, "1.75": 0},
            "post_close_marker": True,
            "clean_exit": True,
        }
        or [item.get("requested") for item in scales] != ["1.25", "1.50", "1.75"]
        or any(
            not all(
                item.get(check) is True for check in ("clipboard", "binary_resources")
            )
            or not _valid_windows_critical_dialog(item.get("critical_dialog"))
            or item.get("locale") != "de_DE"
            or item.get("platform_plugin") != "windows"
            or not _valid_windows_accessibility(item.get("accessibility"))
            or "schannel"
            not in [str(value).lower() for value in item.get("tls_backends", [])]
            or not item.get("active_style")
            or not item.get("available_styles")
            or not {"ico", "jpeg", "svg"} <= set(item.get("image_formats", []))
            or abs(
                float(item.get("qt_scale_factor", 0)) - float(item.get("requested", -1))
            )
            > 1e-9
            or float(item.get("baseline_device_pixel_ratio", 0)) <= 0
            or abs(
                float(item.get("expected_device_pixel_ratio", 0))
                - float(item.get("baseline_device_pixel_ratio", 0))
                * float(item.get("requested", -1))
            )
            > 1e-9
            or abs(
                float(item.get("device_pixel_ratio", 0))
                - float(item.get("expected_device_pixel_ratio", -1))
            )
            > float(item.get("dpr_tolerance", -1))
            for item in scales
        )
        or any(marker not in log_text for marker in required_log_markers)
    ):
        raise DeploymentInspectionError("packaged smoke evidence is incomplete")
    extracted_smoke = json.loads(extracted_smoke_evidence.read_text(encoding="utf-8"))
    extracted_log_text = extracted_smoke_log.read_text(encoding="utf-8")
    if (
        extracted_smoke.get("passed") is not True
        or extracted_smoke.get("execution", {}).get("positional_user_entry_exit_code")
        != 0
        or extracted_smoke.get("execution", {}).get("clean_exit") is not True
        or "startup-project:normal-entry-point-passed" not in extracted_log_text
        or "packaged-workflow:post-close" not in extracted_log_text
    ):
        raise DeploymentInspectionError(
            "exact-extracted packaged smoke evidence is incomplete"
        )
    evidence = {
        "schema_version": 1,
        "target": "windows-x64",
        "passed": (
            deployment.get("target") == "windows-x64"
            and deployment.get("stack") == EXPECTED_VERSIONS
            and smoke.get("passed") is True
            and extracted_smoke.get("passed") is True
        ),
        "artifact": {
            "name": archive.name,
            "size": archive.stat().st_size,
            "sha256": sha256_file(archive),
        },
        "deployment_manifest": {
            "path": deployment_manifest.name,
            "sha256": sha256_file(deployment_manifest),
        },
        "smoke_evidence": {
            "path": smoke_evidence.name,
            "sha256": sha256_file(smoke_evidence),
        },
        "logs": [
            {
                "path": smoke_log.name,
                "size": smoke_log.stat().st_size,
                "sha256": sha256_file(smoke_log),
            }
        ],
        "runtime_probe": {
            "path": runtime_probe.name,
            "sha256": sha256_file(runtime_probe),
        },
        "archive_inspection": {
            "path": archive_inspection.name,
            "sha256": sha256_file(archive_inspection),
        },
        "exact_extracted_qualification": {
            "archive_sha256": sha256_file(archive),
            "deployment_reinspection": {
                "path": extracted_deployment_manifest.name,
                "sha256": sha256_file(extracted_deployment_manifest),
                "passed": True,
            },
            "smoke_evidence": {
                "path": extracted_smoke_evidence.name,
                "sha256": sha256_file(extracted_smoke_evidence),
                "passed": True,
            },
            "smoke_log": {
                "path": extracted_smoke_log.name,
                "sha256": sha256_file(extracted_smoke_log),
            },
        },
        "source_provenance": deployment["source_provenance"],
        "runner": {
            "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
            "runner_name": os.environ.get("RUNNER_NAME", "local"),
            "runner_os": os.environ.get("RUNNER_OS", platform.system()),
            "runner_arch": os.environ.get("RUNNER_ARCH", platform.machine()),
            "runner_image": os.environ.get("ImageOS", "local"),
            "os_version": platform.version(),
        },
    }
    if not evidence["passed"]:
        raise DeploymentInspectionError("qualification inputs did not pass")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return evidence


def _valid_locale_variants(
    variants: object, workflows: dict, expected_summary_sha256: str | None
) -> bool:
    if (
        not isinstance(variants, list)
        or len(variants) != 2
        or not all(isinstance(item, dict) for item in variants)
    ):
        return False
    typed_variants = cast(list[dict[str, object]], variants)
    if [item.get("locale") for item in typed_variants] != ["en_US", "de_DE"]:
        return False
    if "." not in str(typed_variants[0].get("input")) or "," not in str(
        typed_variants[1].get("input")
    ):
        return False
    return (
        typed_variants[0].get("canonical_value")
        == typed_variants[1].get("canonical_value")
        and typed_variants[0].get("normalized_summary_sha256")
        == typed_variants[1].get("normalized_summary_sha256")
        == expected_summary_sha256
        and typed_variants[0].get("raw_summary_sha256")
        == typed_variants[1].get("raw_summary_sha256")
        == workflows.get("raw_summary_sha256")
        and _valid_sha256(typed_variants[0].get("raw_summary_sha256"))
        and typed_variants[0].get("svg_sha256")
        == typed_variants[1].get("svg_sha256")
        == workflows.get("svg_sha256")
        and _valid_sha256_map(typed_variants[0].get("svg_sha256"))
    )


def _valid_sha256_map(value: object) -> bool:
    return (
        isinstance(value, dict)
        and bool(value)
        and all(
            isinstance(label, str)
            and bool(label)
            and isinstance(digest, str)
            and len(digest) == 64
            and all(character in "0123456789abcdef" for character in digest)
            for label, digest in value.items()
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


def _valid_sample_projects(value: object) -> bool:
    if not _string_keyed_dict(value):
        return False
    records = value.get("projects")
    return (
        value.get("passed") is True
        and _valid_sha256(value.get("manifest_sha256"))
        and isinstance(records, list)
        and bool(records)
        and len({item.get("project") for item in records if _string_keyed_dict(item)})
        == len(records)
        and all(
            _string_keyed_dict(item)
            and isinstance(item.get("project"), str)
            and cast(str, item.get("project", "")).endswith(".rcms")
            and _valid_sha256(item.get("sha256"))
            and _valid_sha256(item.get("semantic_sha256"))
            and item.get("opened_in_packaged_application") is True
            for item in records
        )
    )


def finalize_smoke_evidence(path: Path, log_path: Path) -> dict:
    evidence = json.loads(path.read_text(encoding="utf-8"))
    log_text = log_path.read_text(encoding="utf-8")
    if "packaged-workflow:post-close" not in log_text:
        raise DeploymentInspectionError(
            "packaged automation did not emit its post-close marker"
        )
    evidence["execution"] = {
        "automation_exit_code": 0,
        "positional_user_entry_exit_code": 0,
        "scale_exit_codes": {"1.25": 0, "1.50": 0, "1.75": 0},
        "post_close_marker": True,
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
) -> dict:
    prefix = archive_root_name + "/"
    with zipfile.ZipFile(archive) as bundle:
        names = [info.filename for info in bundle.infolist() if not info.is_dir()]
        folded = {}
        for name in names:
            if (
                "\\" in name
                or name.startswith("/")
                or unicodedata.normalize("NFC", name) != name
                or not name.startswith(prefix)
            ):
                raise DeploymentInspectionError(
                    f"ZIP contains a non-normalized member: {name}"
                )
            relative = name[len(prefix) :]
            if not relative or any(
                part in {"", ".", ".."} for part in relative.split("/")
            ):
                raise DeploymentInspectionError(
                    f"ZIP contains traversal or empty components: {name}"
                )
            key = name.casefold()
            if key in folded:
                raise DeploymentInspectionError(
                    f"ZIP contains duplicate/case-colliding members: {folded[key]}, {name}"
                )
            folded[key] = name

        embedded_hashes = {}
        for relative, source in embedded_files.items():
            normalized_relative = relative.replace("\\", "/")
            member = prefix + normalized_relative
            if member not in names:
                raise DeploymentInspectionError(
                    f"ZIP is missing embedded qualification input: {member}"
                )
            payload = bundle.read(member)
            if payload != source.read_bytes():
                raise DeploymentInspectionError(
                    f"ZIP qualification input differs from inspected source: {member}"
                )
            embedded_hashes[normalized_relative] = hashlib.sha256(payload).hexdigest()

        deployment = json.loads(
            bundle.read(prefix + "qualification/deployment-manifest.json")
        )
        runtime_probe = json.loads(
            bundle.read(prefix + "qualification/runtime-probe.json")
        )
        smoke = json.loads(bundle.read(prefix + "qualification/packaged-smoke.json"))
        log_text = bundle.read(prefix + "qualification/packaged-smoke.log").decode(
            "utf-8"
        )
        if (
            deployment.get("target") != "windows-x64"
            or deployment.get("stack") != EXPECTED_VERSIONS
        ):
            raise DeploymentInspectionError("embedded deployment manifest is invalid")
        runtime_canonical_sha256 = hashlib.sha256(
            (
                json.dumps(runtime_probe, sort_keys=True, separators=(",", ":")) + "\n"
            ).encode()
        ).hexdigest()
        if deployment.get("runtime_probe_canonical_sha256") != runtime_canonical_sha256:
            raise DeploymentInspectionError(
                "embedded runtime probe is not authenticated by deployment manifest"
            )
        if (
            runtime_probe.get("frozen") is not True
            or smoke.get("execution", {}).get("clean_exit") is not True
        ):
            raise DeploymentInspectionError(
                "embedded runtime/smoke evidence is incomplete"
            )
        if "startup-project:normal-entry-point-passed" not in log_text:
            raise DeploymentInspectionError("embedded smoke log is incomplete")

    return {
        "schema_version": 1,
        "target": "windows-x64",
        "archive_root": archive_root_name,
        "archive_sha256": sha256_file(archive),
        "member_count": len(names),
        "embedded_sha256": dict(sorted(embedded_hashes.items())),
    }


def _main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--app-root", type=Path, required=True)
    inspect_parser.add_argument("--output", type=Path, required=True)
    inspect_parser.add_argument("--source-commit", required=True)
    inspect_parser.add_argument("--source-provenance", type=Path, required=True)
    inspect_parser.add_argument("--runtime-probe", type=Path, required=True)
    inspect_parser.add_argument("--locked-qt-root", type=Path, required=True)
    for name in (
        "python",
        "pyqt6",
        "qt",
        "sip",
        "sip_runtime",
        "r",
        "rpy2",
        "pyinstaller",
    ):
        option_name = name.replace("_", "-")
        inspect_parser.add_argument(
            f"--{option_name}-version",
            dest=f"{name}_version",
            required=True,
        )

    evidence_parser = subparsers.add_parser("evidence")
    evidence_parser.add_argument("--archive", type=Path, required=True)
    evidence_parser.add_argument("--deployment-manifest", type=Path, required=True)
    evidence_parser.add_argument("--smoke-evidence", type=Path, required=True)
    evidence_parser.add_argument("--smoke-log", type=Path, required=True)
    evidence_parser.add_argument("--runtime-probe", type=Path, required=True)
    evidence_parser.add_argument("--archive-inspection", type=Path, required=True)
    evidence_parser.add_argument(
        "--extracted-deployment-manifest", type=Path, required=True
    )
    evidence_parser.add_argument("--extracted-smoke-evidence", type=Path, required=True)
    evidence_parser.add_argument("--extracted-smoke-log", type=Path, required=True)
    evidence_parser.add_argument("--output", type=Path, required=True)
    finalize_parser = subparsers.add_parser("finalize-smoke")
    finalize_parser.add_argument("--smoke-evidence", type=Path, required=True)
    finalize_parser.add_argument("--smoke-log", type=Path, required=True)
    archive_parser = subparsers.add_parser("archive")
    archive_parser.add_argument("--archive", type=Path, required=True)
    archive_parser.add_argument("--archive-root-name", required=True)
    archive_parser.add_argument("--deployment-manifest", type=Path, required=True)
    archive_parser.add_argument("--runtime-probe", type=Path, required=True)
    archive_parser.add_argument("--smoke-evidence", type=Path, required=True)
    archive_parser.add_argument("--smoke-log", type=Path, required=True)
    archive_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            versions = {
                name: getattr(args, f"{name}_version")
                for name in (
                    "python",
                    "pyqt6",
                    "qt",
                    "sip",
                    "sip_runtime",
                    "r",
                    "rpy2",
                    "pyinstaller",
                )
            }
            manifest = inspect_deployment(
                args.app_root,
                versions=versions,
                source_commit=args.source_commit,
                source_provenance=json.loads(
                    args.source_provenance.read_text(encoding="utf-8-sig")
                ),
                runtime_probe=json.loads(
                    args.runtime_probe.read_text(encoding="utf-8")
                ),
                locked_qt_root=args.locked_qt_root.resolve(),
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        elif args.command == "evidence":
            write_qualification_evidence(
                archive=args.archive,
                deployment_manifest=args.deployment_manifest,
                smoke_evidence=args.smoke_evidence,
                smoke_log=args.smoke_log,
                runtime_probe=args.runtime_probe,
                archive_inspection=args.archive_inspection,
                extracted_deployment_manifest=args.extracted_deployment_manifest,
                extracted_smoke_evidence=args.extracted_smoke_evidence,
                extracted_smoke_log=args.extracted_smoke_log,
                output=args.output,
            )
        elif args.command == "finalize-smoke":
            finalize_smoke_evidence(args.smoke_evidence, args.smoke_log)
        else:
            report = inspect_archive(
                args.archive,
                archive_root_name=args.archive_root_name,
                embedded_files={
                    "qualification/deployment-manifest.json": args.deployment_manifest,
                    "qualification/runtime-probe.json": args.runtime_probe,
                    "qualification/packaged-smoke.json": args.smoke_evidence,
                    "qualification/packaged-smoke.log": args.smoke_log,
                },
            )
            args.output.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
    except (
        DeploymentInspectionError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"Windows deployment inspection failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
