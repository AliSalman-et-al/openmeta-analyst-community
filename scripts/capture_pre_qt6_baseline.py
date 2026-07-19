#!/usr/bin/env python3
"""Capture and validate the immutable PyQt5 diagnostic baseline for Issue #327."""

from __future__ import annotations

import argparse
import ast
import contextlib
import fnmatch
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path
from typing import Any


BASELINE_COMMIT = "e8a21fc3c277e8a8c144413dfa320ea9e68a20e4"
BASELINE_TAG = "pre-qt6-baseline"
BASELINE_RELATIVE_DIR = Path("docs/verification/pre-qt6-baseline")
BASELINE_INPUT_PATHS = (
    ".github",
    "packaging",
    "pyproject.toml",
    "sample_projects",
    "scripts",
    "src",
    "uv.lock",
)
BASELINE_CAPTURE_EXCLUSIONS = {"scripts/capture_pre_qt6_baseline.py"}
AUTHORITATIVE_BASELINE_ENVIRONMENT = {
    "id": "rc-metastudio-python3-pyqt5-r4-RCMetaR",
    "os": "Windows",
    "package": "RCMetaR",
    "pyqt": "5.15.11",
    "python": "3.11.9",
    "qt": "5.15.2",
    "r": "R version 4.6.1",
    "rpy2": "3.6.7",
    "sip": "12.18.0",
}
AUTHORITATIVE_TOOL_VERSIONS = {
    "pyqt": "5.15.11",
    "python": "3.11.9",
    "qt": "5.15.2",
    "rpy2": "3.6.7",
    "sip": "12.18.0",
}
GENERATED_MARKERS = (
    "Form implementation generated from reading ui file",
    "Resource object code",
)
REMOVED_OR_DISPLACED_APIS = {
    "QAction": "QtWidgets to QtGui",
    "QDesktopWidget": "removed; use QScreen",
    "QGraphicsSvgItem": "QtSvg to QtSvgWidgets",
    "QRegExp": "removed; use QRegularExpression",
    "exec_": "renamed to exec",
}
QT_ENUM_NAMESPACES = {
    "AlignmentFlag",
    "ApplicationAttribute",
    "AspectRatioMode",
    "CheckState",
    "ContextMenuPolicy",
    "CursorShape",
    "DateFormat",
    "DockWidgetArea",
    "DropAction",
    "FocusPolicy",
    "GlobalColor",
    "ItemDataRole",
    "ItemFlag",
    "Key",
    "KeyboardModifier",
    "MouseButton",
    "Orientation",
    "PenStyle",
    "ScrollBarPolicy",
    "SortOrder",
    "TextElideMode",
    "TextFormat",
    "ToolBarArea",
    "WindowModality",
    "WindowState",
    "WindowType",
}


class BaselineDriftError(RuntimeError):
    """Raised when one-time capture is attempted from post-baseline inputs."""


