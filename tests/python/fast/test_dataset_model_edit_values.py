import os
import sys

import pytest

pytestmark = pytest.mark.usefixtures("inject_python_boundary")


sys.path.insert(0, os.path.abspath("src"))

from rc_metastudio import r_backend

r_backend.install_r_backend()

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from rc_metastudio import dataset_table_model
from rc_metastudio import analysis_dataset
from rc_metastudio import meta_globals


def _derived_effect_and_ci(analysis_unit, metric, group_comparison):
    value = analysis_unit.get_effect_for_source(
        "derived_preview", metric, group_comparison
    )
    return value.estimate, value.lower, value.upper


def test_workspace_numeric_edit_accepts_dot_and_comma_decimal_without_value_drift():
    model = _diagnostic_model_with_empty_cells()
    model.dataset.add_covariate(
        analysis_dataset.Covariate("Dose", "continuous"), {"Alpha": 0.0}
    )
    model.update_column_indices()
    index = model.index(0, model.columnCount() - 1)

    assert model.setData(index, "1.25") is True
    assert model.dataset.studies[0].covariate_values["Dose"] == 1.25
    assert model.setData(index, "1,25") is True
    assert model.dataset.studies[0].covariate_values["Dose"] == 1.25


def test_workspace_numeric_edit_rejects_ambiguous_decimal_text_without_mutation():
    model = _diagnostic_model_with_empty_cells()
    model.dataset.add_covariate(
        analysis_dataset.Covariate("Dose", "continuous"), {"Alpha": 5.5}
    )
    model.update_column_indices()
    index = model.index(0, model.columnCount() - 1)

    for invalid in ("1,234.5", "NaN", "Infinity"):
        assert model.setData(index, invalid) is False
        assert model.dataset.studies[0].covariate_values["Dose"] == 5.5


def test_raw_data_uses_the_shared_strict_decimal_parser(monkeypatch):
    model = _continuous_model_with_named_study()
    monkeypatch.setattr(model, "update_outcome_if_possible", lambda _row: None)
    index = model.index(0, model.RAW_DATA[0])
    raw_data = (
        model.get_current_analysis_unit_for_study(0)
        .groups[model.current_groups[0]]
        .raw_data
    )

    assert model.setData(index, "1.25") is True
    assert raw_data[0] == 1.25
    assert model.setData(index, "1,25") is True
    assert raw_data[0] == 1.25

    for invalid in ("1,234.5", "NaN", "Infinity"):
        assert model.setData(index, invalid) is False
        assert raw_data[0] == 1.25


def test_direct_outcomes_use_the_shared_strict_decimal_parser(monkeypatch):
    model = _binary_model_with_blank_study()
    model.dataset.studies[0].name = "Alpha"
    monkeypatch.setattr(
        dataset_table_model.r_bridge,
        "binary_convert_scale",
        lambda value, *args, **kwargs: value,
    )
    index = model.index(0, model.OUTCOMES[0])
    analysis_unit = model.get_current_analysis_unit_for_study(0)
    group = model.get_current_group_comparison()

    assert model.setData(index, "1.25") is True
    assert analysis_unit.get_entered_effect_and_ci("OR", group)[0] == 1.25
    assert model.setData(index, "1,25") is True
    assert analysis_unit.get_entered_effect_and_ci("OR", group)[0] == 1.25

    for invalid in ("1,234.5", "NaN", "Infinity"):
        assert model.setData(index, invalid) is False
        assert analysis_unit.get_entered_effect_and_ci("OR", group)[0] == 1.25


def test_workspace_model_rejects_invalid_index_and_unscoped_roles_once():
    model = _diagnostic_model_with_empty_cells()
    errors = []
    model.dataError.connect(errors.append)

    assert model.setData(model.index(-1, -1), "ignored") is False
    assert (
        model.setData(
            model.index(0, model.NAME), "ignored", Qt.ItemDataRole.DisplayRole
        )
        is False
    )
    assert (
        model.setData(
            model.index(0, model.NAME),
            Qt.CheckState.Checked,
            Qt.ItemDataRole.CheckStateRole,
        )
        is False
    )

    assert len(errors) == 3
    assert model.dataset.studies[0].name == "Alpha"


