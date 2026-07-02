import sys
from pathlib import Path

import pytest
from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "forms"))


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def test_calculator_cell_validators_accept_pyqt5_table_item_text():
    import binary_data_form
    import continuous_data_form
    import diagnostic_data_form

    assert binary_data_form.BinaryDataForm2._cell_data_not_valid(None, "  ") is None
    assert (
        binary_data_form.BinaryDataForm2._cell_data_not_valid(None, " 1 ")
        is None
    )
    assert (
        binary_data_form.BinaryDataForm2._cell_data_not_valid(None, "1.5")
        == "Expected a whole number (count), but a decimal value was entered."
    )

    assert (
        continuous_data_form.ContinuousDataForm._cell_data_not_valid(
            None, " 1.25 ", "mean"
        )
        is None
    )
    assert (
        continuous_data_form.ContinuousDataForm._cell_data_not_valid(None, "", "mean")
        is None
    )

    assert diagnostic_data_form.DiagnosticDataForm.cell_data_invalid(None, " 2 ") is None
    assert (
        diagnostic_data_form.DiagnosticDataForm.cell_data_invalid(None, "-1")
        == "Counts cannot be negative."
    )


def test_consistency_checker_uses_pyqt5_foreground_api(qapp):
    import calculator_routines as calc_fncs

    table = QTableWidget(3, 3)
    values = [
        [1, 2, 99],
        [3, 4, 7],
        [4, 6, 10],
    ]
    for row, row_values in enumerate(values):
        for col, value in enumerate(row_values):
            table.setItem(row, col, QTableWidgetItem(str(value)))

    checker = calc_fncs.ConsistencyChecker(
        fn_consistent=lambda: None,
        fn_inconsistent=lambda: None,
        table_2x2=table,
    )

    assert checker.run() == "Rows must sum!"
    assert table.item(0, 0).foreground().color() == calc_fncs.ERROR_COLOR

    table.item(0, 2).setText("3")
    assert checker.run() is None
    assert table.item(0, 0).foreground().color() == calc_fncs.OK_COLOR
