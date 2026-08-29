import json
import os
from pathlib import Path
import subprocess
import sys
from typing import cast

import pytest
from PyQt6 import QtCore, QtGui, QtWidgets


ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RCMS_QT6_BUILD_ROOT", str(ROOT / "build" / "qt6-verification"))
from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()
from rc_metastudio import adaptive_window
from test_types import key_click, mouse_click, required


def _page(wizard: QtWidgets.QWizard, page_id: int, page_type):
    """Narrow a registered generated page at the Qt lookup seam."""

    return cast(page_type, required(wizard.page(page_id), "wizard page"))


def _show(wizard, qapp):
    wizard.restart()
    wizard.show()
    qapp.processEvents()
    qapp.processEvents()


def _frame_tuple(window):
    geometry = window.frameGeometry()
    return geometry.x(), geometry.y(), geometry.width(), geometry.height()


def _assert_page_contract(wizard, expected_buttons):

    page = required(wizard.currentPage(), "current wizard page")
    overflow = required(
        page.findChild(QtWidgets.QScrollArea, "pageScrollArea"), "page scroll area"
    )
    assert overflow is not None
    assert overflow.widgetResizable()
    for role in expected_buttons:
        button = wizard.button(role)
        assert button.isVisible(), (page.objectName(), role)
        assert not overflow.isAncestorOf(button)


def _assert_multiline_data_type_labels_fit(page) -> None:
    for button in page._data_type_buttons():
        line_count = max(1, len(button.text().splitlines()))
        margin = max(
            0,
            button.style().pixelMetric(
                QtWidgets.QStyle.PixelMetric.PM_ButtonMargin, None, button
            ),
        )
        frame = max(
            0,
            button.style().pixelMetric(
                QtWidgets.QStyle.PixelMetric.PM_DefaultFrameWidth, None, button
            ),
        )
        required_height = (
            button.iconSize().height()
            + line_count * button.fontMetrics().lineSpacing()
            + 2 * margin
            + 2 * frame
        )
        assert button.height() >= required_height, button.objectName()


def test_main_wizard_is_a_stable_workflow_window(qapp):
    from rc_metastudio import main_wizard

    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        _show(wizard, qapp)
        initial_geometry = _frame_tuple(wizard)

        assert (
            adaptive_window.adaptive_window_state(wizard).policy.archetype
            is adaptive_window.WindowArchetype.WORKFLOW
        )
        assert (
            adaptive_window.adaptive_window_state(wizard).role
            is adaptive_window.WindowRole.WORKFLOW
        )

        welcome_page = _page(wizard, main_wizard.Page_Welcome, main_wizard.WelcomePage)
        for button in (
            welcome_page.create_new_btn,
            welcome_page.import_csv_btn,
            welcome_page.open_recent_btn,
            welcome_page.open_btn,
        ):
            assert button.iconSize() == QtCore.QSize(24, 24)
            assert button.minimumHeight() == 36

        data_type_page = _page(
            wizard, main_wizard.Page_DataType, main_wizard.DataTypePage
        )
        data_type_page.twoarm_proportions_Button.click()
        wizard.next()
        qapp.processEvents()
        assert _frame_tuple(wizard) == initial_geometry

        metric_page = _page(
            wizard, main_wizard.Page_ChooseMetric, main_wizard.ChooseMetricPage
        )
        metric_page.label_2.setText("A very long translated instruction. " * 80)
        larger_font = QtGui.QFont(metric_page.font())
        larger_font.setPointSize(larger_font.pointSize() + 8)
        metric_page.setFont(larger_font)
        metric_page.updateGeometry()
        qapp.processEvents()
        qapp.processEvents()

        assert _frame_tuple(wizard) == initial_geometry
    finally:
        wizard.close()
        qapp.processEvents()


