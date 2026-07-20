"""Native PyQt6 application-shell behavior."""

from __future__ import annotations

import json
import hashlib
import copy
import os
from pathlib import Path
import subprocess
import sys
import zipfile

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
            "Application shell failure teardown passed at %s." % stage in result.stdout
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

        assert (
            window.action_open.shortcut().matches(
                QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Open)
            )
            == QtGui.QKeySequence.SequenceMatch.ExactMatch
        )
        assert (
            window.action_save.shortcut().matches(
                QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Save)
            )
            == QtGui.QKeySequence.SequenceMatch.ExactMatch
        )
        assert (
            window.action_new_dataset.shortcut().matches(
                QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.New)
            )
            == QtGui.QKeySequence.SequenceMatch.ExactMatch
        )
        assert (
            window.action_quit.shortcut().matches(
                QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Quit)
            )
            == QtGui.QKeySequence.SequenceMatch.ExactMatch
        )

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
    assert isinstance(store.value("workspace_layout/main/maximized", type=bool), bool)
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
        "[1,2,3,4]",
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
        "{}",
        "[0.5]",
        "[true,0.5]",
        '["0.5",0.5]',
        "[0.0,1.0]",
        "[-0.1,1.1]",
        "[0.2,1.2]",
        "[NaN,0.5]",
        "[Infinity,0.5]",
    )
    for invalid in invalid_splitters:
        store.clear()
        store.setValue("workspace_layout/schema_version", 2)
        store.setValue("workspace_layout/results/maximized", "false")
        store.setValue("workspace_layout/results/full_screen", 1)
        store.setValue("workspace_layout/results/splitter_proportions", invalid)
        store.setValue("workspace_layout/results/portable_note", "keep")
        state = settings.load_results_window_state([QtCore.QRect(0, 0, 1920, 1080)])
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
        dynamic_names = {
            bytes(name).decode("utf-8") for name in window.dynamicPropertyNames()
        }
        assert "RCMS_window_archetype" not in dynamic_names
        assert "RCMS_window_role" not in dynamic_names
    finally:
        _close_shell(app, window)


def test_structured_project_lifecycle_opens_every_sample_and_round_trips_state(
    qapp, tmp_path, monkeypatch
):
    import launch
    import project_adapter
    import project_format

    app, window = launch.start_automation()
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "critical",
        lambda _parent, title, message: pytest.fail(f"{title}: {message}"),
    )
    try:
        for sample in sorted((ROOT / "sample_projects").glob("*.rcms")):
            expected = project_format.load_project(sample).project["dataset"]
            assert window.open(str(sample)) is True
            observed = project_adapter.dataset_to_project(window.model.dataset)[
                "dataset"
            ]
            assert observed["title"] == expected["title"]
            assert observed["analysis_family"] == expected["analysis_family"]
            assert observed["outcomes"] == expected["outcomes"]
            assert [study["name"] for study in observed["studies"]] == [
                study["name"] for study in expected["studies"]
            ]

        assert window.open(str(ROOT / "sample_projects" / "lymph.rcms")) is True
        window.model.dataset.notes = "durable project note"
        window.model.set_current_outcome("LAG positive")
        window.model.set_current_follow_up("first")
        window.model.current_txs = ["test 1"]
        window.model.current_effect = "Sens"
        window.model.set_conf_level(90.0)
        window.data_dirtied()
        destination = tmp_path / "round-trip.rcms"
        monkeypatch.setattr(
            QtWidgets.QFileDialog,
            "getSaveFileName",
            lambda **_kwargs: (str(destination), ""),
        )

        assert window.save_as() is True
        assert destination.is_file()
        assert not Path(str(destination) + ".state").exists()
        assert window.current_data_unsaved is False
        assert window.open(str(destination)) is True
        assert window.model.dataset.notes == "durable project note"
        assert window.model.current_outcome == "LAG positive"
        assert window.model.get_current_follow_up_name() == "first"
        assert window.model.current_txs == ["test 1"]
        assert window.model.current_effect == "Sens"
        assert window.model.get_global_conf_level() == 90.0

        window.model.dataset.notes = "saved through Save"
        window.data_dirtied()
        assert window.save() is True
        assert window.open(str(destination)) is True
        assert window.model.dataset.notes == "saved through Save"
    finally:
        _close_shell(app, window)


