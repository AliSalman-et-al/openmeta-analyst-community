"""Fail-closed source contracts for the native Qt6 hard cutover."""

from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import tomllib
from typing import cast


BASELINE = Path("docs/verification/pre-qt6-baseline/qt-port-inventory.json")
CLASSIFICATION = Path("docs/verification/qt6-legacy-test-classification.json")
DELETED_NODE_BASELINE = Path(
    "docs/verification/pre-qt6-baseline/deleted-test-nodeids.json"
)
TEST_TAXONOMY = Path("docs/verification/test-taxonomy.json")
TY_IGNORE_ALLOWLIST = Path("config/qt6-ty-ignore-allowlist.json")
ALLOWED_DECISIONS = {"ported", "rewritten-at-stronger-seam", "retired"}
ACTIVE_AUDIT_GLOBS = (
    "scripts/*.py",
    "scripts/*.ps1",
    "scripts/*.sh",
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
)
HISTORICAL_AUDIT_ALLOWLIST = {
    "scripts/capture_pre_qt6_baseline.py",
    "scripts/qt6_port.py",
}


class CutoverAuditError(ValueError):
    """Raised when a closed cutover contract is incomplete or malformed."""


@dataclass(frozen=True, order=True)
class CutoverFinding:
    path: str
    rule: str
    detail: str


def discover_handwritten_qt_files(root: Path) -> list[Path]:
    """Return every active handwritten source or script importing PyQt6."""
    root = root.resolve()
    modules: list[Path] = []
    candidates = [
        *root.glob("src/rc_metastudio/**/*.py"),
        *root.glob("scripts/**/*.py"),
    ]
    for path in sorted(set(candidates)):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            (
                isinstance(node, ast.Import)
                and any(
                    alias.name == "PyQt6" or alias.name.startswith("PyQt6.")
                    for alias in node.names
                )
            )
            or (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and (node.module == "PyQt6" or node.module.startswith("PyQt6."))
            )
            for node in ast.walk(tree)
        ):
            modules.append(path)
    return modules


def discover_application_qt_modules(root: Path) -> list[Path]:
    """Return the importable application-module subset of the Qt-bearing files."""
    source_root = root.resolve() / "src/rc_metastudio"
    return [
        path
        for path in discover_handwritten_qt_files(root)
        if path.parent == source_root
    ]


_TY_IGNORE_RE = re.compile(r"# ty:" + r" ignore\[([^\]]+)\]\s*--\s*(.+)$")


