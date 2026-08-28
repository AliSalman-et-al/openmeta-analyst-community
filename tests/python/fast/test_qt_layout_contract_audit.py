# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_qt_layout_contracts


def test_repository_satisfies_canonical_qt_layout_contract():
    assert audit_qt_layout_contracts.audit_repository(ROOT) == []


def test_audit_rejects_unmanaged_content_geometry_and_legacy_helpers(tmp_path):
    forms = tmp_path / "src" / "rc_metastudio" / "forms"
    forms.mkdir(parents=True)
    (forms / "bad.ui").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0"><class>Bad</class>
<widget class="QDialog" name="Bad">
 <property name="geometry"><rect><x>0</x><y>0</y><width>640</width><height>480</height></rect></property>
 <widget class="QLabel" name="label">
  <property name="geometry"><rect><x>10</x><y>10</y><width>200</width><height>20</height></rect></property>
  <property name="minimumSize"><size><width>500</width><height>40</height></size></property>
  <property name="maximumSize"><size><width>300</width><height>20</height></size></property>
  <property name="font"><font><family>Consolas</family><pixelsize>13</pixelsize></font></property>
  <property name="styleSheet"><string>font-family: Consolas; font-size: 13px;</string></property>
 </widget>
</widget><resources/><connections/></ui>
""",
        encoding="utf-8",
    )
    source = tmp_path / "src" / "rc_metastudio" / "bad.py"
    source.write_text(
        """from PyQt6.QtGui import QFont

class Bad:
    def __init__(self):
        adaptive_window.WindowRole.TRANSACTIONAL
        other.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.MAIN
        )
        widget.setMinimumWidth(computed_width)
        widget.setMaximumHeight(computed_height)
        widget.setFixedSize(computed_size)
        widget.setGeometry(computed_rect)
        widget.move(computed_point)
        widget.adjustSize()
fit_application_dialog_to_contents(window)
font = QFont(
    "Verdana",
    12,
)
keyword_font = QFont(family="Arial", pointSize=11)
font.setFamily(
    "Helvetica"
)
font.setPointSize(computed_size)
font.setPointSizeF(12.5)
font.setPixelSize(pixel_size)
widget.setStyleSheet("QLabel { font-family: Verdana; }")
widget.setStyleSheet(
    "QLabel { font-"
    + "size: 12px; }"
)
STYLE = "QLabel { font: 12px Verdana; }"
widget.setStyleSheet(STYLE)
if use_override:
    CONDITIONAL_STYLE = "QLabel { font-family: Consolas; }"
else:
    CONDITIONAL_STYLE = "QLabel { color: palette(text); }"
widget.setStyleSheet(CONDITIONAL_STYLE)
TERNARY_STYLE = "QLabel { font-size: 11px; }" if compact else ""
widget.setStyleSheet(TERNARY_STYLE)
LOOP_STYLE = "QLabel { color: palette(text); }"
for item in possibly_empty:
    LOOP_STYLE = "QLabel { font-family: Consolas; }"
widget.setStyleSheet(LOOP_STYLE)
EXCEPTION_STYLE = "QLabel { color: palette(text); }"
try:
    may_raise()
    EXCEPTION_STYLE = "QLabel { font-size: 10px; }"
except RuntimeError:
    recover()
widget.setStyleSheet(EXCEPTION_STYLE)
""",
        encoding="utf-8",
    )
    nested = tmp_path / "src" / "rc_metastudio" / "nested" / "bad_geometry.py"
    nested.parent.mkdir()
    nested.write_text(
        "# layout-audit: allow=anything; reason=not a recognized exception\n"
        "widget.resize(width, height)\n",
        encoding="utf-8",
    )
    aliased = nested.parent / "aliased_font.py"
    aliased.write_text(
        """def qt_font():
    from PyQt6.QtGui import QFont as Font
    if use_domain_font:
        Font = domain_font_factory
    return Font('Consolas', 12)

def domain_font(Font):
    return Font('Consolas', 12)

def locally_shadowed():
    Font = domain_font_factory
    return Font('Consolas', 12)

def qtgui_alias():
    import PyQt6.QtGui as Gui
    return Gui.QFont('Consolas', 12)

def from_pyqt_alias():
    from PyQt6 import QtGui as Gui
    return Gui.QFont('Consolas', 12)

def pyqt_alias():
    import PyQt6 as Qt
    return Qt.QtGui.QFont('Consolas', 12)