def _run(root: Path, *args: str) -> str:
    result = subprocess.run(
        args,
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _tracked(root: Path, *patterns: str) -> list[str]:
    output = _run(root, "git", "ls-files", "--", *patterns)
    return sorted(
        relative
        for line in output.splitlines()
        if line
        for relative in (line.replace("\\", "/"),)
        if (root / relative).is_file()
    )


def _tracked_at(root: Path, commit: str, *patterns: str) -> list[str]:
    output = _run(root, "git", "ls-tree", "-r", "--name-only", commit)
    paths = [line.replace("\\", "/") for line in output.splitlines() if line]
    return sorted(
        path
        for path in paths
        if any(fnmatch.fnmatch(path, pattern) for pattern in patterns)
    )


def _source_text(root: Path, relative: str, commit: str | None) -> str:
    if commit is None:
        return (root / relative).read_text(encoding="utf-8", errors="replace")
    return _git_blob(root, commit, relative).decode("utf-8", errors="replace")


def _source_tracked(root: Path, commit: str | None, *patterns: str) -> list[str]:
    return (
        _tracked(root, *patterns)
        if commit is None
        else _tracked_at(root, commit, *patterns)
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256(path.read_bytes())


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _occurrence(
    path: str, node: ast.AST, symbol: str, **details: Any
) -> dict[str, Any]:
    return {
        "file": path,
        "line": getattr(node, "lineno", 1),
        "symbol": symbol,
        **details,
    }


class _QtSurfaceVisitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.short_enums: list[dict[str, Any]] = []
        self.signals: list[dict[str, Any]] = []
        self.dynamic_properties: list[dict[str, Any]] = []
        self.removed_apis: list[dict[str, Any]] = []

    def visit_Attribute(self, node: ast.Attribute) -> None:
        owner = _call_name(node.value)
        if owner == "Qt" or owner.endswith(".Qt"):
            if node.attr not in QT_ENUM_NAMESPACES:
                self.short_enums.append(
                    _occurrence(self.path, node, f"{owner}.{node.attr}")
                )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        if name in {"pyqtSignal", "QtCore.pyqtSignal", "SIGNAL", "QtCore.SIGNAL"}:
            self.signals.append(_occurrence(self.path, node, name))
        if name.endswith(".setProperty") or name.endswith(".property"):
            property_name = _literal_string(node.args[0]) if node.args else "<dynamic>"
            self.dynamic_properties.append(
                _occurrence(
                    self.path,
                    node,
                    name,
                    property_name=property_name,
                    classification=_dynamic_property_classification(self.path),
                )
            )
        self.generic_visit(node)


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _literal_string(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return "<dynamic>"


def detect_removed_or_displaced_apis(path: str, text: str) -> list[dict[str, Any]]:
    """Detect only Qt6-invalid API ownership, resolving common import aliases."""
    tree = ast.parse(text, filename=path)
    module_aliases: dict[str, str] = {}
    occurrences: list[dict[str, Any]] = []

    def add(node: ast.AST, symbol: str) -> None:
        occurrences.append(
            _occurrence(
                path,
                node,
                symbol,
                qt6_change=REMOVED_OR_DISPLACED_APIS[
                    "exec_" if symbol.endswith("exec_") else symbol.split(".")[-1]
                ],
            )
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for imported in node.names:
                if imported.asname:
                    module_aliases[imported.asname] = imported.name
                else:
                    root_name = imported.name.split(".")[0]
                    module_aliases[root_name] = root_name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for imported in node.names:
                local = imported.asname or imported.name
                qualified = f"{node.module}.{imported.name}"
                module_aliases[local] = qualified
                if imported.name == "QAction" and node.module.endswith(".QtWidgets"):
                    add(node, "QAction")
                elif imported.name == "QGraphicsSvgItem" and node.module.endswith(
                    ".QtSvg"
                ):
                    add(node, "QGraphicsSvgItem")
                elif imported.name == "QRegExp":
                    add(node, "QRegExp")
                elif imported.name == "QDesktopWidget":
                    add(node, "QDesktopWidget")

    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if node.attr == "exec_":
            add(node, "exec_")
            continue
        owner = _call_name(node.value)
        if not owner:
            continue
        root_name, _, remainder = owner.partition(".")
        resolved_owner = module_aliases.get(root_name, root_name)
        if remainder:
            resolved_owner = f"{resolved_owner}.{remainder}"
        if node.attr == "QAction" and resolved_owner.endswith(".QtWidgets"):
            add(node, "QAction")
        elif node.attr == "QGraphicsSvgItem" and resolved_owner.endswith(".QtSvg"):
            add(node, "QGraphicsSvgItem")
        elif node.attr == "QRegExp" and resolved_owner.endswith(".QtCore"):
            add(node, "QRegExp")
        elif node.attr == "QDesktopWidget" and resolved_owner.endswith(".QtWidgets"):
            add(node, "QDesktopWidget")

    unique = {
        (item["file"], item["line"], item["symbol"]): item for item in occurrences
    }
    return [unique[key] for key in sorted(unique)]


def _dynamic_property_classification(path: str) -> str:
    if path.startswith("tests/"):
        return "test_only"
    if "/ui_" in path or path.endswith("/icons_rc.py"):
        return "allowed_qt_designer"
    return "application_owned"


def _packaging_entry_points(root: Path, commit: str | None) -> list[str]:
    workflows = _source_tracked(root, commit, ".github/workflows/*.yml")
    packaging = _source_tracked(root, commit, "packaging/*", "packaging/**/*")
    script_pattern = re.compile(
        r"(?:build-.+-package|package-.+|sign-.+|delivery|resolve_package_ci_metadata|verify_package_release)",
        re.IGNORECASE,
    )
    scripts = [
        path
        for path in _source_tracked(root, commit, "scripts/*")
        if script_pattern.search(Path(path).stem)
    ]
    return sorted(
        set(
            workflows
            + packaging
            + scripts
            + ["pyproject.toml:[project.scripts].rc-metastudio"]
        )
    )


def build_qt_port_inventory(
    root: Path,
    include_completion_checks: bool = True,
    source_commit: str | None = BASELINE_COMMIT,
) -> dict[str, Any]:
    python_files = [
        path
        for path in _source_tracked(root, source_commit, "*.py")
        if path not in BASELINE_CAPTURE_EXCLUSIONS
    ]
    generated: list[str] = []
    handwritten_qt: list[str] = []
    qt_tests: list[str] = []
    short_enums: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    dynamic_properties: list[dict[str, Any]] = []
    removed_apis: list[dict[str, Any]] = []

    for relative in python_files:
        text = _source_text(root, relative, source_commit)
        is_generated = any(marker in text[:1000] for marker in GENERATED_MARKERS)
        if is_generated:
            generated.append(relative)
        if "PyQt5" in text:
            if relative.startswith("tests/"):
                qt_tests.append(relative)
            elif relative.startswith("src/rc_metastudio/") and not is_generated:
                handwritten_qt.append(relative)
        try:
            tree = ast.parse(text, filename=relative)
        except SyntaxError:
            continue
        visitor = _QtSurfaceVisitor(relative)
        visitor.visit(tree)
        short_enums.extend(visitor.short_enums)
        signals.extend(visitor.signals)
        dynamic_properties.extend(visitor.dynamic_properties)
        removed_apis.extend(detect_removed_or_displaced_apis(relative, text))

    packaging = _packaging_entry_points(root, source_commit)
    dynamic_by_classification = {
        classification: [
            item
            for item in dynamic_properties
            if item["classification"] == classification
        ]
        for classification in (
            "application_owned",
            "allowed_qt_designer",
            "test_only",
        )
    }
    inventory = {
        "schema_version": 1,
        "source_commit": source_commit or "working-tree",
        "classification_policy": {
            "generated_module_markers": list(GENERATED_MARKERS),
            "handwritten_qt_module": "tracked src Python containing PyQt5, excluding generated modules",
            "qt_bearing_test": "tracked test Python containing PyQt5",
            "short_enum": "Qt.<member> access that is not a scoped Qt6 enum namespace",
        },
        "handwritten_qt_modules": handwritten_qt,
        "canonical_forms": _source_tracked(
            root, source_commit, "src/rc_metastudio/forms/*.ui"
        ),
        "generated_modules": generated,
        "resources": _source_tracked(root, source_commit, "*.qrc"),
        "qt_bearing_tests": qt_tests,
        "short_enums": short_enums,
        "signals": signals,
        "dynamic_properties": dynamic_by_classification,
        "removed_or_displaced_apis": removed_apis,
        "packaging_entry_points": sorted(set(packaging)),
        "counts": {
            "handwritten_qt_modules": len(handwritten_qt),
            "canonical_forms": len(
                _source_tracked(root, source_commit, "src/rc_metastudio/forms/*.ui")
            ),
            "generated_modules": len(generated),
            "resources": len(_source_tracked(root, source_commit, "*.qrc")),
            "qt_bearing_tests": len(qt_tests),
            "short_enums": len(short_enums),
            "signals": len(signals),
            "dynamic_properties": {
                key: len(value) for key, value in dynamic_by_classification.items()
            },
            "removed_or_displaced_apis": len(removed_apis),
            "packaging_entry_points": len(set(packaging)),
        },
    }
    if include_completion_checks:
        inventory["zero_legacy_completion_checks"] = run_zero_legacy_detectors(
            root, inventory=inventory
        )["checks"]
    return inventory


def _text_occurrences(
    root: Path,
    paths: list[str],
    pattern: re.Pattern[str],
    detector: str,
) -> list[dict[str, Any]]:
    occurrences = []
    for relative in paths:
        if relative in BASELINE_CAPTURE_EXCLUSIONS or relative.endswith(
            "test_pre_qt6_baseline.py"
        ):
            continue
        text = (root / relative).read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                occurrences.append(
                    {
                        "file": relative,
                        "line": line_number,
                        "detector": detector,
                    }
                )
    return occurrences


def detect_legacy_dependency_declarations(
    sources: dict[str, str],
) -> dict[str, list[dict[str, Any]]]:
    """Detect forbidden GUI binding declarations independently of Python imports."""
    pyqt5_pattern = re.compile(r"\bPyQt5(?:-Qt5|-sip)?\b", re.IGNORECASE)
    compatibility_pattern = re.compile(
        r"\b(?:qtpy|PySide2|PySide6|Qt5Compat)\b", re.IGNORECASE
    )
    result = {"pyqt5": [], "compatibility": []}
    for path, text in sorted(sources.items()):
        for line_number, line in enumerate(text.splitlines(), 1):
            if pyqt5_pattern.search(line):
                result["pyqt5"].append(
                    {
                        "file": path,
                        "line": line_number,
                        "detector": "dependency-text:PyQt5-family",
                    }
                )
            if compatibility_pattern.search(line):
                result["compatibility"].append(
                    {
                        "file": path,
                        "line": line_number,
                        "detector": "dependency-text:alternate-or-compatibility-binding",
                    }
                )
    return result


def run_zero_legacy_detectors(
    root: Path, inventory: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Run every final Native Qt6 Port contraction detector."""
    inventory = inventory or build_qt_port_inventory(
        root, include_completion_checks=False, source_commit=None
    )
    python_files = _tracked(root, "*.py")
    pyqt5 = _text_occurrences(
        root, python_files, re.compile(r"\bPyQt5\b"), "python-text:PyQt5"
    )
    compatibility = _text_occurrences(
        root,
        python_files,
        re.compile(r"\b(?:qtpy|Qt5Compat|PySide[26])\b"),
        "python-text:compatibility-binding",
    )
    dependency_findings = detect_legacy_dependency_declarations(
        {
            path: (root / path).read_text(encoding="utf-8", errors="replace")
            for path in ("pyproject.toml", "uv.lock")
        }
    )
    pyqt5.extend(dependency_findings["pyqt5"])
    compatibility.extend(dependency_findings["compatibility"])
    pickle_storage = _text_occurrences(
        root,
        [path for path in python_files if path.startswith(("src/", "tests/"))],
        re.compile(
            r"(?:project_pickle|load_project_pickle|\.rcms\.state|pickle\.dump|pickle\.load)"
        ),
        "python-text:pickle-project-storage",
    )
    packaging_files = [
        path
        for path in inventory["packaging_entry_points"]
        if ":" not in path and (root / path).is_file()
    ]
    packaging_pyqt5 = _text_occurrences(
        root,
        packaging_files,
        re.compile(r"\bPyQt5\b"),
        "packaging-text:PyQt5",
    )
    detectors = [
        (
            "no-pyqt5-imports",
            "tracked Python imports or references PyQt5",
            "python-text:PyQt5",
            pyqt5,
        ),
        (
            "no-qt-compatibility-layer",
            "tracked Python references qtpy, Qt5Compat, or another Qt binding",
            "python-text:compatibility-binding",
            compatibility,
        ),
        (
            "no-tracked-generated-qt-python",
            "tracked pyuic or pyrcc generated Python modules",
            "generated-marker-scan",
            [{"file": path} for path in inventory["generated_modules"]],
        ),
        (
            "no-unscoped-qt-enums",
            "Qt.<member> access outside a scoped Qt6 enum namespace",
            "python-ast:unscoped-qt-enum",
            inventory["short_enums"],
        ),
        (
            "no-removed-qt-apis",
            "removed or displaced Qt API occurrences",
            "python-ast:removed-or-displaced-api",
            inventory["removed_or_displaced_apis"],
        ),
        (
            "no-dynamic-application-state",
            "application-owned dynamic Qt properties",
            "python-ast:application-owned-dynamic-property",
            inventory["dynamic_properties"]["application_owned"],
        ),
        (
            "no-pickle-project-storage",
            "runtime pickle project read/write or .rcms.state sidecar paths",
            "python-text:pickle-project-storage",
            pickle_storage,
        ),
        (
            "no-pyqt5-packaging-contract",
            "packaging entry points naming PyQt5",
            "packaging-text:PyQt5",
            packaging_pyqt5,
        ),
    ]
    checks = [
        {
            "id": check_id,
            "measure": measure,
            "detector": detector,
            "target": 0,
            "current_count": len(occurrences),
            "occurrences": occurrences,
        }
        for check_id, measure, detector, occurrences in detectors
    ]
    return {
        "schema_version": 1,
        "source_commit": BASELINE_COMMIT,
        "passed": all(check["current_count"] == 0 for check in checks),
        "checks": checks,
    }


def _normalize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _normalize_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    return str(value)


def _nonempty_effects(effects: dict[str, Any]) -> dict[str, Any]:
    retained: dict[str, Any] = {}
    for metric, groups in sorted(effects.items()):
        retained_groups = {}
        for group, values in sorted(groups.items()):
            nonempty = {
                key: _normalize_value(value)
                for key, value in sorted(values.items())
                if value not in (None, "")
            }
            if nonempty:
                retained_groups[group] = nonempty
        if retained_groups:
            retained[metric] = retained_groups
    return retained


def _dataset_snapshot(dataset: Any) -> dict[str, Any]:
    outcome_names = dataset.get_outcome_names()
    outcomes = []
    for name in outcome_names:
        outcome = dataset.get_outcome_obj(name)
        followups = sorted(
            [
                value
                for value in dataset.outcome_names_to_follow_ups[name].values()
                if value is not None
            ],
            key=str,
        )
        outcomes.append(
            {
                "name": name,
                "data_type": outcome.data_type,
                "sub_type": getattr(outcome, "sub_type", None),
                "follow_ups": followups,
            }
        )
    studies = []
    for study in dataset.studies:
        units = []
        for outcome_name in sorted(study.outcomes_to_follow_ups):
            for follow_up, unit in sorted(
                study.outcomes_to_follow_ups[outcome_name].items(),
                key=lambda pair: (pair[0] is not None, str(pair[0])),
            ):
                units.append(
                    {
                        "outcome": outcome_name,
                        "follow_up": follow_up,
                        "groups": [
                            {
                                "id": group.id,
                                "name": name,
                                "raw_data": _normalize_value(group.raw_data),
                            }
                            for name, group in sorted(unit.tx_groups.items())
                        ],
                        "entered_effects": _nonempty_effects(unit.effects_dict),
                    }
                )
        studies.append(
            {
                "id": study.id,
                "name": study.name,
                "year": study.year,
                "include": study.include,
                "manually_excluded": getattr(study, "manually_excluded", False),
                "notes": study.notes,
                "sample_size": study.N,
                "covariates": _normalize_value(study.covariate_dict),
                "analysis_units": units,
            }
        )
    families = {outcome["data_type"] for outcome in outcomes}
    family_names = {0: "binary", 1: "continuous", 2: "diagnostic"}
    analysis_family = (
        family_names[next(iter(families))] if len(families) == 1 else "mixed"
    )
    return {
        "title": dataset.title,
        "summary": dataset.summary,
        "notes": dataset.notes,
        "is_diagnostic": dataset.is_diag,
        "analysis_family": analysis_family,
        "outcomes": outcomes,
        "covariates": [
            {
                "name": covariate.name,
                "data_type": covariate.data_type,
                "stable_id": getattr(covariate, "stable_id", None),
            }
            for covariate in dataset.covariates
        ],
        "studies": studies,
    }


def capture_sample_snapshots(root: Path) -> dict[str, dict[str, Any]]:
    source_dir = root / "src" / "rc_metastudio"
    sys.path.insert(0, str(source_dir))
    try:
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            import project_pickle
        snapshots = {}
        for path in sorted((root / "sample_projects").glob("*.rcms")):
            with (
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                dataset = project_pickle.load_project_pickle(path)
            snapshots[path.name] = {
                "schema_version": 1,
                "baseline_commit": BASELINE_COMMIT,
                "project_file": path.relative_to(root).as_posix(),
                "source_sha256": _file_sha256(path),
                "dataset": _dataset_snapshot(dataset),
            }
        return snapshots
    finally:
        if sys.path and sys.path[0] == str(source_dir):
            sys.path.pop(0)


def inspect_observed_golden_bundle(
    bundle_path: Path,
) -> tuple[list[str], dict[str, Any]]:
    """Validate a real comprehensive capture and return a compact observed summary."""
    errors: list[str] = []
    outputs: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(bundle_path) as archive:
            names = set(archive.namelist())
            manifest = json.loads(archive.read("manifest.json"))
            captures = manifest.get("curated_golden_set", [])
            capture_metadata = manifest.get("capture_metadata") or {}
            if (
                capture_metadata.get("baseline_environment")
                != AUTHORITATIVE_BASELINE_ENVIRONMENT
            ):
                errors.append(
                    "observed Golden Analysis manifest has the wrong baseline environment"
                )
            if manifest.get("passed") is not True:
                errors.append("observed Golden Analysis capture did not pass")
            if manifest.get("capture_failures") != []:
                errors.append("observed Golden Analysis capture contains failures")
            if len(captures) != 11:
                errors.append(
                    f"observed Golden Analysis capture has {len(captures)} entries, expected 11"
                )
            for capture in captures:
                capture_id = capture.get("id", "<missing>")
                if capture.get("commit_sha") != BASELINE_COMMIT:
                    errors.append(f"{capture_id}: capture commit is not the baseline")
                if capture.get("status") != "success":
                    errors.append(f"{capture_id}: capture did not succeed")
                if capture.get("authoritative") is not True:
                    errors.append(f"{capture_id}: capture is not authoritative")
                if capture.get("authority") != "authoritative":
                    errors.append(f"{capture_id}: authority is not authoritative")
                if capture.get("capture_mode") != "authoritative":
                    errors.append(f"{capture_id}: capture mode is not authoritative")
                environment = capture.get("baseline_environment") or {}
                if environment.get("matches_expected") is not True:
                    errors.append(f"{capture_id}: baseline environment does not match")
                if environment.get("expected") != AUTHORITATIVE_BASELINE_ENVIRONMENT:
                    errors.append(
                        f"{capture_id}: expected baseline environment is wrong"
                    )
                for key, expected in AUTHORITATIVE_BASELINE_ENVIRONMENT.items():
                    observed = environment.get(key)
                    matches = (
                        isinstance(observed, str) and observed.startswith(expected)
                        if key == "r"
                        else observed == expected
                    )
                    if not matches:
                        errors.append(
                            f"{capture_id}: baseline {key} identity is {observed!r}, "
                            f"expected {expected!r}"
                        )
                tool_versions = capture.get("tool_versions") or {}
                for key, expected in AUTHORITATIVE_TOOL_VERSIONS.items():
                    if tool_versions.get(key) != expected:
                        errors.append(
                            f"{capture_id}: tool {key} identity is "
                            f"{tool_versions.get(key)!r}, expected {expected!r}"
                        )
                r_version = tool_versions.get("r")
                if not isinstance(r_version, str) or not r_version.startswith(
                    AUTHORITATIVE_BASELINE_ENVIRONMENT["r"]
                ):
                    errors.append(f"{capture_id}: tool R identity is wrong")
                package_versions = capture.get("package_versions") or {}
                if package_versions.get("RCMetaR") != "0.1.2":
                    errors.append(f"{capture_id}: RCMetaR identity is not 0.1.2")
                for key in ("pyqt", "qt", "rpy2", "sip"):
                    if package_versions.get(key) != AUTHORITATIVE_TOOL_VERSIONS[key]:
                        errors.append(f"{capture_id}: package {key} identity is wrong")
                texts = capture.get("texts") or {}
                numeric = capture.get("outputs") or {}
                artifacts = capture.get("artifacts") or []
                if not texts and not numeric:
                    errors.append(f"{capture_id}: no observed numeric or text output")
                if not artifacts:
                    errors.append(f"{capture_id}: no observed plot artifact")
                observed_artifacts = []
                for artifact in artifacts:
                    artifact_name = (
                        f"artifacts/{capture_id}/{Path(artifact['path']).name}"
                    )
                    if artifact_name not in names:
                        errors.append(f"{capture_id}: missing {artifact_name}")
                        continue
                    actual_hash = _sha256(archive.read(artifact_name))
                    if actual_hash != artifact.get("sha256"):
                        errors.append(f"{capture_id}: plot hash mismatch")
                    observed_artifacts.append(
                        {
                            "label": artifact["label"],
                            "archive_path": artifact_name,
                            "sha256": actual_hash,
                        }
                    )
                outputs.append(
                    {
                        "id": capture_id,
                        "status": capture.get("status"),
                        "numeric_sections": sorted(numeric),
                        "text_sections": sorted(texts),
                        "artifacts": observed_artifacts,
                    }
                )
    except (
        FileNotFoundError,
        KeyError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
    ) as exc:
        errors.append(f"invalid observed Golden Analysis bundle: {exc}")
    return errors, {
        "schema_version": 1,
        "source_commit": BASELINE_COMMIT,
        "capture_kind": "observed comprehensive Golden Analysis Test outputs",
        "passed": not errors,
        "outputs": outputs,
    }


def capture_rendered_interface_evidence(
    root: Path, evidence_dir: Path
) -> list[dict[str, Any]]:
    """Render two representative baseline interfaces to committed PNG payloads."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    source_dir = root / "src" / "rc_metastudio"
    forms_dir = source_dir / "forms"
    sys.path.insert(0, str(forms_dir))
    sys.path.insert(0, str(source_dir))
    evidence_dir.mkdir(parents=True, exist_ok=True)
    try:
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            from PyQt5 import QtCore, QtWidgets
            import main_wizard

        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        cases = [
            ("startup-welcome", main_wizard.MainWizard()),
            (
                "new-dataset-data-type",
                main_wizard.MainWizard(path="new_dataset"),
            ),
        ]
        records = []
        try:
            for surface, wizard in cases:
                wizard.restart()
                wizard.show()
                for _index in range(3):
                    app.processEvents()
                payload = evidence_dir / f"{surface}.png"
                pixmap = wizard.grab()
                if pixmap.isNull() or not pixmap.save(str(payload), "PNG"):
                    raise RuntimeError(f"could not render baseline surface {surface}")
                records.append(
                    {
                        "surface": surface,
                        "path": payload.relative_to(root).as_posix()
                        if payload.is_relative_to(root)
                        else payload.name,
                        "sha256": _file_sha256(payload),
                        "width": pixmap.width(),
                        "height": pixmap.height(),
                        "platform_plugin": QtWidgets.QApplication.platformName(),
                        "pyqt": QtCore.PYQT_VERSION_STR,
                        "qt": QtCore.QT_VERSION_STR,
                        "source_commit": BASELINE_COMMIT,
                    }
                )
        finally:
            for _surface, wizard in cases:
                wizard.close()
            app.processEvents()
        return records
    finally:
        if sys.path and sys.path[0] == str(source_dir):
            sys.path.pop(0)
        if sys.path and sys.path[0] == str(forms_dir):
            sys.path.pop(0)


def baseline_input_drift(root: Path) -> list[str]:
    """Return runtime/capture inputs that differ from the immutable commit."""
    changed = _run(
        root,
        "git",
        "diff",
        "--name-only",
        BASELINE_COMMIT,
        "--",
        *BASELINE_INPUT_PATHS,
    )
    untracked = _run(
        root,
        "git",
        "ls-files",
        "--others",
        "--exclude-standard",
        "--",
        *BASELINE_INPUT_PATHS,
    )
    return sorted(
        {
            path.replace("\\", "/")
            for path in (changed + "\n" + untracked).splitlines()
            if path and path.replace("\\", "/") not in BASELINE_CAPTURE_EXCLUSIONS
        }
    )


def assert_baseline_inputs_pristine(root: Path) -> None:
    drift = baseline_input_drift(root)
    if drift:
        raise BaselineDriftError(
            "one-time baseline capture refuses post-baseline inputs: "
            + ", ".join(drift)
        )


def _evidence_record(root: Path, relative: str, role: str) -> dict[str, str]:
    return {
        "path": relative,
        "role": role,
        "sha256": _sha256(_git_blob(root, BASELINE_COMMIT, relative)),
    }


def build_baseline_manifest(
    root: Path, baseline_dir: Path | None = None
) -> dict[str, Any]:
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]
    versions = {
        item.split("==", 1)[0]: item.split("==", 1)[1]
        for item in dependencies
        if "==" in item
    }
    workflow_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / ".github/workflows").glob("*.yml")
    )
    python_patch = sorted(
        set(re.findall(r"uv python install (3\.11\.\d+)", workflow_text))
    )[0]
    r_patch = sorted(set(re.findall(r"r-version:\s*(4\.6\.\d+)", workflow_text)))[0]
    baseline_dir = baseline_dir or root / BASELINE_RELATIVE_DIR
    snapshots = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _file_sha256(path),
        }
        for path in sorted((baseline_dir / "sample-projects").glob("*.json"))
    ]
    rendered = json.loads(
        (baseline_dir / "rendered-interface-evidence.json").read_text(encoding="utf-8")
    )["surfaces"]
    return {
        "schema_version": 1,
        "tag": BASELINE_TAG,
        "source_commit": BASELINE_COMMIT,
        "purpose": "Immutable diagnostic oracle for the Native Qt6 Port; not a maintained Qt5 release line.",
        "support_policy": {
            "diagnostic_only": True,
            "forward_ci": False,
            "packaged": False,
            "supported_runtime": False,
        },
        "runtime_identities": {
            "python": python_patch,
            "PyQt5": versions["PyQt5"],
            "Qt5": versions["PyQt5-Qt5"],
            "PyQt5-sip": "12.18.0",
            "R_ci": r_patch,
            "R_minimum": "4.6.0",
            "rpy2": versions["rpy2"],
            "rpy2-rinterface": "3.6.6",
            "rpy2-robjects": "3.6.5",
            "PyInstaller": versions["pyinstaller"],
            "pyinstaller-hooks-contrib": "2026.6",
        },
        "dependency_lock": {
            "path": "uv.lock",
            "sha256": _sha256(_git_blob(root, BASELINE_COMMIT, "uv.lock")),
        },
        "retained_evidence": [
            _evidence_record(
                root,
                "src/rc_metastudio/golden_analysis.py",
                "Golden Analysis Test expected outputs and capture logic",
            ),
            _evidence_record(
                root,
                "docs/verification/comprehensive-golden-baseline-manifest.json",
                "Golden Output Bundle manifest",
            ),
            _evidence_record(
                root,
                "docs/verification/golden-coverage-manifest.json",
                "Golden Analysis Test coverage",
            ),
            _evidence_record(
                root,
                "docs/verification/gui-verification-evidence.md",
                "representative interface evidence",
            ),
            _evidence_record(
                root,
                "docs/verification/adaptive-layout-native-evidence.md",
                "native interface rendering evidence",
            ),
        ],
        "sample_semantic_snapshots": snapshots,
        "observed_golden_analysis_bundle": {
            "path": (baseline_dir / "observed-golden-baseline.zip")
            .relative_to(root)
            .as_posix(),
            "sha256": _file_sha256(baseline_dir / "observed-golden-baseline.zip"),
        },
        "observed_golden_analysis_summary": {
            "path": (baseline_dir / "observed-golden-summary.json")
            .relative_to(root)
            .as_posix(),
            "sha256": _file_sha256(baseline_dir / "observed-golden-summary.json"),
        },
        "rendered_interface_manifest": {
            "path": (baseline_dir / "rendered-interface-evidence.json")
            .relative_to(root)
            .as_posix(),
            "sha256": _file_sha256(baseline_dir / "rendered-interface-evidence.json"),
        },
        "rendered_interface_evidence": rendered,
        "qt_port_inventory": {
            "path": "docs/verification/pre-qt6-baseline/qt-port-inventory.json",
            "sha256": _file_sha256(baseline_dir / "qt-port-inventory.json"),
        },
        "reproduce": "uv run python scripts/capture_pre_qt6_baseline.py --check",
    }


