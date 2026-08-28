from collections.abc import Sequence
from typing import TypeVar


_Cell = TypeVar("_Cell")


def normalize_rows(
    rows: Sequence[Sequence[_Cell]], minimum_width: int = 0
) -> list[list[_Cell | str]]:
    """Return rows padded with blanks to a shared width."""
    if not rows:
        return []

    width = max([len(row) for row in rows] + [minimum_width])
    if width == 0:
        return []
    return [list(row) + [""] * (width - len(row)) for row in rows]
