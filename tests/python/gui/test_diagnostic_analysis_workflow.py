"""Diagnostic analysis workflow behavior."""

import os
import sys
from pathlib import Path
from collections.abc import Callable

import pytest
from rc_metastudio import automation

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath("src"))


REPO_ROOT = os.getcwd()
ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("RCMS_QT6_BUILD_ROOT", str(ROOT / "build" / "qt6-verification"))
from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()


def _set_backend(
    monkeypatch, backend: object, name: str, replacement: Callable[..., object]
) -> None:
    """Patch one dynamic R backend function at the test seam."""

    monkeypatch.setattr(backend, name, replacement, raising=False)


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


def test_diagnostic_backend_dispatch_preserves_standard_and_workflow_calls(monkeypatch):
    from rc_metastudio import analysis_adapter
    from rc_metastudio import analysis_setup_dialog

    calls = []
    monkeypatch.setattr(
        analysis_setup_dialog.r_bridge,
        "run_diagnostic_multi",
        lambda methods, params: (
            calls.append(("standard", methods, params)) or "standard"
        ),
    )
    monkeypatch.setattr(
        analysis_setup_dialog.r_bridge,
        "run_diagnostic_workflow",
        lambda workflow, methods, params: (
            calls.append((workflow, methods, params)) or workflow
        ),
    )

    assert (
        analysis_adapter._run_diagnostic_backend(
            "standard", ["diagnostic.random"], [{"measure": "Sens"}]
        )
        == "standard"
    )
    assert (
        analysis_adapter._run_diagnostic_backend(
            "subgroup", ["diagnostic.random"], [{"measure": "Sens"}]
        )
        == "subgroup"
    )
    assert calls == [
        ("standard", ["diagnostic.random"], [{"measure": "Sens"}]),
        ("subgroup", ["diagnostic.random"], [{"measure": "Sens"}]),
    ]


def test_diagnostic_next_surfaces_specs_failure_instead_of_silent_dead_end():

    app, window = automation.start_automation()
    main_window = sys.modules["rc_metastudio.main_window"]
    from rc_metastudio import diagnostic_metrics_dialog
    from rc_metastudio import analysis_setup_dialog

    original_specs = analysis_setup_dialog.AnalysisSetupDialog
    original_critical = main_window.QMessageBox.critical
    shown = []
    try:
        _create_diagnostic_dataset(window)

        # Simulate a Method & Parameters construction failure raised after the
        # diagnostic metrics dialog hands off to the shared builder.
        def _boom(*args, **kwargs):
            raise ValueError("simulated preparation failure")

        setattr(analysis_setup_dialog, "AnalysisSetupDialog", _boom)
        # QMessageBox.critical (a modal exec) aborts under the offscreen
        # platform, so record the call instead of actually showing it.
        setattr(
            main_window.QMessageBox,
            "critical",
            staticmethod(lambda *args, **kwargs: shown.append(args)),
        )

        form = diagnostic_metrics_dialog.DiagnosticMetricsDialog(
            window.model, parent=window
        )

        # The bug: this used to raise out of the slot with no user feedback.
        form.ok()

        assert shown, "diagnostic next > swallowed the backend error silently"
        assert shown[0][1] == "Could Not Prepare Analysis"
        assert "simulated preparation failure" in shown[0][2]
        assert "backend is not available" not in shown[0][2]
    finally:
        analysis_setup_dialog.AnalysisSetupDialog = original_specs
        main_window.QMessageBox.critical = original_critical
        _close_without_prompt(app, window)


