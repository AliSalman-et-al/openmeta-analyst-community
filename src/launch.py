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
APPLICATION_ICON_PATH = ":/misc/meta.png"


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
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-wizard-layout-smoke":
        return start_wizard_layout_smoke()

    startup_project_path = _startup_project_path(startup_argv)
    meta_form = _import_meta_form()
    app = app_error_handler.get_or_create_application(list(sys.argv))
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
    _show_main_window(meta)
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
    sys.exit(app.exec())


def start_automation():
    app_error_handler.install_global_exception_handler()
    meta_form = _import_meta_form()
    app = app_error_handler.get_or_create_application(sys.argv)
    app.setApplicationName(meta_globals.APPLICATION_NAME)
    app.setOrganizationName(meta_globals.ORGANIZATION_NAME)
    _set_application_icon(app)
    settings.setup_directories()
    if os.environ.get("OMA_REQUIRE_IN_PROCESS_RPY2") == "1":
        load_R_libraries(app, None)
    meta = meta_form.MetaForm()
    _show_main_window(meta)
    return app, meta


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


def start_wizard_layout_smoke():
    app_error_handler.install_global_exception_handler()
    app = app_error_handler.get_or_create_application(sys.argv)
    app.setApplicationName(meta_globals.APPLICATION_NAME)
    app.setOrganizationName(meta_globals.ORGANIZATION_NAME)
    _set_application_icon(app)
    settings.setup_directories()

    import main_wizard

    parent_shell = QtWidgets.QMainWindow()
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
            _show_wizard_for_layout_smoke(app, wizard, scenario_name)
            for action, expected_page_id, value in actions:
                _advance_wizard_layout_smoke_page(
                    app, wizard, action, expected_page_id, value
                )
                _assert_wizard_layout_smoke_page(app, wizard, scenario_name)
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


def _assert_wizard_layout_smoke_page(app, wizard, scenario_name):
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
    if (
        wizard.parentWidget() is not None
        and wizard.width() > int(wizard.parentWidget().width() * 0.75)
    ):
        raise SystemExit(
            "Wizard layout smoke inherited parent shell width in %s: wizard=%s parent=%s"
            % (scenario_name, wizard.width(), wizard.parentWidget().width())
        )
    if page.width() < body_rect.width() - 4:
        raise SystemExit(
            "Wizard page leaves unused body width in %s: page=%s body=%s"
            % (scenario_name, page.width(), body_rect.width())
        )
    if page.height() < body_rect.height() - 4:
        raise SystemExit(
            "Wizard page leaves unused body height in %s: page=%s body=%s"
            % (scenario_name, page.height(), body_rect.height())
        )

    _assert_visible_children_inside_page(page, scenario_name)
    pixmap = wizard.grab()
    image = pixmap.toImage()
    if pixmap.isNull() or image.isNull() or image.width() <= 0 or image.height() <= 0:
        raise SystemExit("Wizard layout smoke could not render: %s" % scenario_name)


def _assert_visible_children_inside_page(page, scenario_name):
    page_rect = page.rect().adjusted(0, 0, 1, 1)
    for child in page.findChildren(QtWidgets.QWidget):
        if child is page or child.isWindow() or not child.isVisible():
            continue
        if not child.objectName():
            continue
        mapped_top_left = child.parentWidget().mapTo(page, child.geometry().topLeft())
        mapped_rect = child.geometry()
        mapped_rect.moveTopLeft(mapped_top_left)
        if not page_rect.contains(mapped_rect):
            raise SystemExit(
                "Wizard child is clipped in %s: %s"
                % (scenario_name, child.objectName() or child.__class__.__name__)
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
