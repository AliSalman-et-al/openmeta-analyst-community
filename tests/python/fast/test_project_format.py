from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
import stat
import warnings
import zipfile

import pytest

import rc_metastudio.project_format as project_format
from rc_metastudio.project_format import (
    AnalysisDataset,
    CURRENT_FORMAT_VERSION,
    ProjectArchiveLimits,
    ProjectDurabilityError,
    ProjectFormatError,
    load_project,
    migrate_to_latest,
    save_project,
    reconstruct_analysis_dataset,
    JsonObject,
    JsonValue,
)


ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT_DIR = ROOT / "tests/python/fixtures/project_snapshots"
SAMPLE_DIR = ROOT / "sample_projects"


def _minimal_project() -> JsonObject:
    return {
        "schema_version": CURRENT_FORMAT_VERSION,
        "dataset": {
            "analysis_family": "binary",
            "covariates": [],
            "is_diagnostic": False,
            "notes": "",
            "outcomes": [
                {
                    "data_type": 0,
                    "follow_ups": ["first"],
                    "name": "Mortality",
                    "sub_type": None,
                }
            ],
            "studies": [],
            "summary": None,
            "title": "Example",
        },
    }


def _minimal_state() -> JsonObject:
    return {
        "schema_version": CURRENT_FORMAT_VERSION,
        "active_outcome": None,
        "active_follow_up": None,
        "active_groups": [],
        "active_effect": None,
        "confidence_level": 95.0,
    }


def _group_project(
    family: str, subtype: str | None, raw_values: list[list[JsonValue]]
) -> JsonObject:
    data_type = {"binary": 0, "continuous": 1, "diagnostic": 2}[family]
    return {
        "schema_version": CURRENT_FORMAT_VERSION,
        "dataset": {
            "analysis_family": family,
            "covariates": [],
            "is_diagnostic": family == "diagnostic",
            "notes": "",
            "outcomes": [
                {
                    "data_type": data_type,
                    "follow_ups": ["first"],
                    "name": "Outcome",
                    "sub_type": subtype,
                }
            ],
            "studies": [
                {
                    "analysis_units": [
                        {
                            "entered_effects": {},
                            "follow_up": "first",
                            "groups": [
                                {
                                    "id": index,
                                    "name": f"Tx {index + 1}",
                                    "raw_data": raw,
                                }
                                for index, raw in enumerate(raw_values)
                            ],
                            "outcome": "Outcome",
                        }
                    ],
                    "covariates": {},
                    "id": 0,
                    "include": True,
                    "manually_excluded": False,
                    "name": "Study",
                    "notes": "",
                    "sample_size": None,
                    "year": 2026,
                }
            ],
            "summary": None,
            "title": "Group contract",
        },
    }


def _snapshot_project(name: str) -> JsonObject:
    snapshot = json.loads((SNAPSHOT_DIR / f"{name}.json").read_text("utf-8"))
    return {"schema_version": CURRENT_FORMAT_VERSION, "dataset": snapshot["dataset"]}


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _object(value: JsonValue) -> JsonObject:
    """Narrow a JSON value at a test mutation/read boundary."""

    if not isinstance(value, dict):
        raise AssertionError("expected JSON object")
    return value


def _objects(value: JsonValue) -> list[JsonObject]:
    """Narrow a JSON array whose members are objects."""

    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise AssertionError("expected JSON object array")
    return value


def _first_study(project: JsonObject) -> JsonObject:
    return _objects(_object(project["dataset"])["studies"])[0]


def _write_archive(path: Path, members: list[tuple[str, bytes]]) -> None:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Duplicate name:")
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, payload in members:
                archive.writestr(name, payload)


def _members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _replace_json_member(path: Path, member: str, value: JsonValue) -> None:
    members = _members(path)
    members[member] = _json_bytes(value)
    if member != "manifest.json":
        manifest = json.loads(members["manifest.json"])
        manifest["members"][member] = {
            "sha256": hashlib.sha256(members[member]).hexdigest(),
            "size": len(members[member]),
        }
        members["manifest.json"] = _json_bytes(manifest)
    _write_archive(path, [(name, members[name]) for name in members])


def _replace_raw_member(path: Path, member: str, payload: bytes) -> None:
    members = _members(path)
    members[member] = payload
    manifest = json.loads(members["manifest.json"])
    manifest["members"][member] = {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
    }
    members["manifest.json"] = _json_bytes(manifest)
    _write_archive(path, [(name, members[name]) for name in members])


