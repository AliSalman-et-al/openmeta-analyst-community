# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Audit serialized analysis results for user-visible formatting defects.

The audit intentionally works on result captures rather than a running GUI.  A
capture is either the normal ``{"texts": ..., "images": ...}`` result mapping
or a regression-capture record containing that mapping plus metadata.  The
command also accepts a directory of JSON captures or a zip containing a
``captures/`` directory.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import TypedDict, TypeGuard

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

REQUIRED_CATEGORIES = (
    "binary",
    "continuous",
    "diagnostic",
    "subgroup",
    "cumulative",
    "leave-one-out",
    "meta-regression",
    "publication-bias",
    "failures",
)

_RAW_R_PREFIX = re.compile(r"(?m)^\s*\[\d+\](?:\s|$)")
_UNSAFE_REPR = re.compile(
    r"(?m)^\s*(?:\$[A-Za-z][\w.]*|\[\[\d+\]\]|List of \d+|"
    r"named list\s*\(|structure\s*\(|<[^>]+>)"
)
_PYTHON_REPR = re.compile(r"(?m)^\s*\{(?:['\"][^'\"]+['\"]\s*:)")
_VECTOR_REPR = re.compile(r"(?m)^\s*(?:c\s*\(|list\s*\(|\[[^\]]*,[^\]]*\])")
_INTERNAL_HEADING = re.compile(
    r"(?im)^\s*(?:MAResults|summary\.disp|res\.info|table\.titles|"
    r"model\.title|plot_names|plot_params_paths|plot_capabilities|"
    r"image_var_names|display_images|arrays)(?:\s*:)?\s*$"
)
_INTERNAL_KEY = re.compile(
    r"(?im)^\s*(?:prepared(?:[._-][A-Za-z0-9._-]+)+|routing(?:[._-][A-Za-z0-9._-]+)+|"
    r"(?:tests\.data|eligibility\$|params\$|res\$|plot\.(?:data|params)))\s*[:=]"
)
_RAW_FIELD_KEY = re.compile(r"(?im)^\s*([a-z][a-z0-9]*(?:\.[a-z0-9_-]+)+)\s*[:=]")
_SAFE_DOTTED_LABELS = {
    "normalized.partial.auc",
    "partial.fpr.bounds",
    "false.positive.rate",
    "summary.seed",
    "summary.iterations",
}
_LABELED_DUMP = re.compile(r"(?im)^\s*(package(?:\.version)?|call|geometry)\s*[:=]")
_PRECISE_NUMBER = re.compile(r"(?<![\w])[-+]?\d+\.\d{6,}(?!\d)")
_PIPE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")

_PUBLICATION_ORDER = (
    "Warning",
    "Data and eligibility",
    "Tests",
    "Pooled comparison",
    "Trim-and-fill",
    "Trim-and-fill left",
    "Trim-and-fill right",
    "Trim-and-fill model",
    "Extrapolation",
    "Failures",
    "References",
)
_TECHNICAL_SECTIONS = {
    "weights",
    "method details",
    "model information",
    "moderator coding",
    "overall ml likelihood-ratio test",
    "moderator block tests",
    "residual diagnostic i-squared",
}


class AuditSummary(TypedDict):
    errors: int
    warnings: int
    sources: int


class AuditInventory(TypedDict):
    required: list[str]
    covered: list[str]
    missing: list[str]
    sources_by_category: dict[str, list[str]]


class AuditReport(TypedDict):
    schema_version: int
    summary: AuditSummary
    inventory: AuditInventory
    findings: list[dict[str, str]]


def _string_keyed_mapping(value: object) -> TypeGuard[Mapping[str, object]]:
    return isinstance(value, Mapping) and all(isinstance(key, str) for key in value)


def _finding(code: str, source: str, message: str, section: str | None = None) -> dict[str, str]:
    item = {
        "severity": "error",
        "code": code,
        "source": source,
        "message": message,
    }
    if section is not None:
        item["section"] = section
    return item