def test_every_wizard_page_declares_a_focus_revealing_overflow_boundary(qapp):
    from rc_metastudio import main_wizard

    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        _show(wizard, qapp)

        for page_id in wizard.pageIds():
            page = required(wizard.page(page_id), "wizard page")
            overflow = required(
                page.findChild(QtWidgets.QScrollArea, "pageScrollArea"),
                "page scroll area",
            )
            assert overflow is not None, page_id
            assert overflow.widgetResizable() is True
            assert overflow.focusPolicy() == QtCore.Qt.FocusPolicy.NoFocus
            assert overflow.widget() is not None

        overflow = required(
            required(wizard.currentPage(), "current wizard page").findChild(
                QtWidgets.QScrollArea, "pageScrollArea"
            ),
            "page scroll area",
        )
        for button_id in (
            main_wizard.QWizard.WizardButton.NextButton,
            main_wizard.QWizard.WizardButton.CancelButton,
        ):
            button = required(wizard.button(button_id), "wizard button")
            assert button.isVisible()
            assert not overflow.isAncestorOf(button)

        wizard.resize(500, 330)
        diagnostic = _page(
            wizard, main_wizard.Page_DataType, main_wizard.DataTypePage
        ).diagnostic_Button
        diagnostic.setFocus()
        qapp.processEvents()
        visible_rect = required(overflow.viewport(), "overflow viewport").rect()
        control_rect = QtCore.QRect(
            diagnostic.mapTo(
                required(overflow.viewport(), "overflow viewport"), QtCore.QPoint()
            ),
            diagnostic.size(),
        )
        assert visible_rect.intersects(control_rect)
    finally:
        wizard.close()
        qapp.processEvents()


@pytest.mark.parametrize("available_size", [(800, 600), (1024, 640)])
@pytest.mark.parametrize("path", [None, "new_dataset", "csv_import"])
def test_workflow_path_matrix_is_bounded_stable_and_scrollable(
    qapp, monkeypatch, available_size, path
):
    from rc_metastudio import adaptive_window
    from rc_metastudio import main_wizard

    available = QtCore.QRect(0, 0, *available_size)
    monkeypatch.setattr(
        adaptive_window, "available_geometry_for_window", lambda _window: available
    )
    original_font = QtGui.QFont(qapp.font())
    enlarged_font = QtGui.QFont(original_font)
    enlarged_font.setPointSize(max(1, original_font.pointSize()) + 8)
    qapp.setFont(enlarged_font)
    wizard = main_wizard.MainWizard(path=path)
    try:
        _show(wizard, qapp)
        initial_geometry = _frame_tuple(wizard)
        assert initial_geometry[2] <= int(available.width() * 0.9)
        assert initial_geometry[3] <= int(available.height() * 0.9)

        if path is None:
            _assert_page_contract(
                wizard, [main_wizard.QWizard.WizardButton.CancelButton]
            )
            _page(
                wizard, main_wizard.Page_Welcome, main_wizard.WelcomePage
            ).create_new_btn.click()
            qapp.processEvents()

        _assert_page_contract(
            wizard,
            [
                main_wizard.QWizard.WizardButton.NextButton,
                main_wizard.QWizard.WizardButton.CancelButton,
            ],
        )
        data_type_page = _page(
            wizard, main_wizard.Page_DataType, main_wizard.DataTypePage
        )
        _assert_multiline_data_type_labels_fit(data_type_page)
        data_type_page.twoarm_proportions_Button.click()
        wizard.next()
        qapp.processEvents()
        _assert_page_contract(
            wizard,
            [
                main_wizard.QWizard.WizardButton.BackButton,
                main_wizard.QWizard.WizardButton.NextButton,
                main_wizard.QWizard.WizardButton.CancelButton,
            ],
        )
        metric_page = _page(
            wizard, main_wizard.Page_ChooseMetric, main_wizard.ChooseMetricPage
        )
        metric_page.label_2.setText("Long translated metric guidance. " * 80)
        wizard.next()
        qapp.processEvents()

        outcome_buttons = [
            main_wizard.QWizard.WizardButton.BackButton,
            main_wizard.QWizard.WizardButton.CancelButton,
            main_wizard.QWizard.WizardButton.NextButton
            if path == "csv_import"
            else main_wizard.QWizard.WizardButton.FinishButton,
        ]
        _assert_page_contract(wizard, outcome_buttons)
        outcome_page = _page(
            wizard, main_wizard.Page_OutcomeName, main_wizard.OutcomeNamePage
        )
        outcome_page.outcome_name_LineEdit.setText("Outcome")
        if path == "csv_import":
            wizard.next()
            qapp.processEvents()
            page = _page(wizard, main_wizard.Page_CsvImport, main_wizard.CsvImportPage)
            page.instructions.setText("Content-rich CSV guidance. " * 100)
            page.preview_table.setRowCount(100)
            page.preview_table.setColumnCount(20)
            page.updateGeometry()
            qapp.processEvents()
            _assert_page_contract(
                wizard,
                [
                    main_wizard.QWizard.WizardButton.BackButton,
                    main_wizard.QWizard.WizardButton.FinishButton,
                    main_wizard.QWizard.WizardButton.CancelButton,
                ],
            )
            assert (
                required(
                    page.pageScrollArea.verticalScrollBar(), "page scrollbar"
                ).maximum()
                > 0
            )

        assert _frame_tuple(wizard) == initial_geometry
    finally:
        wizard.close()
        qapp.setFont(original_font)
        qapp.processEvents()


