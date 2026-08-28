import os
import sys
import types
from collections.abc import Callable
from typing import NoReturn

from study_effect_shapes import (
    effect_triplet,
    normalize_diagnostic_effects,
    normalize_effect_result,
)
from meta_globals import validate_confidence_level


class AnalysisBackendUnavailableError(RuntimeError):
    """Raised when the configured R analysis backend cannot service requests."""


_BackendCallable = Callable[..., object]


def _analysis_unavailable() -> NoReturn:
    raise AnalysisBackendUnavailableError(
        "The analysis backend (in-process rpy2/R) is not available in this "
        "build, so meta-analyses cannot be run."
    )


def _get_mult_from_r(conf_level: object) -> float:
    validate_confidence_level(conf_level)
    return 1.96


def _set_global_conf_level(conf_level: object) -> float:
    return float(validate_confidence_level(conf_level))


def _get_R_libpaths() -> list[object]:
    return []


def _get_r_version_string() -> None:
    return None


def _get_r_package_version(package_name: object) -> None:
    return None


def _reset_Rs_working_dir() -> None:
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
    x: object, metric_name: object, convert_to: object = "display.scale", n1: object = None
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
    metrics: object = ["Spec", "Sens"],
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


def _ma_dataset_to_simple_binary(
    table_model: object,
    var_name: object = "tmp_obj",
    include_raw_data: object = True,
    covs_to_include: object = None,
    studies: object = None,
) -> NoReturn:
    _analysis_unavailable()


def _ma_dataset_to_simple_continuous(
    table_model: object,
    var_name: object = "tmp_obj",
    covs_to_include: object = None,
    studies: object = None,
) -> NoReturn:
    _analysis_unavailable()


def _ma_dataset_to_simple_diagnostic(
    table_model: object,
    var_name: object = "tmp_obj",
    metric: object = "Sens",
    covs_to_include: object = None,
    effects_on_disp_scale: object = False,
    studies: object = None,
) -> NoReturn:
    _analysis_unavailable()


def _ma_dataset_to_simple_network(
    table_model: object,
    var_name: object = "tmp_obj",
    studies: object = None,
    data_type: object = None,
    outcome: object = None,
    follow_up: object = None,
    network_path: object = None,
) -> NoReturn:
    _analysis_unavailable()


def _get_available_methods(
    for_data_type: object = None,
    data_obj_name: object = None,
    metric: object = None,
    workflow: object = "standard",
) -> NoReturn:
    _analysis_unavailable()


def _get_params(method_name: object) -> NoReturn:
    _analysis_unavailable()


def _get_method_description(method_name: object) -> NoReturn:
    _analysis_unavailable()


def _run_continuous_ma(
    function_name: object,
    params: object,
    res_name: object = "result",
    cont_data_name: object = "tmp_obj",
) -> NoReturn:
    _analysis_unavailable()


def _run_binary_ma(
    function_name: object,
    params: object,
    res_name: object = "result",
    bin_data_name: object = "tmp_obj",
) -> NoReturn:
    _analysis_unavailable()


def _run_diagnostic_multi(
    function_names: object,
    list_of_params: object,
    res_name: object = "result",
    diag_data_name: object = "tmp_obj",
) -> NoReturn:
    _analysis_unavailable()


def _run_workflow_analysis(
    workflow: object,
    function_name: object,
    params: object,
    res_name: object = "result",
    data_name: object = "tmp_obj",
) -> NoReturn:
    _analysis_unavailable()


def _run_diagnostic_workflow(
    workflow: object,
    function_names: object,
    list_of_params: object,
    res_name: object = "result",
    diag_data_name: object = "tmp_obj",
) -> NoReturn:
    _analysis_unavailable()


def _run_meta_regression(
    dataset: object,
    study_names: object,
    cov_list: object,
    metric_name: object,
    data_name: object = "tmp_obj",
    results_name: object = "results_obj",
    fixed_effects: object = False,
    conf_level: object = None,
    params: object = None,
) -> NoReturn:
    _analysis_unavailable()


class _StubRObjects:
    @staticmethod
    def r(expression: object) -> list[float]:
        return [95.0]


class _StubRlibLoader:
    def load_metafor(self) -> None:
        return None

    def load_RCMetaR(self) -> None:
        return None

    def load_igraph(self) -> None:
        return None

    def load_grid(self) -> None:
        return None

    def load_gemtc(self) -> None:
        return None