def _first_populated_raw(project: JsonObject) -> list[JsonValue]:
    dataset = _object(project["dataset"])
    for study in _objects(dataset["studies"]):
        for unit in _objects(study["analysis_units"]):
            for group in _objects(unit["groups"]):
                raw = group["raw_data"]
                if not isinstance(raw, list):
                    raise AssertionError("expected raw-data array")
                if any(value != "" for value in raw):
                    return raw
    raise AssertionError("sample has no populated raw data")


def _patch_first_central_header(path: Path, offset: int, value: int) -> None:
    payload = bytearray(path.read_bytes())
    header = payload.find(b"PK\x01\x02")
    assert header >= 0
    payload[header + offset : header + offset + 2] = value.to_bytes(2, "little")
    path.write_bytes(payload)


def test_project_round_trip_has_schema_validated_integrity_members(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "example.rcms"

    save_project(destination, _minimal_project(), _minimal_state())
    loaded = load_project(destination)

    assert loaded.format_version == CURRENT_FORMAT_VERSION
    assert loaded.project == _minimal_project()
    assert loaded.state == _minimal_state()
    with zipfile.ZipFile(destination) as archive:
        assert archive.namelist() == ["manifest.json", "project.json", "state.json"]
        manifest = json.loads(archive.read("manifest.json"))
        for member in ("project.json", "state.json"):
            payload = archive.read(member)
            assert manifest["members"][member] == {
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update(unexpected=True), "Additional properties"),
        (lambda value: value.update(schema_version="1"), "schema_version"),
    ],
    ids=["unknown-field", "invalid-type"],
)
def test_project_schema_rejects_unknown_fields_and_invalid_types(
    tmp_path: Path, mutation, message: str
) -> None:
    destination = tmp_path / "invalid.rcms"
    save_project(destination, _minimal_project(), _minimal_state())
    project = _minimal_project()
    mutation(project)
    _replace_json_member(destination, "project.json", project)

    with pytest.raises(ProjectFormatError, match=message):
        load_project(destination)


def test_state_schema_contains_only_explicit_durable_v1_fields(tmp_path: Path) -> None:
    destination = tmp_path / "state.rcms"
    save_project(destination, _minimal_project(), _minimal_state())
    state = _minimal_state()
    state["analysis_selections"] = {"anything": {"nested": True}}
    _replace_json_member(destination, "state.json", state)

    with pytest.raises(ProjectFormatError, match="Additional properties"):
        load_project(destination)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda dataset: dataset["outcomes"].append(dataset["outcomes"][0].copy()),
            "duplicate outcome identifier",
        ),
        (
            lambda dataset: dataset["studies"][0]["analysis_units"][0].update(
                outcome="missing"
            ),
            "undeclared outcome",
        ),
        (
            lambda dataset: dataset["studies"][0]["analysis_units"][1]["groups"][
                0
            ].update(raw_data=[1.0]),
            "raw-data arity",
        ),
        (
            lambda dataset: dataset["studies"][0]["analysis_units"][1][
                "entered_effects"
            ]["OR"].update(
                {
                    "unknown comparison": next(
                        iter(
                            dataset["studies"][0]["analysis_units"][1][
                                "entered_effects"
                            ]["OR"].values()
                        )
                    )
                }
            ),
            "undeclared group comparison",
        ),
    ],
    ids=["duplicate-outcome", "outcome-reference", "raw-arity", "group-reference"],
)
def test_semantic_validation_rejects_invalid_domain_relationships(
    tmp_path: Path, mutation, message: str
) -> None:
    destination = tmp_path / "semantic.rcms"
    project = _snapshot_project("amino.rcms")
    dataset = _object(project["dataset"])
    mutation(dataset)

    with pytest.raises(ProjectFormatError, match=message):
        save_project(destination, project, _minimal_state())


@pytest.mark.parametrize(
    ("family", "subtype", "raw_values"),
    [
        ("binary", "proportions", [[1, 10], [2, 20], [3, 30]]),
        (
            "continuous",
            "means",
            [[10, 1.0, 0.5], [20, 2.0, 0.75], [30, 3.0, 1.0]],
        ),
    ],
    ids=["binary-three-arm", "continuous-three-arm"],
)
def test_pairwise_subtypes_preserve_valid_multi_arm_analysis_units(
    tmp_path: Path,
    family: str,
    subtype: str,
    raw_values: list[list[JsonValue]],
) -> None:
    destination = tmp_path / f"{family}-multi-arm.rcms"
    project = _group_project(family, subtype, raw_values)

    save_project(destination, project, _minimal_state())

    assert load_project(destination).project == project


