# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate plot capabilities and resolve their user-interface contracts."""

REQUIRED_FIELDS = (
    "plot_kind",
    "editable",
    "styleable",
    "composition",
    "regenerator",
)

PLOT_OPTION_GROUPS = {
    "forest": frozenset(
        ("style", "appearance", "columns", "forest", "axis", "summary")
    ),
    "cumulative_forest": frozenset(
        ("style", "appearance", "forest", "axis", "summary")
    ),
    "leave_one_out_forest": frozenset(
        ("style", "appearance", "forest", "axis", "summary")
    ),
    "subgroup_forest": frozenset(
        ("style", "appearance", "forest", "axis", "summary")
    ),
    "regression": frozenset(("style", "appearance", "axis", "regression")),
    "roc": frozenset(),
    "sroc": frozenset(),
    "other": frozenset(),
}

REGENERATOR_NAMES = {
    "forest": "generate_forest_plot",
    "regression": "generate_reg_plot",
    "none": None,
}

COMPOSITIONS = frozenset(("single",))


def option_groups(plot_kind):
    return PLOT_OPTION_GROUPS.get(plot_kind, frozenset())


def regenerator_name(regenerator):
    try:
        return REGENERATOR_NAMES[regenerator]
    except KeyError:
        raise ValueError("Unknown plot regenerator: %s" % regenerator)


def validate_result(result):
    images = result.get("images") or {}
    descriptors = result.get("plot_capabilities") or {}
    missing = sorted(set(images) - set(descriptors))
    extra = sorted(set(descriptors) - set(images))
    if missing:
        raise ValueError(
            "Plot capability descriptor missing for: %s" % ", ".join(missing)
        )
    if extra:
        raise ValueError(
            "Plot capability descriptor has no matching image: %s"
            % ", ".join(extra)
        )

    normalized = {
        title: _validate_descriptor(title, descriptors[title]) for title in images
    }
    params_paths = result.get("image_params_paths") or {}
    missing_params = sorted(
        title
        for title, descriptor in normalized.items()
        if descriptor["editable"] and title not in params_paths
    )
    if missing_params:
        raise ValueError(
            "Editable plot capability descriptor missing plot data for: %s"
            % ", ".join(missing_params)
        )
    return normalized


def _validate_descriptor(title, descriptor):
    if not isinstance(descriptor, dict):
        raise ValueError("Plot capability descriptor for %s must be a mapping" % title)
    missing = [field for field in REQUIRED_FIELDS if field not in descriptor]
    extra = sorted(set(descriptor) - set(REQUIRED_FIELDS))
    if missing or extra:
        raise ValueError(
            "Invalid plot capability fields for %s (missing: %s; extra: %s)"
            % (title, ", ".join(missing) or "none", ", ".join(extra) or "none")
        )

    normalized = {field: descriptor[field] for field in REQUIRED_FIELDS}
    plot_kind = str(normalized["plot_kind"])
    if plot_kind not in PLOT_OPTION_GROUPS:
        raise ValueError("Unknown plot_kind for %s: %s" % (title, plot_kind))
    normalized["plot_kind"] = plot_kind

    for field in ("editable", "styleable"):
        if not isinstance(normalized[field], bool):
            raise ValueError("%s for %s must be boolean" % (field, title))

    composition = str(normalized["composition"])
    if composition not in COMPOSITIONS:
        raise ValueError("Unknown composition for %s: %s" % (title, composition))
    normalized["composition"] = composition

    regenerator = str(normalized["regenerator"])
    regenerator_name(regenerator)
    normalized["regenerator"] = regenerator
    if normalized["editable"] and regenerator == "none":
        raise ValueError("Editable plot %s requires a regenerator" % title)
    if normalized["styleable"] and not option_groups(plot_kind):
        raise ValueError("Styleable plot %s requires option groups" % title)
    return normalized
