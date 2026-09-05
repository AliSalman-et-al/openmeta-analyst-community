import os
import sys
from pathlib import Path
import pytest

pytestmark = pytest.mark.usefixtures("inject_python_boundary")


sys.path.insert(0, os.path.abspath("src"))

from rc_metastudio import r_backend

r_backend.install_r_backend()

from rc_metastudio import covariate_type_dialog
from rc_metastudio import edit_list_models
from rc_metastudio import dataset_table_view
from rc_metastudio import analysis_setup_dialog
from rc_metastudio import main_wizard
from rc_metastudio import main_window
from rc_metastudio import qt_text


ROOT = Path(__file__).resolve().parents[3]


def test_none_is_blank_at_text_boundaries():
    assert qt_text.to_native_text(None) == ""
    assert qt_text.is_blank(None)
    assert edit_list_models._to_native_text(None) == ""
    assert covariate_type_dialog._to_native_text(None) == ""
    assert dataset_table_view._to_text(None) == ""
    assert main_window._qt_item_text(None) == ""
    assert main_window._qt_text(None) == ""
    assert main_window._qt_dialog_path(None) == ""
    assert main_wizard._qt_item_text(None) == ""
    specs = analysis_setup_dialog.AnalysisSetupDialog.__new__(
        analysis_setup_dialog.AnalysisSetupDialog
    )
    assert specs._enum_item_value(None) == ""


def test_old_qt_string_and_item_color_apis_stay_inside_compat_boundaries():
    forbidden_patterns = (
        "." + "trimmed(",
        "." + "to" + "Utf8(",
        "." + "exec" + "_(",
        "." + "reset(",
        "def " + "reset(",
        "Q" + "Variant(",
        "QtCore." + "Q" + "Variant",
        "set" + "TextColor(",
        "set" + "BackgroundColor(",
        "SIG" + "NAL(",
        "SL" + "OT(",
        "QObject." + "connect",
        "." + "to" + "String(",
    )

    offenders = []
    for path in (ROOT / "src").rglob("*.py"):
        relative_path = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            if pattern in text:
                offenders.append(f"{relative_path.as_posix()}: {pattern}")

    assert offenders == []