@pytest.mark.parametrize(
    ("family", "subtype", "raw_values"),
    [
        ("binary", "proportions", [[1, 10]]),
        ("binary", "proportion", [[1, 10], [2, 20]]),
        ("diagnostic", None, [[1, 2, 3, 4], [5, 6, 7, 8]]),
    ],
    ids=["two-arm-needs-two", "one-arm-stays-exact", "diagnostic-stays-exact"],
)
def test_group_subtype_contract_rejects_too_few_or_forbidden_extra_groups(
    tmp_path: Path,
    family: str,
    subtype: str | None,
    raw_values: list[list[JsonValue]],
) -> None:
    project = _group_project(family, subtype, raw_values)

    with pytest.raises(ProjectFormatError, match="group count conflicts with subtype"):
        save_project(tmp_path / "invalid-groups.rcms", project, _minimal_state())


@pytest.mark.parametrize(
    ("field", "value"),
    [("data_type", 99), ("sub_type", "unknown")],
)
def test_schema_rejects_values_outside_the_domain_vocabulary(
    tmp_path: Path, field: str, value: JsonValue
) -> None:
    project = _snapshot_project("amino.rcms")
    dataset = _object(project["dataset"])
    outcome = _objects(dataset["outcomes"])[0]
    outcome[field] = value

    with pytest.raises(ProjectFormatError, match=field):
        save_project(tmp_path / "vocabulary.rcms", project, _minimal_state())


@pytest.mark.parametrize(
    ("sample", "mutation", "message"),
    [
        (
            "amino.rcms",
            lambda dataset: dataset["studies"].append(
                copy.deepcopy(dataset["studies"][0])
            ),
            "duplicate study identifier",
        ),
        (
            "amino.rcms",
            lambda dataset: dataset["studies"][0]["analysis_units"][1]["groups"][
                1
            ].update(id=0),
            "duplicate group identifier",
        ),
        (
            "BCG.rcms",
            lambda dataset: dataset["covariates"].append(
                copy.deepcopy(dataset["covariates"][0])
            ),
            "duplicate covariate identifier",
        ),
        (
            "amino.rcms",
            lambda dataset: dataset["studies"][0]["analysis_units"][1].update(
                follow_up="missing"
            ),
            "undeclared follow-up",
        ),
        (
            "amino.rcms",
            lambda dataset: dataset["studies"][0]["analysis_units"][1][
                "entered_effects"
            ].update(
                MD=dataset["studies"][0]["analysis_units"][1]["entered_effects"]["OR"]
            ),
            "metric conflicts with family",
        ),
        (
            "amino.rcms",
            lambda dataset: dataset["studies"][0]["analysis_units"][1]["groups"][
                0
            ].update(raw_data=[-1.0, 27.0]),
            "count data cannot be negative",
        ),
    ],
    ids=[
        "study-identifier",
        "group-identifier",
        "covariate-identifier",
        "follow-up-reference",
        "cross-family-metric",
        "numeric-domain",
    ],
)
def test_semantic_validation_enforces_domain_identity_family_and_numeric_contracts(
    tmp_path: Path, sample: str, mutation, message: str
) -> None:
    project = _snapshot_project(sample)
    mutation(_object(project["dataset"]))

    with pytest.raises(ProjectFormatError, match=message):
        save_project(tmp_path / "invalid-domain.rcms", project, _minimal_state())


def test_typed_snapshot_relationships_do_not_depend_on_editable_labels() -> None:
    project = _group_project("binary", "proportions", [[1, 10], [2, 20]])
    dataset = _object(project["dataset"])
    outcome = _objects(dataset["outcomes"])[0]
    study = _objects(dataset["studies"])[0]
    unit = _objects(study["analysis_units"])[0]
    groups = _objects(unit["groups"])
    outcome.update(stable_id="outcome-id", follow_up_ids=["follow-up-id"])
    study["stable_id"] = "study-id"
    unit["stable_id"] = "unit-id"
    groups[0]["stable_id"] = "group-a-id"
    groups[1]["stable_id"] = "group-b-id"

    before = reconstruct_analysis_dataset(
        project_format.ProjectDocument(1, project, _minimal_state())
    )
    outcome["name"] = "Renamed outcome"
    outcome["follow_ups"] = ["Renamed follow-up"]
    unit["outcome"] = "Renamed outcome"
    unit["follow_up"] = "Renamed follow-up"
    groups[0]["name"] = "Renamed treatment"
    after = reconstruct_analysis_dataset(
        project_format.ProjectDocument(1, project, _minimal_state())
    )

    assert after.outcomes[0].identity == before.outcomes[0].identity
    assert (
        after.outcomes[0].follow_ups[0].identity
        == before.outcomes[0].follow_ups[0].identity
    )
    assert after.studies[0].identity == before.studies[0].identity
    assert (
        after.studies[0].units[0].outcome == before.studies[0].units[0].outcome
    )
    assert (
        after.studies[0].units[0].follow_up == before.studies[0].units[0].follow_up
    )
    assert (
        after.studies[0].units[0].groups[0].identity
        == before.studies[0].units[0].groups[0].identity
    )


