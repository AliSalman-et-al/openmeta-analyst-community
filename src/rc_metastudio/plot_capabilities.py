# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate plot capabilities and resolve their user-interface contracts."""

from collections.abc import Mapping
from typing import TypedDict

from rc_metastudio.analysis_results import (
    PlotCapability,
    PlotComposition,
    PlotKind,
    PlotRegenerator,
)


class _Regenerator(TypedDict):
    function: str | None
    plot_kinds: frozenset[str]


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
    "subgroup_forest": frozenset(("style", "appearance", "forest", "axis", "summary")),
    "regression": frozenset(("style", "appearance", "axis", "regression")),
    "roc": frozenset(),
    "sroc": frozenset(("style", "appearance", "axis", "sroc")),
    # Reitsma coefficient plots are forest-shaped, but they have no study
    # rows or raw-count columns. Keep the shared style/axis editor while
    # omitting controls that cannot affect this coefficient-only renderer.
    "reitsma_coefficient": frozenset(("style", "appearance", "axis")),
    "funnel": frozenset(("funnel", "axis")),
    "contour_funnel": frozenset(("funnel", "axis")),
    "deeks_funnel": frozenset(("funnel", "axis")),
    "trimfill_funnel": frozenset(("funnel", "axis")),
    "other": frozenset(),
}

REGENERATORS: dict[str, _Regenerator] = {
    "forest": {
        "function": "generate_forest_plot",
        "plot_kinds": frozenset(
            ("forest", "cumulative_forest", "leave_one_out_forest", "subgroup_forest")
        ),
    },
    "regression": {
        "function": "generate_reg_plot",
        "plot_kinds": frozenset(("regression",)),
    },
    "funnel": {
        "function": "generate_small_study_effects_funnel",
        "plot_kinds": frozenset(
            ("funnel", "contour_funnel", "deeks_funnel", "trimfill_funnel")
        ),
    },
    "sroc": {
        "function": "generate_sroc_plot",
        "plot_kinds": frozenset(("sroc",)),
    },
    "none": {
        "function": None,
        "plot_kinds": frozenset(("roc", "other")),
    },
}

COMPOSITIONS = frozenset(("single",))


def option_groups(plot_kind: str) -> frozenset[str]:
    return PLOT_OPTION_GROUPS.get(plot_kind, frozenset())


def regenerator_name(regenerator: str) -> str | None:
    try:
        return REGENERATORS[regenerator]["function"]
    except KeyError:
        raise ValueError("Unknown plot regenerator: %s" % regenerator)


def validate_result(result: Mapping[str, object]) -> dict[str, PlotCapability]:
    images = _string_mapping(result.get("images"), "images")
    descriptors = _descriptor_mapping(result.get("plot_capabilities"))
    missing = sorted(set(images) - set(descriptors))
    extra = sorted(set(descriptors) - set(images))
    if missing:
        raise ValueError(
            "Plot capability descriptor missing for: %s" % ", ".join(missing)
        )
    if extra:
        raise ValueError(
            "Plot capability descriptor has no matching image: %s" % ", ".join(extra)
        )

    normalized = {
        title: _validate_descriptor(title, descriptors[title]) for title in images
    }
    params_paths = _string_mapping(
        result.get("image_params_paths"), "image_params_paths"
    )
    missing_params = sorted(
        title
        for title, descriptor in normalized.items()
        if descriptor.editable and title not in params_paths
    )
    if missing_params:
        raise ValueError(
            "Editable plot capability descriptor missing plot data for: %s"
            % ", ".join(missing_params)
        )
    return normalized


def _string_mapping(value: object, label: str) -> dict[str, str]:
    if value is None or value == [] or value == ():
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    normalized: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError(f"{label} keys and values must be text")
        normalized[key] = item
    return normalized


def _descriptor_mapping(value: object) -> dict[str, dict[str, object]]:
    if value is None or value == [] or value == ():
        return {}
    if not isinstance(value, dict):
        raise ValueError("plot_capabilities must be a mapping")
    normalized: dict[str, dict[str, object]] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, dict):
            raise ValueError("plot capability entries must be named mappings")
        descriptor: dict[str, object] = {}
        for field, field_value in item.items():
            if not isinstance(field, str):
                raise ValueError("plot capability field names must be text")
            descriptor[field] = field_value
        normalized[key] = descriptor
    return normalized


