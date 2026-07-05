import os
import sys
import math
import copy

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath("src"))

import pytest


REPO_ROOT = os.getcwd()


def test_data_table_return_moves_vertically_from_selected_cells():
    from PyQt5 import QtCore, QtTest

    import launch

    app, window = launch.start_automation()
    try:
        _create_binary_dataset(window)
        table = window.tableView
        model = window.model

        table.setCurrentIndex(model.index(0, model.NAME))
        QtTest.QTest.keyClick(table, QtCore.Qt.Key_Return)
        assert table.currentIndex() == model.index(1, model.NAME)

        QtTest.QTest.keyClick(table, QtCore.Qt.Key_Enter)
        assert table.currentIndex() == model.index(2, model.NAME)

        QtTest.QTest.keyClick(table, QtCore.Qt.Key_Return, QtCore.Qt.ShiftModifier)
        assert table.currentIndex() == model.index(1, model.NAME)
    finally:
        _close_without_prompt(app, window)


def test_data_table_return_commits_editor_and_moves_down_same_column():
    from PyQt5 import QtCore, QtTest, QtWidgets

    import launch

    app, window = launch.start_automation()
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
        QtTest.QTest.keyClick(editor, QtCore.Qt.Key_Return)
        app.processEvents()

        assert _cell_text(model, 0, model.NAME) == "Alpha"
        assert table.currentIndex() == model.index(1, model.NAME)
    finally:
        _close_without_prompt(app, window)


