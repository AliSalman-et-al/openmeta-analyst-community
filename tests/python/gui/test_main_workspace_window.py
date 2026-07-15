import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RCMS_STUB_BACKEND", "1")
sys.path.insert(0, os.path.abspath("src/rc_metastudio"))
sys.path.insert(0, os.path.abspath("src/rc_metastudio/forms"))

from PyQt5 import QtCore, QtWidgets


def test_main_is_a_managed_workspace_with_expanding_table_and_layouted_navigation(qapp):
    import adaptive_window
    import meta_form

    window = meta_form.MetaForm()
    try:
        assert window.property("RCMS_window_archetype") == "workspace"
        assert window.property("RCMS_window_role") == "main"
        assert window.layout().sizeConstraint() == QtWidgets.QLayout.SetNoConstraint
        assert (
            window.tableView.sizePolicy().horizontalPolicy()
            == QtWidgets.QSizePolicy.Expanding
        )
        assert (
            window.tableView.sizePolicy().verticalPolicy()
            == QtWidgets.QSizePolicy.Expanding
        )
        assert (
            window._adaptive_window_controller.policy
            == (adaptive_window.WINDOW_POLICIES[adaptive_window.WindowRole.MAIN])
        )
        for control in (
            window.nav_left_btn,
            window.nav_up_btn,
            window.nav_down_btn,
            window.nav_right_btn,
            window.nav_add_btn,
            window.nav_lbl,
        ):
            assert window.navigationLayout.indexOf(control) >= 0
        assert window.action_auto_fit_columns.text() == "Auto-Fit Columns"
    finally:
        window.hide()
        window.deleteLater()
        qapp.processEvents()


def test_runtime_content_changes_do_not_resize_or_reposition_visible_main(qapp):
    import meta_form

    window = meta_form.MetaForm()
    window.showNormal()
    window.resize(920, 640)
    window.move(40, 30)
    window.show()
    qapp.processEvents()
    before = window.frameGeometry()

    window.cl_label.setText("A very long runtime status message " * 30)
    window.dataset_file_lbl.setText(
        "Open Project: <font color='red'>C:/"
        + "a-very-long-path/" * 30
        + "study.rcms</font>"
    )
    window.model.reset_model()
    qapp.processEvents()

    try:
        assert window.frameGeometry() == before
        assert window.cl_label.toolTip().startswith("A very long runtime status")
        assert window.dataset_file_lbl.toolTip().startswith("Open Project: C:/")
        assert "<font" not in window.dataset_file_lbl.toolTip()
        assert (
            window.dataset_file_lbl.sizePolicy().horizontalPolicy()
            == QtWidgets.QSizePolicy.Ignored
        )
    finally:
        window.hide()
        window.deleteLater()
        qapp.processEvents()


def test_main_inherits_fonts_and_navigation_icons_from_active_style(qapp):
    import meta_form
    import qt_layout

    window = meta_form.MetaForm()
    try:
        inherited_family = qapp.font().family()
        for widget in (
            window,
            window.centralwidget,
            window.menu_file,
            window.nav_lbl,
            window.dataset_file_lbl,
            window.cl_label,
        ):
            assert widget.font().family() == inherited_family

        for button in (
            window.nav_left_btn,
            window.nav_up_btn,
            window.nav_down_btn,
            window.nav_right_btn,
            window.nav_add_btn,
        ):
            expected = qt_layout.OUTCOME_NAVIGATION_ICON_EXTENT
            assert button.iconSize() == QtCore.QSize(expected, expected)
            assert button.minimumSize() == QtCore.QSize(
                qt_layout.OUTCOME_NAVIGATION_CONTROL_EXTENT,
                qt_layout.OUTCOME_NAVIGATION_CONTROL_EXTENT,
            )
            assert button.iconSize() != QtCore.QSize(64, 64)
        assert window.toolBar.iconSize() == QtCore.QSize(
            qt_layout.TOOLBAR_ICON_EXTENT, qt_layout.TOOLBAR_ICON_EXTENT
        )
        toolbar_buttons = [
            button
            for button in window.toolBar.findChildren(QtWidgets.QToolButton)
            if button.defaultAction() is not None
        ]
        assert toolbar_buttons
        assert all(
            button.minimumSize()
            == QtCore.QSize(
                qt_layout.TOOLBAR_CONTROL_EXTENT,
                qt_layout.TOOLBAR_CONTROL_EXTENT,
            )
            for button in toolbar_buttons
        )
        assert (
            window.menuAnalysis.style().pixelMetric(
                QtWidgets.QStyle.PM_SmallIconSize, None, window.menuAnalysis
            )
            == 18
        )
        for action in (
            window.action_go,
            window.action_cum_ma,
            window.action_loo_ma,
            window.action_subgroup_ma,
            window.action_meta_regression,
        ):
            assert action.icon().pixmap(18, 18).isNull() is False
            assert action.icon().pixmap(28, 28).isNull() is False
    finally:
        window.hide()
        window.deleteLater()
        qapp.processEvents()


