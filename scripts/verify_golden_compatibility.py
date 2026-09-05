# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare current real-R results with the frozen behavior baseline."""

from __future__ import annotations

import argparse
import copy
import hashlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
from pathlib import PurePosixPath
import shutil
import stat
import sys
from typing import Any, TypeAlias, TypedDict, cast
import zipfile

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from tests.analysis_regression.golden.support import golden_analysis  # noqa: E402
from tests.analysis_regression.golden.support.analysis_regression_compare import (  # noqa: E402
    compare_golden_baseline,
)


ARCHIVE_RELATIVE_PATH = PurePosixPath(
    "tests/analysis_regression/baseline/observed-golden-baseline.zip"
)
OUTER_MANIFEST_RELATIVE_PATH = Path("tests/analysis_regression/baseline/manifest.json")
OUTPUT_BASE_RELATIVE_PATH = Path("build/qt6-verification")
OUTPUT_MARKER = ".rcms-golden-verification-output"
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_MEMBER_COUNT = 64
MAX_MEMBER_BYTES = 4 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 16 * 1024 * 1024
MAX_NUMERIC_CONTRACT_BYTES = 256 * 1024
NUMERIC_CONTRACT_RELATIVE_PATH = (
    "tests/analysis_regression/baseline/numeric-contract.json"
)
REQUIRED_RPY2_IDENTITIES = {
    "rpy2": "3.6.7",
    "rpy2-rinterface": "3.6.6",
    "rpy2-robjects": "3.6.5",
}


JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)
JsonObject: TypeAlias = dict[str, JsonValue]


class GoldenArtifact(TypedDict):
    bundle_path: str
    path: str
    sha256: str
    label: str


class GoldenCase(TypedDict, total=False):
    id: str
    status: str
    texts: JsonObject
    outputs: JsonObject
    artifacts: list[GoldenArtifact]
    numeric_tolerance_policy: JsonObject


class FrozenGoldenReference(TypedDict):
    baseline: str
    curated_golden_set: list[GoldenCase]


class ManifestEntry(TypedDict, total=False):
    path: str
    sha256: str
    size: int


class RepositoryManifest(TypedDict, total=False):
    schema_version: int
    observed_golden_analysis_bundle: ManifestEntry
    golden_plot_descriptor_contract: ManifestEntry
    golden_numeric_contract: ManifestEntry
    runtime_identities: dict[str, str]


class PlotDescriptorContract(TypedDict, total=False):
    schema_version: int
    contract: str
    oracle_sha256: str
    rows: list[JsonObject]


class NumericContract(TypedDict, total=False):
    schema_version: int
    contract: str
    oracle_sha256: str
    cases: list[JsonObject]
    tolerance_policy: JsonObject
    coverage: dict[str, JsonObject]


class CaptureManifest(TypedDict, total=False):
    curated_golden_set: list[str]


class ExceptionManifest(TypedDict, total=False):
    exceptions: list[JsonObject]


def _load_json(path: Path) -> JsonValue:
    return _narrow_json(json.loads(path.read_text(encoding="utf-8")))


def _narrow_json(value: object) -> JsonValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_narrow_json(item) for item in value]
    if isinstance(value, dict):
        result: JsonObject = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be strings")
            result[key] = _narrow_json(item)
        return result
    raise ValueError("JSON contains an unsupported value")


def _load_manifest(path: Path) -> RepositoryManifest:
    value = _load_json(path)
    record = _json_object(value, "JSON manifest must contain an object")
    result: RepositoryManifest = {}
    schema_version = record.get("schema_version")
    if schema_version is not None:
        if not isinstance(schema_version, int) or isinstance(schema_version, bool):
            raise ValueError("JSON manifest schema version must be an integer")
        result["schema_version"] = schema_version
    for field in (
        "observed_golden_analysis_bundle",
        "golden_plot_descriptor_contract",
        "golden_numeric_contract",
    ):
        if field in record:
            result[field] = _manifest_entry(record[field])
    identities = record.get("runtime_identities")
    if identities is not None:
        identity_record = _json_object(
            identities, "runtime identities must contain an object"
        )
        result["runtime_identities"] = {
            name: identity
            for name, identity in identity_record.items()
            if isinstance(identity, str)
        }
        if len(result["runtime_identities"]) != len(identity_record):
            raise ValueError("runtime identities must contain only strings")
    return result