def test_workspace_model_rejects_invalid_headers_and_flags():
    model = _diagnostic_model_with_empty_cells()

    assert model.flags(model.index(-1, -1)) == Qt.ItemFlag.NoItemFlags
    assert (
        model.flags(model.createIndex(model.rowCount(), 0)) == Qt.ItemFlag.NoItemFlags
    )
    assert (
        model.flags(model.createIndex(0, model.columnCount()))
        == Qt.ItemFlag.NoItemFlags
    )
    for section in (-1, model.columnCount()):
        assert model.headerData(section, Qt.Orientation.Horizontal) is None
        assert (
            model.headerData(
                section,
                Qt.Orientation.Horizontal,
                dataset_table_model.WORKSPACE_COLUMN_IDENTITY_ROLE,
            )
            is None
        )
    for section in (-1, model.rowCount()):
        assert model.headerData(section, Qt.Orientation.Vertical) is None


@pytest.mark.parametrize("invalid_kind", ("foreign", "row", "column"))
def test_workspace_model_rejects_non_owned_indexes_and_valid_parents(invalid_kind):
    model = _diagnostic_model_with_empty_cells()
    other_model = _diagnostic_model_with_empty_cells()
    invalid_indexes = {
        "foreign": other_model.index(0, 0),
        "row": model.createIndex(model.rowCount(), 0),
        "column": model.createIndex(0, model.columnCount()),
    }
    invalid = invalid_indexes[invalid_kind]
    roles = (
        Qt.ItemDataRole.DisplayRole,
        Qt.ItemDataRole.EditRole,
        Qt.ItemDataRole.CheckStateRole,
        Qt.ItemDataRole.DecorationRole,
    )

    for role in roles:
        assert model.data(invalid, role) is None
    assert model.flags(invalid) == Qt.ItemFlag.NoItemFlags
    assert model.setData(invalid, "ignored") is False

    parent = model.index(0, model.NAME)
    assert parent.isValid()
    assert model.rowCount(parent) == 0
    assert model.columnCount(parent) == 0
    assert model.index(0, 0, parent).isValid() is False


def test_inclusion_workspace_edit_captures_complete_semantic_state():
    model = _diagnostic_model_with_empty_cells()
    study = model.dataset.studies[0]
    study.include = False
    study.manually_excluded = False
    edits = []
    model.workspaceEditCommitted.connect(edits.append)

    assert (
        model.setData(
            model.index(0, model.INCLUDE_STUDY),
            Qt.CheckState.Checked,
            Qt.ItemDataRole.CheckStateRole,
        )
        is True
    )

    assert len(edits) == 1
    assert edits[0].old_value == dataset_table_model.StudyInclusionState(False, False)
    assert edits[0].new_value == dataset_table_model.StudyInclusionState(True, False)


def test_inclusion_edit_accepts_only_explicit_pyqt6_check_states_and_booleans():
    model = _diagnostic_model_with_empty_cells()
    index = model.index(0, model.INCLUDE_STUDY)

    for value, expected in (
        (Qt.CheckState.Checked, True),
        (Qt.CheckState.Unchecked, False),
        (2, True),
        (0, False),
        (True, True),
        (False, False),
    ):
        assert model.setData(index, value, Qt.ItemDataRole.CheckStateRole) is True
        assert model.dataset.studies[0].include is expected

    for invalid in (Qt.CheckState.PartiallyChecked, 1, "2", None):
        before = model.dataset.studies[0].include
        assert model.setData(index, invalid, Qt.ItemDataRole.CheckStateRole) is False
        assert model.dataset.studies[0].include is before