def test_packaged_sample_evidence_covers_the_authoritative_manifest(qapp):
    import launch

    app, window = launch.start_automation()
    try:
        evidence = launch._exercise_all_packaged_samples(
            window, ROOT / "sample_projects" / "BCG.rcms"
        )
        manifest = json.loads(
            (ROOT / "sample_projects" / "manifest.json").read_text(encoding="utf-8")
        )
        assert evidence["passed"] is True
        assert [item["project"] for item in evidence["projects"]] == sorted(
            item["file"] for item in manifest["projects"]
        )
        assert all(
            item["opened_in_packaged_application"] for item in evidence["projects"]
        )
    finally:
        _close_shell(app, window)


def test_structured_project_restores_nondefault_active_selection_without_normalizing_it(
    qapp, tmp_path, monkeypatch
):
    import launch
    import project_format

    source = project_format.load_project(ROOT / "sample_projects" / "amino.rcms")
    project = copy.deepcopy(source.project)
    for outcome in project["dataset"]["outcomes"]:
        if outcome["name"] == "nephrotoxic":
            outcome["follow_ups"].append("second")
    for study in project["dataset"]["studies"]:
        first = next(
            unit
            for unit in study["analysis_units"]
            if unit["outcome"] == "nephrotoxic" and unit["follow_up"] == "first"
        )
        second = copy.deepcopy(first)
        second["follow_up"] = "second"
        study["analysis_units"].append(second)
    state = {
        "schema_version": 1,
        "active_outcome": "nephrotoxic",
        "active_follow_up": "second",
        "active_groups": ["tx B", "tx A"],
        "active_effect": "RR",
        "confidence_level": 90.0,
    }
    selected = tmp_path / "selected.rcms"
    project_format.save_project(selected, project, state)

    app, window = launch.start_automation()
    monkeypatch.setattr(QtWidgets.QMessageBox, "critical", lambda *_args: None)
    try:
        assert window.open(str(selected)) is True
        assert window.model.current_outcome == "nephrotoxic"
        assert window.model.get_current_follow_up_name() == "second"
        assert window.model.current_txs == ["tx B", "tx A"]
        assert window.model.current_effect == "RR"
        assert window.model.get_global_conf_level() == 90.0
        assert window.save() is True
        assert window.open(str(selected)) is True
        assert window.model.current_outcome == "nephrotoxic"
        assert window.model.get_current_follow_up_name() == "second"
        assert window.model.current_txs == ["tx B", "tx A"]
        assert window.model.current_effect == "RR"
    finally:
        _close_shell(app, window)


@pytest.mark.parametrize("wizard_path", ["new_dataset", "csv_import"])
def test_wizard_created_projects_save_as_latest_structured_containers(
    qapp, tmp_path, monkeypatch, wizard_path
):
    import launch
    import project_format

    app, window = launch.start_automation()
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "critical",
        lambda _parent, title, message: pytest.fail(f"{title}: {message}"),
    )
    try:
        result = {
            "path": wizard_path,
            "outcome_info": {
                "arms": "two",
                "data_type": "binary",
                "sub_type": "proportions",
                "effect": "OR",
                "metric_choices": ["OR", "RR"],
                "name": "Mortality",
            },
            "selected_dataset": None,
        }
        if wizard_path == "csv_import":
            result["csv_data"] = {
                "headers": [],
                "expected_headers": [],
                "data": [["Alpha", "2020", "1", "10", "2", "12"]],
                "covariate_names": [],
                "covariate_types": [],
            }
        window._handle_wizard_results(result)
        destination = tmp_path / f"{wizard_path}.rcms"
        monkeypatch.setattr(
            QtWidgets.QFileDialog,
            "getSaveFileName",
            lambda **_kwargs: (str(destination), ""),
        )

        assert window.save_as() is True
        document = project_format.load_project(destination)
        assert document.format_version == project_format.CURRENT_FORMAT_VERSION
        assert document.project["dataset"]["outcomes"][0]["name"] == "Mortality"
        assert document.project["dataset"]["summary"]["effect"] == "OR"
        assert document.project["dataset"]["summary"]["metric_choices"] == ["OR", "RR"]
    finally:
        _close_shell(app, window)


