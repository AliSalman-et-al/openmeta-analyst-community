"""Audit active surfaces for retired RC MetaStudio identity tokens."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_PROJECT_EXTENSION = ".rcms"
RETIRED_PROJECT_EXTENSIONS = {".oma"}
R_PACKAGE_NAME = "RCMetaR"
R_FACADE_PREFIX = "rcmetar."

DEFAULT_SCAN_ENTRIES = (
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "pyproject.toml",
    "docs",
    "doc",
    "scripts",
    "src",
    "tests",
    "sample_data",
    "packaging",
)

SKIPPED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "artifacts",
    "build",
    "dist",
    "htmlcov",
    "r_tmp",
}

TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".css",
    ".csv",
    ".html",
    ".ini",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".qrc",
    ".r",
    ".rd",
    ".sh",
    ".toml",
    ".txt",
    ".ui",
    ".xml",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class ForbiddenPattern:
    name: str
    pattern: re.Pattern[str]
    message: str


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    column: int
    rule: str
    token: str
    message: str
    text: str


FORBIDDEN_PATTERNS = (
    ForbiddenPattern(
        "legacy-project-extension",
        re.compile(r"(?i)\.oma(?=$|[^A-Za-z0-9])"),
        "use .rcms for RC MetaStudio Project Files",
    ),
    ForbiddenPattern(
        "legacy-env-prefix",
        re.compile(r"\bOMA_[A-Z0-9_]*\b"),
        "use RCMS_ for maintained environment variables",
    ),
    ForbiddenPattern(
        "legacy-r-package",
        re.compile(r"\bOpenMetaR\b"),
        "use RCMetaR for the bundled R package identity",
    ),
    ForbiddenPattern(
        "legacy-r-facade",
        re.compile(r"(?<![A-Za-z0-9_])\.?openmetar\.[A-Za-z0-9_.]+"),
        "use rcmetar.* for the maintained R facade",
    ),
    ForbiddenPattern(
        "legacy-product-bracketed",
        re.compile(r"OpenMeta\[Analyst\]", re.IGNORECASE),
        "use RC MetaStudio for the maintained product identity",
    ),
    ForbiddenPattern(
        "legacy-product-compact",
        re.compile(r"\bOpenMetaAnalyst\b", re.IGNORECASE),
        "use RC MetaStudio for the maintained product identity",
    ),
    ForbiddenPattern(
        "legacy-product-hyphenated",
        re.compile(r"\bOpen\s+Meta-Analyst\b", re.IGNORECASE),
        "use RC MetaStudio for the maintained product identity",
    ),
    ForbiddenPattern(
        "legacy-repository-slug",
        re.compile(r"\bopenmeta-analyst(?:-community|-error)?\b", re.IGNORECASE),
        "use RC MetaStudio repository, artifact, and output names",
    ),
)

ALLOWLISTED_PATHS = {
    "NOTICE.md",
    "docs/contexts/project-provenance/CONTEXT.md",
    "docs/legal/source-headers.md",
    "scripts/audit_rc_metastudio_identity.py",
}

ALLOWLISTED_PATH_PREFIXES = (
    "docs/adr/",
)

ALLOWLISTED_PROVENANCE_LINES = (
    re.compile(r"\bOriginal OpenMeta\[Analyst\] Project\b"),
    re.compile(r"\bderived from OpenMeta\[Analyst\]\b"),
    re.compile(r"\bOpenMeta\[Analyst\] portions\b"),
)

HEADER_PROVENANCE_PATTERNS = (
    re.compile(r"OpenMeta\[?analyst\]?", re.IGNORECASE),
    re.compile(r"\bOpen\s+Meta-Analyst\b", re.IGNORECASE),
    re.compile(r"\bBrown\b|\bTufts\b|\bCEBM\b", re.IGNORECASE),
)


def normalized_relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def is_allowlisted_path(relative_path: str) -> bool:
    if relative_path in ALLOWLISTED_PATHS:
        return True
    return any(relative_path.startswith(prefix) for prefix in ALLOWLISTED_PATH_PREFIXES)


def is_allowlisted_line(relative_path: str, line_number: int, line: str) -> bool:
    if is_allowlisted_path(relative_path):
        return True
    if any(pattern.search(line) for pattern in ALLOWLISTED_PROVENANCE_LINES):
        return True
    stripped = line.lstrip()
    is_comment = stripped.startswith(("#", "//", "/*", "*", "<!--"))
    if line_number <= 25 and is_comment and any(
        pattern.search(line) for pattern in HEADER_PROVENANCE_PATTERNS
    ):
        return True
    return False


def iter_scan_files(root: Path, entries: tuple[str, ...] = DEFAULT_SCAN_ENTRIES):
    for entry in entries:
        path = root / entry
        if not path.exists():
            continue
        if path.is_file():
            if should_scan_file(path):
                yield path
            continue
        for child in path.rglob("*"):
            if not child.is_file():
                continue
            if any(part in SKIPPED_DIRS for part in child.relative_to(root).parts):
                continue
            if should_scan_file(child):
                yield child


def should_scan_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    if path.name in {"LICENSE", "NOTICE", "Dockerfile"}:
        return True
    return False


def read_text(path: Path) -> str | None:
    data = path.read_bytes()
    if b"\0" in data:
        return None
    for encoding in ("utf-8", "latin1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def audit(root: Path, entries: tuple[str, ...] = DEFAULT_SCAN_ENTRIES) -> list[Finding]:
    root = root.resolve()
    findings: list[Finding] = []
    for path in iter_scan_files(root, entries):
        text = read_text(path)
        if text is None:
            continue
        relative_path = normalized_relative_path(path, root)
        for line_number, line in enumerate(text.splitlines(), start=1):
            if is_allowlisted_line(relative_path, line_number, line):
                continue
            for forbidden in FORBIDDEN_PATTERNS:
                for match in forbidden.pattern.finditer(line):
                    findings.append(
                        Finding(
                            path=relative_path,
                            line=line_number,
                            column=match.start() + 1,
                            rule=forbidden.name,
                            token=match.group(0),
                            message=forbidden.message,
                            text=line.strip(),
                        )
                    )
    return findings


def print_text_report(findings: list[Finding]) -> None:
    if not findings:
        print(
            "RC MetaStudio identity audit passed: active surfaces use .rcms, "
            "RCMetaR, and rcmetar.* identity."
        )
        return
    print("error: RC MetaStudio identity audit found retired active-surface tokens")
    for finding in findings:
        print(
            f"{finding.path}:{finding.line}:{finding.column}: "
            f"{finding.rule}: {finding.token!r}: {finding.message}"
        )
        print(f"  {finding.text}")


def finding_to_dict(finding: Finding) -> dict[str, object]:
    return {
        "path": finding.path,
        "line": finding.line,
        "column": finding.column,
        "rule": finding.rule,
        "token": finding.token,
        "message": finding.message,
        "text": finding.text,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scan active source, docs, tests, scripts, manifests, packaging "
            "metadata, resources, and templates for retired RC MetaStudio identity."
        )
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable findings instead of the text report",
    )
    args = parser.parse_args(argv)

    findings = audit(args.root)
    if args.json:
        print(json.dumps([finding_to_dict(f) for f in findings], indent=2))
    else:
        print_text_report(findings)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
