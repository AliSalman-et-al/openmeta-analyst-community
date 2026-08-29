from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QDialog
from rc_metastudio import adaptive_window

if TYPE_CHECKING:
    import ui_edit_name_dialog as _ui_edit_name_dialog
else:
    from rc_metastudio.forms import ui_edit_name_dialog as _ui_edit_name_dialog


class EditGroupNameDialog(QDialog, _ui_edit_name_dialog.Ui_EditNameDialog):
    def __init__(self, cur_group_name, parent=None):
        super(EditGroupNameDialog, self).__init__(parent)
        self.setupUi(self)
        self.group_name_le.setText(cur_group_name)
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )


class EditCovariateNameDialog(QDialog, _ui_edit_name_dialog.Ui_EditNameDialog):
    def __init__(self, cur_cov_name, parent=None):
        super(EditCovariateNameDialog, self).__init__(parent)
        self.setupUi(self)
        self.group_name_le.setText(cur_cov_name)
        self.field_lbl.setText("Covariate name:")
        self.setWindowTitle("Edit Covariate Name")
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )
