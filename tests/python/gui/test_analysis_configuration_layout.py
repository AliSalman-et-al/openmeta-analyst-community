import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, cast
import subprocess
import sys
from types import SimpleNamespace

import pytest
from PyQt6 import QtCore, QtGui, QtWidgets
from rc_metastudio import analysis_dataset


ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RCMS_STUB_BACKEND", "1")
os.environ.setdefault("RCMS_QT6_BUILD_ROOT", str(ROOT / "build" / "qt6-verification"))
from rc_metastudio.qt6_ui import prepare_generated_ui_imports
from test_types import key_click, required, wait

prepare_generated_ui_imports()

if TYPE_CHECKING:
    from ui_analysis_setup_dialog import Ui_AnalysisSetupDialog
else:
    from rc_metastudio.forms.ui_analysis_setup_dialog import Ui_AnalysisSetupDialog


class _AnalysisModel(object):
    def __init__(self, data_type, covariates=()):
        self._data_type = data_type
        self.current_effect = "Sens" if data_type == "diagnostic" else "OR"
        self.dataset = analysis_dataset.Dataset()
        self.dataset.covariates = list(covariates)

    def get_current_outcome_type(self):
        return self._data_type

    def included_studies_have_raw_data(self):
        return True

    def included_studies_have_point_estimates(self, effect):
        return True

    def get_studies(
        self, only_if_included: bool = True
    ) -> list[analysis_dataset.Study]:
        return []


def _install_analysis_backend(monkeypatch, analysis_setup_dialog):
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
    backend = sys.modules.get("rc_metastudio.r_bridge", analysis_setup_dialog.r_bridge)
    monkeypatch.setattr(analysis_setup_dialog, "r_bridge", backend)
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
        "dataset_to_simple_binary_r_object",
        "dataset_to_simple_continuous_r_object",
        "dataset_to_simple_diagnostic_r_object",
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
    dialog = QtWidgets.QDialog()
    ui = Ui_AnalysisSetupDialog()
    ui.setupUi(dialog)
    try:
        assert ui.content_scroll_area.widgetResizable()
        assert ui.content_scroll_area.isAncestorOf(ui.specs_tab)
        assert not ui.content_scroll_area.isAncestorOf(ui.buttonBox)
        layout = required(dialog.layout(), "dialog layout")
        assert layout.indexOf(ui.buttonBox) > layout.indexOf(ui.content_scroll_area)
    finally:
        dialog.close()


def test_analysis_setup_keeps_scratch_plot_path_internal(qapp, monkeypatch):
    from rc_metastudio import analysis_setup_dialog

    _install_analysis_backend(monkeypatch, analysis_setup_dialog)
    dialog = analysis_setup_dialog.AnalysisSetupDialog(
        _AnalysisModel("binary"), confidence_level=95.0
    )
    try:
        assert dialog.image_path.text().endswith("forest.png")
        assert dialog.label_3.isHidden()
        assert dialog.image_path.isHidden()
        assert dialog.save_btn.isHidden()
    finally:
        dialog.close()


@pytest.mark.parametrize(
    ("data_type", "diagnostic_metrics", "expected_title", "expected_method_label"),
    (
        ("binary", None, "Method & Parameters", "Analysis method:"),
        ("continuous", None, "Method & Parameters", "Analysis method:"),
        (
            "diagnostic",
            ["lr", "dor"],
            "Method & Parameters for Likelihood Ratios and Diagnostic Odds Ratio",
            "Method for Likelihood Ratios and Diagnostic Odds Ratio",
        ),
    ),
)
def test_method_dialog_wording_is_scoped_to_its_analysis_family(
    qapp,
    monkeypatch,
    data_type,
    diagnostic_metrics,
    expected_title,
    expected_method_label,
):
    from rc_metastudio import analysis_setup_dialog

    _install_analysis_backend(monkeypatch, analysis_setup_dialog)
    dialog = analysis_setup_dialog.AnalysisSetupDialog(
        _AnalysisModel(data_type),
        diagnostic_metrics=diagnostic_metrics,
        confidence_level=95.0,
    )
    try:
        assert dialog.windowTitle() == expected_title
        assert dialog.method_lbl.text() == expected_method_label
    finally:
        dialog.close()


