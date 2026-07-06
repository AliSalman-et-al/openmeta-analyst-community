import os
import pickle
import sys

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RCMS_STUB_BACKEND", "1")
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
        assert shown[0][1] == "Analysis Failed"
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
        backend.run_workflow_analysis = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("simulated recompute failure")
        )
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


def test_diagnostic_progress_dialog_closes_when_run_setup_raises(monkeypatch):
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
            "ma_dataset_to_simple_diagnostic_robj",
        )
    }
    progress_events = []

    class ProgressSpy(object):
        def __init__(self, parent=None):
            self.parent = parent

        def show(self):
            progress_events.append("show")

        def hide(self):
            progress_events.append("hide")

    try:
        window._handle_wizard_results(
            {
                "path": "new_dataset",
                "outcome_info": {
                    "arms": "two",
                    "data_type": "diagnostic",
                    "sub_type": None,
                    "effect": "Sens",
                    "metric_choices": [],
                    "name": "Accuracy",
                },
                "csv_data": None,
                "selected_dataset": None,
            }
        )

        backend.ma_dataset_to_simple_diagnostic_robj = lambda model, **kwargs: None
        backend.get_available_methods = lambda **kwargs: {
            "HSROC": "diagnostic.hsroc",
            "Diagnostic Random-Effects": "diagnostic.random",
        }
        backend.get_params = lambda method: ({}, {}, [], {})
        backend.get_method_description = lambda method: "stub method"
        monkeypatch.setattr(ma_specs, "MetaProgress", ProgressSpy)
        monkeypatch.setattr(
            ma_specs,
            "add_plot_params",
            lambda specs_form: (_ for _ in ()).throw(
                RuntimeError("simulated setup failure")
            ),
        )

        form = window._build_analysis_specs_dialog(
            diag_metrics=["sens", "spec"],
            conf_level=window.model.get_global_conf_level(),
        )

        with pytest.raises(RuntimeError, match="simulated setup failure"):
            form.run_ma()

        assert progress_events == ["show", "hide"]
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
        assert shown[0][1] == "Could Not Prepare Analysis"
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
        assert shown[0][1] == "Analysis Backend Unavailable"
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
        assert shown[0][1] == "Could Not Display Analysis Results"
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
        window.out_path = str(tmp_path / "project.rcms")

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
        assert shown[0][1] == "Could Not Save Project"
        assert "disk is full" in shown[0][2]
        assert "whoops" not in shown[0][2].lower()
    finally:
        _close_without_prompt(app, window)


def test_opening_pickled_non_dataset_reports_invalid_project(monkeypatch, tmp_path):
    import launch
    import meta_form

    invalid_project = tmp_path / "not-a-dataset.rcms"
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
        assert shown[0][1] == "Could Not Open Project"
        assert "is not a valid RC MetaStudio project file" in shown[0][2]
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
    log_path = tmp_path / "rc-metastudio-error.log"
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


def test_safe_signal_connection_replaces_and_disconnects_wrapped_slots():
    from PyQt5.QtCore import QObject, pyqtSignal

    import app_error_handler

    class Emitter(QObject):
        fired = pyqtSignal()

    emitter = Emitter()
    calls = []

    connection = app_error_handler.connect_safely(
        emitter.fired, lambda: calls.append("first")
    )
    emitter.fired.emit()

    connection.replace(lambda: calls.append("second"))
    emitter.fired.emit()

    connection.disconnect()
    emitter.fired.emit()

    assert calls == ["first", "second"]


def test_safe_slot_discards_surplus_signal_arguments(monkeypatch):
    import app_error_handler

    unexpected_errors = []
    calls = []
    monkeypatch.setattr(
        app_error_handler,
        "handle_exception",
        lambda *args, **kwargs: unexpected_errors.append(args),
    )

    app_error_handler.safe_slot(lambda: calls.append("no-args"))(True)
    app_error_handler.safe_slot(lambda checked: calls.append(checked))(True, "extra")

    assert calls == ["no-args", True]
    assert unexpected_errors == []


def test_safe_slot_preserves_callback_type_errors(monkeypatch):
    import app_error_handler

    unexpected_errors = []
    monkeypatch.setattr(
        app_error_handler,
        "handle_exception",
        lambda *args, **kwargs: unexpected_errors.append(args),
    )

    def callback(_checked):
        raise TypeError("internal type problem")

    app_error_handler.safe_slot(callback)(True, "extra")

    assert unexpected_errors
    assert unexpected_errors[0][0] is TypeError
    assert str(unexpected_errors[0][1]) == "internal type problem"


