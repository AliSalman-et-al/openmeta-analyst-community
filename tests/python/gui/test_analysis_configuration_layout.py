import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest


ROOT = Path(__file__).resolve().parents[3]


class _AnalysisModel(object):
    def __init__(self, data_type, covariates=()):
        self._data_type = data_type
        self.current_effect = "Sens" if data_type == "diagnostic" else "OR"
        self.dataset = SimpleNamespace(covariates=list(covariates))

    def get_current_outcome_type(self):
        return self._data_type

    def included_studies_have_raw_data(self):
        return True


def _install_analysis_backend(monkeypatch, ma_specs):
    methods = {
        "A concise random-effects method": "random",
        "A deliberately long fixed-effect method whose full name must remain selectable": "fixed",
    }
    diagnostic_methods = {
        "A concise diagnostic random-effects method": "diagnostic-random",
        "A deliberately long diagnostic fixed-effect method whose full name must remain selectable": "diagnostic-fixed",
    }
    parameters = {
        "estimator": [
            "short",
            "A deliberately long estimator value that must remain visible in the popup",
        ],
        "conf.level": "float",
        "digits": "int",
        "label": "string",
    }
    defaults = {
        "estimator": "short",
        "conf.level": 95.0,
        "digits": 2,
        "label": "complete editable value",
    }
    backend = sys.modules.get("meta_py_r", ma_specs.meta_py_r)
    monkeypatch.setattr(ma_specs, "meta_py_r", backend)
    monkeypatch.setattr(
        backend,
        "get_available_methods",
        lambda **kwargs: (
            diagnostic_methods
            if kwargs.get("for_data_type") == "diagnostic"
            else methods
        ),
    )
    monkeypatch.setattr(
        backend,
        "get_params",
        lambda method: (
            {
                name: definition
                for name, definition in parameters.items()
                if not str(method).startswith("diagnostic-") or name != "label"
            },
            {
                name: value
                for name, value in defaults.items()
                if not str(method).startswith("diagnostic-") or name != "label"
            },
            [
                name
                for name in parameters
                if not str(method).startswith("diagnostic-") or name != "label"
            ],
            {},
        ),
    )
    monkeypatch.setattr(
        backend,
        "get_method_description",
        lambda method: ("A long method description that wraps locally. " * 8) + method,
    )
    for name in (
        "ma_dataset_to_simple_binary_robj",
        "ma_dataset_to_simple_continuous_robj",
        "ma_dataset_to_simple_diagnostic_robj",
    ):
        monkeypatch.setattr(backend, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        backend,
        "get_analysis_plot_capabilities",
        lambda _data_type, method, **_kwargs: (
            [{"plot_kind": "forest", "styleable": True}]
            if str(method).endswith("fixed")
            else []
        ),
        raising=False,
    )


def test_method_parameters_declares_scroll_body_with_actions_outside(qapp):
    from forms.ui_ma_specs import Ui_Dialog

    dialog = QtWidgets.QDialog()
    ui = Ui_Dialog()
    ui.setupUi(dialog)
    try:
        assert ui.content_scroll_area.widgetResizable()
        assert ui.content_scroll_area.isAncestorOf(ui.specs_tab)
        assert not ui.content_scroll_area.isAncestorOf(ui.buttonBox)
        assert dialog.layout().indexOf(ui.buttonBox) > dialog.layout().indexOf(
            ui.content_scroll_area
        )
    finally:
        dialog.close()


