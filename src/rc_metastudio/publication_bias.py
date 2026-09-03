# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
"""Typed boundary for the guided small-study effects analysis.

The statistical policy lives in RCMetaR.  This module deliberately contains
only the immutable request shape and the small amount of parsing needed to
present RCMetaR's eligibility report in Qt.  Keeping this boundary boring is
important: a request is serialized once and cannot change while R is running.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Literal, TypeAlias, TypeVar

from rc_metastudio.analysis_results import AnalysisResult, parse_analysis_result


class CorrectionPolicy(str, Enum):
    """Continuity-correction target labels used by RCMetaR."""

    STUDIES_WITH_ANY_ZERO_CELL = "Studies with any zero cell"
    ALL_STUDIES = "All studies"
    ALL_STUDIES_IF_ANY_ZERO_EXISTS = "All studies if any zero exists"


class TestMethod(str, Enum):
    __test__ = False

    CLASSICAL_EGGER = "classical-egger"
    MIXED_EFFECTS_EGGER = "mixed-effects-egger"
    BEGG_MAZUMDAR = "begg-mazumdar"
    HARBORD = "harbord"
    PETERS = "peters"
    PUSTEJOVSKY_RODGERS = "pustejovsky-rodgers"
    RUCKER_AS_RE = "rucker-as-re"
    DEEKS = "deeks"


class FunnelKind(str, Enum):
    ORDINARY = "ordinary"
    CONTOUR = "contour"
    DEEKS = "deeks"


class FunnelStyle(str, Enum):
    DEFAULT = "default"
    REVMAN = "revman"
    BMJ = "bmj"


FUNNEL_STYLE_LABELS = {
    FunnelStyle.DEFAULT: "Default (metafor)",
    FunnelStyle.REVMAN: "RevMan",
    FunnelStyle.BMJ: "BMJ",
}
FUNNEL_STYLE_PRESETS = {
    FunnelStyle.DEFAULT: {
        "point_symbol": 19,
        "point_color": "#2F5597",
        "reference_color": "#2F5597",
        "region_color": "#DDE6F4",
        "background_color": "#FFFFFF",
    },
    FunnelStyle.REVMAN: {
        "point_symbol": 15,
        "point_color": "#111111",
        "reference_color": "#000000",
        "region_color": "#D9D9D9",
        "background_color": "#FFFFFF",
    },
    FunnelStyle.BMJ: {
        "point_symbol": 18,
        "point_color": "#6B58A6",
        "reference_color": "#6B58A6",
        "region_color": "#E8E2F4",
        "background_color": "#FFFFFF",
    },
}


class TrimAndFillSide(str, Enum):
    AUTO = "auto"
    LEFT = "left"
    RIGHT = "right"


class TrimAndFillEstimator(str, Enum):
    L0 = "L0"
    R0 = "R0"


class TrimAndFillModel(str, Enum):
    RANDOM = "random"
    COMMON = "common"


class PooledDisplayModel(str, Enum):
    """Model whose estimate is shown on a funnel plot."""

    COMMON = "common"
    RANDOM = "random"


class LabelPolicy(str, Enum):
    NONE = "none"
    OUTSIDE_REGION = "outside-pseudo-confidence-region"
    ALL = "all"


@dataclass(frozen=True)
class FunnelPlotSpec:
    """Explicit ordinary-funnel presentation request."""

    kind: FunnelKind
    confidence_level: float = 95.0
    show_sampling_region: bool = True
    reverse_standard_error_axis: bool = True
    label_policy: LabelPolicy = LabelPolicy.NONE
    sampling_confidence_level: float = 95.0
    include_tau2: bool = False
    point_size: float = 1.0
    reference_line_visible: bool = True
    contour_levels: tuple[float, ...] = ()
    pooled_overlay_visible: bool = True
    style: FunnelStyle = FunnelStyle.DEFAULT
    point_symbol: int = 19
    point_color: str = "#2F5597"
    reference_color: str = "#2F5597"
    region_color: str = "#DDE6F4"
    background_color: str = "#FFFFFF"

    def __post_init__(self) -> None:
        if not isinstance(self.kind, FunnelKind):
            raise TypeError("funnel kind must use FunnelKind")
        if not 0 < float(self.confidence_level) < 100:
            raise ValueError("funnel confidence level must be between 0 and 100")
        if not isinstance(self.label_policy, LabelPolicy):
            raise TypeError("label policy must use LabelPolicy")
        if not isinstance(self.style, FunnelStyle):
            raise TypeError("funnel style must use FunnelStyle")
        if not 0 < float(self.sampling_confidence_level) < 100:
            raise ValueError("sampling confidence level must be between 0 and 100")
        if float(self.point_size) <= 0:
            raise ValueError("funnel point size must be positive")
        if int(self.point_symbol) < 0:
            raise ValueError("funnel point symbol must be non-negative")
        if self.kind is FunnelKind.CONTOUR and not self.contour_levels:
            object.__setattr__(self, "contour_levels", (90.0, 95.0, 99.0))
        if self.kind is not FunnelKind.CONTOUR and self.contour_levels:
            raise ValueError("contour levels apply only to contour funnels")
        if any(not 0 < float(level) < 100 for level in self.contour_levels):
            raise ValueError("contour levels must be between 0 and 100")
        if not isinstance(self.point_color, str) or not self.point_color.strip():
            raise ValueError("funnel point color must be text")
        if (
            not isinstance(self.reference_color, str)
            or not self.reference_color.strip()
        ):
            raise ValueError("funnel reference color must be text")
        if not isinstance(self.region_color, str) or not self.region_color.strip():
            raise ValueError("funnel region color must be text")
        if (
            not isinstance(self.background_color, str)
            or not self.background_color.strip()
        ):
            raise ValueError("funnel background color must be text")


@dataclass(frozen=True)
class AsymmetryTestSpec:
    """Explicit asymmetry procedure selected by RCMetaR eligibility."""

    method: TestMethod

    def __post_init__(self) -> None:
        if not isinstance(self.method, TestMethod):
            raise TypeError("asymmetry method must use TestMethod")


@dataclass(frozen=True)
class SensitivitySpec:
    """Explicit sensitivity-analysis controls for this request."""

    trim_and_fill: bool = False
    side: TrimAndFillSide = TrimAndFillSide.AUTO
    estimator: TrimAndFillEstimator = TrimAndFillEstimator.L0
    model: TrimAndFillModel = TrimAndFillModel.RANDOM
    extrapolation: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.side, TrimAndFillSide):
            raise TypeError("trim-and-fill side must use TrimAndFillSide")
        if not isinstance(self.estimator, TrimAndFillEstimator):
            raise TypeError("trim-and-fill estimator must use TrimAndFillEstimator")
        if not isinstance(self.model, TrimAndFillModel):
            raise TypeError("trim-and-fill model must use TrimAndFillModel")


@dataclass(frozen=True)
class PooledDisplaySpec:
    """Explicit pooled-display model settings."""

    model: PooledDisplayModel = PooledDisplayModel.COMMON
    method_tau: str = "REML"

    def __post_init__(self) -> None:
        if not isinstance(self.model, PooledDisplayModel):
            raise TypeError("pooled display model must use PooledDisplayModel")
        if self.method_tau != "REML":
            raise ValueError("pooled display tau estimator must be REML")


AnalysisFamily: TypeAlias = Literal["binary", "continuous", "diagnostic"]
_MappingKey = TypeVar("_MappingKey")


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _string_key_mapping(
    value: Mapping[_MappingKey, object], field_name: str
) -> dict[str, object]:
    """Validate and normalize mappings crossing the untyped R boundary."""
    return {_text(key, f"{field_name} key"): item for key, item in value.items()}


def _float(value: object, field_name: str) -> float:
    """Convert the scalar values accepted by R's serialized report."""
    if not isinstance(value, (int, float, str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be numeric")
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be numeric") from error


def _test_method(value: str | TestMethod) -> TestMethod:
    raw = value.value if isinstance(value, TestMethod) else value
    try:
        return TestMethod(raw)
    except (TypeError, ValueError) as error:
        raise ValueError(f"unsupported small-study effects test: {raw!r}") from error


def _funnel_kind(value: str | FunnelKind) -> FunnelKind:
    raw = value.value if isinstance(value, FunnelKind) else value
    try:
        return FunnelKind(raw)
    except (TypeError, ValueError) as error:
        raise ValueError(f"unsupported funnel kind: {raw!r}") from error


def _frozen_mapping(
    value: Mapping[str, object] | None,
) -> tuple[tuple[str, object], ...]:
    if value is None:
        return ()
    items: list[tuple[str, object]] = []
    for key, item in value.items():
        items.append((_text(key, "mapping key"), item))
    return tuple(sorted(items))


def _text_values(value: object, field_name: str) -> tuple[object, ...]:
    """Normalize R's length-one vectors to the same wire shape as lists."""
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(value)
    raise ValueError(f"{field_name} must be a sequence or scalar text value")


@dataclass(frozen=True)
class SmallStudyEffectsRequest:
    """One complete serialized small-study effects execution request."""

    data_type: AnalysisFamily
    metric: str
    confidence_level: float = 95.0
    correction_policy: CorrectionPolicy | None = None
    plot_specs: tuple[FunnelPlotSpec, ...] = (FunnelPlotSpec(FunnelKind.ORDINARY),)
    test_specs: tuple[AsymmetryTestSpec, ...] = ()
    sensitivity_specs: tuple[SensitivitySpec, ...] = ()
    pooled_display: PooledDisplaySpec = PooledDisplaySpec()
    version: int = 1

    def __post_init__(self) -> None:
        if self.version != 1:
            raise ValueError(
                "unsupported small-study effects request version: %s" % self.version
            )
        if self.data_type not in ("binary", "continuous", "diagnostic"):
            raise ValueError(
                f"unsupported small-study effects data family: {self.data_type!r}"
            )
        _text(self.metric, "metric")
        if self.data_type == "diagnostic" and self.metric != "DOR":
            raise ValueError(
                "diagnostic small-study effects requests use read-only DOR"
            )
        try:
            level = float(self.confidence_level)
        except (TypeError, ValueError) as error:
            raise ValueError("confidence_level must be numeric") from error
        if not 0 < level < 100:
            raise ValueError("confidence_level must be between 0 and 100")
        if self.correction_policy is not None and not isinstance(
            self.correction_policy, CorrectionPolicy
        ):
            raise ValueError("correction_policy must use CorrectionPolicy")
        if not isinstance(self.pooled_display, PooledDisplaySpec):
            raise TypeError("pooled_display must use PooledDisplaySpec")
        if not all(isinstance(spec, FunnelPlotSpec) for spec in self.plot_specs):
            raise TypeError("plot_specs must contain FunnelPlotSpec values")
        if not all(isinstance(spec, AsymmetryTestSpec) for spec in self.test_specs):
            raise TypeError("test_specs must contain AsymmetryTestSpec values")
        if not all(
            isinstance(spec, SensitivitySpec) for spec in self.sensitivity_specs
        ):
            raise TypeError("sensitivity_specs must contain SensitivitySpec values")
        if self.data_type == "diagnostic":
            if any(spec.kind is not FunnelKind.DEEKS for spec in self.plot_specs):
                raise ValueError("diagnostic requests use only the Deeks funnel")
            if any(spec.method is not TestMethod.DEEKS for spec in self.test_specs):
                raise ValueError("diagnostic requests use only the Deeks test")
            if any(
                spec.trim_and_fill or spec.extrapolation
                for spec in self.sensitivity_specs
            ):
                raise ValueError(
                    "diagnostic requests do not support generic sensitivities"
                )

    @classmethod
    def create(
        cls,
        *,
        data_type: str,
        metric: str,
        confidence_level: float = 95.0,
        correction_policy: CorrectionPolicy | str | None = None,
        selected_tests: Sequence[str | TestMethod] = (),
        selected_funnels: Sequence[str | FunnelKind] = (FunnelKind.ORDINARY.value,),
        label_policy: LabelPolicy | str = LabelPolicy.NONE,
        sampling_confidence_level: float = 95.0,
        include_tau2: bool = False,
        point_size: float = 1.0,
        reference_line_visible: bool = True,
        contour_levels: Sequence[float] = (),
        pooled_overlay_visible: bool = True,
        style: FunnelStyle | str = FunnelStyle.DEFAULT,
        trim_and_fill: bool = False,
        trim_and_fill_side: TrimAndFillSide | str = TrimAndFillSide.AUTO,
        trim_and_fill_estimator: TrimAndFillEstimator | str = TrimAndFillEstimator.L0,
        trim_and_fill_model: TrimAndFillModel | str = TrimAndFillModel.RANDOM,
        extrapolation: bool = False,
    ) -> SmallStudyEffectsRequest:
        policy = (
            None if correction_policy is None else CorrectionPolicy(correction_policy)
        )
        label = LabelPolicy(label_policy)
        funnel_style = FunnelStyle(style)
        style_preset = FUNNEL_STYLE_PRESETS[funnel_style]
        funnel_values = (
            (FunnelKind.DEEKS.value,) if data_type == "diagnostic" else selected_funnels
        )
        funnels = tuple(
            FunnelPlotSpec(
                _funnel_kind(item),
                float(confidence_level),
                label_policy=label,
                sampling_confidence_level=float(sampling_confidence_level),
                include_tau2=bool(include_tau2),
                point_size=float(point_size),
                reference_line_visible=bool(reference_line_visible),
                contour_levels=(
                    tuple(float(level) for level in contour_levels)
                    if _funnel_kind(item) is FunnelKind.CONTOUR
                    else ()
                ),
                pooled_overlay_visible=bool(pooled_overlay_visible),
                style=funnel_style,
                point_symbol=int(style_preset["point_symbol"]),
                point_color=str(style_preset["point_color"]),
                reference_color=str(style_preset["reference_color"]),
                region_color=str(style_preset["region_color"]),
                background_color=str(style_preset["background_color"]),
            )
            for item in funnel_values
        )
        tests = tuple(AsymmetryTestSpec(_test_method(item)) for item in selected_tests)
        sensitivities = (
            SensitivitySpec(
                bool(trim_and_fill),
                TrimAndFillSide(trim_and_fill_side),
                TrimAndFillEstimator(trim_and_fill_estimator),
                TrimAndFillModel(trim_and_fill_model),
                bool(extrapolation),
            ),
        )
        return cls(
            data_type=data_type,  # type: ignore[arg-type]
            metric=_text(metric, "metric"),
            confidence_level=float(confidence_level),
            correction_policy=policy,
            plot_specs=funnels,
            test_specs=tests,
            sensitivity_specs=sensitivities,
            pooled_display=PooledDisplaySpec(),
        )

    def to_mapping(self) -> dict[str, object]:
        """Return the stable wire representation sent to RCMetaR."""
        result: dict[str, object] = {
            "data.type": self.data_type,
            "metric": self.metric,
            "conf.level": self.confidence_level,
            "tests": [spec.method.value for spec in self.test_specs],
            "funnels": [spec.kind.value for spec in self.plot_specs],
            "funnel.conf.levels": [spec.confidence_level for spec in self.plot_specs],
            "funnel.show.reference": [
                spec.reference_line_visible for spec in self.plot_specs
            ],
            "funnel.sampling.region.visible": [
                spec.show_sampling_region for spec in self.plot_specs
            ],
            "funnel.reverse.se.axis": [
                spec.reverse_standard_error_axis for spec in self.plot_specs
            ],
            "funnel.label.policy": [
                spec.label_policy.value for spec in self.plot_specs
            ],
            "funnel.sampling.conf.level": [
                spec.sampling_confidence_level for spec in self.plot_specs
            ],
            "funnel.include.tau2": [spec.include_tau2 for spec in self.plot_specs],
            "funnel.point.size": [spec.point_size for spec in self.plot_specs],
            "funnel.reference.visible": [
                spec.reference_line_visible for spec in self.plot_specs
            ],
            "funnel.contour.levels": [
                ",".join(format(level, "g") for level in spec.contour_levels)
                for spec in self.plot_specs
            ],
            "funnel.pooled.overlay.visible": [
                spec.pooled_overlay_visible for spec in self.plot_specs
            ],
            "funnel.style": [spec.style.value for spec in self.plot_specs],
            "funnel.point.symbol": [spec.point_symbol for spec in self.plot_specs],
            "funnel.point.color": [spec.point_color for spec in self.plot_specs],
            "funnel.reference.color": [
                spec.reference_color for spec in self.plot_specs
            ],
            "funnel.region.color": [spec.region_color for spec in self.plot_specs],
            "funnel.background.color": [
                spec.background_color for spec in self.plot_specs
            ],
            "trim.and.fill": any(spec.trim_and_fill for spec in self.sensitivity_specs),
            "trim.and.fill.side": next(
                (
                    spec.side.value
                    for spec in self.sensitivity_specs
                    if spec.trim_and_fill
                ),
                TrimAndFillSide.AUTO.value,
            ),
            "trim.and.fill.estimator": next(
                (
                    spec.estimator.value
                    for spec in self.sensitivity_specs
                    if spec.trim_and_fill
                ),
                TrimAndFillEstimator.L0.value,
            ),
            "trim.and.fill.model": next(
                (
                    spec.model.value
                    for spec in self.sensitivity_specs
                    if spec.trim_and_fill
                ),
                TrimAndFillModel.RANDOM.value,
            ),
            "extrapolation": any(spec.extrapolation for spec in self.sensitivity_specs),
            "pooled.display.model": self.pooled_display.model.value,
            "pooled.display.tau": self.pooled_display.method_tau,
        }
        if self.correction_policy is not None:
            result["correction.policy"] = self.correction_policy.value
        return result

    @property
    def semantic_id(self) -> str:
        """Stable identity for the statistical request, independent of titles."""
        return hashlib.sha256(
            json.dumps(
                self.to_mapping(), sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()


@dataclass(frozen=True)
class EligibilityMethod:
    """One method's RCMetaR-computed eligibility state."""

    method: str
    available: bool
    reason: str = ""
    usable_studies: int | None = None
    required_inputs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    role: str = ""

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> EligibilityMethod:
        required_fields = {
            "method",
            "available",
            "reason",
            "usable.studies",
            "required.inputs",
            "warnings",
            "role",
        }
        missing = sorted(required_fields - set(value))
        if missing:
            raise ValueError(
                "eligibility method is missing fields: " + ", ".join(missing)
            )
        method_value = value["method"]
        if not isinstance(method_value, str):
            raise ValueError("eligibility method must be text")
        method = _test_method(method_value).value
        reason = _text(value["reason"], "eligibility reason") if value["reason"] else ""
        count = value["usable.studies"]
        if (
            not isinstance(count, (int, float))
            or isinstance(count, bool)
            or int(count) != count
        ):
            raise ValueError("eligibility usable.studies must be an integer")
        usable = int(count)
        required = _text_values(value["required.inputs"], "eligibility required.inputs")
        warnings = _text_values(value["warnings"], "eligibility warnings")
        if not isinstance(value["available"], bool):
            raise ValueError("eligibility available must be boolean")
        if not isinstance(value["role"], str):
            raise ValueError("eligibility role must be text")
        return cls(
            method=method,
            available=value["available"],
            reason=reason,
            usable_studies=usable,
            required_inputs=tuple(str(item) for item in required if item is not None),
            warnings=tuple(str(item) for item in warnings if item is not None),
            role=value["role"],
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "method": self.method,
            "available": self.available,
            "reason": self.reason,
            "usable.studies": self.usable_studies,
            "required.inputs": list(self.required_inputs),
            "warnings": list(self.warnings),
            "role": self.role,
        }


@dataclass(frozen=True)
class EligibilityReport:
    """Typed view of the one RCMetaR eligibility report."""

    data_type: str
    metric: str
    usable_studies: int
    methods: tuple[EligibilityMethod, ...]
    warnings: tuple[str, ...] = ()
    raw_data_available: bool = False
    standard_error_range: tuple[float, float] | None = None
    package_versions: tuple[tuple[str, str], ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> EligibilityReport:
        required_fields = {
            "data.type",
            "metric",
            "usable.studies",
            "raw.data.available",
            "standard.error.range",
            "methods",
            "warnings",
            "package.versions",
        }
        missing = sorted(required_fields - set(value))
        if missing:
            raise ValueError(
                "eligibility report is missing fields: " + ", ".join(missing)
            )
        method_values = value["methods"]
        # rpy2 scalarizes a length-one list of named records to its record
        # mapping.  Normalize that wire representation before validating the
        # otherwise stable sequence contract.
        if isinstance(method_values, Mapping):
            method_values = (method_values,)
        if isinstance(method_values, (str, bytes)) or not isinstance(
            method_values, Sequence
        ):
            raise ValueError("eligibility methods must be a sequence")
        methods = tuple(
            EligibilityMethod.from_mapping(
                _string_key_mapping(item, "eligibility method")
            )
            for item in method_values
            if isinstance(item, Mapping)
        )
        if len(methods) != len(method_values):
            raise ValueError("eligibility methods must contain mappings")
        standard_error = value["standard.error.range"]
        standard_error_range = None
        if not isinstance(standard_error, (list, tuple)) or len(standard_error) not in (
            0,
            2,
        ):
            raise ValueError(
                "eligibility standard.error.range must have zero or two values"
            )
        if len(standard_error) == 2:
            standard_error_range = (
                _float(standard_error[0], "eligibility standard.error.range"),
                _float(standard_error[1], "eligibility standard.error.range"),
            )
        versions = value["package.versions"]
        if not isinstance(versions, Mapping):
            raise ValueError("eligibility package.versions must be a mapping")
        package_versions = _frozen_mapping(
            _string_key_mapping(versions, "eligibility package.versions")
        )
        if not isinstance(value["data.type"], str) or not isinstance(
            value["metric"], str
        ):
            raise ValueError("eligibility data.type and metric must be text")
        count = value["usable.studies"]
        if (
            not isinstance(count, (int, float))
            or isinstance(count, bool)
            or int(count) != count
        ):
            raise ValueError("eligibility usable.studies must be an integer")
        if not isinstance(value["raw.data.available"], bool):
            raise ValueError("eligibility raw.data.available must be boolean")
        warnings = _text_values(value["warnings"], "eligibility warnings")
        return cls(
            data_type=value["data.type"],
            metric=value["metric"],
            usable_studies=int(count),
            methods=methods,
            warnings=tuple(str(item) for item in warnings if item is not None),
            raw_data_available=value["raw.data.available"],
            standard_error_range=standard_error_range,
            package_versions=tuple((key, str(item)) for key, item in package_versions),
        )

    @property
    def primary_method(self) -> EligibilityMethod | None:
        return next(
            (method for method in self.methods if method.role == "primary"), None
        )

    def method(self, method_name: str) -> EligibilityMethod | None:
        return next((item for item in self.methods if item.method == method_name), None)


def parse_eligibility_report(value: object) -> EligibilityReport:
    if not isinstance(value, Mapping):
        raise TypeError("small-study effects eligibility report must be a mapping")
    return EligibilityReport.from_mapping(
        _string_key_mapping(value, "eligibility report")
    )


def execute_small_study_effects(
    model: object, request: SmallStudyEffectsRequest
) -> AnalysisResult:
    """Convert and execute one immutable request through the serialized R call."""
    from rc_metastudio import r_bridge

    result = r_bridge.run_small_study_effects(model, request.to_mapping())
    return parse_analysis_result(result)


def regenerate_small_study_effects_funnel(
    params_path: str, output_path: str | None = None
) -> str | None:
    """Regenerate only a persisted funnel presentation/geometry artifact."""
    from rc_metastudio import r_bridge

    return r_bridge.regenerate_small_study_effects_funnel(params_path, output_path)


def unavailable_reason(method: EligibilityMethod | Mapping[str, object]) -> str:
    """Return the exact RCMetaR reason shown by the dialog."""
    item = (
        method
        if isinstance(method, EligibilityMethod)
        else EligibilityMethod.from_mapping(method)
    )
    if item.available:
        return ""
    if item.reason:
        return item.reason
    if item.usable_studies is not None and item.usable_studies < 3:
        return "Unavailable: fewer than 3 usable included studies."
    return "Unavailable for the eligible study set."


__all__ = [
    "FUNNEL_STYLE_LABELS",
    "FUNNEL_STYLE_PRESETS",
    "AsymmetryTestSpec",
    "CorrectionPolicy",
    "EligibilityMethod",
    "EligibilityReport",
    "FunnelKind",
    "FunnelPlotSpec",
    "FunnelStyle",
    "LabelPolicy",
    "PooledDisplayModel",
    "PooledDisplaySpec",
    "SensitivitySpec",
    "SmallStudyEffectsRequest",
    "TestMethod",
    "TrimAndFillEstimator",
    "TrimAndFillModel",
    "TrimAndFillSide",
    "execute_small_study_effects",
    "parse_eligibility_report",
    "regenerate_small_study_effects_funnel",
    "unavailable_reason",
]
