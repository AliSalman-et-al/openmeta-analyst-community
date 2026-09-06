from __future__ import annotations

import copy
from pathlib import Path

import pytest

from rc_metastudio.project_format import JsonObject, JsonValue, ProjectDocument


from rc_metastudio import project_adapter
from rc_metastudio.workspace_session import WorkspaceSession


def _multi_arm_project(family: str) -> JsonObject:
    data_type = {"binary": 0, "continuous": 1}[family]
    subtype = {"binary": "proportions", "continuous": "means"}[family]
    raw_values = {
        "binary": [[1, 10], [2, 20], [3, 30]],
        "continuous": [[10, 1.0, 0.5], [20, 2.0, 0.75], [30, 3.0, 1.0]],
    }[family]
    return {
        "schema_version": 1,
        "dataset": {
            "analysis_family": family,
            "covariates": [],
            "is_diagnostic": False,
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
            "title": "Adapter group contract",
        },
    }


def _object(value: JsonValue) -> JsonObject:
    if not isinstance(value, dict):
        raise AssertionError("expected JSON object")
    return value


def _objects(value: JsonValue) -> list[JsonObject]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise AssertionError("expected JSON object array")
    return value


@pytest.mark.parametrize("family", ["binary", "continuous"])
def test_adapter_round_trip_preserves_every_multi_arm_group(family: str) -> None:
    project = _multi_arm_project(family)

    dataset = project_adapter.project_to_dataset(copy.deepcopy(project))
    rebuilt = project_adapter.dataset_to_project(dataset)

    expected_units = _objects(
        _object(_objects(_object(project["dataset"])["studies"])[0])["analysis_units"]
    )
    rebuilt_units = _objects(
        _object(_objects(_object(rebuilt["dataset"])["studies"])[0])["analysis_units"]
    )
    assert [
        {key: value for key, value in unit.items() if key != "stable_id"}
        | {
            "groups": [
                {key: value for key, value in group.items() if key != "stable_id"}
                for group in _objects(unit["groups"])
            ]
        }
        for unit in rebuilt_units
    ] == expected_units
    assert list(
        dataset.studies[0].analysis_units_by_outcome["Outcome"]["first"].groups
    ) == [
        "Tx 1",
        "Tx 2",
        "Tx 3",
    ]


def test_adapter_reconstructs_internal_identities_across_reopen() -> None:
    dataset = project_adapter.project_to_dataset(_multi_arm_project("binary"))
    original = (
        dataset.studies[0].stable_id,
        dataset.get_outcome_obj("Outcome").stable_id,
        dataset.studies[0].analysis_units_by_outcome["Outcome"]["first"].stable_id,
        dataset.studies[0]
        .analysis_units_by_outcome["Outcome"]["first"]
        .groups["Tx 1"]
        .stable_id,
    )
    reopened = project_adapter.project_to_dataset(
        project_adapter.dataset_to_project(dataset)
    )
    assert original == (
        reopened.studies[0].stable_id,
        reopened.get_outcome_obj("Outcome").stable_id,
        reopened.studies[0].analysis_units_by_outcome["Outcome"]["first"].stable_id,
        reopened.studies[0]
        .analysis_units_by_outcome["Outcome"]["first"]
        .groups["Tx 1"]
        .stable_id,
    )


def test_adapter_does_not_write_internal_identities_to_v1() -> None:
    project = project_adapter.dataset_to_project(
        project_adapter.project_to_dataset(_multi_arm_project("binary"))
    )
    dataset = _object(project["dataset"])
    outcome = _objects(dataset["outcomes"])[0]
    study = _objects(dataset["studies"])[0]
    unit = _objects(study["analysis_units"])[0]
    group = _objects(unit["groups"])[0]

    assert "stable_id" not in outcome
    assert "follow_up_ids" not in outcome
    assert "stable_id" not in study
    assert "stable_id" not in unit
    assert "stable_id" not in group


@pytest.mark.parametrize("values", [
    {"est": 1.5},
    {"est": 1.5, "SE": 0.25, "display_est": 1.5, "display_se": 0.25},
    {"est": 1.5, "lower": 1.0, "upper": 2.0, "SE": 0.25,
     "display_est": 1.5, "display_lower": 1.0, "display_upper": 2.0},
])
def test_generic_effect_round_trip_uses_entered_values_only(values) -> None:
    project = _multi_arm_project("continuous")
    dataset_data = _object(project["dataset"])
    outcomes = _objects(dataset_data["outcomes"])
    outcomes[0]["sub_type"] = "generic_effect"
    studies = _objects(dataset_data["studies"])
    units = _objects(_object(studies[0])["analysis_units"])
    unit = units[0]
    groups = _objects(unit["groups"])
    unit["groups"] = [groups[0]]
    unit["entered_effects"] = {
        "TX Mean": {
            "Tx 1": values
        }
    }

    dataset = project_adapter.project_to_dataset(copy.deepcopy(project))
    rebuilt = project_adapter.dataset_to_project(dataset)
    rebuilt_unit = _objects(
        _object(_objects(_object(rebuilt["dataset"])["studies"])[0])["analysis_units"]
    )[0]

    assert rebuilt_unit["entered_effects"] == unit["entered_effects"]
    reopened_unit = dataset.studies[0].get_analysis_unit("Outcome", "first")
    assert reopened_unit.get_entered_effect_and_ci("TX Mean", "Tx 1") == (
        1.5,
        values.get("lower"),
        values.get("upper"),
    )


