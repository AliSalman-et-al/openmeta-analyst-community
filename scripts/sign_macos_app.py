#!/usr/bin/env python3
"""Sign a macOS application from an explicit native-code inventory."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import plistlib
import stat
import subprocess
from typing import NoReturn, Sequence

from rc_metastudio.qt6_macos_feasibility import is_macho_candidate


CODE_BUNDLE_SUFFIXES = frozenset(
    {".app", ".appex", ".bundle", ".framework", ".plugin", ".xpc"}
)


class MacOSSigningError(RuntimeError):
    """Raised when explicit macOS signing cannot prove a complete code inventory."""


@dataclass(frozen=True)
class SigningPlan:
    app: Path
    native_files: tuple[Path, ...]
    nested_bundles: tuple[Path, ...]

    @property
    def signing_targets(self) -> tuple[Path, ...]:
        return (*self.native_files, *self.nested_bundles, self.app)


def _fail(message: str) -> NoReturn:
    raise MacOSSigningError(message)


def _depth(path: Path) -> int:
    return len(path.parts)


def _inside_out(paths: set[Path]) -> tuple[Path, ...]:
    return tuple(sorted(paths, key=lambda path: (-_depth(path), str(path))))


def _raise_walk_error(error: OSError) -> None:
    raise error


def _walk(root: Path):
    for directory, dirnames, filenames in os.walk(
        root, followlinks=False, onerror=_raise_walk_error
    ):
        dirnames.sort()
        filenames.sort()
        yield Path(directory), dirnames, filenames


def _native_files(app: Path) -> tuple[Path, ...]:
    native: set[Path] = set()
    try:
        for directory, _, filenames in _walk(app):
            for filename in filenames:
                path = directory / filename
                if not stat.S_ISREG(path.lstat().st_mode):
                    continue
                if is_macho_candidate(path):
                    native.add(path)
    except OSError as exc:
        _fail(f"cannot classify macOS signing inventory under {app}: {exc}")
    return _inside_out(native)


def _contains_path(root: Path, paths: set[Path]) -> bool:
    return any(root == path or root in path.parents for path in paths)


def _bundle_info_plists(bundle: Path) -> tuple[Path, ...]:
    if bundle.suffix == ".framework":
        candidates = [
            bundle / "Resources" / "Info.plist",
            bundle / "Versions" / "Current" / "Resources" / "Info.plist",
        ]
        versions = bundle / "Versions"
        if versions.is_dir():
            candidates.extend(
                version / "Resources" / "Info.plist"
                for version in sorted(versions.iterdir())
                if version.name != "Current"
            )
    else:
        candidates = [bundle / "Contents" / "Info.plist"]
    return tuple(path for path in candidates if path.is_file())


def _bundle_executables(bundle: Path, executable_name: str) -> tuple[Path, ...]:
    if not executable_name or Path(executable_name).name != executable_name:
        return ()
    if bundle.suffix != ".framework":
        return (bundle / "Contents" / "MacOS" / executable_name,)
    candidates = [bundle / executable_name]
    versions = bundle / "Versions"
    if versions.is_dir():
        candidates.extend(
            version / executable_name for version in sorted(versions.iterdir())
        )
    return tuple(candidates)


def _is_valid_code_bundle(bundle: Path, native: set[Path]) -> bool:
    for info_path in _bundle_info_plists(bundle):
        try:
            with info_path.open("rb") as stream:
                info = plistlib.load(stream)
        except (OSError, plistlib.InvalidFileException) as exc:
            _fail(f"cannot read code-bundle metadata {info_path}: {exc}")
        executable_name = info.get("CFBundleExecutable")
        if not isinstance(executable_name, str):
            continue
        for executable in _bundle_executables(bundle, executable_name):
            if not executable.exists():
                if executable.is_symlink():
                    _fail(f"code-bundle executable is a broken link: {executable}")
                continue
            try:
                resolved_executable = executable.resolve(strict=True)
                if executable.is_file() and (
                    executable in native or resolved_executable in native
                ):
                    return True
            except (OSError, RuntimeError) as exc:
                _fail(f"cannot inspect code-bundle executable {executable}: {exc}")
    return False


def _main_executables(bundle: Path, native: set[Path]) -> set[Path]:
    """Return native files whose signatures are owned by ``bundle`` itself."""
    executables: set[Path] = set()
    for info_path in _bundle_info_plists(bundle):
        try:
            with info_path.open("rb") as stream:
                info = plistlib.load(stream)
        except (OSError, plistlib.InvalidFileException) as exc:
            _fail(f"cannot read code-bundle metadata {info_path}: {exc}")
        executable_name = info.get("CFBundleExecutable")
        if not isinstance(executable_name, str):
            continue
        for executable in _bundle_executables(bundle, executable_name):
            try:
                if not executable.exists():
                    continue
                resolved = executable.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                _fail(f"cannot inspect code-bundle executable {executable}: {exc}")
            if executable in native:
                executables.add(executable)
            elif resolved in native:
                executables.add(resolved)
    return executables


def build_signing_plan(app: Path) -> SigningPlan:
    """Classify every Mach-O and real nested bundle without name-based deep signing."""
    app = Path(app).absolute()
    if app.suffix != ".app" or not app.is_dir():
        _fail(f"macOS signing target is not an application bundle: {app}")

    native_files = _native_files(app)
    native = set(native_files)
    if not native:
        _fail(f"macOS application contains no classified native code: {app}")
    if not _is_valid_code_bundle(app, native):
        _fail(
            f"outer application bundle is malformed or has no native executable: {app}"
        )

    candidate_bundles: set[Path] = set()
    try:
        for directory, dirnames, _ in _walk(app):
            for dirname in dirnames:
                candidate = directory / dirname
                if candidate != app and candidate.suffix in CODE_BUNDLE_SUFFIXES:
                    candidate_bundles.add(candidate)
    except OSError as exc:
        _fail(f"cannot enumerate nested code bundles under {app}: {exc}")

    nested_bundles: set[Path] = set()
    for bundle in candidate_bundles:
        contains_native = _contains_path(bundle, native)
        if not contains_native:
            continue
        if _is_valid_code_bundle(bundle, native):
            nested_bundles.add(bundle)
        else:
            _fail(f"malformed nested code bundle contains native code: {bundle}")

    resources_root = app / "Contents" / "Resources"
    for native_path in native:
        if resources_root in native_path.parents and not any(
            bundle in native_path.parents for bundle in nested_bundles
        ):
            _fail(
                "Contents/Resources contains native code outside a validated "
                f"nested code bundle: {native_path}"
            )

    macos_root = app / "Contents" / "MacOS"
    allowed_macos_entries = native | nested_bundles
    try:
        for entry in macos_root.iterdir():
            if entry not in allowed_macos_entries:
                _fail(
                    "Contents/MacOS contains a non-code payload; move data and "
                    f"scripts to Contents/Resources: {entry}"
                )
    except OSError as exc:
        _fail(f"cannot validate the Contents/MacOS code-only layout: {exc}")

    return SigningPlan(
        app=app,
        native_files=native_files,
        nested_bundles=_inside_out(nested_bundles),
    )


def _run_codesign(arguments: Sequence[str]) -> None:
    try:
        subprocess.run(["codesign", *arguments], check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        _fail(f"codesign failed for {arguments[-1]}: {exc}")


def _sign(path: Path, *, identity: str, timestamp: bool) -> None:
    arguments = ["--force", "--options", "runtime"]
    if timestamp:
        arguments.append("--timestamp")
    arguments.extend(("--sign", identity, str(path)))
    _run_codesign(arguments)


def _verify(path: Path, *, deep: bool = False) -> None:
    arguments = ["--verify"]
    if deep:
        arguments.append("--deep")
    arguments.extend(("--strict", "--verbose=2", str(path)))
    _run_codesign(arguments)


def sign_and_verify(
    app: Path, *, identity: str, timestamp: bool | None = None
) -> SigningPlan:
    """Sign all classified code inside-out, then strictly verify the same inventory."""
    plan = build_signing_plan(app)
    use_timestamp = identity != "-" if timestamp is None else timestamp

    # Preserve the proven inside-out signing sequence for every Mach-O and
    # nested bundle. The outer app seal owns the final signing context of its
    # launcher, however, so validate that launcher through the strict outer-app
    # checks instead of attempting a standalone check after the app is sealed.
    native = set(plan.native_files)
    app_executables = _main_executables(plan.app, native)
    standalone_verification_files = tuple(
        path for path in plan.native_files if path not in app_executables
    )

    for native_file in plan.native_files:
        _sign(native_file, identity=identity, timestamp=use_timestamp)
    for bundle in plan.nested_bundles:
        _sign(bundle, identity=identity, timestamp=use_timestamp)
    _sign(plan.app, identity=identity, timestamp=use_timestamp)

    post_sign_plan = build_signing_plan(plan.app)
    if (
        post_sign_plan.native_files != plan.native_files
        or post_sign_plan.nested_bundles != plan.nested_bundles
    ):
        _fail("macOS native-code inventory changed during signing")

    for native_file in standalone_verification_files:
        _verify(native_file)
    for bundle in plan.nested_bundles:
        _verify(bundle)
    # Apple's Gatekeeper-equivalent bundle check is strict deep verification.
    # A separate shallow pass is redundant and can misclassify PyInstaller's
    # sealed launcher context before the authoritative recursive validation.
    _verify(plan.app, deep=True)
    return plan


def _write_inventory(path: Path, plan: SigningPlan, identity: str) -> None:
    def relative(item: Path) -> str:
        return item.relative_to(plan.app).as_posix()

    payload = {
        "schema_version": 1,
        "app": plan.app.name,
        "identity": "ad-hoc" if identity == "-" else "developer-id",
        "native_files": [relative(item) for item in plan.native_files],
        "nested_bundles": [relative(item) for item in plan.nested_bundles],
        "verification": {"individual_strict": True, "outer_deep_strict": True},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", type=Path)
    parser.add_argument("--identity")
    parser.add_argument("--inventory-output", type=Path)
    parser.add_argument(
        "--inventory-only",
        action="store_true",
        help="verify the final bundle and write its native inventory without signing",
    )
    parser.add_argument(
        "--timestamp",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="request a trusted timestamp (defaults on except for ad-hoc signing)",
    )
    args = parser.parse_args()
    if args.inventory_only:
        if args.identity is not None or args.timestamp is not None:
            parser.error("--inventory-only cannot be combined with signing options")
        _verify(args.app, deep=True)
        plan = build_signing_plan(args.app)
        identity = "-"
    else:
        if args.identity is None:
            parser.error("--identity is required unless --inventory-only is used")
        plan = sign_and_verify(
            args.app, identity=args.identity, timestamp=args.timestamp
        )
        identity = args.identity
    if args.inventory_output is not None:
        _write_inventory(args.inventory_output, plan, identity)
    print(
        "Signed and verified "
        f"{len(plan.native_files)} Mach-O files and "
        f"{len(plan.nested_bundles)} nested code bundles."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
