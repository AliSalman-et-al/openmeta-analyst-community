"""Small hidden qualification hook for the packaged application."""

from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path

from rc_metastudio import app_error_handler
from rc_metastudio.launch import dispose_qobjects


def _mark_workspace_saved(window) -> None:
    workspace = getattr(window, "workspace", None)
    if workspace is not None and workspace.document is not None:
        workspace.mark_saved()


def start_automation(phase_callback=None):
    """Construct the ordinary application composition for tests and packaging."""
    from rc_metastudio.launch import compose_application

    return compose_application(phase_callback=phase_callback)


def _close_automation_window(app, window) -> None:
    _mark_workspace_saved(window)
    window.close()
    app.processEvents()
    dispose_qobjects(app, (window,))
    app.quit()


def start_package_open_report(output_path: str, project_path: str) -> int:
    """Open one explicit project and report only resulting window facts."""
    app, window = start_automation()
    try:
        opened = window.open(os.path.abspath(project_path), raise_on_error=True)
        app.processEvents()
        model = window.tableView.model()
        _write_json(output_path, {
            "project": os.path.abspath(project_path), "opened": bool(opened),
            "rows": model.rowCount(), "visible": window.isVisible(),
            "exposed": bool(window.windowHandle() and window.windowHandle().isExposed()),
            "platform_plugin": app.platformName().lower(),
        })
        return 0
    finally:
        _close_automation_window(app, window)


def _model_column(model, column: str) -> int:
    if column == "name":
        return model.NAME
    if column.startswith("raw-data-"):
        return model.RAW_DATA[int(column.removeprefix("raw-data-"))]
    raise ValueError("edit column must be name or raw-data-N")


def start_package_edit_save(
    output_path: str, project_path: str, destination_path: str, column: str, value: str
) -> int:
    """Edit one explicit cell and save to one explicit destination."""
    _configure_package_locale()
    app, window = start_automation()
    try:
        opened = bool(window.open(os.path.abspath(project_path), raise_on_error=True))
        edited = saved = False
        destination = Path(destination_path)
        display_value = ""
        if opened:
            model = window.tableView.model()
            index = model.index(0, _model_column(model, column))
            edited = bool(model.setData(index, value))
            destination.parent.mkdir(parents=True, exist_ok=True)
            window.out_path = str(destination)
            saved = bool(edited and window.save() is True)
            display_value = str(model.data(index))
        _write_json(output_path, {
            "project": os.path.abspath(project_path), "destination": str(destination),
            "column": column, "value": value,
            "opened": opened, "display_value": display_value,
            "edited": edited, "saved": saved,
        })
        return 0
    finally:
        _close_automation_window(app, window)


def start_package_analyze(output_path: str, project_path: str, analysis_method: str) -> int:
    """Open one explicit project and run one explicit analysis method."""
    _configure_package_locale()
    app, window = start_automation()
    try:
        opened = bool(window.open(os.path.abspath(project_path), raise_on_error=True))
        if not opened:
            _write_json(output_path, {
                "project": os.path.abspath(project_path),
                "analysis_method": analysis_method,
                "opened": False,
                "texts": {},
                "display_images": {},
            })
            return 0
        from rc_metastudio import main_window

        result = _run_analysis(window, main_window, analysis_method)
        if result is None:
            raise RuntimeError("analysis produced no result")
        _write_json(output_path, {
            "project": os.path.abspath(project_path), "analysis_method": analysis_method,
            "opened": True,
            "texts": dict(result.texts), "display_images": dict(result.display_images),
        })
        return 0
    finally:
        _close_automation_window(app, window)


def _configure_package_locale() -> None:
    from PyQt6 import QtCore

    configured_locale = os.environ.get("RCMS_PACKAGE_LOCALE")
    if configured_locale:
        QtCore.QLocale.setDefault(QtCore.QLocale(configured_locale))


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


def _write_json(path: str, value: dict) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def start_package_runtime_probe(output_path: str) -> int:
    """Observe the concrete runtime loaded by the packaged executable."""
    from PyQt6 import QtCore, sip

    from rc_metastudio import project_format, r_runtime

    for member in ("manifest.json", "project.json", "state.json"):
        project_format._schema(1, member)
    configured = r_runtime.configure_bundled_r_environment()
    from rc_metastudio import r_bridge

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


def dispatch(startup_argv: list[str]) -> int:
    """Dispatch only narrow, raw qualification observations."""
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-package-runtime-probe":
        if len(startup_argv) != 3:
            raise SystemExit("--automation-package-runtime-probe requires an output path.")
        return start_package_runtime_probe(startup_argv[2])
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-package-open-report":
        if len(startup_argv) != 4:
            raise SystemExit("--automation-package-open-report requires an output and project path.")
        return start_package_open_report(startup_argv[2], startup_argv[3])
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-package-edit-save":
        if len(startup_argv) != 7:
            raise SystemExit("--automation-package-edit-save requires output, project, destination, column, and value.")
        return start_package_edit_save(*startup_argv[2:])
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-package-analyze":
        if len(startup_argv) != 5:
            raise SystemExit("--automation-package-analyze requires output, project, and method.")
        return start_package_analyze(*startup_argv[2:])
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-package-surface-smoke":
        if len(startup_argv) != 4:
            raise SystemExit("--automation-package-surface-smoke requires an evidence path and scale.")
        return start_package_surface_smoke(startup_argv[2], startup_argv[3])
    raise SystemExit("Unknown packaged qualification command: %s" % startup_argv[1])