def test_entered_effect_edits_survive_history_and_save(tmp_path: Path) -> None:
    project = _multi_arm_project("continuous")
    dataset_data = _object(project["dataset"])
    _objects(dataset_data["outcomes"])[0]["sub_type"] = "generic_effect"
    unit_data = _objects(_objects(dataset_data["studies"])[0]["analysis_units"])[0]
    for group in _objects(unit_data["groups"]):
        group["raw_data"] = ["", "", ""]
    state: JsonObject = {
        "schema_version": 1,
        "active_outcome": "Outcome",
        "active_follow_up": "first",
        "active_groups": ["Tx 1", "Tx 2"],
        "active_effect": "TX Mean",
        "confidence_level": 95.0,
    }
    session = WorkspaceSession(ProjectDocument(1, project, state))
    runtime = session.runtime
    assert runtime is not None
    unit = runtime.dataset.studies[0].get_analysis_unit("Outcome", "first")
    unit.set_effect_for_source("entered", "TX Mean", "Tx 1", 1.5, None, None)
    session.checkpoint()
    assert session.is_dirty
    assert session.can_undo
    unit.set_effect_for_source("entered", "TX Mean", "Tx 1", 1.5, None, None, 0.2)
    session.checkpoint()
    runtime.dataset.studies[0].include = False
    session.checkpoint()

    assert session.undo()
    assert session.runtime is not None
    restored = session.runtime.dataset.studies[0].get_analysis_unit("Outcome", "first")
    assert restored.get_effect_for_source("entered", "TX Mean", "Tx 1").standard_error == 0.2
    assert session.undo()
    assert session.runtime is not None
    restored = session.runtime.dataset.studies[0].get_analysis_unit("Outcome", "first")
    effect = restored.get_effect_for_source("entered", "TX Mean", "Tx 1")
    assert effect.estimate == 1.5
    assert effect.standard_error is None
    assert session.redo()
    destination = tmp_path / "entered.rcms"
    session.save(destination)
    reopened = WorkspaceSession()
    reopened.open(destination)
    assert reopened.runtime is not None
    restored = reopened.runtime.dataset.studies[0].get_analysis_unit("Outcome", "first")
    effect = restored.get_effect_for_source("entered", "TX Mean", "Tx 1")
    assert effect.estimate == 1.5
    assert effect.standard_error == 0.2


def test_adapter_derives_repeatable_identities_for_legacy_projects() -> None:
    project = _multi_arm_project("binary")

    first = project_adapter.project_to_dataset(copy.deepcopy(project))
    second = project_adapter.project_to_dataset(copy.deepcopy(project))

    def identities(dataset):
        unit = dataset.studies[0].analysis_units_by_outcome["Outcome"]["first"]
        return (
            dataset.studies[0].stable_id,
            dataset.get_outcome_obj("Outcome").stable_id,
            dataset.get_follow_up_stable_id("Outcome", "first"),
            unit.stable_id,
            tuple(group.stable_id for group in unit.groups.values()),
        )

    assert identities(first) == identities(second)


def test_adding_follow_up_after_legacy_reopen_preserves_follow_up_order() -> None:
    dataset = project_adapter.project_to_dataset(_multi_arm_project("binary"))

    dataset.add_follow_up_to_outcome("Outcome", "week 4")

    assert dataset.get_follow_up_names_for_outcome("Outcome") == ["first", "week 4"]
    follow_ups = next(iter(dataset.follow_ups_by_outcome_id.values()))
    follow_up_values = list(follow_ups.values())
    assert [follow_up.label for follow_up in follow_up_values] == ["first", "week 4"]
    assert follow_up_values[0].ordinal is None
    assert follow_up_values[-1].ordinal == 1


def test_document_to_runtime_project_reconstructs_state_and_selection() -> None:
    project = _multi_arm_project("binary")
    state: JsonObject = {
        "schema_version": 1,
        "active_outcome": "Outcome",
        "active_follow_up": "first",
        "active_groups": ["Tx 1", "Tx 2"],
        "active_effect": "OR",
        "confidence_level": 95.0,
    }

    runtime_project = project_adapter.document_to_runtime_project(
        ProjectDocument(format_version=1, project=project, state=state)
    )

    assert isinstance(runtime_project, project_adapter.RuntimeProject)
    assert runtime_project.dataset.get_outcome_names() == ["Outcome"]
    assert runtime_project.model_state == {
        "current_outcome_name": "Outcome",
        "current_follow_up_index": 0,
        "current_groups": ["Tx 1", "Tx 2"],
        "current_effect": "OR",
        "study_auto_added": False,
        "confidence_level": 95.0,
    }
    assert runtime_project.restored_selection is True
