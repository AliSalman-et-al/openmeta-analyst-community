"""Run and validate the pre-codemod native macOS Qt6 feasibility proof."""

from __future__ import annotations

import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import platform
import posixpath
import re
import shutil
import subprocess
import sys
from typing import Any, BinaryIO, Literal, NoReturn, cast


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_VERSIONS = {
    "python": "3.11.9",
    "pyqt6": "6.11.0",
    "qt": "6.11.1",
    "sip": "13.11.1",
    "r": "4.6.1",
    "rpy2": "3.6.7",
    "pyinstaller": "6.21.0",
}
TARGET_MACHINES = {"macos-x64": "x86_64", "macos-arm64": "arm64"}
DIAGNOSTIC_KEYS = {"source_smoke", "pyinstaller_build", "packaged_smoke"}
NATIVE_COMPONENT_KEYS = {
    "python",
    "pyqt6_qtcore",
    "qt6_core",
    "sip",
    "r",
    "rpy2",
    "rcc",
    "cocoa_plugin",
}
RUNNER_KEYS = {
    "system",
    "release",
    "platform",
    "machine",
    "python_machine",
    "rosetta_translated",
    "github_runner_os",
    "github_runner_arch",
    "runner_image",
}
MAX_DEPLOYMENT_FILES = 10_000
MAX_DEPLOYMENT_BYTES = 1_000_000_000
MAX_RETAINED_NATIVE_BYTES = 100_000_000
MAX_MACHO_ARCHITECTURES = 16
MACHO_CPU_ARCHITECTURES = {
    0x01000007: "x86_64",
    0x0100000C: "arm64",
}
MACHO_CPU_SUBTYPE_MASK = 0xFF000000
MACHO_CPU_SUBTYPES = {
    0x01000007: {3: {0, 0x80000000}},
    0x0100000C: {0: {0}},
}
MACHO_THIN_MAGICS: dict[bytes, tuple[Literal["big", "little"], int, bool]] = {
    b"\xfe\xed\xfa\xce": ("big", 28, False),
    b"\xce\xfa\xed\xfe": ("little", 28, False),
    b"\xfe\xed\xfa\xcf": ("big", 32, True),
    b"\xcf\xfa\xed\xfe": ("little", 32, True),
}
MACHO_FAT_MAGICS: dict[bytes, tuple[Literal["big", "little"], int]] = {
    b"\xca\xfe\xba\xbe": ("big", 20),
    b"\xbe\xba\xfe\xca": ("little", 20),
    b"\xca\xfe\xba\xbf": ("big", 32),
    b"\xbf\xba\xfe\xca": ("little", 32),
}


class EvidenceError(RuntimeError):
    """Raised when native evidence cannot substantiate the locked contract."""


def _fail(message: str) -> NoReturn:
    raise EvidenceError(message)


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _retained_path(record: dict[str, Any], label: str, evidence_dir: Path) -> Path:
    raw_path = record.get("retained_path")
    if not isinstance(raw_path, str) or not raw_path:
        _fail(f"{label} has no retained path")
    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        _fail(f"{label} retained path must remain within the evidence directory")
    return evidence_dir / relative


def _validate_retained_file_record(
    record: dict[str, Any], label: str, evidence_dir: Path | None
) -> None:
    digest = record.get("sha256")
    size = record.get("size")
    if not isinstance(record.get("retained_path"), str) or not isinstance(
        digest, str
    ):
        _fail(f"{label} has no retained path or digest")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        _fail(f"{label} has an invalid retained size")
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        _fail(f"{label} has an invalid SHA-256 digest")
    if evidence_dir is not None:
        retained = _retained_path(record, label, evidence_dir)
        if (
            not retained.is_file()
            or retained.stat().st_size != size
            or _sha256(retained) != digest
        ):
            _fail(f"{label} does not match its retained bytes")
        architectures = record.get("architectures")
        if isinstance(architectures, list) and architectures:
            if _archs(retained) != architectures:
                _fail(f"{label} architectures do not match retained bytes")


def _normalize_inventory_link(parent: str, link_target: str) -> str:
    if (
        not link_target
        or link_target.startswith("/")
        or "\\" in link_target
        or "\0" in link_target
        or ":" in link_target
        or "//" in link_target
        or any(part == "." for part in link_target.split("/"))
    ):
        _fail("deployment inventory has an unsafe symlink target")
    normalized = posixpath.normpath(posixpath.join(parent, link_target))
    if normalized == ".." or normalized.startswith("../") or normalized.startswith("/"):
        _fail("deployment inventory symlink escapes the virtual bundle")
    return normalized


def _validate_inventory_record_path(path: object, label: str) -> str:
    if not isinstance(path, str) or not path:
        _fail(f"{label} must be a non-empty relative POSIX path")
    if (
        path.startswith("/")
        or "\\" in path
        or "\0" in path
        or ":" in path
        or "//" in path
    ):
        _fail(f"{label} is not a canonical relative POSIX path")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts) or posixpath.normpath(path) != path:
        _fail(f"{label} contains path-normalization ambiguity")
    return path


def _validate_inventory_symlinks(
    records: dict[str, dict[str, Any]],
) -> dict[str, str]:
    virtual_nodes = set(records)
    for path in records:
        components = path.split("/")
        virtual_nodes.update(
            "/".join(components[:index]) for index in range(1, len(components))
        )

    resolution_cache: dict[str, str] = {}

    def resolve(start: str) -> str:
        current = start
        seen: set[str] = set()
        cacheable: list[str] = []
        hop_bound = len(records)
        for _hop in range(hop_bound + 1):
            components = current.split("/")
            symlink_path = None
            suffix: list[str] = []
            for index in range(1, len(components) + 1):
                prefix = "/".join(components[:index])
                record = records.get(prefix)
                if record is not None and record.get("kind") == "symlink":
                    symlink_path = prefix
                    suffix = components[index:]
                    break
            if symlink_path is None:
                for path in cacheable:
                    resolution_cache[path] = current
                return current
            if symlink_path in seen:
                _fail(f"deployment inventory contains a cyclic symlink at {symlink_path}")
            seen.add(symlink_path)
            if not suffix:
                cacheable.append(symlink_path)
            cached = resolution_cache.get(symlink_path)
            if cached is None:
                record = records[symlink_path]
                cached = _normalize_inventory_link(
                    posixpath.dirname(symlink_path), cast(str, record["link_target"])
                )
            current = posixpath.join(cached, *suffix) if suffix else cached
        _fail(f"deployment inventory symlink hop bound exceeded at {start}")

    resolved_links: dict[str, str] = {}
    for path, record in records.items():
        if record.get("kind") != "symlink":
            continue
        resolved = resolve(path)
        if resolved not in virtual_nodes:
            _fail(f"deployment inventory contains a dangling symlink at {path}")
        if record.get("resolved_path") != resolved:
            _fail(f"deployment inventory symlink resolution mismatch at {path}")
        resolved_links[path] = resolved
    return resolved_links


