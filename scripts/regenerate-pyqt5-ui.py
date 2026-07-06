from pathlib import Path
import subprocess
import sys

from PyQt5 import uic


ROOT = Path(__file__).resolve().parents[1]

UI_MODULES = {
    "src/rc_metastudio/forms/binary_data_form2.ui": "src/rc_metastudio/forms/ui_binary_data_form.py",
    "src/rc_metastudio/forms/change_cov_type_form.ui": "src/rc_metastudio/forms/ui_change_cov_type.py",
    "src/rc_metastudio/forms/change_group_name_dlg.ui": "src/rc_metastudio/forms/ui_edit_group_name.py",
    "src/rc_metastudio/forms/choose_back_calc_result_form.ui": "src/rc_metastudio/forms/ui_choose_back_calc_result_form.py",
    "src/rc_metastudio/forms/choose_metric_page.ui": "src/rc_metastudio/forms/ui_choose_metric_page.py",
    "src/rc_metastudio/forms/continuous_data_form.ui": "src/rc_metastudio/forms/ui_continuous_data_form.py",
    "src/rc_metastudio/forms/cov_reg_dlg2.ui": "src/rc_metastudio/forms/ui_meta_reg.py",
    "src/rc_metastudio/forms/cov_subgroup_dlg.ui": "src/rc_metastudio/forms/ui_cov_subgroup_dlg.py",
    "src/rc_metastudio/forms/csv_import_page.ui": "src/rc_metastudio/forms/ui_csv_import_page.py",
    "src/rc_metastudio/forms/data_type_page.ui": "src/rc_metastudio/forms/ui_data_type_page.py",
    "src/rc_metastudio/forms/diag_explain_form.ui": "src/rc_metastudio/forms/ui_diagnostic_explain_dlg.py",
    "src/rc_metastudio/forms/diagnostic_data_form.ui": "src/rc_metastudio/forms/ui_diagnostic_data_form.py",
    "src/rc_metastudio/forms/diagnostic_metrics.ui": "src/rc_metastudio/forms/ui_diagnostic_metrics.py",
    "src/rc_metastudio/forms/edit_dialog2.ui": "src/rc_metastudio/forms/ui_edit_dialog.py",
    "src/rc_metastudio/forms/edit_forest_plot.ui": "src/rc_metastudio/forms/ui_edit_forest_plot.py",
    "src/rc_metastudio/forms/ma_specs2.ui": "src/rc_metastudio/forms/ui_ma_specs.py",
    "src/rc_metastudio/forms/network_view_window.ui": "src/rc_metastudio/forms/ui_network_view.py",
    "src/rc_metastudio/forms/new_covariate_dlg.ui": "src/rc_metastudio/forms/ui_new_covariate.py",
    "src/rc_metastudio/forms/new_follow_up_dlg.ui": "src/rc_metastudio/forms/ui_new_follow_up.py",
    "src/rc_metastudio/forms/new_group_dlg.ui": "src/rc_metastudio/forms/ui_new_group.py",
    "src/rc_metastudio/forms/new_outcome_dlg.ui": "src/rc_metastudio/forms/ui_new_outcome.py",
    "src/rc_metastudio/forms/new_study_dlg.ui": "src/rc_metastudio/forms/ui_new_study.py",
    "src/rc_metastudio/forms/outcome_name_page.ui": "src/rc_metastudio/forms/ui_outcome_name_page.py",
    "src/rc_metastudio/forms/running.ui": "src/rc_metastudio/forms/ui_running.py",
    "src/rc_metastudio/forms/welcome_page.ui": "src/rc_metastudio/forms/ui_welcome_page.py",
    "src/rc_metastudio/forms/meta.ui": "src/rc_metastudio/ui_meta.py",
    "src/rc_metastudio/forms/results_window.ui": "src/rc_metastudio/ui_results_window.py",
}


def compile_ui(source, target):
    with target.open("w", encoding="utf-8", newline="\n") as output:
        uic.compileUi(str(source), output)


def main():
    for source_name, target_name in UI_MODULES.items():
        compile_ui(ROOT / source_name, ROOT / target_name)

    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "PyQt5.pyrcc_main",
            "-o",
            str(ROOT / "src/rc_metastudio/forms/icons_rc.py"),
            "icons.qrc",
        ],
        cwd=str(ROOT / "src/rc_metastudio/images"),
    )


if __name__ == "__main__":
    main()
