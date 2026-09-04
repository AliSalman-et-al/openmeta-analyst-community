from collections.abc import Callable, Mapping
import sys
from typing import NoReturn

from rc_metastudio.study_effect_shapes import (
    effect_triplet,
    normalize_diagnostic_effects,
    normalize_effect_result,
)
from rc_metastudio.meta_globals import validate_confidence_level


class AnalysisBackendUnavailableError(RuntimeError):
    """Raised when the configured R analysis backend cannot service requests."""


_BackendCallable = Callable[..., object]
_REAL_BACKEND = None


def is_backend_installed() -> bool:
    """Return whether startup composed the real or explicitly injected bridge."""
    return _REAL_BACKEND is not None


def _analysis_unavailable(*_args: object, **_kwargs: object) -> NoReturn:
    raise AnalysisBackendUnavailableError(
        "The analysis backend (in-process rpy2/R) is not available in this "
        "build, so meta-analyses cannot be run."
    )


def _get_confidence_multiplier_from_r(confidence_level: object) -> float:
    validate_confidence_level(confidence_level)
    return 1.96


def _set_confidence_level(confidence_level: object) -> float:
    return float(validate_confidence_level(confidence_level))


def _get_r_library_paths() -> list[object]:
    return []


def _get_r_version_string() -> None:
    return None


def _get_r_package_version(package_name: object) -> None:
    return None


def _reset_r_working_directory() -> None:
    return None


def _execute_r_string(expression: object) -> list[float]:
    return [95.0]


def _execute_r_function(
    function_name: object, *args: object, **kwargs: object
) -> list[float]:
    return [95.0]


def _get_analysis_plot_capabilities(
    data_type: object, method_name: object, workflow: object = "standard"
) -> list[object]:
    return []


def _run_small_study_effects(*_args: object, **_kwargs: object) -> object:
    return _analysis_unavailable(*_args, **_kwargs)


def _regenerate_small_study_effects_funnel(*_args: object, **_kwargs: object) -> object:
    return _analysis_unavailable(*_args, **_kwargs)


def _generate_small_study_effects_funnel(*_args: object, **_kwargs: object) -> object:
    return _analysis_unavailable(*_args, **_kwargs)


def _binary_convert_scale(
    x: object,
    metric_name: object,
    convert_to: object = "display.scale",
    n1: object = None,
) -> object:
    return x


def _continuous_convert_scale(
    x: object, metric_name: object, convert_to: object = "display.scale"
) -> object:
    return x


def _diagnostic_convert_scale(
    x: object, metric_name: object, convert_to: object = "display.scale"
) -> object:
    return x


def _effect_for_study(
    e1: object,
    n1: object,
    e2: object = None,
    n2: object = None,
    two_arm: object = True,
    metric: object = "OR",
    confidence_level: object = 95,
) -> None:
    return None


def _continuous_effect_for_study(
    n1: object,
    m1: object,
    sd1: object,
    se1: object = None,
    n2: object = None,
    m2: object = None,
    sd2: object = None,
    se2: object = None,
    metric: object = "MD",
    two_arm: object = True,
    confidence_level: object = 95.0,
) -> None:
    return None


def _diagnostic_effects(
    tp: object,
    fn: object,
    fp: object,
    tn: object,
    metrics: object = ("Spec", "Sens"),
    confidence_level: object = 95.0,
) -> dict[object, object]:
    return {}


def _impute_binary_data(binary_data: object) -> dict[str, bool]:
    return {"FAIL": True}


def _back_calculate_continuous_data(
    group1_data: object,
    group2_data: object,
    effect_data: object,
    confidence_level: object,
) -> dict[str, bool]:
    return {"FAIL": True}


def _impute_continuous_data(continuous_data: object, alpha: object) -> dict[str, bool]:
    return {"succeeded": False}


