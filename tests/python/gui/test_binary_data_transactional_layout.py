import copy
import os
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtTest, QtWidgets

import adaptive_window


REPO_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault(
    "RCMS_QT6_BUILD_ROOT", str(REPO_ROOT / "build" / "qt6-verification")
)

from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()
AVAILABLE = QtCore.QRect(20, 30, 1024, 640)


def _open_binary_dialog(monkeypatch):
    import binary_data_form
    import launch

    app, window = launch.start_automation()
    monkeypatch.setattr(
        binary_data_form.adaptive_window,
        "available_geometry_for_window",
        lambda _window: QtCore.QRect(AVAILABLE),
    )
    monkeypatch.setattr(
        binary_data_form.meta_py_r, "get_mult_from_r", lambda _level: 1.96
    )
    monkeypatch.setattr(
        binary_data_form.meta_py_r,
        "binary_convert_scale",
        lambda value, *_args, **_kwargs: value,
    )
    monkeypatch.setattr(
        binary_data_form.meta_py_r, "impute_bin_data", lambda _data: {"FAIL": True}
    )
    monkeypatch.setattr(
        binary_data_form.meta_py_r,
        "effect_for_study",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        binary_data_form.meta_py_r,
        "effect_triplet",
        lambda *_args, **_kwargs: (None, None, None),
    )
    assert window.open(str(REPO_ROOT / "sample_projects" / "amino.rcms")) is True
    model = window.model
    dialog = binary_data_form.BinaryDataForm2(
        copy.deepcopy(model.get_current_ma_unit_for_study(0)),
        model.current_txs,
        model.get_cur_group_str(),
        model.current_effect,
        conf_level=model.get_global_conf_level(),
        parent=window.tableView,
    )
    return app, window, dialog


def _close(app, window, dialog):
    dialog.close()
    window.close()
    app.processEvents()


