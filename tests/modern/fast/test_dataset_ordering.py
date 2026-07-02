import json
import os
import subprocess
import sys
import textwrap
import builtins


sys.path.insert(0, os.path.abspath("src"))

import modern_compat

modern_compat.install()

import ma_data_table_model
import ma_dataset
import meta_globals
import meta_py_r


def test_dataset_group_and_follow_up_order_is_stable_across_hash_seeds():
    script = textwrap.dedent(
        """
        import json
        import modern_compat

        modern_compat.install()

        import ma_dataset
        import meta_globals

        dataset = ma_dataset.Dataset()
        outcome = ma_dataset.Outcome("Mortality", meta_globals.BINARY)
        study = ma_dataset.Study(1, "Alpha")
        study.add_outcome(outcome, group_names=["tx A", "tx B", "tx C", "tx D"])
        study.add_follow_up_to_outcome(
            outcome,
            "week 4",
            group_names=["tx A", "tx B", "tx C", "tx D"],
        )
        dataset.add_study(study)
        dataset.outcome_names_to_follow_ups["Mortality"] = {
            0: "baseline",
            1: "week 4",
            2: "week 8",
        }

        print(json.dumps({
            "all_groups": dataset.get_group_names(),
            "fu_groups": dataset.get_group_names_for_outcome_fu("Mortality", "week 4"),
            "follow_ups": dataset.get_follow_up_names(),
            "network_nodes": dataset.get_network("Mortality", "week 4")[0],
        }))
        """
    )
    expected = {
        "all_groups": ["tx A", "tx B", "tx C", "tx D"],
        "fu_groups": ["tx A", "tx B", "tx C", "tx D"],
        "follow_ups": ["baseline", "week 4", "week 8"],
        "network_nodes": ["tx A", "tx B", "tx C", "tx D"],
    }

    for seed in ("1", "2"):
        env = os.environ.copy()
        env["OMA_STUB_BACKEND"] = "1"
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
    dataset = ma_dataset.Dataset()
    studies = [
        ma_dataset.Study(1, name="Gamma", year=1988),
        ma_dataset.Study(2, name="Alpha", year=1977),
        ma_dataset.Study(3, name="Beta", year=1989),
    ]
    for study in studies:
        dataset.add_study(study)

    dataset.add_outcome(ma_dataset.Outcome("Mortality", meta_globals.BINARY))
    dataset.add_covariate(
        ma_dataset.Covariate("Dose", "continuous"),
        cov_values={"Gamma": 30, "Alpha": 10, "Beta": 20},
    )

    raw_events_by_name = {"Gamma": 3, "Alpha": 1, "Beta": 2}
    effects_by_name = {"Gamma": 0.3, "Alpha": 0.1, "Beta": 0.2}
    group_str = "-".join(meta_globals.DEFAULT_GROUP_NAMES)
    for study in dataset.studies:
        ma_unit = study.get_ma_unit("Mortality", "first")
        ma_unit.set_raw_data_for_groups(
            meta_globals.DEFAULT_GROUP_NAMES,
            [[raw_events_by_name[study.name], 10], [5, 10]],
        )
        ma_unit.set_effect_and_ci(
            "OR",
            group_str,
            effects_by_name[study.name],
            effects_by_name[study.name] - 0.01,
            effects_by_name[study.name] + 0.01,
            mult=1.96,
        )

    model = ma_data_table_model.DatasetModel(dataset=dataset, add_blank_study=False)
    model.current_outcome = "Mortality"
    model.current_effect = "OR"
    model.current_txs = meta_globals.DEFAULT_GROUP_NAMES
    model.update_column_indices()
    return model


def _study_names(model):
    return [study.name for study in model.dataset.studies]


def test_dataset_model_sort_studies_uses_python3_key_sort(monkeypatch):
    model = _sortable_dataset_model()
    monkeypatch.setattr(
        meta_py_r, "binary_convert_scale", lambda value, *args, **kwargs: value
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