def test_family_raw_counts_and_sample_sizes_reject_fractional_values_on_save_and_load(
    tmp_path: Path,
) -> None:
    for sample in ("amino.rcms", "continuous.rcms", "lymph.rcms"):
        project = _snapshot_project(sample)
        _first_populated_raw(project)[0] = 1.5
        with pytest.raises(ProjectFormatError, match="integer-valued"):
            save_project(tmp_path / f"save-{sample}", project, _minimal_state())

        destination = tmp_path / f"load-{sample}"
        valid_project = _snapshot_project(sample)
        save_project(destination, valid_project, _minimal_state())
        _first_populated_raw(valid_project)[0] = 1.5
        _replace_json_member(destination, "project.json", valid_project)
        with pytest.raises(ProjectFormatError, match="integer-valued"):
            load_project(destination)


def test_family_raw_counts_and_sample_sizes_accept_json_integers_and_integral_floats(
    tmp_path: Path,
) -> None:
    for sample in ("amino.rcms", "continuous.rcms", "lymph.rcms"):
        for value in (6, 6.0):
            project = _snapshot_project(sample)
            _first_populated_raw(project)[0] = value
            destination = tmp_path / f"{sample}-{type(value).__name__}.rcms"
            save_project(destination, project, _minimal_state())
            assert _first_populated_raw(load_project(destination).project)[0] == value


def test_reader_rejects_oversized_overflowing_and_nonfinite_numeric_literals(
    tmp_path: Path,
) -> None:
    source = tmp_path / "numeric-source.rcms"
    save_project(source, _snapshot_project("amino.rcms"), _minimal_state())
    source_project = _members(source)["project.json"]
    assert b'"raw_data":[6.0,27.0]' in source_project
    assert b'"sample_size":null' in source_project

    cases = {
        "oversized-integer": source_project.replace(
            b'"raw_data":[6.0,27.0]',
            b'"raw_data":[' + (b"1" * 4301) + b",27.0]",
            1,
        ),
        "overflowing-integer": source_project.replace(
            b'"raw_data":[6.0,27.0]',
            b'"raw_data":[' + (b"9" * 400) + b",27.0]",
            1,
        ),
        "overflowing-exponent": source_project.replace(
            b'"raw_data":[6.0,27.0]', b'"raw_data":[1e999,27.0]', 1
        ),
        "overflowing-sample-size": source_project.replace(
            b'"sample_size":null', b'"sample_size":1e400', 1
        ),
    }
    for name, payload in cases.items():
        destination = tmp_path / f"{name}.rcms"
        destination.write_bytes(source.read_bytes())
        _replace_raw_member(destination, "project.json", payload)
        with pytest.raises(ProjectFormatError, match="JSON number|finite JSON"):
            load_project(destination)


def test_writer_and_reconstruction_normalize_numeric_conversion_overflow(
    tmp_path: Path,
) -> None:
    huge_count_project = _snapshot_project("amino.rcms")
    _first_populated_raw(huge_count_project)[0] = 10**399
    with pytest.raises(ProjectFormatError, match="finite JSON numeric range"):
        save_project(tmp_path / "huge-count.rcms", huge_count_project, _minimal_state())

    document = project_format.ProjectDocument(
        format_version=CURRENT_FORMAT_VERSION,
        project=huge_count_project,
        state=_minimal_state(),
    )
    with pytest.raises(ProjectFormatError, match="expected a finite number"):
        reconstruct_analysis_dataset(document)

    oversized_project = _snapshot_project("amino.rcms")
    _first_study(oversized_project)["year"] = 10**5000
    with pytest.raises(ProjectFormatError, match="portable JSON numeric range"):
        save_project(tmp_path / "oversized.rcms", oversized_project, _minimal_state())

    nonfinite_project = _snapshot_project("amino.rcms")
    _first_study(nonfinite_project)["sample_size"] = float("inf")
    with pytest.raises(ProjectFormatError, match="finite JSON number"):
        save_project(tmp_path / "nonfinite.rcms", nonfinite_project, _minimal_state())


