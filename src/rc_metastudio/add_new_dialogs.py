from PyQt6.QtWidgets import QDialog

# from meta_globals import *
from meta_globals import DIAGNOSTIC
import forms.ui_new_group
import forms.ui_new_follow_up
import forms.ui_new_outcome
import forms.ui_new_covariate
import forms.ui_new_study
import adaptive_controls
import adaptive_window

# import pdb


class AddNewGroupForm(QDialog, forms.ui_new_group.Ui_new_group_dialog):
    def __init__(self, parent=None):
        super(AddNewGroupForm, self).__init__(parent)
        self.setupUi(self)
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )


class AddNewFollowUpForm(QDialog, forms.ui_new_follow_up.Ui_new_follow_up_dialog):
    def __init__(self, parent=None):
        super(AddNewFollowUpForm, self).__init__(parent)
        self.setupUi(self)
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )


class AddNewOutcomeForm(QDialog, forms.ui_new_outcome.Ui_Dialog):
    def __init__(self, parent=None, is_diag=False):
        super(AddNewOutcomeForm, self).__init__(parent)
        ###
        # we need to know if the outcome should be diagnostic
        # or not.
        self.is_diag = is_diag

        self.setupUi(self)
        self._populate_combo_box()
        adaptive_controls.configure_choice_control(self.datatype_cbo_box)
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )

    def _populate_combo_box(self):
        # diagnostic datasets can have only diagnostic outcomes
        if self.is_diag:
            self.datatype_cbo_box.addItem("Diagnostic", DIAGNOSTIC)
        else:
            for name, type_id in zip(["Binary", "Continuous"], range(2)):
                self.datatype_cbo_box.addItem(name, type_id)


class AddNewStudyForm(QDialog, forms.ui_new_study.Ui_new_study_dialog):
    def __init__(self, parent=None):
        super(AddNewStudyForm, self).__init__(parent)
        self.setupUi(self)
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )


class AddNewCovariateForm(QDialog, forms.ui_new_covariate.Ui_new_covariate_dialog):
    def __init__(self, parent=None):
        super(AddNewCovariateForm, self).__init__(parent)
        self.setupUi(self)
        self._populate_combo_box()
        adaptive_controls.configure_choice_control(self.datatype_cbo_box)
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )

    def _populate_combo_box(self):
        for name, type_id in zip(["continuous", "factor"], range(2)):
            self.datatype_cbo_box.addItem(name, type_id)