def test_meta_reg_covariate_toggles_refresh_ok_button_without_unexpected_error(
    monkeypatch,
):
    from PyQt5.QtWidgets import QApplication, QDialogButtonBox

    import app_error_handler
    import meta_globals
    import meta_reg_form

    class Covariate(object):
        def __init__(self, name):
            self.name = name
            self.data_type = meta_globals.CONTINUOUS

    class Study(object):
        def __init__(self):
            self.covariate_dict = {"Dose": 1.0, "Age": 2.0}

    class Dataset(object):
        covariates = [Covariate("Dose"), Covariate("Age")]

    class Model(object):
        dataset = Dataset()

        def get_studies(self, only_if_included=True):
            return [Study()]

        def get_current_outcome_type(self):
            return "binary"

    app = QApplication.instance() or QApplication([])
    unexpected_errors = []
    monkeypatch.setattr(
        app_error_handler,
        "handle_exception",
        lambda *args, **kwargs: unexpected_errors.append(args),
    )

    form = meta_reg_form.MetaRegForm(Model())
    try:
        ok_button = form.buttonBox.button(QDialogButtonBox.Ok)
        assert ok_button.isEnabled() is True

        for _covariate, checkbox in form.covs_and_check_boxes:
            checkbox.setChecked(False)
            app.processEvents()
            assert unexpected_errors == []

        assert ok_button.isEnabled() is False

        form.covs_and_check_boxes[0][1].setChecked(True)
        app.processEvents()

        assert unexpected_errors == []
        assert ok_button.isEnabled() is True
    finally:
        form.close()
        app.processEvents()


def test_metaform_model_reconnect_preserves_external_signal_subscribers():
    import launch

    app, window = launch.start_automation()
    calls = []
    try:
        window.tableView.dataDirtied.connect(lambda: calls.append("external"))

        _create_binary_dataset(window)
        window.tableView.dataDirtied.emit()

        assert calls == ["external"]
    finally:
        _close_without_prompt(app, window)


def test_main_window_action_exceptions_are_recoverable(monkeypatch, tmp_path):
    from PyQt5.QtWidgets import QAction

    import launch
    import app_error_handler
    import meta_form

    app, window = launch.start_automation()
    log_path = tmp_path / "rc-metastudio-error.log"
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
    log_path = tmp_path / "rc-metastudio-error.log"
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


def test_context_menu_popup_helper_ignores_reentrant_popups(monkeypatch):
    from PyQt5.QtCore import QPoint

    import app_error_handler

    popups = []

    class FakeSignal(object):
        def __init__(self):
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)

        def emit(self):
            for callback in self._callbacks:
                callback()

    class FakeEvent(object):
        def __init__(self):
            self.accepted = False

        def accept(self):
            self.accepted = True

    class FakeMenu(object):
        def __init__(self, name):
            self.name = name
            self.aboutToHide = FakeSignal()

        def popup(self, pos):
            popups.append((self.name, pos))

    monkeypatch.setattr(app_error_handler, "_active_context_menu", None)
    first_menu = FakeMenu("first")
    second_menu = FakeMenu("second")
    first_event = FakeEvent()
    second_event = FakeEvent()

    assert (
        app_error_handler.popup_context_menu(
            first_menu, QPoint(1, 2), event=first_event
        )
        is True
    )
    assert (
        app_error_handler.popup_context_menu(
            second_menu, QPoint(3, 4), event=second_event
        )
        is False
    )

    assert first_event.accepted is True
    assert second_event.accepted is True
    assert popups == [("first", QPoint(1, 2))]

    first_menu.aboutToHide.emit()
    assert app_error_handler.popup_context_menu(second_menu, QPoint(3, 4)) is True
    assert popups == [("first", QPoint(1, 2)), ("second", QPoint(3, 4))]


def test_context_menu_events_are_suppressed_while_menu_is_active(monkeypatch):
    from PyQt5.QtCore import QEvent

    import app_error_handler

    class FakeEvent(object):
        def type(self):
            return QEvent.ContextMenu

    monkeypatch.setattr(app_error_handler, "is_context_menu_active", lambda: True)

    assert app_error_handler.should_suppress_context_menu_event(FakeEvent()) is True


def test_context_menu_popup_failure_clears_active_guard(monkeypatch):
    from PyQt5.QtCore import QPoint

    import app_error_handler

    handled = []

    class FakeSignal(object):
        def connect(self, callback):
            pass

    class RaisingMenu(object):
        aboutToHide = FakeSignal()

        def popup(self, pos):
            raise RuntimeError("popup exploded")

    monkeypatch.setattr(app_error_handler, "_active_context_menu", None)
    monkeypatch.setattr(
        app_error_handler,
        "handle_exception",
        lambda *args, **kwargs: handled.append(args),
    )

    assert app_error_handler.popup_context_menu(RaisingMenu(), QPoint(1, 2)) is False

    assert handled
    assert app_error_handler._active_context_menu is None


def _close_without_prompt(app, window):
    window.current_data_unsaved = False
    window.close()
    app.processEvents()
    os.chdir(REPO_ROOT)
