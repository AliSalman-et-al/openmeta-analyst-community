import math
import os
import sys

import pytest


sys.path.insert(0, os.path.abspath("src"))

from rc_metastudio.meta_globals import (
    normalize_confidence_level_params,
    seems_sane,
    validate_analysis_digits,
    validate_correction_factor,
    validate_confidence_level,
)


def test_plot_ticks_accept_only_comma_separated_finite_numbers():
    assert seems_sane("-1.5, 0, 2e3")
    assert not seems_sane("1")
    assert not seems_sane("1, inf")
    assert not seems_sane("1, __import__('os').getcwd()")


def test_validate_confidence_level_accepts_finite_exclusive_percentage():
    assert validate_confidence_level(95) == 95.0
    assert validate_confidence_level("99.9") == 99.9


def test_validate_confidence_level_rejects_endpoints_and_non_finite_values():
    for value in (0, 100, -1, 101, math.inf, -math.inf, math.nan, None, "bad"):
        with pytest.raises(ValueError, match="greater than 0 and less than 100"):
            validate_confidence_level(value)


def test_normalize_confidence_level_params_validates_analysis_dictionaries():
    params = {"conf.level": "99.9", "digits": 3}

    normalized = normalize_confidence_level_params(params)

    assert normalized == {"conf.level": 99.9, "digits": 3}
    assert params == {"conf.level": "99.9", "digits": 3}


def test_normalize_confidence_level_params_rejects_invalid_analysis_dictionaries():
    with pytest.raises(ValueError, match="greater than 0 and less than 100"):
        normalize_confidence_level_params({"conf.level": 100, "digits": 3})


def test_validate_analysis_digits_accepts_non_negative_integer_precision():
    assert validate_analysis_digits(0) == 0
    assert validate_analysis_digits("5") == 5
    assert validate_analysis_digits(3.0) == 3


def test_validate_analysis_digits_rejects_negative_and_non_integer_values():
    for value in (-1, "-5", 1.5, "2.5", math.inf, math.nan, None, "bad"):
        with pytest.raises(ValueError, match="Decimal places"):
            validate_analysis_digits(value)


def test_normalize_confidence_level_params_rejects_invalid_digits():
    with pytest.raises(ValueError, match="Decimal places"):
        normalize_confidence_level_params({"conf.level": 95, "digits": -5})


def test_validate_correction_factor_accepts_finite_non_negative_values():
    assert validate_correction_factor(0) == 0.0
    assert validate_correction_factor("0.5") == 0.5


def test_validate_correction_factor_rejects_negative_and_non_finite_values():
    for value in (-0.1, math.inf, math.nan, None, "bad"):
        with pytest.raises(ValueError, match="Correction factor"):
            validate_correction_factor(value)


def test_normalize_confidence_level_params_validates_reitsma_controls():
    assert normalize_confidence_level_params(
        {"conf.level": "99.9", "digits": "3", "adjust": "0.5"}
    ) == {"conf.level": 99.9, "digits": 3, "adjust": 0.5}
