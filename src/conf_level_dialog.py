"""
Created on Apr 29, 2013

@author: George Dietz
"""

from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from meta_globals import DEFAULT_CONF_LEVEL, CONFIDENCE_LEVEL_DISPLAY_MAX
import qt_layout


class ChangeConfLevelDlg(QDialog):
    """Dialog for changing confidence level"""

    def __init__(self, previous_value=DEFAULT_CONF_LEVEL, parent=None):
        super(ChangeConfLevelDlg, self).__init__(parent)

        cl_label = QLabel("Global Confidence Level:")

        self.conf_level_spinbox = QDoubleSpinBox()
        self.conf_level_spinbox.setDecimals(1)
        self.conf_level_spinbox.setRange(50, CONFIDENCE_LEVEL_DISPLAY_MAX)
        self.conf_level_spinbox.setSingleStep(0.1)
        self.conf_level_spinbox.setSuffix("%")
        self.conf_level_spinbox.setValue(previous_value)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        hlayout = QHBoxLayout()
        hlayout.addWidget(cl_label)
        hlayout.addWidget(self.conf_level_spinbox)
        vlayout = QVBoxLayout()
        vlayout.addLayout(hlayout)
        vlayout.addWidget(buttonBox)
        self.setLayout(vlayout)
        self.setMinimumWidth(qt_layout.ANALYSIS_DIALOG_MINIMUM_WIDTH)

        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        self.setWindowTitle("Change Confidence Level")
        qt_layout.fit_analysis_dialog_to_contents(self)

    def get_value(self):
        return self.conf_level_spinbox.value()
