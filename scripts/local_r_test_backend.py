"""Explicit test capability used only by developer-facing native smoke scripts."""

from __future__ import annotations

from types import SimpleNamespace
def _identity(value: object, *_args: object, **_kwargs: object) -> object:
    return value


def _unavailable(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("native smoke test capability is not an R analysis")


def create() -> SimpleNamespace:
    """Return a local capability object; it never replaces the app module."""
    backend = SimpleNamespace()
    backend.AnalysisBackendUnavailableError = RuntimeError
    backend.get_confidence_multiplier_from_r = lambda _level: 1.96
    backend.set_confidence_level = lambda level: float(level)
    backend.get_r_library_paths = lambda: []
    backend.get_r_version_string = lambda: None
    backend.get_r_package_version = lambda _name: None
    backend.reset_r_working_directory = lambda: None
    backend.execute_r_string = lambda _expression: [95.0]
    backend.execute_r_function = lambda _name, *_args, **_kwargs: [95.0]
    backend.binary_convert_scale = _identity
    backend.continuous_convert_scale = _identity
    backend.diagnostic_convert_scale = _identity
    backend.effect_triplet = lambda result, scale, metric=None: result[scale]
    backend.effect_for_study = lambda *_args, **_kwargs: {"calc_scale": (1.0, 0.5, 1.5)}
    backend.continuous_effect_for_study = backend.effect_for_study
    backend.diagnostic_effects_for_study = lambda *_args, metrics=("Spec", "Sens"), **_kwargs: {
        metric: {"calc_scale": (1.0, 0.5, 1.5)} for metric in metrics
    }
    backend.impute_binary_data = lambda _data: {"FAIL": True}
    backend.impute_continuous_data = lambda _data, _alpha: {"succeeded": False}
    backend.impute_pre_post_continuous_data = lambda _data, _corr, _alpha: {"succeeded": False}
    backend.back_calculate_continuous_data = lambda *_args, **_kwargs: {"FAIL": True}
    backend.impute_diagnostic_data = lambda _data: {"TP": None, "TN": None, "FP": None, "FN": None}
    backend.dataset_to_simple_binary_r_object = _unavailable
    backend.dataset_to_simple_continuous_r_object = _unavailable
    backend.dataset_to_simple_diagnostic_r_object = _unavailable
    backend.get_available_methods = _unavailable
    backend.get_params = _unavailable
    backend.get_method_description = _unavailable
    backend.get_analysis_plot_capabilities = lambda *_args, **_kwargs: []
    backend.run_small_study_effects = _unavailable
    backend.regenerate_small_study_effects_funnel = _unavailable
    backend.generate_small_study_effects_funnel = _unavailable
    backend.run_diagnostic_multi = _unavailable
    backend.run_diagnostic_workflow = _unavailable
    backend.run_versioned_analysis_request = lambda _request: {"texts": {}, "images": {}}
    backend.run_versioned_analysis_requests = lambda _requests: []
    backend.ro = SimpleNamespace(r=lambda _expression: [95.0])
    backend.RLibraryLoader = type("RLibraryLoader", (), {})
    return backend
