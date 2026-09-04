"""Narrow calculation boundary used by outcome editors."""

from __future__ import annotations

from rc_metastudio import r_bridge


class CalculatorService:
    """Concrete calculation operations shared by transactional editors."""

    def get_confidence_multiplier(self, confidence_level: float) -> float:
        return r_bridge.get_confidence_multiplier_from_r(confidence_level)

    def binary_convert_scale(self, x: object, metric_name: str, convert_to: str = "display.scale", n1: object = None) -> object:
        return r_bridge.binary_convert_scale(x, metric_name, convert_to=convert_to, n1=n1)

    def continuous_convert_scale(self, x: object, metric_name: str, convert_to: str = "display.scale") -> object:
        return r_bridge.continuous_convert_scale(x, metric_name, convert_to=convert_to)

    def diagnostic_convert_scale(self, x: object, metric_name: str, convert_to: str = "display.scale") -> object:
        return r_bridge.diagnostic_convert_scale(x, metric_name, convert_to=convert_to)

    def effect_for_study(self, e1: object, n1: object, e2: object = None, n2: object = None, *, two_arm: bool = True, metric: str = "OR", confidence_level: float = 95) -> object:
        return r_bridge.effect_for_study(e1, n1, e2, n2, two_arm=two_arm, metric=metric, confidence_level=confidence_level)

    def continuous_effect_for_study(self, n1: object, m1: object, sd1: object, se1: object = None, n2: object = None, m2: object = None, sd2: object = None, se2: object = None, *, metric: str = "MD", two_arm: bool = True, confidence_level: float = 95.0) -> object:
        return r_bridge.continuous_effect_for_study(n1, m1, sd1, se1, n2, m2, sd2, se2, metric=metric, two_arm=two_arm, confidence_level=confidence_level)

    def diagnostic_effects_for_study(self, tp: object, fn: object, fp: object, tn: object, *, metrics: tuple[str, ...] = ("Spec", "Sens"), confidence_level: float = 95.0) -> object:
        return r_bridge.diagnostic_effects_for_study(tp, fn, fp, tn, metrics=metrics, confidence_level=confidence_level)

    def effect_triplet(self, effect_entry: object, scale_name: str = "calc_scale", metric: str | None = None) -> tuple[object, object, object]:
        return r_bridge.effect_triplet(effect_entry, scale_name, metric=metric)

    def impute_binary_data(self, binary_data: dict[str, object]) -> object:
        return r_bridge.impute_binary_data(binary_data)

    def impute_continuous_data(self, continuous_data: dict[str, object], alpha: float) -> object:
        return r_bridge.impute_continuous_data(continuous_data, alpha)

    def impute_pre_post_continuous_data(self, continuous_data: dict[str, object], correlation: object, alpha: float) -> object:
        return r_bridge.impute_pre_post_continuous_data(continuous_data, correlation, alpha)

    def back_calculate_continuous_data(self, group1_data: dict[str, object], group2_data: dict[str, object], effect_data: dict[str, object], confidence_level: float) -> object:
        return r_bridge.back_calculate_continuous_data(group1_data, group2_data, effect_data, confidence_level)

    def impute_diagnostic_data(self, diagnostic_data: dict[str, object]) -> object:
        return r_bridge.impute_diagnostic_data(diagnostic_data)
