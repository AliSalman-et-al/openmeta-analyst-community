# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Translate between the application dataset model and portable project JSON."""

from __future__ import annotations

import copy
from typing import Any

import ma_dataset
import two_way_dict


_FAMILY_NAMES = {0: "binary", 1: "continuous", 2: "diagnostic"}


class ProjectAdapterError(ValueError):
    """The application model cannot be represented as a structured project."""


def _portable_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_portable_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _portable_value(item) for key, item in value.items()}
    raise ProjectAdapterError(
        f"project data contains unsupported {type(value).__name__} value"
    )


def _entered_effects(effects: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    required = {
        "est",
        "lower",
        "upper",
        "display_est",
        "display_lower",
        "display_upper",
    }
    for metric, comparisons in effects.items():
        kept_comparisons = {}
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


def dataset_to_project(dataset: ma_dataset.Dataset) -> dict[str, Any]:
    """Return latest-version project data for an application dataset."""

    outcomes = []
    families = set()
    for name in dataset.get_outcome_names():
        outcome = dataset.get_outcome_obj(name)
        if outcome is None:
            raise ProjectAdapterError(f"outcome {name!r} has no definition")
        families.add(outcome.data_type)
        follow_ups = [
            value
            for _, value in sorted(
                dataset.outcome_names_to_follow_ups[name].items(),
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
    if len(families) != 1 or next(iter(families), None) not in _FAMILY_NAMES:
        raise ProjectAdapterError(
            "a project must contain outcomes from exactly one supported analysis family"
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
                        "outcome": str(outcome_name),
                        "follow_up": follow_up,
                        "groups": [
                            {
                                "id": group.id,
                                "name": str(name),
                                "raw_data": _portable_value(group.raw_data),
                            }
                            for name, group in sorted(unit.tx_groups.items())
                        ],
                        "entered_effects": _entered_effects(unit.effects_dict),
                    }
                )
        studies.append(
            {
                "id": study.id,
                "name": str(study.name),
                "year": study.year,
                "include": bool(study.include),
                "manually_excluded": bool(
                    getattr(study, "manually_excluded", False)
                ),
                "notes": str(study.notes),
                "sample_size": study.N,
                "covariates": _portable_value(study.covariate_dict),
                "analysis_units": units,
            }
        )

    family = _FAMILY_NAMES[next(iter(families))]
    return {
        "schema_version": 1,
        "dataset": {
            "title": str(dataset.title or ""),
            "summary": _portable_value(dataset.summary),
            "notes": str(dataset.notes),
            "is_diagnostic": bool(dataset.is_diag),
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


def model_to_state(model: Any) -> dict[str, Any]:
    """Capture only durable, project-scoped working state."""

    return {
        "schema_version": 1,
        "active_outcome": model.current_outcome,
        "active_follow_up": model.get_current_follow_up_name(),
        "active_groups": list(model.current_txs or []),
        "active_effect": model.current_effect,
        "confidence_level": float(model.get_global_conf_level()),
    }


def project_to_dataset(project: dict[str, Any]) -> ma_dataset.Dataset:
    """Rebuild an application dataset from validated project data."""

    source = project["dataset"]
    dataset = ma_dataset.Dataset(
        title=source["title"],
        is_diag=source["is_diagnostic"],
        summary=copy.deepcopy(source["summary"]),
    )
    dataset.notes = source["notes"]
    outcomes = {
        item["name"]: ma_dataset.Outcome(
            item["name"], item["data_type"], sub_type=item["sub_type"]
        )
        for item in source["outcomes"]
    }
    dataset.outcome_names_to_follow_ups = {}
    for item in source["outcomes"]:
        mapping = two_way_dict.TwoWayDict()
        for index, follow_up in enumerate(item["follow_ups"]):
            mapping[index] = follow_up
        dataset.outcome_names_to_follow_ups[item["name"]] = mapping
    dataset.covariates = [
        ma_dataset.Covariate(
            item["name"],
            "continuous" if item["data_type"] == 1 else "factor",
            stable_id=item["stable_id"],
        )
        for item in source["covariates"]
    ]
    for covariate, item in zip(dataset.covariates, source["covariates"], strict=True):
        covariate.stable_id = item["stable_id"]

    for item in source["studies"]:
        study = ma_dataset.Study(
            item["id"], item["name"], item["year"], include=item["include"]
        )
        study.N = item["sample_size"]
        study.notes = item["notes"]
        study.manually_excluded = item["manually_excluded"]
        study.covariate_dict = copy.deepcopy(item["covariates"])
        study.outcomes = [outcomes[name] for name in outcomes]
        for unit_data in item["analysis_units"]:
            outcome = outcomes[unit_data["outcome"]]
            group_names = [group["name"] for group in unit_data["groups"]]
            raw_data = [copy.deepcopy(group["raw_data"]) for group in unit_data["groups"]]
            unit = ma_dataset.MetaAnalyticUnit(
                outcome, raw_data=raw_data, group_names=group_names
            )
            for group_data in unit_data["groups"]:
                unit.tx_groups[group_data["name"]].id = group_data["id"]
            for metric, comparisons in unit_data["entered_effects"].items():
                for comparison, values in comparisons.items():
                    if comparison not in unit.effects_dict[metric]:
                        raise ProjectAdapterError(
                            f"unknown effect comparison {comparison!r} for {metric}"
                        )
                    unit.effects_dict[metric][comparison].update(
                        copy.deepcopy(values)
                    )
            study.outcomes_to_follow_ups.setdefault(unit_data["outcome"], {})[
                unit_data["follow_up"]
            ] = unit
        dataset.studies.append(study)
    return dataset


def state_to_model_state(dataset: ma_dataset.Dataset, state: dict[str, Any]) -> dict[str, Any]:
    """Translate portable durable state to the table model's typed state keys."""

    outcome = state["active_outcome"]
    follow_up = state["active_follow_up"]
    groups = list(state["active_groups"])
    effect = state["active_effect"]
    if outcome is None and dataset.get_outcome_names():
        outcome = dataset.get_outcome_names()[0]
        follow_up_mapping = dataset.outcome_names_to_follow_ups[outcome]
        if follow_up_mapping:
            time_key = min(follow_up_mapping)
            follow_up = follow_up_mapping[time_key]
        first_unit = None
        for study in dataset.studies:
            first_unit = study.outcomes_to_follow_ups.get(outcome, {}).get(follow_up)
            if first_unit is not None:
                break
        available_groups = list(first_unit.tx_groups) if first_unit is not None else []
        groups = available_groups[:1] if dataset.is_diag else available_groups[:2]
        summary = dataset.summary if isinstance(dataset.summary, dict) else {}
        effect = summary.get("effect")
        if effect is None and not dataset.is_diag:
            effect = "OR" if dataset.get_outcome_type(outcome) == 0 else "SMD"
    time_point = None
    if outcome is not None and follow_up is not None:
        time_point = dataset.outcome_names_to_follow_ups[outcome].get_key(follow_up)
    return {
        "current_outcome": outcome,
        "current_time_point": time_point,
        "current_txs": groups,
        "current_effect": effect,
        "study_auto_added": False,
        "conf_level": state["confidence_level"],
    }
