import os
import sys


sys.path.insert(0, os.path.abspath("src"))

from rc_metastudio.result_sections import (
    format_references,
    normalize_identifier_label,
    order_display_sections,
    order_text_sections,
    section_display_title,
)


def test_format_references_preserves_method_order_and_dedupes_exact_matches():
    method_reference = (
        "Random-effects meta-analysis: DerSimonian, R., & Laird, N. (1986). "
        "Meta-analysis in clinical trials."
    )
    implementation_reference = (
        "Implementation reference: Viechtbauer, W. (2010). Conducting "
        "meta-analyses in R with the metafor package."
    )

    formatted = format_references(
        [method_reference, implementation_reference, implementation_reference]
    )

    assert formatted.splitlines() == [
        "1. " + method_reference,
        "2. " + implementation_reference,
    ]


def test_order_text_sections_puts_primary_diagnostic_accuracy_before_likelihoods():
    ordered = order_text_sections(
        [
            ("Negative Likelihood Ratio Summary", "nlr"),
            ("Positive Likelihood Ratio Summary", "plr"),
            ("Reitsma Summary", "sens/spec"),
            ("Odds Ratio Summary", "dor"),
            ("References", "refs"),
        ]
    )

    assert [title for title, _value in ordered] == [
        "Reitsma Summary",
        "Negative Likelihood Ratio Summary",
        "Positive Likelihood Ratio Summary",
        "Odds Ratio Summary",
    ]


def test_order_text_sections_does_not_group_composite_reitsma_labels():
    ordered = order_text_sections(
        [
            ("Summary operating point", "point"),
            ("Sampling-based summary ratios", "ratios"),
            ("SROC AUC", "auc"),
            ("Between-study heterogeneity", "heterogeneity"),
            (
                "Between-study heterogeneity: Sensitivity-specificity covariance",
                "covariance",
            ),
        ]
    )

    assert [title for title, _value in ordered] == [
        "Summary operating point",
        "Sampling-based summary ratios",
        "SROC AUC",
        "Between-study heterogeneity",
        "Between-study heterogeneity: Sensitivity-specificity covariance",
    ]


def test_order_text_sections_keeps_reitsma_meta_regression_contract_order():
    ordered = order_text_sections(
        [
            ("Sensitivity coefficients", "sens"),
            ("Specificity coefficients", "spec"),
            ("Moderator coding", "coding"),
            ("Overall ML likelihood-ratio test", "lrt"),
            ("Moderator block tests", "blocks"),
            ("Residual diagnostic I-squared", "i2"),
            ("Model information", "model"),
        ]
    )

    assert [title for title, _value in ordered] == [
        "Sensitivity coefficients",
        "Specificity coefficients",
        "Moderator coding",
        "Overall ML likelihood-ratio test",
        "Moderator block tests",
        "Residual diagnostic I-squared",
        "Model information",
    ]


def test_display_titles_normalize_result_navigation_labels():
    context = {
        "text_titles": ["Summary", "Weights"],
        "image_titles": ["Forest Plot"],
    }

    assert section_display_title("Summary", context) == "Meta-Analysis Summary"
    assert section_display_title("NLR Forest Plot", context) == (
        "Negative Likelihood Ratio Forest Plot"
    )
    assert section_display_title("PLR Forest Plot", context) == (
        "Positive Likelihood Ratio Forest Plot"
    )
    assert (
        section_display_title("Within-study parameters - theta", context)
        == "Within-study parameters - theta"
    )
    assert section_display_title("NLR Summary", context) == (
        "Negative Likelihood Ratio Summary"
    )
    assert section_display_title("DOR Forest plot", context) == (
        "Diagnostic Odds Ratio Forest Plot"
    )
    assert section_display_title("SROC", context) == "Summary ROC Plot"
    assert section_display_title("Warning", context) == "Interpretation"
    assert section_display_title("Data and eligibility", context) == "Analysis Summary"
    assert section_display_title("Tests", context) == "Small-Study Effects Tests"
    assert section_display_title("Pooled comparison", context) == "Pooled Estimates"
    assert section_display_title("Failures", context) == "Procedure Warnings"


def test_standard_meta_analysis_sections_keep_headline_result_with_plot():
    ordered = order_display_sections(
        texts=[
            ("Weights", "weights"),
            ("Summary", "summary"),
        ],
        images=[("Forest Plot", "forest.png")],
    )

    assert [(section.kind, section.display_title) for section in ordered] == [
        ("text", "Meta-Analysis Summary"),
        ("image", "Forest Plot"),
        ("text", "Weights"),
    ]


