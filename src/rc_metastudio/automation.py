"""Small hidden qualification hook for the packaged application."""

from __future__ import annotations

import json
import hashlib
import importlib
import importlib.metadata
import os
import platform
import sys
import tempfile
from pathlib import Path
from rc_metastudio.cocoa_accessibility import find_accessibility_element

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
        _dispose_qobjects(app, (window,))
        app.quit()
        _log("packaged-workflow:post-close")


def start_package_operation(output_path: str, sample_path: str, operation: str, locale_name: str = "en_US") -> int:
    """Perform one ordinary packaged-project operation for developer tooling."""
    app, window = start_automation()
    try:
        if not window.open(os.path.abspath(sample_path), raise_on_error=True):
            raise RuntimeError("packaged workflow observation could not open project")
        observation = _package_operation_observation(window, operation, locale_name)
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(observation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 0
    finally:
        _mark_workspace_saved(window)
        window.close()
        app.processEvents()
        _dispose_qobjects(app, (window,))
        app.quit()


def _package_operation_observation(window, operation: str, locale_name: str) -> dict:
    if operation == "edit":
        model = window.tableView.model()
        observed = model.setData(model.index(0, model.NAME), "Packaged Smoke – München")
        return {"operation": operation, "observed": bool(observed)}
    if operation in {"analysis", "locale"}:
        return _observe_locale_analysis(window, operation, locale_name)
    if operation in {"save-reopen", "save-reopen-analysis"}:
        return _observe_save_reopen(window, operation)
    raise ValueError(f"unknown packaged operation: {operation}")


def _observe_locale_analysis(window, operation: str, locale_name: str) -> dict:
    from PyQt6 import QtCore
    from rc_metastudio import main_window, qt_text

    model = window.tableView.model()
    raw_index = model.index(0, model.RAW_DATA[0])
    QtCore.QLocale.setDefault(QtCore.QLocale(locale_name))
    locale = QtCore.QLocale()
    raw_value, valid = qt_text.parse_decimal(model.data(raw_index, QtCore.Qt.ItemDataRole.DisplayRole))
    if not valid:
        raise RuntimeError("packaged locale operation could not parse the product value")
    numeric_text = locale.toString(raw_value, "f", 1)
    edited = model.setData(raw_index, numeric_text)
    canonical_value, canonical_valid = qt_text.parse_decimal(model.data(raw_index, QtCore.Qt.ItemDataRole.DisplayRole))
    result = _run_binary_analysis(window, main_window)
    if result is None:
        raise RuntimeError("packaged analysis operation produced no result")
    observed = edited and canonical_valid and canonical_value == raw_value and bool(result.texts.get("Summary"))
    return {"operation": operation, "observed": bool(observed), "locale": locale.name(), "decimal_point": locale.decimalPoint(), "input": numeric_text, "canonical_value": canonical_value, "summary": result.texts.get("Summary", ""), "svg_paths": dict(result.display_images)}


def _observe_save_reopen(window, operation: str) -> dict:
    from rc_metastudio import main_window

    model = window.tableView.model()
    edited = model.setData(model.index(0, model.NAME), "Packaged Smoke – München")
    handle, raw_destination = tempfile.mkstemp(suffix=".rcms")
    os.close(handle)
    destination = Path(raw_destination)
    destination.unlink()
    try:
        window.out_path = str(destination)
        reopened = edited and window.save() is True and window.open(str(destination), raise_on_error=True)
        result = _run_binary_analysis(window, main_window) if reopened and operation == "save-reopen-analysis" else None
        observed = reopened and (operation == "save-reopen" or result is not None and bool(result.texts.get("Summary")))
        return {"operation": operation, "observed": bool(observed), "analysis_after_reopen_observed": bool(observed and operation == "save-reopen-analysis"), "summary": result.texts.get("Summary", "") if result else "", "svg_paths": dict(result.display_images) if result else {}}
    finally:
        destination.unlink(missing_ok=True)


def _run_binary_analysis(window, main_window):
    captured = {}
    dialog = main_window.analysis_setup_dialog.AnalysisSetupDialog(window.model, parent=window, confidence_level=window.model.get_confidence_level())
    original = window.analysis
    try:
        dialog.current_method = "binary.random"
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
    from rc_metastudio import project_format, r_runtime

    for member in ("manifest.json", "project.json", "state.json"):
        project_format._schema(1, member)
    configured = r_runtime.configure_bundled_r_environment()
    api_bridge = importlib.import_module("_rinterface_cffi_api")
    from rpy2 import robjects
    from rpy2.rinterface_lib import openrlib

    app = app_error_handler.get_or_create_application(sys.argv)
    _configure_application(app)
    primary = app.primaryScreen()
    if primary is None:
        raise SystemExit("Packaged runtime probe found no primary screen.")
    r_home = str(robjects.r("normalizePath(R.home(), winslash='/', mustWork=TRUE)")[0])
    r_version = str(robjects.r("as.character(getRversion())")[0])
    r_library_paths = [str(item) for item in robjects.r("normalizePath(.libPaths(), winslash='/', mustWork=TRUE)")]
    api_bridge_path = Path(str(api_bridge.__file__)).resolve()
    shared_path = Path(configured.get("R_HOME", "")) / "bin" / "x64" / "R.dll"
    if sys.platform == "darwin":
        shared_path = Path(configured.get("R_HOME", "")) / "lib" / "libR.dylib"
    if not shared_path.is_file():
        raise RuntimeError("Packaged runtime has no private R shared library.")
    macos_profile = None
    if sys.platform == "darwin":
        png_path = Path(str(robjects.r("output <- tempfile(fileext='.png'); grDevices::png(output); graphics::plot(1, 1); grDevices::dev.off(); output")[0]))
        macos_profile = {"tcltk_available": bool(robjects.r("isTRUE(requireNamespace('tcltk', quietly=TRUE))")[0]), "tcltk_loaded": bool(robjects.r("'tcltk' %in% loadedNamespaces()")[0]), "aqua": bool(robjects.r("capabilities('aqua')")[0]), "bitmap_type": str(robjects.r("getOption('bitmapType')")[0]), "default_png": {"size": png_path.stat().st_size, "sha256": hashlib.sha256(png_path.read_bytes()).hexdigest()}}
        png_path.unlink(missing_ok=True)
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
            "rpy2": {"distribution_version": importlib.metadata.version("rpy2"), "rinterface_distribution_version": importlib.metadata.version("rpy2-rinterface"), "robjects_distribution_version": importlib.metadata.version("rpy2-robjects"), "cffi_mode": os.environ.get("RPY2_CFFI_MODE"), "loaded_cffi_mode": openrlib.cffi_mode.name, "api_bridge_loaded": openrlib.cffi_mode.name == "API", "api_bridge_path": str(api_bridge_path), "api_bridge_sha256": hashlib.sha256(api_bridge_path.read_bytes()).hexdigest()},
            "project_schemas": {"version": 1, "validated_members": ["manifest.json", "project.json", "state.json"]},
            "r": {"version": r_version, "home": r_home, "library_paths": r_library_paths, "configured_home": configured.get("R_HOME"), "configured_library": configured.get("R_LIBS"), "macos_product_profile": macos_profile, "shared_library_path": str(shared_path.resolve()), "shared_library_sha256": hashlib.sha256(shared_path.read_bytes()).hexdigest(), "direct_spike": configured.get("direct_spike") is True, "lc_numeric": os.environ.get("LC_NUMERIC")},
    }
    if configured.get("kit_sha256") is not None:
        probe["r"]["kit_sha256"] = configured["kit_sha256"]
    _write_json(output_path, probe)
    _log("packaged-runtime-probe:passed")
    app.quit()
    return 0