def _as_sections(value: object, field: str) -> list[tuple[str, object]]:
    """Read mappings and list-shaped sections while preserving list duplicates."""
    if value is None:
        return []
    if _string_keyed_mapping(value):
        return [(str(key), item) for key, item in value.items()]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        sections: list[tuple[str, object]] = []
        for item in value:
            if not _string_keyed_mapping(item):
                sections.append(("", item))
                continue
            title = item.get("title", item.get("name", ""))
            text = item.get("text", item.get("value", ""))
            sections.append((str(title), text))
        return sections
    raise ValueError(f"{field} must be a mapping or list of named sections")


def _record_source(record: Mapping[str, object], fallback: str) -> str:
    source = record.get("_source", record.get("id", fallback))
    return str(source or fallback)


def _category_for_record(record: Mapping[str, object], titles: Sequence[str]) -> set[str]:
    haystack = " ".join(
        str(record.get(key, "")) for key in ("id", "method", "workflow", "analysis")
    ).lower()
    data_family = str(record.get("data_family", record.get("data.type", ""))).lower()
    categories: set[str] = set()
    if data_family in {"binary", "continuous", "diagnostic"}:
        categories.add(data_family)
    for category, terms in {
        "publication-bias": ("publication", "small.study", "small study", "asymmetry"),
        "meta-regression": ("meta_regression", "meta-regression", "regression"),
    }.items():
        if any(term in haystack for term in terms):
            categories.add(category)
    lowered_titles = [title.lower() for title in titles]
    if any("subgroup" in title for title in lowered_titles):
        categories.add("subgroup")
    if any("cumulative" in title for title in lowered_titles):
        categories.add("cumulative")
    if any("leave-one-out" in title or "leave one out" in title for title in lowered_titles):
        categories.add("leave-one-out")
    if {"warning", "data and eligibility", "tests"}.issubset(
        {title.lower() for title in titles}
    ):
        categories.add("publication-bias")
    if str(record.get("status", "success")).lower() not in {"success", "ok", "passed"}:
        categories.add("failures")
    if "failures" in {title.lower() for title in titles}:
        categories.add("failures")
    return categories


def _audit_table(text: str, source: str, section: str) -> list[dict[str, str]]:
    if section == "References":
        return []
    findings: list[dict[str, str]] = []
    lines = text.splitlines()
    pipe_rows = [line for line in lines if "|" in line]
    if len(pipe_rows) >= 2:
        widths = {len([cell for cell in line.strip().strip("|").split("|")]) for line in pipe_rows}
        has_separator = any(_PIPE_SEPARATOR.match(line) for line in pipe_rows)
        if len(widths) != 1 or not has_separator:
            findings.append(
                _finding(
                    "malformed-table",
                    source,
                    "Pipe-delimited table has ragged rows or no header separator.",
                    section,
                )
            )

    # These are the stable table contracts emitted by RCMetaR.  Checking the
    # semantic headers catches truncation without trying to parse narrative
    # prose or infer arbitrary whitespace columns.
    normalized = text.lower()
    def has_header(header: str) -> bool:
        return bool(re.search(r"\b%s\b" % re.escape(header), normalized))
    required_headers = (
        (("estimate",), ("lower bound",), ("upper bound",), "estimate table"),
        (("study names",), ("weights",), "weights table"),
        (("covariate",), ("coefficient", "coefficients"), "meta-regression table"),
    )
    for *header_groups, label in required_headers:
        if label == "estimate table" and has_header("coefficients"):
            continue
        present = {
            group[0]
            for group in header_groups
            if any(has_header(header) for header in group)
        }
        expected = {group[0] for group in header_groups}
        if present and present != expected:
            findings.append(
                _finding(
                    "malformed-table",
                    source,
                    f"{label} is missing required column(s): {', '.join(sorted(expected - present))}.",
                    section,
                )
            )
    return findings