def test_method_parameters_variants_stay_bounded_and_stable(
    qapp, monkeypatch
):
    import adaptive_window
    import ma_specs

    _install_analysis_backend(monkeypatch, ma_specs)
    monkeypatch.setattr(
        adaptive_window,
        "available_geometry_for_window",
        lambda _window: QtCore.QRect(0, 0, 800, 600),
    )

    dialogs = []
    try:
        long_covariate = SimpleNamespace(
            name="A continuous moderator with a deliberately long complete name",
            data_type=0,
        )
        for data_type, diagnostic_metrics, workflow, covariates in (
            ("binary", None, None, ()),
            ("continuous", None, None, ()),
            ("diagnostic", ["sens", "spec"], None, ()),
            ("diagnostic", ["lr", "dor"], None, ()),
            ("diagnostic", ["sens", "spec", "lr", "dor"], None, ()),
            ("continuous", None, "meta-regression", (long_covariate,)),
            ("continuous", None, "subgroup", ()),
        ):
            dialog = ma_specs.MA_Specs(
                _AnalysisModel(data_type, covariates),
                meta_f_str=workflow,
                diag_metrics=diagnostic_metrics,
                conf_level=95.0,
            )
            dialogs.append(dialog)
            font = QtGui.QFont(dialog.font())
            font.setPointSize(max(14, font.pointSize() + 5))
            dialog.setFont(font)
            dialog.show()
            qapp.processEvents()

            assert dialog.property("RCMS_window_archetype") == "transactional"
            assert dialog.frameGeometry().width() <= 720
            assert dialog.frameGeometry().height() <= 540
            assert dialog.buttonBox.isVisible()
            assert dialog.contentsRect().contains(dialog.buttonBox.geometry().center())

            stable_geometry = QtCore.QRect(dialog.frameGeometry())
            plot_was_enabled = dialog.plot_tab.isEnabled()
            dialog.method_cbo_box.setCurrentIndex(1)
            qapp.processEvents()
            assert dialog.frameGeometry() == stable_geometry
            if workflow not in ("meta-regression",):
                assert plot_was_enabled is True
                assert dialog.plot_tab.isEnabled() is False

            enum_control = dialog.parameter_grp_box.findChild(QtWidgets.QComboBox)
            assert enum_control.maximumWidth() == QtWidgets.QWIDGETSIZE_MAX
            complete_value_width = max(
                enum_control.fontMetrics().horizontalAdvance(enum_control.itemText(i))
                for i in range(enum_control.count())
            )
            assert enum_control.view().minimumWidth() <= 800
            if complete_value_width > enum_control.view().viewport().width():
                enum_control.showPopup()
                qapp.processEvents()
                assert enum_control.view().window().frameGeometry().width() <= 800
                assert enum_control.view().horizontalScrollBar().maximum() > 0
                enum_control.hidePopup()
            editable_value = dialog.parameter_grp_box.findChild(QtWidgets.QLineEdit)
            if data_type != "diagnostic":
                assert editable_value.text() == "complete editable value"
                dialog.content_scroll_area.verticalScrollBar().setValue(0)
                editable_value.setFocus()
                qapp.processEvents()
                visible_region = dialog.content_scroll_area.viewport().rect()
                control_center = editable_value.mapTo(
                    dialog.content_scroll_area.viewport(), editable_value.rect().center()
                )
                assert visible_region.contains(control_center)
            assert dialog.buttonBox.button(QtWidgets.QDialogButtonBox.Ok).isVisible()
            assert dialog.buttonBox.button(QtWidgets.QDialogButtonBox.Cancel).isVisible()

            dialog.method_cbo_box.setFocus()
            initial_focus = qapp.focusWidget()
            QTest.keyClick(initial_focus, QtCore.Qt.Key_Tab)
            qapp.processEvents()
            forward_focus = qapp.focusWidget()
            assert forward_focus is not initial_focus
            QTest.keyClick(forward_focus, QtCore.Qt.Key_Backtab)
            qapp.processEvents()
            assert qapp.focusWidget() is not forward_focus
            assert dialog.isAncestorOf(qapp.focusWidget())
    finally:
        for dialog in dialogs:
            dialog.close()


def test_method_parameters_opens_at_its_content_preferred_width(qapp, monkeypatch):
    import adaptive_window
    import ma_specs

    _install_analysis_backend(monkeypatch, ma_specs)
    monkeypatch.setattr(
        adaptive_window,
        "available_geometry_for_window",
        lambda _window: QtCore.QRect(0, 0, 1920, 1080),
    )
    monkeypatch.setattr(
        adaptive_window.AdaptiveWindowController,
        "_connect_runtime_screen",
        lambda _controller, _screen: None,
    )

    dialog = ma_specs.MA_Specs(_AnalysisModel("binary"), conf_level=95.0)
    try:
        dialog.show()
        QTest.qWait(1)
        qapp.processEvents()

        assert dialog.frameGeometry().width() <= 1728
        assert dialog.content_scroll_area.horizontalScrollBar().maximum() == 0
    finally:
        dialog.close()