def _load_plot_contract(path: Path) -> PlotDescriptorContract:
    record = _json_object(_load_json(path), "plot descriptor contract must contain an object")
    rows = record.get("rows")
    if not isinstance(rows, list):
        raise ValueError("plot descriptor contract rows must contain objects")
    row_records: list[JsonObject] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("plot descriptor contract rows must contain objects")
        row_records.append(row)
    result: PlotDescriptorContract = {"rows": row_records}
    for field in ("schema_version", "contract", "oracle_sha256"):
        value = record.get(field)
        if field == "schema_version" and isinstance(value, int):
            result[field] = value
        elif field != "schema_version" and isinstance(value, str):
            result[field] = value
        else:
            raise ValueError("plot descriptor contract has an invalid field")
    return result


def _load_numeric_contract_record(path: Path) -> NumericContract:
    record = _json_object(_load_json(path), "numeric contract must contain an object")
    cases = record.get("cases")
    tolerance = record.get("tolerance_policy")
    coverage = record.get("coverage")
    if not isinstance(cases, list) or not isinstance(tolerance, dict) or not isinstance(coverage, dict):
        raise ValueError("numeric contract has invalid record shapes")
    case_records: list[JsonObject] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("numeric contract cases must contain objects")
        case_records.append(case)
    coverage_records: dict[str, JsonObject] = {}
    for name, value in coverage.items():
        if not isinstance(value, dict):
            raise ValueError("numeric contract coverage must contain objects")
        coverage_records[name] = value
    schema_version = record.get("schema_version")
    contract_name = record.get("contract")
    oracle_sha256 = record.get("oracle_sha256")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or not isinstance(contract_name, str)
        or not isinstance(oracle_sha256, str)
    ):
        raise ValueError("numeric contract has invalid identity fields")
    return {
        "schema_version": schema_version,
        "contract": contract_name,
        "oracle_sha256": oracle_sha256,
        "cases": case_records,
        "tolerance_policy": tolerance,
        "coverage": coverage_records,
    }


def _load_capture_manifest(path: Path) -> CaptureManifest:
    record = _json_object(_load_json(path), "capture manifest must contain an object")
    cases = record.get("curated_golden_set")
    if not isinstance(cases, list) or not all(isinstance(case, str) for case in cases):
        raise ValueError("capture manifest cases must contain strings")
    return {"curated_golden_set": cases}


def _load_exception_manifest(path: Path) -> ExceptionManifest:
    record = _json_object(
        _load_json(path), "exception manifest must contain an object"
    )
    exceptions = record.get("exceptions", [])
    if not isinstance(exceptions, list):
        raise ValueError("exception manifest entries must contain objects")
    exception_records: list[JsonObject] = []
    for exception in exceptions:
        if not isinstance(exception, dict):
            raise ValueError("exception manifest entries must contain objects")
        exception_records.append(exception)
    return {"exceptions": exception_records}


def _json_object(value: JsonValue | None, message: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError(message)
    return value


def _manifest_entry(value: JsonValue) -> ManifestEntry:
    record = _json_object(value, "manifest entry must contain an object")
    path = record.get("path")
    sha256 = record.get("sha256")
    size = record.get("size")
    if (
        not isinstance(path, str)
        or not isinstance(sha256, str)
        or not isinstance(size, int)
        or isinstance(size, bool)
    ):
        raise ValueError("manifest entry has invalid fields")
    return {"path": path, "sha256": sha256, "size": size}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_reparse_point(path: Path) -> bool:
    attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _assert_plain_path(path: Path, *, include_leaf: bool = True) -> None:
    existing = path if include_leaf else path.parent
    while not existing.exists() and existing != existing.parent:
        existing = existing.parent
    current = existing
    while True:
        if current.is_symlink() or _is_reparse_point(current):
            raise ValueError("verification path contains a symlink or reparse point")
        if current == current.parent:
            break
        current = current.parent


def _safe_output_root(root: Path, requested: Path) -> Path:
    root = root.resolve(strict=True)
    output_base_path = root / OUTPUT_BASE_RELATIVE_PATH
    _assert_plain_path(output_base_path)
    output_base = output_base_path.resolve(strict=False)
    candidate = requested if requested.is_absolute() else root / requested
    _assert_plain_path(candidate)
    canonical = candidate.resolve(strict=False)
    try:
        relative = canonical.relative_to(output_base)
    except ValueError as exc:
        raise ValueError(
            "Golden output must stay under build/qt6-verification"
        ) from exc
    if relative == Path(".") or not relative.parts:
        raise ValueError("Golden output cannot be the verification root")
    if not relative.parts[0].startswith("golden-compatibility-"):
        raise ValueError(
            "Golden output must use a dedicated golden-compatibility directory"
        )
    return canonical


def _prepare_output_root(root: Path, requested: Path) -> Path:
    output_root = _safe_output_root(root, requested)
    if output_root.exists():
        marker = output_root / OUTPUT_MARKER
        if (
            not output_root.is_dir()
            or not marker.is_file()
            or marker.read_text(encoding="utf-8") != "rcms-golden-verification-v1\n"
        ):
            raise ValueError("refusing to delete an unowned Golden output directory")
        _assert_plain_path(output_root)
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    (output_root / OUTPUT_MARKER).write_text(
        "rcms-golden-verification-v1\n", encoding="utf-8"
    )
    return output_root


def _validate_internal_manifest(reference: object) -> FrozenGoldenReference:
    if not isinstance(reference, dict):
        raise ValueError("frozen internal manifest has the wrong schema")
    record = cast(dict[str, object], reference)
    if record.get("baseline") != "comprehensive-golden":
        raise ValueError("frozen internal manifest has the wrong schema")
    rows = record.get("curated_golden_set")
    if not isinstance(rows, list) or len(rows) != 11:
        raise ValueError("frozen internal manifest must contain exactly 11 cases")
    ids = []
    typed_rows: list[GoldenCase] = []
    for raw_row in rows:
        if not isinstance(raw_row, dict):
            raise ValueError("frozen case is malformed or unsuccessful")
        raw_row = cast(JsonObject, raw_row)
        status = raw_row.get("status")
        if status != "success":
            raise ValueError("frozen case is malformed or unsuccessful")
        row_id = raw_row.get("id")
        if (
            not isinstance(row_id, str)
            or not row_id
            or any(
                character not in "abcdefghijklmnopqrstuvwxyz0123456789-"
                for character in row_id
            )
        ):
            raise ValueError("frozen case id is unsafe")
        ids.append(row_id)
        texts = raw_row.get("texts")
        if not isinstance(texts, dict) or len(texts) > 16:
            raise ValueError("frozen text contract is malformed")
        outputs = raw_row.get("outputs")
        if not isinstance(outputs, dict) or len(outputs) > 16:
            raise ValueError("frozen numeric contract is malformed")
        artifacts = _validate_golden_artifacts(raw_row.get("artifacts"))
        if len(artifacts) > 4:
            raise ValueError("frozen artifact contract is malformed")
        typed_rows.append(cast(GoldenCase, {**raw_row, "artifacts": artifacts}))
    if len(set(ids)) != len(ids):
        raise ValueError("frozen case ids are duplicated")
    return {"baseline": "comprehensive-golden", "curated_golden_set": typed_rows}


def _validate_golden_artifacts(value: JsonValue | None) -> list[GoldenArtifact]:
    if not isinstance(value, list):
        raise ValueError("frozen artifact contract is malformed")
    artifacts: list[GoldenArtifact] = []
    for raw_artifact in value:
        if not isinstance(raw_artifact, dict):
            raise ValueError("frozen artifact contract is malformed")
        bundle_path = raw_artifact.get("bundle_path")
        path = raw_artifact.get("path")
        sha256 = raw_artifact.get("sha256")
        label = raw_artifact.get("label")
        if not all(
            isinstance(field, str) and field
            for field in (bundle_path, path, sha256, label)
        ):
            raise ValueError("frozen artifact contract is malformed")
        artifacts.append(
            {
                "bundle_path": bundle_path,
                "path": path,
                "sha256": sha256,
                "label": label,
            }
        )
    return artifacts


def _validate_member_name(name: str) -> None:
    pure = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or ":" in name
        or pure.is_absolute()
        or ".." in pure.parts
        or str(pure) != name
    ):
        raise ValueError("unsafe frozen ZIP member name: %s" % name)