def test_binary_data_declares_transactional_overflow_and_reachable_actions(
    monkeypatch,
):
    app, window, dialog = _open_binary_dialog(monkeypatch)
    try:
        assert (
            adaptive_window.adaptive_window_state(dialog).role
            is adaptive_window.WindowRole.TRANSACTIONAL
        )
        assert isinstance(dialog.content_scroll, QtWidgets.QScrollArea)
        assert dialog.content_scroll.widgetResizable()
        assert not dialog.content_scroll.isAncestorOf(dialog.buttonBox)
        assert dialog.layout().indexOf(dialog.buttonBox) >= 0
        assert (
            dialog.raw_data_table.horizontalScrollBarPolicy()
            == QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        assert (
            dialog.raw_data_table.verticalScrollBarPolicy()
            == QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        assert (
            dialog.raw_data_table.horizontalHeader().sectionResizeMode(0)
            == QtWidgets.QHeaderView.ResizeMode.Interactive
        )
    finally:
        _close(app, window, dialog)


def test_binary_data_keyboard_and_accessibility_contract(monkeypatch):
    app, window, dialog = _open_binary_dialog(monkeypatch)
    try:
        dialog.show()
        app.processEvents()
        ok = dialog.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        assert dialog.focusWidget() is dialog.raw_data_table
        assert ok.isDefault()
        assert dialog.label_17.buddy() is dialog.effect_cbo_box
        assert dialog.est_lbl.buddy() is dialog.effect_txt_box
        assert dialog.raw_data_table.accessibleName() == "Binary study counts"
        assert dialog.effect_txt_box.accessibleDescription()

        dialog.effect_cbo_box.setFocus()
        QtTest.QTest.keyClick(dialog.effect_cbo_box, QtCore.Qt.Key.Key_Tab)
        assert dialog.focusWidget() is dialog.effect_txt_box

        QtTest.QTest.keyClick(dialog, QtCore.Qt.Key.Key_Escape)
        assert dialog.result() == QtWidgets.QDialog.DialogCode.Rejected
    finally:
        _close(app, window, dialog)


def test_binary_data_is_screen_bounded_with_large_font_and_long_metric(monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    old_font = app.font()
    enlarged = QtGui.QFont(old_font)
    enlarged.setPointSize(max(16, old_font.pointSize() + 6))
    app.setFont(enlarged)
    app, window, dialog = _open_binary_dialog(monkeypatch)
    try:
        longest_index = max(
            range(dialog.effect_cbo_box.count()),
            key=lambda index: len(dialog.effect_cbo_box.itemText(index)),
        )
        dialog.effect_cbo_box.setCurrentIndex(longest_index)
        dialog.show()
        app.processEvents()

        available = AVAILABLE
        frame = dialog.frameGeometry()
        assert available.contains(frame)
        assert frame.width() <= int(available.width() * 0.9) + 2
        assert frame.height() <= int(available.height() * 0.9) + 2
        assert dialog.effect_cbo_box.sizePolicy().horizontalPolicy() in (
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.MinimumExpanding,
        )
        assert dialog.effect_cbo_box.maximumWidth() == QtWidgets.QWIDGETSIZE_MAX
        full_metric = dialog.effect_cbo_box.currentText()
        assert dialog.effect_cbo_box.toolTip() == full_metric
        assert dialog.effect_cbo_box.view().minimumWidth() >= (
            dialog.effect_cbo_box.fontMetrics().horizontalAdvance(full_metric)
        )
        dialog.effect_cbo_box.showPopup()
        app.processEvents()
        assert dialog.effect_cbo_box.view().isVisible()
        assert dialog.effect_cbo_box.view().width() >= (
            dialog.effect_cbo_box.fontMetrics().horizontalAdvance(full_metric)
        )
        dialog.effect_cbo_box.hidePopup()
    finally:
        app.setFont(old_font)
        _close(app, window, dialog)


def test_binary_back_calculation_choices_are_scrollable_and_screen_bounded(monkeypatch):
    import binary_data_form

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setattr(
        binary_data_form.adaptive_window,
        "available_geometry_for_window",
        lambda _window: QtCore.QRect(20, 30, 800, 600),
    )
    data = {
        "op1": {"a": 1, "b": 10, "c": 2, "d": 12},
        "op2": {"a": 3, "b": 14, "c": 4, "d": 16},
    }
    dialog = binary_data_form.ChooseBackCalcResultForm(data)
    try:
        dialog.info_label.setText("Long back-calculation guidance " * 40)
        dialog._layout_controller.request_content_refit()
        dialog.show()
        app.processEvents()
        assert (
            adaptive_window.adaptive_window_state(dialog).role
            is adaptive_window.WindowRole.TRANSACTIONAL
        )
        assert isinstance(dialog.content_scroll, QtWidgets.QScrollArea)
        assert not dialog.content_scroll.isAncestorOf(dialog.buttonBox)
        assert QtCore.QRect(20, 30, 800, 600).contains(dialog.frameGeometry())
        dialog.choice2_btn.setFocus()
        app.processEvents()
        mapped = dialog.choice2_btn.mapTo(
            dialog.content_scroll.viewport(), QtCore.QPoint()
        )
        assert (
            dialog.content_scroll.viewport()
            .rect()
            .intersects(QtCore.QRect(mapped, dialog.choice2_btn.size()))
        )
    finally:
        dialog.close()


def _binary_table_snapshot(dialog):
    return [
        dialog.raw_data_table.item(row, column).text()
        for row in range(dialog.raw_data_table.rowCount())
        for column in range(dialog.raw_data_table.columnCount())
    ]


def test_binary_back_calculation_chooser_cancel_is_an_exact_nested_transaction(
    monkeypatch,
):
    import binary_data_form

    app, window, dialog = _open_binary_dialog(monkeypatch)
    imputed = {
        "op1": {"a": 2, "b": 10, "c": 3, "d": 12},
        "op2": {"a": 4, "b": 14, "c": 5, "d": 16},
    }
    monkeypatch.setattr(
        binary_data_form.meta_py_r, "impute_bin_data", lambda _d: imputed
    )

    def cancel_choice(chooser):
        chooser.show()
        app.processEvents()
        QtTest.QTest.mouseClick(
            chooser.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel),
            QtCore.Qt.MouseButton.LeftButton,
        )
        return chooser.result()

    monkeypatch.setattr(
        binary_data_form.ChooseBackCalcResultForm, "exec", cancel_choice
    )
    try:
        dialog.clear_form()
        dialog.undoStack.clear()
        dialog.enable_back_calculation_btn()
        table_before = _binary_table_snapshot(dialog)
        model_before = copy.deepcopy(dialog.ma_unit)
        dirty_before = window.current_data_unsaved
        ok = dialog.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        assert dialog.back_calc_btn.isEnabled()

        QtTest.QTest.mouseClick(dialog.back_calc_btn, QtCore.Qt.MouseButton.LeftButton)
        app.processEvents()

        assert _binary_table_snapshot(dialog) == table_before
        assert dialog.ma_unit.get_raw_data_for_groups(dialog.cur_groups) == (
            model_before.get_raw_data_for_groups(dialog.cur_groups)
        )
        assert dialog.ma_unit.get_effects_dict() == model_before.get_effects_dict()
        assert dialog.undoStack.count() == 0
        assert window.current_data_unsaved is dirty_before
        assert dialog.result() == 0
        assert ok.isEnabled()
    finally:
        _close(app, window, dialog)


def test_binary_back_calculation_chooser_accept_commits_selected_option(monkeypatch):
    import binary_data_form

    app, window, dialog = _open_binary_dialog(monkeypatch)
    imputed = {
        "op1": {"a": 2, "b": 10, "c": 3, "d": 12},
        "op2": {"a": 4, "b": 14, "c": 5, "d": 16},
    }
    monkeypatch.setattr(
        binary_data_form.meta_py_r, "impute_bin_data", lambda _d: imputed
    )

    def accept_second_choice(chooser):
        chooser.show()
        app.processEvents()
        QtTest.QTest.mouseClick(chooser.choice2_btn, QtCore.Qt.MouseButton.LeftButton)
        QtTest.QTest.mouseClick(
            chooser.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok),
            QtCore.Qt.MouseButton.LeftButton,
        )
        return chooser.result()

    monkeypatch.setattr(
        binary_data_form.ChooseBackCalcResultForm, "exec", accept_second_choice
    )
    try:
        dialog.clear_form()
        dialog.undoStack.clear()
        dialog.enable_back_calculation_btn()
        QtTest.QTest.mouseClick(dialog.back_calc_btn, QtCore.Qt.MouseButton.LeftButton)
        app.processEvents()

        assert _binary_table_snapshot(dialog)[:6] == ["4", "10", "14", "5", "11", "16"]
        assert dialog.ma_unit.get_raw_data_for_groups(dialog.cur_groups) == [
            4,
            14,
            5,
            16,
        ]
        assert dialog.undoStack.count() == 1
    finally:
        _close(app, window, dialog)


def test_binary_data_focus_reveals_offscreen_controls_without_moving_actions(
    monkeypatch,
):
    app, window, dialog = _open_binary_dialog(monkeypatch)
    try:
        dialog.show()
        dialog.resize(dialog.width(), 260)
        app.processEvents()
        footer_before = dialog.buttonBox.geometry()
        dialog.high_txt_box.setFocus()
        app.processEvents()

        viewport_rect = dialog.content_scroll.viewport().rect()
        mapped = dialog.high_txt_box.mapTo(
            dialog.content_scroll.viewport(), QtCore.QPoint()
        )
        assert viewport_rect.intersects(
            QtCore.QRect(mapped, dialog.high_txt_box.size())
        )
        assert dialog.buttonBox.isVisible()
        assert dialog.buttonBox.geometry() == footer_before
    finally:
        _close(app, window, dialog)


def test_binary_table_long_count_overflows_inside_table_and_remains_accessible(
    monkeypatch,
):
    import app_error_handler
    import binary_data_form

    warnings = []
    monkeypatch.setattr(
        binary_data_form.QMessageBox,
        "warning",
        lambda *args: warnings.append(args),
    )
    monkeypatch.setattr(
        app_error_handler.QMessageBox,
        "critical",
        lambda *args: warnings.append(args),
    )
    app, window, dialog = _open_binary_dialog(monkeypatch)
    long_count = "9" * 80
    try:
        dialog.show()
        dialog.resize(320, dialog.height())
        dialog.raw_data_table.setCurrentCell(0, 0)
        dialog.raw_data_table.item(0, 0).setText(long_count)
        app.processEvents()

        table = dialog.raw_data_table
        assert warnings == []
        assert table.horizontalScrollBar().maximum() > 0
        assert table.item(0, 0).text() == long_count
        assert table.columnWidth(0) >= table.fontMetrics().horizontalAdvance(long_count)
        table.horizontalScrollBar().setValue(0)
        assert (
            table.viewport().rect().intersects(table.visualItemRect(table.item(0, 0)))
        )
        table.horizontalScrollBar().setValue(table.horizontalScrollBar().maximum())
        assert (
            table.horizontalScrollBar().value() == table.horizontalScrollBar().maximum()
        )
    finally:
        _close(app, window, dialog)


def test_binary_validation_message_wraps_and_is_revealed(monkeypatch):
    import binary_data_form

    app, window, dialog = _open_binary_dialog(monkeypatch)
    warnings = []
    monkeypatch.setattr(
        binary_data_form.QMessageBox,
        "warning",
        lambda *args: warnings.append(args),
    )
    try:
        dialog.show()
        dialog.resize(dialog.width(), 260)
        dialog.raw_data_table.setCurrentCell(0, 0)
        dialog.raw_data_table.item(0, 0).setText("1.5")
        app.processEvents()

        assert warnings
        assert dialog.inconsistencyLabel.isVisible()
        assert dialog.inconsistencyLabel.wordWrap()
        assert "whole number" in dialog.inconsistencyLabel.text()
        mapped = dialog.inconsistencyLabel.mapTo(
            dialog.content_scroll.viewport(), QtCore.QPoint()
        )
        assert (
            dialog.content_scroll.viewport()
            .rect()
            .intersects(QtCore.QRect(mapped, dialog.inconsistencyLabel.size()))
        )
        assert not dialog.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
        ).isEnabled()
    finally:
        _close(app, window, dialog)