def _is_shiboken_native_payload(parts: list[str], name: str) -> bool:
    if any(part in {"shiboken", "shiboken6"} for part in parts[:-1]):
        return True
    extension = next(
        (candidate for candidate in (".dylib", ".so") if name.endswith(candidate)),
        None,
    )
    if extension is None:
        return False
    stem = name[: -len(extension)]
    return re.match(r"(?:lib)?shiboken6?(?=[._-]|$)", stem) is not None


def _classify_macos_qt_payload(path: str) -> str | None:
    folded = path.casefold()
    name = Path(folded).name
    parts = folded.split("/")
    if (
        any(part.startswith("pyside6") for part in parts)
        or _is_shiboken_native_payload(parts, name)
        or re.fullmatch(
            r"libpyside6(?:\.abi3)?(?:\.\d+)*\.dylib", name
        )
    ):
        return "alternate-binding"
    if any(part == "pyqt6" for part in parts):
        return "pyqt6-binding"
    if any(re.fullmatch(r"qt[a-z0-9]+\.framework", part) for part in parts):
        return "qt-framework"
    if re.fullmatch(
        r"(?:lib)?qt(?:5|6)?[a-z0-9]+"
        r"(?:(?:[_-]debug)|(?:\.(?:abi3|debug|\d+)))*\.dylib",
        name,
    ):
        return "qt-library"
    if re.fullmatch(r"libq[a-z0-9_]+\.dylib", name):
        return "qt-plugin"
    return None


def _is_allowed_authoritative_qt_path(path: str) -> bool:
    relative = path.removeprefix("Contents/Frameworks/PyQt6/Qt6/")
    if relative == "translations":
        return True
    framework = re.fullmatch(
        r"lib/(Qt[A-Za-z0-9]+)\.framework/(.+)", relative
    )
    if framework is not None and framework.group(2) in {
        framework.group(1),
        f"Versions/A/{framework.group(1)}",
        "Versions/A/Resources/Info.plist",
        "Versions/A/_CodeSignature/CodeResources",
        "Versions/Current",
        "Resources",
    }:
        return True
    if re.fullmatch(
        r"plugins/(generic|iconengines|imageformats|platforms|styles)/"
        r"libq[A-Za-z0-9_]+\.dylib",
        relative,
    ):
        return True
    return bool(
        re.fullmatch(r"translations/[^/]+\.qm", relative)
        or re.fullmatch(
            r"(?:resources|data)/(?:[^/]+/)*[^/]+\.(?:bin|conf|dat|ini|json|pak)",
            relative,
        )
    )


def _is_known_pyqt6_binding_module(name: str) -> bool:
    return bool(
        re.fullmatch(r"Qt[A-Za-z0-9]+\.abi3\.so", name)
        or re.fullmatch(r"sip\.cpython-\d+-darwin\.so", name)
    )


