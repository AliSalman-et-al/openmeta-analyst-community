import os
import sys
from pathlib import Path

import pytest


# Python verification tests run without a live R backend; use the pure-Python stub.
os.environ.setdefault("RCMS_STUB_BACKEND", "1")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_ROOT = Path(__file__).resolve().parents[1]
_APP_PACKAGE = _ROOT / "src" / "rc_metastudio"
for _path in (_APP_PACKAGE, _APP_PACKAGE / "forms"):
    _path_text = str(_path)
    if _path_text not in sys.path:
        sys.path.insert(0, _path_text)

_QAPPLICATION = None


def _get_qapplication():
    global _QAPPLICATION
    from PyQt6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    _QAPPLICATION = app
    return app


@pytest.fixture(scope="session")
def qapp():
    return _get_qapplication()


@pytest.fixture(scope="session", autouse=True)
def _qapplication_for_qt_test_selections(request):
    if getattr(request.config, "_needs_qapplication", False):
        return _get_qapplication()
    return None


@pytest.fixture(autouse=True)
def _isolate_qsettings_for_qt_tests(request, tmp_path):
    if not (
        request.node.get_closest_marker("gui")
        or request.node.get_closest_marker("qsettings")
    ):
        return

    from PyQt6 import QtCore

    QtCore.QSettings.setPath(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        str(tmp_path),
    )
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)


def pytest_collection_modifyitems(config, items):
    config._needs_qapplication = False
    for item in items:
        relative = item.path.resolve().relative_to(_ROOT).as_posix()
        lane = next(
            (
                marker
                for marker, segment in (
                    ("fast", "/python/fast/"),
                    ("gui", "/python/gui/"),
                    ("r_stack", "/r_stack/"),
                    ("golden", "/analysis_regression/golden/"),
                    ("packaging_contract", "/packaging/contract/"),
                    ("packaged_smoke", "/packaged_smoke/"),
                )
                if segment in f"/{relative}"
            ),
            None,
        )
        if lane is not None and item.get_closest_marker(lane) is None:
            item.add_marker(getattr(pytest.mark, lane))
    config._needs_qapplication = any(
        item.get_closest_marker("gui") is not None for item in items
    )
