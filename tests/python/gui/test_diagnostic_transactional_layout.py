import os
from pathlib import Path
from typing import cast

import pytest
from PyQt6 import QtCore, QtGui, QtWidgets

from rc_metastudio import adaptive_window



REPO_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault(
    "RCMS_QT6_BUILD_ROOT", str(REPO_ROOT / "build" / "qt6-verification")
)

from rc_metastudio.qt6_ui import prepare_generated_ui_imports
from test_types import key_click, required

prepare_generated_ui_imports()


AVAILABLE = QtCore.QRect(20, 30, 800, 600)


class FakeDiagnosticGroup:
    def __init__(self, raw_data):
        self.raw_data = raw_data


class FakeDiagnosticAnalysisUnit:
    def __init__(self, raw_data=None, effects=None):
        self.raw_data = list(raw_data or [12, 3, 4, 21])
        self.effects = dict(effects or {})
        self.groups = {"Group 1-Group 2": FakeDiagnosticGroup(self.raw_data)}

    def get_raw_data_for_group(self, _group):
        return self.raw_data

    def get_raw_data_for_groups(self, _groups):
        return list(self.raw_data)

    def get_effect_and_ci(self, metric, _group, _mult):
        return self.effects.get(metric, (None, None, None))

    def set_effect_and_ci(self, metric, _group, est, low, high, **_kwargs):
        self.effects[metric] = (est, low, high)

    def set_effect(self, metric, _group, value, **_kwargs):
        _old, low, high = self.effects.get(metric, (None, None, None))
        self.effects[metric] = (value, low, high)

    def set_lower(self, metric, _group, value, **_kwargs):
        est, _old, high = self.effects.get(metric, (None, None, None))
        self.effects[metric] = (est, value, high)

    def set_upper(self, metric, _group, value, **_kwargs):
        est, low, _old = self.effects.get(metric, (None, None, None))
        self.effects[metric] = (est, low, value)


class FakeDiagnosticModel:
    def __init__(self, raw_available=False, entered_effects=()):
        self.raw_available = raw_available
        self.entered_effects = set(entered_effects)

    def included_studies_have_raw_data(self):
        return self.raw_available

    def included_studies_have_point_estimates(self, effect):
        return effect in self.entered_effects

    def get_confidence_level(self):
        return 95.0


def _open_data_dialog(
    monkeypatch, raw_data=None, effects=None, imputed=None, available=AVAILABLE
):
    from rc_metastudio import diagnostic_data_dialog

    app = required(
        QtWidgets.QApplication.instance() or QtWidgets.QApplication([]), "application"
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.adaptive_window,
        "available_geometry_for_window",
        lambda _window: QtCore.QRect(available),
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge,
        "get_confidence_multiplier_from_r",
        lambda _conf: 1.96,
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge,
        "diagnostic_convert_scale",
        lambda value, *_args, **_kwargs: value,
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge,
        "impute_diagnostic_data",
        lambda _data: imputed or {"TP": None, "FP": None, "FN": None, "TN": None},
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge,
        "diagnostic_effects_for_study",
        lambda *_args, metrics, **_kwargs: {
            metric: {"calc_scale": (0.8, 0.7, 0.9)} for metric in metrics
        },
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge,
        "effect_triplet",
        lambda effect, scale, metric=None: effect[scale],
    )
    dialog = diagnostic_data_dialog.DiagnosticDataDialog(
        FakeDiagnosticAnalysisUnit(raw_data=raw_data, effects=effects),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        confidence_level=95.0,
    )
    return app, dialog


def _open_metrics_dialog(monkeypatch, model):
    from rc_metastudio import diagnostic_metrics_dialog

    app = required(
        QtWidgets.QApplication.instance() or QtWidgets.QApplication([]), "application"
    )
    monkeypatch.setattr(
        diagnostic_metrics_dialog.adaptive_window,
        "available_geometry_for_window",
        lambda _window: QtCore.QRect(AVAILABLE),
    )
    dialog = diagnostic_metrics_dialog.DiagnosticMetricsDialog(model)
    return app, dialog


