from __future__ import annotations

import copy

import pytest

from rc_metastudio.project_format import JsonObject, JsonValue, ProjectDocument



from rc_metastudio import project_adapter


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
    assert rebuilt_units == expected_units
    assert list(
        dataset.studies[0].outcomes_to_follow_ups["Outcome"]["first"].tx_groups
    ) == [
        "Tx 1",
        "Tx 2",
        "Tx 3",
    ]


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
        "current_outcome": "Outcome",
        "current_time_point": 0,
        "current_txs": ["Tx 1", "Tx 2"],
        "current_effect": "OR",
        "study_auto_added": False,
        "conf_level": 95.0,
    }
    assert runtime_project.restored_selection is True