class _StubMetaPyRModule(types.ModuleType):
    """Typed module-shaped compatibility surface for tests without in-process R."""

    _oma_stub_backend: bool
    AnalysisBackendUnavailableError: type[AnalysisBackendUnavailableError]
    get_mult_from_r: _BackendCallable
    set_global_conf_level: _BackendCallable
    get_R_libpaths: _BackendCallable
    get_r_version_string: _BackendCallable
    get_r_package_version: _BackendCallable
    reset_Rs_working_dir: _BackendCallable
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
    ma_dataset_to_simple_binary_robj: _BackendCallable
    ma_dataset_to_simple_continuous_robj: _BackendCallable
    ma_dataset_to_simple_diagnostic_robj: _BackendCallable
    ma_dataset_to_simple_network: _BackendCallable
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
    RlibLoader: type[_StubRlibLoader]

    def __init__(self) -> None:
        super().__init__("rc_metastudio.meta_py_r")
        self._oma_stub_backend = True
        self.AnalysisBackendUnavailableError = AnalysisBackendUnavailableError
        self.get_mult_from_r = _get_mult_from_r
        self.set_global_conf_level = _set_global_conf_level
        self.get_R_libpaths = _get_R_libpaths
        self.get_r_version_string = _get_r_version_string
        self.get_r_package_version = _get_r_package_version
        self.reset_Rs_working_dir = _reset_Rs_working_dir
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
        self.ma_dataset_to_simple_binary_robj = _ma_dataset_to_simple_binary
        self.ma_dataset_to_simple_continuous_robj = _ma_dataset_to_simple_continuous
        self.ma_dataset_to_simple_diagnostic_robj = _ma_dataset_to_simple_diagnostic
        self.ma_dataset_to_simple_network = _ma_dataset_to_simple_network
        self.get_available_methods = _get_available_methods
        self.get_params = _get_params
        self.get_method_description = _get_method_description
        self.get_analysis_plot_capabilities = _get_analysis_plot_capabilities
        self.run_binary_ma = _run_binary_ma
        self.run_continuous_ma = _run_continuous_ma
        self.run_diagnostic_multi = _run_diagnostic_multi
        self.run_workflow_analysis = _run_workflow_analysis
        self.run_diagnostic_workflow = _run_diagnostic_workflow
        self.run_meta_regression = _run_meta_regression
        self.ro = _StubRObjects
        self.RlibLoader = _StubRlibLoader


def _registered_backend() -> types.ModuleType | None:
    for module_name in ("rc_metastudio.meta_py_r", "meta_py_r"):
        backend = sys.modules.get(module_name)
        if backend is not None:
            return backend
    return None


def _register_backend(backend: types.ModuleType) -> types.ModuleType:
    sys.modules["rc_metastudio.meta_py_r"] = backend
    sys.modules["meta_py_r"] = backend
    return backend


def install_meta_py_r_backend() -> types.ModuleType:
    """Install and return the real R backend, or the test compatibility backend."""

    # The real backend is the in-process rpy2 module (meta_py_r). When R/rpy2
    # is unavailable -- notably in CI and GUI-only tests -- fall back to a pure
    # Python stub. Set RCMS_STUB_BACKEND=1 to force the stub even where R exists;
    # set RCMS_REQUIRE_IN_PROCESS_RPY2=1 to fail loudly instead of falling back.
    if os.environ.get("RCMS_STUB_BACKEND") == "1":
        return install_stub_meta_py_r()

    existing = _registered_backend()
    if existing is not None:
        return _register_backend(existing)

    try:
        import r_runtime

        r_runtime.configure_bundled_r_environment()
        from rc_metastudio import meta_py_r

        return meta_py_r
    except Exception:
        if (
            getattr(sys, "frozen", False)
            or os.environ.get("RCMS_REQUIRE_IN_PROCESS_RPY2") == "1"
        ):
            raise
        return install_stub_meta_py_r()


def install_stub_meta_py_r() -> types.ModuleType:
    existing = _registered_backend()
    if existing is not None and getattr(existing, "_oma_stub_backend", False):
        return _register_backend(existing)

    return _register_backend(_StubMetaPyRModule())


if os.environ.get("RCMS_STUB_BACKEND") == "1" and _registered_backend() is None:
    install_stub_meta_py_r()
