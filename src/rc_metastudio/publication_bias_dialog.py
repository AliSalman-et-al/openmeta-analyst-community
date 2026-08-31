# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
"""Method and plot settings for small-study effects analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox

from rc_metastudio import adaptive_window, app_error_handler, r_bridge
from rc_metastudio.meta_globals import ALL_METRIC_NAMES, ONE_ARM_METRICS
from rc_metastudio.publication_bias import (
    CorrectionPolicy,
    FunnelKind,
    FunnelStyle,
    LabelPolicy,
    SmallStudyEffectsRequest,
    TrimAndFillEstimator,
    TrimAndFillModel,
    TrimAndFillSide,
    execute_small_study_effects,
    parse_eligibility_report,
)

if TYPE_CHECKING:
    import ui_publication_bias_dialog as _ui_publication_bias_dialog
else:
    from rc_metastudio.forms import (
        ui_publication_bias_dialog as _ui_publication_bias_dialog,
    )


_TEST_LABELS = {
    "classical-egger": "Classical Egger",
    "mixed-effects-egger": "Mixed-effects Egger",
    "begg-mazumdar": "Begg-Mazumdar",
    "harbord": "Harbord",
    "peters": "Peters",
    "pustejovsky-rodgers": "Pustejovsky-Rodgers",
    "rucker-as-re": "Rücker AS+RE",
    "deeks": "Deeks",
}


class PublicationBiasDialog(QDialog, _ui_publication_bias_dialog.Ui_PublicationBiasDialog):
    """Configure methods and plots while RCMetaR chooses eligible tests."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.setupUi(self)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setModal(True)
        self.correction_policy_combo.addItems([policy.value for policy in CorrectionPolicy])
        self.trim_fill_estimator_combo.addItems([item.value for item in TrimAndFillEstimator])
        self.trim_fill_side_combo.addItems([item.value for item in TrimAndFillSide])
        self.trim_fill_model_combo.addItems([item.value for item in TrimAndFillModel])
        confidence_level = getattr(self.model, "get_confidence_level", lambda: 95.0)()
        confidence_text = str(int(round(float(confidence_level))))
        self.sampling_confidence_combo.setCurrentText(
            confidence_text
            if self.sampling_confidence_combo.findText(confidence_text) >= 0
            else "95"
        )
        self._eligibility_report = None
        if str(self.model.get_current_outcome_type()) == "diagnostic":
            self.correction_policy_combo.setCurrentText(
                CorrectionPolicy.ALL_STUDIES_IF_ANY_ZERO_EXISTS.value
            )
        self._populate_context()
        self._update_controls()
        self.failure_label.clear()
        for control in (
            self.ordinary_funnel_check,
            self.contour_funnel_check,
            self.deeks_funnel_check,
            self.trim_fill_check,
        ):
            control.toggled.connect(self._update_controls)
        self.correction_policy_combo.currentTextChanged.connect(
            self._refresh_eligibility
        )
        self.button_box.rejected.connect(self.reject)
        self.button_box.accepted.connect(
            app_error_handler.safe_slot(self.run, parent=self)
        )
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )

    def _preview_request(self) -> SmallStudyEffectsRequest:
        data_type = str(self.model.get_current_outcome_type())
        metric = "DOR" if data_type == "diagnostic" else str(self.model.current_effect)
        correction_applicable = data_type in {"binary", "diagnostic"} and metric not in ONE_ARM_METRICS
        return SmallStudyEffectsRequest.create(
            data_type=data_type,
            metric=metric,
            correction_policy=(
                self.correction_policy_combo.currentText()
                if correction_applicable and self.correction_policy_combo.isEnabled()
                else None
            ),
            selected_tests=(),
        )

    def _populate_context(self):
        request = self._preview_request()
        try:
            report = parse_eligibility_report(
                r_bridge.run_small_study_effects(
                    self.model, request.to_mapping(), preview=True
                )
            )
        except Exception:  # noqa: BLE001 - Qt boundary remains recoverable
            self._eligibility_report = None
            self.context_label.setText(self._context_summary())
            self.automatic_test_label.setText(
                "Test availability will be checked when the analysis runs."
            )
            return
        self._eligibility_report = report
        self.context_label.setText(self._context_summary(report))
        available = [item for item in report.methods if item.available]
        if available:
            primary = [
                _TEST_LABELS.get(item.method, item.method)
                for item in available
                if item.role == "primary"
            ]
            additional = [
                _TEST_LABELS.get(item.method, item.method)
                for item in available
                if item.role != "primary"
            ]
            lines = []
            if primary:
                lines.append("Primary: " + ", ".join(primary))
            if additional:
                lines.append("Additional: " + ", ".join(additional))
            self.automatic_test_label.setText("\n".join(lines))
        else:
            self.automatic_test_label.setText(
                "No formal asymmetry test is available for this effect measure."
            )

    def _context_summary(self, report=None) -> str:
        data_type = str(self.model.get_current_outcome_type())
        metric = "DOR" if data_type == "diagnostic" else str(self.model.current_effect)
        dataset = getattr(self.model, "dataset", None)
        studies = getattr(dataset, "studies", None)
        included = (
            sum(bool(getattr(study, "include", True)) for study in studies)
            if studies is not None
            else "?"
        )
        report = report or self._eligibility_report
        eligible = report.usable_studies if report is not None else "?"
        outcome_label = data_type.capitalize()
        metric_label = ALL_METRIC_NAMES.get(metric, metric)
        return (
            f"{outcome_label}  ·  {metric_label} ({metric})  ·  "
            f"{included} included  ·  {eligible} eligible"
        )

    def _refresh_eligibility(self):
        self._populate_context()
        self._update_controls()

    def _update_controls(self):
        data_type = str(self.model.get_current_outcome_type())
        metric = "DOR" if data_type == "diagnostic" else str(self.model.current_effect)
        deeks = data_type == "diagnostic"
        contour = self.contour_funnel_check.isChecked()
        if deeks:
            self.ordinary_funnel_check.setChecked(False)
            self.contour_funnel_check.setChecked(False)
            self.deeks_funnel_check.setChecked(True)
        self.ordinary_funnel_check.setEnabled(not deeks)
        self.contour_funnel_check.setEnabled(not deeks)
        self.deeks_funnel_check.setEnabled(deeks)
        outside_label = "Outside pseudo-confidence region"
        outside_index = self.label_policy_combo.findText(outside_label)
        if deeks and outside_index >= 0:
            self.label_policy_combo.removeItem(outside_index)
        elif not deeks and outside_index < 0:
            self.label_policy_combo.insertItem(1, outside_label)
        if self.label_policy_combo.currentText() not in {"None", outside_label, "All"}:
            self.label_policy_combo.setCurrentText("None")
        self.label_policy_combo.setEnabled(True)
        self.sampling_confidence_combo.setEnabled(not deeks)
        self.include_tau2_check.setEnabled(not deeks)
        self.contour_levels_edit.setEnabled(contour and not deeks)
        self.contour_levels_label.setEnabled(contour and not deeks)
        trim_fill_enabled = self.trim_fill_check.isChecked() and not deeks
        self.trim_fill_group.setEnabled(trim_fill_enabled)
        self.trim_fill_group.setVisible(trim_fill_enabled)
        if deeks:
            self.trim_fill_check.setChecked(False)
            self.extrapolation_check.setChecked(False)
        self.sensitivity_group.setVisible(not deeks)
        self.extrapolation_check.setEnabled(not deeks)

        raw_data_available = bool(
            self._eligibility_report and self._eligibility_report.raw_data_available
        )
        correction_applicable = str(self.model.get_current_outcome_type()) in {
            "binary",
            "diagnostic",
        } and metric not in ONE_ARM_METRICS
        correction_enabled = correction_applicable and raw_data_available
        self.correction_policy_combo.setEnabled(correction_enabled)
        self.correction_group.setVisible(correction_enabled)
        self.correction_reason_label.clear()

    def _request(self) -> SmallStudyEffectsRequest:
        funnels = [
            kind.value
            for kind, control in (
                (FunnelKind.ORDINARY, self.ordinary_funnel_check),
                (FunnelKind.CONTOUR, self.contour_funnel_check),
                (FunnelKind.DEEKS, self.deeks_funnel_check),
            )
            if control.isChecked()
        ]
        data_type = str(self.model.get_current_outcome_type())
        metric = "DOR" if data_type == "diagnostic" else str(self.model.current_effect)
        selected_tests = [
            item.method
            for item in (self._eligibility_report.methods if self._eligibility_report else ())
            if item.available
        ]
        labels = {
            "None": LabelPolicy.NONE,
            "Outside pseudo-confidence region": LabelPolicy.OUTSIDE_REGION,
            "All": LabelPolicy.ALL,
        }
        levels = tuple(
            float(value.strip())
            for value in self.contour_levels_edit.text().split(",")
            if value.strip()
        )
        return SmallStudyEffectsRequest.create(
            data_type=data_type,
            metric=metric,
            correction_policy=(
                self.correction_policy_combo.currentText()
                if self.correction_policy_combo.isEnabled()
                else None
            ),
            selected_tests=selected_tests,
            selected_funnels=funnels,
            label_policy=labels[self.label_policy_combo.currentText()],
            sampling_confidence_level=float(self.sampling_confidence_combo.currentText()),
            include_tau2=self.include_tau2_check.isChecked(),
            point_size=float(self.point_size_spin.value()),
            reference_line_visible=self.reference_line_check.isChecked(),
            contour_levels=levels,
            pooled_overlay_visible=self.pooled_overlay_check.isChecked(),
            style={
                "Default (metafor)": FunnelStyle.DEFAULT,
                "RevMan": FunnelStyle.REVMAN,
                "BMJ": FunnelStyle.BMJ,
            }[self.style_combo.currentText()],
            trim_and_fill=self.trim_fill_check.isChecked(),
            trim_and_fill_estimator=self.trim_fill_estimator_combo.currentText(),
            trim_and_fill_side=self.trim_fill_side_combo.currentText(),
            trim_and_fill_model=self.trim_fill_model_combo.currentText(),
            extrapolation=self.extrapolation_check.isChecked(),
        )

    def run(self):
        run_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if run_button is not None:
            run_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.failure_label.clear()
        self.failure_label.setVisible(False)
        try:
            result = execute_small_study_effects(self.model, self._request())
            owner = self.parentWidget()
            callback = getattr(owner, "analysis", None)
            if not callable(callback):
                raise TypeError("small-study effects dialog has no results owner")
            callback(result)
            self.progress_bar.setVisible(False)
            self.accept()
        except Exception as error:  # noqa: BLE001 - Qt boundary remains recoverable
            self.failure_label.setText(str(error))
            self.failure_label.setVisible(True)
            app_error_handler.handle_exception(type(error), error, error.__traceback__, parent=self)
            if run_button is not None:
                run_button.setEnabled(True)
