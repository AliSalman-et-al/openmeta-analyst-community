import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from rc_metastudio.analysis_method_labels import (  # noqa: E402
    diagnostic_metric_group_display_label,
    method_display_label,
    normalize_available_method_labels,
    parameter_display_label,
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


def test_method_labels_use_canonical_statistical_names():
    assert method_display_label("binary.fixed.mh") == (
        "Binary Fixed-Effect Mantel-Haenszel"
    )
    assert method_display_label("diagnostic.fixed.mh") == (
        "Diagnostic Fixed-Effect Mantel-Haenszel"
    )
    assert method_display_label("Binary Fixed-Effect Mantel Haenszel") == (
        "Binary Fixed-Effect Mantel-Haenszel"
    )


def test_available_method_labels_are_normalized_without_changing_method_keys():
    methods = {
        "binary.random": "binary.random",
        "Continuous Random-Effects": "continuous.random",
        "diagnostic.bivariate.ml": "diagnostic.bivariate.ml",
        "Binary Fixed-Effect Mantel Haenszel": "binary.fixed.mh",
    }

    assert normalize_available_method_labels(methods) == {
        "Binary Random-Effects": "binary.random",
        "Continuous Random-Effects": "continuous.random",
        "Bivariate (Maximum Likelihood)": "diagnostic.bivariate.ml",
        "Binary Fixed-Effect Mantel-Haenszel": "binary.fixed.mh",
    }


def test_parameter_value_labels_hide_internal_codes_without_changing_values():
    metadata = {"rm.method.names": {"DL": "DerSimonian-Laird"}}
    inference_metadata = {"inference.method.names": {"knha": "Knapp-Hartung"}}

    assert parameter_value_display_label("rm.method", "DL", metadata) == (
        "DerSimonian-Laird"
    )
    assert parameter_value_display_label("to", "only0") == "Only zero-event studies"
    assert parameter_value_display_label("to", "all") == "All studies"
    assert (
        parameter_value_display_label("inference.method", "knha", inference_metadata)
        == "Knapp-Hartung"
    )
    assert parameter_value_display_label("inference.method", "adhoc") == (
        "Modified Knapp-Hartung"
    )
    assert parameter_value_display_label("unknown", "raw-code") == "raw-code"


def test_parameter_labels_hide_internal_names_when_metadata_is_missing():
    assert parameter_display_label("theta.lower") == "Accuracy Prior Lower Bound"
    assert parameter_display_label("theta.upper") == "Accuracy Prior Upper Bound"
    assert parameter_display_label("lambda.lower") == "Threshold Prior Lower Bound"
    assert parameter_display_label("num.iters") == "Number of Iterations"
    assert parameter_display_label("conf.level") == "Confidence Level"
    assert parameter_display_label("rm.method") == "Random-Effects Method"
    assert parameter_display_label("inference.method") == "Inference Method"


def test_diagnostic_metric_group_labels_spell_out_abbreviations():
    assert diagnostic_metric_group_display_label("sens_spec") == (
        "Sensitivity and Specificity"
    )
    assert diagnostic_metric_group_display_label("lr_dor") == (
        "Likelihood Ratios and Diagnostic Odds Ratio"
    )
