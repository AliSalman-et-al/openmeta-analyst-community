# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Application-wide constants and small shared helpers."""

# This module still mixes constants and small helpers because long-standing call
# sites import it as the application-wide metadata namespace.

import os
import math
from collections.abc import Callable, Sequence
from typing import TypeVar, overload

from PyQt6.QtGui import QColor, QUndoCommand

APPLICATION_NAME = "RCMetaStudio"
APPLICATION_DISPLAY_NAME = "RC MetaStudio"
ORGANIZATION_NAME = "Research Consultancy"
ORGANIZATION_DOMAIN = "rcmetastudio.org"

# Default display precision. Editing and calculations retain their full values.
NUM_DIGITS = 2
PERCENTAGE_DISPLAY_DIGITS = 1

# number of digits to display in calculator
#   It is now a global here and in the data_table_view class. (However
#   here we show four digits; ordinary display uses 2. We want different
#   levels of granularity).
CALC_NUM_DIGITS = 4

VERSION = "0.3.1"

DEFAULT_DATASET_NAME = "untitled_dataset"

# Supported metrics are part of the application contract. R methods operate on
# these known effects and variances.

# Binary metrics
BINARY_TWO_ARM_METRICS = ["OR", "RD", "RR", "AS", "YUQ", "YUY"]
BINARY_ONE_ARM_METRICS = ["PR", "PLN", "PLO", "PAS", "PFT"]
BINARY_METRIC_NAMES = {
    "OR": "Odds Ratio",
    "RD": "Risk Difference",
    "RR": "Risk Ratio",
    "AS": "Arcsine Difference",
    "YUQ": "Yule's Q",
    "YUY": "Yule's Y",
    "PR": "Untransformed Proportion",
    "PLN": "Natural Logarithm transformed Proportion",
    "PLO": "Logit transformed Proportion",
    "PAS": "Arcsine transformed Proportion",
    "PFT": "Freeman-Tukey transformed Proportion",
}

# Continuous metrics
CONTINUOUS_TWO_ARM_METRICS = ["MD", "SMD"]
CONTINUOUS_ONE_ARM_METRICS = ["TX Mean"]
CONTINUOUS_METRIC_NAMES = {
    "MD": "Mean Difference",
    "SMD": "Standardized Mean Difference",
    "TX Mean": "TX Mean",
}


# Default metrics (for when making a new dataset)
DEFAULT_BINARY_ONE_ARM = "PR"
DEFAULT_BINARY_TWO_ARM = "OR"
DEFAULT_CONTINUOUS_ONE_ARM = "TX Mean"
DEFAULT_CONTINUOUS_TWO_ARM = "SMD"

# Sometimes it's useful to know if we're dealing with a one-arm outcome,
# in general
ONE_ARM_METRICS = BINARY_ONE_ARM_METRICS + CONTINUOUS_ONE_ARM_METRICS
TWO_ARM_METRICS = BINARY_TWO_ARM_METRICS + CONTINUOUS_TWO_ARM_METRICS

DIAGNOSTIC_METRICS = ["Sens", "Spec", "PLR", "NLR", "DOR"]
DIAGNOSTIC_LOG_METRICS = ["PLR", "NLR", "DOR"]
DIAGNOSTIC_METRIC_LABELS = {
    "Sens": "Sensitivity",
    "Spec": "Specificity",
    "PLR": "Positive Likelihood Ratio",
    "NLR": "Negative Likelihood Ratio",
    "DOR": "Diagnostic Odds Ratio",
}

ALL_METRIC_NAMES = {}
ALL_METRIC_NAMES.update(BINARY_METRIC_NAMES)
ALL_METRIC_NAMES.update(CONTINUOUS_METRIC_NAMES)
ALL_METRIC_NAMES.update(DIAGNOSTIC_METRIC_LABELS)

# enumeration of data types and dictionaries mapping both ways
BINARY, CONTINUOUS, DIAGNOSTIC, OTHER = range(4)

# Continuous shares the general data-type enumeration; factor is covariate-only.
FACTOR = 4

