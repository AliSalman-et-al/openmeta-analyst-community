"""Validate Comprehensive Golden Baseline manifest consistency."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


VERIFICATION_DIR = Path("docs") / "verification"
WORKFLOW_TRACEABILITY = VERIFICATION_DIR / "workflow-traceability.json"
GOLDEN_COVERAGE = VERIFICATION_DIR / "golden-coverage-manifest.json"
GUI_EVIDENCE = VERIFICATION_DIR / "gui-verification-evidence.md"
COMPATIBILITY_EXCEPTIONS = VERIFICATION_DIR / "compatibility-exceptions.json"
GUI_COMPATIBILITY_EXCEPTIONS = VERIFICATION_DIR / "gui-compatibility-exceptions.json"
GOLDEN_SCHEMA = VERIFICATION_DIR / "golden-baseline.schema.json"
GOLDEN_BASELINE = VERIFICATION_DIR / "comprehensive-golden-baseline-manifest.json"
GOLDEN_MATRIX = VERIFICATION_DIR / "golden-coverage-matrix.md"
WORKFLOW_INVENTORY = VERIFICATION_DIR / "user-facing-workflow-inventory.md"

EXPECTED_MODERN_BASELINE_ENVIRONMENT = {
    "id": "rc-metastudio-python3-pyqt5-r4-RCMetaR",
    "os": "Windows",
    "python": "3.11",
    "pyqt": "5.15.11",
    "r": "R version 4.6.0",
    "rpy2": "3.6.7",
    "package": "RCMetaR",
}

REQUIRED_CAPTURE_METADATA_FIELDS = {
    "python",
    "os",
    "r",
    "rpy2",
    "pyqt",
    "package_versions",
    "commit_sha",
    "capture_mode",
    "capture_command",
    "baseline_environment",
    "authoritative",
    "authority",
}

TRACE_TYPES = {
    "pending",
    "golden_coverage_row",
    "gui_evidence_entry",
    "omission",
    "compatibility_exception",
    "gui_compatibility_exception",
}

REQUIRED_FILES = [
    WORKFLOW_TRACEABILITY,
    GOLDEN_COVERAGE,
    GUI_EVIDENCE,
    COMPATIBILITY_EXCEPTIONS,
    GUI_COMPATIBILITY_EXCEPTIONS,
    GOLDEN_SCHEMA,
    GOLDEN_BASELINE,
    GOLDEN_MATRIX,
    WORKFLOW_INVENTORY,
]


class ValidationError(Exception):
    pass


def load_json(root: Path, relative_path: Path) -> dict:
    path = root / relative_path
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{relative_path}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValidationError(f"{relative_path}: expected a JSON object")
    return data


def require_keys(data: dict, keys: list[str], label: str) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise ValidationError(f"{label}: missing required keys: {', '.join(missing)}")


def require_string(value: object, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{label}: expected a non-empty string")


def require_list(value: object, label: str) -> list:
    if not isinstance(value, list):
        raise ValidationError(f"{label}: expected a list")
    return value


def markdown_headings(root: Path, relative_path: Path) -> set[str]:
    headings: set[str] = set()
    for line in (root / relative_path).read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            headings.add(line.removeprefix("## ").strip())
    return headings


def inventory_release_cutover_names(root: Path) -> set[str]:
    text = (root / WORKFLOW_INVENTORY).read_text(encoding="utf-8")
    in_scope = False
    names: set[str] = set()
    for line in text.splitlines():
        if line == "## Release Cutover Scope":
            in_scope = True
            continue
        if in_scope and line.startswith("## "):
            break
        if in_scope and line.startswith("- "):
            names.add(line[2:].rstrip("."))
    return names


def comparable_name(name: str) -> str:
    return name.replace("`", "")


def validate_baseline_manifest(root: Path) -> None:
    manifest = load_json(root, GOLDEN_BASELINE)
    schema = load_json(root, GOLDEN_SCHEMA)
    require_keys(
        manifest,
        [
            "baseline",
            "captured_at",
            "coverage_matrix",
            "coverage_manifest",
            "schema",
            "curated_golden_set",
            "artifact_bundle",
            "capture_metadata",
            "bundle_contents",
        ],
        str(GOLDEN_BASELINE),
    )
    if manifest["baseline"] != "comprehensive-golden":
        raise ValidationError(
            f"{GOLDEN_BASELINE}: baseline must be comprehensive-golden"
        )
    for key in ("coverage_matrix", "coverage_manifest", "schema"):
        require_string(manifest[key], f"{GOLDEN_BASELINE}:{key}")
        if not (root / manifest[key]).exists():
            raise ValidationError(
                f"{GOLDEN_BASELINE}:{key} points to missing file {manifest[key]}"
            )
    if Path(manifest["coverage_matrix"]) != GOLDEN_MATRIX:
        raise ValidationError(
            f"{GOLDEN_BASELINE}: coverage_matrix must point to {GOLDEN_MATRIX}"
        )
    if Path(manifest["coverage_manifest"]) != GOLDEN_COVERAGE:
        raise ValidationError(
            f"{GOLDEN_BASELINE}: coverage_manifest must point to {GOLDEN_COVERAGE}"
        )
    if Path(manifest["schema"]) != GOLDEN_SCHEMA:
        raise ValidationError(
            f"{GOLDEN_BASELINE}: schema must point to {GOLDEN_SCHEMA}"
        )
    if schema.get("title") != "Comprehensive Golden Baseline Manifest":
        raise ValidationError(f"{GOLDEN_SCHEMA}: unexpected schema title")
    require_list(
        manifest["curated_golden_set"], f"{GOLDEN_BASELINE}:curated_golden_set"
    )
    require_keys(
        manifest["artifact_bundle"],
        ["path", "storage"],
        f"{GOLDEN_BASELINE}:artifact_bundle",
    )
    validate_capture_metadata(manifest["capture_metadata"])
    require_list(manifest["bundle_contents"], f"{GOLDEN_BASELINE}:bundle_contents")


def validate_capture_metadata(metadata: object) -> None:
    if not isinstance(metadata, dict):
        raise ValidationError(f"{GOLDEN_BASELINE}:capture_metadata must be an object")
    require_keys(
        metadata,
        [
            "required_fields",
            "local_default_capture_mode",
            "authoritative_capture_mode",
            "authority_values",
            "baseline",
            "baseline_environment",
            "authoritative_requires_baseline_environment_match",
        ],
        f"{GOLDEN_BASELINE}:capture_metadata",
    )
    fields = set(
        require_list(
            metadata["required_fields"],
            f"{GOLDEN_BASELINE}:capture_metadata.required_fields",
        )
    )
    missing = REQUIRED_CAPTURE_METADATA_FIELDS - fields
    if missing:
        raise ValidationError(
            f"{GOLDEN_BASELINE}:capture_metadata.required_fields missing {', '.join(sorted(missing))}"
        )
    if metadata["local_default_capture_mode"] != "local-debug":
        raise ValidationError(
            f"{GOLDEN_BASELINE}:capture_metadata.local_default_capture_mode must be local-debug"
        )
    if metadata["authoritative_capture_mode"] != "authoritative":
        raise ValidationError(
            f"{GOLDEN_BASELINE}:capture_metadata.authoritative_capture_mode must be authoritative"
        )
    authority_values = set(
        require_list(
            metadata["authority_values"],
            f"{GOLDEN_BASELINE}:capture_metadata.authority_values",
        )
    )
    if authority_values != {"authoritative", "local-debug"}:
        raise ValidationError(
            f"{GOLDEN_BASELINE}:capture_metadata.authority_values must be authoritative and local-debug"
        )
    if metadata["baseline"] != "rc-metastudio-behavior":
        raise ValidationError(
            f"{GOLDEN_BASELINE}:capture_metadata.baseline must be rc-metastudio-behavior"
        )
    if metadata["baseline_environment"] != EXPECTED_MODERN_BASELINE_ENVIRONMENT:
        raise ValidationError(
            f"{GOLDEN_BASELINE}:capture_metadata.baseline_environment does not match the RC MetaStudio Behavior Baseline"
        )
    if metadata["authoritative_requires_baseline_environment_match"] is not True:
        raise ValidationError(
            f"{GOLDEN_BASELINE}:capture_metadata.authoritative_requires_baseline_environment_match must be true"
        )


def validate_exception_manifest(data: dict, expected_name: str, label: str) -> set[str]:
    require_keys(
        data,
        [
            "manifest",
            "schema_version",
            "accepted_exception_required_fields",
            "accepted_exception_requires_one_of",
            "exceptions",
        ],
        label,
    )
    if data["manifest"] != expected_name:
        raise ValidationError(f"{label}: manifest must be {expected_name}")
    exceptions = require_list(data["exceptions"], f"{label}:exceptions")
    required = require_list(
        data["accepted_exception_required_fields"],
        f"{label}:accepted_exception_required_fields",
    )
    one_of = require_list(
        data["accepted_exception_requires_one_of"],
        f"{label}:accepted_exception_requires_one_of",
    )
    accepted_ids: set[str] = set()
    for index, exception in enumerate(exceptions):
        if not isinstance(exception, dict):
            raise ValidationError(f"{label}:exceptions[{index}] must be an object")
        if exception.get("status") != "accepted":
            continue
        missing = [field for field in required if field not in exception]
        if missing:
            raise ValidationError(
                f"{label}:exceptions[{index}] missing {', '.join(missing)}"
            )
        if not any(field in exception for field in one_of):
            raise ValidationError(
                f"{label}:exceptions[{index}] must include one of {', '.join(one_of)}"
            )
        require_string(exception["id"], f"{label}:exceptions[{index}].id")
        require_list(
            exception["affected_workflows"],
            f"{label}:exceptions[{index}].affected_workflows",
        )
        accepted_ids.add(exception["id"])
    return accepted_ids


def validate_golden_coverage(data: dict) -> tuple[set[str], set[str]]:
    require_keys(data, ["matrix", "omissions", "rows"], str(GOLDEN_COVERAGE))
    if data["matrix"] != "golden-coverage":
        raise ValidationError(f"{GOLDEN_COVERAGE}: matrix must be golden-coverage")
    rows = require_list(data["rows"], f"{GOLDEN_COVERAGE}:rows")
    omissions = require_list(data["omissions"], f"{GOLDEN_COVERAGE}:omissions")
    row_ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValidationError(f"{GOLDEN_COVERAGE}:rows[{index}] must be an object")
        require_keys(
            row, ["id", "workflow", "status"], f"{GOLDEN_COVERAGE}:rows[{index}]"
        )
        require_string(row["id"], f"{GOLDEN_COVERAGE}:rows[{index}].id")
        row_ids.add(row["id"])
    omission_branches: set[str] = set()
    for index, omission in enumerate(omissions):
        if not isinstance(omission, dict):
            raise ValidationError(
                f"{GOLDEN_COVERAGE}:omissions[{index}] must be an object"
            )
        require_keys(
            omission,
            ["branch", "reason", "follow_up"],
            f"{GOLDEN_COVERAGE}:omissions[{index}]",
        )
        require_string(
            omission["branch"], f"{GOLDEN_COVERAGE}:omissions[{index}].branch"
        )
        omission_branches.add(omission["branch"])
    return row_ids, omission_branches


def trace_values(trace: object, label: str) -> list[str]:
    if isinstance(trace, str):
        return [trace]
    values = require_list(trace, label)
    for value in values:
        require_string(value, label)
    return values


def validate_traceability(root: Path, strict_no_pending: bool) -> int:
    traceability = load_json(root, WORKFLOW_TRACEABILITY)
    require_keys(
        traceability,
        ["manifest", "source_inventory", "trace_targets", "gate_status", "workflows"],
        str(WORKFLOW_TRACEABILITY),
    )
    if traceability["manifest"] != "workflow-traceability":
        raise ValidationError(
            f"{WORKFLOW_TRACEABILITY}: manifest must be workflow-traceability"
        )
    if Path(traceability["source_inventory"]) != WORKFLOW_INVENTORY:
        raise ValidationError(
            f"{WORKFLOW_TRACEABILITY}: source_inventory must point to {WORKFLOW_INVENTORY}"
        )
    expected_targets = {
        "golden_coverage": GOLDEN_COVERAGE,
        "gui_evidence": GUI_EVIDENCE,
        "compatibility_exceptions": COMPATIBILITY_EXCEPTIONS,
        "gui_compatibility_exceptions": GUI_COMPATIBILITY_EXCEPTIONS,
    }
    for key, path in expected_targets.items():
        if Path(traceability["trace_targets"].get(key, "")) != path:
            raise ValidationError(
                f"{WORKFLOW_TRACEABILITY}: trace_targets.{key} must point to {path}"
            )

    golden_rows, omissions = validate_golden_coverage(load_json(root, GOLDEN_COVERAGE))
    gui_entries = markdown_headings(root, GUI_EVIDENCE)
    compatibility_exceptions = validate_exception_manifest(
        load_json(root, COMPATIBILITY_EXCEPTIONS),
        "compatibility-exceptions",
        str(COMPATIBILITY_EXCEPTIONS),
    )
    gui_exceptions = validate_exception_manifest(
        load_json(root, GUI_COMPATIBILITY_EXCEPTIONS),
        "gui-compatibility-exceptions",
        str(GUI_COMPATIBILITY_EXCEPTIONS),
    )

    target_sets = {
        "golden_coverage_row": golden_rows,
        "gui_evidence_entry": gui_entries,
        "omission": omissions,
        "compatibility_exception": compatibility_exceptions,
        "gui_compatibility_exception": gui_exceptions,
    }

    workflows = require_list(
        traceability["workflows"], f"{WORKFLOW_TRACEABILITY}:workflows"
    )
    inventory_names = inventory_release_cutover_names(root)
    traced_names: set[str] = set()
    pending_count = 0
    for index, workflow in enumerate(workflows):
        if not isinstance(workflow, dict):
            raise ValidationError(
                f"{WORKFLOW_TRACEABILITY}:workflows[{index}] must be an object"
            )
        require_keys(
            workflow,
            ["id", "name", "trace_type", "trace"],
            f"{WORKFLOW_TRACEABILITY}:workflows[{index}]",
        )
        require_string(workflow["id"], f"{WORKFLOW_TRACEABILITY}:workflows[{index}].id")
        require_string(
            workflow["name"], f"{WORKFLOW_TRACEABILITY}:workflows[{index}].name"
        )
        trace_type = workflow["trace_type"]
        if trace_type not in TRACE_TYPES:
            raise ValidationError(
                f"{WORKFLOW_TRACEABILITY}:{workflow['id']} has unknown trace_type {trace_type}"
            )
        traced_names.add(workflow["name"])
        if trace_type == "pending":
            if workflow["trace"] is not None:
                raise ValidationError(
                    f"{WORKFLOW_TRACEABILITY}:{workflow['id']} pending trace must be null"
                )
            pending_count += 1
            continue
        for target in trace_values(
            workflow["trace"], f"{WORKFLOW_TRACEABILITY}:{workflow['id']}.trace"
        ):
            if target not in target_sets[trace_type]:
                raise ValidationError(
                    f"{WORKFLOW_TRACEABILITY}:{workflow['id']} trace target {target!r} "
                    f"not found for {trace_type}"
                )

    comparable_traced_names = {comparable_name(name) for name in traced_names}
    missing_inventory = []
    for name in sorted(inventory_names):
        comparable_inventory_name = comparable_name(name)
        if not any(
            comparable_inventory_name.startswith(traced_name)
            or traced_name.startswith(comparable_inventory_name)
            for traced_name in comparable_traced_names
        ):
            missing_inventory.append(name)
    if missing_inventory:
        raise ValidationError(
            f"{WORKFLOW_TRACEABILITY}: missing Release Cutover workflow trace entries: "
            + "; ".join(missing_inventory)
        )
    if strict_no_pending and pending_count:
        raise ValidationError(
            f"{WORKFLOW_TRACEABILITY}: {pending_count} pending trace entries remain"
        )
    return pending_count


def validate(root: Path, strict_no_pending: bool) -> int:
    for relative_path in REQUIRED_FILES:
        if not (root / relative_path).exists():
            raise ValidationError(f"missing required file: {relative_path}")
    validate_baseline_manifest(root)
    return validate_traceability(root, strict_no_pending)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--strict-no-pending", action="store_true")
    args = parser.parse_args(argv)
    try:
        pending_count = validate(args.root, args.strict_no_pending)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    mode = (
        "strict no-pending mode"
        if args.strict_no_pending
        else "manifest-completeness mode"
    )
    if pending_count:
        print(f"validated {mode}; {pending_count} pending trace entries allowed")
    else:
        print(f"validated {mode}; no pending trace entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
