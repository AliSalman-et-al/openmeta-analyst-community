# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

import faulthandler
import hashlib
import json
import platform
import sys, time, traceback
import tempfile
from pathlib import Path
from typing import Any, cast
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QThread
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QSplashScreen

import os

forms_path = os.path.join(os.path.dirname(__file__), "forms")
if forms_path not in sys.path:
    sys.path.insert(0, forms_path)

from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()

import meta_py_r_backend
import meta_globals

meta_py_r_backend.install_meta_py_r_backend()
import app_error_handler
import settings
import adaptive_window
import qt6_resources

SPLASH_DISPLAY_TIME = 0  # Keep startup smoke tests fast; packaged builds may override.
APPLICATION_ICON_PATH = ":/misc/meta.png"
AUTOMATION_SMOKE_LOG_ENV = "RCMS_AUTOMATION_SMOKE_LOG"
ADAPTIVE_LAYOUT_EVIDENCE_LOG_ENV = "RCMS_ADAPTIVE_LAYOUT_EVIDENCE_LOG"
PACKAGED_SUMMARY_SHA256 = "78294820c83cd94c19dfdca8c24b6a96cdc8b6f1319a5cd1bedffacde73851e2"


def screen_bounded_splash_pixmap(source, available_logical_size):
    """Bound a splash in Logical Layout Space while preserving source DPR."""
    pixmap = QPixmap(source)
    available = QtCore.QSize(available_logical_size)
    if pixmap.isNull() or not available.isValid():
        return pixmap

    device_pixel_ratio = max(1.0, pixmap.devicePixelRatioF())
    logical_width = pixmap.width() / device_pixel_ratio
    logical_height = pixmap.height() / device_pixel_ratio
    if (
        logical_width <= available.width()
        and logical_height <= available.height()
    ):
        return pixmap

    scale = min(
        available.width() / logical_width,
        available.height() / logical_height,
    )
    target_logical_width = max(1, int(logical_width * scale))
    target_logical_height = max(1, int(logical_height * scale))
    target_physical_size = QtCore.QSize(
        max(1, round(target_logical_width * device_pixel_ratio)),
        max(1, round(target_logical_height * device_pixel_ratio)),
    )
    bounded = pixmap.scaled(
        target_physical_size,
        QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
        QtCore.Qt.TransformationMode.SmoothTransformation,
    )
    bounded.setDevicePixelRatio(device_pixel_ratio)
    return bounded


def create_startup_splash() -> QSplashScreen:
    """Build the startup Transient Window from high-DPI-capable resources."""
    qt6_resources.ensure_application_resources()
    splash_pixmap = QPixmap(":/misc/splash.png")
    screen = QtWidgets.QApplication.primaryScreen()
    if screen is not None:
        splash_pixmap = screen_bounded_splash_pixmap(
            splash_pixmap, screen.availableGeometry().size()
        )
    splash = QSplashScreen(splash_pixmap)
    adaptive_window.register_adaptive_window(
        splash, adaptive_window.WindowRole.TRANSIENT
    )
    return splash


def _write_automation_smoke_log(message):
    log_path = os.environ.get(ADAPTIVE_LAYOUT_EVIDENCE_LOG_ENV) or os.environ.get(
        AUTOMATION_SMOKE_LOG_ENV
    )
    if not log_path:
        return
    try:
        os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(str(message))
            log_file.write("\n")
    except OSError:
        pass


def _run_automation_smoke(callback):
    try:
        return callback()
    except BaseException as exc:
        _write_automation_smoke_log("".join(traceback.format_exception(exc)))
        raise


def _native_windows_command_line_argv():
    if os.name != "nt":
        return None

    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return None

    shell32 = ctypes.windll.shell32
    kernel32 = ctypes.windll.kernel32
    shell32.CommandLineToArgvW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.c_int),
    ]
    shell32.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
    kernel32.GetCommandLineW.argtypes = []
    kernel32.GetCommandLineW.restype = wintypes.LPWSTR
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL

    argc = ctypes.c_int()
    argv = shell32.CommandLineToArgvW(kernel32.GetCommandLineW(), ctypes.byref(argc))
    if not argv:
        return None
    try:
        return [argv[index] for index in range(argc.value)]
    finally:
        kernel32.LocalFree(argv)


def _startup_project_path(argv):
    args = list(argv or [])
    index = 1
    while index < len(args):
        arg = args[index]
        if arg in ("--automation-smoke", "--automation-native-smoke"):
            return None
        if arg.startswith("-"):
            index += 1
            continue
        return arg
    return None


def _resolve_startup_argv(argv=None, native_argv=None, frozen=None):
    resolved = list(sys.argv if argv is None else argv)
    is_frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if not is_frozen:
        return resolved

    if native_argv is None:
        native_argv = _native_windows_command_line_argv()
    native_argv = list(native_argv or [])

    if (
        _startup_project_path(resolved) is None
        and _startup_project_path(native_argv) is not None
    ):
        return native_argv
    return resolved


def _emit_automation_phase(phase_callback, phase):
    if phase_callback is not None:
        phase_callback(phase)


