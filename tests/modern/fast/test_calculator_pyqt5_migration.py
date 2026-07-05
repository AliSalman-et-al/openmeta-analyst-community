import sys
from pathlib import Path

from PyQt5 import QtCore
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
)


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "forms"))


def test_calculator_cell_validators_accept_pyqt5_table_item_text():
    import binary_data_form
    import continuous_data_form
    import diagnostic_data_form

    assert binary_data_form.BinaryDataForm2._cell_data_not_valid(None, "  ") is None
    assert binary_data_form.BinaryDataForm2._cell_data_not_valid(None, " 1 ") is None
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

    assert (
        diagnostic_data_form.DiagnosticDataForm.cell_data_invalid(None, " 2 ") is None
    )
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


def test_continuous_imputation_uses_r_keys_not_visible_headers(qapp, monkeypatch):
    import continuous_data_form

    captured = []

    def fake_impute_cont_data(params, alpha):
        captured.append(params.copy())
        return {"succeeded": False}

    monkeypatch.setattr(
        continuous_data_form.meta_py_r, "impute_cont_data", fake_impute_cont_data
    )

    form = continuous_data_form.ContinuousDataForm.__new__(
        continuous_data_form.ContinuousDataForm
    )
    form.simple_table = QTableWidget(2, 8)
    form.simple_table.setHorizontalHeaderLabels(
        ["N", "Mean", "SD", "SE", "Variance", "Lower", "Upper", "P-Value"]
    )
    form.cur_groups = ["Group 1", "Group 2"]
    form.conf_level = 95.0
    form.ma_unit = object()

    form.simple_table.setItem(0, 0, QTableWidgetItem("10"))
    form.simple_table.setItem(0, 1, QTableWidgetItem("94"))
    form.simple_table.setItem(0, 4, QTableWidgetItem("2.5"))
    form.simple_table.setItem(0, 5, QTableWidgetItem("90"))
    form.simple_table.setItem(0, 6, QTableWidgetItem("98"))

    form.impute_data()

    assert captured[0] == {
        "n": 10.0,
        "mean": 94.0,
        "var": 2.5,
        "low": 90.0,
        "high": 98.0,
    }


def test_row_header_signals_are_restored_when_calculator_opening_raises(
    qapp, monkeypatch
):
    import ma_data_table_view

    class CalculatorOpenError(RuntimeError):
        pass

    class RaisingContinuousForm:
        def __init__(self, *args, **kwargs):
            raise CalculatorOpenError("boom")

    class FakeModel(QtCore.QAbstractTableModel):
        dataset = [object()]
        current_txs = ["Group 1", "Group 2"]
        current_effect = "MD"

        def rowCount(self, parent=QtCore.QModelIndex()):
            return 1

        def columnCount(self, parent=QtCore.QModelIndex()):
            return 1

        def data(self, index, role=QtCore.Qt.DisplayRole):
            return None

        def get_current_ma_unit_for_study(self, study_index):
            return FakeMAUnit()

        def get_cur_group_str(self):
            return "Group 1-Group 2"

        def get_current_outcome_type(self):
            return "continuous"

        def get_global_conf_level(self):
            return 95.0

    monkeypatch.setattr(
        ma_data_table_view.continuous_data_form,
        "ContinuousDataForm",
        RaisingContinuousForm,
    )

    view = ma_data_table_view.MADataTable()
    view.setModel(FakeModel())

    try:
        view.row_header_clicked(0)
    except CalculatorOpenError:
        pass

    assert not view.vert_header.signalsBlocked()


class FakeMAUnit:
    def __init__(self):
        from meta_globals import BINARY_ONE_ARM_METRICS, BINARY_TWO_ARM_METRICS

        self.effects_dict = {
            metric: {} for metric in BINARY_ONE_ARM_METRICS + BINARY_TWO_ARM_METRICS
        }
        self.raw_data = {"Group 1": [6, 20], "Group 2": [8, 22]}

    def get_effect_names(self):
        return list(self.effects_dict.keys())

    def get_effects_dict(self):
        return self.effects_dict

    def get_raw_data_for_group(self, group):
        return self.raw_data[group]

    def get_raw_data_for_groups(self, groups):
        values = []
        for group in groups:
            values.extend(self.raw_data[group])
        return values

    def get_effect_and_ci(self, metric, group_str, mult):
        return 1.0, 0.5, 2.0

    def set_effect_and_ci(self, *args, **kwargs):
        pass

    def set_effect(self, *args, **kwargs):
        pass

    def set_lower(self, *args, **kwargs):
        pass

    def set_upper(self, *args, **kwargs):
        pass


