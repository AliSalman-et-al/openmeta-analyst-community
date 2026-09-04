"""Narrow calculation boundary used by outcome editors."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from typing import NotRequired, TypeAlias, TypedDict, cast

from rc_metastudio import r_bridge

Scalar: TypeAlias = float | int | str | None
Numeric: TypeAlias = float | int
ScaleValue: TypeAlias = Numeric | tuple[Numeric | None, ...] | list[Numeric | None] | None
EffectData: TypeAlias = Mapping[str, ScaleValue]
MutableData: TypeAlias = Mapping[str, Scalar | bool]
DiagnosticData: TypeAlias = Mapping[str, EffectData]
BinaryImputationOption: TypeAlias = Mapping[str, Numeric | None]
BinaryImputationResult: TypeAlias = Mapping[
    str, BinaryImputationOption | Scalar | bool
]
ContinuousValues: TypeAlias = Mapping[str, Numeric | None]


class ContinuousImputationResult(TypedDict):
    succeeded: bool
    output: NotRequired[ContinuousValues]


class PrePostImputationResult(TypedDict):
    succeeded: bool
    output: NotRequired[ContinuousValues]
    pre: NotRequired[ContinuousValues]
    post: NotRequired[ContinuousValues]


BackCalculationValue: TypeAlias = Numeric | Sequence[Numeric | None] | None
BackCalculationResult: TypeAlias = MutableMapping[str, BackCalculationValue]
DiagnosticImputationResult: TypeAlias = Mapping[str, Numeric | None]


class CalculatorService:
    """Concrete calculation operations shared by transactional editors."""

    def get_confidence_multiplier(self, confidence_level: float) -> float:
        return r_bridge.get_confidence_multiplier_from_r(confidence_level)

    def binary_convert_scale(self, x: ScaleValue, metric_name: str, convert_to: str = "display.scale", n1: Numeric | None = None) -> ScaleValue:
        return r_bridge.binary_convert_scale(x, metric_name, convert_to=convert_to, n1=n1)

    def continuous_convert_scale(self, x: ScaleValue, metric_name: str, convert_to: str = "display.scale") -> ScaleValue:
        return r_bridge.continuous_convert_scale(x, metric_name, convert_to=convert_to)

    def diagnostic_convert_scale(self, x: ScaleValue, metric_name: str, convert_to: str = "display.scale") -> ScaleValue:
        return r_bridge.diagnostic_convert_scale(x, metric_name, convert_to=convert_to)

    def effect_for_study(self, e1: Numeric, n1: Numeric, e2: Numeric | None = None, n2: Numeric | None = None, *, two_arm: bool = True, metric: str = "OR", confidence_level: float = 95) -> EffectData:
        return r_bridge.effect_for_study(e1, n1, e2, n2, two_arm=two_arm, metric=metric, confidence_level=confidence_level)

    def continuous_effect_for_study(self, n1: Numeric, m1: Numeric, sd1: Numeric, se1: Numeric | None = None, n2: Numeric | None = None, m2: Numeric | None = None, sd2: Numeric | None = None, se2: Numeric | None = None, *, metric: str = "MD", two_arm: bool = True, confidence_level: float = 95.0) -> EffectData:
        return r_bridge.continuous_effect_for_study(n1, m1, sd1, se1, n2, m2, sd2, se2, metric=metric, two_arm=two_arm, confidence_level=confidence_level)

    def diagnostic_effects_for_study(self, tp: Numeric, fn: Numeric, fp: Numeric, tn: Numeric, *, metrics: Sequence[str] = ("Spec", "Sens"), confidence_level: float = 95.0) -> DiagnosticData:
        return r_bridge.diagnostic_effects_for_study(tp, fn, fp, tn, metrics=metrics, confidence_level=confidence_level)

    def effect_triplet(self, effect_entry: EffectData, scale_name: str = "calc_scale", metric: str | None = None) -> tuple[Numeric | None, Numeric | None, Numeric | None]:
        return r_bridge.effect_triplet(effect_entry, scale_name, metric=metric)

    def impute_binary_data(self, binary_data: MutableData) -> BinaryImputationResult:
        return cast(BinaryImputationResult, r_bridge.impute_binary_data(binary_data))

    def impute_continuous_data(self, continuous_data: MutableData, alpha: float) -> ContinuousImputationResult:
        return cast(ContinuousImputationResult, r_bridge.impute_continuous_data(continuous_data, alpha))

    def impute_pre_post_continuous_data(self, continuous_data: MutableData, correlation: Numeric, alpha: float) -> PrePostImputationResult:
        return cast(PrePostImputationResult, r_bridge.impute_pre_post_continuous_data(continuous_data, correlation, alpha))

    def back_calculate_continuous_data(self, group1_data: MutableData, group2_data: MutableData, effect_data: MutableData, confidence_level: float) -> BackCalculationResult:
        return cast(BackCalculationResult, r_bridge.back_calculate_continuous_data(group1_data, group2_data, effect_data, confidence_level))

    def impute_diagnostic_data(self, diagnostic_data: MutableData) -> DiagnosticImputationResult:
        return cast(DiagnosticImputationResult, r_bridge.impute_diagnostic_data(diagnostic_data))
