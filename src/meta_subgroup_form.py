from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QMessageBox

import forms.ui_cov_subgroup_dlg
from meta_globals import FACTOR


class MetaSubgroupForm(QDialog, forms.ui_cov_subgroup_dlg.Ui_cov_subgroup_dialog):
    def __init__(self, model, parent=None):
        super(MetaSubgroupForm, self).__init__(parent)
        self.model = model
        self.setupUi(self)
        self._populate_combo_box()
        self._update_ok_button()
        self.buttonBox.rejected.connect(self.cancel)
        self.buttonBox.accepted.connect(self.get_selected_cov)

    def cancel(self):
        print("(cancel)")
        self.reject()

    def get_selected_cov(self):
        selected_cov = str(self.cov_subgroup_cbo_box.currentText())
        if not selected_cov:
            QMessageBox.warning(
                self,
                "No covariate selected",
                "Select a factor covariate before running subgroup analysis.",
            )
            return
        self.parent().meta_subgroup(selected_cov)
        self.accept()

    def _update_ok_button(self):
        ok_button = self.buttonBox.button(QDialogButtonBox.Ok)
        if ok_button is not None:
            ok_button.setEnabled(self.cov_subgroup_cbo_box.count() > 0)

    def _populate_combo_box(self):
        studies = self.model.get_studies(only_if_included=True)

        for cov in self.model.dataset.covariates:
            if cov.get_data_type() != FACTOR:
                continue
            cov_vals = [study.covariate_dict[cov.name] for study in studies]
            if not None in cov_vals:
                self.cov_subgroup_cbo_box.addItem(cov.name)
