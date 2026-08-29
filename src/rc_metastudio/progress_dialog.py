from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QDialog

from rc_metastudio import adaptive_window

if TYPE_CHECKING:
    import ui_progress_dialog as _ui_progress_dialog
else:
    from rc_metastudio.forms import ui_progress_dialog as _ui_progress_dialog


class AnalysisProgressDialog(QDialog, _ui_progress_dialog.Ui_ProgressDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self._layout_controller = adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSIENT
        )


def hide_once(progress_dialog):
    if getattr(progress_dialog, "_rcms_hidden", False):
        return
    progress_dialog.hide()
    progress_dialog._rcms_hidden = True