def test_study_sample_size_requires_a_finite_positive_integer_on_save_and_load(
    tmp_path: Path,
) -> None:
    for invalid in (0, -1, 1.5):
        project = _snapshot_project("amino.rcms")
        _first_study(project)["sample_size"] = invalid
        with pytest.raises(ProjectFormatError, match="positive integer"):
            save_project(
                tmp_path / f"save-sample-size-{invalid}.rcms", project, _minimal_state()
            )

        destination = tmp_path / f"load-sample-size-{invalid}.rcms"
        valid = _snapshot_project("amino.rcms")
        save_project(destination, valid, _minimal_state())
        _first_study(valid)["sample_size"] = invalid
        _replace_json_member(destination, "project.json", valid)
        with pytest.raises(ProjectFormatError, match="positive integer"):
            load_project(destination)

    valid = _snapshot_project("amino.rcms")
    _first_study(valid)["sample_size"] = 10.0
    destination = tmp_path / "valid-sample-size.rcms"
    save_project(destination, valid, _minimal_state())
    assert load_project(destination).project == valid


def test_reader_rejects_unsupported_versions_before_decoding_project_data(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "future.rcms"
    save_project(destination, _minimal_project(), _minimal_state())
    members = _members(destination)
    manifest = json.loads(members["manifest.json"])
    manifest["format_version"] = 999
    members["manifest.json"] = _json_bytes(manifest)
    members["project.json"] = b"not even json"
    _write_archive(destination, [(name, members[name]) for name in members])

    with pytest.raises(
        ProjectFormatError, match="unsupported project format version: 999"
    ):
        load_project(destination)


@pytest.mark.parametrize(
    "members",
    [
        [("manifest.json", b"{}"), ("../project.json", b"{}"), ("state.json", b"{}")],
        [
            ("manifest.json", b"{}"),
            ("project.json", b"{}"),
            ("project.json", b"{}"),
            ("state.json", b"{}"),
        ],
        [("manifest.json", b"{}"), ("project.json", b"{}")],
    ],
    ids=["unsafe-name", "duplicate-name", "missing-member"],
)
def test_reader_rejects_unsafe_duplicate_or_missing_archive_members(
    tmp_path: Path, members: list[tuple[str, bytes]]
) -> None:
    destination = tmp_path / "unsafe.rcms"
    _write_archive(destination, members)

    with pytest.raises(ProjectFormatError, match="archive|members|member names"):
        load_project(destination)


def test_reader_rejects_malformed_utf8_before_schema_validation(tmp_path: Path) -> None:
    destination = tmp_path / "encoding.rcms"
    save_project(destination, _minimal_project(), _minimal_state())
    members = _members(destination)
    members["project.json"] = b"\xff"
    manifest = json.loads(members["manifest.json"])
    manifest["members"]["project.json"] = {
        "sha256": hashlib.sha256(b"\xff").hexdigest(),
        "size": 1,
    }
    members["manifest.json"] = _json_bytes(manifest)
    _write_archive(destination, [(name, members[name]) for name in members])

    with pytest.raises(ProjectFormatError, match="strict UTF-8"):
        load_project(destination)


def test_reader_rejects_member_content_that_does_not_match_integrity(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "tampered.rcms"
    save_project(destination, _minimal_project(), _minimal_state())
    members = _members(destination)
    members["project.json"] = members["project.json"].replace(
        b'"title":"Example"', b'"title":"example"'
    )
    _write_archive(destination, [(name, members[name]) for name in members])

    with pytest.raises(ProjectFormatError, match="integrity digest mismatch"):
        load_project(destination)


def test_reader_applies_member_size_and_compression_limits(tmp_path: Path) -> None:
    destination = tmp_path / "limited.rcms"
    save_project(destination, _minimal_project(), _minimal_state())

    with pytest.raises(ProjectFormatError, match="member exceeds size limit"):
        load_project(
            destination,
            limits=ProjectArchiveLimits(max_member_size=32),
        )
    with pytest.raises(ProjectFormatError, match="compression ratio limit"):
        load_project(
            destination,
            limits=ProjectArchiveLimits(max_compression_ratio=1.0),
        )


def test_reader_rejects_symlink_encryption_and_unsupported_compression_metadata(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.rcms"
    save_project(source, _minimal_project(), _minimal_state())
    members = _members(source)

    symlink = tmp_path / "symlink.rcms"
    with zipfile.ZipFile(symlink, "w") as archive:
        for name, payload in members.items():
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            mode = (
                stat.S_IFLNK | 0o777 if name == "project.json" else stat.S_IFREG | 0o600
            )
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payload)
    with pytest.raises(ProjectFormatError, match="unsafe archive member type"):
        load_project(symlink)

    encrypted = tmp_path / "encrypted.rcms"
    encrypted.write_bytes(source.read_bytes())
    with zipfile.ZipFile(encrypted) as archive:
        flag_bits = archive.infolist()[0].flag_bits
    _patch_first_central_header(encrypted, 8, flag_bits | 0x1)
    with pytest.raises(ProjectFormatError, match="encrypted archive member"):
        load_project(encrypted)

    unsupported = tmp_path / "unsupported-compression.rcms"
    unsupported.write_bytes(source.read_bytes())
    _patch_first_central_header(unsupported, 10, 99)
    with pytest.raises(ProjectFormatError, match="unsupported archive compression"):
        load_project(unsupported)


def test_reader_enforces_archive_total_size_and_member_count_ceilings(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "ceilings.rcms"
    save_project(destination, _minimal_project(), _minimal_state())
    with zipfile.ZipFile(destination) as archive:
        total_uncompressed = sum(info.file_size for info in archive.infolist())

    with pytest.raises(ProjectFormatError, match="configured size limit"):
        load_project(
            destination,
            limits=ProjectArchiveLimits(
                max_archive_size=destination.stat().st_size - 1
            ),
        )
    with pytest.raises(ProjectFormatError, match="total uncompressed size limit"):
        load_project(
            destination,
            limits=ProjectArchiveLimits(
                max_total_uncompressed_size=total_uncompressed - 1
            ),
        )
    with pytest.raises(ProjectFormatError, match="too many members"):
        load_project(destination, limits=ProjectArchiveLimits(max_member_count=2))


def test_reader_normalizes_crc_and_truncated_archive_failures(tmp_path: Path) -> None:
    source = tmp_path / "source.rcms"
    save_project(source, _minimal_project(), _minimal_state())

    corrupt = tmp_path / "crc.rcms"
    corrupt.write_bytes(source.read_bytes())
    payload = bytearray(corrupt.read_bytes())
    with zipfile.ZipFile(corrupt) as archive:
        info = archive.getinfo("project.json")
    local = info.header_offset
    name_length = int.from_bytes(payload[local + 26 : local + 28], "little")
    extra_length = int.from_bytes(payload[local + 28 : local + 30], "little")
    data_offset = local + 30 + name_length + extra_length
    payload[data_offset + info.compress_size // 2] ^= 0x01
    corrupt.write_bytes(payload)
    with pytest.raises(ProjectFormatError, match="could not be read safely"):
        load_project(corrupt)

    truncated = tmp_path / "truncated.rcms"
    truncated.write_bytes(source.read_bytes()[:-12])
    with pytest.raises(ProjectFormatError, match="not a valid ZIP container"):
        load_project(truncated)


def test_reader_supports_bounded_zip_data_descriptors(tmp_path: Path) -> None:
    source = tmp_path / "source.rcms"
    save_project(source, _minimal_project(), _minimal_state())
    members = _members(source)

    class UnseekableBuffer(io.BytesIO):
        def seekable(self) -> bool:
            return False

        def seek(self, *_args: object, **_kwargs: object) -> int:
            raise io.UnsupportedOperation("not seekable")

    buffer = UnseekableBuffer()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    destination = tmp_path / "data-descriptors.rcms"
    destination.write_bytes(buffer.getvalue())
    with zipfile.ZipFile(destination) as archive:
        assert all(info.flag_bits & 0x08 for info in archive.infolist())

    assert load_project(destination).project == _minimal_project()


def test_failed_atomic_replace_preserves_the_previous_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "research.rcms"
    original = _minimal_project()
    save_project(destination, original, _minimal_state())
    changed = _minimal_project()
    _object(changed["dataset"])["title"] = "Changed"

    def fail_replace(_source: object, _destination: object) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(project_format.os, "replace", fail_replace)
    with pytest.raises(ProjectFormatError, match="injected replace failure"):
        save_project(destination, changed, _minimal_state())

    assert load_project(destination).project == original
    assert list(tmp_path.glob(".research.rcms.*.tmp")) == []


def test_pre_replace_failures_preserve_previous_project_and_clean_temporary_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "staged.rcms"
    original = _minimal_project()
    save_project(destination, original, _minimal_state())
    changed = _minimal_project()
    _object(changed["dataset"])["title"] = "Changed"
    real_load = project_format.load_project

    stages = [
        (
            "archive-write",
            lambda context: context.setattr(
                project_format,
                "_write_container",
                lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    OSError("archive write")
                ),
            ),
        ),
        (
            "file-fsync",
            lambda context: context.setattr(
                project_format.os,
                "fsync",
                lambda _descriptor: (_ for _ in ()).throw(OSError("file fsync")),
            ),
        ),
        (
            "temporary-validation",
            lambda context: context.setattr(
                project_format,
                "load_project",
                lambda path, **kwargs: (
                    (_ for _ in ()).throw(ProjectFormatError("temporary validation"))
                    if str(path).endswith(".tmp")
                    else real_load(path, **kwargs)
                ),
            ),
        ),
    ]
    for stage, install_failure in stages:
        with monkeypatch.context() as context:
            install_failure(context)
            with pytest.raises(ProjectFormatError, match=stage.replace("-", " ")):
                save_project(destination, changed, _minimal_state())
        assert real_load(destination).project == original
        assert list(tmp_path.glob(".staged.rcms.*.tmp")) == []


def test_serialization_and_schema_recursion_errors_use_project_format_boundary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "recursive.rcms"
    save_project(destination, _minimal_project(), _minimal_state())
    original = destination.read_bytes()

    with monkeypatch.context() as context:
        context.setattr(
            project_format.json,
            "dumps",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RecursionError()),
        )
        with pytest.raises(ProjectFormatError, match="portable JSON"):
            save_project(destination, _minimal_project(), _minimal_state())
    assert destination.read_bytes() == original

    with monkeypatch.context() as context:
        context.setattr(
            project_format.Draft202012Validator,
            "validate",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RecursionError()),
        )
        with pytest.raises(ProjectFormatError, match="schema validation"):
            save_project(destination, _minimal_project(), _minimal_state())
    assert destination.read_bytes() == original


def test_json_nesting_is_bounded_for_manifest_and_project_data(tmp_path: Path) -> None:
    nested: JsonObject = {}
    cursor = nested
    for _index in range(project_format.MAX_JSON_NESTING + 2):
        child: JsonObject = {}
        cursor["child"] = child
        cursor = child

    with pytest.raises(ProjectFormatError, match="nesting exceeds"):
        project = _minimal_project()
        project["unexpected"] = nested
        save_project(tmp_path / "deep-data.rcms", project, _minimal_state())

    valid = tmp_path / "deep-manifest.rcms"
    save_project(valid, _minimal_project(), _minimal_state())
    members = _members(valid)
    members["manifest.json"] = _json_bytes({"unexpected": nested})
    _write_archive(valid, [(name, members[name]) for name in members])
    with pytest.raises(ProjectFormatError, match="nesting exceeds"):
        load_project(valid)


def test_cleanup_failure_preserves_and_annotates_the_primary_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "cleanup.rcms"
    save_project(destination, _minimal_project(), _minimal_state())

    with monkeypatch.context() as context:
        context.setattr(
            project_format,
            "_write_container",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                ProjectFormatError("primary archive failure")
            ),
        )
        context.setattr(
            Path,
            "unlink",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("cleanup denied")),
        )
        with pytest.raises(
            ProjectFormatError, match="primary archive failure"
        ) as error:
            save_project(destination, _minimal_project(), _minimal_state())

    assert error.value.__notes__ == ["temporary cleanup also failed: cleanup denied"]
    assert load_project(destination).project == _minimal_project()
    for temporary in tmp_path.glob(".cleanup.rcms.*.tmp"):
        temporary.unlink()


