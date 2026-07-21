# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Application-wide constants and small shared helpers."""

# This module still mixes constants and small helpers because long-standing call
# sites import it as the application-wide metadata namespace.

import os
import math

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

VERSION = "0.2.2"

DISABLE_NETWORK_STUFF = True  # disable this until we can package jags, rjags, getmc
DEFAULT_DATASET_NAME = "untitled_dataset"

## For now we're going to hardcode which metrics are available.
# In the future, we may want to pull these out dynamically from
# the R side. But then meta-analytic methods would have either to
# only operate over the effects and variances or else themselves
# know how to compute arbitrary metrics.

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

# Diagnostic metrics
DIAGNOSTIC_METRICS = ["Sens", "Spec", "PLR", "NLR", "DOR"]
DIAGNOSTIC_LOG_METRICS = ["PLR", "NLR", "DOR"]
DIAGNOSTIC_METRIC_NAMES = {
    "Sens": "Sensitivity",
    "Spec": "Specificity",
    "PLR": "Positive Likelihood Ratio",
    "NLR": "Negative Likelihood Ratio",
    "DOR": "Diagnostic Odds Ratio",
}

# Construct dictionary of all the metric names
ALL_METRIC_NAMES = {}
ALL_METRIC_NAMES.update(BINARY_METRIC_NAMES)
ALL_METRIC_NAMES.update(CONTINUOUS_METRIC_NAMES)
ALL_METRIC_NAMES.update(DIAGNOSTIC_METRIC_NAMES)

# enumeration of data types and dictionaries mapping both ways
BINARY, CONTINUOUS, DIAGNOSTIC, OTHER = range(4)

# we need two types for covariates; factor and continuous. we'll use the
# above definition (enumerated as part of a general data type) for continuous
# and just define factor here.
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
VANILLA, NETWORK = range(2)

EMPTY_VALS = ("", None)  # these indicate an empty row/cell

BASE_PATH = str(os.path.abspath(os.getcwd()))

# def get_BASE_PATH():
#    BASE_PATH = str(os.path.abspath(os.getcwd())) # where temporary R output should go


# this is a useful function sometimes.
none_to_str = lambda x: "" if x is None else x

# for diagnostic data -- this dictionary maps
# the mteric names as they appear in the UI/ure
# used here to the names used in the model.
# see get_diag_metrics_to_run.
DIAG_METRIC_NAMES_D = {
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
    THRESHOLD = 1e-4
    if abs(x - y) < THRESHOLD:
        return True
    else:
        return False


### CONFIDENCE LEVEL STUFF #####
DEFAULT_CONF_LEVEL = 95.0  # (normal 95% CI)
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
ANALYSIS_COUNT_MAX = 1000000000
ANALYSIS_POSITIVE_INTEGER_PARAMS = set(["num.iters", "thin", "num.chains"])
ANALYSIS_NON_NEGATIVE_INTEGER_PARAMS = set(["burn.in"])
ANALYSIS_NON_NEGATIVE_FLOAT_PARAMS = set(["adjust"])
ANALYSIS_FLOAT_PARAMS = set(
    [
        "theta.lower",
        "theta.upper",
        "lambda.lower",
        "lambda.upper",
    ]
)
INVALID_CORRECTION_FACTOR_MESSAGE = (
    "Correction factor must be a finite non-negative number."
)


def validate_confidence_level(conf_level):
    try:
        value = float(conf_level)
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


def validate_analysis_count(name, count):
    try:
        value = float(count)
    except (TypeError, ValueError):
        raise ValueError("%s must be an integer." % name)

    minimum = 1 if name in ANALYSIS_POSITIVE_INTEGER_PARAMS else 0
    if (
        not math.isfinite(value)
        or not value.is_integer()
        or not (minimum <= value <= ANALYSIS_COUNT_MAX)
    ):
        raise ValueError(
            "%s must be an integer greater than or equal to %d." % (name, minimum)
        )

    return int(value)


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
    for name in ANALYSIS_POSITIVE_INTEGER_PARAMS | ANALYSIS_NON_NEGATIVE_INTEGER_PARAMS:
        if name in normalized:
            normalized[name] = validate_analysis_count(name, normalized[name])
    for name in ANALYSIS_FLOAT_PARAMS:
        if name in normalized:
            normalized[name] = validate_analysis_float(name, normalized[name])
    return normalized


"""
some useful static methods
"""


def seems_sane(xticks):
    num_list = xticks.split(",")
    if len(num_list) == 1:
        return False
    try:
        num_list = [eval(x) for x in num_list]
    except:
        return False
    return True


def check_plot_bound(bound):
    try:
        # errrm... this might cause a problem if
        # bound is 0...
        return float(bound)
    except:
        return False


def is_a_float(s):
    try:
        float(s)
        return True
    except:
        return False


def is_empty(s):
    return s is None or s == ""


def is_an_int(s):
    try:
        int(s)
        return True
    except:
        try:
            value = float(s)
            return value.is_integer()
        except:
            return False


def is_NaN(x):
    # there's no built-in for checking if a number is a NaN in
    # Python < 2.6. checking if a number is equal to itself
    # does the trick, though purportedly does not always work.
    return x != x


class CommandGenericDo(QUndoCommand):
    """
    This is a generic undo/redo command that takes two unevaluated lambdas --
    thunks, if you will -- one for doing and one for undoing.
    """

    def __init__(self, redo_f, undo_f, description=""):
        super(CommandGenericDo, self).__init__(description)
        self.redo_f = redo_f
        self.undo_f = undo_f

    def redo(self):
        self.redo_f()

    def undo(self):
        self.undo_f()


def tabulate(lists, sep=" | ", return_col_widths=False, align=[]):
    """Makes a pretty table from the lists in args"""
    """ each arg is a list """
    """ if return_max_col_lenths is true, the return type is a tuple of (str, col_widths) """
    """ align is a list the same length as lists telling how the column should be aligned ('L','R') etc """

    if len(align) != len(lists):
        align = [
            "L",
        ] * len(lists)
    print("Align is now %s: " % align)

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
            for x, width, row_alignment in zip(row, max_lengths, align)
        ]
        row_str = sep.join(row_str)
        out.append(row_str)
    out_str = "\n".join(out)

    if return_col_widths:
        return (out_str, max_lengths)
    return out_str
