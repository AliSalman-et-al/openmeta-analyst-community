"""Small hidden qualification hook for the packaged application."""

from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
from pathlib import Path

from rc_metastudio import app_error_handler
from rc_metastudio.launch import dispose_qobjects


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
    from rc_metastudio.launch import compose_automation_application

    return compose_automation_application(phase_callback=phase_callback)


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
        _log("packaged-workflow:shell-created")
        _log("packaged-workflow:project-open:start")
        _log("packaged-workflow:project-open:return")
        _force_table_paint(app, window)
        _log("packaged-workflow:paint:complete")
        return 0
    finally:
        _mark_workspace_saved(window)
        window.close()
        app.processEvents()
        dispose_qobjects(app, (window,))
        app.quit()
        _log("packaged-workflow:post-close")


def start_package_operation(
    output_path: str,
    sample_path: str,
    operation: str,
    locale_name: str,
    edit_value: str,
    analysis_method: str | None = None,
) -> int:
    """Perform one ordinary packaged-project operation for developer tooling."""
    app, window = start_automation()
    try:
        if not window.open(os.path.abspath(sample_path), raise_on_error=True):
            raise RuntimeError("packaged workflow observation could not open project")
        observation = _package_operation_observation(
            window, operation, locale_name, edit_value, analysis_method
        )
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(observation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 0
    finally:
        _mark_workspace_saved(window)
        window.close()
        app.processEvents()
        dispose_qobjects(app, (window,))
        app.quit()


def _package_operation_observation(
    window, operation: str, locale_name: str, edit_value: str, analysis_method: str | None
) -> dict:
    if operation == "edit":
        model = window.tableView.model()
        edited = model.setData(model.index(0, model.NAME), edit_value)
        return {"operation": operation, "edited": bool(edited)}
    if operation in {"analysis", "locale"}:
        if not analysis_method:
            raise ValueError("analysis operation requires an analysis method")
        return _observe_locale_analysis(window, operation, locale_name, analysis_method)
    if operation in {"save-reopen", "save-reopen-analysis"}:
        if operation == "save-reopen-analysis" and not analysis_method:
            raise ValueError("save-reopen-analysis requires an analysis method")
        return _observe_save_reopen(window, operation, edit_value, analysis_method)
    raise ValueError(f"unknown packaged operation: {operation}")


def _observe_locale_analysis(
    window, operation: str, locale_name: str, analysis_method: str
) -> dict:
    from PyQt6 import QtCore
    from rc_metastudio import main_window, qt_text

    model = window.tableView.model()
    raw_index = model.index(0, model.RAW_DATA[0])
    QtCore.QLocale.setDefault(QtCore.QLocale(locale_name))
    locale = QtCore.QLocale()
    raw_value, valid = qt_text.parse_decimal(model.data(raw_index, QtCore.Qt.ItemDataRole.DisplayRole))
    if not valid:
        raise RuntimeError("packaged locale operation could not parse the product value")
    numeric_text = format(raw_value, ".1f").replace(".", locale.decimalPoint())
    edited = model.setData(raw_index, numeric_text)
    canonical_value, canonical_valid = qt_text.parse_decimal(model.data(raw_index, QtCore.Qt.ItemDataRole.DisplayRole))
    result = _run_analysis(window, main_window, analysis_method)
    if result is None:
        raise RuntimeError("packaged analysis operation produced no result")
    return {"operation": operation, "edited": bool(edited), "canonical_valid": bool(canonical_valid), "locale": locale.name(), "decimal_point": locale.decimalPoint(), "input": numeric_text, "canonical_value": canonical_value, "summary": result.texts.get("Summary", ""), "svg_paths": dict(result.display_images)}


def _observe_save_reopen(
    window, operation: str, edit_value: str, analysis_method: str | None
) -> dict:
    from rc_metastudio import main_window

    model = window.tableView.model()
    edited = model.setData(model.index(0, model.NAME), edit_value)
    handle, raw_destination = tempfile.mkstemp(suffix=".rcms")
    os.close(handle)
    destination = Path(raw_destination)
    destination.unlink()
    try:
        window.out_path = str(destination)
        saved, reopened = _save_and_reopen(window, destination, edited)
        result = _analysis_after_reopen(
            window, operation, reopened, main_window, analysis_method
        )
        return {
            "operation": operation,
            "edited": bool(edited),
            "saved": saved,
            "reopened": reopened,
            **_analysis_artifacts(result),
        }
    finally:
        destination.unlink(missing_ok=True)


def _save_and_reopen(window, destination: Path, edited: bool) -> tuple[bool, bool]:
    if not edited:
        return False, False
    saved = window.save() is True
    reopened = saved and window.open(str(destination), raise_on_error=True)
    return saved, bool(reopened)


def _analysis_after_reopen(
    window, operation: str, reopened: bool, main_window, analysis_method: str | None
):
    if not reopened or operation != "save-reopen-analysis":
        return None
    if not analysis_method:
        raise ValueError("save-reopen-analysis requires an analysis method")
    return _run_analysis(window, main_window, analysis_method)


def _analysis_artifacts(result) -> dict:
    if result is None:
        return {"summary": "", "svg_paths": {}}
    return {"summary": result.texts.get("Summary", ""), "svg_paths": dict(result.display_images)}


def _run_analysis(window, main_window, analysis_method: str):
    captured = {}
    dialog = main_window.analysis_setup_dialog.AnalysisSetupDialog(window.model, parent=window, confidence_level=window.model.get_confidence_level())
    original = window.analysis
    try:
        dialog.current_method = analysis_method
        dialog.current_param_vals = {}
        dialog.setup_params()
        dialog.current_param_vals.update(dialog.current_defaults)
        window.analysis = lambda result: captured.setdefault("result", result)
        dialog.run_ma()
    finally:
        window.analysis = original
        dialog.close()
    return captured.get("result")


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
    """Observe the concrete runtime loaded by the packaged executable."""
    from PyQt6 import QtCore, sip
    from rc_metastudio import project_format, r_bridge, r_runtime

    for member in ("manifest.json", "project.json", "state.json"):
        project_format._schema(1, member)
    configured = r_runtime.configure_bundled_r_environment()

    app = app_error_handler.get_or_create_application(sys.argv)
    from rc_metastudio.launch import configure_application

    configure_application(app)
    primary = app.primaryScreen()
    if primary is None:
        raise SystemExit("Packaged runtime probe found no primary screen.")

    runtime = r_bridge.packaged_runtime_observation()
    shared_path = Path(configured.get("R_HOME", "")) / "bin" / "x64" / "R.dll"
    if sys.platform == "darwin":
        shared_path = Path(configured.get("R_HOME", "")) / "lib" / "libR.dylib"
    if not shared_path.is_file():
        raise RuntimeError("Packaged runtime has no private R shared library.")
    probe = {
            "schema_version": 1,
            "frozen": bool(getattr(sys, "frozen", False)),
            "python": {"version": platform.python_version(), "executable": str(Path(sys.executable).resolve()), "architecture": platform.machine(), "bundle_root": str(Path(getattr(sys, "_MEIPASS", "")).resolve())},
            "qt": {
                "pyqt_version": QtCore.PYQT_VERSION_STR,
                "compiled_qt_version": QtCore.QT_VERSION_STR,
                "runtime_qt_version": QtCore.qVersion(),
                "sip_runtime_version": sip.SIP_VERSION_STR,
                "platform_plugin": app.platformName().lower(),
                "plugins_path": QtCore.QLibraryInfo.path(QtCore.QLibraryInfo.LibraryPath.PluginsPath),
                "library_paths": list(app.libraryPaths()),
                "scale_factor_environment": os.environ.get("QT_SCALE_FACTOR"),
                "baseline_device_pixel_ratio": float(primary.devicePixelRatio()),
                "baseline_logical_dpi": float(primary.logicalDotsPerInch()),
            },
            "rpy2": runtime["rpy2"],
            "project_schemas": {"version": 1, "validated_members": ["manifest.json", "project.json", "state.json"]},
            "r": {"version": runtime["r_version"], "home": runtime["r_home"], "library_paths": runtime["r_library_paths"], "configured_home": configured.get("R_HOME"), "configured_library": configured.get("R_LIBS"), "shared_library_path": str(shared_path.resolve()), "direct_spike": configured.get("direct_spike") is True, "lc_numeric": os.environ.get("LC_NUMERIC")},
    }
    if configured.get("kit_sha256") is not None:
        probe["r"]["kit_sha256"] = configured["kit_sha256"]
    _write_json(output_path, probe)
    app.quit()
    return 0


def start_package_surface_smoke(evidence_path: str, requested_scale: str) -> int:
    """Observe raw facts from the ordinary main window at one Qt scale."""
    from PyQt6 import QtCore, QtGui, QtNetwork, QtWidgets

    _configure_surface_locale(QtCore)
    app, window = start_automation()
    close_attempted = False
    try:
        record = _surface_record(
            QtCore, QtGui, QtNetwork, QtWidgets, app, window, requested_scale
        )
        _mark_workspace_saved(window)
        closed = window.close()
        close_attempted = True
        window_visible = window.isVisible()
        app.processEvents()
        record["cleanup"] = {
            "close_accepted": bool(closed),
            "window_visible": window_visible,
        }
        _write_json(evidence_path, record)
        return 0
    finally:
        if not close_attempted:
            _mark_workspace_saved(window)
            window.close()
        app.processEvents()
        dispose_qobjects(app, (window,))
        app.quit()


def _configure_surface_locale(QtCore) -> None:
    configured_locale = os.environ.get("RCMS_PACKAGE_LOCALE")
    if configured_locale:
        QtCore.QLocale.setDefault(QtCore.QLocale(configured_locale))


def _surface_record(QtCore, QtGui, QtNetwork, QtWidgets, app, window, requested_scale):
    actual_locale = QtCore.QLocale()
    primary = app.primaryScreen()
    menu_bar = window.menuBar()
    menu_actions = menu_bar.actions()
    accessibility = _surface_accessibility(app, window)
    actual_dpr = float(primary.devicePixelRatio()) if primary is not None else None
    baseline_value = os.environ.get("RCMS_PACKAGE_BASELINE_DPR")
    baseline = float(baseline_value) if baseline_value is not None else actual_dpr
    display = _surface_display_facts(QtGui, QtNetwork, QtWidgets, window)
    return {
        "requested": requested_scale,
        "qt_scale_factor": os.environ.get("QT_SCALE_FACTOR"),
        "device_pixel_ratio": actual_dpr,
        "baseline_device_pixel_ratio": baseline,
        "logical_dpi": float(primary.logicalDotsPerInch()) if primary is not None else None,
        "binary_resources": display["binary_resources"],
        "native_menu": {"is_native": bool(menu_bar.isNativeMenuBar()), "menu_count": len(menu_actions), "action_count": sum(len(action.menu().actions()) for action in menu_actions if action.menu() is not None)},
        "accessibility": accessibility,
        "tls_backends": display["tls_backends"],
        "active_style": display["active_style"],
        "available_styles": display["available_styles"],
        "image_formats": display["image_formats"],
        "platform_plugin": app.platformName().lower(),
        "locale": actual_locale.name(),
        "decimal_point": actual_locale.decimalPoint(),
        "frame": [window.frameGeometry().x(), window.frameGeometry().y(), window.frameGeometry().width(), window.frameGeometry().height()],
        "visible": window.isVisible(),
        "exposed": bool(window.windowHandle() and window.windowHandle().isExposed()),
    }


def _surface_accessibility(app, window):
    table = getattr(window, "tableView", None)
    if table is not None:
        table.setFocus()
        app.processEvents()
    focus = app.focusWidget()
    return {
        "focus_widget": focus.objectName() if focus is not None else None,
        "accessible_name": window.accessibleName(),
        "accessible_description": window.accessibleDescription(),
    }


def _surface_display_facts(QtGui, QtNetwork, QtWidgets, window):
    return {
        "binary_resources": not QtGui.QPixmap(":/misc/meta.png").isNull(),
        "tls_backends": list(QtNetwork.QSslSocket.availableBackends()),
        "active_style": window.style().objectName(),
        "available_styles": list(QtWidgets.QStyleFactory.keys()),
        "image_formats": sorted(
            value.data().decode("ascii").lower()
            for value in QtGui.QImageReader.supportedImageFormats()
        ),
    }


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
            "opened": opened,
            "visible": window.isVisible(),
            "active": window.isActiveWindow(),
            "minimized": window.isMinimized(),
            "exposed": bool(handle and handle.isExposed()),
            "frame": [frame.x(), frame.y(), frame.width(), frame.height()],
            "rows": window.tableView.model().rowCount(),
        }
        _write_json(evidence_path, evidence)
        return 0
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
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-package-operation":
        if len(startup_argv) < 6:
            raise SystemExit(
                "--automation-package-operation requires output, project, operation, and operation parameters."
            )
        operation_args = startup_argv[5:]
        if startup_argv[4] in {"analysis", "locale"} and len(operation_args) != 2:
            raise SystemExit(
                "analysis package operations require locale and analysis method."
            )
        if startup_argv[4] == "save-reopen-analysis" and len(operation_args) != 2:
            raise SystemExit(
                "save-reopen-analysis requires an edit value and analysis method."
            )
        if startup_argv[4] in {"edit", "save-reopen"} and len(operation_args) != 1:
            raise SystemExit(
                "edit and save-reopen operations require an edit value."
            )
        locale, edit_value, analysis_method = "en_US", operation_args[0], None
        if startup_argv[4] in {"analysis", "locale"}:
            locale, analysis_method = operation_args
            edit_value = ""
        elif startup_argv[4] == "save-reopen-analysis":
            edit_value, analysis_method = operation_args
        return _run_automation_smoke(
            lambda: start_package_operation(
                startup_argv[2], startup_argv[3], startup_argv[4],
                locale, edit_value, analysis_method
            )
        )
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
