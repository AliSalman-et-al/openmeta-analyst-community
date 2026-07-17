import os
import sys
import types

from study_effect_shapes import (
    effect_triplet,
    normalize_diagnostic_effects,
    normalize_effect_result,
)
from meta_globals import validate_confidence_level


class AnalysisBackendUnavailableError(RuntimeError):
    """Raised when the configured R analysis backend cannot service requests."""


def install_meta_py_r_backend():
    # The real backend is the in-process rpy2 module (meta_py_r). When R/rpy2
    # is unavailable -- notably in CI and GUI-only tests -- fall back to a pure
    # Python stub. Set RCMS_STUB_BACKEND=1 to force the stub even where R exists;
    # set RCMS_REQUIRE_IN_PROCESS_RPY2=1 to fail loudly instead of falling back.
    if os.environ.get("RCMS_STUB_BACKEND") == "1":
        return install_stub_meta_py_r()
    for module_name in ("rc_metastudio.meta_py_r", "meta_py_r"):
        if module_name in sys.modules:
            backend = sys.modules[module_name]
            sys.modules["rc_metastudio.meta_py_r"] = backend
            sys.modules["meta_py_r"] = backend
            return backend
    try:
        import r_runtime

        r_runtime.configure_bundled_r_environment()
        from rc_metastudio import meta_py_r

        return meta_py_r
    except Exception:
        if os.environ.get("RCMS_REQUIRE_IN_PROCESS_RPY2") == "1":
            raise
        return install_stub_meta_py_r()


def install_stub_meta_py_r():
    existing = sys.modules.get("rc_metastudio.meta_py_r") or sys.modules.get(
        "meta_py_r"
    )
    if getattr(existing, "_oma_stub_backend", False):
        sys.modules["rc_metastudio.meta_py_r"] = existing
        sys.modules["meta_py_r"] = existing
        return existing

    meta_py_r = existing or types.ModuleType("rc_metastudio.meta_py_r")
    meta_py_r._oma_stub_backend = True
    meta_py_r.AnalysisBackendUnavailableError = AnalysisBackendUnavailableError

    def _analysis_unavailable(*args, **kwargs):
        raise AnalysisBackendUnavailableError(
            "The analysis backend (in-process rpy2/R) is not available in this "
            "build, so meta-analyses cannot be run."
        )

    def _get_mult_from_r(conf_level):
        validate_confidence_level(conf_level)
        return 1.96

    def _set_global_conf_level(conf_level):
        return float(validate_confidence_level(conf_level))

    meta_py_r.get_mult_from_r = _get_mult_from_r
    meta_py_r.set_global_conf_level = _set_global_conf_level
    meta_py_r.get_R_libpaths = lambda: []
    meta_py_r.get_r_version_string = lambda: None
    meta_py_r.get_r_package_version = lambda package_name: None
    meta_py_r.reset_Rs_working_dir = lambda: None
    meta_py_r.execute_r_string = lambda expression: [95.0]
    meta_py_r.execute_r_function = lambda function_name, *args, **kwargs: [95.0]
    meta_py_r.binary_convert_scale = lambda value, *args, **kwargs: value
    meta_py_r.continuous_convert_scale = lambda value, *args, **kwargs: value
    meta_py_r.diagnostic_convert_scale = lambda value, *args, **kwargs: value
    meta_py_r.effect_triplet = effect_triplet
    meta_py_r.normalize_effect_result = normalize_effect_result
    meta_py_r.normalize_diagnostic_effects = normalize_diagnostic_effects
    meta_py_r.effect_for_study = lambda *args, **kwargs: None
    meta_py_r.continuous_effect_for_study = lambda *args, **kwargs: None
    meta_py_r.diagnostic_effects_for_study = lambda *args, **kwargs: {}
    meta_py_r.impute_bin_data = lambda *args, **kwargs: {"FAIL": True}
    meta_py_r.impute_cont_data = lambda *args, **kwargs: {"succeeded": False}
    meta_py_r.impute_pre_post_cont_data = lambda *args, **kwargs: {"succeeded": False}
    meta_py_r.impute_diag_data = lambda *args, **kwargs: {
        "TP": None,
        "TN": None,
        "FP": None,
        "FN": None,
    }
    meta_py_r.back_calc_cont_data = lambda *args, **kwargs: {"FAIL": True}
    meta_py_r.ma_dataset_to_simple_binary_robj = _analysis_unavailable
    meta_py_r.ma_dataset_to_simple_continuous_robj = _analysis_unavailable
    meta_py_r.ma_dataset_to_simple_diagnostic_robj = _analysis_unavailable
    meta_py_r.ma_dataset_to_simple_network = _analysis_unavailable
    meta_py_r.get_available_methods = _analysis_unavailable
    meta_py_r.get_params = _analysis_unavailable
    meta_py_r.get_method_description = _analysis_unavailable
    meta_py_r.get_analysis_plot_capabilities = lambda *args, **kwargs: []
    meta_py_r.run_binary_ma = _analysis_unavailable
    meta_py_r.run_continuous_ma = _analysis_unavailable
    meta_py_r.run_diagnostic_multi = _analysis_unavailable
    meta_py_r.run_workflow_analysis = _analysis_unavailable
    meta_py_r.run_diagnostic_workflow = _analysis_unavailable
    meta_py_r.run_meta_regression = _analysis_unavailable
    meta_py_r.ro = type("RObjects", (), {"r": staticmethod(lambda expression: [95.0])})
    meta_py_r.RlibLoader = lambda: type(
        "RlibLoader",
        (),
        {
            "load_metafor": lambda self: None,
            "load_RCMetaR": lambda self: None,
            "load_igraph": lambda self: None,
            "load_grid": lambda self: None,
            "load_gemtc": lambda self: None,
        },
    )()
    sys.modules["rc_metastudio.meta_py_r"] = meta_py_r
    sys.modules["meta_py_r"] = meta_py_r
    return meta_py_r


if os.environ.get("RCMS_STUB_BACKEND") == "1" and "meta_py_r" not in sys.modules:
    install_stub_meta_py_r()