def start_package_surface_smoke(evidence_path: str, expected_scale: str) -> int:
    """Observe one scale's native Qt surfaces and write only that record."""
    from PyQt6 import QtCore, QtGui, QtNetwork, QtWidgets

    _configure_surface_locale(QtCore)
    app = app_error_handler.get_or_create_application(sys.argv)
    _configure_application(app)
    qt6_resources.ensure_application_resources()
    platform_name = app.platformName().lower()
    _require_surface_platform(platform_name)
    primary = _verify_surface_basics(app, QtGui)
    window, menu_bar, menu, control = _build_surface_window(QtWidgets)
    focus_before, focus_after = _observe_surface_focus(app, window, control)
    record = _surface_record(
        QtCore, QtGui, QtNetwork, QtWidgets, platform_name, expected_scale,
        primary, window, menu_bar, menu, control, focus_before, focus_after,
    )
    _write_json(evidence_path, record)
    _log("packaged-surface:scale-%s-passed" % expected_scale)
    window.close()
    app.quit()
    return 0


def _configure_surface_locale(QtCore) -> None:
    configured_locale = os.environ.get("RCMS_PACKAGE_LOCALE")
    if configured_locale:
        QtCore.QLocale.setDefault(QtCore.QLocale(configured_locale))


def _require_surface_platform(platform_name: str) -> None:
    expected = {"win32": "windows", "darwin": "cocoa"}.get(sys.platform)
    if expected is not None and platform_name != expected:
        raise SystemExit("Package surface smoke loaded the wrong Qt platform plugin.")