def test_workspace_edit_emits_one_settled_semantic_payload_and_view_range(monkeypatch):
    model = _binary_model_with_blank_study()
    model.dataset.studies[0].name = "Alpha"
    index = model.index(0, model.RAW_DATA[0])
    edits = []
    changes = []
    model.workspaceEditCommitted.connect(edits.append)
    model.dataChanged.connect(
        lambda top, bottom, roles: changes.append((top, bottom, roles))
    )
    monkeypatch.setattr(model, "update_outcome_if_possible", lambda _row: None)

    assert model.setData(index, "1") is True

    assert len(edits) == 1
    assert len(changes) == 1
    edit = edits[0]
    assert edit.index == index
    assert edit.changed_top_left == model.index(0, model.INCLUDE_STUDY)
    assert edit.changed_bottom_right == model.index(0, model.OUTCOMES[-1])
    assert changes[0][0] == edit.changed_top_left
    assert changes[0][1] == edit.changed_bottom_right
    assert tuple(changes[0][2]) == edit.roles
    assert model.dataset.studies[0].include is False


def _diagnostic_model_with_empty_cells():
    dataset = analysis_dataset.Dataset(is_diagnostic=True)
    study = analysis_dataset.Study(1, name="Alpha", year=None)
    outcome = analysis_dataset.Outcome("Accuracy", meta_globals.DIAGNOSTIC)
    study.add_outcome(outcome)
    dataset.add_study(study)
    dataset.follow_ups_by_outcome["Accuracy"] = {0: "first"}

    model = dataset_table_model.DatasetTableModel(
        dataset=dataset, add_blank_study=False
    )
    model.current_outcome_name = "Accuracy"
    model.current_groups = ["test 1"]
    model.update_column_indices()
    return model


def _binary_model_with_blank_study():
    dataset = analysis_dataset.Dataset()
    blank_study = analysis_dataset.Study(1, name="", year=None, include=False)
    dataset.add_study(blank_study)
    dataset.add_outcome(analysis_dataset.Outcome("Mortality", meta_globals.BINARY))

    model = dataset_table_model.DatasetTableModel(
        dataset=dataset, add_blank_study=False
    )
    model.current_outcome_name = "Mortality"
    model.current_effect = "OR"
    model.current_groups = meta_globals.DEFAULT_GROUP_NAMES
    model.update_column_indices()
    return model


def _model_with_real_study_and_empty_new_entry_row(data_type):
    dataset = analysis_dataset.Dataset(
        is_diagnostic=data_type == meta_globals.DIAGNOSTIC
    )
    study = analysis_dataset.Study(1, name="Alpha", year=2020)
    outcome = analysis_dataset.Outcome("Outcome", data_type)
    dataset.add_study(study)
    dataset.add_outcome(outcome)

    model = dataset_table_model.DatasetTableModel(dataset=dataset, add_blank_study=True)
    model.current_outcome_name = "Outcome"
    model.current_effect = "OR" if data_type == meta_globals.BINARY else "MD"
    model.current_groups = (
        ["test 1"]
        if data_type == meta_globals.DIAGNOSTIC
        else meta_globals.DEFAULT_GROUP_NAMES
    )
    model.update_column_indices()
    return model


def _continuous_model_with_named_study():
    dataset = analysis_dataset.Dataset()
    study = analysis_dataset.Study(1, name="Alpha", year=None)
    dataset.add_study(study)
    dataset.add_outcome(analysis_dataset.Outcome("Score", meta_globals.CONTINUOUS))

    model = dataset_table_model.DatasetTableModel(
        dataset=dataset, add_blank_study=False
    )
    model.current_outcome_name = "Score"
    model.current_effect = "MD"
    model.current_groups = meta_globals.DEFAULT_GROUP_NAMES
    model.update_column_indices()
    return model