def _read_validated_zip(archive_path: Path) -> FrozenGoldenReference:
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        if not infos or len(infos) > MAX_MEMBER_COUNT:
            raise ValueError("frozen ZIP member count is outside the allowed bounds")
        names = []
        total = 0
        for info in infos:
            _validate_member_name(info.filename)
            if info.is_dir() or info.flag_bits & 0x1:
                raise ValueError("frozen ZIP contains a directory or encrypted member")
            if info.file_size > MAX_MEMBER_BYTES:
                raise ValueError("frozen ZIP member exceeds the size bound")
            total += info.file_size
            names.append(info.filename)
        if total > MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise ValueError("frozen ZIP exceeds the uncompressed size bound")
        if len(set(name.casefold() for name in names)) != len(names):
            raise ValueError("frozen ZIP contains duplicate member names")
        if "manifest.json" not in names:
            raise ValueError("frozen ZIP has no internal manifest")
        reference = _validate_internal_manifest(
            json.loads(archive.read("manifest.json").decode("utf-8"))
        )
        expected_members = {"manifest.json"}
        for row in reference["curated_golden_set"]:
            capture_member = "captures/%s.json" % row["id"]
            expected_members.add(capture_member)
            if capture_member not in names:
                raise ValueError("frozen case capture is missing")
            if json.loads(archive.read(capture_member).decode("utf-8")) != row:
                raise ValueError("frozen internal manifest and case capture disagree")
            for artifact in row["artifacts"]:
                basename = Path(
                    str(artifact.get("bundle_path") or artifact.get("path"))
                ).name
                member = "artifacts/%s/%s" % (row["id"], basename)
                expected_members.add(member)
                if member not in names:
                    raise ValueError("frozen artifact is missing: %s" % member)
                observed = hashlib.sha256(archive.read(member)).hexdigest()
                if observed != artifact.get("sha256"):
                    raise ValueError("frozen artifact hash mismatch: %s" % member)
        if set(names) != expected_members:
            raise ValueError("frozen ZIP contains missing or unexpected members")
        return reference


def _load_frozen_reference(root: Path) -> tuple[Path, FrozenGoldenReference]:
    outer_path = (root / OUTER_MANIFEST_RELATIVE_PATH).resolve(strict=True)
    outer = _load_manifest(outer_path)
    entry = outer.get("observed_golden_analysis_bundle")
    if (
        outer.get("schema_version") != 1
        or not isinstance(entry, dict)
        or entry.get("path") != str(ARCHIVE_RELATIVE_PATH)
        or not isinstance(entry.get("size"), int)
        or not 0 < entry["size"] <= MAX_ARCHIVE_BYTES
        or not isinstance(entry.get("sha256"), str)
        or len(entry["sha256"]) != 64
    ):
        raise ValueError("outer Golden manifest contract is malformed")
    archive_path = (root / Path(*ARCHIVE_RELATIVE_PATH.parts)).resolve(strict=True)
    expected_path = (root / Path(*ARCHIVE_RELATIVE_PATH.parts)).absolute()
    if archive_path != expected_path or not archive_path.is_file():
        raise ValueError("frozen archive is not the exact committed regular file")
    _assert_plain_path(archive_path)
    if archive_path.stat().st_size != entry["size"]:
        raise ValueError("frozen archive size does not match the outer manifest")
    if _sha256(archive_path) != entry["sha256"]:
        raise ValueError("frozen archive hash does not match the outer manifest")
    return archive_path, _read_validated_zip(archive_path)


