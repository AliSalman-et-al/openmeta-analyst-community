from pathlib import Path
import importlib
import sys

from PyQt5 import QtCore, QtWidgets


ROOT = Path(__file__).resolve().parents[3]
HELP_HTML = sorted(
    path.relative_to(ROOT).as_posix() for path in (ROOT / "doc").glob("*.html")
)

GENERATED_UI_MODULE_NAMES = [
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
    "forms.ui_welcome_page",
    "ui_meta",
    "ui_results_window",
]


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


def test_content_fit_resizes_dialog_roots_only(monkeypatch):
    sys.path.insert(0, str(ROOT / "src"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    dialog = QtWidgets.QDialog()
    dialog_layout = QtWidgets.QVBoxLayout(dialog)
    dialog_layout.addWidget(QtWidgets.QLabel("Dialog text that needs fitting"))
    dialog_adjust_calls = []
    monkeypatch.setattr(dialog, "adjustSize", lambda: dialog_adjust_calls.append(True))

    main_window = QtWidgets.QMainWindow()
    central = QtWidgets.QWidget(main_window)
    main_layout = QtWidgets.QVBoxLayout(central)
    main_label = QtWidgets.QLabel("Main window text that needs fitting")
    main_layout.addWidget(main_label)
    main_window.setCentralWidget(central)
    main_adjust_calls = []
    monkeypatch.setattr(
        main_window, "adjustSize", lambda: main_adjust_calls.append(True)
    )

    try:
        qt_layout.fit_text_to_contents(dialog)
        qt_layout.fit_text_to_contents(main_window)

        assert dialog_adjust_calls == [True]
        assert main_adjust_calls == []
        assert main_label.minimumWidth() >= main_label.sizeHint().width()
    finally:
        dialog.close()
        dialog.deleteLater()
        main_window.close()
        main_window.deleteLater()
    app.processEvents()


def test_maximized_roots_fit_child_text_without_resizing_root(monkeypatch):
    sys.path.insert(0, str(ROOT / "src"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = QtWidgets.QDialog()
    layout = QtWidgets.QVBoxLayout(dialog)
    label = QtWidgets.QLabel("Maximized dialog text that still needs fitting")
    layout.addWidget(label)
    adjust_calls = []
    monkeypatch.setattr(dialog, "isMaximized", lambda: True)
    monkeypatch.setattr(dialog, "adjustSize", lambda: adjust_calls.append(True))

    try:
        qt_layout.fit_text_to_contents(dialog)

        assert adjust_calls == []
        assert label.minimumWidth() >= label.sizeHint().width()
    finally:
        dialog.close()
        dialog.deleteLater()
    app.processEvents()


def test_generated_ui_surfaces_do_not_cap_visible_text_widgets_below_contents():
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "src" / "forms"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    for module_name in GENERATED_UI_MODULE_NAMES:
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
            if isinstance(root, QtWidgets.QWizardPage):
                assert root.minimumHeight() >= root.sizeHint().height(), module_name
        finally:
            root.close()
            root.deleteLater()
    app.processEvents()


def test_generated_dialog_and_wizard_surfaces_fit_root_to_contents():
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "src" / "forms"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    for module_name in GENERATED_UI_MODULE_NAMES:
        module = importlib.import_module(module_name)
        ui_class = next(
            value for name, value in vars(module).items() if name.startswith("Ui_")
        )
        if ui_class.__name__ in {"Ui_MainWindow", "Ui_ResultsWindow"}:
            continue

        root = _root_for_ui_class(ui_class)
        ui = ui_class()
        ui.setupUi(root)
        qt_layout.fit_application_dialog_to_contents(root)

        try:
            assert root.minimumWidth() >= root.sizeHint().width(), module_name
            assert root.minimumHeight() >= root.sizeHint().height(), module_name
        finally:
            root.close()
            root.deleteLater()
    app.processEvents()


def test_generated_fixed_position_dialog_rows_fill_fitted_width():
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "src" / "forms"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    fixed_position_dialogs = 0

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
                QtWidgets.QWidget, options=QtCore.Qt.FindDirectChildrenOnly
            )
            if not child.isHidden() and not child.isWindow()
        ]
        if not isinstance(root, QtWidgets.QDialog) or root.layout() is not None:
            root.deleteLater()
            continue
        if not direct_children:
            root.deleteLater()
            continue

        fixed_position_dialogs += 1
        rows = _geometry_rows(direct_children)
        qt_layout.fit_application_dialog_to_contents(root)
        root.show()
        app.processEvents()
        root.layout().activate()
        app.processEvents()

        try:
            layout_margins = root.layout().contentsMargins()
            expected_left = root.contentsRect().left() + layout_margins.left()
            expected_right = root.contentsRect().right() - layout_margins.right()

            for row in rows:
                visible_row_children = [
                    child for child in row if not _hidden_for_fit(child, root)
                ]
                if not visible_row_children:
                    continue
                row_rect = visible_row_children[0].geometry()
                for child in visible_row_children[1:]:
                    row_rect = row_rect.united(child.geometry())

                assert row_rect.left() <= expected_left + 1, module_name
                assert row_rect.right() >= expected_right - 1, module_name
        finally:
            root.close()
            root.deleteLater()

    assert fixed_position_dialogs > 0
    app.processEvents()


def test_generated_ui_combo_boxes_do_not_stretch_to_wide_parent_geometry():
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "src" / "forms"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    surfaces_with_combos = 0

    for module_name in GENERATED_UI_MODULE_NAMES:
        module = importlib.import_module(module_name)
        ui_class = next(
            value for name, value in vars(module).items() if name.startswith("Ui_")
        )
        root = _root_for_ui_class(ui_class)
        ui = ui_class()
        ui.setupUi(root)
        combo_boxes = root.findChildren(QtWidgets.QComboBox)
        if not combo_boxes:
            root.deleteLater()
            continue
        surfaces_with_combos += 1

        root.resize(900, max(root.sizeHint().height(), root.height()))
        qt_layout.fit_text_to_contents(root)
        root.show()
        app.processEvents()
        root.resize(900, root.height())
        app.processEvents()

        try:
            for combo_box in combo_boxes:
                if _hidden_for_fit(combo_box, root):
                    continue
                assert (
                    combo_box.sizeAdjustPolicy() == QtWidgets.QComboBox.AdjustToContents
                )
                assert (
                    combo_box.sizePolicy().horizontalPolicy()
                    == QtWidgets.QSizePolicy.Maximum
                ), module_name
                assert combo_box.width() <= combo_box.maximumWidth(), module_name
                if combo_box.count() > 0:
                    assert combo_box.maximumWidth() <= max(
                        qt_layout.APPLICATION_DIALOG_COMBO_MAXIMUM_WIDTH,
                        _combo_contents_width(combo_box),
                    ), module_name
        finally:
            root.close()
            root.deleteLater()

    assert surfaces_with_combos > 0
    app.processEvents()


def test_generated_qdialog_surfaces_use_application_dialog_width_floor_and_fit_combos():
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "src" / "forms"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    module_names = [
        "forms.ui_change_cov_type",
        "forms.ui_cov_subgroup_dlg",
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
        "forms.ui_running",
    ]

    for module_name in module_names:
        module = importlib.import_module(module_name)
        ui_class = next(
            value for name, value in vars(module).items() if name.startswith("Ui_")
        )
        root = QtWidgets.QDialog()
        ui = ui_class()
        ui.setupUi(root)
        qt_layout.fit_application_dialog_to_contents(root)
        root.show()
        app.processEvents()

        try:
            assert root.minimumWidth() >= qt_layout.APPLICATION_DIALOG_MINIMUM_WIDTH
            assert root.minimumHeight() <= max(
                _root_content_height(root),
                qt_layout.APPLICATION_DIALOG_MINIMUM_HEIGHT,
            )
            _assert_visible_text_widgets_fit(root, module_name)
            for combo_box in root.findChildren(QtWidgets.QComboBox):
                if _hidden_for_fit(combo_box, root):
                    continue
                assert combo_box.maximumWidth() >= combo_box.minimumWidth()
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


def _geometry_rows(widgets):
    rows = []
    current_row = []
    current_bottom = None

    for widget in sorted(widgets, key=lambda child: child.geometry().top()):
        top = widget.geometry().top()
        if current_bottom is None or top <= current_bottom:
            current_row.append(widget)
            current_bottom = (
                widget.geometry().bottom()
                if current_bottom is None
                else max(current_bottom, widget.geometry().bottom())
            )
            continue

        rows.append(sorted(current_row, key=lambda child: child.geometry().left()))
        current_row = [widget]
        current_bottom = widget.geometry().bottom()

    if current_row:
        rows.append(sorted(current_row, key=lambda child: child.geometry().left()))
    return rows


def _assert_visible_text_widgets_fit(root, module_name):
    for label in root.findChildren(QtWidgets.QLabel):
        if not _visible_text(label, root, label.text()):
            continue
        if label.wordWrap():
            assert label.minimumWidth() == 0, module_name
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
        assert combo_box.minimumWidth() >= _combo_contents_width(combo_box), module_name
        assert combo_box.maximumWidth() >= combo_box.minimumWidth(), module_name


def _visible_text(widget, root, text):
    return not _hidden_for_fit(widget, root) and str(text).strip()


def _combo_contents_width(combo_box):
    if combo_box.count() == 0:
        return combo_box.sizeHint().width()
    metrics = combo_box.fontMetrics()
    widest_item = max(
        metrics.horizontalAdvance(str(combo_box.itemText(index)))
        for index in range(combo_box.count())
    )
    return widest_item + 48


def _root_content_height(root):
    size_hint = root.sizeHint()
    if size_hint.isValid():
        return size_hint.height()

    content_bottom = 0
    top_margin = 0
    for child in root.findChildren(
        QtWidgets.QWidget, options=QtCore.Qt.FindDirectChildrenOnly
    ):
        if child.isHidden():
            continue
        top_margin = max(top_margin, child.geometry().top())
        content_bottom = max(content_bottom, child.geometry().bottom() + 1)
    return content_bottom + top_margin


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
        assert combo.minimumWidth() >= _combo_contents_width(combo)
        assert combo.maximumWidth() >= combo.minimumWidth()
        assert root.minimumWidth() >= root.sizeHint().width()

        title_width = root.fontMetrics().horizontalAdvance(root.windowTitle())
        assert root.minimumWidth() >= title_width
    finally:
        root.close()
        root.deleteLater()
    app.processEvents()


def test_dialog_width_fit_does_not_lock_stretched_combo_geometry():
    sys.path.insert(0, str(ROOT / "src"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    root = QtWidgets.QDialog()
    root.setWindowTitle("Method & Parameters")
    layout = QtWidgets.QGridLayout(root)
    label = QtWidgets.QLabel("Analysis method:")
    label.setMinimumWidth(200)
    label.setMaximumWidth(200)
    combo = QtWidgets.QComboBox()
    combo.addItems(
        [
            "Short",
            "Medium option",
        ]
    )

    layout.addWidget(label, 0, 0)
    layout.addWidget(combo, 0, 1)
    root.resize(900, root.sizeHint().height())

    qt_layout.fit_analysis_dialog_to_contents(root)
    root.show()
    app.processEvents()

    try:
        assert combo.minimumWidth() >= _combo_contents_width(combo)
        assert combo.maximumWidth() <= qt_layout.ANALYSIS_DIALOG_COMBO_MAXIMUM_WIDTH
        assert combo.width() <= combo.maximumWidth()
        assert combo.width() < root.width() - label.width()
        assert combo.sizePolicy().horizontalPolicy() == QtWidgets.QSizePolicy.Maximum
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
        assert combo.minimumWidth() >= _combo_contents_width(combo)
        assert combo.maximumWidth() >= combo.minimumWidth()
        assert root.minimumWidth() >= qt_layout.ANALYSIS_DIALOG_MINIMUM_WIDTH
        assert root.minimumWidth() >= root.sizeHint().width()
    finally:
        root.close()
        root.deleteLater()
    app.processEvents()


def test_analysis_dialog_combo_widths_fit_long_selectable_items():
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
        assert combo.minimumWidth() >= _combo_contents_width(combo)
        assert combo.maximumWidth() >= combo.minimumWidth()
    finally:
        root.close()
        root.deleteLater()
    app.processEvents()


def test_application_dialog_refit_expands_for_new_combo_choices():
    sys.path.insert(0, str(ROOT / "src"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    root = QtWidgets.QDialog()
    root.setWindowTitle("Dynamic dialog")
    layout = QtWidgets.QVBoxLayout(root)
    label = QtWidgets.QLabel("Short label")
    combo = QtWidgets.QComboBox()
    combo.addItems(["Short", "Medium"])
    layout.addWidget(label)
    layout.addWidget(combo)

    qt_layout.fit_application_dialog_to_contents(root)
    root.show()
    app.processEvents()
    stable_width = root.width()
    stable_minimum = root.minimumSize()

    try:
        label.setText(
            "A much longer dynamically generated label that should not cause "
            "an already fitted application dialog to grow wider."
        )
        combo.addItem(
            "A much longer dynamically generated choice that should fit when refit"
        )
        qt_layout.fit_application_dialog_to_contents(root)
        app.processEvents()

        assert combo.minimumWidth() >= _combo_contents_width(combo)
        assert combo.maximumWidth() >= combo.minimumWidth()
        assert root.width() > stable_width
        assert root.minimumSize().width() > stable_minimum.width()
    finally:
        root.close()
        root.deleteLater()
    app.processEvents()


def test_application_dialog_refit_shrinks_to_current_contents():
    sys.path.insert(0, str(ROOT / "src"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    root = QtWidgets.QDialog()
    root.setWindowTitle("Dynamic dialog")
    layout = QtWidgets.QVBoxLayout(root)
    label = QtWidgets.QLabel("Visible field")
    extra = QtWidgets.QGroupBox("Advanced")
    extra_layout = QtWidgets.QVBoxLayout(extra)
    extra_layout.addWidget(QtWidgets.QLabel("Additional option"))
    layout.addWidget(label)
    layout.addWidget(extra)

    qt_layout.fit_application_dialog_to_contents(root)
    root.show()
    app.processEvents()
    expanded_height = root.height()

    try:
        extra.setVisible(False)
        qt_layout.fit_application_dialog_to_contents(root)
        app.processEvents()

        assert root.height() < expanded_height
        assert root.minimumHeight() <= max(
            root.sizeHint().height(),
            qt_layout.APPLICATION_DIALOG_MINIMUM_HEIGHT,
        )
    finally:
        root.close()
        root.deleteLater()
    app.processEvents()


def test_application_dialog_fit_collapses_expanding_vertical_spacers():
    sys.path.insert(0, str(ROOT / "src"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    root = QtWidgets.QDialog()
    layout = QtWidgets.QVBoxLayout(root)
    layout.addWidget(QtWidgets.QLabel("One visible control"))
    layout.addSpacerItem(
        QtWidgets.QSpacerItem(
            20,
            80,
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Expanding,
        )
    )
    layout.addWidget(QtWidgets.QPushButton("OK"))

    try:
        inflated_height = root.sizeHint().height()
        qt_layout.fit_application_dialog_to_contents(root)

        assert root.sizeHint().height() < inflated_height
        assert root.minimumHeight() == qt_layout.APPLICATION_DIALOG_MINIMUM_HEIGHT
    finally:
        root.close()
        root.deleteLater()
    app.processEvents()


def test_application_dialog_refits_after_first_show_content_changes():
    sys.path.insert(0, str(ROOT / "src"))
    import qt_layout

    class FirstShowExpandingDialog(QtWidgets.QDialog):
        def __init__(self):
            super(FirstShowExpandingDialog, self).__init__()
            self.label = QtWidgets.QLabel("Short")
            layout = QtWidgets.QVBoxLayout(self)
            layout.addWidget(self.label)

        def showEvent(self, event):
            super(FirstShowExpandingDialog, self).showEvent(event)
            self.label.setText(
                "A much longer first-show label that must be fitted before "
                "the user interacts with the dialog."
            )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    root = FirstShowExpandingDialog()

    try:
        qt_layout.fit_application_dialog_to_contents(root)
        root.show()
        app.processEvents()
        app.processEvents()

        assert root.label.minimumWidth() >= root.label.sizeHint().width()
        assert root.minimumWidth() >= root.sizeHint().width()
    finally:
        root.close()
        root.deleteLater()
    app.processEvents()


def test_wizard_refit_shrinks_to_current_page_contents():
    sys.path.insert(0, str(ROOT / "src"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = QtWidgets.QWizard()
    tall_page = QtWidgets.QWizardPage()
    tall_layout = QtWidgets.QVBoxLayout(tall_page)
    tall_layout.addWidget(QtWidgets.QLabel("Detailed setup"))
    tall_layout.addSpacing(220)
    compact_page = QtWidgets.QWizardPage()
    compact_layout = QtWidgets.QVBoxLayout(compact_page)
    compact_layout.addWidget(QtWidgets.QLabel("Name:"))
    compact_layout.addWidget(QtWidgets.QLineEdit())
    wizard.addPage(tall_page)
    wizard.addPage(compact_page)
    wizard.restart()
    app.processEvents()

    qt_layout.fit_application_dialog_to_contents(wizard)
    tall_height = wizard.minimumHeight()

    try:
        wizard.next()
        qt_layout.fit_application_dialog_to_contents(wizard)

        assert wizard.minimumHeight() < tall_height
        assert wizard.minimumHeight() >= qt_layout.APPLICATION_DIALOG_MINIMUM_HEIGHT
    finally:
        wizard.close()
        wizard.deleteLater()
    app.processEvents()


def test_wizard_refit_allows_current_page_to_fill_page_container():
    sys.path.insert(0, str(ROOT / "src"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = QtWidgets.QWizard()
    wide_page = QtWidgets.QWizardPage()
    wide_layout = QtWidgets.QVBoxLayout(wide_page)
    wide_label = QtWidgets.QLabel("Detailed setup that establishes the wizard width")
    wide_label.setMinimumWidth(560)
    wide_layout.addWidget(wide_label)

    compact_page = QtWidgets.QWizardPage()
    compact_page.setMinimumSize(QtCore.QSize(220, 80))
    compact_page.setMaximumSize(QtCore.QSize(220, 80))
    compact_layout = QtWidgets.QVBoxLayout(compact_page)
    compact_layout.addWidget(QtWidgets.QLabel("Name:"))
    compact_layout.addWidget(QtWidgets.QLineEdit())

    wizard.addPage(wide_page)
    wizard.addPage(compact_page)
    wizard.restart()
    app.processEvents()

    try:
        qt_layout.fit_application_dialog_to_contents(wizard)
        wizard.next()
        qt_layout.fit_application_dialog_to_contents(wizard)
        app.processEvents()

        page_width = wizard.minimumWidth() - (
            wizard.width() - wizard.currentPage().width()
        )
        page_height = wizard.minimumHeight() - (
            wizard.height() - wizard.currentPage().height()
        )
        assert compact_page.maximumWidth() >= page_width
        assert compact_page.maximumHeight() >= page_height
        assert (
            compact_page.sizePolicy().horizontalPolicy()
            == QtWidgets.QSizePolicy.Expanding
        )
        assert (
            compact_page.sizePolicy().verticalPolicy()
            == QtWidgets.QSizePolicy.Expanding
        )
    finally:
        wizard.close()
        wizard.deleteLater()
    app.processEvents()


def test_application_fit_allows_embedded_pages_to_fill_page_containers():
    sys.path.insert(0, str(ROOT / "src"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    root = QtWidgets.QDialog()
    root_layout = QtWidgets.QVBoxLayout(root)

    tab_widget = QtWidgets.QTabWidget()
    tab_page = QtWidgets.QWidget()
    tab_page.setMinimumSize(QtCore.QSize(180, 70))
    tab_page.setMaximumSize(QtCore.QSize(180, 70))
    tab_layout = QtWidgets.QVBoxLayout(tab_page)
    tab_layout.addWidget(QtWidgets.QLabel("Compact tab page"))
    tab_widget.addTab(tab_page, "Options")
    root_layout.addWidget(tab_widget)

    stacked_widget = QtWidgets.QStackedWidget()
    stacked_page = QtWidgets.QWidget()
    stacked_page.setMinimumSize(QtCore.QSize(160, 60))
    stacked_page.setMaximumSize(QtCore.QSize(160, 60))
    stacked_layout = QtWidgets.QVBoxLayout(stacked_page)
    stacked_layout.addWidget(QtWidgets.QLabel("Compact stacked page"))
    stacked_widget.addWidget(stacked_page)
    root_layout.addWidget(stacked_widget)

    try:
        qt_layout.fit_application_dialog_to_contents(root)

        for page in (tab_page, stacked_page):
            assert page.maximumWidth() == QtWidgets.QWIDGETSIZE_MAX
            assert page.maximumHeight() == QtWidgets.QWIDGETSIZE_MAX
            assert (
                page.sizePolicy().horizontalPolicy()
                == QtWidgets.QSizePolicy.Expanding
            )
            assert (
                page.sizePolicy().verticalPolicy()
                == QtWidgets.QSizePolicy.Expanding
            )
    finally:
        root.close()
        root.deleteLater()
    app.processEvents()


def test_analysis_dialog_refit_does_not_ratchet_after_hidden_content_changes():
    sys.path.insert(0, str(ROOT / "src"))
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    root = QtWidgets.QDialog()
    root.setWindowTitle("Analysis options")
    layout = QtWidgets.QVBoxLayout(root)
    details = QtWidgets.QGroupBox("Advanced")
    details_layout = QtWidgets.QVBoxLayout(details)
    details_layout.addWidget(QtWidgets.QLabel("Short advanced option"))
    layout.addWidget(QtWidgets.QLabel("Analysis method"))
    layout.addWidget(details)

    qt_layout.fit_analysis_dialog_to_contents(root)
    root.show()
    app.processEvents()
    stable_width = root.width()
    stable_height = root.height()
    stable_minimum = root.minimumSize()

    try:
        details.setVisible(False)
        qt_layout.fit_analysis_dialog_to_contents(root)
        details.setVisible(True)
        details_layout.addWidget(
            QtWidgets.QLabel(
                "A long dynamically revealed advanced option should not ratchet "
                "the fitted analysis dialog after the first stable size is recorded."
            )
        )
        qt_layout.fit_analysis_dialog_to_contents(root)
        app.processEvents()

        assert root.width() == stable_width
        assert root.height() == stable_height
        assert root.minimumSize() == stable_minimum
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
            "src/forms/ui_binary_data_form.py",
            "src/forms/binary_data_form2.ui",
            "src/forms/ui_continuous_data_form.py",
            "src/forms/continuous_data_form.ui",
            "src/forms/ui_change_cov_type.py",
            "src/forms/change_cov_type_form.ui",
            "src/forms/ui_cov_subgroup_dlg.py",
            "src/forms/cov_subgroup_dlg.ui",
            "src/forms/ui_diagnostic_explain_dlg.py",
            "src/forms/diag_explain_form.ui",
            "src/forms/ui_diagnostic_data_form.py",
            "src/forms/diagnostic_data_form.ui",
            "src/forms/ui_diagnostic_metrics.py",
            "src/forms/diagnostic_metrics.ui",
            "src/forms/ui_data_type_page.py",
            "src/forms/data_type_page.ui",
            "src/forms/ui_edit_dialog.py",
            "src/forms/edit_dialog2.ui",
            "src/forms/ui_edit_forest_plot.py",
            "src/forms/edit_forest_plot.ui",
            "src/forms/ui_edit_group_name.py",
            "src/forms/change_group_name_dlg.ui",
            "src/forms/ui_ma_specs.py",
            "src/forms/ma_specs2.ui",
            "src/forms/ui_network_view.py",
            "src/forms/network_view_window.ui",
            "src/forms/ui_new_covariate.py",
            "src/forms/new_covariate_dlg.ui",
            "src/forms/ui_new_follow_up.py",
            "src/forms/new_follow_up_dlg.ui",
            "src/forms/ui_new_group.py",
            "src/forms/new_group_dlg.ui",
            "src/forms/ui_new_outcome.py",
            "src/forms/new_outcome_dlg.ui",
            "src/forms/ui_new_study.py",
            "src/forms/new_study_dlg.ui",
            "src/forms/ui_running.py",
            "src/forms/running.ui",
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
        "OpenMeta[analyst] -",
        "Open Meta-Analysis",
        "Open Meta-Analyst",
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
        '_translate("new_covariate_dialog", "add new covariate")',
        '_translate("BinaryDataForm", "back-calculate table")',
        "<string>back-calculate table</string>",
        '_translate("diag_metric", "select metrics for analysis")',
        "<string>select metrics for analysis</string>",
        '_translate("edit_dialog", "edit dataset")',
        "<string>edit dataset</string>",
        '_translate("edit_forest_plot_dlg", "edit forest plot")',
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
        'QAction("Edit Plot"',
        "tau^2",
        "I^2",
        "Results (log scale)",
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
            "src/forms/welcome_page.ui",
            "src/forms/ui_binary_data_form.py",
            "src/forms/binary_data_form2.ui",
            "src/forms/ui_continuous_data_form.py",
            "src/forms/continuous_data_form.ui",
            "src/forms/ui_change_cov_type.py",
            "src/forms/change_cov_type_form.ui",
            "src/forms/ui_cov_subgroup_dlg.py",
            "src/forms/cov_subgroup_dlg.ui",
            "src/forms/ui_diagnostic_explain_dlg.py",
            "src/forms/diag_explain_form.ui",
            "src/forms/ui_diagnostic_data_form.py",
            "src/forms/diagnostic_data_form.ui",
            "src/forms/ui_diagnostic_metrics.py",
            "src/forms/diagnostic_metrics.ui",
            "src/forms/ui_data_type_page.py",
            "src/forms/data_type_page.ui",
            "src/forms/ui_edit_dialog.py",
            "src/forms/edit_dialog2.ui",
            "src/forms/ui_edit_forest_plot.py",
            "src/forms/edit_forest_plot.ui",
            "src/forms/ui_edit_group_name.py",
            "src/forms/change_group_name_dlg.ui",
            "src/forms/ui_ma_specs.py",
            "src/forms/ma_specs2.ui",
            "src/forms/ui_network_view.py",
            "src/forms/network_view_window.ui",
            "src/forms/ui_new_covariate.py",
            "src/forms/new_covariate_dlg.ui",
            "src/forms/ui_new_follow_up.py",
            "src/forms/new_follow_up_dlg.ui",
            "src/forms/ui_new_group.py",
            "src/forms/new_group_dlg.ui",
            "src/forms/ui_new_outcome.py",
            "src/forms/new_outcome_dlg.ui",
            "src/forms/ui_new_study.py",
            "src/forms/new_study_dlg.ui",
            "src/forms/ui_running.py",
            "src/forms/running.ui",
            "src/ui_meta.py",
            "src/meta.ui",
            "src/ui_results_window.py",
            "src/results_window.ui",
            "src/results_window.py",
            "src/conf_level_dialog.py",
            "src/main_wizard.py",
            "src/meta_form.py",
            "src/continuous_data_form.py",
            "src/edit_group_name_form.py",
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
        "Create a New Dataset",
        "Open Recent...",
        "Diagnostic Data",
        "Regression\nCoefficient",
        "Follow-Ups",
        "Undo",
        "Ctrl+Z",
        "Correction factor target",
        "Number of digits",
        "Fixed-Effect Model",
        "Outcomes must be numeric.",
        "Negative Predictive Value",
        "Yule's Y",
        "OpenMetaAnalyst",
        "You've made unsaved changes to your data. Do you want to save your changes?",
        "Choose CSV File",
        "Open Existing Dataset",
        "Covariate for",
        "Tool Bar",
        "SMD Bias Correction",
        "Rename Covariate %s",
        "Expected a whole number",
        "prepended to study_data.csv",
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
        '_translate("Dialog", "Forest Plot")',
        '_translate("new_covariate_dialog", "Add Covariate")',
        '_translate("BinaryDataForm", "Back-Calculate Table")',
        '_translate("ContinuousDataForm", "Back-Calculate Table")',
        '_translate("DiagnosticDataForm", "Back-Calculate Table")',
        '_translate("diag_metric", "Select Metrics for Analysis")',
        '_translate("edit_dialog", "Edit Dataset")',
        '_translate("edit_forest_plot_dlg", "Edit Forest Plot")',
        '_translate("running", "Running Analysis...")',
        '_translate("DataTypePage", "Proportion")',
        'QAction("Rename Group %s"',
        'QAction("Rename Covariate %s"',
        'QAction("Save PDF Image As"',
        'QAction("Save PNG Image As"',
    ]

    for expected_string in expected_strings:
        assert expected_string in text


def test_issue_173_user_facing_commands_and_headers_use_desktop_casing():
    text = _combined_text(
        [
            "src/meta.ui",
            "src/ui_meta.py",
            "src/forms/binary_data_form2.ui",
            "src/forms/ui_binary_data_form.py",
            "src/forms/continuous_data_form.ui",
            "src/forms/ui_continuous_data_form.py",
            "src/forms/diagnostic_data_form.ui",
            "src/forms/ui_diagnostic_data_form.py",
            "src/ma_data_table_view.py",
            "src/meta_form.py",
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
        "Open File: %s",
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
