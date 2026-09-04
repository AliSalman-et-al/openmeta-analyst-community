# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared calculator helpers for data-entry dialogs."""

import sys
from collections.abc import Callable
from functools import partial
from typing import Protocol, TypeAlias
from weakref import WeakKeyDictionary
from PyQt6.QtCore import Qt

from PyQt6.QtWidgets import QMessageBox, QSizePolicy, QStyle

from rc_metastudio.meta_globals import (
    CALC_NUM_DIGITS,
    EMPTY_VALS,
    ERROR_COLOR,
    OK_COLOR,
)
from rc_metastudio import r_bridge
from rc_metastudio import qt_text
from rc_metastudio.runtime_types import required


_EFFECT_CI_BASE_MINIMUM_WIDTHS = WeakKeyDictionary()


def cell_text_is_blank(value):
    """Return whether Qt item text is blank."""
    return qt_text.is_blank(value)


def numeric_value(value):
    """Return finite interface numeric input using explicit decimal rules."""
    number, valid = qt_text.parse_decimal(value)
    if not valid:
        raise ValueError(
            "Enter an unambiguous finite number using '.' or ',' as decimal separator."
        )
    return number


def set_table_item_text_color(item, color):
    if item is not None:
        item.setForeground(color)


def between_bounds(est=None, low=None, high=None):
    def my_lt(a, b):
        try:
            return numeric_value(a) < numeric_value(b)
        except ValueError:
            return None

    good_result = my_lt(low, est)
    okay = True if good_result is not None else False
    if okay and not good_result:
        msg = "The lower CI must be less than the point estimate!"
        return False, msg

    good_result = my_lt(est, high)
    okay = True if good_result is not None else False
    if okay and not good_result:
        msg = "The higher CI must be greater than the point estimate!"
        return False, msg

    good_result = my_lt(low, high)
    okay = True if good_result is not None else False
    if okay and not good_result:
        msg = "The lower CI must be less than the higher CI!"
        return False, msg

    return True, None


def compute_2x2_table_from_inner_counts(params):
    """Derive 2x2 margins from the four independent inner count cells."""
    c11 = params["c11"]
    c12 = params["c12"]
    c21 = params["c21"]
    c22 = params["c22"]

    def add_if_present(left, right):
        if left in EMPTY_VALS or right in EMPTY_VALS:
            return None
        return left + right

    r1sum = add_if_present(c11, c12)
    r2sum = add_if_present(c21, c22)
    c1sum = add_if_present(c11, c21)
    c2sum = add_if_present(c12, c22)
    total = add_if_present(r1sum, r2sum)
    if total in EMPTY_VALS:
        total = add_if_present(c1sum, c2sum)

    return {
        "c11": c11,
        "c12": c12,
        "r1sum": r1sum,
        "c21": c21,
        "c22": c22,
        "r2sum": r2sum,
        "c1sum": c1sum,
        "c2sum": c2sum,
        "total": total,
    }


def set_table_item_editable(item, editable):
    if item is None:
        return
    flags = item.flags()
    if editable:
        flags = flags | Qt.ItemFlag.ItemIsEditable
    else:
        flags = flags & ~Qt.ItemFlag.ItemIsEditable
    item.setFlags(flags)


def set_table_cells_editable(table, editable_cells):
    table.blockSignals(True)
    try:
        for row in range(table.rowCount()):
            for col in range(table.columnCount()):
                set_table_item_editable(
                    table.item(row, col), (row, col) in editable_cells
                )
    finally:
        table.blockSignals(False)


