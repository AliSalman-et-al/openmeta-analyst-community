# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared static contracts for analysis results crossing the R boundary."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Self, SupportsIndex, TypedDict, overload


PlotKind = Literal[
    "forest",
    "cumulative_forest",
    "leave_one_out_forest",
    "subgroup_forest",
    "regression",
    "roc",
    "sroc",
    "funnel",
    "contour_funnel",
    "deeks_funnel",
    "trimfill_funnel",
    "other",
]
PlotComposition = Literal["single"]
PlotRegenerator = Literal["forest", "regression", "funnel", "sroc", "none"]


@dataclass(frozen=True, slots=True)
class PlotCapability(Mapping[str, object]):
    """Immutable capability data attached to one semantic plot artifact."""

    plot_kind: PlotKind
    editable: bool
    styleable: bool
    composition: PlotComposition
    regenerator: PlotRegenerator

    def __getitem__(self, key: str) -> object:
        if key == "plot_kind":
            return self.plot_kind
        if key == "editable":
            return self.editable
        if key == "styleable":
            return self.styleable
        if key == "composition":
            return self.composition
        if key == "regenerator":
            return self.regenerator
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(("plot_kind", "editable", "styleable", "composition", "regenerator"))

    def __len__(self) -> int:
        return 5

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            return dict(self.items()) == dict(other.items())
        return super().__eq__(other)


class RawAnalysisResult(TypedDict, total=False):
    """Untrusted result shape accepted at the application boundary."""

    texts: dict[str, str]
    images: dict[str, str]
    display_images: dict[str, str]
    image_var_names: dict[str, str]
    image_params_paths: dict[str, str]
    image_order: list[str] | None
    plot_capabilities: dict[str, dict[str, object]]