def _validate_deployment_inventory(
    value: object,
    expected_machine: str,
    executable: dict[str, Any],
    cocoa_plugin: dict[str, Any],
) -> None:
    inventory = _mapping(value, "deployment inventory")
    if set(inventory) != {"schema_version", "file_count", "total_bytes", "files"}:
        _fail("deployment inventory contains missing or unknown fields")
    files = inventory.get("files")
    if inventory.get("schema_version") != 2 or not isinstance(files, list):
        _fail("deployment inventory has an unsupported schema")
    if not files or len(files) > MAX_DEPLOYMENT_FILES:
        _fail("deployment inventory file count is empty or exceeds its bound")
    records: dict[str, dict[str, Any]] = {}
    total = 0
    for raw_record in files:
        record = _mapping(raw_record, "deployment inventory file")
        path = _validate_inventory_record_path(
            record.get("path"), "deployment inventory record path"
        )
        size = record.get("size")
        if path in records:
            _fail("deployment inventory has a duplicate path")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            _fail(f"deployment inventory has an invalid size for {path}")
        kind = record.get("kind")
        if kind == "file":
            if set(record) != {
                "path",
                "kind",
                "size",
                "sha256",
                "architectures",
            }:
                _fail("deployment inventory file contains missing or unknown fields")
            digest = record.get("sha256")
            architectures = record.get("architectures")
            if not isinstance(digest, str) or len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                _fail(f"deployment inventory has an invalid digest for {path}")
            if not isinstance(architectures, list) or not all(
                architecture in {"x86_64", "arm64"}
                for architecture in architectures
            ):
                _fail(f"deployment inventory has invalid architectures for {path}")
        elif kind == "symlink":
            if set(record) != {
                "path",
                "kind",
                "size",
                "link_target",
                "resolved_path",
            }:
                _fail("deployment inventory symlink contains missing or unknown fields")
            link_target = record.get("link_target")
            resolved_path = record.get("resolved_path")
            if (
                not isinstance(link_target, str)
                or not link_target
                or not isinstance(resolved_path, str)
            ):
                _fail(f"deployment inventory has an unsafe symlink for {path}")
            _validate_inventory_record_path(
                resolved_path, f"deployment inventory resolved path for {path}"
            )
        else:
            _fail(f"deployment inventory has an invalid kind for {path}")
        records[path] = record
        total += size
    if inventory.get("file_count") != len(files) or inventory.get(
        "total_bytes"
    ) != total:
        _fail("deployment inventory totals do not match its files")
    if total > MAX_DEPLOYMENT_BYTES:
        _fail("deployment inventory exceeds the bounded feasibility deployment size")
    resolved_links = _validate_inventory_symlinks(records)

    lowered = [path.lower() for path in records]
    forbidden = ("pyqt5", "pyside2", "pyside6", "qt5")
    if any(token in path for path in lowered for token in forbidden):
        _fail("deployment inventory contains an alternate or legacy Qt binding")
    authoritative_qt_root = "Contents/Frameworks/PyQt6/Qt6/"
    authoritative_binding_root = "Contents/Frameworks/PyQt6/"
    qt_directory_aliases = {
        "Contents/Frameworks/PyQt6/Qt6/translations": (
            "../../../Resources/PyQt6/Qt6/translations",
            "Contents/Resources/PyQt6/Qt6/translations",
        ),
        "Contents/Resources/PyQt6/Qt6/lib": (
            "../../../Frameworks/PyQt6/Qt6/lib",
            "Contents/Frameworks/PyQt6/Qt6/lib",
        ),
        "Contents/Resources/PyQt6/Qt6/plugins": (
            "../../../Frameworks/PyQt6/Qt6/plugins",
            "Contents/Frameworks/PyQt6/Qt6/plugins",
        ),
    }
    present_qt_directory_aliases = set(records).intersection(qt_directory_aliases)
    if present_qt_directory_aliases != set(qt_directory_aliases):
        _fail("deployment inventory has an incomplete Qt directory alias set")
    for path, (expected_link, expected_resolved) in qt_directory_aliases.items():
        record = records[path]
        if record.get("kind") != "symlink":
            _fail(f"Qt directory alias {path} must be a symlink")
        if (
            record.get("link_target") != expected_link
            or resolved_links.get(path) != expected_resolved
        ):
            _fail(f"Qt directory alias {path} targets the wrong canonical root")
    authoritative_files = {
        path: record
        for path, record in records.items()
        if path.startswith(authoritative_qt_root) and record["kind"] == "file"
    }
    if not authoritative_files:
        _fail("deployment inventory is missing the authoritative PyQt6 Qt root")
    for path in records:
        if path.startswith(authoritative_qt_root) and not _is_allowed_authoritative_qt_path(
            path
        ):
            _fail(f"unrecognized payload inside the authoritative Qt root: {path}")
    if not any(
        path.startswith(authoritative_binding_root)
        and path.lower().endswith("/qtcore.abi3.so")
        and record["kind"] == "file"
        for path, record in records.items()
    ):
        _fail("deployment inventory is missing the PyQt6 QtCore extension")
    if not any("rinterface" in path for path in lowered):
        _fail("deployment inventory is missing the packaged rpy2 native bridge")
    cocoa_paths = [
        path
        for path, record in records.items()
        if path.endswith("libqcocoa.dylib") and record["kind"] == "file"
    ]
    authoritative_cocoa = (
        "Contents/Frameworks/PyQt6/Qt6/plugins/platforms/libqcocoa.dylib"
    )
    if cocoa_paths != [authoritative_cocoa]:
        _fail("deployment inventory must contain exactly one Cocoa platform plugin")

    framework_pattern = re.compile(
        r"^Contents/Frameworks/PyQt6/Qt6/lib/(Qt[A-Za-z0-9]+)\.framework/"
        r"Versions/A/\1$"
    )
    canonical_frameworks: dict[str, tuple[str, tuple[str, ...]]] = {}
    canonical_framework_paths: dict[str, str] = {}
    for path, record in authoritative_files.items():
        match = framework_pattern.fullmatch(path)
        if match:
            canonical_frameworks[match.group(1)] = (
                cast(str, record["sha256"]),
                tuple(cast(list[str], record["architectures"])),
            )
            canonical_framework_paths[match.group(1)] = path
    if "QtCore" not in canonical_frameworks:
        _fail("deployment inventory is missing authoritative QtCore")
    for path, record in authoritative_files.items():
        name = Path(path).name
        if name not in canonical_frameworks or framework_pattern.fullmatch(path):
            continue
        identity = (
            cast(str, record["sha256"]),
            tuple(cast(list[str], record["architectures"])),
        )
        expected_alias = (
            f"Contents/Frameworks/PyQt6/Qt6/lib/{name}.framework/{name}"
        )
        if path != expected_alias or identity != canonical_frameworks[name]:
            _fail(f"incoherent authoritative Qt framework alias: {path}")

    binding_extensions = {
        Path(path).name: (
            cast(str, record["sha256"]),
            tuple(cast(list[str], record["architectures"])),
        )
        for path, record in records.items()
        if path.startswith(authoritative_binding_root)
        and not path.startswith(authoritative_qt_root)
        and path.count("/") == 3
        and _is_known_pyqt6_binding_module(Path(path).name)
        and record["kind"] == "file"
    }
    binding_extension_paths = {
        Path(path).name: path
        for path, record in records.items()
        if path.startswith(authoritative_binding_root)
        and not path.startswith(authoritative_qt_root)
        and path.count("/") == 3
        and _is_known_pyqt6_binding_module(Path(path).name)
        and record["kind"] == "file"
    }
    for path in records:
        if (
            path.startswith(authoritative_binding_root)
            and not path.startswith(authoritative_qt_root)
            and path not in binding_extension_paths.values()
        ):
            _fail(f"unrecognized payload inside the authoritative PyQt6 root: {path}")
    for path, record in records.items():
        if record["kind"] == "symlink":
            resolved = resolved_links[path]
            name = Path(path).name
            if name in canonical_framework_paths:
                if resolved != canonical_framework_paths[name]:
                    _fail(f"Qt alias {path} targets the wrong canonical component")
            elif name in binding_extension_paths:
                if resolved != binding_extension_paths[name]:
                    _fail(f"PyQt6 alias {path} targets the wrong canonical extension")
            elif path in qt_directory_aliases:
                continue
            elif match := re.fullmatch(
                r"Contents/Frameworks/PyQt6/Qt6/lib/(Qt[A-Za-z0-9]+)\.framework/"
                r"(Versions/Current|Resources)",
                path,
            ):
                component = match.group(1)
                canonical_path = canonical_framework_paths.get(component)
                if canonical_path is None:
                    _fail(f"framework alias has no canonical component: {path}")
                canonical_root = posixpath.dirname(canonical_path)
                expected = (
                    canonical_root
                    if match.group(2) == "Versions/Current"
                    else canonical_root + "/Resources"
                )
                if resolved != expected:
                    _fail(f"framework alias {path} targets the wrong component")
            elif _classify_macos_qt_payload(path) is not None or any(
                token in path.lower() for token in ("pyqt", "pyside")
            ):
                _fail(f"unrecognized Qt deployment symlink: {path}")
            continue
        if path.startswith(authoritative_qt_root):
            continue
        name = Path(path).name
        identity = (
            cast(str, record["sha256"]),
            tuple(cast(list[str], record["architectures"])),
        )
        if path in binding_extension_paths.values():
            continue
        if name in canonical_frameworks:
            if path not in {
                f"Contents/Frameworks/{name}",
                f"Contents/Resources/{name}",
            } or identity != canonical_frameworks[name]:
                _fail(f"incoherent Qt framework alias: {path}")
        elif name in binding_extensions and path == f"Contents/Resources/PyQt6/{name}":
            if identity != binding_extensions[name]:
                _fail(f"incoherent PyQt6 extension alias: {path}")
        elif re.fullmatch(
            r"Contents/Resources/PyQt6/Qt6/translations/[^/]+\.qm", path
        ):
            continue
        elif path.startswith("Contents/Resources/PyQt6/"):
            _fail(f"unrecognized PyQt6 resource alias: {path}")
        elif (
            path.startswith(("Contents/Frameworks/", "Contents/Resources/"))
            and re.fullmatch(r"Qt[A-Za-z0-9]+", name)
        ) or _classify_macos_qt_payload(path) is not None:
            _fail(f"deployment inventory contains a second Qt payload: {path}")
    for label, artifact in (("executable", executable), ("Cocoa plugin", cocoa_plugin)):
        deployment_path = artifact.get("deployment_path")
        if not isinstance(deployment_path, str) or deployment_path not in records:
            _fail(f"packaged {label} is absent from the deployment inventory")
        inventory_record = records[deployment_path]
        if inventory_record["sha256"] != artifact.get("sha256"):
            _fail(f"packaged {label} digest disagrees with the deployment inventory")
    if authoritative_cocoa != cocoa_plugin.get("deployment_path"):
        _fail("packaged Cocoa plugin path disagrees with the deployment inventory")
    if records[cast(str, executable["deployment_path"])]["architectures"] != [
        expected_machine
    ]:
        _fail("deployment inventory does not prove a thin packaged executable")


