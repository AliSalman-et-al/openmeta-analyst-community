from PyQt5.QtWidgets import QDialog
import forms.ui_tom_form
import qt_layout


class TomDialog(QDialog, forms.ui_tom_form.Ui_Dialog):
    def __init__(self, parent=None):
        super(TomDialog, self).__init__(parent)
        self.setupUi(self)
        qt_layout.fit_text_to_contents(self)


# class PersonDialog(QDialog, forms.ui_tom_form.Ui_Dialog):
#    def __init__(self, parent=None, person="tom"):
#        super(PersonDialog, self).__init__(parent)
#        self.setupUi(self)
#
#        personPixmap =
#
#        self.label.setPixmap
