import os
import sys
from pathlib import Path


sys.path.insert(0, os.path.abspath("src"))
sys.path.insert(0, os.path.abspath(os.path.join("src", "forms")))

import modern_compat

modern_compat.install()

from PyQt5 import QtCore

import change_cov_type_form
import edit_list_models
import ma_data_table_view
import ma_specs
import main_wizard
import meta_form
import qt_text


ROOT = Path(__file__).resolve().parents[3]


def test_invalid_qvariant_is_blank_at_text_boundaries():
    invalid_value = QtCore.QVariant()

    assert qt_text.to_native_text(invalid_value) == ""
    assert qt_text.is_blank(invalid_value)
    assert edit_list_models._to_native_text(invalid_value) == ""
    assert change_cov_type_form._to_native_text(invalid_value) == ""
    assert ma_data_table_view._to_text(invalid_value) == ""
    assert meta_form._qt_item_text(invalid_value) == ""
    assert meta_form._qt_text(invalid_value) == ""
    assert meta_form._qt_dialog_path(invalid_value) == ""
    assert main_wizard._qt_item_text(invalid_value) == ""
    assert ma_specs.MA_Specs._enum_item_value(object(), invalid_value) == ""


def test_old_qt_string_and_item_color_apis_stay_inside_compat_boundaries():
    allowed_paths = {
        Path("src/qt_text.py"),
    }
    forbidden_patterns = (
        ".trimmed(",
        ".toUtf8(",
        "setTextColor(",
        "setBackgroundColor(",
    )

    offenders = []
    for path in (ROOT / "src").rglob("*.py"):
        relative_path = path.relative_to(ROOT)
        if relative_path in allowed_paths:
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            if pattern in text:
                offenders.append(f"{relative_path.as_posix()}: {pattern}")

    assert offenders == []
