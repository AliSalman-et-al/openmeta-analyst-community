# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared option-group registry for general and per-plot editing surfaces."""

PLOT_OPTION_GROUPS = {
    "forest": frozenset(
        ("style", "appearance", "columns", "forest", "axis", "summary")
    ),
    "regression": frozenset(("style", "appearance", "axis", "regression")),
}


def option_groups(plot_type):
    return PLOT_OPTION_GROUPS.get(plot_type, frozenset())