# Consistency checking code for 2x2 tables (binary and diagnostic)
class ConsistencyChecker:
    def __init__(self, fn_consistent=None, fn_inconsistent=None, table_2x2=None):
        functions_passed = (fn_consistent is not None) and (fn_inconsistent is not None)
        assert functions_passed, (
            "Not enough functions passed to check_for_consistencies"
        )
        assert table_2x2 is not None, "No table argument passed."

        self.inconsistent = False
        self.inconsistent_action = required(fn_inconsistent, "inconsistency callback")
        self.consistent_action = required(fn_consistent, "consistency callback")
        self.table = table_2x2

    def run(self):
        msg = self.check_for_consistencies()

        if not self.inconsistent:
            self._color_all(color=OK_COLOR)
        return msg

    def check_for_consistencies(self):
        self.inconsistent = False
        rows_sum = self.check_that_rows_sum()  # also colors non-summing rows
        cols_sum = self.check_that_cols_sum()
        all_pos = self.check_that_values_positive()

        if self.inconsistent:
            self.inconsistent_action()
        else:
            self.consistent_action()

        if not rows_sum:
            return "Rows must sum!"
        elif not cols_sum:
            return "Columns must sum!"
        elif not all_pos:
            return "Counts must be positive!"
        else:
            return None

    def check_that_rows_sum(self):
        rows_sum = True
        for row in range(3):
            if self._row_is_populated(row):
                row_sum = 0
                for col in range(2):
                    row_sum += self._get_int(row, col)
                if not row_sum == self._get_int(row, 2):
                    self._color_row(row)
                    self.inconsistent = True
                    rows_sum = False
        return rows_sum

    def _get_int(self, i, j):
        """Get value from cell specified by row=i, col=j as an integer"""
        if not self._is_empty_cell(i, j):
            return int(float(self.table.item(i, j).text()))
        else:
            return None  # its good to be explicit

    def check_that_cols_sum(self):
        cols_sum = True
        for col in range(3):
            if self._col_is_populated(col):
                col_sum = 0
                for row in range(2):
                    col_sum += self._get_int(row, col)
                if not col_sum == self._get_int(2, col):
                    self._color_col(col)
                    self.inconsistent = True
                    cols_sum = False
        return cols_sum

    def check_that_values_positive(self):
        all_positive = True

        for row in range(3):
            for col in range(3):
                value = self._get_int(row, col)
                if value not in EMPTY_VALS:
                    if value < 0:
                        self.table.blockSignals(True)
                        set_table_item_text_color(
                            self.table.item(row, col), ERROR_COLOR
                        )
                        self.table.blockSignals(False)
                        self.inconsistent = True
                        all_positive = False
        return all_positive

    def _color_all(self, color=ERROR_COLOR):
        self.table.blockSignals(True)
        for row in range(3):
            for col in range(3):
                item = self.table.item(row, col)
                if item is not None:
                    set_table_item_text_color(item, color)
        self.table.blockSignals(False)

    def _color_row(self, row):
        self.table.blockSignals(True)
        for col in range(3):
            set_table_item_text_color(self.table.item(row, col), ERROR_COLOR)
        self.table.blockSignals(False)

    def _color_col(self, col):
        self.table.blockSignals(True)
        for row in range(3):
            set_table_item_text_color(self.table.item(row, col), ERROR_COLOR)
        self.table.blockSignals(False)

    def _row_is_populated(self, row):
        return True not in [self._is_empty_cell(row, col) for col in range(3)]

    def _col_is_populated(self, col):
        return True not in [self._is_empty_cell(row, col) for row in range(3)]

    def _is_empty_cell(self, i, j):
        val = self.table.item(i, j)
        return val is None or val.text() == ""


def enable_txt_box_input(*args):
    """Enable empty text boxes and disable populated text boxes."""
    for text_box in args:
        text_box.blockSignals(True)

        text_box.setEnabled(False)
        if text_box.text() in EMPTY_VALS:
            text_box.setEnabled(True)

        text_box.blockSignals(False)


