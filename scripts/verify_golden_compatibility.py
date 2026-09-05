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
from typing import TypeAlias, TypedDict, cast
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
TextSections: TypeAlias = dict[str, str]
NumericSections: TypeAlias = dict[str, JsonObject]


class GoldenArtifact(TypedDict):
    bundle_path: str
    path: str
    sha256: str
    label: str


class GoldenCase(TypedDict, total=False):
    id: str
    status: str
    texts: TextSections
    outputs: NumericSections
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
    cases: list["NumericCase"]
    tolerance_policy: JsonObject
    coverage: dict[str, JsonObject]


class NumericCase(TypedDict):
    id: str
    sections: NumericSections
    nonnumeric_omissions: list[JsonObject]


class CaptureManifest(TypedDict, total=False):
    curated_golden_set: list[str]


class ExceptionManifest(TypedDict, total=False):
    exceptions: list[JsonObject]


class GoldenCaptureBase(TypedDict):
    curated_golden_set: list[JsonObject]


class GoldenCapture(GoldenCaptureBase):
    passed: bool


class ComparisonReport(TypedDict):
    rows: list[JsonObject]
    passed: bool


class CompatibilityReport(TypedDict):
    baseline: str
    case_count: int
    comparison_count: int
    capture_passed: bool
    comparison: ComparisonReport
    numeric_contract: JsonObject
    rpy2_identities: dict[str, str]
    passed: bool


def _load_json(path: Path) -> JsonValue:
    return _narrow_json(json.loads(path.read_text(encoding="utf-8")))


def _parse_json_bytes(payload: bytes) -> JsonValue:
    return _narrow_json(json.loads(payload.decode("utf-8")))


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
    record = _json_object(_load_json(path), "JSON manifest must contain an object")
    result: RepositoryManifest = {}
    _load_manifest_schema(record, result)
    _load_manifest_entries(record, result)
    _load_manifest_identities(record, result)
    return result


def _load_manifest_schema(record: JsonObject, result: RepositoryManifest) -> None:
    schema_version = record.get("schema_version")
    if schema_version is None:
        return
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        raise ValueError("JSON manifest schema version must be an integer")
    result["schema_version"] = schema_version


def _load_manifest_entries(record: JsonObject, result: RepositoryManifest) -> None:
    for field in (
        "observed_golden_analysis_bundle",
        "golden_plot_descriptor_contract",
        "golden_numeric_contract",
    ):
        value = record.get(field)
        if value is not None:
            result[field] = _manifest_entry(value)


def _load_manifest_identities(record: JsonObject, result: RepositoryManifest) -> None:
    identities = record.get("runtime_identities")
    if identities is None:
        return
    identity_record = _json_object(identities, "runtime identities must contain an object")
    if not all(isinstance(identity, str) for identity in identity_record.values()):
        raise ValueError("runtime identities must contain only strings")
    result["runtime_identities"] = {
        name: identity for name, identity in identity_record.items() if isinstance(identity, str)
    }


def _load_plot_contract(path: Path) -> PlotDescriptorContract:
    record = _json_object(_load_json(path), "plot descriptor contract must contain an object")
    return {
        "rows": _json_object_list(record.get("rows"), "plot descriptor contract rows must contain objects"),
        "schema_version": _required_int(record, "schema_version", "plot descriptor contract has an invalid field"),
        "contract": _required_string(record, "contract", "plot descriptor contract has an invalid field"),
        "oracle_sha256": _required_string(record, "oracle_sha256", "plot descriptor contract has an invalid field"),
    }


def _load_numeric_contract_record(path: Path) -> NumericContract:
    record = _json_object(_load_json(path), "numeric contract must contain an object")
    cases = record.get("cases")
    tolerance = record.get("tolerance_policy")
    coverage = record.get("coverage")
    if not isinstance(cases, list) or not isinstance(tolerance, dict) or not isinstance(coverage, dict):
        raise ValueError("numeric contract has invalid record shapes")
    return {
        "schema_version": _required_int(record, "schema_version", "numeric contract has invalid identity fields"),
        "contract": _required_string(record, "contract", "numeric contract has invalid identity fields"),
        "oracle_sha256": _required_string(record, "oracle_sha256", "numeric contract has invalid identity fields"),
        "cases": [_numeric_case(case) for case in cases],
        "tolerance_policy": tolerance,
        "coverage": _json_object_map(coverage, "numeric contract coverage must contain objects"),
    }


