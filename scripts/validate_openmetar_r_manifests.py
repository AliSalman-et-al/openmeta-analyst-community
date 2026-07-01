"""Validate OpenMetaR R dependency and drift manifests."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


MODERNIZATION_DIR = Path("docs") / "modernization"
DEPENDENCY_MANIFEST = MODERNIZATION_DIR / "OpenMetaR-r-dependencies.json"
DRIFT_MANIFEST = MODERNIZATION_DIR / "OpenMetaR-statistical-drift.json"
EXPECTED_R_TARGET = "4.6.0"

DIRECT_DEPENDENCY_REQUIRED_FIELDS = {
    "name",
    "source",
    "scope",
    "declared_in",
    "evidence",
    "reason",
    "installed_version",
}
APP_BUNDLE_REQUIRED_FIELDS = {"name", "source", "reason", "evidence"}
DRIFT_RECORD_REQUIRED_FIELDS = {
    "id",
    "status",
    "workflow",
    "result_family",
    "reference_implementation_output",
    "modern_OpenMetaR_output",
    "package_versions",
    "methods_involved",
    "likely_reason",
    "independent_validation_signal",
    "user_facing_impact",
    "reviewed_by",
    "reviewed_at",
    "approval_reference",
}


class ValidationError(Exception):
    pass


def load_json(root: Path, relative_path: Path) -> dict:
    path = root / relative_path
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing required file: {relative_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{relative_path}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValidationError(f"{relative_path}: expected a JSON object")
    return data


def require_keys(data: dict, keys: set[str], label: str) -> None:
    missing = sorted(keys - data.keys())
    if missing:
        raise ValidationError(f"{label}: missing required keys: {', '.join(missing)}")


def require_non_empty_string(value: object, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{label}: expected a non-empty string")


def require_list(value: object, label: str) -> list:
    if not isinstance(value, list):
        raise ValidationError(f"{label}: expected a list")
    return value


def validate_dependency_manifest(manifest: dict) -> list[str]:
    require_keys(
        manifest,
        {
            "manifest",
            "schema_version",
            "target_runtime",
            "package_metadata",
            "empty_scope_rationale",
            "direct_OpenMetaR_dependencies",
            "app_r_bundle_dependencies",
            "validation",
        },
        str(DEPENDENCY_MANIFEST),
    )
    if manifest["manifest"] != "OpenMetaR-r-dependencies":
        raise ValidationError(
            f"{DEPENDENCY_MANIFEST}: manifest must be OpenMetaR-r-dependencies"
        )
    if manifest["schema_version"] != 1:
        raise ValidationError(f"{DEPENDENCY_MANIFEST}: schema_version must be 1")
    target_runtime = manifest["target_runtime"]
    if (
        not isinstance(target_runtime, dict)
        or target_runtime.get("r") != EXPECTED_R_TARGET
    ):
        raise ValidationError(
            f"{DEPENDENCY_MANIFEST}: target_runtime.r must be {EXPECTED_R_TARGET}"
        )
    if target_runtime.get("cran_policy") != "latest-compatible":
        raise ValidationError(
            f"{DEPENDENCY_MANIFEST}: target_runtime.cran_policy must be latest-compatible"
        )

    package_metadata = manifest["package_metadata"]
    if not isinstance(package_metadata, dict):
        raise ValidationError(
            f"{DEPENDENCY_MANIFEST}: package_metadata must be an object"
        )
    require_keys(
        package_metadata,
        {"package", "description", "dependency_fields"},
        f"{DEPENDENCY_MANIFEST}:package_metadata",
    )
    if package_metadata["package"] != "OpenMetaR":
        raise ValidationError(
            f"{DEPENDENCY_MANIFEST}: package_metadata.package must be OpenMetaR"
        )
    empty_scope_rationale = manifest["empty_scope_rationale"]
    if not isinstance(empty_scope_rationale, dict):
        raise ValidationError(
            f"{DEPENDENCY_MANIFEST}: empty_scope_rationale must be an object"
        )
    direct_dependencies = require_list(
        manifest["direct_OpenMetaR_dependencies"],
        f"{DEPENDENCY_MANIFEST}:direct_OpenMetaR_dependencies",
    )
    scopes_present = {
        scope
        for dependency in direct_dependencies
        if isinstance(dependency, dict)
        for scope in dependency.get("scope", [])
    }
    for optional_scope in ("test", "build"):
        if optional_scope not in scopes_present:
            require_non_empty_string(
                empty_scope_rationale.get(optional_scope),
                f"{DEPENDENCY_MANIFEST}:empty_scope_rationale.{optional_scope}",
            )

    app_dependencies = require_list(
        manifest["app_r_bundle_dependencies"],
        f"{DEPENDENCY_MANIFEST}:app_r_bundle_dependencies",
    )
    if not direct_dependencies:
        raise ValidationError(
            f"{DEPENDENCY_MANIFEST}: direct_OpenMetaR_dependencies must not be empty"
        )

    direct_names: list[str] = []
    seen_direct: set[str] = set()
    for index, dependency in enumerate(direct_dependencies):
        label = f"{DEPENDENCY_MANIFEST}:direct_OpenMetaR_dependencies[{index}]"
        if not isinstance(dependency, dict):
            raise ValidationError(f"{label}: expected an object")
        require_keys(dependency, DIRECT_DEPENDENCY_REQUIRED_FIELDS, label)
        require_non_empty_string(dependency["name"], f"{label}.name")
        if dependency["name"] in seen_direct:
            raise ValidationError(
                f"{label}: duplicate direct dependency {dependency['name']}"
            )
        seen_direct.add(dependency["name"])
        direct_names.append(dependency["name"])
        scope = require_list(dependency["scope"], f"{label}.scope")
        if not scope or not set(scope) <= {"runtime", "build", "test", "documentation"}:
            raise ValidationError(
                f"{label}.scope: expected runtime/build/test/documentation values"
            )
        if not require_list(dependency["evidence"], f"{label}.evidence"):
            raise ValidationError(
                f"{label}.evidence: expected at least one evidence entry"
            )
        require_non_empty_string(dependency["reason"], f"{label}.reason")
        if (
            dependency["source"] == "cran-archive"
            and dependency["installed_version"] == "latest-compatible"
        ):
            raise ValidationError(
                f"{label}.installed_version: archived CRAN packages must declare an exact version"
            )

    seen_app: set[str] = set()
    overlap = set()
    for index, dependency in enumerate(app_dependencies):
        label = f"{DEPENDENCY_MANIFEST}:app_r_bundle_dependencies[{index}]"
        if not isinstance(dependency, dict):
            raise ValidationError(f"{label}: expected an object")
        require_keys(dependency, APP_BUNDLE_REQUIRED_FIELDS, label)
        require_non_empty_string(dependency["name"], f"{label}.name")
        if dependency["name"] in seen_app:
            raise ValidationError(
                f"{label}: duplicate app bundle dependency {dependency['name']}"
            )
        seen_app.add(dependency["name"])
        if dependency["name"] in seen_direct:
            overlap.add(dependency["name"])
        if not require_list(dependency["evidence"], f"{label}.evidence"):
            raise ValidationError(
                f"{label}.evidence: expected at least one evidence entry"
            )
        require_non_empty_string(dependency["reason"], f"{label}.reason")
    if overlap:
        raise ValidationError(
            f"{DEPENDENCY_MANIFEST}: dependencies must be separated between direct OpenMetaR and app bundle: "
            + ", ".join(sorted(overlap))
        )

    return direct_names


def validate_drift_manifest(manifest: dict) -> None:
    require_keys(
        manifest,
        {
            "manifest",
            "schema_version",
            "target_runtime",
            "reviewed_drift_required_fields",
            "statuses",
            "drift_records",
        },
        str(DRIFT_MANIFEST),
    )
    if manifest["manifest"] != "OpenMetaR-statistical-drift":
        raise ValidationError(
            f"{DRIFT_MANIFEST}: manifest must be OpenMetaR-statistical-drift"
        )
    if manifest["schema_version"] != 1:
        raise ValidationError(f"{DRIFT_MANIFEST}: schema_version must be 1")
    required_fields = set(
        require_list(
            manifest["reviewed_drift_required_fields"],
            f"{DRIFT_MANIFEST}:reviewed_drift_required_fields",
        )
    )
    missing = DRIFT_RECORD_REQUIRED_FIELDS - required_fields
    if missing:
        raise ValidationError(
            f"{DRIFT_MANIFEST}: reviewed_drift_required_fields missing {', '.join(sorted(missing))}"
        )
    statuses = set(require_list(manifest["statuses"], f"{DRIFT_MANIFEST}:statuses"))
    if statuses != {"reviewed", "superseded"}:
        raise ValidationError(
            f"{DRIFT_MANIFEST}: statuses must be reviewed and superseded"
        )
    for index, record in enumerate(
        require_list(manifest["drift_records"], f"{DRIFT_MANIFEST}:drift_records")
    ):
        label = f"{DRIFT_MANIFEST}:drift_records[{index}]"
        if not isinstance(record, dict):
            raise ValidationError(f"{label}: expected an object")
        require_keys(record, DRIFT_RECORD_REQUIRED_FIELDS, label)
        if record["status"] not in statuses:
            raise ValidationError(
                f"{label}.status: expected one of {', '.join(sorted(statuses))}"
            )


def validate(root: Path) -> list[str]:
    direct_dependencies = validate_dependency_manifest(
        load_json(root, DEPENDENCY_MANIFEST)
    )
    validate_drift_manifest(load_json(root, DRIFT_MANIFEST))
    return direct_dependencies


def report_installed_versions(rscript: str, package_names: list[str]) -> dict:
    r_code = "; ".join(
        (
            "packages <- commandArgs(trailingOnly = TRUE)",
            "installed <- installed.packages()",
            "cat(paste('R', getRversion(), sep='\\t'), '\\n', sep='')",
            "for (package in packages) { version <- if (package == 'R') as.character(getRversion()) else if (package %in% rownames(installed)) as.character(installed[package, 'Version']) else NA_character_; cat(paste(package, version, sep='\\t'), '\\n', sep='') }",
        )
    )
    result = subprocess.run(
        [rscript, "-e", r_code, *package_names],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise ValidationError(
            f"R version report failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    versions: dict[str, str | None] = {}
    runtime_version = None
    for line in result.stdout.splitlines():
        parts = line.rstrip("\n").split("\t", 1)
        if len(parts) != 2:
            continue
        name, version = parts
        if name == "R":
            runtime_version = version
        versions[name] = None if version == "NA" else version
    return {"r_version": runtime_version, "packages": versions}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report-installed-versions", action="store_true")
    parser.add_argument("--rscript", default="Rscript")
    args = parser.parse_args(argv)
    try:
        direct_dependencies = validate(args.root)
        if args.report_installed_versions:
            print(
                json.dumps(
                    report_installed_versions(args.rscript, direct_dependencies),
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print("validated OpenMetaR R dependency and drift manifests")
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
