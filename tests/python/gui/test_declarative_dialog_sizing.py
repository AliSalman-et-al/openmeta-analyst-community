import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath("src"))
sys.path.insert(0, os.path.abspath(os.path.join("src", "forms")))

from PyQt5 import QtWidgets


def test_application_wizard_uses_workflow_policy_without_legacy_refit(qapp):
    import main_wizard

    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        wizard.restart()
        qapp.processEvents()

        assert wizard.property("RCMS_window_archetype") == "workflow"
        assert wizard.currentPage().findChild(QtWidgets.QScrollArea, "pageScrollArea")
        assert not hasattr(wizard, "_oma_first_show_refit_filter")
        assert wizard.property("RCMS_first_show_refit_options") is None
        assert wizard.property("RCMS_stable_fit_size") is None
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

        page = wizard.currentPage()

        assert wizard.width() <= int(parent.width() * 0.75)
        assert page.width() >= page.parentWidget().contentsRect().width() - 4
    finally:
        wizard.close()
        parent.close()
        qapp.processEvents()


def test_application_wizard_pages_do_not_use_background_pixmaps(qapp):
    import main_wizard

    wizard = main_wizard.MainWizard()
    try:
        for page_id in wizard.pageIds():
            page = wizard.page(page_id)
            assert page.pixmap(QtWidgets.QWizard.BackgroundPixmap).isNull()
            assert page.pixmap(QtWidgets.QWizard.BannerPixmap).isNull()
        assert wizard.pixmap(QtWidgets.QWizard.BackgroundPixmap).isNull()
        assert wizard.pixmap(QtWidgets.QWizard.BannerPixmap).isNull()
    finally:
        wizard.close()
        qapp.processEvents()