def load_R_libraries(app, splash=None, phase_callback=None):
    """Loads the R libraries while updating the splash screen"""
    from rc_metastudio import meta_py_r

    def _status(message):
        if splash is not None:
            splash.showMessage(message)
        app.processEvents()

    _emit_automation_phase(phase_callback, "r-library-paths:start")
    meta_py_r.get_R_libpaths()  # print the lib paths
    _emit_automation_phase(phase_callback, "r-library-paths:complete")
    rloader = meta_py_r.RlibLoader()

    _status("Loading R libraries\n..")

    _status("Loading metafor\n....")
    _emit_automation_phase(phase_callback, "r-library:metafor:start")
    rloader.load_metafor()
    _emit_automation_phase(phase_callback, "r-library:metafor:complete")

    _status("Loading RCMetaR\n........")
    _emit_automation_phase(phase_callback, "r-library:RCMetaR:start")
    rloader.load_RCMetaR()
    _emit_automation_phase(phase_callback, "r-library:RCMetaR:complete")

    _status("Loading igraph\n............")
    _emit_automation_phase(phase_callback, "r-library:igraph:start")
    rloader.load_igraph()
    _emit_automation_phase(phase_callback, "r-library:igraph:complete")

    _status("Loading grid\n................")
    _emit_automation_phase(phase_callback, "r-library:grid:start")
    rloader.load_grid()
    _emit_automation_phase(phase_callback, "r-library:grid:complete")

    import meta_form

    if not meta_form.DISABLE_NETWORK_STUFF:
        _status("Loading gemtc\n...................")
        rloader.load_gemtc()


def start():
    qt6_resources.ensure_application_resources()
    app_error_handler.install_global_exception_handler()
    startup_argv = _resolve_startup_argv()
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-smoke":
        sample_path = (
            startup_argv[2]
            if len(startup_argv) > 2
            else os.path.join("sample_projects", "amino.rcms")
        )
        return start_automation_smoke(sample_path)
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-shell-smoke":
        return start_shell_smoke()
    if (
        len(startup_argv) > 1
        and startup_argv[1] == "--automation-native-shell-smoke"
    ):
        return start_shell_smoke(require_native_window=True)
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-shell-failure-smoke":
        if len(startup_argv) != 3:
            raise SystemExit(
                "--automation-shell-failure-smoke requires r-load or meta-form"
            )
        return start_shell_failure_smoke(startup_argv[2])
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-native-smoke":
        sample_path = (
            startup_argv[2]
            if len(startup_argv) > 2
            else os.path.join("sample_projects", "amino.rcms")
        )
        return _run_automation_smoke(
            lambda: start_automation_smoke(sample_path, require_native_window=True)
        )
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-package-surface-smoke":
        if len(startup_argv) != 4:
            raise SystemExit(
                "--automation-package-surface-smoke requires an evidence path and scale."
            )
        return _run_automation_smoke(
            lambda: start_package_surface_smoke(startup_argv[2], startup_argv[3])
        )
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-package-runtime-probe":
        if len(startup_argv) != 3:
            raise SystemExit("--automation-package-runtime-probe requires an output path.")
        return _run_automation_smoke(lambda: start_package_runtime_probe(startup_argv[2]))
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-wizard-layout-smoke":
        return _run_automation_smoke(start_wizard_layout_smoke)
    if (
        len(startup_argv) > 1
        and startup_argv[1] == "--automation-adaptive-layout-evidence"
    ):
        if len(startup_argv) < 3:
            raise SystemExit(
                "--automation-adaptive-layout-evidence requires an output directory."
            )
        output_dir = startup_argv[2]
        sample_path = (
            startup_argv[3]
            if len(startup_argv) > 3
            else os.path.join("sample_projects", "amino.rcms")
        )
        return _run_automation_smoke(
            lambda: start_adaptive_layout_evidence(output_dir, sample_path)
        )

    startup_project_path = _startup_project_path(startup_argv)
    meta_form = _import_meta_form()
    app = app_error_handler.get_or_create_application(list(sys.argv))
    _configure_application(app)
    baseline_ids = _top_level_ids(app)
    try:
        settings.setup_directories()
        meta = _create_interactive_shell(app, meta_form.MetaForm, load_R_libraries)
        if startup_project_path:
            opened = meta.open(startup_project_path)
            if os.environ.get("RCMS_STARTUP_PROJECT_SMOKE") == "1":
                return _assert_opened_project_for_startup_smoke(
                    app, meta, startup_project_path, opened
                )
        else:
            if os.environ.get("RCMS_STARTUP_PROJECT_SMOKE") == "1":
                raise SystemExit(
                    "Startup project smoke test did not receive a project path."
                )
            meta.start()
        return app.exec()
    finally:
        _dispose_new_top_levels(app, baseline_ids)


