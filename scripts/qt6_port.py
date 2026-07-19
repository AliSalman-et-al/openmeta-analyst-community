#!/usr/bin/env python3
"""Run the repository-owned Qt6 codemod or strict migration policy scan."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from typing import Iterable

from rc_metastudio.qt6_port_tools import (
    MigrationTransactionError,
    MigrationRefused,
    apply_migration_transaction,
    findings_snapshot,
    prepare_file_migration,
    report_findings,
    scan_paths,
    write_atomic_text,
)


def _files(paths: Iterable[Path], suffixes: set[str]) -> list[Path]:
    files: list[Path] = []
    for candidate in paths:
        if candidate.is_symlink():
            raise MigrationTransactionError(
                f"refusing symbolic link input: {candidate.absolute()}"
            )
        if candidate.is_dir():
            files.extend(
                path.absolute()
                for path in candidate.rglob("*")
                if path.is_file() and path.suffix.lower() in suffixes
            )
        elif candidate.is_file() and candidate.suffix.lower() in suffixes:
            files.append(candidate.absolute())
        else:
            raise ValueError(
                f"path does not name a supported file or directory: {candidate}"
            )
    return sorted(files, key=lambda path: path.as_posix())


def _dedupe_files(files: list[Path]) -> list[Path]:
    return list(dict.fromkeys(files))


def _write_report(payload: dict[str, object], path: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path is None:
        print(rendered, end="")
    else:
        write_atomic_text(path, rendered)


def _validate_disjoint_paths(files: list[Path], report: Path | None) -> None:
    normalized: dict[str, Path] = {}
    identities: dict[tuple[int, int], Path] = {}
    for path in files:
        if path.is_symlink():
            raise MigrationTransactionError(f"refusing symbolic link input: {path}")
        resolved = path.resolve(strict=True)
        key = os.path.normcase(str(resolved))
        details = path.stat(follow_symlinks=False)
        identity = (details.st_dev, details.st_ino)
        if key in normalized or identity in identities:
            other = normalized.get(key) or identities[identity]
            raise MigrationTransactionError(
                f"input paths alias the same file: {other} and {path}"
            )
        normalized[key] = path
        identities[identity] = path
    if report is None:
        return
    report_absolute = report.absolute()
    if report_absolute.is_symlink():
        raise MigrationTransactionError(
            f"report path must not be a symbolic link: {report_absolute}"
        )
    report_key = os.path.normcase(str(report_absolute.resolve(strict=False)))
    if report_key in normalized:
        raise MigrationTransactionError(
            f"report path overlaps migration input: {report_absolute}"
        )
    if report_absolute.exists():
        details = report_absolute.stat(follow_symlinks=False)
        identity = (details.st_dev, details.st_ino)
        if identity in identities:
            raise MigrationTransactionError(
                f"report path aliases migration input: {report_absolute}"
            )


def _validate_distinct_named_paths(named: dict[str, Path | None]) -> None:
    seen_paths: dict[str, str] = {}
    seen_identities: dict[tuple[int, int], str] = {}
    for role, candidate in named.items():
        if candidate is None:
            continue
        absolute = candidate.absolute()
        if absolute.is_symlink():
            raise MigrationTransactionError(
                f"{role} path must not be a symbolic link: {absolute}"
            )
        key = os.path.normcase(str(absolute.resolve(strict=False)))
        if key in seen_paths:
            raise MigrationTransactionError(
                f"{role} path aliases {seen_paths[key]} path: {absolute}"
            )
        seen_paths[key] = role
        if absolute.exists():
            details = absolute.stat(follow_symlinks=False)
            identity = (details.st_dev, details.st_ino)
            if identity in seen_identities:
                raise MigrationTransactionError(
                    f"{role} path hardlinks {seen_identities[identity]} path: {absolute}"
                )
            seen_identities[identity] = role


def _codemod(options: argparse.Namespace) -> int:
    files = _files(options.paths, {".py"})
    _validate_disjoint_paths(files, options.report)
    files = _dedupe_files(files)
    plans = []
    refusals = []
    for path in files:
        try:
            plans.append(prepare_file_migration(path))
        except MigrationRefused as exc:
            refusals.extend(exc.result.refusals)
    transformations = [
        transformation
        for plan in plans
        for transformation in plan.result.transformations
    ]
    changed = [
        plan.path.as_posix() for plan in plans if plan.source_bytes != plan.target_bytes
    ]
    payload: dict[str, object] = {
        "schema_version": 1,
        "changed_files": changed,
        "transformations": [asdict(item) for item in transformations],
        "refusals": [asdict(item) for item in refusals],
    }
    _write_report(payload, options.report)
    if refusals:
        return 2
    if options.write:
        apply_migration_transaction(plans)
    if options.check and changed:
        return 1
    return 0


def _strict(options: argparse.Namespace) -> int:
    files = _files(options.paths, {".py", ".toml", ".lock", ".txt", ".in"})
    _validate_disjoint_paths(files, options.report)
    _validate_disjoint_paths(files, options.write_snapshot)
    _validate_disjoint_paths(files, options.expected_snapshot)
    _validate_distinct_named_paths(
        {
            "strict report": options.report,
            "written snapshot": options.write_snapshot,
            "expected snapshot": options.expected_snapshot,
        }
    )
    files = _dedupe_files(files)
    root = options.root.resolve()
    findings = scan_paths(files, root=root)
    snapshot = findings_snapshot(findings)
    rendered = report_findings(findings)
    if options.report is None:
        print(rendered, end="")
    else:
        write_atomic_text(options.report, rendered)
    if options.write_snapshot is not None:
        write_atomic_text(
            options.write_snapshot,
            json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        )
        return 0
    if options.expected_snapshot is not None:
        expected = json.loads(options.expected_snapshot.read_text(encoding="utf-8"))
        if expected != snapshot:
            print(
                "strict finding snapshot drifted:\n"
                + json.dumps(
                    {"expected": expected, "observed": snapshot},
                    indent=2,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 1
        return 0
    return 1 if findings else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    codemod = commands.add_parser("codemod", help="rewrite unambiguous Python sites")
    mode = codemod.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="write changed files")
    mode.add_argument(
        "--check", action="store_true", help="fail if a rewrite is pending"
    )
    codemod.add_argument("--report", type=Path)
    codemod.add_argument("paths", nargs="+", type=Path)
    codemod.set_defaults(handler=_codemod)

    strict = commands.add_parser(
        "strict", help="reject forbidden active Qt migration patterns"
    )
    strict.add_argument("--root", type=Path, default=Path.cwd())
    strict.add_argument("--report", type=Path)
    snapshot_mode = strict.add_mutually_exclusive_group()
    snapshot_mode.add_argument("--expected-snapshot", type=Path)
    snapshot_mode.add_argument("--write-snapshot", type=Path)
    strict.add_argument("paths", nargs="+", type=Path)
    strict.set_defaults(handler=_strict)
    return parser


def main(arguments: list[str] | None = None) -> int:
    try:
        options = _parser().parse_args(arguments)
        return int(options.handler(options))
    except (MigrationTransactionError, OSError, UnicodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
