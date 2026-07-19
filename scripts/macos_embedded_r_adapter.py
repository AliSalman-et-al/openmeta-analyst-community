#!/usr/bin/env python3
"""Normalize one official macOS R.framework for private PyInstaller embedding."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
from typing import Any

from rc_metastudio.qt6_macos_feasibility import is_macho_candidate


SYSTEM_ROOTS = ("/usr/lib/", "/System/Library/")
FORBIDDEN_ROOTS = (
    "/opt/X11/",
    "/usr/local/",
    "/opt/homebrew/",
    "/homebrew/",
    "/conda/",
)
OFFICIAL_ALIASES = (
    "Versions/Current",
    "Resources",
    "R",
    "Versions/{version}/R",
    "Versions/{version}/Resources/R",
)


class AdapterError(RuntimeError):
    """Raised when the narrow embedded-R boundary cannot be proven closed."""


def filter_pyinstaller_r_binaries(
    binaries: list[tuple[str, str, str]], staged_framework: Path | dict[str, str]
) -> list[tuple[str, str, str]]:
    if isinstance(staged_framework, dict):
        # Compatibility for the unit-level policy seam. Production passes the
        # actual staged framework below, so filtering is membership based.
        retained = []
        for destination, source, typecode in binaries:
            source_text = str(source).replace("\\", "/")
            if source_text.startswith("/Library/Frameworks/R.framework/"):
                continue
            if source_text.startswith("/opt/R/"):
                raise AdapterError(
                    f"unmapped /opt/R binary discovered by PyInstaller: {source_text}"
                )
            retained.append((destination, source, typecode))
        return retained
    staged_root = staged_framework.resolve(strict=True)
    retained = []
    for destination, source, typecode in binaries:
        try:
            Path(source).resolve(strict=True).relative_to(staged_root)
        except ValueError:
            source_text = str(source).replace("\\", "/")
            destination_text = str(destination).replace("\\", "/")
            if (
                "/R.framework/" in source_text
                or Path(source_text).name in {"R", "libR.dylib"}
                or destination_text.startswith("R.framework/")
                or Path(destination_text).name in {"R", "libR.dylib"}
            ):
                raise AdapterError(
                    f"R-like PyInstaller binary is outside exact staged membership: {source_text}"
                )
        else:
            # The explicit framework TOC is authoritative.  Exclude exactly
            # its members from PyInstaller's dependency walk rather than
            # recognizing a few host-path prefixes.
            continue
        retained.append((destination, source, typecode))
    return retained


def _absolute_link_target(value: str) -> bool:
    return Path(value).is_absolute() or PurePosixPath(value).is_absolute()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=check)


def architectures(path: Path) -> list[str]:
    return _run("lipo", "-archs", str(path)).stdout.split()


def dependencies(path: Path) -> list[str]:
    lines = _run("otool", "-L", str(path)).stdout.splitlines()[1:]
    return [line.strip().split(" (", 1)[0] for line in lines]


def install_id(path: Path) -> str | None:
    lines = _run("otool", "-D", str(path), check=False).stdout.splitlines()[1:]
    return lines[0].strip() if lines else None


def _relative_inside(path: Path, root: Path) -> str:
    try:
        return (
            path.resolve(strict=True).relative_to(root.resolve(strict=True)).as_posix()
        )
    except (OSError, ValueError, RuntimeError) as exc:
        raise AdapterError(f"path escapes embedded R.framework: {path}") from exc


def current_version(framework: Path) -> str:
    link = framework / "Versions/Current"
    if not link.is_symlink():
        raise AdapterError("R.framework lacks Versions/Current")
    version = os.readlink(link)
    if (
        version in {"", ".", ".."}
        or _absolute_link_target(version)
        or "/" in version
        or "\\" in version
    ):
        raise AdapterError(f"unsafe R.framework Versions/Current target: {version}")
    if not (framework / "Versions" / version).is_dir():
        raise AdapterError("R.framework Versions/Current is broken")
    return version


def remove_debug_bundles(framework: Path) -> list[str]:
    removed = []
    for path in sorted(framework.rglob("*.dSYM")):
        if path.is_symlink() or not path.is_dir():
            raise AdapterError(f"unexpected .dSYM shape: {path}")
        removed.append(path.relative_to(framework).as_posix())
        shutil.rmtree(path)
    return removed


def plan_fontconfig_links(framework: Path) -> list[dict[str, str]]:
    resources = framework / "Versions" / current_version(framework) / "Resources"
    font_root = resources / "fontconfig/fonts/conf.d"
    normalized = []
    for link in sorted(font_root.iterdir()):
        if not link.is_symlink():
            continue
        target = os.readlink(link)
        if not _absolute_link_target(target):
            continue
        prefixes = (
            "/Library/Frameworks/R.framework/Resources/",
            f"/Library/Frameworks/R.framework/Versions/{current_version(framework)}/Resources/",
        )
        relative_target = next(
            (target[len(prefix) :] for prefix in prefixes if target.startswith(prefix)),
            None,
        )
        if relative_target is None:
            raise AdapterError(
                f"fontconfig link has unsupported absolute target: {link} -> {target}"
            )
        internal = resources / relative_target
        if not internal.is_file():
            raise AdapterError(f"fontconfig target is absent: {link} -> {target}")
        replacement = os.path.relpath(internal, link.parent)
        normalized.append(
            {
                "path": link.relative_to(framework).as_posix(),
                "from": target,
                "to": replacement,
            }
        )
    return normalized


def normalize_fontconfig_links(framework: Path) -> list[dict[str, str]]:
    planned = plan_fontconfig_links(framework)
    for record in planned:
        link = framework / record["path"]
        if os.readlink(link) != record["from"]:
            raise AdapterError(f"fontconfig link changed after audit: {record['path']}")
        link.unlink()
        link.symlink_to(record["to"])
    return planned


def audit_pre_normalization_symlinks(
    framework: Path, font_links: list[dict[str, str]]
) -> list[dict[str, str]]:
    planned = {record["path"]: record["from"] for record in font_links}
    records = []
    folded: dict[str, str] = {}
    for path in sorted(framework.rglob("*")):
        relative = path.relative_to(framework).as_posix()
        key = relative.casefold()
        if key in folded:
            raise AdapterError(f"case-colliding R paths: {folded[key]}, {relative}")
        folded[key] = relative
        if not path.is_symlink():
            continue
        target = os.readlink(path)
        if _absolute_link_target(target):
            if planned.get(relative) != target:
                raise AdapterError(
                    f"unplanned absolute R symlink: {relative} -> {target}"
                )
            records.append(
                {"path": relative, "target": target, "planned": planned[relative]}
            )
            continue
        resolved = _relative_inside(path, framework)
        records.append({"path": relative, "target": target, "resolved": resolved})
    return records


def audit_symlinks(framework: Path) -> list[dict[str, str]]:
    records = []
    folded: dict[str, str] = {}
    for path in sorted(framework.rglob("*")):
        relative = path.relative_to(framework).as_posix()
        key = relative.casefold()
        if key in folded:
            raise AdapterError(f"case-colliding R paths: {folded[key]}, {relative}")
        folded[key] = relative
        if not path.is_symlink():
            continue
        target = os.readlink(path)
        if _absolute_link_target(target):
            raise AdapterError(f"absolute R symlink remains: {relative} -> {target}")
        resolved = _relative_inside(path, framework)
        records.append({"path": relative, "target": target, "resolved": resolved})
    version = current_version(framework)
    observed = {record["path"] for record in records}
    required = {item.format(version=version) for item in OFFICIAL_ALIASES}
    missing = required - observed
    if missing:
        raise AdapterError(
            "official R aliases are missing: " + ", ".join(sorted(missing))
        )
    return records


def macho_inventory(framework: Path, architecture: str) -> list[dict[str, Any]]:
    result = []
    for path in sorted(framework.rglob("*")):
        if path.is_symlink() or not path.is_file() or not is_macho_candidate(path):
            continue
        observed = architectures(path)
        if observed != [architecture]:
            raise AdapterError(
                f"R Mach-O is not {architecture}-only: {path}: {observed}"
            )
        result.append(
            {
                "path": path.relative_to(framework).as_posix(),
                "sha256": sha256_file(path),
                "architectures": observed,
                "install_id": install_id(path),
                "dependencies": dependencies(path),
            }
        )
    if not result:
        raise AdapterError("embedded R framework has no Mach-O inventory")
    return result


def _map_absolute(
    framework: Path, value: str, architecture: str
) -> tuple[Path, Path | None]:
    version = current_version(framework)
    prefixes = (
        ("/Library/Frameworks/R.framework/Resources/", framework / "Resources"),
        (
            f"/Library/Frameworks/R.framework/Versions/{version}/Resources/",
            framework / "Resources",
        ),
    )
    for prefix, root in prefixes:
        if value.startswith(prefix):
            return root / value[len(prefix) :], None
    if value in {
        "/Library/Frameworks/R.framework/R",
        f"/Library/Frameworks/R.framework/Versions/{version}/R",
    }:
        return framework / "Resources/lib/libR.dylib", None
    opt_prefix = f"/opt/R/{architecture}/lib/"
    if value.startswith(opt_prefix):
        relative = Path(value[len(opt_prefix) :])
        if any(part in {"", ".", ".."} for part in relative.parts):
            raise AdapterError(f"unsafe /opt/R dependency: {value}")
        # CRAN's build metadata can retain an /opt/R toolchain identity.  It
        # is acceptable only when the same named runtime is already present
        # in the authenticated framework.  Do not copy a runner dependency.
        return framework / "Resources/lib" / relative, None
    raise AdapterError(f"unsupported non-system R dependency: {value}")


def _loader_replacement(binary: Path, target: Path) -> str:
    return "@loader_path/" + os.path.relpath(target, binary.parent)


def validate_relocated_inventory(
    framework: Path, inventory: list[dict[str, Any]]
) -> None:
    for record in inventory:
        binary = framework / record["path"]
        values = [*record["dependencies"]]
        if record["install_id"]:
            values.append(record["install_id"])
        for value in values:
            if value.startswith(SYSTEM_ROOTS):
                continue
            if not value.startswith("@loader_path/"):
                raise AdapterError(
                    f"relocated R Mach-O retains unresolved identity: {binary}: {value}"
                )
            target = (binary.parent / value[len("@loader_path/") :]).resolve()
            _relative_inside(target, framework)
            if not target.is_file():
                raise AdapterError(
                    f"relocated R dependency is broken: {binary}: {value}"
                )


def pre_normalization_audit(framework: Path, architecture: str) -> dict[str, Any]:
    framework = framework.resolve(strict=True)
    font_links = plan_fontconfig_links(framework)
    links = audit_pre_normalization_symlinks(framework, font_links)
    native = macho_inventory(framework, architecture)
    dependency_map = []
    queue = [(record, framework / record["path"]) for record in native]
    planned_copies: dict[str, dict[str, Any]] = {}
    while queue:
        record, inspected_binary = queue.pop(0)
        binary = framework / record["path"]
        values = [*record["dependencies"]]
        if record["install_id"]:
            values.append(record["install_id"])
        for value in values:
            if value.startswith(SYSTEM_ROOTS):
                dependency_map.append(
                    {
                        "binary": record["path"],
                        "source": value,
                        "classification": "system",
                    }
                )
                continue
            if value.startswith(FORBIDDEN_ROOTS):
                raise AdapterError(f"forbidden R dependency root: {binary}: {value}")
            if not value.startswith("/"):
                raise AdapterError(
                    f"unresolved R dependency identity: {binary}: {value}"
                )
            target, source = _map_absolute(framework, value, architecture)
            if source is not None and not target.exists():
                # Kept solely for injected/unit test maps. The production
                # mapper never returns a source outside the framework.
                target_relative = target.relative_to(framework).as_posix()
                source_hash = sha256_file(source)
                planned_copies[target_relative] = {
                    "source": str(source),
                    "sha256": source_hash,
                }
                native.append(
                    {
                        "path": target_relative,
                        "sha256": source_hash,
                        "architectures": [architecture],
                        "install_id": install_id(source),
                        "dependencies": dependencies(source),
                    }
                )
                queue.append((native[-1], source))
            if source is None and (
                not target.is_file() or not is_macho_candidate(target)
            ):
                raise AdapterError(
                    f"mapped R dependency is absent or non-Mach-O: {value} -> {target}"
                )
            dependency_map.append(
                {
                    "binary": record["path"],
                    "source": value,
                    "classification": "bundled",
                    "target": target.relative_to(framework).as_posix(),
                    "copy_source": str(source) if source is not None else None,
                    "replacement": _loader_replacement(binary, target),
                }
            )
        if (
            inspected_binary != binary
            and sha256_file(inspected_binary) != record["sha256"]
        ):
            raise AdapterError(
                f"planned dependency source changed during audit: {inspected_binary}"
            )
    dsyms = sorted(framework.rglob("*.dSYM"))
    for path in dsyms:
        if path.is_symlink() or not path.is_dir():
            raise AdapterError(f"unexpected .dSYM shape: {path}")
    return {
        "schema_version": 1,
        "kind": "rc-metastudio-direct-macos-r-pre-normalization-audit",
        "framework": str(framework),
        "architecture": architecture,
        "version": current_version(framework),
        "planned_dsym_removals": [
            path.relative_to(framework).as_posix() for path in dsyms
        ],
        "planned_fontconfig_links": font_links,
        "symlinks": links,
        "mach_o": sorted(native, key=lambda record: record["path"]),
        "planned_copies": dict(sorted(planned_copies.items())),
        "dependency_map": dependency_map,
    }


def write_pre_normalization_audit(
    framework: Path, architecture: str, output: Path
) -> None:
    output.write_text(
        json.dumps(
            pre_normalization_audit(framework, architecture), indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )


def explicit_toc(framework: Path) -> list[dict[str, str]]:
    entries = []
    for path in sorted(framework.rglob("*")):
        relative = path.relative_to(framework).as_posix()
        destination = f"R.framework/{relative}"
        if path.is_symlink():
            target = os.readlink(path)
            if _absolute_link_target(target):
                raise AdapterError(f"TOC contains absolute symlink: {relative}")
            _relative_inside(path, framework)
            entries.append(
                {"destination": destination, "source": target, "type": "SYMLINK"}
            )
        elif path.is_file():
            entries.append(
                {
                    "destination": destination,
                    "source": str(path.resolve()),
                    "type": "DATA",
                }
            )
        elif not path.is_dir():
            raise AdapterError(f"unsupported R filesystem member: {relative}")
    destinations = [item["destination"].casefold() for item in entries]
    if len(destinations) != len(set(destinations)):
        raise AdapterError("explicit R TOC has duplicate destinations")
    return sorted(entries, key=lambda item: item["destination"])


def relocate_bridge(
    framework: Path, bridge: Path, architecture: str, output: Path
) -> None:
    framework = framework.resolve(strict=True)
    bridge = bridge.resolve(strict=True)
    if not is_macho_candidate(bridge) or architectures(bridge) != [architecture]:
        raise AdapterError("final rpy2 API bridge is not target-native Mach-O")
    r_edges = [
        value
        for value in dependencies(bridge)
        if value.endswith(("/R", "/libR.dylib"))
        or value in {"@rpath/libR.dylib", "libR.dylib"}
    ]
    if len(r_edges) != 1:
        raise AdapterError(f"rpy2 API bridge must have one R edge, found {r_edges}")
    lib_r = (framework / "Resources/lib/libR.dylib").resolve(strict=True)
    replacement = _loader_replacement(bridge, lib_r)
    _run("install_name_tool", "-change", r_edges[0], replacement, str(bridge))
    final_dependencies = dependencies(bridge)
    if replacement not in final_dependencies or any(
        edge in final_dependencies for edge in r_edges
    ):
        raise AdapterError("rpy2 API bridge relocation did not converge")
    output.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "bridge": str(bridge),
                "architecture": architecture,
                "sha256": sha256_file(bridge),
                "r_dependency": replacement,
                "dependencies": final_dependencies,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def post_app_gate(app: Path, architecture: str, output: Path) -> None:
    app = app.resolve(strict=True)
    framework = app / "Contents/Frameworks/R.framework"
    links = audit_symlinks(framework)
    native = macho_inventory(framework, architecture)
    validate_relocated_inventory(framework, native)
    lib_r_paths = list(app.rglob("libR.dylib"))
    expected_lib_r = (framework / "Resources/lib/libR.dylib").resolve(strict=True)
    if (
        len(lib_r_paths) != 1
        or lib_r_paths[0].is_symlink()
        or lib_r_paths[0].resolve() != expected_lib_r
        or not is_macho_candidate(expected_lib_r)
        or architectures(expected_lib_r) != [architecture]
    ):
        raise AdapterError(f"final app has duplicate or displaced libR: {lib_r_paths}")
    bridges = [path for path in app.rglob("_rinterface_cffi_api*.so") if path.is_file()]
    if len(bridges) != 1 or any(app.rglob("_rinterface_cffi_abi*")):
        raise AdapterError("final app must contain one API bridge and no ABI bridge")
    if architectures(bridges[0]) != [architecture]:
        raise AdapterError("final API bridge has the wrong architecture")
    r_edge = [
        value for value in dependencies(bridges[0]) if value.endswith("libR.dylib")
    ]
    if len(r_edge) != 1 or not r_edge[0].startswith("@loader_path/"):
        raise AdapterError("final API bridge does not resolve uniquely to private libR")
    if (
        bridges[0].parent / r_edge[0][len("@loader_path/") :]
    ).resolve() != expected_lib_r:
        raise AdapterError("final API bridge resolves outside the private R.framework")
    output.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "architecture": architecture,
                "framework_symlinks": links,
                "framework_mach_o": native,
                "api_bridge": str(bridges[0].relative_to(app)),
                "lib_r": str(expected_lib_r.relative_to(app)),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def finalize_toc(
    framework: Path, architecture: str, output: Path, toc_output: Path
) -> None:
    """Validate an already-relocated framework and emit its authoritative TOC."""
    framework = framework.resolve(strict=True)
    removed = remove_debug_bundles(framework)
    font_links = normalize_fontconfig_links(framework)
    links = audit_symlinks(framework)
    native = macho_inventory(framework, architecture)
    validate_relocated_inventory(framework, native)
    output.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "rc-metastudio-staged-r-toc",
                "architecture": architecture,
                "framework": str(framework),
                "version": current_version(framework),
                "removed_dsym": removed,
                "normalized_fontconfig_links": font_links,
                "symlinks": links,
                "mapped_sources": {},
                "mach_o": native,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    toc_output.write_text(
        json.dumps(
            {"schema_version": 1, "entries": explicit_toc(framework)},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--framework", type=Path, required=True)
    audit.add_argument("--architecture", required=True)
    audit.add_argument("--output", type=Path, required=True)
    toc = sub.add_parser("finalize-toc")
    toc.add_argument("--framework", type=Path, required=True)
    toc.add_argument("--architecture", required=True)
    toc.add_argument("--output", type=Path, required=True)
    toc.add_argument("--toc-output", type=Path, required=True)
    bridge = sub.add_parser("relocate-bridge")
    bridge.add_argument("--framework", type=Path, required=True)
    bridge.add_argument("--bridge", type=Path, required=True)
    bridge.add_argument("--architecture", required=True)
    bridge.add_argument("--output", type=Path, required=True)
    post_app = sub.add_parser("post-app")
    post_app.add_argument("--app", type=Path, required=True)
    post_app.add_argument("--architecture", required=True)
    post_app.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "audit":
            write_pre_normalization_audit(
                args.framework, args.architecture, args.output
            )
        elif args.command == "relocate-bridge":
            relocate_bridge(args.framework, args.bridge, args.architecture, args.output)
        elif args.command == "finalize-toc":
            finalize_toc(
                args.framework, args.architecture, args.output, args.toc_output
            )
        else:
            post_app_gate(args.app, args.architecture, args.output)
    except (AdapterError, OSError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