def _required_int(record: JsonObject, name: str, message: str) -> int:
    value = record.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(message)
    return value


def _required_string(record: JsonObject, name: str, message: str) -> str:
    value = record.get(name)
    if not isinstance(value, str):
        raise ValueError(message)
    return value


def _json_object_list(value: JsonValue | None, message: str) -> list[JsonObject]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(message)
    return value


def _json_object_map(value: JsonValue, message: str) -> dict[str, JsonObject]:
    if not isinstance(value, dict) or not all(isinstance(item, dict) for item in value.values()):
        raise ValueError(message)
    return value


def _load_capture_manifest(path: Path) -> CaptureManifest:
    record = _json_object(_load_json(path), "capture manifest must contain an object")
    cases = record.get("curated_golden_set")
    if not isinstance(cases, list) or not all(isinstance(case, str) for case in cases):
        raise ValueError("capture manifest cases must contain strings")
    return {"curated_golden_set": cases}


def _numeric_case(value: JsonValue) -> NumericCase:
    record = _json_object(value, "numeric contract case must contain an object")
    case_id = record.get("id")
    omissions = record.get("nonnumeric_omissions")
    if not isinstance(case_id, str) or not isinstance(omissions, list):
        raise ValueError("numeric contract case has invalid fields")
    omission_records: list[JsonObject] = []
    for omission in omissions:
        if not isinstance(omission, dict):
            raise ValueError("numeric contract omissions must contain objects")
        omission_records.append(omission)
    return {
        "id": case_id,
        "sections": _numeric_sections(record.get("sections")),
        "nonnumeric_omissions": omission_records,
    }


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


def _validate_internal_manifest(reference: JsonValue) -> FrozenGoldenReference:
    record = _json_object(reference, "frozen internal manifest has the wrong schema")
    if record.get("baseline") != "comprehensive-golden":
        raise ValueError("frozen internal manifest has the wrong schema")
    rows = record.get("curated_golden_set")
    if not isinstance(rows, list) or len(rows) != 11:
        raise ValueError("frozen internal manifest must contain exactly 11 cases")
    typed_rows = [_validate_internal_case(raw_row) for raw_row in rows]
    ids = [row["id"] for row in typed_rows]
    if len(set(ids)) != len(ids):
        raise ValueError("frozen case ids are duplicated")
    return {"baseline": "comprehensive-golden", "curated_golden_set": typed_rows}


def _validate_internal_case(value: JsonValue) -> GoldenCase:
    row = _json_object(value, "frozen case is malformed or unsuccessful")
    if row.get("status") != "success":
        raise ValueError("frozen case is malformed or unsuccessful")
    row_id = row.get("id")
    if not isinstance(row_id, str) or not row_id or not _safe_case_id(row_id):
        raise ValueError("frozen case id is unsafe")
    texts = _text_sections(row.get("texts"))
    outputs = _numeric_sections(row.get("outputs"))
    artifacts = _validate_golden_artifacts(row.get("artifacts"))
    if len(texts) > 16:
        raise ValueError("frozen text contract is malformed")
    if len(outputs) > 16:
        raise ValueError("frozen numeric contract is malformed")
    if len(artifacts) > 4:
        raise ValueError("frozen artifact contract is malformed")
    return cast(
        GoldenCase,
        {**row, "texts": texts, "outputs": outputs, "artifacts": artifacts},
    )


def _safe_case_id(value: str) -> bool:
    return all(character in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in value)


def _text_sections(value: JsonValue | None) -> TextSections:
    if not isinstance(value, dict) or not all(
        isinstance(name, str) and isinstance(text, str)
        for name, text in value.items()
    ):
        raise ValueError("frozen text contract is malformed")
    return value