def test_supported_directory_fsync_runs_after_atomic_replacement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "durable.rcms"
    calls: list[tuple[str, int]] = []
    real_fsync = project_format.os.fsync

    monkeypatch.setattr(project_format, "_supports_directory_fsync", lambda: True)
    monkeypatch.setattr(project_format, "_open_directory", lambda *_args: 987)
    monkeypatch.setattr(
        project_format, "_close_directory", lambda fd: calls.append(("close", fd))
    )
    monkeypatch.setattr(
        project_format.os,
        "fsync",
        lambda fd: calls.append(("fsync", fd)) if fd == 987 else real_fsync(fd),
    )

    save_project(destination, _minimal_project(), _minimal_state())

    assert ("fsync", 987) in calls
    assert ("close", 987) in calls


def test_post_replace_directory_fsync_failure_reports_new_file_is_installed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "post-replace.rcms"
    save_project(destination, _minimal_project(), _minimal_state())
    changed = _minimal_project()
    _object(changed["dataset"])["title"] = "Already replaced"
    real_fsync = project_format.os.fsync

    monkeypatch.setattr(project_format, "_supports_directory_fsync", lambda: True)
    monkeypatch.setattr(project_format, "_open_directory", lambda *_args: 988)
    monkeypatch.setattr(project_format, "_close_directory", lambda _fd: None)
    monkeypatch.setattr(
        project_format.os,
        "fsync",
        lambda fd: (
            (_ for _ in ()).throw(OSError("directory fsync"))
            if fd == 988
            else real_fsync(fd)
        ),
    )

    with pytest.raises(ProjectDurabilityError, match="new file is already installed"):
        save_project(destination, changed, _minimal_state())

    assert load_project(destination).project == changed


