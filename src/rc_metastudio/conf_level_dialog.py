# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Confidence-level editing dialog."""

from PyQt6.QtWidgets import QDialog

from meta_globals import DEFAULT_CONF_LEVEL, CONFIDENCE_LEVEL_DISPLAY_MAX
import adaptive_window
import forms.ui_conf_level_dialog  # ty: ignore[unresolved-import]


class ChangeConfLevelDlg(
    QDialog, forms.ui_conf_level_dialog.Ui_change_conf_level_dialog
):
    """Dialog for changing confidence level"""

    def __init__(self, previous_value=DEFAULT_CONF_LEVEL, parent=None):
        super(ChangeConfLevelDlg, self).__init__(parent)
        self.setupUi(self)
        self.conf_level_spinbox.setRange(50, CONFIDENCE_LEVEL_DISPLAY_MAX)
        self.conf_level_spinbox.setValue(previous_value)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self._layout_controller = adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.CONFIDENCE_LEVEL
        )

    def request_layout_refit(self):
        """Coalesce a content-driven refit owned by this dialog."""
        self._layout_controller.request_content_refit()

    def get_value(self):
        return self.conf_level_spinbox.value()