def _validate_pyinstaller_build_plan(value: object) -> None:
    plan = _mapping(value, "PyInstaller build plan")
    if set(plan) != {"schema_version", "builder", "arguments", "manual_qt_inputs"}:
        _fail("PyInstaller build plan contains missing or unknown fields")
    arguments = plan.get("arguments")
    if (
        plan.get("schema_version") != 1
        or plan.get("builder") != "PyInstaller"
        or plan.get("manual_qt_inputs") != []
        or not isinstance(arguments, list)
        or not all(isinstance(argument, str) for argument in arguments)
    ):
        _fail("PyInstaller build plan is malformed")
    collection_options = {
        "--add-binary",
        "--collect-all",
        "--collect-binaries",
        "--collect-data",
        "--collect-submodules",
        "--hidden-import",
    }
    normalized_options = {
        argument.partition("=")[0]
        for argument in arguments
        if argument.startswith("--")
    }
    if normalized_options & collection_options:
        _fail("PyInstaller build plan contains a manual Qt collection mechanism")
    expected_options = [
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        "--target-architecture",
        "--distpath",
        "--workpath",
        "--specpath",
        "--add-data",
        "--copy-metadata",
    ]
    if [argument for argument in arguments if argument.startswith("--")] != expected_options:
        _fail("PyInstaller build plan does not match the allowlisted invocation")
    if len(arguments) != 19:
        _fail("PyInstaller build plan does not match the allowlisted invocation")
    add_data_source, separator, add_data_destination = arguments[15].rpartition(":")
    windows_source = PureWindowsPath(add_data_source)
    posix_source = PurePosixPath(add_data_source)
    windows_drive_colons = 1 if re.match(r"^[A-Za-z]:[\\/]", add_data_source) else 0
    if (
        arguments[4:6] != ["--name", "Qt6MacFeasibility"]
        or arguments[6] != "--target-architecture"
        or arguments[7] not in {"x86_64", "arm64"}
        or arguments[8] != "--distpath"
        or arguments[10] != "--workpath"
        or arguments[12] != "--specpath"
        or arguments[14] != "--add-data"
        or separator != ":"
        or add_data_destination != "resources"
        or add_data_source.count(":") != windows_drive_colons
        or not (posix_source.is_absolute() or windows_source.is_absolute())
        or (
            posix_source.name != "icons.rcc"
            and windows_source.name != "icons.rcc"
        )
        or arguments[16:18] != ["--copy-metadata", "rpy2"]
        or not arguments[18].endswith("entry.py")
    ):
        _fail("PyInstaller build plan contains unexpected manual inputs")
    for path_argument in (arguments[9], arguments[11], arguments[13], arguments[18]):
        if not (
            PurePosixPath(path_argument).is_absolute()
            or PureWindowsPath(path_argument).is_absolute()
        ):
            _fail("PyInstaller build plan paths must be absolute")


