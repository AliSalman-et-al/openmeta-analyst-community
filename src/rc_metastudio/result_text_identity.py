"""Narrow cross-platform identity policy for analysis result text."""

import re


_HETEROGENEITY_HEADER = re.compile(r"(?m)^(\s*)τ²(?=\s+Q(?:\(|\s))")
_CONFIDENCE_BOUND_HEADER = re.compile(
    r"\b(?P<bound>Lower|Upper) bound \([0-9]+(?:\.[0-9]+)?% CI\)"
)


def normalize_heterogeneity_header(value: str) -> str:
    """Canonicalize only a line-leading tau-squared header before Q."""
    return _HETEROGENEITY_HEADER.sub(r"\1t²", value)


def normalize_packaged_summary_identity(value: str) -> str:
    """Remove intentional display-label variance from the packaged smoke identity."""
    normalized = normalize_heterogeneity_header(value)
    normalized = _CONFIDENCE_BOUND_HEADER.sub(r"\g<bound> bound", normalized)
    return " ".join(normalized.split())
