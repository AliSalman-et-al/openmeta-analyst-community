# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QMessageBox,
)

import forms.ui_meta_reg
import adaptive_window
import app_error_handler
import meta_py_r


class MetaRegForm(QDialog, forms.ui_meta_reg.Ui_cov_reg_dialog):
    def __init__(self, model, parent=None):
        super(MetaRegForm, self).__init__(parent)
        self.model = model
        self.setupUi(self)
        self.covs_and_check_boxes = None
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
        print("(cancel)")
        self.reject()

    def run_meta_reg(self):
        at_least_one_study_does_not_have_vals = False
        cov_d = {}
        selected_covariates = self._selected_covariates()
        if not selected_covariates:
            QMessageBox.warning(
                self,
                "No Covariates Selected",
                "Select at least one covariate before running meta-regression.",
            )
            return

        for cov, chk_box in self.covs_and_check_boxes:
            # here we have to exclude studies that do not have values
            # for all of the selected covariates
            cov_d[cov.name] = self.model.dataset.get_values_for_cov(
                cov.name, ids_for_keys=True
            )

        current_effect = self.model.current_effect
        if self.is_diagnostic:
            if self.dor_radio.isChecked():
                current_effect = "DOR"
            elif self.sensitivity_radio.isChecked():
                current_effect = "Sens"
            else:
                current_effect = "Spec"

        studies = []
        for study in [study for study in self.model.get_studies(only_if_included=True)]:
            has_covs = [
                study.id in cov_d[selected_cov.name]
                for selected_cov in selected_covariates
            ]
            # if study != '' and study.id in cov_d and cov_d[study.id] is not None:
            #    studies.append(study)
            if all(has_covs):
                studies.append(study)
            else:
                at_least_one_study_does_not_have_vals = True

        if self.is_diagnostic:
            meta_py_r.ma_dataset_to_simple_diagnostic_robj(
                self.model,
                metric=current_effect,
                covs_to_include=selected_covariates,
                studies=studies,
            )
        elif self.model.get_current_outcome_type() == "continuous":
            meta_py_r.ma_dataset_to_simple_continuous_robj(
                self.model, covs_to_include=selected_covariates, studies=studies
            )
        else:
            meta_py_r.ma_dataset_to_simple_binary_robj(
                self.model,
                include_raw_data=False,
                covs_to_include=selected_covariates,
                studies=studies,
            )

        # fixed or random effects meta-regression?
        fixed_effects = False
        if self.fixed_effects_radio.isChecked():
            fixed_effects = True

        if at_least_one_study_does_not_have_vals:
            # Missing covariate values are rejected here until the analysis
            # workflow can exclude affected studies consistently.
            run_with_missing = QMessageBox.warning(
                self,
                "Missing Covariate Values",
                "Some studies do not have values for the covariate(s) you have selected. Do you want me to run the regression without them (i.e., drop studies with missing values)?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if run_with_missing == QMessageBox.StandardButton.No:
                self.accept()
                return

        result = meta_py_r.run_meta_regression(
            self.model.dataset,
            studies,
            selected_covariates,
            current_effect,
            fixed_effects=fixed_effects,
            conf_level=self.model.get_global_conf_level(),
        )
        if isinstance(result, str):
            # then there was an error!
            QMessageBox.critical(
                self,
                "Analysis Failed",
                "Sorry, there was an error performing the regression.\n%s" % result,
            )
        else:
            self.parent().analysis(result)
            self.accept()

    def _selected_covariates(self):
        return [
            cov for cov, chk_box in self.covs_and_check_boxes if chk_box.isChecked()
        ]

    def _update_ok_button(self):
        ok_button = self.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setEnabled(bool(self._selected_covariates()))

    def _populate_combo_box(self):
        studies = self.model.get_studies(only_if_included=True)

        for cov in self.model.dataset.covariates:
            cov_vals = [study.covariate_dict[cov.name] for study in studies]
            if not None in cov_vals:
                self.cov_cbo_box.addItem(cov.name)

    def _populate_chk_boxes(self):
        self.covs_and_check_boxes = []
        studies = self.model.get_studies(only_if_included=True)

        chk_box_layout = QGridLayout()
        for cov in self.model.dataset.covariates:
            cov_vals = [study.covariate_dict[cov.name] for study in studies]
            # note that we're *allowing* empty strings
            chk_box = QCheckBox(cov.name)
            if len(self.covs_and_check_boxes) == 0:
                # check the first covariate by default
                # (this is arbitrary)
                chk_box.setChecked(True)
            chk_box.toggled.connect(
                app_error_handler.safe_slot(self._update_ok_button, parent=self)
            )
            chk_box_layout.addWidget(chk_box)
            self.covs_and_check_boxes.append((cov, chk_box))

            self.cov_grp_box.setLayout(chk_box_layout)