def test_diagnostic_data_declares_transactional_overflow_and_reachable_actions(
    monkeypatch,
):
    app, dialog = _open_data_dialog(monkeypatch)
    try:
        dialog.show()
        app.processEvents()

        assert (
            adaptive_window.adaptive_window_state(dialog).role
            is adaptive_window.WindowRole.TRANSACTIONAL
        )
        assert isinstance(dialog.content_scroll, QtWidgets.QScrollArea)
        assert dialog.content_scroll.widgetResizable()
        assert not dialog.content_scroll.isAncestorOf(dialog.buttonBox)
        assert required(dialog.layout(), "dialog layout").indexOf(dialog.buttonBox) >= 0
        assert AVAILABLE.contains(dialog.frameGeometry())
        assert (
            dialog.two_by_two_table.horizontalScrollBarPolicy()
            == QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        assert (
            dialog.two_by_two_table.horizontalHeader().sectionResizeMode(0)
            == QtWidgets.QHeaderView.ResizeMode.Interactive
        )
    finally:
        dialog.close()
        app.processEvents()


def test_diagnostic_data_keyboard_and_accessibility_contract(monkeypatch):
    app, dialog = _open_data_dialog(monkeypatch)
    try:
        dialog.show()
        app.processEvents()
        ok = dialog.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        assert dialog.focusWidget() is dialog.two_by_two_table
        assert ok.isDefault()
        assert dialog.prevalence_lbl.buddy() is dialog.prevalence_text_box
        assert dialog.effect_metric_label.buddy() is dialog.effect_combo_box
        assert dialog.label_14.buddy() is dialog.effect_text_box
        assert dialog.two_by_two_table.accessibleName() == (
            "Diagnostic two by two counts"
        )

        dialog.effect_combo_box.setFocus()
        key_click(dialog.effect_combo_box, QtCore.Qt.Key.Key_Tab)
        assert dialog.focusWidget() is dialog.effect_text_box

        key_click(dialog, QtCore.Qt.Key.Key_Escape)
        assert dialog.result() == QtWidgets.QDialog.DialogCode.Rejected
    finally:
        dialog.close()
        app.processEvents()


@pytest.mark.parametrize("size", [(1440, 900), (1024, 640), (800, 600)])
def test_count_entry_preserves_diagnostic_behavior_without_root_growth(
    monkeypatch, size
):
    from rc_metastudio import diagnostic_data_dialog

    available = QtCore.QRect(20, 30, *size)
    app, dialog = _open_data_dialog(monkeypatch, available=available)
    warnings = []
    monkeypatch.setattr(
        diagnostic_data_dialog.QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(message),
    )
    try:
        dialog.show()
        app.processEvents()
        settled = QtCore.QRect(dialog.frameGeometry())

        dialog.current_item_data = 12
        dialog.two_by_two_table.item(0, 0).setText("15")
        app.processEvents()

        assert warnings == []
        assert dialog.analysis_unit.raw_data == [15.0, 3.0, 4.0, 21.0]
        assert dialog.two_by_two_table.item(0, 2).text() == "19"
        assert dialog.two_by_two_table.item(2, 2).text() == "43"
        assert dialog.analysis_unit.effects["Sens"] == (0.8, 0.7, 0.9)
        assert dialog.frameGeometry() == settled
        assert available.contains(dialog.frameGeometry())
        assert dialog.frameGeometry().width() <= int(available.width() * 0.9) + 2
        assert dialog.frameGeometry().height() <= int(available.height() * 0.9) + 2
        assert dialog.buttonBox.isVisible()
    finally:
        dialog.close()
        app.processEvents()


def test_entered_effect_switching_is_semantically_sized_and_geometry_stable(
    monkeypatch,
):
    app, dialog = _open_data_dialog(
        monkeypatch,
        raw_data=[None, None, None, None],
        effects={"Sens": (0.75, 0.60, 0.85), "Spec": (0.80, 0.70, 0.90)},
    )
    try:
        dialog.show()
        app.processEvents()
        settled = QtCore.QRect(dialog.frameGeometry())

        spec_index = dialog.effect_combo_box.findText("Spec")
        dialog.effect_combo_box.setCurrentIndex(spec_index)
        app.processEvents()

        assert dialog.current_effect == "Spec"
        assert [
            dialog.effect_text_box.text(),
            dialog.lower_text_box.text(),
            dialog.upper_text_box.text(),
        ] == ["0.8", "0.7", "0.9"]
        for field in (
            dialog.prevalence_text_box,
            dialog.effect_text_box,
            dialog.lower_text_box,
            dialog.upper_text_box,
        ):
            required = field.fontMetrics().horizontalAdvance("1.0000")
            assert field.minimumWidth() >= required
        assert dialog.frameGeometry() == settled
        app.processEvents()
        assert dialog.frameGeometry() == settled
    finally:
        dialog.close()
        app.processEvents()


def test_back_calculation_updates_counts_without_root_growth(monkeypatch):
    app, dialog = _open_data_dialog(
        monkeypatch,
        raw_data=[None, None, None, None],
        effects={"Sens": (0.75, 0.60, 0.85), "Spec": (0.80, 0.70, 0.90)},
        imputed={"TP": 12, "FP": 4, "FN": 3, "TN": 21},
    )
    try:
        dialog.show()
        app.processEvents()
        settled = QtCore.QRect(dialog.frameGeometry())
        assert dialog.back_calculate_button.isEnabled()

        QtWidgets.QApplication.processEvents()
        dialog.back_calculate_button.click()
        app.processEvents()

        assert dialog.analysis_unit.raw_data == [12.0, 3.0, 4.0, 21.0]
        assert [
            dialog.two_by_two_table.item(row, column).text()
            for row in range(2)
            for column in range(2)
        ] == ["12", "4", "3", "21"]
        assert dialog.frameGeometry() == settled
        assert AVAILABLE.contains(dialog.frameGeometry())
    finally:
        dialog.close()
        app.processEvents()


def test_large_font_count_overflow_and_focus_stay_inside_content(monkeypatch):
    app = cast(
        QtWidgets.QApplication,
        required(
            QtWidgets.QApplication.instance() or QtWidgets.QApplication([]),
            "application",
        ),
    )
    old_font = app.font()
    enlarged = QtGui.QFont(old_font)
    enlarged.setPointSize(max(16, old_font.pointSize() + 6))
    app.setFont(enlarged)
    app, dialog = _open_data_dialog(monkeypatch)
    try:
        dialog.show()
        dialog.resize(320, 300)
        app.processEvents()
        dialog.current_item_data = 12
        dialog.two_by_two_table.item(0, 0).setText("999999999999999999")
        app.processEvents()

        assert AVAILABLE.contains(dialog.frameGeometry())
        assert dialog.two_by_two_table.horizontalScrollBar().maximum() > 0
        assert dialog.two_by_two_table.item(0, 0).text()
        header = dialog.two_by_two_table.horizontalHeader()
        for column in range(dialog.two_by_two_table.columnCount()):
            assert header.sectionSize(column) >= (
                dialog.two_by_two_table.sizeHintForColumn(column)
            )
        table = dialog.two_by_two_table
        table.horizontalScrollBar().setValue(table.horizontalScrollBar().maximum())
        table.scrollToItem(table.item(0, 0))
        app.processEvents()
        assert (
            table.viewport().rect().intersects(table.visualItemRect(table.item(0, 0)))
        )
        dialog.upper_text_box.setFocus()
        app.processEvents()
        mapped = dialog.upper_text_box.mapTo(
            dialog.content_scroll.viewport(), QtCore.QPoint()
        )
        assert (
            dialog.content_scroll.viewport()
            .rect()
            .intersects(QtCore.QRect(mapped, dialog.upper_text_box.size()))
        )
        assert dialog.buttonBox.isVisible()
    finally:
        app.setFont(old_font)
        dialog.close()
        app.processEvents()


@pytest.mark.parametrize("initially_blocked", [False, True])
def test_diagnostic_set_val_restores_table_signal_state(initially_blocked):
    from rc_metastudio import diagnostic_data_dialog

    app = cast(
        QtWidgets.QApplication,
        required(
            QtWidgets.QApplication.instance() or QtWidgets.QApplication([]),
            "application",
        ),
    )
    table = QtWidgets.QTableWidget(1, 1)

    class StubDialog:
        two_by_two_table = table

        @staticmethod
        def _raw_count_cell_is_editable(_row, _col):
            return True

    table.blockSignals(initially_blocked)
    diagnostic_data_dialog.DiagnosticDataDialog._set_val(
        cast(diagnostic_data_dialog.DiagnosticDataDialog, StubDialog()), 0, 0, 3
    )

    assert table.signalsBlocked() is initially_blocked
    table.deleteLater()
    app.processEvents()


def test_diagnostic_set_val_restores_blocked_state_when_item_update_fails(monkeypatch):
    from rc_metastudio import diagnostic_data_dialog

    app = cast(
        QtWidgets.QApplication,
        required(
            QtWidgets.QApplication.instance() or QtWidgets.QApplication([]),
            "application",
        ),
    )
    table = QtWidgets.QTableWidget(1, 1)
    table.setItem(0, 0, QtWidgets.QTableWidgetItem("old"))

    class StubDialog:
        two_by_two_table = table

        @staticmethod
        def _raw_count_cell_is_editable(_row, _col):
            return True

    def fail(*_args, **_kwargs):
        raise RuntimeError("injected item update failure")

    monkeypatch.setattr(diagnostic_data_dialog, "required", fail)
    table.blockSignals(True)
    with pytest.raises(RuntimeError, match="injected item update failure"):
        diagnostic_data_dialog.DiagnosticDataDialog._set_val(
            cast(diagnostic_data_dialog.DiagnosticDataDialog, StubDialog()), 0, 0, 3
        )

    assert table.signalsBlocked()
    table.deleteLater()
    app.processEvents()


def test_invalid_count_guidance_wraps_and_remains_reachable(monkeypatch):
    from rc_metastudio import diagnostic_data_dialog

    app = cast(
        QtWidgets.QApplication,
        required(
            QtWidgets.QApplication.instance() or QtWidgets.QApplication([]),
            "application",
        ),
    )
    old_font = app.font()
    enlarged = QtGui.QFont(old_font)
    enlarged.setPointSize(max(16, old_font.pointSize() + 6))
    app.setFont(enlarged)
    app, dialog = _open_data_dialog(monkeypatch)
    warnings = []
    monkeypatch.setattr(
        diagnostic_data_dialog.QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(message),
    )
    try:
        dialog.show()
        dialog.resize(dialog.width(), 280)
        app.processEvents()
        dialog.current_item_data = 12
        dialog.two_by_two_table.item(0, 0).setText("1.5")
        app.processEvents()

        assert warnings == [
            "Expected a whole number (count), but a decimal value was entered."
        ]
        assert dialog.inconsistencyLabel.isVisible()
        assert dialog.inconsistencyLabel.wordWrap()
        assert "whole number" in dialog.inconsistencyLabel.text()
        assert dialog.analysis_unit.raw_data == [12, 3, 4, 21]
        assert dialog.two_by_two_table.item(0, 0).text() == "12"
        mapped = dialog.inconsistencyLabel.mapTo(
            dialog.content_scroll.viewport(), QtCore.QPoint()
        )
        assert (
            dialog.content_scroll.viewport()
            .rect()
            .intersects(QtCore.QRect(mapped, dialog.inconsistencyLabel.size()))
        )
        ok = dialog.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        assert ok.isEnabled()
        assert ok.isVisible()
        assert AVAILABLE.contains(dialog.frameGeometry())
        spec_index = dialog.effect_combo_box.findText("Spec")
        dialog.effect_combo_box.setCurrentIndex(spec_index)
        app.processEvents()
        assert ok.isEnabled()
    finally:
        app.setFont(old_font)
        dialog.close()
        app.processEvents()


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "guidance", "restored"),
    [
        ("effect_text_box", "not numeric", "must be numeric", "0.75"),
        ("lower_text_box", "0.95", "lower CI must be less", "0.6"),
    ],
    ids=["effect", "interval"],
)
def test_direct_effect_validation_is_complete_and_reachable_with_large_font(
    monkeypatch, field_name, invalid_value, guidance, restored
):
    from rc_metastudio import diagnostic_data_dialog

    app = cast(
        QtWidgets.QApplication,
        required(
            QtWidgets.QApplication.instance() or QtWidgets.QApplication([]),
            "application",
        ),
    )
    old_font = app.font()
    enlarged = QtGui.QFont(old_font)
    enlarged.setPointSize(max(16, old_font.pointSize() + 6))
    app.setFont(enlarged)
    app, dialog = _open_data_dialog(
        monkeypatch,
        raw_data=[None, None, None, None],
        effects={"Sens": (0.75, 0.60, 0.85), "Spec": (0.80, 0.70, 0.90)},
    )
    warnings = []
    monkeypatch.setattr(
        diagnostic_data_dialog.calc_fncs.QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(message),
    )
    try:
        dialog.show()
        dialog.resize(dialog.width(), 280)
        app.processEvents()
        field = getattr(dialog, field_name)
        field.setText(invalid_value)
        field.editingFinished.emit()
        app.processEvents()

        assert warnings
        assert guidance in dialog.inconsistencyLabel.text()
        assert dialog.inconsistencyLabel.wordWrap()
        assert field.text() == restored
        mapped = dialog.inconsistencyLabel.mapTo(
            dialog.content_scroll.viewport(), QtCore.QPoint()
        )
        assert (
            dialog.content_scroll.viewport()
            .rect()
            .intersects(QtCore.QRect(mapped, dialog.inconsistencyLabel.size()))
        )
        ok = dialog.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        assert ok.isEnabled()
        assert ok.isVisible()
        assert AVAILABLE.contains(dialog.frameGeometry())
    finally:
        app.setFont(old_font)
        dialog.close()
        app.processEvents()


