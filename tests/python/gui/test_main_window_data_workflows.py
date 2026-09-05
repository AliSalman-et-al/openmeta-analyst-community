import os
import sys
import math
import copy
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath("src"))

import pytest
from rc_metastudio import automation, calculator_service
from PyQt6.QtWidgets import QDialog
from test_types import key_click, required


REPO_ROOT = os.getcwd()


def _derived_effect_and_ci(analysis_unit, metric, group_comparison):
    value = analysis_unit.get_effect_for_source(
        "derived_preview", metric, group_comparison
    )
    return value.estimate, value.lower, value.upper


def test_data_table_return_moves_vertically_from_selected_cells():
    from PyQt6 import QtCore

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)
        assert window.model.dataset is window.workspace.runtime.dataset
        table = window.tableView
        model = window.model

        table.setCurrentIndex(model.index(0, model.NAME))
        key_click(table, QtCore.Qt.Key.Key_Return)
        assert table.currentIndex() == model.index(1, model.NAME)

        key_click(table, QtCore.Qt.Key.Key_Enter)
        assert table.currentIndex() == model.index(2, model.NAME)

        key_click(
            table, QtCore.Qt.Key.Key_Return, QtCore.Qt.KeyboardModifier.ShiftModifier
        )
        assert table.currentIndex() == model.index(1, model.NAME)
    finally:
        _close_without_prompt(app, window)


def test_data_table_return_commits_editor_and_moves_down_same_column():
    from PyQt6 import QtCore, QtWidgets

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)
        table = window.tableView
        model = window.model

        table.setCurrentIndex(model.index(0, model.NAME))
        table.edit(model.index(0, model.NAME))
        app.processEvents()
        editor = table.findChild(QtWidgets.QLineEdit)
        assert editor is not None

        editor.setText("Alpha")
        key_click(editor, QtCore.Qt.Key.Key_Return)
        app.processEvents()

        assert _cell_text(model, 0, model.NAME) == "Alpha"
        assert table.currentIndex() == model.index(1, model.NAME)
    finally:
        _close_without_prompt(app, window)


def test_data_table_ctrl_a_selects_all_cells_without_running_analysis(monkeypatch):
    from PyQt6 import QtCore

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)
        table = window.tableView
        model = window.model
        analysis_calls = []

        monkeypatch.setattr(
            window, "analysis", lambda *args, **kwargs: analysis_calls.append(args)
        )
        table.setFocus()
        table.setCurrentIndex(model.index(0, model.NAME))

        key_click(
            table, QtCore.Qt.Key.Key_A, QtCore.Qt.KeyboardModifier.ControlModifier
        )
        app.processEvents()

        assert analysis_calls == []
        assert len(table.selectionModel().selectedIndexes()) == (
            model.rowCount() * model.columnCount()
        )
    finally:
        _close_without_prompt(app, window)


def test_data_table_delete_and_backspace_clear_selected_cells(monkeypatch):
    from PyQt6 import QtCore

    from rc_metastudio import dataset_table_model

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)
        model = window.model
        table = window.tableView
        table.set_data_in_model(model.index(0, model.NAME), _variant("Alpha"))

        monkeypatch.setattr(
            window.model.editing_service.bridge,
            "binary_convert_scale",
            lambda value, *args, **kwargs: value,
        )
        monkeypatch.setattr(
            window.model.editing_service.bridge,
            "effect_for_study",
            lambda *args, **kwargs: {"calc_scale": (0.5, 0.25, 1.0)},
        )

        table.paste_contents(
            model.index(0, model.RAW_DATA[0]), [["41", "50", "3", "48"]]
        )
        model = window.model
        assert _cell_text(model, 0, model.RAW_DATA[0]) == "41.0"
        assert all(_cell_text(model, 0, col) != "" for col in model.OUTCOMES)

        table.setFocus()
        table.setCurrentIndex(model.index(0, model.RAW_DATA[0]))
        key_click(table, QtCore.Qt.Key.Key_Delete)
        app.processEvents()

        assert _cell_text(model, 0, model.RAW_DATA[0]) == ""
        assert all(_cell_text(model, 0, col) == "" for col in model.OUTCOMES)

        table.set_data_in_model(model.index(0, model.RAW_DATA[0]), _variant("41"))
        assert _cell_text(model, 0, model.RAW_DATA[0]) == "41.0"

        table.setCurrentIndex(model.index(0, model.RAW_DATA[0]))
        key_click(table, QtCore.Qt.Key.Key_Backspace)
        app.processEvents()

        assert _cell_text(model, 0, model.RAW_DATA[0]) == ""
        assert all(_cell_text(model, 0, col) == "" for col in model.OUTCOMES)
    finally:
        _close_without_prompt(app, window)


def test_main_window_creates_binary_continuous_and_diagnostic_datasets():

    cases = [
        ("binary", "proportions", "OR", "Mortality", "binary"),
        ("continuous", "means", "SMD", "Recovery", "continuous"),
        ("diagnostic", None, "Sens", "Accuracy", "diagnostic"),
    ]

    for data_type, sub_type, effect, name, expected_type in cases:
        app, window = automation.start_automation()
        try:
            outcome_info = {
                "arms": "two",
                "data_type": data_type,
                "sub_type": sub_type,
                "effect": effect,
                "metric_choices": [],
                "name": name,
            }

            window._handle_wizard_results(
                {
                    "path": "new_dataset",
                    "outcome_info": outcome_info,
                    "csv_data": None,
                    "selected_dataset": None,
                }
            )

            assert window.model.get_current_outcome_type() == expected_type
            assert window.model.current_outcome_name == name
            assert window.tableView.model() is window.model
            assert window.model.rowCount() > 0
            if data_type != "diagnostic":
                assert window.model.current_effect == effect
        finally:
            _close_without_prompt(app, window)