def test_cancelled_save_as_blocks_new_open_recent_and_import_for_unsaved_wizards(
    qapp, monkeypatch
):
    import launch
    import main_wizard

    target = str(ROOT / "sample_projects" / "amino.rcms")
    for source_path in ("new_dataset", "csv_import"):
        app, window = launch.start_automation()
        try:
            result = {
                "path": source_path,
                "outcome_info": {
                    "arms": "two",
                    "data_type": "binary",
                    "sub_type": "proportions",
                    "effect": "OR",
                    "metric_choices": ["OR", "RR"],
                    "name": "Unsaved outcome",
                },
                "selected_dataset": None,
            }
            if source_path == "csv_import":
                result["csv_data"] = {
                    "headers": [],
                    "expected_headers": [],
                    "data": [["Unsaved study", "2024", "1", "10", "2", "12"]],
                    "covariate_names": [],
                    "covariate_types": [],
                }
            window._handle_wizard_results(result)
            original_model = window.model
            original_path = window.out_path
            original_title = window.model.dataset.title
            assert window.current_data_unsaved is True

            monkeypatch.setattr(
                window,
                "prompt_to_save_unsaved_data",
                lambda: QtWidgets.QMessageBox.StandardButton.Yes,
            )
            monkeypatch.setattr(
                QtWidgets.QFileDialog,
                "getSaveFileName",
                lambda **_kwargs: ("", ""),
            )
            monkeypatch.setattr(
                main_wizard,
                "MainWizard",
                lambda *_args, **_kwargs: pytest.fail(
                    "replacement wizard opened after Save As cancellation"
                ),
            )

            for action in (
                window.create_new_dataset,
                lambda: window.open(target),
                lambda: window.dataset_selected(target),
                window._import_csv,
            ):
                action()
                assert window.model is original_model
                assert window.tableView.model() is original_model
                assert window.out_path == original_path
                assert window.model.dataset.title == original_title
                assert window.current_data_unsaved is True
        finally:
            _close_shell(app, window)
            monkeypatch.undo()


