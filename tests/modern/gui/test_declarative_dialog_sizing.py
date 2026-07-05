import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath("src"))
sys.path.insert(0, os.path.abspath(os.path.join("src", "forms")))

from PyQt5 import QtWidgets

import qt_layout


def _longest_combo_item_width(combo_box):
    return (
        max(
            combo_box.fontMetrics().horizontalAdvance(str(combo_box.itemText(index)))
            for index in range(combo_box.count())
        )
        + qt_layout.COMBO_CONTENT_HORIZONTAL_PADDING
    )


def test_analysis_dialog_uses_fixed_layout_constraint_without_refit_filter(qapp):
    dialog = QtWidgets.QDialog()
    layout = QtWidgets.QVBoxLayout(dialog)
    layout.addWidget(QtWidgets.QLabel("Analysis parameter"))

    qt_layout.fit_analysis_dialog_to_contents(dialog)

    assert layout.sizeConstraint() == QtWidgets.QLayout.SetFixedSize
    assert dialog.minimumWidth() >= qt_layout.ANALYSIS_DIALOG_MINIMUM_WIDTH
    assert dialog.minimumHeight() >= qt_layout.ANALYSIS_DIALOG_MINIMUM_HEIGHT
    assert not hasattr(dialog, "_oma_first_show_refit_filter")
    assert dialog.property("oma_first_show_refit_options") is None
    assert dialog.property("oma_stable_fit_size") is None


def test_combo_policy_caps_closed_control_but_keeps_popup_full_width(qapp):
    dialog = QtWidgets.QDialog()
    layout = QtWidgets.QVBoxLayout(dialog)
    combo = QtWidgets.QComboBox()
    combo.setProperty(
        "oma_maximum_value_control_width",
        qt_layout.ANALYSIS_DIALOG_VALUE_CONTROL_MAXIMUM_WIDTH,
    )
    combo.addItems(
        [
            "Short",
            "Diagnostic Fixed-Effect Inverse Variance With Full Description",
        ]
    )
    layout.addWidget(combo)

    qt_layout.fit_analysis_dialog_to_contents(dialog)

    longest_item_width = _longest_combo_item_width(combo)

    assert longest_item_width > qt_layout.ANALYSIS_DIALOG_VALUE_CONTROL_MAXIMUM_WIDTH
    assert combo.sizeAdjustPolicy() == QtWidgets.QComboBox.AdjustToContents
    assert combo.minimumWidth() == qt_layout.ANALYSIS_DIALOG_VALUE_CONTROL_MAXIMUM_WIDTH
    assert combo.maximumWidth() == qt_layout.ANALYSIS_DIALOG_VALUE_CONTROL_MAXIMUM_WIDTH
    assert combo.view().minimumWidth() >= longest_item_width
    assert combo.toolTip() == combo.currentText()
    assert combo.sizePolicy().horizontalPolicy() != QtWidgets.QSizePolicy.Expanding


def test_application_wizard_uses_minimum_layout_constraint_without_refit_filter(qapp):
    import main_wizard

    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        wizard.restart()
        qapp.processEvents()

        assert wizard.layout().sizeConstraint() == QtWidgets.QLayout.SetMinimumSize
        assert not hasattr(wizard, "_oma_first_show_refit_filter")
        assert wizard.property("oma_first_show_refit_options") is None
        assert wizard.property("oma_stable_fit_size") is None
    finally:
        wizard.close()
        qapp.processEvents()


def test_application_wizard_modern_style_renders_sized_nonblank_pages(qapp, tmp_path):
    import launch
    import main_wizard

    for path in ("new_dataset", "csv_import"):
        wizard = main_wizard.MainWizard(path=path)
        try:
            wizard.restart()
            wizard.show()
            qapp.processEvents()
            qapp.processEvents()

            page = wizard.currentPage()
            if page.layout() is not None:
                page.layout().activate()
            qapp.processEvents()

            image_path = tmp_path / ("modern_wizard_%s.png" % path)
            pixmap = wizard.grab()
            assert pixmap.width() >= wizard.minimumWidth()
            assert pixmap.height() >= wizard.minimumHeight()
            assert pixmap.save(str(image_path), "PNG")
            assert image_path.stat().st_size > 0
            assert not pixmap.toImage().isGrayscale()
            assert wizard.wizardStyle() == QtWidgets.QWizard.ModernStyle
            assert page.width() >= page.parentWidget().contentsRect().width() - 4
        finally:
            wizard.close()
            qapp.processEvents()