@pytest.mark.parametrize("count", ["7.0", "7,0"])
def test_binary_calculator_accept_cancel_and_project_round_trip(
    monkeypatch, tmp_path, count
):
    from PyQt6 import QtCore, QtWidgets

    from rc_metastudio import binary_data_dialog
    from rc_metastudio import dataset_table_model

    app, window = automation.start_automation()
    try:
        warnings = []
        monkeypatch.setattr(
            binary_data_dialog.QMessageBox,
            "warning",
            lambda *args: warnings.append(args),
        )
        monkeypatch.setattr(
            calculator_service.r_bridge,
            "get_confidence_multiplier_from_r",
            lambda confidence: 1.96,
        )
        monkeypatch.setattr(
            calculator_service.r_bridge,
            "effect_for_study",
            lambda *args, **kwargs: {"calc_scale": (1.2, 0.8, 1.8)},
        )
        monkeypatch.setattr(
            window.model.editing_service.bridge,
            "effect_for_study",
            lambda *args, **kwargs: {"calc_scale": (1.2, 0.8, 1.8)},
        )
        monkeypatch.setattr(
            calculator_service.r_bridge,
            "binary_convert_scale",
            lambda value, *args, **kwargs: value,
        )
        monkeypatch.setattr(
            window.model.editing_service.bridge,
            "binary_convert_scale",
            lambda value, *args, **kwargs: value,
        )
        monkeypatch.setattr(
            calculator_service.r_bridge,
            "impute_binary_data",
            lambda data: {"FAIL": True},
        )
        monkeypatch.setattr(
            calculator_service.r_bridge,
            "effect_triplet",
            lambda result, scale, metric=None: result[scale],
        )
        monkeypatch.setattr(
            window.model.editing_service.bridge,
            "effect_triplet",
            lambda result, scale, metric=None: result[scale],
        )
        _create_binary_dataset(window)
        model = window.model
        table = window.tableView
        table.set_data_in_model(model.index(0, model.NAME), _variant("Alpha"))
        for offset, value in enumerate(("6", "21", "9", "18")):
            table.set_data_in_model(model.index(0, model.RAW_DATA[offset]), value)

        opened_dialogs = []
        callback_errors = []

        def accept_edit():
            dialog = cast(
                binary_data_dialog.BinaryDataDialog,
                required(
                    QtWidgets.QApplication.activeModalWidget(), "binary edit dialog"
                ),
            )
            opened_dialogs.append(dialog)
            try:
                dialog.raw_data_table.setCurrentCell(0, 0)
                required(dialog.raw_data_table.item(0, 0), "raw data item").setText(
                    count
                )
                dialog.accept()
            except Exception as error:
                callback_errors.append(error)
                if isinstance(dialog, QtWidgets.QDialog):
                    dialog.reject()

        QtCore.QTimer.singleShot(0, accept_edit)
        table.row_header_clicked(0)
        assert callback_errors == []
        assert warnings == []
        assert isinstance(opened_dialogs[-1], binary_data_dialog.BinaryDataDialog)
        committed = model.get_current_analysis_unit_for_study(0)
        assert committed.get_raw_data_for_group(model.current_groups[0]) == [7, 22]

        def reject_edit():
            dialog = cast(
                binary_data_dialog.BinaryDataDialog,
                required(
                    QtWidgets.QApplication.activeModalWidget(), "binary edit dialog"
                ),
            )
            opened_dialogs.append(dialog)
            try:
                dialog.raw_data_table.setCurrentCell(0, 0)
                required(dialog.raw_data_table.item(0, 0), "raw data item").setText("8")
                dialog.reject()
            except Exception as error:
                callback_errors.append(error)
                if isinstance(dialog, QtWidgets.QDialog):
                    dialog.reject()

        QtCore.QTimer.singleShot(0, reject_edit)
        table.row_header_clicked(0)
        assert callback_errors == []
        unchanged = model.get_current_analysis_unit_for_study(0)
        assert unchanged.get_raw_data_for_group(model.current_groups[0]) == [7, 22]

        saved_path = str(
            tmp_path / ("binary-" + count.replace(",", "c") + "-round-trip.rcms")
        )
        main_window = sys.modules["rc_metastudio.main_window"]
        monkeypatch.setattr(
            main_window.QFileDialog,
            "getSaveFileName",
            lambda **kwargs: (saved_path, ""),
        )
        assert window.save_as() is True
        assert window.open(file_path=saved_path) is True
        reopened = window.model.get_current_analysis_unit_for_study(0)
        assert reopened.get_raw_data_for_group(window.model.current_groups[0]) == [
            7,
            22,
        ]
    finally:
        _close_without_prompt(app, window)


@pytest.mark.parametrize("decimal", ["95.5", "95,5"])
def test_continuous_calculator_workspace_transaction_and_locale_round_trip(
    monkeypatch, tmp_path, decimal
):
    from PyQt6 import QtCore, QtWidgets

    from rc_metastudio import continuous_data_dialog
    from rc_metastudio import dataset_table_model

    app, window = automation.start_automation()
    r_payloads = []
    warnings = []
    try:
        monkeypatch.setattr(
            continuous_data_dialog.QMessageBox,
            "warning",
            lambda *args: warnings.append(args[2]),
        )
        monkeypatch.setattr(
            calculator_service.r_bridge,
            "get_confidence_multiplier_from_r",
            lambda _level: 1.96,
        )
        monkeypatch.setattr(
            calculator_service.r_bridge,
            "continuous_convert_scale",
            lambda value, *args, **kwargs: value,
        )
        monkeypatch.setattr(
            window.model.editing_service.bridge,
            "continuous_convert_scale",
            lambda value, *args, **kwargs: value,
        )

        def impute(payload, alpha):
            r_payloads.append(dict(payload))
            return {"succeeded": False, "comment": "complete input"}

        monkeypatch.setattr(
            calculator_service.r_bridge, "impute_continuous_data", impute
        )
        monkeypatch.setattr(
            calculator_service.r_bridge,
            "continuous_effect_for_study",
            lambda *args, **kwargs: {"calc_scale": (1.5, 1.0, 2.0)},
        )
        monkeypatch.setattr(
            window.model.editing_service.bridge,
            "continuous_effect_for_study",
            lambda *args, **kwargs: {"calc_scale": (1.5, 1.0, 2.0)},
        )
        monkeypatch.setattr(
            calculator_service.r_bridge,
            "effect_triplet",
            lambda result, scale, metric=None: result[scale],
        )
        monkeypatch.setattr(
            window.model.editing_service.bridge,
            "effect_triplet",
            lambda result, scale, metric=None: result[scale],
        )
        monkeypatch.setattr(
            calculator_service.r_bridge,
            "back_calculate_continuous_data",
            lambda *args, **kwargs: {"FAIL": True},
        )
        _create_continuous_dataset(window)
        model = window.model
        table = window.tableView
        unit = model.get_current_analysis_unit_for_study(0)
        unit.get_raw_data_for_group(model.current_groups[0])[:] = [10, 94, 2]
        unit.get_raw_data_for_group(model.current_groups[1])[:] = [12, 90, 3]
        window.data_dirtied()
        window.workspace.mark_saved()

        callback_errors = []

        def accept_edit():
            dialog = cast(
                continuous_data_dialog.ContinuousDataDialog,
                required(
                    QtWidgets.QApplication.activeModalWidget(), "continuous edit dialog"
                ),
            )
            try:
                dialog.simple_table.setCurrentCell(0, 1)
                required(
                    dialog.simple_table.item(0, 1), "continuous data item"
                ).setText(decimal)
                dialog.accept()
            except Exception as error:
                callback_errors.append(error)
                dialog.reject()

        QtCore.QTimer.singleShot(0, accept_edit)
        table.row_header_clicked(0)
        assert callback_errors == []
        assert warnings == []
        committed = model.get_current_analysis_unit_for_study(0)
        assert committed.get_raw_data_for_group(model.current_groups[0]) == [
            10.0,
            95.5,
            2.0,
        ]
        assert any(payload.get("mean") == 95.5 for payload in r_payloads)
        assert window.workspace.can_undo
        assert window.workspace.is_dirty

        window.undo()
        model = window.model
        assert model.get_current_analysis_unit_for_study(0).get_raw_data_for_group(
            model.current_groups[0]
        ) == [10, 94, 2]
        assert not window.workspace.is_dirty
        window.redo()
        model = window.model
        assert window.workspace.is_dirty

        undo_count = window.workspace.can_undo
        before_invalid = copy.deepcopy(model.get_current_analysis_unit_for_study(0))

        def reject_invalid_edit():
            dialog = cast(
                continuous_data_dialog.ContinuousDataDialog,
                required(
                    QtWidgets.QApplication.activeModalWidget(),
                    "continuous edit dialog",
                ),
            )
            dialog.simple_table.setCurrentCell(0, 0)
            required(dialog.simple_table.item(0, 0), "continuous data cell").setText(
                "10,5"
            )
            dialog.reject()

        QtCore.QTimer.singleShot(0, reject_invalid_edit)
        table.row_header_clicked(0)
        assert warnings[-1] == "N must be a non-negative whole number."
        assert window.workspace.can_undo == undo_count
        assert model.get_current_analysis_unit_for_study(0).get_raw_data_for_groups(
            model.current_groups
        ) == before_invalid.get_raw_data_for_groups(model.current_groups)

        saved_path = str(
            tmp_path / ("continuous-" + decimal.replace(",", "c") + ".rcms")
        )
        main_window = sys.modules["rc_metastudio.main_window"]
        monkeypatch.setattr(
            main_window.QFileDialog,
            "getSaveFileName",
            lambda **kwargs: (saved_path, ""),
        )
        assert window.save_as() is True
        assert window.open(file_path=saved_path) is True
        reopened = window.model.get_current_analysis_unit_for_study(0)
        assert reopened.get_raw_data_for_group(window.model.current_groups[0]) == [
            10.0,
            95.5,
            2.0,
        ]
    finally:
        _close_without_prompt(app, window)


