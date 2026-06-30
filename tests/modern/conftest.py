import json
import os
from pathlib import Path


# Modern tests run without a live R backend; use the pure-Python stub.
os.environ.setdefault("OMA_STUB_BACKEND", "1")


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
    for item in items:
        entry = entries.get(item.nodeid.replace("\\", "/"))
        if not entry:
            continue
        marker_names = {entry.get("size"), entry.get("lane")}
        marker_names.update(entry.get("evidence", []))
        if entry.get("runtime_class") == "minutes":
            marker_names.add("slow")
        for marker_name in sorted(name for name in marker_names if name):
            item.add_marker(marker_name)
