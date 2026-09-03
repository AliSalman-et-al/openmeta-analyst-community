import os
import sys

import pytest


sys.path.insert(0, os.path.abspath("src"))


def test_r_backend_composes_real_module_and_keeps_fakes_local():
    from rc_metastudio import r_backend
    from rc_metastudio import r_bridge

    r_bridge = r_backend.install_r_backend()

    assert r_bridge is sys.modules["rc_metastudio.r_bridge"]
    assert hasattr(r_bridge, "get_r_library_paths")
    assert r_bridge.get_analysis_plot_capabilities("binary", "method") == []
    assert r_bridge.get_r_library_paths() == []
    assert r_bridge.get_r_version_string() is None
    assert r_bridge.get_r_package_version("RCMetaR") is None
    assert r_bridge.reset_r_working_directory() is None
    assert r_bridge.execute_r_string("R.version.string") == [95.0]
    assert r_bridge.execute_r_function("identity", 95) == [95.0]
    assert r_bridge.effect_for_study(1, 2) is None
    assert r_bridge.continuous_effect_for_study(1, 2, 3) is None

    with pytest.raises(TypeError):
        r_bridge.get_r_library_paths(object())
    with pytest.raises(TypeError):
        r_bridge.get_r_version_string(object())
    with pytest.raises(TypeError):
        r_bridge.get_r_package_version()
    with pytest.raises(TypeError):
        r_bridge.reset_r_working_directory(object())
    with pytest.raises(TypeError):
        r_bridge.execute_r_string()
    with pytest.raises(TypeError):
        r_bridge.get_analysis_plot_capabilities("binary")
    with pytest.raises(TypeError):
        r_bridge.effect_for_study(1)
    with pytest.raises(TypeError):
        r_bridge.continuous_effect_for_study(1, 2)

    assert r_bridge.set_confidence_level(95) == 95.0
    fake = r_backend.make_test_backend()
    assert fake is not r_bridge
    assert fake.execute_r_string("R.version.string") == [95.0]