def _display_headers(data_type_name, data_type, sub_type, current_effect):
    raw_columns, outcome_columns = (
        dataset_table_model.DatasetTableModel.get_column_indices(
            data_type_name, sub_type
        )
    )
    return [
        dataset_table_model.DatasetTableModel._basic_horizontal_header_data(
            column,
            data_type,
            sub_type,
            raw_columns,
            outcome_columns,
            current_effect,
            meta_globals.DEFAULT_GROUP_NAMES,
        )
        for column in range(
            raw_columns[0] if raw_columns else outcome_columns[0],
            outcome_columns[-1] + 1,
        )
    ]


def test_main_data_grid_display_headers_use_desktop_casing_without_changing_keys():
    assert dataset_table_model.DatasetTableModel.headers == [
        "include",
        "study name",
        "year",
    ]

    base_headers = [
        dataset_table_model.DatasetTableModel._basic_horizontal_header_data(
            column,
            "binary",
            None,
            [3, 4, 5, 6],
            [7, 8, 9],
            "OR",
            meta_globals.DEFAULT_GROUP_NAMES,
        )
        for column in range(3)
    ]
    assert base_headers == ["Include", "Study Name", "Year"]

    assert _display_headers("binary", meta_globals.BINARY, None, "OR") == [
        "Tx A #evts",
        "Tx A #total",
        "Tx B #evts",
        "Tx B #total",
        "OR",
        "Lower",
        "Upper",
    ]
    assert _display_headers("continuous", meta_globals.CONTINUOUS, None, "SMD") == [
        "Tx A N",
        "Tx A Mean",
        "Tx A SD",
        "Tx B N",
        "Tx B Mean",
        "Tx B SD",
        "SMD",
        "Lower",
        "Upper",
    ]
    raw_columns, outcome_columns = (
        dataset_table_model.DatasetTableModel.get_column_indices("continuous", None)
    )
    assert (
        dataset_table_model.DatasetTableModel._basic_horizontal_header_data(
            raw_columns[1],
            meta_globals.CONTINUOUS,
            None,
            raw_columns,
            outcome_columns,
            "SMD",
            ["eBay arm", "control arm"],
        )
        == "eBay arm Mean"
    )
    assert _display_headers(
        "continuous", meta_globals.CONTINUOUS, "generic_effect", "MD"
    ) == [
        "MD",
        "SE",
    ]
    assert _display_headers("diagnostic", meta_globals.DIAGNOSTIC, None, "Sens") == [
        "TP",
        "FN",
        "FP",
        "TN",
        "Sens.",
        "Lower",
        "Upper",
        "Spec.",
        "Lower",
        "Upper",
    ]


def test_empty_editable_cells_return_blank_edit_text():
    model = _diagnostic_model_with_empty_cells()
    analysis_unit = model.get_current_analysis_unit_for_study(0)
    analysis_unit.groups["test 1"].raw_data[0] = None
    model.dataset.add_covariate(analysis_dataset.Covariate("Dose", "continuous"))
    model.update_column_indices()

    editable_columns = [
        model.YEAR,
        model.RAW_DATA[0],
        model.columnCount() - 1,
    ]

    for column in editable_columns:
        value = model.data(model.index(0, column), Qt.ItemDataRole.EditRole)

        assert value == ""


def test_normal_study_cells_do_not_override_view_alternating_row_background():
    model = _continuous_model_with_named_study()

    assert (
        model.data(model.index(0, model.NAME), Qt.ItemDataRole.BackgroundRole) is None
    )
    assert (
        model.data(model.index(0, model.RAW_DATA[0]), Qt.ItemDataRole.BackgroundRole)
        is None
    )
    assert model.data(
        model.index(0, model.OUTCOMES[0]), Qt.ItemDataRole.BackgroundRole
    ) == QColor("#D6A93A")


def test_highlighted_outcome_cells_use_dark_text_for_theme_independent_contrast():
    model = _continuous_model_with_named_study()
    outcome_index = model.index(0, model.OUTCOMES[0])

    assert model.data(outcome_index, Qt.ItemDataRole.BackgroundRole) == QColor(
        "#D6A93A"
    )
    assert model.data(outcome_index, Qt.ItemDataRole.ForegroundRole) == QColor(
        Qt.GlobalColor.black
    )