def test_binary_calculator_uses_table_headers_friendly_two_arm_metrics_and_clear_message(
    qapp, monkeypatch
):
    import binary_data_form

    monkeypatch.setattr(
        binary_data_form.meta_py_r, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        binary_data_form.meta_py_r, "binary_convert_scale", lambda x, *args, **kwargs: x
    )
    monkeypatch.setattr(
        binary_data_form.meta_py_r, "impute_bin_data", lambda data: {"FAIL": True}
    )

    form = binary_data_form.BinaryDataForm2(
        FakeMAUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        "OR",
        conf_level=95.0,
    )

    assert not form.raw_data_table.horizontalHeader().isHidden()
    assert not form.raw_data_table.verticalHeader().isHidden()
    assert [
        form.raw_data_table.horizontalHeaderItem(col).text()
        for col in range(form.raw_data_table.columnCount())
    ] == ["Event", "No Event", "Total"]
    assert [
        form.raw_data_table.verticalHeaderItem(row).text()
        for row in range(form.raw_data_table.rowCount())
    ] == ["Group 1", "Group 2", "Total"]
    assert form.raw_data_table.maximumHeight() >= form.raw_data_table.minimumHeight()
    assert [
        form.effect_cbo_box.itemData(index)
        for index in range(form.effect_cbo_box.count())
    ] == ["OR", "RD", "RR", "AS", "YUQ", "YUY"]
    assert "Odds Ratio (OR)" in [
        form.effect_cbo_box.itemText(index)
        for index in range(form.effect_cbo_box.count())
    ]
    assert (
        binary_data_form.INCONSISTENT_2X2_EDIT_MESSAGE
        == "Editing a single value would make the 2x2 table inconsistent. "
        "Use Clear Form and re-enter all four values."
    )


def test_binary_calculator_table_layout_uses_real_headers_and_visible_total_row(
    qapp, monkeypatch
):
    import binary_data_form

    monkeypatch.setattr(
        binary_data_form.meta_py_r, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        binary_data_form.meta_py_r, "binary_convert_scale", lambda x, *args, **kwargs: x
    )
    monkeypatch.setattr(
        binary_data_form.meta_py_r, "impute_bin_data", lambda data: {"FAIL": True}
    )

    form = binary_data_form.BinaryDataForm2(
        FakeMAUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        "OR",
        conf_level=95.0,
    )

    table = form.raw_data_table

    assert form.event_lbl_3.isHidden()
    assert table.maximumWidth() > table.minimumWidth()
    assert table.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding

    required_height = (
        table.horizontalHeader().height()
        + sum(table.rowHeight(row) for row in range(table.rowCount()))
        + 2 * table.frameWidth()
    )
    assert table.minimumHeight() >= required_height
    assert table.maximumHeight() >= required_height


def _assert_calculator_table_grid_fills_width(qapp, table):
    calculator = table.window()
    calculator.resize(calculator.width() + 180, calculator.height())
    calculator.show()
    qapp.processEvents()

    section_width = sum(
        table.horizontalHeader().sectionSize(column)
        for column in range(table.columnCount())
    )

    assert table.horizontalHeader().sectionResizeMode(0) == QHeaderView.Stretch
    assert section_width >= table.viewport().width() - 1


def _assert_calculator_table_content_columns_fill_width(qapp, table):
    calculator = table.window()
    calculator.resize(calculator.width() + 180, calculator.height())
    calculator.show()
    qapp.processEvents()

    header = table.horizontalHeader()
    section_width = sum(
        header.sectionSize(column) for column in range(table.columnCount())
    )

    assert header.sectionResizeMode(0) == QHeaderView.Interactive
    assert header.stretchLastSection()
    assert section_width >= table.viewport().width() - 1
    for column in range(table.columnCount()):
        assert table.columnWidth(column) >= table.sizeHintForColumn(column)


def test_binary_calculator_grid_columns_fill_expanded_table_width(qapp, monkeypatch):
    import binary_data_form

    monkeypatch.setattr(
        binary_data_form.meta_py_r, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        binary_data_form.meta_py_r, "binary_convert_scale", lambda x, *args, **kwargs: x
    )
    monkeypatch.setattr(
        binary_data_form.meta_py_r, "impute_bin_data", lambda data: {"FAIL": True}
    )

    form = binary_data_form.BinaryDataForm2(
        FakeMAUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        "OR",
        conf_level=95.0,
    )

    _assert_calculator_table_grid_fills_width(qapp, form.raw_data_table)