@pytest.mark.parametrize(
    ("model", "selected"),
    [
        (FakeDiagnosticModel(raw_available=True), ["sens", "spec"]),
        (
            FakeDiagnosticModel(entered_effects=("Sens", "Spec")),
            ["sens", "spec"],
        ),
    ],
    ids=["raw-counts", "entered-effects"],
)
def test_diagnostic_metric_availability_preserves_workflow_and_explains_limits(
    monkeypatch, model, selected
):
    app, dialog = _open_metrics_dialog(monkeypatch, model)
    try:
        dialog.show()
        app.processEvents()

        assert (
            adaptive_window.adaptive_window_state(dialog).role
            is adaptive_window.WindowRole.TRANSACTIONAL
        )
        assert isinstance(dialog.content_scroll, QtWidgets.QScrollArea)
        assert dialog.content_scroll.widgetResizable()
        assert not dialog.content_scroll.isAncestorOf(dialog.btn_ok)
        assert dialog.get_selected_metrics() == selected
        assert dialog.availability_label.wordWrap()
        assert AVAILABLE.contains(dialog.frameGeometry())
        if model.raw_available:
            assert "All diagnostic metrics are available" in (
                dialog.availability_label.text()
            )
            # The joint Sensitivity/Specificity path is the default, while
            # univariate DOR/LR remain explicit, available requests.
            assert dialog.chk_box_lr.isEnabled()
            assert dialog.chk_box_dor.isEnabled()
            assert not dialog.chk_box_lr.isChecked()
            assert not dialog.chk_box_dor.isChecked()
            dialog.chk_box_lr.setChecked(True)
            dialog.chk_box_dor.setChecked(True)
            assert dialog.get_selected_metrics() == ["sens", "spec", "dor", "lr"]
        else:
            assert "Likelihood Ratio: Requires complete TP/FN/FP/TN counts" in (
                dialog.availability_label.text()
            )
            assert not dialog.chk_box_lr.isEnabled()
            assert not dialog.chk_box_dor.isEnabled()
        assert dialog.btn_ok.isEnabled()
        assert dialog.btn_ok.isDefault()
    finally:
        dialog.close()
        app.processEvents()