@pytest.mark.parametrize(
    ("analysis_type", "expected_title", "expected_method_label"),
    (
        (
            "meta-regression",
            "Reitsma Meta-Regression",
            "Reitsma bivariate model",
        ),
        (
            None,
            "Method & Parameters for Sensitivity and Specificity",
            "Method for Sensitivity and Specificity",
        ),
    ),
    ids=["meta-regression", "standard"],
)
def test_diagnostic_reitsma_method_layout_and_meta_regression_uses_joint_mode(
    monkeypatch, qapp, analysis_type, expected_title, expected_method_label
):
    from rc_metastudio import adaptive_window, analysis_adapter, analysis_setup_dialog

    covariate = SimpleNamespace(name="quality", data_type=4)
    model = _AnalysisModel("diagnostic", (covariate,))
    backend = sys.modules.get("rc_metastudio.r_bridge", analysis_setup_dialog.r_bridge)
    monkeypatch.setattr(
        backend,
        "dataset_to_simple_diagnostic_r_object",
        lambda *_args, **_kwargs: None,
        raising=False,
    )
    monkeypatch.setattr(
        backend,
        "get_available_methods",
        lambda **_kwargs: {"Reitsma bivariate model": "diagnostic.reitsma"},
        raising=False,
    )
    monkeypatch.setattr(
        backend,
        "get_params",
        lambda _method: (
            {
                "estimator": ["REML", "ML"],
                "conf.level": "float",
                "adjust": "float",
                "correction.policy": [
                    "Studies with any zero cell",
                    "All studies if any zero exists",
                    "None",
                ],
                "digits": "int",
            },
            {
                "estimator": "REML",
                "conf.level": 95.0,
                "adjust": 0.5,
                "correction.policy": "All studies if any zero exists",
                "digits": 2,
            },
            ["estimator", "conf.level", "adjust", "correction.policy", "digits"],
            {},
        ),
        raising=False,
    )
    monkeypatch.setattr(
        backend,
        "get_method_description",
        lambda _method: "Count-based joint Reitsma model",
        raising=False,
    )
    monkeypatch.setattr(
        backend,
        "get_analysis_plot_capabilities",
        lambda *_args, **_kwargs: [],
        raising=False,
    )

    dialog = analysis_setup_dialog.AnalysisSetupDialog(
        model,
        analysis_type=analysis_type,
        diagnostic_metrics=["sens", "spec"],
        confidence_level=95.0,
    )
    try:
        monkeypatch.setattr(
            adaptive_window,
            "available_geometry_for_window",
            lambda _window: QtCore.QRect(0, 0, 800, 600),
        )
        font = QtGui.QFont(dialog.font())
        font.setPointSize(max(14, font.pointSize() + 5))
        dialog.setFont(font)
        dialog.specs_tab.setCurrentWidget(dialog.methods_tab)
        dialog.show()
        qapp.processEvents()

        assert dialog.windowTitle() == expected_title
        assert dialog.method_lbl.text() == expected_method_label
        assert dialog.current_method == "diagnostic.reitsma"
        assert dialog.diagnostic_regression_group.isHidden() is (
            analysis_type == "meta-regression"
        )
        assert dialog.regression_model_group.isHidden() is (
            analysis_type == "meta-regression"
        )
        method_text_width = dialog.method_cbo_box.fontMetrics().horizontalAdvance(
            dialog.method_cbo_box.currentText()
        )
        assert method_text_width <= dialog.method_cbo_box.width(), (
            method_text_width,
            dialog.method_cbo_box.width(),
            dialog.method_cbo_box.sizeHint().width(),
            dialog.width(),
            dialog.method_lbl.width(),
            dialog.methods_tab.width(),
            required(
                dialog.method_cbo_box.parentWidget(), "method combo parent"
            ).width(),
            dialog.parameter_grp_box.width(),
        )
        estimator = next(
            combo
            for combo in dialog.parameter_grp_box.findChildren(QtWidgets.QComboBox)
            if combo.findData("REML") >= 0
        )
        assert [estimator.itemText(i) for i in range(estimator.count())] == [
            "REML",
            "ML",
        ]
        assert estimator.currentData() == "REML"
        estimator.setCurrentText("ML")
        assert estimator.currentData() == "ML"
        assert dialog.current_param_vals["estimator"] == "ML"
        assert dialog.buttonBox.isVisible()
        assert dialog.contentsRect().contains(dialog.buttonBox.geometry().center())

        if analysis_type is None:
            return

        requests = []
        monkeypatch.setattr(
            analysis_adapter,
            "execute_meta_regression_request",
            lambda *args, **_kwargs: requests.append(args) or {},
        )
        monkeypatch.setattr(
            dialog,
            "_run_analysis",
            lambda operation, *_args, **_kwargs: operation(),
        )
        dialog.run_meta_regression()
        request = requests[0][3]
        assert request.method == "diagnostic.reitsma"
        assert request.metric == "Sens"
        assert request.parameter_values()["joint.metrics"] == "Sens,Spec"
    finally:
        dialog.close()
        qapp.processEvents()


