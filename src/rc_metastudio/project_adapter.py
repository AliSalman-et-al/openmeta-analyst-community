# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Translate between the application dataset model and portable project JSON."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from rc_metastudio import analysis_dataset
from rc_metastudio import analysis_unit
from rc_metastudio import two_way_dict
from rc_metastudio.project_format import JsonObject, JsonValue, ProjectDocument


_FAMILY_NAMES = {0: "binary", 1: "continuous", 2: "diagnostic"}


class ProjectAdapterError(ValueError):
    """The application model cannot be represented as a structured project."""


@dataclass(frozen=True, slots=True)
class RuntimeProject:
    """Reconstructed application state from a validated project document."""

    dataset: analysis_dataset.Dataset
    model_state: JsonObject
    restored_selection: bool


class ProjectStateModel(Protocol):
    """Workspace fields that are durable in a project archive."""

    current_outcome_name: str | None
    current_groups: list[str]
    current_effect: str | None

    def get_current_follow_up_name(self) -> str | None: ...

    def get_confidence_level(self) -> float: ...


def _portable_value(value: object) -> JsonValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_portable_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _portable_value(item) for key, item in value.items()}
    raise ProjectAdapterError(
        f"project data contains unsupported {type(value).__name__} value"
    )


def _entered_effects(
    effects: Mapping[str, Mapping[str, Mapping[str, object]]],
) -> JsonObject:
    result: JsonObject = {}
    required = {
        "est",
        "lower",
        "upper",
        "display_est",
        "display_lower",
        "display_upper",
    }
    for metric, comparisons in effects.items():
        kept_comparisons: JsonObject = {}
        for comparison, values in comparisons.items():
            kept = {
                key: _portable_value(value)
                for key, value in values.items()
                if value not in (None, "")
            }
            # Partially calculated display caches are transient, not durable
            # artifact metadata. The v1 contract stores only complete effects.
            if required.issubset(kept):
                kept_comparisons[str(comparison)] = kept
        if kept_comparisons:
            result[str(metric)] = kept_comparisons
    return result


def _project_outcomes(
    dataset: analysis_dataset.Dataset,
) -> tuple[list[JsonValue], set[str]]:
    outcomes: list[JsonValue] = []
    families = set()
    for name in dataset.get_outcome_names():
        outcome = dataset.get_outcome_obj(name)
        if outcome is None:
            raise ProjectAdapterError(f"outcome {name!r} has no definition")
        families.add(outcome.data_type)
        follow_ups = [
            value
            for _, value in sorted(
                dataset.follow_ups_by_outcome[name].items(),
                key=lambda pair: pair[0],
            )
            if value is not None
        ]
        outcomes.append(
            {
                "name": str(name),
                "data_type": outcome.data_type,
                "sub_type": getattr(outcome, "sub_type", None),
                "follow_ups": follow_ups,
            }
        )
    if len(families) > 1 or next(iter(families), 0) not in _FAMILY_NAMES:
        raise ProjectAdapterError(
            "a project must contain outcomes from exactly one supported analysis family"
        )
    return outcomes, families


def _project_studies(dataset: analysis_dataset.Dataset) -> list[JsonValue]:
    studies: list[JsonValue] = []
    for study in dataset.studies:
        units: list[JsonValue] = []
        for outcome_name in sorted(study.analysis_units_by_outcome):
            for follow_up, unit in sorted(
                study.analysis_units_by_outcome[outcome_name].items(),
                key=lambda pair: (pair[0] is not None, str(pair[0])),
            ):
                units.append(
                    {
                        "outcome": str(outcome_name),
                        "follow_up": follow_up,
                        "groups": [
                            {
                                "id": group.id,
                                "name": str(name),
                                "raw_data": _portable_value(group.raw_data),
                            }
                            for name, group in sorted(unit.groups.items())
                        ],
                        "entered_effects": _entered_effects(unit.effects),
                    }
                )
        studies.append(
            {
                "id": study.id,
                "name": str(study.name),
                "year": study.year,
                "include": bool(study.include),
                "manually_excluded": bool(getattr(study, "manually_excluded", False)),
                "notes": str(study.notes),
                "sample_size": study.sample_size,
                "covariates": _portable_value(study.covariate_values),
                "analysis_units": units,
            }
        )
    return studies