def test_small_study_effects_sections_put_plot_between_context_and_tests():
    ordered = order_display_sections(
        texts=[
            ("Failures", "none"),
            ("References", "refs"),
            ("Pooled comparison", "pool"),
            ("Tests", "tests"),
            ("Data and eligibility", "eligible"),
            ("Warning", "warning"),
        ],
        images=[("Ordinary Funnel Plot", "ordinary.png")],
    )

    assert [section.key for section in ordered] == [
        "Warning",
        "Data and eligibility",
        "Ordinary Funnel Plot",
        "Tests",
        "Pooled comparison",
        "Failures",
    ]


def test_trim_and_fill_navigation_titles_distinguish_estimate_from_plot():
    ordered = order_display_sections(
        texts=[
            ("Warning", "warning"),
            ("Data and eligibility", "eligibility"),
            ("Trim-and-fill left", "left estimate"),
            ("Trim-and-fill right", "right estimate"),
        ],
        images=[
            ("Trim-and-fill left", "left.png"),
            ("Trim-and-fill right", "right.png"),
        ],
    )

    assert [section.display_title for section in ordered] == [
        "Interpretation",
        "Analysis Summary",
        "Trim-and-Fill: Left Plot",
        "Trim-and-Fill: Right Plot",
        "Trim-and-Fill: Left Estimate",
        "Trim-and-Fill: Right Estimate",
    ]


def test_new_result_sections_preserve_producer_order():
    sections = [("Interpretation", "warning"), ("Methods not applicable", "none"), ("Tests", "tests")]

    assert order_text_sections(sections) == sections


def test_result_labels_expand_diagnostic_identifiers_without_r_console_names():
    assert normalize_identifier_label("posLR") == "Positive Likelihood Ratio"
    assert normalize_identifier_label("invnegLR") == "Inverse Negative Likelihood Ratio"
    assert normalize_identifier_label("Zhou.Dendukuri") == "Zhou-Dendukuri"
    assert normalize_identifier_label("Holling.Unadjusted") == "Holling (unadjusted)"
    assert normalize_identifier_label("I.squared") == "I²"
    assert normalize_identifier_label("tau2") == "τ²"


def test_references_accept_scalar_and_nested_values_without_character_splitting():
    assert format_references("One reference") == "1. One reference\n"
    assert format_references([["One reference"], "Two reference"]) == (
        "1. One reference\n2. Two reference\n"
    )


def test_reitsma_results_put_findings_and_sroc_before_supporting_details():
    ordered = order_display_sections(
        texts=[
            ("Model information", "model"),
            ("Diagnostic I-squared", "i2"),
            ("Clinical interpretation", "interpretation"),
            ("Sampling-based summary ratios", "ratios"),
            ("SROC AUC", "auc"),
            ("Summary operating point", "point"),
            ("Marginal prediction", "prediction"),
        ],
        images=[("SROC", "sroc.png")],
    )

    assert [section.key for section in ordered] == [
        "Clinical interpretation",
        "Summary operating point",
        "SROC AUC",
        "SROC",
        "Sampling-based summary ratios",
        "Marginal prediction",
        "Diagnostic I-squared",
        "Model information",
    ]


def test_reitsma_results_keep_contract_order_when_auc_is_unavailable():
    ordered = order_display_sections(
        texts=[
            ("Model information", "model"),
            ("Clinical interpretation", "interpretation"),
            ("Summary operating point", "point"),
            ("Sampling-based summary ratios", "ratios"),
            ("Marginal prediction", "prediction"),
        ],
        images=[("SROC", "sroc.png")],
    )

    assert [section.key for section in ordered] == [
        "Clinical interpretation",
        "Summary operating point",
        "SROC",
        "Sampling-based summary ratios",
        "Marginal prediction",
        "Model information",
    ]


def test_reitsma_meta_regression_keeps_coefficient_plots_adjacent():
    ordered = order_display_sections(
        texts=[
            ("Model information", "model"),
            ("Moderator coding", "coding"),
            ("Specificity coefficients", "spec"),
            ("Overall ML likelihood-ratio test", "overall"),
            ("Sensitivity coefficients", "sens"),
            ("Moderator block tests", "blocks"),
        ],
        images=[
            ("Specificity Moderator Coefficients", "spec.png"),
            ("Sensitivity Moderator Coefficients", "sens.png"),
        ],
    )

    assert [section.key for section in ordered] == [
        "Overall ML likelihood-ratio test",
        "Moderator block tests",
        "Sensitivity coefficients",
        "Sensitivity Moderator Coefficients",
        "Specificity coefficients",
        "Specificity Moderator Coefficients",
        "Moderator coding",
        "Model information",
    ]