def test_post_replace_directory_close_failure_reports_durability_uncertainty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "close-failure.rcms"
    changed = _minimal_project()
    _object(changed["dataset"])["title"] = "Installed before close failure"
    real_fsync = project_format.os.fsync

    monkeypatch.setattr(project_format, "_supports_directory_fsync", lambda: True)
    monkeypatch.setattr(project_format, "_open_directory", lambda *_args: 989)
    monkeypatch.setattr(
        project_format,
        "_close_directory",
        lambda _fd: (_ for _ in ()).throw(OSError("directory close")),
    )
    monkeypatch.setattr(
        project_format.os,
        "fsync",
        lambda fd: None if fd == 989 else real_fsync(fd),
    )

    with pytest.raises(
        ProjectDurabilityError, match="new file is already installed"
    ) as error:
        save_project(destination, changed, _minimal_state())

    assert "closing the parent directory handle failed" in str(error.value)
    cause = error.value.__cause__
    assert cause is not None
    assert cause.args == ("directory close",)
    assert load_project(destination).project == changed


def test_directory_close_failure_annotates_primary_post_replace_fsync_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "fsync-and-close-failure.rcms"
    changed = _minimal_project()
    _object(changed["dataset"])["title"] = "Installed before both failures"
    real_fsync = project_format.os.fsync

    monkeypatch.setattr(project_format, "_supports_directory_fsync", lambda: True)
    monkeypatch.setattr(project_format, "_open_directory", lambda *_args: 990)
    monkeypatch.setattr(
        project_format,
        "_close_directory",
        lambda _fd: (_ for _ in ()).throw(OSError("directory close")),
    )
    monkeypatch.setattr(
        project_format.os,
        "fsync",
        lambda fd: (
            (_ for _ in ()).throw(OSError("directory fsync"))
            if fd == 990
            else real_fsync(fd)
        ),
    )

    with pytest.raises(
        ProjectDurabilityError, match="new file is already installed"
    ) as error:
        save_project(destination, changed, _minimal_state())

    cause = error.value.__cause__
    assert cause is not None
    assert cause.args == ("directory fsync",)
    assert error.value.__notes__ == [
        "closing the parent directory handle also failed: directory close"
    ]
    assert load_project(destination).project == changed