def _load_plot_descriptor_contract(
    root: Path, archive_path: Path, reference: FrozenGoldenReference
) -> PlotDescriptorContract:
    outer = _load_manifest(root / OUTER_MANIFEST_RELATIVE_PATH)
    entry = outer.get("golden_plot_descriptor_contract")
    expected_relative = "tests/analysis_regression/baseline/plot-descriptors.json"
    if (
        not isinstance(entry, dict)
        or entry.get("path") != expected_relative
        or not isinstance(entry.get("size"), int)
        or not 0 < entry["size"] < 65536
        or not isinstance(entry.get("sha256"), str)
        or len(entry["sha256"]) != 64
    ):
        raise ValueError("plot descriptor outer contract is malformed")
    path = (root / expected_relative).resolve(strict=True)
    if path != (root / expected_relative).absolute() or not path.is_file():
        raise ValueError("plot descriptor contract is not the exact committed file")
    _assert_plain_path(path)
    if path.stat().st_size != entry["size"] or _sha256(path) != entry["sha256"]:
        raise ValueError("plot descriptor contract failed size or hash verification")
    contract = _load_plot_contract(path)
    rows = contract.get("rows")
    if (
        contract.get("schema_version") != 1
        or contract.get("contract") != "golden-plot-descriptors"
        or contract.get("oracle_sha256") != _sha256(archive_path)
        or not isinstance(rows, list)
        or len(rows) != 11
    ):
        raise ValueError("plot descriptor contract schema or oracle binding is invalid")
    reference_by_id = {row["id"]: row for row in reference["curated_golden_set"]}
    seen = set()
    for row in rows:
        row_id = row.get("id")
        if row_id in seen or row_id not in reference_by_id:
            raise ValueError("plot descriptor contract case set is invalid")
        seen.add(row_id)
        artifacts = {
            artifact["label"]: artifact
            for artifact in reference_by_id[row_id]["artifacts"]
        }
        label = row.get("artifact_label")
        if label not in artifacts or row.get("artifact_oracle_sha256") != artifacts[
            label
        ].get("sha256"):
            raise ValueError(
                "plot descriptor is not tied to its frozen artifact oracle"
            )
    if seen != set(reference_by_id):
        raise ValueError("plot descriptor contract is missing cases")
    return contract


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _load_numeric_contract(
    root: Path, archive_path: Path, reference: FrozenGoldenReference
) -> NumericContract:
    outer = _load_manifest(root / OUTER_MANIFEST_RELATIVE_PATH)
    entry = outer.get("golden_numeric_contract")
    if (
        not isinstance(entry, dict)
        or entry.get("path") != NUMERIC_CONTRACT_RELATIVE_PATH
        or not isinstance(entry.get("size"), int)
        or not 0 < entry["size"] <= MAX_NUMERIC_CONTRACT_BYTES
        or not isinstance(entry.get("sha256"), str)
        or len(entry["sha256"]) != 64
    ):
        raise ValueError("numeric outer contract is malformed")
    path = (root / NUMERIC_CONTRACT_RELATIVE_PATH).resolve(strict=True)
    if path != (root / NUMERIC_CONTRACT_RELATIVE_PATH).absolute() or not path.is_file():
        raise ValueError("numeric contract is not the exact committed file")
    _assert_plain_path(path)
    raw = path.read_bytes()
    if len(raw) != entry["size"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError("numeric contract failed size or hash verification")
    try:
        contract = _load_numeric_contract_record(path)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("numeric contract is not canonical UTF-8 JSON") from exc
    if raw != _canonical_json_bytes(contract):
        raise ValueError("numeric contract is not canonically serialized")

    cases = contract.get("cases")
    tolerance = contract.get("tolerance_policy")
    if (
        contract.get("schema_version") != 1
        or contract.get("contract") != "golden-numeric-results"
        or contract.get("oracle_sha256") != _sha256(archive_path)
        or not isinstance(cases, list)
        or len(cases) != 11
        or not isinstance(tolerance, dict)
        or set(tolerance) != {"absolute", "relative", "rule"}
        or tolerance.get("rule") != "max(absolute, relative * abs(expected))"
    ):
        raise ValueError("numeric contract schema or oracle binding is invalid")
    for name in ("absolute", "relative"):
        value = tolerance.get(name)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0 <= value <= 0.01
        ):
            raise ValueError("numeric tolerance policy is invalid")

    reference_rows = reference["curated_golden_set"]
    expected_ids = [row["id"] for row in reference_rows]
    if [case.get("id") for case in cases] != expected_ids:
        raise ValueError("numeric contract case order or coverage is invalid")
    coverage = contract.get("coverage")
    if not isinstance(coverage, dict) or set(coverage) != set(expected_ids):
        raise ValueError("numeric contract coverage map is invalid")
    for case, frozen in zip(cases, reference_rows):
        sections = case.get("sections")
        omissions = case.get("nonnumeric_omissions")
        if (
            not isinstance(sections, dict)
            or not sections
            or len(sections) > 8
            or not isinstance(omissions, list)
            or not omissions
            or len(omissions) > 8
        ):
            raise ValueError("numeric case sections or omissions are malformed")
        derived_coverage = {}
        for section, metrics in sections.items():
            if (
                not isinstance(section, str)
                or not section
                or section not in frozen["texts"]
                or not isinstance(metrics, dict)
                or not metrics
                or len(metrics) > 256
            ):
                raise ValueError("numeric section coverage is invalid")
            metric_names = []
            for metric, value in metrics.items():
                if (
                    not isinstance(metric, str)
                    or not metric
                    or len(metric) > 128
                    or any(
                        character not in "abcdefghijklmnopqrstuvwxyz0123456789_."
                        for character in metric
                    )
                    or isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or abs(value) > 1_000_000
                ):
                    raise ValueError("numeric metric contract is invalid")
                metric_names.append(metric)
            derived_coverage[section] = sorted(metric_names)
        if coverage[case["id"]] != derived_coverage:
            raise ValueError("numeric case-section-metric coverage drifted")
        omitted_sections = set()
        for omission in omissions:
            if (
                not isinstance(omission, dict)
                or set(omission) != {"reason", "section", "target"}
                or omission.get("section") not in frozen["texts"]
                or not isinstance(omission.get("target"), str)
                or not omission["target"]
                or not isinstance(omission.get("reason"), str)
                or not 10 <= len(omission["reason"]) <= 300
            ):
                raise ValueError("nonnumeric omission is not explicit or justified")
            if omission["target"] == "entire_section":
                omitted_sections.add(omission["section"])
        if set(frozen["texts"]) != set(sections) | omitted_sections:
            raise ValueError("numeric contract does not account for every text section")
    return contract


