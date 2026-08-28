import os
from pathlib import Path

import pytest
from PyQt6 import QtCore, QtGui, QtTest, QtWidgets

import adaptive_window


REPO_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault(
    "RCMS_QT6_BUILD_ROOT", str(REPO_ROOT / "build" / "qt6-verification")
)

from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()


class FakeContinuousMAUnit:
    def __init__(self, raw_data=None, effects=None):
        self.raw_data = raw_data or {
            "Group 1": [10, 94, 2],
            "Group 2": [12, 90, 3],
        }
        self.effects = effects or {}

    def get_effect_names(self):
        return ["MD", "SMD", "TX Mean"]

    def get_raw_data_for_group(self, group):
        return self.raw_data[group]

    def get_raw_data_for_groups(self, groups):
        return [value for group in groups for value in self.raw_data[group]]

    def get_se(self, *_args, **_kwargs):
        return None

    def get_effect_and_ci(self, *_args, **_kwargs):
        metric = _args[0]
        return self.effects.get(metric, (None, None, None))

    def set_effect_and_ci(self, metric, _group, est, low, high, **_kwargs):
        self.effects[metric] = (est, low, high)

    def set_effect(self, metric, _group, value, **_kwargs):
        _old_est, low, high = self.effects.get(metric, (None, None, None))
        self.effects[metric] = (value, low, high)

    def set_lower(self, metric, _group, value, **_kwargs):
        est, _old_low, high = self.effects.get(metric, (None, None, None))
        self.effects[metric] = (est, value, high)

    def set_upper(self, metric, _group, value, **_kwargs):
        est, low, _old_high = self.effects.get(metric, (None, None, None))
        self.effects[metric] = (est, low, value)


def _open_continuous_dialog(
    monkeypatch,
    available,
    metric="MD",
    recorder=None,
    ma_unit=None,
    back_calc_result=None,
    choose_metric=False,
):
    import continuous_data_form

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    recorder = recorder if recorder is not None else {}
    recorder.setdefault("metric_choice_exec", [])
    monkeypatch.setattr(
        continuous_data_form.adaptive_window,
        "available_geometry_for_window",
        lambda _window: QtCore.QRect(available),
    )
    if choose_metric:

        def choose_second_option(dialog):
            recorder["metric_choice_exec"].append(dialog.windowTitle())
            dialog.show()
            app.processEvents()
            QtTest.QTest.mouseClick(
                dialog.choice2_label, QtCore.Qt.MouseButton.LeftButton
            )
            QtTest.QTest.mouseClick(
                dialog.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok),
                QtCore.Qt.MouseButton.LeftButton,
            )
            return dialog.result()

        monkeypatch.setattr(
            continuous_data_form.ChooseBackCalcResultForm,
            "exec",
            choose_second_option,
        )
    else:

        def reject_metric_choice(dialog):
            recorder["metric_choice_exec"].append(dialog.windowTitle())
            return False

        monkeypatch.setattr(
            continuous_data_form.ChooseBackCalcResultForm,
            "exec",
            reject_metric_choice,
        )
    monkeypatch.setattr(
        continuous_data_form.meta_py_r, "get_mult_from_r", lambda _conf: 1.96
    )
    monkeypatch.setattr(
        continuous_data_form.meta_py_r,
        "continuous_convert_scale",
        lambda value, *_args, **_kwargs: value,
    )
    recorder.setdefault("impute", [])
    recorder.setdefault("pre_post", [])
    recorder.setdefault("back_calc", [])

    def impute(data, alpha):
        recorder["impute"].append((dict(data), alpha))
        return {"succeeded": False, "comment": "stub"}

    def impute_pre_post(data, correlation, alpha):
        recorder["pre_post"].append((dict(data), correlation, alpha))
        return {"succeeded": False, "comment": "stub"}

    monkeypatch.setattr(
        continuous_data_form.meta_py_r,
        "impute_cont_data",
        impute,
    )
    monkeypatch.setattr(
        continuous_data_form.meta_py_r,
        "impute_pre_post_cont_data",
        impute_pre_post,
    )
    monkeypatch.setattr(
        continuous_data_form.meta_py_r,
        "continuous_effect_for_study",
        lambda *_args, **_kwargs: {"calc_scale": (2.5, 1.5, 3.5)},
    )
    monkeypatch.setattr(
        continuous_data_form.meta_py_r,
        "effect_triplet",
        lambda effect, _scale, metric=None: effect["calc_scale"],
    )

    def back_calc(*args, **kwargs):
        recorder["back_calc"].append((args, kwargs))
        return back_calc_result or {"FAIL": True}

    monkeypatch.setattr(
        continuous_data_form.meta_py_r, "back_calc_cont_data", back_calc
    )
    dialog = continuous_data_form.ContinuousDataForm(
        ma_unit or FakeContinuousMAUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        metric,
        conf_level=95.0,
    )
    return app, dialog


