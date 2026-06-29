import py_compile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_full_app_import_path_has_no_python2_syntax():
    for module in [
        "launch.py",
        "meta_form.py",
        "ui_meta.py",
        "ma_data_table_view.py",
        "ma_data_table_model.py",
        "ma_dataset.py",
        "settings.py",
        "main_wizard.py",
        "add_new_dialogs.py",
        "results_window.py",
        "ma_specs.py",
        "diag_metrics.py",
        "meta_reg_form.py",
        "meta_subgroup_form.py",
        "edit_dialog.py",
        "edit_group_name_form.py",
        "change_cov_type_form.py",
        "network_view.py",
        "conf_level_dialog.py",
        "easter_egg.py",
        "binary_data_form.py",
        "calculator_routines.py",
        "continuous_data_form.py",
        "diagnostic_data_form.py",
        "edit_forest_plot_form.py",
        "edit_list_models.py",
        "ma_text_edit.py",
        "meta_py_r.py",
        "qconsole.py",
    ]:
        py_compile.compile(str(ROOT / "src" / module), doraise=True)
