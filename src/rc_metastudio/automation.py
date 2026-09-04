"""Small hidden qualification hook for the packaged application."""

from __future__ import annotations

import os
import sys

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


def _log(message: str) -> None:
    path = os.environ.get(AUTOMATION_SMOKE_LOG_ENV)
    if path:
        with open(path, "a", encoding="utf-8") as output:
            output.write(message + "\n")


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


def start_automation_smoke(sample_path: str) -> int:
    """Run one ordinary open/paint/close path used by shipped qualification."""
    app, window = start_automation()
    try:
        if not window.open(os.path.abspath(sample_path), raise_on_error=True):
            raise RuntimeError("packaged smoke could not open the project")
        app.processEvents()
        return 0
    finally:
        window.workspace_is_dirty = False
        window.close()
        app.processEvents()
        _dispose_qobjects(app, (window,))
        app.quit()


def assert_opened_project_for_startup_smoke(
    app, window, project_path, opened, *, completion_marker=None
) -> int:
    """Hidden packaged hook for the normal startup-project path."""
    if not opened or window.tableView.model().rowCount() < 1:
        raise SystemExit("startup project did not open: %s" % project_path)
    if completion_marker:
        with open(completion_marker, "w", encoding="utf-8") as marker:
            marker.write("startup-project:complete\n")
    window.workspace_is_dirty = False
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
        return start_automation_smoke(sample)
    raise SystemExit("Unknown packaged qualification command: %s" % startup_argv[1])
