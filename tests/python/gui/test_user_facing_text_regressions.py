from pathlib import Path
import importlib
import sys

from PyQt6 import QtCore, QtWidgets

from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()


ROOT = Path(__file__).resolve().parents[3]
HELP_HTML = sorted(
    path.relative_to(ROOT).as_posix() for path in (ROOT / "doc").glob("*.html")
)

GENERATED_UI_MODULE_NAMES = [
    "forms.ui_about_legal",
    "forms.ui_binary_data_form",
    "forms.ui_change_cov_type",
    "forms.ui_choose_back_calc_result_form",
    "forms.ui_continuous_back_calc_result_form",
    "forms.ui_choose_metric_page",
    "forms.ui_cov_subgroup_dlg",
    "forms.ui_csv_import_page",
    "forms.ui_data_type_page",
    "forms.ui_diagnostic_data_form",
    "forms.ui_diagnostic_metrics",
    "forms.ui_edit_dialog",
    "forms.ui_edit_forest_plot",
    "forms.ui_edit_group_name",
    "forms.ui_ma_specs",
    "forms.ui_meta_reg",
    "forms.ui_network_view",
    "forms.ui_new_covariate",
    "forms.ui_new_follow_up",
    "forms.ui_new_group",
    "forms.ui_new_outcome",
    "forms.ui_new_study",
    "forms.ui_outcome_name_page",
    "forms.ui_running",
    "forms.ui_welcome_page",
    "ui_meta",
    "ui_results_window",
]


def _read(relative_path):
    source_path = Path(relative_path)
    if source_path.parent == Path("src/rc_metastudio/forms") and source_path.name.startswith(
        "ui_"
    ):
        source_path = Path("build/qt6/generated/rc_metastudio/forms") / source_path.name
    elif source_path in {
        Path("src/rc_metastudio/ui_meta.py"),
        Path("src/rc_metastudio/ui_results_window.py"),
    }:
        source_path = Path("build/qt6/generated/rc_metastudio") / source_path.name
    return (ROOT / source_path).read_text(encoding="utf-8")


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
        assert label.sizePolicy().horizontalPolicy() != QtWidgets.QSizePolicy.Policy.Fixed

    window.deleteLater()
    app.processEvents()


def test_issue_190_main_window_does_not_expose_toolbar_toggle_popup():
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "src" / "forms"))
    from meta_form import MetaForm

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MetaForm()

    try:
        assert window.createPopupMenu() is None
        assert window.toolBar.toggleViewAction().isEnabled()
    finally:
        window.close()
        window.deleteLater()
    app.processEvents()


def test_generated_dialogs_do_not_depend_on_fixed_position_content():
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "src" / "forms"))
    unmanaged_dialogs = []

    for module_name in GENERATED_UI_MODULE_NAMES:
        module = importlib.import_module(module_name)
        ui_class = next(
            value for name, value in vars(module).items() if name.startswith("Ui_")
        )
        root = _root_for_ui_class(ui_class)
        ui = ui_class()
        ui.setupUi(root)

        direct_children = [
            child
            for child in root.findChildren(
                QtWidgets.QWidget, options=QtCore.Qt.FindChildOption.FindDirectChildrenOnly
            )
            if not child.isHidden() and not child.isWindow()
        ]
        if (
            isinstance(root, QtWidgets.QDialog)
            and root.layout() is None
            and direct_children
        ):
            unmanaged_dialogs.append(module_name)
        root.deleteLater()

    assert unmanaged_dialogs == []


def _root_for_ui_class(ui_class):
    if ui_class.__name__ in {"Ui_MainWindow", "Ui_ResultsWindow"}:
        return QtWidgets.QMainWindow()
    if "WizardPage" in ui_class.__name__ or ui_class.__name__ == "Ui_DataTypePage":
        return QtWidgets.QWizardPage()
    return QtWidgets.QDialog()


def test_change_confidence_level_dialog_does_not_use_legacy_fixed_layout_policy():
    sys.path.insert(0, str(ROOT / "src"))
    import conf_level_dialog

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = conf_level_dialog.ChangeConfLevelDlg(95.0)
    dialog.show()
    app.processEvents()

    try:
        assert (
            dialog.layout().sizeConstraint()
            == QtWidgets.QLayout.SizeConstraint.SetMinimumSize
        )
        import adaptive_window

        assert (
            adaptive_window.adaptive_window_state(dialog).policy.archetype.value
            == "transactional"
        )
        assert dialog.minimumWidth() < dialog.sizeHint().width()
    finally:
        dialog.close()
        dialog.deleteLater()
    app.processEvents()


