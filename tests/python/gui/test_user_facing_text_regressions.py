from pathlib import Path
import importlib
from typing import TYPE_CHECKING, cast

from PyQt6 import QtCore, QtWidgets

from rc_metastudio.qt6_ui import prepare_generated_ui_imports
from test_types import required

prepare_generated_ui_imports()

if TYPE_CHECKING:
    from ui_main_window import Ui_MainWindow
else:
    from rc_metastudio.ui_main_window import Ui_MainWindow


ROOT = Path(__file__).resolve().parents[3]
HELP_HTML = sorted(
    path.relative_to(ROOT).as_posix() for path in (ROOT / "doc").glob("*.html")
)

GENERATED_UI_MODULE_NAMES = [
    "rc_metastudio.forms.ui_about_legal",
    "rc_metastudio.forms.ui_binary_data_dialog",
    "rc_metastudio.forms.ui_covariate_type_dialog",
    "rc_metastudio.forms.ui_binary_back_calculation_dialog",
    "rc_metastudio.forms.ui_continuous_back_calculation_dialog",
    "rc_metastudio.forms.ui_choose_metric_page",
    "rc_metastudio.forms.ui_subgroup_analysis_dialog",
    "rc_metastudio.forms.ui_csv_import_page",
    "rc_metastudio.forms.ui_data_type_page",
    "rc_metastudio.forms.ui_diagnostic_data_dialog",
    "rc_metastudio.forms.ui_diagnostic_metrics_dialog",
    "rc_metastudio.forms.ui_edit_dialog",
    "rc_metastudio.forms.ui_edit_plot_dialog",
    "rc_metastudio.forms.ui_edit_name_dialog",
    "rc_metastudio.forms.ui_analysis_setup_dialog",
    "rc_metastudio.forms.ui_meta_regression_dialog",
    "rc_metastudio.forms.ui_network_view_dialog",
    "rc_metastudio.forms.ui_new_covariate_dialog",
    "rc_metastudio.forms.ui_new_follow_up_dialog",
    "rc_metastudio.forms.ui_new_group_dialog",
    "rc_metastudio.forms.ui_new_outcome_dialog",
    "rc_metastudio.forms.ui_new_study_dialog",
    "rc_metastudio.forms.ui_outcome_name_page",
    "rc_metastudio.forms.ui_progress_dialog",
    "rc_metastudio.forms.ui_welcome_page",
    "rc_metastudio.ui_main_window",
    "rc_metastudio.ui_results_window",
]


def _read(relative_path):
    source_path = Path(relative_path)
    if source_path.parent == Path(
        "src/rc_metastudio/forms"
    ) and source_path.name.startswith("ui_"):
        source_path = Path("build/qt6/generated/rc_metastudio/forms") / source_path.name
    elif source_path in {
        Path("src/rc_metastudio/ui_main_window.py"),
        Path("src/rc_metastudio/ui_results_window.py"),
    }:
        source_path = Path("build/qt6/generated/rc_metastudio") / source_path.name
    return (ROOT / source_path).read_text(encoding="utf-8")


def _combined_text(paths):
    return "\n".join(_read(path) for path in paths)


def test_issue_94_current_outcome_and_follow_up_labels_can_expand():
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

    for label in (ui.current_outcome_label, ui.current_follow_up_label):
        assert label.maximumWidth() > 80
        assert (
            label.sizePolicy().horizontalPolicy() != QtWidgets.QSizePolicy.Policy.Fixed
        )

    window.deleteLater()
    app.processEvents()


def test_issue_190_main_window_does_not_expose_toolbar_toggle_popup():
    from rc_metastudio.main_window import MainWindow

    app = cast(
        QtWidgets.QApplication,
        required(
            QtWidgets.QApplication.instance() or QtWidgets.QApplication([]),
            "application",
        ),
    )
    window = MainWindow()

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
    from rc_metastudio import confidence_level_dialog

    app = cast(
        QtWidgets.QApplication,
        required(
            QtWidgets.QApplication.instance() or QtWidgets.QApplication([]),
            "application",
        ),
    )
    dialog = confidence_level_dialog.ConfidenceLevelDialog(95.0)
    dialog.show()
    app.processEvents()

    try:
        assert (
            required(dialog.layout(), "dialog layout").sizeConstraint()
            == QtWidgets.QLayout.SizeConstraint.SetMinimumSize
        )
        from rc_metastudio import adaptive_window

        assert (
            adaptive_window.adaptive_window_state(dialog).policy.archetype.value
            == "transactional"
        )
        assert dialog.minimumWidth() < dialog.sizeHint().width()
    finally:
        dialog.close()
        dialog.deleteLater()
    app.processEvents()
