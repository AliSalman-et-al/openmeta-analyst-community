# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import time
from pathlib import Path
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QThread
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QSplashScreen

import os

from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()

from rc_metastudio import meta_globals, r_backend

r_backend.install_r_backend()
from rc_metastudio import adaptive_window, app_error_handler, qt6_resources, settings
SPLASH_DISPLAY_TIME = 0  # Keep startup smoke tests fast; packaged builds may override.
APPLICATION_ICON_PATH = ":/misc/meta.png"


def screen_bounded_splash_pixmap(source, available_logical_size):
    """Bound a splash in Logical Layout Space while preserving source DPR."""
    pixmap = QPixmap(source)
    available = QtCore.QSize(available_logical_size)
    if pixmap.isNull() or not available.isValid():
        return pixmap

    device_pixel_ratio = max(1.0, pixmap.devicePixelRatioF())
    logical_width = pixmap.width() / device_pixel_ratio
    logical_height = pixmap.height() / device_pixel_ratio
    if logical_width <= available.width() and logical_height <= available.height():
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
        if arg in {
            "--automation-startup-completion-marker",
            "--automation-pid-file",
            "--automation-smoke-log",
        }:
            index += 2
            continue
        if arg.startswith("-"):
            index += 1
            continue
        return arg
    return None


def _argument_value(argv, option):
    args = list(argv or [])
    if option not in args:
        return None
    index = args.index(option)
    if index + 1 >= len(args):
        raise SystemExit("%s requires a value." % option)
    return args[index + 1]


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
    from rc_metastudio import r_bridge

    def _status(message):
        if splash is not None:
            splash.showMessage(message)
        app.processEvents()

    _emit_automation_phase(phase_callback, "r-library-paths:start")
    r_bridge.get_r_library_paths()
    _emit_automation_phase(phase_callback, "r-library-paths:complete")
    rloader = r_bridge.RLibraryLoader()

    _status("Loading R libraries\n..")

    _status("Loading metafor\n....")
    _emit_automation_phase(phase_callback, "r-library:metafor:start")
    rloader.load_metafor()
    _emit_automation_phase(phase_callback, "r-library:metafor:complete")

    _status("Loading RCMetaR\n........")
    _emit_automation_phase(phase_callback, "r-library:RCMetaR:start")
    rloader.load_rcmetar()
    _emit_automation_phase(phase_callback, "r-library:RCMetaR:complete")

    _status("Loading igraph\n............")
    _emit_automation_phase(phase_callback, "r-library:igraph:start")
    rloader.load_igraph()
    _emit_automation_phase(phase_callback, "r-library:igraph:complete")

    _status("Loading grid\n................")
    _emit_automation_phase(phase_callback, "r-library:grid:start")
    rloader.load_grid()
    _emit_automation_phase(phase_callback, "r-library:grid:complete")

    from rc_metastudio import main_window

    if not main_window.NETWORK_ANALYSIS_DISABLED:
        _status("Loading gemtc\n...................")
        rloader.load_gemtc()


def start():
    qt6_resources.ensure_application_resources()
    app_error_handler.install_global_exception_handler()
    pid_path = os.environ.get("RCMS_AUTOMATION_PID_FILE")
    startup_argv = _resolve_startup_argv()
    pid_path = _argument_value(startup_argv, "--automation-pid-file") or pid_path
    if pid_path:
        Path(pid_path).write_text(str(os.getpid()) + "\n", encoding="utf-8")
    if (
        len(startup_argv) > 1
        and startup_argv[1].startswith("--automation-")
        and startup_argv[1] != "--automation-startup-project-smoke"
    ):
        from rc_metastudio import automation

        return automation.dispatch(startup_argv)
    startup_project_path = _startup_project_path(startup_argv)
    main_window = _import_main_window()
    app = app_error_handler.get_or_create_application(list(sys.argv))
    _configure_application(app)
    baseline_ids = _top_level_ids(app)
    try:
        settings.setup_directories()
        meta = _create_interactive_shell(app, main_window.MainWindow, load_R_libraries)
        if startup_project_path:
            opened = meta.open(startup_project_path)
            if (
                os.environ.get("RCMS_STARTUP_PROJECT_SMOKE") == "1"
                or "--automation-startup-project-smoke" in startup_argv
            ):
                from rc_metastudio.automation import (
                    assert_opened_project_for_startup_smoke,
                )

                return assert_opened_project_for_startup_smoke(
                    app,
                    meta,
                    startup_project_path,
                    opened,
                    completion_marker=_argument_value(
                        startup_argv, "--automation-startup-completion-marker"
                    ),
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


def _import_main_window():
    from rc_metastudio import main_window

    return main_window


if __name__ == "__main__":
    start()