def test_tab_and_backtab_follow_logical_order_and_reveal_controls(qapp):
    from rc_metastudio import main_wizard

    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        _show(wizard, qapp)
        wizard.resize(500, 330)
        page = _page(wizard, main_wizard.Page_DataType, main_wizard.DataTypePage)
        diagnostic = page.diagnostic_Button
        mouse_click(diagnostic, QtCore.Qt.MouseButton.LeftButton)
        qapp.processEvents()
        assert qapp.focusWidget() is diagnostic

        next_button = wizard.button(main_wizard.QWizard.WizardButton.NextButton)
        cancel_button = wizard.button(main_wizard.QWizard.WizardButton.CancelButton)
        key_click(diagnostic, QtCore.Qt.Key.Key_Tab)
        qapp.processEvents()
        assert qapp.focusWidget() is next_button
        key_click(next_button, QtCore.Qt.Key.Key_Tab)
        qapp.processEvents()
        assert qapp.focusWidget() is cancel_button
        key_click(cancel_button, QtCore.Qt.Key.Key_Backtab)
        qapp.processEvents()
        assert qapp.focusWidget() is next_button
        key_click(next_button, QtCore.Qt.Key.Key_Backtab)
        qapp.processEvents()
        assert qapp.focusWidget() is diagnostic

        overflow = page.pageScrollArea
        diagnostic_rect = QtCore.QRect(
            diagnostic.mapTo(
                required(overflow.viewport(), "overflow viewport"), QtCore.QPoint()
            ),
            diagnostic.size(),
        )
        assert (
            required(overflow.viewport(), "overflow viewport")
            .rect()
            .intersects(diagnostic_rect)
        )
    finally:
        wizard.close()
        qapp.processEvents()


def test_return_activates_visible_default_wizard_action(qapp):
    from rc_metastudio import main_wizard

    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        _show(wizard, qapp)
        choice = _page(
            wizard, main_wizard.Page_DataType, main_wizard.DataTypePage
        ).diagnostic_Button
        mouse_click(choice, QtCore.Qt.MouseButton.LeftButton)
        qapp.processEvents()
        next_button = cast(
            QtWidgets.QPushButton,
            required(
                wizard.button(main_wizard.QWizard.WizardButton.NextButton),
                "next button",
            ),
        )
        assert next_button.isVisible()
        assert next_button.isEnabled()
        assert next_button.isDefault()
        before_page = wizard.currentId()

        assert qapp.focusWidget() is choice
        key_click(choice, QtCore.Qt.Key.Key_Return)
        qapp.processEvents()

        assert wizard.currentId() != before_page
    finally:
        wizard.close()
        qapp.processEvents()


def test_data_type_icons_follow_button_text_color_across_palette_changes(qapp):
    from rc_metastudio import main_wizard
    from rc_metastudio import qt6_resources

    qt6_resources.ensure_application_resources()
    original_palette = qapp.palette()
    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        _show(wizard, qapp)
        page = _page(wizard, main_wizard.Page_DataType, main_wizard.DataTypePage)

        rendered_icons = {}
        for foreground in ("#111111", "#f5f5f5"):
            palette = qapp.palette()
            palette.setColor(
                QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(foreground)
            )
            qapp.setPalette(palette)
            qapp.processEvents()

            for button in page.findChildren(QtWidgets.QAbstractButton):
                image = button.icon().pixmap(button.iconSize()).toImage()
                colors = [
                    image.pixelColor(x, y)
                    for y in range(image.height())
                    for x in range(image.width())
                    if image.pixelColor(x, y).alpha() >= 128
                ]
                assert colors, (foreground, button.objectName(), button.icon().isNull())
                rendered_icons.setdefault(foreground, {})[button.objectName()] = tuple(
                    sorted(color.rgba() for color in colors)
                )

            diagnostic = (
                page.diagnostic_Button.icon()
                .pixmap(page.diagnostic_Button.iconSize())
                .toImage()
            )
            diagnostic_colors = {
                diagnostic.pixelColor(x, y).rgba()
                for y in range(diagnostic.height())
                for x in range(diagnostic.width())
                if diagnostic.pixelColor(x, y).alpha() >= 128
            }
            assert len(diagnostic_colors) >= 3

        assert rendered_icons["#111111"] != rendered_icons["#f5f5f5"]
    finally:
        qapp.setPalette(original_palette)
        wizard.close()
        qapp.processEvents()


def test_diagnostic_data_type_button_matches_standard_choice_geometry(qapp):
    from rc_metastudio import main_wizard

    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        _show(wizard, qapp)
        page = _page(wizard, main_wizard.Page_DataType, main_wizard.DataTypePage)
        required(page.layout(), "data type layout").activate()
        qapp.processEvents()

        standard = page.onearm_proportion_Button
        diagnostic = page.diagnostic_Button
        assert diagnostic.width() == pytest.approx(standard.width(), abs=4)
        assert diagnostic.height() == pytest.approx(standard.height(), abs=2)
    finally:
        wizard.close()
        qapp.processEvents()


def test_hidden_and_closed_wizards_do_not_react_to_other_wizard_focus(qapp):
    from rc_metastudio import main_wizard

    first = main_wizard.MainWizard(path="new_dataset")
    second = main_wizard.MainWizard(path="new_dataset")
    try:
        _show(first, qapp)
        first_page = _page(first, main_wizard.Page_DataType, main_wizard.DataTypePage)
        first_scroll = required(
            first_page.findChild(QtWidgets.QScrollArea, "pageScrollArea"),
            "first page scroll area",
        )
        first_scroll.ensureWidgetVisible(first_page.diagnostic_Button)
        qapp.processEvents()
        first_scroll_value = required(
            first_scroll.verticalScrollBar(), "first scrollbar"
        ).value()
        first.hide()
        qapp.processEvents()

        _show(second, qapp)
        second_page = _page(second, main_wizard.Page_DataType, main_wizard.DataTypePage)
        second_page.onearm_mean_Button.setFocus()
        qapp.processEvents()
        assert (
            required(first_scroll.verticalScrollBar(), "first scrollbar").value()
            == first_scroll_value
        )

        first.close()
        second_page.twoarm_means_Button.setFocus()
        qapp.processEvents()
        assert second_page.twoarm_means_Button.hasFocus()
    finally:
        first.close()
        second.close()
        qapp.processEvents()


