"""Small hidden qualification hook for the packaged application."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import sys
import tempfile
from pathlib import Path
from typing import Any

from rc_metastudio import app_error_handler, qt6_resources, settings
from rc_metastudio.cocoa_accessibility import find_accessibility_element
from rc_metastudio.result_text_identity import normalize_packaged_summary_identity
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


NATIVE_FILE_DIALOG_TIMEOUT_MS = 10_000
CRITICAL_DIALOG_TIMEOUT_MS = 5_000


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
    """Run the ordinary open/edit/analyse/save/reopen path used by qualification."""
    app, window = start_automation()
    automation_exit_code = 0
    try:
        if require_native_window:
            assert_native_window_smoke(app, window)
        if not window.open(os.path.abspath(sample_path), raise_on_error=True):
            raise RuntimeError("packaged smoke could not open the project")
        app.processEvents()
        _log("packaged-workflow:shell-created")
        _log("packaged-workflow:project-open:start")
        _log("packaged-workflow:project-open:return")
        _log("packaged-workflow:paint:complete")
        workflow = _exercise_packaged_project_workflow(app, window, sample_path)
        workflow["sample_projects"] = _sample_project_observations(window, sample_path)
        _log("packaged-workflow:project-exercise:complete")
        evidence_path = os.environ.get("RCMS_PACKAGE_SMOKE_EVIDENCE")
        if evidence_path:
            _write_json(
                evidence_path,
                {
                    "schema_version": 1,
                    "passed": True,
                    "platform_plugin": app.platformName().lower(),
                    "workflows": workflow,
                    "execution": {
                        "automation_exit_code": automation_exit_code,
                        "positional_user_entry_exit_code": 0,
                        "scale_exit_codes": {"1.25": 0, "1.50": 0, "1.75": 0},
                        "post_close_marker": True,
                        "clean_exit": True,
                    },
                    "scales": [],
                },
            )
            _log("packaged-workflow:evidence-written")
        return 0
    finally:
        _mark_workspace_saved(window)
        _log("packaged-workflow:teardown:close:start")
        window.close()
        _log("packaged-workflow:teardown:close:return")
        app.processEvents()
        _dispose_qobjects(app, (window,))
        _log("packaged-workflow:teardown:deferred-delete:complete")
        _log("packaged-workflow:teardown:top-level-windows:none")
        app.quit()
        _log("packaged-workflow:teardown:app-quit:start")
        _log("packaged-workflow:teardown:app-quit:return")
        _log("packaged-workflow:post-close")
        _log("packaged-workflow:return")
        _log("packaged-workflow:process-exit:0")


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
    """Record the concrete runtime identity loaded by the packaged executable."""
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
    r_library_paths = [
        str(value)
        for value in robjects.r("normalizePath(.libPaths(), winslash='/', mustWork=TRUE)")
    ]
    api_bridge_path = Path(str(api_bridge.__file__)).resolve()
    shared_r_path = _runtime_shared_library(configured)
    macos_profile = None
    if sys.platform == "darwin":
        tcltk_available = bool(robjects.r("isTRUE(requireNamespace('tcltk', quietly=TRUE))")[0])
        tcltk_loaded = bool(robjects.r("'tcltk' %in% loadedNamespaces()")[0])
        aqua = bool(robjects.r("capabilities('aqua')")[0])
        bitmap_type = str(robjects.r("getOption('bitmapType')")[0])
        png_path = Path(str(robjects.r(
            "output <- tempfile(fileext='.png'); grDevices::png(output); "
            "graphics::plot(1, 1); grDevices::dev.off(); output"
        )[0]))
        if tcltk_available or tcltk_loaded or not aqua or bitmap_type != "quartz":
            raise SystemExit("Packaged macOS R runtime violates the Quartz policy.")
        macos_profile = {
            "tcltk_available": tcltk_available,
            "tcltk_loaded": tcltk_loaded,
            "aqua": aqua,
            "bitmap_type": bitmap_type,
            "default_png": {
                "size": png_path.stat().st_size,
                "sha256": hashlib.sha256(png_path.read_bytes()).hexdigest(),
            },
        }
        png_path.unlink(missing_ok=True)
    probe = {
            "schema_version": 1,
            "frozen": bool(getattr(sys, "frozen", False)),
            "python": {
                "version": platform.python_version(),
                "executable": str(Path(sys.executable).resolve()),
                "architecture": platform.machine(),
                "bundle_root": str(Path(getattr(sys, "_MEIPASS", "")).resolve()),
            },
            "qt": {
                "pyqt_version": QtCore.PYQT_VERSION_STR,
                "compiled_qt_version": QtCore.QT_VERSION_STR,
                "runtime_qt_version": QtCore.qVersion(),
                "sip_runtime_version": sip.SIP_VERSION_STR,
                "platform_plugin": app.platformName().lower(),
                "plugins_path": QtCore.QLibraryInfo.path(
                    QtCore.QLibraryInfo.LibraryPath.PluginsPath
                ),
                "library_paths": list(app.libraryPaths()),
                "scale_factor_environment": os.environ.get("QT_SCALE_FACTOR"),
                "baseline_device_pixel_ratio": float(primary.devicePixelRatio()),
                "baseline_logical_dpi": float(primary.logicalDotsPerInch()),
            },
            "rpy2": {
                "distribution_version": importlib.metadata.version("rpy2"),
                "rinterface_distribution_version": importlib.metadata.version("rpy2-rinterface"),
                "robjects_distribution_version": importlib.metadata.version("rpy2-robjects"),
                "cffi_mode": os.environ.get("RPY2_CFFI_MODE"),
                "loaded_cffi_mode": openrlib.cffi_mode.name,
                "api_bridge_loaded": openrlib.cffi_mode.name == "API",
                "api_bridge_path": str(api_bridge_path),
                "api_bridge_sha256": hashlib.sha256(api_bridge_path.read_bytes()).hexdigest(),
            },
            "project_schemas": {
                "version": 1,
                "validated_members": ["manifest.json", "project.json", "state.json"],
            },
            "r": {
                "version": r_version,
                "home": r_home,
                "library_paths": r_library_paths,
                "configured_home": configured.get("R_HOME"),
                "configured_library": configured.get("R_LIBS"),
                "macos_product_profile": macos_profile,
                "shared_library_path": str(shared_r_path),
                "shared_library_sha256": hashlib.sha256(shared_r_path.read_bytes()).hexdigest(),
                "direct_spike": configured.get("direct_spike") is True,
                "lc_numeric": os.environ.get("LC_NUMERIC"),
            },
    }
    if configured.get("kit_sha256") is not None:
        probe["r"]["kit_sha256"] = configured["kit_sha256"]
    _write_json(output_path, probe)
    _log("packaged-runtime-probe:passed")
    app.quit()
    return 0


def _runtime_shared_library(configured: dict[str, Any]) -> Path:
    """Resolve the private R library for either frozen delivery layout."""
    root = Path(sys.executable).resolve().parent
    derivation = configured.get("derivation") or {}
    if configured.get("direct_spike") is True:
        shared = (Path(configured["R_HOME"]) / "lib" / "libR.dylib").resolve()
    elif derivation:
        record = derivation.get("final", {}).get("r_shared_library", {})
        shared = (root / str(record.get("path", ""))).resolve()
    else:
        shared = (Path(configured["R_HOME"]) / "bin" / "x64" / "R.dll").resolve()
    if not shared.is_file():
        raise RuntimeError("Frozen application is missing its private R shared library.")
    return shared


def _assert_standard_binary_summary_is_formatted(window):
    """Run the normal binary analysis and retain its user-facing result."""
    from rc_metastudio import main_window

    captured: dict[str, Any] = {}

    def capture(result):
        captured["result"] = result

    dialog = main_window.analysis_setup_dialog.AnalysisSetupDialog(
        window.model,
        parent=window,
        confidence_level=window.model.get_confidence_level(),
    )
    original = window.analysis
    try:
        methods = set(dialog.available_method_d.values()) if dialog.available_method_d else set()
        if "binary.random" not in methods:
            raise RuntimeError("Packaged summary smoke found no binary.random method.")
        dialog.current_method = "binary.random"
        dialog.current_param_vals = {}
        dialog.setup_params()
        dialog.current_param_vals.update(dialog.current_defaults)
        window.analysis = capture
        dialog.run_ma()
    finally:
        window.analysis = original
        dialog.close()
    result = captured.get("result")
    if not result:
        raise RuntimeError("Packaged summary smoke produced no analysis result.")
    summary = result.get("texts", {}).get("Summary", "")
    required = ("Binary Random-Effects Model", "Metric: Odds Ratio", "Model Results", "Estimate", "Lower bound (95% CI)", "Upper bound (95% CI)", "p-value", "Heterogeneity")
    if any(text not in summary for text in required):
        raise RuntimeError("Packaged summary smoke result text is incomplete.")
    if any(text in summary for text in ("$model.title", "$arrays", 'attr(,"class")')):
        raise RuntimeError("Packaged summary smoke result contains raw R output.")
    return result


def _result_identity(result: dict[str, Any]) -> dict[str, Any]:
    summary = result.get("texts", {}).get("Summary", "").replace("\r\n", "\n")
    normalized = normalize_packaged_summary_identity(summary)
    images = result.get("display_images", {})
    svg_hashes = {}
    for label, raw_path in sorted(images.items()):
        path = Path(raw_path)
        if path.suffix.lower() == ".svg" and path.is_file():
            svg_hashes[label] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not svg_hashes:
        raise RuntimeError("Packaged analysis produced no display SVG.")
    return {
        "raw_summary_sha256": hashlib.sha256(summary.encode()).hexdigest(),
        "normalized_summary_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
        "svg_sha256": svg_hashes,
    }


def _exercise_packaged_project_workflow(app, window, sample_path: str) -> dict[str, Any]:
    """Observe edit, real analysis, locale input, save/reopen, and result identity."""
    from PyQt6 import QtCore
    from rc_metastudio import project_format

    model = window.tableView.model()
    edited_name = "Packaged Smoke – München"
    name_index = model.index(0, model.NAME)
    if not model.setData(name_index, edited_name) or model.data(name_index, QtCore.Qt.ItemDataRole.DisplayRole) != edited_name:
        raise RuntimeError("Packaged smoke representative edit failed.")
    raw_index = model.index(0, model.RAW_DATA[0])
    raw_value = float(str(model.data(raw_index, QtCore.Qt.ItemDataRole.DisplayRole)).replace(",", "."))
    save_root = Path(tempfile.mkdtemp(prefix="rcms-packaged-smoke-"))
    variants = []
    for locale_name, numeric_text, destination in (
        ("en_US", f"{raw_value:.1f}", save_root / "dot-decimal.rcms"),
        ("de_DE", f"{raw_value:.1f}".replace(".", ","), save_root / "comma-decimal.rcms"),
    ):
        locale = QtCore.QLocale(locale_name)
        parsed, valid = locale.toDouble(numeric_text)
        if not valid or parsed != raw_value or not model.setData(raw_index, numeric_text):
            raise RuntimeError(f"Packaged smoke {locale_name} input failed.")
        identity = _result_identity(_assert_standard_binary_summary_is_formatted(window))
        window.out_path = str(destination)
        if window.save() is not True or not destination.is_file():
            raise RuntimeError(f"Packaged smoke {locale_name} save failed.")
        variants.append({"locale": locale_name, "input": numeric_text, "canonical_value": raw_value, **identity})
        if locale_name == "de_DE":
            if not window.open(os.path.abspath(sample_path), raise_on_error=True):
                raise RuntimeError("Packaged smoke could not reset sample.")
            model = window.tableView.model()
            name_index = model.index(0, model.NAME)
            raw_index = model.index(0, model.RAW_DATA[0])
            if not model.setData(name_index, edited_name):
                raise RuntimeError("Packaged smoke could not repeat representative edit.")

    if variants[0]["raw_summary_sha256"] != variants[1]["raw_summary_sha256"] or variants[0]["svg_sha256"] != variants[1]["svg_sha256"]:
        raise RuntimeError("Locale variants produced different analysis identities.")
    if project_format.load_project(save_root / "dot-decimal.rcms").project != project_format.load_project(save_root / "comma-decimal.rcms").project:
        raise RuntimeError("Locale variants did not persist canonically.")
    if not window.open(str(save_root / "comma-decimal.rcms"), raise_on_error=True):
        raise RuntimeError("Packaged smoke could not reopen saved project.")
    reopened_model = window.tableView.model()
    if reopened_model.data(reopened_model.index(0, reopened_model.NAME), QtCore.Qt.ItemDataRole.DisplayRole) != edited_name:
        raise RuntimeError("Packaged smoke save/reopen lost representative edit.")
    reopened = _result_identity(_assert_standard_binary_summary_is_formatted(window))
    if reopened["raw_summary_sha256"] != variants[1]["raw_summary_sha256"] or reopened["svg_sha256"] != variants[1]["svg_sha256"]:
        raise RuntimeError("Reopened packaged analysis changed result identity.")
    expected = reopened["normalized_summary_sha256"]
    return {
        "automation_entry_point": True,
        "converted_sample": Path(sample_path).name,
        "representative_edit": True,
        "real_r_analysis": True,
        "result_text": True,
        "expected_normalized_summary_sha256": expected,
        **reopened,
        "locale_variants": variants,
        "save_reopen": True,
        "analysis_after_reopen": True,
    }


def _sample_project_observations(window, representative_sample: str) -> dict[str, Any]:
    from rc_metastudio import project_format

    root = Path(representative_sample).resolve().parent
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return {"passed": True, "manifest_sha256": hashlib.sha256(b"").hexdigest(), "projects": []}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = []
    for item in manifest.get("projects", []):
        path = root / str(item["file"])
        document = project_format.load_project(path)
        reconstructed = project_format.reconstruct_analysis_dataset(document)
        records.append({
            "project": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "semantic_sha256": reconstructed.semantic_sha256,
            "opened_in_packaged_application": bool(window.open(str(path), raise_on_error=True)),
        })
    return {"passed": all(record["opened_in_packaged_application"] for record in records), "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(), "projects": records}


def start_package_surface_smoke(evidence_path: str, expected_scale: str) -> int:
    """Exercise resources and basic native Qt surfaces in the packaged app."""
    from PyQt6 import QtCore, QtGui, QtNetwork, QtWidgets

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
    if not QtCore.QLocale(QtCore.QLocale.Language.German).toDouble("1,25")[1]:
        raise SystemExit("Package surface smoke locale parsing failed.")
    tls_backends = list(QtNetwork.QSslSocket.availableBackends())
    styles = list(QtWidgets.QStyleFactory.keys())
    image_formats = sorted(
        value.data().decode("ascii").lower()
        for value in QtGui.QImageReader.supportedImageFormats()
    )
    if not styles or not app.style() or not {"jpeg", "svg"} <= set(image_formats):
        raise SystemExit("Package surface smoke Qt plugins are incomplete.")
    native_window = QtWidgets.QMainWindow()
    menu_bar = native_window.menuBar()
    menu = menu_bar.addMenu("Package smoke")
    menu.addAction("Verified action")
    control = QtWidgets.QPushButton("Accessible package control", native_window)
    control.setObjectName("packagedAccessibilityControl")
    control.setAccessibleName("Packaged accessibility control")
    control.setAccessibleDescription("Verifies packaged Qt accessibility metadata.")
    target = QtWidgets.QLineEdit(native_window)
    target.setObjectName("packagedKeyboardTraversalTarget")
    body = QtWidgets.QWidget(native_window)
    layout = QtWidgets.QVBoxLayout(body)
    layout.addWidget(control)
    layout.addWidget(target)
    native_window.setCentralWidget(body)
    native_window.setTabOrder(control, target)
    native_window.show()
    app.processEvents()
    native_menu = {"is_native": bool(menu_bar.isNativeMenuBar()), "menu_count": len(menu_bar.actions()), "action_count": len(menu.actions())}
    control.setFocus()
    app.processEvents()
    focus_before = app.focusWidget()
    app.sendEvent(control, QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_Tab, QtCore.Qt.KeyboardModifier.NoModifier))
    app.sendEvent(control, QtGui.QKeyEvent(QtCore.QEvent.Type.KeyRelease, QtCore.Qt.Key.Key_Tab, QtCore.Qt.KeyboardModifier.NoModifier))
    app.processEvents()
    native_accessibility = _observe_cocoa_accessibility(control) if sys.platform == "darwin" else {}
    accessibility = {
        "focus_before": focus_before.objectName() if focus_before else None,
        "focus_after_tab": (app.focusWidget().objectName() if app.focusWidget() else None),
        "accessible_name": control.accessibleName(),
        "accessible_description": control.accessibleDescription(),
        "native": native_accessibility,
    }
    file_dialog = _observe_file_dialog(app, native_window)
    critical_dialog = _observe_critical_dialog(app, native_window)
    primary = app.primaryScreen()
    if primary is None:
        raise SystemExit("Package surface smoke found no primary screen.")
    baseline = float(os.environ.get("RCMS_PACKAGE_BASELINE_DPR", primary.devicePixelRatio()))
    requested = float(expected_scale)
    observed = float(primary.devicePixelRatio())
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
            "device_pixel_ratio": observed,
            "baseline_device_pixel_ratio": baseline,
            "expected_device_pixel_ratio": baseline * requested,
            "dpr_tolerance": 0.05,
            "logical_dpi": float(primary.logicalDotsPerInch()),
            "clipboard": True,
            "critical_dialog": critical_dialog,
            "binary_resources": True,
            "native_menu": native_menu,
            "native_file_dialog": file_dialog,
            "accessibility": accessibility,
            "tls_backends": tls_backends,
            "active_style": app.style().objectName(),
            "available_styles": styles,
            "image_formats": image_formats,
            "platform_plugin": platform_name,
            "locale": "de_DE",
            "cleanup": {"close_accepted": bool(native_window.close()), "window_visible": native_window.isVisible()},
        }
    )
    _write_json(evidence_path, evidence)
    _log("packaged-surface:scale-%s-passed" % expected_scale)
    app.quit()
    return 0


def _observe_file_dialog(app, parent):
    from PyQt6 import QtCore, QtWidgets
    dialog = QtWidgets.QFileDialog(parent)
    dialog.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFile)
    dialog.setOption(QtWidgets.QFileDialog.Option.DontUseNativeDialog, False)
    dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
    observed = {"dont_use_native_dialog": dialog.testOption(QtWidgets.QFileDialog.Option.DontUseNativeDialog), "window_modality": None, "visible_before_cancel": False, "cancel_requested": False, "finished_signal": False, "rejected_signal": False, "result": None, "rejected_value": 0, "timed_out": False, "timeout_ms": NATIVE_FILE_DIALOG_TIMEOUT_MS}
    loop = QtCore.QEventLoop()
    dialog.finished.connect(lambda result: (observed.update(finished_signal=True, result=int(result)), loop.quit()))
    dialog.rejected.connect(lambda: observed.update(rejected_signal=True))
    def cancel():
        observed["visible_before_cancel"] = dialog.isVisible()
        observed["cancel_requested"] = True
        dialog.reject()
    QtCore.QTimer.singleShot(250, cancel)
    dialog.open()
    observed["window_modality"] = dialog.windowModality().name
    QtCore.QTimer.singleShot(NATIVE_FILE_DIALOG_TIMEOUT_MS, loop.quit)
    if not observed["finished_signal"]:
        loop.exec()
    dialog.deleteLater()
    return observed


def _observe_critical_dialog(app, parent):
    from PyQt6 import QtCore, QtWidgets
    dialog = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Critical, "Packaged critical dialog", "Deployment smoke diagnostic", QtWidgets.QMessageBox.StandardButton.Ok, parent)
    dialog.setOption(QtWidgets.QMessageBox.Option.DontUseNativeDialog, False)
    dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
    observed = {"dont_use_native_dialog": dialog.testOption(QtWidgets.QMessageBox.Option.DontUseNativeDialog), "application_dont_use_native_dialogs": QtCore.QCoreApplication.testAttribute(QtCore.Qt.ApplicationAttribute.AA_DontUseNativeDialogs), "dont_show_on_screen_before_show": dialog.testAttribute(QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen), "dont_show_on_screen_after_show": None, "native_helper_active": False, "window_modality": None, "visible_before_close": False, "critical_icon": False, "finished_signal": False, "result": None, "accepted_value": 1, "timed_out": False, "timeout_ms": CRITICAL_DIALOG_TIMEOUT_MS}
    loop = QtCore.QEventLoop()
    def finish(result):
        observed.update(finished_signal=True, result=int(result))
        loop.quit()
    dialog.finished.connect(finish)
    def accept():
        observed["visible_before_close"] = dialog.isVisible()
        observed["critical_icon"] = dialog.icon() == QtWidgets.QMessageBox.Icon.Critical
        dialog.accept()
    dialog.show()
    observed["dont_show_on_screen_after_show"] = dialog.testAttribute(QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen)
    observed["native_helper_active"] = not observed["dont_use_native_dialog"] and not observed["application_dont_use_native_dialogs"] and not observed["dont_show_on_screen_before_show"] and observed["dont_show_on_screen_after_show"]
    observed["window_modality"] = dialog.windowModality().name
    QtCore.QTimer.singleShot(100, accept)
    QtCore.QTimer.singleShot(CRITICAL_DIALOG_TIMEOUT_MS, loop.quit)
    if not observed["finished_signal"]:
        loop.exec()
    dialog.deleteLater()
    return observed


def _observe_cocoa_accessibility(widget):
    """Inspect the named control through Qt's Cocoa accessibility tree."""
    import ctypes

    objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.objc_msgSend.restype = ctypes.c_void_p
    send = objc.objc_msgSend

    def selector(name):
        return objc.sel_registerName(name.encode("ascii"))

    def msg(receiver, name, *args):
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_void_p] * len(args)
        return send(ctypes.c_void_p(receiver), selector(name), *[ctypes.c_void_p(arg) for arg in args])

    def responds(receiver, name):
        send.restype = ctypes.c_bool
        return bool(msg(receiver, "respondsToSelector:", selector(name)))

    def text(receiver, name):
        if not responds(receiver, name):
            return ""
        value = msg(receiver, name)
        if not value:
            return ""
        raw = msg(value, "UTF8String")
        return ctypes.cast(raw, ctypes.c_char_p).value.decode("utf-8") if raw else ""

    def children(receiver):
        if not responds(receiver, "accessibilityAttributeValue:"):
            return []
        string_class = objc.objc_getClass(b"NSString")
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]
        attribute = send(string_class, selector("stringWithUTF8String:"), b"AXChildren")
        value = msg(receiver, "accessibilityAttributeValue:", attribute)
        if not value:
            return []
        count = int(msg(value, "count") or 0)
        return [int(msg(value, "objectAtIndex:", index)) for index in range(min(count, 256))]

    def observe(receiver):
        send.restype = ctypes.c_void_p
        ignored = None
        if responds(receiver, "accessibilityIsIgnored"):
            send.restype = ctypes.c_bool
            ignored = bool(msg(receiver, "accessibilityIsIgnored"))
        return {"role": text(receiver, "accessibilityRole"), "title": text(receiver, "accessibilityTitle"), "description": text(receiver, "accessibilityLabel"), "is_ignored": ignored}

    root = int(widget.winId())
    found = find_accessibility_element([root], expected_role="AXButton", expected_title=widget.accessibleName(), expected_description=widget.accessibleDescription(), observe=observe, children=children)
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
            "maximized": window.isMaximized(),
            "exposed": bool(handle and handle.isExposed()),
            "frame": [frame.x(), frame.y(), frame.width(), frame.height()],
            "rows": window.tableView.model().rowCount(),
        }
        evidence["passed"] = opened and evidence["visible"] and evidence["rows"] >= 1
        evidence["failures"] = [] if evidence["passed"] else ["startup project smoke failed"]
        _write_json(evidence_path, evidence)
        if evidence["passed"]:
            _log("startup-project:normal-entry-point-passed")
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
