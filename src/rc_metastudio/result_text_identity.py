"""Narrow cross-platform identity policy for analysis result text."""

import re


_HETEROGENEITY_HEADER = re.compile(r"(?m)^(\s*)τ²(?=\s+Q(?:\(|\s))")


def normalize_heterogeneity_header(value: str) -> str:
    """Canonicalize only a line-leading tau-squared header before Q."""
    return _HETEROGENEITY_HEADER.sub(r"\1t²", value)
