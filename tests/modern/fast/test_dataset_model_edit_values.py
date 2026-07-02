import os
import sys


sys.path.insert(0, os.path.abspath("src"))

import modern_compat

modern_compat.install()

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

import ma_data_table_model
import ma_dataset
import meta_globals


def _diagnostic_model_with_empty_cells():
    dataset = ma_dataset.Dataset(is_diag=True)
    study = ma_dataset.Study(1, name="Alpha", year=None)
    outcome = ma_dataset.Outcome("Accuracy", meta_globals.DIAGNOSTIC)
    study.add_outcome(outcome)
    dataset.add_study(study)
    dataset.outcome_names_to_follow_ups["Accuracy"] = {0: "first"}

    model = ma_data_table_model.DatasetModel(dataset=dataset, add_blank_study=False)
    model.current_outcome = "Accuracy"
    model.current_txs = ["test 1"]
    model.update_column_indices()
    return model


def _binary_model_with_blank_study():
    dataset = ma_dataset.Dataset()
    blank_study = ma_dataset.Study(1, name="", year=None, include=False)
    dataset.add_study(blank_study)
    dataset.add_outcome(ma_dataset.Outcome("Mortality", meta_globals.BINARY))

    model = ma_data_table_model.DatasetModel(dataset=dataset, add_blank_study=False)
    model.current_outcome = "Mortality"
    model.current_effect = "OR"
    model.current_txs = meta_globals.DEFAULT_GROUP_NAMES
    model.update_column_indices()
    return model


def _model_with_real_study_and_empty_new_entry_row(data_type):
    dataset = ma_dataset.Dataset(is_diag=data_type == meta_globals.DIAGNOSTIC)
    study = ma_dataset.Study(1, name="Alpha", year=2020)
    outcome = ma_dataset.Outcome("Outcome", data_type)
    dataset.add_study(study)
    dataset.add_outcome(outcome)

    model = ma_data_table_model.DatasetModel(dataset=dataset, add_blank_study=True)
    model.current_outcome = "Outcome"
    model.current_effect = "OR" if data_type == meta_globals.BINARY else "MD"
    model.current_txs = (
        ["test 1"]
        if data_type == meta_globals.DIAGNOSTIC
        else meta_globals.DEFAULT_GROUP_NAMES
    )
    model.update_column_indices()
    return model


def _continuous_model_with_named_study():
    dataset = ma_dataset.Dataset()
    study = ma_dataset.Study(1, name="Alpha", year=None)
    dataset.add_study(study)
    dataset.add_outcome(ma_dataset.Outcome("Score", meta_globals.CONTINUOUS))

    model = ma_data_table_model.DatasetModel(dataset=dataset, add_blank_study=False)
    model.current_outcome = "Score"
    model.current_effect = "MD"
    model.current_txs = meta_globals.DEFAULT_GROUP_NAMES
    model.update_column_indices()
    return model


def test_empty_editable_cells_return_blank_edit_text():
    model = _diagnostic_model_with_empty_cells()
    ma_unit = model.get_current_ma_unit_for_study(0)
    ma_unit.tx_groups["test 1"].raw_data[0] = None
    model.dataset.add_covariate(ma_dataset.Covariate("Dose", "continuous"))
    model.update_column_indices()

    editable_columns = [
        model.YEAR,
        model.RAW_DATA[0],
        model.columnCount() - 1,
    ]

    for column in editable_columns:
        value = model.data(model.index(0, column), Qt.EditRole)

        assert value == ""


def test_normal_study_cells_do_not_override_view_alternating_row_background():
    model = _continuous_model_with_named_study()

    assert model.data(model.index(0, model.NAME), Qt.BackgroundColorRole) is None
    assert model.data(model.index(0, model.RAW_DATA[0]), Qt.BackgroundColorRole) is None
    assert model.data(model.index(0, model.OUTCOMES[0]), Qt.BackgroundColorRole) == QColor(
        Qt.yellow
    )