@pytest.mark.parametrize("count", ["13.0", "13,0"])
def test_diagnostic_calculator_workspace_transaction_and_locale_round_trip(
    monkeypatch, tmp_path, count
):
    from PyQt6 import QtCore, QtWidgets

    from rc_metastudio import diagnostic_data_dialog
    from rc_metastudio import dataset_table_model

    app, window = automation.start_automation()
    r_payloads = []
    warnings = []
    try:
        monkeypatch.setattr(
            diagnostic_data_dialog.QMessageBox,
            "warning",
            lambda *args: warnings.append(args[2]),
        )
        monkeypatch.setattr(
            calculator_service.r_bridge,
            "get_confidence_multiplier_from_r",
            lambda _level: 1.96,
        )
        monkeypatch.setattr(
            calculator_service.r_bridge,
            "diagnostic_convert_scale",
            lambda value, *args, **kwargs: value,
        )
        monkeypatch.setattr(
            window.model.editing_service.bridge,
            "diagnostic_convert_scale",
            lambda value, *args, **kwargs: value,
        )

        def impute(payload):
            r_payloads.append(dict(payload))
            return {"TP": None, "FP": None, "FN": None, "TN": None}

        monkeypatch.setattr(
            calculator_service.r_bridge, "impute_diagnostic_data", impute
        )
        monkeypatch.setattr(
            calculator_service.r_bridge,
            "diagnostic_effects_for_study",
            lambda *args, metrics, **kwargs: {
                metric: {"calc_scale": (0.8, 0.7, 0.9)} for metric in metrics
            },
        )
        monkeypatch.setattr(
            window.model.editing_service.bridge,
            "diagnostic_effects_for_study",
            lambda *args, metrics, **kwargs: {
                metric: {"calc_scale": (0.8, 0.7, 0.9)} for metric in metrics
            },
        )
        monkeypatch.setattr(
            calculator_service.r_bridge,
            "effect_triplet",
            lambda result, scale, metric=None: result[scale],
        )
        monkeypatch.setattr(
            window.model.editing_service.bridge,
            "effect_triplet",
            lambda result, scale, metric=None: result[scale],
        )
        _create_diagnostic_dataset(window)
        model = window.model
        table = window.tableView
        unit = model.get_current_analysis_unit_for_study(0)
        unit.get_raw_data_for_group(model.current_groups[0])[:] = [12, 3, 4, 21]
        window.data_dirtied()
        window.workspace.mark_saved()

        def accept_edit():
            dialog = cast(
                diagnostic_data_dialog.DiagnosticDataDialog,
                required(
                    QtWidgets.QApplication.activeModalWidget(), "diagnostic edit dialog"
                ),
            )
            dialog.two_by_two_table.setCurrentCell(0, 0)
            required(
                dialog.two_by_two_table.item(0, 0), "diagnostic data item"
            ).setText(count)
            dialog.accept()

        QtCore.QTimer.singleShot(0, accept_edit)
        table.row_header_clicked(0)
        committed = model.get_current_analysis_unit_for_study(0)
        assert committed.get_raw_data_for_group(model.current_groups[0]) == [
            13.0,
            3.0,
            4.0,
            21.0,
        ]
        assert any(payload.get("TP") == 13 for payload in r_payloads)
        assert window.workspace.can_undo
        assert window.workspace.is_dirty

        window.undo()
        model = window.model
        assert model.get_current_analysis_unit_for_study(0).get_raw_data_for_group(
            model.current_groups[0]
        ) == [12, 3, 4, 21]
        assert not window.workspace.is_dirty
        window.redo()
        model = window.model

        undo_count = window.workspace.can_undo

        def reject_invalid_edit():
            dialog = cast(
                diagnostic_data_dialog.DiagnosticDataDialog,
                required(
                    QtWidgets.QApplication.activeModalWidget(),
                    "diagnostic edit dialog",
                ),
            )
            dialog.two_by_two_table.setCurrentCell(0, 0)
            required(
                dialog.two_by_two_table.item(0, 0), "diagnostic data cell"
            ).setText("13,5")
            dialog.reject()

        QtCore.QTimer.singleShot(0, reject_invalid_edit)
        table.row_header_clicked(0)
        assert "whole number" in warnings[-1]
        assert window.workspace.can_undo == undo_count
        assert model.get_current_analysis_unit_for_study(0).get_raw_data_for_group(
            model.current_groups[0]
        ) == [13.0, 3.0, 4.0, 21.0]

        saved_path = str(tmp_path / ("diagnostic-" + count.replace(",", "c") + ".rcms"))
        main_window = sys.modules["rc_metastudio.main_window"]
        monkeypatch.setattr(
            main_window.QFileDialog,
            "getSaveFileName",
            lambda **kwargs: (saved_path, ""),
        )
        assert window.save_as() is True
        assert window.open(file_path=saved_path) is True
        reopened = window.model.get_current_analysis_unit_for_study(0)
        assert reopened.get_raw_data_for_group(window.model.current_groups[0]) == [
            13.0,
            3.0,
            4.0,
            21.0,
        ]
    finally:
        _close_without_prompt(app, window)


@pytest.mark.parametrize(
    ("show_method", "state_method"),
    [
        ("showMaximized", "isMaximized"),
        ("showFullScreen", "isFullScreen"),
    ],
)
def test_new_dataset_preserves_main_window_state(show_method, state_method):

    app, window = automation.start_automation()
    try:
        getattr(window, show_method)()
        app.processEvents()

        _create_binary_dataset(window)
        app.processEvents()

        assert getattr(window, state_method)()
        assert window.tableView.model() is window.model
        assert window.model.current_outcome_name == "Mortality"
    finally:
        _close_without_prompt(app, window)


def test_data_table_editing_preserves_maximized_main_window_state():

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)
        window.showMaximized()
        app.processEvents()

        model = window.model
        window.tableView.set_data_in_model(
            model.index(0, model.NAME), _variant("Alpha")
        )
        app.processEvents()

        assert window.isMaximized()
        assert _cell_text(window.model, 0, window.model.NAME) == "Alpha"
    finally:
        _close_without_prompt(app, window)


def test_dataset_model_rejects_missing_or_unknown_outcome_data_type():

    app, window = automation.start_automation()
    try:
        with pytest.raises(ValueError, match="without a data type"):
            window.model.add_new_outcome("Missing type", None)

        with pytest.raises(ValueError, match="Unsupported outcome data type"):
            window.model.add_new_outcome("Unknown type", "not-a-data-type")
    finally:
        _close_without_prompt(app, window)


def test_dataset_model_rejects_blank_and_duplicate_outcome_names():

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)

        with pytest.raises(ValueError, match="Outcome names cannot be empty"):
            window.model.add_new_outcome("   ", "binary")

        with pytest.raises(ValueError, match="already exists"):
            window.model.add_new_outcome("Mortality", "binary")
    finally:
        _close_without_prompt(app, window)


