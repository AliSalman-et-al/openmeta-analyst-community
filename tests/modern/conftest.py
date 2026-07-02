import json
import os
from pathlib import Path

import pytest


# Modern tests run without a live R backend; use the pure-Python stub.
os.environ.setdefault("OMA_STUB_BACKEND", "1")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_QAPPLICATION = None


def _get_qapplication():
    global _QAPPLICATION
    from PyQt5 import QtWidgets

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


def _taxonomy_entries():
    root = Path(__file__).resolve().parents[2]
    taxonomy_path = root / "docs" / "modernization" / "test-taxonomy.json"
    try:
        taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    return {
        entry["nodeid"].replace("\\", "/"): entry
        for entry in taxonomy.get("tests", [])
        if isinstance(entry, dict) and "nodeid" in entry
    }


def pytest_collection_modifyitems(config, items):
    entries = _taxonomy_entries()
    config._needs_qapplication = False
    for item in items:
        entry = entries.get(item.nodeid.replace("\\", "/"))
        if not entry:
            continue
        has_qt_dependency = "qt" in entry.get("external_dependencies", [])
        has_gui_evidence = "gui_compatibility" in entry.get("evidence", [])
        if has_qt_dependency or has_gui_evidence:
            config._needs_qapplication = True
        marker_names = {entry.get("size"), entry.get("lane")}
        marker_names.update(entry.get("evidence", []))
        if entry.get("runtime_class") == "minutes":
            marker_names.add("slow")
        for marker_name in sorted(name for name in marker_names if name):
            item.add_marker(marker_name)