def test_one_arm_inactive_raw_data_cells_keep_disabled_background():
    model = _continuous_model_with_named_study()
    model.current_effect = "TX Mean"

    assert model.data(
        model.index(0, model.RAW_DATA[3]), Qt.ItemDataRole.BackgroundRole
    ) == QColor(Qt.GlobalColor.gray)
    assert (
        model.data(model.index(0, model.RAW_DATA[0]), Qt.ItemDataRole.BackgroundRole)
        is None
    )


def test_empty_new_entry_row_does_not_render_populated_study_chrome():
    for data_type in (
        meta_globals.BINARY,
        meta_globals.CONTINUOUS,
        meta_globals.DIAGNOSTIC,
    ):
        model = _model_with_real_study_and_empty_new_entry_row(data_type)
        blank_row = 1

        assert (
            model.headerData(
                blank_row, Qt.Orientation.Vertical, Qt.ItemDataRole.DecorationRole
            )
            is None
        )
        assert (
            model.data(
                model.index(blank_row, model.INCLUDE_STUDY),
                Qt.ItemDataRole.CheckStateRole,
            )
            is None
        )

        for column in model.OUTCOMES:
            assert (
                model.data(
                    model.index(blank_row, column), Qt.ItemDataRole.BackgroundRole
                )
                is None
            )


def test_named_new_entry_row_keeps_populated_study_chrome(qapp):
    from rc_metastudio import qt6_resources

    qt6_resources.ensure_application_resources()
    model = _model_with_real_study_and_empty_new_entry_row(meta_globals.BINARY)
    model.dataset.studies[1].name = "Beta"
    model.dataset.studies[1].include = True

    assert (
        model.headerData(
            1, Qt.Orientation.Vertical, Qt.ItemDataRole.DecorationRole
        ).isNull()
        is False
    )
    assert (
        model.data(model.index(1, model.INCLUDE_STUDY), Qt.ItemDataRole.CheckStateRole)
        == Qt.CheckState.Checked
    )
    assert model.data(
        model.index(1, model.OUTCOMES[0]), Qt.ItemDataRole.BackgroundRole
    ) == QColor("#D6A93A")


def test_raw_data_edit_on_placeholder_row_emits_study_name_error():
    model = _diagnostic_model_with_empty_cells()
    errors = []
    model.dataError.connect(errors.append)

    assert model.setData(model.index(1, model.RAW_DATA[0]), "90") is False

    assert errors == ["Please enter a study name before entering study data."]


def test_direct_effect_edit_on_unnamed_study_emits_study_name_error(monkeypatch):
    model = _binary_model_with_blank_study()
    errors = []
    model.dataError.connect(errors.append)
    monkeypatch.setattr(
        dataset_table_model.r_bridge,
        "binary_convert_scale",
        lambda value, *args, **kwargs: value,
    )

    assert model.setData(model.index(0, model.OUTCOMES[0]), "1.5") is False

    study = model.dataset.studies[0]
    analysis_unit = model.get_current_analysis_unit_for_study(0)
    assert errors == ["Please enter a study name before entering study data."]
    assert study.include is False
    assert analysis_unit.get_entered_effect_and_ci(
        "OR", model.get_current_group_comparison()
    ) == (
        None,
        None,
        None,
    )


def test_unnamed_study_cannot_be_manually_included():
    model = _binary_model_with_blank_study()
    errors = []
    model.dataError.connect(errors.append)

    assert model.setData(model.index(0, model.INCLUDE_STUDY), True) is False

    assert errors == ["Please enter a study name before entering study data."]
    assert model.dataset.studies[0].include is False