def test_writer_output_and_current_version_migration_are_deterministic(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.rcms"
    second = tmp_path / "second.rcms"
    project = _minimal_project()
    state = _minimal_state()

    save_project(first, project, state)
    save_project(second, project, state)
    migrated_project, migrated_state = migrate_to_latest(
        CURRENT_FORMAT_VERSION, project, state
    )
    _object(migrated_project["dataset"])["title"] = "Independent copy"

    assert first.read_bytes() == second.read_bytes()
    assert _object(project["dataset"])["title"] == "Example"
    assert migrated_state == state
    with pytest.raises(ProjectFormatError, match="unsupported project format version"):
        migrate_to_latest(999, project, state)


def test_all_committed_samples_match_the_frozen_semantics_and_round_trip(
    tmp_path: Path,
) -> None:
    snapshot_paths = sorted(SNAPSHOT_DIR.glob("*.rcms.json"))
    assert snapshot_paths
    sample_manifest = json.loads((SAMPLE_DIR / "manifest.json").read_text("utf-8"))
    manifest_projects = {item["file"]: item for item in sample_manifest["projects"]}
    assert sample_manifest["format_version"] == CURRENT_FORMAT_VERSION

    for snapshot_path in snapshot_paths:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        sample_path = SAMPLE_DIR / snapshot_path.stem
        assert (
            manifest_projects[sample_path.name]["sha256"]
            == hashlib.sha256(sample_path.read_bytes()).hexdigest()
        )
        loaded = load_project(sample_path)
        assert loaded.project["dataset"] == snapshot["dataset"]
        assert loaded.state == {
            "schema_version": CURRENT_FORMAT_VERSION,
            "active_outcome": None,
            "active_follow_up": None,
            "active_groups": [],
            "active_effect": None,
            "confidence_level": 95.0,
        }

        reconstructed = reconstruct_analysis_dataset(loaded)
        assert isinstance(reconstructed, AnalysisDataset)
        assert reconstructed.to_json() == snapshot["dataset"]

        round_trip = tmp_path / sample_path.name
        save_project(round_trip, loaded.project, loaded.state)
        reopened = load_project(round_trip)
        assert reopened == loaded
