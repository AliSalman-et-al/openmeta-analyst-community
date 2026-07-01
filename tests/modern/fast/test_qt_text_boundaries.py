import os
import sys


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


def test_invalid_qvariant_is_blank_at_text_boundaries():
    invalid_value = QtCore.QVariant()

    assert qt_text.to_native_text(invalid_value) == ""
    assert edit_list_models._to_native_text(invalid_value) == ""
    assert change_cov_type_form._to_native_text(invalid_value) == ""
    assert ma_data_table_view._to_text(invalid_value) == ""
    assert meta_form._qt_item_text(invalid_value) == ""
    assert meta_form._qt_text(invalid_value) == ""
    assert meta_form._qt_dialog_path(invalid_value) == ""
    assert main_wizard._qt_item_text(invalid_value) == ""
    assert ma_specs.MA_Specs._enum_item_value(object(), invalid_value) == ""