def test_diagnostic_method_dialog_builds_with_working_backend(monkeypatch):

    app, window = automation.start_automation()
    from rc_metastudio import analysis_setup_dialog

    backend = analysis_setup_dialog.r_bridge
    saved = {
        name: getattr(backend, name)
        for name in (
            "get_available_methods",
            "get_params",
            "get_method_description",
            "dataset_to_simple_diagnostic_r_object",
        )
    }
    try:
        _create_diagnostic_dataset(window)

        # Minimal working-backend stub so construction reaches the diagnostic UI
        # setup (and the previously-broken translate() call) without real R.
        # Parameter controls build the R data object for feasibility checks, so
        # that entry point has to be stubbed too.
        _set_backend(
            monkeypatch,
            backend,
            "dataset_to_simple_diagnostic_r_object",
            lambda model, **kwargs: None,
        )
        _set_backend(
            monkeypatch,
            backend,
            "get_available_methods",
            lambda **kwargs: {
                "Reitsma bivariate model": "diagnostic.reitsma",
                "Diagnostic Random-Effects": "diagnostic.random",
            },
        )
        _set_backend(
            monkeypatch, backend, "get_params", lambda method: ({}, {}, [], {})
        )
        _set_backend(
            monkeypatch, backend, "get_method_description", lambda method: "stub method"
        )
        monkeypatch.setattr(
            backend,
            "get_analysis_plot_capabilities",
            lambda *args, **kwargs: [],
            raising=False,
        )

        form = window._build_analysis_specs_dialog(
            diagnostic_metrics=["sens", "spec"],
            confidence_level=window.model.get_confidence_level(),
        )

        # The method dialog must open with the selected diagnostic metrics.
        assert form is not None
        assert str(form.windowTitle()) == (
            "Method & Parameters for Sensitivity and Specificity"
        )
    finally:
        for name, value in saved.items():
            setattr(backend, name, value)
        _close_without_prompt(app, window)


def test_diagnostic_method_dialog_opens_without_multiple_metrics_note(monkeypatch):

    app, window = automation.start_automation()
    from rc_metastudio import diagnostic_metrics_dialog
    from rc_metastudio import analysis_setup_dialog

    backend = analysis_setup_dialog.r_bridge
    saved = {
        name: getattr(backend, name)
        for name in (
            "get_available_methods",
            "get_params",
            "get_method_description",
            "dataset_to_simple_diagnostic_r_object",
        )
    }
    try:
        _create_diagnostic_dataset(window)
        monkeypatch.setattr(
            window.model, "included_studies_have_raw_data", lambda: True
        )

        _set_backend(
            monkeypatch,
            backend,
            "dataset_to_simple_diagnostic_r_object",
            lambda model, **kwargs: None,
        )
        _set_backend(
            monkeypatch,
            backend,
            "get_available_methods",
            lambda **kwargs: {
                "Diagnostic Random-Effects": "diagnostic.random",
            },
        )
        _set_backend(
            monkeypatch, backend, "get_params", lambda method: ({}, {}, [], {})
        )
        _set_backend(
            monkeypatch, backend, "get_method_description", lambda method: "stub method"
        )
        monkeypatch.setattr(
            backend,
            "get_analysis_plot_capabilities",
            lambda data_type, method, workflow="standard": [],
            raising=False,
        )

        metrics_form = diagnostic_metrics_dialog.DiagnosticMetricsDialog(
            window.model, parent=window
        )
        metrics_form.show()
        metrics_form.ok()
        app.processEvents()

        visible_dialog_titles = {
            str(widget.windowTitle())
            for widget in app.topLevelWidgets()
            if widget.isVisible()
        }

        assert "Method & Parameters for Sensitivity and Specificity" in visible_dialog_titles
        assert "Diagnostic MA with Multiple Metrics" not in visible_dialog_titles
        assert metrics_form.isVisible() is False
    finally:
        for name, value in saved.items():
            setattr(backend, name, value)
        _close_without_prompt(app, window)