def fit_effect_ci_line_edits_to_contents(
    line_edits, digits=CALC_NUM_DIGITS, semantic_samples=None
):
    """Size calculator values from a semantic contract when one is supplied."""
    if semantic_samples is None:
        semantic_samples = ()
    for line_edit in line_edits:
        if line_edit is None:
            continue

        policy = line_edit.sizePolicy()
        line_edit.setSizePolicy(QSizePolicy.Policy.Fixed, policy.verticalPolicy())

        if semantic_samples:
            content_width = max(
                line_edit.fontMetrics().horizontalAdvance(sample)
                for sample in semantic_samples
            )
            text_margins = line_edit.textMargins()
            frame_width = line_edit.style().pixelMetric(
                QStyle.PixelMetric.PM_DefaultFrameWidth, None, line_edit
            )
            required_width = (
                content_width
                + text_margins.left()
                + text_margins.right()
                + (2 * frame_width)
            )
        else:
            signed_precision_sample = "-0." + ("8" * digits)
            base_minimum_width = _EFFECT_CI_BASE_MINIMUM_WIDTHS.get(line_edit)
            if base_minimum_width is None:
                base_minimum_width = line_edit.minimumWidth()
                _EFFECT_CI_BASE_MINIMUM_WIDTHS[line_edit] = base_minimum_width
            content_width = max(
                line_edit.fontMetrics().horizontalAdvance(value)
                for value in (signed_precision_sample, str(line_edit.text()))
            )
            required_width = max(base_minimum_width, content_width + 12)
        # layout-audit: allow=numeric-domain-control; reason=editor width follows representative values from its numeric domain
        line_edit.setMinimumWidth(required_width)
        # layout-audit: allow=numeric-domain-control; reason=editor width follows representative values from its numeric domain
        line_edit.setMaximumWidth(required_width)


def format_calculator_display_value(value, digits=CALC_NUM_DIGITS):
    """Format a calculator value exactly as it is rendered in its line edit."""
    return str(round(value, digits))


def binary_effect_display_samples(metric, digits=CALC_NUM_DIGITS):
    """Return semantic display-domain samples for a binary calculator metric."""
    precision = "0." + ("0" * digits)
    proportion_metrics = {"PR", "PLN", "PLO", "PAS", "PFT"}
    signed_unit_metrics = {"RD", "YUQ", "YUY"}
    positive_ratio_metrics = {"OR", "RR"}

    if metric in proportion_metrics:
        return (precision, "1." + ("0" * digits))
    if metric in signed_unit_metrics:
        return ("-1." + ("0" * digits), "1." + ("0" * digits))
    if metric == "AS":
        # Keep a signed-unit value in the semantic sample set. It is inside the
        # arcsine domain and prevents native proportional fonts from making the
        # field narrower than the signed-unit metrics when users switch scales.
        return ("-1.5708", "-1.0000", "1.5708")
    if metric in positive_ratio_metrics:
        # Ratios are positive and unbounded, so use the exact text produced by
        # the renderer at the largest accepted finite binary64 value.
        return (
            precision,
            format_calculator_display_value(sys.float_info.max, digits),
        )
    return ("-" + precision, precision)


def continuous_effect_display_samples(metric, digits=CALC_NUM_DIGITS):
    """Return formatter-derived semantic samples for continuous effect fields.

    Continuous effect domains are mathematically unbounded, so values beyond
    these common display magnitudes remain reachable through QLineEdit's native
    horizontal navigation rather than forcing the dialog to grow indefinitely.
    """
    magnitude = 10.9999 if metric == "SMD" else 9999.9999
    return tuple(
        format_calculator_display_value(value, digits)
        for value in (-magnitude, magnitude)
    )


def diagnostic_effect_display_samples(metric, digits=CALC_NUM_DIGITS):
    """Return valid display-domain samples for diagnostic effect fields."""
    precision = "0." + ("0" * digits)
    if metric in {"Sens", "Spec"}:
        return (precision, "1." + ("0" * digits))
    # Diagnostic ratios are positive and unbounded. Keep common values visible;
    # larger entries remain reachable through native line-edit navigation.
    return (precision, "9999." + ("9" * digits))


