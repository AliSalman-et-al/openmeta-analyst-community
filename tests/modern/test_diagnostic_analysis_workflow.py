"""Regression tests for issue #53.

In the modern (PyQt5) build the diagnostic meta-analysis workflow dead-ended
silently: clicking "next >" in the Diagnostic Metrics dialog did nothing and
showed no error. Two distinct defects caused this:

1. ``Diag_Metrics.ok`` built ``MA_Specs`` directly, *without* the backend-error
   handling that the binary/continuous path uses. A backend failure raised out
   of the Qt slot and was swallowed by the event loop (no feedback at all).

2. ``MA_Specs.setup_diagnostic_ui`` called ``QApplication.translate`` with the
   old PyQt4 four-argument signature (``..., None, UnicodeUTF8``). PyQt5 rejects
   ``None`` for the 4th argument, so even with a working backend the dialog
   construction raised before it could be shown.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("OMA_STUB_BACKEND", "1")
sys.path.insert(0, os.path.abspath("src"))


REPO_ROOT = os.getcwd()


def _create_diagnostic_dataset(window):
    window._handle_wizard_results({
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
    })


def test_diagnostic_next_surfaces_backend_failure_instead_of_silent_dead_end():
    import launch

    app, window = launch.start_automation()
    meta_form = sys.modules["meta_form"]
    import diag_metrics
    import ma_specs

    original_specs = ma_specs.MA_Specs
    original_critical = meta_form.QMessageBox.critical
    shown = []
    try:
        _create_diagnostic_dataset(window)

        # Simulate the underlying backend failure (#51 analogue) raised while
        # building the Method & Parameters dialog.
        def _boom(*args, **kwargs):
            raise ValueError("simulated backend failure")

        ma_specs.MA_Specs = _boom
        # QMessageBox.critical (a modal exec) aborts under the offscreen
        # platform, so record the call instead of actually showing it.
        meta_form.QMessageBox.critical = staticmethod(
            lambda *args, **kwargs: shown.append(args))

        form = diag_metrics.Diag_Metrics(window.model, parent=window)

        # The bug: this used to raise out of the slot with no user feedback.
        form.ok()

        assert shown, "diagnostic next > swallowed the backend error silently"
        assert shown[0][1] == "Analysis backend unavailable"
    finally:
        ma_specs.MA_Specs = original_specs
        meta_form.QMessageBox.critical = original_critical
        _close_without_prompt(app, window)


def test_diagnostic_method_dialog_builds_with_working_backend():
    import launch

    app, window = launch.start_automation()
    import ma_specs

    backend = ma_specs.meta_py_r
    saved = {name: getattr(backend, name) for name in
             ("get_available_methods", "get_params", "get_method_description",
              "ma_dataset_to_simple_diagnostic_robj")}
    try:
        _create_diagnostic_dataset(window)

        # Minimal working-backend stub so construction reaches the diagnostic UI
        # setup (and the previously-broken translate() call) without real R.
        # populate_cbo_box builds the R data object for feasibility checks, so
        # that entry point has to be stubbed too.
        backend.ma_dataset_to_simple_diagnostic_robj = lambda model, **kwargs: None
        backend.get_available_methods = lambda **kwargs: {
            "Bivariate (Maximum Likelihood)": "diagnostic.hsroc",
            "HSROC": "diagnostic.hsroc",
            "Diagnostic Random-Effects": "diagnostic.random",
        }
        backend.get_params = lambda method: ({}, {}, [], {})
        backend.get_method_description = lambda method: "stub method"

        form = window._build_analysis_specs_dialog(
            diag_metrics=["sens", "spec"],
            conf_level=window.model.get_global_conf_level(),
        )

        # Construction succeeded (no swallowed exception) and the diagnostic
        # window title was set via the PyQt5-compatible translate() call.
        assert form is not None
        assert str(form.windowTitle()) == "Method & Parameters for Sens./Spec."
    finally:
        for name, value in saved.items():
            setattr(backend, name, value)
        _close_without_prompt(app, window)


def test_diagnostic_backend_failure_does_not_open_empty_results(monkeypatch):
    import launch

    app, window = launch.start_automation()
    import ma_specs

    backend = ma_specs.meta_py_r
    saved = {name: getattr(backend, name) for name in
             ("get_available_methods", "get_params", "get_method_description",
              "ma_dataset_to_simple_diagnostic_robj", "run_diagnostic_multi",
              "reset_Rs_working_dir")}
    shown = []
    results = []
    try:
        _create_diagnostic_dataset(window)

        backend.ma_dataset_to_simple_diagnostic_robj = lambda model, **kwargs: None
        backend.get_available_methods = lambda **kwargs: {
            "Diagnostic Random-Effects": "diagnostic.random",
        }
        backend.get_params = lambda method: ({}, {}, [], {})
        backend.get_method_description = lambda method: "stub method"
        backend.run_diagnostic_multi = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("simulated diagnostic failure"))
        backend.reset_Rs_working_dir = lambda: None
        monkeypatch.setattr(ma_specs.QMessageBox, "critical",
                            lambda *args, **kwargs: shown.append(args))
        monkeypatch.setattr(window, "analysis", lambda result: results.append(result))

        form = window._build_analysis_specs_dialog(
            diag_metrics=["lr", "dor"],
            conf_level=window.model.get_global_conf_level(),
        )

        form.run_ma()

        assert shown, "diagnostic backend failure did not surface an error"
        assert results == []
    finally:
        for name, value in saved.items():
            setattr(backend, name, value)
        _close_without_prompt(app, window)


def test_diagnostic_direct_effects_build_analysis_data_per_metric(monkeypatch):
    import launch

    app, window = launch.start_automation()
    import ma_specs

    backend = ma_specs.meta_py_r
    saved = {name: getattr(backend, name, None) for name in
             ("get_available_methods", "get_params", "get_method_description",
              "ma_dataset_to_simple_diagnostic_robj", "run_diagnostic_multi",
              "run_diagnostic_multi_for_entered_effects")}
    built_metrics = []
    multi_calls = []
    results = []
    try:
        _create_diagnostic_dataset(window)

        monkeypatch.setattr(window.model, "included_studies_have_raw_data",
                            lambda: False)
        monkeypatch.setattr(window.model, "included_studies_have_point_estimates",
                            lambda effect=None: effect in ("Sens", "Spec"))

        backend.get_available_methods = lambda **kwargs: {
            "Diagnostic Random-Effects": "diagnostic.random",
        }
        backend.get_params = lambda method: ({}, {}, [], {})
        backend.get_method_description = lambda method: "stub method"

        def build_metric(model, **kwargs):
            built_metrics.append(kwargs.get("metric", "Sens"))

        def run_metric(method_names, param_vals):
            multi_calls.append((list(method_names), [dict(p) for p in param_vals]))
            return {
                "texts": {
                    "%s Summary" % param_vals[0]["measure"]: "ok",
                },
                "images": {},
                "image_var_names": {},
                "image_params_paths": {},
                "image_order": None,
            }

        backend.ma_dataset_to_simple_diagnostic_robj = build_metric
        backend.run_diagnostic_multi = run_metric
        monkeypatch.setattr(window, "analysis", lambda result: results.append(result))

        form = window._build_analysis_specs_dialog(
            diag_metrics=["sens", "spec"],
            conf_level=window.model.get_global_conf_level(),
        )
        built_metrics[:] = []

        form.run_ma()

        assert built_metrics == ["Sens", "Spec"]
        assert [call[1][0]["measure"] for call in multi_calls] == ["Sens", "Spec"]
        assert results and sorted(results[0]["texts"]) == ["Sens Summary", "Spec Summary"]
    finally:
        for name, value in saved.items():
            if value is None:
                try:
                    delattr(backend, name)
                except AttributeError:
                    pass
            else:
                setattr(backend, name, value)
        _close_without_prompt(app, window)


def _close_without_prompt(app, window):
    window.current_data_unsaved = False
    window.close()
    app.processEvents()
    os.chdir(REPO_ROOT)
