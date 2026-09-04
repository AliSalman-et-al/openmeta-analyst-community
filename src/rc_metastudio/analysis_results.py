# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared static contracts for analysis results crossing the R boundary."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, TypedDict, cast, overload


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
        return iter(
            ("plot_kind", "editable", "styleable", "composition", "regenerator")
        )

    def __len__(self) -> int:
        return 5

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            return dict(self.items()) == dict(other.items())
        return super().__eq__(other)


class RawAnalysisResult(TypedDict, total=False):
    """Untrusted result shape accepted at the application boundary."""

    version: int
    texts: dict[str, str]
    images: dict[str, str]
    display_images: dict[str, str]
    image_var_names: dict[str, str]
    image_params_paths: dict[str, str]
    image_order: list[str] | None
    plot_capabilities: dict[str, dict[str, object]]
    sections: list[dict[str, object]]


@dataclass(frozen=True, slots=True)
class ResultSection:
    """Stable result identity and stored display/regeneration data."""

    semantic_id: str
    kind: Literal["text", "image"]
    order: int
    title: str
    value: str
    source_key: str
    plot_kind: PlotKind | None = None
    plot_data: str | None = None
    capability: PlotCapability | None = None


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Validated immutable result contract consumed by application adapters."""

    version: int
    texts: Mapping[str, str]
    images: Mapping[str, str]
    display_images: Mapping[str, str]
    image_var_names: Mapping[str, str]
    image_params_paths: Mapping[str, str]
    image_order: tuple[str, ...] | None
    plot_capabilities: Mapping[str, PlotCapability]
    sections: tuple[ResultSection, ...]

    @overload
    def __getitem__(self, key: Literal["version"]) -> int: ...

    @overload
    def __getitem__(self, key: Literal["texts"]) -> Mapping[str, str]: ...

    @overload
    def __getitem__(
        self,
        key: Literal[
            "images", "display_images", "image_var_names", "image_params_paths"
        ],
    ) -> Mapping[str, str]: ...

    @overload
    def __getitem__(self, key: Literal["image_order"]) -> tuple[str, ...] | None: ...

    @overload
    def __getitem__(
        self, key: Literal["plot_capabilities"]
    ) -> Mapping[str, PlotCapability]: ...

    @overload
    def __getitem__(self, key: Literal["sections"]) -> tuple[ResultSection, ...]: ...

    @overload
    def __getitem__(self, key: str) -> object: ...

    def __getitem__(self, key: str) -> object:
        values = {
            "version": self.version,
            "texts": self.texts,
            "images": self.images,
            "display_images": self.display_images,
            "image_var_names": self.image_var_names,
            "image_params_paths": self.image_params_paths,
            "image_order": self.image_order,
            "plot_capabilities": self.plot_capabilities,
            "sections": self.sections,
        }
        return values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(
            (
                "version",
                "texts",
                "images",
                "display_images",
                "image_var_names",
                "image_params_paths",
                "image_order",
                "plot_capabilities",
                "sections",
            )
        )

    def __len__(self) -> int:
        return 9

    def get(self, key: str, default: object = None) -> object:
        try:
            return self[key]
        except KeyError:
            return default


def _sections(
    texts: Mapping[str, str],
    images: Mapping[str, str],
    image_params_paths: Mapping[str, str],
    capabilities: Mapping[str, PlotCapability],
    metadata: Iterable[Mapping[str, object]],
) -> tuple[ResultSection, ...]:
    result: list[ResultSection] = []
    seen_ids: set[str] = set()
    seen_orders: set[int] = set()
    seen_values: set[tuple[str, str]] = set()
    for item in metadata:
        section = _result_section(item, texts, images, image_params_paths, capabilities)
        semantic_id = section.semantic_id
        order = section.order
        value_key = (section.kind, section.source_key)
        if semantic_id in seen_ids or order in seen_orders:
            raise ValueError(
                "analysis result section identity and order must be unique"
            )
        if value_key in seen_values:
            raise ValueError("analysis result values must have exactly one section")
        seen_ids.add(semantic_id)
        seen_orders.add(order)
        seen_values.add(value_key)
        result.append(section)
    expected_values = {("text", key) for key in texts} | {
        ("image", key) for key in images
    }
    if seen_values != expected_values:
        raise ValueError("analysis result sections must cover every text and image")
    return tuple(result)


def _result_section(
    item: Mapping[str, object],
    texts: Mapping[str, str],
    images: Mapping[str, str],
    image_params_paths: Mapping[str, str],
    capabilities: Mapping[str, PlotCapability],
) -> ResultSection:
    semantic_id, kind, order, title, source_key = _section_fields(item)
    values = texts if kind == "text" else images
    value = values.get(source_key)
    if value is None:
        raise ValueError("analysis result section references missing value")
    if kind == "text":
        return ResultSection(semantic_id, kind, order, title, value, source_key)
    capability = capabilities.get(source_key)
    if capability is None:
        raise ValueError("analysis result image has no plot capability")
    return ResultSection(
        semantic_id,
        kind,
        order,
        title,
        value,
        source_key,
        capability.plot_kind,
        image_params_paths.get(source_key),
        capability,
    )


def _section_fields(
    item: Mapping[str, object],
) -> tuple[str, Literal["text", "image"], int, str, str]:
    semantic_id = item.get("id")
    kind = item.get("kind")
    source_key = item.get("source_key")
    title = item.get("title")
    order = item.get("order")
    if not isinstance(semantic_id, str) or not semantic_id:
        raise ValueError("analysis result section id must be non-empty text")
    if kind not in ("text", "image"):
        raise ValueError("analysis result section kind is invalid")
    if not isinstance(source_key, str) or not source_key:
        raise ValueError("analysis result section source key must be non-empty text")
    if not isinstance(title, str) or not title:
        raise ValueError("analysis result section title must be non-empty text")
    if type(order) is not int or order < 0:
        raise ValueError("analysis result section order must be a non-negative integer")
    return semantic_id, cast(Literal["text", "image"], kind), order, title, source_key


def _freeze_result(
    texts: Mapping[str, str],
    images: Mapping[str, str],
    display_images: Mapping[str, str],
    image_var_names: Mapping[str, str],
    image_params_paths: Mapping[str, str],
    image_order: Iterable[str] | None,
    plot_capabilities: Mapping[str, PlotCapability],
    metadata: Iterable[Mapping[str, object]] = (),
) -> AnalysisResult:
    return AnalysisResult(
        version=1,
        texts=MappingProxyType(dict(texts)),
        images=MappingProxyType(dict(images)),
        display_images=MappingProxyType(dict(display_images)),
        image_var_names=MappingProxyType(dict(image_var_names)),
        image_params_paths=MappingProxyType(dict(image_params_paths)),
        image_order=None if image_order is None else tuple(image_order),
        plot_capabilities=MappingProxyType(dict(plot_capabilities)),
        sections=_sections(
            texts, images, image_params_paths, plot_capabilities, metadata
        ),
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
        "version": _result_version(source.get("version")),
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
        "sections": _section_metadata(source.get("sections")),
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
        raw["sections"],
    )


def _result_version(value: object) -> int:
    if type(value) is not int or value != 1:
        raise ValueError(f"unsupported analysis result version: {value!r}")
    return value


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


def _section_metadata(value: object) -> list[dict[str, object]]:
    if value is None:
        raise ValueError("analysis result sections are required")
    if not isinstance(value, (list, tuple)):
        raise ValueError("sections must be a list")
    metadata: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("sections entries must be mappings")
        metadata.append({str(key): field for key, field in item.items()})
    return metadata