def test_added_covariate_keeps_identity_and_width_through_undo_redo(qapp):
    import meta_form
    from workspace_column_identity import WORKSPACE_COLUMN_IDENTITY_ROLE

    window = meta_form.MetaForm()
    try:
        command = window._make_add_covariate_command("Age", "continuous")
        window.tableView.undoStack.push(command)
        column = window.model.columnCount() - 1
        identity_before = window.model.headerData(
            column, QtCore.Qt.Horizontal, WORKSPACE_COLUMN_IDENTITY_ROLE
        )
        window.tableView.setColumnWidth(column, 277)

        window.tableView.undoStack.undo()
        window.tableView.undoStack.redo()
        qapp.processEvents()

        identity_after = window.model.headerData(
            column, QtCore.Qt.Horizontal, WORKSPACE_COLUMN_IDENTITY_ROLE
        )
        assert identity_after == identity_before
        assert window.tableView.columnWidth(column) == 277
    finally:
        window.hide()
        window.deleteLater()
        qapp.processEvents()


def test_deleted_covariate_keeps_identity_and_width_through_undo_redo(qapp):
    import meta_form
    from workspace_column_identity import WORKSPACE_COLUMN_IDENTITY_ROLE

    window = meta_form.MetaForm()
    try:
        covariate = window.model.add_covariate("Age", "continuous")
        window.tableView.synchronize_column_widths()
        column = window.model.columnCount() - 1
        identity_before = window.model.headerData(
            column, QtCore.Qt.Horizontal, WORKSPACE_COLUMN_IDENTITY_ROLE
        )
        window.tableView.setColumnWidth(column, 263)

        window.delete_covariate(covariate)
        assert window.model.dataset.get_cov_obj_from_name("Age") is None

        window.tableView.undoStack.undo()
        qapp.processEvents()
        identity_after_undo = window.model.headerData(
            column, QtCore.Qt.Horizontal, WORKSPACE_COLUMN_IDENTITY_ROLE
        )
        assert identity_after_undo == identity_before
        assert window.tableView.columnWidth(column) == 263

        window.tableView.undoStack.redo()
        assert window.model.dataset.get_cov_obj_from_name("Age") is None
        window.tableView.undoStack.undo()
        qapp.processEvents()
        assert (
            window.model.headerData(
                column, QtCore.Qt.Horizontal, WORKSPACE_COLUMN_IDENTITY_ROLE
            )
            == identity_before
        )
        assert window.tableView.columnWidth(column) == 263
    finally:
        window.hide()
        window.deleteLater()
        qapp.processEvents()


def test_returning_normal_workspace_is_not_remaximized_on_first_show(qapp, tmp_path):
    import adaptive_window
    import settings

    QtCore.QSettings.setPath(
        QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, str(tmp_path)
    )
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.IniFormat)
    store = QtCore.QSettings()
    store.clear()
    store.setValue("workspace_layout/schema_version", 1)
    store.setValue(
        "workspace_layout/main/frame_geometry", QtCore.QRect(40, 30, 640, 480)
    )
    store.setValue("workspace_layout/main/maximized", False)
    window = QtWidgets.QMainWindow()
    adaptive_window.register_adaptive_window(window, adaptive_window.WindowRole.MAIN)

    settings.restore_main_window_placement(window)
    qapp.processEvents()

    try:
        assert window.isVisible()
        assert not window.isMaximized()
        assert window.frameGeometry().size() == QtCore.QSize(640, 480)
    finally:
        window.hide()
        window.deleteLater()
        qapp.processEvents()