def test_dataset_model_rejects_invalid_added_entity_names():

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)

        for method, args, message in [
            (window.model.add_new_group, ("   ",), "Group names cannot be empty"),
            (
                window.model.add_follow_up_to_current_outcome,
                ("   ",),
                "Follow-up names cannot be empty",
            ),
            (
                window.model.add_covariate,
                ("   ", "continuous"),
                "Covariate names cannot be empty",
            ),
        ]:
            with pytest.raises(ValueError, match=message):
                method(*args)

        with pytest.raises(ValueError, match="already exists"):
            window.model.add_new_group(window.model.get_current_groups()[0])

        with pytest.raises(ValueError, match="already exists"):
            window.model.add_follow_up_to_current_outcome(
                window.model.get_current_follow_up_name()
            )

        window.model.add_covariate("Dose", "continuous")
        with pytest.raises(ValueError, match="already exists"):
            window.model.add_covariate("Dose", "continuous")
    finally:
        _close_without_prompt(app, window)


def test_data_table_editing_preserves_project_state_and_round_trips(
    tmp_path, monkeypatch
):

    app, window = automation.start_automation()
    saved_path = str(tmp_path / "edited.rcms")
    try:
        _create_binary_dataset(window)

        model = window.model
        table = window.tableView
        table.set_data_in_model(model.index(0, model.NAME), _variant("Alpha"))
        table.set_data_in_model(model.index(0, model.YEAR), _variant("2020"))
        for offset, value in enumerate(["1", "10", "2", "12"]):
            table.set_data_in_model(
                model.index(0, model.RAW_DATA[offset]), _variant(value)
            )

        model.add_new_group("Tx C")
        model.add_new_outcome("Readmission", "binary", "proportions")
        model.add_follow_up_to_current_outcome("week 4")
        model.add_covariate("Dose", "continuous", {"Alpha": 5.5})
        model.set_current_groups(["tx B", "Tx C"])
        model.set_confidence_level(90.0)

        main_window = sys.modules["rc_metastudio.main_window"]
        critical_messages = []
        monkeypatch.setattr(
            main_window.QFileDialog,
            "getSaveFileName",
            lambda **kwargs: (saved_path, ""),
        )
        monkeypatch.setattr(
            main_window.QMessageBox,
            "critical",
            lambda *args, **kwargs: critical_messages.append(args),
        )
        assert window.save_as() is True
        assert critical_messages == []
        assert window.model.dataset is window.workspace.runtime.dataset

        # Exercise the real project install boundary so both the normalized
        # dataset and project-scoped workspace selection are covered.
        assert window.open(file_path=saved_path) is True
        reopened = window.model.dataset
        assert reopened is window.workspace.runtime.dataset

        assert [
            (str(study.name), str(study.year)) for study in reopened.studies[:1]
        ] == [("Alpha", "2020")]
        assert "Readmission" in reopened.get_outcome_names()
        assert "week 4" in reopened.follow_ups_by_outcome["Mortality"].values()
        assert "Tx C" in reopened.get_group_names()
        assert [(cov.name, cov.data_type) for cov in reopened.covariates] == [
            ("Dose", 1)
        ]
        assert reopened.studies[0].covariate_values["Dose"] == 5.5
        assert window.model.current_outcome_name == "Mortality"
        assert window.model.get_current_follow_up_name() == "first"
        assert window.model.current_groups == ["tx B", "Tx C"]
        assert window.model.current_effect == "OR"
        assert window.model.get_confidence_level() == 90.0
        assert not window.workspace.is_dirty
        assert not window.workspace.is_dirty
    finally:
        _close_without_prompt(app, window)


def test_copy_paste_undo_and_redo_work_through_real_table_path(tmp_path):

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)
        model = window.model
        table = window.tableView
        assert model.dataset is window.workspace.runtime.dataset

        table.paste_contents(
            model.index(0, model.NAME), [["Alpha", "2020", "1", "10", "2", "12"]]
        )
        model = window.model
        copied = table.copy_contents_in_range(
            model.index(0, model.RAW_DATA[0]),
            model.index(0, model.RAW_DATA[-1]),
            to_clipboard=True,
        )

        assert copied == "1.0\t10.0\t2.0\t12.0"

        table.set_data_in_model(model.index(1, model.NAME), _variant("Beta"))
        paste_origin = model.index(1, model.RAW_DATA[0])
        table.selectRow(1)
        # selectRow() may move the current index to the row's first column on
        # the native Windows Qt backend. Set the explicit paste origin after
        # selecting so the edit/undo focus contract is deterministic.
        table.setCurrentIndex(paste_origin)
        window.workspace.mark_saved()
        table.paste_from_clipboard(paste_origin)
        model = window.model
        assert _cell_text(model, 1, model.NAME) == "Beta"
        assert _cell_text(model, 1, model.RAW_DATA[-1]) == "12.0"
        assert window.workspace.is_dirty
        assert (table.currentIndex().row(), table.currentIndex().column()) == (
            paste_origin.row(),
            paste_origin.column(),
        )

        window.undo()
        assert window.model.dataset is window.workspace.runtime.dataset
        assert _cell_text(window.model, 1, window.model.NAME) == "Beta"
        assert _cell_text(window.model, 1, window.model.RAW_DATA[-1]) == ""
        assert not window.workspace.is_dirty
        assert (table.currentIndex().row(), table.currentIndex().column()) == (
            1,
            window.model.RAW_DATA[0],
        )

        window.redo()
        assert window.model.dataset is window.workspace.runtime.dataset
        assert _cell_text(window.model, 1, window.model.NAME) == "Beta"
        assert _cell_text(window.model, 1, window.model.RAW_DATA[-1]) == "12.0"
        assert window.workspace.is_dirty
        assert (table.currentIndex().row(), table.currentIndex().column()) == (
            1,
            window.model.RAW_DATA[0],
        )

        window.out_path = str(tmp_path / "workspace-edits.rcms")
        assert window.save() is True
        assert window.model.dataset is window.workspace.runtime.dataset
        assert not window.workspace.is_dirty

        window.undo()
        assert window.workspace.is_dirty
    finally:
        _close_without_prompt(app, window)


def test_clipboard_preserves_platform_newlines_unicode_blanks_and_comma_decimals():
    from PyQt6.QtWidgets import QApplication

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)
        model = window.model
        table = window.tableView
        required(QApplication.clipboard(), "clipboard").setText(
            "Étude Ω\t2020\t1\t10\t\t12\r\nBeta\t2021\t2\t20\t3\t30\r\n"
        )

        table.paste_from_clipboard(model.index(0, model.NAME))

        assert _cell_text(model, 0, model.NAME) == "Étude Ω"
        assert _cell_text(model, 1, model.NAME) == "Beta"
        assert _cell_text(model, 0, model.RAW_DATA[2]) == ""
        assert _cell_text(model, 1, model.RAW_DATA[-1]) == "30.0"

        model.add_covariate("Dose", "continuous", {"Étude Ω": None, "Beta": None})
        table.synchronize_column_widths()
        comma_decimal = model.index(0, model.columnCount() - 1)
        required(QApplication.clipboard(), "clipboard").setText("1,25\r\n")
        table.paste_from_clipboard(comma_decimal)

        assert model.dataset.studies[0].covariate_values["Dose"] == 1.25
    finally:
        _close_without_prompt(app, window)


