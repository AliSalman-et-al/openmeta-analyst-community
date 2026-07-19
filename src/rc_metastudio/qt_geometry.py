"""Audited Qt logical-to-physical coordinate boundaries."""

from __future__ import annotations

import math


def logical_extent_to_physical_pixels(
    logical_extent: float, device_pixel_ratio: float
) -> int:
    """Convert a nonnegative logical extent using Qt-consistent half-up rounding.

    Geometry stays floating point until an API requires a physical pixel count.
    This named boundary deliberately does not use Python's ties-to-even ``round``.
    """
    extent = float(logical_extent)
    ratio = float(device_pixel_ratio)
    if not math.isfinite(extent) or extent < 0.0:
        raise ValueError("logical extent must be finite and nonnegative")
    if not math.isfinite(ratio) or ratio <= 0.0:
        raise ValueError("device pixel ratio must be finite and positive")
    return int(math.floor((extent * ratio) + 0.5))
