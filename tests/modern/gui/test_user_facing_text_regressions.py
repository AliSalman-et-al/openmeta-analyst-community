from pathlib import Path
import importlib
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


def test_option_group_forms_fit_checkbox_and_radio_labels():
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "src" / "forms"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    module_names = [
        "forms.ui_binary_data_form",
        "forms.ui_choose_back_calc_result_form",
        "forms.ui_csv_import_page",
        "forms.ui_diagnostic_data_form",
        "forms.ui_diagnostic_metrics",
        "forms.ui_diagnostic_explain_dlg",
        "forms.ui_edit_forest_plot",
        "forms.ui_ma_specs",
        "forms.ui_meta_reg",
    ]

    for module_name in module_names:
        module = importlib.import_module(module_name)
        ui_class = next(
            value for name, value in vars(module).items() if name.startswith("Ui_")
        )
        root = (
            QtWidgets.QWizardPage()
            if "WizardPage" in ui_class.__name__
            else QtWidgets.QDialog()
        )
        ui = ui_class()
        ui.setupUi(root)
        qt_layout.fit_option_groups_to_contents(root)

        root.show()
        app.processEvents()
        if root.layout() is not None:
            root.layout().activate()

        for group_box in root.findChildren(QtWidgets.QGroupBox):
            option_buttons = group_box.findChildren(
                QtWidgets.QCheckBox
            ) + group_box.findChildren(QtWidgets.QRadioButton)
            if not any(
                not _hidden_for_fit(button, root) and str(button.text()).strip()
                for button in option_buttons
            ):
                continue
            assert group_box.height() >= group_box.sizeHint().height(), module_name

        root.close()
        root.deleteLater()
    app.processEvents()


def test_layout_fitters_ignore_missing_or_deleted_roots():
    sys.path.insert(0, str(ROOT / "src"))
    import qt_layout
    from PyQt5 import sip

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    fitters = [
        qt_layout.fit_text_to_contents,
        qt_layout.fit_option_groups_to_contents,
        qt_layout.fit_analysis_dialog_to_contents,
    ]

    for fitter in fitters:
        fitter(None)

    deleted_root = QtWidgets.QDialog()
    sip.delete(deleted_root)

    for fitter in fitters:
        fitter(deleted_root)

    app.processEvents()


def test_generated_ui_surfaces_do_not_cap_visible_text_widgets_below_contents():
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "src" / "forms"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    module_names = [
        "forms.ui_binary_data_form",
        "forms.ui_change_cov_type",
        "forms.ui_choose_back_calc_result_form",
        "forms.ui_choose_metric_page",
        "forms.ui_cov_subgroup_dlg",
        "forms.ui_csv_import_page",
        "forms.ui_data_type_page",
        "forms.ui_diagnostic_data_form",
        "forms.ui_diagnostic_explain_dlg",
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
        "forms.ui_tom_form",
        "forms.ui_welcome_page",
        "ui_meta",
        "ui_results_window",
    ]

    for module_name in module_names:
        module = importlib.import_module(module_name)
        ui_class = next(
            value for name, value in vars(module).items() if name.startswith("Ui_")
        )
        root = _root_for_ui_class(ui_class)
        ui = ui_class()
        ui.setupUi(root)
        qt_layout.fit_text_to_contents(root)
        root.show()
        app.processEvents()

        try:
            _assert_visible_text_widgets_fit(root, module_name)
        finally:
            root.close()
            root.deleteLater()
    app.processEvents()


def _root_for_ui_class(ui_class):
    class_name = ui_class.__name__
    if class_name in {"Ui_MainWindow", "Ui_ResultsWindow"}:
        return QtWidgets.QMainWindow()
    if "WizardPage" in class_name or "DataTypePage" in class_name:
        return QtWidgets.QWizardPage()
    return QtWidgets.QDialog()