def test_one_arm_inactive_raw_data_cells_keep_disabled_background():
    model = _continuous_model_with_named_study()
    model.current_effect = "TX Mean"

    assert model.data(model.index(0, model.RAW_DATA[3]), Qt.BackgroundColorRole) == QColor(
        Qt.gray
    )
    assert model.data(model.index(0, model.RAW_DATA[0]), Qt.BackgroundColorRole) is None


def test_empty_new_entry_row_does_not_render_populated_study_chrome():
    for data_type in (
        meta_globals.BINARY,
        meta_globals.CONTINUOUS,
        meta_globals.DIAGNOSTIC,
    ):
        model = _model_with_real_study_and_empty_new_entry_row(data_type)
        blank_row = 1

        assert model.headerData(blank_row, Qt.Vertical, Qt.DecorationRole) is None
        assert (
            model.data(model.index(blank_row, model.INCLUDE_STUDY), Qt.CheckStateRole)
            is None
        )

        for column in model.OUTCOMES:
            assert (
                model.data(model.index(blank_row, column), Qt.BackgroundColorRole)
                is None
            )


def test_named_new_entry_row_keeps_populated_study_chrome():
    model = _model_with_real_study_and_empty_new_entry_row(meta_globals.BINARY)
    model.dataset.studies[1].name = "Beta"
    model.dataset.studies[1].include = True

    assert model.headerData(1, Qt.Vertical, Qt.DecorationRole).isNull() is False
    assert (
        model.data(model.index(1, model.INCLUDE_STUDY), Qt.CheckStateRole)
        == Qt.Checked
    )
    assert model.data(model.index(1, model.OUTCOMES[0]), Qt.BackgroundColorRole) == QColor(
        Qt.yellow
    )


def test_raw_data_edit_on_placeholder_row_emits_study_name_error():
    model = _diagnostic_model_with_empty_cells()
    errors = []
    model.dataError.connect(errors.append)

    assert model.setData(model.index(1, model.RAW_DATA[0]), "90") is False

    assert errors == ["Please enter a study name before entering study data."]


def test_direct_effect_edit_on_unnamed_study_emits_study_name_error(monkeypatch):
    model = _binary_model_with_blank_study()
    errors = []
    model.dataError.connect(errors.append)
    monkeypatch.setattr(
        ma_data_table_model.meta_py_r,
        "binary_convert_scale",
        lambda value, *args, **kwargs: value,
    )

    assert model.setData(model.index(0, model.OUTCOMES[0]), "1.5") is False

    study = model.dataset.studies[0]
    ma_unit = model.get_current_ma_unit_for_study(0)
    assert errors == ["Please enter a study name before entering study data."]
    assert study.include is False
    assert ma_unit.get_entered_effect_and_ci("OR", model.get_cur_group_str()) == (
        None,
        None,
        None,
    )


def test_unnamed_study_cannot_be_manually_included():
    model = _binary_model_with_blank_study()
    errors = []
    model.dataError.connect(errors.append)

    assert model.setData(model.index(0, model.INCLUDE_STUDY), True) is False

    assert errors == ["Please enter a study name before entering study data."]
    assert model.dataset.studies[0].include is False


def test_named_direct_effect_entry_still_auto_includes_study(monkeypatch):
    model = _binary_model_with_blank_study()
    model.dataset.studies[0].name = "Alpha"
    monkeypatch.setattr(
        ma_data_table_model.meta_py_r,
        "binary_convert_scale",
        lambda value, *args, **kwargs: value,
    )

    assert model.setData(model.index(0, model.OUTCOMES[0]), "1.5") is True
    assert model.setData(model.index(0, model.OUTCOMES[1]), "0.8") is True
    assert model.setData(model.index(0, model.OUTCOMES[2]), "2.8") is True

    assert model.dataset.studies[0].include is True


