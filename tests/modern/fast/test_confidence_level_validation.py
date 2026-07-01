import math
import os
import sys

import pytest


sys.path.insert(0, os.path.abspath("src"))

from meta_globals import normalize_confidence_level_params, validate_confidence_level


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
