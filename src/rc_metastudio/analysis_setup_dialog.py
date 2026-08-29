# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Method-selection dialog and analysis specification builder."""

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent, QColor, QHideEvent, QShowEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QDoubleSpinBox,
    QSizePolicy,
    QSpinBox,
)

import copy
import hashlib
import os
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

from rc_metastudio import (
    adaptive_controls,
    adaptive_window,
    analysis_adapter,
    app_error_handler,
    plot_capabilities,
    progress_dialog,
    qt_text,
    r_bridge,
)
from rc_metastudio.analysis_method_labels import (
    diagnostic_metric_group_display_label,
    normalize_available_method_labels,
    parameter_description,
    parameter_display_label,
    parameter_value_display_label,
)
from rc_metastudio.plot_defaults import apply_default_forest_arm_labels
from rc_metastudio.plot_text import apply_plot_text_input_limits
from rc_metastudio.meta_globals import (
    ANALYSIS_COUNT_MAX,
    ANALYSIS_DIGITS_MAX,
    ANALYSIS_DIGITS_MIN,
    ANALYSIS_NON_NEGATIVE_FLOAT_PARAMS,
    ANALYSIS_NON_NEGATIVE_INTEGER_PARAMS,
    ANALYSIS_NUMERIC_MAX,
    ANALYSIS_NUMERIC_MIN,
    ANALYSIS_POSITIVE_INTEGER_PARAMS,
    CONFIDENCE_LEVEL_DISPLAY_MAX,
    CONTINUOUS,
    DIAGNOSTIC_METRIC_GROUPS,
    ONE_ARM_METRICS,
    check_plot_bound,
    seems_sane,
    validate_analysis_count,
    validate_analysis_digits,
    validate_analysis_float,
    validate_confidence_level,
    validate_correction_factor,
)
from rc_metastudio.settings import analysis_output_path

if TYPE_CHECKING:
    from ui_analysis_setup_dialog import Ui_AnalysisSetupDialog
else:
    from rc_metastudio.forms.ui_analysis_setup_dialog import Ui_AnalysisSetupDialog

PLOT_STYLE_LABELS = {
    "default": "Default (metafor)",
    "revman": "RevMan",
    "bmj": "BMJ",
}
PLOT_STYLE_VALUES = {label: value for value, label in PLOT_STYLE_LABELS.items()}
PLOT_STYLE_DEFAULT_COLORS = {
    "default": "#2f5597",
    "revman": "#000000",
    "bmj": "#6b58a6",
}

COUNT_BASED_DIAGNOSTIC_METHODS = {
    "diagnostic.bivariate.ml",
    "diagnostic.hsroc",
}

SHARED_DIAGNOSTIC_PARAMS = ("conf.level", "digits", "adjust", "to")

ParameterKind = Literal["enum", "float", "int", "string"]


@dataclass(frozen=True)
class _ParameterDefinition:
    name: str
    kind: ParameterKind
    default: object
    metadata: object
    values: tuple[object, ...] = ()


def _normalize_parameter_definition(
    name: str, definition: object, default: object, metadata: object
) -> _ParameterDefinition:
    if isinstance(definition, list):
        return _ParameterDefinition(name, "enum", default, metadata, tuple(definition))
    if _is_integer_analysis_param(name) or str(definition).lower() == "int":
        kind: ParameterKind = "int"
    elif str(definition).lower() == "string":
        kind = "string"
    else:
        kind = "float"
    return _ParameterDefinition(name, kind, default, metadata)


class _DiagnosticMethodPanel(object):
    """A group-specific method editor used by the unified diagnostic dialog."""

    def __init__(self, owner, label, metric, label_widget, combo, param_box):
        self.owner = owner
        self.metric = metric
        self.params = {}
        self.widgets = []
        self.label = label_widget
        self.label.setText(label)
        self.combo = combo
        self.param_box = param_box
        owner._configure_method_selector(self.combo)
        self.param_box.setLayout(QGridLayout())
        self.combo.currentTextChanged.connect(
            app_error_handler.safe_slot(
                lambda _text: self._method_changed(), parent=owner
            )
        )

    @property
    def method(self):
        return self.methods[str(self.combo.currentText())]

    def populate(self):
        r_bridge.dataset_to_simple_diagnostic_r_object(
            self.owner.model, var_name="tmp_obj"
        )
        self.methods = normalize_available_method_labels(
            r_bridge.get_available_methods(
                for_data_type="diagnostic",
                data_obj_name="tmp_obj",
                metric=self.metric,
            )
        )
        names = [
            name
            for name in self.methods
            if self.methods[name] not in COUNT_BASED_DIAGNOSTIC_METHODS
        ]
        if "Diagnostic Fixed-Effect Peto" in names:
            names.remove("Diagnostic Fixed-Effect Peto")
        names.sort(reverse=True)
        blocked = self.combo.blockSignals(True)
        try:
            self.combo.clear()
            self.combo.addItems(names)
        finally:
            self.combo.blockSignals(blocked)
        self._method_changed()

    def _method_changed(self):
        for widget in self.widgets:
            self.param_box.layout().removeWidget(widget)
            widget.deleteLater()
        self.widgets = []
        self.params = {}
        method = self.method
        definitions, defaults, order, metadata = r_bridge.get_params(method)
        self.param_box.setTitle(str(self.combo.currentText()))
        description = QLabel(
            "Description: %s" % r_bridge.get_method_description(method)
        )
        description.setWordWrap(True)
        self.param_box.layout().addWidget(description, 0, 0, 1, 2)
        self.widgets.append(description)
        row = 1
        for name in order or definitions:
            spec = _normalize_parameter_definition(
                name, definitions[name], defaults.get(name), metadata.get(name)
            )
            if name in SHARED_DIAGNOSTIC_PARAMS:
                self.owner._register_shared_diagnostic_param(
                    spec,
                )
                continue
            label = self.owner._parameter_label(spec)
            control = self.owner._create_parameter_control(spec, self.params)
            self.param_box.layout().addWidget(label, row, 0)
            self.param_box.layout().addWidget(control, row, 1)
            self.widgets.extend((label, control))
            row += 1
        self.owner._schedule_local_reflow()