def start_automation(phase_callback=None):
    qt6_resources.ensure_application_resources()
    app_error_handler.install_global_exception_handler()
    meta_form = _import_meta_form()
    app = app_error_handler.get_or_create_application(sys.argv)
    _configure_application(app)
    _emit_automation_phase(phase_callback, "application:configured")
    baseline_ids = _top_level_ids(app)
    try:
        settings.setup_directories()
        _emit_automation_phase(phase_callback, "settings:ready")
        if os.environ.get("RCMS_REQUIRE_IN_PROCESS_RPY2") == "1":
            _emit_automation_phase(phase_callback, "r-libraries:start")
            load_R_libraries(app, None, phase_callback=phase_callback)
            _emit_automation_phase(phase_callback, "r-libraries:complete")
        _emit_automation_phase(phase_callback, "meta-form:create:start")
        meta = meta_form.MetaForm()
        _emit_automation_phase(phase_callback, "meta-form:create:complete")
        _show_main_window(meta)
        _emit_automation_phase(phase_callback, "main-window:shown")
        return app, meta
    except BaseException:
        _dispose_new_top_levels(app, baseline_ids)
        raise


def _create_interactive_shell(app, meta_factory, r_loader):
    """Create splash and shell with fail-closed ownership transfer."""
    baseline_ids = _top_level_ids(app)
    splash = None
    try:
        splash = create_startup_splash()
        splash.show()
        splash_starttime = time.time()
        r_loader(app, splash)

        time_elapsed = time.time() - splash_starttime
        print("It took %s seconds to load the R libraries" % time_elapsed)
        if time_elapsed < SPLASH_DISPLAY_TIME:
            QThread.msleep(max(0, round((SPLASH_DISPLAY_TIME - time_elapsed) * 1000)))

        meta = meta_factory()
        splash.finish(meta)
        _show_main_window(meta)
        _dispose_qobjects(app, (splash,))
        return meta
    except BaseException:
        _dispose_new_top_levels(app, baseline_ids, (splash,))
        raise


def _top_level_ids(app):
    return {id(widget) for widget in app.topLevelWidgets()}


def _dispose_new_top_levels(app, baseline_ids, known=()):
    owned = list(known)
    owned.extend(
        widget for widget in app.topLevelWidgets() if id(widget) not in baseline_ids
    )
    _dispose_qobjects(app, owned)


def _dispose_qobjects(app, objects):
    """Hide and delete owned Qt objects without invoking user close prompts."""
    unique = {id(obj): obj for obj in objects if obj is not None}
    for obj in unique.values():
        try:
            obj.hide()
            obj.deleteLater()
        except RuntimeError:
            pass
    for _index in range(2):
        app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        app.processEvents()


def _show_main_window(window):
    if hasattr(settings, "restore_main_window_placement") and hasattr(
        window, "restoreGeometry"
    ):
        settings.restore_main_window_placement(window)
    elif hasattr(window, "showMaximized"):
        window.showMaximized()
    else:
        window.show()


def _set_application_icon(app):
    app.setWindowIcon(QIcon(APPLICATION_ICON_PATH))


def _configure_application(app):
    """Apply the complete process-wide application identity exactly once."""
    app.setApplicationName(meta_globals.APPLICATION_NAME)
    app.setApplicationDisplayName(meta_globals.APPLICATION_DISPLAY_NAME)
    app.setApplicationVersion(meta_globals.VERSION)
    app.setOrganizationName(meta_globals.ORGANIZATION_NAME)
    app.setOrganizationDomain(meta_globals.ORGANIZATION_DOMAIN)
    _set_application_icon(app)


def start_automation_smoke(sample_path, require_native_window=False):
    _write_automation_smoke_log("packaged-workflow:start")
    hang_trace = _start_automation_hang_trace()
    meta = None
    try:
        app, meta = start_automation(
            phase_callback=lambda phase: _write_automation_smoke_log(
                "packaged-workflow:shell:%s" % phase
            )
        )
        _write_automation_smoke_log("packaged-workflow:shell-created")
        if require_native_window:
            platform_name = app.platformName().lower()
            expected = "windows" if sys.platform == "win32" else "cocoa"
            if platform_name != expected:
                raise SystemExit(
                    "Native smoke loaded Qt platform %s, expected %s."
                    % (platform_name, expected)
                )
            app.processEvents()
            if not meta.isVisible():
                raise SystemExit(
                    "Native smoke main window was not visible on Qt platform %s."
                    % platform_name
                )
            print(
                "Native smoke showed the main window with Qt platform %s."
                % platform_name
            )
        sample_path = os.path.abspath(sample_path)
        _write_automation_smoke_log("packaged-workflow:project-open:start")
        if not meta.open(sample_path):
            raise SystemExit("Could not open smoke-test project: %s" % sample_path)
        _write_automation_smoke_log("packaged-workflow:project-open:return")
        app.processEvents()
        _write_automation_smoke_log("packaged-workflow:sample-opened")
        model = meta.tableView.model()
        if model is None or model.rowCount() < 1:
            raise SystemExit(
                "Smoke-test project opened without table rows: %s" % sample_path
            )

        # Force a real paint pass. Painting queries data()/headerData() for paint
        # roles (e.g. BackgroundColorRole) that offscreen layout never touches, so
        # This catches paint-time model/data regressions in the packaged build. A
        # paint error aborts the process, failing the smoke test with a non-zero
        # exit code rather than shipping a build that crashes on first render.
        _write_automation_smoke_log("packaged-workflow:paint:start")
        _force_table_paint(app, meta)
        _write_automation_smoke_log("packaged-workflow:paint:complete")
        _write_automation_smoke_log("packaged-workflow:project-exercise:start")
        workflow = _exercise_packaged_project_workflow(app, meta, sample_path)
        _write_automation_smoke_log("packaged-workflow:project-exercise:complete")
        _write_automation_smoke_log("packaged-workflow:save-reopen-complete")
        evidence_path = os.environ.get("RCMS_PACKAGE_SMOKE_EVIDENCE")
        if evidence_path:
            evidence = {
                "schema_version": 1,
                "passed": True,
                "platform_plugin": app.platformName().lower(),
                "workflows": workflow,
                "scales": [],
            }
            Path(evidence_path).write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _write_automation_smoke_log("packaged-workflow:evidence-written")
    finally:
        try:
            if meta is not None:
                # Automation owns this disposable window.  Never let an earlier
                # smoke failure become an unattended save-confirmation dialog that
                # masks the real error until the outer watchdog expires.
                meta.current_data_unsaved = False
                meta.close()
                app.processEvents()
        finally:
            _stop_automation_hang_trace(hang_trace)
    _write_automation_smoke_log("packaged-workflow:post-close")
    return 0