def _close(app, dialog):
    dialog.close()
    app.processEvents()


def test_continuous_back_calculation_choice_opens_only_after_user_action(monkeypatch):
    recorder = {}
    app, dialog = _open_continuous_dialog(
        monkeypatch, QtCore.QRect(20, 30, 1024, 640), recorder=recorder
    )
    try:
        assert recorder["metric_choice_exec"] == []
        recorder["back_calc"].clear()

        dialog.enable_back_calculation_btn(engage=True)

        assert recorder["metric_choice_exec"] == ["Population SD Assumptions"]
        assert recorder["back_calc"] == []
    finally:
        _close(app, dialog)


@pytest.mark.parametrize(
    ("working_parameter", "expected_parameters"),
    [(True, [True]), (False, [True, False])],
)
@pytest.mark.parametrize("metric", ["MD", "SMD"])
def test_continuous_back_calculation_enablement_probes_metric_assumptions(
    monkeypatch, metric, working_parameter, expected_parameters
):
    import continuous_data_form

    unit = FakeContinuousMAUnit(
        raw_data={
            "Group 1": [100, 10, 10],
            "Group 2": [100, 6, None],
        },
        effects={metric: (4.0, 2.0, 6.0)},
    )
    app, dialog = _open_continuous_dialog(
        monkeypatch,
        QtCore.QRect(20, 30, 1024, 640),
        metric=metric,
        ma_unit=unit,
    )
    observed_parameters = []

    def assumption_dependent_solver(
        _group1_data, _group2_data, effect_data, _conf_level
    ):
        parameter = effect_data.get("met.param")
        observed_parameters.append(parameter)
        if parameter is not working_parameter:
            return {"FAIL": True}
        return {
            "n1": 100,
            "mean1": 10,
            "sd1": 10,
            "n2": 100,
            "mean2": 6,
            "sd2": 2.0,
        }

    monkeypatch.setattr(
        continuous_data_form.meta_py_r,
        "back_calc_cont_data",
        assumption_dependent_solver,
    )
    try:
        dialog.metric_parameter = None
        dialog.enable_back_calculation_btn()

        assert dialog.back_calc_btn.isEnabled()
        assert dialog.metric_parameter is None
        assert observed_parameters == expected_parameters
    finally:
        _close(app, dialog)


def test_continuous_assumptions_cancel_button_prevents_r_and_state_mutation(
    monkeypatch,
):
    import continuous_data_form

    recorder = {}
    unit = FakeContinuousMAUnit(
        raw_data={"Group 1": [None, None, None], "Group 2": [None, None, None]},
        effects={"MD": (5.0, 4.0, 6.0)},
    )
    result = {
        "n1": 10.0,
        "sd1": 2.0,
        "mean1": 94.0,
        "n2": 12.0,
        "sd2": 3.0,
        "mean2": 90.0,
    }
    app, dialog = _open_continuous_dialog(
        monkeypatch,
        QtCore.QRect(20, 30, 1024, 640),
        recorder=recorder,
        ma_unit=unit,
        back_calc_result=result,
    )

    def cancel_with_button(chooser):
        recorder["metric_choice_exec"].append(chooser.windowTitle())
        chooser.show()
        app.processEvents()
        QtTest.QTest.mouseClick(
            chooser.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel),
            QtCore.Qt.MouseButton.LeftButton,
        )
        return chooser.result()

    monkeypatch.setattr(
        continuous_data_form.ChooseBackCalcResultForm, "exec", cancel_with_button
    )
    try:
        table_before = [
            dialog.simple_table.item(row, column).text()
            for row in range(2)
            for column in range(dialog.simple_table.columnCount())
        ]
        raw_before = {group: list(values) for group, values in unit.raw_data.items()}
        effects_before = dict(unit.effects)
        dialog.undoStack.clear()
        recorder["back_calc"].clear()

        QtTest.QTest.mouseClick(dialog.back_calc_btn, QtCore.Qt.MouseButton.LeftButton)
        app.processEvents()

        assert recorder["metric_choice_exec"] == ["Population SD Assumptions"]
        assert recorder["back_calc"] == []
        assert dialog.metric_parameter is None
        assert unit.raw_data == raw_before
        assert unit.effects == effects_before
        assert [
            dialog.simple_table.item(row, column).text()
            for row in range(2)
            for column in range(dialog.simple_table.columnCount())
        ] == table_before
        assert dialog.undoStack.count() == 0
        assert dialog.result() == 0
    finally:
        _close(app, dialog)