def test_diagnostic_backend_failure_does_not_open_empty_results(monkeypatch):

    app, window = automation.start_automation()
    from rc_metastudio import analysis_setup_dialog

    backend = analysis_setup_dialog.r_bridge
    saved = {
        name: getattr(backend, name)
        for name in (
            "get_available_methods",
            "get_params",
            "get_method_description",
            "dataset_to_simple_diagnostic_r_object",
            "run_diagnostic_multi",
            "reset_r_working_directory",
        )
    }
    shown = []
    results = []
    try:
        _create_diagnostic_dataset(window)

        _set_backend(
            monkeypatch,
            backend,
            "dataset_to_simple_diagnostic_r_object",
            lambda model, **kwargs: None,
        )
        _set_backend(
            monkeypatch,
            backend,
            "get_available_methods",
            lambda **kwargs: {
                "Diagnostic Random-Effects": "diagnostic.random",
            },
        )
        _set_backend(
            monkeypatch, backend, "get_params", lambda method: ({}, {}, [], {})
        )
        _set_backend(
            monkeypatch, backend, "get_method_description", lambda method: "stub method"
        )
        monkeypatch.setattr(
            backend,
            "get_analysis_plot_capabilities",
            lambda *args, **kwargs: [],
            raising=False,
        )
        _set_backend(
            monkeypatch,
            backend,
            "run_diagnostic_multi",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError("simulated diagnostic failure")
            ),
        )
        _set_backend(monkeypatch, backend, "reset_r_working_directory", lambda: None)
        monkeypatch.setattr(
            analysis_setup_dialog.QMessageBox,
            "critical",
            lambda *args, **kwargs: shown.append(args),
        )
        monkeypatch.setattr(window, "analysis", lambda result: results.append(result))

        form = window._build_analysis_specs_dialog(
            diagnostic_metrics=["lr", "dor"],
            confidence_level=window.model.get_confidence_level(),
        )

        form.run_ma()

        assert shown, "diagnostic backend failure did not surface an error"
        assert results == []
    finally:
        for name, value in saved.items():
            setattr(backend, name, value)
        _close_without_prompt(app, window)