def _start_automation_hang_trace():
    path = os.environ.get("RCMS_AUTOMATION_HANG_TRACE")
    if not path:
        return None
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    trace = open(path, "a", encoding="utf-8")
    faulthandler.dump_traceback_later(60, repeat=True, file=trace)
    return trace


def _stop_automation_hang_trace(trace):
    if trace is None:
        return
    faulthandler.cancel_dump_traceback_later()
    trace.flush()
    trace.close()


def start_package_surface_smoke(evidence_path, expected_scale):
    """Exercise native package-only Qt surfaces at a requested scale factor."""
    app_error_handler.install_global_exception_handler()
    app = app_error_handler.get_or_create_application(sys.argv)
    _configure_application(app)
    qt6_resources.ensure_application_resources()
    from PyQt6 import QtNetwork
    platform_name = app.platformName().lower()
    if sys.platform == "win32" and platform_name != "windows":
        raise SystemExit("Package surface smoke did not load qwindows.")

    clipboard = app.clipboard()
    clipboard_text = "RC MetaStudio clipboard – München – 1,25"
    clipboard.setText(clipboard_text)
    if clipboard.text() != clipboard_text:
        raise SystemExit("Package surface smoke clipboard round-trip failed.")

    locale = QtCore.QLocale(QtCore.QLocale.Language.German)
    value, valid = locale.toDouble("1,25")
    if not valid or value != 1.25:
        raise SystemExit("Package surface smoke locale parsing failed.")

    if QIcon(":/icons/actions/copy.svg").isNull() or QPixmap(":/misc/meta.png").isNull():
        raise SystemExit("Package surface smoke could not load binary resources.")
    tls_backends = list(QtNetwork.QSslSocket.availableBackends())
    if "schannel" not in [backend.lower() for backend in tls_backends]:
        raise SystemExit("Package surface smoke did not load the Schannel TLS backend.")
    available_styles = list(QtWidgets.QStyleFactory.keys())
    if not available_styles or app.style() is None:
        raise SystemExit("Package surface smoke found no Qt style plugin/style.")
    image_formats = sorted(value.data().decode("ascii").lower() for value in QtGui.QImageReader.supportedImageFormats())
    if not {"ico", "jpeg", "svg"} <= set(image_formats):
        raise SystemExit("Package surface smoke did not load required image/SVG plugins.")

    dialog = QtWidgets.QMessageBox(
        QtWidgets.QMessageBox.Icon.Critical,
        "Packaged critical dialog",
        "Deployment smoke diagnostic",
        QtWidgets.QMessageBox.StandardButton.Ok,
    )
    dialog.show()
    app.processEvents()
    if not dialog.isVisible() or dialog.icon() != QtWidgets.QMessageBox.Icon.Critical:
        raise SystemExit("Package surface smoke could not show a critical dialog.")
    dialog.close()
    app.processEvents()

    primary = app.primaryScreen()
    if primary is None or primary.devicePixelRatio() <= 0 or primary.logicalDotsPerInch() <= 0:
        raise SystemExit("Package surface smoke found invalid display metrics.")

    requested_scale = float(expected_scale)
    environment_scale = float(os.environ.get("QT_SCALE_FACTOR", "0"))
    observed_dpr = float(primary.devicePixelRatio())
    baseline_dpr = float(os.environ.get("RCMS_PACKAGE_BASELINE_DPR", "0"))
    expected_dpr = baseline_dpr * requested_scale
    tolerance = 0.05
    if abs(environment_scale - requested_scale) > 1e-9:
        raise SystemExit("Package surface smoke scale environment differs from request.")
    if baseline_dpr <= 0 or abs(observed_dpr - expected_dpr) > tolerance:
        raise SystemExit(
            "Package surface smoke observed DPR %.4f, expected %.4f ± %.4f."
            % (observed_dpr, expected_dpr, tolerance)
        )

    path = Path(evidence_path)
    evidence = json.loads(path.read_text(encoding="utf-8"))
    evidence.setdefault("scales", []).append(
        {
            "requested": expected_scale,
            "qt_scale_factor": os.environ.get("QT_SCALE_FACTOR"),
            "device_pixel_ratio": observed_dpr,
            "baseline_device_pixel_ratio": baseline_dpr,
            "expected_device_pixel_ratio": expected_dpr,
            "dpr_tolerance": tolerance,
            "logical_dpi": primary.logicalDotsPerInch(),
            "clipboard": True,
            "critical_dialog": True,
            "binary_resources": True,
            "tls_backends": tls_backends,
            "active_style": app.style().objectName(),
            "available_styles": available_styles,
            "image_formats": image_formats,
            "locale": "de_DE",
            "platform_plugin": platform_name,
        }
    )
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_automation_smoke_log("packaged-surface:scale-%s-passed" % expected_scale)
    return 0