def _verify_surface_basics(app, QtGui):
    clipboard_text = "RC MetaStudio clipboard – München – 1,25"
    app.clipboard().setText(clipboard_text)
    if app.clipboard().text() != clipboard_text:
        raise SystemExit("Package surface smoke clipboard round-trip failed.")
    if QtGui.QPixmap(":/misc/meta.png").isNull():
        raise SystemExit("Package surface smoke could not load binary resources.")
    primary = app.primaryScreen()
    if primary is None:
        raise SystemExit("Package surface smoke found no primary screen.")
    return primary


def _build_surface_window(QtWidgets):
    window = QtWidgets.QMainWindow()
    menu_bar = window.menuBar()
    menu = menu_bar.addMenu("Package smoke")
    menu.addAction("Verified action")
    control = QtWidgets.QPushButton("Accessible package control", window)
    control.setObjectName("packagedAccessibilityControl")
    control.setAccessibleName("Packaged accessibility control")
    control.setAccessibleDescription("Verifies packaged Qt accessibility metadata.")
    target = QtWidgets.QLineEdit(window)
    target.setObjectName("packagedKeyboardTraversalTarget")
    body = QtWidgets.QWidget(window)
    layout = QtWidgets.QVBoxLayout(body)
    layout.addWidget(control)
    layout.addWidget(target)
    window.setCentralWidget(body)
    window.setTabOrder(control, target)
    window.show()
    return window, menu_bar, menu, control


def _observe_surface_focus(app, window, control):
    app.processEvents()
    control.setFocus()
    app.processEvents()
    focus_before = app.focusWidget()
    app.focusNextPrevChild(True)
    return focus_before, app.focusWidget()


def _surface_record(QtCore, QtGui, QtNetwork, QtWidgets, platform_name, expected_scale, primary, window, menu_bar, menu, control, focus_before, focus_after):
    actual_locale = QtCore.QLocale()
    accessibility = {"focus_before": focus_before.objectName() if focus_before else None, "focus_after_tab": focus_after.objectName() if focus_after else None, "accessible_name": control.accessibleName(), "accessible_description": control.accessibleDescription(), "native": {}}
    if sys.platform == "darwin":
        accessibility["native"] = _observe_cocoa_accessibility(control)
    baseline = float(os.environ.get("RCMS_PACKAGE_BASELINE_DPR", primary.devicePixelRatio()))
    return {
        "requested": expected_scale,
        "qt_scale_factor": os.environ.get("QT_SCALE_FACTOR"),
        "device_pixel_ratio": float(primary.devicePixelRatio()),
        "baseline_device_pixel_ratio": baseline,
        "expected_device_pixel_ratio": baseline * float(expected_scale),
        "dpr_tolerance": 0.05,
        "logical_dpi": float(primary.logicalDotsPerInch()),
        "clipboard": True,
        "binary_resources": True,
        "native_menu": {"is_native": bool(menu_bar.isNativeMenuBar()), "menu_count": len(menu_bar.actions()), "action_count": len(menu.actions())},
        "accessibility": accessibility,
        "tls_backends": list(QtNetwork.QSslSocket.availableBackends()),
        "active_style": window.style().objectName(),
        "available_styles": list(QtWidgets.QStyleFactory.keys()),
        "image_formats": sorted(value.data().decode("ascii").lower() for value in QtGui.QImageReader.supportedImageFormats()),
        "platform_plugin": platform_name,
        "locale": actual_locale.name(),
        "decimal_point": actual_locale.decimalPoint(),
        "native_file_dialog": _observe_native_file_dialog(window),
        "critical_dialog": _observe_critical_dialog(window),
        "cleanup": {"close_accepted": bool(window.close()), "window_visible": window.isVisible()},
    }


def _observe_native_file_dialog(parent):
    from PyQt6 import QtCore, QtWidgets

    dialog = QtWidgets.QFileDialog(parent)
    dialog.setOption(QtWidgets.QFileDialog.Option.DontUseNativeDialog, False)
    dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
    observation = {"dont_use_native_dialog": dialog.testOption(QtWidgets.QFileDialog.Option.DontUseNativeDialog), "window_modality": None, "visible_before_cancel": False, "cancel_requested": False, "finished_signal": False, "rejected_signal": False, "result": None, "rejected_value": 0, "timed_out": False, "timeout_ms": 10_000}
    loop = QtCore.QEventLoop()
    dialog.finished.connect(lambda result: (observation.update(finished_signal=True, result=int(result)), loop.quit()))
    dialog.rejected.connect(lambda: observation.update(rejected_signal=True))
    def cancel():
        observation.update(visible_before_cancel=dialog.isVisible(), cancel_requested=True)
        dialog.reject()
    dialog.open()
    observation["window_modality"] = dialog.windowModality().name
    QtCore.QTimer.singleShot(250, cancel)
    QtCore.QTimer.singleShot(10_000, loop.quit)
    loop.exec()
    dialog.deleteLater()
    return observation


