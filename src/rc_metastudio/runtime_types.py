# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Small runtime guards that turn optional framework values into contracts."""

from typing import TypeVar


T = TypeVar("T")


def required(value: T | None, description: str) -> T:
    """Return *value* or fail where an invariant supplied by Qt was broken."""
    if value is None:
        raise RuntimeError(f"Required Qt object is unavailable: {description}")
    return value