def _qualified_function_nodes(
    tree: ast.Module,
) -> dict[int, tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    nodes: dict[int, tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = {}

    def visit(body: list[ast.stmt], prefix: tuple[str, ...]) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                visit(node.body, (*prefix, node.name))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified_name = ".".join((*prefix, node.name))
                nodes[node.lineno] = (qualified_name, node)
                visit(node.body, (*prefix, node.name))

    visit(tree.body, ())
    return nodes


def _ty_ignore_entries(root: Path) -> list[dict[str, str]]:
    """Fingerprint each override suppression with its owner and full function AST."""
    root = root.resolve()
    entries: list[dict[str, str]] = []
    for base in (root / "src", root / "scripts"):
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            functions = _qualified_function_nodes(tree)
            relative = path.relative_to(root).as_posix()
            for lineno, line in enumerate(source.splitlines(), start=1):
                if "# ty:" + " ignore" not in line:
                    continue
                match = _TY_IGNORE_RE.search(line)
                if match is None:
                    raise CutoverAuditError(
                        f"malformed ty ignore at {relative}:{lineno}"
                    )
                function = functions.get(lineno)
                if function is None:
                    raise CutoverAuditError(
                        f"ty ignore must annotate a function declaration at "
                        f"{relative}:{lineno}"
                    )
                qualified_name, node = function
                rule = match.group(1)
                payload = json.dumps(
                    {
                        "path": relative,
                        "qualified_name": qualified_name,
                        "rule": rule,
                        "function_ast": ast.dump(
                            node, annotate_fields=True, include_attributes=False
                        ),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                entries.append(
                    {
                        "path": relative,
                        "qualified_name": qualified_name,
                        "rule": rule,
                        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                    }
                )
    return sorted(
        entries,
        key=lambda entry: (entry["path"], entry["qualified_name"], entry["rule"]),
    )


def validate_ty_ignore_allowlist(root: Path) -> dict[str, int]:
    """Reject every unreviewed or context-modified ``ty`` override suppression."""
    root = root.resolve()
    manifest = _load_json(root / TY_IGNORE_ALLOWLIST)
    schema_version = manifest.get("schema_version")
    maximum = manifest.get("maximum_total")
    records = manifest.get("entries")
    if (
        schema_version != 2
        or not isinstance(maximum, int)
        or maximum < 0
        or not isinstance(records, list)
    ):
        raise CutoverAuditError(
            "ty ignore allowlist needs schema version 2, a non-negative budget, "
            "and entries"
        )
    expected: list[dict[str, str]] = []
    for record in records:
        if not isinstance(record, dict):
            raise CutoverAuditError("ty ignore allowlist records must be objects")
        entry = {
            key: record.get(key) for key in ("path", "qualified_name", "rule", "sha256")
        }
        if not all(isinstance(value, str) for value in entry.values()):
            raise CutoverAuditError("ty ignore allowlist record is malformed")
        expected.append(cast(dict[str, str], entry))
    expected = sorted(
        expected,
        key=lambda entry: (entry["path"], entry["qualified_name"], entry["rule"]),
    )
    identities = [
        (entry["path"], entry["qualified_name"], entry["rule"]) for entry in expected
    ]
    if len(identities) != len(set(identities)):
        raise CutoverAuditError("duplicate ty ignore allowlist entry")

    observed = _ty_ignore_entries(root)
    if observed != expected:
        raise CutoverAuditError(
            f"ty ignore allowlist drifted: expected={expected!r} observed={observed!r}"
        )
    total = len(observed)
    if total > maximum:
        raise CutoverAuditError(f"ty ignore budget exceeded: {total} > {maximum}")
    return {
        "files": len({entry["path"] for entry in observed}),
        "total": total,
        "maximum": maximum,
    }


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CutoverAuditError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CutoverAuditError(f"{path} must contain a JSON object")
    return value


def validate_legacy_test_classification(root: Path) -> dict[str, object]:
    """Prove every frozen PyQt5-era test has a named Qt6 disposition."""
    root = root.resolve()
    baseline = _load_json(root / BASELINE)
    manifest = _load_json(root / CLASSIFICATION)
    expected = baseline.get("qt_bearing_tests")
    records = manifest.get("classifications")
    if not isinstance(expected, list) or not all(
        isinstance(item, str) for item in expected
    ):
        raise CutoverAuditError("frozen qt_bearing_tests must be a list of paths")
    if not isinstance(records, list):
        raise CutoverAuditError("classifications must be a list")

    observed: dict[str, dict[str, object]] = {}
    decisions: Counter[str] = Counter()
    for raw_record in records:
        if not isinstance(raw_record, dict):
            raise CutoverAuditError("every classification needs one legacy_test path")
        record = cast(dict[str, object], raw_record)
        if not isinstance(record.get("legacy_test"), str):
            raise CutoverAuditError("every classification needs one legacy_test path")
        legacy_test = record["legacy_test"]
        assert isinstance(legacy_test, str)
        if legacy_test in observed:
            raise CutoverAuditError(
                f"duplicate legacy test classification: {legacy_test}"
            )
        decision = record.get("decision")
        if decision not in ALLOWED_DECISIONS:
            raise CutoverAuditError(f"invalid decision for {legacy_test}: {decision!r}")
        evidence = record.get("evidence")
        if (
            not isinstance(evidence, list)
            or not evidence
            or not all(isinstance(item, str) and item for item in evidence)
        ):
            raise CutoverAuditError(f"{legacy_test} needs named stronger evidence")
        evidence_items = cast(list[str], evidence)
        for item in evidence_items:
            evidence_path = item.split("::", 1)[0]
            if not (root / evidence_path).is_file():
                raise CutoverAuditError(
                    f"{legacy_test} names missing evidence: {evidence_path}"
                )
        if decision == "ported" and legacy_test not in evidence_items:
            raise CutoverAuditError(
                f"ported test must name its maintained path: {legacy_test}"
            )
        observed[legacy_test] = record
        decisions[str(decision)] += 1

    missing = sorted(set(expected) - set(observed))
    extra = sorted(set(observed) - set(expected))
    if missing or extra:
        raise CutoverAuditError(
            f"legacy test classification is not closed: missing={missing!r} extra={extra!r}"
        )

    deleted_baseline = _load_json(root / DELETED_NODE_BASELINE)
    expected_nodes = deleted_baseline.get("deleted_test_nodes")
    node_records = manifest.get("deleted_test_nodes")
    taxonomy = _load_json(root / TEST_TAXONOMY)
    taxonomy_records = taxonomy.get("tests")
    if not isinstance(expected_nodes, list) or not all(
        isinstance(item, str) for item in expected_nodes
    ):
        raise CutoverAuditError("deleted test node baseline must be a list of nodeids")
    if not isinstance(node_records, list):
        raise CutoverAuditError("deleted test classifications need exact records")
    if not isinstance(taxonomy_records, list):
        raise CutoverAuditError("test taxonomy must contain a collected test list")
    collected_nodeids = {
        item["nodeid"]
        for item in taxonomy_records
        if isinstance(item, dict) and isinstance(item.get("nodeid"), str)
    }
    observed_nodes: set[str] = set()
    for record in node_records:
        if not isinstance(record, dict):
            raise CutoverAuditError("deleted test classifications must be objects")
        nodeid = record.get("legacy_nodeid")
        decision = record.get("decision")
        evidence = record.get("evidence_nodeid")
        rationale = record.get("rationale")
        if not isinstance(nodeid, str) or decision not in ALLOWED_DECISIONS:
            raise CutoverAuditError(
                "deleted test record needs a nodeid and valid decision"
            )
        if not isinstance(evidence, str) or "::" not in evidence:
            raise CutoverAuditError(f"{nodeid} needs one exact replacement test nodeid")
        if not isinstance(rationale, str) or len(rationale.strip()) < 20:
            raise CutoverAuditError(f"{nodeid} needs a concrete semantic rationale")
        if evidence not in collected_nodeids:
            raise CutoverAuditError(
                f"{nodeid} names a replacement not present in collected taxonomy: {evidence!r}"
            )
        if nodeid in observed_nodes:
            raise CutoverAuditError(f"duplicate deleted test classification: {nodeid}")
        observed_nodes.add(nodeid)
    missing_nodes = sorted(set(expected_nodes) - observed_nodes)
    extra_nodes = sorted(observed_nodes - set(expected_nodes))
    if missing_nodes or extra_nodes:
        raise CutoverAuditError(
            "deleted test node classification is not closed: "
            f"missing={missing_nodes!r} extra={extra_nodes!r}"
        )
    return {
        "classified": len(observed),
        "classified_deleted_nodes": len(observed_nodes),
        "decisions": dict(sorted(decisions.items())),
    }


def _python_findings(root: Path, path: Path) -> list[CutoverFinding]:
    relative = path.relative_to(root).as_posix()
    findings: list[CutoverFinding] = []
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative)
    except (OSError, UnicodeError, SyntaxError) as exc:
        return [CutoverFinding(relative, "python-parse", str(exc))]

    generated_name = (
        path.parent.name == "forms" and path.name.startswith("ui_")
    ) or path.name in {"ui_meta.py", "ui_results_window.py", "icons_rc.py"}
    generated_marker = (
        "generated from reading ui file" in source.lower()
        or "qt_resource_data" in source
    )
    if generated_name or generated_marker:
        findings.append(
            CutoverFinding(
                relative, "generated-python", "generated Qt Python is tracked"
            )
        )

    for node in ast.walk(tree):
        imported: list[str] = []
        if isinstance(node, ast.Import):
            imported = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported = [node.module]
        for name in imported:
            root_name = name.split(".", 1)[0]
            if root_name in {"PyQt5", "qtpy", "PySide2", "PySide6", "Qt5Compat"}:
                findings.append(CutoverFinding(relative, "legacy-binding", name))
            if root_name == "pickle":
                findings.append(
                    CutoverFinding(
                        relative,
                        "pickle-project-runtime",
                        "pickle import in application source",
                    )
                )
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and ".rcms.state" in node.value
        ):
            findings.append(CutoverFinding(relative, "rcms-state-sidecar", node.value))
    return findings


def audit_cutover(root: Path) -> list[CutoverFinding]:
    """Return active runtime, generated-source, and packaging cutover violations."""
    root = root.resolve()
    findings: list[CutoverFinding] = []
    source_root = root / "src/rc_metastudio"
    if source_root.is_dir():
        for path in sorted(source_root.rglob("*.py")):
            if "__pycache__" not in path.parts and path.name not in {
                "qt6_cutover.py",
                "qt6_port_tools.py",
            }:
                findings.extend(_python_findings(root, path))

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        package_data = (
            data.get("tool", {}).get("setuptools", {}).get("package-data", {})
        )
        packaged_patterns = (
            [
                pattern
                for patterns in package_data.values()
                for pattern in patterns
                if isinstance(pattern, str)
            ]
            if isinstance(package_data, dict)
            else []
        )
        if any(
            pattern.endswith(".py") or ".py" in pattern for pattern in packaged_patterns
        ):
            findings.append(
                CutoverFinding(
                    "pyproject.toml",
                    "python-package-input",
                    "Python generated output is package data",
                )
            )

    active_verification: list[Path] = []
    for pattern in ACTIVE_AUDIT_GLOBS:
        active_verification.extend(root.glob(pattern))
    for path in sorted(set(active_verification)):
        relative = path.relative_to(root).as_posix()
        if relative in HISTORICAL_AUDIT_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        for token in ("PyQt5", "Qt5Compat", "pyuic5", "pyrcc5", "sip.setapi"):
            if token in text:
                findings.append(
                    CutoverFinding(relative, "legacy-verification-or-packaging", token)
                )

    return sorted(set(findings))


def main() -> int:
    root = Path.cwd()
    validate_legacy_test_classification(root)
    validate_ty_ignore_allowlist(root)
    findings = audit_cutover(root)
    if findings:
        for finding in findings:
            print(f"{finding.path}: {finding.rule}: {finding.detail}")
        return 1
    print("Qt6 final cutover audit passed with zero active legacy findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