def test_diagnostic_reitsma_meta_regression_hides_legacy_controls_for_factor_and_multiple_moderators(
    monkeypatch, qapp
):
    """Joint Reitsma regression must not expose univariate model controls."""
    from rc_metastudio import analysis_setup_dialog

    continuous = SimpleNamespace(name="threshold", data_type=0)
    factor = SimpleNamespace(name="reader", data_type=1)
    model = _AnalysisModel("diagnostic", (continuous, factor))
    backend = sys.modules.get("rc_metastudio.r_bridge", analysis_setup_dialog.r_bridge)
    monkeypatch.setattr(
        backend,
        "dataset_to_simple_diagnostic_r_object",
        lambda *_args, **_kwargs: None,
        raising=False,
    )
    monkeypatch.setattr(
        backend,
        "get_available_methods",
        lambda **_kwargs: {"Reitsma bivariate model": "diagnostic.reitsma"},
        raising=False,
    )
    monkeypatch.setattr(
        backend,
        "get_params",
        lambda _method: (
            {
                "estimator": ["REML", "ML"],
                "conf.level": "float",
                "adjust": "float",
                "correction.policy": [
                    "Studies with any zero cell",
                    "All studies if any zero exists",
                    "None",
                ],
                "digits": "int",
            },
            {
                "estimator": "REML",
                "conf.level": 95.0,
                "adjust": 0.5,
                "correction.policy": "All studies if any zero exists",
                "digits": 2,
            },
            ["estimator", "conf.level", "adjust", "correction.policy", "digits"],
            {},
        ),
        raising=False,
    )
    monkeypatch.setattr(
        backend, "get_method_description", lambda _method: "Reitsma", raising=False
    )
    monkeypatch.setattr(
        backend, "get_analysis_plot_capabilities", lambda *_args, **_kwargs: [
            {"plot_kind": "forest", "styleable": True}
        ], raising=False
    )

    dialog = analysis_setup_dialog.AnalysisSetupDialog(
        model,
        analysis_type="meta-regression",
        diagnostic_metrics=["sens", "spec"],
        confidence_level=95.0,
    )
    try:
        assert dialog.regression_model_group.isHidden()
        assert dialog.diagnostic_regression_group.isHidden()
        assert not dialog.fixed_effects_radio.isVisible()
        assert len(dialog.covs_and_check_boxes) == 2
        # A factor moderator cannot use the bubble-plot controls. Selecting it
        # alongside the continuous moderator also proves multiple moderators
        # do not re-enable the obsolete plot path.
        dialog.covs_and_check_boxes[1][1].setChecked(True)
        assert not dialog.plot_tab.isEnabled()
    finally:
        dialog.close()


