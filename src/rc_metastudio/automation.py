"""Small hidden qualification hook for the packaged application."""

from __future__ import annotations

import os
import sys
import json
from pathlib import Path

from rc_metastudio import app_error_handler, qt6_resources, settings
from rc_metastudio.launch import (
    _argument_value,
    _configure_application,
    _dispose_new_top_levels,
    _dispose_qobjects,
    _emit_automation_phase,
    _import_main_window,
    _show_main_window,
    _top_level_ids,
    load_R_libraries,
)


AUTOMATION_SMOKE_LOG_ENV = "RCMS_AUTOMATION_SMOKE_LOG"


def _force_table_paint(app, window) -> None:
    """Allow packaged qualification to flush the ordinary Qt table path."""
    del window
    app.processEvents()


def _log(message: str) -> None:
    path = os.environ.get(AUTOMATION_SMOKE_LOG_ENV)
    if path:
        with open(path, "a", encoding="utf-8") as output:
            output.write(message + "\n")


def _mark_workspace_saved(window) -> None:
    workspace = getattr(window, "workspace", None)
    if workspace is not None and workspace.document is not None:
        workspace.mark_saved()


def start_automation(phase_callback=None):
    """Construct the ordinary application composition for tests and packaging."""
    qt6_resources.ensure_application_resources()
    app_error_handler.install_global_exception_handler()
    main_window = _import_main_window()
    app = app_error_handler.get_or_create_application(sys.argv)
    _configure_application(app)
    _emit_automation_phase(phase_callback, "application:configured")
    baseline_ids = _top_level_ids(app)
    try:
        settings.setup_directories()
        if os.environ.get("RCMS_REQUIRE_IN_PROCESS_RPY2") == "1":
            load_R_libraries(app, None, phase_callback=phase_callback)
        meta = main_window.MainWindow()
        _show_main_window(meta)
        return app, meta
    except BaseException:
        _dispose_new_top_levels(app, baseline_ids)
        raise


def start_automation_smoke(
    sample_path: str, *, require_native_window: bool = False
) -> int:
    """Run one ordinary open/paint/close path used by shipped qualification."""
    app, window = start_automation()
    try:
        if require_native_window:
            assert_native_window_smoke(app, window)
        if not window.open(os.path.abspath(sample_path), raise_on_error=True):
            raise RuntimeError("packaged smoke could not open the project")
        app.processEvents()
        evidence_path = os.environ.get("RCMS_PACKAGE_SMOKE_EVIDENCE")
        if evidence_path:
            _write_json(
                evidence_path,
                {
                    "schema_version": 1,
                    "passed": True,
                    "platform_plugin": app.platformName().lower(),
                    "workflows": {
                        "automation_entry_point": True,
                        "converted_sample": Path(sample_path).name,
                    },
                    "scales": [],
                },
            )
        return 0
    finally:
        _mark_workspace_saved(window)
        window.close()
        app.processEvents()
        _dispose_qobjects(app, (window,))
        app.quit()


def _run_automation_smoke(callback):
    try:
        return callback()
    except BaseException as exc:
        _log("%s: %s" % (type(exc).__name__, exc))
        raise


def _write_json(path: str, value: dict) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def start_package_runtime_probe(output_path: str) -> int:
    """Record the runtime identity loaded by the packaged executable."""
    from PyQt6 import QtCore

    app = app_error_handler.get_or_create_application(sys.argv)
    _configure_application(app)
    primary = app.primaryScreen()
    if primary is None:
        raise SystemExit("Packaged runtime probe found no primary screen.")
    _write_json(
        output_path,
        {
            "schema_version": 1,
            "frozen": bool(getattr(sys, "frozen", False)),
            "python": {"executable": str(Path(sys.executable).resolve())},
            "qt": {
                "compiled_qt_version": QtCore.QT_VERSION_STR,
                "runtime_qt_version": QtCore.qVersion(),
                "platform_plugin": app.platformName().lower(),
                "baseline_device_pixel_ratio": float(primary.devicePixelRatio()),
                "baseline_logical_dpi": float(primary.logicalDotsPerInch()),
            },
        },
    )
    app.quit()
    return 0


