def normalize_rows(rows, minimum_width=0):
    """Return rows padded with blanks to a shared width."""
    if not rows:
        return []

    width = max([len(row) for row in rows] + [minimum_width])
    if width == 0:
        return []
    return [row + [""] * (width - len(row)) for row in rows]