def test_invalid_clipboard_paste_is_rejected_before_mutation_or_undo(monkeypatch):
    from PyQt6.QtWidgets import QApplication

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)
        model = window.model
        table = window.tableView
        table.set_data_in_model(model.index(0, model.NAME), _variant("Alpha"))
        window.workspace.mark_saved()
        warnings = []
        monkeypatch.setattr(
            sys.modules["rc_metastudio.main_window"].QMessageBox,
            "warning",
            lambda *args, **kwargs: warnings.append(args),
        )
        required(QApplication.clipboard(), "clipboard").setText("1\tnot numeric")

        assert table.paste_from_clipboard(model.index(0, model.RAW_DATA[0])) is False

        assert [_cell_text(model, 0, column) for column in model.RAW_DATA] == [
            "",
            "",
            "",
            "",
        ]
        assert not window.workspace.is_dirty
        assert not window.workspace.is_dirty
        assert warnings[-1][1:] == ("Warning", "Raw data needs to be numeric.")
    finally:
        _close_without_prompt(app, window)


def test_inclusion_edit_undo_redo_restores_semantics_selection_and_dirty_state():
    from PyQt6.QtCore import Qt

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)
        model = window.model
        table = window.tableView
        table.paste_contents(
            model.index(0, model.NAME), [["Alpha", "2020", "1", "10", "2", "12"]]
        )
        inclusion = model.index(0, model.INCLUDE_STUDY)
        model.dataset.studies[0].include = False
        model.dataset.studies[0].manually_excluded = False
        window.data_dirtied()
        table.setCurrentIndex(inclusion)
        table.selectRow(0)
        window.workspace.mark_saved()

        assert (
            model.setData(
                inclusion, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole
            )
            is True
        )
        assert model.dataset.studies[0].include is True
        assert model.dataset.studies[0].manually_excluded is False
        assert window.workspace.can_undo
        assert window.workspace.is_dirty

        window.undo()
        assert window.model.dataset.studies[0].include is False
        assert window.model.dataset.studies[0].manually_excluded is False
        assert not window.workspace.is_dirty
        assert table.currentIndex() == window.model.index(0, window.model.INCLUDE_STUDY)

        window.redo()
        assert window.model.dataset.studies[0].include is True
        assert window.model.dataset.studies[0].manually_excluded is False
        assert window.workspace.is_dirty
        assert table.currentIndex() == window.model.index(0, window.model.INCLUDE_STUDY)
    finally:
        _close_without_prompt(app, window)


def test_toolbar_copy_without_a_selection_is_a_no_op(monkeypatch):
    from rc_metastudio import app_error_handler

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)
        table = window.tableView
        table.clearSelection()
        assert table.selectionModel().selectedIndexes() == []

        errors = []
        monkeypatch.setattr(
            app_error_handler,
            "handle_exception",
            lambda exc_type, exc_value, exc_traceback, parent=None: errors.append(
                exc_value
            ),
        )

        window.action_copy.trigger()
        app.processEvents()

        assert errors == []
    finally:
        _close_without_prompt(app, window)


def test_diagnostic_complete_paste_recomputes_sens_spec_confidence_intervals(
    monkeypatch,
):
    from rc_metastudio import dataset_table_model

    app, window = automation.start_automation()
    try:
        _create_diagnostic_dataset(window)
        model = window.model
        table = window.tableView
        table.set_data_in_model(model.index(0, model.NAME), _variant("Kinderman"))

        monkeypatch.setattr(
            window.model.editing_service.bridge,
            "diagnostic_convert_scale",
            lambda value, *args, **kwargs: value,
        )

        def diagnostic_effects_for_study(tp, fn, fp, tn, **kwargs):
            assert (tp, fn, fp, tn) == (30.0, 10.0, 1.0, 81.0)
            return {
                "Sens": {"calc_scale": (0.750, 0.588, 0.873)},
                "Spec": {"calc_scale": (0.988, 0.919, 0.998)},
                "PLR": {"calc_scale": (61.5, 8.8, 431.0)},
                "NLR": {"calc_scale": (0.253, 0.148, 0.431)},
                "DOR": {"calc_scale": (243.0, 28.0, 2111.0)},
            }

        monkeypatch.setattr(
            window.model.editing_service.bridge,
            "diagnostic_effects_for_study",
            diagnostic_effects_for_study,
        )

        table.paste_contents(
            model.index(0, model.RAW_DATA[0]), [["30", "10", "1", "81"]]
        )

        analysis_unit = model.get_current_analysis_unit_for_study(0)
        group_comparison = model.get_current_group_comparison()
        assert _cell_text(model, 0, model.OUTCOMES[0]) == "0.750"
        assert all(_cell_text(model, 0, col) != "" for col in model.OUTCOMES)
        assert _derived_effect_and_ci(analysis_unit, "Sens", group_comparison) == (
            0.750,
            0.588,
            0.873,
        )
        assert _derived_effect_and_ci(analysis_unit, "PLR", group_comparison) == (
            61.5,
            8.8,
            431.0,
        )
    finally:
        _close_without_prompt(app, window)


def test_diagnostic_partial_paste_clears_stale_sens_spec_confidence_intervals(
    monkeypatch,
):
    from rc_metastudio import dataset_table_model
    from rc_metastudio import meta_globals

    app, window = automation.start_automation()
    try:
        _create_diagnostic_dataset(window)
        model = window.model
        table = window.tableView
        table.set_data_in_model(model.index(0, model.NAME), _variant("Lehman"))
        table.set_data_in_model(model.index(1, model.NAME), _variant("Lagasse"))
        analysis_unit = model.get_current_analysis_unit_for_study(1)
        group_comparison = model.get_current_group_comparison()
        analysis_unit.groups[group_comparison].raw_data = [15.0, 11.0, 16.0, 49.0]
        for metric in meta_globals.DIAGNOSTIC_METRICS:
            analysis_unit.set_effect_and_ci(
                metric,
                group_comparison,
                0.577,
                0.385,
                0.748,
                model.get_confidence_multiplier(),
            )
            analysis_unit.calculate_display_effect_and_ci(
                metric,
                group_comparison,
                lambda value: value,
                confidence_level=model.get_confidence_level(),
                confidence_multiplier=model.get_confidence_multiplier(),
                source="derived_preview",
            )
        model.dataset.studies[1].include = True
        window.data_dirtied()

        monkeypatch.setattr(
            window.model.editing_service.bridge,
            "diagnostic_convert_scale",
            lambda value, *args, **kwargs: value,
        )
        monkeypatch.setattr(
            window.model.editing_service.bridge,
            "diagnostic_effects_for_study",
            lambda *args, **kwargs: {
                "Sens": {"calc_scale": (0.800, 0.490, 0.943)},
                "Spec": {"calc_scale": (0.842, 0.687, 0.930)},
                "PLR": {"calc_scale": (5.0, 2.0, 12.0)},
                "NLR": {"calc_scale": (0.25, 0.08, 0.75)},
                "DOR": {"calc_scale": (20.0, 5.0, 80.0)},
            },
        )

        table.paste_contents(
            model.index(0, model.RAW_DATA[0]),
            [["8", "2", "6", "32"], ["5", "3"]],
        )

        assert [_cell_text(model, 1, col) for col in model.RAW_DATA] == [
            "5.0",
            "3.0",
            "",
            "",
        ]
        assert all(_cell_text(model, 1, col) == "" for col in model.OUTCOMES)
        assert model.dataset.studies[1].include is False
    finally:
        _close_without_prompt(app, window)


