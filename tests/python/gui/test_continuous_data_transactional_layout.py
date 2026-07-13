import pytest
from PyQt5 import QtCore, QtGui, QtTest, QtWidgets


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
    monkeypatch.setattr(
        continuous_data_form.adaptive_window,
        "available_geometry_for_window",
        lambda _window: QtCore.QRect(available),
    )
    if choose_metric:

        def choose_second_option(dialog):
            dialog.show()
            app.processEvents()
            QtTest.QTest.mouseClick(dialog.choice2_label, QtCore.Qt.LeftButton)
            QtTest.QTest.mouseClick(
                dialog.buttonBox.button(QtWidgets.QDialogButtonBox.Ok),
                QtCore.Qt.LeftButton,
            )
            return dialog.result()

        monkeypatch.setattr(
            continuous_data_form.ChooseBackCalcResultForm,
            "exec",
            choose_second_option,
        )
    else:
        monkeypatch.setattr(
            continuous_data_form.ChooseBackCalcResultForm, "exec", lambda self: False
        )
    monkeypatch.setattr(
        continuous_data_form.meta_py_r, "get_mult_from_r", lambda _conf: 1.96
    )
    monkeypatch.setattr(
        continuous_data_form.meta_py_r,
        "continuous_convert_scale",
        lambda value, *_args, **_kwargs: value,
    )
    recorder = recorder if recorder is not None else {}
    recorder.setdefault("impute", [])
    recorder.setdefault("pre_post", [])

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
    monkeypatch.setattr(
        continuous_data_form.meta_py_r,
        "back_calc_cont_data",
        lambda *_args, **_kwargs: back_calc_result or {"FAIL": True},
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


@pytest.mark.parametrize("size", [(1440, 900), (1024, 640), (800, 600)])
def test_continuous_variants_are_transactional_and_screen_bounded(monkeypatch, size):
    available = QtCore.QRect(20, 30, *size)
    app, dialog = _open_continuous_dialog(monkeypatch, available)
    try:
        dialog.show()
        app.processEvents()

        assert dialog.property("RCMS_window_archetype") == "transactional"
        assert isinstance(dialog.content_scroll, QtWidgets.QScrollArea)
        assert dialog.content_scroll.widgetResizable()
        assert not dialog.content_scroll.isAncestorOf(dialog.buttonBox)
        assert not isinstance(dialog.simple_group, QtWidgets.QGroupBox)
        assert not isinstance(dialog.effect_group, QtWidgets.QGroupBox)
        assert dialog.label_13.text() == "Effect"
        assert dialog.label_14.text() == "Est."
        assert [
            dialog.label_15.text(),
            dialog.label_2.text(),
            dialog.label_16.text(),
        ] == [
            "[",
            ",",
            "]",
        ]
        assert available.contains(dialog.frameGeometry())
        for table in (
            dialog.simple_table,
            dialog.g1_pre_post_table,
            dialog.g2_pre_post_table,
        ):
            assert table.horizontalScrollBarPolicy() == QtCore.Qt.ScrollBarAsNeeded
            assert (
                table.horizontalHeader().sectionResizeMode(0)
                == QtWidgets.QHeaderView.Interactive
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


@pytest.mark.parametrize("size", [(1440, 900), (1024, 640), (800, 600)])
@pytest.mark.parametrize("variant", ["md_simple", "smd_pre_post", "tx_mean"])
def test_continuous_major_variant_behavior_matrix(monkeypatch, size, variant):
    available = QtCore.QRect(20, 30, *size)
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
        assert edited_table.item(0, 1).text() == "95"
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
        assert view.textElideMode() == QtCore.Qt.ElideNone
        assert view.horizontalScrollBarPolicy() == QtCore.Qt.ScrollBarAsNeeded
        assert view.horizontalScrollBar().maximum() > 0
        assert dialog.effect_cbo_box.itemData(smd_index, QtCore.Qt.ToolTipRole) == (
            full_value
        )
        dialog.effect_cbo_box.hidePopup()
    finally:
        _close(app, dialog)


@pytest.mark.parametrize("size", [(1440, 900), (1024, 640), (800, 600)])
def test_successful_continuous_back_calculation_updates_data_without_root_growth(
    monkeypatch, size
):
    available = QtCore.QRect(20, 30, *size)
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
        ma_unit=unit,
        back_calc_result=result,
        choose_metric=True,
    )
    try:
        dialog.show()
        app.processEvents()
        settled = QtCore.QRect(dialog.frameGeometry())
        assert dialog.back_calc_btn.isEnabled()

        QtTest.QTest.mouseClick(dialog.back_calc_btn, QtCore.Qt.LeftButton)
        app.processEvents()

        assert dialog.metric_parameter is False
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
        assert dialog.property("RCMS_window_archetype") == "transactional"
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
        QtTest.QTest.mouseClick(dialog.choice2_label, QtCore.Qt.LeftButton)
        assert dialog.choice2_btn.isChecked()
    finally:
        dialog.close()