""",
        encoding="utf-8",
    )
    domain_fonts = nested.parent / "domain_fonts.py"
    domain_fonts.write_text(
        """from domain_models import QFont
import domain_models as domain
local = QFont('Consolas', 12)
qualified = domain.QFont('Consolas', 12)
""",
        encoding="utf-8",
    )
    findings = audit_qt_layout_contracts.audit_repository(tmp_path)

    rules = {finding.rule for finding in findings}
    assert "managed-content-root" in rules
    assert "historical-root-geometry" in rules
    assert "unmanaged-content-geometry" in rules
    assert "contradictory-constraint" in rules
    assert "unjustified-hard-dimension" in rules
    assert "unjustified-geometry-call" in rules
    assert "legacy-sizing-helper" in rules
    assert "platform-font" in rules
    assert any(finding.path == nested for finding in findings)
    assert any(
        finding.path == aliased and "Font hard-codes" in finding.detail
        for finding in findings
    )
    assert sum(finding.path == aliased for finding in findings) == 8
    assert not any(finding.path == domain_fonts for finding in findings)
    font_details = [
        finding.detail for finding in findings if finding.rule == "platform-font"
    ]
    assert any("QFont hard-codes a family" in detail for detail in font_details)
    assert any("QFont hard-codes an absolute size" in detail for detail in font_details)
    assert any("setFamily hard-codes a family" in detail for detail in font_details)
    assert any("setPointSize " in detail for detail in font_details)
    assert any("setPointSizeF " in detail for detail in font_details)
    assert any("setPixelSize " in detail for detail in font_details)
    assert sum("stylesheet font" in detail for detail in font_details) >= 8


def test_audit_allows_qt_chrome_and_scroll_area_content_geometry(tmp_path):
    forms = tmp_path / "src" / "rc_metastudio" / "forms"
    forms.mkdir(parents=True)
    (forms / "allowed.ui").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0"><class>Allowed</class>
<widget class="QMainWindow" name="Allowed">
 <property name="geometry"><rect><x>0</x><y>0</y><width>0</width><height>0</height></rect></property>
 <widget class="QWidget" name="centralwidget"><layout class="QVBoxLayout" name="layout">
  <item><widget class="QScrollArea" name="scroll"><widget class="QWidget" name="scrollContents">
   <property name="geometry"><rect><x>0</x><y>0</y><width>300</width><height>200</height></rect></property>
  </widget></widget></item>
  <item><widget class="QPushButton" name="swatch">
   <property name="minimumSize"><size><width>24</width><height>24</height></size></property>
   <property name="maximumSize"><size><width>24</width><height>24</height></size></property>
   <property name="RCMS_semantic_size_invariant"><string>style-metric-control: square swatch follows the active Qt style</string></property>
  </widget></item>
 </layout></widget>
 <widget class="QMenuBar" name="menubar"><property name="geometry"><rect><x>0</x><y>0</y><width>300</width><height>20</height></rect></property></widget>
</widget><resources/><connections/></ui>
""",
        encoding="utf-8",
    )
    source = tmp_path / "src" / "rc_metastudio" / "network_view.py"
    source.write_text(
        """from PyQt6.QtGui import QFont, QFontDatabase

class Allowed:
    def __init__(self):
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.MAIN
        )
        system_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        inherited_font = QFont(self.font())
        label.setText("Font: inherit the system default")
        docs = "font-family and font-size belong in the layout policy documentation"
        logger.info("font: inherit the platform default")
        # layout-audit: allow=intrinsic-ratio; reason=scene follows its visual artifact
        scene.setSceneRect(0, 0, canvas_width, canvas_height)

def unrelated_scope():
    STYLE = "QLabel { font-family: Consolas; }"

def safe_scope(widget):
    STYLE = "QLabel { color: palette(text); }"
    widget.setStyleSheet(STYLE)

def sequential_overwrite(widget):
    STYLE = "QLabel { font-family: Consolas; }"
    STYLE = "QLabel { color: palette(text); }"
    widget.setStyleSheet(STYLE)
""",
        encoding="utf-8",
    )
    (tmp_path / "src" / "rc_metastudio" / "edit_dialog.py").write_text(
        """# layout-audit: allow=style-metric-control; reason=square swatch follows Qt style
swatch.setFixedSize(style_metric)
""",
        encoding="utf-8",
    )
    assert audit_qt_layout_contracts.audit_repository(tmp_path) == []
