#!/usr/bin/env python3
"""Update RC MetaStudio release version surfaces."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path


VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Bump RC MetaStudio and bundled RCMetaR versions from one canonical "
            "release version."
        )
    )
    parser.add_argument("version", help="New release version, for example 0.1.2.")
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Release date for r/RCMetaR/DESCRIPTION. Defaults to today.",
    )
    parser.add_argument(
        "--root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root. Defaults to the parent of scripts/.",
    )
    parser.add_argument(
        "--no-changelog",
        action="store_true",
        help="Do not create a CHANGELOG.md section for the new version.",
    )
    args = parser.parse_args(argv)

    if not VERSION_RE.fullmatch(args.version):
        parser.error("version must use the repo release format X.Y.Z, for example 0.1.2")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        parser.error("date must use YYYY-MM-DD")

    root = args.root.resolve()
    replacements = [
        (
            root / "pyproject.toml",
            r'(?m)^version = "\d+\.\d+\.\d+"$',
            f'version = "{args.version}"',
        ),
        (
            root / "uv.lock",
            (
                r'(?ms)^(\[\[package\]\]\r?\nname = "rc-metastudio"\r?\n)'
                r'version = "\d+\.\d+\.\d+"'
            ),
            rf'\1version = "{args.version}"',
        ),
        (
            root / "src" / "rc_metastudio" / "__init__.py",
            r'(?m)^__version__ = "\d+\.\d+\.\d+"$',
            f'__version__ = "{args.version}"',
        ),
        (
            root / "src" / "rc_metastudio" / "meta_globals.py",
            r'(?m)^VERSION = "\d+\.\d+\.\d+"$',
            f'VERSION = "{args.version}"',
        ),
        (
            root / "r" / "RCMetaR" / "DESCRIPTION",
            r"(?m)^Version: \d+\.\d+\.\d+(?=\r?$)",
            f"Version: {args.version}",
        ),
        (
            root / "r" / "RCMetaR" / "DESCRIPTION",
            r"(?m)^Date: \d{4}-\d{2}-\d{2}(?=\r?$)",
            f"Date: {args.date}",
        ),
    ]

    for path, pattern, replacement in replacements:
        replace_once(path, pattern, replacement)

    if not args.no_changelog:
        ensure_changelog_section(root / "CHANGELOG.md", args.version)

    print(f"Bumped RC MetaStudio version surfaces to {args.version}.")
    return 0


def replace_once(path: Path, pattern: str, replacement: str) -> None:
    text = read_text(path)
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise SystemExit(f"Expected exactly one version surface match in {path}")
    write_text(path, updated)


def ensure_changelog_section(path: Path, version: str) -> None:
    text = read_text(path)
    if re.search(rf"(?m)^## {re.escape(version)}(?:\s|-)", text):
        return

    first_release = re.search(r"(?m)^## \d+\.\d+\.\d+(?:\s|-)", text)
    if first_release is None:
        raise SystemExit(f"Could not find a release section in {path}")

    section = (
        f"## {version} - Unreleased\n\n"
        "### Added\n\n"
        "- TODO: summarize user-visible additions.\n\n"
        "### Changed\n\n"
        "- TODO: summarize user-visible changes.\n\n"
    )
    updated = text[: first_release.start()] + section + text[first_release.start() :]
    write_text(path, updated)


def read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as file:
        return file.read()


def write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        file.write(text)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