def test_binary_calculator_refits_are_local_and_coalesced(monkeypatch):
    app, window, dialog = _open_binary_dialog(monkeypatch)
    try:
        dialog.show()
        app.processEvents()
        app.processEvents()

        raw_counts = [
            dialog.raw_data_table.item(row, column).text()
            for row in range(2)
            for column in range(2)
        ]
        indices_by_metric = {
            dialog.effect_cbo_box.itemData(index): index
            for index in range(dialog.effect_cbo_box.count())
        }
        applied = []
        dialog._layout_controller.refitApplied.connect(lambda: applied.append(True))

        for metric in ("RD", "RR", "AS"):
            index = indices_by_metric[metric]
            dialog.effect_cbo_box.setCurrentIndex(index)
        assert applied == []

        app.processEvents()
        assert len(applied) == 1
        assert dialog.effect_cbo_box.currentData() == "AS"
        assert not dialog.back_calc_btn.isVisible()
        assert AVAILABLE.contains(dialog.frameGeometry())
        assert [
            dialog.raw_data_table.item(row, column).text()
            for row in range(2)
            for column in range(2)
        ] == raw_counts

        widths = {
            field.width()
            for field in (
                dialog.effect_txt_box,
                dialog.low_txt_box,
                dialog.high_txt_box,
            )
        }
        assert len(widths) == 1

        settled_geometry = QtCore.QRect(dialog.frameGeometry())
        app.processEvents()
        app.processEvents()
        assert dialog.frameGeometry() == settled_geometry
        assert len(applied) == 1
    finally:
        _close(app, window, dialog)