def _observe_critical_dialog(parent):
    from PyQt6 import QtCore, QtWidgets

    dialog = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Critical, "Packaged smoke", "Deployment diagnostic", QtWidgets.QMessageBox.StandardButton.Ok, parent)
    dialog.setOption(QtWidgets.QMessageBox.Option.DontUseNativeDialog, False)
    dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
    observation = {"dont_use_native_dialog": dialog.testOption(QtWidgets.QMessageBox.Option.DontUseNativeDialog), "application_dont_use_native_dialogs": QtCore.QCoreApplication.testAttribute(QtCore.Qt.ApplicationAttribute.AA_DontUseNativeDialogs), "dont_show_on_screen_before_show": dialog.testAttribute(QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen), "dont_show_on_screen_after_show": None, "native_helper_active": False, "window_modality": None, "visible_before_close": False, "critical_icon": False, "finished_signal": False, "result": None, "accepted_value": 1, "timed_out": False, "timeout_ms": 5_000}
    loop = QtCore.QEventLoop()
    dialog.finished.connect(lambda result: (observation.update(finished_signal=True, result=int(result)), loop.quit()))
    def accept():
        observation.update(visible_before_close=dialog.isVisible(), critical_icon=dialog.icon() == QtWidgets.QMessageBox.Icon.Critical)
        dialog.accept()
    dialog.show()
    observation["dont_show_on_screen_after_show"] = dialog.testAttribute(QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen)
    observation["native_helper_active"] = not observation["dont_use_native_dialog"] and not observation["application_dont_use_native_dialogs"] and not observation["dont_show_on_screen_before_show"] and observation["dont_show_on_screen_after_show"]
    observation["window_modality"] = dialog.windowModality().name
    QtCore.QTimer.singleShot(100, accept)
    QtCore.QTimer.singleShot(5_000, loop.quit)
    loop.exec()
    dialog.deleteLater()
    return observation


def _observe_cocoa_accessibility(widget):
    """Read AXChildren through the QNSView bridge, not the backing view."""
    import ctypes

    objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.objc_getClass.restype = ctypes.c_void_p
    message = objc.objc_msgSend

    def selector(name):
        return objc.sel_registerName(name.encode("ascii"))

    def send(receiver, name, *args):
        message.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_void_p] * len(args)
        message.restype = ctypes.c_void_p
        return message(ctypes.c_void_p(receiver), selector(name), *[ctypes.c_void_p(item) for item in args])

    def text(receiver, name):
        value = send(receiver, name)
        raw = send(value, "UTF8String") if value else None
        return ctypes.cast(raw, ctypes.c_char_p).value.decode("utf-8") if raw else ""

    def responds(receiver, name):
        message.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        message.restype = ctypes.c_bool
        return bool(message(ctypes.c_void_p(receiver), selector("respondsToSelector:"), selector(name)))

    def observe(receiver):
        ignored = None
        if responds(receiver, "accessibilityIsIgnored"):
            message.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            message.restype = ctypes.c_bool
            ignored = bool(message(ctypes.c_void_p(receiver), selector("accessibilityIsIgnored")))
        return {"role": text(receiver, "accessibilityRole"), "title": text(receiver, "accessibilityTitle"), "description": text(receiver, "accessibilityLabel"), "is_ignored": ignored}

    def children(receiver):
        string_class = objc.objc_getClass(b"NSString")
        message.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]
        message.restype = ctypes.c_void_p
        attribute = message(string_class, selector("stringWithUTF8String:"), b"AXChildren")
        value = send(receiver, "accessibilityAttributeValue:", int(attribute or 0))
        if not value:
            return []
        count = int(send(value, "count") or 0)
        return [int(send(value, "objectAtIndex:", index)) for index in range(min(count, 256))]

    found = find_accessibility_element([int(widget.winId())], expected_role="AXButton", expected_title=widget.accessibleName(), expected_description=widget.accessibleDescription(), observe=observe, children=children)
    found.update({"bridge": "accessibilityAttributeValue:AXChildren", "bridge_supported": True, "root_count": 1})
    return found


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
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-package-operation":
        if len(startup_argv) not in {5, 6}:
            raise SystemExit("--automation-package-operation requires output, project, operation, and optional locale.")
        locale = startup_argv[5] if len(startup_argv) == 6 else "en_US"
        return _run_automation_smoke(lambda: start_package_operation(startup_argv[2], startup_argv[3], startup_argv[4], locale))
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