def test_named_direct_effect_entry_still_auto_includes_study(monkeypatch):
    model = _binary_model_with_blank_study()
    model.dataset.studies[0].name = "Alpha"
    monkeypatch.setattr(
        dataset_table_model.r_bridge,
        "binary_convert_scale",
        lambda value, *args, **kwargs: value,
    )

    assert model.setData(model.index(0, model.OUTCOMES[0]), "1.5") is True
    assert model.setData(model.index(0, model.OUTCOMES[1]), "0.8") is True
    assert model.setData(model.index(0, model.OUTCOMES[2]), "2.8") is True

    assert model.dataset.studies[0].include is True


def test_empty_existing_study_name_emits_study_name_error():
    model = _diagnostic_model_with_empty_cells()
    errors = []
    model.dataError.connect(errors.append)

    assert model.setData(model.index(0, model.NAME), "") is False

    assert errors == ["Please enter a study name before entering study data."]
    assert model.dataset.studies[0].name == "Alpha"


def test_study_name_edit_on_placeholder_row_creates_study():
    model = _diagnostic_model_with_empty_cells()

    assert model.setData(model.index(1, model.NAME), "Beta") is True

    assert model.dataset.studies[1].name == "Beta"
    assert len(model.dataset.studies) == 3
    assert model.dataset.studies[2].name == ""
    assert model.dataset.studies[2].include is False


def test_invalid_continuous_covariate_edit_emits_error_and_preserves_value():
    model = _diagnostic_model_with_empty_cells()
    model.dataset.add_covariate(
        analysis_dataset.Covariate("Dose", "continuous"), {"Alpha": 5.5}
    )
    model.update_column_indices()
    errors = []
    model.dataError.connect(errors.append)
    covariate_index = model.index(0, model.columnCount() - 1)

    assert model.setData(covariate_index, "not numeric") is False

    assert errors == ["Covariate values for continuous covariates need to be numeric."]
    assert model.dataset.studies[0].covariate_values["Dose"] == 5.5


def test_diagnostic_raw_count_edit_accepts_scalar_metric_effects(monkeypatch):
    model = _diagnostic_model_with_empty_cells()
    analysis_unit = model.get_current_analysis_unit_for_study(0)
    group_comparison = model.get_current_group_comparison()
    analysis_unit.groups[group_comparison].raw_data = [19.0, 10.0, 1.0, 81.0]
    errors = []
    model.dataError.connect(errors.append)

    monkeypatch.setattr(
        dataset_table_model.r_bridge,
        "diagnostic_convert_scale",
        lambda value, *args, **kwargs: value,
    )

    def diagnostic_effects_for_study(*args, **kwargs):
        return {
            "Sens": {"calc_scale": 0.75},
            "Spec": {"calc_scale": [0.95, 0.88, 0.99]},
            "PLR": {"calc_scale": [15.0]},
            "NLR": {"calc_scale": [0.25, 0.12, 0.50]},
            "DOR": {"calc_scale": [60.0, 25.0, 120.0]},
        }

    monkeypatch.setattr(
        dataset_table_model.r_bridge,
        "diagnostic_effects_for_study",
        diagnostic_effects_for_study,
    )

    assert model.setData(model.index(0, model.RAW_DATA[0]), "20") is True

    assert errors == []
    assert analysis_unit.groups[group_comparison].raw_data[0] == 20.0
    assert analysis_unit.get_effect_and_ci(
        "Sens", group_comparison, model.get_confidence_multiplier()
    ) == (
        0.75,
        None,
        None,
    )
    assert _derived_effect_and_ci(analysis_unit, "Spec", group_comparison) == (
        0.95,
        0.88,
        0.99,
    )


