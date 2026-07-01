import os
import sys
import math

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath("src"))

import pytest


REPO_ROOT = os.getcwd()


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
        reopened = meta_form._load_legacy_pickle(saved_path)

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
        assert shown[-1][1:] == ("Whoops", "Raw data needs to be numeric.")
        assert _cell_text(model, 0, model.RAW_DATA[0]) == ""
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

            def exec_(self):
                return True

        class CovariateNameDialog(object):
            def __init__(self, *args, **kwargs):
                self.group_name_le = QtWidgets.QLineEdit()
                self.group_name_le.setText("Renamed dose")

            def exec_(self):
                return True

        class NewCovariateDialog(object):
            def __init__(self, *args, **kwargs):
                self.covariate_name_le = QtWidgets.QLineEdit()
                self.covariate_name_le.setText("Dose")
                self.datatype_cbo_box = QtWidgets.QComboBox()
                self.datatype_cbo_box.addItem("Continuous")

            def exec_(self):
                return True

        class NewOutcomeDialog(object):
            def __init__(self, *args, **kwargs):
                self.outcome_name_le = QtWidgets.QLineEdit()
                self.outcome_name_le.setText("Recovery")
                self.datatype_cbo_box = QtWidgets.QComboBox()
                self.datatype_cbo_box.addItem("Continuous")

            def exec_(self):
                return True

        class NewGroupDialog(object):
            def __init__(self, *args, **kwargs):
                self.group_name_le = QtWidgets.QLineEdit()
                self.group_name_le.setText("Added group")

            def exec_(self):
                return True

        class NewFollowUpDialog(object):
            def __init__(self, *args, **kwargs):
                self.follow_up_name_le = QtWidgets.QLineEdit()
                self.follow_up_name_le.setText("week 4")

            def exec_(self):
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
        assert window.cl_label.text() == "confidence level: 90.0%"

        window.set_model(window.model.dataset.copy(), state)

        assert window.model.current_effect == "RR"
        assert window.model.get_global_conf_level() == 90.0
        assert window.cl_label.text() == "confidence level: 90.0%"
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


def test_dataset_model_rejects_invalid_confidence_levels_without_touching_r(monkeypatch):
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
            with pytest.raises(
                ValueError, match="greater than 0 and less than 100"
            ):
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


def _metric_action(window, metric):
    for menu_action in window.menuMetric.actions():
        menu = menu_action.menu()
        if menu is None:
            continue
        for action in menu.actions():
            action_data = action.data()
            action_metric = (
                str(action_data.toString())
                if hasattr(action_data, "toString")
                else str(action_data)
            )
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
