# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QMessageBox,
)

from rc_metastudio import adaptive_window
from rc_metastudio import app_error_handler
from rc_metastudio import analysis_adapter

if TYPE_CHECKING:
    import ui_meta_regression_dialog as _ui_meta_regression_dialog
else:
    from rc_metastudio.forms import (
        ui_meta_regression_dialog as _ui_meta_regression_dialog,
    )


class MetaRegressionDialog(QDialog, _ui_meta_regression_dialog.Ui_MetaRegressionDialog):
    def __init__(self, model, parent=None):
        super(MetaRegressionDialog, self).__init__(parent)
        self.model = model
        self.setupUi(self)
        self.covs_and_check_boxes = []
        self._populate_chk_boxes()
        self._update_ok_button()

        # as usual, diagnostic data is special
        self.is_diagnostic = self.model.get_current_outcome_type() == "diagnostic"

        if not self.is_diagnostic:
            self.diagnostic_group_box.hide()

        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )

        self.buttonBox.rejected.connect(
            app_error_handler.safe_slot(self.cancel, parent=self)
        )
        self.buttonBox.accepted.connect(
            app_error_handler.safe_slot(self.run_meta_reg, parent=self)
        )

    def cancel(self):
        self.reject()

    def run_meta_reg(self):
        selected_covariates = self._selected_covariates()
        if not selected_covariates:
            QMessageBox.warning(
                self,
                "No Covariates Selected",
                "Select at least one covariate before running meta-regression.",
            )
            return

        current_effect = self.model.current_effect
        if self.is_diagnostic:
            if self.dor_radio.isChecked():
                current_effect = "DOR"
            elif self.sensitivity_radio.isChecked():
                current_effect = "Sens"
            else:
                current_effect = "Spec"

        selection = analysis_adapter.select_studies_for_covariates(
            self.model, selected_covariates
        )

        # fixed or random effects meta-regression?
        fixed_effects = False
        if self.fixed_effects_radio.isChecked():
            fixed_effects = True

        if selection.has_missing_values:
            # Missing covariate values are rejected here until the analysis
            # workflow can exclude affected studies consistently.
            run_with_missing = QMessageBox.warning(
                self,
                "Missing Covariate Values",
                "Some studies have no value for a selected covariate. "
                "Run the regression without those studies?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if run_with_missing == QMessageBox.StandardButton.No:
                self.accept()
                return

        request = analysis_adapter.make_analysis_request(
            data_type=self.model.get_current_outcome_type(),
            workflow="meta-regression",
            method="meta_regression",
            metric=current_effect,
            parameters={"measure": current_effect},
        )
        try:
            result = analysis_adapter.execute_meta_regression_request(
                self.model,
                selection.studies,
                tuple(selected_covariates),
                request,
                fixed_effects,
                self.model.get_confidence_level(),
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                "Analysis Failed",
                "Sorry, there was an error performing the regression.\n%s" % error,
            )
            return

        parent = self.parentWidget()
        callback = getattr(parent, "analysis", None)
        if not callable(callback):
            raise RuntimeError("meta-regression configuration has no results owner")
        callback(result)
        self.accept()

    def _selected_covariates(self):
        return [
            cov for cov, chk_box in self.covs_and_check_boxes if chk_box.isChecked()
        ]

    def _update_ok_button(self):
        ok_button = self.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setEnabled(bool(self._selected_covariates()))

    def _populate_chk_boxes(self):
        self.covs_and_check_boxes = []
        chk_box_layout = QGridLayout()
        for cov in self.model.dataset.covariates:
            chk_box = QCheckBox(cov.name)
            if len(self.covs_and_check_boxes) == 0:
                # check the first covariate by default
                chk_box.setChecked(True)
            chk_box.toggled.connect(
                app_error_handler.safe_slot(self._update_ok_button, parent=self)
            )
            chk_box_layout.addWidget(chk_box)
            self.covs_and_check_boxes.append((cov, chk_box))

            self.covariate_group_box.setLayout(chk_box_layout)
