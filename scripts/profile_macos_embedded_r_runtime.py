#!/usr/bin/env python3
"""Apply RC MetaStudio's explicit non-X11 product profile to CRAN R.framework.

The official macOS R distribution contains optional Tcl/Tk and X11 loadable
modules.  They are not application dependencies, and following their host
paths would turn an XQuartz installation into an accidental product input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import cast


EXCLUSIONS = (
    ("library/tcltk", "tcltk"),
    ("modules/R_X11.so", "X11 device"),
    ("modules/R_de.so", "X11 data editor"),
    ("library/grDevices/libs/cairo.so", "X11-linked Cairo device"),
)
DEPENDENCY_FIELDS = ("Depends", "Imports", "LinkingTo")


class ProfileError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_dir():
        for item in sorted(path.rglob("*")):
            digest.update(item.relative_to(path).as_posix().encode() + b"\0")
            if item.is_file() and not item.is_symlink():
                digest.update(sha256(item).encode())
        return digest.hexdigest()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command_lines(*command: str) -> list[str]:
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise ProfileError(f"{' '.join(command)} failed: {completed.stderr.strip()}")
    return completed.stdout.splitlines()


def is_macho(path: Path) -> bool:
    return path.is_file() and subprocess.run(
        ["otool", "-L", str(path)], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0


def macho_record(path: Path, root: Path) -> dict[str, object]:
    loads = command_lines("otool", "-L", str(path))[1:]
    loads = [line.strip().split(" (", 1)[0] for line in loads]
    install = command_lines("otool", "-D", str(path))[1:]
    architectures = command_lines("lipo", "-archs", str(path))[0].split()
    return {
        "relative_path": path.relative_to(root).as_posix(),
        "sha256": sha256(path),
        "architectures": architectures,
        "install_id": install[0].strip() if install else None,
        "load_commands": loads,
    }


def description_dependencies(description: Path) -> set[str]:
    fields: dict[str, str] = {}
    active: str | None = None
    for line in description.read_text(encoding="utf-8", errors="replace").splitlines():
        if line[:1].isspace() and active:
            fields[active] += " " + line.strip()
        elif ":" in line:
            active, value = line.split(":", 1)
            fields[active] = value.strip()
        else:
            active = None
    result: set[str] = set()
    for field in DEPENDENCY_FIELDS:
        for entry in fields.get(field, "").split(","):
            name = re.split(r"\s|\(", entry.strip(), 1)[0]
            if name and name != "R":
                result.add(name)
    return result


def sha256_tree_identity(root: Path) -> str:
    """Content-authenticate a tree without following potentially external symlinks."""
    digest = hashlib.sha256()
    for item in sorted(root.rglob("*")):
        stat = item.lstat()
        digest.update(item.relative_to(root).as_posix().encode() + b"\0")
        if item.is_symlink():
            digest.update(b"L\0" + item.readlink().as_posix().encode() + b"\0")
        elif item.is_file():
            digest.update(b"F\0")
            with item.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        elif item.is_dir():
            digest.update(b"D\0")
        else:
            digest.update(f"O:{stat.st_mode}\0".encode())
    return digest.hexdigest()


def manifest_roots(manifest_path: Path) -> tuple[list[str], set[str], str]:
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    roots = {"RCMetaR"}
    roots.update(manifest["binary_package_policy"]["required_normal_packages"])
    roots.update(item["name"] for item in manifest["binary_package_policy"]["source_exceptions"])
    roots.update(item["name"] for item in manifest["direct_RCMetaR_dependencies"])
    roots.update(item["name"] for item in manifest["app_r_bundle_dependencies"])
    builtin = {
        item["name"] for item in manifest["direct_RCMetaR_dependencies"]
        if item.get("source") in {"base-runtime", "recommended"}
    } | {
        item["name"] for item in manifest["app_r_bundle_dependencies"]
        if item.get("source") in {"base-runtime", "recommended"}
    } | {"R"}
    return sorted(roots, key=str.casefold), builtin, hashlib.sha256(raw).hexdigest()


def hard_dependency_closure(library: Path, roots: list[str], builtin: set[str]) -> list[str]:
    packages = {item.name: item for item in library.iterdir() if (item / "DESCRIPTION").is_file()}
    missing = [name for name in roots if name not in packages and name not in builtin]
    if missing:
        raise ProfileError("required package roots are absent: " + ", ".join(missing))
    pending = list(roots)
    closure: set[str] = set()
    while pending:
        package = pending.pop()
        if package in closure:
            continue
        closure.add(package)
        package_path = packages.get(package)
        # Base packages may be recorded in R's base package table, not library.
        if package_path is None and package in builtin:
            continue
        if package_path is None:
            raise ProfileError(f"required hard dependency is absent: {package}")
        for dependency in description_dependencies(package_path / "DESCRIPTION"):
            if dependency not in closure:
                pending.append(dependency)
    if "tcltk" in {name.casefold() for name in closure}:
        raise ProfileError("hard dependency closure requires tcltk")
    return sorted(closure, key=str.casefold)


def profile(resources: Path, evidence: Path, manifest_path: Path, r_version: str, architecture: str, source_resources: Path | None = None) -> None:
    resources = resources.resolve(strict=True)
    library = resources / "library"
    roots, builtin, manifest_sha256 = manifest_roots(manifest_path)
    closure = hard_dependency_closure(library, roots, builtin)
    source_resources = (source_resources or resources).resolve(strict=True)
    source_macho = source_resources / "lib" / "libR.dylib"
    if not source_macho.is_file() or not is_macho(source_macho):
        raise ProfileError("canonical source lib/libR.dylib is missing or is not Mach-O")
    source_macho_record = macho_record(source_macho, source_resources)
    if source_macho_record["architectures"] != [architecture]:
        raise ProfileError(
            f"canonical source libR must be {architecture}-only, found {source_macho_record['architectures']}"
        )
    source_executable = source_resources / "bin" / "exec" / "R"
    if not source_executable.is_file() or not is_macho(source_executable):
        raise ProfileError("source bin/exec/R executable is missing or is not Mach-O")
    source_executable_record = macho_record(source_executable, source_resources)
    if source_executable_record["architectures"] != [architecture]:
        raise ProfileError(
            f"source bin/exec/R executable must be {architecture}-only, found "
            f"{source_executable_record['architectures']}"
        )
    source_launcher = source_resources / "bin" / "R"
    if not source_launcher.is_file() or is_macho(source_launcher):
        raise ProfileError("source bin/R must be the expected non-Mach-O launcher")
    launcher_bytes = source_launcher.read_bytes()
    if not launcher_bytes.startswith(b"#!"):
        raise ProfileError("source bin/R launcher is missing its script shebang")
    source_launcher_record = {
        "relative_path": source_launcher.relative_to(source_resources).as_posix(),
        "kind": "script",
        "sha256": hashlib.sha256(launcher_bytes).hexdigest(),
        "symlink_target": source_launcher.readlink().as_posix() if source_launcher.is_symlink() else None,
    }
    exclusions: list[dict[str, object]] = []
    expected_paths = {relative for relative, _ in EXCLUSIONS}
    x11_machos: set[str] = set()
    tcltk_machos: set[str] = set()
    allowed_opt_r: dict[str, list[str]] = {}
    for candidate in resources.rglob("*"):
        if not is_macho(candidate):
            continue
        record = macho_record(candidate, resources)
        loads = cast(list[str], record["load_commands"])
        if any(str(value).startswith("/opt/X11/") for value in loads):
            x11_machos.add(str(record["relative_path"]))
        if any(re.search(r"/opt/R/[^/]+/lib/lib(?:tcl|tk)[^.]*", value) for value in loads):
            tcltk_machos.add(str(record["relative_path"]))
        opt_r = [value for value in loads if value.startswith("/opt/R/")]
        if opt_r:
            allowed_opt_r[str(record["relative_path"])] = opt_r
    # Only these optional modules may refer to the separately installed X11/Tcl stack.
    expected_machos = {"library/tcltk/libs/tcltk.so", "modules/R_X11.so", "modules/R_de.so", "library/grDevices/libs/cairo.so"}
    if x11_machos != expected_machos or tcltk_machos != {"library/tcltk/libs/tcltk.so"}:
        raise ProfileError(
            "unexpected optional-R external dependency layout: "
            f"expected X11 {sorted(expected_machos)} and Tcl/Tk tcltk.so; found "
            f"X11 {sorted(x11_machos)}, Tcl/Tk {sorted(tcltk_machos)}"
        )
    for relative, feature in EXCLUSIONS:
        target = resources / relative
        if not target.exists():
            raise ProfileError(f"expected optional R surface is missing: {relative}")
        item: dict[str, object] = {"feature": feature, "relative_path": relative, "sha256": sha256(target)}
        machos = [macho_record(path, resources) for path in ([target] if target.is_file() else target.rglob("*")) if is_macho(path)]
        item["mach_o"] = machos
        if relative == "library/tcltk" and [entry["relative_path"] for entry in machos] != ["library/tcltk/libs/tcltk.so"]:
            raise ProfileError("tcltk exclusion has an unexpected Mach-O layout")
        if relative != "library/tcltk" and len(machos) != 1:
            raise ProfileError(f"optional R surface is not exactly one Mach-O: {relative}")
        if any(macho["architectures"] != [architecture] for macho in machos):
            raise ProfileError(f"optional R surface is not {architecture}-only: {relative}")
        commands = [command for macho in machos for command in cast(list[str], macho["load_commands"])]
        if relative == "library/tcltk":
            required_families = (
                r"/opt/R/[^/]+/lib/libtcl[^/]*\.dylib",
                r"/opt/R/[^/]+/lib/libtk[^/]*\.dylib",
                r"/opt/X11/lib/libX11[^/]*\.dylib",
                r"/opt/X11/lib/libXss[^/]*\.dylib",
                r"/opt/X11/lib/libXext[^/]*\.dylib",
            )
        elif relative in {"modules/R_X11.so", "modules/R_de.so"}:
            required_families = tuple(rf"/opt/X11/lib/lib{name}[^/]*\.dylib" for name in ("SM", "ICE", "X11", "Xext", "Xrender", "Xt", "Xmu"))
        else:
            required_families = tuple(rf"/opt/X11/lib/lib{name}[^/]*\.dylib" for name in ("Xrender", "SM", "ICE", "X11", "Xext"))
        if any(not any(re.search(family, command) for command in commands) for family in required_families):
            raise ProfileError(f"optional R surface has changed dependency families: {relative}")
        exclusions.append(item)
    for relative, _ in EXCLUSIONS:
        target = resources / relative
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    remaining_x11: list[str] = []
    for candidate in resources.rglob("*"):
        if is_macho(candidate):
            loads = cast(list[str], macho_record(candidate, resources)["load_commands"])
            if any(str(value).startswith("/opt/X11/") for value in loads):
                remaining_x11.append(candidate.relative_to(resources).as_posix())
    if remaining_x11:
        raise ProfileError("profile left external X11 dependencies: " + ", ".join(sorted(remaining_x11)))
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps({
        "schema_version": 1,
        "policy": "official-cran-r-with-optional-x11-tcl-surfaces-removed",
        "hard_dependency_fields": list(DEPENDENCY_FIELDS),
        "dependency_manifest": {"path": manifest_path.name, "sha256": manifest_sha256},
        "hard_dependency_roots": roots,
        "base_or_recommended_roots": sorted(builtin, key=str.casefold),
        "hard_dependency_closure": closure,
        "source_framework": {
            "version": r_version,
            "expected_architecture": architecture,
            "source_resources": str(source_resources),
            "source_tree_identity_sha256": sha256_tree_identity(source_resources),
            "pre_profile_tree_identity_sha256": sha256_tree_identity(resources),
            "canonical_macho": source_macho_record,
            "executable_macho": source_executable_record,
            "launcher": source_launcher_record,
        },
        "allowed_non_tcl_opt_r_dependencies": {
            path: [value for value in values if not re.search(r"/lib(?:tcl|tk)[^.]*", value)]
            for path, values in allowed_opt_r.items()
            if any(not re.search(r"/lib(?:tcl|tk)[^.]*", value) for value in values)
        },
        "excluded_surfaces": exclusions,
        "post_profile_exclusions": sorted(expected_paths),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resources", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--dependency-manifest", type=Path, required=True)
    parser.add_argument("--r-version", required=True)
    parser.add_argument("--architecture", required=True)
    parser.add_argument("--source-resources", type=Path)
    args = parser.parse_args()
    try:
        profile(args.resources, args.evidence, args.dependency_manifest, args.r_version, args.architecture, args.source_resources)
    except (OSError, ProfileError) as exc:
        print(f"Embedded R product profile failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