def test_empty_existing_study_name_emits_study_name_error():
    model = _diagnostic_model_with_empty_cells()
    errors = []
    model.dataError.connect(errors.append)

    assert model.setData(model.index(0, model.NAME), "") is False

    assert errors == ["Please enter a study name before entering study data."]
    assert model.dataset.studies[0].name == "Alpha"


def test_study_name_edit_on_placeholder_row_creates_study():
    model = _diagnostic_model_with_empty_cells()

    assert model.setData(model.index(1, model.NAME), "Beta") is True

    assert model.dataset.studies[1].name == "Beta"
    assert len(model.dataset.studies) == 3
    assert model.dataset.studies[2].name == ""
    assert model.dataset.studies[2].include is False


def test_invalid_continuous_covariate_edit_emits_error_and_preserves_value():
    model = _diagnostic_model_with_empty_cells()
    model.dataset.add_covariate(
        ma_dataset.Covariate("Dose", "continuous"), {"Alpha": 5.5}
    )
    model.update_column_indices()
    errors = []
    model.dataError.connect(errors.append)
    covariate_index = model.index(0, model.columnCount() - 1)

    assert model.setData(covariate_index, "not numeric") is False

    assert errors == ["Covariate values for continuous covariates need to be numeric."]
    assert model.dataset.studies[0].covariate_dict["Dose"] == 5.5


def test_diagnostic_raw_count_edit_accepts_scalar_metric_effects(monkeypatch):
    model = _diagnostic_model_with_empty_cells()
    ma_unit = model.get_current_ma_unit_for_study(0)
    group_str = model.get_cur_group_str()
    ma_unit.tx_groups[group_str].raw_data = [19.0, 10.0, 1.0, 81.0]
    errors = []
    model.dataError.connect(errors.append)

    monkeypatch.setattr(
        ma_data_table_model.meta_py_r,
        "diagnostic_convert_scale",
        lambda value, *args, **kwargs: value,
    )

    def diagnostic_effects_for_study(*args, **kwargs):
        return {
            "Sens": {"calc_scale": 0.75},
            "Spec": {"calc_scale": [0.95, 0.88, 0.99]},
            "PLR": {"calc_scale": [15.0]},
            "NLR": {"calc_scale": [0.25, 0.12, 0.50]},
            "DOR": {"calc_scale": [60.0, 25.0, 120.0]},
        }

    monkeypatch.setattr(
        ma_data_table_model.meta_py_r,
        "diagnostic_effects_for_study",
        diagnostic_effects_for_study,
    )

    assert model.setData(model.index(0, model.RAW_DATA[0]), "20") is True

    assert errors == []
    assert ma_unit.tx_groups[group_str].raw_data[0] == 20.0
    assert ma_unit.get_effect_and_ci("Sens", group_str, model.get_mult()) == (
        0.75,
        None,
        None,
    )
    assert ma_unit.get_entered_effect_and_ci("Spec", group_str) == (
        0.95,
        0.88,
        0.99,
    )


def test_binary_raw_count_edit_accepts_scalar_metric_effect(monkeypatch):
    model = _binary_model_with_blank_study()
    model.dataset.studies[0].name = "Alpha"
    ma_unit = model.get_current_ma_unit_for_study(0)
    group_str = model.get_cur_group_str()
    ma_unit.tx_groups[model.current_txs[0]].raw_data = [3.0, 10.0]
    ma_unit.tx_groups[model.current_txs[1]].raw_data = [2.0, 10.0]
    errors = []
    model.dataError.connect(errors.append)

    monkeypatch.setattr(
        ma_data_table_model.meta_py_r,
        "binary_convert_scale",
        lambda value, *args, **kwargs: value,
    )
    monkeypatch.setattr(
        ma_data_table_model.meta_py_r,
        "effect_for_study",
        lambda *args, **kwargs: {"calc_scale": 0.5},
    )

    assert model.setData(model.index(0, model.RAW_DATA[0]), "4") is True

    assert errors == []
    assert ma_unit.tx_groups[model.current_txs[0]].raw_data[0] == 4.0
    assert ma_unit.get_effect_and_ci("OR", group_str, model.get_mult()) == (
        0.5,
        None,
        None,
    )


