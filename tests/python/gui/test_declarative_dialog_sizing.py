import os
from pathlib import Path
from test_types import required

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("RCMS_QT6_BUILD_ROOT", str(ROOT / "build" / "qt6-verification"))

from PyQt6 import QtWidgets
from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()


def test_application_wizard_uses_workflow_policy_without_legacy_refit(qapp):
    import adaptive_window
    import main_wizard

    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        wizard.restart()
        qapp.processEvents()

        assert (
            adaptive_window.adaptive_window_state(wizard).policy.archetype
            is adaptive_window.WindowArchetype.WORKFLOW
        )
        page = required(wizard.currentPage(), "current wizard page")
        assert page.findChild(QtWidgets.QScrollArea, "pageScrollArea")
    finally:
        wizard.close()
        qapp.processEvents()


def test_application_wizard_modern_style_renders_sized_nonblank_pages(qapp, tmp_path):
    import main_wizard

    for path in ("new_dataset", "csv_import"):
        wizard = main_wizard.MainWizard(path=path)
        try:
            wizard.restart()
            wizard.show()
            qapp.processEvents()
            qapp.processEvents()

            page = required(wizard.currentPage(), "current wizard page")
            layout = page.layout()
            if layout is not None:
                layout.activate()
            qapp.processEvents()

            image_path = tmp_path / ("modern_wizard_%s.png" % path)
            pixmap = wizard.grab()
            assert pixmap.width() >= wizard.minimumWidth()
            assert pixmap.height() >= wizard.minimumHeight()
            assert pixmap.save(str(image_path), "PNG")
            assert image_path.stat().st_size > 0
            image = pixmap.toImage()
            background = image.pixelColor(0, 0)
            assert any(
                image.pixelColor(x, y) != background
                for x in range(0, image.width(), 8)
                for y in range(0, image.height(), 8)
            )
            assert wizard.wizardStyle() == QtWidgets.QWizard.WizardStyle.ModernStyle
            assert (
                page.width()
                >= required(page.parentWidget(), "wizard parent").contentsRect().width()
                - 4
            )
        finally:
            wizard.close()
            qapp.processEvents()


def test_parented_application_wizard_does_not_inherit_shell_width(qapp):
    import main_wizard

    parent = QtWidgets.QMainWindow()
    parent.resize(1600, 900)
    parent.show()
    qapp.processEvents()

    wizard = main_wizard.MainWizard(parent=parent)
    try:
        wizard.show()
        qapp.processEvents()
        qapp.processEvents()

        page = required(wizard.currentPage(), "current wizard page")

        assert wizard.width() <= int(parent.width() * 0.75)
        assert (
            page.width()
            >= required(page.parentWidget(), "wizard parent").contentsRect().width() - 4
        )
    finally:
        wizard.close()
        parent.close()
        qapp.processEvents()


def test_application_wizard_pages_do_not_use_background_pixmaps(qapp):
    import main_wizard

    wizard = main_wizard.MainWizard()
    try:
        for page_id in wizard.pageIds():
            page = required(wizard.page(page_id), "wizard page")
            assert page.pixmap(QtWidgets.QWizard.WizardPixmap.BackgroundPixmap).isNull()
            assert page.pixmap(QtWidgets.QWizard.WizardPixmap.BannerPixmap).isNull()
        assert wizard.pixmap(QtWidgets.QWizard.WizardPixmap.BackgroundPixmap).isNull()
        assert wizard.pixmap(QtWidgets.QWizard.WizardPixmap.BannerPixmap).isNull()
    finally:
        wizard.close()
        qapp.processEvents()