def _validate_descriptor(title: str, descriptor: dict[str, object]) -> PlotCapability:
    plot_kind, editable, styleable, composition, regenerator = _descriptor_values(title, descriptor)
    regenerator_name(regenerator)
    _validate_plot_rules(title, plot_kind, editable, styleable, regenerator)
    return PlotCapability(
        plot_kind=plot_kind,
        editable=editable,
        styleable=styleable,
        composition=composition,
        regenerator=regenerator,
    )


def _descriptor_values(
    title: str, descriptor: dict[str, object]
) -> tuple[PlotKind, bool, bool, PlotComposition, PlotRegenerator]:
    _validate_descriptor_fields(title, descriptor)
    editable, styleable = _descriptor_flags(title, descriptor)
    return (
        _plot_kind(descriptor["plot_kind"], title),
        editable,
        styleable,
        _composition(descriptor["composition"], title),
        _regenerator(descriptor["regenerator"], title),
    )


def _validate_descriptor_fields(title: str, descriptor: dict[str, object]) -> None:
    if not isinstance(descriptor, dict):
        raise ValueError("Plot capability descriptor for %s must be a mapping" % title)
    missing = [field for field in REQUIRED_FIELDS if field not in descriptor]
    extra = sorted(set(descriptor) - set(REQUIRED_FIELDS))
    if missing or extra:
        raise ValueError(
            "Invalid plot capability fields for %s (missing: %s; extra: %s)"
            % (title, ", ".join(missing) or "none", ", ".join(extra) or "none")
        )


def _descriptor_flags(title: str, descriptor: dict[str, object]) -> tuple[bool, bool]:
    editable = descriptor["editable"]
    styleable = descriptor["styleable"]
    if not isinstance(editable, bool):
        raise ValueError("editable for %s must be boolean" % title)
    if not isinstance(styleable, bool):
        raise ValueError("styleable for %s must be boolean" % title)
    return editable, styleable


def _validate_plot_rules(
    title: str,
    plot_kind: PlotKind,
    editable: bool,
    styleable: bool,
    regenerator: str,
) -> None:
    if editable and regenerator == "none":
        raise ValueError("Editable plot %s requires a regenerator" % title)
    if editable and plot_kind not in REGENERATORS[regenerator]["plot_kinds"]:
        raise ValueError(
            "Plot regenerator %s does not support plot kind %s for %s"
            % (regenerator, plot_kind, title)
        )
    if styleable and not option_groups(plot_kind):
        raise ValueError("Styleable plot %s requires option groups" % title)


def _plot_kind(value: object, title: str) -> PlotKind:
    if value == "forest":
        return "forest"
    if value == "cumulative_forest":
        return "cumulative_forest"
    if value == "leave_one_out_forest":
        return "leave_one_out_forest"
    if value == "subgroup_forest":
        return "subgroup_forest"
    if value == "regression":
        return "regression"
    if value == "roc":
        return "roc"
    if value == "sroc":
        return "sroc"
    if value == "funnel":
        return "funnel"
    if value == "contour_funnel":
        return "contour_funnel"
    if value == "deeks_funnel":
        return "deeks_funnel"
    if value == "trimfill_funnel":
        return "trimfill_funnel"
    if value == "other":
        return "other"
    raise ValueError("Unknown plot_kind for %s: %s" % (title, value))


def _composition(value: object, title: str) -> PlotComposition:
    if value == "single":
        return "single"
    raise ValueError("Unknown composition for %s: %s" % (title, value))


def _regenerator(value: object, title: str) -> PlotRegenerator:
    if value == "forest":
        return "forest"
    if value == "regression":
        return "regression"
    if value == "funnel":
        return "funnel"
    if value == "sroc":
        return "sroc"
    if value == "none":
        return "none"
    raise ValueError("Unknown plot regenerator for %s: %s" % (title, value))