class AnalysisSetupDialog(QDialog, Ui_AnalysisSetupDialog):
    def __init__(
        self,
        model,
        parent=None,
        analysis_type=None,
        external_params=None,
        diagnostic_metrics=None,
        diagnostic_analysis_details=None,
        fp_specs_only=False,
        confidence_level=None,
    ):

        super(AnalysisSetupDialog, self).__init__(parent)
        self.setupUi(self)
        self._layout_reflow_pending = False
        self._layout_reflow_timer = QtCore.QTimer(self)
        self._layout_reflow_timer.setSingleShot(True)
        self._layout_reflow_timer.timeout.connect(self._apply_local_reflow)
        self._focus_reveal_connected = False
        for combo in self.findChildren(QComboBox):
            self._configure_value_control(combo)
        apply_plot_text_input_limits(self)
        apply_default_forest_arm_labels(self)
        if _text_value(self.image_path) == "":
            self.image_path.setText(analysis_output_path("forest.png"))
        self.current_param_vals: dict[str, object] = dict(external_params or {})
        self.analysis_type = analysis_type
        self.is_meta_regression = analysis_type == "meta-regression"
        self.model = model
        self._loading_plot_style = False
        self._setup_plot_controls()
        self._load_plot_params()

        if confidence_level is None:
            raise ValueError("CONFIDENCE LEVEL MUST BE SPECIFIED")
        self.confidence_level = validate_confidence_level(confidence_level)

        self._accepted_connection = None
        self._set_accepted_handler(
            self.run_meta_regression if self.is_meta_regression else self.run_ma
        )
        self.buttonBox.rejected.connect(
            app_error_handler.safe_slot(self.cancel, parent=self)
        )
        self.save_btn.pressed.connect(
            app_error_handler.safe_slot(self.select_out_path, parent=self)
        )
        self._configure_method_selector(self.method_cbo_box)
        self.method_cbo_box.currentTextChanged.connect(
            app_error_handler.safe_slot(
                lambda _text: self.method_changed(), parent=self
            )
        )

        self.data_type = self.model.get_current_outcome_type()
        self._setup_covariates_tab()
        if self.data_type != "binary":
            self.disable_bin_only_fields()
            if self.data_type == "diagnostic":
                self.enable_diagnostic_fields()

        # disable second arm display for one-arm analyses
        if self.model.current_effect in ONE_ARM_METRICS:
            self.setup_fields_for_one_arm()

        self.current_widgets = []
        self.current_method = ""
        self.current_params: dict[str, object] = {}
        self.current_defaults: dict[str, object] = {}
        self.param_d: dict[str, object] = {}
        self.var_order: list[str] | None = None

        # Diagnostic analyses can run several metrics at once. Map each
        # selected metric to its method and parameters, for example:
        #   diagnostic_analysis_details["Sens"] -> (method, parameters)
        # Paired metrics currently share configuration but retain separate
        # entries because downstream analysis dispatches by metric.
        self.diagnostic_analysis_details = diagnostic_analysis_details or {}

        # Callers exclude metrics already present in the details mapping.
        self.diagnostic_metrics: tuple[str, ...] = tuple(diagnostic_metrics or ())
        self._combined_diagnostic = False
        self._shared_diagnostic_param_specs = {
            "conf.level": _normalize_parameter_definition(
                "conf.level", "float", self.confidence_level, None
            ),
            "digits": _normalize_parameter_definition("digits", "int", 2, None),
            "adjust": _normalize_parameter_definition("adjust", "float", 0.5, None),
            "to": _normalize_parameter_definition(
                "to", ["only0", "all"], "only0", None
            ),
        }
        self._shared_diagnostic_widgets = []

        if self.data_type == "diagnostic":
            self.sens_spec = any(
                [m in ("sens", "spec") for m in self.diagnostic_metrics]
            )
            self.lr_dor = any([m in ("lr", "dor") for m in self.diagnostic_metrics])
            self._combined_diagnostic = self.sens_spec and self.lr_dor
            self.setup_diagnostic_ui()

        self.populate_parameter_controls()
        if self._combined_diagnostic:
            self._finish_combined_diagnostic_ui()
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )

    def sizeHint(self):
        """Include the scroll body's content width in first-use negotiation."""
        hint = super(AnalysisSetupDialog, self).sizeHint()
        if hasattr(self, "specs_tab"):
            content_hint = self.specs_tab.minimumSizeHint()
            if content_hint.isValid():
                root_layout = self.layout()
                if root_layout is None:
                    return hint
                margins = root_layout.contentsMargins()
                scrollbar = self.content_scroll_area.verticalScrollBar()
                if scrollbar is None:
                    return hint
                scrollbar_width = scrollbar.sizeHint().width()
                hint.setWidth(
                    max(
                        hint.width(),
                        content_hint.width()
                        + margins.left()
                        + margins.right()
                        + scrollbar_width,
                    )
                )
        return hint

    def showEvent(  # ty: ignore[invalid-method-override] -- PyQt6 multiple-inheritance stub mismatch
        self, event: QShowEvent | None
    ) -> None:
        super(AnalysisSetupDialog, self).showEvent(event)
        app = QtWidgets.QApplication.instance()
        if isinstance(app, QtWidgets.QApplication) and not self._focus_reveal_connected:
            app.focusChanged.connect(self._reveal_focused_control)
            self._focus_reveal_connected = True

    def hideEvent(  # ty: ignore[invalid-method-override] -- PyQt6 multiple-inheritance stub mismatch
        self, event: QHideEvent | None
    ) -> None:
        self._disconnect_focus_reveal()
        super(AnalysisSetupDialog, self).hideEvent(event)

    def closeEvent(  # ty: ignore[invalid-method-override] -- PyQt6 multiple-inheritance stub mismatch
        self, event: QCloseEvent | None
    ) -> None:
        self._release_owned_connections()
        super(AnalysisSetupDialog, self).closeEvent(event)
        self.deleteLater()

    def _disconnect_focus_reveal(self):
        if not self._focus_reveal_connected:
            return
        app = QtWidgets.QApplication.instance()
        if isinstance(app, QtWidgets.QApplication):
            try:
                app.focusChanged.disconnect(self._reveal_focused_control)
            except (TypeError, RuntimeError):
                pass
        self._focus_reveal_connected = False

    def cancel(self):
        self.reject()

    def _setup_covariates_tab(self):
        if not self.is_meta_regression:
            self.specs_tab.removeTab(self.specs_tab.indexOf(self.covariates_tab))
            self.regression_group.hide()
            return

        self.covs_and_check_boxes = []
        for row, covariate in enumerate(self.model.dataset.covariates):
            checkbox = QtWidgets.QCheckBox(covariate.name, self.covariate_group_box)
            checkbox.setChecked(row == 0)
            checkbox.toggled.connect(
                app_error_handler.safe_slot(
                    self._update_meta_regression_ok, parent=self
                )
            )
            checkbox.toggled.connect(
                app_error_handler.safe_slot(
                    self._update_meta_regression_plot_availability, parent=self
                )
            )
            self.covariates_layout.addWidget(checkbox, row, 0)
            self.covs_and_check_boxes.append((covariate, checkbox))
        self.diagnostic_regression_group.setVisible(self.data_type == "diagnostic")
        self.image_path.setText(analysis_output_path("reg.png"))
        self._update_meta_regression_ok()
        self._update_meta_regression_plot_availability()

    def _selected_covariates(self):
        return [
            covariate
            for covariate, checkbox in self.covs_and_check_boxes
            if checkbox.isChecked()
        ]

    def _update_meta_regression_ok(self):
        button = self.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        if button is not None:
            button.setEnabled(bool(self._selected_covariates()))

    def _update_meta_regression_plot_availability(self):
        if not self.is_meta_regression:
            return
        selected = self._selected_covariates()
        bubble_available = len(selected) == 1 and selected[0].data_type == CONTINUOUS
        self.plot_tab.setEnabled(bubble_available)
        self.plot_tab.setToolTip(
            ""
            if bubble_available
            else "Bubble plot options require exactly one continuous covariate."
        )

    def _set_accepted_handler(self, handler):
        if self._accepted_connection is None:
            self._accepted_connection = app_error_handler.connect_safely(
                self.buttonBox.accepted, handler, parent=self
            )
        else:
            self._accepted_connection.replace(handler, parent=self)

    def select_out_path(self):
        out_f = "."
        out_f, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "RCMetaStudio - Plot Path",
            out_f,
            "png image files: (.png)",
        )
        if out_f == "" or out_f is None:
            return None
        else:
            self.image_path.setText(out_f)

    def _setup_plot_controls(self):
        self.color_btn.clicked.connect(
            app_error_handler.safe_slot(self._choose_plot_color, parent=self)
        )
        self.style_cbo.currentTextChanged.connect(
            app_error_handler.safe_slot(self._plot_style_changed, parent=self)
        )

    def _configure_plot_option_groups(self):
        workflow = self.analysis_type or "standard"
        capabilities = r_bridge.get_analysis_plot_capabilities(
            self.data_type, self.current_method, workflow=workflow
        )
        plot_kinds = [capability["plot_kind"] for capability in capabilities]
        groups = frozenset().union(
            *(plot_capabilities.option_groups(plot_kind) for plot_kind in plot_kinds)
        )
        self.style_group.setVisible("style" in groups)
        self.appearance_group.setVisible("appearance" in groups)
        self.groupBox.setVisible("columns" in groups)
        self.default_panel.setVisible("forest" in groups)
        self.regression_group.setVisible("regression" in groups)
        self.label_11.setVisible("summary" in groups)
        self.show_summary_line.setVisible("summary" in groups)
        self.plot_tab.setEnabled(
            any(capability["styleable"] for capability in capabilities)
        )
        self._update_meta_regression_plot_availability()

    def run_meta_regression(self):
        selected_covariates = self._selected_covariates()
        if not selected_covariates:
            QMessageBox.warning(
                self,
                "No Covariates Selected",
                "Select at least one covariate before running meta-regression.",
            )
            return

        selection = analysis_adapter.select_studies_for_covariates(
            self.model, selected_covariates
        )

        if selection.has_missing_values:
            choice = QMessageBox.warning(
                self,
                "Missing Covariate Values",
                "Some studies do not have values for the selected covariates. "
                "Run the regression without those studies?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if choice == QMessageBox.StandardButton.No:
                return

        metric = self.model.current_effect
        if self.data_type == "diagnostic":
            metric = (
                "Sens"
                if self.sensitivity_radio.isChecked()
                else "Spec"
                if self.specificity_radio.isChecked()
                else "DOR"
            )
        add_plot_params(self)
        parameters = copy.deepcopy(self.current_param_vals)
        parameters["measure"] = metric
        request = analysis_adapter.make_analysis_request(
            data_type=self.data_type,
            workflow="meta-regression",
            method="meta_regression",
            metric=metric,
            parameters=parameters,
        )
        fixed_effects = self.fixed_effects_radio.isChecked()
        self._run_analysis(
            lambda: analysis_adapter.execute_meta_regression_request(
                self.model,
                selection.studies,
                tuple(selected_covariates),
                request,
                fixed_effects,
                self.confidence_level,
            ),
            "Sorry, there was an error performing the regression.\n%s",
            string_result_is_failure=True,
        )

    def _load_plot_params(self):
        self._loading_plot_style = True
        try:
            prefix = "bp" if self.is_meta_regression else "fp"
            style = _normalized_plot_style(
                self.current_param_vals.get("%s_style" % prefix, "default")
            )
            self.style_cbo.setCurrentText(PLOT_STYLE_LABELS[style])
            self._set_plot_accent_color(
                self.current_param_vals.get("%s_accent_color" % prefix)
                or PLOT_STYLE_DEFAULT_COLORS[style]
            )
            self.point_size_multiplier.setValue(
                _float_plot_param(
                    self.current_param_vals.get("%s_point_size_multiplier" % prefix),
                    1.0,
                )
            )
            if self.is_meta_regression:
                self.show_regression_line.setChecked(
                    _bool_plot_param(
                        self.current_param_vals.get("bp_show_regression_line"), True
                    )
                )
                self.show_confidence_band.setChecked(
                    _bool_plot_param(
                        self.current_param_vals.get("bp_show_confidence_band"), True
                    )
                )
                self.show_prediction_interval.setChecked(
                    _bool_plot_param(
                        self.current_param_vals.get("bp_show_prediction_interval"),
                        False,
                    )
                )
                self.show_legend.setChecked(
                    _bool_plot_param(
                        self.current_param_vals.get("bp_show_legend"), False
                    )
                )
            self.show_raw_counts.setChecked(
                _bool_plot_param(
                    self.current_param_vals.get("fp_show_raw_counts"), True
                )
            )
            self.show_headers.setChecked(
                _bool_plot_param(self.current_param_vals.get("fp_show_headers"), True)
            )
            self.show_annotation.setChecked(
                _bool_plot_param(
                    self.current_param_vals.get("fp_show_annotation"), True
                )
            )
        finally:
            self._loading_plot_style = False

    def _plot_style_changed(self, label):
        if self._loading_plot_style:
            return
        style = PLOT_STYLE_VALUES.get(str(label), "default")
        self._set_plot_accent_color(PLOT_STYLE_DEFAULT_COLORS[style])

    def _choose_plot_color(self):
        current = QColor(self.accent_color.text())
        color = QtWidgets.QColorDialog.getColor(current, self, "Plot Accent Color")
        if color.isValid():
            self._set_plot_accent_color(color.name())

    def _set_plot_accent_color(self, color):
        text = str(color or PLOT_STYLE_DEFAULT_COLORS["default"])
        self.accent_color.setText(text)
        self.color_btn.setStyleSheet("background-color: %s;" % text)

    def run_network_analysis(self):
        bar = progress_dialog.AnalysisProgressDialog(self)
        bar.show()
        try:
            if self.data_type not in ["binary", "continuous"]:
                raise ValueError(
                    "Network Analysis can currently only be done with binary or continuous data"
                )

            r_bridge.dataset_to_simple_network(
                table_model=self.model,
                var_name="tmp_obj",
                data_type=None,
                outcome=None,
                follow_up=None,
                network_path=analysis_output_path("network.png"),
            )
        finally:
            progress_dialog.hide_once(bar)

    def run_ma(self):
        self._run_analysis(
            lambda: analysis_adapter.execute_analysis_requests(
                self.model, self.analysis_requests()
            ),
            "Sorry, this analysis could not be completed:\n\n%s",
        )

    def _run_analysis(self, operation, failure_message, string_result_is_failure=False):
        bar = progress_dialog.AnalysisProgressDialog(self)
        bar.show()
        result = None
        succeeded = False
        try:
            result = operation()
            if string_result_is_failure and isinstance(result, str):
                raise RuntimeError(result)
            succeeded = True
        except Exception as error:
            app_error_handler.log_exception(type(error), error, error.__traceback__)
            QMessageBox.critical(self, "Analysis Failed", failure_message % error)
            _reset_r_working_dir_safely()
        finally:
            _dispose_progress(bar)
        try:
            if succeeded:
                self._deliver_result(result)
        finally:
            self.done(QDialog.DialogCode.Accepted.value)

    def done(  # ty: ignore[invalid-method-override] -- PyQt6 generated-form multiple inheritance
        self, result: int
    ) -> None:
        self._release_owned_connections()
        super().done(result)
        self.deleteLater()

    def _release_owned_connections(self) -> None:
        self._disconnect_focus_reveal()
        self._layout_reflow_timer.stop()
        try:
            self._layout_reflow_timer.timeout.disconnect(self._apply_local_reflow)
        except (TypeError, RuntimeError):
            pass

    def _deliver_result(self, result):
        parent = self.parentWidget()
        callback = getattr(parent, "analysis", None)
        if not callable(callback):
            raise RuntimeError("analysis configuration has no results owner")
        callback(result)

    def analysis_requests(self):
        """Return typed requests represented by the current user configuration."""
        add_plot_params(self)
        workflow = self.analysis_type or "standard"
        if self.data_type != "diagnostic":
            metric = str(self.model.current_effect)
            self.current_param_vals["measure"] = metric
            parameters = copy.deepcopy(self.current_param_vals)
            return (
                analysis_adapter.make_analysis_request(
                    data_type=self.data_type,
                    workflow=workflow,
                    method=self.current_method,
                    metric=metric,
                    parameters=parameters,
                ),
            )

        self.add_current_analysis_details()
        method_names, parameter_values = _diagnostic_analysis_requests(self)
        return tuple(
            analysis_adapter.make_analysis_request(
                data_type=self.data_type,
                workflow=workflow,
                method=method,
                metric=str(parameters["measure"]),
                parameters=parameters,
            )
            for method, parameters in zip(method_names, parameter_values)
        )

    def enable_diagnostic_fields(self):
        self.col3_str_edit.setText("[default]")
        self.show_3.setEnabled(True)
        self.show_3.setChecked(True)

    def disable_bin_only_fields(self):
        self.col3_str_edit.setEnabled(False)
        self.col4_str_edit.setEnabled(False)
        self.show_3.setChecked(False)
        self.show_3.setEnabled(False)
        self.show_4.setChecked(False)
        self.show_4.setEnabled(False)

    def setup_fields_for_one_arm(self):
        self.show_4.setChecked(False)
        self.show_4.setEnabled(False)

    def method_changed(self):
        self.clear_param_ui()
        self.current_widgets = []
        if self.available_method_d is None:
            raise RuntimeError("Analysis methods have not been initialized")
        self.current_method = self.available_method_d[
            str(self.method_cbo_box.currentText())
        ]
        self.setup_params()
        self._set_parameter_box_title(self.method_cbo_box, self.parameter_grp_box)
        self.ui_for_params(
            excluded_names=SHARED_DIAGNOSTIC_PARAMS if self._combined_diagnostic else ()
        )
        self._schedule_local_reflow()

    def _set_parameter_box_title(self, cbo_box, param_box):
        param_box.setTitle(str(cbo_box.currentText()))

    def populate_parameter_controls(self, cbo_box=None, param_box=None):
        if cbo_box is None:
            cbo_box = self.method_cbo_box
            param_box = self.parameter_grp_box

        # The backend filters methods against the selected dataset and metric.
        tmp_obj_name = "tmp_obj"
        if self.data_type == "binary":
            r_bridge.dataset_to_simple_binary_r_object(
                self.model, var_name=tmp_obj_name
            )
        elif self.data_type == "continuous":
            r_bridge.dataset_to_simple_continuous_r_object(
                self.model, var_name=tmp_obj_name
            )
        elif self.data_type == "diagnostic":
            r_bridge.dataset_to_simple_diagnostic_r_object(
                self.model, var_name=tmp_obj_name
            )

        self.available_method_d = None
        # The feasibility API accepts one diagnostic metric even when the analysis
        # configures a pair. Each supported pair has the same feasible methods, so
        # use its representative metric.
        metric = self.model.current_effect
        if self.data_type == "diagnostic":
            if self.analysis_type is None:
                metric = "Sens" if self.sens_spec else "DOR"
            else:
                metric = "Sens"

        method_query = {
            "for_data_type": self.data_type,
            "data_obj_name": tmp_obj_name,
            "metric": metric,
        }
        if self.analysis_type is not None:
            method_query["workflow"] = self.analysis_type
        self.available_method_d = r_bridge.get_available_methods(**method_query)
        self.available_method_d = normalize_available_method_labels(
            self.available_method_d
        )

        # Preserve the method order returned by the backend.
        method_names = list(self.available_method_d.keys())

        # Hide bivariate diagnostic methods when sensitivity and specificity
        # cannot both be estimated from the selected effects.
        biv_ml_name = "Bivariate (Maximum Likelihood)"
        if self.data_type == "diagnostic" and not self.is_meta_regression:
            for biv_method in (biv_ml_name, "HSROC"):
                method_function = self.available_method_d.get(biv_method)
                should_remove_bivariate_method = (
                    metric != "Sens"
                    or self.analysis_type is not None
                    or not (
                        "sens" in self.diagnostic_metrics
                        and "spec" in self.diagnostic_metrics
                    )
                    or (
                        method_function in COUNT_BASED_DIAGNOSTIC_METHODS
                        and not self.model.included_studies_have_raw_data()
                    )
                )
                if biv_method in method_names and should_remove_bivariate_method:
                    method_names.remove(biv_method)
            # Fix for issue # 175
            if all(metric in self.diagnostic_metrics for metric in ("lr", "dor")):
                peto_method = "Diagnostic Fixed-Effect Peto"
                if peto_method in method_names:
                    method_names.remove(peto_method)

        method_names.sort(reverse=True)

        # default to bivariate method for diagnostic
        if (
            self.data_type == "diagnostic"
            and not self.is_meta_regression
            and biv_ml_name in method_names
        ):
            method_names.remove(biv_ml_name)
            method_names.insert(0, biv_ml_name)

        signals_were_blocked = cbo_box.blockSignals(True)
        try:
            for method in method_names:
                cbo_box.addItem(method)
        finally:
            cbo_box.blockSignals(signals_were_blocked)
        self.current_method = self.available_method_d[str(cbo_box.currentText())]
        self.setup_params()
        self._set_parameter_box_title(cbo_box, param_box)
        if cbo_box is self.method_cbo_box:
            self.ui_for_params(
                excluded_names=SHARED_DIAGNOSTIC_PARAMS
                if self._combined_diagnostic
                else ()
            )

    def clear_param_ui(self):
        parameter_layout = self.parameter_grp_box.layout()
        for widget in self.current_widgets:
            if parameter_layout is not None:
                parameter_layout.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
            widget = None

    def ui_for_params(self, adjust_root=True, excluded_names=()):
        self._configure_plot_option_groups()
        parameter_layout = self.parameter_grp_box.layout()
        if parameter_layout is None:
            parameter_layout = QGridLayout()
            parameter_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            self.parameter_grp_box.setLayout(parameter_layout)
        if not isinstance(parameter_layout, QGridLayout):
            raise TypeError("Analysis parameters require a grid layout")

        current_grid_row = 0

        # add the method description
        method_description = r_bridge.get_method_description(self.current_method)

        self.add_method_description(
            parameter_layout,
            current_grid_row,
            "Description: %s" % method_description,
        )
        current_grid_row += 1

        definitions = [
            _normalize_parameter_definition(
                name,
                self.current_params[name],
                self.current_defaults.get(name),
                self.param_d.get(name),
            )
            for name in self.current_params
        ]
        if self.var_order is not None:
            by_name = {spec.name: spec for spec in definitions}
            definitions = [by_name[name] for name in self.var_order]
        else:
            # Keep the legacy display order when the backend omits var_order.
            definitions = [
                spec
                for kind in ("enum", "float", "int", "string")
                for spec in definitions
                if spec.kind == kind
            ]

        for spec in definitions:
            if spec.name in excluded_names:
                self._register_shared_diagnostic_param(spec)
                continue
            label = self._parameter_label(spec)
            control = self._create_parameter_control(spec, self.current_param_vals)
            self.current_widgets.extend((label, control))
            parameter_layout.addWidget(label, current_grid_row, 0)
            parameter_layout.addWidget(control, current_grid_row, 1)
            current_grid_row += 1

        self._schedule_local_reflow()

    def _parameter_label(self, spec):
        label = QLabel(parameter_display_label(spec.name, spec.metadata))
        label.setToolTip(parameter_description(spec.name, spec.metadata))
        return label

    def _create_parameter_control(self, spec, target):
        if spec.kind == "enum":
            control = adaptive_controls.AdaptiveComboBox()
            for value in spec.values:
                control.addItem(
                    parameter_value_display_label(spec.name, value, spec.metadata),
                    value,
                )
            if spec.default is not None:
                index = self._find_enum_item_index(control, spec.default)
                if index >= 0:
                    control.setCurrentIndex(index)
                target[spec.name] = self._enum_item_value(control.currentData())
            combo = control
            control.currentIndexChanged[int].connect(
                app_error_handler.safe_slot(
                    lambda index: target.__setitem__(
                        spec.name, self._enum_item_value(combo.itemData(index))
                    ),
                    parent=self,
                )
            )
        elif spec.kind == "int":
            control = QSpinBox()
            if spec.name == "digits":
                control.setRange(ANALYSIS_DIGITS_MIN, ANALYSIS_DIGITS_MAX)
            elif spec.name in ANALYSIS_POSITIVE_INTEGER_PARAMS:
                control.setRange(1, ANALYSIS_COUNT_MAX)
            elif spec.name in ANALYSIS_NON_NEGATIVE_INTEGER_PARAMS:
                control.setRange(0, ANALYSIS_COUNT_MAX)
            else:
                control.setRange(-2147483648, 2147483647)
            control.setCorrectionMode(
                QtWidgets.QAbstractSpinBox.CorrectionMode.CorrectToPreviousValue
            )
            if spec.default is not None:
                value = (
                    validate_analysis_digits(spec.default)
                    if spec.name == "digits"
                    else (
                        validate_analysis_count(spec.name, spec.default)
                        if _is_count_analysis_param(spec.name)
                        else _coerce_integer_default(spec.name, spec.default)
                    )
                )
                control.setValue(value)
                target[spec.name] = value
            control.valueChanged[int].connect(
                app_error_handler.safe_slot(
                    lambda value: target.__setitem__(spec.name, value), parent=self
                )
            )
        elif spec.kind == "float":
            control = QDoubleSpinBox()
            control.setDecimals(1 if spec.name == "conf.level" else 6)
            if spec.name == "conf.level":
                control.setRange(50, CONFIDENCE_LEVEL_DISPLAY_MAX)
                control.setSingleStep(0.1)
                control.setSuffix("%")
            elif spec.name in ANALYSIS_NON_NEGATIVE_FLOAT_PARAMS:
                control.setRange(0, ANALYSIS_NUMERIC_MAX)
            else:
                control.setRange(ANALYSIS_NUMERIC_MIN, ANALYSIS_NUMERIC_MAX)
            control.setCorrectionMode(
                QtWidgets.QAbstractSpinBox.CorrectionMode.CorrectToPreviousValue
            )
            if spec.default is not None:
                value = (
                    validate_confidence_level(spec.default)
                    if spec.name == "conf.level"
                    else (
                        validate_correction_factor(spec.default)
                        if spec.name in ANALYSIS_NON_NEGATIVE_FLOAT_PARAMS
                        else validate_analysis_float(spec.name, spec.default)
                    )
                )
                control.setValue(value)
                target[spec.name] = value
            control.valueChanged[float].connect(
                app_error_handler.safe_slot(
                    lambda value: target.__setitem__(spec.name, value), parent=self
                )
            )
        else:
            control = QLineEdit()
            if spec.default is not None:
                control.setText(str(spec.default))
                target[spec.name] = spec.default
            adaptive_controls.configure_text_value_control(control)
            control.textChanged.connect(
                app_error_handler.safe_slot(
                    lambda value: target.__setitem__(spec.name, str(value)), parent=self
                )
            )
            return control

        if isinstance(control, QComboBox):
            self._configure_value_control(control)
        else:
            adaptive_controls.configure_numeric_value_control(control)
        return control

    def _find_enum_item_index(self, cbo_box, value):
        for index in range(cbo_box.count()):
            if self._enum_item_value(cbo_box.itemData(index)) == str(value):
                return index
        return -1

    def _enum_item_value(self, item_data):
        if hasattr(item_data, "value"):
            item_data = item_data.value()
        return qt_text.to_native_text(item_data)

    def add_method_description(self, layout, current_grid_row, text):
        lbl = QLabel(text, self.parameter_grp_box)
        lbl.setWordWrap(True)
        # layout-audit: allow=content-overflow-control; reason=required content may consume available layout width
        lbl.setMinimumWidth(0)
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.current_widgets.append(lbl)
        layout.addWidget(lbl, current_grid_row, 0, 1, 2)

    def _configure_value_control(self, widget):
        adaptive_controls.configure_choice_control(widget)

    def _configure_method_selector(self, widget):
        adaptive_controls.configure_choice_control(widget, visible_characters=28)

    def _schedule_local_reflow(self):
        """Coalesce dynamic content negotiation without resizing the root window."""
        if self._layout_reflow_pending:
            return
        self._layout_reflow_pending = True
        self._layout_reflow_timer.start(0)

    def _apply_local_reflow(self):
        self._layout_reflow_pending = False
        for combo in self.content_scroll_area.findChildren(QComboBox):
            adaptive_controls.refresh_choice_popup_width(combo)
        for layout in (
            self.parameter_grp_box.layout(),
            self.shared_diagnostic_params_box.layout(),
            self.content_scroll_layout,
        ):
            if layout is not None:
                layout.invalidate()
        self.content_scroll_area_widget.updateGeometry()
        self.specs_tab.updateGeometry()
        self._reveal_focused_control(None, QtWidgets.QApplication.focusWidget())

    def _reveal_focused_control(self, _old, focused):
        if focused is not None and self.content_scroll_area.isAncestorOf(focused):
            self.content_scroll_area.ensureWidgetVisible(focused)

    def setup_params(self):
        # parses out information about the parameters of the current method
        # param_d holds (meta) information about the parameter -- it's a each param
        # itself maps to a dictionary with a pretty name and description (assuming
        # they were provided for the given param)
        self.current_params, self.current_defaults, self.var_order, self.param_d = (
            r_bridge.get_params(self.current_method)
        )

        for name, definition in self.current_params.items():
            if name not in self.current_param_vals:
                continue
            saved_value = self.current_param_vals[name]
            if isinstance(definition, list) and str(saved_value) not in {
                str(option) for option in definition
            }:
                continue
            self.current_defaults[name] = saved_value

        # The application-level confidence setting overrides method defaults.
        self.current_defaults["conf.level"] = self.confidence_level

    def _register_shared_diagnostic_param(self, spec):
        if spec.name not in SHARED_DIAGNOSTIC_PARAMS:
            return
        existing = self._shared_diagnostic_param_specs[spec.name]
        self._shared_diagnostic_param_specs[spec.name] = replace(
            existing, metadata=spec.metadata or existing.metadata
        )
        if (
            hasattr(self, "shared_diagnostic_params_box")
            and self.shared_diagnostic_params_box.layout() is not None
        ):
            self._rebuild_shared_diagnostic_params()

    def _finish_combined_diagnostic_ui(self):
        self.setWindowTitle("Method & Parameters")
        self.method_lbl.setText(diagnostic_metric_group_display_label("sens_spec"))

        self.shared_diagnostic_params_box.show()
        self.shared_diagnostic_params_box.setLayout(QGridLayout())

        lr_label = diagnostic_metric_group_display_label("lr_dor")
        self.lr_dor_method_lbl.show()
        self.lr_dor_method_cbo_box.show()
        self.lr_dor_parameter_grp_box.show()
        self.lr_dor_panel = _DiagnosticMethodPanel(
            self,
            lr_label,
            "DOR",
            self.lr_dor_method_lbl,
            self.lr_dor_method_cbo_box,
            self.lr_dor_parameter_grp_box,
        )
        self.lr_dor_panel.populate()
        self._rebuild_shared_diagnostic_params()

    def _rebuild_shared_diagnostic_params(self):
        layout = self.shared_diagnostic_params_box.layout()
        if not isinstance(layout, QGridLayout):
            raise RuntimeError("Shared diagnostic parameters require a grid layout")
        for widget in self._shared_diagnostic_widgets:
            layout.removeWidget(widget)
            widget.deleteLater()
        self._shared_diagnostic_widgets = []

        for row, name in enumerate(SHARED_DIAGNOSTIC_PARAMS):
            spec = self._shared_diagnostic_param_specs.get(name)
            if spec is None:
                continue
            value = self.current_param_vals.get(name, spec.default)
            spec = replace(spec, default=value)
            label = self._parameter_label(spec)
            control = self._create_parameter_control(spec, self.current_param_vals)
            layout.addWidget(label, row, 0)
            layout.addWidget(control, row, 1)
            self._shared_diagnostic_widgets.extend((label, control))

    def add_current_analysis_details(self):
        """This method only applicable for diagnostic data, wherein
        we have multiple metrics. here the parameters/method for
        these metrics are added to a dictionary.
        """
        # this was extracted earlier, ultimately from the checkboxes
        # selected by the user
        metrics_to_run = list(self.diagnostic_analysis_details.keys())

        if self._combined_diagnostic:
            first_params = self._diagnostic_params_for_method(
                self.current_method, self.current_param_vals
            )
            second_params = self._diagnostic_params_for_method(
                self.lr_dor_panel.method, self.lr_dor_panel.params
            )
            for metric in [m for m in ("Sens", "Spec") if m in metrics_to_run]:
                self.diagnostic_analysis_details[metric] = (
                    self.current_method,
                    copy.deepcopy(first_params),
                )
            for metric in [m for m in ("DOR", "PLR", "NLR") if m in metrics_to_run]:
                self.diagnostic_analysis_details[metric] = (
                    self.lr_dor_panel.method,
                    copy.deepcopy(second_params),
                )
        elif self.sens_spec:
            for metric in [m for m in ("Sens", "Spec") if m in metrics_to_run]:
                self.diagnostic_analysis_details[metric] = (
                    self.current_method,
                    self.current_param_vals,
                )
        else:
            for metric in [m for m in ("DOR", "PLR", "NLR") if m in metrics_to_run]:
                self.diagnostic_analysis_details[metric] = (
                    self.current_method,
                    self.current_param_vals,
                )

    def _diagnostic_params_for_method(self, method, local_params):
        definitions, _defaults, _order, _metadata = r_bridge.get_params(method)
        params = {
            name: value
            for name, value in self.current_param_vals.items()
            if name.startswith("fp_") or name.startswith("bp_")
        }
        for name in SHARED_DIAGNOSTIC_PARAMS:
            if name in definitions and name in self.current_param_vals:
                params[name] = self.current_param_vals[name]
        for name in definitions:
            if name not in SHARED_DIAGNOSTIC_PARAMS and name in local_params:
                params[name] = local_params[name]
        return params

    def setup_diagnostic_ui(self):
        if len(self.diagnostic_analysis_details) == 0:
            metrics_to_run = []
            for m in self.diagnostic_metrics:
                metrics_to_run.extend(DIAGNOSTIC_METRIC_GROUPS[m])

            self.diagnostic_analysis_details = dict(
                list(zip(metrics_to_run, [None for m in metrics_to_run]))
            )

        # Reflect the selected method in the dialog labels.
        window_title, method_label = "", ""
        if self._combined_diagnostic:
            window_title = "Method & Parameters"
            method_label = diagnostic_metric_group_display_label("sens_spec")
        elif self.sens_spec:
            metric_group_label = diagnostic_metric_group_display_label("sens_spec")
            window_title = "Method & Parameters for %s" % metric_group_label
            method_label = "Method for %s" % metric_group_label
        else:
            metric_group_label = diagnostic_metric_group_display_label("lr_dor")
            window_title = "Method & Parameters for %s" % metric_group_label
            method_label = "Method for %s" % metric_group_label

        self.setWindowTitle(QtCore.QCoreApplication.translate("Dialog", window_title))
        self.method_lbl.setText(method_label)


def _dispose_progress(progress):
    progress_dialog.hide_once(progress)
    progress.close()
    progress.deleteLater()


def _reset_r_working_dir_safely():
    try:
        r_bridge.reset_r_working_directory()
    except Exception:
        pass


def _is_count_analysis_param(name):
    return name in (
        ANALYSIS_POSITIVE_INTEGER_PARAMS | ANALYSIS_NON_NEGATIVE_INTEGER_PARAMS
    )


def _coerce_integer_default(name: str, value: object) -> int:
    """Convert a persisted integer default after validating its concrete type."""
    if not isinstance(value, (str, bytes, bytearray, int, float)):
        raise TypeError(f"Invalid integer default for {name}: {value!r}")
    return int(value)


def _is_integer_analysis_param(name):
    return name == "digits" or _is_count_analysis_param(name)


def _display_svg_path(output_path):
    root, _extension = os.path.splitext(str(output_path))
    normalized_path = os.path.normcase(os.path.abspath(str(output_path)))
    path_digest = hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()[:12]
    plot_name = os.path.basename(root) or "plot"
    return analysis_output_path("%s-%s.display.svg" % (plot_name, path_digest))


def add_plot_params(specs_form):
    if getattr(specs_form, "analysis_type", None) == "meta-regression":
        bubble_outpath = _text_value(specs_form.image_path)
        specs_form.current_param_vals.update(
            {
                "bp_style": PLOT_STYLE_VALUES.get(
                    str(specs_form.style_cbo.currentText()), "default"
                ),
                "bp_accent_color": _text_value(specs_form.accent_color),
                "bp_point_size_multiplier": specs_form.point_size_multiplier.value(),
                "bp_xlabel": _text_value(specs_form.x_lbl_le),
                "bp_xticks": _validated_plot_ticks(specs_form.x_ticks_le),
                "bp_plot_lb": _validated_plot_bound(specs_form.plot_lb_le),
                "bp_plot_ub": _validated_plot_bound(specs_form.plot_ub_le),
                "bp_outpath": bubble_outpath,
                "bp_display_path": _display_svg_path(bubble_outpath),
                "bp_show_regression_line": specs_form.show_regression_line.isChecked(),
                "bp_show_confidence_band": specs_form.show_confidence_band.isChecked(),
                "bp_show_prediction_interval": specs_form.show_prediction_interval.isChecked(),
                "bp_show_legend": specs_form.show_legend.isChecked(),
            }
        )
        return

    specs_form.current_param_vals["fp_style"] = PLOT_STYLE_VALUES.get(
        str(specs_form.style_cbo.currentText()), "default"
    )
    specs_form.current_param_vals["fp_show_col1"] = specs_form.show_1.isChecked()
    specs_form.current_param_vals["fp_col1_str"] = _text_value(specs_form.col1_str_edit)
    specs_form.current_param_vals["fp_show_col2"] = specs_form.show_2.isChecked()
    specs_form.current_param_vals["fp_col2_str"] = _text_value(specs_form.col2_str_edit)
    specs_form.current_param_vals["fp_show_col3"] = specs_form.show_3.isChecked()
    specs_form.current_param_vals["fp_col3_str"] = _text_value(specs_form.col3_str_edit)
    specs_form.current_param_vals["fp_show_col4"] = specs_form.show_4.isChecked()
    specs_form.current_param_vals["fp_col4_str"] = _text_value(specs_form.col4_str_edit)
    specs_form.current_param_vals["fp_xlabel"] = _text_value(specs_form.x_lbl_le)
    forest_outpath = _text_value(specs_form.image_path)
    specs_form.current_param_vals["fp_outpath"] = forest_outpath
    specs_form.current_param_vals["fp_display_path"] = _display_svg_path(forest_outpath)

    plot_lb = _text_value(specs_form.plot_lb_le)
    specs_form.current_param_vals["fp_plot_lb"] = "[default]"
    if plot_lb != "[default]" and check_plot_bound(plot_lb):
        specs_form.current_param_vals["fp_plot_lb"] = plot_lb

    plot_ub = _text_value(specs_form.plot_ub_le)
    specs_form.current_param_vals["fp_plot_ub"] = "[default]"
    if plot_ub != "[default]" and check_plot_bound(plot_ub):
        specs_form.current_param_vals["fp_plot_ub"] = plot_ub

    xticks = _text_value(specs_form.x_ticks_le)
    specs_form.current_param_vals["fp_xticks"] = "[default]"
    if xticks != "[default]" and seems_sane(xticks):
        specs_form.current_param_vals["fp_xticks"] = xticks

    specs_form.current_param_vals["fp_show_summary_line"] = (
        specs_form.show_summary_line.isChecked()
    )
    specs_form.current_param_vals["fp_show_raw_counts"] = (
        specs_form.show_raw_counts.isChecked()
    )
    specs_form.current_param_vals["fp_show_headers"] = (
        specs_form.show_headers.isChecked()
    )
    specs_form.current_param_vals["fp_show_annotation"] = (
        specs_form.show_annotation.isChecked()
    )
    specs_form.current_param_vals["fp_accent_color"] = _text_value(
        specs_form.accent_color
    )
    specs_form.current_param_vals["fp_point_size_multiplier"] = (
        specs_form.point_size_multiplier.value()
    )


def _validated_plot_bound(widget):
    value = _text_value(widget)
    return value if value != "[default]" and check_plot_bound(value) else "[default]"


def _validated_plot_ticks(widget):
    value = _text_value(widget)
    return value if value != "[default]" and seems_sane(value) else "[default]"


def _normalized_plot_style(style):
    style = str(_scalar_plot_param(style) or "default").strip().lower()
    return style if style in PLOT_STYLE_LABELS else "default"


def _scalar_plot_param(value):
    if isinstance(value, (list, tuple)) and value:
        return value[0]
    return value


def _bool_plot_param(value, default):
    value = _scalar_plot_param(default if value is None else value)
    if isinstance(value, str):
        return value.lower() in ("true", "t", "1", "yes")
    return bool(value)


def _float_plot_param(value, default):
    try:
        return float(_scalar_plot_param(default if value is None else value))
    except (TypeError, ValueError):
        return default


def _diagnostic_analysis_requests(specs_form):
    method_names, list_of_param_vals = [], []
    missing_metrics = []

    ordered_metrics = ["Sens", "Spec", "NLR", "PLR", "DOR"]
    for diagnostic_metric in [
        metric
        for metric in ordered_metrics
        if metric in specs_form.diagnostic_analysis_details
    ]:
        details = specs_form.diagnostic_analysis_details[diagnostic_metric]
        if details is None:
            missing_metrics.append(diagnostic_metric)
            continue

        try:
            method, param_vals = details
        except (TypeError, ValueError):
            raise ValueError(
                "Invalid method and parameter selection for: %s." % diagnostic_metric
            )

        if method is None or param_vals is None:
            missing_metrics.append(diagnostic_metric)
            continue

        param_vals = copy.deepcopy(param_vals)

        # update the forest plot path
        split_fp_path = specs_form.current_param_vals["fp_outpath"].split(".")
        new_str = (
            split_fp_path[0]
            if len(split_fp_path) == 1
            else ".".join(split_fp_path[:-1])
        )
        new_str = new_str + "_%s" % diagnostic_metric.lower() + ".png"
        param_vals["fp_outpath"] = new_str
        param_vals["fp_display_path"] = _display_svg_path(new_str)

        # update the metric
        param_vals["measure"] = diagnostic_metric

        method_names.append(method)
        list_of_param_vals.append(param_vals)

    if missing_metrics:
        raise ValueError(
            "No method and parameters were selected for: %s. "
            "Complete all diagnostic method screens before running analysis."
            % ", ".join(missing_metrics)
        )

    if not method_names:
        raise ValueError("No diagnostic metrics were configured for analysis.")

    return method_names, list_of_param_vals


def _text_value(widget):
    return qt_text.to_native_text(widget.text())