def test_binary_calculator_accepts_single_raw_count_edit_and_recomputes_margins(
    qapp, monkeypatch
):
    import binary_data_form

    warnings = []

    monkeypatch.setattr(
        binary_data_form.meta_py_r, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        binary_data_form.meta_py_r, "binary_convert_scale", lambda x, *args, **kwargs: x
    )
    monkeypatch.setattr(
        binary_data_form.meta_py_r, "impute_bin_data", lambda data: {"FAIL": True}
    )
    monkeypatch.setattr(
        binary_data_form.meta_py_r,
        "effect_for_study",
        lambda *args, **kwargs: {"calc_scale": (1.2, 0.8, 1.8)},
    )
    monkeypatch.setattr(
        binary_data_form.meta_py_r,
        "effect_triplet",
        lambda effect, scale, metric=None: effect[scale],
    )
    monkeypatch.setattr(
        binary_data_form.QMessageBox,
        "warning",
        lambda parent, title, message: warnings.append(message),
    )

    form = binary_data_form.BinaryDataForm2(
        FakeMAUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        "OR",
        conf_level=95.0,
    )

    table = form.raw_data_table
    form.current_item_data = 6
    table.item(0, 0).setText("7")
    qapp.processEvents()

    assert warnings == []
    assert table.item(0, 0).text() == "7"
    assert table.item(0, 1).text() == "14"
    assert table.item(0, 2).text() == "21"
    assert table.item(2, 0).text() == "15"
    assert table.item(2, 1).text() == "28"
    assert table.item(2, 2).text() == "43"
    assert form.ma_unit.get_raw_data_for_group("Group 1") == [7, 21]
    assert not form.inconsistencyLabel.isVisible()
    assert form.buttonBox.button(QDialogButtonBox.Ok).isEnabled()


class FakeDiagnosticMAUnit:
    def __init__(self):
        self.raw_data = [1, 2, 3, 4]
        self.tx_groups = {"Group 1-Group 2": FakeDiagnosticGroup(self.raw_data)}

    def get_raw_data_for_group(self, group):
        return self.raw_data

    def get_effect_and_ci(self, metric, group_str, mult):
        return None, None, None

    def set_effect_and_ci(self, *args, **kwargs):
        pass

    def set_effect(self, *args, **kwargs):
        pass

    def set_lower(self, *args, **kwargs):
        pass

    def set_upper(self, *args, **kwargs):
        pass


class FakeDiagnosticGroup:
    def __init__(self, raw_data):
        self.raw_data = raw_data


def test_diagnostic_calculator_grid_columns_fill_expanded_table_width(
    qapp, monkeypatch
):
    import diagnostic_data_form

    monkeypatch.setattr(
        diagnostic_data_form.meta_py_r, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        diagnostic_data_form.meta_py_r,
        "diagnostic_convert_scale",
        lambda x, *args, **kwargs: x,
    )
    monkeypatch.setattr(
        diagnostic_data_form.meta_py_r,
        "impute_diag_data",
        lambda data: {"TP": None, "FP": None, "FN": None, "TN": None},
    )

    form = diagnostic_data_form.DiagnosticDataForm(
        FakeDiagnosticMAUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        conf_level=95.0,
    )

    _assert_calculator_table_grid_fills_width(qapp, form.two_by_two_table)