def validate_evidence(
    evidence: object, target: str, *, evidence_dir: Path | None = None
) -> None:
    """Fail closed unless *evidence* proves one complete native target."""

    if target not in TARGET_MACHINES:
        _fail(f"unsupported target {target!r}")
    root = _mapping(evidence, "evidence")
    expected_root_keys = {
        "schema_version",
        "target",
        "status",
        "runner",
        "dependencies",
        "source_smoke",
        "r_call",
        "package",
        "diagnostics",
        "native_components",
    }
    if set(root) != expected_root_keys:
        _fail("evidence contains missing or unknown top-level fields")
    if root.get("schema_version") != 1 or root.get("status") != "passed":
        _fail("evidence must be a passed schema version 1 record")
    if root.get("target") != target:
        _fail(f"target mismatch: expected {target}")

    expected_machine = TARGET_MACHINES[target]
    runner = _mapping(root.get("runner"), "runner")
    if set(runner) != RUNNER_KEYS:
        _fail("runner identity contains missing or unknown fields")
    if runner.get("system") != "Darwin":
        _fail("runner system must be Darwin")
    if not isinstance(runner.get("release"), str) or not re.fullmatch(
        r"[0-9]+(?:\.[0-9]+){1,3}", runner["release"]
    ):
        _fail("runner release is missing or malformed")
    if not isinstance(runner.get("platform"), str) or not runner["platform"].startswith(
        "macOS-"
    ):
        _fail("runner platform is not a recognized macOS identity")
    if runner.get("machine") != expected_machine:
        _fail(f"runner architecture must be {expected_machine}")
    if runner.get("python_machine") != expected_machine:
        _fail(f"Python architecture must be {expected_machine}")
    if runner.get("rosetta_translated") is not False:
        _fail("Rosetta translation is forbidden")
    expected_github_arch = "ARM64" if target == "macos-arm64" else "X64"
    if runner.get("github_runner_os") != "macOS" or runner.get(
        "github_runner_arch"
    ) != expected_github_arch:
        _fail("GitHub runner OS or architecture identity is inconsistent")
    if not isinstance(runner.get("runner_image"), str) or not re.fullmatch(
        r"macos-[0-9]+(?:-intel)?", runner["runner_image"]
    ):
        _fail("runner image identity is missing or malformed")

    dependencies = _mapping(root.get("dependencies"), "dependencies")
    if dependencies != EXPECTED_VERSIONS:
        differing = sorted(
            key
            for key, value in EXPECTED_VERSIONS.items()
            if dependencies.get(key) != value
        )
        _fail(f"locked dependency mismatch: {', '.join(differing) or 'unexpected keys'}")

    source = _mapping(root.get("source_smoke"), "source_smoke")
    if source.get("qpa") != "cocoa":
        _fail("source smoke did not load the Cocoa platform plugin")
    for key in (
        "visible",
        "resource_registered",
        "svg_rendered",
        "clean_exit",
    ):
        if source.get(key) is not True:
            _fail(f"source smoke did not prove {key}")
    if source.get("form") != "AboutLegalDialog":
        _fail("source smoke did not launch the generated form")
    if not isinstance(source.get("plugin_path"), str):
        _fail("source smoke did not record the Qt plugin path")

    r_call = _mapping(root.get("r_call"), "r_call")
    if r_call.get("expression") != "sum(c(1.25, 2.5, 3.75))" or r_call.get(
        "result"
    ) != 7.5:
        _fail("R result did not match the representative rpy2 call")

    package = _mapping(root.get("package"), "package")
    if package.get("target_arch") != expected_machine:
        _fail(f"packaged target architecture must be {expected_machine}")
    if package.get("qt_dependency_collector") != "PyInstaller":
        _fail("PyInstaller must be the sole Qt dependency collector")
    if package.get("qpa") != "cocoa" or not str(package.get("cocoa_plugin", "")).endswith(
        "libqcocoa.dylib"
    ):
        _fail("packaged smoke did not load its Cocoa platform plugin")
    if package.get("dependencies") != {
        key: EXPECTED_VERSIONS[key] for key in ("pyqt6", "qt", "r", "rpy2")
    }:
        _fail("packaged dependency identities do not match the locked stack")
    for key in (
        "visible",
        "resource_registered",
        "svg_rendered",
        "clean_exit",
    ):
        if package.get(key) is not True:
            _fail(f"packaged smoke did not prove {key}")
    if package.get("r_result") != 7.5:
        _fail("packaged R result did not match the representative call")

    executable = _mapping(package.get("executable"), "package.executable")
    cocoa_plugin = _mapping(package.get("cocoa_plugin_artifact"), "package.cocoa_plugin_artifact")
    if executable.get("architectures") != [expected_machine]:
        _fail("packaged executable must be a thin native binary")
    if expected_machine not in cocoa_plugin.get("architectures", []):
        _fail("packaged Cocoa plugin has no native architecture slice")
    for label, record in (("executable", executable), ("Cocoa plugin", cocoa_plugin)):
        _validate_retained_file_record(record, label, evidence_dir)

    inventory_record = _mapping(package.get("inventory"), "package.inventory")
    build_plan_record = _mapping(package.get("build_plan"), "package.build_plan")
    _validate_retained_file_record(inventory_record, "deployment inventory", evidence_dir)
    _validate_retained_file_record(build_plan_record, "PyInstaller build plan", evidence_dir)
    if evidence_dir is not None:
        inventory = json.loads(
            _retained_path(inventory_record, "deployment inventory", evidence_dir).read_text(
                encoding="utf-8"
            )
        )
        _validate_deployment_inventory(
            inventory, expected_machine, executable, cocoa_plugin
        )
        build_plan = json.loads(
            _retained_path(build_plan_record, "PyInstaller build plan", evidence_dir).read_text(
                encoding="utf-8"
            )
        )
        _validate_pyinstaller_build_plan(build_plan)

    diagnostics = _mapping(root.get("diagnostics"), "diagnostics")
    if set(diagnostics) != DIAGNOSTIC_KEYS:
        _fail("diagnostic inventory is incomplete or contains unknown records")
    for name, raw_record in diagnostics.items():
        record = _mapping(raw_record, f"diagnostics.{name}")
        digest = record.get("sha256")
        if not isinstance(record.get("path"), str) or not isinstance(digest, str):
            _fail(f"diagnostic {name} has no path or digest")
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            _fail(f"diagnostic {name} has an invalid SHA-256 digest")
        if evidence_dir is not None:
            relative = Path(record["path"])
            if relative.is_absolute() or ".." in relative.parts:
                _fail(f"diagnostic {name} path must remain within the evidence directory")
            diagnostic_path = evidence_dir / relative
            if not diagnostic_path.is_file() or _sha256(diagnostic_path) != digest:
                _fail(f"diagnostic {name} digest does not match retained bytes")

    components = _mapping(root.get("native_components"), "native_components")
    if set(components) != NATIVE_COMPONENT_KEYS:
        _fail("native component inventory is incomplete or contains unknown records")
    for name, raw_record in components.items():
        record = _mapping(raw_record, f"native_components.{name}")
        retained = record.get("retained")
        source_paths = record.get("source_paths")
        if not isinstance(retained, list) or not retained or not isinstance(
            source_paths, list
        ) or len(source_paths) != len(retained):
            _fail(f"native component {name} has an incomplete retained inventory")
        for item in retained:
            item_record = _mapping(item, f"native_components.{name}.retained")
            if expected_machine not in item_record.get("architectures", []):
                _fail(f"native component {name} has no {expected_machine} slice")
            _validate_retained_file_record(item_record, f"native component {name}", evidence_dir)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(
    command: list[str],
    *,
    environment: dict[str, str] | None = None,
    log: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if log is not None:
        log.write_text(completed.stdout, encoding="utf-8", newline="\n")
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed with exit {completed.returncode}: {' '.join(command)}\n"
            f"{completed.stdout}"
        )
    return completed


def _macho_cpu_identity(
    cpu_type: int, raw_subtype: int, path: Path
) -> tuple[str, int, int]:
    architecture = MACHO_CPU_ARCHITECTURES.get(cpu_type)
    if architecture is None:
        _fail(f"Mach-O file {path} has unsupported CPU type 0x{cpu_type:08x}")
    base_subtype = raw_subtype & ~MACHO_CPU_SUBTYPE_MASK
    capabilities = raw_subtype & MACHO_CPU_SUBTYPE_MASK
    supported_capabilities = MACHO_CPU_SUBTYPES[cpu_type].get(base_subtype)
    if supported_capabilities is None or capabilities not in supported_capabilities:
        _fail(
            f"Mach-O file {path} has unsupported {architecture} CPU subtype "
            f"0x{raw_subtype:08x}"
        )
    return architecture, base_subtype, capabilities


def _read_macho_bytes(
    stream: BinaryIO, path: Path, offset: int, size: int, label: str
) -> bytes:
    stream.seek(offset)
    value = stream.read(size)
    if len(value) != size:
        _fail(f"Mach-O file {path} has a truncated {label}")
    return value


def _thin_macho_architecture(
    header: bytes, available_size: int, path: Path
) -> tuple[str, int, int]:
    if len(header) < 12:
        _fail(f"Mach-O file {path} has a truncated thin header")
    thin_format = MACHO_THIN_MAGICS.get(header[:4])
    if thin_format is None:
        _fail(f"Mach-O file {path} has an unsupported thin magic")
    byte_order, minimum_header_size, is_64_bit = thin_format
    if available_size < minimum_header_size:
        _fail(f"Mach-O file {path} has a truncated thin header")
    cpu_type = int.from_bytes(header[4:8], byte_order)
    if bool(cpu_type & 0x01000000) != is_64_bit:
        _fail(f"Mach-O file {path} has a CPU type inconsistent with its thin class")
    raw_subtype = int.from_bytes(header[8:12], byte_order)
    return _macho_cpu_identity(cpu_type, raw_subtype, path)