# making life easier
COV_INTS_TO_STRS = {4: "factor", 1: "continuous"}

STR_TO_TYPE_DICT = {
    "binary": BINARY,
    "continuous": CONTINUOUS,
    "diagnostic": DIAGNOSTIC,
    "OTHER": OTHER,
}

TYPE_TO_STR_DICT = {
    BINARY: "binary",
    CONTINUOUS: "continuous",
    DIAGNOSTIC: "diagnostic",
    OTHER: "OTHER",
    FACTOR: "factor",
}

# enumeration of meta-analytic types
VANILLA = 0

EMPTY_VALS = ("", None)  # these indicate an empty row/cell

BASE_PATH = str(os.path.abspath(os.getcwd()))

_Value = TypeVar("_Value")


@overload
def none_to_str(value: None) -> str: ...


@overload
def none_to_str(value: _Value) -> _Value: ...


def none_to_str(value: object | None) -> object | str:
    """Return an empty display value for ``None`` without changing other values."""
    return "" if value is None else value


DIAGNOSTIC_METRIC_GROUPS = {
    "sens": ["Sens"],
    "spec": ["Spec"],
    "dor": ["DOR"],
    "lr": ["PLR", "NLR"],
}

DIAG_FIELDS_TO_RAW_INDICES = {"TP": 0, "FN": 1, "FP": 2, "TN": 3}

# this is the maximum size of a residual that we're willing to accept
# when computing 2x2 data
THRESHOLD = 1e-5

ERROR_COLOR = QColor("red")
OK_COLOR = QColor("black")

DEFAULT_GROUP_NAMES = ["tx A", "tx B"]


def equal_close_enough(x, y):
    threshold = 1e-4
    return abs(x - y) < threshold


DEFAULT_CONFIDENCE_LEVEL = 95.0  # (normal 95% CI)
CONFIDENCE_LEVEL_MIN = 0.0
CONFIDENCE_LEVEL_MAX = 100.0
CONFIDENCE_LEVEL_DISPLAY_MAX = 99.9
INVALID_CONFIDENCE_LEVEL_MESSAGE = (
    "Confidence level must be greater than 0 and less than 100."
)
ANALYSIS_DIGITS_MIN = 0
ANALYSIS_DIGITS_MAX = 15
INVALID_ANALYSIS_DIGITS_MESSAGE = "Decimal places must be a non-negative integer."
ANALYSIS_NUMERIC_MIN = -1000000000.0
ANALYSIS_NUMERIC_MAX = 1000000000.0
ANALYSIS_NON_NEGATIVE_FLOAT_PARAMS = set(["adjust"])
INVALID_CORRECTION_FACTOR_MESSAGE = (
    "Correction factor must be a finite non-negative number."
)


def validate_confidence_level(confidence_level):
    try:
        value = float(confidence_level)
    except (TypeError, ValueError):
        raise ValueError(INVALID_CONFIDENCE_LEVEL_MESSAGE)

    if not math.isfinite(value) or not (
        CONFIDENCE_LEVEL_MIN < value < CONFIDENCE_LEVEL_MAX
    ):
        raise ValueError(INVALID_CONFIDENCE_LEVEL_MESSAGE)

    return value


def validate_analysis_digits(digits):
    try:
        value = float(digits)
    except (TypeError, ValueError):
        raise ValueError(INVALID_ANALYSIS_DIGITS_MESSAGE)

    if (
        not math.isfinite(value)
        or not value.is_integer()
        or not (ANALYSIS_DIGITS_MIN <= value <= ANALYSIS_DIGITS_MAX)
    ):
        raise ValueError(INVALID_ANALYSIS_DIGITS_MESSAGE)

    return int(value)


def validate_correction_factor(adjust):
    try:
        value = float(adjust)
    except (TypeError, ValueError):
        raise ValueError(INVALID_CORRECTION_FACTOR_MESSAGE)

    if not math.isfinite(value) or not (0 <= value <= ANALYSIS_NUMERIC_MAX):
        raise ValueError(INVALID_CORRECTION_FACTOR_MESSAGE)
    return value