def _impute_pre_post_continuous_data(
    continuous_data: object, correlation: object, alpha: object
) -> dict[str, bool]:
    return {"succeeded": False}


def _impute_diagnostic_data(diagnostic_data: object) -> dict[str, None]:
    return {"TP": None, "TN": None, "FP": None, "FN": None}


class _TestRObjects:
    @staticmethod
    def r(expression: object) -> list[float]:
        return [95.0]


class _TestRLibraryLoader:
    def load_meta(self) -> None:
        return None

    def load_metafor(self) -> None:
        return None

    def load_rcmetar(self) -> None:
        return None

    def load_grid(self) -> None:
        return None


class _TestRBridge:
    """Explicit local fake used by tests that do not exercise the R boundary."""

    AnalysisBackendUnavailableError: type[AnalysisBackendUnavailableError]
    get_confidence_multiplier_from_r: _BackendCallable
    set_confidence_level: _BackendCallable
    get_r_library_paths: _BackendCallable
    get_r_version_string: _BackendCallable
    get_r_package_version: _BackendCallable
    reset_r_working_directory: _BackendCallable
    execute_r_string: _BackendCallable
    execute_r_function: _BackendCallable
    binary_convert_scale: _BackendCallable
    continuous_convert_scale: _BackendCallable
    diagnostic_convert_scale: _BackendCallable
    effect_triplet: _BackendCallable
    normalize_effect_result: _BackendCallable
    normalize_diagnostic_effects: _BackendCallable
    effect_for_study: _BackendCallable
    continuous_effect_for_study: _BackendCallable
    diagnostic_effects_for_study: _BackendCallable
    impute_binary_data: _BackendCallable
    impute_continuous_data: _BackendCallable
    impute_pre_post_continuous_data: _BackendCallable
    impute_diagnostic_data: _BackendCallable
    back_calculate_continuous_data: _BackendCallable
    dataset_to_simple_binary_r_object: _BackendCallable
    dataset_to_simple_continuous_r_object: _BackendCallable
    dataset_to_simple_diagnostic_r_object: _BackendCallable
    get_available_methods: _BackendCallable
    get_params: _BackendCallable
    get_method_description: _BackendCallable
    get_analysis_plot_capabilities: _BackendCallable
    run_small_study_effects: _BackendCallable
    regenerate_small_study_effects_funnel: _BackendCallable
    generate_small_study_effects_funnel: _BackendCallable
    run_binary_analysis: _BackendCallable
    run_continuous_analysis: _BackendCallable
    run_diagnostic_multi: _BackendCallable
    run_workflow_analysis: _BackendCallable
    run_diagnostic_workflow: _BackendCallable
    run_versioned_analysis_request: _BackendCallable
    run_versioned_analysis_requests: _BackendCallable
    run_meta_regression: _BackendCallable
    ro: type[_TestRObjects]
    RLibraryLoader: type[_TestRLibraryLoader]

    def __init__(self) -> None:
        self.AnalysisBackendUnavailableError = AnalysisBackendUnavailableError
        self.get_confidence_multiplier_from_r = _get_confidence_multiplier_from_r
        self.set_confidence_level = _set_confidence_level
        self.get_r_library_paths = _get_r_library_paths
        self.get_r_version_string = _get_r_version_string
        self.get_r_package_version = _get_r_package_version
        self.reset_r_working_directory = _reset_r_working_directory
        self.execute_r_string = _execute_r_string
        self.execute_r_function = _execute_r_function
        self.binary_convert_scale = _binary_convert_scale
        self.continuous_convert_scale = _continuous_convert_scale
        self.diagnostic_convert_scale = _diagnostic_convert_scale
        self.effect_triplet = effect_triplet
        self.normalize_effect_result = normalize_effect_result
        self.normalize_diagnostic_effects = normalize_diagnostic_effects
        self.effect_for_study = _effect_for_study
        self.continuous_effect_for_study = _continuous_effect_for_study
        self.diagnostic_effects_for_study = _diagnostic_effects
        self.impute_binary_data = _impute_binary_data
        self.impute_continuous_data = _impute_continuous_data
        self.impute_pre_post_continuous_data = _impute_pre_post_continuous_data
        self.impute_diagnostic_data = _impute_diagnostic_data
        self.back_calculate_continuous_data = _back_calculate_continuous_data
        self.dataset_to_simple_binary_r_object = _analysis_unavailable
        self.dataset_to_simple_continuous_r_object = _analysis_unavailable
        self.dataset_to_simple_diagnostic_r_object = _analysis_unavailable
        self.get_available_methods = _analysis_unavailable
        self.get_params = _analysis_unavailable
        self.get_method_description = _analysis_unavailable
        self.get_analysis_plot_capabilities = _get_analysis_plot_capabilities
        self.run_small_study_effects = _run_small_study_effects
        self.regenerate_small_study_effects_funnel = (
            _regenerate_small_study_effects_funnel
        )
        self.generate_small_study_effects_funnel = _generate_small_study_effects_funnel
        self.run_binary_analysis = _analysis_unavailable
        self.run_continuous_analysis = _analysis_unavailable
        self.run_diagnostic_multi = _analysis_unavailable
        self.run_workflow_analysis = _analysis_unavailable
        self.run_diagnostic_workflow = _analysis_unavailable
        self.run_versioned_analysis_request = self._versioned_analysis_request
        self.run_versioned_analysis_requests = self._versioned_analysis_requests
        self.run_meta_regression = _analysis_unavailable
        self.ro = _TestRObjects
        self.RLibraryLoader = _TestRLibraryLoader

    def _versioned_analysis_request(self, request: Mapping[str, object]) -> object:
        if request.get("version") != 1:
            raise ValueError("unsupported analysis request version")
        method = request.get("method")
        params = request.get("params", request.get("parameters", {}))
        if not isinstance(method, str) or not isinstance(params, Mapping):
            raise TypeError("invalid analysis request")
        workflow = request.get("workflow", "standard")
        module = sys.modules.get("rc_metastudio.r_bridge")
        backend = module if module is not None else self
        if workflow == "standard":
            runner = (
                getattr(backend, "run_binary_analysis")
                if request.get("data.type", request.get("data_type")) == "binary"
                else getattr(backend, "run_continuous_analysis")
            )
            return runner(method, dict(params))
        return getattr(backend, "run_workflow_analysis")(workflow, method, dict(params))

    def _versioned_analysis_requests(self, requests: list[Mapping[str, object]]) -> object:
        if not requests:
            raise ValueError("at least one analysis request is required")
        first = requests[0]
        workflow = first.get("workflow", "standard")
        module = sys.modules.get("rc_metastudio.r_bridge")
        backend = module if module is not None else self
        methods = [request.get("method") for request in requests]
        params = [request.get("params", request.get("parameters", {})) for request in requests]
        if workflow == "standard":
            return getattr(backend, "run_diagnostic_multi")(methods, params)
        return getattr(backend, "run_diagnostic_workflow")(workflow, methods, params)


def install_r_backend():
    """Configure and return the one real in-process embedded-R backend."""
    global _REAL_BACKEND
    if _REAL_BACKEND is not None:
        return _REAL_BACKEND
    try:
        from rc_metastudio import r_runtime

        r_runtime.configure_bundled_r_environment()
        from rc_metastudio import r_bridge

        _REAL_BACKEND = r_bridge
        return _REAL_BACKEND
    except Exception as error:
        raise AnalysisBackendUnavailableError(
            "Unable to start the embedded R runtime. Install the pinned R/RCMetaR "
            "runtime or repair the packaged integration kit, then restart RC MetaStudio."
        ) from error


def make_test_backend() -> _TestRBridge:
    """Create a local fake explicitly for tests that avoid real R."""
    return _TestRBridge()