def _numeric_sections(value: JsonValue | None) -> NumericSections:
    if not isinstance(value, dict):
        raise ValueError("frozen numeric contract is malformed")
    sections: NumericSections = {}
    for name, metrics in value.items():
        if not isinstance(name, str) or not isinstance(metrics, dict):
            raise ValueError("frozen numeric contract is malformed")
        sections[name] = metrics
    return sections


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
        names = _validated_zip_names(archive.infolist())
        reference = _validate_zip_manifest(archive, names)
        expected_members = _validate_zip_cases(archive, names, reference)
        if set(names) != expected_members:
            raise ValueError("frozen ZIP contains missing or unexpected members")
        return reference


def _validated_zip_names(infos: list[zipfile.ZipInfo]) -> list[str]:
    if not infos or len(infos) > MAX_MEMBER_COUNT:
        raise ValueError("frozen ZIP member count is outside the allowed bounds")
    names = []
    total = 0
    for info in infos:
        _validate_zip_info(info)
        names.append(info.filename)
        total += info.file_size
    if total > MAX_TOTAL_UNCOMPRESSED_BYTES:
        raise ValueError("frozen ZIP exceeds the uncompressed size bound")
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError("frozen ZIP contains duplicate member names")
    return names


def _validate_zip_info(info: zipfile.ZipInfo) -> None:
    _validate_member_name(info.filename)
    if info.is_dir() or info.flag_bits & 0x1:
        raise ValueError("frozen ZIP contains a directory or encrypted member")
    if info.file_size > MAX_MEMBER_BYTES:
        raise ValueError("frozen ZIP member exceeds the size bound")


def _validate_zip_manifest(
    archive: zipfile.ZipFile, names: list[str]
) -> FrozenGoldenReference:
    if "manifest.json" not in names:
        raise ValueError("frozen ZIP has no internal manifest")
    return _validate_internal_manifest(_parse_json_bytes(archive.read("manifest.json")))


def _validate_zip_cases(
    archive: zipfile.ZipFile, names: list[str], reference: FrozenGoldenReference
) -> set[str]:
    expected_members = {"manifest.json"}
    for row in reference["curated_golden_set"]:
        _validate_zip_capture(archive, names, row)
        expected_members.add("captures/%s.json" % row["id"])
        for artifact in row["artifacts"]:
            expected_members.add(_validate_zip_artifact(archive, names, row, artifact))
    return expected_members


def _validate_zip_capture(
    archive: zipfile.ZipFile, names: list[str], row: GoldenCase
) -> None:
    member = "captures/%s.json" % row["id"]
    if member not in names:
        raise ValueError("frozen case capture is missing")
    if _parse_json_bytes(archive.read(member)) != row:
        raise ValueError("frozen internal manifest and case capture disagree")


def _validate_zip_artifact(
    archive: zipfile.ZipFile,
    names: list[str],
    row: GoldenCase,
    artifact: GoldenArtifact,
) -> str:
    basename = Path(artifact["bundle_path"] or artifact["path"]).name
    member = "artifacts/%s/%s" % (row["id"], basename)
    if member not in names:
        raise ValueError("frozen artifact is missing: %s" % member)
    observed = hashlib.sha256(archive.read(member)).hexdigest()
    if observed != artifact["sha256"]:
        raise ValueError("frozen artifact hash mismatch: %s" % member)
    return member


def _load_frozen_reference(root: Path) -> tuple[Path, FrozenGoldenReference]:
    outer_path = (root / OUTER_MANIFEST_RELATIVE_PATH).resolve(strict=True)
    outer = _load_manifest(outer_path)
    if outer.get("schema_version") != 1:
        raise ValueError("outer Golden manifest contract is malformed")
    entry = _required_manifest_entry(outer, "observed_golden_analysis_bundle")
    _validate_archive_entry(entry)
    archive_path = _exact_committed_path(root, entry["path"], "frozen archive")
    if archive_path.stat().st_size != entry["size"]:
        raise ValueError("frozen archive size does not match the outer manifest")
    if _sha256(archive_path) != entry["sha256"]:
        raise ValueError("frozen archive hash does not match the outer manifest")
    return archive_path, _read_validated_zip(archive_path)