@pytest.mark.parametrize("entered_only", [False, True])
def test_csv_import_includes_complete_rows_from_the_first_row(entered_only):
    from rc_metastudio.main_window import ImportCsvCommand

    app, window = automation.start_automation()
    try:
        if entered_only:
            window._handle_wizard_results({
                "path": "new_dataset",
                "outcome_info": {
                    "arms": "one", "data_type": "continuous",
                    "sub_type": "generic_effect", "effect": "TX Mean",
                    "metric_choices": ["TX Mean"], "name": "Entered",
                },
                "csv_data": None, "selected_dataset": None,
            })
            values = ["1.5", "0.2"]
        else:
            _create_binary_dataset(window)
            values = ["1", "10", "2", "12", "", "", ""]
        command = ImportCsvCommand(
            imported_data=[[name, "2020", *values] for name in ("Alpha", "Beta")],
            main_form=window, covariate_names=[], covariate_types=[],
        )
        command._import_data_into_new_dataset()
        assert [study.include for study in window.model.dataset.studies] == [True, True]
    finally:
        _close_without_prompt(app, window)


def test_csv_import_progress_dialog_closes_when_model_write_raises(monkeypatch):
    from rc_metastudio import dataset_table_model
    from rc_metastudio import main_window

    app, window = automation.start_automation()
    progress_events = []

    class ProgressSpy(object):
        def __init__(self, parent=None, min_=0, max_=10):
            self.parent = parent
            self.min_ = min_
            self.max_ = max_
            self.current = min_

        def setValue(self, value):
            self.current = value

        def show(self):
            progress_events.append("show")

        def hide(self):
            progress_events.append("hide")

        def minimum(self):
            return self.min_

        def maximum(self):
            return self.max_

        def value(self):
            return self.current

    def raise_on_set_data(self, *args, **kwargs):
        raise RuntimeError("simulated CSV model write failure")

    try:
        _create_binary_dataset(window)
        command = main_window.ImportCsvCommand(
            imported_data=[["Alpha", "2020", "1", "10", "2", "12"]],
            main_form=window,
            covariate_names=[],
            covariate_types=[],
        )
        monkeypatch.setattr(main_window, "ImportProgressDialog", ProgressSpy)
        monkeypatch.setattr(
            dataset_table_model.DatasetTableModel, "setData", raise_on_set_data
        )

        with pytest.raises(RuntimeError, match="simulated CSV model write failure"):
            command._import_data_into_new_dataset()

        assert progress_events == ["show", "hide"]
    finally:
        _close_without_prompt(app, window)


def test_paste_contents_pads_short_rows_and_clears_trailing_cells():

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)
        model = window.model
        table = window.tableView

        table.paste_contents(
            model.index(1, model.NAME), [["Beta", "2021", "3", "11", "4", "99"]]
        )

        table.paste_contents(
            model.index(0, model.NAME),
            [
                ["Alpha", "2020", "1", "10", "2", "12"],
                ["Beta", "2021", "3", "11", "4"],
            ],
        )

        assert _cell_text(model, 0, model.RAW_DATA[-1]) == "12.0"
        assert _cell_text(model, 1, model.NAME) == "Beta"
        assert _cell_text(model, 1, model.RAW_DATA[-1]) == ""
    finally:
        _close_without_prompt(app, window)


def test_paste_contents_keeps_columns_from_rows_wider_than_the_first():

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)
        model = window.model
        table = window.tableView

        table.paste_contents(
            model.index(0, model.NAME),
            [
                ["Alpha", "2020", "1", "10", "2"],
                ["Beta", "2021", "3", "11", "4", "13"],
            ],
        )

        assert _cell_text(model, 0, model.RAW_DATA[-1]) == ""
        assert _cell_text(model, 1, model.RAW_DATA[-1]) == "13.0"
    finally:
        _close_without_prompt(app, window)


def test_invalid_paste_reports_validation_error_when_model_signals_are_blocked(
    monkeypatch,
):

    app, window = automation.start_automation()
    model = None
    try:
        _create_binary_dataset(window)
        model = window.model
        table = window.tableView
        shown = []
        main_window = sys.modules["rc_metastudio.main_window"]
        monkeypatch.setattr(
            main_window.QMessageBox,
            "warning",
            lambda *args, **kwargs: shown.append(args),
        )

        table.set_data_in_model(model.index(0, model.NAME), _variant("Alpha"))
        model.blockSignals(True)
        table.paste_contents(model.index(0, model.RAW_DATA[0]), [["not numeric"]])

        assert shown
        assert shown[-1][1:] == ("Warning", "Raw data needs to be numeric.")
        assert _cell_text(model, 0, model.RAW_DATA[0]) == ""
        assert model.signalsBlocked()
    finally:
        if model is not None:
            model.blockSignals(False)
        _close_without_prompt(app, window)


def test_add_outcome_dialog_rejects_blank_and_duplicate_names(monkeypatch):
    from PyQt6 import QtWidgets

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)
        main_window = sys.modules["rc_metastudio.main_window"]
        warnings = []
        monkeypatch.setattr(
            main_window.QMessageBox,
            "warning",
            lambda *args, **kwargs: warnings.append(args),
        )

        class BlankOutcomeDialog(object):
            def __init__(self, *args, **kwargs):
                self.outcome_name_le = QtWidgets.QLineEdit()
                self.outcome_name_le.setText("   ")
                self.datatype_cbo_box = QtWidgets.QComboBox()
                self.datatype_cbo_box.addItem("Binary")

            def exec(self):
                return True

        monkeypatch.setattr(
            main_window.add_new_dialogs, "AddOutcomeDialog", BlankOutcomeDialog
        )

        window.current_dimension = "outcome"
        window.add_new()

        assert warnings[-1][1:] == ("Warning", "Outcome names cannot be empty.")
        assert window.model.dataset.get_outcome_names() == ["Mortality"]

        class DuplicateOutcomeDialog(BlankOutcomeDialog):
            def __init__(self, *args, **kwargs):
                super(DuplicateOutcomeDialog, self).__init__(*args, **kwargs)
                self.outcome_name_le.setText("Mortality")

        monkeypatch.setattr(
            main_window.add_new_dialogs, "AddOutcomeDialog", DuplicateOutcomeDialog
        )

        window.add_new()

        assert warnings[-1][1:] == (
            "Warning",
            "An outcome named Mortality already exists. Please pick another name.",
        )
        assert window.model.dataset.get_outcome_names() == ["Mortality"]
    finally:
        _close_without_prompt(app, window)


def test_edit_dialog_rejects_blank_outcome_name(monkeypatch):
    from rc_metastudio import edit_dialog
    from PyQt6 import QtWidgets

    app, window = automation.start_automation()
    dialog = None
    try:
        _create_binary_dataset(window)
        warnings = []
        monkeypatch.setattr(
            edit_dialog.QMessageBox,
            "warning",
            lambda *args, **kwargs: warnings.append(args),
        )

        class BlankOutcomeDialog(object):
            def __init__(self, *args, **kwargs):
                self.outcome_name_le = QtWidgets.QLineEdit()
                self.outcome_name_le.setText("")
                self.datatype_cbo_box = QtWidgets.QComboBox()
                self.datatype_cbo_box.addItem("Continuous")

            def exec(self):
                return True

        monkeypatch.setattr(
            edit_dialog.add_new_dialogs, "AddOutcomeDialog", BlankOutcomeDialog
        )

        dialog = edit_dialog.EditDialog(window.model.dataset, parent=window)
        dialog.add_outcome()

        assert warnings[-1][1:] == ("Warning", "Outcome names cannot be empty.")
        assert window.model.dataset.get_outcome_names() == ["Mortality"]
    finally:
        if dialog is not None:
            dialog.close()
        _close_without_prompt(app, window)