def test_diagnostic_raw_count_edit_recomputes_sens_spec_confidence_intervals(
    monkeypatch,
):
    model = _diagnostic_model_with_empty_cells()
    analysis_unit = model.get_current_analysis_unit_for_study(0)
    group_comparison = model.get_current_group_comparison()
    analysis_unit.groups[group_comparison].raw_data = [19.0, 10.0, 1.0, 81.0]
    errors = []
    model.dataError.connect(errors.append)

    monkeypatch.setattr(
        dataset_table_model.r_bridge,
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
        dataset_table_model.r_bridge,
        "diagnostic_effects_for_study",
        diagnostic_effects_for_study,
    )

    assert model.setData(model.index(0, model.RAW_DATA[0]), "30") is True

    assert errors == []
    assert _derived_effect_and_ci(analysis_unit, "Sens", group_comparison) == (
        0.750,
        0.588,
        0.873,
    )
    assert _derived_effect_and_ci(analysis_unit, "Spec", group_comparison) == (
        0.988,
        0.919,
        0.998,
    )
    assert all(model.data(model.index(0, col)) != "" for col in model.OUTCOMES)


def test_diagnostic_partial_raw_count_edit_clears_all_derived_metrics(monkeypatch):
    model = _diagnostic_model_with_empty_cells()
    analysis_unit = model.get_current_analysis_unit_for_study(0)
    group_comparison = model.get_current_group_comparison()
    analysis_unit.groups[group_comparison].raw_data = [19.0, 10.0, 1.0, 81.0]
    for metric in meta_globals.DIAGNOSTIC_METRICS:
        analysis_unit.set_effect_and_ci(
            metric,
            group_comparison,
            0.75,
            0.50,
            0.90,
            model.get_confidence_multiplier(),
        )
        analysis_unit.calculate_display_effect_and_ci(
            metric,
            group_comparison,
            lambda value: value,
            confidence_level=model.get_confidence_level(),
            confidence_multiplier=model.get_confidence_multiplier(),
        )
    model.dataset.studies[0].include = True

    monkeypatch.setattr(
        dataset_table_model.r_bridge,
        "diagnostic_convert_scale",
        lambda value, *args, **kwargs: value,
    )

    assert model.setData(model.index(0, model.RAW_DATA[2]), "") is True

    assert analysis_unit.groups[group_comparison].raw_data == [19.0, 10.0, "", 81.0]
    assert model.dataset.studies[0].include is False
    for metric in meta_globals.DIAGNOSTIC_METRICS:
        assert analysis_unit.get_entered_effect_and_ci(metric, group_comparison) == (
            None,
            None,
            None,
        )
        assert analysis_unit.get_display_effect_and_ci(metric, group_comparison) == (
            None,
            None,
            None,
        )


def test_binary_raw_count_edit_accepts_scalar_metric_effect(monkeypatch):
    model = _binary_model_with_blank_study()
    model.dataset.studies[0].name = "Alpha"
    analysis_unit = model.get_current_analysis_unit_for_study(0)
    group_comparison = model.get_current_group_comparison()
    analysis_unit.groups[model.current_groups[0]].raw_data = [3.0, 10.0]
    analysis_unit.groups[model.current_groups[1]].raw_data = [2.0, 10.0]
    errors = []
    model.dataError.connect(errors.append)

    monkeypatch.setattr(
        dataset_table_model.r_bridge,
        "binary_convert_scale",
        lambda value, *args, **kwargs: value,
    )
    monkeypatch.setattr(
        dataset_table_model.r_bridge,
        "effect_for_study",
        lambda *args, **kwargs: {"calc_scale": 0.5},
    )

    assert model.setData(model.index(0, model.RAW_DATA[0]), "4") is True

    assert errors == []
    assert analysis_unit.groups[model.current_groups[0]].raw_data[0] == 4.0
    assert analysis_unit.get_effect_and_ci(
        "OR", group_comparison, model.get_confidence_multiplier()
    ) == (
        0.5,
        None,
        None,
    )