def test_failed_open_and_save_preserve_current_project_dirty_state_and_recents(
    qapp, tmp_path, monkeypatch
):
    import launch
    import project_adapter
    import project_format
    import settings

    app, window = launch.start_automation()
    meta_form = sys.modules["meta_form"]
    assert "project_pickle" not in meta_form.__dict__
    assert "_load_project_pickle" not in meta_form.__dict__
    critical_messages = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "critical",
        lambda _parent, title, message: critical_messages.append((title, message)),
    )
    try:
        good = ROOT / "sample_projects" / "amino.rcms"
        assert window.open(str(good)) is True
        prior_path = window.out_path
        prior_title = window.model.dataset.title
        prior_recents = list(settings.get_setting("recent_files"))

        malformed = tmp_path / "malformed.rcms"
        malformed.write_bytes(b"not a project")
        pickle_file = tmp_path / "pickle.rcms"
        pickle_file.write_bytes(b"\x80\x02cma_dataset\nDataset\n.")

        def rewritten_project(name, mutate):
            destination = tmp_path / name
            with zipfile.ZipFile(good) as archive:
                members = {entry: archive.read(entry) for entry in archive.namelist()}
            decoded = {
                entry: json.loads(payload.decode("utf-8"))
                for entry, payload in members.items()
            }
            mutate(decoded)
            project_payload = (
                json.dumps(
                    decoded["project.json"], sort_keys=True, separators=(",", ":")
                )
                + "\n"
            ).encode("utf-8")
            state_payload = (
                json.dumps(decoded["state.json"], sort_keys=True, separators=(",", ":"))
                + "\n"
            ).encode("utf-8")
            manifest = decoded["manifest.json"]
            manifest["members"]["project.json"] = {
                "sha256": hashlib.sha256(project_payload).hexdigest(),
                "size": len(project_payload),
            }
            manifest["members"]["state.json"] = {
                "sha256": hashlib.sha256(state_payload).hexdigest(),
                "size": len(state_payload),
            }
            manifest_payload = (
                json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
            ).encode("utf-8")
            with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("manifest.json", manifest_payload)
                archive.writestr("project.json", project_payload)
                archive.writestr("state.json", state_payload)
            return destination

        unknown_version = rewritten_project(
            "unknown-version.rcms",
            lambda members: members["manifest.json"].update(format_version=99),
        )
        schema_invalid = rewritten_project(
            "schema-invalid.rcms",
            lambda members: members["state.json"].update(
                confidence_level="ninety-five"
            ),
        )

        for rejected, expected_message in (
            (malformed, "valid ZIP container"),
            (pickle_file, "valid ZIP container"),
            (unknown_version, "unsupported project format version"),
            (schema_invalid, "confidence_level"),
        ):
            assert window.open(str(rejected)) is None
            assert window.out_path == prior_path
            assert window.model.dataset.title == prior_title
            assert settings.get_setting("recent_files") == prior_recents
            assert expected_message in critical_messages[-1][1]

        window.model.dataset.notes = "unsaved"
        window.data_dirtied()
        destination = tmp_path / "failed-save.rcms"
        monkeypatch.setattr(
            QtWidgets.QFileDialog,
            "getSaveFileName",
            lambda **_kwargs: (str(destination), ""),
        )
        for boundary, owner, attribute in (
            ("adapter failed", project_adapter, "dataset_to_project"),
            ("disk full", project_format, "save_project"),
        ):
            with monkeypatch.context() as context:
                context.setattr(
                    owner,
                    attribute,
                    lambda *_args, message=boundary, **_kwargs: (_ for _ in ()).throw(
                        OSError(message)
                    ),
                )
                assert window.save_as() is False
            assert window.out_path == prior_path
            assert window.model.dataset.notes == "unsaved"
            assert window.current_data_unsaved is True
            assert settings.get_setting("recent_files") == prior_recents
            assert boundary in critical_messages[-1][1]
    finally:
        _close_shell(app, window)


def test_durable_save_and_open_succeed_when_recent_project_bookkeeping_fails(
    qapp, tmp_path, monkeypatch
):
    import launch
    import meta_form
    import settings

    app, window = launch.start_automation()
    warnings = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "warning",
        lambda _parent, title, message, *_args, **_kwargs: warnings.append(
            (title, message)
        ),
    )
    try:
        assert window.open(str(ROOT / "sample_projects" / "amino.rcms")) is True
        for fault in ("add", "menu", "settings"):
            destination = tmp_path / f"saved-despite-{fault}.rcms"
            window.model.dataset.notes = f"durable-{fault}"
            window.data_dirtied()
            with monkeypatch.context() as context:
                context.setattr(
                    QtWidgets.QFileDialog,
                    "getSaveFileName",
                    lambda **_kwargs: (str(destination), ""),
                )
                if fault == "add":
                    context.setattr(
                        meta_form,
                        "add_file_to_recent_files",
                        lambda _path: (_ for _ in ()).throw(
                            OSError("add recent failed")
                        ),
                    )
                elif fault == "menu":
                    context.setattr(
                        window,
                        "populate_open_recent_menu",
                        lambda: (_ for _ in ()).throw(
                            RuntimeError("menu rebuild failed")
                        ),
                    )
                else:
                    context.setattr(
                        settings,
                        "save_settings",
                        lambda: (_ for _ in ()).throw(OSError("settings write failed")),
                    )
                assert window.save_as() is True
            assert destination.is_file()
            assert window.out_path == str(destination)
            assert window.current_data_unsaved is False
            assert window.model.analysis_source_path == str(destination)
            assert "saved successfully" in warnings[-1][1]

            with monkeypatch.context() as context:
                if fault == "add":
                    context.setattr(
                        meta_form,
                        "add_file_to_recent_files",
                        lambda _path: (_ for _ in ()).throw(
                            OSError("add recent failed")
                        ),
                    )
                elif fault == "menu":
                    context.setattr(
                        window,
                        "populate_open_recent_menu",
                        lambda: (_ for _ in ()).throw(
                            RuntimeError("menu rebuild failed")
                        ),
                    )
                else:
                    context.setattr(
                        settings,
                        "save_settings",
                        lambda: (_ for _ in ()).throw(OSError("settings write failed")),
                    )
                assert window.open(str(destination)) is True
            assert window.out_path == str(destination)
            assert window.current_data_unsaved is False
            assert window.model.dataset.notes == f"durable-{fault}"
            assert "opened successfully" in warnings[-1][1]
    finally:
        _close_shell(app, window)