def test_issue_76_to_105_reported_bad_user_facing_strings_are_absent():
    text = _combined_text(
        [
            "src/rc_metastudio/forms/ui_csv_import_page.py",
            "src/rc_metastudio/forms/csv_import_page.ui",
            "src/rc_metastudio/forms/ui_meta_reg.py",
            "src/rc_metastudio/forms/cov_reg_dlg2.ui",
            "src/rc_metastudio/forms/ui_welcome_page.py",
            "src/rc_metastudio/forms/welcome_page.ui",
            "src/rc_metastudio/forms/ui_binary_data_form.py",
            "src/rc_metastudio/forms/binary_data_form2.ui",
            "src/rc_metastudio/forms/ui_continuous_data_form.py",
            "src/rc_metastudio/forms/continuous_data_form.ui",
            "src/rc_metastudio/forms/ui_change_cov_type.py",
            "src/rc_metastudio/forms/change_cov_type_form.ui",
            "src/rc_metastudio/forms/ui_cov_subgroup_dlg.py",
            "src/rc_metastudio/forms/cov_subgroup_dlg.ui",
            "src/rc_metastudio/forms/ui_diagnostic_data_form.py",
            "src/rc_metastudio/forms/diagnostic_data_form.ui",
            "src/rc_metastudio/forms/ui_diagnostic_metrics.py",
            "src/rc_metastudio/forms/diagnostic_metrics.ui",
            "src/rc_metastudio/forms/ui_data_type_page.py",
            "src/rc_metastudio/forms/data_type_page.ui",
            "src/rc_metastudio/forms/ui_edit_dialog.py",
            "src/rc_metastudio/forms/edit_dialog2.ui",
            "src/rc_metastudio/forms/ui_edit_forest_plot.py",
            "src/rc_metastudio/forms/edit_forest_plot.ui",
            "src/rc_metastudio/forms/ui_edit_group_name.py",
            "src/rc_metastudio/forms/change_group_name_dlg.ui",
            "src/rc_metastudio/forms/ui_ma_specs.py",
            "src/rc_metastudio/forms/ma_specs2.ui",
            "src/rc_metastudio/forms/ui_network_view.py",
            "src/rc_metastudio/forms/network_view_window.ui",
            "src/rc_metastudio/forms/ui_new_covariate.py",
            "src/rc_metastudio/forms/new_covariate_dlg.ui",
            "src/rc_metastudio/forms/ui_new_follow_up.py",
            "src/rc_metastudio/forms/new_follow_up_dlg.ui",
            "src/rc_metastudio/forms/ui_new_group.py",
            "src/rc_metastudio/forms/new_group_dlg.ui",
            "src/rc_metastudio/forms/ui_new_outcome.py",
            "src/rc_metastudio/forms/new_outcome_dlg.ui",
            "src/rc_metastudio/forms/ui_new_study.py",
            "src/rc_metastudio/forms/new_study_dlg.ui",
            "src/rc_metastudio/forms/ui_running.py",
            "src/rc_metastudio/forms/running.ui",
            "src/rc_metastudio/ui_meta.py",
            "src/rc_metastudio/forms/meta.ui",
            "src/rc_metastudio/ui_results_window.py",
            "src/rc_metastudio/forms/results_window.ui",
            "src/rc_metastudio/results_window.py",
            "src/rc_metastudio/conf_level_dialog.py",
            "src/rc_metastudio/main_wizard.py",
            "src/rc_metastudio/meta_form.py",
            "src/rc_metastudio/binary_data_form.py",
            "src/rc_metastudio/continuous_data_form.py",
            "src/rc_metastudio/diagnostic_data_form.py",
            "src/rc_metastudio/calculator_routines.py",
            "src/rc_metastudio/meta_reg_form.py",
            "src/rc_metastudio/ma_data_table_model.py",
            "src/rc_metastudio/ma_data_table_view.py",
            "src/rc_metastudio/meta_globals.py",
            "r/RCMetaR/R/binary_methods.R",
            "r/RCMetaR/R/continuous_methods.R",
            "r/RCMetaR/R/diagnostic_methods.R",
            "r/RCMetaR/R/meta_methods.R",
            "r/RCMetaR/R/plotting.R",
            "r/RCMetaR/R/utilities.R",
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
        '"Whoops"',
        '"Whoops."',
        '"analysis failed"',
        "SMD bias correction",
        "covariate name:",
        "edit covariate name",
        "Choose CSV file",
        "Open an existing dataset",
        "<string>toolBar</string>",
        'toolBar"))',
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
        "RC MetaStudio -",
        "Open Meta-Analysis",
        "you've made unsaved changes to your data.",
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
        "be default",
        "Please select a csv file to import:",
        '"p-Val"',
        "p-Value",
        '"z-Val"',
        "z-Value",
        '"Het. p-Val"',
        "Het. p-Value",
        '"fixed effect"',
        "Difference of arcsines transformed proportions",
        "Yule's Q is equal to",
        "Yule's Y is equal to",
        '"weights"=weights(res)',
        'setHeaderLabels(["results"])',
        "results / analysis",
        '_translate("MainWindow", "open recent...")',
        '_translate("MainWindow", "open...")',
        '_translate("MainWindow", "save as...")',
        '_translate("MainWindow", "meta-analysis...")',
        '_translate("MainWindow", "edit...")',
        '_translate("MainWindow", "view network...")',
        '_translate("MainWindow", "add covariate...")',
        '_translate("MainWindow", "cumulative meta-analysis...")',
        '_translate("MainWindow", "leave-one-out meta-analysis...")',
        '_translate("MainWindow", "new dataset...")',
        '_translate("MainWindow", "meta-analysis")',
        '_translate("MainWindow", "add covariate")',
        '_translate("MainWindow", "cumulative meta-analysis")',
        '_translate("MainWindow", "leave-one-out meta-analysis")',
        '_translate("MainWindow", "new dataset")',
        '_translate("Dialog", "method")',
        '_translate("Dialog", "forest plot")',
        '_translate("Dialog", "Forest Plot")',
        '_translate("new_covariate_dialog", "add new covariate")',
        '_translate("BinaryDataForm", "back-calculate table")',
        "<string>back-calculate table</string>",
        '_translate("diag_metric", "select metrics for analysis")',
        "<string>select metrics for analysis</string>",
        '_translate("edit_dialog", "edit dataset")',
        "<string>edit dataset</string>",
        '_translate("edit_forest_plot_dlg", "edit forest plot")',
        '_translate("edit_forest_plot_dlg", "Edit Forest Plot")',
        "<string>edit forest plot</string>",
        '_translate("new_follow_up_dialog", "add new follow-up")',
        "<string>add new follow-up</string>",
        '_translate("new_outcome_dialog", "add new outcome")',
        "<string>add new outcome</string>",
        '_translate("new_study_dlg", "add new study")',
        "<string>add new study</string>",
        '_translate("running", "running analysis...")',
        "<string>running analysis...</string>",
        '_translate("WizardPage", "Open recent...")',
        "<string>Open recent...</string>",
        '_translate("WizardPage", "Create a new dataset")',
        "<string>Create a new dataset</string>",
        '_translate("edit_forest_plot_dlg", "col 1 label:")',
        "<string>col 1 label:</string>",
        '_translate("edit_forest_plot_dlg", "show summary line:")',
        "<string>show summary line:</string>",
        '_translate("edit_forest_plot_dlg", "save image to:")',
        "<string>save image to:</string>",
        'QAction("rename group %s..."',
        'QAction("rename covariate %s..."',
        'QAction("save pdf image as..."',
        'QAction("save png image as..."',
        'QAction("edit plot..."',
        'QAction("save pdf image as"',
        'QAction("save png image as"',
        'QAction("edit plot"',
        'QAction("Edit Forest Plot"',
        "tau^2",
        "I^2",
        "Results (log scale)",
    ]

    for bad_string in bad_strings:
        assert bad_string not in text


def test_issue_76_to_105_corrected_user_facing_strings_are_present():
    text = _combined_text(
        [
            "src/rc_metastudio/forms/ui_csv_import_page.py",
            "src/rc_metastudio/forms/csv_import_page.ui",
            "src/rc_metastudio/forms/ui_meta_reg.py",
            "src/rc_metastudio/forms/cov_reg_dlg2.ui",
            "src/rc_metastudio/forms/ui_welcome_page.py",
            "src/rc_metastudio/forms/welcome_page.ui",
            "src/rc_metastudio/forms/ui_binary_data_form.py",
            "src/rc_metastudio/forms/binary_data_form2.ui",
            "src/rc_metastudio/forms/ui_continuous_data_form.py",
            "src/rc_metastudio/forms/continuous_data_form.ui",
            "src/rc_metastudio/forms/ui_change_cov_type.py",
            "src/rc_metastudio/forms/change_cov_type_form.ui",
            "src/rc_metastudio/forms/ui_cov_subgroup_dlg.py",
            "src/rc_metastudio/forms/cov_subgroup_dlg.ui",
            "src/rc_metastudio/forms/ui_diagnostic_data_form.py",
            "src/rc_metastudio/forms/diagnostic_data_form.ui",
            "src/rc_metastudio/forms/ui_diagnostic_metrics.py",
            "src/rc_metastudio/forms/diagnostic_metrics.ui",
            "src/rc_metastudio/forms/ui_data_type_page.py",
            "src/rc_metastudio/forms/data_type_page.ui",
            "src/rc_metastudio/forms/ui_edit_dialog.py",
            "src/rc_metastudio/forms/edit_dialog2.ui",
            "src/rc_metastudio/forms/ui_edit_forest_plot.py",
            "src/rc_metastudio/forms/edit_forest_plot.ui",
            "src/rc_metastudio/forms/ui_edit_group_name.py",
            "src/rc_metastudio/forms/change_group_name_dlg.ui",
            "src/rc_metastudio/forms/ui_ma_specs.py",
            "src/rc_metastudio/forms/ma_specs2.ui",
            "src/rc_metastudio/forms/ui_network_view.py",
            "src/rc_metastudio/forms/network_view_window.ui",
            "src/rc_metastudio/forms/ui_new_covariate.py",
            "src/rc_metastudio/forms/new_covariate_dlg.ui",
            "src/rc_metastudio/forms/ui_new_follow_up.py",
            "src/rc_metastudio/forms/new_follow_up_dlg.ui",
            "src/rc_metastudio/forms/ui_new_group.py",
            "src/rc_metastudio/forms/new_group_dlg.ui",
            "src/rc_metastudio/forms/ui_new_outcome.py",
            "src/rc_metastudio/forms/new_outcome_dlg.ui",
            "src/rc_metastudio/forms/ui_new_study.py",
            "src/rc_metastudio/forms/new_study_dlg.ui",
            "src/rc_metastudio/forms/ui_running.py",
            "src/rc_metastudio/forms/running.ui",
            "src/rc_metastudio/ui_meta.py",
            "src/rc_metastudio/forms/meta.ui",
            "src/rc_metastudio/ui_results_window.py",
            "src/rc_metastudio/forms/results_window.ui",
            "src/rc_metastudio/results_window.py",
            "src/rc_metastudio/conf_level_dialog.py",
            "src/rc_metastudio/main_wizard.py",
            "src/rc_metastudio/meta_form.py",
            "src/rc_metastudio/analysis_method_labels.py",
            "src/rc_metastudio/continuous_data_form.py",
            "src/rc_metastudio/edit_group_name_form.py",
            "src/rc_metastudio/ma_data_table_model.py",
            "src/rc_metastudio/ma_data_table_view.py",
            "src/rc_metastudio/meta_globals.py",
            "r/RCMetaR/R/continuous_methods.R",
            "r/RCMetaR/R/meta_reg.R",
            "r/RCMetaR/R/binary_methods.R",
            "r/RCMetaR/R/meta_methods.R",
            "r/RCMetaR/R/plotting.R",
            "r/RCMetaR/R/utilities.R",
            *HELP_HTML,
        ]
    )

    expected_strings = [
        "Delimiter:",
        "CSV exported from Excel?",
        "Select CSV file...",
        "Create a New Dataset",
        "Open Recent...",
        "Diagnostic Data",
        "Regression\nCoefficient",
        "Follow-Ups",
        "Undo",
        "Ctrl+Z",
        "Correction factor target",
        "Decimal Places",
        "Fixed-Effect Model",
        "Outcomes must be numeric.",
        "Negative Predictive Value",
        "Yule's Y",
        "RCMetaStudio",
        "You've made unsaved changes to your data. Do you want to save your changes?",
        "Choose CSV File",
        "Open Existing Dataset",
        "Covariate for",
        "Tool Bar",
        "SMD Bias Correction",
        "Rename Covariate %s",
        "Expected a whole number",
        "Subgroup Meta-Analysis",
        "by default",
        "Please select a CSV file to import:",
        "Subgroup Meta-Analysis",
        "Meta-Regression",
        "Change Confidence Level",
        "Import CSV",
        "p-value",
        "z-value",
        "Het. p-value",
        "tx A",
        "tx B",
        "Fixed Effects",
        "Arcsine Difference",
        "Yule's Q",
        "Yule's Y",
        '"Weights"=weights(res)',
        'setHeaderLabels(["Results"])',
        "Results / Analysis",
        '_translate("MainWindow", "Open Recent")',
        '_translate("MainWindow", "Open")',
        '_translate("MainWindow", "Save As")',
        '_translate("MainWindow", "Meta-Analysis")',
        '_translate("MainWindow", "Edit")',
        '_translate("MainWindow", "View Network")',
        '_translate("MainWindow", "Add Covariate")',
        '_translate("MainWindow", "Cumulative Meta-Analysis")',
        '_translate("MainWindow", "Leave-One-Out Meta-Analysis")',
        '_translate("MainWindow", "New Dataset")',
        '_translate("Dialog", "Method")',
        '_translate("Dialog", "Plots")',
        '_translate("new_covariate_dialog", "Add Covariate")',
        '_translate("BinaryDataForm", "Back-Calculate Table")',
        '_translate("ContinuousDataForm", "Back-Calculate Table")',
        '_translate("DiagnosticDataForm", "Back-Calculate Table")',
        '_translate("diag_metric", "Select Metrics for Analysis")',
        '_translate("edit_dialog", "Edit Dataset")',
        '_translate("edit_forest_plot_dlg", "Edit Plot")',
        '_translate("running", "Running Analysis...")',
        '_translate("DataTypePage", "Proportion")',
        'QAction("Rename Group %s"',
        'QAction("Rename Covariate %s"',
        'QAction("Edit Plot"',
        'QAction("Save %s Image As"',
    ]

    for expected_string in expected_strings:
        assert expected_string in text


def test_issue_173_user_facing_commands_and_headers_use_desktop_casing():
    text = _combined_text(
        [
            "src/rc_metastudio/forms/meta.ui",
            "src/rc_metastudio/ui_meta.py",
            "src/rc_metastudio/forms/binary_data_form2.ui",
            "src/rc_metastudio/forms/ui_binary_data_form.py",
            "src/rc_metastudio/forms/continuous_data_form.ui",
            "src/rc_metastudio/forms/ui_continuous_data_form.py",
            "src/rc_metastudio/forms/diagnostic_data_form.ui",
            "src/rc_metastudio/forms/ui_diagnostic_data_form.py",
            "src/rc_metastudio/ma_data_table_view.py",
            "src/rc_metastudio/meta_form.py",
        ]
    )

    expected_strings = [
        "Undo",
        "Redo",
        "Copy",
        "Paste",
        "Event",
        "No Event",
        "Total",
        "Group 1",
        "Group 2",
        "N",
        "Mean",
        "SD",
        "SE",
        "Variance",
        "P-Value",
        "Lower",
        "Upper",
        "Pre / Post",
        "Pre",
        "Post",
        "(Test) +",
        "(Test) -",
        "(Disease) +",
        "(Disease) -",
        "Delete Study %s",
        "Include All",
        "Exclude All",
        "Sort Studies by %s",
        "Rename Group %s",
        "Rename Covariate %s",
        "Delete Covariate %s",
        "Create a %s Copy of %s",
        "Open Project: %s",
    ]
    forbidden_strings = [
        '"undo"',
        '"redo"',
        '"copy"',
        '"paste"',
        ">event<",
        ">no event<",
        ">total<",
        ">group 1<",
        ">group 2<",
        ">n<",
        ">mean<",
        ">sd<",
        ">se<",
        ">var<",
        ">pval<",
        "p-value",
        "p-Value",
        ">low<",
        ">high<",
        ">pre / post<",
        ">pre<",
        ">post<",
        'QAction("delete study %s"',
        'QAction("include all"',
        'QAction("exclude all"',
        'QAction("sort studies by %s"',
        'QAction("rename group %s"',
        'QAction("rename covariate %s"',
        'QAction("delete covariate %s"',
        '"create a %s copy of %s"',
        '"open file: %s"',
    ]

    for expected_string in expected_strings:
        assert expected_string in text
    for forbidden_string in forbidden_strings:
        assert forbidden_string not in text