def start_package_runtime_probe(output_path):
    """Report the runtime actually loaded by the assembled frozen executable."""
    import importlib.metadata

    from PyQt6 import sip

    import r_runtime

    configured = r_runtime.configure_bundled_r_environment()
    from rpy2 import robjects

    app = app_error_handler.get_or_create_application(sys.argv)
    _configure_application(app)
    primary = app.primaryScreen()
    if primary is None:
        raise SystemExit("Frozen runtime probe found no primary screen.")
    r_home_values = cast(Any, robjects.r("normalizePath(R.home(), winslash='/', mustWork=TRUE)"))
    r_version_values = cast(Any, robjects.r("as.character(getRversion())"))
    r_library_values = cast(Any, robjects.r("normalizePath(.libPaths(), winslash='/', mustWork=TRUE)"))
    r_home = str(r_home_values[0])
    r_version = str(r_version_values[0])
    r_library_paths = [str(value) for value in r_library_values]
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
            "plugins_path": QtCore.QLibraryInfo.path(QtCore.QLibraryInfo.LibraryPath.PluginsPath),
            "library_paths": list(app.libraryPaths()),
            "scale_factor_environment": os.environ.get("QT_SCALE_FACTOR"),
            "baseline_device_pixel_ratio": float(primary.devicePixelRatio()),
            "baseline_logical_dpi": float(primary.logicalDotsPerInch()),
        },
        "rpy2": {"distribution_version": importlib.metadata.version("rpy2")},
        "r": {
            "version": r_version,
            "home": r_home,
            "library_paths": r_library_paths,
            "configured_home": configured.get("R_HOME"),
            "configured_library": configured.get("R_LIBS"),
        },
    }
    Path(output_path).write_text(
        json.dumps(probe, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_automation_smoke_log("packaged-runtime-probe:passed")
    return 0


def _exercise_packaged_project_workflow(app, meta, sample_path):
    import project_format

    model = meta.tableView.model()
    study_index = model.index(0, model.NAME)
    edited_name = "Packaged Smoke – München"
    if not model.setData(study_index, edited_name):
        raise SystemExit("Packaged smoke could not edit representative data.")
    if model.data(study_index, QtCore.Qt.ItemDataRole.DisplayRole) != edited_name:
        raise SystemExit("Packaged smoke edit did not round-trip through the model.")

    save_root = Path(tempfile.mkdtemp(prefix="rcms-packaged-smoke-"))
    raw_index = model.index(0, model.RAW_DATA[0])
    original_raw = model.data(raw_index, QtCore.Qt.ItemDataRole.DisplayRole)
    numeric_value = float(str(original_raw).replace(",", "."))
    dot_text = "%.1f" % numeric_value
    comma_text = dot_text.replace(".", ",")

    variants = []
    for locale_name, numeric_text, destination in (
        ("en_US", dot_text, save_root / "dot-decimal.rcms"),
        ("de_DE", comma_text, save_root / "comma-decimal.rcms"),
    ):
        locale = QtCore.QLocale(locale_name)
        parsed_value, parsed = locale.toDouble(numeric_text)
        if not parsed or parsed_value != numeric_value:
            raise SystemExit("Packaged smoke could not parse the %s locale boundary." % locale_name)
        if locale_name == "de_DE":
            if not meta.open(os.path.abspath(sample_path)):
                raise SystemExit("Packaged smoke could not reset the locale comparison project.")
            model = meta.tableView.model()
            study_index = model.index(0, model.NAME)
            raw_index = model.index(0, model.RAW_DATA[0])
            if not model.setData(study_index, edited_name):
                raise SystemExit("Packaged smoke could not repeat the representative edit.")
        if not model.setData(raw_index, numeric_text):
            raise SystemExit("Packaged smoke rejected %s numeric input." % locale_name)
        result = _assert_standard_binary_summary_is_formatted(meta)
        identity = _packaged_result_identity(result)
        _write_automation_smoke_log("packaged-workflow:analysis-%s-complete" % locale_name)
        meta.out_path = str(destination)
        if meta.save() is not True or not destination.is_file():
            raise SystemExit("Packaged smoke could not save the %s project." % locale_name)
        variants.append(
            {
                "locale": locale_name,
                "input": numeric_text,
                "canonical_value": numeric_value,
                "summary_sha256": identity["summary_sha256"],
                "svg_sha256": identity["svg_sha256"],
                "path": destination,
            }
        )

    dot_project = project_format.load_project(variants[0]["path"]).project
    comma_project = project_format.load_project(variants[1]["path"]).project
    if dot_project != comma_project:
        raise SystemExit("Dot/comma packaged inputs did not persist canonically.")
    if variants[0]["summary_sha256"] != variants[1]["summary_sha256"]:
        raise SystemExit("Dot/comma packaged analyses produced different result text.")
    if variants[0]["svg_sha256"] != variants[1]["svg_sha256"]:
        raise SystemExit("Dot/comma packaged analyses produced different SVG content.")

    saved_path = variants[1]["path"]
    if not meta.open(str(saved_path)):
        raise SystemExit("Packaged smoke could not reopen the saved project.")
    reopened = meta.tableView.model()
    reopened_index = reopened.index(0, reopened.NAME)
    if reopened.data(reopened_index, QtCore.Qt.ItemDataRole.DisplayRole) != edited_name:
        raise SystemExit("Packaged smoke save/reopen lost the representative edit.")
    reopened_identity = _packaged_result_identity(
        _assert_standard_binary_summary_is_formatted(meta)
    )
    if reopened_identity["summary_sha256"] != variants[1]["summary_sha256"]:
        raise SystemExit("Reopened packaged analysis changed result text.")
    if reopened_identity["svg_sha256"] != variants[1]["svg_sha256"]:
        raise SystemExit("Reopened packaged analysis changed SVG content.")
    return {
        "automation_entry_point": True,
        "converted_sample": Path(sample_path).name,
        "representative_edit": True,
        "real_r_analysis": True,
        "result_text": True,
        "expected_summary_sha256": PACKAGED_SUMMARY_SHA256,
        "summary_sha256": reopened_identity["summary_sha256"],
        "svg_sha256": reopened_identity["svg_sha256"],
        "locale_variants": [
            {key: value for key, value in variant.items() if key != "path"}
            for variant in variants
        ],
        "save_reopen": True,
        "analysis_after_reopen": True,
    }


def _packaged_result_identity(result):
    summary = result.get("texts", {}).get("Summary", "").replace("\r\n", "\n")
    summary_sha256 = hashlib.sha256(summary.encode("utf-8")).hexdigest()
    if summary_sha256 != PACKAGED_SUMMARY_SHA256:
        raise SystemExit(
            "Packaged summary identity mismatch: %s != %s"
            % (summary_sha256, PACKAGED_SUMMARY_SHA256)
        )
    display_images = result.get("display_images", {})
    svg_hashes = {}
    for label, raw_path in sorted(display_images.items()):
        path = Path(raw_path)
        if path.suffix.lower() != ".svg":
            continue
        payload = path.read_bytes() if path.is_file() else b""
        if b"<svg" not in payload[:4096].lower():
            raise SystemExit("Packaged smoke analysis produced an invalid SVG: %s" % path)
        svg_hashes[label] = hashlib.sha256(payload).hexdigest()
    if not svg_hashes:
        raise SystemExit("Packaged smoke analysis produced no display SVG.")
    return {"summary_sha256": summary_sha256, "svg_sha256": svg_hashes}


def start_shell_smoke(require_native_window=False):
    """Exercise the maintained full shell without invoking analysis."""
    app, meta = start_automation()
    try:
        if require_native_window:
            platform_name = app.platformName().lower()
            expected = "windows" if sys.platform == "win32" else "cocoa"
            if platform_name != expected:
                raise SystemExit(
                    "Native shell smoke loaded Qt platform %s, expected %s."
                    % (platform_name, expected)
                )
        app.processEvents()
        if not meta.isVisible():
            raise SystemExit("Application shell did not become visible.")
        if meta.menuBar() is None or not meta.menuBar().actions():
            raise SystemExit("Application shell did not expose its menus.")
        print(
            "Application shell smoke passed with Qt platform %s."
            % app.platformName().lower()
        )
    finally:
        meta.current_data_unsaved = False
        meta.close()
        app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        app.processEvents()
    if meta in app.topLevelWidgets():
        raise SystemExit("Application shell remained owned after close.")
    return 0


class _InjectedStartupFailure(RuntimeError):
    pass


def start_shell_failure_smoke(stage):
    """Prove startup failures release every newly owned top-level object."""
    if stage not in {"r-load", "meta-form"}:
        raise SystemExit("Unknown shell failure stage: %s" % stage)
    app = app_error_handler.get_or_create_application(sys.argv)
    _configure_application(app)
    baseline_ids = _top_level_ids(app)

    def r_loader(_app, _splash):
        if stage == "r-load":
            raise _InjectedStartupFailure(stage)

    def meta_factory():
        if stage == "meta-form":
            partial = QtWidgets.QMainWindow()
            partial.setWindowTitle("Injected partial shell")
            partial.show()
            app.processEvents()
            raise _InjectedStartupFailure(stage)
        return QtWidgets.QMainWindow()

    try:
        _create_interactive_shell(app, meta_factory, r_loader)
    except _InjectedStartupFailure:
        pass
    else:
        raise SystemExit("Injected startup failure did not fire: %s" % stage)

    leaked = [
        widget for widget in app.topLevelWidgets() if id(widget) not in baseline_ids
    ]
    if leaked:
        raise SystemExit(
            "Startup failure leaked top-level objects at %s: %s"
            % (stage, [type(widget).__name__ for widget in leaked])
        )
    print("Application shell failure teardown passed at %s." % stage)
    return 0


def start_adaptive_layout_evidence(output_dir, sample_path):
    """Run the packaged native adaptive-layout evidence workflow."""
    import adaptive_layout_evidence

    adaptive_layout_evidence.configure_isolated_evidence_settings(output_dir)
    app, meta = start_automation()
    adaptive_layout_evidence.run_native_adaptive_layout_evidence(
        app,
        meta,
        sample_path,
        output_dir,
    )
    return 0


def start_wizard_layout_smoke():
    app_error_handler.install_global_exception_handler()
    app = app_error_handler.get_or_create_application(sys.argv)
    app.setApplicationName(meta_globals.APPLICATION_NAME)
    app.setOrganizationName(meta_globals.ORGANIZATION_NAME)
    _set_application_icon(app)
    settings.setup_directories()

    import main_wizard

    parent_shell = QtWidgets.QMainWindow()
    # layout-audit: allow=verification-layout-fixture; reason=automation smoke fixture exercises a representative viewport
    parent_shell.resize(1600, 900)
    parent_shell.show()
    _flush_gui_events(app)

    scenarios = [
        ("startup welcome", main_wizard.MainWizard(), []),
        (
            "parented startup welcome",
            main_wizard.MainWizard(parent=parent_shell),
            [],
        ),
        (
            "new dataset",
            main_wizard.MainWizard(path="new_dataset"),
            [
                ("select", main_wizard.Page_DataType, "twoarm_proportions_Button"),
                ("next", main_wizard.Page_ChooseMetric, None),
                ("text", main_wizard.Page_OutcomeName, "Packaged Layout Smoke"),
            ],
        ),
        (
            "csv import",
            main_wizard.MainWizard(path="csv_import"),
            [
                ("select", main_wizard.Page_DataType, "twoarm_proportions_Button"),
                ("next", main_wizard.Page_ChooseMetric, None),
                ("text", main_wizard.Page_OutcomeName, "Packaged Layout Smoke"),
                ("next", main_wizard.Page_CsvImport, None),
            ],
        ),
    ]

    try:
        for scenario_name, wizard, actions in scenarios:
            stable_geometry = _show_wizard_for_layout_smoke(
                app, wizard, scenario_name
            )
            for action, expected_page_id, value in actions:
                _advance_wizard_layout_smoke_page(
                    app, wizard, action, expected_page_id, value
                )
                _assert_wizard_layout_smoke_page(
                    app, wizard, scenario_name, stable_geometry
                )
    finally:
        for _scenario_name, wizard, _actions in scenarios:
            wizard.close()
        parent_shell.close()
        app.processEvents()
    return 0


def _show_wizard_for_layout_smoke(app, wizard, scenario_name):
    wizard.restart()
    wizard.show()
    _flush_gui_events(app)
    _assert_wizard_layout_smoke_page(app, wizard, scenario_name)
    return _window_frame_tuple(wizard)


def _advance_wizard_layout_smoke_page(app, wizard, action, expected_page_id, value):
    if wizard.currentId() != expected_page_id:
        wizard.next()
        _flush_gui_events(app)
    if wizard.currentId() != expected_page_id:
        raise SystemExit(
            "Wizard layout smoke expected page %s but reached %s"
            % (expected_page_id, wizard.currentId())
        )

    page = wizard.currentPage()
    if action == "select":
        getattr(page, value).click()
    elif action == "text":
        page.outcome_name_LineEdit.setText(value)
    elif action != "next":
        raise SystemExit("Unknown wizard layout smoke action: %s" % action)
    _flush_gui_events(app)


def _assert_wizard_layout_smoke_page(
    app, wizard, scenario_name, expected_geometry=None
):
    _flush_gui_events(app)
    page = wizard.currentPage()
    if page is None:
        raise SystemExit("Wizard layout smoke has no current page: %s" % scenario_name)

    parent = page.parentWidget()
    if parent is None:
        raise SystemExit(
            "Wizard layout smoke page has no body parent: %s" % scenario_name
        )

    if page.layout() is not None:
        page.layout().activate()
    _flush_gui_events(app)

    body_rect = parent.contentsRect()
    if body_rect.width() <= 0 or body_rect.height() <= 0:
        raise SystemExit("Wizard layout smoke saw an empty body: %s" % scenario_name)
    if wizard.wizardStyle() != QtWidgets.QWizard.WizardStyle.ModernStyle:
        raise SystemExit("Wizard layout smoke expected ModernStyle: %s" % scenario_name)
    if (
        adaptive_window.adaptive_window_state(wizard).policy.archetype
        is not adaptive_window.WindowArchetype.WORKFLOW
    ):
        raise SystemExit(
            "Wizard layout smoke expected Workflow Window policy: %s"
            % scenario_name
        )
    overflow = page.findChild(QtWidgets.QScrollArea, "pageScrollArea")
    if overflow is None or not overflow.widgetResizable():
        raise SystemExit(
            "Wizard layout smoke expected a page Overflow Boundary: %s"
            % scenario_name
        )
    for button_role in (
        QtWidgets.QWizard.WizardButton.BackButton,
        QtWidgets.QWizard.WizardButton.NextButton,
        QtWidgets.QWizard.WizardButton.FinishButton,
        QtWidgets.QWizard.WizardButton.CancelButton,
    ):
        if overflow.isAncestorOf(wizard.button(button_role)):
            raise SystemExit(
                "Wizard navigation entered page overflow: %s" % scenario_name
            )
    if (
        expected_geometry is not None
        and _window_frame_tuple(wizard) != expected_geometry
    ):
        raise SystemExit(
            "Visible Workflow Window geometry changed between pages: %s"
            % scenario_name
        )
    if page.sizeHint().width() <= 0 or page.sizeHint().height() <= 0:
        raise SystemExit(
            "Wizard layout smoke saw an invalid page size hint: %s" % scenario_name
        )
    if page.width() <= 0 or page.height() <= 0:
        raise SystemExit("Wizard layout smoke saw an unsized page: %s" % scenario_name)

    _assert_visible_children_are_laid_out(page, scenario_name)
    pixmap = wizard.grab()
    image = pixmap.toImage()
    if pixmap.isNull() or image.isNull() or image.width() <= 0 or image.height() <= 0:
        raise SystemExit("Wizard layout smoke could not render: %s" % scenario_name)


def _window_frame_tuple(window):
    geometry = window.frameGeometry()
    return geometry.x(), geometry.y(), geometry.width(), geometry.height()


def _assert_visible_children_are_laid_out(page, scenario_name):
    for child in page.findChildren(QtWidgets.QWidget):
        if child is page or child.isWindow() or not child.isVisible():
            continue
        object_name = child.objectName()
        if not object_name or object_name.startswith("qt_"):
            continue
        if child.width() <= 0 or child.height() <= 0:
            raise SystemExit(
                "Wizard child was not laid out in %s: %s"
                % (scenario_name, object_name or child.__class__.__name__)
            )


def _flush_gui_events(app):
    for _index in range(3):
        app.processEvents()


def _assert_opened_project_for_startup_smoke(app, meta, sample_path, opened):
    try:
        if not opened:
            raise SystemExit("Could not open startup project: %s" % sample_path)
        app.processEvents()
        model = meta.tableView.model()
        if model is None or model.rowCount() < 1:
            raise SystemExit(
                "Startup project opened without table rows: %s" % sample_path
            )
        _force_table_paint(app, meta)
        _write_automation_smoke_log("startup-project:normal-entry-point-passed")
    finally:
        meta.close()
        app.processEvents()
    return 0


def _assert_standard_binary_summary_is_formatted(meta):
    import meta_form

    captured = {}
    original_analysis = meta.analysis

    def capture_analysis(result):
        captured["result"] = result

    specs = meta_form.ma_specs.MA_Specs(
        meta.model,
        parent=meta,
        conf_level=meta.model.get_global_conf_level(),
    )
    try:
        if specs.available_method_d is None:
            raise SystemExit("Packaged summary smoke test found no analysis methods.")
        if "binary.random" not in set(specs.available_method_d.values()):
            raise SystemExit(
                "Packaged summary smoke test could not find binary.random."
            )
        specs.current_method = "binary.random"
        specs.current_param_vals = {}
        specs.setup_params()
        specs.current_param_vals.update(specs.current_defaults)

        meta.analysis = capture_analysis
        specs.run_ma()
    finally:
        meta.analysis = original_analysis
        specs.close()

    result = captured.get("result")
    if not result:
        raise SystemExit(
            "Packaged summary smoke test did not produce analysis results."
        )
    summary = result.get("texts", {}).get("Summary", "")
    required = [
        "Binary Random-Effects Model",
        "Metric: Odds Ratio",
        "Model Results",
        "Estimate",
        "Lower bound",
        "Upper bound",
        "p-value",
        "Heterogeneity",
    ]
    missing = [text for text in required if text not in summary]
    if missing:
        raise SystemExit(
            "Packaged summary smoke test missing expected text: %s" % ", ".join(missing)
        )
    leaks = ["$model.title", "$arrays", 'attr(,"class")']
    leaked = [text for text in leaks if text in summary]
    if leaked:
        raise SystemExit(
            "Packaged summary smoke test saw raw R list output: %s" % ", ".join(leaked)
        )
    return result


def _force_table_paint(app, meta):
    """Renders every cell and both headers so paint-time data() bugs surface here."""
    view = meta.tableView
    # layout-audit: allow=verification-layout-fixture; reason=automation smoke fixture exercises a representative viewport
    view.resize(1400, 900)
    app.processEvents()
    model = view.model()
    for row in range(model.rowCount()):
        view.scrollTo(model.index(row, 0))
        app.processEvents()
        view.viewport().grab()
    view.horizontalHeader().grab()
    view.verticalHeader().grab()
    app.processEvents()


def _import_meta_form():
    if "ma_dataset" in sys.modules and not hasattr(
        sys.modules["ma_dataset"], "__file__"
    ):
        for module_name in [
            "ma_dataset",
            "ma_data_table_model",
            "ma_data_table_view",
            "meta_form",
        ]:
            sys.modules.pop(module_name, None)
    import meta_form

    return meta_form


if __name__ == "__main__":
    start()