def validate_analysis_float(name, value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError("%s must be a finite number." % name)

    if not math.isfinite(value) or not (
        ANALYSIS_NUMERIC_MIN <= value <= ANALYSIS_NUMERIC_MAX
    ):
        raise ValueError("%s must be a finite number." % name)

    return value


def normalize_confidence_level_params(params):
    normalized = dict(params)
    if "conf.level" in normalized:
        normalized["conf.level"] = validate_confidence_level(normalized["conf.level"])
    if "digits" in normalized:
        normalized["digits"] = validate_analysis_digits(normalized["digits"])
    if "adjust" in normalized:
        normalized["adjust"] = validate_correction_factor(normalized["adjust"])
    return normalized


def seems_sane(xticks: str) -> bool:
    """Return whether a comma-separated tick list contains only finite numbers."""
    raw_ticks = xticks.split(",")
    if len(raw_ticks) < 2:
        return False
    try:
        ticks = [float(tick.strip()) for tick in raw_ticks]
    except ValueError:
        return False
    return all(math.isfinite(tick) for tick in ticks)


def check_plot_bound(bound: str | int | float | None) -> float | bool:
    if bound is None:
        return False
    try:
        return float(bound)
    except (TypeError, ValueError):
        return False


def is_a_float(value: object) -> bool:
    try:
        float(value)  # type: ignore[arg-type] -- This predicate intentionally accepts user input of unknown type.
        return True
    except (TypeError, ValueError):
        return False


def is_empty(value: object | None) -> bool:
    return value is None or value == ""


def is_an_int(value: object) -> bool:
    try:
        int(value)  # type: ignore[call-overload] -- This predicate intentionally accepts user input of unknown type.
        return True
    except (TypeError, ValueError):
        try:
            numeric_value = float(value)  # type: ignore[arg-type] -- This predicate intentionally accepts user input of unknown type.
            return numeric_value.is_integer()
        except (TypeError, ValueError):
            return False


def is_nan(value: object) -> bool:
    """Return whether ``value`` has IEEE NaN comparison behavior."""

    return value != value


class CallbackCommand(QUndoCommand):
    """Execute paired redo and undo callbacks."""

    def __init__(
        self,
        redo_f: Callable[[], None],
        undo_f: Callable[[], None],
        description: str = "",
    ) -> None:
        super().__init__(description)
        self.redo_f = redo_f
        self.undo_f = undo_f

    def redo(self) -> None:
        self.redo_f()

    def undo(self) -> None:
        self.undo_f()


@overload
def tabulate(
    lists: Sequence[Sequence[object]],
    sep: str = " | ",
    return_col_widths: bool = False,
    align: Sequence[str] | None = None,
) -> str: ...


@overload
def tabulate(
    lists: Sequence[Sequence[object]],
    sep: str,
    return_col_widths: bool,
    align: Sequence[str] | None = None,
) -> str | tuple[str, list[int]]: ...


def tabulate(
    lists: Sequence[Sequence[object]],
    sep: str = " | ",
    return_col_widths: bool = False,
    align: Sequence[str] | None = None,
) -> str | tuple[str, list[int]]:
    """Render equally sized columns as a plain-text table."""
    column_alignments = list(align) if align is not None else []
    if len(column_alignments) != len(lists):
        column_alignments = ["L"] * len(lists)

    # covert lists in args to string lists
    string_lists = []
    for arg in lists:
        str_arg = [str(x) for x in arg]
        string_lists.append(str_arg)

    # get max length of each element in each column
    max_lengths = []
    for arg in string_lists:
        max_len = max([len(x) for x in arg])
        max_lengths.append(max_len)

    data = zip(*string_lists)
    out = []
    for row in data:
        row_str = [
            "{0:{align}{width}}".format(
                x, width=width, align="<" if row_alignment == "L" else ">"
            )
            for x, width, row_alignment in zip(row, max_lengths, column_alignments)
        ]
        row_str = sep.join(row_str)
        out.append(row_str)
    out_str = "\n".join(out)

    if return_col_widths:
        return (out_str, max_lengths)
    return out_str