def test_edit_dialog_rejects_blank_names_for_other_dataset_entities(monkeypatch):
    from rc_metastudio import edit_dialog
    from PyQt6 import QtWidgets

    app, window = automation.start_automation()
    dialog = None
    try:
        _create_binary_dataset(window)
        warnings = []
        monkeypatch.setattr(
            edit_dialog.QMessageBox,
            "warning",
            lambda *args, **kwargs: warnings.append(args),
        )

        class BlankGroupDialog(object):
            def __init__(self, *args, **kwargs):
                self.group_name_le = QtWidgets.QLineEdit()
                self.group_name_le.setText(" ")

            def exec(self):
                return True

        class BlankFollowUpDialog(object):
            def __init__(self, *args, **kwargs):
                self.follow_up_name_le = QtWidgets.QLineEdit()
                self.follow_up_name_le.setText("   ")

            def exec(self):
                return True

        class BlankCovariateDialog(object):
            def __init__(self, *args, **kwargs):
                self.covariate_name_le = QtWidgets.QLineEdit()
                self.covariate_name_le.setText("")
                self.datatype_cbo_box = QtWidgets.QComboBox()
                self.datatype_cbo_box.addItem("Continuous")

            def exec(self):
                return True

        class BlankStudyDialog(object):
            def __init__(self, *args, **kwargs):
                self.study_lbl = QtWidgets.QLineEdit()
                self.study_lbl.setText(" ")

            def exec(self):
                return True

        monkeypatch.setattr(
            edit_dialog.add_new_dialogs, "AddGroupDialog", BlankGroupDialog
        )
        monkeypatch.setattr(
            edit_dialog.add_new_dialogs, "AddFollowUpDialog", BlankFollowUpDialog
        )
        monkeypatch.setattr(
            edit_dialog.add_new_dialogs, "AddCovariateDialog", BlankCovariateDialog
        )
        monkeypatch.setattr(
            edit_dialog.add_new_dialogs, "AddStudyDialog", BlankStudyDialog
        )

        dialog = edit_dialog.EditDialog(window.model.dataset, parent=window)

        dialog.add_group()
        assert warnings[-1][1:] == ("Warning", "Group names cannot be empty.")

        dialog.add_follow_up()
        assert warnings[-1][1:] == ("Warning", "Follow-up names cannot be empty.")

        dialog.add_covariate()
        assert warnings[-1][1:] == ("Warning", "Covariate names cannot be empty.")

        dialog.add_study()
        assert warnings[-1][1:] == ("Warning", "Study names cannot be empty.")

        assert " " not in window.model.dataset.get_group_names()
        assert "   " not in window.model.dataset.get_follow_up_names()
        assert "" not in window.model.get_covariate_names()
        assert " " not in window.model.dataset.get_study_names()
    finally:
        if dialog is not None:
            dialog.close()
        _close_without_prompt(app, window)


def test_add_dialogs_reject_blank_names_for_other_dataset_entities(monkeypatch):
    from PyQt6 import QtWidgets

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)
        main_window = sys.modules["rc_metastudio.main_window"]
        warnings = []
        monkeypatch.setattr(
            main_window.QMessageBox,
            "warning",
            lambda *args, **kwargs: warnings.append(args),
        )

        class BlankGroupDialog(object):
            def __init__(self, *args, **kwargs):
                self.group_name_le = QtWidgets.QLineEdit()
                self.group_name_le.setText("   ")

            def exec(self):
                return True

        class BlankFollowUpDialog(object):
            def __init__(self, *args, **kwargs):
                self.follow_up_name_le = QtWidgets.QLineEdit()
                self.follow_up_name_le.setText("")

            def exec(self):
                return True

        class BlankCovariateDialog(object):
            def __init__(self, *args, **kwargs):
                self.covariate_name_le = QtWidgets.QLineEdit()
                self.covariate_name_le.setText(" ")
                self.datatype_cbo_box = QtWidgets.QComboBox()
                self.datatype_cbo_box.addItem("Continuous")

            def exec(self):
                return True

        monkeypatch.setattr(
            main_window.add_new_dialogs, "AddGroupDialog", BlankGroupDialog
        )
        monkeypatch.setattr(
            main_window.add_new_dialogs, "AddFollowUpDialog", BlankFollowUpDialog
        )
        monkeypatch.setattr(
            main_window.add_new_dialogs, "AddCovariateDialog", BlankCovariateDialog
        )

        window.current_dimension = "group"
        window.add_new()
        assert warnings[-1][1:] == ("Warning", "Group names cannot be empty.")

        window.current_dimension = "follow-up"
        window.add_new()
        assert warnings[-1][1:] == ("Warning", "Follow-up names cannot be empty.")

        window.add_covariate()
        assert warnings[-1][1:] == ("Warning", "Covariate names cannot be empty.")

        assert "   " not in window.model.dataset.get_group_names()
        assert "" not in window.model.dataset.get_follow_up_names()
        assert " " not in window.model.get_covariate_names()
    finally:
        _close_without_prompt(app, window)


def test_main_window_dialog_text_slots_accept_native_pyqt6_line_edit_strings(
    monkeypatch,
):
    from PyQt6 import QtWidgets

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)
        main_window = sys.modules["rc_metastudio.main_window"]

        class GroupNameDialog(object):
            def __init__(self, *args, **kwargs):
                self.group_name_le = QtWidgets.QLineEdit()
                self.group_name_le.setText("Renamed group")

            def exec(self):
                return True

        class CovariateNameDialog(object):
            def __init__(self, *args, **kwargs):
                self.group_name_le = QtWidgets.QLineEdit()
                self.group_name_le.setText("Renamed dose")

            def exec(self):
                return True

        class NewCovariateDialog(object):
            def __init__(self, *args, **kwargs):
                self.covariate_name_le = QtWidgets.QLineEdit()
                self.covariate_name_le.setText("Dose")
                self.datatype_cbo_box = QtWidgets.QComboBox()
                self.datatype_cbo_box.addItem("Continuous")

            def exec(self):
                return True

        class NewOutcomeDialog(object):
            def __init__(self, *args, **kwargs):
                self.outcome_name_le = QtWidgets.QLineEdit()
                self.outcome_name_le.setText("Recovery")
                self.datatype_cbo_box = QtWidgets.QComboBox()
                self.datatype_cbo_box.addItem("Binary")

            def exec(self):
                return True

        class NewGroupDialog(object):
            def __init__(self, *args, **kwargs):
                self.group_name_le = QtWidgets.QLineEdit()
                self.group_name_le.setText("Added group")

            def exec(self):
                return True

        class NewFollowUpDialog(object):
            def __init__(self, *args, **kwargs):
                self.follow_up_name_le = QtWidgets.QLineEdit()
                self.follow_up_name_le.setText("week 4")

            def exec(self):
                return True

        monkeypatch.setattr(
            main_window.edit_name_dialogs, "EditGroupNameDialog", GroupNameDialog
        )
        monkeypatch.setattr(
            main_window.edit_name_dialogs,
            "EditCovariateNameDialog",
            CovariateNameDialog,
        )
        monkeypatch.setattr(
            main_window.add_new_dialogs, "AddCovariateDialog", NewCovariateDialog
        )
        monkeypatch.setattr(
            main_window.add_new_dialogs, "AddOutcomeDialog", NewOutcomeDialog
        )
        monkeypatch.setattr(
            main_window.add_new_dialogs, "AddGroupDialog", NewGroupDialog
        )
        monkeypatch.setattr(
            main_window.add_new_dialogs, "AddFollowUpDialog", NewFollowUpDialog
        )

        window.edit_group_name(window.model.get_current_groups()[0])
        window.add_covariate()
        window.current_dimension = "outcome"
        window.add_new()
        window.current_dimension = "group"
        window.add_new()
        window.current_dimension = "follow-up"
        window.add_new()
        window.rename_covariate(window.model.dataset.covariates[0])

        assert "Renamed group" in window.model.get_current_groups()
        assert "Recovery" in window.model.dataset.get_outcome_names()
        assert "Added group" in window.model.dataset.get_group_names()
        assert "week 4" in window.model.dataset.get_follow_up_names()
        assert "Renamed dose" in window.model.get_covariate_names()
    finally:
        _close_without_prompt(app, window)


