from PyQt6.QtWidgets import QDialog
import forms.ui_edit_group_name
import adaptive_window


class EditGroupName(QDialog, forms.ui_edit_group_name.Ui_group_name_dialog):
    def __init__(self, cur_group_name, parent=None):
        super(EditGroupName, self).__init__(parent)
        self.setupUi(self)
        self.group_name_le.setText(cur_group_name)
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )


class EditCovariateName(QDialog, forms.ui_edit_group_name.Ui_group_name_dialog):
    def __init__(self, cur_cov_name, parent=None):
        super(EditCovariateName, self).__init__(parent)
        self.setupUi(self)
        self.group_name_le.setText(cur_cov_name)
        self.field_lbl.setText("Covariate name:")
        self.setWindowTitle("Edit Covariate Name")
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )
