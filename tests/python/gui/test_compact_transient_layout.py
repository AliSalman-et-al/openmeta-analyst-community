import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from PyQt6 import QtCore, QtGui, QtWidgets


ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RCMS_QT6_BUILD_ROOT", str(ROOT / "build" / "qt6-verification"))
from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()
LONG_VALUE = "A representative translated value with complete required content " * 20


def _show(window, qapp):
    window.show()
    qapp.processEvents()
    qapp.processEvents()


def _remaining_surface_inventory():
    import about_legal_dialog
    import add_new_dialogs
    import adaptive_controls
    import edit_group_name_form
    import launch
    import ma_specs
    import meta_form
    import progress_bar

    surfaces = [
        ("add-group", "compact", add_new_dialogs.AddNewGroupForm()),
        ("add-follow-up", "compact", add_new_dialogs.AddNewFollowUpForm()),
        ("add-outcome", "choice", add_new_dialogs.AddNewOutcomeForm()),
        (
            "add-diagnostic-outcome",
            "choice",
            add_new_dialogs.AddNewOutcomeForm(is_diag=True),
        ),
        ("add-study", "compact", add_new_dialogs.AddNewStudyForm()),
        ("add-covariate", "choice", add_new_dialogs.AddNewCovariateForm()),
        (
            "edit-group-name",
            "compact",
            edit_group_name_form.EditGroupName("Treatment group"),
        ),
        (
            "edit-covariate-name",
            "compact",
            edit_group_name_form.EditCovariateName("Baseline risk"),
        ),
        ("about-legal", "about", about_legal_dialog.AboutLegalDialog()),
        (
            "import-progress",
            "progress",
            meta_form.ImportProgress(min_=0, max_=100),
        ),
        ("analysis-progress", "progress", ma_specs.MetaProgress()),
        ("shared-progress", "progress", progress_bar.MetaProgress()),
        ("startup-splash", "splash", launch.create_startup_splash()),
    ]
    for _name, kind, window in surfaces:
        for line_edit in window.findChildren(QtWidgets.QLineEdit):
            line_edit.setText(LONG_VALUE)
        if kind == "choice":
            combo = window.findChild(QtWidgets.QComboBox)
            combo.addItem(LONG_VALUE)
            combo.setCurrentText(LONG_VALUE)
        if kind == "progress":
            window.progress_bar.setFormat("Loading analysis resources: %p%")
        if kind == "splash":
            window.showMessage(LONG_VALUE)
    return surfaces


def _frame_margins(window):
    frame = window.frameGeometry()
    return QtCore.QSize(
        max(0, frame.width() - window.width()),
        max(0, frame.height() - window.height()),
    )


def _pixmap_logical_size(pixmap):
    ratio = max(1.0, pixmap.devicePixelRatioF())
    return QtCore.QSize(round(pixmap.width() / ratio), round(pixmap.height() / ratio))


def _assert_content_preferred_outer_size(window, available, fraction, tolerance=6):
    hint = window.sizeHint().expandedTo(window.minimumSizeHint())
    frame_extra = _frame_margins(window)
    expected_width = min(
        hint.width() + frame_extra.width(), int(available.width() * fraction)
    )
    expected_height = min(
        hint.height() + frame_extra.height(), int(available.height() * fraction)
    )
    frame = window.frameGeometry()
    assert abs(frame.width() - expected_width) <= tolerance
    assert abs(frame.height() - expected_height) <= tolerance


def test_complete_compact_transactional_inventory_is_content_preferred(
    qapp, monkeypatch
):
    import adaptive_window

    original_font = QtGui.QFont(qapp.font())
    for enlarged_font in (False, True):
        font = QtGui.QFont(original_font)
        if enlarged_font:
            font.setPointSize(max(16, font.pointSize() + 6))
        qapp.setFont(font)
        for available_size in ((800, 600), (1024, 640), (1600, 1000)):
            available = QtCore.QRect(0, 0, *available_size)
            monkeypatch.setattr(
                adaptive_window,
                "available_geometry_for_window",
                lambda _window, bounds=available: bounds,
            )
            surfaces = _remaining_surface_inventory()
            try:
                for name, kind, window in surfaces:
                    _show(window, qapp)
                    expected = (
                        adaptive_window.WindowArchetype.TRANSIENT
                        if kind in ("progress", "splash")
                        else adaptive_window.WindowArchetype.TRANSACTIONAL
                    )
                    assert (
                        adaptive_window.adaptive_window_state(window).policy.archetype
                        is expected
                    ), name
                    assert available.contains(window.frameGeometry()), name

                    if kind in ("compact", "choice"):
                        assert not window.findChildren(QtWidgets.QScrollArea), name
                        _assert_content_preferred_outer_size(window, available, 0.90)
                        button_box = window.findChild(QtWidgets.QDialogButtonBox)
                        for role in (
                            QtWidgets.QDialogButtonBox.StandardButton.Ok,
                            QtWidgets.QDialogButtonBox.StandardButton.Cancel,
                        ):
                            assert button_box.button(role).isVisible(), (name, role)
                        for editor in window.findChildren(QtWidgets.QLineEdit):
                            assert editor.isVisible() and editor.isEnabled(), name
                    elif kind == "about":
                        assert isinstance(
                            window.content_scroll_area, QtWidgets.QTextBrowser
                        )
                        close = window.buttonBox.button(
                            QtWidgets.QDialogButtonBox.StandardButton.Close
                        )
                        assert close.isVisible()
                        assert not window.content_scroll_area.isAncestorOf(close)
                        assert (
                            "GPL-3.0-or-later"
                            in window.content_scroll_area.toPlainText()
                        )
                    elif kind == "progress":
                        _assert_content_preferred_outer_size(window, available, 1.0)
                        frame = window.frameGeometry()
                        assert frame.width() < available.width() * 0.60, name
                        assert frame.height() < available.height() * 0.30, name
                        assert window.isSizeGripEnabled() is False
                        initial = QtCore.QRect(frame)
                        window.progress_bar.setValue(window.progress_bar.maximum())
                        qapp.processEvents()
                        assert window.frameGeometry() == initial, name
                    else:
                        assert not window.pixmap().isNull()
                        assert window.size() == _pixmap_logical_size(window.pixmap())
            finally:
                for _name, _kind, window in surfaces:
                    window.close()
                    window.deleteLater()
                qapp.processEvents()
    qapp.setFont(original_font)


def test_long_choice_values_remain_available_without_widening_the_dialog(qapp):
    import add_new_dialogs
    import adaptive_controls

    for dialog in (
        add_new_dialogs.AddNewOutcomeForm(),
        add_new_dialogs.AddNewCovariateForm(),
    ):
        combo = dialog.datatype_cbo_box
        combo.addItem(LONG_VALUE)
        combo.setCurrentText(LONG_VALUE)
        _show(dialog, qapp)
        try:
            controller = adaptive_controls.choice_control_controller(combo)
            assert controller.combo is combo
            assert controller.parent() is combo
            assert combo.toolTip() == LONG_VALUE
            assert (
                combo.itemData(combo.currentIndex(), QtCore.Qt.ItemDataRole.ToolTipRole)
                == LONG_VALUE
            )
            assert (
                combo.view().horizontalScrollBarPolicy()
                == QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
            assert (
                dialog.frameGeometry().width()
                < dialog.screen().availableGeometry().width()
            )
        finally:
            dialog.close()
    qapp.processEvents()


def test_choice_control_state_is_typed_and_rejects_stale_ownership(qapp):
    import adaptive_controls

    unconfigured = adaptive_controls.AdaptiveComboBox()
    with pytest.raises(LookupError, match="not configured"):
        adaptive_controls.choice_control_controller(unconfigured)

    owner = adaptive_controls.AdaptiveComboBox()
    stale_target = adaptive_controls.AdaptiveComboBox()
    controller = adaptive_controls.configure_choice_control(owner)
    stale_target._adaptive_choice_controller = controller
    with pytest.raises(LookupError, match="stale ownership"):
        adaptive_controls.choice_control_controller(stale_target)

    assert adaptive_controls.choice_control_controller(owner) is controller


def test_compact_transactional_keyboard_and_accessibility_matrix(qapp, monkeypatch):
    import add_new_dialogs
    import change_cov_type_form
    import edit_group_name_form
    from PyQt6.QtTest import QTest

    class PreviewModel(QtGui.QStandardItemModel):
        dataError = QtCore.pyqtSignal(str)

        def __init__(self, _dataset, _covariate):
            super().__init__(2, 3)

    monkeypatch.setattr(change_cov_type_form, "CovModel", PreviewModel)
    factories = (
        ("add-group", add_new_dialogs.AddNewGroupForm, "group_name_le"),
        ("add-follow-up", add_new_dialogs.AddNewFollowUpForm, "follow_up_name_le"),
        ("add-outcome", add_new_dialogs.AddNewOutcomeForm, "outcome_name_le"),
        ("add-study", add_new_dialogs.AddNewStudyForm, "study_lbl"),
        ("add-covariate", add_new_dialogs.AddNewCovariateForm, "covariate_name_le"),
        (
            "edit-group-name",
            lambda: edit_group_name_form.EditGroupName("Original group"),
            "group_name_le",
        ),
        (
            "edit-covariate-name",
            lambda: edit_group_name_form.EditCovariateName("Original covariate"),
            "group_name_le",
        ),
        (
            "change-covariate-type",
            lambda: change_cov_type_form.ChangeCovTypeForm(object(), object()),
            "cov_prev_table",
        ),
    )

    for name, factory, initial_name in factories:
        accepted = []
        dialog = factory()
        dialog.accepted.connect(lambda surface=name: accepted.append(surface))
        dialog.show()
        dialog.activateWindow()
        qapp.processEvents()
        initial = dialog.findChild(QtWidgets.QWidget, initial_name)
        assert initial is not None, name
        assert initial.isVisible() and initial.isEnabled(), name
        initial.setFocus()
        qapp.processEvents()
        assert qapp.focusWidget() is initial, name
        box = dialog.findChild(QtWidgets.QDialogButtonBox)
        ok = box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        cancel = box.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        assert ok.isVisible() and ok.isDefault(), name
        assert cancel.isVisible(), name
        QTest.keyClick(initial, QtCore.Qt.Key.Key_Tab)
        qapp.processEvents()
        assert qapp.focusWidget() is not initial, name
        for control in dialog.findChildren(QtWidgets.QAbstractButton):
            if control.icon().isNull() or control.text().strip():
                continue
            assert control.accessibleName().strip(), (name, control.objectName())
        for view in dialog.findChildren(QtWidgets.QAbstractItemView):
            if isinstance(view, QtWidgets.QHeaderView):
                continue
            assert view.accessibleName().strip(), (name, view.objectName())
        initial.setFocus()
        QTest.keyClick(initial, QtCore.Qt.Key.Key_Return)
        qapp.processEvents()
        assert accepted == [name], name
        dialog.deleteLater()
        qapp.processEvents()

        rejected = []
        dialog = factory()
        before_cancel = {
            "editors": [editor.text() for editor in dialog.findChildren(QtWidgets.QLineEdit)],
            "models": [
                (view.model().rowCount(), view.model().columnCount())
                for view in dialog.findChildren(QtWidgets.QAbstractItemView)
                if view.model() is not None
            ],
        }
        dialog.rejected.connect(lambda surface=name: rejected.append(surface))
        dialog.show()
        qapp.processEvents()
        QTest.keyClick(dialog, QtCore.Qt.Key.Key_Escape)
        qapp.processEvents()
        assert rejected == [name], name
        assert dialog.result() == QtWidgets.QDialog.DialogCode.Rejected, name
        assert not dialog.isVisible(), name
        assert before_cancel == {
            "editors": [editor.text() for editor in dialog.findChildren(QtWidgets.QLineEdit)],
            "models": [
                (view.model().rowCount(), view.model().columnCount())
                for view in dialog.findChildren(QtWidgets.QAbstractItemView)
                if view.model() is not None
            ],
        }, name
        dialog.deleteLater()
        qapp.processEvents()


def test_about_legal_has_explicit_overflow_and_reachable_action(qapp):
    import about_legal_dialog

    dialog = about_legal_dialog.AboutLegalDialog()
    dialog.content_scroll_area.setHtml("<p>{}</p>".format(LONG_VALUE * 8))
    enlarged = QtGui.QFont(dialog.font())
    enlarged.setPointSize(max(16, enlarged.pointSize() + 6))
    dialog.setFont(enlarged)
    dialog.resize(420, 300)
    _show(dialog, qapp)
    try:
        close_button = dialog.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Close
        )
        import adaptive_window

        assert (
            adaptive_window.adaptive_window_state(dialog).policy.archetype
            is adaptive_window.WindowArchetype.TRANSACTIONAL
        )
        assert dialog.content_scroll_area.verticalScrollBar().maximum() > 0
        assert close_button.isVisible()
        assert not dialog.content_scroll_area.isAncestorOf(close_button)
        assert dialog.content_scroll_area.lineWrapMode() != (
            QtWidgets.QTextEdit.LineWrapMode.NoWrap
        )
    finally:
        dialog.close()
        qapp.processEvents()


def test_all_progress_entry_points_are_minimal_stable_transient_windows(qapp):
    progress_surfaces = [
        entry for entry in _remaining_surface_inventory() if entry[1] == "progress"
    ]
    try:
        for name, _kind, dialog in progress_surfaces:
            _show(dialog, qapp)
            _assert_content_preferred_outer_size(
                dialog, qapp.primaryScreen().availableGeometry(), 1.0
            )
            frame = QtCore.QRect(dialog.frameGeometry())
            assert frame.width() < 480, name
            assert frame.height() < 160, name
            dialog.progress_bar.setValue(dialog.progress_bar.maximum())
            qapp.processEvents()
            assert dialog.frameGeometry() == frame, name
    finally:
        for _name, _kind, dialog in progress_surfaces:
            dialog.close()
        qapp.processEvents()


def test_startup_splash_declares_transient_archetype(qapp):
    import launch

    splash = launch.create_startup_splash()
    try:
        _show(splash, qapp)
        import adaptive_window

        assert (
            adaptive_window.adaptive_window_state(splash).policy.archetype
            is adaptive_window.WindowArchetype.TRANSIENT
        )
        assert not splash.pixmap().isNull()
        assert splash.size() == _pixmap_logical_size(splash.pixmap())
    finally:
        splash.close()
        qapp.processEvents()


def test_bounded_dpr_splash_preserves_its_logical_size(qapp):
    import launch

    source = QtGui.QPixmap(800, 600)
    source.fill(QtGui.QColor("navy"))
    source.setDevicePixelRatio(2.0)

    bounded = launch.screen_bounded_splash_pixmap(source, QtCore.QSize(500, 400))

    assert bounded.devicePixelRatioF() == 2.0
    assert bounded.size() == QtCore.QSize(800, 600)
    assert _pixmap_logical_size(bounded) == QtCore.QSize(400, 300)


def test_oversized_dpr_splash_is_bounded_without_double_scaling(qapp):
    import launch

    source = QtGui.QPixmap(1600, 1200)
    source.fill(QtGui.QColor("navy"))
    source.setDevicePixelRatio(2.0)

    bounded = launch.screen_bounded_splash_pixmap(source, QtCore.QSize(500, 320))
    logical_width = bounded.width() / bounded.devicePixelRatioF()
    logical_height = bounded.height() / bounded.devicePixelRatioF()

    assert bounded.devicePixelRatioF() == 2.0
    assert logical_width <= 500
    assert logical_height <= 320
    assert logical_width > 400
    assert abs((logical_width / logical_height) - (4.0 / 3.0)) < 0.01


def test_remaining_inventory_survives_representative_process_scale_factors():
    script = r"""
import json
from PyQt6 import QtWidgets
from rc_metastudio.qt6_ui import prepare_generated_ui_imports
prepare_generated_ui_imports()
import app_error_handler
import adaptive_window
import about_legal_dialog, add_new_dialogs, edit_group_name_form, launch, ma_specs, meta_form, progress_bar

app = app_error_handler.get_or_create_application([])
windows = [
    add_new_dialogs.AddNewGroupForm(), add_new_dialogs.AddNewFollowUpForm(),
    add_new_dialogs.AddNewOutcomeForm(), add_new_dialogs.AddNewOutcomeForm(is_diag=True),
    add_new_dialogs.AddNewStudyForm(), add_new_dialogs.AddNewCovariateForm(),
    edit_group_name_form.EditGroupName("Group"),
    edit_group_name_form.EditCovariateName("Covariate"),
    about_legal_dialog.AboutLegalDialog(), meta_form.ImportProgress(),
    ma_specs.MetaProgress(), progress_bar.MetaProgress(), launch.create_startup_splash(),
]
for window in windows:
    window.show()
app.processEvents(); app.processEvents()
available = app.primaryScreen().availableGeometry()
payload = {
    "roles": [adaptive_window.adaptive_window_state(window).policy.archetype.value for window in windows],
    "visible": all(window.isVisible() for window in windows),
    "actions": all(box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).isVisible()
        for box in [window.findChild(QtWidgets.QDialogButtonBox) for window in windows[:8]]),
    "splash": not windows[-1].pixmap().isNull(),
    "bounded": all(available.contains(window.frameGeometry()) for window in windows),
}
for window in windows:
    window.close()
    window.deleteLater()
app.processEvents()
print("COMPACT_LAYOUT=" + json.dumps(payload), flush=True)
"""
    expected_roles = ["transactional"] * 9 + ["transient"] * 4
    for scale_factor in ("1", "1.5", "2"):
        environment = os.environ.copy()
        environment.update(
            {
                "QT_QPA_PLATFORM": "offscreen",
                "QT_SCALE_FACTOR": scale_factor,
                "PYTHONPATH": os.pathsep.join(
                    [
                        str(ROOT / "src"),
                        str(ROOT / "src" / "rc_metastudio"),
                        str(
                            ROOT
                            / "build"
                            / "qt6-verification"
                            / "generated"
                            / "rc_metastudio"
                        ),
                    ]
                ),
                "RCMS_QT6_BUILD_ROOT": str(ROOT / "build" / "qt6-verification"),
            }
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        marker = next(
            line
            for line in completed.stdout.splitlines()
            if line.startswith("COMPACT_LAYOUT=")
        )
        assert json.loads(marker.split("=", 1)[1]) == {
            "roles": expected_roles,
            "visible": True,
            "actions": True,
            "splash": True,
            "bounded": True,
        }


def test_canonical_forms_do_not_hard_code_platform_fonts():
    form_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src" / "rc_metastudio" / "forms").glob("*.ui")
    )
    for forbidden in ("Verdana", "Courier", "<pointsize>"):
        assert forbidden not in form_text