def test_edit_dataset_rejection_leaves_main_dataset_unchanged(monkeypatch):
    from rc_metastudio import edit_dialog

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)
        original_dataset = window.model.dataset
        original_names = [study.name for study in original_dataset.studies]
        original_history = window.workspace.document

        def reject_after_editing_copy(dialog):
            dialog.dataset.studies[0].name = "Rejected dataset edit"
            return QDialog.DialogCode.Rejected

        monkeypatch.setattr(edit_dialog.EditDialog, "exec", reject_after_editing_copy)

        window.edit_dataset()

        assert window.model.dataset is original_dataset
        assert [study.name for study in window.model.dataset.studies] == original_names
        assert window.workspace.document == original_history
    finally:
        _close_without_prompt(app, window)


def test_edit_empty_dataset_can_be_cancelled(monkeypatch):
    from rc_metastudio import edit_dialog

    app, window = automation.start_automation()
    try:
        original_dataset = window.model.dataset
        monkeypatch.setattr(
            edit_dialog.EditDialog,
            "exec",
            lambda dialog: QDialog.DialogCode.Rejected,
        )

        window.edit_dataset()

        assert window.model.dataset is original_dataset
        assert window.model.current_outcome_name is None
    finally:
        _close_without_prompt(app, window)


def test_edit_empty_dataset_acceptance_preserves_state_without_empty_undo(monkeypatch):
    from rc_metastudio import edit_dialog

    app, window = automation.start_automation()
    try:
        monkeypatch.setattr(
            edit_dialog.EditDialog,
            "exec",
            lambda dialog: QDialog.DialogCode.Accepted,
        )

        window.edit_dataset()

        assert window.model.dataset.get_outcome_names() == []
        assert window.model.current_outcome_name is None
        assert not window.workspace.can_undo
    finally:
        _close_without_prompt(app, window)


def test_edit_dataset_acceptance_propagates_copied_dataset_mutation(monkeypatch):
    from rc_metastudio import edit_dialog

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)
        original_dataset = window.model.dataset
        original_name = original_dataset.studies[0].name
        renamed_study = "Renamed through Edit Dataset"
        original_history = window.workspace.document

        def accept_after_renaming_study(dialog):
            dialog.dataset.studies[0].name = renamed_study
            return QDialog.DialogCode.Accepted

        monkeypatch.setattr(edit_dialog.EditDialog, "exec", accept_after_renaming_study)

        window.edit_dataset()

        assert window.model.dataset is not original_dataset
        assert window.model.dataset.studies[0].name == renamed_study
        assert original_dataset.studies[0].name == original_name
        assert window.workspace.can_undo

        window.undo()
        assert window.model.dataset.studies[0].name == original_name
    finally:
        _close_without_prompt(app, window)


def test_metric_selection_and_confidence_level_are_preserved_in_model_state():

    app, window = automation.start_automation()
    try:
        _create_binary_dataset(window)

        rr_action = _metric_action(window, "RR")
        rr_action.setChecked(True)
        window.model.set_confidence_level(90.0)
        window._update_confidence_level_label()
        state = window.model.get_state()

        assert window.model.current_effect == "RR"
        assert window.model.get_confidence_level() == 90.0
        assert window.cl_label.text() == "Confidence Level: 90.0%"

        window.set_model(window.model.dataset.copy(), state)

        assert window.model.current_effect == "RR"
        assert window.model.get_confidence_level() == 90.0
        assert window.cl_label.text() == "Confidence Level: 90.0%"
        assert _metric_action(window, "RR").isChecked()
    finally:
        _close_without_prompt(app, window)


def test_confidence_level_dialog_rejects_represented_100_percent():
    from PyQt6.QtWidgets import QApplication

    from rc_metastudio import confidence_level_dialog

    _app = required(QApplication.instance() or QApplication([]), "application")
    dialog = confidence_level_dialog.ConfidenceLevelDialog(95.0)
    try:
        spinbox = dialog.confidence_level_spinbox

        required(spinbox.lineEdit(), "confidence level edit").setText("100")
        spinbox.interpretText()

        assert spinbox.maximum() == 99.9
        assert spinbox.value() == 95.0
        assert dialog.get_value() == 95.0
    finally:
        dialog.close()


def test_dataset_model_rejects_invalid_confidence_levels_without_touching_r(
    monkeypatch,
):
    from rc_metastudio import dataset_table_model

    app, window = automation.start_automation()
    try:
        calls = []

        def fail_if_called(confidence_level):
            calls.append(confidence_level)
            raise AssertionError("invalid confidence level reached R multiplier")

        monkeypatch.setattr(
            window.model.editing_service.bridge,
            "get_confidence_multiplier_from_r",
            fail_if_called,
        )

        for invalid_value in (0, 100, math.inf, math.nan, "not-a-number"):
            with pytest.raises(ValueError, match="greater than 0 and less than 100"):
                window.model.set_confidence_level(invalid_value)

        assert calls == []
        assert window.model.get_confidence_level() == 95.0
    finally:
        _close_without_prompt(app, window)


def _create_binary_dataset(window):
    window._handle_wizard_results(
        {
            "path": "new_dataset",
            "outcome_info": {
                "arms": "two",
                "data_type": "binary",
                "sub_type": "proportions",
                "effect": "OR",
                "metric_choices": [],
                "name": "Mortality",
            },
            "csv_data": None,
            "selected_dataset": None,
        }
    )


def _create_continuous_dataset(window):
    window._handle_wizard_results(
        {
            "path": "new_dataset",
            "outcome_info": {
                "arms": "two",
                "data_type": "continuous",
                "sub_type": "means",
                "effect": "MD",
                "metric_choices": [],
                "name": "Recovery",
            },
            "csv_data": None,
            "selected_dataset": None,
        }
    )


def _create_diagnostic_dataset(window):
    window._handle_wizard_results(
        {
            "path": "new_dataset",
            "outcome_info": {
                "arms": "two",
                "data_type": "diagnostic",
                "sub_type": None,
                "effect": "Sens",
                "metric_choices": [],
                "name": "Accuracy",
            },
            "csv_data": None,
            "selected_dataset": None,
        }
    )


def _metric_action(window, metric):
    from rc_metastudio import qt_text

    for menu_action in window.menuMetric.actions():
        menu = menu_action.menu()
        if menu is None:
            continue
        for action in menu.actions():
            action_data = action.data()
            action_metric = qt_text.to_native_text(action_data)
            if action_metric == metric:
                return action
    raise AssertionError("Metric action not found: %s" % metric)


def _variant(value):
    return value


def _cell_text(model, row, column):
    value = model.data(model.index(row, column))
    return str(value.value() if hasattr(value, "value") else value)


def _close_without_prompt(app, window):
    if window.workspace.document is not None:
        window.workspace.mark_saved()
    window.close()
    app.processEvents()
    os.chdir(REPO_ROOT)