def _reference_with_numeric_contract(
    reference: FrozenGoldenReference, contract: NumericContract
) -> FrozenGoldenReference:
    expected = copy.deepcopy(reference)
    by_id = {case["id"]: case for case in contract["cases"]}
    for row in expected["curated_golden_set"]:
        row["outputs"] = cast(JsonObject, copy.deepcopy(by_id[row["id"]]["sections"]))
        row["numeric_tolerance_policy"] = copy.deepcopy(contract["tolerance_policy"])
    return expected


def _validate_rpy2_identities(root: Path) -> dict[str, str]:
    outer = _load_manifest(root / OUTER_MANIFEST_RELATIVE_PATH)
    committed = outer.get("runtime_identities", {})
    expected = {
        distribution: committed.get(distribution)
        for distribution in REQUIRED_RPY2_IDENTITIES
    }
    if expected != REQUIRED_RPY2_IDENTITIES:
        raise ValueError("committed rpy2 identity contract is missing or unexpected")
    actual = {}
    for distribution, required in REQUIRED_RPY2_IDENTITIES.items():
        try:
            observed = metadata.version(distribution)
        except metadata.PackageNotFoundError as exc:
            raise ValueError(
                "required distribution is missing: %s" % distribution
            ) from exc
        if observed != required:
            raise ValueError(
                "%s identity mismatch: expected %s, observed %s"
                % (distribution, required, observed)
            )
        actual[distribution] = observed
    return actual


def _compare_plot_descriptors(
    contract: PlotDescriptorContract, current: dict[str, Any]
) -> list[dict[str, Any]]:
    rows = []
    current_by_id = {row["id"]: row for row in current["curated_golden_set"]}
    for expected in contract["rows"]:
        case_id = expected["id"]
        actual_descriptors = current_by_id.get(case_id, {}).get("plot_descriptors", [])
        actual_by_label = {
            descriptor.get("artifact_label"): descriptor
            for descriptor in actual_descriptors
            if isinstance(descriptor, dict)
        }
        expected_label = expected["artifact_label"]
        actual = actual_by_label.get(expected_label)
        passed = actual is not None
        detail = "Plot descriptor matched the committed oracle-bound contract."
        if actual is None:
            detail = "Required plot descriptor is missing."
        else:
            display = actual.get("display", {})
            projected_display = {
                "content_required": bool(display.get("sha256")),
                "identity": display.get("identity"),
                "name": display.get("name"),
                "type": display.get("type"),
            }
            sha256 = display.get("sha256")
            passed = (
                projected_display == expected["display"]
                and actual.get("capability") == expected["capability"]
                and isinstance(sha256, str)
                and len(sha256) == 64
                and all(character in "0123456789abcdef" for character in sha256)
            )
            if not passed:
                detail = "Display identity/content or plot capability metadata drifted."
        if len(actual_descriptors) != len(actual_by_label) or set(actual_by_label) - {
            expected_label
        }:
            passed = False
            detail = "Unexpected plot descriptors were produced."
        rows.append(
            {
                "classification": "pass" if passed else "text_artifact_drift",
                "dataset": current_by_id.get(case_id, {}).get("dataset"),
                "detail": detail,
                "id": case_id,
                "method": current_by_id.get(case_id, {}).get("method"),
                "metric": current_by_id.get(case_id, {}).get("metric"),
            }
        )
    return rows