def test_continuous_raw_count_edit_accepts_scalar_metric_effect(monkeypatch):
    model = _continuous_model_with_named_study()
    analysis_unit = model.get_current_analysis_unit_for_study(0)
    group_comparison = model.get_current_group_comparison()
    analysis_unit.groups[model.current_groups[0]].raw_data = [10.0, 5.0, 1.0]
    analysis_unit.groups[model.current_groups[1]].raw_data = [12.0, 4.0, 1.5]
    errors = []
    model.dataError.connect(errors.append)

    monkeypatch.setattr(
        dataset_table_model.r_bridge,
        "continuous_convert_scale",
        lambda value, *args, **kwargs: value,
    )
    monkeypatch.setattr(
        dataset_table_model.r_bridge,
        "continuous_effect_for_study",
        lambda *args, **kwargs: {"calc_scale": 1.25},
    )

    assert model.setData(model.index(0, model.RAW_DATA[1]), "5.5") is True

    assert errors == []
    assert analysis_unit.groups[model.current_groups[0]].raw_data[1] == 5.5
    assert analysis_unit.get_effect_and_ci(
        "MD", group_comparison, model.get_confidence_multiplier()
    ) == (
        1.25,
        None,
        None,
    )


def test_diagnostic_raw_count_edit_rolls_back_when_effect_calculation_fails(
    monkeypatch,
):
    model = _diagnostic_model_with_empty_cells()
    analysis_unit = model.get_current_analysis_unit_for_study(0)
    group_comparison = model.get_current_group_comparison()
    analysis_unit.groups[group_comparison].raw_data = [19.0, 10.0, 1.0, 81.0]
    analysis_unit.set_effect_and_ci(
        "Sens", group_comparison, 0.66, 0.50, 0.80, model.get_confidence_multiplier()
    )
    model.dataset.studies[0].include = True
    errors = []
    model.dataError.connect(errors.append)

    def diagnostic_effects_for_study(*args, **kwargs):
        raise RuntimeError("simulated diagnostic calculation failure")

    monkeypatch.setattr(
        dataset_table_model.r_bridge,
        "diagnostic_effects_for_study",
        diagnostic_effects_for_study,
    )

    assert model.setData(model.index(0, model.RAW_DATA[0]), "20") is False

    assert analysis_unit.groups[group_comparison].raw_data == [19.0, 10.0, 1.0, 81.0]
    assert _derived_effect_and_ci(analysis_unit, "Sens", group_comparison) == (
        0.66,
        0.50,
        0.80,
    )
    assert model.dataset.studies[0].include is True
    assert errors == [
        "Could not compute study effects from the edited raw data: "
        "simulated diagnostic calculation failure"
    ]


def test_effect_normalizer_preserves_triplets_and_expands_scalars():
    effect = dataset_table_model.r_bridge.normalize_effect_result(
        {"calc_scale": 1.25, "display_scale": [1.25, 1.0, 1.5]},
    )
    effects = dataset_table_model.r_bridge.normalize_diagnostic_effects(
        {
            "Sens": {"calc_scale": 0.75},
            "Spec": {"calc_scale": [0.95, 0.88, 0.99]},
            "PLR": {"calc_scale": [15.0]},
        }
    )

    assert effect["calc_scale"] == (1.25, None, None)
    assert effect["display_scale"] == (1.25, 1.0, 1.5)
    assert effects["Sens"]["calc_scale"] == (0.75, None, None)
    assert effects["Spec"]["calc_scale"] == (0.95, 0.88, 0.99)
    assert effects["PLR"]["calc_scale"] == (15.0, None, None)


def test_effect_normalizer_can_require_diagnostic_triplets():
    with pytest.raises(
        ValueError,
        match="Expected calc_scale study effect for Sens to contain 3 values; got scalar",
    ):
        dataset_table_model.r_bridge.normalize_diagnostic_effects(
            {"Sens": {"calc_scale": 0.75}},
            require_triplets=True,
        )

    with pytest.raises(
        ValueError,
        match="Expected calc_scale study effect for Spec to contain 3 values; got 1",
    ):
        dataset_table_model.r_bridge.normalize_diagnostic_effects(
            {"Spec": {"calc_scale": [0.95]}},
            require_triplets=True,
        )