def test_meta_regression_missing_moderator_confirmation_names_excluded_studies(
    monkeypatch, qapp
):
    from rc_metastudio import analysis_adapter, analysis_setup_dialog

    covariate = SimpleNamespace(name="quality", data_type=0)
    model = _AnalysisModel("continuous", (covariate,))
    _install_analysis_backend(monkeypatch, analysis_setup_dialog)
    dialog = analysis_setup_dialog.AnalysisSetupDialog(
        model, analysis_type="meta-regression", confidence_level=95.0
    )
    messages = []
    monkeypatch.setattr(
        analysis_adapter,
        "select_studies_for_covariates",
        lambda *_args, **_kwargs: analysis_adapter.StudySelectionResult(
            studies=(),
            has_missing_values=True,
            excluded_study_names=("Study A", "Study B"),
        ),
    )
    monkeypatch.setattr(
        analysis_setup_dialog.QMessageBox,
        "warning",
        lambda _parent, _title, text, _buttons: messages.append(text)
        or QtWidgets.QMessageBox.StandardButton.No,
    )
    try:
        dialog.run_meta_regression()
        assert len(messages) == 1
        assert "Study A, Study B" in messages[0]
        assert "Run the regression without those studies?" in messages[0]
    finally:
        dialog.close()


def test_method_parameters_variants_stay_bounded_and_stable(qapp, monkeypatch):
    from rc_metastudio import adaptive_window
    from rc_metastudio import analysis_setup_dialog

    _install_analysis_backend(monkeypatch, analysis_setup_dialog)
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
            dialog = analysis_setup_dialog.AnalysisSetupDialog(
                _AnalysisModel(data_type, covariates),
                analysis_type=workflow,
                diagnostic_metrics=diagnostic_metrics,
                confidence_level=95.0,
            )
            dialogs.append(dialog)
            font = QtGui.QFont(dialog.font())
            font.setPointSize(max(14, font.pointSize() + 5))
            dialog.setFont(font)
            dialog.show()
            qapp.processEvents()

            assert (
                adaptive_window.adaptive_window_state(dialog).policy.archetype
                is adaptive_window.WindowArchetype.TRANSACTIONAL
            )
            assert dialog.frameGeometry().width() <= 720
            assert dialog.frameGeometry().height() <= 540
            assert dialog.buttonBox.isVisible()
            assert dialog.contentsRect().contains(dialog.buttonBox.geometry().center())

            stable_geometry = QtCore.QRect(dialog.frameGeometry())
            plot_was_enabled = dialog.plot_tab.isEnabled()
            if dialog.method_cbo_box.count() > 1:
                dialog.method_cbo_box.setCurrentIndex(1)
                qapp.processEvents()
            assert dialog.frameGeometry() == stable_geometry
            if workflow not in ("meta-regression",):
                assert plot_was_enabled is True
                assert dialog.plot_tab.isEnabled() is False

            if getattr(dialog, "_combined_diagnostic", False):
                # Combined diagnostic dialogs intentionally expose shared
                # method parameters in their dedicated panel. Their local
                # method box need not contain a second enum control.
                continue

            enum_control = dialog.parameter_grp_box.findChild(QtWidgets.QComboBox)
            enum_control = cast(
                QtWidgets.QComboBox,
                required(enum_control, "parameter combo"),
            )
            assert enum_control.maximumWidth() == QtWidgets.QWIDGETSIZE_MAX
            complete_value_width = max(
                enum_control.fontMetrics().horizontalAdvance(enum_control.itemText(i))
                for i in range(enum_control.count())
            )
            combo_view = required(enum_control.view(), "parameter combo view")
            assert combo_view.minimumWidth() <= 800
            if (
                complete_value_width
                > required(combo_view.viewport(), "combo viewport").width()
            ):
                enum_control.showPopup()
                qapp.processEvents()
                assert (
                    required(combo_view.window(), "combo popup").frameGeometry().width()
                    <= 800
                )
                assert (
                    required(
                        combo_view.horizontalScrollBar(), "combo scrollbar"
                    ).maximum()
                    > 0
                )
                enum_control.hidePopup()
            if data_type != "diagnostic":
                editable_value = cast(
                    QtWidgets.QLineEdit,
                    required(
                        dialog.parameter_grp_box.findChild(QtWidgets.QLineEdit),
                        "editable value",
                    ),
                )
                assert editable_value.text() == "complete editable value"
                required(
                    dialog.content_scroll_area.verticalScrollBar(), "vertical scrollbar"
                ).setValue(0)
                editable_value.setFocus()
                qapp.processEvents()
                visible_region = required(
                    dialog.content_scroll_area.viewport(), "content viewport"
                ).rect()
                control_center = editable_value.mapTo(
                    required(dialog.content_scroll_area.viewport(), "content viewport"),
                    editable_value.rect().center(),
                )
                assert visible_region.contains(control_center)
            assert required(
                dialog.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok),
                "ok button",
            ).isVisible()
            assert required(
                dialog.buttonBox.button(
                    QtWidgets.QDialogButtonBox.StandardButton.Cancel
                ),
                "cancel button",
            ).isVisible()

            dialog.method_cbo_box.setFocus()
            initial_focus = required(qapp.focusWidget(), "initial focus")
            key_click(initial_focus, QtCore.Qt.Key.Key_Tab)
            qapp.processEvents()
            forward_focus = required(qapp.focusWidget(), "forward focus")
            assert forward_focus is not initial_focus
            key_click(forward_focus, QtCore.Qt.Key.Key_Backtab)
            qapp.processEvents()
            assert qapp.focusWidget() is not forward_focus
            assert dialog.isAncestorOf(required(qapp.focusWidget(), "current focus"))
    finally:
        for dialog in dialogs:
            dialog.close()