def test_diagnostic_multi_metric_failure_keeps_independent_results(monkeypatch):
    from rc_metastudio.analysis_errors import DiagnosticExecutionError

    app, window = automation.start_automation()
    from rc_metastudio import analysis_setup_dialog

    backend = analysis_setup_dialog.r_bridge
    saved = {
        name: getattr(backend, name)
        for name in (
            "get_available_methods",
            "get_params",
            "get_method_description",
            "dataset_to_simple_diagnostic_r_object",
            "run_diagnostic_multi",
            "reset_r_working_directory",
        )
    }
    shown = []
    results = []
    try:
        _create_diagnostic_dataset(window)

        _set_backend(
            monkeypatch,
            backend,
            "dataset_to_simple_diagnostic_r_object",
            lambda model, **kwargs: None,
        )
        _set_backend(
            monkeypatch,
            backend,
            "get_available_methods",
            lambda **kwargs: {
                "Reitsma bivariate model": "diagnostic.reitsma",
                "Diagnostic Random-Effects": "diagnostic.random",
            },
        )
        _set_backend(
            monkeypatch, backend, "get_params", lambda method: ({}, {}, [], {})
        )
        _set_backend(
            monkeypatch, backend, "get_method_description", lambda method: "stub method"
        )
        monkeypatch.setattr(
            backend,
            "get_analysis_plot_capabilities",
            lambda *args, **kwargs: [],
            raising=False,
        )
        _set_backend(monkeypatch, backend, "reset_r_working_directory", lambda: None)

        def run_metric(method_names, param_vals):
            if len(param_vals) > 1:
                raise DiagnosticExecutionError("combined diagnostic failure")
            metric = param_vals[0]["measure"]
            if metric == "Sens":
                raise DiagnosticExecutionError("Reitsma bivariate model failed to converge")
            title = "%s Forest plot" % metric
            return {
                "texts": {
                    "%s Summary" % metric: "%s ok" % metric,
                },
                "images": {
                    title: "%s.png" % metric.lower(),
                },
                "display_images": {},
                "image_var_names": {},
                "image_params_paths": {},
                "image_order": [title],
                "plot_capabilities": {
                    title: {
                        "plot_kind": "forest",
                        "editable": False,
                        "styleable": True,
                        "composition": "single",
                        "regenerator": "forest",
                    }
                },
            }

        _set_backend(monkeypatch, backend, "run_diagnostic_multi", run_metric)
        monkeypatch.setattr(
            analysis_setup_dialog.QMessageBox,
            "critical",
            lambda *args, **kwargs: shown.append(args),
        )
        monkeypatch.setattr(window, "analysis", lambda result: results.append(result))

        form = window._build_analysis_specs_dialog(
            diagnostic_metrics=["sens", "lr", "dor"],
            confidence_level=window.model.get_confidence_level(),
        )
        form.diagnostic_analysis_details = {
            "Sens": ("diagnostic.reitsma", {"conf.level": 95.0}),
            "DOR": ("diagnostic.random", {"conf.level": 95.0}),
            "PLR": ("diagnostic.random", {"conf.level": 95.0}),
            "NLR": ("diagnostic.random", {"conf.level": 95.0}),
        }
        form.sens_spec = False
        form.lr_dor = True

        form.run_ma()

        assert shown == []
        assert len(results) == 1
        assert results[0]["texts"]["Sens Error"] == "Reitsma bivariate model failed to converge"
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

    app, window = automation.start_automation()
    from rc_metastudio import analysis_setup_dialog
    from rc_metastudio import app_error_handler

    backend = analysis_setup_dialog.r_bridge
    saved = {
        name: getattr(backend, name)
        for name in (
            "get_available_methods",
            "get_params",
            "get_method_description",
            "dataset_to_simple_diagnostic_r_object",
            "run_diagnostic_multi",
            "reset_r_working_directory",
        )
    }
    unexpected_errors = []
    analysis_results = []
    run_calls = []
    try:
        _create_diagnostic_dataset(window)

        _set_backend(
            monkeypatch,
            backend,
            "dataset_to_simple_diagnostic_r_object",
            lambda model, **kwargs: None,
        )
        _set_backend(
            monkeypatch,
            backend,
            "get_available_methods",
            lambda **kwargs: {
                "Reitsma bivariate model": "diagnostic.reitsma",
                "Diagnostic Random-Effects": "diagnostic.random",
            },
        )

        def get_params(method):
            if method == "diagnostic.reitsma":
                definitions = {
                    "estimator": ["REML", "ML"],
                    "conf.level": "float",
                    "adjust": "float",
                    "correction.policy": [
                        "Studies with any zero cell",
                        "All studies if any zero exists",
                        "None",
                    ],
                    "digits": "int",
                }
                defaults = {
                    "estimator": "REML",
                    "conf.level": 95.0,
                    "adjust": 0.5,
                    "correction.policy": "All studies if any zero exists",
                    "digits": 2,
                }
                return (definitions, defaults, list(definitions), {})
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

        _set_backend(monkeypatch, backend, "get_params", get_params)
        _set_backend(
            monkeypatch, backend, "get_method_description", lambda method: "stub method"
        )
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

        _set_backend(monkeypatch, backend, "run_diagnostic_multi", run_diagnostic)
        _set_backend(monkeypatch, backend, "reset_r_working_directory", lambda: None)
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
            diagnostic_metrics=["sens", "spec", "lr", "dor"],
            confidence_level=window.model.get_confidence_level(),
        )
        assert preparation_errors == [], "".join(
            __import__("traceback").format_exception(preparation_errors[0])
        )
        assert form is not None
        form.method_cbo_box.setCurrentText("Reitsma bivariate model")
        form.lr_dor_method_cbo_box.setCurrentText("Diagnostic Random-Effects")
        form.current_param_vals.update(
            {"estimator": "ML", "conf.level": 90.0, "digits": 4,
             "adjust": 0.25, "correction.policy": "All studies if any zero exists"}
        )
        form.lr_dor_panel.params["rm.method"] = "REML"
        form.add_current_analysis_details()

        assert form.windowTitle() == "Method & Parameters"
        assert (
            form.buttonBox.button(
                analysis_setup_dialog.QDialogButtonBox.StandardButton.Ok
            )
            is not None
        )
        assert form.method_lbl.text() == "Sensitivity and Specificity"
        assert form.lr_dor_method_lbl.text() == (
            "Likelihood Ratios and Diagnostic Odds Ratio"
        )
        assert not any(button.text() == "next >" for button in form.buttonBox.buttons())
        sens_method, sens_params = form.diagnostic_analysis_details["Sens"]
        dor_method, dor_params = form.diagnostic_analysis_details["DOR"]
        assert sens_method == "diagnostic.reitsma"
        assert sens_params == {
            "estimator": "ML", "conf.level": 90.0, "digits": 4,
            "adjust": 0.25, "correction.policy": "All studies if any zero exists",
        }
        assert dor_method == "diagnostic.random"
        assert dor_params == {
            "rm.method": "REML",
            "conf.level": 90.0,
            "digits": 4,
            "adjust": 0.25,
                "to": "only0",
        }
        monkeypatch.setattr(
            analysis_setup_dialog,
            "AnalysisSetupDialog",
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


def test_per_metric_diagnostic_merge_preserves_display_artifacts(monkeypatch):
    from rc_metastudio import analysis_adapter
    from rc_metastudio.analysis_errors import DiagnosticExecutionError

    def run_backend(_workflow, _methods, parameter_values):
        if len(_methods) > 1:
            raise DiagnosticExecutionError(
                "combined execution is intentionally unavailable"
            )
        metric = parameter_values[0]["measure"]
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

    monkeypatch.setattr(analysis_adapter, "_run_diagnostic_backend", run_backend)
    monkeypatch.setattr(
        analysis_adapter.r_bridge,
        "dataset_to_simple_diagnostic_r_object",
        lambda *_args, **_kwargs: None,
    )
    requests = tuple(
        analysis_adapter.make_analysis_request(
            data_type="diagnostic",
            workflow="standard",
            method="diagnostic.random",
            metric=metric,
            parameters={"measure": metric},
        )
        for metric in ("Sens", "Spec")
    )
    model = type(
        "Model",
        (),
        {
            "included_studies_have_raw_data": lambda self: True,
            "included_studies_have_point_estimates": lambda self, effect: True,
        },
    )()
    result = analysis_adapter.execute_analysis_requests(model, requests)

    assert result["display_images"] == {
        "Sens Forest Plot": "sens.display.svg",
        "Spec Forest Plot": "spec.display.svg",
    }


def test_unexpected_combined_diagnostic_error_is_not_retried(monkeypatch):
    from rc_metastudio import analysis_adapter

    calls = []

    def run_backend(_workflow, _methods, _parameter_values):
        calls.append("combined")
        raise ValueError("programming error")

    monkeypatch.setattr(analysis_adapter, "_run_diagnostic_backend", run_backend)
    monkeypatch.setattr(
        analysis_adapter.r_bridge,
        "dataset_to_simple_diagnostic_r_object",
        lambda *_args, **_kwargs: None,
    )
    requests = tuple(
        analysis_adapter.make_analysis_request(
            data_type="diagnostic",
            workflow="standard",
            method="diagnostic.random",
            metric=metric,
            parameters={"measure": metric},
        )
        for metric in ("Sens", "Spec")
    )

    model = type(
        "Model",
        (),
        {
            "included_studies_have_raw_data": lambda self: True,
            "included_studies_have_point_estimates": lambda self, effect: True,
        },
    )()
    with pytest.raises(ValueError, match="programming error"):
        analysis_adapter.execute_analysis_requests(model, requests)
    assert calls == ["combined"]


def test_combined_diagnostic_configuration_returns_typed_analysis_requests(monkeypatch):

    app, window = automation.start_automation()
    from rc_metastudio import analysis_adapter
    from rc_metastudio import analysis_setup_dialog

    backend = analysis_setup_dialog.r_bridge
    saved = {
        name: getattr(backend, name)
        for name in (
            "get_available_methods",
            "get_params",
            "get_method_description",
            "dataset_to_simple_diagnostic_r_object",
            "run_diagnostic_multi",
            "reset_r_working_directory",
        )
    }
    try:
        _create_diagnostic_dataset(window)

        _set_backend(
            monkeypatch,
            backend,
            "dataset_to_simple_diagnostic_r_object",
            lambda model, **kwargs: None,
        )
        _set_backend(
            monkeypatch,
            backend,
            "get_available_methods",
            lambda **kwargs: {
                "Reitsma bivariate model": "diagnostic.reitsma",
                "Diagnostic Random-Effects": "diagnostic.random",
            },
        )
        _set_backend(
            monkeypatch,
            backend,
            "get_params",
            lambda method: (
                {"conf.level": "float"},
                {"conf.level": 95.0},
                ["conf.level"],
                {},
            ),
        )
        _set_backend(
            monkeypatch, backend, "get_method_description", lambda method: "stub method"
        )
        monkeypatch.setattr(
            backend,
            "get_analysis_plot_capabilities",
            lambda *args, **kwargs: [],
            raising=False,
        )
        _set_backend(monkeypatch, backend, "reset_r_working_directory", lambda: None)

        form = window._build_analysis_specs_dialog(
            diagnostic_metrics=["sens", "spec", "lr", "dor"],
            confidence_level=window.model.get_confidence_level(),
        )
        requests = form.analysis_requests()

        assert all(
            isinstance(request, analysis_adapter.AnalysisRequest)
            for request in requests
        )
        assert [request.metric for request in requests] == ["Sens", "NLR", "PLR", "DOR"]
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

    app, window = automation.start_automation()
    from rc_metastudio import analysis_setup_dialog

    backend = analysis_setup_dialog.r_bridge
    saved = {
        name: getattr(backend, name, None)
        for name in (
            "get_available_methods",
            "get_params",
            "get_method_description",
            "dataset_to_simple_diagnostic_r_object",
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

        _set_backend(
            monkeypatch,
            backend,
            "get_available_methods",
            lambda **kwargs: {
                "Diagnostic Random-Effects": "diagnostic.random",
            },
        )
        _set_backend(
            monkeypatch, backend, "get_params", lambda method: ({}, {}, [], {})
        )
        _set_backend(
            monkeypatch, backend, "get_method_description", lambda method: "stub method"
        )
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

        _set_backend(
            monkeypatch,
            backend,
            "dataset_to_simple_diagnostic_r_object",
            build_metric,
        )
        _set_backend(monkeypatch, backend, "run_diagnostic_multi", run_metric)
        monkeypatch.setattr(window, "analysis", lambda result: results.append(result))

        form = window._build_analysis_specs_dialog(
            diagnostic_metrics=["sens", "spec"],
            confidence_level=window.model.get_confidence_level(),
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

    app, window = automation.start_automation()
    from rc_metastudio import diagnostic_metrics_dialog

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

        form = diagnostic_metrics_dialog.DiagnosticMetricsDialog(
            window.model, parent=window
        )

        assert form.get_selected_metrics() == ["sens", "spec"]
        assert not form.chk_box_lr.isChecked()
        assert not form.chk_box_lr.isEnabled()
        assert not form.chk_box_dor.isChecked()
        assert not form.chk_box_dor.isEnabled()

        form.ok()

        assert captured[0]["diagnostic_metrics"] == ["sens", "spec"]
    finally:
        _close_without_prompt(app, window)


def test_diagnostic_metric_dialog_does_not_run_without_selected_metrics(monkeypatch):

    app, window = automation.start_automation()
    from rc_metastudio import diagnostic_metrics_dialog

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
            diagnostic_metrics_dialog.QMessageBox,
            "warning",
            lambda *args: warnings.append(args),
        )

        form = diagnostic_metrics_dialog.DiagnosticMetricsDialog(
            window.model, parent=window
        )

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

    app, window = automation.start_automation()
    from rc_metastudio import app_error_handler
    from rc_metastudio import diagnostic_metrics_dialog

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

        form = diagnostic_metrics_dialog.DiagnosticMetricsDialog(
            window.model, parent=window
        )

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

    app, window = automation.start_automation()
    from rc_metastudio import analysis_setup_dialog

    backend = analysis_setup_dialog.r_bridge
    saved = {
        name: getattr(backend, name)
        for name in (
            "get_available_methods",
            "get_params",
            "get_method_description",
            "dataset_to_simple_diagnostic_r_object",
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

        _set_backend(
            monkeypatch,
            backend,
            "dataset_to_simple_diagnostic_r_object",
            lambda model, **kwargs: None,
        )
        _set_backend(
            monkeypatch,
            backend,
            "get_available_methods",
            lambda **kwargs: {
                "Reitsma bivariate model": "diagnostic.reitsma",
                "Diagnostic Random-Effects": "diagnostic.random",
                "Diagnostic Fixed-Effect Inverse Variance": "diagnostic.fixed.inv.var",
            },
        )
        _set_backend(
            monkeypatch, backend, "get_params", lambda method: ({}, {}, [], {})
        )
        _set_backend(
            monkeypatch, backend, "get_method_description", lambda method: "stub method"
        )
        monkeypatch.setattr(
            backend,
            "get_analysis_plot_capabilities",
            lambda *args, **kwargs: [],
            raising=False,
        )

        form = window._build_analysis_specs_dialog(
            diagnostic_metrics=["sens", "spec"],
            confidence_level=window.model.get_confidence_level(),
        )

        method_names = [
            str(form.method_cbo_box.itemText(index))
            for index in range(form.method_cbo_box.count())
        ]

        assert "Reitsma bivariate model" not in method_names
        assert method_names == [
            "Diagnostic Random-Effects",
            "Diagnostic Fixed-Effect Inverse Variance",
        ]
    finally:
        for name, value in saved.items():
            setattr(backend, name, value)
        _close_without_prompt(app, window)


def test_diagnostic_method_selector_exposes_full_choices_without_root_cap(monkeypatch):
    from rc_metastudio import adaptive_controls
    from rc_metastudio import adaptive_window
    from PyQt6 import QtCore, QtWidgets

    app, window = automation.start_automation()
    from rc_metastudio import analysis_setup_dialog

    backend = sys.modules.get("rc_metastudio.r_bridge", analysis_setup_dialog.r_bridge)
    saved = {
        name: getattr(backend, name)
        for name in (
            "get_available_methods",
            "get_params",
            "get_method_description",
            "dataset_to_simple_diagnostic_r_object",
        )
    }
    try:
        _create_diagnostic_dataset(window)

        _set_backend(
            monkeypatch,
            backend,
            "dataset_to_simple_diagnostic_r_object",
            lambda model, **kwargs: None,
        )
        _set_backend(
            monkeypatch,
            backend,
            "get_available_methods",
            lambda **kwargs: {
                "Diagnostic Random-Effects": "diagnostic.random",
                "Diagnostic Fixed-Effect Inverse Variance": "diagnostic.fixed.inv.var",
            },
        )
        _set_backend(
            monkeypatch, backend, "get_params", lambda method: ({}, {}, [], {})
        )
        _set_backend(
            monkeypatch, backend, "get_method_description", lambda method: "stub method"
        )
        monkeypatch.setattr(
            backend,
            "get_analysis_plot_capabilities",
            lambda *_args, **_kwargs: [],
            raising=False,
        )

        form = window._build_analysis_specs_dialog(
            diagnostic_metrics=["sens", "spec"],
            confidence_level=window.model.get_confidence_level(),
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
        assert (
            form.method_cbo_box.itemData(
                label_index, QtCore.Qt.ItemDataRole.ToolTipRole
            )
            == label
        )
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