def test_post_replace_durability_failure_commits_save_and_authorizes_next_actions(
    qapp, tmp_path, monkeypatch
):
    import launch
    import main_wizard
    import project_format

    app, window = launch.start_automation()
    warnings = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "warning",
        lambda _parent, title, message, *_args, **_kwargs: warnings.append(
            (title, message)
        ),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "critical",
        lambda *_args, **_kwargs: pytest.fail(
            "durability uncertainty was falsely reported as save failure"
        ),
    )
    try:
        assert window.open(str(ROOT / "sample_projects" / "amino.rcms")) is True
        destination = tmp_path / "durability.rcms"
        window.model.dataset.notes = "save-as installed"
        window.data_dirtied()
        monkeypatch.setattr(
            QtWidgets.QFileDialog,
            "getSaveFileName",
            lambda **_kwargs: (str(destination), ""),
        )

        def uncertain(_destination):
            raise project_format.ProjectDurabilityError(
                "project was atomically replaced, but directory durability could not be confirmed; the new file is already installed"
            )

        with monkeypatch.context() as context:
            context.setattr(project_format, "_fsync_parent_directory", uncertain)
            assert window.save_as() is True
        assert window.out_path == str(destination)
        assert window.model.analysis_source_path == str(destination)
        assert window.current_data_unsaved is False
        assert project_format.load_project(destination).project["dataset"]["notes"] == (
            "save-as installed"
        )
        assert warnings[-1][0] == "Project Saved; Durability Uncertain"
        assert "installed the saved project" in warnings[-1][1]

        wizard_calls = []

        class CancelledWizard:
            def __init__(self, *_args, **_kwargs):
                wizard_calls.append(True)

            def exec(self):
                return False

        monkeypatch.setattr(main_wizard, "MainWizard", CancelledWizard)
        monkeypatch.setattr(
            window,
            "prompt_to_save_unsaved_data",
            lambda: pytest.fail("clean installed save prompted before New"),
        )
        window.create_new_dataset()
        assert wizard_calls == [True]

        window.model.dataset.notes = "save installed"
        window.data_dirtied()
        with monkeypatch.context() as context:
            context.setattr(project_format, "_fsync_parent_directory", uncertain)
            assert window.save() is True
        assert window.current_data_unsaved is False
        assert project_format.load_project(destination).project["dataset"]["notes"] == (
            "save installed"
        )
        assert warnings[-1][0] == "Project Saved; Durability Uncertain"

        assert window.open(str(ROOT / "sample_projects" / "BCG.rcms")) is True
        assert window.model.dataset.title == "BCG"
    finally:
        _close_shell(app, window)


