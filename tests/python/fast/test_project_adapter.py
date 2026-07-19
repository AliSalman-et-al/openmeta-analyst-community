from __future__ import annotations

import copy
import os
import sys

import pytest


sys.path.insert(0, os.path.abspath("src/rc_metastudio"))

import project_adapter


def _multi_arm_project(family: str) -> dict[str, object]:
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


@pytest.mark.fast
@pytest.mark.small
@pytest.mark.release_readiness
@pytest.mark.parametrize("family", ["binary", "continuous"])
def test_adapter_round_trip_preserves_every_multi_arm_group(family: str) -> None:
    project = _multi_arm_project(family)

    dataset = project_adapter.project_to_dataset(copy.deepcopy(project))
    rebuilt = project_adapter.dataset_to_project(dataset)

    expected_units = project["dataset"]["studies"][0]["analysis_units"]
    rebuilt_units = rebuilt["dataset"]["studies"][0]["analysis_units"]
    assert rebuilt_units == expected_units
    assert list(
        dataset.studies[0].outcomes_to_follow_ups["Outcome"]["first"].tx_groups
    ) == [
        "Tx 1",
        "Tx 2",
        "Tx 3",
    ]
