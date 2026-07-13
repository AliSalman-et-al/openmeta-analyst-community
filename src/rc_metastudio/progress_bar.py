from PyQt5.QtWidgets import QDialog

# import pdb
import forms.ui_running
import adaptive_window


class MetaProgress(QDialog, forms.ui_running.Ui_running):
    def __init__(self, parent=None):
        super(MetaProgress, self).__init__(parent)
        self.setupUi(self)
        self._layout_controller = adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSIENT
        )


def hide_once(progress_dialog):
    if getattr(progress_dialog, "_oma_hidden", False):
        return
    progress_dialog.hide()
    progress_dialog._oma_hidden = True