def dataset_to_project(dataset: analysis_dataset.Dataset) -> JsonObject:
    """Return latest-version project data for an application dataset."""
    outcomes, families = _project_outcomes(dataset)
    studies = _project_studies(dataset)
    family = _FAMILY_NAMES[next(iter(families), 2 if dataset.is_diagnostic else 0)]
    return {
        "schema_version": 1,
        "dataset": {
            "title": str(dataset.title or ""),
            "summary": _portable_value(dataset.summary),
            "notes": str(dataset.notes),
            "is_diagnostic": bool(dataset.is_diagnostic),
            "analysis_family": family,
            "outcomes": outcomes,
            "covariates": [
                {
                    "name": str(covariate.name),
                    "data_type": covariate.data_type,
                    "stable_id": getattr(covariate, "stable_id", None),
                }
                for covariate in dataset.covariates
            ],
            "studies": studies,
        },
    }


def model_to_state(model: ProjectStateModel) -> JsonObject:
    """Capture only durable, project-scoped working state."""
    return {
        "schema_version": 1,
        "active_outcome": model.current_outcome_name,
        "active_follow_up": model.get_current_follow_up_name(),
        "active_groups": list(model.current_groups or []),
        "active_effect": model.current_effect,
        "confidence_level": float(model.get_confidence_level()),
    }


def _object(value: JsonValue, location: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ProjectAdapterError(f"{location} must be an object")
    return value


def _array(value: JsonValue, location: str) -> list[JsonValue]:
    if not isinstance(value, list):
        raise ProjectAdapterError(f"{location} must be an array")
    return value


def _text(value: JsonValue, location: str) -> str:
    if not isinstance(value, str):
        raise ProjectAdapterError(f"{location} must be text")
    return value


def _optional_text(value: JsonValue, location: str) -> str | None:
    if value is None:
        return None
    return _text(value, location)


def _integer(value: JsonValue, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProjectAdapterError(f"{location} must be an integer")
    return value


def _optional_integer(value: JsonValue, location: str) -> int | None:
    if value is None:
        return None
    return _integer(value, location)


def _boolean(value: JsonValue, location: str) -> bool:
    if not isinstance(value, bool):
        raise ProjectAdapterError(f"{location} must be boolean")
    return value


def _number(value: JsonValue, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProjectAdapterError(f"{location} must be numeric")
    return float(value)


def project_to_dataset(project: JsonObject) -> analysis_dataset.Dataset:
    """Rebuild an application dataset from validated project data."""
    source = _object(project["dataset"], "dataset")
    dataset = analysis_dataset.Dataset(
        title=_text(source["title"], "dataset title"),
        is_diagnostic=_boolean(source["is_diagnostic"], "diagnostic flag"),
        summary=copy.deepcopy(source["summary"]),
    )
    dataset.notes = _text(source["notes"], "dataset notes")
    outcome_items = [
        _object(item, "outcome") for item in _array(source["outcomes"], "outcomes")
    ]
    outcomes = {}
    for index, item in enumerate(outcome_items):
        outcome_name = _text(item["name"], "outcome name")
        outcomes[outcome_name] = analysis_dataset.Outcome(
            outcome_name,
            _integer(item["data_type"], "outcome data type"),
            sub_type=_optional_text(item["sub_type"], "outcome subtype"),
            stable_id=f"outcome:{index}",
        )
    dataset.follow_ups_by_outcome = {}
    dataset.follow_up_stable_ids_by_outcome = {}
    for item in outcome_items:
        outcome_name = _text(item["name"], "outcome name")
        mapping = two_way_dict.TwoWayDict()
        for index, follow_up in enumerate(
            _array(item["follow_ups"], "outcome follow-ups")
        ):
            mapping[index] = _optional_text(follow_up, "follow-up")
        dataset.follow_ups_by_outcome[outcome_name] = mapping
        outcome_id = outcomes[outcome_name].stable_id
        follow_up_ids = [
            f"{outcome_id}:follow-up:{index}" for index in range(len(mapping))
        ]
        dataset.follow_up_stable_ids_by_outcome[outcome_name] = {
            follow_up: stable_id
            for follow_up, stable_id in zip(
                mapping.values(), follow_up_ids, strict=True
            )
            if follow_up is not None and stable_id is not None
        }

    covariate_items = [
        _object(item, "covariate")
        for item in _array(source["covariates"], "covariates")
    ]
    dataset.covariates = [
        analysis_dataset.Covariate(
            _text(item["name"], "covariate name"),
            "continuous"
            if _integer(item["data_type"], "covariate data type") == 1
            else "factor",
            stable_id=(
                _optional_text(item["stable_id"], "covariate stable id")
                or f"covariate:{index}"
            ),
        )
        for index, item in enumerate(covariate_items)
    ]

    for study_index, study_value in enumerate(_array(source["studies"], "studies")):
        item = _object(study_value, "study")
        study = analysis_dataset.Study(
            _integer(item["id"], "study id"),
            _text(item["name"], "study name"),
            _optional_integer(item["year"], "study year"),
            include=_boolean(item["include"], "study inclusion"),
            stable_id=f"study:{study_index}",
        )
        study.sample_size = copy.deepcopy(item["sample_size"])
        study.notes = _text(item["notes"], "study notes")
        study.manually_excluded = _boolean(
            item["manually_excluded"], "manual exclusion"
        )
        study.covariate_values = copy.deepcopy(
            _object(item["covariates"], "study covariates")
        )
        study.outcomes = [outcomes[name] for name in outcomes]
        for unit_value in _array(item["analysis_units"], "analysis units"):
            unit_data = _object(unit_value, "analysis unit")
            outcome_name = _text(unit_data["outcome"], "analysis unit outcome")
            outcome = outcomes[outcome_name]
            group_items = [
                _object(group, "analysis group")
                for group in _array(unit_data["groups"], "analysis groups")
            ]
            group_names = [
                _text(group["name"], "analysis group name") for group in group_items
            ]
            raw_data = [
                copy.deepcopy(_array(group["raw_data"], "group raw data"))
                for group in group_items
            ]
            follow_up = _optional_text(unit_data["follow_up"], "unit follow-up")
            follow_up_id = dataset.follow_up_stable_ids_by_outcome[outcome_name].get(
                follow_up
            )
            unit_id = f"{outcome.stable_id}:{follow_up_id or 'default'}"
            unit = analysis_unit.AnalysisUnit(
                outcome,
                raw_data=raw_data,
                group_names=group_names,
                stable_id=unit_id,
            )
            for group_index, group_data in enumerate(group_items):
                group_name = _text(group_data["name"], "analysis group name")
                unit.groups[group_name].id = _integer(
                    group_data["id"], "analysis group id"
                )
                unit.groups[group_name].stable_id = f"{unit_id}:group:{group_index}"
            entered_effects = _object(unit_data["entered_effects"], "entered effects")
            for metric, comparisons_value in entered_effects.items():
                comparisons = _object(comparisons_value, "effect comparisons")
                for comparison, values_value in comparisons.items():
                    if comparison not in unit.effects[metric]:
                        raise ProjectAdapterError(
                            f"unknown effect comparison {comparison!r} for {metric}"
                        )
                    values = _object(values_value, "effect values")
                    unit.effects[metric][comparison].update(copy.deepcopy(values))
            study.analysis_units_by_outcome.setdefault(outcome_name, {})[follow_up] = (
                unit
            )
        dataset.studies.append(study)
    return dataset


def state_to_model_state(
    dataset: analysis_dataset.Dataset, state: JsonObject
) -> JsonObject:
    """Translate portable durable state to the table model's typed state keys."""
    outcome = _optional_text(state["active_outcome"], "active outcome")
    follow_up = _optional_text(state["active_follow_up"], "active follow-up")
    groups = [
        _text(group, "active group")
        for group in _array(state["active_groups"], "active groups")
    ]
    effect = _optional_text(state["active_effect"], "active effect")
    if outcome is None and dataset.get_outcome_names():
        outcome = dataset.get_outcome_names()[0]
        follow_up_mapping = dataset.follow_ups_by_outcome[outcome]
        if follow_up_mapping:
            time_key = min(follow_up_mapping)
            follow_up = follow_up_mapping[time_key]
        first_unit = None
        for study in dataset.studies:
            first_unit = study.analysis_units_by_outcome.get(outcome, {}).get(follow_up)
            if first_unit is not None:
                break
        available_groups = list(first_unit.groups) if first_unit is not None else []
        groups = available_groups[:1] if dataset.is_diagnostic else available_groups[:2]
        summary = dataset.summary if isinstance(dataset.summary, dict) else {}
        effect_value = summary.get("effect")
        effect = effect_value if isinstance(effect_value, str) else None
        if effect is None and not dataset.is_diagnostic:
            effect = "OR" if dataset.get_outcome_type(outcome) == 0 else "SMD"
    time_point = None
    if outcome is not None and follow_up is not None:
        time_point = dataset.follow_ups_by_outcome[outcome].get_key(follow_up)
    return {
        "current_outcome_name": outcome,
        "current_follow_up_index": time_point,
        "current_groups": groups,
        "current_effect": effect,
        "study_auto_added": False,
        "confidence_level": _number(state["confidence_level"], "confidence level"),
    }


def document_to_runtime_project(document: ProjectDocument) -> RuntimeProject:
    """Reconstruct the application dataset and durable state from a document."""
    dataset = project_to_dataset(document.project)
    model_state = state_to_model_state(dataset, document.state)
    return RuntimeProject(
        dataset=dataset,
        model_state=model_state,
        restored_selection=document.state["active_outcome"] is not None,
    )
