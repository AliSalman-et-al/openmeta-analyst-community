"""Regression tests for issue #53.

In the maintained PyQt5 build the diagnostic meta-analysis workflow dead-ended
silently: clicking "next >" in the Diagnostic Metrics dialog did nothing and
showed no error. Two distinct defects caused this:

1. ``Diag_Metrics.ok`` built ``MA_Specs`` directly, *without* the backend-error
   handling that the binary/continuous path uses. A backend failure raised out
   of the Qt slot and was swallowed by the event loop (no feedback at all).

2. ``MA_Specs.setup_diagnostic_ui`` called ``QApplication.translate`` with a
   removed four-argument signature. PyQt5 rejects that call shape, so even with
   a working backend the dialog construction raised before it could be shown.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RCMS_STUB_BACKEND", "1")
sys.path.insert(0, os.path.abspath("src"))


REPO_ROOT = os.getcwd()
ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault(
    "RCMS_QT6_BUILD_ROOT", str(ROOT / "build" / "qt6-verification")
)
from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()


def _create_diagnostic_dataset(window):
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


def test_diagnostic_next_surfaces_specs_failure_instead_of_silent_dead_end():
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

        # Simulate a Method & Parameters construction failure raised after the
        # diagnostic metrics dialog hands off to the shared builder.
        def _boom(*args, **kwargs):
            raise ValueError("simulated preparation failure")

        ma_specs.MA_Specs = _boom
        # QMessageBox.critical (a modal exec) aborts under the offscreen
        # platform, so record the call instead of actually showing it.
        meta_form.QMessageBox.critical = staticmethod(
            lambda *args, **kwargs: shown.append(args)
        )

        form = diag_metrics.Diag_Metrics(window.model, parent=window)

        # The bug: this used to raise out of the slot with no user feedback.
        form.ok()

        assert shown, "diagnostic next > swallowed the backend error silently"
        assert shown[0][1] == "Could Not Prepare Analysis"
        assert "simulated preparation failure" in shown[0][2]
        assert "backend is not available" not in shown[0][2]
    finally:
        ma_specs.MA_Specs = original_specs
        meta_form.QMessageBox.critical = original_critical
        _close_without_prompt(app, window)


def test_diagnostic_method_dialog_builds_with_working_backend(monkeypatch):
    import launch

    app, window = launch.start_automation()
    import ma_specs

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
        monkeypatch.setattr(
            backend,
            "get_analysis_plot_capabilities",
            lambda *args, **kwargs: [],
            raising=False,
        )

        form = window._build_analysis_specs_dialog(
            diag_metrics=["sens", "spec"],
            conf_level=window.model.get_global_conf_level(),
        )

        # Construction succeeded (no swallowed exception) and the diagnostic
        # window title was set via the PyQt5-compatible translate() call.
        assert form is not None
        assert str(form.windowTitle()) == (
            "Method & Parameters for Sensitivity and Specificity"
        )
    finally:
        for name, value in saved.items():
            setattr(backend, name, value)
        _close_without_prompt(app, window)


def test_diagnostic_method_dialog_opens_without_multiple_metrics_note(monkeypatch):
    import launch

    app, window = launch.start_automation()
    import diag_metrics
    import ma_specs

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
    try:
        _create_diagnostic_dataset(window)
        monkeypatch.setattr(
            window.model, "included_studies_have_raw_data", lambda: True
        )

        backend.ma_dataset_to_simple_diagnostic_robj = lambda model, **kwargs: None
        backend.get_available_methods = lambda **kwargs: {
            "Diagnostic Random-Effects": "diagnostic.random",
        }
        backend.get_params = lambda method: ({}, {}, [], {})
        backend.get_method_description = lambda method: "stub method"
        monkeypatch.setattr(
            backend,
            "get_analysis_plot_capabilities",
            lambda data_type, method, workflow="standard": [],
            raising=False,
        )

        metrics_form = diag_metrics.Diag_Metrics(window.model, parent=window)
        metrics_form.show()
        metrics_form.ok()
        app.processEvents()

        visible_dialog_titles = {
            str(widget.windowTitle())
            for widget in app.topLevelWidgets()
            if widget.isVisible()
        }

        assert "Method & Parameters" in visible_dialog_titles
        assert "Diagnostic MA with Multiple Metrics" not in visible_dialog_titles
        assert metrics_form.isVisible() is False
    finally:
        for name, value in saved.items():
            setattr(backend, name, value)
        _close_without_prompt(app, window)


def test_diagnostic_backend_failure_does_not_open_empty_results(monkeypatch):
    import launch

    app, window = launch.start_automation()
    import ma_specs

    backend = ma_specs.meta_py_r
    saved = {
        name: getattr(backend, name)
        for name in (
            "get_available_methods",
            "get_params",
            "get_method_description",
            "ma_dataset_to_simple_diagnostic_robj",
            "run_diagnostic_multi",
            "reset_Rs_working_dir",
        )
    }
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
        monkeypatch.setattr(
            backend,
            "get_analysis_plot_capabilities",
            lambda *args, **kwargs: [],
            raising=False,
        )
        backend.run_diagnostic_multi = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("simulated diagnostic failure")
        )
        backend.reset_Rs_working_dir = lambda: None
        monkeypatch.setattr(
            ma_specs.QMessageBox, "critical", lambda *args, **kwargs: shown.append(args)
        )
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


def test_diagnostic_multi_metric_failure_keeps_independent_results(monkeypatch):
    import launch

    app, window = launch.start_automation()
    import ma_specs

    backend = ma_specs.meta_py_r
    saved = {
        name: getattr(backend, name)
        for name in (
            "get_available_methods",
            "get_params",
            "get_method_description",
            "ma_dataset_to_simple_diagnostic_robj",
            "run_diagnostic_multi",
            "reset_Rs_working_dir",
        )
    }
    shown = []
    results = []
    try:
        _create_diagnostic_dataset(window)

        backend.ma_dataset_to_simple_diagnostic_robj = lambda model, **kwargs: None
        backend.get_available_methods = lambda **kwargs: {
            "HSROC": "diagnostic.hsroc",
            "Diagnostic Random-Effects": "diagnostic.random",
        }
        backend.get_params = lambda method: ({}, {}, [], {})
        backend.get_method_description = lambda method: "stub method"
        monkeypatch.setattr(
            backend,
            "get_analysis_plot_capabilities",
            lambda *args, **kwargs: [],
            raising=False,
        )
        backend.reset_Rs_working_dir = lambda: None

        def run_metric(method_names, param_vals):
            if len(param_vals) > 1:
                raise RuntimeError("combined diagnostic failure")
            metric = param_vals[0]["measure"]
            if metric == "Sens":
                raise RuntimeError("HSROC failed to converge")
            return {
                "texts": {
                    "%s Summary" % metric: "%s ok" % metric,
                },
                "images": {
                    "%s Forest plot" % metric: "%s.png" % metric.lower(),
                },
                "image_var_names": {},
                "image_params_paths": {},
                "image_order": ["%s Forest plot" % metric],
            }

        backend.run_diagnostic_multi = run_metric
        monkeypatch.setattr(
            ma_specs.QMessageBox, "critical", lambda *args, **kwargs: shown.append(args)
        )
        monkeypatch.setattr(window, "analysis", lambda result: results.append(result))

        form = window._build_analysis_specs_dialog(
            diag_metrics=["sens", "lr", "dor"],
            conf_level=window.model.get_global_conf_level(),
        )
        form.diag_metrics_to_analysis_details = {
            "Sens": ("diagnostic.hsroc", {"conf.level": 95.0}),
            "DOR": ("diagnostic.random", {"conf.level": 95.0}),
            "PLR": ("diagnostic.random", {"conf.level": 95.0}),
            "NLR": ("diagnostic.random", {"conf.level": 95.0}),
        }
        form.sens_spec = False
        form.lr_dor = True

        form.run_ma()

        assert shown == []
        assert len(results) == 1
        assert results[0]["texts"]["Sens Error"] == "HSROC failed to converge"
        assert results[0]["texts"]["DOR Summary"] == "DOR ok"
        assert results[0]["texts"]["PLR Summary"] == "PLR ok"
        assert results[0]["texts"]["NLR Summary"] == "NLR ok"
        assert results[0]["image_order"] == [
            "NLR Forest plot",
            "PLR Forest plot",
            "DOR Forest plot",
        ]
    finally:
        for name, value in saved.items():
            setattr(backend, name, value)
        _close_without_prompt(app, window)


def test_combined_diagnostic_metrics_use_one_method_dialog(monkeypatch):
    import launch

    app, window = launch.start_automation()
    import ma_specs
    import app_error_handler

    backend = ma_specs.meta_py_r
    saved = {
        name: getattr(backend, name)
        for name in (
            "get_available_methods",
            "get_params",
            "get_method_description",
            "ma_dataset_to_simple_diagnostic_robj",
            "run_diagnostic_multi",
            "reset_Rs_working_dir",
        )
    }
    unexpected_errors = []
    analysis_results = []
    run_calls = []
    try:
        _create_diagnostic_dataset(window)

        backend.ma_dataset_to_simple_diagnostic_robj = lambda model, **kwargs: None
        backend.get_available_methods = lambda **kwargs: {
            "Bivariate (Maximum Likelihood)": "diagnostic.bivariate.ml",
            "HSROC": "diagnostic.hsroc",
            "Diagnostic Random-Effects": "diagnostic.random",
        }

        def get_params(method):
            if method == "diagnostic.hsroc":
                return ({"num.iters": "int"}, {"num.iters": 5000}, ["num.iters"], {})
            if method == "diagnostic.random":
                definitions = {
                    "rm.method": ["DL", "REML"],
                    "conf.level": "float",
                    "digits": "int",
                    "adjust": "float",
                    "to": ["only0", "all"],
                }
                defaults = {
                    "rm.method": "DL",
                    "conf.level": 95.0,
                    "digits": 2,
                    "adjust": 0.5,
                    "to": "only0",
                }
                return (definitions, defaults, list(definitions), {})
            definitions = {
                "conf.level": "float",
                "adjust": "float",
                "to": ["only0", "all"],
            }
            defaults = {"conf.level": 95.0, "adjust": 0.5, "to": "only0"}
            return (definitions, defaults, list(definitions), {})

        backend.get_params = get_params
        backend.get_method_description = lambda method: "stub method"
        monkeypatch.setattr(
            backend,
            "get_analysis_plot_capabilities",
            lambda *args, **kwargs: [],
            raising=False,
        )
        def run_diagnostic(*args, **kwargs):
            run_calls.append(args)
            return {
                "texts": {},
                "images": {},
                "image_var_names": {},
                "image_params_paths": {},
                "image_order": [],
            }

        backend.run_diagnostic_multi = run_diagnostic
        backend.reset_Rs_working_dir = lambda: None
        monkeypatch.setattr(
            app_error_handler,
            "handle_exception",
            lambda *args, **kwargs: unexpected_errors.append(args),
        )
        monkeypatch.setattr(
            window, "analysis", lambda result: analysis_results.append(result)
        )
        preparation_errors = []
        monkeypatch.setattr(
            window,
            "_show_analysis_specs_error",
            lambda error: preparation_errors.append(error),
        )

        form = window._build_analysis_specs_dialog(
            diag_metrics=["sens", "spec", "lr", "dor"],
            conf_level=window.model.get_global_conf_level(),
        )
        assert preparation_errors == [], "".join(
            __import__("traceback").format_exception(preparation_errors[0])
        )
        assert form is not None
        form.method_cbo_box.setCurrentText("HSROC")
        form.lr_dor_method_cbo_box.setCurrentText("Diagnostic Random-Effects")
        form.current_param_vals.update(
            {"conf.level": 90.0, "digits": 4, "adjust": 0.25, "to": "all"}
        )
        form.lr_dor_panel.params["rm.method"] = "REML"
        form.add_cur_analysis_details()

        assert form.windowTitle() == "Method & Parameters"
        assert (
            form.buttonBox.button(
                ma_specs.QDialogButtonBox.StandardButton.Ok
            )
            is not None
        )
        assert form.method_lbl.text() == "Sensitivity and Specificity"
        assert form.lr_dor_method_lbl.text() == (
            "Likelihood Ratios and Diagnostic Odds Ratio"
        )
        assert not any(button.text() == "next >" for button in form.buttonBox.buttons())
        sens_method, sens_params = form.diag_metrics_to_analysis_details["Sens"]
        dor_method, dor_params = form.diag_metrics_to_analysis_details["DOR"]
        assert sens_method == "diagnostic.hsroc"
        assert sens_params == {"num.iters": 5000}
        assert dor_method == "diagnostic.random"
        assert dor_params == {
            "rm.method": "REML",
            "conf.level": 90.0,
            "digits": 4,
            "adjust": 0.25,
            "to": "all",
        }
        monkeypatch.setattr(
            ma_specs,
            "MA_Specs",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("opened a second Method & Parameters dialog")
            ),
        )
        form.buttonBox.accepted.emit()
        app.processEvents()

        assert unexpected_errors == []
        assert len(analysis_results) == 1
        assert run_calls
    finally:
        for name, value in saved.items():
            setattr(backend, name, value)
        _close_without_prompt(app, window)


def test_per_metric_diagnostic_merge_preserves_display_artifacts():
    import analysis_adapter
    import ma_specs

    def run_metric(request):
        metric = request.metric
        title = "%s Forest Plot" % metric
        return {
            "texts": {"%s Summary" % metric: "%s ok" % metric},
            "images": {title: "%s.png" % metric.lower()},
            "display_images": {title: "%s.display.svg" % metric.lower()},
            "image_var_names": {},
            "image_params_paths": {},
            "plot_capabilities": {
                title: {
                    "plot_kind": "forest",
                    "editable": False,
                    "styleable": True,
                    "composition": "single",
                    "regenerator": "forest",
                }
            },
            "image_order": [title],
        }

    result = ma_specs._run_diagnostic_methods_per_metric(
        tuple(
            analysis_adapter.make_analysis_request(
                data_type="diagnostic",
                workflow="standard",
                method="diagnostic.random",
                metric=metric,
                parameters={"measure": metric},
            )
            for metric in ("Sens", "Spec")
        ),
        run_metric,
    )

    assert result["display_images"] == {
        "Sens Forest Plot": "sens.display.svg",
        "Spec Forest Plot": "spec.display.svg",
    }


def test_combined_diagnostic_configuration_returns_typed_analysis_requests(monkeypatch):
    import launch

    app, window = launch.start_automation()
    import analysis_adapter
    import ma_specs

    backend = ma_specs.meta_py_r
    saved = {
        name: getattr(backend, name)
        for name in (
            "get_available_methods",
            "get_params",
            "get_method_description",
            "ma_dataset_to_simple_diagnostic_robj",
            "run_diagnostic_multi",
            "reset_Rs_working_dir",
        )
    }
    try:
        _create_diagnostic_dataset(window)

        backend.ma_dataset_to_simple_diagnostic_robj = lambda model, **kwargs: None
        backend.get_available_methods = lambda **kwargs: {
            "HSROC": "diagnostic.hsroc",
            "Diagnostic Random-Effects": "diagnostic.random",
        }
        backend.get_params = lambda method: (
            {"conf.level": "float"},
            {"conf.level": 95.0},
            ["conf.level"],
            {},
        )
        backend.get_method_description = lambda method: "stub method"
        monkeypatch.setattr(
            backend,
            "get_analysis_plot_capabilities",
            lambda *args, **kwargs: [],
            raising=False,
        )
        backend.reset_Rs_working_dir = lambda: None

        form = window._build_analysis_specs_dialog(
            diag_metrics=["sens", "spec", "lr", "dor"],
            conf_level=window.model.get_global_conf_level(),
        )
        requests = form.analysis_requests()

        assert all(
            isinstance(request, analysis_adapter.AnalysisRequest)
            for request in requests
        )
        assert [request.metric for request in requests] == [
            "Sens",
            "Spec",
            "NLR",
            "PLR",
            "DOR",
        ]
        assert all(request.workflow == "standard" for request in requests)
        assert all(
            isinstance(request.parameter_values()["conf.level"], float)
            for request in requests
        )
    finally:
        for name, value in saved.items():
            setattr(backend, name, value)
        _close_without_prompt(app, window)


def test_diagnostic_direct_effects_build_analysis_data_per_metric(monkeypatch):
    import launch

    app, window = launch.start_automation()
    import ma_specs

    backend = ma_specs.meta_py_r
    saved = {
        name: getattr(backend, name, None)
        for name in (
            "get_available_methods",
            "get_params",
            "get_method_description",
            "ma_dataset_to_simple_diagnostic_robj",
            "run_diagnostic_multi",
            "run_diagnostic_multi_for_entered_effects",
        )
    }
    built_metrics = []
    multi_calls = []
    results = []
    try:
        _create_diagnostic_dataset(window)

        monkeypatch.setattr(
            window.model, "included_studies_have_raw_data", lambda: False
        )
        monkeypatch.setattr(
            window.model,
            "included_studies_have_point_estimates",
            lambda effect=None: effect in ("Sens", "Spec"),
        )

        backend.get_available_methods = lambda **kwargs: {
            "Diagnostic Random-Effects": "diagnostic.random",
        }
        backend.get_params = lambda method: ({}, {}, [], {})
        backend.get_method_description = lambda method: "stub method"
        monkeypatch.setattr(
            backend,
            "get_analysis_plot_capabilities",
            lambda *args, **kwargs: [],
            raising=False,
        )

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
        assert results and sorted(results[0]["texts"]) == [
            "Sens Summary",
            "Spec Summary",
        ]
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


def test_diagnostic_metric_dialog_defaults_to_supported_direct_effects(monkeypatch):
    import launch

    app, window = launch.start_automation()
    import diag_metrics

    captured = []

    class _ShownForm(object):
        def show(self):
            pass

    try:
        _create_diagnostic_dataset(window)

        monkeypatch.setattr(
            window.model, "included_studies_have_raw_data", lambda: False
        )
        monkeypatch.setattr(
            window.model,
            "included_studies_have_point_estimates",
            lambda effect=None: effect in ("Sens", "Spec"),
        )
        monkeypatch.setattr(
            window,
            "_build_analysis_specs_dialog",
            lambda **kwargs: captured.append(kwargs) or _ShownForm(),
        )

        form = diag_metrics.Diag_Metrics(window.model, parent=window)

        assert form.get_selected_metrics() == ["sens", "spec"]
        assert not form.chk_box_lr.isChecked()
        assert not form.chk_box_lr.isEnabled()
        assert not form.chk_box_dor.isChecked()
        assert not form.chk_box_dor.isEnabled()

        form.ok()

        assert captured[0]["diag_metrics"] == ["sens", "spec"]
    finally:
        _close_without_prompt(app, window)


def test_diagnostic_metric_dialog_does_not_run_without_selected_metrics(monkeypatch):
    import launch

    app, window = launch.start_automation()
    import diag_metrics

    warnings = []
    captured = []

    try:
        _create_diagnostic_dataset(window)

        monkeypatch.setattr(
            window.model, "included_studies_have_raw_data", lambda: False
        )
        monkeypatch.setattr(
            window.model,
            "included_studies_have_point_estimates",
            lambda effect=None: False,
        )
        monkeypatch.setattr(
            window,
            "_build_analysis_specs_dialog",
            lambda **kwargs: captured.append(kwargs),
        )
        monkeypatch.setattr(
            diag_metrics.QMessageBox,
            "warning",
            lambda *args: warnings.append(args),
        )

        form = diag_metrics.Diag_Metrics(window.model, parent=window)

        assert form.get_selected_metrics() == []
        assert form.btn_ok.isEnabled() is False

        form.ok()

        assert captured == []
        assert warnings
        assert warnings[0][1:3] == (
            "No Diagnostic Metric Selected",
            "Select at least one available diagnostic metric before running analysis.",
        )
    finally:
        _close_without_prompt(app, window)


def test_diagnostic_metric_toggles_refresh_ok_button_without_unexpected_error(
    monkeypatch,
):
    import launch

    app, window = launch.start_automation()
    import app_error_handler
    import diag_metrics

    unexpected_errors = []
    try:
        _create_diagnostic_dataset(window)
        monkeypatch.setattr(
            window.model, "included_studies_have_raw_data", lambda: True
        )
        monkeypatch.setattr(
            app_error_handler,
            "handle_exception",
            lambda *args, **kwargs: unexpected_errors.append(args),
        )

        form = diag_metrics.Diag_Metrics(window.model, parent=window)

        assert form.btn_ok.isEnabled() is True
        for metric in form.SELECTABLE_METRICS:
            form._metric_checkbox(metric).setChecked(False)
            app.processEvents()
            assert unexpected_errors == []

        assert form.btn_ok.isEnabled() is False

        form.chk_box_sens.setChecked(True)
        app.processEvents()

        assert unexpected_errors == []
        assert form.btn_ok.isEnabled() is True
    finally:
        _close_without_prompt(app, window)


def test_diagnostic_direct_effects_do_not_offer_count_based_methods(monkeypatch):
    import launch

    app, window = launch.start_automation()
    import ma_specs

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
    try:
        _create_diagnostic_dataset(window)

        monkeypatch.setattr(
            window.model, "included_studies_have_raw_data", lambda: False
        )
        monkeypatch.setattr(
            window.model,
            "included_studies_have_point_estimates",
            lambda effect=None: effect in ("Sens", "Spec"),
        )

        backend.ma_dataset_to_simple_diagnostic_robj = lambda model, **kwargs: None
        backend.get_available_methods = lambda **kwargs: {
            "Bivariate (Maximum Likelihood)": "diagnostic.bivariate.ml",
            "HSROC": "diagnostic.hsroc",
            "Diagnostic Random-Effects": "diagnostic.random",
            "Diagnostic Fixed-Effect Inverse Variance": "diagnostic.fixed.inv.var",
        }
        backend.get_params = lambda method: ({}, {}, [], {})
        backend.get_method_description = lambda method: "stub method"
        monkeypatch.setattr(
            backend,
            "get_analysis_plot_capabilities",
            lambda *args, **kwargs: [],
            raising=False,
        )

        form = window._build_analysis_specs_dialog(
            diag_metrics=["sens", "spec"],
            conf_level=window.model.get_global_conf_level(),
        )

        method_names = [
            str(form.method_cbo_box.itemText(index))
            for index in range(form.method_cbo_box.count())
        ]

        assert "HSROC" not in method_names
        assert "Bivariate (Maximum Likelihood)" not in method_names
        assert method_names == [
            "Diagnostic Random-Effects",
            "Diagnostic Fixed-Effect Inverse Variance",
        ]
    finally:
        for name, value in saved.items():
            setattr(backend, name, value)
        _close_without_prompt(app, window)


def test_diagnostic_method_selector_exposes_full_choices_without_root_cap(monkeypatch):
    import adaptive_controls
    import adaptive_window
    import launch
    from PyQt6 import QtCore, QtWidgets

    app, window = launch.start_automation()
    import ma_specs

    backend = sys.modules.get("meta_py_r", ma_specs.meta_py_r)
    saved = {
        name: getattr(backend, name)
        for name in (
            "get_available_methods",
            "get_params",
            "get_method_description",
            "ma_dataset_to_simple_diagnostic_robj",
        )
    }
    try:
        _create_diagnostic_dataset(window)

        backend.ma_dataset_to_simple_diagnostic_robj = lambda model, **kwargs: None
        backend.get_available_methods = lambda **kwargs: {
            "Diagnostic Random-Effects": "diagnostic.random",
            "Diagnostic Fixed-Effect Inverse Variance": "diagnostic.fixed.inv.var",
        }
        backend.get_params = lambda method: ({}, {}, [], {})
        backend.get_method_description = lambda method: "stub method"
        monkeypatch.setattr(
            backend,
            "get_analysis_plot_capabilities",
            lambda *_args, **_kwargs: [],
            raising=False,
        )

        form = window._build_analysis_specs_dialog(
            diag_metrics=["sens", "spec"],
            conf_level=window.model.get_global_conf_level(),
        )
        form.show()
        app.processEvents()

        label = "Diagnostic Fixed-Effect Inverse Variance"
        label_index = form.method_cbo_box.findText(label)
        assert label_index >= 0
        controller = adaptive_controls.configure_choice_control(
            form.method_cbo_box, visible_characters=28
        )
        app.processEvents()
        baseline = (
            controller.measurement_applied_count,
            controller.tooltip_scan_applied_count,
            controller.popup_clamp_applied_count,
        )
        form.method_cbo_box.showPopup()
        settle = QtCore.QEventLoop()
        QtCore.QTimer.singleShot(20, settle.quit)
        settle.exec()

        popup = form.method_cbo_box.view().window()
        available = adaptive_controls.available_geometry_for_choice_control(
            form.method_cbo_box
        )
        applied = (
            controller.measurement_applied_count - baseline[0],
            controller.tooltip_scan_applied_count - baseline[1],
            controller.popup_clamp_applied_count - baseline[2],
        )
        assert applied == (1, 1, 1)
        assert available.contains(popup.frameGeometry())
        if (
            form.method_cbo_box.view().sizeHintForColumn(0)
            > form.method_cbo_box.view().viewport().width()
        ):
            assert form.method_cbo_box.view().horizontalScrollBar().maximum() > 0
        assert form.method_cbo_box.itemData(label_index, QtCore.Qt.ItemDataRole.ToolTipRole) == label
        assert form.method_cbo_box.toolTip() == form.method_cbo_box.currentText()
        form.method_cbo_box.hidePopup()
        assert form.method_cbo_box.maximumWidth() == QtWidgets.QWIDGETSIZE_MAX
        assert (
            adaptive_window.adaptive_window_state(form).policy.archetype
            is adaptive_window.WindowArchetype.TRANSACTIONAL
        )
    finally:
        for name, value in saved.items():
            setattr(backend, name, value)
        _close_without_prompt(app, window)


def _close_without_prompt(app, window):
    window.current_data_unsaved = False
    window.close()
    app.processEvents()
    os.chdir(REPO_ROOT)