def test_method_parameters_opens_at_its_content_preferred_width(qapp, monkeypatch):
    from rc_metastudio import adaptive_window
    from rc_metastudio import analysis_setup_dialog

    _install_analysis_backend(monkeypatch, analysis_setup_dialog)
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

    dialog = analysis_setup_dialog.AnalysisSetupDialog(
        _AnalysisModel("binary"), confidence_level=95.0
    )
    try:
        dialog.show()
        wait(1)
        qapp.processEvents()

        assert dialog.frameGeometry().width() <= 1728
        assert (
            required(
                dialog.content_scroll_area.horizontalScrollBar(), "horizontal scrollbar"
            ).maximum()
            == 0
        )
    finally:
        dialog.close()


def test_subgroup_and_covariate_selectors_use_transactional_layouts(qapp, monkeypatch):
    from rc_metastudio import adaptive_controls
    from rc_metastudio import adaptive_window
    from rc_metastudio import covariate_type_dialog
    from rc_metastudio import subgroup_analysis_dialog
    from rc_metastudio.meta_globals import FACTOR

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

    study = SimpleNamespace(covariate_values={long_name: "north"}, id=1)

    class Model(object):
        current_effect = "OR"
        dataset = SimpleNamespace(
            covariates=[Covariate()],
            get_covariate_values=lambda *_args, **_kwargs: {1: "north"},
        )

        def get_current_outcome_type(self):
            return "binary"

        def get_studies(self, only_if_included=False):
            return [study]

    parent = QtWidgets.QWidget()
    setattr(parent, "meta_subgroup", lambda _covariate: None)
    subgroup = subgroup_analysis_dialog.SubgroupAnalysisDialog(Model(), parent=parent)

    class PreviewModel(QtGui.QStandardItemModel):
        dataError = QtCore.pyqtSignal(str)

        def __init__(self, _dataset, _covariate):
            super(PreviewModel, self).__init__(2, 3)

    monkeypatch.setattr(covariate_type_dialog, "CovariateTypeModel", PreviewModel)
    covariate_type = covariate_type_dialog.CovariateTypeDialog(
        SimpleNamespace(), SimpleNamespace(), parent=parent
    )
    try:
        subgroup.show()
        covariate_type.show()
        qapp.processEvents()

        assert (
            adaptive_window.adaptive_window_state(subgroup).policy.archetype
            is adaptive_window.WindowArchetype.TRANSACTIONAL
        )
        assert subgroup.covariate_combo_box.currentText() == long_name
        choice = subgroup.covariate_combo_box
        subgroup.move(available.right() - 20, available.top() + 40)
        choice_view = cast(
            QtWidgets.QAbstractItemView, required(choice.view(), "choice view")
        )
        original_column_width = choice_view.sizeHintForColumn(0)
        enlarged = QtGui.QFont(choice.font())
        enlarged.setPointSize(enlarged.pointSize() + 6)
        choice.setFont(enlarged)
        choice.showPopup()
        qapp.processEvents()
        qapp.processEvents()
        popup = required(choice_view.window(), "choice popup")
        assert available.contains(popup.frameGeometry())
        assert choice_view.textElideMode() == QtCore.Qt.TextElideMode.ElideNone
        assert (
            choice_view.horizontalScrollBarPolicy()
            == QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        assert (
            required(choice_view.horizontalScrollBar(), "choice scrollbar").maximum()
            > 0
        )
        assert choice.itemData(0, QtCore.Qt.ItemDataRole.ToolTipRole) == long_name
        assert choice.toolTip() == long_name
        assert choice_view.sizeHintForColumn(0) > original_column_width
        choice.hidePopup()
        assert (
            adaptive_window.adaptive_window_state(covariate_type).policy.archetype
            is adaptive_window.WindowArchetype.TRANSACTIONAL
        )
        assert covariate_type.covariate_preview_table.verticalScrollMode() == (
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerItem
        )
        assert covariate_type.buttonBox.isVisible()
    finally:
        subgroup.close()
        covariate_type.close()
        parent.close()


def test_choice_control_remeasures_font_and_style_before_bounded_popup(
    qapp, monkeypatch
):
    from rc_metastudio import adaptive_controls

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
    combo_view = required(combo.view(), "combo view")
    initial_width = combo_view.minimumWidth()

    font = QtGui.QFont(combo.font())
    font.setPointSize(font.pointSize() + 6)
    combo.setFont(font)
    qapp.processEvents()
    font_width = combo_view.minimumWidth()

    class WideChromeStyle(QtWidgets.QProxyStyle):
        def pixelMetric(self, metric, option=None, widget=None):
            value = super(WideChromeStyle, self).pixelMetric(metric, option, widget)
            if metric == QtWidgets.QStyle.PixelMetric.PM_ScrollBarExtent:
                return value + 30
            return value

    style = WideChromeStyle()
    combo.setStyle(style)
    combo.showPopup()
    qapp.processEvents()
    qapp.processEvents()
    try:
        assert font_width > initial_width
        assert combo_view.minimumWidth() > font_width
        assert (
            required(combo_view.window(), "combo popup").frameGeometry().width() <= 2000
        )
        assert combo.itemData(1, QtCore.Qt.ItemDataRole.ToolTipRole) == combo.itemText(
            1
        )
    finally:
        combo.hidePopup()
        combo.close()


def test_choice_popup_show_burst_coalesces_measurement_tooltips_and_clamp(qapp):
    from rc_metastudio import adaptive_controls

    available = QtCore.QRect(
        required(qapp.primaryScreen(), "primary screen").availableGeometry()
    )
    combo = adaptive_controls.AdaptiveComboBox()
    combo.addItems(["short", "complete choice " * 80])
    combo.resize(180, combo.sizeHint().height())
    combo.move(available.right() - 10, available.top() + available.height() // 3)
    controller = adaptive_controls.configure_choice_control(combo)
    combo.show()
    qapp.processEvents()
    combo_view = required(combo.view(), "combo view")
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
        assert available.contains(
            required(combo_view.window(), "combo popup").frameGeometry()
        )
        assert (
            required(combo_view.horizontalScrollBar(), "combo scrollbar").maximum() > 0
        )
        assert combo.itemData(1, QtCore.Qt.ItemDataRole.ToolTipRole) == combo.itemText(
            1
        )
    finally:
        combo.hidePopup()
        combo.close()


def test_native_windows_promoted_choice_popup_is_bounded_at_real_right_edge():
    if sys.platform != "win32":
        pytest.skip("The native Windows Qt platform is unavailable on this host")

    script = r"""
import json
from rc_metastudio import app_error_handler
from PyQt6 import QtCore, QtWidgets
from rc_metastudio import adaptive_controls
from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()
from rc_metastudio.forms.ui_subgroup_analysis_dialog import Ui_SubgroupAnalysisDialog

app = app_error_handler.get_or_create_application([])
dialog = QtWidgets.QDialog()
ui = Ui_SubgroupAnalysisDialog()
ui.setupUi(dialog)
combo = ui.covariate_combo_box
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
    "tooltip_complete": combo.itemData(
        1, QtCore.Qt.ItemDataRole.ToolTipRole
    ) == extreme,
}
print("NATIVE_CHOICE_POPUP=" + json.dumps(result))
combo.hidePopup()
dialog.close()
app.processEvents()
"""
    environment = os.environ.copy()
    environment.pop("QT_QPA_PLATFORM", None)
    environment["RCMS_QT6_BUILD_ROOT"] = str(ROOT / "build" / "qt6-verification")
    environment["PYTHONPATH"] = os.pathsep.join(
        [
            str(ROOT / "src"),
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
    from rc_metastudio import analysis_setup_dialog

    _install_analysis_backend(monkeypatch, analysis_setup_dialog)

    def make_dialog():
        dialog = analysis_setup_dialog.AnalysisSetupDialog(
            _AnalysisModel("binary"), confidence_level=95.0
        )
        dialog.buttonBox.accepted.disconnect()
        dialog.buttonBox.accepted.connect(dialog.accept)
        dialog.show()
        qapp.processEvents()
        return dialog

    accepted = make_dialog()
    accepted.method_cbo_box.setFocus()
    key_click(accepted.method_cbo_box, QtCore.Qt.Key.Key_Return)
    qapp.processEvents()
    assert accepted.result() == QtWidgets.QDialog.DialogCode.Accepted

    cancelled = make_dialog()
    cancelled.method_cbo_box.setFocus()
    key_click(cancelled.method_cbo_box, QtCore.Qt.Key.Key_Escape)
    qapp.processEvents()
    assert cancelled.result() == QtWidgets.QDialog.DialogCode.Rejected
    accepted.close()
    cancelled.close()
    qapp.processEvents()


def test_dot_and_comma_decimal_locales_produce_equivalent_analysis_requests():
    script = r"""
import json
from types import SimpleNamespace
from PyQt6 import QtCore, QtWidgets
from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()
from rc_metastudio import app_error_handler
from rc_metastudio import analysis_adapter
from rc_metastudio import analysis_setup_dialog

class Model:
    current_effect = "OR"
    dataset = SimpleNamespace(covariates=[])
    def get_current_outcome_type(self):
        return "binary"
    def included_studies_have_raw_data(self):
        return True

backend = analysis_setup_dialog.r_bridge
data_calls = []
backend.dataset_to_simple_binary_r_object = lambda *args, **kwargs: data_calls.append("binary")
backend.get_available_methods = lambda **kwargs: {"Random": "binary.random"}
backend.get_params = lambda method: (
    {"conf.level": "float"}, {"conf.level": 95.0}, ["conf.level"], {}
)
backend.get_method_description = lambda method: "Random-effects analysis"
backend.get_analysis_plot_capabilities = lambda *args, **kwargs: []

app = app_error_handler.get_or_create_application([])
observed = []
backend_calls = []
execution_data_calls = []
backend.run_binary_analysis = lambda method, params: backend_calls.append(
    [method, params["conf.level"]]
) or {"texts": {}}
for locale, text in (
    (QtCore.QLocale(QtCore.QLocale.Language.English), "90.5"),
    (QtCore.QLocale(QtCore.QLocale.Language.German), "90,5"),
):
    dialog = analysis_setup_dialog.AnalysisSetupDialog(Model(), confidence_level=95.0)
    confidence_inputs = dialog.parameter_grp_box.findChildren(
        QtWidgets.QDoubleSpinBox
    )
    assert len(confidence_inputs) == 1
    confidence_input = confidence_inputs[0]
    confidence_input.setLocale(locale)
    confidence_input.lineEdit().setText(text)
    confidence_input.interpretText()
    request = dialog.analysis_requests()[0]
    observed.append(request.parameter_values()["conf.level"])
    confidence_input.setValue(11.0)
    data_calls.clear()
    analysis_adapter.execute_analysis_requests(dialog.model, (request,))
    execution_data_calls.extend(data_calls)
    dialog.close()
    app.processEvents()
print("LOCALE_ANALYSIS_REQUESTS=" + json.dumps({
    "requests": observed, "backend_calls": backend_calls,
    "data_calls": execution_data_calls
}))
"""
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["RCMS_STUB_BACKEND"] = "1"
    environment["RCMS_QT6_BUILD_ROOT"] = str(ROOT / "build" / "qt6-verification")
    environment["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src")])
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
        if line.startswith("LOCALE_ANALYSIS_REQUESTS=")
    )
    assert json.loads(marker.split("=", 1)[1]) == {
        "requests": [90.5, 90.5],
        "backend_calls": [["binary.random", 90.5], ["binary.random", 90.5]],
        "data_calls": ["binary", "binary"],
    }


def test_backend_execution_uses_only_frozen_analysis_requests(monkeypatch):
    cases = [
        ("binary", "standard", "run_binary_analysis"),
        ("binary", "cumulative", "run_workflow_analysis"),
        ("continuous", "standard", "run_continuous_analysis"),
        ("continuous", "leave-one-out", "run_workflow_analysis"),
        ("diagnostic", "standard", "run_diagnostic_multi"),
        ("diagnostic", "subgroup", "run_diagnostic_workflow"),
    ]
    from rc_metastudio import analysis_adapter
    from rc_metastudio import analysis_setup_dialog

    backend = analysis_setup_dialog.r_bridge
    for converter in (
        "dataset_to_simple_binary_r_object",
        "dataset_to_simple_continuous_r_object",
        "dataset_to_simple_diagnostic_r_object",
    ):
        monkeypatch.setattr(backend, converter, lambda *_args, **_kwargs: None)

    for data_type, workflow, backend_name in cases:
        calls = []

        def capture(*args):
            calls.append(args)
            return {"texts": {"Summary": "ok"}, "images": {}}

        monkeypatch.setattr(backend, backend_name, capture)
        metric = {
            "binary": "OR",
            "continuous": "SMD",
            "diagnostic": "DOR",
        }[data_type]
        mutable_parameters = {"conf.level": 90.5, "measure": metric}
        request = analysis_adapter.make_analysis_request(
            data_type=data_type,
            workflow=workflow,
            method="diagnostic.random"
            if data_type == "diagnostic"
            else data_type + ".random",
            metric=metric,
            parameters=mutable_parameters,
        )
        mutable_parameters["conf.level"] = 1.0
        mutable_parameters["measure"] = "MUTATED"

        analysis_adapter.execute_analysis_requests(
            _AnalysisModel(data_type), (request,)
        )

        rendered = repr(calls)
        assert "90.5" in rendered
        assert "MUTATED" not in rendered
        assert (workflow in rendered) is (workflow != "standard")


def test_meta_regression_backend_execution_uses_frozen_request(monkeypatch):
    from rc_metastudio import analysis_adapter
    from rc_metastudio import analysis_setup_dialog

    calls = []
    model = _AnalysisModel("continuous")
    parameters = {"conf.level": 90.5, "measure": "SMD", "bp_xlabel": "Year"}
    request = analysis_adapter.make_analysis_request(
        data_type="continuous",
        workflow="meta-regression",
        method="meta_regression",
        metric="SMD",
        parameters=parameters,
    )
    parameters["conf.level"] = 1.0
    monkeypatch.setattr(
        analysis_setup_dialog.r_bridge,
        "dataset_to_simple_continuous_r_object",
        lambda model, **kwargs: calls.append(("data", kwargs)),
    )
    monkeypatch.setattr(
        analysis_setup_dialog.r_bridge,
        "run_meta_regression",
        lambda *args, **kwargs: calls.append(("backend", args, kwargs)) or {},
    )

    analysis_adapter.execute_meta_regression_request(
        model,
        (analysis_dataset.Study("Study"),),
        (analysis_dataset.Covariate("Covariate", "continuous"),),
        request,
        True,
        95.0,
    )

    rendered = repr(calls)
    assert "90.5" in rendered
    assert "1.0" not in rendered
    assert "SMD" in rendered
    assert isinstance(calls[0][1]["studies"][0], analysis_dataset.Study)
    assert isinstance(calls[0][1]["covs_to_include"][0], analysis_dataset.Covariate)