def test_regression_and_subgroup_selectors_use_transactional_layouts(qapp, monkeypatch):
    import adaptive_controls
    import change_cov_type_form
    import meta_reg_form
    import meta_subgroup_form
    from meta_globals import FACTOR

    long_name = "A factor covariate " + ("complete-value-" * 80)
    available = QtCore.QRect(100, 50, 800, 600)
    monkeypatch.setattr(
        adaptive_controls,
        "available_geometry_for_choice_control",
        lambda _combo: QtCore.QRect(available),
        raising=False,
    )

    class Covariate(object):
        name = long_name
        data_type = FACTOR

        def get_data_type(self):
            return FACTOR

    study = SimpleNamespace(covariate_dict={long_name: "north"}, id=1)

    class Model(object):
        current_effect = "OR"
        dataset = SimpleNamespace(
            covariates=[Covariate()],
            get_values_for_cov=lambda *_args, **_kwargs: {1: "north"},
        )

        def get_current_outcome_type(self):
            return "binary"

        def get_studies(self, only_if_included=False):
            return [study]

    parent = QtWidgets.QWidget()
    parent.meta_subgroup = lambda _covariate: None
    regression = meta_reg_form.MetaRegForm(Model(), parent=parent)
    subgroup = meta_subgroup_form.MetaSubgroupForm(Model(), parent=parent)
    class PreviewModel(QtGui.QStandardItemModel):
        dataError = QtCore.pyqtSignal(str)

        def __init__(self, _dataset, _covariate):
            super(PreviewModel, self).__init__(2, 3)

    monkeypatch.setattr(change_cov_type_form, "CovModel", PreviewModel)
    covariate_type = change_cov_type_form.ChangeCovTypeForm(
        SimpleNamespace(), SimpleNamespace(), parent=parent
    )
    try:
        regression.show()
        subgroup.show()
        covariate_type.show()
        qapp.processEvents()

        assert regression.property("RCMS_window_archetype") == "transactional"
        assert regression.content_scroll_area.isAncestorOf(regression.cov_grp_box)
        assert not regression.content_scroll_area.isAncestorOf(regression.buttonBox)
        assert subgroup.property("RCMS_window_archetype") == "transactional"
        assert subgroup.cov_subgroup_cbo_box.currentText() == long_name
        choice = subgroup.cov_subgroup_cbo_box
        subgroup.move(available.right() - 20, available.top() + 40)
        original_column_width = choice.view().sizeHintForColumn(0)
        enlarged = QtGui.QFont(choice.font())
        enlarged.setPointSize(enlarged.pointSize() + 6)
        choice.setFont(enlarged)
        choice.showPopup()
        qapp.processEvents()
        qapp.processEvents()
        popup = choice.view().window()
        assert available.contains(popup.frameGeometry())
        assert choice.view().textElideMode() == QtCore.Qt.ElideNone
        assert choice.view().horizontalScrollBarPolicy() == QtCore.Qt.ScrollBarAsNeeded
        assert choice.view().horizontalScrollBar().maximum() > 0
        assert choice.itemData(0, QtCore.Qt.ToolTipRole) == long_name
        assert choice.toolTip() == long_name
        assert choice.view().sizeHintForColumn(0) > original_column_width
        choice.hidePopup()
        assert covariate_type.property("RCMS_window_archetype") == "transactional"
        assert covariate_type.cov_prev_table.verticalScrollMode() == (
            QtWidgets.QAbstractItemView.ScrollPerItem
        )
        assert covariate_type.buttonBox.isVisible()
    finally:
        regression.close()
        subgroup.close()
        covariate_type.close()
        parent.close()


def test_choice_control_remeasures_font_and_style_before_bounded_popup(
    qapp, monkeypatch
):
    import adaptive_controls

    monkeypatch.setattr(
        adaptive_controls,
        "available_geometry_for_choice_control",
        lambda _combo: QtCore.QRect(0, 0, 2000, 1200),
    )
    combo = adaptive_controls.AdaptiveComboBox()
    combo.addItems(["short", "A moderately long complete choice value"])
    adaptive_controls.configure_choice_control(combo)
    combo.resize(180, combo.sizeHint().height())
    combo.show()
    qapp.processEvents()
    initial_width = combo.view().minimumWidth()

    font = QtGui.QFont(combo.font())
    font.setPointSize(font.pointSize() + 6)
    combo.setFont(font)
    qapp.processEvents()
    font_width = combo.view().minimumWidth()

    class WideChromeStyle(QtWidgets.QProxyStyle):
        def pixelMetric(self, metric, option=None, widget=None):
            value = super(WideChromeStyle, self).pixelMetric(metric, option, widget)
            if metric == QtWidgets.QStyle.PM_ScrollBarExtent:
                return value + 30
            return value

    style = WideChromeStyle()
    combo.setStyle(style)
    combo.showPopup()
    qapp.processEvents()
    qapp.processEvents()
    try:
        assert font_width > initial_width
        assert combo.view().minimumWidth() > font_width
        assert combo.view().window().frameGeometry().width() <= 2000
        assert combo.itemData(1, QtCore.Qt.ToolTipRole) == combo.itemText(1)
    finally:
        combo.hidePopup()
        combo.close()