def _assert_visible_text_widgets_fit(root, module_name):
    for label in root.findChildren(QtWidgets.QLabel):
        if not _visible_text(label, root, label.text()):
            continue
        assert label.minimumWidth() >= label.sizeHint().width(), module_name
        assert label.maximumWidth() >= label.sizeHint().width(), module_name

    for button in root.findChildren(QtWidgets.QAbstractButton):
        if isinstance(button, QtWidgets.QToolButton):
            continue
        if not _visible_text(button, root, button.text()):
            continue
        assert button.minimumWidth() >= button.sizeHint().width(), module_name
        assert button.maximumWidth() >= button.sizeHint().width(), module_name

    for combo_box in root.findChildren(QtWidgets.QComboBox):
        if _hidden_for_fit(combo_box, root):
            continue
        assert combo_box.sizeAdjustPolicy() == QtWidgets.QComboBox.AdjustToContents
        assert combo_box.minimumWidth() >= combo_box.sizeHint().width(), module_name
        assert combo_box.maximumWidth() >= combo_box.sizeHint().width(), module_name


def _visible_text(widget, root, text):
    return not _hidden_for_fit(widget, root) and str(text).strip()


def _hidden_for_fit(widget, root):
    current = widget
    while current is not None and current is not root:
        if current.isHidden() and not _hidden_page_for_fit(current):
            return True
        current = current.parentWidget()
    return False


def _hidden_page_for_fit(widget):
    parent = widget.parentWidget()
    if isinstance(parent, QtWidgets.QTabWidget) and parent.indexOf(widget) >= 0:
        return True
    if isinstance(parent, QtWidgets.QStackedWidget) and parent.indexOf(widget) >= 0:
        return True
    return False


