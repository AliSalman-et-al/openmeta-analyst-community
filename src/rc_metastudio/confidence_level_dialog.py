# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Confidence-level editing dialog."""

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QDialog

from rc_metastudio.meta_globals import (
    DEFAULT_CONFIDENCE_LEVEL,
    CONFIDENCE_LEVEL_DISPLAY_MAX,
)
from rc_metastudio import adaptive_window

if TYPE_CHECKING:
    import ui_confidence_level_dialog as _ui_confidence_level_dialog
else:
    from rc_metastudio.forms import (
        ui_confidence_level_dialog as _ui_confidence_level_dialog,
    )


class ConfidenceLevelDialog(
    QDialog, _ui_confidence_level_dialog.Ui_change_confidence_level_dialog
):
    """Dialog for changing confidence level"""

    def __init__(self, previous_value=DEFAULT_CONFIDENCE_LEVEL, parent=None):
        super(ConfidenceLevelDialog, self).__init__(parent)
        self.setupUi(self)
        self.confidence_level_spinbox.setRange(50, CONFIDENCE_LEVEL_DISPLAY_MAX)
        self.confidence_level_spinbox.setValue(previous_value)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self._layout_controller = adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.CONFIDENCE_LEVEL
        )

    def request_layout_refit(self):
        """Coalesce a content-driven refit owned by this dialog."""
        self._layout_controller.request_content_refit()

    def get_value(self):
        return self.confidence_level_spinbox.value()