def test_diagnostic_calculator_accepts_single_raw_count_edit_and_recomputes_margins(
    qapp, monkeypatch
):
    import diagnostic_data_form

    warnings = []

    monkeypatch.setattr(
        diagnostic_data_form.meta_py_r, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        diagnostic_data_form.meta_py_r,
        "diagnostic_convert_scale",
        lambda x, *args, **kwargs: x,
    )
    monkeypatch.setattr(
        diagnostic_data_form.meta_py_r,
        "impute_diag_data",
        lambda data: {"TP": None, "FP": None, "FN": None, "TN": None},
    )
    monkeypatch.setattr(
        diagnostic_data_form.meta_py_r,
        "diagnostic_effects_for_study",
        lambda *args, metrics, **kwargs: {
            metric: {"calc_scale": (0.5, 0.4, 0.6)} for metric in metrics
        },
    )
    monkeypatch.setattr(
        diagnostic_data_form.meta_py_r,
        "effect_triplet",
        lambda effect, scale, metric=None: effect[scale],
    )
    monkeypatch.setattr(
        diagnostic_data_form.QMessageBox,
        "warning",
        lambda parent, title, message: warnings.append(message),
    )

    form = diagnostic_data_form.DiagnosticDataForm(
        FakeDiagnosticMAUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        conf_level=95.0,
    )

    table = form.two_by_two_table
    form.current_item_data = 1
    table.item(0, 0).setText("5")
    qapp.processEvents()

    assert warnings == []
    assert table.item(0, 0).text() == "5"
    assert table.item(0, 2).text() == "8"
    assert table.item(1, 2).text() == "6"
    assert table.item(2, 0).text() == "7"
    assert table.item(2, 1).text() == "7"
    assert table.item(2, 2).text() == "14"
    assert form.ma_unit.raw_data == [5.0, 2.0, 3.0, 4.0]
    assert not form.inconsistencyLabel.isVisible()
    assert form.buttonBox.button(QDialogButtonBox.Ok).isEnabled()


class FakeContinuousMAUnit:
    def __init__(self):
        self.raw_data = {
            "Group 1": [10, 94, 2],
            "Group 2": [12, 90, 3],
        }

    def get_effect_names(self):
        return ["ROM"]

    def get_raw_data_for_group(self, group):
        return self.raw_data[group]

    def get_raw_data_for_groups(self, groups):
        values = []
        for group in groups:
            values.extend(self.raw_data[group])
        return values

    def get_se(self, *args, **kwargs):
        return None

    def get_effect_and_ci(self, *args, **kwargs):
        return None, None, None

    def set_effect_and_ci(self, *args, **kwargs):
        pass

    def set_effect(self, *args, **kwargs):
        pass

    def set_lower(self, *args, **kwargs):
        pass

    def set_upper(self, *args, **kwargs):
        pass


def test_continuous_calculator_grid_columns_fill_expanded_table_width(
    qapp, monkeypatch
):
    import continuous_data_form

    monkeypatch.setattr(
        continuous_data_form.meta_py_r, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        continuous_data_form.meta_py_r,
        "continuous_convert_scale",
        lambda x, *args, **kwargs: x,
    )
    monkeypatch.setattr(
        continuous_data_form.meta_py_r,
        "impute_cont_data",
        lambda data, alpha: {"succeeded": False, "comment": "stub"},
    )

    form = continuous_data_form.ContinuousDataForm(
        FakeContinuousMAUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        "ROM",
        conf_level=95.0,
    )

    _assert_calculator_table_content_columns_fill_width(qapp, form.simple_table)


def test_continuous_calculator_keeps_long_imputed_values_compact(qapp, monkeypatch):
    import continuous_data_form
    import qt_layout

    long_imputed = {
        "n": 10,
        "mean": 92.89482413483651,
        "sd": 2.604729426373378,
        "se": 8.75360686626884e-310,
        "var": 3.4972319657703745e-249,
        "pval": 0.12345678912345678,
        "low": 91.11111111111111,
        "high": 94.99999999999999,
    }

    monkeypatch.setattr(
        continuous_data_form.meta_py_r, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        continuous_data_form.meta_py_r,
        "continuous_convert_scale",
        lambda x, *args, **kwargs: x,
    )
    monkeypatch.setattr(
        continuous_data_form.meta_py_r,
        "impute_cont_data",
        lambda data, alpha: {"succeeded": True, "output": long_imputed},
    )

    form = continuous_data_form.ContinuousDataForm(
        FakeContinuousMAUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        "ROM",
        conf_level=95.0,
    )

    form.show()
    qapp.processEvents()

    displayed_values = [
        form.simple_table.item(0, column).text()
        for column in range(form.simple_table.columnCount())
    ]
    assert "2.604729426373378" not in displayed_values
    assert "3.4972319657703745e-249" not in displayed_values
    assert form.simple_table.item(0, 2).text() == "2.6047"

    natural_width = sum(
        max(
            form.simple_table.horizontalHeader().sectionSizeHint(column),
            form.simple_table.sizeHintForColumn(column),
        )
        for column in range(form.simple_table.columnCount())
    )
    assert form.simple_table.minimumWidth() < natural_width * 2
    assert form.minimumWidth() < qt_layout.ANALYSIS_DIALOG_MINIMUM_WIDTH * 2