def test_csv_preview_overflows_inside_stable_wizard_and_finish_stays_reachable(qapp):
    from rc_metastudio import main_wizard

    wizard = main_wizard.MainWizard(path="csv_import")
    try:
        wizard.setStartId(main_wizard.Page_CsvImport)
        wizard.set_dataset_info(
            {
                "arms": "two",
                "data_type": "binary",
                "sub_type": "proportions",
                "effect": "OR",
                "metric_choices": ["OR"],
                "name": None,
            }
        )
        _show(wizard, qapp)
        wizard.resize(560, 400)
        qapp.processEvents()
        initial_geometry = _frame_tuple(wizard)
        page = _page(wizard, main_wizard.Page_CsvImport, main_wizard.CsvImportPage)
        page.instructions.setText("Long CSV guidance. " * 120)
        page.preview_table.setRowCount(100)
        page.preview_table.setColumnCount(20)
        page.updateGeometry()
        qapp.processEvents()
        qapp.processEvents()

        overflow = required(
            page.findChild(QtWidgets.QScrollArea, "pageScrollArea"), "page scroll area"
        )
        finish = required(
            wizard.button(main_wizard.QWizard.WizardButton.FinishButton),
            "finish button",
        )
        cancel = required(
            wizard.button(main_wizard.QWizard.WizardButton.CancelButton),
            "cancel button",
        )
        assert _frame_tuple(wizard) == initial_geometry
        assert required(overflow.verticalScrollBar(), "page scrollbar").maximum() > 0
        assert finish.isVisible()
        assert cancel.isVisible()
        assert not overflow.isAncestorOf(finish)
        assert not overflow.isAncestorOf(cancel)
    finally:
        wizard.close()
        qapp.processEvents()


def test_workflow_layout_survives_process_level_scale_factors():
    root = Path(__file__).resolve().parents[3]
    script = r"""
import json
from PyQt6 import QtCore, QtWidgets
from rc_metastudio.qt6_ui import prepare_generated_ui_imports
prepare_generated_ui_imports()
from rc_metastudio import app_error_handler
from rc_metastudio import adaptive_window
from rc_metastudio import main_wizard

app = app_error_handler.get_or_create_application([])
wizard = main_wizard.MainWizard(path="new_dataset")
try:
    wizard.restart()
    wizard.show()
    app.processEvents()
    page = wizard.currentPage()
    overflow = page.findChild(QtWidgets.QScrollArea, "pageScrollArea")
    buttons = [wizard.button(role) for role in (
        main_wizard.QWizard.WizardButton.NextButton,
        main_wizard.QWizard.WizardButton.CancelButton,
    )]
    print("WORKFLOW_LAYOUT=" + json.dumps({
        "archetype": adaptive_window.adaptive_window_state(wizard).policy.archetype.value,
        "overflow": overflow is not None,
        "buttons": all(button.isVisible() for button in buttons),
        "bounded": wizard.frameGeometry().width() <= app.primaryScreen().availableGeometry().width()
            and wizard.frameGeometry().height() <= app.primaryScreen().availableGeometry().height(),
    }), flush=True)
finally:
    wizard.close()
    wizard.deleteLater()
    QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()
    app.quit()
    app.processEvents()
"""
    for scale_factor in ("1", "1.5"):
        environment = os.environ.copy()
        environment["QT_QPA_PLATFORM"] = "offscreen"
        environment["QT_SCALE_FACTOR"] = scale_factor
        environment["PYTHONPATH"] = os.pathsep.join(
            [
                str(root / "src"),
                str(
                    root / "build" / "qt6-verification" / "generated"
                ),
            ]
        )
        environment["RCMS_QT6_BUILD_ROOT"] = str(root / "build" / "qt6-verification")
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        marker = next(
            line
            for line in completed.stdout.splitlines()
            if line.startswith("WORKFLOW_LAYOUT=")
        )
        assert json.loads(marker.split("=", 1)[1]) == {
            "archetype": "workflow",
            "overflow": True,
            "buttons": True,
            "bounded": True,
        }
