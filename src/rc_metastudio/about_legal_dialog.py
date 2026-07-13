# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Screen-bounded About/Legal Transactional Dialog."""

from PyQt5.QtWidgets import QDialog

import adaptive_window
import meta_globals
import forms.ui_about_legal


ABOUT_LEGAL_TEXT = """<h2>RC MetaStudio {version}</h2>
<p>Open-source desktop software for advanced meta-analysis, developed and
maintained by Research Consultancy (RC).</p>
<p><b>Maintainer:</b> Ali Salman and RC MetaStudio contributors<br>
<b>License:</b> GPL-3.0-or-later<br>
<b>Issues:</b> <a href="https://github.com/AliSalman-et-al/rc-metastudio/issues">
github.com/AliSalman-et-al/rc-metastudio/issues</a></p>
<p>RC MetaStudio is distributed without warranty, including without the implied
warranty of merchantability or fitness for a particular purpose.</p>
<p>RC MetaStudio is derived from the Original OpenMeta[Analyst] Project and is
independently maintained. See NOTICE.md for provenance and affiliation details.</p>
"""


class AboutLegalDialog(QDialog, forms.ui_about_legal.Ui_AboutLegalDialog):
    def __init__(self, parent=None):
        super(AboutLegalDialog, self).__init__(parent)
        self.setupUi(self)
        self.content_scroll_area.setHtml(
            ABOUT_LEGAL_TEXT.format(version=meta_globals.VERSION)
        )
        self._layout_controller = adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )
