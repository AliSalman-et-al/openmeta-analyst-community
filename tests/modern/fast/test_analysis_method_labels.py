import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from analysis_method_labels import (  # noqa: E402
    method_display_label,
    normalize_available_method_labels,
    parameter_value_display_label,
)


def test_known_analysis_method_keys_have_user_facing_labels():
    method_keys = [
        "binary.fixed.inv.var",
        "binary.fixed.mh",
        "binary.fixed.peto",
        "binary.random",
        "continuous.fixed",
        "continuous.random",
        "diagnostic.fixed.inv.var",
        "diagnostic.fixed.mh",
        "diagnostic.fixed.peto",
        "diagnostic.random",
        "diagnostic.hsroc",
        "diagnostic.bivariate.ml",
        "meta.regression",
    ]

    for method_key in method_keys:
        label = method_display_label(method_key)
        assert label != method_key
        assert "." not in label


def test_available_method_labels_are_normalized_without_changing_method_keys():
    methods = {
        "binary.random": "binary.random",
        "Continuous Random-Effects": "continuous.random",
        "diagnostic.bivariate.ml": "diagnostic.bivariate.ml",
    }

    assert normalize_available_method_labels(methods) == {
        "Binary Random-Effects": "binary.random",
        "Continuous Random-Effects": "continuous.random",
        "Bivariate (Maximum Likelihood)": "diagnostic.bivariate.ml",
    }


def test_parameter_value_labels_hide_internal_codes_without_changing_values():
    metadata = {"rm.method.names": {"DL": "DerSimonian-Laird"}}

    assert parameter_value_display_label("rm.method", "DL", metadata) == (
        "DerSimonian-Laird"
    )
    assert parameter_value_display_label("to", "only0") == "Only zero-event studies"
    assert parameter_value_display_label("to", "all") == "All studies"
    assert parameter_value_display_label("unknown", "raw-code") == "raw-code"