def _audit_text(
    source: str,
    section: str,
    value: object,
    *,
    allow_method_metadata: bool = False,
) -> list[dict[str, str]]:
    if not isinstance(value, str):
        return [_finding("malformed-text", source, "Result text is not a string.", section)]
    if not value.strip():
        return [_finding("empty-section", source, "Result text is empty.", section)]
    findings: list[dict[str, str]] = []
    if _RAW_R_PREFIX.search(value):
        findings.append(_finding("raw-r-console-prefix", source, "Raw R console prefix such as [1] is visible.", section))
    if _UNSAFE_REPR.search(value) or _PYTHON_REPR.search(value) or _VECTOR_REPR.search(value):
        findings.append(_finding("unsafe-list-repr", source, "Internal R/Python object representation is visible.", section))
    if _INTERNAL_HEADING.search(value):
        findings.append(_finding("internal-heading", source, "Internal-only result heading is visible.", section))
    if _INTERNAL_KEY.search(value):
        findings.append(_finding("internal-key", source, "Raw backend field key is visible in result text.", section))
    for match in _RAW_FIELD_KEY.finditer(value):
        key = match.group(1).lower()
        if key not in _SAFE_DOTTED_LABELS and not (
            key.startswith(("prepared.", "routing.", "tests.data", "plot."))
            or key == "package.version"
        ):
            findings.append(_finding("internal-key", source, "Raw dotted backend field key is visible in result text.", section))
    for match in _LABELED_DUMP.finditer(value):
        label = match.group(1).lower()
        # Publication Bias deliberately discloses the package and exact call
        # under curated method details.  A raw geometry/vector dump is never
        # a display contract; only the compact dimensions sentence is safe.
        if (
            allow_method_metadata
            and label in {"package", "package.version", "call"}
            and section in {
            "Tests",
            "Method details",
            }
        ):
            continue
        line = value[match.start() :].splitlines()[0]
        if label == "geometry" and re.search(
            r"geometry\s*:\s*\d+\s+rows?\s+x\s+\d+\s+columns?",
            line,
            flags=re.IGNORECASE,
        ):
            continue
        findings.append(
            _finding(
                "internal-dump",
                source,
                f"Backend {label} field is exposed outside its curated display form.",
                section,
            )
        )
    if section != "References" and _PRECISE_NUMBER.search(value):
        findings.append(
            _finding(
                "excessive-precision",
                source,
                "Numeric output contains six or more decimal places; display values should be rounded.",
                section,
            )
        )
    findings.extend(_audit_table(value, source, section))
    return findings


def _audit_order(source: str, sections: list[tuple[str, object]], categories: set[str]) -> list[dict[str, str]]:
    titles = [title for title, _value in sections]
    comparable = [title for title in titles if title != "References"]
    if "publication-bias" in categories:
        rank = {title.lower(): index for index, title in enumerate(_PUBLICATION_ORDER)}
        expected = sorted(comparable, key=lambda title: rank.get(title.lower(), len(rank)))
    else:
        try:
            from rc_metastudio.result_sections import order_text_sections

            expected = [title for title, _value in order_text_sections(sections)]
        except (ImportError, ValueError):
            expected = comparable
    if comparable != expected:
        return [
            _finding(
                "section-order",
                source,
                "Text sections are not in the application result ordering contract.",
            )
        ]
    return []


