import py_compile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
APP_PACKAGE = ROOT / "src" / "rc_metastudio"

RETIRED_LEGACY_MODULES = {
    "edit_forest_plot_form.py",
    "ma_text_edit.py",
    "new_outcome_form.py",
    "win_prelaunch.py",
}


def test_full_app_import_path_has_no_python2_syntax():
    for module in [
        "launch.py",
        "meta_form.py",
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
        "binary_data_form.py",
        "calculator_routines.py",
        "continuous_data_form.py",
        "diagnostic_data_form.py",
        "edit_list_models.py",
        "meta_py_r.py",
    ]:
        py_compile.compile(str(APP_PACKAGE / module), doraise=True)


def test_retired_modules_are_not_on_the_application_import_path():
    for module in RETIRED_LEGACY_MODULES:
        assert not (APP_PACKAGE / module).exists()


def test_application_source_lives_under_rc_metastudio_package():
    loose_python_source = sorted(
        path.name for path in (ROOT / "src").glob("*.py") if path.name != "__init__.py"
    )

    assert loose_python_source == []
    assert (APP_PACKAGE / "launch.py").exists()
    assert not any((APP_PACKAGE / "forms").glob("ui_*.py"))
    assert not (APP_PACKAGE / "ui_meta.py").exists()
    assert not (APP_PACKAGE / "ui_results_window.py").exists()
    assert (APP_PACKAGE / "images" / "icons.qrc").exists()


def test_polyglot_roots_hold_r_package_and_packaging_definitions():
    retired_product_spec = "OpenMeta" + "Analyst.spec"

    assert (ROOT / "r" / "RCMetaR" / "DESCRIPTION").exists()
    assert (ROOT / "packaging" / "pyinstaller" / "rc-metastudio.spec").exists()
    assert not (ROOT / "src" / "R" / "RCMetaR").exists()
    assert not (ROOT / "src" / retired_product_spec).exists()
