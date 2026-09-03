from rc_metastudio.result_text_identity import normalize_packaged_summary_identity


def test_packaged_summary_identity_ignores_display_only_confidence_labels():
    old = "  Estimate  Lower bound  Upper bound  p-value\n  1.2  1.0  1.4  0.01"
    labelled = (
        "  Estimate  Lower bound (90% CI)  Upper bound (90% CI)  p-value\n"
        "  1.2  1.0  1.4  0.01"
    )

    assert normalize_packaged_summary_identity(labelled) == (
        normalize_packaged_summary_identity(old)
    )
    assert normalize_packaged_summary_identity(labelled) == (
        "Estimate Lower bound Upper bound p-value 1.2 1.0 1.4 0.01"
    )