def audit_records(records: Iterable[Mapping[str, object]]) -> AuditReport:
    findings: list[dict[str, str]] = []
    inventory: dict[str, list[str]] = {}
    source_count = 0
    for index, record in enumerate(records, start=1):
        if not isinstance(record, Mapping):
            findings.append(_finding("malformed-record", f"record-{index}", "Capture is not a mapping."))
            continue
        source = _record_source(record, f"record-{index}")
        source_count += 1
        try:
            sections = _as_sections(record.get("texts", record.get("sections")), "texts")
            images = _as_sections(record.get("images"), "images")
        except ValueError as error:
            findings.append(_finding("malformed-record", source, str(error)))
            continue
        categories = _category_for_record(record, [title for title, _value in sections])
        for category in categories:
            inventory.setdefault(category, []).append(source)
        seen_titles: dict[str, str] = {}
        for title, value in sections:
            normalized = " ".join(title.strip().lower().split())
            if not normalized:
                findings.append(_finding("empty-title", source, "Result section has an empty title."))
            elif normalized in seen_titles:
                findings.append(
                    _finding("duplicate-title", source, f"Duplicate result title: {title!r}.", title)
                )
            else:
                seen_titles[normalized] = title
            if re.search(r"(?:\$|\[\[|^\.?res(?:ult)?\.|^params?\.|^plot\.)", title, re.IGNORECASE):
                findings.append(
                    _finding("internal-key", source, "Raw backend field key is used as a result title.", title)
                )
            findings.extend(
                _audit_text(
                    source,
                    title,
                    value,
                    allow_method_metadata="publication-bias" in categories,
                )
            )
        findings.extend(_audit_order(source, sections, categories))
        summary_positions = [
            index
            for index, (title, _value) in enumerate(sections)
            if "summary" in title.lower()
        ]
        technical_positions = [
            index
            for index, (title, _value) in enumerate(sections)
            if title.strip().lower() in _TECHNICAL_SECTIONS
        ]
        if summary_positions and technical_positions and min(technical_positions) < min(summary_positions):
            findings.append(
                _finding(
                    "technical-before-summary",
                    source,
                    "Technical result sections precede the headline summary.",
                )
            )
        if "publication-bias" in categories:
            required = {"Warning", "Data and eligibility", "Tests"}
            missing = sorted(required - {title for title, _value in sections})
            if missing:
                findings.append(
                    _finding(
                        "missing-contract-section",
                        source,
                        "Publication Bias result is missing required section(s): " + ", ".join(missing),
                    )
                )
        if not sections and not images:
            findings.append(_finding("empty-result", source, "Result has neither text nor image sections."))

    findings.sort(
        key=lambda item: (
            item.get("source", ""),
            item.get("section", ""),
            item.get("code", ""),
            item.get("message", ""),
        )
    )
    covered = sorted(category for category in inventory if category in REQUIRED_CATEGORIES)
    report: AuditReport = {
        "schema_version": 1,
        "summary": {
            "errors": len(findings),
            "warnings": 0,
            "sources": source_count,
        },
        "inventory": {
            "required": list(REQUIRED_CATEGORIES),
            "covered": covered,
            "missing": sorted(set(REQUIRED_CATEGORIES) - set(covered)),
            "sources_by_category": {
                category: sorted(set(sources)) for category, sources in sorted(inventory.items())
            },
        },
        "findings": findings,
    }
    return report


def _records_from_json(value: object, source: str) -> list[dict[str, object]]:
    if _string_keyed_mapping(value):
        records = value.get("records")
        if isinstance(records, list):
            return [dict(item, _source=f"{source}#{index}") for index, item in enumerate(records, 1) if _string_keyed_mapping(item)]
        captures = value.get("captures")
        if isinstance(captures, list):
            return [dict(item, _source=f"{source}#{index}") for index, item in enumerate(captures, 1) if _string_keyed_mapping(item)]
        if "texts" in value or "sections" in value:
            return [dict(value, _source=source)]
        return []
    if isinstance(value, list):
        return [dict(item, _source=f"{source}#{index}") for index, item in enumerate(value, 1) if _string_keyed_mapping(item)]
    return []


def load_records(paths: Iterable[Path]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in paths:
        if path.is_dir():
            files = sorted(path.rglob("*.json"))
            records.extend(load_records(files))
            continue
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as bundle:
                names = sorted(name for name in bundle.namelist() if name.lower().endswith(".json"))
                for name in names:
                    value = json.loads(bundle.read(name).decode("utf-8"))
                    records.extend(_records_from_json(value, f"{path}!{name}"))
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        records.extend(_records_from_json(value, str(path)))
    return records


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="JSON capture(s), directory, or capture zip")
    parser.add_argument("--output", type=Path, help="Also write the JSON report to this path")
    args = parser.parse_args(argv)
    paths = args.paths or [ROOT / "tests" / "analysis_regression" / "baseline" / "observed-golden-baseline.zip"]
    try:
        report = audit_records(load_records(paths))
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    sys.stdout.write(serialized)
    return 1 if report["summary"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