def test_choice_popup_show_burst_coalesces_measurement_tooltips_and_clamp(qapp):
    import adaptive_controls

    available = QtCore.QRect(qapp.primaryScreen().availableGeometry())
    combo = adaptive_controls.AdaptiveComboBox()
    combo.addItems(["short", "complete choice " * 80])
    combo.resize(180, combo.sizeHint().height())
    combo.move(available.right() - 10, available.top() + available.height() // 3)
    controller = adaptive_controls.configure_choice_control(combo)
    combo.show()
    qapp.processEvents()
    baseline = (
        controller.measurement_applied_count,
        controller.tooltip_scan_applied_count,
        controller.popup_clamp_applied_count,
    )
    combo.addItem("a late model value")
    combo.showPopup()
    qapp.processEvents()
    qapp.processEvents()
    try:
        applied = (
            controller.measurement_applied_count - baseline[0],
            controller.tooltip_scan_applied_count - baseline[1],
            controller.popup_clamp_applied_count - baseline[2],
        )
        assert applied == (1, 1, 1)
        assert available.contains(combo.view().window().frameGeometry())
        assert combo.view().horizontalScrollBar().maximum() > 0
        assert combo.itemData(1, QtCore.Qt.ToolTipRole) == combo.itemText(1)
    finally:
        combo.hidePopup()
        combo.close()


def test_native_windows_promoted_choice_popup_is_bounded_at_real_right_edge():
    if sys.platform != "win32":
        pytest.skip("The native Windows Qt platform is unavailable on this host")

    script = r'''
import json
import app_error_handler
from PyQt5 import QtCore, QtWidgets
import adaptive_controls
from forms.ui_cov_subgroup_dlg import Ui_cov_subgroup_dialog

app = app_error_handler.get_or_create_application([])
dialog = QtWidgets.QDialog()
ui = Ui_cov_subgroup_dialog()
ui.setupUi(dialog)
combo = ui.cov_subgroup_cbo_box
assert isinstance(combo, adaptive_controls.AdaptiveComboBox)
combo.addItem("short")
controller = adaptive_controls.configure_choice_control(combo)
available = QtCore.QRect(app.primaryScreen().availableGeometry())
dialog.adjustSize()
dialog.move(
    available.right() - dialog.width() + 1,
    available.top() + available.height() // 3,
)
dialog.show()
dialog.raise_()
dialog.activateWindow()
combo.setFocus()
app.processEvents()
baseline = (
    controller.measurement_applied_count,
    controller.tooltip_scan_applied_count,
    controller.popup_clamp_applied_count,
)
extreme = "native complete choice " * 200
combo.addItem(extreme)
combo.showPopup()
popup = combo.view().window()
settle = QtCore.QEventLoop()
QtCore.QTimer.singleShot(50, settle.quit)
settle.exec()
result = {
    "platform": app.platformName(),
    "contained": available.contains(popup.frameGeometry()),
    "measurement_delta": controller.measurement_applied_count - baseline[0],
    "tooltip_delta": controller.tooltip_scan_applied_count - baseline[1],
    "clamp_delta": controller.popup_clamp_applied_count - baseline[2],
    "horizontal_access": combo.view().horizontalScrollBar().maximum() > 0,
    "tooltip_complete": combo.itemData(1, QtCore.Qt.ToolTipRole) == extreme,
}
print("NATIVE_CHOICE_POPUP=" + json.dumps(result))
combo.hidePopup()
dialog.close()
app.processEvents()
'''
    environment = os.environ.copy()
    environment.pop("QT_QPA_PLATFORM", None)
    environment["PYTHONPATH"] = os.pathsep.join(
        [
            str(ROOT / "src"),
            str(ROOT / "src" / "rc_metastudio"),
            str(ROOT / "src" / "rc_metastudio" / "forms"),
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    marker = next(
        line
        for line in completed.stdout.splitlines()
        if line.startswith("NATIVE_CHOICE_POPUP=")
    )
    result = json.loads(marker.split("=", 1)[1])
    assert result == {
        "platform": "windows",
        "contained": True,
        "measurement_delta": 1,
        "tooltip_delta": 1,
        "clamp_delta": 1,
        "horizontal_access": True,
        "tooltip_complete": True,
    }


def test_method_parameters_default_and_cancel_keyboard_actions(qapp, monkeypatch):
    import ma_specs

    _install_analysis_backend(monkeypatch, ma_specs)

    def make_dialog():
        dialog = ma_specs.MA_Specs(_AnalysisModel("binary"), conf_level=95.0)
        dialog.buttonBox.accepted.disconnect()
        dialog.buttonBox.accepted.connect(dialog.accept)
        dialog.show()
        qapp.processEvents()
        return dialog

    accepted = make_dialog()
    accepted.method_cbo_box.setFocus()
    QTest.keyClick(accepted.method_cbo_box, QtCore.Qt.Key_Return)
    qapp.processEvents()
    assert accepted.result() == QtWidgets.QDialog.Accepted

    cancelled = make_dialog()
    cancelled.method_cbo_box.setFocus()
    QTest.keyClick(cancelled.method_cbo_box, QtCore.Qt.Key_Escape)
    qapp.processEvents()
    assert cancelled.result() == QtWidgets.QDialog.Rejected