def _required_manifest_entry(manifest: RepositoryManifest, name: str) -> ManifestEntry:
    entry = manifest.get(name)
    if not isinstance(entry, dict):
        raise ValueError("outer Golden manifest contract is malformed")
    return entry


def _validate_archive_entry(entry: ManifestEntry) -> None:
    if (
        entry.get("path") != str(ARCHIVE_RELATIVE_PATH)
        or not 0 < entry["size"] <= MAX_ARCHIVE_BYTES
        or len(entry["sha256"]) != 64
    ):
        raise ValueError("outer Golden manifest contract is malformed")


def _exact_committed_path(root: Path, relative: str, label: str) -> Path:
    path = (root / relative).resolve(strict=True)
    if path != (root / relative).absolute() or not path.is_file():
        raise ValueError("%s is not the exact committed regular file" % label)
    _assert_plain_path(path)
    return path


def _load_plot_descriptor_contract(
    root: Path, archive_path: Path, reference: FrozenGoldenReference
) -> PlotDescriptorContract:
    outer = _load_manifest(root / OUTER_MANIFEST_RELATIVE_PATH)
    expected_relative = "tests/analysis_regression/baseline/plot-descriptors.json"
    entry = _required_manifest_entry(outer, "golden_plot_descriptor_contract")
    _validate_plot_entry(entry, expected_relative)
    path = _exact_committed_path(root, expected_relative, "plot descriptor contract")
    if path.stat().st_size != entry["size"] or _sha256(path) != entry["sha256"]:
        raise ValueError("plot descriptor contract failed size or hash verification")
    contract = _load_plot_contract(path)
    rows = contract["rows"]
    if contract["schema_version"] != 1 or contract["contract"] != "golden-plot-descriptors":
        raise ValueError("plot descriptor contract schema or oracle binding is invalid")
    if contract["oracle_sha256"] != _sha256(archive_path) or len(rows) != 11:
        raise ValueError("plot descriptor contract schema or oracle binding is invalid")
    _validate_plot_descriptor_rows(rows, reference)
    return contract


def _validate_plot_entry(entry: ManifestEntry, expected_relative: str) -> None:
    if (
        entry["path"] != expected_relative
        or not 0 < entry["size"] < 65536
        or len(entry["sha256"]) != 64
    ):
        raise ValueError("plot descriptor outer contract is malformed")


def _validate_plot_descriptor_rows(
    rows: list[JsonObject], reference: FrozenGoldenReference
) -> None:
    reference_by_id = {row["id"]: row for row in reference["curated_golden_set"]}
    seen = set()
    for row in rows:
        _validate_plot_descriptor_row(row, reference_by_id, seen)
    if seen != set(reference_by_id):
        raise ValueError("plot descriptor contract is missing cases")


def _validate_plot_descriptor_row(
    row: JsonObject, reference_by_id: dict[str, GoldenCase], seen: set[str]
) -> None:
    row_id = row.get("id")
    if not isinstance(row_id, str) or row_id in seen or row_id not in reference_by_id:
        raise ValueError("plot descriptor contract case set is invalid")
    seen.add(row_id)
    artifacts = {artifact["label"]: artifact for artifact in reference_by_id[row_id]["artifacts"]}
    label = row.get("artifact_label")
    if not isinstance(label, str) or label not in artifacts:
        raise ValueError("plot descriptor is not tied to its frozen artifact oracle")
    if row.get("artifact_oracle_sha256") != artifacts[label]["sha256"]:
        raise ValueError("plot descriptor is not tied to its frozen artifact oracle")


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _copy_json_object(value: JsonValue) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return copy.deepcopy(value)


def _copy_numeric_sections(value: JsonValue) -> NumericSections:
    return copy.deepcopy(_numeric_sections(value))


