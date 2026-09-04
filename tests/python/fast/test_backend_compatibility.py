import sys


def test_r_backend_composes_only_the_real_module():
    from rc_metastudio import r_backend
    from rc_metastudio import r_bridge

    r_bridge = r_backend.install_r_backend()

    assert r_bridge is sys.modules["rc_metastudio.r_bridge"]
    assert r_backend.is_backend_installed()
    assert hasattr(r_bridge, "run_versioned_analysis_request")
