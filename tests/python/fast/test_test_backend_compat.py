import os
import sys

import pytest


sys.path.insert(0, os.path.abspath("src"))


def test_test_backend_compat_installs_stub_backend(monkeypatch):
    legacy_qt4_name = "Py" + "Qt4"
    for name in list(sys.modules):
        if name == legacy_qt4_name or name.startswith(legacy_qt4_name + "."):
            del sys.modules[name]
    monkeypatch.setenv("RCMS_STUB_BACKEND", "1")

    import test_backend_compat
    import meta_py_r_backend

    def register_backend(backend):
        monkeypatch.setitem(sys.modules, "rc_metastudio.meta_py_r", backend)
        monkeypatch.setitem(sys.modules, "meta_py_r", backend)
        return backend

    monkeypatch.setattr(meta_py_r_backend, "_register_backend", register_backend)

    meta_py_r = test_backend_compat.install()

    assert meta_py_r is sys.modules["meta_py_r"]
    assert hasattr(meta_py_r, "get_R_libpaths")
    assert hasattr(meta_py_r, "ma_dataset_to_simple_network")
    assert meta_py_r.get_analysis_plot_capabilities("binary", "method") == []
    assert meta_py_r.get_R_libpaths() == []
    assert meta_py_r.get_r_version_string() is None
    assert meta_py_r.get_r_package_version("RCMetaR") is None
    assert meta_py_r.reset_Rs_working_dir() is None
    assert meta_py_r.execute_r_string("R.version.string") == [95.0]
    assert meta_py_r.execute_r_function("identity", 95) == [95.0]
    assert meta_py_r.effect_for_study(1, 2) is None
    assert meta_py_r.continuous_effect_for_study(1, 2, 3) is None

    with pytest.raises(TypeError):
        meta_py_r.get_R_libpaths(object())
    with pytest.raises(TypeError):
        meta_py_r.get_r_version_string(object())
    with pytest.raises(TypeError):
        meta_py_r.get_r_package_version()
    with pytest.raises(TypeError):
        meta_py_r.reset_Rs_working_dir(object())
    with pytest.raises(TypeError):
        meta_py_r.execute_r_string()
    with pytest.raises(TypeError):
        meta_py_r.get_analysis_plot_capabilities("binary")
    with pytest.raises(TypeError):
        meta_py_r.effect_for_study(1)
    with pytest.raises(TypeError):
        meta_py_r.continuous_effect_for_study(1, 2)

    with pytest.raises(meta_py_r.AnalysisBackendUnavailableError):
        meta_py_r.ma_dataset_to_simple_network(object())
    assert meta_py_r.set_global_conf_level(95) == 95.0
    assert legacy_qt4_name not in sys.modules