def set_current_effect_from_value(
    analysis_unit,
    txt_boxes,
    current_effect,
    group_comparison,
    data_type,
    confidence_multiplier=None,
):
    """Populate calculator fields from an analysis unit."""
    if confidence_multiplier is None:
        raise ValueError("confidence multiplier must be specified")

    converters = {
        "binary": r_bridge.binary_convert_scale,
        "continuous": r_bridge.continuous_convert_scale,
        "diagnostic": r_bridge.diagnostic_convert_scale,
    }
    try:
        converter = converters[data_type]
    except KeyError as exc:
        raise ValueError("data_type unrecognized") from exc
    conv_to_disp_scale = lambda value: converter(
        value, current_effect, convert_to="display.scale"
    )
    effect_tbox, lower_tbox, upper_tbox = [
        txt_boxes[box_name] for box_name in ("effect", "lower", "upper")
    ]

    (est, lower, upper) = analysis_unit.get_effect_and_ci_for_source(
        "entered", current_effect, group_comparison, confidence_multiplier
    )
    (display_estimate, display_lower, display_upper) = [
        conv_to_disp_scale(x) for x in (est, lower, upper)
    ]
    for val, txt_box in zip(
        (display_estimate, display_lower, display_upper),
        [effect_tbox, lower_tbox, upper_tbox],
    ):
        txt_box.blockSignals(True)
        if val is not None:
            txt_box.setText(format_calculator_display_value(val))
        else:
            txt_box.setText("")
        txt_box.blockSignals(False)
    semantic_samples = {
        "binary": binary_effect_display_samples,
        "continuous": continuous_effect_display_samples,
        "diagnostic": diagnostic_effect_display_samples,
    }[data_type](current_effect)
    fit_effect_ci_line_edits_to_contents(
        [effect_tbox, lower_tbox, upper_tbox],
        semantic_samples=semantic_samples,
    )


def save_table_data(table):
    nrows, ncols = table.rowCount(), table.columnCount()

    none_row = [None] * ncols
    table_backup = []
    for dummy in range(nrows):
        table_backup.append(none_row[:])

    for row in range(nrows):
        for col in range(ncols):
            item = table.item(row, col)
            contents = "" if item is None else item.text()
            table_backup[row][col] = contents
    return table_backup


class CalculatorCommandOwner(Protocol):
    def update_back_calculation_button(self, engage: bool = False) -> None: ...


EditState: TypeAlias = tuple[object, ...]
StateRestorer: TypeAlias = Callable[..., None]


class FieldEditCommand:
    """Transient undo record for fields inside one open calculator dialog."""

    def __init__(
        self,
        *,
        owner: CalculatorCommandOwner,
        restore_state: StateRestorer,
        old_state: EditState,
        new_state: EditState,
        description: str = "",
        refresh_on_initial_redo: bool = True,
    ) -> None:
        self.owner = owner
        self.just_created = True
        self.restore_state = restore_state
        self.old_state = old_state
        self.new_state = new_state
        self.refresh_on_initial_redo = refresh_on_initial_redo

    def redo(self) -> None:
        if self.just_created:
            self.just_created = False
            if self.refresh_on_initial_redo:
                self.owner.update_back_calculation_button()
        else:
            self.restore_state(*self.new_state)

    def undo(self) -> None:
        self.restore_state(*self.old_state)


class TransientEditHistory:
    """Small dialog-local history; it is discarded when the dialog closes."""

    def __init__(self) -> None:
        self._commands: list[FieldEditCommand] = []
        self._index = 0

    def push(self, command: FieldEditCommand) -> None:
        del self._commands[self._index :]
        self._commands.append(command)
        self._index += 1
        command.redo()

    def undo(self) -> None:
        if self._index:
            self._index -= 1
            self._commands[self._index].undo()

    def redo(self) -> None:
        if self._index < len(self._commands):
            self._commands[self._index].redo()
            self._index += 1