def _load_numeric_contract(
    root: Path, archive_path: Path, reference: FrozenGoldenReference
) -> NumericContract:
    outer = _load_manifest(root / OUTER_MANIFEST_RELATIVE_PATH)
    entry = _required_manifest_entry(outer, "golden_numeric_contract")
    _validate_numeric_entry(entry)
    path = _exact_committed_path(root, NUMERIC_CONTRACT_RELATIVE_PATH, "numeric contract")
    raw = path.read_bytes()
    if len(raw) != entry["size"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError("numeric contract failed size or hash verification")
    try:
        contract = _load_numeric_contract_record(path)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("numeric contract is not canonical UTF-8 JSON") from exc
    if raw != _canonical_json_bytes(contract):
        raise ValueError("numeric contract is not canonically serialized")

    _validate_numeric_identity(contract, archive_path)
    _validate_numeric_tolerance(contract["tolerance_policy"])
    _validate_numeric_cases(contract, reference)
    return contract


def _validate_numeric_entry(entry: ManifestEntry) -> None:
    if (
        entry["path"] != NUMERIC_CONTRACT_RELATIVE_PATH
        or not 0 < entry["size"] <= MAX_NUMERIC_CONTRACT_BYTES
        or len(entry["sha256"]) != 64
    ):
        raise ValueError("numeric outer contract is malformed")


def _validate_numeric_identity(contract: NumericContract, archive_path: Path) -> None:
    if (
        contract["schema_version"] != 1
        or contract["contract"] != "golden-numeric-results"
        or contract["oracle_sha256"] != _sha256(archive_path)
        or len(contract["cases"]) != 11
    ):
        raise ValueError("numeric contract schema or oracle binding is invalid")


def _validate_numeric_tolerance(tolerance: JsonObject) -> None:
    if set(tolerance) != {"absolute", "relative", "rule"} or tolerance.get(
        "rule"
    ) != "max(absolute, relative * abs(expected))":
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


def _validate_numeric_cases(
    contract: NumericContract, reference: FrozenGoldenReference
) -> None:
    reference_rows = reference["curated_golden_set"]
    expected_ids = [row["id"] for row in reference_rows]
    cases = contract["cases"]
    if [case["id"] for case in cases] != expected_ids:
        raise ValueError("numeric contract case order or coverage is invalid")
    coverage = contract.get("coverage", {})
    if set(coverage) != set(expected_ids):
        raise ValueError("numeric contract coverage map is invalid")
    for case, frozen in zip(cases, reference_rows):
        _validate_numeric_case(case, frozen, coverage[case["id"]])


def _validate_numeric_case(
    case: NumericCase, frozen: GoldenCase, expected_coverage: JsonObject
) -> None:
    sections = case["sections"]
    omissions = case["nonnumeric_omissions"]
    if not sections or len(sections) > 8 or not omissions or len(omissions) > 8:
        raise ValueError("numeric case sections or omissions are malformed")
    derived_coverage = _numeric_case_coverage(sections, frozen)
    if expected_coverage != derived_coverage:
        raise ValueError("numeric case-section-metric coverage drifted")
    omitted_sections = _numeric_omitted_sections(omissions, frozen)
    if set(frozen["texts"]) != set(sections) | omitted_sections:
        raise ValueError("numeric contract does not account for every text section")


def _numeric_case_coverage(
    sections: NumericSections, frozen: GoldenCase
) -> JsonObject:
    coverage: JsonObject = {}
    for section, metrics in sections.items():
        _validate_numeric_section(section, metrics, frozen)
        coverage[section] = sorted(metrics)
    return coverage


def _validate_numeric_section(
    section: str, metrics: JsonObject, frozen: GoldenCase
) -> None:
    if not section or section not in frozen["texts"] or not metrics or len(metrics) > 256:
        raise ValueError("numeric section coverage is invalid")
    for metric, value in metrics.items():
        if not _valid_numeric_metric(metric, value):
            raise ValueError("numeric metric contract is invalid")


def _valid_numeric_metric(metric: str, value: JsonValue) -> bool:
    return (
        bool(metric)
        and len(metric) <= 128
        and all(character in "abcdefghijklmnopqrstuvwxyz0123456789_." for character in metric)
        and not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and abs(value) <= 1_000_000
    )


def _numeric_omitted_sections(
    omissions: list[JsonObject], frozen: GoldenCase
) -> set[str]:
    omitted_sections: set[str] = set()
    for omission in omissions:
        _validate_numeric_omission(omission, frozen)
        section = omission["section"]
        if omission["target"] == "entire_section" and isinstance(section, str):
            omitted_sections.add(section)
    return omitted_sections


def _validate_numeric_omission(omission: JsonObject, frozen: GoldenCase) -> None:
    section = omission.get("section")
    target = omission.get("target")
    reason = omission.get("reason")
    if (
        set(omission) != {"reason", "section", "target"}
        or section not in frozen["texts"]
        or not isinstance(section, str)
        or not isinstance(target, str)
        or not target
        or not isinstance(reason, str)
        or not 10 <= len(reason) <= 300
    ):
        raise ValueError("nonnumeric omission is not explicit or justified")


def _reference_with_numeric_contract(
    reference: FrozenGoldenReference, contract: NumericContract
) -> FrozenGoldenReference:
    expected = copy.deepcopy(reference)
    by_id = {case["id"]: case for case in contract["cases"]}
    for row in expected["curated_golden_set"]:
        row["outputs"] = _copy_numeric_sections(by_id[row["id"]]["sections"])
        row["numeric_tolerance_policy"] = _copy_json_object(
            contract["tolerance_policy"]
        )
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
    contract: PlotDescriptorContract, current: GoldenCaptureBase
) -> list[JsonObject]:
    current_by_id = _current_cases_by_id(current)
    return [_compare_plot_row(expected, current_by_id) for expected in contract["rows"]]


