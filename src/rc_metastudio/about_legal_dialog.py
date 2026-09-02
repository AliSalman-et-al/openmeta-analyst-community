# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Screen-bounded About/Legal Transactional Dialog."""

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox

from rc_metastudio import adaptive_window
from rc_metastudio import meta_globals

if TYPE_CHECKING:
    import ui_about_legal as _ui_about_legal
else:
    from rc_metastudio.forms import ui_about_legal as _ui_about_legal


ABOUT_LEGAL_TEXT = """<h2>RC MetaStudio {version}</h2>
<p>Open-source desktop software for advanced meta-analysis, developed and
maintained by Research Consultancy (RC).</p>
<p><b>Maintainer:</b> Ali Salman and RC MetaStudio contributors<br>
<b>License:</b> GPL-3.0-or-later<br>
<b>Issues:</b> <a href="https://github.com/AliSalman-et-al/rc-metastudio/issues">
github.com/AliSalman-et-al/rc-metastudio/issues</a></p>
<p>RC MetaStudio is distributed without warranty, including without the implied
warranty of merchantability or fitness for a particular purpose.</p>
<p>RC MetaStudio is derived from the original OpenMeta[Analyst] project and is
independently maintained. See NOTICE.md for provenance and affiliation details.</p>
"""


class AboutLegalDialog(QDialog, _ui_about_legal.Ui_AboutLegalDialog):
    def __init__(self, parent=None):
        super(AboutLegalDialog, self).__init__(parent)
        self.setupUi(self)
        self.content_scroll_area.setHtml(
            ABOUT_LEGAL_TEXT.format(version=meta_globals.VERSION)
        )
        self.content_scroll_area.setAccessibleName("About and legal information")
        self.content_scroll_area.setTabChangesFocus(True)
        close_button = self.buttonBox.button(QDialogButtonBox.StandardButton.Close)
        if close_button is None:
            raise RuntimeError("About dialog is missing its Close button")
        close_button.setObjectName("about_legal_close_button")
        close_button.setAccessibleName("Close About and Legal")
        close_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setTabOrder(self.content_scroll_area, close_button)
        self._layout_controller = adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )
