import os
import pickle
import sys


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("OMA_STUB_BACKEND", "1")
sys.path.insert(0, os.path.abspath("src"))

REPO_ROOT = os.getcwd()


def _create_binary_dataset(window):
    window._handle_wizard_results(
        {
            "path": "new_dataset",
            "outcome_info": {
                "arms": "two",
                "data_type": "binary",
                "sub_type": None,
                "effect": "OR",
                "metric_choices": [],
                "name": "Binary",
            },
            "csv_data": None,
            "selected_dataset": None,
        }
    )


def test_binary_analysis_failure_shows_dialog_and_does_not_open_results(monkeypatch):
    import launch
    import ma_specs

    app, window = launch.start_automation()
    backend = ma_specs.meta_py_r
    saved = {
        name: getattr(backend, name)
        for name in (
            "get_available_methods",
            "get_params",
            "get_method_description",
            "ma_dataset_to_simple_binary_robj",
            "run_binary_ma",
            "reset_Rs_working_dir",
        )
    }
    shown = []
    results = []
    try:
        _create_binary_dataset(window)

        backend.ma_dataset_to_simple_binary_robj = lambda model, **kwargs: None
        backend.get_available_methods = lambda **kwargs: {
            "Binary Random-Effects": "binary.random"
        }
        backend.get_params = lambda method: ({}, {}, [], {})
        backend.get_method_description = lambda method: "stub method"
        backend.run_binary_ma = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("simulated R failure")
        )
        backend.reset_Rs_working_dir = lambda: None

        monkeypatch.setattr(
            ma_specs.QMessageBox, "critical", lambda *args, **kwargs: shown.append(args)
        )
        monkeypatch.setattr(window, "analysis", lambda result: results.append(result))

        form = window._build_analysis_specs_dialog(
            conf_level=window.model.get_global_conf_level()
        )
        form.run_ma()

        assert shown
        assert shown[0][1] == "analysis failed"
        assert "simulated R failure" in shown[0][2]
        assert results == []
    finally:
        for name, value in saved.items():
            setattr(backend, name, value)
        _close_without_prompt(app, window)


def test_continuous_workflow_failure_shows_dialog_and_does_not_open_results(
    monkeypatch,
):
    import launch
    import ma_specs

    app, window = launch.start_automation()
    backend = ma_specs.meta_py_r
    saved = {
        name: getattr(backend, name)
        for name in (
            "get_available_methods",
            "get_params",
            "get_method_description",
            "ma_dataset_to_simple_continuous_robj",
            "run_workflow_analysis",
            "reset_Rs_working_dir",
        )
    }
    shown = []
    results = []
    try:
        window._handle_wizard_results(
            {
                "path": "new_dataset",
                "outcome_info": {
                    "arms": "two",
                    "data_type": "continuous",
                    "sub_type": None,
                    "effect": "SMD",
                    "metric_choices": [],
                    "name": "Continuous",
                },
                "csv_data": None,
                "selected_dataset": None,
            }
        )

        backend.ma_dataset_to_simple_continuous_robj = lambda model, **kwargs: None
        backend.get_available_methods = lambda **kwargs: {
            "Continuous Random-Effects": "continuous.random"
        }
        backend.get_params = lambda method: ({}, {}, [], {})
        backend.get_method_description = lambda method: "stub method"
        backend.run_workflow_analysis = lambda *args, **kwargs: (
            _ for _ in ()
        ).throw(RuntimeError("simulated recompute failure"))
        backend.reset_Rs_working_dir = lambda: None

        monkeypatch.setattr(
            ma_specs.QMessageBox, "critical", lambda *args, **kwargs: shown.append(args)
        )
        monkeypatch.setattr(window, "analysis", lambda result: results.append(result))

        form = window._build_analysis_specs_dialog(
            meta_f_str="leave-one-out",
            conf_level=window.model.get_global_conf_level(),
        )
        form.run_ma()

        assert shown
        assert "simulated recompute failure" in shown[0][2]
        assert results == []
    finally:
        for name, value in saved.items():
            setattr(backend, name, value)
        _close_without_prompt(app, window)


def test_method_parameters_build_failure_reports_preparation_error(monkeypatch):
    import launch
    import ma_specs
    import meta_form

    app, window = launch.start_automation()
    shown = []
    try:
        _create_binary_dataset(window)

        def _boom(*args, **kwargs):
            raise TypeError("study name is missing")

        monkeypatch.setattr(ma_specs, "MA_Specs", _boom)
        monkeypatch.setattr(
            meta_form.QMessageBox,
            "critical",
            lambda *args, **kwargs: shown.append(args),
        )

        form = window._build_analysis_specs_dialog(
            conf_level=window.model.get_global_conf_level()
        )

        assert form is None
        assert shown
        assert shown[0][1] == "Could not prepare analysis"
        assert "study name is missing" in shown[0][2]
        assert "backend is not available" not in shown[0][2]
    finally:
        _close_without_prompt(app, window)


def test_method_parameters_backend_unavailable_keeps_backend_error(monkeypatch):
    import launch
    import meta_form

    app, window = launch.start_automation()
    shown = []
    try:
        _create_binary_dataset(window)
        monkeypatch.setattr(
            meta_form.QMessageBox,
            "critical",
            lambda *args, **kwargs: shown.append(args),
        )

        form = window._build_analysis_specs_dialog(
            conf_level=window.model.get_global_conf_level()
        )

        assert form is None
        assert shown
        assert shown[0][1] == "Analysis backend unavailable"
        assert "could not be reached" in shown[0][2]
        assert "not available in this modern build" not in shown[0][2]
    finally:
        _close_without_prompt(app, window)


