import os
import sys


sys.path.insert(0, os.path.abspath("src"))

from result_sections import (
    format_references,
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
            ("Bivariate Summary", "sens/spec"),
            ("Odds Ratio Summary", "dor"),
            ("References", "refs"),
        ]
    )

    assert [title for title, _value in ordered] == [
        "Bivariate Summary",
        "Negative Likelihood Ratio Summary",
        "Positive Likelihood Ratio Summary",
        "Odds Ratio Summary",
    ]


def test_display_titles_normalize_result_navigation_labels():
    context = {
        "text_titles": ["Summary", "Weights"],
        "image_titles": ["Forest Plot"],
    }

    assert section_display_title("Summary", context) == "Meta-Analysis Summary"
    assert (
        section_display_title("NLR and PLR Forest Plot", context)
        == "Negative and Positive Likelihood Ratio Forest Plot"
    )
    assert section_display_title("Density plots", context) == "Density Plots"
    assert (
        section_display_title("Within-study parameters - theta", context)
        == "Study-Level Threshold Parameters"
    )
    assert section_display_title("NLR Summary", context) == (
        "Negative Likelihood Ratio Summary"
    )
    assert section_display_title("DOR Forest plot", context) == (
        "Diagnostic Odds Ratio Forest Plot"
    )
    assert section_display_title("SROC", context) == "Summary ROC Plot"


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


def test_hsroc_sections_lead_with_clinical_result_before_model_details():
    ordered = order_display_sections(
        texts=[
            ("Within-study parameters - theta", "theta"),
            ("Between-study parameters", "between"),
            ("Clinical Accuracy Summary", "clinical"),
        ],
        images=[
            ("Density plots", "density.png"),
            ("Trace plots", "trace.png"),
            ("Summary ROC", "roc.png"),
        ],
        explicit_image_order=["Summary ROC", "Density plots", "Trace plots"],
    )

    assert [(section.kind, section.display_title) for section in ordered] == [
        ("text", "Clinical Accuracy Summary"),
        ("image", "Summary ROC"),
        ("text", "HSROC Model Parameters"),
        ("text", "Study-Level Threshold Parameters"),
        ("image", "Density Plots"),
        ("image", "Trace Plots"),
    ]
