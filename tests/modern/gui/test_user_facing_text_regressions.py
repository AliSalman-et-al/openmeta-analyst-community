from pathlib import Path
import sys

from PyQt5 import QtWidgets


ROOT = Path(__file__).resolve().parents[3]
HELP_HTML = sorted(
    path.relative_to(ROOT).as_posix() for path in (ROOT / "doc").glob("*.html")
)


def _read(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _combined_text(paths):
    return "\n".join(_read(path) for path in paths)


def test_issue_94_current_outcome_and_follow_up_labels_can_expand():
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "src" / "forms"))
    from ui_meta import Ui_MainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(window)

    for label in (ui.cur_outcome_lbl, ui.cur_time_lbl):
        assert label.maximumWidth() > 80
        assert label.sizePolicy().horizontalPolicy() != QtWidgets.QSizePolicy.Fixed

    window.deleteLater()
    app.processEvents()


def test_issue_76_to_105_reported_bad_user_facing_strings_are_absent():
    text = _combined_text(
        [
            "src/forms/ui_csv_import_page.py",
            "src/forms/csv_import_page.ui",
            "src/forms/ui_meta_reg.py",
            "src/forms/cov_reg_dlg2.ui",
            "src/forms/ui_welcome_page.py",
            "src/forms/welcome_page.ui",
            "src/forms/ui_diagnostic_data_form.py",
            "src/forms/diagnostic_data_form.ui",
            "src/forms/ui_data_type_page.py",
            "src/forms/data_type_page.ui",
            "src/forms/ui_edit_dialog.py",
            "src/forms/edit_dialog2.ui",
            "src/ui_meta.py",
            "src/meta.ui",
            "src/ui_results_window.py",
            "src/results_window.ui",
            "src/results_window.py",
            "src/conf_level_dialog.py",
            "src/main_wizard.py",
            "src/meta_form.py",
            "src/binary_data_form.py",
            "src/continuous_data_form.py",
            "src/diagnostic_data_form.py",
            "src/calculator_routines.py",
            "src/meta_reg_form.py",
            "src/ma_data_table_model.py",
            "src/ma_data_table_view.py",
            "src/meta_globals.py",
            "src/R/OpenMetaR/R/binary_methods.r",
            "src/R/OpenMetaR/R/continuous_methods.r",
            "src/R/OpenMetaR/R/diagnostic_methods.r",
            "src/R/OpenMetaR/R/meta_methods.r",
            "src/R/OpenMetaR/R/plotting.r",
            "src/R/OpenMetaR/R/utilities.r",
            *HELP_HTML,
        ]
    )

    bad_strings = [
        "Delimter:",
        "csv exported from excel?",
        "select csv file ...",
        "No data in CSV!, try again",
        "trying to import csv, try again",
        "Create a new Project",
        "open recent ...",
        "www.google.com",
        '"Dialog"))',
        '"whoops"',
        '"whoops."',
        '"Whoops."',
        "regression coefficient",
        "follow ups",
        "undo (ctrl + z)",
        "redo (ctrl + y)",
        "copy (ctrl + c)",
        "paste (ctrl + v)",
        "leason",
        "Cells to which correction factor should be added",
        "Number of digits of precision to display",
        "Fixed-effect Model",
        "248-254.)",
        "(1959) Statistical",
        '"  Heterogeneity"',
        "Outcomes need to be numeric, you crazy person",
        "Negative Predictive value",
        "Yules Y",
        "Freeman-Tukey Transformed Proportion",
        "Relative Risk",
        "Arcsine Risk Difference",
        "Log Proportion",
        "Arcsine of Square Root Proportion",
        "Freeman-Tukey Double Arcsine Proportion",
        "OpenMeta[analyst] -",
        "Open Meta-Analysis",
        "Open Meta-Analyst",
        "Data Set",
        "Data Sets",
        "data set",
        "data sets",
        "rename group...'",
        "rename group <name>...'",
        "sort studies...'",
        "float (?)",
        "leave me alone!",
        "to to study_data.csv",
        "Random-Effects.</b>.",
        "meta-analyis",
        "and and follow-up",
        'be default',
        "Please select a csv file to import:",
        '"Undo"',
        '"Redo"',
        '"Copy"',
        '"Paste"',
        '"p-Val"',
        '"z-Val"',
        '"Het. p-Val"',
        '"fixed effect"',
        "Difference of arcsines transformed proportions",
        "Yule's Q is equal to",
        "Yule's Y is equal to",
        '"weights"=weights(res)',
        "setHeaderLabels([\"results\"])",
        "results / analysis",
        "_translate(\"MainWindow\", \"open recent...\")",
        "_translate(\"MainWindow\", \"open...\")",
        "_translate(\"MainWindow\", \"save as...\")",
        "_translate(\"MainWindow\", \"meta-analysis...\")",
        "_translate(\"MainWindow\", \"edit...\")",
        "_translate(\"MainWindow\", \"view network...\")",
        "_translate(\"MainWindow\", \"add covariate...\")",
        "_translate(\"MainWindow\", \"cumulative meta-analysis...\")",
        "_translate(\"MainWindow\", \"leave-one-out meta-analysis...\")",
        "_translate(\"MainWindow\", \"new dataset...\")",
        "QAction(\"rename group %s...\"",
        "QAction(\"rename covariate %s...\"",
        "QAction(\"save pdf image as...\"",
        "QAction(\"save png image as...\"",
        "QAction(\"edit plot...\"",
    ]

    for bad_string in bad_strings:
        assert bad_string not in text


