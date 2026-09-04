# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qt table model for dataset, outcome, follow-up, and treatment views."""

import copy
from statistics import NormalDist
from dataclasses import dataclass
from functools import cmp_to_key

from PyQt6 import QtCore
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon

from rc_metastudio import calculator_routines as calc_fncs
from rc_metastudio import name_validation, project_adapter, qt_text, workspace_editing
from rc_metastudio.analysis_dataset import Covariate, Dataset, Outcome, Study
from rc_metastudio.dataset_analysis_domain import (
    ensure_analysis_unit,
    has_entered_data,
    has_study_entered_data,
    included_studies_have_effects,
    included_studies_have_raw_data,
    raw_data_is_complete,
    raw_data_is_empty,
)
from rc_metastudio.meta_globals import (
    ALL_METRIC_NAMES,
    BINARY,
    BINARY_METRIC_NAMES,
    BINARY_ONE_ARM_METRICS,
    CONTINUOUS,
    CONTINUOUS_METRIC_NAMES,
    CONTINUOUS_ONE_ARM_METRICS,
    DEFAULT_CONFIDENCE_LEVEL,
    DEFAULT_GROUP_NAMES,
    DIAGNOSTIC,
    DIAGNOSTIC_METRIC_LABELS,
    DIAGNOSTIC_METRICS,
    EMPTY_VALS,
    FACTOR,
    NUM_DIGITS,
    ONE_ARM_METRICS,
    OTHER,
    STR_TO_TYPE_DICT,
    is_a_float,
    is_an_int,
    is_empty,
    validate_confidence_level,
)
from rc_metastudio.workspace_column_identity import (
    WORKSPACE_COLUMN_IDENTITY_ROLE,
    WorkspaceColumnIdentity,
    stable_covariate_identity,
)

# Compatibility export for callers that used to patch the bridge through this
# module. The model itself delegates all bridge calls to ``editing_service``.
r_bridge = workspace_editing.r_bridge

# number of (empty) rows in the spreadsheet to show
# following the last study.
DUMMY_ROWS = 20
STUDY_NAME_REQUIRED_MESSAGE = "Please enter a study name before entering study data."
DISPLAY_LABEL_ACRONYMS = {
    "sd": "SD",
    "se": "SE",
    "tp": "TP",
    "fn": "FN",
    "fp": "FP",
    "tn": "TN",
}
DISPLAY_LABEL_ACRONYMS.update(
    {metric.lower(): metric for metric in ALL_METRIC_NAMES.keys()}
)


def _display_label_token(token):
    if token == "":
        return token
    label = DISPLAY_LABEL_ACRONYMS.get(token.lower())
    if label is not None:
        return label
    if token.startswith("#"):
        return token
    if len(token) == 1:
        return token.upper()
    return token[0].upper() + token[1:]


def _display_label(value):
    if value is None:
        return value
    return " ".join(_display_label_token(token) for token in str(value).split(" "))


def _display_group_label(value):
    if str(value).lower().startswith("tx "):
        return _display_label(value)
    return value


def _raw_data_display_label(group_name, suffix):
    return "{} {}".format(_display_group_label(group_name), _display_label(suffix))


def _item_data(value=None):
    if value is None:
        return None
    return value


def _editable_data(value=None):
    if value is None:
        return ""
    return value


def _to_text_value(value):
    return qt_text.to_native_text(value)


def _to_native_text(value):
    return qt_text.to_native_text(value)


def validate_new_outcome_name(dataset, name):
    return name_validation.validate_unique_name(
        "outcome", name, dataset.get_outcome_names()
    )


def validate_new_group_name(dataset, name):
    return name_validation.validate_unique_name(
        "group", name, dataset.get_group_names()
    )


def validate_new_follow_up_name(dataset, outcome_name, name):
    return name_validation.validate_unique_name(
        "follow-up", name, dataset.get_follow_up_names_for_outcome(outcome_name)
    )


def validate_new_global_follow_up_name(dataset, name):
    return name_validation.validate_unique_name(
        "follow-up", name, dataset.get_follow_up_names()
    )


def validate_new_covariate_name(dataset, name):
    return name_validation.validate_unique_name(
        "covariate", name, dataset.get_covariate_names()
    )


def validate_new_study_name(name):
    return name_validation.validate_required_name("study", name)


def _to_int(value):
    if hasattr(value, "toInt"):
        return value.toInt()
    try:
        return int(value), True
    except (TypeError, ValueError):
        return 0, False


def _to_double(value):
    if hasattr(value, "toDouble"):
        return value.toDouble()
    return qt_text.parse_decimal(value)


def _parse_inclusion(value):
    if isinstance(value, Qt.CheckState):
        return value is Qt.CheckState.Checked, value in (
            Qt.CheckState.Checked,
            Qt.CheckState.Unchecked,
        )
    if type(value) is bool:
        return value, True
    if type(value) is int and value in (0, 2):
        return value == 2, True
    return False, False


@dataclass(frozen=True)
class StudyInclusionState:
    include: bool
    manually_excluded: bool


@dataclass(frozen=True)
class WorkspaceEdit:
    index: QModelIndex
    old_value: object
    new_value: object
    added_study_id: int | None
    changed_top_left: QModelIndex
    changed_bottom_right: QModelIndex
    roles: tuple[int, ...]
    before_workspace_snapshot: tuple[object, object] | None = None


@dataclass(frozen=True)
class _EditTarget:
    study: Study
    column: int
    old_value: object
    data_type: str | None
    outcome_subtype: str | None


