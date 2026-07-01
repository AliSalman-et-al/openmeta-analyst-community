import os
import sys
import types


def install_meta_py_r_backend():
    # The real backend is the in-process rpy2 module (meta_py_r). When R/rpy2
    # is unavailable -- notably in CI and GUI-only tests -- fall back to a pure
    # Python stub. Set OMA_STUB_BACKEND=1 to force the stub even where R exists;
    # set OMA_REQUIRE_IN_PROCESS_RPY2=1 to fail loudly instead of falling back.
    if os.environ.get("OMA_STUB_BACKEND") == "1":
        return install_stub_meta_py_r()
    if "meta_py_r" in sys.modules:
        return sys.modules["meta_py_r"]
    try:
        import r_runtime

        r_runtime.configure_bundled_r_environment()
        import meta_py_r

        return meta_py_r
    except Exception:
        if os.environ.get("OMA_REQUIRE_IN_PROCESS_RPY2") == "1":
            raise
        return install_stub_meta_py_r()


def _install_meta_py_r_backend():
    return install_meta_py_r_backend()


def install_stub_meta_py_r():
    existing = sys.modules.get("meta_py_r")
    if getattr(existing, "_oma_stub_backend", False):
        return existing

    meta_py_r = types.ModuleType("meta_py_r")
    meta_py_r._oma_stub_backend = True

    def _analysis_unavailable(*args, **kwargs):
        raise RuntimeError(
            "The analysis backend (in-process rpy2/R) is not available in this "
            "build, so meta-analyses cannot be run."
        )

    meta_py_r.get_mult_from_r = lambda conf_level: 1.96
    meta_py_r.get_R_libpaths = lambda: []
    meta_py_r.reset_Rs_working_dir = lambda: None
    meta_py_r.execute_r_string = lambda expression: [95.0]
    meta_py_r.execute_r_function = lambda function_name, *args, **kwargs: [95.0]
    meta_py_r.binary_convert_scale = lambda value, *args, **kwargs: value
    meta_py_r.continuous_convert_scale = lambda value, *args, **kwargs: value
    meta_py_r.diagnostic_convert_scale = lambda value, *args, **kwargs: value
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
    meta_py_r.get_available_methods = _analysis_unavailable
    meta_py_r.get_params = _analysis_unavailable
    meta_py_r.get_method_description = _analysis_unavailable
    meta_py_r.run_binary_ma = _analysis_unavailable
    meta_py_r.run_continuous_ma = _analysis_unavailable
    meta_py_r.run_diagnostic_multi = _analysis_unavailable
    meta_py_r.run_meta_method = _analysis_unavailable
    meta_py_r.run_meta_method_diag = _analysis_unavailable
    meta_py_r.run_meta_regression = _analysis_unavailable
    meta_py_r.ro = type("RObjects", (), {"r": staticmethod(lambda expression: [95.0])})
    meta_py_r.RlibLoader = lambda: type(
        "RlibLoader",
        (),
        {
            "load_metafor": lambda self: None,
            "load_OpenMetaR": lambda self: None,
            "load_igraph": lambda self: None,
            "load_grid": lambda self: None,
            "load_gemtc": lambda self: None,
        },
    )()
    sys.modules["meta_py_r"] = meta_py_r
    return meta_py_r


def _install_stub_meta_py_r():
    return install_stub_meta_py_r()


if os.environ.get("OMA_STUB_BACKEND") == "1" and "meta_py_r" not in sys.modules:
    install_stub_meta_py_r()
