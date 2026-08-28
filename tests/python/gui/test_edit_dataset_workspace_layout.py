import types
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PyQt6 import QtCore, QtGui, QtTest, QtWidgets

pytestmark = pytest.mark.qsettings


ROOT = Path(__file__).resolve().parents[3]
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RCMS_QT6_BUILD_ROOT", str(ROOT / "build" / "qt6-verification"))
from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()
import adaptive_window


DATASET_FORM_PATHS = (
    "edit_dialog2.ui",
    "new_study_dlg.ui",
    "new_outcome_dlg.ui",
    "new_follow_up_dlg.ui",
    "new_group_dlg.ui",
    "new_covariate_dlg.ui",
    "change_group_name_dlg.ui",
)


class _DatasetParent(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.model = types.SimpleNamespace(
            current_outcome="Outcome",
            get_current_follow_up_name=lambda: "first",
        )


def _empty_edit_dialog(parent):
    import edit_dialog
    import ma_dataset

    dataset = ma_dataset.Dataset()
    dataset.add_outcome(ma_dataset.Outcome("Outcome", ma_dataset.BINARY))
    return edit_dialog.EditDialog(dataset, parent=parent)


def _dispose(qapp, *widgets):
    for widget in widgets:
        widget.close()
        widget.deleteLater()
    qapp.processEvents()


@pytest.mark.parametrize("screen_size", [(800, 600), (1024, 640), (1600, 1000)])
def test_edit_dataset_first_use_tracks_logical_screen_contract(
    qapp, monkeypatch, screen_size
):
    import adaptive_window

    available = QtCore.QRect(0, 0, *screen_size)
    monkeypatch.setattr(
        adaptive_window,
        "available_geometry_for_window",
        lambda _window: QtCore.QRect(available),
    )
    parent = _DatasetParent()
    dialog = _empty_edit_dialog(parent)
    try:
        assert dialog.frameGeometry().width() == pytest.approx(
            available.width() * 0.80, abs=8
        )
        assert dialog.frameGeometry().height() == pytest.approx(
            available.height() * 0.80, abs=8
        )
        assert available.contains(dialog.frameGeometry())
    finally:
        _dispose(qapp, dialog, parent)


def test_edit_dataset_is_modal_workspace_with_persisted_placement_and_panes(
    qapp, tmp_path
):
    import ma_dataset
    import settings

    parent = _DatasetParent()
    parent.setGeometry(0, 0, 800, 600)
    parent.show()
    first = _empty_edit_dialog(parent)
    try:
        first.show()
        qapp.processEvents()
        available = first.screen().availableGeometry()

        assert first.isModal()
        assert (
            adaptive_window.adaptive_window_state(first).policy.archetype
            is adaptive_window.WindowArchetype.WORKSPACE
        )
        assert (
            adaptive_window.adaptive_window_state(first).role
            is adaptive_window.WindowRole.EDIT_DATASET
        )
        assert first.frameGeometry().width() == pytest.approx(
            available.width() * 0.80, abs=8
        )
        assert first.frameGeometry().height() == pytest.approx(
            available.height() * 0.80, abs=8
        )
        assert first.dataset_structure_splitter.count() == 3
        for view in (
            first.outcome_list,
            first.follow_up_list,
            first.group_list,
            first.study_list,
            first.covariate_list,
        ):
            assert (
                view.sizePolicy().horizontalPolicy()
                == QtWidgets.QSizePolicy.Policy.Expanding
            )
            assert (
                view.sizePolicy().verticalPolicy()
                == QtWidgets.QSizePolicy.Policy.Expanding
            )
            assert (
                view.horizontalScrollBarPolicy()
                == QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
            assert (
                view.verticalScrollBarPolicy()
                == QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )

        for button in (
            first.add_outcome_btn,
            first.remove_outcome_btn,
            first.add_follow_up_btn,
            first.remove_follow_up_btn,
            first.add_group_btn,
            first.remove_group_btn,
            first.add_study_btn,
            first.remove_study_btn,
            first.add_covariate_btn,
            first.remove_covariate_btn,
        ):
            assert button.iconSize() == QtCore.QSize(24, 24)
            assert button.size() == QtCore.QSize(32, 32)
            assert not button.icon().isNull()

        original_font = QtGui.QFont(first.font())
        enlarged = QtGui.QFont(original_font)
        enlarged.setPointSize(max(16, enlarged.pointSize() + 6))
        first.setFont(enlarged)
        qapp.processEvents()
        stable_geometry = QtCore.QRect(first.geometry())
        assert first.buttonBox.isVisible()
        assert first.rect().contains(first.buttonBox.geometry().center())
        for index in range(40):
            first.dataset.add_study(
                ma_dataset.Study(index, name=("Very long study name " * 8) + str(index))
            )
        first.studies_model.update_study_list()
        first.edit_tab.setCurrentWidget(first.tab_2)
        qapp.processEvents()
        assert first.geometry() == stable_geometry
        assert first.study_list.textElideMode() == QtCore.Qt.TextElideMode.ElideNone
        assert first.study_list.horizontalScrollBar().maximum() > 0

        first.edit_tab.setCurrentWidget(first.tab)
        first.activateWindow()
        first.outcome_list.setFocus()
        traversed = set()
        for _ in range(8):
            QtTest.QTest.keyClick(qapp.focusWidget(), QtCore.Qt.Key.Key_Tab)
            traversed.add(qapp.focusWidget().objectName())
        assert {
            "add_outcome_btn",
            "follow_up_list",
            "add_follow_up_btn",
            "group_list",
            "add_group_btn",
        }.issubset(traversed)

        first.setFont(original_font)
        qapp.processEvents()
        first.showNormal()
        first.setGeometry(20, 60, 760, 430)
        first.dataset_structure_splitter.setSizes([200, 250, 350])
        qapp.processEvents()
        expected_frame = QtCore.QRect(first.frameGeometry())
        expected_sizes = first.dataset_structure_splitter.sizes()
        expected_proportions = tuple(
            value / sum(expected_sizes) for value in expected_sizes
        )
        first.done(QtWidgets.QDialog.DialogCode.Rejected)

        state = settings.load_edit_dataset_window_state(
            available_geometries=[QtCore.QRect(0, 0, 800, 600)]
        )
        assert state.frame_geometry == expected_frame
        assert state.splitter_proportions == pytest.approx(expected_proportions)

        restored = _empty_edit_dialog(parent)
        try:
            restored.show()
            qapp.processEvents()
            assert restored.frameGeometry() == expected_frame
            sizes = restored.dataset_structure_splitter.sizes()
            assert [value / sum(sizes) for value in sizes] == pytest.approx(
                expected_proportions, abs=0.03
            )
        finally:
            _dispose(qapp, restored)

        store = QtCore.QSettings()
        group = settings.EDIT_DATASET_WORKSPACE_GROUP
        store.setValue(group + "/frame_geometry", QtCore.QRect(5000, 4000, 760, 430))
        store.setValue(group + "/maximized", True)
        store.setValue(group + "/full_screen", True)
        store.sync()
        stale = settings.load_edit_dataset_window_state(
            available_geometries=[QtCore.QRect(0, 0, 800, 600)]
        )
        assert stale.frame_geometry is None
        assert not store.contains(group + "/frame_geometry")
        assert stale.maximized is True
        assert stale.full_screen is True
    finally:
        _dispose(qapp, first, parent)


def test_dataset_nested_actions_keep_long_required_content_and_keyboard_access(qapp):
    import add_new_dialogs
    import edit_group_name_form

    old_font = QtGui.QFont(qapp.font())
    enlarged = QtGui.QFont(old_font)
    enlarged.setPointSize(max(16, old_font.pointSize() + 6))
    qapp.setFont(enlarged)
    long_name = "A very long dataset structure name " * 12
    dialogs = [
        add_new_dialogs.AddNewStudyForm(),
        add_new_dialogs.AddNewOutcomeForm(),
        add_new_dialogs.AddNewFollowUpForm(),
        add_new_dialogs.AddNewGroupForm(),
        add_new_dialogs.AddNewCovariateForm(),
        edit_group_name_form.EditGroupName(long_name),
        edit_group_name_form.EditCovariateName(long_name),
    ]
    try:
        for dialog in dialogs:
            dialog.resize(320, 180)
            dialog.show()
            qapp.processEvents()
            assert (
                adaptive_window.adaptive_window_state(dialog).policy.archetype
                is adaptive_window.WindowArchetype.TRANSACTIONAL
            )
            assert dialog.layout() is not None
            assert dialog.buttonBox.isVisible()
            assert dialog.rect().contains(dialog.buttonBox.geometry().center())

        outcome = dialogs[1]
        outcome.activateWindow()
        outcome.raise_()
        qapp.processEvents()
        outcome.outcome_name_le.setText(long_name)
        outcome.outcome_name_le.setFocus()
        QtTest.QTest.keyClick(outcome.outcome_name_le, QtCore.Qt.Key.Key_Tab)
        assert outcome.datatype_cbo_box.hasFocus()
        assert outcome.outcome_name_le.text() == long_name

        rename = dialogs[-1]
        rename.activateWindow()
        rename.raise_()
        qapp.processEvents()
        assert rename.group_name_le.text() == long_name
        rename.group_name_le.setFocus()
        QtTest.QTest.keyClick(rename.group_name_le, QtCore.Qt.Key.Key_Tab)
        assert qapp.focusWidget() in rename.buttonBox.buttons()
    finally:
        qapp.setFont(old_font)
        _dispose(qapp, *dialogs)


def test_dataset_path_canonical_forms_are_declarative_and_platform_native():
    forms_dir = Path("src/rc_metastudio/forms")
    for filename in DATASET_FORM_PATHS:
        path = forms_dir / filename
        text = path.read_text(encoding="utf-8")
        root = ET.fromstring(text)
        top_widget = root.find("widget")

        assert "Verdana" not in text
        assert top_widget is not None
        root_geometry = top_widget.find("property[@name='geometry']/rect")
        assert root_geometry is not None
        assert int(root_geometry.findtext("width", "-1")) == 0, filename
        assert int(root_geometry.findtext("height", "-1")) == 0, filename
        assert top_widget.find("layout") is not None
        assert top_widget.find("property[@name='minimumSize']") is None
        assert top_widget.find("property[@name='maximumSize']") is None
        for child in top_widget.iter("widget"):
            if child is not top_widget:
                assert child.find("property[@name='geometry']") is None, (
                    filename,
                    child.attrib.get("name"),
                )