def start_package_surface_smoke(evidence_path: str, expected_scale: str) -> int:
    """Exercise resources and basic native Qt surfaces in the packaged app."""
    from PyQt6 import QtGui

    app = app_error_handler.get_or_create_application(sys.argv)
    _configure_application(app)
    qt6_resources.ensure_application_resources()
    platform_name = app.platformName().lower()
    if sys.platform == "win32" and platform_name != "windows":
        raise SystemExit("Package surface smoke did not load qwindows.")
    if sys.platform == "darwin" and platform_name != "cocoa":
        raise SystemExit("Package surface smoke did not load Cocoa.")
    clipboard_text = "RC MetaStudio clipboard – München – 1,25"
    app.clipboard().setText(clipboard_text)
    if app.clipboard().text() != clipboard_text:
        raise SystemExit("Package surface smoke clipboard round-trip failed.")
    if QtGui.QPixmap(":/misc/meta.png").isNull():
        raise SystemExit("Package surface smoke could not load binary resources.")
    primary = app.primaryScreen()
    if primary is None:
        raise SystemExit("Package surface smoke found no primary screen.")
    evidence_path_obj = Path(evidence_path)
    if evidence_path_obj.exists():
        evidence = json.loads(evidence_path_obj.read_text(encoding="utf-8"))
    else:
        evidence = {
            "schema_version": 1,
            "passed": True,
            "platform_plugin": platform_name,
            "workflows": {},
            "scales": [],
        }
    evidence.setdefault("scales", []).append(
        {
            "requested": expected_scale,
            "qt_scale_factor": os.environ.get("QT_SCALE_FACTOR"),
            "device_pixel_ratio": float(primary.devicePixelRatio()),
            "baseline_device_pixel_ratio": float(
                os.environ.get("RCMS_PACKAGE_BASELINE_DPR", primary.devicePixelRatio())
            ),
            "clipboard": True,
            "binary_resources": True,
            "platform_plugin": platform_name,
            "locale": "de_DE",
        }
    )
    _write_json(evidence_path, evidence)
    app.quit()
    return 0


def start_startup_wizard_smoke(evidence_path: str, sample_path: str) -> int:
    """Open a project through the startup-project boundary and record evidence."""
    app, window = start_automation()
    try:
        opened = bool(window.open(os.path.abspath(sample_path), raise_on_error=True))
        app.processEvents()
        frame = window.frameGeometry()
        handle = window.windowHandle()
        evidence = {
            "schema_version": 1,
            "platform_plugin": app.platformName().lower(),
            "project": Path(sample_path).name,
            "visible": window.isVisible(),
            "active": window.isActiveWindow(),
            "minimized": window.isMinimized(),
            "exposed": bool(handle and handle.isExposed()),
            "frame": [frame.x(), frame.y(), frame.width(), frame.height()],
            "rows": window.tableView.model().rowCount(),
        }
        evidence["passed"] = opened and evidence["visible"] and evidence["rows"] >= 1
        evidence["failures"] = [] if evidence["passed"] else ["startup project smoke failed"]
        _write_json(evidence_path, evidence)
        return 0 if evidence["passed"] else 1
    finally:
        _mark_workspace_saved(window)
        window.close()
        app.processEvents()
        app.quit()


def assert_native_window_smoke(app, window) -> None:
    expected = "windows" if sys.platform == "win32" else "cocoa"
    if app.platformName().lower() != expected:
        raise SystemExit(
            "Native smoke loaded Qt platform %s, expected %s."
            % (app.platformName().lower(), expected)
        )
    app.processEvents()
    handle = window.windowHandle()
    if not window.isVisible() or (handle is not None and not handle.isExposed()):
        raise SystemExit("Native smoke main window was not exposed.")


def assert_opened_project_for_startup_smoke(
    app, window, project_path, opened, *, completion_marker=None
) -> int:
    """Hidden packaged hook for the normal startup-project path."""
    if not opened or window.tableView.model().rowCount() < 1:
        raise SystemExit("startup project did not open: %s" % project_path)
    if completion_marker:
        with open(completion_marker, "w", encoding="utf-8") as marker:
            json.dump({"project": os.path.basename(project_path)}, marker)
    _mark_workspace_saved(window)
    window.close()
    app.processEvents()
    app.quit()
    return 0


def dispatch(startup_argv: list[str]) -> int:
    """Dispatch only the hidden packaged open/close qualification hook."""
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-shell-smoke":
        print("Application shell smoke passed with Qt platform offscreen.")
        return 0
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-shell-failure-smoke":
        stage = startup_argv[2] if len(startup_argv) > 2 else "unknown"
        print("Application shell failure teardown passed at %s." % stage)
        return 0
    if len(startup_argv) > 1 and startup_argv[1] in {
        "--automation-smoke",
        "--automation-native-smoke",
    }:
        sample = startup_argv[2] if len(startup_argv) > 2 else "sample_projects/amino.rcms"
        return start_automation_smoke(
            sample, require_native_window=startup_argv[1] == "--automation-native-smoke"
        )
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-package-runtime-probe":
        if len(startup_argv) != 3:
            raise SystemExit("--automation-package-runtime-probe requires an output path.")
        return _run_automation_smoke(lambda: start_package_runtime_probe(startup_argv[2]))
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-package-surface-smoke":
        if len(startup_argv) != 4:
            raise SystemExit("--automation-package-surface-smoke requires an evidence path and scale.")
        return _run_automation_smoke(
            lambda: start_package_surface_smoke(startup_argv[2], startup_argv[3])
        )
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-startup-wizard-smoke":
        if len(startup_argv) != 4:
            raise SystemExit(
                "--automation-startup-wizard-smoke requires an evidence path and project path."
            )
        return _run_automation_smoke(
            lambda: start_startup_wizard_smoke(startup_argv[2], startup_argv[3])
        )
    raise SystemExit("Unknown packaged qualification command: %s" % startup_argv[1])
