from pathlib import Path
import importlib
import sys
from typing import cast

from PyQt6 import QtCore, QtWidgets

from rc_metastudio.qt6_ui import prepare_generated_ui_imports
from test_types import required

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
    if source_path.parent == Path(
        "src/rc_metastudio/forms"
    ) and source_path.name.startswith("ui_"):
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

    app = cast(
        QtWidgets.QApplication,
        required(
            QtWidgets.QApplication.instance() or QtWidgets.QApplication([]),
            "application",
        ),
    )
    window = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(window)

    for label in (ui.cur_outcome_lbl, ui.cur_time_lbl):
        assert label.maximumWidth() > 80
        assert (
            label.sizePolicy().horizontalPolicy() != QtWidgets.QSizePolicy.Policy.Fixed
        )

    window.deleteLater()
    app.processEvents()


def test_issue_190_main_window_does_not_expose_toolbar_toggle_popup():
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "src" / "forms"))
    from meta_form import MetaForm

    app = cast(
        QtWidgets.QApplication,
        required(
            QtWidgets.QApplication.instance() or QtWidgets.QApplication([]),
            "application",
        ),
    )
    window = MetaForm()

    try:
        assert window.createPopupMenu() is None
        assert required(
            window.toolBar.toggleViewAction(), "toolbar toggle action"
        ).isEnabled()
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
                QtWidgets.QWidget,
                options=QtCore.Qt.FindChildOption.FindDirectChildrenOnly,
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

    app = cast(
        QtWidgets.QApplication,
        required(
            QtWidgets.QApplication.instance() or QtWidgets.QApplication([]),
            "application",
        ),
    )
    dialog = conf_level_dialog.ChangeConfLevelDlg(95.0)
    dialog.show()
    app.processEvents()

    try:
        assert (
            required(dialog.layout(), "dialog layout").sizeConstraint()
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