def write_baseline(
    root: Path,
    output_dir: Path | None = None,
    observed_golden_bundle: Path | None = None,
) -> None:
    assert_baseline_inputs_pristine(root)
    target = output_dir or root / BASELINE_RELATIVE_DIR
    snapshots_dir = target / "sample-projects"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    snapshots = capture_sample_snapshots(root)
    for name, snapshot in snapshots.items():
        (snapshots_dir / f"{name}.json").write_bytes(_json_bytes(snapshot))
    (target / "qt-port-inventory.json").write_bytes(
        _json_bytes(build_qt_port_inventory(root))
    )
    destination_bundle = target / "observed-golden-baseline.zip"
    source_bundle = observed_golden_bundle or (
        destination_bundle if destination_bundle.exists() else None
    )
    if source_bundle is None:
        raise RuntimeError(
            "one-time capture requires --observed-golden-bundle from the tagged comprehensive capture"
        )
    errors, observed_summary = inspect_observed_golden_bundle(source_bundle)
    if errors:
        raise RuntimeError("; ".join(errors))
    if source_bundle.resolve() != destination_bundle.resolve():
        destination_bundle.write_bytes(source_bundle.read_bytes())
    (target / "observed-golden-summary.json").write_bytes(_json_bytes(observed_summary))
    rendered = capture_rendered_interface_evidence(root, target / "rendered-interface")
    (target / "rendered-interface-evidence.json").write_bytes(
        _json_bytes(
            {
                "schema_version": 1,
                "source_commit": BASELINE_COMMIT,
                "surfaces": rendered,
            }
        )
    )
    (target / "manifest.json").write_bytes(
        _json_bytes(build_baseline_manifest(root, baseline_dir=target))
    )


