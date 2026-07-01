"""""" """""" """""" """""" """"""

" admittedly, kind of silly. "
"""""" """""" """""" """""" """"""

from PyQt5.QtWidgets import QDialog

# import pdb
import forms.ui_running
import qt_layout


class MetaProgress(QDialog, forms.ui_running.Ui_running):
    def __init__(self, parent=None):
        super(MetaProgress, self).__init__(parent)
        self.setupUi(self)
        qt_layout.fit_text_to_contents(self)
