"""Qt-independent semantic contract for Versioned Project Format datasets."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import NewType, TypeAlias, cast

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
StudyId = NewType("StudyId", str)
OutcomeId = NewType("OutcomeId", str)
FollowUpId = NewType("FollowUpId", str)
GroupId = NewType("GroupId", str)
CovariateId = NewType("CovariateId", str)


@dataclass(frozen=True, slots=True)
class FollowUpSnapshot:
    identity: FollowUpId
    label: str


@dataclass(frozen=True, slots=True)
class OutcomeSnapshot:
    identity: OutcomeId
    label: str
    data_type: int
    sub_type: str | None
    follow_ups: tuple[FollowUpSnapshot, ...]
    wire: tuple[tuple[str, JsonValue], ...]


@dataclass(frozen=True, slots=True)
class CovariateSnapshot:
    identity: CovariateId
    label: str
    data_type: int
    wire: tuple[tuple[str, JsonValue], ...]


@dataclass(frozen=True, slots=True)
class GroupSnapshot:
    identity: GroupId
    label: str
    raw_data: tuple[JsonValue, ...]
    wire: tuple[tuple[str, JsonValue], ...]


@dataclass(frozen=True, slots=True)
class UnitSnapshot:
    outcome: OutcomeId
    follow_up: FollowUpId | None
    groups: tuple[GroupSnapshot, ...]
    entered_effects: Mapping[str, JsonValue]
    wire: tuple[tuple[str, JsonValue], ...]


@dataclass(frozen=True, slots=True)
class StudySnapshot:
    identity: StudyId
    label: str
    year: int | None
    include: bool
    sample_size: float | None
    covariates: Mapping[str, JsonValue]
    units: tuple[UnitSnapshot, ...]
    wire: tuple[tuple[str, JsonValue], ...]


class ProjectSemanticError(ValueError):
    """Schema-valid project content violates a domain relationship."""


@dataclass(frozen=True, slots=True)
class AnalysisDataset:
    """Normalized input contract for later Analysis Adapter integration."""

    analysis_family: str
    title: str
    outcomes: tuple[OutcomeSnapshot, ...]
    covariates: tuple[CovariateSnapshot, ...]
    studies: tuple[StudySnapshot, ...]
    is_diagnostic: bool
    notes: str
    summary: JsonValue

    def to_json(self) -> JsonObject:
        return {
            "analysis_family": self.analysis_family,
            "covariates": [dict(item.wire) for item in self.covariates],
            "is_diagnostic": self.is_diagnostic,
            "notes": self.notes,
            "outcomes": [dict(item.wire) for item in self.outcomes],
            "studies": [dict(item.wire) for item in self.studies],
            "summary": copy.deepcopy(self.summary),
            "title": self.title,
        }

    @property
    def semantic_sha256(self) -> str:
        payload = (
            json.dumps(
                self.to_json(),
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


_FAMILY_DATA_TYPES = {"binary": 0, "continuous": 1, "diagnostic": 2}
_FAMILY_RAW_ARITY = {"binary": 2, "continuous": 3, "diagnostic": 4}
_FAMILY_METRICS = {
    "binary": frozenset(
        {"OR", "RD", "RR", "AS", "YUQ", "YUY", "PR", "PLN", "PLO", "PAS", "PFT"}
    ),
    "continuous": frozenset({"MD", "SMD", "TX Mean"}),
    "diagnostic": frozenset({"Sens", "Spec", "PLR", "NLR", "DOR"}),
}
_ONE_ARM_METRICS = frozenset({"PR", "PLN", "PLO", "PAS", "PFT", "TX Mean"})
_FAMILY_SUBTYPES = {
    "binary": frozenset({None, "proportion", "proportions"}),
    "continuous": frozenset(
        {None, "mean", "means", "smd", "reg_coef", "generic_effect"}
    ),
    "diagnostic": frozenset({None}),
}


def _object(value: object, location: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ProjectSemanticError(f"{location}: expected an object")
    return cast(dict[str, object], value)


def _array(value: object, location: str) -> list[object]:
    if not isinstance(value, list):
        raise ProjectSemanticError(f"{location}: expected an array")
    return cast(list[object], value)


def _finite(value: object, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProjectSemanticError(f"{location}: expected a number")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise ProjectSemanticError(f"{location}: expected a finite number") from exc
    if not math.isfinite(number):
        raise ProjectSemanticError(f"{location}: expected a finite number")
    return number


def _integer_valued(value: float | None, location: str) -> None:
    if value is not None and value % 1 != 0:
        raise ProjectSemanticError(f"{location}: count must be integer-valued")


def _validate_raw(family: str, values: list[object], location: str) -> None:
    arity = _FAMILY_RAW_ARITY[family]
    if len(values) != arity:
        raise ProjectSemanticError(
            f"{location}: raw-data arity for {family} must be {arity}"
        )
    if any(isinstance(value, str) and value != "" for value in values):
        raise ProjectSemanticError(
            f"{location}: missing raw data must use an empty string"
        )
    numbers = [None if value == "" else _finite(value, location) for value in values]
    present = [value for value in numbers if value is not None]
    if family in {"binary", "diagnostic"}:
        for index, number in enumerate(numbers):
            _integer_valued(number, f"{location}/{index}")
        if any(value < 0 for value in present):
            raise ProjectSemanticError(f"{location}: count data cannot be negative")
    if (
        family == "binary"
        and numbers[0] is not None
        and numbers[1] is not None
        and numbers[0] > numbers[1]
    ):
        raise ProjectSemanticError(f"{location}: events cannot exceed the group total")
    if family == "continuous":
        if numbers[0] is not None and numbers[0] % 1 != 0:
            raise ProjectSemanticError(
                f"{location}/0: sample size must be integer-valued"
            )
        if (numbers[0] is not None and numbers[0] <= 0) or (
            numbers[2] is not None and numbers[2] < 0
        ):
            raise ProjectSemanticError(
                f"{location}: sample size must be positive and SD nonnegative"
            )


def _validate_effect(effect: dict[str, object], location: str) -> None:
    for key, value in effect.items():
        number = _finite(value, f"{location}/{key}")
        if key in {"SE", "display_se"} and number < 0:
            raise ProjectSemanticError(
                f"{location}/{key}: standard error cannot be negative"
            )
    for prefix in ("", "display_"):
        ordered_values = [
            _finite(effect[f"{prefix}{key}"], location)
            for key in ("lower", "est", "upper")
            if f"{prefix}{key}" in effect
        ]
        if ordered_values != sorted(ordered_values):
            raise ProjectSemanticError(
                f"{location}: interval does not contain estimate"
            )


def _validate_summary(dataset: Mapping[str, object], family: str) -> None:
    if bool(dataset["is_diagnostic"]) != (family == "diagnostic"):
        raise ProjectSemanticError("analysis family and is_diagnostic disagree")
    summary = dataset["summary"]
    if not isinstance(summary, dict):
        return
    summary_value = cast(dict[str, object], summary)
    _validate_summary_identity(summary_value, family)
    _validate_summary_metrics(summary_value, family)


def _validate_summary_identity(summary: Mapping[str, object], family: str) -> None:
    if summary["data_type"] != family:
        raise ProjectSemanticError("project summary data type conflicts with family")
    if summary["sub_type"] not in _FAMILY_SUBTYPES[family]:
        raise ProjectSemanticError("project summary subtype conflicts with family")


def _validate_summary_metrics(summary: Mapping[str, object], family: str) -> None:
    effect = summary["effect"]
    metrics = cast(list[str], summary["metric_choices"])
    if effect is not None and effect not in _FAMILY_METRICS[family]:
        raise ProjectSemanticError("project summary metric conflicts with family")
    if not set(metrics) <= _FAMILY_METRICS[family]:
        raise ProjectSemanticError("project summary metric conflicts with family")


def _validated_outcomes(
    dataset: Mapping[str, object], family: str
) -> dict[str, dict[str, object]]:
    outcomes = [
        _object(value, f"outcome {index}")
        for index, value in enumerate(_array(dataset["outcomes"], "outcomes"))
    ]
    names = [cast(str, outcome["name"]) for outcome in outcomes]
    if len(names) != len(set(names)):
        raise ProjectSemanticError("duplicate outcome identifier")
    outcome_by_name = dict(zip(names, outcomes, strict=True))
    expected_data_type = _FAMILY_DATA_TYPES[family]
    for name, outcome in outcome_by_name.items():
        _validate_outcome(name, outcome, family, expected_data_type)
    return outcome_by_name


def _validate_outcome(
    name: str,
    outcome: Mapping[str, object],
    family: str,
    expected_data_type: int,
) -> None:
    if outcome["data_type"] != expected_data_type:
        raise ProjectSemanticError(
            f"outcome {name!r}: data type conflicts with {family} family"
        )
    if outcome["sub_type"] not in _FAMILY_SUBTYPES[family]:
        raise ProjectSemanticError(
            f"outcome {name!r}: subtype conflicts with {family} family"
        )
    follow_ups = cast(list[str], outcome["follow_ups"])
    if len(follow_ups) != len(set(follow_ups)):
        raise ProjectSemanticError(f"outcome {name!r}: duplicate follow-up identifier")


def _validated_covariates(
    dataset: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    covariates = [
        _object(value, f"covariate {index}")
        for index, value in enumerate(_array(dataset["covariates"], "covariates"))
    ]
    names = [cast(str, value["name"]) for value in covariates]
    if len(names) != len(set(names)):
        raise ProjectSemanticError("duplicate covariate identifier")
    stable_ids = [
        cast(str, value["stable_id"])
        for value in covariates
        if value["stable_id"] is not None
    ]
    if len(stable_ids) != len(set(stable_ids)):
        raise ProjectSemanticError("duplicate covariate stable identifier")
    return dict(zip(names, covariates, strict=True))


def _validate_studies(
    dataset: Mapping[str, object],
    family: str,
    outcomes: Mapping[str, dict[str, object]],
    covariates: Mapping[str, dict[str, object]],
) -> dict[tuple[str, str | None], set[str]]:
    studies = [
        _object(value, f"study {index}")
        for index, value in enumerate(_array(dataset["studies"], "studies"))
    ]
    study_ids = [cast(int, study["id"]) for study in studies]
    if len(study_ids) != len(set(study_ids)):
        raise ProjectSemanticError("duplicate study identifier")
    available_groups: dict[tuple[str, str | None], set[str]] = {}
    for study in studies:
        _validate_study(study, family, outcomes, covariates, available_groups)
    return available_groups


def _validate_study(
    study: Mapping[str, object],
    family: str,
    outcomes: Mapping[str, dict[str, object]],
    covariates: Mapping[str, dict[str, object]],
    available_groups: dict[tuple[str, str | None], set[str]],
) -> None:
    study_id = study["id"]
    _validate_sample_size(study, study_id)
    _validate_study_covariates(study, study_id, covariates)
    seen_units: set[tuple[str, str | None]] = set()
    for unit_index, unit_value in enumerate(
        _array(study["analysis_units"], "analysis_units")
    ):
        _validate_analysis_unit(
            _object(unit_value, f"study {study_id} unit {unit_index}"),
            study_id,
            unit_index,
            family,
            outcomes,
            seen_units,
            available_groups,
        )


def _validate_sample_size(study: Mapping[str, object], study_id: object) -> None:
    sample_size = study["sample_size"]
    if sample_size is None:
        return
    numeric_sample_size = _finite(sample_size, f"study {study_id} sample_size")
    if numeric_sample_size <= 0 or numeric_sample_size % 1 != 0:
        raise ProjectSemanticError(
            f"study {study_id} sample_size: expected a positive integer"
        )


def _validate_study_covariates(
    study: Mapping[str, object],
    study_id: object,
    covariates: Mapping[str, dict[str, object]],
) -> None:
    values = _object(study["covariates"], f"study {study_id} covariates")
    if set(values) != set(covariates):
        raise ProjectSemanticError(
            f"study {study_id}: covariate references do not match declarations"
        )
    for name, value in values.items():
        if value is None or value == "":
            continue
        if covariates[name]["data_type"] == 1:
            _finite(value, f"study {study_id} covariate {name}")
        elif not isinstance(value, str):
            raise ProjectSemanticError(
                f"study {study_id} covariate {name}: factor value must be text"
            )


def _validate_analysis_unit(
    unit: Mapping[str, object],
    study_id: object,
    unit_index: int,
    family: str,
    outcomes: Mapping[str, dict[str, object]],
    seen_units: set[tuple[str, str | None]],
    available_groups: dict[tuple[str, str | None], set[str]],
) -> None:
    outcome_name = cast(str, unit["outcome"])
    if outcome_name not in outcomes:
        raise ProjectSemanticError(
            f"study {study_id} unit {unit_index}: undeclared outcome"
        )
    follow_up = cast(str | None, unit["follow_up"])
    follow_ups = cast(list[str], outcomes[outcome_name]["follow_ups"])
    if follow_up is not None and follow_up not in follow_ups:
        raise ProjectSemanticError(
            f"study {study_id} unit {unit_index}: undeclared follow-up"
        )
    unit_key = (outcome_name, follow_up)
    if unit_key in seen_units:
        raise ProjectSemanticError(f"study {study_id}: duplicate analysis unit")
    seen_units.add(unit_key)
    groups, group_names = _validate_groups(unit, study_id, unit_index)
    _validate_group_count(
        study_id, unit_index, outcomes[outcome_name], family, len(groups)
    )
    _validate_group_raw_data(groups, study_id, unit_index, family)
    available_groups.setdefault(unit_key, set()).update(group_names)
    _validate_entered_effects(unit, study_id, unit_index, family, group_names)


def _validate_groups(
    unit: Mapping[str, object],
    study_id: object,
    unit_index: int,
) -> tuple[list[dict[str, object]], list[str]]:
    groups = [
        _object(value, f"study {study_id} unit {unit_index} group")
        for value in _array(unit["groups"], "groups")
    ]
    group_ids = [cast(int, group["id"]) for group in groups]
    group_names = [cast(str, group["name"]) for group in groups]
    if len(group_ids) != len(set(group_ids)) or len(group_names) != len(
        set(group_names)
    ):
        raise ProjectSemanticError(
            f"study {study_id} unit {unit_index}: duplicate group identifier"
        )
    return groups, group_names


def _validate_group_raw_data(
    groups: list[dict[str, object]], study_id: object, unit_index: int, family: str
) -> None:
    for group in groups:
        _validate_raw(
            family,
            _array(group["raw_data"], "raw_data"),
            f"study {study_id} unit {unit_index} group {group['name']}",
        )


def _validate_group_count(
    study_id: object,
    unit_index: int,
    outcome: Mapping[str, object],
    family: str,
    group_count: int,
) -> None:
    subtype = outcome["sub_type"]
    if family == "diagnostic":
        valid = group_count == 1
    elif subtype in {"proportion", "mean", "reg_coef", "generic_effect"}:
        valid = group_count >= 1
    elif subtype in {"proportions", "means", "smd"}:
        # Retain all arms for pair selection even though each comparison is two-arm.
        valid = group_count >= 2
    else:
        return
    if not valid:
        raise ProjectSemanticError(
            f"study {study_id} unit {unit_index}: group count conflicts with subtype"
        )


def _valid_comparisons(family: str, metric: str, group_names: list[str]) -> set[str]:
    if metric in _ONE_ARM_METRICS or family == "diagnostic":
        return set(group_names)
    return {
        f"{left}-{right}"
        for left in group_names
        for right in group_names
        if left != right
    }


def _validate_entered_effects(
    unit: Mapping[str, object],
    study_id: object,
    unit_index: int,
    family: str,
    group_names: list[str],
) -> None:
    effects = _object(unit["entered_effects"], "entered_effects")
    for metric, comparisons_value in effects.items():
        if metric not in _FAMILY_METRICS[family]:
            raise ProjectSemanticError(
                f"study {study_id} unit {unit_index}: metric conflicts with family"
            )
        comparisons = _object(comparisons_value, "effect comparisons")
        valid_comparisons = _valid_comparisons(family, metric, group_names)
        for comparison, effect in comparisons.items():
            if comparison not in valid_comparisons:
                raise ProjectSemanticError(
                    f"study {study_id} unit {unit_index}: undeclared group comparison"
                )
            _validate_effect(_object(effect, "effect"), f"{metric}/{comparison}")


def _validate_active_state(
    state: Mapping[str, JsonValue],
    family: str,
    outcomes: Mapping[str, dict[str, object]],
    available_groups: Mapping[tuple[str, str | None], set[str]],
) -> None:
    active_outcome = cast(str | None, state["active_outcome"])
    active_follow_up = cast(str | None, state["active_follow_up"])
    active_groups = cast(list[str], state["active_groups"])
    active_effect = cast(str | None, state["active_effect"])
    if active_outcome is None:
        _validate_empty_active_state(active_follow_up, active_groups, active_effect)
        return
    if active_outcome not in outcomes:
        raise ProjectSemanticError("active outcome is not declared")
    _validate_active_follow_up(active_follow_up, outcomes[active_outcome])
    _validate_active_effect(active_effect, family)
    groups = available_groups.get((active_outcome, active_follow_up), set())
    if not set(active_groups) <= groups:
        raise ProjectSemanticError("active group is not declared")


def _validate_empty_active_state(
    active_follow_up: str | None, active_groups: list[str], active_effect: str | None
) -> None:
    if active_follow_up is not None or active_groups or active_effect is not None:
        raise ProjectSemanticError("active outcome is required for other active state")


def _validate_active_follow_up(
    active_follow_up: str | None, outcome: Mapping[str, object]
) -> None:
    if active_follow_up is None:
        return
    follow_ups = cast(list[str], outcome["follow_ups"])
    if active_follow_up not in follow_ups:
        raise ProjectSemanticError("active follow-up is not declared")


def _validate_active_effect(active_effect: str | None, family: str) -> None:
    if active_effect is not None and active_effect not in _FAMILY_METRICS[family]:
        raise ProjectSemanticError("active effect conflicts with analysis family")


def validate_project_semantics(
    project: Mapping[str, JsonValue], state: Mapping[str, JsonValue]
) -> None:
    dataset = _object(project["dataset"], "project.json/dataset")
    family = cast(str, dataset["analysis_family"])
    _validate_summary(dataset, family)
    outcomes = _validated_outcomes(dataset, family)
    covariates = _validated_covariates(dataset)
    available_groups = _validate_studies(dataset, family, outcomes, covariates)
    _validate_active_state(state, family, outcomes, available_groups)


def _wire_pairs(value: Mapping[str, object]) -> tuple[tuple[str, JsonValue], ...]:
    return tuple(
        (key, cast(JsonValue, copy.deepcopy(item))) for key, item in value.items()
    )


def _typed_outcome(value: Mapping[str, object], index: int) -> OutcomeSnapshot:
    label = cast(str, value["name"])
    identity = OutcomeId(f"outcome:{index}")
    labels = cast(list[str], value["follow_ups"])
    follow_ups = tuple(
        FollowUpSnapshot(
            FollowUpId(f"{identity}:follow-up:{follow_up_index}"),
            name,
        )
        for follow_up_index, name in enumerate(labels)
    )
    return OutcomeSnapshot(
        identity,
        label,
        cast(int, value["data_type"]),
        cast(str | None, value["sub_type"]),
        follow_ups,
        _wire_pairs(value),
    )


def _typed_covariate(value: Mapping[str, object], index: int) -> CovariateSnapshot:
    label = cast(str, value["name"])
    return CovariateSnapshot(
        CovariateId(cast(str, value.get("stable_id") or f"covariate:{index}")),
        label,
        cast(int, value["data_type"]),
        _wire_pairs(value),
    )


def _follow_up_snapshot(
    outcome: OutcomeSnapshot, label: str | None
) -> FollowUpSnapshot | None:
    return next((item for item in outcome.follow_ups if item.label == label), None)


def _typed_group(value: Mapping[str, object], unit_identity: str, index: int):
    identity = f"{unit_identity}:group:{index}"
    raw_data = tuple(
        cast(JsonValue, copy.deepcopy(item))
        for item in cast(list[object], value["raw_data"])
    )
    return GroupSnapshot(
        GroupId(identity),
        cast(str, value["name"]),
        raw_data,
        _wire_pairs(value),
    )


def _typed_unit(
    value: Mapping[str, object], outcomes: Mapping[str, OutcomeSnapshot]
) -> UnitSnapshot:
    outcome = cast(str, value["outcome"])
    follow_up = cast(str | None, value["follow_up"])
    outcome_snapshot = outcomes[outcome]
    follow_up_snapshot = _follow_up_snapshot(outcome_snapshot, follow_up)
    fallback_identity = (
        follow_up_snapshot.identity if follow_up_snapshot is not None else "default"
    )
    unit_identity = f"{outcome_snapshot.identity}:{fallback_identity}"
    groups = tuple(
        _typed_group(group, unit_identity, index)
        for index, group in enumerate(
            _object(item, "group") for item in _array(value["groups"], "groups")
        )
    )
    return UnitSnapshot(
        outcome_snapshot.identity,
        None if follow_up_snapshot is None else follow_up_snapshot.identity,
        groups,
        cast(
            Mapping[str, JsonValue],
            copy.deepcopy(_object(value["entered_effects"], "entered_effects")),
        ),
        _wire_pairs(value),
    )


def _typed_study(
    value: Mapping[str, object],
    outcomes: Mapping[str, OutcomeSnapshot],
    index: int,
) -> StudySnapshot:
    name = cast(str, value["name"])
    year = cast(int | None, value["year"])
    sample_size = cast(float | None, value["sample_size"])
    units = tuple(
        _typed_unit(_object(item, "analysis unit"), outcomes)
        for item in _array(value["analysis_units"], "analysis_units")
    )
    return StudySnapshot(
        StudyId(f"study:{index}"),
        name,
        year,
        cast(bool, value["include"]),
        sample_size,
        cast(
            Mapping[str, JsonValue],
            copy.deepcopy(_object(value["covariates"], "covariates")),
        ),
        units,
        _wire_pairs(value),
    )


def reconstruct_analysis_dataset(
    project: Mapping[str, JsonValue], state: Mapping[str, JsonValue]
) -> AnalysisDataset:
    validate_project_semantics(project, state)
    dataset = _object(project["dataset"], "project.json/dataset")
    typed_outcomes = tuple(
        _typed_outcome(_object(value, "outcome"), index)
        for index, value in enumerate(_array(dataset["outcomes"], "outcomes"))
    )
    outcomes_by_label = {item.label: item for item in typed_outcomes}
    return AnalysisDataset(
        analysis_family=cast(str, dataset["analysis_family"]),
        title=cast(str, dataset["title"]),
        outcomes=typed_outcomes,
        covariates=tuple(
            _typed_covariate(_object(value, "covariate"), index)
            for index, value in enumerate(_array(dataset["covariates"], "covariates"))
        ),
        studies=tuple(
            _typed_study(_object(value, "study"), outcomes_by_label, index)
            for index, value in enumerate(_array(dataset["studies"], "studies"))
        ),
        is_diagnostic=cast(bool, dataset["is_diagnostic"]),
        notes=cast(str, dataset["notes"]),
        summary=cast(JsonValue, copy.deepcopy(dataset["summary"])),
    )
