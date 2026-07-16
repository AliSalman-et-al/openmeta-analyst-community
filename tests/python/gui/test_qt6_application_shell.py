"""Native PyQt6 application-shell behavior."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from PyQt6 import QtCore, QtGui, QtWidgets


ROOT = Path(__file__).resolve().parents[3]


def _close_shell(app: QtWidgets.QApplication, window: QtWidgets.QMainWindow) -> None:
    window.current_data_unsaved = False
    window.close()
    app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()


def _configure_qsettings_identity(qapp: QtWidgets.QApplication) -> None:
    qapp.setOrganizationName("Research Consultancy")
    qapp.setApplicationName("RCMetaStudio")


def test_maintained_entry_point_reuses_one_native_application_and_closes_shell(qapp):
    import launch

    app, first = launch.start_automation()
    try:
        assert app is qapp
        assert type(app).__module__.startswith("PyQt6")
        assert QtWidgets.QApplication.instance() is app
        assert first.isVisible()
        assert app.applicationName() == "RCMetaStudio"
        assert app.organizationName() == "Research Consultancy"
        assert app.applicationVersion()
    finally:
        _close_shell(app, first)

    app_again, second = launch.start_automation()
    try:
        assert app_again is app
        assert second is not first
        assert second.isVisible()
        assert first not in app.topLevelWidgets()
    finally:
        _close_shell(app, second)

    assert second not in app.topLevelWidgets()


def test_console_entry_point_launches_real_shell_and_exits_cleanly():
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["RCMS_STUB_BACKEND"] = "1"
    environment["RCMS_QT6_BUILD_ROOT"] = os.environ.get(
        "RCMS_QT6_BUILD_ROOT", str(ROOT / "build" / "qt6")
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "rc_metastudio",
            "--automation-shell-smoke",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Application shell smoke passed with Qt platform offscreen." in result.stdout


def test_startup_failure_injections_release_qt_objects_with_fatal_warnings():
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["QT_FATAL_WARNINGS"] = "1"
    environment["RCMS_STUB_BACKEND"] = "1"
    environment["RCMS_QT6_BUILD_ROOT"] = os.environ.get(
        "RCMS_QT6_BUILD_ROOT", str(ROOT / "build" / "qt6")
    )
    for stage in ("r-load", "meta-form"):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "rc_metastudio",
                "--automation-shell-failure-smoke",
                stage,
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert (
            "Application shell failure teardown passed at %s." % stage
            in result.stdout
        )


def test_shell_actions_use_native_resources_and_fire_once(qapp, monkeypatch):
    import launch
    import about_legal_dialog
    import meta_form

    about_calls: list[QtWidgets.QWidget] = []
    open_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        about_legal_dialog.AboutLegalDialog,
        "exec",
        lambda dialog: about_calls.append(dialog.parentWidget()) or 0,
    )
    monkeypatch.setattr(
        meta_form.QFileDialog,
        "getOpenFileName",
        lambda **kwargs: open_calls.append(kwargs) or ("", ""),
    )

    app, window = launch.start_automation()
    try:
        connected_actions = (
            window.action_save,
            window.action_save_as,
            window.action_open,
            window.action_new_dataset,
            window.action_quit,
            window.action_go,
            window.action_cum_ma,
            window.action_loo_ma,
            window.action_undo,
            window.action_redo,
            window.action_copy,
            window.action_paste,
            window.action_auto_fit_columns,
            window.action_edit,
            window.action_view_network,
            window.action_add_covariate,
            window.action_meta_regression,
            window.action_subgroup_ma,
            window.action_about_legal,
            window.action_change_conf_level,
            window.action_import_csv,
        )
        for action in connected_actions:
            assert isinstance(action, QtGui.QAction)
            assert action.text()
            assert not action.icon().isNull()

        assert [action.text() for action in window.menuBar().actions()] == [
            "File",
            "Edit",
            "View",
            "Analysis",
            "Dataset",
            "Help",
        ]

        assert window.action_open.shortcut().matches(
            QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Open)
        ) == QtGui.QKeySequence.SequenceMatch.ExactMatch
        assert window.action_save.shortcut().matches(
            QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Save)
        ) == QtGui.QKeySequence.SequenceMatch.ExactMatch
        assert window.action_new_dataset.shortcut().matches(
            QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.New)
        ) == QtGui.QKeySequence.SequenceMatch.ExactMatch
        assert window.action_quit.shortcut().matches(
            QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Quit)
        ) == QtGui.QKeySequence.SequenceMatch.ExactMatch

        window.action_about_legal.trigger()
        window.action_open.trigger()
        app.processEvents()

        assert about_calls == [window]
        assert len(open_calls) == 1
        assert open_calls[0]["parent"] is window
        assert "*.rcms" in str(open_calls[0]["filter"])
    finally:
        _close_shell(app, window)


def test_close_cancel_and_failed_save_keep_owned_shell_alive(qapp, monkeypatch):
    import launch

    app, window = launch.start_automation()
    window.current_data_unsaved = True
    monkeypatch.setattr(
        window,
        "prompt_to_save_unsaved_data",
        lambda: QtWidgets.QMessageBox.StandardButton.Cancel,
    )

    assert window.close() is False
    assert window.isVisible()

    monkeypatch.setattr(
        window,
        "prompt_to_save_unsaved_data",
        lambda: QtWidgets.QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(window, "save", lambda: None)
    assert window.close() is False
    assert window.isVisible()

    monkeypatch.setattr(
        window,
        "prompt_to_save_unsaved_data",
        lambda: QtWidgets.QMessageBox.StandardButton.No,
    )
    assert window.close() is True
    app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()
    assert window not in app.topLevelWidgets()


def test_qt6_settings_migration_preserves_domain_values_and_recent_projects(qapp):
    import settings

    _configure_qsettings_identity(qapp)
    store = QtCore.QSettings()
    store.clear()
    store.setValue("workspace_layout/schema_version", 1)
    store.setValue("main_window/geometry", QtCore.QByteArray(b"qt5-geometry"))
    store.setValue("main_window/window_state", QtCore.QByteArray(b"qt5-state"))
    store.setValue("main_window/splitter", QtCore.QByteArray(b"qt5-splitter"))
    store.setValue("main_window/screen", "retired-monitor")
    store.setValue("workspace_layout/main/frame_geometry", QtCore.QRect(1, 2, 3, 4))
    store.setValue("workspace_layout/main/maximized", False)
    store.setValue("workspace_layout/main/full_screen", True)
    store.setValue("workspace_layout/main/column_widths", '{"version":1}')
    store.setValue("workspace_layout/results/splitter_proportions", [30, 70])
    store.setValue("analysis/default_method", "REML")
    store.setValue("domain/confidence_level", 95)
    store.beginGroup("recent_files")
    store.setValue("0", "first.rcms")
    store.setValue("1", "second.rcms")
    store.endGroup()

    settings.load_settings()

    assert not store.contains("main_window/geometry")
    assert not store.contains("main_window/window_state")
    assert not store.contains("main_window/splitter")
    assert not store.contains("main_window/screen")
    assert not store.contains("workspace_layout/main/frame_geometry")
    assert not store.contains("workspace_layout/main/maximized")
    assert not store.contains("workspace_layout/main/full_screen")
    assert not store.contains("workspace_layout/results/splitter_proportions")
    assert store.value("workspace_layout/main/column_widths") == '{"version":1}'
    assert store.value("analysis/default_method") == "REML"
    assert store.value("domain/confidence_level", type=int) == 95
    assert store.value(settings.APPLICATION_SETTINGS_SCHEMA_KEY, type=int) == 1
    assert settings.get_setting("recent_files") == ["first.rcms", "second.rcms"]


def test_workspace_settings_store_only_portable_typed_values(qapp):
    import settings

    _configure_qsettings_identity(qapp)
    store = QtCore.QSettings()
    store.clear()
    settings.migrate_workspace_layout_settings()
    window = QtWidgets.QMainWindow()
    window.setGeometry(20, 30, 900, 600)

    settings.save_main_window_placement(window)
    raw_geometry = store.value("workspace_layout/main/frame_geometry")
    decoded = json.loads(raw_geometry)

    assert decoded == {"height": 600, "width": 900, "x": 20, "y": 30}
    assert isinstance(raw_geometry, str)
    assert isinstance(
        store.value("workspace_layout/main/maximized", type=bool), bool
    )
    assert settings.load_main_window_placement(
        [QtCore.QRect(0, 0, 1920, 1080)]
    ).frame_geometry == QtCore.QRect(20, 30, 900, 600)


def test_invalid_portable_setting_resets_only_its_own_field(qapp):
    import settings

    _configure_qsettings_identity(qapp)
    store = QtCore.QSettings()
    store.clear()
    store.setValue("domain/confidence_level", 90)
    store.setValue("digits", 100)

    assert settings.get_setting("digits") == 2
    assert store.value("domain/confidence_level", type=int) == 90

    with pytest.raises(TypeError):
        settings.update_setting("digits", "5")
    assert settings.get_setting("digits") == 2
    with pytest.raises(TypeError):
        settings.update_setting(
            "recent_files", ["project-%d.rcms" % index for index in range(11)]
        )


def test_schema_versions_use_strict_raw_integer_validation(qapp):
    import settings

    _configure_qsettings_identity(qapp)
    store = QtCore.QSettings()
    invalid_versions = (True, "1", 0, -1, 2**40, 1.0, QtCore.QByteArray(b"1"))
    for invalid in invalid_versions:
        store.clear()
        store.setValue(settings.APPLICATION_SETTINGS_SCHEMA_KEY, invalid)
        store.setValue("workspace_layout/schema_version", invalid)
        store.setValue("domain/confidence_level", 90)
        settings.migrate_application_settings()
        assert type(store.value(settings.APPLICATION_SETTINGS_SCHEMA_KEY)) is int
        assert store.value(settings.APPLICATION_SETTINGS_SCHEMA_KEY) == 1
        assert type(store.value("workspace_layout/schema_version")) is int
        assert store.value("workspace_layout/schema_version") == 2
        assert store.value("domain/confidence_level") == 90


def test_geometry_codec_rejects_overflow_and_repairs_only_geometry(qapp):
    import settings

    _configure_qsettings_identity(qapp)
    store = QtCore.QSettings()
    invalid_values = (
        QtCore.QRect(1, 2, 3, 4),
        '[1,2,3,4]',
        '{"height":4,"width":3,"x":true,"y":2}',
        '{"height":4,"width":0,"x":1,"y":2}',
        '{"height":4,"width":3,"x":2147483647,"y":2}',
        '{"height":2147483648,"width":3,"x":1,"y":2}',
        '{"height":4,"width":3,"x":-2147483649,"y":2}',
    )
    for invalid in invalid_values:
        store.clear()
        store.setValue("workspace_layout/schema_version", 2)
        store.setValue("workspace_layout/main/frame_geometry", invalid)
        store.setValue("workspace_layout/main/column_widths", "portable-widths")
        placement = settings.load_main_window_placement(
            [QtCore.QRect(0, 0, 1920, 1080)]
        )
        assert placement.frame_geometry is None
        assert not store.contains("workspace_layout/main/frame_geometry")
        assert store.value("workspace_layout/main/column_widths") == "portable-widths"


def test_workspace_boolean_and_splitter_codecs_repair_only_invalid_fields(qapp):
    import settings

    _configure_qsettings_identity(qapp)
    store = QtCore.QSettings()
    invalid_splitters = (
        "not-json",
        '{}',
        '[0.5]',
        '[true,0.5]',
        '["0.5",0.5]',
        '[0.0,1.0]',
        '[-0.1,1.1]',
        '[0.2,1.2]',
        '[NaN,0.5]',
        '[Infinity,0.5]',
    )
    for invalid in invalid_splitters:
        store.clear()
        store.setValue("workspace_layout/schema_version", 2)
        store.setValue("workspace_layout/results/maximized", "false")
        store.setValue("workspace_layout/results/full_screen", 1)
        store.setValue("workspace_layout/results/splitter_proportions", invalid)
        store.setValue("workspace_layout/results/portable_note", "keep")
        state = settings.load_results_window_state(
            [QtCore.QRect(0, 0, 1920, 1080)]
        )
        assert state.maximized is True
        assert state.full_screen is False
        assert state.splitter_proportions == (0.3, 0.7)
        assert not store.contains("workspace_layout/results/maximized")
        assert not store.contains("workspace_layout/results/full_screen")
        assert json.loads(
            store.value("workspace_layout/results/splitter_proportions")
        ) == [0.3, 0.7]
        assert store.value("workspace_layout/results/portable_note") == "keep"

    invalid_sizes = (
        [True, 10],
        ["10", 20],
        [float("nan"), 20],
        [float("inf"), 20],
        [-1, 20],
        [0, 20],
        [2**31, 20],
        [10],
    )
    for sizes in invalid_sizes:
        assert settings._splitter_proportions(sizes) == [0.3, 0.7]


def test_adaptive_shell_state_is_typed_without_dynamic_qt_properties(qapp):
    import adaptive_window
    import launch

    app, window = launch.start_automation()
    try:
        state = adaptive_window.adaptive_window_state(window)
        assert state.role is adaptive_window.WindowRole.MAIN
        assert state.policy.archetype is adaptive_window.WindowArchetype.WORKSPACE
        dynamic_names = {bytes(name).decode("utf-8") for name in window.dynamicPropertyNames()}
        assert "RCMS_window_archetype" not in dynamic_names
        assert "RCMS_window_role" not in dynamic_names
    finally:
        _close_shell(app, window)