def test_issue_76_to_105_corrected_user_facing_strings_are_present():
    text = _combined_text(
        [
            "src/forms/ui_csv_import_page.py",
            "src/forms/csv_import_page.ui",
            "src/forms/ui_meta_reg.py",
            "src/forms/cov_reg_dlg2.ui",
            "src/forms/ui_welcome_page.py",
            "src/forms/ui_diagnostic_data_form.py",
            "src/forms/ui_data_type_page.py",
            "src/forms/data_type_page.ui",
            "src/forms/ui_edit_dialog.py",
            "src/ui_meta.py",
            "src/meta.ui",
            "src/ui_results_window.py",
            "src/results_window.ui",
            "src/results_window.py",
            "src/conf_level_dialog.py",
            "src/main_wizard.py",
            "src/ma_data_table_model.py",
            "src/ma_data_table_view.py",
            "src/meta_globals.py",
            "src/R/OpenMetaR/R/continuous_methods.r",
            "src/R/OpenMetaR/R/meta_reg.r",
            "src/R/OpenMetaR/R/binary_methods.r",
            "src/R/OpenMetaR/R/meta_methods.r",
            "src/R/OpenMetaR/R/plotting.r",
            "src/R/OpenMetaR/R/utilities.r",
            *HELP_HTML,
        ]
    )

    expected_strings = [
        "Delimiter:",
        "CSV exported from Excel?",
        "Select CSV file...",
        "Create a new dataset",
        "Open recent...",
        "Diagnostic Data",
        "regression\ncoefficient",
        "follow-ups",
        "undo",
        "Ctrl+Z",
        "Correction factor target",
        "Number of digits",
        "Fixed-Effect Model",
        "Outcomes must be numeric.",
        "Negative Predictive Value",
        "Yule's Y",
        "OpenMetaAnalyst",
        "rename covariate %s",
        "Expected a whole number",
        "prepended to study_data.csv",
        "subgroup meta-analysis",
        "by default",
        "Please select a CSV file to import:",
        "subgroup meta-analysis",
        "meta-regression",
        "change confidence level",
        "import CSV",
        "p-Value",
        "z-Value",
        "Het. p-Value",
        "tx A",
        "tx B",
        "fixed effects",
        "Arcsine Difference",
        "Yule's Q",
        "Yule's Y",
        '"Weights"=weights(res)',
        "setHeaderLabels([\"Results\"])",
        "Results / Analysis",
        "_translate(\"MainWindow\", \"open recent\")",
        "_translate(\"MainWindow\", \"open\")",
        "_translate(\"MainWindow\", \"save as\")",
        "_translate(\"MainWindow\", \"meta-analysis\")",
        "_translate(\"MainWindow\", \"edit\")",
        "_translate(\"MainWindow\", \"view network\")",
        "_translate(\"MainWindow\", \"add covariate\")",
        "_translate(\"MainWindow\", \"cumulative meta-analysis\")",
        "_translate(\"MainWindow\", \"leave-one-out meta-analysis\")",
        "_translate(\"MainWindow\", \"new dataset\")",
        "QAction(\"rename group %s\"",
        "QAction(\"rename covariate %s\"",
        "QAction(\"save pdf image as\"",
        "QAction(\"save png image as\"",
        "QAction(\"edit plot\"",
    ]

    for expected_string in expected_strings:
        assert expected_string in text