class DatasetTableModel(QAbstractTableModel):
    """Expose dataset studies and analysis units through Qt's table model API."""

    workspaceEditCommitted = pyqtSignal(WorkspaceEdit)
    outcomeChanged = pyqtSignal()
    followUpChanged = pyqtSignal()
    dataError = pyqtSignal(str)
    editFocusRequested = pyqtSignal(QModelIndex)
    confLevelChanged = pyqtSignal()
    INCLUDE_STUDY = 0
    NAME, YEAR = [col + 1 for col in range(2)]

    headers = ["include", "study name", "year"]

    dataset: Dataset

    def __init__(
        self, filename="", dataset: Dataset | None = None, add_blank_study=True
    ):
        super().__init__()

        self.editing_service = workspace_editing.WorkspaceEditingService()
        # Kept as a module-level compatibility seam for existing test and
        # plugin code. Calculations go through ``editing_service`` below.
        self.confidence_level = self.set_confidence_level(DEFAULT_CONFIDENCE_LEVEL)

        self.dataset = dataset if dataset is not None else Dataset()
        self.analysis_source_path: str | None = None

        if add_blank_study:
            self.dataset.studies.append(Study(self.max_study_id() + 1))
            self.study_auto_added = self.dataset.studies[-1].id

        self.current_outcome_name = None
        self.current_follow_up_index = 0

        self.group_index_a = 0
        self.group_index_b = 1

        self.update_current_group_names()

        self.update_column_indices()

        # Default binary effect until the active outcome selection provides one.
        self.current_effect = "OR"

        self.COVARIATES = None
        self.currently_displayed_covariates = []

        self.LABELS = None

        self.NUM_DIGITS = NUM_DIGITS
        self.dirty = False

    def reset_model(self):
        self.beginResetModel()
        self.endResetModel()

    def _reject_edit(self, msg):
        self.last_data_error = msg
        self.dataError.emit(msg)
        return False

    def _study_name_is_blank(self, study):
        return qt_text.is_blank(study.name)

    def _value_is_empty(self, value):
        return value in EMPTY_VALS

    def _analysis_unit_has_entered_data(self, analysis_unit):
        return has_entered_data(analysis_unit)

    def _study_has_entered_data(self, row):
        if row < 0 or row >= len(self.dataset):
            return False
        return has_study_entered_data(self.dataset.studies[row])

    def _edit_requires_named_study(self, column, value):
        if column == self.NAME:
            return False
        if column == self.INCLUDE_STUDY:
            included, valid = _parse_inclusion(value)
            return valid and included
        if column == self.YEAR:
            return False

        value_is_blank = qt_text.is_blank(value)
        if self.current_outcome_name is not None and column in self.RAW_DATA:
            return not value_is_blank
        if column in self.OUTCOMES:
            return not value_is_blank
        if self.OUTCOMES and column > max(self.OUTCOMES):
            return not value_is_blank
        return False

    def set_current_metric(self, metric):
        self.current_effect = metric

    def update_current_outcome(self):
        outcome_names = self.dataset.get_outcome_names()
        self.current_outcome_name = outcome_names[0] if len(outcome_names) > 0 else None
        self.reset_model()

    def update_current_time_points(self):
        if self.current_outcome_name is not None:
            self.current_follow_up_index = list(
                self.dataset.follow_ups_by_outcome[self.current_outcome_name].keys()
            )[0]
        else:
            self.current_follow_up_index = 0
        self.reset_model()

    def update_current_group_names(self):
        group_names = self.dataset.get_group_names()
        n_groups = len(group_names)
        if n_groups > 1:
            self.group_index_a = self.group_index_a % n_groups
            self.group_index_b = self.group_index_b % n_groups
            while self.group_index_a == self.group_index_b:
                self._next_group_indices(group_names)
            self.current_groups = [
                group_names[self.group_index_a],
                group_names[self.group_index_b],
            ]
        else:
            if not self.is_diagnostic():
                self.current_groups = DEFAULT_GROUP_NAMES
            else:
                self.current_groups = ["test 1"]
        self.previous_groups = self.current_groups
        self.reset_model()

    def update_column_indices(self):
        current_data_type = self.get_current_outcome_type()
        outcome_subtype = self.get_current_outcome_subtype()

        self.RAW_DATA, self.OUTCOMES = self.get_column_indices(
            current_data_type, outcome_subtype
        )

    @staticmethod
    def get_column_indices(data_type, sub_type):
        """Return column indices without constructing a table model."""
        raws, outcomes = [], []

        # The first three columns are include, study name, and year.
        offset = 3
        if data_type == "binary":
            raws = [col + offset for col in range(4)]
            outcomes = [7, 8, 9]
        elif data_type == "continuous":
            raws = [col + offset for col in range(6)]
            outcomes = [9, 10, 11]
            if sub_type == "generic_effect":  # generic effect and se
                raws = []
                outcomes = [offset, offset + 1]  # effect and se
        else:  # diagnostic
            raws = [col + offset for col in range(4)]
            outcomes = [7, 8, 9, 10, 11, 12]  # sensitivity & specificity

        return raws, outcomes

    def format_float(self, float_var, num_digits=None):
        """This method assumes the input can be cast to a float!"""
        float_var = float(float_var)
        precision = num_digits or self.NUM_DIGITS
        return f"{float_var:.{precision}f}"

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """Implements the required QTTableModel data method. There is a lot of switching on
        role/index/datatype here, but this seems consistent with the QT paradigm (see
        Summerfield's book)
        """
        if (
            not index.isValid()
            or index.model() is not self
            or not 0 <= index.row() < self.rowCount()
            or not 0 <= index.column() < self.columnCount()
        ):
            return None

        precise_digits = 12
        num_digits = None

        if not index.isValid() or not (0 <= index.row() < len(self.dataset)):
            return _item_data()
        study = self.dataset.studies[index.row()]
        current_data_type = self.dataset.get_outcome_type(self.current_outcome_name)
        outcome_subtype = self.dataset.get_outcome_subtype(self.current_outcome_name)
        column = index.column()

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if column == self.NAME:
                return _item_data(_editable_data(study.name))
            elif column == self.YEAR:
                if study.year in (None, "", 0):
                    return _item_data("")
                else:
                    return _item_data(study.year)
            elif self.current_outcome_name is not None and column in self.RAW_DATA:
                adjusted_index = column - 3
                if self.current_outcome_name in study.analysis_units_by_outcome:
                    analysis_unit = self.get_current_analysis_unit_for_study(
                        index.row()
                    )
                    current_raw_data = analysis_unit.get_raw_data_for_groups(
                        self.current_groups
                    )
                    if len(current_raw_data) > adjusted_index:
                        val = current_raw_data[adjusted_index]
                        if val == "" or val is None:
                            return _item_data("")
                        try:
                            sample_size_columns = (
                                self.RAW_DATA[0],
                                self.RAW_DATA[3],
                            )

                            if (
                                current_data_type == CONTINUOUS
                                and column not in sample_size_columns
                            ):
                                if role == Qt.ItemDataRole.EditRole:
                                    num_digits = precise_digits
                                return _item_data(
                                    str(self.format_float(val, num_digits=num_digits))
                                )
                            else:
                                return _item_data(round(val, self.NUM_DIGITS))
                        except (TypeError, ValueError):
                            return _item_data(_to_native_text(val))
                    else:
                        return _item_data("")
                else:
                    return _item_data("")
            elif (
                self.current_outcome_name is not None
                and self.get_current_follow_up_name() is not None
                and column in self.OUTCOMES
            ):
                if role == Qt.ItemDataRole.EditRole:
                    num_digits = precise_digits

                group_comparison = self.get_current_group_comparison()
                outcome_index = column - self.OUTCOMES[0]
                outcome_val = None
                analysis_unit = self.get_current_analysis_unit_for_study(index.row())

                if not self.is_diagnostic():
                    effect = self.current_effect

                    if (
                        current_data_type == CONTINUOUS
                        and outcome_subtype == "generic_effect"
                    ):
                        display_effect_and_error = (
                            analysis_unit.get_display_effect_and_se(
                                effect, group_comparison
                            )
                        )
                        outcome_val = display_effect_and_error[outcome_index]
                    else:
                        display_effect_and_interval = (
                            analysis_unit.get_display_effect_and_ci(
                                effect, group_comparison
                            )
                        )
                        outcome_val = display_effect_and_interval[outcome_index]

                    if outcome_val is None:
                        return _item_data("")
                    return _item_data(
                        self.format_float(outcome_val, num_digits=num_digits)
                    )
                else:
                    # Diagnostic tables always show sensitivity and specificity
                    # rather than one current effect, so parse
                    # out the estimates and CIs for these manually here.
                    m_str = "Sens"
                    if column in self.OUTCOMES[3:]:
                        m_str = "Spec"

                    display_effect_and_interval = (
                        analysis_unit.get_display_effect_and_ci(m_str, group_comparison)
                    )
                    outcome_val = display_effect_and_interval[outcome_index % 3]

                    if outcome_val is None:
                        return _item_data("")

                    # Sensitivity and specificity have historically been
                    # displayed to three decimals. Preserve that presentation
                    # contract without rounding the stored calculation values.
                    diagnostic_digits = num_digits if num_digits is not None else 3
                    return _item_data(
                        self.format_float(outcome_val, num_digits=diagnostic_digits)
                    )

            elif column != self.INCLUDE_STUDY and column > max(self.OUTCOMES):
                # here the column is to the right of the outcomes (and not the 0th, or
                # 'include study' column), and thus must correspond to a covariate.
                covariate = self.get_covariate_for_column(column)
                if covariate is None:
                    return _item_data("")

                covariate_name = covariate.name
                cov_value = (
                    study.covariate_values[covariate_name]
                    if covariate_name in study.covariate_values
                    else None
                )
                if cov_value is None:
                    cov_value = ""

                if cov_value != "" and covariate.data_type == CONTINUOUS:
                    return _item_data(
                        self.format_float(cov_value, num_digits=num_digits)
                    )
                else:
                    # factor
                    return _item_data(_to_native_text(cov_value))
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return _item_data(
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            )
        elif role == Qt.ItemDataRole.CheckStateRole:
            # this is where we deal with the inclusion/exclusion of studies
            if column == self.INCLUDE_STUDY and self._study_has_entered_data(
                index.row()
            ):
                checked_state = Qt.CheckState.Unchecked
                if index.row() < self.rowCount() - 1 and study.include:
                    checked_state = Qt.CheckState.Checked
                return _item_data(checked_state)
        elif role == Qt.ItemDataRole.BackgroundRole:
            row_has_entered_data = self._study_has_entered_data(index.row())
            if row_has_entered_data and column in self.OUTCOMES:
                return _item_data(QColor("#D6A93A"))
            elif (
                row_has_entered_data
                and column in self.RAW_DATA[len(self.RAW_DATA) // 2 :]
                and self.current_effect in ONE_ARM_METRICS
            ):
                return _item_data(QColor(Qt.GlobalColor.gray))
        elif role == Qt.ItemDataRole.ForegroundRole:
            row_has_entered_data = self._study_has_entered_data(index.row())
            if row_has_entered_data and column in self.OUTCOMES:
                return _item_data(QColor(Qt.GlobalColor.black))

        return _item_data()

    def get_current_group_comparison(self):
        # we have to build a key (string) here to index into the
        # correct outcome in the meta-analytic unit. the protocol is
        # as follows. if we are dealing with a two group outcome,
        # then the string is:
        #    tx A-tx B
        # A one-group outcome uses:
        #    tx A
        if self.current_effect in ONE_ARM_METRICS:
            group_comparison = self.current_groups[0]
        else:
            group_comparison = "-".join(self.current_groups)
        return group_comparison

    def _verify_raw_data(self, s, col, data_type, index_of_s=None):
        def as_int(value):
            return int(float(value))

        # ignore blank entries
        if qt_text.is_blank(s):
            return True, None

        if not is_a_float(s):
            return False, "Raw data needs to be numeric."

        if data_type in (BINARY, DIAGNOSTIC):
            if not is_an_int(s):
                return (
                    False,
                    "Expected a whole number (count), but a decimal value was entered.",
                )
            if as_int(s) < 0:
                return False, "Counts cannot be negative."

        # Event counts cannot exceed the matching group sample sizes.
        msg = "Number of events cannot be greater than number of samples."
        if index_of_s is None:
            raise ValueError("Raw-data validation requires a model index")
        (row, col) = (index_of_s.row(), index_of_s.column())
        if data_type == BINARY:
            if col in [3, 5]:  # col is TxA or TxB
                sample_count = _to_text_value(self.data(self.index(row, col + 1)))
                if is_an_int(sample_count):
                    if as_int(s) > as_int(sample_count):
                        return False, msg
            elif col in [4, 6]:  # col is N_A or N_B
                event_count = _to_text_value(self.data(self.index(row, col - 1)))
                if is_an_int(event_count):
                    if as_int(s) < as_int(event_count):
                        return False, msg

        if data_type == CONTINUOUS:
            if float(s) <= 0:
                if col in [3, 6]:
                    return False, "Count cannot be zero or negative"
                if col in [5, 8]:
                    return False, "Standard Deviation cannot be zero or negative"

        return True, None

    def _verify_outcome_data(self, s, col, row, data_type):
        outcome_subtype = self.dataset.get_outcome_subtype(self.current_outcome_name)

        if not is_a_float(s):
            return False, "Outcomes must be numeric."

        analysis_unit = self.get_current_analysis_unit_for_study(row)
        group_comparison = self.get_current_group_comparison()

        n1 = None
        if self.current_effect == "PFT":
            _e1, n1, _e2, _n2 = self.get_current_raw_data_for_study(study_index=row)

        binary_display_scale = self._get_conv_to_display_scale(
            data_type=BINARY, effect=self.current_effect, n1=n1
        )
        continuous_display_scale = self._get_conv_to_display_scale(
            data_type=CONTINUOUS, effect=self.current_effect
        )

        previous_estimate, previous_lower, previous_upper = None, None, None
        if data_type in [BINARY, CONTINUOUS]:
            previous_estimate, previous_lower, previous_upper = (
                analysis_unit.get_effect_and_ci(
                    self.current_effect,
                    group_comparison,
                    self.get_confidence_multiplier(),
                )
            )
        if data_type == BINARY:
            previous_estimate, previous_lower, previous_upper = [
                binary_display_scale(x)
                for x in [previous_estimate, previous_lower, previous_upper]
            ]
        elif data_type == CONTINUOUS:
            previous_estimate, previous_lower, previous_upper = [
                continuous_display_scale(x)
                for x in [previous_estimate, previous_lower, previous_upper]
            ]
        elif data_type == DIAGNOSTIC:
            m_str = "Sens" if col in self.OUTCOMES[:3] else "Spec"
            previous_estimate, previous_lower, previous_upper = (
                analysis_unit.get_effect_and_ci(
                    m_str, group_comparison, self.get_confidence_multiplier()
                )
            )
            diagnostic_display_scale = self._get_conv_to_display_scale(
                data_type=DIAGNOSTIC, effect=m_str
            )
            previous_estimate, previous_lower, previous_upper = [
                diagnostic_display_scale(x)
                for x in [previous_estimate, previous_lower, previous_upper]
            ]

        # here we check if there is raw data for this study;
        # if there is, we don't allow entry of outcomes
        raw_data = self.get_current_raw_data_for_study(row)

        if not all([is_empty(s_i) for s_i in raw_data]):
            # Treat tiny floating-point differences as unchanged so tabbing
            # through calculated cells does not trigger unnecessary warnings.
            # for the last 'raw data' column.
            d = dict(
                list(
                    zip(
                        self.OUTCOMES,
                        [previous_estimate, previous_lower, previous_upper],
                    )
                )
            )
            new_val = float(s)
            previously_was_none = d[col] is None
            delta = None
            if previously_was_none:
                # then it was previously not set;
                # go ahead and let the user override.
                delta = float("-inf")
            else:
                delta = abs(new_val - d[col])
            epsilon = 10e-6
            if delta > epsilon:
                return (
                    False,
                    """You have already entered raw data for this study. If you want to enter the outcome directly, delete the raw data first.""",
                )

        if qt_text.is_blank(s):
            # in this case, they've deleted a value
            # (i.e., left it blank) -- this is OK.
            return True, None
        if self.current_effect in ("OR", "RR"):
            if float(s) < 0:
                return False, "Ratios cannot be negative."

        # figure out why type of column we are in
        fields = ["est", "lower", "upper"]
        if data_type == DIAGNOSTIC:
            fields.extend(fields[:])
        col_to_type = dict(list(zip(self.OUTCOMES, fields)))
        val_str = col_to_type[col]

        if outcome_subtype == "generic_effect":
            if col == self.OUTCOMES[1]:  # se column
                if float(s) < 0:
                    return False, "Standard Error cannot be negative"
        else:

            def is_between_bounds(
                est=previous_estimate, low=previous_lower, high=previous_upper
            ):
                return calc_fncs.between_bounds(est=est, low=low, high=high)

            good_result = None
            msg = ""
            if val_str == "est":
                (good_result, msg) = is_between_bounds(est=float(s))
            elif val_str == "lower":
                (good_result, msg) = is_between_bounds(low=float(s))
            elif val_str == "upper":
                (good_result, msg) = is_between_bounds(high=float(s))
            assert good_result is not None, (
                "Why don't we have a result for what outcome we're in?"
            )
            if not good_result:
                return False, msg

        return True, None

    def _verify_year(self, s):
        if qt_text.is_blank(s):
            return True, None

        if not is_an_int(s):
            return False, "Years need to be integers."

        return True, None

    def _edit_year(self, study, value):
        year_ok, msg = self._verify_year(_to_text_value(value))
        if not year_ok:
            self._reject_edit(msg)
            return False
        study.year = _to_int(value)[0]
        return True

    def _edit_raw_data(self, index, value, study, data_type):
        normalized_value, numeric_valid = qt_text.normalize_decimal_text(value)
        if not numeric_valid:
            self._reject_edit("Raw data needs to be numeric.")
            return False
        data_ok, msg = self._verify_raw_data(
            normalized_value, index.column(), data_type, index
        )
        if not data_ok:
            self._reject_edit(msg)
            return False

        column = index.column()
        adjust_by = 3
        group_name = self.current_groups[0]
        if data_type == BINARY and column in self.RAW_DATA[2:]:
            adjust_by += 2
            group_name = self.current_groups[1]
        elif data_type == CONTINUOUS and column in self.RAW_DATA[3:]:
            adjust_by += 3
            group_name = self.current_groups[1]

        live_analysis_unit = self.get_current_analysis_unit_for_study(index.row())
        analysis_unit = copy.deepcopy(live_analysis_unit)
        old_include = study.include
        old_manually_excluded = study.manually_excluded
        double_value, converted_ok = _to_double(normalized_value)
        analysis_unit.groups[group_name].raw_data[column - adjust_by] = (
            double_value if converted_ok else ""
        )
        follow_up = self.get_current_follow_up_name()
        study.replace_analysis_unit(self.current_outcome_name, follow_up, analysis_unit)
        try:
            self.update_outcome_if_possible(index.row())
        except Exception as exc:
            study.replace_analysis_unit(
                self.current_outcome_name, follow_up, live_analysis_unit
            )
            study.include = old_include
            study.manually_excluded = old_manually_excluded
            self._reject_edit(
                "Could not compute study effects from the edited raw data: %s" % exc
            )
            return False
        live_analysis_unit.adopt_calculated_state(analysis_unit)
        study.replace_analysis_unit(
            self.current_outcome_name, follow_up, live_analysis_unit
        )
        return True

    def _edit_covariate(self, study, column, value):
        cov = self.get_covariate_for_column(column)
        if cov.data_type == FACTOR:
            new_value = _to_native_text(value)
        elif qt_text.is_blank(value):
            new_value = None
        else:
            new_value, converted_ok = _to_double(value)
            if not converted_ok:
                self._reject_edit(
                    "Covariate values for continuous covariates need to be numeric."
                )
                return False
        study.set_covariate_value(cov, new_value)
        return True

    def _edit_outcome(
        self, index, value, data_type, subtype, group_comparison, import_csv
    ):
        column = index.column()
        row = index.row()
        if qt_text.is_blank(value):
            display_scale_val = None
            converted_ok = False
        else:
            normalized_value, numeric_valid = qt_text.normalize_decimal_text(value)
            if not numeric_valid:
                self._reject_edit("Outcomes must be numeric.")
                return False
            data_ok, msg = self._verify_outcome_data(
                normalized_value, column, row, data_type
            )
            if not data_ok and not import_csv:
                self._reject_edit(msg)
                return False
            display_scale_val, converted_ok = _to_double(normalized_value)

        if display_scale_val is not None and not converted_ok:
            return True
        if not self.is_diagnostic():
            n1 = None
            if self.current_effect == "PFT":
                _e1, n1, _e2, _n2 = self.get_current_raw_data_for_study(study_index=row)
            calculation_scale_value = self._get_calc_scale_value(
                display_scale_val,
                data_type=data_type,
                effect=self.current_effect,
                n1=n1,
            )
            analysis_unit = self.get_current_analysis_unit_for_study(row)
            if subtype == "generic_effect":
                if column == self.OUTCOMES[0]:
                    analysis_unit.set_effect(
                        self.current_effect, group_comparison, calculation_scale_value
                    )
                elif column == self.OUTCOMES[1]:
                    analysis_unit.set_standard_error(
                        self.current_effect, group_comparison, calculation_scale_value
                    )
            else:
                if column == self.OUTCOMES[0]:
                    analysis_unit.set_effect(
                        self.current_effect, group_comparison, calculation_scale_value
                    )
                elif column == self.OUTCOMES[1]:
                    analysis_unit.set_lower(
                        self.current_effect, group_comparison, calculation_scale_value
                    )
                else:
                    analysis_unit.set_upper(
                        self.current_effect, group_comparison, calculation_scale_value
                    )
                se = (
                    analysis_unit.calculate_se_if_possible(
                        self.current_effect,
                        group_comparison,
                        confidence_multiplier=self.confidence_multiplier,
                    )
                    if None
                    not in analysis_unit.get_entered_effect_and_ci(
                        self.current_effect, group_comparison
                    )
                    else None
                )
                analysis_unit.set_standard_error(
                    self.current_effect, group_comparison, se
                )
            analysis_unit.calculate_display_effect_and_ci(
                self.current_effect,
                group_comparison,
                self._get_conv_to_display_scale(
                    data_type=data_type, effect=self.current_effect, n1=n1
                ),
                confidence_level=self.get_confidence_level(),
                confidence_multiplier=self.confidence_multiplier,
            )
        else:
            analysis_unit = self.get_current_analysis_unit_for_study(row)
            metric = "Spec" if column in self.OUTCOMES[3:] else "Sens"
            calculation_scale_value = self._get_calc_scale_value(
                display_scale_val, data_type=data_type, effect=metric
            )
            if column in (self.OUTCOMES[0], self.OUTCOMES[3]):
                analysis_unit.set_effect(
                    metric, group_comparison, calculation_scale_value
                )
            elif column in (self.OUTCOMES[1], self.OUTCOMES[4]):
                analysis_unit.set_lower(
                    metric, group_comparison, calculation_scale_value
                )
            else:
                analysis_unit.set_upper(
                    metric, group_comparison, calculation_scale_value
                )
            analysis_unit.calculate_display_effect_and_ci(
                metric,
                group_comparison,
                self._get_conv_to_display_scale(data_type=data_type, effect=metric),
                confidence_level=self.get_confidence_level(),
                confidence_multiplier=self.confidence_multiplier,
            )
        return True

    def _inclusion_value_for_edit(self, index, value, role):
        if role not in (Qt.ItemDataRole.EditRole, Qt.ItemDataRole.CheckStateRole):
            self._reject_edit("That data role cannot edit a workspace cell.")
            return None, False
        if role == Qt.ItemDataRole.CheckStateRole and (
            not index.isValid()
            or index.model() is not self
            or index.column() != self.INCLUDE_STUDY
        ):
            self._reject_edit("Check state applies only to study inclusion.")
            return None, False

        inclusion_value = None
        if (
            index.isValid()
            and index.model() is self
            and index.column() == self.INCLUDE_STUDY
        ):
            inclusion_value, inclusion_valid = _parse_inclusion(value)
            if not inclusion_valid:
                self._reject_edit("Study inclusion must be checked or unchecked.")
                return None, False
        return inclusion_value, True

    def _prepare_edit_target(self, index, value, allow_empty_names):
        if not (
            index.isValid()
            and index.model() is self
            and 0 <= index.row() < self.rowCount()
            and 0 <= index.column() < self.columnCount()
        ):
            self._reject_edit("Cannot edit that cell.")
            return None

        column = index.column()
        old_value = (
            StudyInclusionState(
                include=bool(self.dataset.studies[index.row()].include),
                manually_excluded=bool(
                    self.dataset.studies[index.row()].manually_excluded
                ),
            )
            if index.row() < len(self.dataset) and column == self.INCLUDE_STUDY
            else self.data(index, Qt.ItemDataRole.EditRole)
        )

        if index.row() >= len(self.dataset):
            if column != self.NAME:
                self._reject_edit(STUDY_NAME_REQUIRED_MESSAGE)
                return None

            name = _to_text_value(value)
            if name == "" and not allow_empty_names:
                self._reject_edit(STUDY_NAME_REQUIRED_MESSAGE)
                return None

            while len(self.dataset) <= index.row():
                self.dataset.add_study(Study(self.max_study_id() + 1))

        study = self.dataset.studies[index.row()]
        if (
            not allow_empty_names
            and self._study_name_is_blank(study)
            and self._edit_requires_named_study(column, value)
        ):
            self._reject_edit(STUDY_NAME_REQUIRED_MESSAGE)
            return None
        return _EditTarget(
            study=study,
            column=column,
            old_value=old_value,
            data_type=self.dataset.get_outcome_type(self.current_outcome_name),
            outcome_subtype=self.dataset.get_outcome_subtype(self.current_outcome_name),
        )

    def _edit_study_name(self, index, study, value, allow_empty_names):
        name = _to_text_value(value)
        if name == "" and not allow_empty_names:
            self._reject_edit(STUDY_NAME_REQUIRED_MESSAGE)
            return False, None
        if name in self.dataset.get_study_names() and name != study.name:
            self._reject_edit("Duplicate study names not allowed")
            return False, None

        added_study_id = None
        if index.row() == self.rowCount() - DUMMY_ROWS - 1 and name != "":
            new_study = Study(self.max_study_id() + 1)
            new_study.include = False
            self.dataset.add_study(new_study)
            added_study_id = int(new_study.id)
            self.study_auto_added = added_study_id
            self.reset_model()
            self.editFocusRequested.emit(self.index(index.row(), index.column() + 1))
        study.name = name
        return True, added_study_id

    def _apply_edit(
        self,
        index,
        value,
        target,
        inclusion_value,
        import_csv,
        allow_empty_names,
    ):
        column = target.column
        study = target.study
        if column == self.NAME:
            return self._edit_study_name(index, study, value, allow_empty_names)
        if column == self.YEAR:
            if not self._edit_year(study, value):
                return False, None
        elif self.current_outcome_name is not None and column in self.RAW_DATA:
            if not self._edit_raw_data(index, value, study, target.data_type):
                return False, None
        elif column in self.OUTCOMES:
            if not self._edit_outcome(
                index,
                value,
                target.data_type,
                target.outcome_subtype,
                self.get_current_group_comparison(),
                import_csv,
            ):
                return False, None
        elif column == self.INCLUDE_STUDY:
            study.include = inclusion_value
            study.manually_excluded = not inclusion_value
        else:
            if not self._edit_covariate(study, column, value):
                return False, None
        return True, None

    def _update_inclusion_after_edit(self, index, target):
        if (
            self.is_diagnostic()
            or target.column == self.INCLUDE_STUDY
            or self.current_outcome_name is None
        ):
            return
        effect = self.get_current_analysis_unit_for_study(index.row()).entered_effects[
            self.current_effect
        ][self.get_current_group_comparison()]
        self.editing_service.update_inclusion_after_edit(
            target.study,
            diagnostic=self.is_diagnostic(),
            inclusion_column=target.column == self.INCLUDE_STUDY,
            outcome_selected=self.current_outcome_name is not None,
            effect=effect,
            data_type=target.data_type,
            outcome_subtype=target.outcome_subtype,
        )

    def _publish_workspace_edit(
        self, index, target, added_study_id, before_workspace_snapshot
    ):
        changed_first_column = target.column
        changed_last_column = target.column
        roles = [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]
        if target.column == self.INCLUDE_STUDY:
            roles = [Qt.ItemDataRole.CheckStateRole]
        elif target.column in self.RAW_DATA or target.column in self.OUTCOMES:
            changed_first_column = self.INCLUDE_STUDY
            changed_last_column = max(self.OUTCOMES or [target.column])
            roles = [
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.EditRole,
                Qt.ItemDataRole.CheckStateRole,
                Qt.ItemDataRole.BackgroundRole,
            ]
        changed_top_left = self.index(index.row(), changed_first_column)
        changed_bottom_right = self.index(index.row(), changed_last_column)
        role_values = [int(item) for item in roles]
        self.dataChanged.emit(changed_top_left, changed_bottom_right, role_values)

        new_value = (
            StudyInclusionState(
                include=bool(target.study.include),
                manually_excluded=bool(target.study.manually_excluded),
            )
            if target.column == self.INCLUDE_STUDY
            else self.data(index, Qt.ItemDataRole.EditRole)
        )
        self.workspaceEditCommitted.emit(
            WorkspaceEdit(
                index=QModelIndex(index),
                old_value=target.old_value,
                new_value=new_value,
                added_study_id=added_study_id,
                changed_top_left=QModelIndex(changed_top_left),
                changed_bottom_right=QModelIndex(changed_bottom_right),
                roles=tuple(role_values),
                before_workspace_snapshot=before_workspace_snapshot,
            )
        )

    def setData(
        self,
        index,
        value,
        role=Qt.ItemDataRole.EditRole,
        import_csv=False,
        allow_empty_names=False,
    ):
        """Apply one workspace edit requested through Qt's table-model interface."""
        self.last_data_error = None
        inclusion_value, valid = self._inclusion_value_for_edit(index, value, role)
        if not valid:
            return False
        target = self._prepare_edit_target(index, value, allow_empty_names)
        if target is None:
            return False
        before_workspace_snapshot = (
            project_adapter.dataset_to_project(copy.deepcopy(self.dataset)),
            project_adapter.model_to_state(self),
        )
        with self.editing_service.transaction(self.dataset) as transaction:
            applied, added_study_id = self._apply_edit(
                index,
                value,
                target,
                inclusion_value,
                import_csv,
                allow_empty_names,
            )
            if not applied:
                transaction.rollback()
                return False
            self._update_inclusion_after_edit(index, target)
            transaction.commit()
        self._publish_workspace_edit(
            index, target, added_study_id, before_workspace_snapshot
        )
        return True

    @staticmethod
    def _basic_horizontal_header_data(
        section,
        data_type,
        sub_type,
        raw_columns,
        outcome_columns,
        current_effect,
        groups,
        outcome_is_present=True,
    ):
        """Return basic header data without constructing a table model."""
        if section == DatasetTableModel.INCLUDE_STUDY:
            return _item_data(
                _display_label(
                    DatasetTableModel.headers[DatasetTableModel.INCLUDE_STUDY]
                )
            )
        elif section == DatasetTableModel.NAME:
            return _item_data(
                _display_label(DatasetTableModel.headers[DatasetTableModel.NAME])
            )
        elif section == DatasetTableModel.YEAR:
            return _item_data(
                _display_label(DatasetTableModel.headers[DatasetTableModel.YEAR])
            )
        # Raw-data columns display at most two groups.
        elif outcome_is_present and section in raw_columns:
            current_group = groups[0]
            if data_type == BINARY:
                if section in raw_columns[2:]:
                    current_group = groups[1]

                if section in (raw_columns[0], raw_columns[2]):
                    return _item_data(_raw_data_display_label(current_group, "#evts"))
                else:
                    return _item_data(_raw_data_display_label(current_group, "#total"))
            elif data_type == CONTINUOUS:
                if len(raw_columns) < 6:
                    return _item_data("")

                if sub_type == "generic_effect":
                    return _item_data("")
                else:
                    if section in raw_columns[3:]:
                        current_group = groups[1]
                    if section in (raw_columns[0], raw_columns[3]):
                        return _item_data(_raw_data_display_label(current_group, "N"))
                    elif section in (raw_columns[1], raw_columns[4]):
                        return _item_data(
                            _raw_data_display_label(current_group, "mean")
                        )
                    else:
                        return _item_data(_raw_data_display_label(current_group, "SD"))
            elif data_type == DIAGNOSTIC:
                if section == raw_columns[0]:
                    return _item_data("TP")
                elif section == raw_columns[1]:
                    return _item_data("FN")
                elif section == raw_columns[2]:
                    return _item_data("FP")
                else:
                    return _item_data("TN")

        elif section in outcome_columns:
            if data_type == BINARY:
                if section == outcome_columns[0]:
                    return _item_data(current_effect)
                elif section == outcome_columns[1]:
                    return _item_data("Lower")
                else:
                    return _item_data("Upper")
            elif data_type == CONTINUOUS:
                if sub_type == "generic_effect":
                    if section == outcome_columns[0]:
                        return _item_data(current_effect)
                    if section == outcome_columns[1]:
                        return _item_data("SE")
                else:  # normal case with no outcome_subtype
                    if section == outcome_columns[0]:
                        return _item_data(current_effect)
                    elif section == outcome_columns[1]:
                        return _item_data("Lower")
                    elif section == outcome_columns[2]:
                        return _item_data("Upper")
            elif data_type == DIAGNOSTIC:
                outcome_index = section - outcome_columns[0]
                outcome_headers = [
                    "Sens.",
                    "Lower",
                    "Upper",
                    "Spec.",
                    "Lower",
                    "Upper",
                ]
                return _item_data(outcome_headers[outcome_index])

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if not 0 <= section < self.columnCount():
                return None
        elif orientation == Qt.Orientation.Vertical:
            if not 0 <= section < self.rowCount():
                return None
        else:
            return None

        if (
            orientation == Qt.Orientation.Horizontal
            and role == WORKSPACE_COLUMN_IDENTITY_ROLE
        ):
            return self.workspace_column_identity(section)

        outcome_type = self.dataset.get_outcome_type(self.current_outcome_name)
        outcome_subtype = self.dataset.get_outcome_subtype(self.current_outcome_name)
        length_dataset = len(self.dataset)

        section_is_valid = section < length_dataset
        if role == Qt.ItemDataRole.ToolTipRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                if section == self.INCLUDE_STUDY:
                    return (
                        "Check if you want to include this study in the meta-analysis"
                    )
                elif section == self.NAME:
                    return "Name to identify the study"
                elif section == self.YEAR:
                    return "Year of publication"
                elif self.current_outcome_name is not None and section in self.RAW_DATA:
                    # switch on the outcome type
                    current_group = self.current_groups[0]  # i.e., the first group

                    rename_col_msg = "\nRename group by right-clicking the column header and selecting 'rename group <name>'"
                    sort_msg = "\nSort on this column by right-clicking the column header and selecting 'sort studies by <column>'"
                    if outcome_type == BINARY:
                        if section in self.RAW_DATA[2:]:
                            current_group = self.current_groups[1]

                        if section in (self.RAW_DATA[0], self.RAW_DATA[2]):
                            num_events_msg = (
                                "# of Events in group {0} (numerator)".format(
                                    current_group
                                )
                            )
                            return num_events_msg + rename_col_msg + sort_msg
                        else:
                            subject_count_message = (
                                "# of Subjects in group {0} (numerator)".format(
                                    current_group
                                )
                            )
                            return subject_count_message + rename_col_msg + sort_msg
                    elif outcome_type == CONTINUOUS:
                        # continuous data
                        if outcome_subtype == "generic_effect":
                            # Logic note: generic-effect continuous outcomes do not expose raw data columns.
                            return ""

                        else:  # normal case with no outcome subtype
                            if section in self.RAW_DATA[3:]:
                                current_group = self.current_groups[1]

                            if section in (self.RAW_DATA[0], self.RAW_DATA[3]):
                                subject_count_message = (
                                    "# Subjects in group {0}".format(current_group)
                                )
                                return subject_count_message + rename_col_msg + sort_msg
                            elif section in (self.RAW_DATA[1], self.RAW_DATA[4]):
                                mean_msg = "Mean of group %s" % current_group
                                return mean_msg + rename_col_msg + sort_msg
                            else:
                                sd_msg = (
                                    "Standard Deviation of group %s" % current_group
                                )
                                return sd_msg
                    elif outcome_type == DIAGNOSTIC:
                        if section == self.RAW_DATA[0]:
                            return "# True Positives" + sort_msg
                        elif section == self.RAW_DATA[1]:
                            return "# False Negatives" + sort_msg
                        elif section == self.RAW_DATA[2]:
                            return "# False Positives" + sort_msg
                        else:
                            return "# True Negatives" + sort_msg
                elif section in self.OUTCOMES:
                    lower_msg = "Lower bound of {0:.1%} confidence interval".format(
                        self.confidence_level / 100.0
                    )
                    upper_msg = "Upper bound of {0:.1%} confidence interval\n".format(
                        self.confidence_level / 100.0
                    )
                    se_msg = "Standard Error"

                    if outcome_type == BINARY:
                        # effect size, lower CI, upper CI
                        if section == self.OUTCOMES[0]:
                            return BINARY_METRIC_NAMES[self.current_effect]
                        elif section == self.OUTCOMES[1]:
                            return lower_msg
                        else:
                            return upper_msg
                    elif outcome_type == CONTINUOUS:
                        if outcome_subtype == "generic_effect":
                            if section == self.OUTCOMES[0]:
                                return CONTINUOUS_METRIC_NAMES[self.current_effect]
                            if section == self.OUTCOMES[1]:
                                return se_msg
                        else:  # normal case with no outcome_subtype
                            if section == self.OUTCOMES[0]:
                                return CONTINUOUS_METRIC_NAMES[self.current_effect]
                            elif section == self.OUTCOMES[1]:
                                return lower_msg
                            elif section == self.OUTCOMES[2]:
                                return upper_msg

                    elif outcome_type == DIAGNOSTIC:
                        if section in (self.OUTCOMES[1], self.OUTCOMES[4]):
                            return lower_msg
                        elif section in (self.OUTCOMES[2], self.OUTCOMES[5]):
                            return upper_msg
                        else:  # in metric name
                            if section == self.OUTCOMES[0]:  # Sens
                                return DIAGNOSTIC_METRIC_LABELS["Sens"]
                            elif section == self.OUTCOMES[3]:  # Spec
                                return DIAGNOSTIC_METRIC_LABELS["Spec"]

            else:  # vertical
                if section_is_valid and self._study_has_entered_data(section):
                    return "Use calculator to fill-in missing information"

        if role == Qt.ItemDataRole.DecorationRole:
            if orientation == Qt.Orientation.Vertical:
                if section_is_valid and self._study_has_entered_data(section):
                    return QIcon(":/icons/table/calculator.svg")
                return _item_data()

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return _item_data(
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            )

        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                res = self._basic_horizontal_header_data(
                    section,
                    data_type=outcome_type,
                    sub_type=outcome_subtype,
                    raw_columns=self.RAW_DATA,
                    outcome_columns=self.OUTCOMES,
                    current_effect=self.current_effect,
                    groups=self.current_groups,
                    outcome_is_present=self.current_outcome_name is not None,
                )
                if res:
                    return res
                elif self.current_outcome_name is not None and section > max(
                    self.OUTCOMES
                ):
                    # then the column is to the right of the outcomes, and must
                    # be a covariate.
                    current_covariate = self.get_covariate_for_column(section)
                    if current_covariate is None:
                        return _item_data("")

                    covariate_name = current_covariate.name
                    covariate_type = current_covariate.get_type_str()
                    # Use the initial because the full covariate type does not fit.
                    return _item_data("%s (%s)" % (covariate_name, covariate_type[0]))
                else:
                    return _item_data("")
            else:  # vertical case
                # Vertical headers display one-based row numbers.
                return _item_data(int(section + 1))

        return _item_data()

    def workspace_column_identity(self, section):
        """Return identity independent of mutable labels and column position."""
        fixed = {
            self.INCLUDE_STUDY: "include",
            self.NAME: "study-name",
            self.YEAR: "year",
        }
        if section in fixed:
            return WorkspaceColumnIdentity("fixed", (fixed[section],))

        outcome_type = (
            self.dataset.get_outcome_type(self.current_outcome_name) or "none"
        )
        outcome_subtype = (
            self.dataset.get_outcome_subtype(self.current_outcome_name) or "none"
        )
        if self.current_outcome_name is not None and section in self.RAW_DATA:
            return WorkspaceColumnIdentity(
                "raw", (outcome_type, outcome_subtype, self.RAW_DATA.index(section))
            )
        if self.current_outcome_name is not None and section in self.OUTCOMES:
            return WorkspaceColumnIdentity(
                "outcome",
                (outcome_type, outcome_subtype, self.OUTCOMES.index(section)),
            )

        covariate = self.get_covariate_for_column(section)
        if covariate is not None:
            return WorkspaceColumnIdentity(
                "covariate",
                (stable_covariate_identity(self.dataset, covariate),),
            )
        return WorkspaceColumnIdentity("dataset-column", (section,))

    def flags(self, index):
        if (
            not index.isValid()
            or index.model() is not self
            or not 0 <= index.row() < self.rowCount()
            or not 0 <= index.column() < self.columnCount()
        ):
            return Qt.ItemFlag.NoItemFlags
        elif index.column() == self.INCLUDE_STUDY:
            if not self._study_has_entered_data(index.row()):
                return Qt.ItemFlag(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
            return Qt.ItemFlag(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
            )
        return Qt.ItemFlag(
            QAbstractTableModel.flags(self, index) | Qt.ItemFlag.ItemIsEditable
        )

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.dataset) + DUMMY_ROWS

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return self._get_col_count()

    def get_covariate_for_column(self, table_col_index):
        # Map the table column to a covariate index. Without an outcome, skip
        # the include, study-name, and year columns.
        covariate_index = (
            table_col_index - (self.OUTCOMES[-1] + 1)
            if self.current_outcome_name is not None
            else table_col_index - 3
        )
        try:
            return self.dataset.covariates[covariate_index]
        except IndexError:
            return None

    def get_covariate_names(self):
        return [cov.name for cov in self.dataset.covariates]

    def rename_covariate(self, old_cov_name, new_cov_name):
        old_cov_obj = self.dataset.get_covariate(old_cov_name)
        self.dataset.change_covariate_name(old_cov_obj, new_cov_name)
        self.reset_model()

    def _get_col_count(self):
        """Calculate how many columns to display; this is contingent on the data type,
        amongst other things (e.g., number of covariates).
        """
        num_cols = 3  # we always show study name and year (and include studies)
        if len(self.dataset.get_outcome_names()) > 0:
            num_effect_size_fields = 3  # point estimate, low, high
            outcome_type = self.dataset.get_outcome_type(self.current_outcome_name)
            outcome_subtype = self.dataset.get_outcome_subtype(
                self.current_outcome_name
            )
            if outcome_subtype == "generic_effect":
                num_effect_size_fields = 2  # point estimate, se
            if outcome_type == DIAGNOSTIC:
                # we have two for diagnostic; sensitivity and specifity.
                # we will display the est, lower, and upper for both of these.
                num_effect_size_fields = 6

            num_cols += num_effect_size_fields + self.num_data_cols_for_current_unit()
        # now add the covariates (if any)
        num_cols += len(self.dataset.covariates)
        return num_cols

    def get_ordered_study_ids(self):
        return [study.id for study in self.dataset.studies]

    def add_new_outcome(self, name, data_type, sub_type=None):
        name = validate_new_outcome_name(self.dataset, name)
        if data_type is None:
            raise ValueError("Cannot add an outcome without a data type")
        data_type_key = str(data_type).lower()
        if data_type_key not in STR_TO_TYPE_DICT:
            raise ValueError("Unsupported outcome data type: %r" % data_type)
        data_type = STR_TO_TYPE_DICT[data_type_key]
        self.dataset.add_outcome(Outcome(name, data_type, sub_type=sub_type))

    def remove_outcome(self, outcome_name):
        self.dataset.remove_outcome(outcome_name)

    def add_new_group(self, name):
        name = validate_new_group_name(self.dataset, name)
        self.dataset.add_group(name, self.current_outcome_name)

    def remove_group(self, group_name):
        self.dataset.remove_group(group_name)

    def rename_group(self, old_group_name, new_group_name):
        self.dataset.change_group_name(old_group_name, new_group_name)
        if old_group_name in self.current_groups:
            group_index = self.current_groups.index(old_group_name)
            # now remove the old group from the list of current groups
            self.current_groups.pop(group_index)
            self.current_groups.insert(group_index, new_group_name)
        self.reset_model()

    def add_follow_up_to_current_outcome(self, follow_up_name):
        follow_up_name = validate_new_follow_up_name(
            self.dataset, self.current_outcome_name, follow_up_name
        )
        self.dataset.add_follow_up_to_outcome(self.current_outcome_name, follow_up_name)

    def remove_follow_up_from_outcome(self, follow_up_name, outcome_name):
        self.dataset.remove_follow_up_from_outcome(follow_up_name, outcome_name)

    def add_covariate(
        self, covariate_name, covariate_type, covariate_values=None, stable_id=None
    ):
        covariate_name = validate_new_covariate_name(self.dataset, covariate_name)
        covariate = Covariate(covariate_name, covariate_type, stable_id=stable_id)
        self.dataset.add_covariate(covariate, covariate_values=covariate_values)
        self.reset_model()
        return covariate

    def remove_covariate(self, covariate_name):
        self.dataset.remove_covariate(covariate_name)
        self.reset_model()

    def remove_study(self, an_id):
        self.dataset.studies.pop(an_id)
        self.reset_model()

    def get_name(self):
        return self.dataset.title

    def get_next_outcome_name(self):
        outcomes = self.dataset.get_outcome_names()
        current_index = outcomes.index(self.current_outcome_name)
        next_outcome = (
            outcomes[0]
            if current_index == len(outcomes) - 1
            else outcomes[current_index + 1]
        )
        return next_outcome

    def get_previous_outcome_name(self):
        outcomes = self.dataset.get_outcome_names()
        current_index = outcomes.index(self.current_outcome_name)
        previous_outcome = (
            outcomes[-1] if current_index == 0 else outcomes[current_index - 1]
        )
        return previous_outcome

    def get_next_follow_up(self):
        follow_up_indices = sorted(
            self.dataset.follow_ups_by_outcome[self.current_outcome_name]
        )
        current_position = follow_up_indices.index(self.current_follow_up_index)
        follow_up_index = follow_up_indices[
            (current_position + 1) % len(follow_up_indices)
        ]
        return (
            follow_up_index,
            self.get_follow_up_name_for_t_point(follow_up_index),
        )

    def get_previous_follow_up(self):
        follow_up_indices = sorted(
            self.dataset.follow_ups_by_outcome[self.current_outcome_name]
        )
        current_position = follow_up_indices.index(self.current_follow_up_index)
        follow_up_index = follow_up_indices[current_position - 1]
        return (
            follow_up_index,
            self.get_follow_up_name_for_t_point(follow_up_index),
        )

    def set_current_follow_up_index(self, follow_up_index):
        self.current_follow_up_index = follow_up_index
        self.followUpChanged.emit()
        self.reset_model()

    def set_current_follow_up(self, follow_up_name):
        t_point = self.dataset.follow_ups_by_outcome[self.current_outcome_name].get_key(
            follow_up_name
        )
        self.set_current_follow_up_index(t_point)

    def get_current_follow_up_name(self):
        if len(self.dataset.follow_ups_by_outcome) > 0:
            try:
                return self.dataset.follow_ups_by_outcome[self.current_outcome_name][
                    self.current_follow_up_index
                ]
            except (KeyError, TypeError):
                return None

    def get_follow_up_name_for_t_point(self, t_point):
        return self.dataset.follow_ups_by_outcome[self.current_outcome_name][t_point]

    def get_t_point_for_follow_up_name(self, follow_up):
        return self.dataset.follow_ups_by_outcome[self.current_outcome_name].get_key(
            follow_up
        )

    def get_current_groups(self):
        return self.current_groups

    def get_previous_groups(self):
        return self.previous_groups

    def next_groups(self):
        """Return the next two group names in round-robin order."""
        if len(self.dataset.get_group_names()) == 0:
            return []

        # Restrict groups to the current outcome and follow-up.
        group_names = self.dataset.get_group_names_for_outcome_follow_up(
            self.current_outcome_name, self.get_current_follow_up_name()
        )

        self._next_group_indices(group_names)

        if not self.is_diagnostic():
            # shuffle over groups
            while self.group_index_a == self.group_index_b:
                self._next_group_indices(group_names)
        else:
            self._next_group_index(group_names)

        next_txs = [group_names[self.group_index_a], group_names[self.group_index_b]]
        return next_txs

    def _next_group_indices(self, group_names):
        if self.group_index_b < len(group_names) - 1:
            self.group_index_b += 1
        else:
            # bump the a index
            if self.group_index_a < len(group_names) - 1:
                self.group_index_a += 1
            else:
                self.group_index_a = 0
            self.group_index_b = 0

    def _next_group_index(self, group_names):
        # increments tx A; ignores B
        if self.group_index_a < len(group_names) - 1:
            self.group_index_a += 1
        else:
            self.group_index_a = 0

    def outcome_has_follow_up(self, outcome, follow_up):
        if outcome is None:
            return None
        analysis_units_by_follow_up = self.dataset.follow_ups_by_outcome[outcome]

        return follow_up in list(analysis_units_by_follow_up.keys())

    def outcome_follow_up_has_group(self, outcome, follow_up, group):
        # Dataset structure guarantees the same outcomes and follow-ups for
        # every study, so inspect the first study.
        analysis_units_by_follow_up = self.dataset.studies[0].analysis_units_by_outcome[
            outcome
        ]

        return group in list(analysis_units_by_follow_up[follow_up].groups.keys())

    def set_current_groups(self, group_names):
        self.previous_groups = self.current_groups
        self.current_groups = group_names
        self.group_index_a = self.dataset.get_group_names().index(group_names[0])
        self.group_index_b = self.dataset.get_group_names().index(group_names[1])

    def get_group_names(self):
        return self.dataset.get_group_names()

    def _sort_studies_with_cmp(
        self, compare_by, reverse, directions_to_analysis_unit=None
    ):
        comparator = self.dataset.cmp_studies(
            compare_by=compare_by,
            reverse=reverse,
            directions_to_analysis_unit=directions_to_analysis_unit,
            confidence_multiplier=self.get_confidence_multiplier(),
        )
        self.dataset.studies.sort(key=cmp_to_key(comparator), reverse=reverse)

    def sort_studies(self, col, reverse):
        if col == self.NAME:
            self._sort_studies_with_cmp("name", reverse)
        elif col == self.YEAR:
            self._sort_studies_with_cmp("year", reverse)
        elif col in self.RAW_DATA:
            # need this to dig down to find right analysis_unit and data we're looking for to compare against
            analysis_unit_reference_info = {
                "outcome_name": self.current_outcome_name,
                "follow_up": self.get_follow_up_name_for_t_point(
                    self.current_follow_up_index
                ),
                "current_groups": self.get_current_groups(),
                "data_index": col - min(self.RAW_DATA),
            }
            self._sort_studies_with_cmp(
                "raw_data", reverse, analysis_unit_reference_info
            )
        elif col in self.OUTCOMES:
            # need this to dig down to find right analysis_unit and data we're looking for to compare against
            analysis_unit_reference_info = {
                "outcome_type": self.dataset.get_outcome_type(
                    self.current_outcome_name
                ),
                "outcome_name": self.current_outcome_name,
                "follow_up": self.get_follow_up_name_for_t_point(
                    self.current_follow_up_index
                ),
                "current_groups": self.get_current_groups(),
                "current_effect": self.current_effect,
                "group_comparison": self.get_current_group_comparison(),
                "data_index": col - min(self.OUTCOMES),
            }
            self._sort_studies_with_cmp(
                "outcomes", reverse, analysis_unit_reference_info
            )

        # Columns to the right of outcomes are covariates.
        elif col > self.OUTCOMES[-1]:
            cov = self.get_covariate_for_column(col)
            self._sort_studies_with_cmp(cov.name, reverse)

        self.reset_model()

    def order_studies(self, ids):
        """Shuffles studies vector to the order specified by ids"""
        ordered_studies = []
        for an_id in ids:
            for study in self.dataset.studies:
                if study.id == an_id:
                    ordered_studies.append(study)
                    break
        self.dataset.studies = ordered_studies
        self.reset_model()

    def set_current_outcome(self, outcome_name):
        self.current_outcome_name = outcome_name
        self.update_column_indices()
        self.update_current_group_effect()
        self.outcomeChanged.emit()
        self.reset_model()

    def update_current_group_effect(self):
        outcome_type = self.dataset.get_outcome_type(self.current_outcome_name)
        if outcome_type == BINARY:
            self.current_effect = "OR"
        elif outcome_type == CONTINUOUS:
            self.current_effect = "MD"
        else:
            # Diagnostic rows display sensitivity/specificity instead of a
            # single current effect.
            self.current_effect = None

    def max_study_id(self):
        return self.dataset.max_study_id()

    def num_data_cols_for_current_unit(self):
        """Returns the number of columns needed to display the raw data
        given the current data type (binary, etc.)

        Note again that outcome names are necessarily unique!
        """
        data_type = self.dataset.get_outcome_type(self.current_outcome_name)
        sub_type = self.dataset.get_outcome_subtype(self.current_outcome_name)
        if data_type is None:
            return 0
        elif data_type in [BINARY, DIAGNOSTIC, OTHER]:
            return 4
        elif data_type == CONTINUOUS:
            if sub_type == "generic_effect":
                return 0  # no raw data for generic effect
            else:
                return 6

    def get_current_outcome_type(self, get_str=True):
        """Returns the type of the currently displayed (or 'active') outcome (e.g., binary)."""
        return self.dataset.get_outcome_type(
            self.current_outcome_name, get_string=get_str
        )

    def get_outcome_type(self, outcome, get_str=True):
        return self.dataset.get_outcome_type(outcome, get_string=get_str)

    def get_current_outcome_subtype(self):
        return self.dataset.get_outcome_subtype(self.current_outcome_name)

    def get_state(self):
        return {
            "NAME": self.NAME,
            "YEAR": self.YEAR,
            "RAW_DATA": self.RAW_DATA,
            "OUTCOMES": self.OUTCOMES,
            "HEADERS": self.headers,
            "current_outcome_name": self.current_outcome_name,
            "current_follow_up_index": self.current_follow_up_index,
            "current_groups": self.current_groups,
            "current_effect": self.current_effect,
            "study_auto_added": self.study_auto_added,
            "confidence_level": self.confidence_level,
        }

    def is_diagnostic(self):
        """Return whether the dataset contains diagnostic outcomes."""
        return self.dataset.is_diagnostic

    def set_state(self, state_dict):
        """Restore the persisted table state through the supported fields only."""
        restored_attributes = {
            "NAME": "NAME",
            "YEAR": "YEAR",
            "RAW_DATA": "RAW_DATA",
            "OUTCOMES": "OUTCOMES",
            "HEADERS": "headers",
            "current_outcome_name": "current_outcome_name",
            "current_follow_up_index": "current_follow_up_index",
            "current_groups": "current_groups",
            "current_effect": "current_effect",
            "study_auto_added": "study_auto_added",
        }
        unknown_fields = (
            set(state_dict) - set(restored_attributes) - {"confidence_level"}
        )
        if unknown_fields:
            names = ", ".join(sorted(unknown_fields))
            raise ValueError(f"Unsupported table state field(s): {names}")

        for state_name, attribute_name in restored_attributes.items():
            if state_name in state_dict:
                setattr(self, attribute_name, state_dict[state_name])

        self.set_confidence_level(
            state_dict.get("confidence_level", DEFAULT_CONFIDENCE_LEVEL)
        )

        # Signals emitted by reset_model immediately query visible cells. Keep
        # the column schema synchronized with the restored outcome before that
        # reset so a continuous project cannot momentarily use the previous
        # binary or diagnostic outcome indices.
        self.update_column_indices()
        self.reset_model()

    def raw_data_is_complete_for_study(self, study_index, first_arm_only=False):
        return raw_data_is_complete(
            self._get_raw_data_according_to_arms(study_index, first_arm_only)
        )

    def _raw_data_is_not_empty_for_study(self, study_index, first_arm_only=False):
        return not raw_data_is_empty(
            self._get_raw_data_according_to_arms(study_index, first_arm_only)
        )

    def _get_raw_data_according_to_arms(self, study_index, first_arm_only=False):
        if self.current_outcome_name is None or self.current_follow_up_index is None:
            return False

        raw_data = self.get_current_raw_data_for_study(study_index)
        data_type = self.get_current_outcome_type(get_str=False)
        # if first_arm_only is true, we are only concerned with whether
        # or not there is sufficient raw data for the first arm of the study

        if first_arm_only:
            if data_type == BINARY:
                raw_data = raw_data[:2]
            elif data_type == CONTINUOUS:
                raw_data = raw_data[:3]
        return raw_data

    def data_for_only_one_arm(self):
        """Really this should read 'data for one *and only one* arm."""
        data_for_arm_one, data_for_arm_two = False, False

        data_type = self.get_current_outcome_type(get_str=False)
        per_group_raw_data_size = 2 if data_type == BINARY else 3

        for study_index in range(len(self.dataset.studies)):
            current_raw_data = self.get_current_raw_data_for_study(study_index)

            if (
                len(
                    [
                        x
                        for x in current_raw_data[:per_group_raw_data_size]
                        if x is not None and x != ""
                    ]
                )
                > 0
            ):
                data_for_arm_one = True
            if (
                len(
                    [
                        x
                        for x in current_raw_data[per_group_raw_data_size:]
                        if x is not None and x != ""
                    ]
                )
                > 0
            ):
                data_for_arm_two = True

        return (data_for_arm_one and not data_for_arm_two) or (
            data_for_arm_two and not data_for_arm_one
        )

    def try_to_update_outcomes(self):
        for study_index in range(len(self.dataset.studies)):
            self.update_outcome_if_possible(study_index)

    def blank_all_studies(self, include_them):
        # Keep the auto-added blank row excluded from include-all changes.
        for study in self.dataset.studies[:-1]:
            study.include = include_them

    def include_all_studies(self):
        self.blank_all_studies(True)

    def exclude_all_studies(self):
        self.blank_all_studies(False)

    def all_studies_are_included(self):
        return all([study.include for study in self.dataset.studies])

    def all_studies_are_excluded(self):
        return all([not study.include for study in self.dataset.studies])

    def update_outcome_if_possible(self, study_index):
        """Rules:
        Checks the parametric study to ascertain if enough raw data has been
        entered to compute the outcome. If so, the outcome is computed and
        displayed.

        If the raw data is not empty, the outcome should be blanked out.
        If the raw data is empty, the outcome should not be effected
        """
        group_comparison = self.get_current_group_comparison()
        data_type = self.get_current_outcome_type(get_str=False)
        one_arm_effect = (
            self.current_effect in BINARY_ONE_ARM_METRICS + CONTINUOUS_ONE_ARM_METRICS
        )
        analysis_unit = self.get_current_analysis_unit_for_study(study_index)

        if data_type == DIAGNOSTIC or not self.study_has_point_est(study_index):
            self.dataset.studies[study_index].include = False

        complete = self.raw_data_is_complete_for_study(study_index) or (
            one_arm_effect
            and self.raw_data_is_complete_for_study(study_index, first_arm_only=True)
        )
        if complete:
            if not self.dataset.studies[study_index].manually_excluded:
                self.dataset.studies[study_index].include = True

            calculated = self.editing_service.preview_raw_effects(
                data_type,
                self.current_effect,
                self.get_current_raw_data_for_study(study_index),
                self.confidence_level,
            )
            if data_type == DIAGNOSTIC:
                if not isinstance(calculated, dict):
                    raise TypeError("diagnostic effects must be a metric mapping")
                for metric, (est, lower, upper) in calculated.items():
                    analysis_unit.set_effect_and_ci(
                        metric,
                        group_comparison,
                        est,
                        lower,
                        upper,
                        confidence_multiplier=self.confidence_multiplier,
                    )
                    analysis_unit.calculate_display_effect_and_ci(
                        metric,
                        group_comparison,
                        self.editing_service.display_scale_converter(data_type, metric),
                        confidence_level=self.get_confidence_level(),
                        confidence_multiplier=self.confidence_multiplier,
                    )
            else:
                if not isinstance(calculated, tuple):
                    raise TypeError("non-diagnostic effects must be a result tuple")
                (est, lower, upper), n1 = calculated
                analysis_unit.set_effect_and_ci(
                    self.current_effect,
                    group_comparison,
                    est,
                    lower,
                    upper,
                    confidence_multiplier=self.confidence_multiplier,
                )
                analysis_unit.calculate_display_effect_and_ci(
                    self.current_effect,
                    group_comparison,
                    self.editing_service.display_scale_converter(
                        data_type, self.current_effect, n1
                    ),
                    confidence_level=self.get_confidence_level(),
                    confidence_multiplier=self.confidence_multiplier,
                )
        elif self._raw_data_is_not_empty_for_study(study_index) or (
            one_arm_effect
            and self._raw_data_is_not_empty_for_study(study_index, first_arm_only=True)
        ):
            if data_type == DIAGNOSTIC:
                self._clear_diagnostic_effects_for_study(
                    analysis_unit, group_comparison
                )
            else:
                analysis_unit.set_effect_and_ci(
                    self.current_effect,
                    group_comparison,
                    None,
                    None,
                    None,
                    confidence_multiplier=self.confidence_multiplier,
                )
                analysis_unit.set_standard_error(
                    self.current_effect, group_comparison, None
                )
                analysis_unit.calculate_display_effect_and_ci(
                    self.current_effect,
                    group_comparison,
                    self.editing_service.display_scale_converter(
                        data_type, self.current_effect
                    ),
                    confidence_level=self.get_confidence_level(),
                    confidence_multiplier=self.confidence_multiplier,
                )

    def _clear_effect_and_display_ci(self, analysis_unit, effect, group_comparison):
        analysis_unit.set_effect_and_ci(
            effect,
            group_comparison,
            None,
            None,
            None,
            confidence_multiplier=self.confidence_multiplier,
        )
        analysis_unit.set_standard_error(effect, group_comparison, None)
        analysis_unit.set_display_effect(effect, group_comparison, None)
        analysis_unit.set_display_lower(effect, group_comparison, None)
        analysis_unit.set_display_upper(effect, group_comparison, None)
        analysis_unit.set_display_se(effect, group_comparison, None)

    def _clear_diagnostic_effects_for_study(self, analysis_unit, group_comparison):
        for metric in DIAGNOSTIC_METRICS:
            self._clear_effect_and_display_ci(analysis_unit, metric, group_comparison)

    def get_current_raw_data(self, only_if_included=True, only_these_studies=None):
        raw_data = []

        for study_index in range(len(self.dataset.studies)):
            if not only_if_included or self.dataset.studies[study_index].include:
                if (
                    only_these_studies is None
                    or self.dataset.studies[study_index].id in only_these_studies
                ):
                    raw_data.append(self.get_current_raw_data_for_study(study_index))

        return raw_data

    def included_studies_have_raw_data(self):
        """Return whether each included study has the required current raw data.

        For a one-arm metric, the active arm alone determines completeness.
        """
        return included_studies_have_raw_data(
            self.dataset.studies,
            self._get_raw_data_according_to_arms,
            self.current_effect in ONE_ARM_METRICS,
        )

    def study_has_point_est(self, study_index, effect=None):
        group_comparison = self.get_current_group_comparison()
        effect = effect or self.current_effect
        analysis_unit = self.get_current_analysis_unit_for_study(study_index)

        if None in analysis_unit.get_effect_and_se(
            effect, group_comparison, self.confidence_multiplier
        ):
            return False

        return True

    def current_estimate_and_standard_error_for_study(self, study_index, effect=None):
        group_comparison = self.get_current_group_comparison()
        analysis_unit = self.get_current_analysis_unit_for_study(study_index)
        effect = effect or self.current_effect

        estimate = analysis_unit.get_estimate(effect, group_comparison)
        standard_error = analysis_unit.get_se(
            effect, group_comparison, self.confidence_multiplier
        )
        return estimate, standard_error

    def get_current_estimates_and_standard_errors(
        self, only_if_included=True, only_these_studies=None, effect=None
    ):
        estimates, standard_errors = [], []
        effect = effect or self.current_effect
        for study_index in range(len(self.dataset.studies)):
            if (
                only_these_studies is None
                or self.dataset.studies[study_index].id in only_these_studies
            ):
                if not only_if_included or self.dataset.studies[study_index].include:
                    estimate, standard_error = (
                        self.current_estimate_and_standard_error_for_study(
                            study_index, effect=effect
                        )
                    )
                    estimates.append(estimate)
                    standard_errors.append(standard_error)
        return estimates, standard_errors

    def included_studies_have_point_estimates(self, effect=None):
        """Return whether included studies have estimates for the selected groups.

        When ``effect`` is omitted, use the currently selected effect.
        """
        return included_studies_have_effects(
            self.dataset.studies,
            lambda index: self.get_current_analysis_unit_for_study(
                index
            ).get_effect_and_se(
                effect or self.current_effect,
                self.get_current_group_comparison(),
                self.confidence_multiplier,
            ),
        )

    def get_studies(self, only_if_included=True):
        included_studies = []

        for study in self.dataset.studies:
            if not only_if_included or study.include:
                included_studies.append(study)
        return list(included_studies)

    def get_current_raw_data_for_study(self, study_index):
        return self.get_current_analysis_unit_for_study(
            study_index
        ).get_raw_data_for_groups(self.current_groups)

    def set_current_analysis_unit_for_study(self, study_index, new_analysis_unit):
        self.dataset.studies[study_index].replace_analysis_unit(
            self.current_outcome_name,
            self.get_current_follow_up_name(),
            new_analysis_unit,
        )

    def get_current_analysis_unit_for_study(self, study_index):
        """Return or create the study's currently selected analysis unit."""
        return self.get_analysis_unit(
            study_index=study_index,
            outcome=self.current_outcome_name,
            follow_up=self.get_current_follow_up_name(),
            groups=self.current_groups,
        )

    def get_analysis_unit(
        self, study=None, study_index=None, outcome=None, follow_up=None, groups=None
    ):
        """Return or create an analysis unit for named outcome and follow-up values."""
        if study is not None and study_index is not None:
            if study != self.dataset.studies[study_index]:
                raise ValueError("study and study index don't match")

        if study is None:  # you can specify a study OR a study index
            if study_index is None:
                raise ValueError("study or study_index must be specified")
            study = self.dataset.studies[study_index]

        if outcome is None or follow_up is None:
            raise ValueError("outcome and follow_up must be specified")

        return ensure_analysis_unit(
            self.dataset, study, outcome, follow_up, tuple(groups or ())
        )

    def recalculate_display_scale(self):
        effect = self.current_effect
        group_comparison = self.get_current_group_comparison()
        current_data_type = self.dataset.get_outcome_type(self.current_outcome_name)

        analysis_units = []
        # Gather analysis_units for spreadsheet
        for study_index in range(
            len(self.dataset.studies) - 1
        ):  # -1 is because last study is always blank
            analysis_units.append(self.get_current_analysis_unit_for_study(study_index))

        for index, x in enumerate(analysis_units):
            if current_data_type in [BINARY, CONTINUOUS]:
                convert_to_display_scale = self._get_conv_to_display_scale(
                    data_type=current_data_type, effect=effect
                )
                x.calculate_display_effect_and_ci(
                    effect,
                    group_comparison,
                    convert_to_display_scale,
                    confidence_level=self.get_confidence_level(),
                    confidence_multiplier=self.confidence_multiplier,
                    check_if_necessary=True,
                )
            elif current_data_type == DIAGNOSTIC:
                for m_str in ["Sens", "Spec"]:
                    x.calculate_display_effect_and_ci(
                        m_str,
                        group_comparison,
                        convert_to_display_scale=self._get_conv_to_display_scale(
                            data_type=DIAGNOSTIC, effect=m_str
                        ),
                        confidence_level=self.get_confidence_level(),
                        confidence_multiplier=self.confidence_multiplier,
                        check_if_necessary=True,
                    )

    def _get_conv_to_display_scale(self, data_type, effect, n1=None):
        return self.editing_service.display_scale_converter(data_type, effect, n1)

    def _get_calc_scale_value(
        self, display_scale_val=None, data_type=None, effect=None, n1=None
    ):
        return self.editing_service.to_calculation_scale(
            display_scale_val, data_type, effect, n1
        )

    def set_confidence_level(self, confidence_level):
        """Sets multiplier as well (~1.96 for 95% conf level)"""
        confidence_level = validate_confidence_level(confidence_level)

        self.confidence_level = confidence_level

        settings = self.editing_service.confidence_settings(confidence_level)
        self.confidence_level = settings.level
        self.confidence_multiplier = settings.multiplier
        self.editing_service.set_backend_confidence_level(settings.level)

        self.confLevelChanged.emit()

        return confidence_level

    def get_confidence_level(self):
        return self.confidence_level

    def get_confidence_multiplier(self):
        return self.confidence_multiplier