def test_continuous_data_keyboard_and_accessibility_contract(monkeypatch):
    app, dialog = _open_continuous_dialog(monkeypatch, QtCore.QRect(20, 30, 1024, 640))
    try:
        dialog.show()
        app.processEvents()
        ok = dialog.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        assert dialog.focusWidget() is dialog.simple_table
        assert ok.isDefault()
        assert dialog.label_13.buddy() is dialog.effect_cbo_box
        assert dialog.label_14.buddy() is dialog.effect_txt_box
        assert dialog.label.buddy() is dialog.correlation_pre_post
        assert dialog.simple_table.accessibleName() == "Continuous group summary data"

        dialog.effect_cbo_box.setFocus()
        QtTest.QTest.keyClick(dialog.effect_cbo_box, QtCore.Qt.Key.Key_Tab)
        assert dialog.focusWidget() is dialog.effect_txt_box

        QtTest.QTest.keyClick(dialog, QtCore.Qt.Key.Key_Escape)
        assert dialog.result() == QtWidgets.QDialog.DialogCode.Rejected
    finally:
        _close(app, dialog)


@pytest.mark.parametrize("table_name", ["g1_pre_post_table", "g2_pre_post_table"])
def test_failed_pre_post_imputation_restores_value_from_owning_table(
    monkeypatch, table_name
):
    app, dialog = _open_continuous_dialog(monkeypatch, QtCore.QRect(20, 30, 1024, 640))
    try:
        table = getattr(dialog, table_name)
        dialog.simple_table.blockSignals(True)
        dialog.simple_table.item(0, 1).setText("777")
        dialog.simple_table.blockSignals(False)
        original = table.item(0, 1).text()

        table.setCurrentCell(0, 1)
        table.item(0, 1).setText("95")
        app.processEvents()

        assert table.item(0, 1).text() == original
        assert table.item(0, 1).text() != dialog.simple_table.item(0, 1).text()
    finally:
        _close(app, dialog)


@pytest.mark.parametrize("invalid_n", ["10.5", "10,5", "nan", "inf", "-1"])
def test_continuous_sample_size_is_rejected_before_model_or_r(monkeypatch, invalid_n):
    recorder = {}
    warnings = []
    unit = FakeContinuousMAUnit()
    app, dialog = _open_continuous_dialog(
        monkeypatch,
        QtCore.QRect(20, 30, 1024, 640),
        recorder=recorder,
        ma_unit=unit,
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "warning",
        lambda *args: warnings.append(args[2]),
    )
    try:
        before_calls = len(recorder["impute"])
        before_raw = list(unit.get_raw_data_for_group("Group 1"))
        dialog.simple_table.setCurrentCell(0, 0)
        dialog.simple_table.item(0, 0).setText(invalid_n)
        app.processEvents()

        assert len(recorder["impute"]) == before_calls
        assert unit.get_raw_data_for_group("Group 1") == before_raw
        assert dialog.simple_table.item(0, 0).text() == "10.0"
        assert warnings
        assert (
            "numeric" in warnings[-1].lower() or "whole number" in warnings[-1].lower()
        )
    finally:
        _close(app, dialog)


