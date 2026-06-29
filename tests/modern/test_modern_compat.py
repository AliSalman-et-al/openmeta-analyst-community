import os
import sys


sys.path.insert(0, os.path.abspath("src"))


def test_modern_compat_installs_stub_backend(monkeypatch):
    legacy_qt4_name = "Py" + "Qt4"
    for name in list(sys.modules):
        if name == legacy_qt4_name or name.startswith(legacy_qt4_name + "."):
            del sys.modules[name]
    monkeypatch.setenv("OMA_STUB_BACKEND", "1")

    import modern_compat

    meta_py_r = modern_compat.install()

    assert meta_py_r is sys.modules["meta_py_r"]
    assert hasattr(meta_py_r, "get_R_libpaths")
    assert legacy_qt4_name not in sys.modules