def test_data_table_ctrl_a_selects_all_cells_without_running_analysis(monkeypatch):
    from PyQt5 import QtCore, QtTest

    import launch

    app, window = launch.start_automation()
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

        QtTest.QTest.keyClick(table, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
        app.processEvents()

        assert analysis_calls == []
        assert len(table.selectionModel().selectedIndexes()) == (
            model.rowCount() * model.columnCount()
        )
    finally:
        _close_without_prompt(app, window)


def test_data_table_delete_and_backspace_clear_selected_cells(monkeypatch):
    from PyQt5 import QtCore, QtTest

    import launch
    import ma_data_table_model

    app, window = launch.start_automation()
    try:
        _create_binary_dataset(window)
        model = window.model
        table = window.tableView
        table.set_data_in_model(model.index(0, model.NAME), _variant("Alpha"))

        monkeypatch.setattr(
            ma_data_table_model.meta_py_r,
            "binary_convert_scale",
            lambda value, *args, **kwargs: value,
        )
        monkeypatch.setattr(
            ma_data_table_model.meta_py_r,
            "effect_for_study",
            lambda *args, **kwargs: {"calc_scale": (0.5, 0.25, 1.0)},
        )

        table.paste_contents(
            model.index(0, model.RAW_DATA[0]), [["41", "50", "3", "48"]]
        )
        assert _cell_text(model, 0, model.RAW_DATA[0]) == "41.0"
        assert all(_cell_text(model, 0, col) != "" for col in model.OUTCOMES)

        table.setFocus()
        table.setCurrentIndex(model.index(0, model.RAW_DATA[0]))
        QtTest.QTest.keyClick(table, QtCore.Qt.Key_Delete)
        app.processEvents()

        assert _cell_text(model, 0, model.RAW_DATA[0]) == ""
        assert all(_cell_text(model, 0, col) == "" for col in model.OUTCOMES)

        table.set_data_in_model(model.index(0, model.RAW_DATA[0]), _variant("41"))
        assert _cell_text(model, 0, model.RAW_DATA[0]) == "41.0"

        table.setCurrentIndex(model.index(0, model.RAW_DATA[0]))
        QtTest.QTest.keyClick(table, QtCore.Qt.Key_Backspace)
        app.processEvents()

        assert _cell_text(model, 0, model.RAW_DATA[0]) == ""
        assert all(_cell_text(model, 0, col) == "" for col in model.OUTCOMES)
    finally:
        _close_without_prompt(app, window)


def test_real_metaform_creates_binary_continuous_and_diagnostic_datasets():
    import launch

    cases = [
        ("binary", "proportions", "OR", "Mortality", "binary"),
        ("continuous", "means", "SMD", "Recovery", "continuous"),
        ("diagnostic", None, "Sens", "Accuracy", "diagnostic"),
    ]

    for data_type, sub_type, effect, name, expected_type in cases:
        app, window = launch.start_automation()
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
            assert window.model.current_outcome == name
            assert window.tableView.model() is window.model
            assert window.model.rowCount() > 0
            if data_type != "diagnostic":
                assert window.model.current_effect == effect
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
    import launch

    app, window = launch.start_automation()
    try:
        getattr(window, show_method)()
        app.processEvents()

        _create_binary_dataset(window)
        app.processEvents()

        assert getattr(window, state_method)()
        assert window.tableView.model() is window.model
        assert window.model.current_outcome == "Mortality"
    finally:
        _close_without_prompt(app, window)


def test_content_fit_does_not_resize_visible_main_window(monkeypatch):
    import launch
    import qt_layout

    app, window = launch.start_automation()
    try:
        window.showMaximized()
        app.processEvents()

        adjust_calls = []
        monkeypatch.setattr(window, "adjustSize", lambda: adjust_calls.append(True))

        qt_layout.fit_text_to_contents(window)

        assert adjust_calls == []
        assert window.isMaximized()
    finally:
        _close_without_prompt(app, window)


def test_data_table_editing_preserves_maximized_main_window_state():
    import launch

    app, window = launch.start_automation()
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
    import launch

    app, window = launch.start_automation()
    try:
        with pytest.raises(ValueError, match="without a data type"):
            window.model.add_new_outcome("Missing type", None)

        with pytest.raises(ValueError, match="Unsupported outcome data type"):
            window.model.add_new_outcome("Unknown type", "not-a-data-type")
    finally:
        _close_without_prompt(app, window)


def test_dataset_model_rejects_blank_and_duplicate_outcome_names():
    import launch

    app, window = launch.start_automation()
    try:
        _create_binary_dataset(window)

        with pytest.raises(ValueError, match="Outcome names cannot be empty"):
            window.model.add_new_outcome("   ", "binary")

        with pytest.raises(ValueError, match="already exists"):
            window.model.add_new_outcome("Mortality", "binary")
    finally:
        _close_without_prompt(app, window)


def test_dataset_model_rejects_invalid_added_entity_names():
    import launch

    app, window = launch.start_automation()
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
    import launch

    app, window = launch.start_automation()
    saved_path = str(tmp_path / "edited.oma")
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

        meta_form = sys.modules["meta_form"]
        monkeypatch.setattr(
            meta_form.QFileDialog, "getSaveFileName", lambda **kwargs: (saved_path, "")
        )
        window.save_as()
        reopened = meta_form._load_project_pickle(saved_path)

        assert [
            (str(study.name), str(study.year)) for study in reopened.studies[:1]
        ] == [("Alpha", "2020")]
        assert "Readmission" in reopened.get_outcome_names()
        assert "week 4" in reopened.outcome_names_to_follow_ups["Mortality"].values()
        assert "Tx C" in reopened.get_group_names()
        assert [(cov.name, cov.data_type) for cov in reopened.covariates] == [
            ("Dose", 1)
        ]
        assert reopened.studies[0].covariate_dict["Dose"] == 5.5
    finally:
        _close_without_prompt(app, window)


def test_copy_paste_undo_and_redo_work_through_real_table_path():
    import launch

    app, window = launch.start_automation()
    try:
        _create_binary_dataset(window)
        model = window.model
        table = window.tableView

        table.paste_contents(
            model.index(0, model.NAME), [["Alpha", "2020", "1", "10", "2", "12"]]
        )
        copied = table.copy_contents_in_range(
            model.index(0, model.RAW_DATA[0]),
            model.index(0, model.RAW_DATA[-1]),
            to_clipboard=True,
        )

        assert copied == "1.0\t10.0\t2.0\t12.0"

        table.set_data_in_model(model.index(1, model.NAME), _variant("Beta"))
        table.paste_from_clipboard(model.index(1, model.RAW_DATA[0]))
        assert _cell_text(model, 1, model.NAME) == "Beta"
        assert _cell_text(model, 1, model.RAW_DATA[-1]) == "12.0"

        window.undo()
        assert _cell_text(window.model, 1, window.model.NAME) == "Beta"
        assert _cell_text(window.model, 1, window.model.RAW_DATA[-1]) == ""

        window.redo()
        assert _cell_text(window.model, 1, window.model.NAME) == "Beta"
        assert _cell_text(window.model, 1, window.model.RAW_DATA[-1]) == "12.0"
    finally:
        _close_without_prompt(app, window)


def test_diagnostic_complete_paste_recomputes_sens_spec_confidence_intervals(
    monkeypatch,
):
    import launch
    import ma_data_table_model

    app, window = launch.start_automation()
    try:
        _create_diagnostic_dataset(window)
        model = window.model
        table = window.tableView
        table.set_data_in_model(model.index(0, model.NAME), _variant("Kinderman"))

        monkeypatch.setattr(
            ma_data_table_model.meta_py_r,
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
            ma_data_table_model.meta_py_r,
            "diagnostic_effects_for_study",
            diagnostic_effects_for_study,
        )

        table.paste_contents(
            model.index(0, model.RAW_DATA[0]), [["30", "10", "1", "81"]]
        )

        assert _cell_text(model, 0, model.OUTCOMES[0]) == "0.750"
        assert all(_cell_text(model, 0, col) != "" for col in model.OUTCOMES)
    finally:
        _close_without_prompt(app, window)


def test_diagnostic_partial_paste_clears_stale_sens_spec_confidence_intervals(
    monkeypatch,
):
    import launch
    import ma_data_table_model
    import meta_globals

    app, window = launch.start_automation()
    try:
        _create_diagnostic_dataset(window)
        model = window.model
        table = window.tableView
        table.set_data_in_model(model.index(0, model.NAME), _variant("Lehman"))
        table.set_data_in_model(model.index(1, model.NAME), _variant("Lagasse"))
        ma_unit = model.get_current_ma_unit_for_study(1)
        group_str = model.get_cur_group_str()
        ma_unit.tx_groups[group_str].raw_data = [15.0, 11.0, 16.0, 49.0]
        for metric in meta_globals.DIAGNOSTIC_METRICS:
            ma_unit.set_effect_and_ci(
                metric, group_str, 0.577, 0.385, 0.748, model.get_mult()
            )
            ma_unit.calculate_display_effect_and_ci(
                metric,
                group_str,
                lambda value: value,
                conf_level=model.get_global_conf_level(),
                mult=model.get_mult(),
            )
        model.dataset.studies[1].include = True

        monkeypatch.setattr(
            ma_data_table_model.meta_py_r,
            "diagnostic_convert_scale",
            lambda value, *args, **kwargs: value,
        )
        monkeypatch.setattr(
            ma_data_table_model.meta_py_r,
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


def test_csv_import_progress_dialog_closes_when_model_write_raises(monkeypatch):
    import launch
    import ma_data_table_model
    import meta_form

    app, window = launch.start_automation()
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
        state = window.tableView.model().get_stateful_dict()
        command = meta_form.CommandImportCSV(
            original_dataset=copy.deepcopy(window.model.dataset),
            old_state_dict=state,
            new_dataset=copy.deepcopy(window.model.dataset),
            new_state_dict=state,
            imported_data=[["Alpha", "2020", "1", "10", "2", "12"]],
            main_form=window,
            covariate_names=[],
            covariate_types=[],
        )
        monkeypatch.setattr(meta_form, "ImportProgress", ProgressSpy)
        monkeypatch.setattr(
            ma_data_table_model.DatasetModel, "setData", raise_on_set_data
        )

        with pytest.raises(RuntimeError, match="simulated CSV model write failure"):
            command._import_data_into_new_dataset()

        assert progress_events == ["show", "hide"]
    finally:
        _close_without_prompt(app, window)


def test_paste_contents_pads_short_rows_and_clears_trailing_cells():
    import launch

    app, window = launch.start_automation()
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
    import launch

    app, window = launch.start_automation()
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
    import launch

    app, window = launch.start_automation()
    try:
        _create_binary_dataset(window)
        model = window.model
        table = window.tableView
        shown = []
        meta_form = sys.modules["meta_form"]
        monkeypatch.setattr(
            meta_form.QMessageBox, "warning", lambda *args, **kwargs: shown.append(args)
        )

        table.set_data_in_model(model.index(0, model.NAME), _variant("Alpha"))
        table.paste_contents(model.index(0, model.RAW_DATA[0]), [["not numeric"]])

        assert shown
        assert shown[-1][1:] == ("Warning", "Raw data needs to be numeric.")
        assert _cell_text(model, 0, model.RAW_DATA[0]) == ""
    finally:
        _close_without_prompt(app, window)


def test_add_outcome_dialog_rejects_blank_and_duplicate_names(monkeypatch):
    import launch
    from PyQt5 import QtWidgets

    app, window = launch.start_automation()
    try:
        _create_binary_dataset(window)
        meta_form = sys.modules["meta_form"]
        warnings = []
        monkeypatch.setattr(
            meta_form.QMessageBox,
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
            meta_form.add_new_dialogs, "AddNewOutcomeForm", BlankOutcomeDialog
        )

        window.cur_dimension = "outcome"
        window.add_new()

        assert warnings[-1][1:] == ("Warning", "Outcome names cannot be empty.")
        assert window.model.dataset.get_outcome_names() == ["Mortality"]

        class DuplicateOutcomeDialog(BlankOutcomeDialog):
            def __init__(self, *args, **kwargs):
                super(DuplicateOutcomeDialog, self).__init__(*args, **kwargs)
                self.outcome_name_le.setText("Mortality")

        monkeypatch.setattr(
            meta_form.add_new_dialogs, "AddNewOutcomeForm", DuplicateOutcomeDialog
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
    import launch
    import edit_dialog
    from PyQt5 import QtWidgets

    app, window = launch.start_automation()
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
            edit_dialog.add_new_dialogs, "AddNewOutcomeForm", BlankOutcomeDialog
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
    import launch
    import edit_dialog
    from PyQt5 import QtWidgets

    app, window = launch.start_automation()
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
            edit_dialog.add_new_dialogs, "AddNewGroupForm", BlankGroupDialog
        )
        monkeypatch.setattr(
            edit_dialog.add_new_dialogs, "AddNewFollowUpForm", BlankFollowUpDialog
        )
        monkeypatch.setattr(
            edit_dialog.add_new_dialogs, "AddNewCovariateForm", BlankCovariateDialog
        )
        monkeypatch.setattr(
            edit_dialog.add_new_dialogs, "AddNewStudyForm", BlankStudyDialog
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
    import launch
    from PyQt5 import QtWidgets

    app, window = launch.start_automation()
    try:
        _create_binary_dataset(window)
        meta_form = sys.modules["meta_form"]
        warnings = []
        monkeypatch.setattr(
            meta_form.QMessageBox,
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
            meta_form.add_new_dialogs, "AddNewGroupForm", BlankGroupDialog
        )
        monkeypatch.setattr(
            meta_form.add_new_dialogs, "AddNewFollowUpForm", BlankFollowUpDialog
        )
        monkeypatch.setattr(
            meta_form.add_new_dialogs, "AddNewCovariateForm", BlankCovariateDialog
        )

        window.cur_dimension = "group"
        window.add_new()
        assert warnings[-1][1:] == ("Warning", "Group names cannot be empty.")

        window.cur_dimension = "follow-up"
        window.add_new()
        assert warnings[-1][1:] == ("Warning", "Follow-up names cannot be empty.")

        window.add_covariate()
        assert warnings[-1][1:] == ("Warning", "Covariate names cannot be empty.")

        assert "   " not in window.model.dataset.get_group_names()
        assert "" not in window.model.dataset.get_follow_up_names()
        assert " " not in window.model.get_covariate_names()
    finally:
        _close_without_prompt(app, window)


def test_metaform_dialog_text_slots_accept_pyqt5_line_edit_strings(monkeypatch):
    import launch
    from PyQt5 import QtWidgets

    app, window = launch.start_automation()
    try:
        _create_binary_dataset(window)
        meta_form = sys.modules["meta_form"]

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
                self.datatype_cbo_box.addItem("Continuous")

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
            meta_form.edit_group_name_form, "EditGroupName", GroupNameDialog
        )
        monkeypatch.setattr(
            meta_form.edit_group_name_form, "EditCovariateName", CovariateNameDialog
        )
        monkeypatch.setattr(
            meta_form.add_new_dialogs, "AddNewCovariateForm", NewCovariateDialog
        )
        monkeypatch.setattr(
            meta_form.add_new_dialogs, "AddNewOutcomeForm", NewOutcomeDialog
        )
        monkeypatch.setattr(
            meta_form.add_new_dialogs, "AddNewGroupForm", NewGroupDialog
        )
        monkeypatch.setattr(
            meta_form.add_new_dialogs, "AddNewFollowUpForm", NewFollowUpDialog
        )

        window.edit_group_name(window.model.get_current_groups()[0])
        window.add_covariate()
        window.cur_dimension = "outcome"
        window.add_new()
        window.cur_dimension = "group"
        window.add_new()
        window.cur_dimension = "follow-up"
        window.add_new()
        window.rename_covariate(window.model.dataset.covariates[0])

        assert "Renamed group" in window.model.get_current_groups()
        assert "Recovery" in window.model.dataset.get_outcome_names()
        assert "Added group" in window.model.dataset.get_group_names()
        assert "week 4" in window.model.dataset.get_follow_up_names()
        assert "Renamed dose" in window.model.get_covariate_names()
    finally:
        _close_without_prompt(app, window)


def test_metric_selection_and_confidence_level_are_preserved_in_model_state():
    import launch

    app, window = launch.start_automation()
    try:
        _create_binary_dataset(window)

        rr_action = _metric_action(window, "RR")
        rr_action.setChecked(True)
        window.model.set_conf_level(90.0)
        window._change_conf_level_label()
        state = window.model.get_stateful_dict()

        assert window.model.current_effect == "RR"
        assert window.model.get_global_conf_level() == 90.0
        assert window.cl_label.text() == "Confidence Level: 90.0%"

        window.set_model(window.model.dataset.copy(), state)

        assert window.model.current_effect == "RR"
        assert window.model.get_global_conf_level() == 90.0
        assert window.cl_label.text() == "Confidence Level: 90.0%"
        assert _metric_action(window, "RR").isChecked()
    finally:
        _close_without_prompt(app, window)


def test_confidence_level_dialog_rejects_represented_100_percent():
    from PyQt5.QtWidgets import QApplication

    import conf_level_dialog

    app = QApplication.instance() or QApplication([])
    dialog = conf_level_dialog.ChangeConfLevelDlg(95.0)
    try:
        spinbox = dialog.conf_level_spinbox

        spinbox.lineEdit().setText("100")
        spinbox.interpretText()

        assert spinbox.maximum() == 99.9
        assert spinbox.value() == 95.0
        assert dialog.get_value() == 95.0
    finally:
        dialog.close()


def test_dataset_model_rejects_invalid_confidence_levels_without_touching_r(
    monkeypatch,
):
    import launch
    import ma_data_table_model

    app, window = launch.start_automation()
    try:
        calls = []

        def fail_if_called(conf_level):
            calls.append(conf_level)
            raise AssertionError("invalid confidence level reached R multiplier")

        monkeypatch.setattr(
            ma_data_table_model.meta_py_r, "get_mult_from_r", fail_if_called
        )

        for invalid_value in (0, 100, math.inf, math.nan, "not-a-number"):
            with pytest.raises(ValueError, match="greater than 0 and less than 100"):
                window.model.set_conf_level(invalid_value)

        assert calls == []
        assert window.model.get_global_conf_level() == 95.0
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
    import qt_text

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
    window.current_data_unsaved = False
    window.close()
    app.processEvents()
    os.chdir(REPO_ROOT)