def test_metric_guidance_and_focus_remain_reachable_with_large_font(monkeypatch):
    app = cast(
        QtWidgets.QApplication,
        required(
            QtWidgets.QApplication.instance() or QtWidgets.QApplication([]),
            "application",
        ),
    )
    old_font = app.font()
    enlarged = QtGui.QFont(old_font)
    enlarged.setPointSize(max(16, old_font.pointSize() + 6))
    app.setFont(enlarged)
    model = FakeDiagnosticModel()
    app, dialog = _open_metrics_dialog(monkeypatch, model)
    try:
        dialog.availability_label.setText(
            "Complete availability guidance for every included study, raw count, "
            "entered effect estimate, lower interval, and upper interval. " * 12
        )
        dialog.show()
        dialog.resize(360, 220)
        app.processEvents()

        assert dialog.content_scroll.verticalScrollBar().maximum() > 0
        assert dialog.btn_ok.isVisible()
        dialog.chk_box_dor.setEnabled(True)
        dialog.chk_box_dor.setFocus()
        app.processEvents()
        mapped = dialog.chk_box_dor.mapTo(
            dialog.content_scroll.viewport(), QtCore.QPoint()
        )
        assert (
            dialog.content_scroll.viewport()
            .rect()
            .intersects(QtCore.QRect(mapped, dialog.chk_box_dor.size()))
        )
        assert AVAILABLE.contains(dialog.frameGeometry())
    finally:
        app.setFont(old_font)
        dialog.close()
        app.processEvents()
