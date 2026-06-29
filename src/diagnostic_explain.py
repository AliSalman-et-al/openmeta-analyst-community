from PyQt5 import QtCore
from PyQt5.QtWidgets import QDialog
import forms.ui_diagnostic_explain_dlg

from settings import update_setting

class DiagnosticExplain(QDialog, forms.ui_diagnostic_explain_dlg.Ui_diag_explain_window):
    
    def __init__(self, parent=None):
        super(DiagnosticExplain, self).__init__(parent)
        self.setupUi(self)

        self.dont_show_again_chk_box.stateChanged.connect(self.update_explain_diag_setting)

    def update_explain_diag_setting(self, state):
        field = "explain_diag"
        
        if state == QtCore.Qt.Checked:
            update_setting(field, True)
        elif state == QtCore.Qt.Unchecked:
            update_setting(field, False)
