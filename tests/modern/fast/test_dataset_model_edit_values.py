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
    dataset = ma_dataset.Dataset()
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
