import copy
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets


REPO_ROOT = Path(__file__).resolve().parents[3]
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
        assert dialog.property("RCMS_window_archetype") == "transactional"
        assert isinstance(dialog.content_scroll, QtWidgets.QScrollArea)
        assert dialog.content_scroll.widgetResizable()
        assert not dialog.content_scroll.isAncestorOf(dialog.buttonBox)
        assert dialog.layout().indexOf(dialog.buttonBox) >= 0
        assert (
            dialog.raw_data_table.horizontalScrollBarPolicy()
            == QtCore.Qt.ScrollBarAsNeeded
        )
        assert (
            dialog.raw_data_table.verticalScrollBarPolicy()
            == QtCore.Qt.ScrollBarAsNeeded
        )
        assert (
            dialog.raw_data_table.horizontalHeader().sectionResizeMode(0)
            == QtWidgets.QHeaderView.Interactive
        )
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
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.MinimumExpanding,
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
        assert dialog.property("RCMS_window_archetype") == "transactional"
        assert isinstance(dialog.content_scroll, QtWidgets.QScrollArea)
        assert not dialog.content_scroll.isAncestorOf(dialog.buttonBox)
        assert QtCore.QRect(20, 30, 800, 600).contains(dialog.frameGeometry())
        dialog.choice2_btn.setFocus()
        app.processEvents()
        mapped = dialog.choice2_btn.mapTo(
            dialog.content_scroll.viewport(), QtCore.QPoint()
        )
        assert dialog.content_scroll.viewport().rect().intersects(
            QtCore.QRect(mapped, dialog.choice2_btn.size())
        )
    finally:
        dialog.close()


def test_binary_data_focus_reveals_offscreen_controls_without_moving_actions(monkeypatch):
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
        assert viewport_rect.intersects(QtCore.QRect(mapped, dialog.high_txt_box.size()))
        assert dialog.buttonBox.isVisible()
        assert dialog.buttonBox.geometry() == footer_before
    finally:
        _close(app, window, dialog)


def test_binary_table_long_count_overflows_inside_table_and_remains_accessible(
    monkeypatch,
):
    app, window, dialog = _open_binary_dialog(monkeypatch)
    long_count = "9" * 80
    try:
        dialog.show()
        dialog.resize(320, dialog.height())
        dialog.raw_data_table.setCurrentCell(0, 0)
        dialog.raw_data_table.item(0, 0).setText(long_count)
        app.processEvents()

        table = dialog.raw_data_table
        assert table.horizontalScrollBar().maximum() > 0
        assert table.item(0, 0).text() == long_count
        assert table.columnWidth(0) >= table.fontMetrics().horizontalAdvance(long_count)
        table.horizontalScrollBar().setValue(0)
        assert table.viewport().rect().intersects(table.visualItemRect(table.item(0, 0)))
        table.horizontalScrollBar().setValue(table.horizontalScrollBar().maximum())
        assert table.horizontalScrollBar().value() == table.horizontalScrollBar().maximum()
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
        assert dialog.content_scroll.viewport().rect().intersects(
            QtCore.QRect(mapped, dialog.inconsistencyLabel.size())
        )
        assert not dialog.buttonBox.button(QtWidgets.QDialogButtonBox.Ok).isEnabled()
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