def _current_cases_by_id(current: GoldenCaptureBase) -> dict[str, JsonObject]:
    result: dict[str, JsonObject] = {}
    for row in current["curated_golden_set"]:
        case_id = row.get("id")
        if isinstance(case_id, str):
            result[case_id] = row
    return result


def _compare_plot_row(
    expected: JsonObject, current_by_id: dict[str, JsonObject]
) -> JsonObject:
    case_id = expected.get("id")
    if not isinstance(case_id, str):
        raise ValueError("plot descriptor contract case id is malformed")
    current_case = current_by_id.get(case_id, {})
    expected_label = expected.get("artifact_label")
    if not isinstance(expected_label, str):
        raise ValueError("plot descriptor contract artifact label is malformed")
    actual_descriptors = _plot_descriptors(current_case)
    actual_by_label = _descriptors_by_label(actual_descriptors)
    passed, detail = _plot_observation(expected, expected_label, actual_by_label)
    if len(actual_descriptors) != len(actual_by_label) or set(actual_by_label) - {expected_label}:
        passed, detail = False, "Unexpected plot descriptors were produced."
    return {
        "classification": "pass" if passed else "text_artifact_drift",
        "dataset": current_case.get("dataset"),
        "detail": detail,
        "id": case_id,
        "method": current_case.get("method"),
        "metric": current_case.get("metric"),
    }


def _plot_descriptors(current_case: JsonObject) -> list[JsonObject]:
    value = current_case.get("plot_descriptors", [])
    return value if isinstance(value, list) and all(isinstance(item, dict) for item in value) else []


def _descriptors_by_label(descriptors: list[JsonObject]) -> dict[str, JsonObject]:
    return {
        label: descriptor
        for descriptor in descriptors
        if isinstance((label := descriptor.get("artifact_label")), str)
    }


def _plot_observation(
    expected: JsonObject,
    expected_label: str,
    actual_by_label: dict[str, JsonObject],
) -> tuple[bool, str]:
    actual = actual_by_label.get(expected_label)
    if actual is None:
        return False, "Required plot descriptor is missing."
    passed = _plot_display_matches(expected, actual)
    detail = "Plot descriptor matched the committed oracle-bound contract."
    if not passed:
        detail = "Display identity/content or plot capability metadata drifted."
    return passed, detail