def _git_blob(root: Path, commit: str, relative: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def validate_checked_in_baseline(root: Path, require_tag: bool = False) -> list[str]:
    errors: list[str] = []
    target = root / BASELINE_RELATIVE_DIR
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    commit = manifest["source_commit"]
    if require_tag:
        try:
            tagged_commit = _run(root, "git", "rev-list", "-n", "1", manifest["tag"])
            if tagged_commit != commit:
                errors.append(
                    f"tag {manifest['tag']} resolves to {tagged_commit}, expected {commit}"
                )
        except subprocess.CalledProcessError:
            errors.append(f"missing baseline tag {manifest['tag']}")
    for record in [manifest["dependency_lock"], *manifest["retained_evidence"]]:
        actual = _sha256(_git_blob(root, commit, record["path"]))
        if actual != record["sha256"]:
            errors.append(f"baseline blob hash mismatch: {record['path']}")
    for record in manifest["sample_semantic_snapshots"]:
        path = root / record["path"]
        if _file_sha256(path) != record["sha256"]:
            errors.append(f"snapshot hash mismatch: {record['path']}")
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        source_path = snapshot["project_file"]
        if _sha256(_git_blob(root, commit, source_path)) != snapshot["source_sha256"]:
            errors.append(f"sample source hash mismatch: {source_path}")
    golden_record = manifest["observed_golden_analysis_bundle"]
    golden_path = root / golden_record["path"]
    if _file_sha256(golden_path) != golden_record["sha256"]:
        errors.append("observed Golden Analysis Test bundle hash mismatch")
    golden_errors, observed_summary = inspect_observed_golden_bundle(golden_path)
    errors.extend(golden_errors)
    summary_record = manifest["observed_golden_analysis_summary"]
    summary_path = root / summary_record["path"]
    if _file_sha256(summary_path) != summary_record["sha256"]:
        errors.append("observed Golden Analysis Test summary hash mismatch")
    elif json.loads(summary_path.read_text(encoding="utf-8")) != observed_summary:
        errors.append("observed Golden Analysis Test summary does not match bundle")
    rendered_manifest = manifest["rendered_interface_manifest"]
    if _file_sha256(root / rendered_manifest["path"]) != rendered_manifest["sha256"]:
        errors.append("rendered interface evidence manifest hash mismatch")
    for record in manifest["rendered_interface_evidence"]:
        if _file_sha256(root / record["path"]) != record["sha256"]:
            errors.append(
                f"rendered interface evidence hash mismatch: {record['path']}"
            )
    inventory_record = manifest["qt_port_inventory"]
    inventory_path = root / inventory_record["path"]
    if _file_sha256(inventory_path) != inventory_record["sha256"]:
        errors.append("Qt port inventory hash mismatch")
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if inventory["source_commit"] != commit:
        errors.append("inventory source commit does not match baseline")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write baseline evidence")
    parser.add_argument(
        "--observed-golden-bundle",
        type=Path,
        help="complete comprehensive bundle captured from the tagged baseline",
    )
    parser.add_argument(
        "--check", action="store_true", help="validate checked-in evidence"
    )
    parser.add_argument(
        "--require-tag", action="store_true", help="also require the annotated tag"
    )
    parser.add_argument(
        "--legacy-report",
        nargs="?",
        const="-",
        metavar="PATH",
        help="emit the eight executable zero-legacy detector results",
    )
    parser.add_argument(
        "--require-zero",
        action="store_true",
        help="fail unless every zero-legacy detector reaches zero",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.write:
        try:
            write_baseline(root, observed_golden_bundle=args.observed_golden_bundle)
        except (BaselineDriftError, RuntimeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
    errors = (
        validate_checked_in_baseline(root, require_tag=args.require_tag)
        if args.check
        else []
    )
    if args.legacy_report is not None or args.require_zero:
        report = run_zero_legacy_detectors(root)
        payload = _json_bytes(report).decode("utf-8")
        if args.legacy_report in (None, "-"):
            print(payload, end="")
        else:
            Path(args.legacy_report).write_text(payload, encoding="utf-8")
        if args.require_zero and not report["passed"]:
            errors.append("one or more zero-legacy detectors remain nonzero")
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
