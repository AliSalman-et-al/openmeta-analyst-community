import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rc_metastudio.two_way_dict import TwoWayDict


def test_two_way_dict_uses_python3_dict_views_and_reverse_lookup():
    mapping = TwoWayDict({"a": 1, "b": 2})

    assert "a" in mapping
    assert list(mapping.keys()) == ["a", "b"]
    assert list(mapping.values()) == [1, 2]
    assert list(mapping.items()) == [("a", 1), ("b", 2)]
    assert mapping.reversed_items() == [(1, "a"), (2, "b")]


def test_two_way_dict_replaces_existing_reverse_mapping_under_python3():
    mapping = TwoWayDict({"a": 1, "b": 2})

    mapping["c"] = 2

    assert "b" not in mapping
    assert mapping["c"] == 2
    assert mapping.key(2) == "c"