def test_open_rolls_back_constructor_rebind_and_ui_initialization_failures(
    qapp, monkeypatch
):
    import launch
    import ma_data_table_model

    app, window = launch.start_automation()
    errors = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "critical",
        lambda _parent, title, message: errors.append((title, message)),
    )
    source = str(ROOT / "sample_projects" / "amino.rcms")
    candidate = str(ROOT / "sample_projects" / "BCG.rcms")
    try:
        assert window.open(source) is True
        old_model = window.model
        old_table_model = window.tableView.model()
        old_path = window.out_path
        old_dirty = window.current_data_unsaved
        old_connection_count = len(window._model_signal_connections)
        selected = old_model.index(0, old_model.NAME)
        window.tableView.setCurrentIndex(selected)
        window.tableView.selectionModel().select(
            selected, QtCore.QItemSelectionModel.SelectionFlag.Select
        )

        def constructor_failure(context):
            context.setattr(
                ma_data_table_model,
                "DatasetModel",
                lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    RuntimeError("candidate construction failed")
                ),
            )

        def rebind_failure(context):
            def fail_after_rebind(model):
                QtWidgets.QTableView.setModel(window.tableView, model)
                raise RuntimeError("table rebind failed")

            context.setattr(window.tableView, "setModel", fail_after_rebind)

        def ui_failure(context):
            context.setattr(
                window,
                "model_updated",
                lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    RuntimeError("UI initialization failed")
                ),
            )

        sync_failures = []

        def sync_failure(context):
            def always_fail():
                sync_failures.append(True)
                raise RuntimeError("column synchronization failed")

            context.setattr(window.tableView, "synchronize_column_widths", always_fail)
            context.setattr(
                window,
                "_restore_metric_menu_state",
                lambda _snapshot: (_ for _ in ()).throw(
                    RuntimeError("rollback menu restore failed")
                ),
            )

        for inject, message in (
            (constructor_failure, "candidate construction failed"),
            (rebind_failure, "table rebind failed"),
            (sync_failure, "column synchronization failed"),
            (ui_failure, "UI initialization failed"),
        ):
            with monkeypatch.context() as context:
                inject(context)
                assert window.open(candidate) is None
            assert message in errors[-1][1]
            assert window.model is old_model
            assert window.tableView.model() is old_table_model
            assert window.out_path == old_path
            assert window.current_data_unsaved is old_dirty
            assert len(window._model_signal_connections) == old_connection_count
            assert window.tableView.currentIndex().row() == 0
            assert window.tableView.currentIndex().column() == old_model.NAME
            assert selected in window.tableView.selectionModel().selectedIndexes()
            assert window.model.dataset.title == "aminoglycosides"
            assert window.model.rowCount() > 0

        # Rollback did not retry the same failing synchronization operation.
        assert sync_failures == [True]

        # The restored connections and model remain usable for a later open.
        assert window.open(candidate) is True
        assert window.model.dataset.title == "BCG"
    finally:
        _close_shell(app, window)


def test_late_cross_family_open_failure_restores_actual_metric_menu_both_directions(
    qapp, monkeypatch
):
    import launch

    def metric_menu_signature(window):
        return (
            window.menuMetric.isEnabled(),
            tuple(
                (
                    action.menu().title(),
                    tuple(
                        (
                            metric_action.data(),
                            metric_action.isChecked(),
                            metric_action.isEnabled(),
                        )
                        for metric_action in action.menu().actions()
                    ),
                )
                for action in window.menuMetric.actions()
                if action.menu() is not None
            ),
        )

    app, window = launch.start_automation()
    errors = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "critical",
        lambda _parent, title, message: errors.append((title, message)),
    )
    binary = str(ROOT / "sample_projects" / "amino.rcms")
    continuous = str(ROOT / "sample_projects" / "continuous.rcms")
    try:
        assert window.open(binary) is True
        binary_model = window.model
        binary_menu = metric_menu_signature(window)
        binary_marker = window.metric_menu_is_set_for
        with monkeypatch.context() as context:
            context.setattr(
                window,
                "data_dirtied",
                lambda: (_ for _ in ()).throw(
                    RuntimeError("late continuous installation failure")
                ),
            )
            assert window.open(continuous) is None
        assert "late continuous installation failure" in errors[-1][1]
        assert window.model is binary_model
        assert window.tableView.model() is binary_model
        assert window.metric_menu_is_set_for == binary_marker
        assert metric_menu_signature(window) == binary_menu

        assert window.open(continuous) is True
        continuous_model = window.model
        continuous_menu = metric_menu_signature(window)
        continuous_marker = window.metric_menu_is_set_for
        with monkeypatch.context() as context:
            context.setattr(
                window,
                "data_dirtied",
                lambda: (_ for _ in ()).throw(
                    RuntimeError("late binary installation failure")
                ),
            )
            assert window.open(binary) is None
        assert "late binary installation failure" in errors[-1][1]
        assert window.model is continuous_model
        assert window.tableView.model() is continuous_model
        assert window.metric_menu_is_set_for == continuous_marker
        assert metric_menu_signature(window) == continuous_menu
    finally:
        _close_shell(app, window)
