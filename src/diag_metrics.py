from PyQt5.QtWidgets import QDialog, QMessageBox

import forms.ui_diagnostic_metrics
import app_error_handler
import ma_specs
import qt_layout
from meta_globals import DIAG_METRIC_NAMES_D


class Diag_Metrics(QDialog, forms.ui_diagnostic_metrics.Ui_diag_metric):
    SELECTABLE_METRICS = ["sens", "spec", "dor", "lr"]

    def __init__(self, model, parent=None, meta_f_str=None, external_params=None):
        super(Diag_Metrics, self).__init__(parent)
        self.setupUi(self)
        self.model = model
        self.parent = parent
        self.external_params = external_params
        self.meta_f_str = meta_f_str
        self.btn_ok.pressed.connect(app_error_handler.safe_slot(self.ok, parent=self))
        self._configure_metric_checkboxes()
        for metric in self.SELECTABLE_METRICS:
            self._metric_checkbox(metric).toggled.connect(
                app_error_handler.safe_slot(self._refresh_ok_enabled, parent=self)
            )
        qt_layout.fit_analysis_dialog_to_contents(self)

    def ok(self):
        selected_metrics = self.get_selected_metrics()
        if not selected_metrics:
            QMessageBox.warning(
                self,
                "No diagnostic metric selected",
                "Select at least one available diagnostic metric before running analysis.",
            )
            return

        # Route the Method & Parameters dialog through the parent's shared
        # error-handling builder (the same path the binary/continuous case
        # uses). This keeps construction failures from propagating out of this
        # Qt slot and being silently swallowed by the event loop. See issue #53.
        builder = getattr(self.parent, "_build_analysis_specs_dialog", None)
        if builder is not None:
            form = builder(
                meta_f_str=self.meta_f_str,
                external_params=self.external_params,
                diag_metrics=selected_metrics,
                conf_level=self.model.get_global_conf_level(),
            )
        else:
            form = ma_specs.MA_Specs(
                self.model,
                parent=self.parent,
                meta_f_str=self.meta_f_str,
                external_params=self.external_params,
                diag_metrics=selected_metrics,
                conf_level=self.model.get_global_conf_level(),
            )
        if form is None:
            return
        form.show()
        self.hide()

    def get_selected_metrics(self):
        selected_metrics = []
        # just loop through all the check
        # boxes on the form and see if they're checked.

        for metric in self.SELECTABLE_METRICS:
            checkbox = self._metric_checkbox(metric)
            if checkbox.isEnabled() and checkbox.isChecked():
                print(metric)
                selected_metrics.append(metric)

        return selected_metrics

    def _configure_metric_checkboxes(self):
        raw_data_available = self.model.included_studies_have_raw_data()
        for metric in self.SELECTABLE_METRICS:
            checkbox = self._metric_checkbox(metric)
            metric_available = (
                raw_data_available
                or self._entered_estimates_available_for_metric(metric)
            )
            checkbox.setEnabled(metric_available)
            checkbox.setChecked(checkbox.isChecked() and metric_available)
            if metric_available:
                checkbox.setToolTip("")
            else:
                checkbox.setToolTip(
                    "Requires complete TP/FN/FP/TN counts or complete entered "
                    "effect estimates and confidence intervals for this metric."
                )
        self._refresh_ok_enabled()

    def _entered_estimates_available_for_metric(self, metric):
        return all(
            self.model.included_studies_have_point_estimates(effect=effect)
            for effect in DIAG_METRIC_NAMES_D[metric]
        )

    def _refresh_ok_enabled(self):
        self.btn_ok.setEnabled(
            any(
                self._metric_checkbox(metric).isEnabled()
                and self._metric_checkbox(metric).isChecked()
                for metric in self.SELECTABLE_METRICS
            )
        )

    def _metric_checkbox(self, metric):
        return getattr(self, "chk_box_%s" % metric)