@pytest.mark.parametrize("size", [(1440, 900), (1024, 640), (800, 600)])
def test_continuous_variants_are_transactional_and_screen_bounded(monkeypatch, size):
    available = QtCore.QRect(20, 30, *size)
    app, dialog = _open_continuous_dialog(monkeypatch, available)
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
        assert not isinstance(dialog.simple_group, QtWidgets.QGroupBox)
        assert not isinstance(dialog.effect_group, QtWidgets.QGroupBox)
        assert dialog.label_13.text() == "Effect"
        assert dialog.label_14.text() == "Est."
        assert [dialog.label_15.text(), dialog.label_2.text()] == ["Lower", "Upper"]
        assert dialog.label_15.buddy() is dialog.low_txt_box
        assert dialog.label_2.buddy() is dialog.high_txt_box
        assert available.contains(dialog.frameGeometry())
        for table in (
            dialog.simple_table,
            dialog.g1_pre_post_table,
            dialog.g2_pre_post_table,
        ):
            assert (
                table.horizontalScrollBarPolicy()
                == QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
            assert (
                table.horizontalHeader().sectionResizeMode(0)
                == QtWidgets.QHeaderView.ResizeMode.Interactive
            )
    finally:
        _close(app, dialog)


def test_continuous_metric_transition_does_not_resize_visible_root(monkeypatch):
    available = QtCore.QRect(20, 30, 1024, 640)
    app, dialog = _open_continuous_dialog(monkeypatch, available)
    try:
        dialog.show()
        app.processEvents()
        settled = QtCore.QRect(dialog.frameGeometry())
        preserved_value = dialog.simple_table.item(0, 1).text()

        smd_index = next(
            index
            for index in range(dialog.effect_cbo_box.count())
            if dialog.effect_cbo_box.itemData(index) == "SMD"
        )
        dialog.effect_cbo_box.setCurrentIndex(smd_index)
        app.processEvents()

        assert dialog.frameGeometry() == settled
        assert dialog.effect_cbo_box.currentData() == "SMD"
        assert dialog.grp_box_pre_post.isVisible()
        assert dialog.simple_table.item(0, 1).text() == preserved_value
        assert dialog.buttonBox.isVisible()
    finally:
        _close(app, dialog)


@pytest.mark.parametrize("variant", ["md_simple", "smd_pre_post", "tx_mean"])
def test_continuous_major_variant_behavior_matrix(monkeypatch, variant):
    available = QtCore.QRect(20, 30, 800, 600)
    recorder = {}
    initial_metric = "TX Mean" if variant == "tx_mean" else "MD"
    app, dialog = _open_continuous_dialog(
        monkeypatch, available, metric=initial_metric, recorder=recorder
    )
    try:
        dialog.show()
        app.processEvents()
        settled = QtCore.QRect(dialog.frameGeometry())

        if variant == "smd_pre_post":
            smd_index = next(
                index
                for index in range(dialog.effect_cbo_box.count())
                if dialog.effect_cbo_box.itemData(index) == "SMD"
            )
            dialog.effect_cbo_box.setCurrentIndex(smd_index)
            dialog.correlation_pre_post.selectAll()
            QtTest.QTest.keyClicks(dialog.correlation_pre_post, "0.5")
            dialog.g1_pre_post_table.setFocus()
            app.processEvents()
            dialog.g1_pre_post_table.setCurrentCell(0, 1)
            dialog.g1_pre_post_table.item(0, 1).setText("95")
            app.processEvents()
            assert dialog.effect_cbo_box.currentData() == "SMD"
            assert dialog.correlation_pre_post.text() == "0.5"
            assert any(
                payload[0].get("mean.A") == 95 for payload in recorder["pre_post"]
            )
        else:
            dialog.simple_table.setCurrentCell(0, 1)
            dialog.simple_table.item(0, 1).setText("95")
            app.processEvents()
            assert any(payload[0].get("mean") == 95 for payload in recorder["impute"])

        assert dialog.effect_txt_box.text() == "2.5"
        assert dialog.low_txt_box.text() == "1.5"
        assert dialog.high_txt_box.text() == "3.5"

        assert dialog.frameGeometry() == settled
        assert available.contains(dialog.frameGeometry())
        assert dialog.buttonBox.isVisible()
        edited_table = (
            dialog.g1_pre_post_table
            if variant == "smd_pre_post"
            else dialog.simple_table
        )
        assert edited_table.item(0, 1).text() == (
            "" if variant == "smd_pre_post" else "95"
        )
        assert dialog.simple_table.isRowHidden(1) is (variant == "tx_mean")
    finally:
        _close(app, dialog)


def test_continuous_long_values_and_large_font_overflow_inside_content(monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    old_font = app.font()
    enlarged = QtGui.QFont(old_font)
    enlarged.setPointSize(max(16, old_font.pointSize() + 6))
    app.setFont(enlarged)
    available = QtCore.QRect(20, 30, 800, 600)
    app, dialog = _open_continuous_dialog(monkeypatch, available)
    try:
        long_value = "9" * 80
        dialog.simple_table.setCurrentCell(0, 1)
        dialog.simple_table.item(0, 1).setText(long_value)
        dialog.show()
        app.processEvents()

        assert available.contains(dialog.frameGeometry())
        assert dialog.simple_table.horizontalScrollBar().maximum() > 0
        assert dialog.simple_table.item(0, 1).text() == long_value
        assert dialog.effect_cbo_box.maximumWidth() == QtWidgets.QWIDGETSIZE_MAX
        assert dialog.effect_cbo_box.toolTip() == dialog.effect_cbo_box.currentText()
        assert dialog.correlation_pre_post.minimumWidth() >= (
            dialog.correlation_pre_post.fontMetrics().horizontalAdvance("-1.0000")
        )
        dialog.high_txt_box.setFocus()
        app.processEvents()
        mapped = dialog.high_txt_box.mapTo(
            dialog.content_scroll.viewport(), QtCore.QPoint()
        )
        assert (
            dialog.content_scroll.viewport()
            .rect()
            .intersects(QtCore.QRect(mapped, dialog.high_txt_box.size()))
        )
        assert dialog.buttonBox.isVisible()
    finally:
        app.setFont(old_font)
        _close(app, dialog)


@pytest.mark.parametrize("size", [(1024, 640), (800, 600)])
def test_continuous_long_metric_choice_is_fully_accessible(monkeypatch, size):
    import continuous_data_form

    long_label = (
        "Standardized Mean Difference with small-sample bias correction and "
        "complete confidence interval reporting across every treatment arm, "
        "follow-up, subgroup, estimator, and sensitivity-analysis scenario"
    )
    monkeypatch.setitem(continuous_data_form.CONTINUOUS_METRIC_NAMES, "SMD", long_label)
    available = QtCore.QRect(20, 30, *size)
    app, dialog = _open_continuous_dialog(monkeypatch, available)
    try:
        dialog.show()
        app.processEvents()
        smd_index = next(
            index
            for index in range(dialog.effect_cbo_box.count())
            if dialog.effect_cbo_box.itemData(index) == "SMD"
        )
        dialog.effect_cbo_box.setCurrentIndex(smd_index)
        app.processEvents()

        full_value = dialog.effect_cbo_box.currentText()
        assert long_label in full_value
        assert dialog.effect_cbo_box.toolTip() == full_value
        assert available.contains(dialog.frameGeometry())
        dialog.effect_cbo_box.showPopup()
        app.processEvents()
        view = dialog.effect_cbo_box.view()
        popup = view.window()
        assert view.isVisible()
        assert available.contains(popup.frameGeometry())
        assert view.textElideMode() == QtCore.Qt.TextElideMode.ElideNone
        assert (
            view.horizontalScrollBarPolicy()
            == QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        assert view.horizontalScrollBar().maximum() > 0
        assert dialog.effect_cbo_box.itemData(
            smd_index, QtCore.Qt.ItemDataRole.ToolTipRole
        ) == (full_value)
        dialog.effect_cbo_box.hidePopup()
    finally:
        _close(app, dialog)


@pytest.mark.parametrize("size", [(1440, 900), (1024, 640), (800, 600)])
def test_successful_continuous_back_calculation_updates_data_without_root_growth(
    monkeypatch, size
):
    available = QtCore.QRect(20, 30, *size)
    recorder = {}
    unit = FakeContinuousMAUnit(
        raw_data={"Group 1": [None, None, None], "Group 2": [None, None, None]},
        effects={"MD": (5.0, 4.0, 6.0)},
    )
    result = {
        "n1": 120.0,
        "sd1": 11.0,
        "mean1": 15.0,
        "n2": 110.0,
        "sd2": 12.0,
        "mean2": 10.0,
    }
    app, dialog = _open_continuous_dialog(
        monkeypatch,
        available,
        recorder=recorder,
        ma_unit=unit,
        back_calc_result=result,
        choose_metric=True,
    )
    try:
        dialog.show()
        app.processEvents()
        settled = QtCore.QRect(dialog.frameGeometry())
        assert dialog.back_calc_btn.isEnabled()

        recorder["back_calc"].clear()
        QtTest.QTest.mouseClick(dialog.back_calc_btn, QtCore.Qt.MouseButton.LeftButton)
        app.processEvents()

        assert dialog.metric_parameter is False
        assert len(recorder["back_calc"]) == 1
        assert recorder["back_calc"][0][0][2]["met.param"] is False
        assert unit.raw_data == {
            "Group 1": [120.0, 15.0, 11.0],
            "Group 2": [110.0, 10.0, 12.0],
        }
        assert [
            dialog.simple_table.item(row, column).text()
            for row in range(2)
            for column in range(3)
        ] == ["120.0", "15.0", "11.0", "110.0", "10.0", "12.0"]
        assert unit.effects["MD"] == (5.0, 4.0, 6.0)
        assert [
            dialog.effect_txt_box.text(),
            dialog.low_txt_box.text(),
            dialog.high_txt_box.text(),
        ] == ["5.0", "4.0", "6.0"]
        assert dialog.frameGeometry() == settled
        assert available.contains(dialog.frameGeometry())
    finally:
        _close(app, dialog)


@pytest.mark.parametrize(
    "fault_boundary",
    ["setter", "impute_data", "copy", "snapshot", "undo_push"],
)
def test_continuous_back_calculation_apply_failures_restore_exact_transaction(
    monkeypatch, fault_boundary
):
    unit = FakeContinuousMAUnit(
        raw_data={"Group 1": [None, None, None], "Group 2": [None, None, None]},
        effects={"MD": (5.0, 4.0, 6.0)},
    )
    result = {
        "n1": 120.0,
        "sd1": 11.0,
        "mean1": 15.0,
        "n2": 110.0,
        "sd2": 12.0,
        "mean2": 10.0,
    }
    recorder = {}
    app, dialog = _open_continuous_dialog(
        monkeypatch,
        QtCore.QRect(20, 30, 1024, 640),
        recorder=recorder,
        ma_unit=unit,
        back_calc_result=result,
        choose_metric=True,
    )
    try:
        tables_before = [
            [
                table.item(row, column).text()
                for row in range(table.rowCount())
                for column in range(table.columnCount())
            ]
            for table in dialog.tables
        ]
        raw_before = {group: list(values) for group, values in unit.raw_data.items()}
        effects_before = dict(unit.effects)
        correlation_before = dialog.correlation_pre_post.text()
        metric_parameter_before = dialog.metric_parameter
        button_before = (
            dialog.back_calc_btn.isEnabled(),
            dialog.back_calc_btn.text(),
            dialog.back_calc_btn.isHidden(),
            dialog.back_calc_btn.isChecked(),
            dialog.back_calc_btn.isDown(),
        )
        undo_before = (
            dialog.undoStack.count(),
            dialog.undoStack.index(),
            dialog.undoStack.isClean(),
        )
        recorder["back_calc"].clear()

        if fault_boundary == "setter":
            original = dialog._set_val
            calls = 0

            def fail_after_partial_values(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise RuntimeError("setter fault")
                return original(*args, **kwargs)

            monkeypatch.setattr(dialog, "_set_val", fail_after_partial_values)
        elif fault_boundary == "impute_data":
            monkeypatch.setattr(
                dialog,
                "impute_data",
                lambda: (_ for _ in ()).throw(RuntimeError("impute fault")),
            )
        elif fault_boundary == "copy":
            monkeypatch.setattr(
                dialog,
                "_copy_raw_data_from_table_to_ma_unit",
                lambda: (_ for _ in ()).throw(RuntimeError("copy fault")),
            )
        elif fault_boundary == "snapshot":
            original = dialog._capture_back_calculation_state
            calls = 0

            def fail_new_snapshot():
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RuntimeError("snapshot fault")
                return original()

            monkeypatch.setattr(
                dialog, "_capture_back_calculation_state", fail_new_snapshot
            )
        else:

            def fail_before_push(_stack, _command):
                raise RuntimeError("undo push fault")

            monkeypatch.setattr(QtGui.QUndoStack, "push", fail_before_push)

        with pytest.raises(RuntimeError, match="fault"):
            dialog.enable_back_calculation_btn(engage=True)

        assert len(recorder["back_calc"]) == 1
        assert [
            [
                table.item(row, column).text()
                for row in range(table.rowCount())
                for column in range(table.columnCount())
            ]
            for table in dialog.tables
        ] == tables_before
        assert unit.raw_data == raw_before
        assert unit.effects == effects_before
        assert dialog.correlation_pre_post.text() == correlation_before
        assert dialog.metric_parameter is metric_parameter_before
        assert (
            dialog.back_calc_btn.isEnabled(),
            dialog.back_calc_btn.text(),
            dialog.back_calc_btn.isHidden(),
            dialog.back_calc_btn.isChecked(),
            dialog.back_calc_btn.isDown(),
        ) == button_before
        assert (
            dialog.undoStack.count(),
            dialog.undoStack.index(),
            dialog.undoStack.isClean(),
        ) == undo_before
    finally:
        _close(app, dialog)


@pytest.mark.parametrize(
    "failure_timing",
    [
        "before_insert",
        "after_insert",
        "ambiguous_after_insert",
        "clean_after_insert",
    ],
)
def test_continuous_back_calculation_undo_publication_has_one_commit_point(
    monkeypatch, failure_timing
):
    unit = FakeContinuousMAUnit(
        raw_data={"Group 1": [None, None, None], "Group 2": [None, None, None]},
        effects={"MD": (5.0, 4.0, 6.0)},
    )
    result = {
        "n1": 120.0,
        "sd1": 11.0,
        "mean1": 15.0,
        "n2": 110.0,
        "sd2": 12.0,
        "mean2": 10.0,
    }
    recorder = {}
    app, dialog = _open_continuous_dialog(
        monkeypatch,
        QtCore.QRect(20, 30, 1024, 640),
        recorder=recorder,
        ma_unit=unit,
        back_calc_result=result,
        choose_metric=True,
    )
    try:
        first = QtGui.QUndoCommand("existing first")
        discarded_redo = QtGui.QUndoCommand("existing redo branch")
        dialog.undoStack.push(first)
        dialog.undoStack.push(discarded_redo)
        dialog.undoStack.setClean()
        dialog.undoStack.undo()
        assert (dialog.undoStack.count(), dialog.undoStack.index()) == (2, 1)
        assert not dialog.undoStack.isClean()
        tables_before = [
            [
                table.item(row, column).text()
                for row in range(table.rowCount())
                for column in range(table.columnCount())
            ]
            for table in dialog.tables
        ]
        recorder["back_calc"].clear()
        original_push = QtGui.QUndoStack.push

        if failure_timing == "before_insert":

            def injected_push(_stack, _command):
                raise RuntimeError("pre-insertion push fault")
        else:

            def injected_push(stack, command):
                original_push(stack, command)
                if failure_timing == "ambiguous_after_insert":
                    dialog.back_calc_btn.setText("ambiguous state")
                elif failure_timing == "clean_after_insert":
                    stack.setClean()
                raise RuntimeError("post-insertion push anomaly")

        monkeypatch.setattr(QtGui.QUndoStack, "push", injected_push)

        if failure_timing == "before_insert":
            with pytest.raises(RuntimeError, match="pre-insertion"):
                dialog.enable_back_calculation_btn(engage=True)
            assert (dialog.undoStack.count(), dialog.undoStack.index()) == (2, 1)
            assert dialog.undoStack.command(0) is first
            assert dialog.undoStack.command(1) is discarded_redo
            assert not dialog.undoStack.isClean()
            assert [
                [
                    table.item(row, column).text()
                    for row in range(table.rowCount())
                    for column in range(table.columnCount())
                ]
                for table in dialog.tables
            ] == tables_before
            assert unit.raw_data == {
                "Group 1": [None, None, None],
                "Group 2": [None, None, None],
            }
        elif failure_timing == "after_insert":
            dialog.enable_back_calculation_btn(engage=True)
            assert (dialog.undoStack.count(), dialog.undoStack.index()) == (2, 2)
            assert dialog.undoStack.command(0) is first
            committed = dialog.undoStack.command(1)
            assert committed is not discarded_redo
            assert committed.text() == "Apply continuous back-calculation"
            assert not dialog.undoStack.isClean()
            assert unit.raw_data == {
                "Group 1": [120.0, 15.0, 11.0],
                "Group 2": [110.0, 10.0, 12.0],
            }

            dialog.undoStack.undo()
            assert (dialog.undoStack.count(), dialog.undoStack.index()) == (2, 1)
            assert unit.raw_data == {
                "Group 1": [None, None, None],
                "Group 2": [None, None, None],
            }
            dialog.undoStack.redo()
            assert (dialog.undoStack.count(), dialog.undoStack.index()) == (2, 2)
            assert dialog.undoStack.command(1) is committed
            assert unit.raw_data == {
                "Group 1": [120.0, 15.0, 11.0],
                "Group 2": [110.0, 10.0, 12.0],
            }
        else:
            with pytest.raises(RuntimeError, match="post-insertion") as caught:
                dialog.enable_back_calculation_btn(engage=True)
            assert any(
                "identity of prior undo commands" in note
                for note in getattr(caught.value, "__notes__", [])
            )
            assert [
                [
                    table.item(row, column).text()
                    for row in range(table.rowCount())
                    for column in range(table.columnCount())
                ]
                for table in dialog.tables
            ] == tables_before
            assert unit.raw_data == {
                "Group 1": [None, None, None],
                "Group 2": [None, None, None],
            }
            assert (dialog.undoStack.count(), dialog.undoStack.index()) == (0, 0)
            assert not dialog.undoStack.isClean()
            dialog.undoStack.redo()
            assert (dialog.undoStack.count(), dialog.undoStack.index()) == (0, 0)
            assert unit.raw_data == {
                "Group 1": [None, None, None],
                "Group 2": [None, None, None],
            }
        assert len(recorder["back_calc"]) == 1
    finally:
        _close(app, dialog)


@pytest.mark.parametrize("size", [(1440, 900), (1024, 640), (800, 600)])
def test_continuous_back_calculation_choice_keeps_guidance_and_actions_reachable(
    monkeypatch, size
):
    import continuous_data_form

    available = QtCore.QRect(20, 30, *size)
    monkeypatch.setattr(
        continuous_data_form.adaptive_window,
        "available_geometry_for_window",
        lambda _window: QtCore.QRect(available),
    )
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = continuous_data_form.ChooseBackCalcResultForm(
        "Required back-calculation guidance " * 40,
        "Use equal population standard deviations",
        "Use unequal population standard deviations",
    )
    try:
        dialog.show()
        app.processEvents()
        assert (
            adaptive_window.adaptive_window_state(dialog).role
            is adaptive_window.WindowRole.TRANSACTIONAL
        )
        assert dialog.info_label.wordWrap()
        assert not dialog.content_scroll.isAncestorOf(dialog.buttonBox)
        assert available.contains(dialog.frameGeometry())
        dialog.choice1_btn.setFocus()
        app.processEvents()
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
        label_position = dialog.choice2_label.mapTo(
            dialog.content_scroll.viewport(), QtCore.QPoint()
        )
        assert (
            dialog.content_scroll.viewport()
            .rect()
            .intersects(QtCore.QRect(label_position, dialog.choice2_label.size()))
        )
        assert dialog.choice2_label.text() == (
            "Use unequal population standard deviations"
        )
        assert dialog.choice1_btn.isChecked()
        QtTest.QTest.mouseClick(dialog.choice2_label, QtCore.Qt.MouseButton.LeftButton)
        assert dialog.choice2_btn.isChecked()
    finally:
        dialog.close()