def _archs(path: Path) -> list[str]:
    try:
        file_size = path.stat().st_size
        with path.open("rb") as stream:
            header = _read_macho_bytes(stream, path, 0, 8, "header")
            fat_format = MACHO_FAT_MAGICS.get(header[:4])
            if fat_format is None:
                thin_header = header + _read_macho_bytes(
                    stream, path, 8, 4, "thin header"
                )
                return [_thin_macho_architecture(thin_header, file_size, path)[0]]
            byte_order, entry_size = fat_format
            architecture_count = int.from_bytes(header[4:8], byte_order)
            if not 1 <= architecture_count <= MAX_MACHO_ARCHITECTURES:
                _fail(f"Mach-O file {path} has an invalid fat architecture count")
            table_end = 8 + architecture_count * entry_size
            if table_end > file_size:
                _fail(f"Mach-O file {path} has a truncated fat architecture table")
            architectures: list[str] = []
            slice_ranges: list[tuple[int, int]] = []
            for index in range(architecture_count):
                entry = _read_macho_bytes(
                    stream,
                    path,
                    8 + index * entry_size,
                    entry_size,
                    "fat architecture entry",
                )
                declared = _macho_cpu_identity(
                    int.from_bytes(entry[0:4], byte_order),
                    int.from_bytes(entry[4:8], byte_order),
                    path,
                )
                field_size = 8 if entry_size == 32 else 4
                slice_offset = int.from_bytes(entry[8 : 8 + field_size], byte_order)
                slice_size = int.from_bytes(
                    entry[8 + field_size : 8 + 2 * field_size], byte_order
                )
                alignment_offset = 24 if entry_size == 32 else 16
                alignment = int.from_bytes(
                    entry[alignment_offset : alignment_offset + 4], byte_order
                )
                if entry_size == 32 and int.from_bytes(entry[28:32], byte_order) != 0:
                    _fail(f"Mach-O file {path} has a nonzero fat64 reserved field")
                if (
                    slice_offset < table_end
                    or slice_size < 8
                    or slice_offset > file_size
                    or slice_size > file_size - slice_offset
                    or alignment > 63
                    or slice_offset % (1 << alignment) != 0
                ):
                    _fail(f"Mach-O file {path} has an out-of-bounds fat slice")
                slice_end = slice_offset + slice_size
                if any(
                    slice_offset < existing_end and existing_start < slice_end
                    for existing_start, existing_end in slice_ranges
                ):
                    _fail(f"Mach-O file {path} has overlapping fat slices")
                slice_ranges.append((slice_offset, slice_end))
                actual = _thin_macho_architecture(
                    _read_macho_bytes(
                        stream, path, slice_offset, 12, "fat slice header"
                    ),
                    slice_size,
                    path,
                )
                if actual != declared:
                    _fail(f"Mach-O file {path} has a mismatched fat slice CPU identity")
                architecture = actual[0]
                if architecture in architectures:
                    _fail(f"Mach-O file {path} has a duplicate fat architecture")
                architectures.append(architecture)
            return sorted(architectures)
    except EvidenceError:
        raise
    except OSError as error:
        _fail(f"cannot read Mach-O file {path}: {error}")


