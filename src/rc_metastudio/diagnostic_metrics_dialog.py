from typing import TYPE_CHECKING

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtWidgets import QDialog, QMessageBox, QWidget

from rc_metastudio import app_error_handler
from rc_metastudio import analysis_setup_dialog
from rc_metastudio import adaptive_window
from rc_metastudio.meta_globals import DIAGNOSTIC_METRIC_GROUPS

if TYPE_CHECKING:
    import ui_diagnostic_metrics_dialog as _ui_diagnostic_metrics_dialog
else:
    from rc_metastudio.forms import (
        ui_diagnostic_metrics_dialog as _ui_diagnostic_metrics_dialog,
    )


class DiagnosticMetricsDialog(
    QDialog, _ui_diagnostic_metrics_dialog.Ui_DiagnosticMetricsDialog
):
    SELECTABLE_METRICS = ["sens", "spec", "dor", "lr"]

    def __init__(self, model, parent=None, analysis_type=None, external_params=None):
        super(DiagnosticMetricsDialog, self).__init__(parent)
        self.setupUi(self)
        # The count-based joint workflow is the default diagnostic experience;
        # likelihood-ratio and DOR analyses remain explicit optional requests.
        self.chk_box_lr.setChecked(False)
        self.chk_box_dor.setChecked(False)
        self._configure_focus_revelation()
        self._layout_controller = adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )
        self.model = model
        self.owner = parent
        self.external_params = external_params
        self.analysis_type = analysis_type
        self.btn_ok.pressed.connect(app_error_handler.safe_slot(self.ok, parent=self))
        self._configure_metric_checkboxes()
        for metric in self.SELECTABLE_METRICS:
            self._metric_checkbox(metric).toggled.connect(
                app_error_handler.safe_slot(self._refresh_ok_enabled, parent=self)
            )
        self._request_initial_content_refit()

    def _configure_focus_revelation(self):
        for widget in self.content_widget.findChildren(QWidget):
            widget.installEventFilter(self)

    def eventFilter(  # ty: ignore[invalid-method-override] -- PyQt6's QDialog stub rejects this runtime-supported QObject override.
        self, watched: QObject | None, event: QEvent | None
    ) -> bool:
        if (
            isinstance(watched, QWidget)
            and event is not None
            and event.type() == QEvent.Type.FocusIn
            and self.content_widget.isAncestorOf(watched)
        ):
            self.content_scroll.ensureWidgetVisible(watched)
        return super(DiagnosticMetricsDialog, self).eventFilter(watched, event)

    def _request_initial_content_refit(self):
        controller = self.__dict__.get("_layout_controller")
        if controller is not None and not self.isVisible():
            controller.request_content_refit()

    def ok(self):
        selected_metrics = self.get_selected_metrics()
        if not selected_metrics:
            QMessageBox.warning(
                self,
                "No Diagnostic Metric Selected",
                "Select at least one available diagnostic metric before running analysis.",
            )
            return

        # Use the parent's builder so dialog-construction failures reach the
        # shared error handler instead of disappearing in the Qt event loop.
        parent = self.parentWidget()
        builder = getattr(parent, "_build_analysis_specs_dialog", None)
        if builder is not None:
            form = builder(
                analysis_type=self.analysis_type,
                external_params=self.external_params,
                diagnostic_metrics=selected_metrics,
                confidence_level=self.model.get_confidence_level(),
            )
        else:
            form = analysis_setup_dialog.AnalysisSetupDialog(
                self.model,
                parent=parent,
                analysis_type=self.analysis_type,
                external_params=self.external_params,
                diagnostic_metrics=selected_metrics,
                confidence_level=self.model.get_confidence_level(),
            )
        if form is None:
            return
        form.show()
        self.hide()

    def get_selected_metrics(self):
        selected_metrics = []
        for metric in self.SELECTABLE_METRICS:
            checkbox = self._metric_checkbox(metric)
            if checkbox.isEnabled() and checkbox.isChecked():
                selected_metrics.append(metric)

        return selected_metrics

    def _configure_metric_checkboxes(self):
        raw_data_available = self.model.included_studies_have_raw_data()
        unavailable = []
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
                reason = (
                    "Requires complete TP/FN/FP/TN counts or complete entered "
                    "effect estimates and confidence intervals for this metric."
                )
                checkbox.setToolTip(reason)
                unavailable.append("{}: {}".format(checkbox.text(), reason))
        if unavailable:
            self.availability_label.setText(
                "Some metrics are unavailable:\n" + "\n".join(unavailable)
            )
        else:
            self.availability_label.setText(
                "All diagnostic metrics are available for the included studies."
            )
        self._refresh_ok_enabled()

    def _entered_estimates_available_for_metric(self, metric):
        return all(
            self.model.included_studies_have_point_estimates(effect=effect)
            for effect in DIAGNOSTIC_METRIC_GROUPS[metric]
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