class FrozenStrings(Sequence[str]):
    """Tuple-backed sequence that keeps the old list equality contract."""

    def __init__(self, values: Iterable[str]) -> None:
        self._values = tuple(values)

    @overload
    def __getitem__(self, index: int) -> str: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[str, ...]: ...

    def __getitem__(self, index: int | slice) -> str | tuple[str, ...]:
        return self._values[index]

    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (list, tuple, FrozenStrings)):
            return tuple(self) == tuple(other)
        return False

    def __repr__(self) -> str:
        return repr(list(self._values))


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Validated immutable result contract consumed by application adapters."""

    texts: Mapping[str, str]
    images: Mapping[str, str]
    display_images: Mapping[str, str]
    image_var_names: Mapping[str, str]
    image_params_paths: Mapping[str, str]
    image_order: FrozenStrings | None
    plot_capabilities: Mapping[str, PlotCapability]

    @overload
    def __getitem__(self, key: Literal["texts"]) -> Mapping[str, str]: ...

    @overload
    def __getitem__(self, key: Literal["images", "display_images", "image_var_names", "image_params_paths"]) -> Mapping[str, str]: ...

    @overload
    def __getitem__(self, key: Literal["image_order"]) -> FrozenStrings | None: ...

    @overload
    def __getitem__(self, key: Literal["plot_capabilities"]) -> Mapping[str, PlotCapability]: ...

    @overload
    def __getitem__(self, key: str) -> object: ...

    def __getitem__(self, key: str) -> object:
        if key == "texts":
            return self.texts
        if key == "images":
            return self.images
        if key == "display_images":
            return self.display_images
        if key == "image_var_names":
            return self.image_var_names
        if key == "image_params_paths":
            return self.image_params_paths
        if key == "image_order":
            return self.image_order
        if key == "plot_capabilities":
            return self.plot_capabilities
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(("texts", "images", "display_images", "image_var_names", "image_params_paths", "image_order", "plot_capabilities"))

    def __len__(self) -> int:
        return 7

    def get(self, key: str, default: object = None) -> object:
        try:
            return self[key]
        except KeyError:
            return default


class _FrozenList(list[str]):
    """Deprecated private helper retained only for old callers during parsing."""

    def _immutable(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("analysis result values are immutable")

    __setitem__ = __delitem__ = append = clear = extend = insert = remove = reverse = sort = _immutable

    def pop(self, index: SupportsIndex = -1, /) -> str:
        raise TypeError("analysis result values are immutable")

    def __iadd__(self, value: Iterable[str], /) -> Self:
        raise TypeError("analysis result values are immutable")

    def __imul__(self, value: SupportsIndex, /) -> Self:
        raise TypeError("analysis result values are immutable")


def _freeze_result(
    texts: Mapping[str, str],
    images: Mapping[str, str],
    display_images: Mapping[str, str],
    image_var_names: Mapping[str, str],
    image_params_paths: Mapping[str, str],
    image_order: Iterable[str] | None,
    plot_capabilities: Mapping[str, PlotCapability],
) -> AnalysisResult:
    return AnalysisResult(
        texts=MappingProxyType(dict(texts)),
        images=MappingProxyType(dict(images)),
        display_images=MappingProxyType(dict(display_images)),
        image_var_names=MappingProxyType(dict(image_var_names)),
        image_params_paths=MappingProxyType(dict(image_params_paths)),
        image_order=None if image_order is None else FrozenStrings(image_order),
        plot_capabilities=MappingProxyType(dict(plot_capabilities)),
    )


def empty_analysis_result() -> AnalysisResult:
    return _freeze_result({}, {}, {}, {}, {}, None, {})


def parse_analysis_result(value: object) -> AnalysisResult:
    """Validate untrusted backend output before application code consumes it."""
    if not isinstance(value, Mapping):
        raise ValueError("analysis result must be a mapping")
    source: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError("analysis result field names must be text")
        source[key] = item
    raw: RawAnalysisResult = {
        "texts": _string_mapping(source.get("texts"), "texts"),
        "images": _string_mapping(source.get("images"), "images"),
        "display_images": _string_mapping(
            source.get("display_images"), "display_images"
        ),
        "image_var_names": _string_mapping(
            source.get("image_var_names"), "image_var_names"
        ),
        "image_params_paths": _string_mapping(
            source.get("image_params_paths"), "image_params_paths"
        ),
        "image_order": _optional_string_list(source.get("image_order"), "image_order"),
        "plot_capabilities": _object_mapping(
            source.get("plot_capabilities"), "plot_capabilities"
        ),
    }

    # Local import avoids a module cycle: plot_capabilities owns descriptor
    # policy and imports the shared result types defined above.
    from rc_metastudio import plot_capabilities

    capabilities = plot_capabilities.validate_result(raw)
    extra_display_images = sorted(set(raw["display_images"]) - set(raw["images"]))
    if extra_display_images:
        raise ValueError(
            "Display artifacts have no matching plot artifact: %s"
            % ", ".join(extra_display_images)
        )
    return _freeze_result(
        raw["texts"],
        raw["images"],
        raw["display_images"],
        raw["image_var_names"],
        raw["image_params_paths"],
        raw["image_order"],
        capabilities,
    )


def _string_mapping(value: object, label: str) -> dict[str, str]:
    if value is None or value == [] or value == ():
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError(f"{label} keys and values must be text")
        result[key] = item
    return result


def _object_mapping(value: object, label: str) -> dict[str, dict[str, object]]:
    if value is None or value == [] or value == ():
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    result: dict[str, dict[str, object]] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, Mapping):
            raise ValueError(f"{label} entries must be named mappings")
        descriptor: dict[str, object] = {}
        for field, field_value in item.items():
            if not isinstance(field, str):
                raise ValueError(f"{label} field names must be text")
            descriptor[field] = field_value
        result[key] = descriptor
    return result


def _optional_string_list(value: object, label: str) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{label} must be a list of text values or null")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{label} must be a list of text values or null")
        result.append(item)
    return result
