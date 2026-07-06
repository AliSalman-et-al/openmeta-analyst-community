from PyQt5 import QtCore


def test_verification_path_uses_pyqt5():
    assert QtCore.PYQT_VERSION_STR.startswith("5.")


def test_verification_path_uses_same_qt5_runtime_version_everywhere():
    assert QtCore.qVersion() == "5.15.2"
