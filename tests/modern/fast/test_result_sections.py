import os
import sys


sys.path.insert(0, os.path.abspath("src"))

from result_sections import format_references, order_text_sections


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
        "3. OpenMetaAnalyst: Wallace, Byron C., Issa J. Dahabreh, Thomas A. "
        'Trikalinos, Joseph Lau, Paul Trow, and Christopher H. Schmid. "Closing '
        'the Gap between Methodologists and End-Users: R as a Computational '
        'Back-End." Journal of Statistical Software 49 (2012): 5."',
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
