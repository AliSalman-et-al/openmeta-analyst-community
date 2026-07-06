import math
import os
import sys

import pytest


sys.path.insert(0, os.path.abspath("src"))

from meta_globals import (
    normalize_confidence_level_params,
    validate_analysis_count,
    validate_analysis_digits,
    validate_correction_factor,
    validate_confidence_level,
)


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
        with pytest.raises(ValueError, match="Number of digits"):
            validate_analysis_digits(value)


def test_normalize_confidence_level_params_rejects_invalid_digits():
    with pytest.raises(ValueError, match="Number of digits"):
        normalize_confidence_level_params({"conf.level": 95, "digits": -5})


def test_validate_correction_factor_accepts_finite_non_negative_values():
    assert validate_correction_factor(0) == 0.0
    assert validate_correction_factor("0.5") == 0.5


def test_validate_correction_factor_rejects_negative_and_non_finite_values():
    for value in (-0.1, math.inf, math.nan, None, "bad"):
        with pytest.raises(ValueError, match="Correction factor"):
            validate_correction_factor(value)


def test_validate_analysis_count_accepts_integer_counts():
    assert validate_analysis_count("num.iters", 10) == 10
    assert validate_analysis_count("burn.in", 0) == 0
    assert validate_analysis_count("thin", "2") == 2
    assert validate_analysis_count("num.chains", 3.0) == 3


def test_validate_analysis_count_rejects_invalid_counts():
    invalid_values = {
        "num.iters": 0,
        "burn.in": -1,
        "thin": 0,
        "num.chains": 1.5,
    }
    for name, value in invalid_values.items():
        with pytest.raises(ValueError, match="must be"):
            validate_analysis_count(name, value)


def test_normalize_confidence_level_params_validates_numeric_analysis_params():
    params = {
        "conf.level": 95,
        "digits": "3",
        "adjust": "0.5",
        "num.iters": "5000",
        "burn.in": "0",
        "thin": "2",
        "num.chains": "3",
        "theta.lower": "-2.5",
    }

    normalized = normalize_confidence_level_params(params)

    assert normalized["digits"] == 3
    assert normalized["adjust"] == 0.5
    assert normalized["num.iters"] == 5000
    assert normalized["burn.in"] == 0
    assert normalized["thin"] == 2
    assert normalized["num.chains"] == 3
    assert normalized["theta.lower"] == -2.5


def test_normalize_confidence_level_params_rejects_bad_numeric_analysis_params():
    bad_params = [
        {"adjust": -0.5},
        {"num.iters": 0},
        {"burn.in": -1},
        {"thin": 0},
        {"num.chains": 2.5},
        {"theta.lower": math.inf},
    ]
    for params in bad_params:
        with pytest.raises(ValueError):
            normalize_confidence_level_params(params)
