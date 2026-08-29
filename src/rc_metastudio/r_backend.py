import os
import sys
import types
from collections.abc import Callable
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


def _analysis_unavailable(*_args: object, **_kwargs: object) -> NoReturn:
    raise AnalysisBackendUnavailableError(
        "The analysis backend (in-process rpy2/R) is not available in this "
        "build, so meta-analyses cannot be run."
    )


def _get_mult_from_r(conf_level: object) -> float:
    validate_confidence_level(conf_level)
    return 1.96


def _set_global_conf_level(conf_level: object) -> float:
    return float(validate_confidence_level(conf_level))


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
    conf_level: object = 95,
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
    conf_level: object = 95.0,
) -> None:
    return None


def _diagnostic_effects(
    tp: object,
    fn: object,
    fp: object,
    tn: object,
    metrics: object = ("Spec", "Sens"),
    conf_level: object = 95.0,
) -> dict[object, object]:
    return {}


def _impute_bin_data(bin_data_dict: object) -> dict[str, bool]:
    return {"FAIL": True}


def _back_calc_cont_data(
    group1_data: object,
    group2_data: object,
    effect_data: object,
    conf_level: object,
) -> dict[str, bool]:
    return {"FAIL": True}


def _impute_cont_data(cont_data_dict: object, alpha: object) -> dict[str, bool]:
    return {"succeeded": False}


def _impute_pre_post_cont_data(
    cont_data_dict: object, correlation: object, alpha: object
) -> dict[str, bool]:
    return {"succeeded": False}


def _impute_diag_data(diag_data_dict: object) -> dict[str, None]:
    return {"TP": None, "TN": None, "FP": None, "FN": None}


class _StubRObjects:
    @staticmethod
    def r(expression: object) -> list[float]:
        return [95.0]


class _StubRLibraryLoader:
    def load_metafor(self) -> None:
        return None

    def load_rcmetar(self) -> None:
        return None

    def load_igraph(self) -> None:
        return None

    def load_grid(self) -> None:
        return None

    def load_gemtc(self) -> None:
        return None


class _StubRBridgeModule(types.ModuleType):
    """Typed module-shaped compatibility surface for tests without in-process R."""

    _rcms_stub_backend: bool
    AnalysisBackendUnavailableError: type[AnalysisBackendUnavailableError]
    get_mult_from_r: _BackendCallable
    set_global_conf_level: _BackendCallable
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
    impute_bin_data: _BackendCallable
    impute_cont_data: _BackendCallable
    impute_pre_post_cont_data: _BackendCallable
    impute_diag_data: _BackendCallable
    back_calc_cont_data: _BackendCallable
    dataset_to_simple_binary_r_object: _BackendCallable
    dataset_to_simple_continuous_r_object: _BackendCallable
    dataset_to_simple_diagnostic_r_object: _BackendCallable
    dataset_to_simple_network: _BackendCallable
    get_available_methods: _BackendCallable
    get_params: _BackendCallable
    get_method_description: _BackendCallable
    get_analysis_plot_capabilities: _BackendCallable
    run_binary_ma: _BackendCallable
    run_continuous_ma: _BackendCallable
    run_diagnostic_multi: _BackendCallable
    run_workflow_analysis: _BackendCallable
    run_diagnostic_workflow: _BackendCallable
    run_meta_regression: _BackendCallable
    ro: type[_StubRObjects]
    RLibraryLoader: type[_StubRLibraryLoader]

    def __init__(self) -> None:
        super().__init__("rc_metastudio.r_bridge")
        self._rcms_stub_backend = True
        self.AnalysisBackendUnavailableError = AnalysisBackendUnavailableError
        self.get_mult_from_r = _get_mult_from_r
        self.set_global_conf_level = _set_global_conf_level
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
        self.impute_bin_data = _impute_bin_data
        self.impute_cont_data = _impute_cont_data
        self.impute_pre_post_cont_data = _impute_pre_post_cont_data
        self.impute_diag_data = _impute_diag_data
        self.back_calc_cont_data = _back_calc_cont_data
        self.dataset_to_simple_binary_r_object = _analysis_unavailable
        self.dataset_to_simple_continuous_r_object = _analysis_unavailable
        self.dataset_to_simple_diagnostic_r_object = _analysis_unavailable
        self.dataset_to_simple_network = _analysis_unavailable
        self.get_available_methods = _analysis_unavailable
        self.get_params = _analysis_unavailable
        self.get_method_description = _analysis_unavailable
        self.get_analysis_plot_capabilities = _get_analysis_plot_capabilities
        self.run_binary_ma = _analysis_unavailable
        self.run_continuous_ma = _analysis_unavailable
        self.run_diagnostic_multi = _analysis_unavailable
        self.run_workflow_analysis = _analysis_unavailable
        self.run_diagnostic_workflow = _analysis_unavailable
        self.run_meta_regression = _analysis_unavailable
        self.ro = _StubRObjects
        self.RLibraryLoader = _StubRLibraryLoader


def _registered_backend() -> types.ModuleType | None:
    return sys.modules.get("rc_metastudio.r_bridge")


def _register_backend(backend: types.ModuleType) -> types.ModuleType:
    sys.modules["rc_metastudio.r_bridge"] = backend
    return backend


def install_r_backend() -> types.ModuleType:
    """Install and return the real R backend, or the test compatibility backend."""
    # The real backend is the in-process rpy2 module (r_bridge). When R/rpy2
    # is unavailable -- notably in CI and GUI-only tests -- fall back to a pure
    # Python stub. Set RCMS_STUB_BACKEND=1 to force the stub even where R exists;
    # set RCMS_REQUIRE_IN_PROCESS_RPY2=1 to fail loudly instead of falling back.
    if os.environ.get("RCMS_STUB_BACKEND") == "1":
        return install_stub_r_bridge()

    existing = _registered_backend()
    if existing is not None:
        return _register_backend(existing)

    try:
        from rc_metastudio import r_runtime

        r_runtime.configure_bundled_r_environment()
        from rc_metastudio import r_bridge

        return r_bridge
    except Exception:
        if (
            getattr(sys, "frozen", False)
            or os.environ.get("RCMS_REQUIRE_IN_PROCESS_RPY2") == "1"
        ):
            raise
        return install_stub_r_bridge()


def install_stub_r_bridge() -> types.ModuleType:
    existing = _registered_backend()
    if existing is not None and getattr(existing, "_rcms_stub_backend", False):
        return _register_backend(existing)

    return _register_backend(_StubRBridgeModule())


if os.environ.get("RCMS_STUB_BACKEND") == "1" and _registered_backend() is None:
    install_stub_r_bridge()