def _plot_display_matches(expected: JsonObject, actual: JsonObject) -> bool:
    display = actual.get("display")
    if not isinstance(display, dict):
        display = {}
    projected_display = {
        "content_required": bool(display.get("sha256")),
        "identity": display.get("identity"),
        "name": display.get("name"),
        "type": display.get("type"),
    }
    return (
        projected_display == expected.get("display")
        and actual.get("capability") == expected.get("capability")
        and _valid_plot_hash(display.get("sha256"))
    )


def _valid_plot_hash(value: JsonValue | None) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_current_rpy2_identities(
    current: GoldenCaptureBase, expected: dict[str, str]
) -> None:
    for case in current.get("curated_golden_set", []):
        case_id = case.get("id", "<unknown>")
        for field in ("tool_versions", "package_versions"):
            identities = case.get(field)
            if not isinstance(identities, dict):
                raise ValueError("%s is missing %s" % (case_id, field))
            observed = {}
            for distribution in expected:
                value = identities.get(distribution)
                if not isinstance(value, str):
                    raise ValueError(
                        "%s %s rpy2 identities contain a non-string value"
                        % (case_id, field)
                    )
                observed[distribution] = value
            if observed != expected:
                raise ValueError(
                    "%s %s rpy2 identities do not match the locked runtime"
                    % (case_id, field)
                )


def _validate_case_contract(
    reference: FrozenGoldenReference, current: GoldenCaptureBase, root: Path
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


def _validate_capture(value: object) -> GoldenCapture:
    record = _json_object(_narrow_json(value), "Golden capture must contain an object")
    cases = record.get("curated_golden_set")
    passed = record.get("passed")
    if not isinstance(cases, list) or not isinstance(passed, bool):
        raise ValueError("Golden capture has an invalid shape")
    case_records: list[JsonObject] = []
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            raise ValueError("Golden capture cases must contain string ids")
        case_records.append(case)
    return {"curated_golden_set": case_records, "passed": passed}


def _validate_comparison(value: object) -> ComparisonReport:
    record = _json_object(_narrow_json(value), "Golden comparison must contain an object")
    rows = record.get("rows")
    passed = record.get("passed")
    if not isinstance(rows, list) or not isinstance(passed, bool):
        raise ValueError("Golden comparison has an invalid shape")
    row_records: list[JsonObject] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("classification"), str):
            raise ValueError("Golden comparison rows must contain classifications")
        row_records.append(row)
    return {"rows": row_records, "passed": passed}


def verify(root: Path, output_root: Path) -> CompatibilityReport:
    root = root.resolve(strict=True)
    archive_path, reference = _load_frozen_reference(root)
    plot_contract = _load_plot_descriptor_contract(root, archive_path, reference)
    numeric_contract = _load_numeric_contract(root, archive_path, reference)
    comparison_reference = _reference_with_numeric_contract(reference, numeric_contract)
    rpy2_identities = _validate_rpy2_identities(root)
    output_root = _prepare_output_root(root, output_root)
    current = _validate_capture(golden_analysis.capture_comprehensive_golden_baseline(
        output_dir=str(output_root), capture_mode="local-debug", root_dir=str(root)
    ))
    _validate_current_rpy2_identities(current, rpy2_identities)
    _validate_case_contract(reference, current, root)
    comparison = _validate_comparison(compare_golden_baseline(
        comparison_reference,
        current,
        exceptions=_load_exception_manifest(
            root / "tests/analysis_regression/baseline/exceptions.json"
        ).get("exceptions", []),
        manifest=_load_capture_manifest(
            root / "tests/analysis_regression/baseline/capture-manifest.json"
        ),
    ))
    comparison["rows"].extend(_compare_plot_descriptors(plot_contract, current))
    comparison["passed"] = all(
        row["classification"] in {"pass", "accepted_exception"}
        for row in comparison["rows"]
    )
    report: CompatibilityReport = {
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