def test_dialog_width_fit_includes_labels_combos_and_window_title():
    sys.path.insert(0, str(ROOT / "src"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    root = QtWidgets.QDialog()
    root.setWindowTitle("select covariates")
    layout = QtWidgets.QVBoxLayout(root)

    group_box = QtWidgets.QGroupBox("binary.random")
    group_layout = QtWidgets.QGridLayout(group_box)
    description = QtWidgets.QLabel(
        "Description: Performs random-effects meta-analysis."
    )
    parameter_label = QtWidgets.QLabel("Correction factor target")
    combo = QtWidgets.QComboBox()
    combo.addItems(
        [
            "DL: DerSimonian-Laird",
            "Binary Fixed-Effect Mantel-Haenszel",
            "Binary Fixed-Effect Inverse Variance",
        ]
    )
    combo.setCurrentIndex(0)

    group_layout.addWidget(description, 0, 0, 1, 2)
    group_layout.addWidget(parameter_label, 1, 0)
    group_layout.addWidget(combo, 1, 1)
    layout.addWidget(group_box)

    qt_layout.fit_option_groups_to_contents(root)
    root.show()
    app.processEvents()

    try:
        assert description.minimumWidth() >= description.sizeHint().width()
        assert parameter_label.minimumWidth() >= parameter_label.sizeHint().width()
        assert combo.sizeAdjustPolicy() == QtWidgets.QComboBox.AdjustToContents
        assert combo.minimumWidth() >= combo.sizeHint().width()
        assert root.minimumWidth() >= root.sizeHint().width()

        title_width = root.fontMetrics().horizontalAdvance(root.windowTitle())
        assert root.minimumWidth() >= title_width
    finally:
        root.close()
        root.deleteLater()
    app.processEvents()


def test_dialog_width_fit_includes_hidden_tab_contents_and_late_content():
    sys.path.insert(0, str(ROOT / "src"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    root = QtWidgets.QDialog()
    root.setWindowTitle("Method & Parameters")
    layout = QtWidgets.QVBoxLayout(root)
    tabs = QtWidgets.QTabWidget(root)
    narrow_tab = QtWidgets.QWidget()
    wide_tab = QtWidgets.QWidget()
    narrow_layout = QtWidgets.QVBoxLayout(narrow_tab)
    wide_layout = QtWidgets.QGridLayout(wide_tab)
    narrow_layout.addWidget(QtWidgets.QLabel("forest plot"))
    tabs.addTab(narrow_tab, "forest plot")
    tabs.addTab(wide_tab, "method")
    tabs.setCurrentWidget(narrow_tab)
    layout.addWidget(tabs)

    description = QtWidgets.QLabel(
        "Description: Performs random-effects meta-analysis with a long generated description."
    )
    parameter_label = QtWidgets.QLabel("Correction factor target")
    combo = QtWidgets.QComboBox()
    combo.addItems(["DL: DerSimonian-Laird", "SJ: Sidik-Jonkman"])
    wide_layout.addWidget(description, 0, 0, 1, 2)
    wide_layout.addWidget(parameter_label, 1, 0)
    wide_layout.addWidget(combo, 1, 1)

    qt_layout.fit_analysis_dialog_to_contents(root)
    root.show()
    app.processEvents()

    try:
        assert tabs.currentWidget() is narrow_tab
        assert wide_tab.isHidden()
        assert description.minimumWidth() >= description.sizeHint().width()
        assert parameter_label.minimumWidth() >= parameter_label.sizeHint().width()
        assert combo.minimumWidth() >= combo.sizeHint().width()
        assert root.minimumWidth() >= qt_layout.ANALYSIS_DIALOG_MINIMUM_WIDTH
        assert root.minimumWidth() >= root.sizeHint().width()
    finally:
        root.close()
        root.deleteLater()
    app.processEvents()


def test_analysis_dialog_combo_widths_are_content_aware_but_capped():
    sys.path.insert(0, str(ROOT / "src"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    root = QtWidgets.QDialog()
    root.setWindowTitle("Method & Parameters")
    layout = QtWidgets.QVBoxLayout(root)
    combo = QtWidgets.QComboBox()
    combo.addItems(
        [
            "DL: DerSimonian-Laird",
            "A very long estimator name that should not make the dialog sprawl horizontally across the screen",
        ]
    )
    layout.addWidget(combo)

    qt_layout.fit_analysis_dialog_to_contents(root)
    root.show()
    app.processEvents()

    try:
        assert combo.minimumWidth() <= qt_layout.ANALYSIS_DIALOG_COMBO_MAXIMUM_WIDTH
        assert combo.maximumWidth() == qt_layout.ANALYSIS_DIALOG_COMBO_MAXIMUM_WIDTH
    finally:
        root.close()
        root.deleteLater()
    app.processEvents()


def test_change_confidence_level_dialog_uses_analysis_dialog_width_floor():
    sys.path.insert(0, str(ROOT / "src"))
    import conf_level_dialog
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = conf_level_dialog.ChangeConfLevelDlg(95.0)
    dialog.show()
    app.processEvents()

    try:
        assert dialog.minimumWidth() >= qt_layout.ANALYSIS_DIALOG_MINIMUM_WIDTH
        assert dialog.minimumHeight() >= qt_layout.ANALYSIS_DIALOG_MINIMUM_HEIGHT
        assert dialog.minimumWidth() >= dialog.sizeHint().width()
    finally:
        dialog.close()
        dialog.deleteLater()
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
        "be default",
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
        'QAction("rename group %s..."',
        'QAction("rename covariate %s..."',
        'QAction("save pdf image as..."',
        'QAction("save png image as..."',
        'QAction("edit plot..."',
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
        'setHeaderLabels(["Results"])',
        "Results / Analysis",
        '_translate("MainWindow", "open recent")',
        '_translate("MainWindow", "open")',
        '_translate("MainWindow", "save as")',
        '_translate("MainWindow", "meta-analysis")',
        '_translate("MainWindow", "edit")',
        '_translate("MainWindow", "view network")',
        '_translate("MainWindow", "add covariate")',
        '_translate("MainWindow", "cumulative meta-analysis")',
        '_translate("MainWindow", "leave-one-out meta-analysis")',
        '_translate("MainWindow", "new dataset")',
        'QAction("rename group %s"',
        'QAction("rename covariate %s"',
        'QAction("save pdf image as"',
        'QAction("save png image as"',
        'QAction("edit plot"',
    ]

    for expected_string in expected_strings:
        assert expected_string in text
