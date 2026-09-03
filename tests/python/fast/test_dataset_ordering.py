import json
import os
import subprocess
import sys
import textwrap
import builtins


sys.path.insert(0, os.path.abspath("src"))

from rc_metastudio import r_backend

r_backend.install_r_backend()

from rc_metastudio import dataset_table_model
from rc_metastudio import analysis_dataset
from rc_metastudio import meta_globals
from rc_metastudio import r_bridge


def test_dataset_group_and_follow_up_order_is_stable_across_hash_seeds():
    script = textwrap.dedent(
        """
        import json
        from rc_metastudio import r_backend

        r_backend.install_r_backend()

        from rc_metastudio import analysis_dataset
        from rc_metastudio import meta_globals

        dataset = analysis_dataset.Dataset()
        outcome = analysis_dataset.Outcome("Mortality", meta_globals.BINARY)
        study = analysis_dataset.Study(1, "Alpha")
        study.add_outcome(outcome, group_names=["tx A", "tx B", "tx C", "tx D"])
        study.add_follow_up_to_outcome(
            outcome,
            "week 4",
            group_names=["tx A", "tx B", "tx C", "tx D"],
        )
        dataset.add_study(study)
        dataset.follow_ups_by_outcome["Mortality"] = {
            0: "baseline",
            1: "week 4",
            2: "week 8",
        }

        print(json.dumps({
            "all_groups": dataset.get_group_names(),
            "fu_groups": dataset.get_group_names_for_outcome_follow_up(
                "Mortality", "week 4"
            ),
            "follow_ups": dataset.get_follow_up_names(),
        }))
        """
    )
    expected = {
        "all_groups": ["tx A", "tx B", "tx C", "tx D"],
        "fu_groups": ["tx A", "tx B", "tx C", "tx D"],
        "follow_ups": ["baseline", "week 4", "week 8"],
    }

    for seed in ("1", "2"):
        env = os.environ.copy()
        env["RCMS_STUB_BACKEND"] = "1"
        env["PYTHONHASHSEED"] = seed
        env["PYTHONPATH"] = os.path.abspath("src")
        result = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert json.loads(result.stdout.splitlines()[-1]) == expected


def _sortable_dataset_model():
    dataset = analysis_dataset.Dataset()
    studies = [
        analysis_dataset.Study(1, name="Gamma", year=1988),
        analysis_dataset.Study(2, name="Alpha", year=1977),
        analysis_dataset.Study(3, name="Beta", year=1989),
    ]
    for study in studies:
        dataset.add_study(study)

    dataset.add_outcome(analysis_dataset.Outcome("Mortality", meta_globals.BINARY))
    dataset.add_covariate(
        analysis_dataset.Covariate("Dose", "continuous"),
        covariate_values={"Gamma": 30, "Alpha": 10, "Beta": 20},
    )

    raw_events_by_name = {"Gamma": 3, "Alpha": 1, "Beta": 2}
    effects_by_name = {"Gamma": 0.3, "Alpha": 0.1, "Beta": 0.2}
    group_comparison = "-".join(meta_globals.DEFAULT_GROUP_NAMES)
    for study in dataset.studies:
        analysis_unit = study.get_analysis_unit("Mortality", "first")
        analysis_unit.set_raw_data_for_groups(
            meta_globals.DEFAULT_GROUP_NAMES,
            [[raw_events_by_name[study.name], 10], [5, 10]],
        )
        analysis_unit.set_effect_and_ci(
            "OR",
            group_comparison,
            effects_by_name[study.name],
            effects_by_name[study.name] - 0.01,
            effects_by_name[study.name] + 0.01,
            confidence_multiplier=1.96,
        )

    model = dataset_table_model.DatasetTableModel(
        dataset=dataset, add_blank_study=False
    )
    model.current_outcome_name = "Mortality"
    model.current_effect = "OR"
    model.current_groups = meta_globals.DEFAULT_GROUP_NAMES
    model.update_column_indices()
    return model


def _study_names(model):
    return [study.name for study in model.dataset.studies]


def test_follow_up_navigation_handles_removed_middle_index():
    model = _sortable_dataset_model()
    model.dataset.add_follow_up_to_outcome("Mortality", "week 4")
    model.dataset.add_follow_up_to_outcome("Mortality", "week 8")
    model.dataset.remove_follow_up_from_outcome("week 4", "Mortality")
    model.set_current_follow_up_index(0)

    assert model.get_next_follow_up() == (2, "week 8")
    assert model.get_previous_follow_up() == (2, "week 8")


def test_dataset_model_sort_studies_uses_key_function(monkeypatch):
    model = _sortable_dataset_model()
    monkeypatch.setattr(
        r_bridge, "binary_convert_scale", lambda value, *args, **kwargs: value
    )
    monkeypatch.delattr(builtins, "cmp", raising=False)

    sort_cases = [
        (model.NAME, ["Alpha", "Beta", "Gamma"]),
        (model.YEAR, ["Alpha", "Gamma", "Beta"]),
        (model.RAW_DATA[0], ["Alpha", "Beta", "Gamma"]),
        (model.OUTCOMES[0], ["Alpha", "Beta", "Gamma"]),
        (model.OUTCOMES[-1] + 1, ["Alpha", "Beta", "Gamma"]),
    ]

    for column, expected_order in sort_cases:
        model.dataset.studies = [
            next(study for study in model.dataset.studies if study.name == name)
            for name in ["Gamma", "Alpha", "Beta"]
        ]

        model.sort_studies(column, reverse=False)

        assert _study_names(model) == expected_order
