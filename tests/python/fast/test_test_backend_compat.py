import os
import sys


sys.path.insert(0, os.path.abspath("src"))


def test_test_backend_compat_installs_stub_backend(monkeypatch):
    legacy_qt4_name = "Py" + "Qt4"
    for name in list(sys.modules):
        if name == legacy_qt4_name or name.startswith(legacy_qt4_name + "."):
            del sys.modules[name]
    monkeypatch.setenv("RCMS_STUB_BACKEND", "1")

    import test_backend_compat

    meta_py_r = test_backend_compat.install()

    assert meta_py_r is sys.modules["meta_py_r"]
    assert hasattr(meta_py_r, "get_R_libpaths")
    assert meta_py_r.set_global_conf_level(95) == 95.0
    assert legacy_qt4_name not in sys.modules
