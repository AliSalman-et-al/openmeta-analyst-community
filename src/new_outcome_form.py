from PyQt5.QtWidgets import QDialog
import forms.ui_new_outcome

class AddNewOutcomeForm(QDialog, forms.ui_new_outcome.Ui_Dialog):
    
    def __init__(self, parent=None):
        super(AddNewOutcomeForm, self).__init__(parent)
        self.setupUi(self)
        self._populate_combo_box()

        
    def _populate_combo_box(self):
        for name, item_id in zip(["Binary", "Continuous", "Diagnostic", "Other"],
                                     range(4)):
            self.datatype_cbo_box.addItem(name, item_id)
        