def push_field_edit(
    history: TransientEditHistory,
    *,
    owner: CalculatorCommandOwner,
    restore_state: StateRestorer,
    old_state: EditState,
    new_state: EditState,
    description: str = "",
    refresh_on_initial_redo: bool = True,
) -> None:
    """Publish an already-applied calculator edit as one undoable state change."""
    history.push(
        make_field_edit_command(
            owner=owner,
            restore_state=restore_state,
            old_state=old_state,
            new_state=new_state,
            description=description,
            refresh_on_initial_redo=refresh_on_initial_redo,
        )
    )


def make_field_edit_command(
    *,
    owner: CalculatorCommandOwner,
    restore_state: StateRestorer,
    old_state: EditState,
    new_state: EditState,
    description: str = "",
    refresh_on_initial_redo: bool = True,
) -> FieldEditCommand:
    """Build a calculator edit command for a caller with atomic publication rules."""
    return FieldEditCommand(
        owner=owner,
        restore_state=restore_state,
        old_state=old_state,
        new_state=new_state,
        description=description,
        refresh_on_initial_redo=refresh_on_initial_redo,
    )


def block_signals(widgets, state):
    for widget in widgets:
        widget.blockSignals(state)


# Only used in binary and continuous?
def get_raw_data(analysis_unit, groups):
    raw_data_dict = {}
    for group in groups:
        raw_data = analysis_unit.get_raw_data_for_group(group)
        raw_data_dict[group] = raw_data
    return raw_data_dict


def _input_fields_disabled(table, text_boxes):
    table_disabled = table_cells_editable(table)
    txt_boxes_disabled = _txt_boxes_disabled(text_boxes)

    if table_disabled and txt_boxes_disabled:
        return True
    return False


def table_cells_editable(table):
    cells_uneditable = True
    nrows = table.rowCount()
    ncols = table.columnCount()
    for row in range(nrows):
        for col in range(ncols):
            item = table.item(row, col)
            if item is None:
                continue
            if (
                item.flags() & Qt.ItemFlag.ItemIsEditable
            ) == Qt.ItemFlag.ItemIsEditable:
                cells_uneditable = False
    return cells_uneditable


def _txt_boxes_disabled(text_boxes):
    return not any([box.isEnabled() for box in text_boxes])


# Function for testing validity and range conditions in form txt boxes
def evaluate(
    new_text,
    analysis_unit,
    current_effect,
    group_comparison,
    conv_to_disp_scale,
    ci_param=None,
    parent=None,
    opt_cmp_fn=None,
    opt_cmp_msg=None,
    confidence_multiplier=None,
):
    """opt_cmp_fn i.e. 'Optional Compare Function' should return True when the
    desired condition is met and False otherwise. It is a function of new_text:
    opt_cmp_fn(new_text)
    """
    if confidence_multiplier is None:
        raise ValueError("confidence multiplier must be specified")

    est, lower, upper = analysis_unit.get_effect_and_ci_for_source(
        "entered", current_effect, group_comparison, confidence_multiplier
    )  # calc scale
    display_estimate, display_lower, display_upper = [
        conv_to_disp_scale(x) for x in (est, lower, upper)
    ]
    is_between_bounds = partial(
        between_bounds, est=display_estimate, low=display_lower, high=display_upper
    )
    try:
        parsed_value = numeric_value(new_text)
    except ValueError:
        QMessageBox.warning(parent, "Warning", "Must be numeric!")
        raise Exception("error")
    if not opt_cmp_fn:  # est, lower, upper
        if ci_param is None:
            raise ValueError("ci_param is required for confidence-bound validation")
        (good_result, msg) = is_between_bounds(**{ci_param: new_text})
        if not good_result:
            QMessageBox.warning(parent, "Warning", msg)
            raise Exception("error")
    else:  # something other than est, lower, upper (like correlation or prevalence)
        if not opt_cmp_fn(new_text):
            QMessageBox.warning(parent, "Warning", opt_cmp_msg)
            raise Exception("error")
    return parsed_value  # display_scale_val