def test_results_window_accepts_incomplete_result_payload():
    from PyQt5.QtWidgets import QApplication

    import results_window

    app = QApplication.instance() or QApplication([])
    window = results_window.ResultsWindow({"texts": {}})
    try:
        assert window.texts == {"No Results": results_window.NO_RESULTS_MESSAGE}
        assert window.images == {}
    finally:
        window.close()
        app.processEvents()


def test_results_window_build_failure_reports_display_error(monkeypatch):
    import launch
    import meta_form

    app, window = launch.start_automation()
    shown = []
    try:
        def _boom(*args, **kwargs):
            raise RuntimeError("plot image could not be loaded")

        monkeypatch.setattr(meta_form.results_window, "ResultsWindow", _boom)
        monkeypatch.setattr(
            meta_form.QMessageBox,
            "critical",
            lambda *args, **kwargs: shown.append(args),
        )

        window.analysis({"texts": {"Summary": "ok"}, "images": {}})

        assert shown
        assert shown[0][1] == "Could not display analysis results"
        assert "plot image could not be loaded" in shown[0][2]
        assert "analysis could not be completed" not in shown[0][2]
    finally:
        _close_without_prompt(app, window)


def test_project_save_failure_reports_original_error(monkeypatch, tmp_path):
    import launch
    import meta_form

    app, window = launch.start_automation()
    shown = []
    try:
        window.out_path = str(tmp_path / "project.oma")

        def _boom(*args, **kwargs):
            raise OSError("disk is full")

        monkeypatch.setattr(meta_form.pickle, "dump", _boom)
        monkeypatch.setattr(
            meta_form.QMessageBox,
            "critical",
            lambda *args, **kwargs: shown.append(args),
        )

        assert window.save() is False
        assert shown
        assert shown[0][1] == "Could not save project"
        assert "disk is full" in shown[0][2]
        assert "whoops" not in shown[0][2].lower()
    finally:
        _close_without_prompt(app, window)


def test_opening_pickled_non_dataset_reports_invalid_project(monkeypatch, tmp_path):
    import launch
    import meta_form

    invalid_project = tmp_path / "not-a-dataset.oma"
    invalid_project.write_bytes(pickle.dumps({"not": "a dataset"}, protocol=2))

    app, window = launch.start_automation()
    shown = []
    try:
        window.current_data_unsaved = False
        monkeypatch.setattr(
            meta_form.QMessageBox,
            "critical",
            lambda *args, **kwargs: shown.append(args),
        )

        assert window.open(str(invalid_project)) is None

        assert shown
        assert shown[0][1] == "Could not open project"
        assert "is not a valid OpenMeta[Analyst] project file" in shown[0][2]
        assert "get_outcome_names" not in shown[0][2]
        assert window.out_path is None
    finally:
        _close_without_prompt(app, window)


def test_global_exception_handler_logs_trace_and_shows_recoverable_dialog(
    monkeypatch, tmp_path
):
    from PyQt5.QtWidgets import QApplication

    import app_error_handler

    app = QApplication.instance() or QApplication([])
    log_path = tmp_path / "openmeta-analyst-error.log"
    shown = []
    monkeypatch.setattr(app_error_handler, "exception_log_path", lambda: str(log_path))
    monkeypatch.setattr(
        app_error_handler.QMessageBox,
        "critical",
        lambda *args, **kwargs: shown.append(args),
    )

    try:
        raise RuntimeError("slot exploded")
    except RuntimeError as e:
        app_error_handler.handle_exception(type(e), e, e.__traceback__)

    assert shown
    assert shown[0][1] == app_error_handler.UNEXPECTED_ERROR_TITLE
    assert "slot exploded" in log_path.read_text(encoding="utf-8")
    app.processEvents()


def test_main_window_action_exceptions_are_recoverable(monkeypatch, tmp_path):
    from PyQt5.QtWidgets import QAction

    import launch
    import app_error_handler
    import meta_form

    app, window = launch.start_automation()
    log_path = tmp_path / "openmeta-analyst-error.log"
    shown = []
    try:
        monkeypatch.setattr(
            app_error_handler, "exception_log_path", lambda: str(log_path)
        )
        monkeypatch.setattr(
            app_error_handler.QMessageBox,
            "critical",
            lambda *args, **kwargs: shown.append(args),
        )
        action = QAction(window)
        meta_form._connect_action(
            action,
            lambda: (_ for _ in ()).throw(RuntimeError("action exploded")),
        )

        action.trigger()
        app.processEvents()

        assert shown
        assert shown[0][1] == app_error_handler.UNEXPECTED_ERROR_TITLE
        assert "action exploded" in log_path.read_text(encoding="utf-8")
    finally:
        _close_without_prompt(app, window)


def test_safe_application_notify_reports_event_handler_exceptions(
    monkeypatch, tmp_path
):
    from PyQt5.QtCore import QEvent
    from PyQt5.QtWidgets import QWidget

    import app_error_handler

    app = app_error_handler.get_or_create_application([])
    log_path = tmp_path / "openmeta-analyst-error.log"
    shown = []
    monkeypatch.setattr(app_error_handler, "exception_log_path", lambda: str(log_path))
    monkeypatch.setattr(
        app_error_handler.QMessageBox,
        "critical",
        lambda *args, **kwargs: shown.append(args),
    )

    class RaisingWidget(QWidget):
        def event(self, event):
            raise RuntimeError("event exploded")

    widget = RaisingWidget()
    try:
        assert app.notify(widget, QEvent(QEvent.User)) is False
        assert shown
        assert "event exploded" in log_path.read_text(encoding="utf-8")
    finally:
        widget.close()
        app.processEvents()


def _close_without_prompt(app, window):
    window.current_data_unsaved = False
    window.close()
    app.processEvents()
    os.chdir(REPO_ROOT)