def _rosetta_translated() -> bool:
    completed = subprocess.run(
        ["sysctl", "-in", "sysctl.proc_translated"],
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "1"


def _dependency_versions() -> tuple[dict[str, str], float]:
    from PyQt6 import QtCore
    import rpy2.robjects as ro

    result = float(cast(Any, ro.r("sum(c(1.25, 2.5, 3.75))"))[0])
    r_version = str(
        cast(Any, ro.r("paste(R.version$major, R.version$minor, sep='.')"))[0]
    )
    versions = {
        "python": platform.python_version(),
        "pyqt6": QtCore.PYQT_VERSION_STR,
        "qt": QtCore.qVersion(),
        "sip": metadata.version("PyQt6-sip"),
        "r": r_version,
        "rpy2": metadata.version("rpy2"),
        "pyinstaller": metadata.version("pyinstaller"),
    }
    if versions != EXPECTED_VERSIONS:
        raise RuntimeError(f"locked dependency mismatch: {versions!r}")
    if result != 7.5:
        raise RuntimeError(f"representative rpy2 result mismatch: {result!r}")
    return versions, result


def discover_rpy2_native_extensions() -> list[Path]:
    """Return concrete native files owned by locked ``rpy2-rinterface``."""

    import rpy2.rinterface_lib as rinterface_lib

    distribution = metadata.distribution("rpy2-rinterface")
    concrete_roots = {Path(path).resolve() for path in rinterface_lib.__path__}
    candidates = {
        Path(str(distribution.locate_file(file))).resolve()
        for file in distribution.files or []
        if Path(str(file)).suffix.lower() in {".dylib", ".pyd", ".so"}
    }
    extensions = sorted(path for path in candidates if path.is_file())
    if not extensions:
        roots = ", ".join(str(root) for root in sorted(concrete_roots))
        raise RuntimeError(
            "rpy2-rinterface installed no concrete native extension; "
            f"searched distribution files associated with {roots}"
        )
    return extensions


def discover_macos_rcc(sdk_root: Path) -> Path:
    """Resolve one recognized Qt macOS SDK ``rcc`` layout, fail closed otherwise."""

    root = sdk_root.resolve()
    relative_candidates = (
        Path("libexec/rcc"),
        Path("libexec/rcc.app/Contents/MacOS/rcc"),
        Path("bin/rcc"),
        Path("bin/rcc.app/Contents/MacOS/rcc"),
    )
    candidates = set()
    for relative in relative_candidates:
        candidate = root / relative
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if not resolved.is_relative_to(root):
            raise RuntimeError(
                f"Qt macOS SDK rcc escapes the declared SDK root: {candidate} -> "
                f"{resolved}"
            )
        candidates.add(resolved)
    if not candidates:
        searched = ", ".join(relative.as_posix() for relative in relative_candidates)
        raise RuntimeError(
            f"Qt macOS SDK contains no rcc in a recognized layout under {root}; "
            f"searched {searched}"
        )
    if len(candidates) != 1:
        raise RuntimeError(
            "Qt macOS SDK contains ambiguous distinct rcc executables: "
            + ", ".join(str(candidate) for candidate in sorted(candidates))
        )
    return candidates.pop()


def append_github_env(github_env: Path, name: str, value: str) -> None:
    """Append one safe, exact UTF-8 GitHub environment-file assignment."""

    if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", name):
        raise RuntimeError(f"invalid GitHub environment variable name: {name!r}")
    if "\r" in value or "\n" in value:
        raise RuntimeError("GitHub environment variable value contains CR or LF")
    github_env.parent.mkdir(parents=True, exist_ok=True)
    with github_env.open("ab") as stream:
        stream.write(f"{name}={value}\n".encode("utf-8"))


def resolve_macos_rcc(
    sdk_root: Path, github_env: Path, diagnostic: Path
) -> dict[str, object]:
    """Validate, record, and export the exact official SDK ``rcc`` executable."""

    from rc_metastudio.qt6_build import validate_macos_rcc

    rcc = discover_macos_rcc(sdk_root)
    validate_macos_rcc(rcc)
    record: dict[str, object] = {
        "path": str(rcc),
        "version": EXPECTED_VERSIONS["qt"],
        "sha256": _sha256(rcc),
        "architectures": _archs(rcc),
    }
    diagnostic.parent.mkdir(parents=True, exist_ok=True)
    diagnostic.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    append_github_env(github_env, "RCMS_QT6_RCC", str(rcc))
    return record


def _native_component_paths() -> dict[str, list[Path]]:
    from PyQt6 import QtCore, sip

    r_home = Path(_run(["R", "RHOME"]).stdout.strip())
    rcc_value = os.environ.get("RCMS_QT6_RCC")
    if not rcc_value:
        raise RuntimeError("RCMS_QT6_RCC must identify the pinned official Qt SDK rcc")
    plugin_root = Path(
        QtCore.QLibraryInfo.path(QtCore.QLibraryInfo.LibraryPath.PluginsPath)
    )
    library_root = Path(
        QtCore.QLibraryInfo.path(QtCore.QLibraryInfo.LibraryPath.LibrariesPath)
    )
    return {
        "python": [Path(sys.executable)],
        "pyqt6_qtcore": [Path(QtCore.__file__)],
        "qt6_core": [library_root / "QtCore.framework/Versions/A/QtCore"],
        "sip": [Path(sip.__file__)],
        "r": [r_home / "bin/exec/R"],
        "rpy2": discover_rpy2_native_extensions(),
        "rcc": [Path(rcc_value)],
        "cocoa_plugin": [plugin_root / "platforms/libqcocoa.dylib"],
    }


def _retain_native_components(evidence_dir: Path) -> dict[str, dict[str, object]]:
    inventory: dict[str, dict[str, object]] = {}
    total_size = 0
    for name, source_paths in _native_component_paths().items():
        retained_records = []
        resolved_sources = []
        for index, source in enumerate(source_paths):
            resolved = source.resolve()
            if not resolved.is_file():
                raise RuntimeError(f"native component does not exist: {resolved}")
            destination = (
                evidence_dir
                / "native-components"
                / name
                / f"{index:02d}-{resolved.name}"
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(resolved, destination)
            total_size += destination.stat().st_size
            if total_size > MAX_RETAINED_NATIVE_BYTES:
                raise RuntimeError("retained native components exceed the 100 MB bound")
            resolved_sources.append(str(resolved))
            retained_records.append(
                {
                    "retained_path": destination.relative_to(evidence_dir).as_posix(),
                    "size": destination.stat().st_size,
                    "sha256": _sha256(destination),
                    "architectures": _archs(destination),
                }
            )
        inventory[name] = {
            "source_paths": resolved_sources,
            "retained": retained_records,
        }
    return inventory


def _maybe_archs(path: Path) -> list[str]:
    completed = subprocess.run(
        ["lipo", "-archs", str(path)], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        return []
    return sorted(completed.stdout.strip().split())


def _write_deployment_inventory(app_root: Path, destination: Path) -> dict[str, object]:
    root = app_root.resolve()
    files: list[dict[str, object]] = []
    total_bytes = 0
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in list(directories):
            path = current_path / name
            if path.is_symlink():
                directories.remove(name)
                resolved = path.resolve(strict=True)
                if not resolved.is_relative_to(root):
                    raise RuntimeError(f"packaged symlink escapes the app bundle: {path}")
                size = path.lstat().st_size
                files.append(
                    {
                        "path": path.relative_to(root).as_posix(),
                        "kind": "symlink",
                        "size": size,
                        "link_target": os.readlink(path),
                        "resolved_path": resolved.relative_to(root).as_posix(),
                    }
                )
                total_bytes += size
        for name in filenames:
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                resolved = path.resolve(strict=True)
                if not resolved.is_relative_to(root):
                    raise RuntimeError(f"packaged symlink escapes the app bundle: {path}")
                size = path.lstat().st_size
                record: dict[str, object] = {
                    "path": relative,
                    "kind": "symlink",
                    "size": size,
                    "link_target": os.readlink(path),
                    "resolved_path": resolved.relative_to(root).as_posix(),
                }
            else:
                size = path.stat().st_size
                record = {
                    "path": relative,
                    "kind": "file",
                    "size": size,
                    "sha256": _sha256(path),
                    "architectures": _maybe_archs(path),
                }
            files.append(record)
            total_bytes += size
        if len(files) > MAX_DEPLOYMENT_FILES or total_bytes > MAX_DEPLOYMENT_BYTES:
            raise RuntimeError("minimal PyInstaller deployment exceeded its inventory bound")
    files.sort(key=lambda record: cast(str, record["path"]))
    inventory = {
        "schema_version": 2,
        "file_count": len(files),
        "total_bytes": total_bytes,
        "files": files,
    }
    destination.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return inventory


def _retained_record(path: Path, evidence_dir: Path, *, architectures: bool) -> dict[str, object]:
    return {
        "retained_path": path.relative_to(evidence_dir).as_posix(),
        "size": path.stat().st_size,
        "sha256": _sha256(path),
        **({"architectures": _archs(path)} if architectures else {}),
    }


PACKAGED_ENTRY = r'''from __future__ import annotations
import json
import os
from pathlib import Path
import sys
from importlib import metadata
from PyQt6 import QtCore, QtGui, QtWidgets
from generated_form import Ui_AboutLegalDialog
import rpy2.robjects as ro

root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
resource = root / "resources" / "icons.rcc"
registered = QtCore.QResource.registerResource(str(resource))
app = QtWidgets.QApplication(["qt6-macos-feasibility"])
dialog = QtWidgets.QDialog()
Ui_AboutLegalDialog().setupUi(dialog)
svg = QtGui.QIcon(":/icons/actions/about-legal.svg").pixmap(QtCore.QSize(24, 24))
dialog.show()
app.processEvents()
plugin_root = Path(QtCore.QLibraryInfo.path(QtCore.QLibraryInfo.LibraryPath.PluginsPath))
cocoa = plugin_root / "platforms" / "libqcocoa.dylib"
report = {
    "qpa": app.platformName(),
    "visible": dialog.isVisible(),
    "resource_registered": registered,
    "svg_rendered": not svg.isNull(),
    "r_result": float(ro.r("sum(c(1.25, 2.5, 3.75))")[0]),
    "cocoa_plugin": str(cocoa),
    "dependencies": {
        "pyqt6": QtCore.PYQT_VERSION_STR,
        "qt": QtCore.qVersion(),
        "r": str(ro.r("paste(R.version$major, R.version$minor, sep='.')")[0]),
        "rpy2": metadata.version("rpy2"),
    },
}
QtCore.QTimer.singleShot(100, app.quit)
exit_code = app.exec()
report["clean_exit"] = exit_code == 0 and QtCore.QResource.unregisterResource(str(resource))
Path(os.environ["RCMS_FEASIBILITY_REPORT"]).write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
raise SystemExit(exit_code)
'''


def run_feasibility(target: str, evidence_dir: Path) -> dict[str, Any]:
    if sys.platform != "darwin":
        raise RuntimeError("native macOS feasibility can run only on macOS")
    expected_machine = TARGET_MACHINES[target]
    machine = platform.machine().lower()
    if machine != expected_machine or _rosetta_translated():
        raise RuntimeError(
            f"native target mismatch: expected {expected_machine}, got {machine}, "
            f"Rosetta={_rosetta_translated()}"
        )

    evidence_dir.mkdir(parents=True, exist_ok=True)
    build_root = ROOT / "build" / "qt6-macos-feasibility" / target
    if build_root.exists():
        shutil.rmtree(build_root)
    build_root.mkdir(parents=True)

    versions, r_result = _dependency_versions()
    components = _retain_native_components(evidence_dir)
    environment = os.environ.copy()
    environment.pop("QT_QPA_PLATFORM", None)
    source_log = evidence_dir / "source-smoke.json"
    source_completed = _run(
        [
            sys.executable,
            str(ROOT / "scripts/build_qt6.py"),
            "native-smoke",
            "--build-root",
            str(build_root / "source"),
            "--exit-after-ms",
            "100",
        ],
        environment=environment,
    )
    source_log.write_text(source_completed.stdout, encoding="utf-8", newline="\n")
    source = json.loads(source_completed.stdout)

    generated = build_root / "source/generated/rc_metastudio/forms/ui_about_legal.py"
    resource = build_root / "source/resources/icons.rcc"
    work = build_root / "package-source"
    work.mkdir()
    shutil.copy2(generated, work / "generated_form.py")
    (work / "entry.py").write_text(PACKAGED_ENTRY, encoding="utf-8", newline="\n")
    pyinstaller_log = evidence_dir / "pyinstaller-build.log"
    target_arch = "x86_64" if target == "macos-x64" else "arm64"
    pyinstaller_arguments = [
            "--noconfirm",
            "--clean",
            "--windowed",
            "--onedir",
            "--name",
            "Qt6MacFeasibility",
            "--target-architecture",
            target_arch,
            "--distpath",
            str(build_root / "dist"),
            "--workpath",
            str(build_root / "work"),
            "--specpath",
            str(build_root),
            "--add-data",
            f"{resource}:resources",
            "--copy-metadata",
            "rpy2",
            str(work / "entry.py"),
        ]
    build_plan_path = evidence_dir / "pyinstaller-build-plan.json"
    build_plan = {
        "schema_version": 1,
        "builder": "PyInstaller",
        "arguments": pyinstaller_arguments,
        "manual_qt_inputs": [],
    }
    build_plan_path.write_text(
        json.dumps(build_plan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _run(
        [sys.executable, "-m", "PyInstaller", *pyinstaller_arguments],
        environment=environment,
        log=pyinstaller_log,
    )
    executable = (
        build_root
        / "dist/Qt6MacFeasibility.app/Contents/MacOS/Qt6MacFeasibility"
    )
    packaged_report = evidence_dir / "packaged-smoke.json"
    package_environment = environment.copy()
    package_environment["RCMS_FEASIBILITY_REPORT"] = str(packaged_report)
    _run([str(executable)], environment=package_environment)
    package = json.loads(packaged_report.read_text(encoding="utf-8"))
    plugin = Path(package["cocoa_plugin"])
    app_root = build_root / "dist/Qt6MacFeasibility.app"
    if not plugin.is_file() or app_root not in plugin.parents:
        raise RuntimeError(f"Cocoa plugin was not collected inside the app: {plugin}")
    package["cocoa_plugin"] = plugin.relative_to(app_root).as_posix()
    probe_root = evidence_dir / "package-probe"
    probe_root.mkdir()
    retained_executable = probe_root / "Qt6MacFeasibility"
    retained_plugin = probe_root / "libqcocoa.dylib"
    shutil.copy2(executable, retained_executable)
    shutil.copy2(plugin, retained_plugin)
    inventory_path = evidence_dir / "pyinstaller-deployment-inventory.json"
    _write_deployment_inventory(app_root, inventory_path)
    package.update(
        {
            "target_arch": expected_machine,
            "qt_dependency_collector": "PyInstaller",
            "executable": {
                **_retained_record(
                    retained_executable, evidence_dir, architectures=True
                ),
                "deployment_path": executable.relative_to(app_root).as_posix(),
            },
            "cocoa_plugin_artifact": {
                **_retained_record(retained_plugin, evidence_dir, architectures=True),
                "deployment_path": plugin.relative_to(app_root).as_posix(),
            },
            "inventory": _retained_record(
                inventory_path, evidence_dir, architectures=False
            ),
            "build_plan": _retained_record(
                build_plan_path, evidence_dir, architectures=False
            ),
        }
    )

    evidence: dict[str, Any] = {
        "schema_version": 1,
        "target": target,
        "status": "passed",
        "runner": {
            "system": platform.system(),
            "release": platform.release(),
            "platform": platform.platform(),
            "machine": machine,
            "python_machine": platform.machine().lower(),
            "rosetta_translated": False,
            "github_runner_os": os.environ.get("RUNNER_OS", ""),
            "github_runner_arch": os.environ.get("RUNNER_ARCH", ""),
            "runner_image": os.environ.get("RCMS_RUNNER_IMAGE", ""),
        },
        "dependencies": versions,
        "source_smoke": {
            "qpa": source["qpa"],
            "visible": source["visible"],
            "form": source["form"],
            "resource_registered": source["resource_registered"],
            "svg_rendered": source["svg_icon"],
            "clean_exit": source["clean_exit"],
            "plugin_path": source["plugin_path"],
        },
        "r_call": {
            "expression": "sum(c(1.25, 2.5, 3.75))",
            "result": r_result,
        },
        "package": package,
        "diagnostics": {},
        "native_components": components,
    }
    for key, path in {
        "source_smoke": source_log,
        "pyinstaller_build": pyinstaller_log,
        "packaged_smoke": packaged_report,
    }.items():
        evidence["diagnostics"][key] = {
            "path": path.name,
            "sha256": _sha256(path),
        }
    validate_evidence(evidence, target, evidence_dir=evidence_dir)
    output = evidence_dir / "evidence.json"
    output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return evidence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--target", choices=sorted(TARGET_MACHINES), required=True)
    run.add_argument("--evidence-dir", type=Path, required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--target", choices=sorted(TARGET_MACHINES), required=True)
    validate.add_argument("--evidence", type=Path, required=True)
    resolve = subparsers.add_parser("resolve-rcc")
    resolve.add_argument("--sdk-root", type=Path, required=True)
    resolve.add_argument("--github-env", type=Path, required=True)
    resolve.add_argument("--diagnostic", type=Path, required=True)
    return parser


def main(arguments: list[str] | None = None) -> int:
    options = _parser().parse_args(arguments)
    if options.command == "run":
        run_feasibility(options.target, options.evidence_dir.resolve())
        return 0
    if options.command == "resolve-rcc":
        record = resolve_macos_rcc(
            options.sdk_root.resolve(),
            options.github_env.resolve(),
            options.diagnostic.resolve(),
        )
        print(json.dumps(record, sort_keys=True))
        return 0
    evidence = json.loads(options.evidence.read_text(encoding="utf-8"))
    validate_evidence(evidence, options.target, evidence_dir=options.evidence.parent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
