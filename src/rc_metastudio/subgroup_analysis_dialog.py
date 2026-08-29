from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QMessageBox

from rc_metastudio import adaptive_controls
from rc_metastudio import adaptive_window
from rc_metastudio import app_error_handler
from rc_metastudio.meta_globals import FACTOR

if TYPE_CHECKING:
    import ui_subgroup_analysis_dialog as _ui_subgroup_analysis_dialog
else:
    from rc_metastudio.forms import (
        ui_subgroup_analysis_dialog as _ui_subgroup_analysis_dialog,
    )


class SubgroupAnalysisDialog(
    QDialog, _ui_subgroup_analysis_dialog.Ui_SubgroupAnalysisDialog
):
    def __init__(self, model, parent=None):
        super(SubgroupAnalysisDialog, self).__init__(parent)
        self.model = model
        self.setupUi(self)
        self._populate_combo_box()
        adaptive_controls.configure_choice_control(self.cov_subgroup_cbo_box)
        self._update_ok_button()
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )
        self.buttonBox.rejected.connect(
            app_error_handler.safe_slot(self.cancel, parent=self)
        )
        self.buttonBox.accepted.connect(
            app_error_handler.safe_slot(self.get_selected_cov, parent=self)
        )

    def cancel(self):
        self.reject()

    def get_selected_cov(self):
        selected_cov = str(self.cov_subgroup_cbo_box.currentText())
        if not selected_cov:
            QMessageBox.warning(
                self,
                "No Covariate Selected",
                "Select a factor covariate before running subgroup analysis.",
            )
            return
        parent = self.parentWidget()
        callback = getattr(parent, "meta_subgroup", None)
        if not callable(callback):
            raise RuntimeError("subgroup configuration has no workflow owner")
        callback(selected_cov)
        self.accept()

    def _update_ok_button(self):
        ok_button = self.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setEnabled(self.cov_subgroup_cbo_box.count() > 0)

    def _populate_combo_box(self):
        studies = self.model.get_studies(only_if_included=True)

        for cov in self.model.dataset.covariates:
            if cov.get_data_type() != FACTOR:
                continue
            cov_vals = [study.covariate_dict[cov.name] for study in studies]
            if None not in cov_vals:
                self.cov_subgroup_cbo_box.addItem(cov.name)
