# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure validation and inventory helpers for native macOS evidence.

This module owns the evidence contract and filesystem hashing. The feasibility
runner imports these functions but remains responsible for invoking native
toolchains and assembling evidence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import posixpath
import re
from typing import Any, Callable, NoReturn, cast

from rc_metastudio.macos_macho import (
    MachOError,
    architectures as _macho_architectures,
    is_macho_candidate as _is_macho_candidate,
    is_valid_java_class as _is_valid_java_class,
)

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
DIAGNOSTIC_KEYS = {
    "r_profile_quarantine",
    "source_smoke",
    "pyinstaller_build",
    "packaged_smoke",
    "packaged_phases",
    "packaged_r_graph",
}
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
MAX_DEPLOYMENT_FILES = 10_000
MAX_DEPLOYMENT_BYTES = 1_000_000_000
MAX_RETAINED_NATIVE_BYTES = 100_000_000


class EvidenceError(RuntimeError):
    """Raised when native evidence cannot substantiate the locked contract."""


def is_valid_java_class(path: Path) -> bool:
    """Compatibility wrapper for the canonical Java ClassFile discriminator."""
    return _is_valid_java_class(path)


def is_macho_candidate(path: Path) -> bool:
    """Compatibility wrapper for the canonical Mach-O discriminator."""
    return _is_macho_candidate(path)


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
    record: dict[str, Any],
    label: str,
    evidence_dir: Path | None,
    *,
    architecture_reader: Callable[[Path], list[str]],
) -> None:
    digest = record.get("sha256")
    size = record.get("size")
    if not isinstance(record.get("retained_path"), str) or not isinstance(digest, str):
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
            if architecture_reader(retained) != architectures:
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
    if (
        any(part in {"", ".", ".."} for part in parts)
        or posixpath.normpath(path) != path
    ):
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
                _fail(
                    f"deployment inventory contains a cyclic symlink at {symlink_path}"
                )
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
        or re.fullmatch(r"libpyside6(?:\.abi3)?(?:\.\d+)*\.dylib", name)
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
    framework = re.fullmatch(r"lib/(Qt[A-Za-z0-9]+)\.framework/(.+)", relative)
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
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                _fail(f"deployment inventory has an invalid digest for {path}")
            if not isinstance(architectures, list) or not all(
                architecture in {"x86_64", "arm64"} for architecture in architectures
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
    if (
        inventory.get("file_count") != len(files)
        or inventory.get("total_bytes") != total
    ):
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
        if path.startswith(
            authoritative_qt_root
        ) and not _is_allowed_authoritative_qt_path(path):
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
    private_lib_r = "Contents/Frameworks/R.framework/Resources/lib/libR.dylib"
    lib_r_paths = [
        path
        for path, record in records.items()
        if Path(path).name == "libR.dylib" and record["kind"] == "file"
    ]
    if lib_r_paths != [private_lib_r]:
        _fail("deployment inventory must contain one private framework-owned libR")
    for required_r_member in (
        "Contents/Frameworks/R.framework/Resources/etc/Renviron",
        "Contents/Frameworks/R.framework/Resources/include/R.h",
    ):
        if required_r_member not in records:
            _fail("deployment inventory has an incomplete private R_HOME")
    flattened_compiler_runtime = re.compile(
        r"^Contents/Frameworks/lib(?:gfortran|quadmath|gcc_s)[^.]*[.]dylib$",
        re.IGNORECASE,
    )
    if any(flattened_compiler_runtime.match(path) for path in records):
        _fail("deployment inventory contains a flattened R compiler runtime")
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
        expected_alias = f"Contents/Frameworks/PyQt6/Qt6/lib/{name}.framework/{name}"
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
            if (
                path
                not in {
                    f"Contents/Frameworks/{name}",
                    f"Contents/Resources/{name}",
                }
                or identity != canonical_frameworks[name]
            ):
                _fail(f"incoherent Qt framework alias: {path}")
        elif name in binding_extensions and path == f"Contents/Resources/PyQt6/{name}":
            if identity != binding_extensions[name]:
                _fail(f"incoherent PyQt6 extension alias: {path}")
        elif re.fullmatch(r"Contents/Resources/PyQt6/Qt6/translations/[^/]+\.qm", path):
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
    expected_options = ["--noconfirm", "--clean", "--distpath", "--workpath"]
    if [
        argument for argument in arguments if argument.startswith("--")
    ] != expected_options:
        _fail("PyInstaller build plan does not match the allowlisted invocation")
    if len(arguments) != 7:
        _fail("PyInstaller build plan does not match the allowlisted invocation")
    if (
        arguments[:3] != ["--noconfirm", "--clean", "--distpath"]
        or arguments[4] != "--workpath"
        or not arguments[6]
        .replace("\\", "/")
        .endswith("packaging/pyinstaller/qt6-macos-feasibility.spec")
    ):
        _fail("PyInstaller build plan contains unexpected manual inputs")
    for path_argument in (arguments[3], arguments[5], arguments[6]):
        if not (
            PurePosixPath(path_argument).is_absolute()
            or PureWindowsPath(path_argument).is_absolute()
        ):
            _fail("PyInstaller build plan paths must be absolute")


def validate_evidence(
    evidence: object,
    target: str,
    *,
    evidence_dir: Path | None = None,
    architecture_reader: Callable[[Path], list[str]] | None = None,
) -> None:
    """Fail closed unless *evidence* proves one complete native target."""
    if architecture_reader is None:
        architecture_reader = _archs

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
    if (
        runner.get("github_runner_os") != "macOS"
        or runner.get("github_runner_arch") != expected_github_arch
    ):
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
        _fail(
            f"locked dependency mismatch: {', '.join(differing) or 'unexpected keys'}"
        )

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
    if (
        r_call.get("expression") != "sum(c(1.25, 2.5, 3.75))"
        or r_call.get("result") != 7.5
    ):
        _fail("R result did not match the representative rpy2 call")

    package = _mapping(root.get("package"), "package")
    if package.get("target_arch") != expected_machine:
        _fail(f"packaged target architecture must be {expected_machine}")
    if package.get("qt_dependency_collector") != "PyInstaller":
        _fail("PyInstaller must be the sole Qt dependency collector")
    if package.get("qpa") != "cocoa" or not str(
        package.get("cocoa_plugin", "")
    ).endswith("libqcocoa.dylib"):
        _fail("packaged smoke did not load its Cocoa platform plugin")
    if package.get("dependencies") != {
        key: EXPECTED_VERSIONS[key] for key in ("pyqt6", "qt", "r", "rpy2")
    }:
        _fail("packaged dependency identities do not match the locked stack")
    if package.get("r_home") != "Contents/Frameworks/R.framework/Resources":
        _fail("packaged smoke did not report its private framework-owned R_HOME")
    if package.get("rpy2_mode") != "API":
        _fail("packaged smoke did not prove the rpy2 API mode")
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
    cocoa_plugin = _mapping(
        package.get("cocoa_plugin_artifact"), "package.cocoa_plugin_artifact"
    )
    if executable.get("architectures") != [expected_machine]:
        _fail("packaged executable must be a thin native binary")
    if expected_machine not in cocoa_plugin.get("architectures", []):
        _fail("packaged Cocoa plugin has no native architecture slice")
    for label, record in (("executable", executable), ("Cocoa plugin", cocoa_plugin)):
        _validate_retained_file_record(
            record, label, evidence_dir, architecture_reader=architecture_reader
        )

    inventory_record = _mapping(package.get("inventory"), "package.inventory")
    build_plan_record = _mapping(package.get("build_plan"), "package.build_plan")
    _validate_retained_file_record(
        inventory_record,
        "deployment inventory",
        evidence_dir,
        architecture_reader=architecture_reader,
    )
    _validate_retained_file_record(
        build_plan_record,
        "PyInstaller build plan",
        evidence_dir,
        architecture_reader=architecture_reader,
    )
    if evidence_dir is not None:
        inventory = json.loads(
            _retained_path(
                inventory_record, "deployment inventory", evidence_dir
            ).read_text(encoding="utf-8")
        )
        _validate_deployment_inventory(
            inventory, expected_machine, executable, cocoa_plugin
        )
        build_plan = json.loads(
            _retained_path(
                build_plan_record, "PyInstaller build plan", evidence_dir
            ).read_text(encoding="utf-8")
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
        if len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            _fail(f"diagnostic {name} has an invalid SHA-256 digest")
        if evidence_dir is not None:
            relative = Path(record["path"])
            if relative.is_absolute() or ".." in relative.parts:
                _fail(
                    f"diagnostic {name} path must remain within the evidence directory"
                )
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
        if (
            not isinstance(retained, list)
            or not retained
            or not isinstance(source_paths, list)
            or len(source_paths) != len(retained)
        ):
            _fail(f"native component {name} has an incomplete retained inventory")
        for item in retained:
            item_record = _mapping(item, f"native_components.{name}.retained")
            if expected_machine not in item_record.get("architectures", []):
                _fail(f"native component {name} has no {expected_machine} slice")
            _validate_retained_file_record(
                item_record,
                f"native component {name}",
                evidence_dir,
                architecture_reader=architecture_reader,
            )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archs(path: Path) -> list[str]:
    """Return Mach-O architectures using the strict parser error contract."""
    try:
        return _macho_architectures(path)
    except MachOError as exc:
        _fail(str(exc))


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file without loading it into memory."""
    return _sha256(path)
