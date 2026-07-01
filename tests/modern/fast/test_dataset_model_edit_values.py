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
