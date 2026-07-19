import os
import sys
import json
from pathlib import Path
import subprocess

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RCMS_STUB_BACKEND", "1")
sys.path.insert(0, os.path.abspath("src/rc_metastudio"))
sys.path.insert(0, os.path.abspath("src/rc_metastudio/forms"))

from PyQt6 import QtCore, QtWidgets

ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("RCMS_QT6_BUILD_ROOT", str(ROOT / "build" / "qt6-verification"))
from rc_metastudio.qt6_ui import prepare_generated_ui_imports
from rc_metastudio.qt6_resources import ensure_application_resources

prepare_generated_ui_imports()
ensure_application_resources()


def test_main_is_a_managed_workspace_with_expanding_table_and_layouted_navigation(qapp):
    import adaptive_window
    import meta_form

    window = meta_form.MetaForm()
    try:
        state = adaptive_window.adaptive_window_state(window)
        assert state.policy.archetype is adaptive_window.WindowArchetype.WORKSPACE
        assert state.role is adaptive_window.WindowRole.MAIN
        assert (
            window.layout().sizeConstraint()
            == QtWidgets.QLayout.SizeConstraint.SetNoConstraint
        )
        assert (
            window.tableView.sizePolicy().horizontalPolicy()
            == QtWidgets.QSizePolicy.Policy.Expanding
        )
        assert (
            window.tableView.sizePolicy().verticalPolicy()
            == QtWidgets.QSizePolicy.Policy.Expanding
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
            == QtWidgets.QSizePolicy.Policy.Ignored
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
                QtWidgets.QStyle.PixelMetric.PM_SmallIconSize, None, window.menuAnalysis
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
            column, QtCore.Qt.Orientation.Horizontal, WORKSPACE_COLUMN_IDENTITY_ROLE
        )
        window.tableView.setColumnWidth(column, 277)

        window.tableView.undoStack.undo()
        window.tableView.undoStack.redo()
        qapp.processEvents()

        identity_after = window.model.headerData(
            column, QtCore.Qt.Orientation.Horizontal, WORKSPACE_COLUMN_IDENTITY_ROLE
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
            column, QtCore.Qt.Orientation.Horizontal, WORKSPACE_COLUMN_IDENTITY_ROLE
        )
        window.tableView.setColumnWidth(column, 263)

        window.delete_covariate(covariate)
        assert window.model.dataset.get_cov_obj_from_name("Age") is None

        window.tableView.undoStack.undo()
        qapp.processEvents()
        identity_after_undo = window.model.headerData(
            column, QtCore.Qt.Orientation.Horizontal, WORKSPACE_COLUMN_IDENTITY_ROLE
        )
        assert identity_after_undo == identity_before
        assert window.tableView.columnWidth(column) == 263

        window.tableView.undoStack.redo()
        assert window.model.dataset.get_cov_obj_from_name("Age") is None
        window.tableView.undoStack.undo()
        qapp.processEvents()
        assert (
            window.model.headerData(
                column, QtCore.Qt.Orientation.Horizontal, WORKSPACE_COLUMN_IDENTITY_ROLE
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
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        str(tmp_path),
    )
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
    store = QtCore.QSettings()
    store.clear()
    store.setValue("workspace_layout/schema_version", 2)
    store.setValue(
        "workspace_layout/main/frame_geometry",
        '{"height":480,"width":640,"x":40,"y":30}',
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


@pytest.mark.skipif(
    sys.platform not in ("win32", "darwin"),
    reason="Native fractional-scale evidence is collected on qwindows and cocoa.",
)
def test_workspace_table_uses_valid_logical_geometry_at_fractional_scale_factors():
    script = r"""
import json
from rc_metastudio import launch
app, window = launch.start_automation()
try:
    window.showNormal()
    window.resize(1000, 700)
    app.processEvents()
    table = window.tableView
    viewport = table.viewport()
    image = viewport.grab().toImage()
    screen = window.windowHandle().screen()
    evidence = {
        "platform": app.platformName(),
        "device_pixel_ratio": screen.devicePixelRatio(),
        "window": [window.width(), window.height()],
        "table": [table.width(), table.height()],
        "viewport": [viewport.width(), viewport.height()],
        "image": [image.width(), image.height()],
        "headers": [table.verticalHeader().width(), table.horizontalHeader().height()],
        "all_columns_positive": all(
            table.columnWidth(column) > 0
            for column in range(table.model().columnCount())
        ),
        "visible": window.isVisible() and table.isVisible() and viewport.isVisible(),
    }
    print("QT6_SCALE_EVIDENCE=" + json.dumps(evidence, sort_keys=True))
finally:
    window.current_data_unsaved = False
    window.close()
    app.processEvents()
"""
    expected_platform = "windows" if sys.platform == "win32" else "cocoa"
    evidence_by_factor = {}
    for factor in ("1", "1.25", "1.5", "1.75"):
        environment = os.environ.copy()
        environment.pop("QT_QPA_PLATFORM", None)
        environment["QT_SCALE_FACTOR"] = factor
        environment["PYTHONPATH"] = os.pathsep.join(
            (
                str(ROOT / "src"),
                str(ROOT / "src" / "rc_metastudio"),
                environment.get("PYTHONPATH", ""),
            )
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, (
            f"workspace failed at scale factor {factor}:\n{result.stdout}\n{result.stderr}"
        )
        evidence_line = next(
            line
            for line in result.stdout.splitlines()
            if line.startswith("QT6_SCALE_EVIDENCE=")
        )
        evidence = json.loads(evidence_line.split("=", 1)[1])
        evidence_by_factor[factor] = evidence
        assert evidence["platform"] == expected_platform
        assert evidence["visible"] is True
        assert evidence["all_columns_positive"] is True
        assert all(dimension > 0 for dimension in evidence["viewport"])
        assert all(dimension > 0 for dimension in evidence["image"])
        assert all(dimension > 0 for dimension in evidence["headers"])
        for logical, physical in zip(evidence["viewport"], evidence["image"]):
            assert physical == pytest.approx(
                logical * evidence["device_pixel_ratio"], abs=3
            )

    baseline = evidence_by_factor["1"]
    for factor, evidence in evidence_by_factor.items():
        assert evidence["device_pixel_ratio"] == pytest.approx(
            baseline["device_pixel_ratio"] * float(factor), abs=0.02
        )
        assert 0 < evidence["table"][0] <= evidence["window"][0]
        assert 0 < evidence["table"][1] <= evidence["window"][1]
