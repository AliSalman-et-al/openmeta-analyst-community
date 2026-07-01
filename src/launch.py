import sys, time
from PyQt5 import QtWidgets
from PyQt5.QtCore import QThread
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QSplashScreen

import os

forms_path = os.path.join(os.path.dirname(__file__), "forms")
if forms_path not in sys.path:
    sys.path.insert(0, forms_path)

import meta_py_r_backend
import meta_globals

meta_py_r_backend.install_meta_py_r_backend()
import app_error_handler
import settings

SPLASH_DISPLAY_TIME = 0  # TODO: change to 5 seconds in production version
APPLICATION_ICON_PATH = ":/misc/meta.ico"


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
        if arg == "--automation-smoke":
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


def load_R_libraries(app, splash=None):
    """Loads the R libraries while updating the splash screen"""
    import meta_py_r

    def _status(message):
        if splash is not None:
            splash.showMessage(message)
        app.processEvents()

    meta_py_r.get_R_libpaths()  # print the lib paths
    rloader = meta_py_r.RlibLoader()

    _status("Loading R libraries\n..")

    _status("Loading metafor\n....")
    rloader.load_metafor()

    _status("Loading OpenMetaR\n........")
    rloader.load_OpenMetaR()

    _status("Loading igraph\n............")
    rloader.load_igraph()

    _status("Loading grid\n................")
    rloader.load_grid()

    import meta_form

    if not meta_form.DISABLE_NETWORK_STUFF:
        _status("Loading gemtc\n...................")
        rloader.load_gemtc()


def start():
    app_error_handler.install_global_exception_handler()
    startup_argv = _resolve_startup_argv()
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-smoke":
        sample_path = (
            startup_argv[2]
            if len(startup_argv) > 2
            else os.path.join("sample_data", "amino.oma")
        )
        return start_automation_smoke(sample_path)

    startup_project_path = _startup_project_path(startup_argv)
    meta_form = _import_meta_form()
    app = QtWidgets.QApplication(list(sys.argv))
    app.setApplicationName(meta_globals.APPLICATION_NAME)
    app.setOrganizationName(meta_globals.ORGANIZATION_NAME)
    _set_application_icon(app)
    settings.setup_directories()

    splash_pixmap = QPixmap(":/misc/splash.png")
    splash = QSplashScreen(splash_pixmap)
    splash.show()
    splash_starttime = time.time()

    load_R_libraries(app, splash)

    # Show splash screen for at least SPLASH_DISPLAY_TIME seconds
    time_elapsed = time.time() - splash_starttime
    print(("It took %s seconds to load the R libraries" % str(time_elapsed)))
    if time_elapsed < SPLASH_DISPLAY_TIME:  # seconds
        print(
            (
                "Going to sleep for %f seconds"
                % float(SPLASH_DISPLAY_TIME - time_elapsed)
            )
        )
        QThread.sleep(int(SPLASH_DISPLAY_TIME - time_elapsed))

    meta = meta_form.MetaForm()
    splash.finish(meta)
    meta.show()
    if startup_project_path:
        opened = meta.open(startup_project_path)
        if os.environ.get("OMA_STARTUP_PROJECT_SMOKE") == "1":
            return _assert_opened_project_for_startup_smoke(
                app, meta, startup_project_path, opened
            )
    else:
        if os.environ.get("OMA_STARTUP_PROJECT_SMOKE") == "1":
            raise SystemExit(
                "Startup project smoke test did not receive a project path."
            )
        meta.start()
    sys.exit(app.exec_())


def start_automation():
    app_error_handler.install_global_exception_handler()
    meta_form = _import_meta_form()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(meta_globals.APPLICATION_NAME)
    app.setOrganizationName(meta_globals.ORGANIZATION_NAME)
    _set_application_icon(app)
    settings.setup_directories()
    if os.environ.get("OMA_REQUIRE_IN_PROCESS_RPY2") == "1":
        load_R_libraries(app, None)
    meta = meta_form.MetaForm()
    meta.show()
    return app, meta


def _set_application_icon(app):
    app.setWindowIcon(QIcon(APPLICATION_ICON_PATH))


def start_automation_smoke(sample_path):
    app, meta = start_automation()
    try:
        sample_path = os.path.abspath(sample_path)
        if not meta.open(sample_path):
            raise SystemExit("Could not open smoke-test project: %s" % sample_path)
        app.processEvents()
        model = meta.tableView.model()
        if model is None or model.rowCount() < 1:
            raise SystemExit(
                "Smoke-test project opened without table rows: %s" % sample_path
            )

        # Force a real paint pass. Painting queries data()/headerData() for paint
        # roles (e.g. BackgroundColorRole) that offscreen layout never touches, so
        # this is what catches paint-time porting bugs in the packaged build. A
        # paint error aborts the process, failing the smoke test with a non-zero
        # exit code rather than shipping a build that crashes on first render.
        _force_table_paint(app, meta)
        _assert_standard_binary_summary_is_formatted(meta)
    finally:
        meta.close()
        app.processEvents()
    return 0


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
        " Model Results",
        "Estimate",
        "Lower bound",
        "Upper bound",
        "p-Value",
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


def _force_table_paint(app, meta):
    """Renders every cell and both headers so paint-time data() bugs surface here."""
    view = meta.tableView
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
