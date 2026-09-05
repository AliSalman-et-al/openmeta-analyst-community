# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime manifest for the generated Qt form modules."""

from pathlib import Path


CANONICAL_FORMS = {
    Path("src/rc_metastudio/forms/about_legal.ui"): Path("rc_metastudio/forms/ui_about_legal.py"),
    Path("src/rc_metastudio/forms/binary_data_dialog.ui"): Path("rc_metastudio/forms/ui_binary_data_dialog.py"),
    Path("src/rc_metastudio/forms/covariate_type_dialog.ui"): Path("rc_metastudio/forms/ui_covariate_type_dialog.py"),
    Path("src/rc_metastudio/forms/edit_name_dialog.ui"): Path("rc_metastudio/forms/ui_edit_name_dialog.py"),
    Path("src/rc_metastudio/forms/binary_back_calculation_dialog.ui"): Path("rc_metastudio/forms/ui_binary_back_calculation_dialog.py"),
    Path("src/rc_metastudio/forms/choose_metric_page.ui"): Path("rc_metastudio/forms/ui_choose_metric_page.py"),
    Path("src/rc_metastudio/forms/confidence_level_dialog.ui"): Path("rc_metastudio/forms/ui_confidence_level_dialog.py"),
    Path("src/rc_metastudio/forms/continuous_back_calculation_dialog.ui"): Path("rc_metastudio/forms/ui_continuous_back_calculation_dialog.py"),
    Path("src/rc_metastudio/forms/continuous_data_dialog.ui"): Path("rc_metastudio/forms/ui_continuous_data_dialog.py"),
    Path("src/rc_metastudio/forms/publication_bias_dialog.ui"): Path("rc_metastudio/forms/ui_publication_bias_dialog.py"),
    Path("src/rc_metastudio/forms/subgroup_analysis_dialog.ui"): Path("rc_metastudio/forms/ui_subgroup_analysis_dialog.py"),
    Path("src/rc_metastudio/forms/csv_import_page.ui"): Path("rc_metastudio/forms/ui_csv_import_page.py"),
    Path("src/rc_metastudio/forms/data_type_page.ui"): Path("rc_metastudio/forms/ui_data_type_page.py"),
    Path("src/rc_metastudio/forms/diagnostic_data_dialog.ui"): Path("rc_metastudio/forms/ui_diagnostic_data_dialog.py"),
    Path("src/rc_metastudio/forms/diagnostic_metrics_dialog.ui"): Path("rc_metastudio/forms/ui_diagnostic_metrics_dialog.py"),
    Path("src/rc_metastudio/forms/edit_dialog.ui"): Path("rc_metastudio/forms/ui_edit_dialog.py"),
    Path("src/rc_metastudio/forms/edit_plot_dialog.ui"): Path("rc_metastudio/forms/ui_edit_plot_dialog.py"),
    Path("src/rc_metastudio/forms/funnel_plot_editor_dialog.ui"): Path("rc_metastudio/forms/ui_funnel_plot_editor_dialog.py"),
    Path("src/rc_metastudio/forms/analysis_setup_dialog.ui"): Path("rc_metastudio/forms/ui_analysis_setup_dialog.py"),
    Path("src/rc_metastudio/forms/main_window.ui"): Path("rc_metastudio/ui_main_window.py"),
    Path("src/rc_metastudio/forms/new_covariate_dialog.ui"): Path("rc_metastudio/forms/ui_new_covariate_dialog.py"),
    Path("src/rc_metastudio/forms/new_follow_up_dialog.ui"): Path("rc_metastudio/forms/ui_new_follow_up_dialog.py"),
    Path("src/rc_metastudio/forms/new_group_dialog.ui"): Path("rc_metastudio/forms/ui_new_group_dialog.py"),
    Path("src/rc_metastudio/forms/new_outcome_dialog.ui"): Path("rc_metastudio/forms/ui_new_outcome_dialog.py"),
    Path("src/rc_metastudio/forms/new_study_dialog.ui"): Path("rc_metastudio/forms/ui_new_study_dialog.py"),
    Path("src/rc_metastudio/forms/outcome_name_page.ui"): Path("rc_metastudio/forms/ui_outcome_name_page.py"),
    Path("src/rc_metastudio/forms/results_window.ui"): Path("rc_metastudio/ui_results_window.py"),
    Path("src/rc_metastudio/forms/progress_dialog.ui"): Path("rc_metastudio/forms/ui_progress_dialog.py"),
    Path("src/rc_metastudio/forms/welcome_page.ui"): Path("rc_metastudio/forms/ui_welcome_page.py"),
}