def _validate_current_rpy2_identities(
    current: dict[str, Any], expected: dict[str, str]
) -> None:
    for case in current.get("curated_golden_set", []):
        case_id = case.get("id", "<unknown>")
        for field in ("tool_versions", "package_versions"):
            identities = case.get(field)
            if not isinstance(identities, dict):
                raise ValueError("%s is missing %s" % (case_id, field))
            observed = {
                distribution: identities.get(distribution) for distribution in expected
            }
            if observed != expected:
                raise ValueError(
                    "%s %s rpy2 identities do not match the locked runtime"
                    % (case_id, field)
                )


def _validate_case_contract(
    reference: FrozenGoldenReference, current: dict[str, Any], root: Path
) -> None:
    committed = _load_capture_manifest(
        root / "tests/analysis_regression/baseline/capture-manifest.json"
    )
    expected_ids = committed["curated_golden_set"]
    reference_ids = [row["id"] for row in reference["curated_golden_set"]]
    current_ids = [row["id"] for row in current["curated_golden_set"]]
    if (
        len(expected_ids) != 11
        or reference_ids != expected_ids
        or current_ids != expected_ids
    ):
        raise ValueError(
            "curated Golden coverage must contain the same ordered 11 cases in "
            "the committed contract, frozen baseline, and current capture"
        )


def _numeric_metric_count(contract: NumericContract) -> int:
    count = 0
    for case in contract["cases"]:
        sections = case.get("sections")
        if not isinstance(sections, dict):
            continue
        count += sum(
            len(metrics) for metrics in sections.values() if isinstance(metrics, dict)
        )
    return count


def verify(root: Path, output_root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    archive_path, reference = _load_frozen_reference(root)
    plot_contract = _load_plot_descriptor_contract(root, archive_path, reference)
    numeric_contract = _load_numeric_contract(root, archive_path, reference)
    comparison_reference = _reference_with_numeric_contract(reference, numeric_contract)
    rpy2_identities = _validate_rpy2_identities(root)
    output_root = _prepare_output_root(root, output_root)
    current = golden_analysis.capture_comprehensive_golden_baseline(
        output_dir=str(output_root), capture_mode="local-debug", root_dir=str(root)
    )
    _validate_current_rpy2_identities(current, rpy2_identities)
    _validate_case_contract(reference, current, root)
    comparison = compare_golden_baseline(
        comparison_reference,
        current,
        exceptions=_load_exception_manifest(
            root / "tests/analysis_regression/baseline/exceptions.json"
        ).get("exceptions", []),
        manifest=_load_capture_manifest(
            root / "tests/analysis_regression/baseline/capture-manifest.json"
        ),
    )
    comparison["rows"].extend(_compare_plot_descriptors(plot_contract, current))
    comparison["passed"] = all(
        row["classification"] in {"pass", "accepted_exception"}
        for row in comparison["rows"]
    )
    report = {
        "baseline": str(archive_path.relative_to(root)).replace("\\", "/"),
        "case_count": len(current["curated_golden_set"]),
        "comparison_count": len(comparison["rows"]),
        "capture_passed": current.get("passed") is True,
        "comparison": comparison,
        "numeric_contract": {
            "path": NUMERIC_CONTRACT_RELATIVE_PATH,
            "sha256": _sha256(root / NUMERIC_CONTRACT_RELATIVE_PATH),
            "metric_count": _numeric_metric_count(numeric_contract),
        },
        "rpy2_identities": rpy2_identities,
        "passed": current.get("passed") is True and comparison["passed"] is True,
    }
    report_path = output_root / "compatibility-report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("build/qt6-verification/golden-compatibility-current"),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output_root = args.output_root
    try:
        report = verify(root, output_root)
    except Exception as exc:
        print("Golden compatibility verification failed: %s" % exc, file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
