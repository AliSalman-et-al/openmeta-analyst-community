import os
import sys


sys.path.insert(0, os.path.abspath("src"))

import modern_compat

modern_compat.install()

from PyQt5 import QtCore

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
        value = model.data(model.index(0, column), QtCore.Qt.EditRole)

        assert value == ""
        assert not isinstance(value, QtCore.QVariant)


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