def test_continuous_raw_count_edit_accepts_scalar_metric_effect(monkeypatch):
    model = _continuous_model_with_named_study()
    ma_unit = model.get_current_ma_unit_for_study(0)
    group_str = model.get_cur_group_str()
    ma_unit.tx_groups[model.current_txs[0]].raw_data = [10.0, 5.0, 1.0]
    ma_unit.tx_groups[model.current_txs[1]].raw_data = [12.0, 4.0, 1.5]
    errors = []
    model.dataError.connect(errors.append)

    monkeypatch.setattr(
        ma_data_table_model.meta_py_r,
        "continuous_convert_scale",
        lambda value, *args, **kwargs: value,
    )
    monkeypatch.setattr(
        ma_data_table_model.meta_py_r,
        "continuous_effect_for_study",
        lambda *args, **kwargs: {"calc_scale": 1.25},
    )

    assert model.setData(model.index(0, model.RAW_DATA[1]), "5.5") is True

    assert errors == []
    assert ma_unit.tx_groups[model.current_txs[0]].raw_data[1] == 5.5
    assert ma_unit.get_effect_and_ci("MD", group_str, model.get_mult()) == (
        1.25,
        None,
        None,
    )


def test_diagnostic_raw_count_edit_rolls_back_when_effect_calculation_fails(
    monkeypatch,
):
    model = _diagnostic_model_with_empty_cells()
    ma_unit = model.get_current_ma_unit_for_study(0)
    group_str = model.get_cur_group_str()
    ma_unit.tx_groups[group_str].raw_data = [19.0, 10.0, 1.0, 81.0]
    ma_unit.set_effect_and_ci("Sens", group_str, 0.66, 0.50, 0.80, model.get_mult())
    model.dataset.studies[0].include = True
    errors = []
    model.dataError.connect(errors.append)

    def diagnostic_effects_for_study(*args, **kwargs):
        raise RuntimeError("simulated diagnostic calculation failure")

    monkeypatch.setattr(
        ma_data_table_model.meta_py_r,
        "diagnostic_effects_for_study",
        diagnostic_effects_for_study,
    )

    assert model.setData(model.index(0, model.RAW_DATA[0]), "20") is False

    assert ma_unit.tx_groups[group_str].raw_data == [19.0, 10.0, 1.0, 81.0]
    assert ma_unit.get_entered_effect_and_ci("Sens", group_str) == (
        0.66,
        0.50,
        0.80,
    )
    assert model.dataset.studies[0].include is True
    assert errors == [
        "Could not compute study effects from the edited raw data: "
        "simulated diagnostic calculation failure"
    ]


def test_effect_normalizer_preserves_triplets_and_expands_scalars():
    effect = ma_data_table_model.meta_py_r.normalize_effect_result(
        {"calc_scale": 1.25, "display_scale": [1.25, 1.0, 1.5]},
    )
    effects = ma_data_table_model.meta_py_r.normalize_diagnostic_effects(
        {
            "Sens": {"calc_scale": 0.75},
            "Spec": {"calc_scale": [0.95, 0.88, 0.99]},
            "PLR": {"calc_scale": [15.0]},
        }
    )

    assert effect["calc_scale"] == (1.25, None, None)
    assert effect["display_scale"] == (1.25, 1.0, 1.5)
    assert effects["Sens"]["calc_scale"] == (0.75, None, None)
    assert effects["Spec"]["calc_scale"] == (0.95, 0.88, 0.99)
    assert effects["PLR"]["calc_scale"] == (15.0, None, None)
