# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Domain operations shared by the dataset table adapter."""

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, TypeAlias

from rc_metastudio.analysis_dataset import Dataset, Study
from rc_metastudio.analysis_unit import AnalysisUnit
from rc_metastudio.meta_globals import (
    BINARY,
    BINARY_TWO_ARM_METRICS,
    CONTINUOUS,
    CONTINUOUS_TWO_ARM_METRICS,
    DIAGNOSTIC,
    DIAGNOSTIC_METRICS,
    EMPTY_VALS,
)

Scalar: TypeAlias = float | int | str | None


class ScaleBridge(Protocol):
    def binary_convert_scale(self, value: object, effect: object, *, convert_to: str, n1: object = None) -> object: ...
    def continuous_convert_scale(self, value: object, effect: object, *, convert_to: str) -> object: ...
    def diagnostic_convert_scale(self, value: object, effect: object, *, convert_to: str) -> object: ...
    def effect_for_study(self, *args: object, **kwargs: object) -> object: ...
    def continuous_effect_for_study(self, *args: object, **kwargs: object) -> object: ...
    def effect_triplet(self, value: object, scale: str, *, metric: object) -> tuple[Scalar, Scalar, Scalar]: ...
    def diagnostic_effects_for_study(self, *args: object, **kwargs: object) -> Mapping[str, object]: ...


def ensure_analysis_unit(
    dataset: Dataset,
    study: Study,
    outcome: str,
    follow_up: str,
    groups: Sequence[str],
) -> AnalysisUnit:
    """Return the selected unit, creating missing structure for new studies."""
    if outcome not in study.analysis_units_by_outcome:
        study.add_outcome(
            dataset.get_outcome_obj(outcome), group_names=dataset.get_group_names()
        )
    if follow_up not in study.analysis_units_by_outcome[outcome]:
        study.add_outcome_at_follow_up(dataset.get_outcome_obj(outcome), follow_up)

    analysis_unit = study.analysis_units_by_outcome[outcome][follow_up]
    for group in groups:
        if group not in analysis_unit.get_group_names():
            analysis_unit.add_group(group)
    return analysis_unit


def make_display_scale_converter(
    bridge: ScaleBridge, data_type: str | None, effect: str | None, n1: object = None
) -> Callable[[object], object]:
    """Build the calculation-to-display conversion for one outcome family."""
    if data_type == BINARY:
        return lambda value: bridge.binary_convert_scale(
            value, effect, convert_to="display.scale", n1=n1
        )
    if data_type == CONTINUOUS:
        return lambda value: bridge.continuous_convert_scale(
            value, effect, convert_to="display.scale"
        )
    if data_type == DIAGNOSTIC:
        return lambda value: bridge.diagnostic_convert_scale(
            value, effect, convert_to="display.scale"
        )
    raise ValueError(f"Unsupported outcome type: {data_type!r}")


def to_calculation_scale(
    bridge: ScaleBridge,
    value: object,
    data_type: str | None,
    effect: str | None,
    n1: object = None,
) -> object:
    """Convert a user-facing value to the backend's calculation scale."""
    if data_type == BINARY:
        return bridge.binary_convert_scale(
            value, effect, convert_to="calc.scale", n1=n1
        )
    if data_type == CONTINUOUS:
        return bridge.continuous_convert_scale(value, effect, convert_to="calc.scale")
    if data_type == DIAGNOSTIC:
        return bridge.diagnostic_convert_scale(value, effect, convert_to="calc.scale")
    raise ValueError(f"Unsupported outcome type: {data_type!r}")


def calculate_raw_effects(
    bridge: ScaleBridge,
    data_type: str | None,
    effect: str | None,
    raw_data: Sequence[object],
    confidence_level: float,
) -> tuple[tuple[Scalar, Scalar, Scalar], object] | dict[str, tuple[Scalar, Scalar, Scalar]]:
    """Calculate backend effects from one study's raw data."""
    if data_type == BINARY:
        e1, n1, e2, n2 = raw_data
        if effect in BINARY_TWO_ARM_METRICS:
            result = bridge.effect_for_study(
                e1, n1, e2, n2, metric=effect, confidence_level=confidence_level
            )
        else:
            result = bridge.effect_for_study(
                e1, n1, two_arm=False, metric=effect, confidence_level=confidence_level
            )
        triplet = (
            (None, None, None)
            if result is None
            else bridge.effect_triplet(result, "calc_scale", metric=effect)
        )
        return triplet, n1
    if data_type == CONTINUOUS:
        n1, m1, sd1, n2, m2, sd2 = raw_data
        if effect in CONTINUOUS_TWO_ARM_METRICS:
            result = bridge.continuous_effect_for_study(
                n1,
                m1,
                sd1,
                n2=n2,
                m2=m2,
                sd2=sd2,
                metric=effect,
                confidence_level=confidence_level,
            )
        else:
            result = bridge.continuous_effect_for_study(
                n1,
                m1,
                sd1,
                two_arm=False,
                metric=effect,
                confidence_level=confidence_level,
            )
        triplet = (
            (None, None, None)
            if result is None
            else bridge.effect_triplet(result, "calc_scale", metric=effect)
        )
        return triplet, n1
    if data_type == DIAGNOSTIC:
        tp, fn, fp, tn = raw_data
        results = bridge.diagnostic_effects_for_study(
            tp,
            fn,
            fp,
            tn,
            metrics=DIAGNOSTIC_METRICS,
            confidence_level=confidence_level,
        )
        return {
            metric: bridge.effect_triplet(results[metric], "calc_scale", metric=metric)
            for metric in DIAGNOSTIC_METRICS
        }
    raise ValueError(f"Unsupported outcome type: {data_type!r}")


def raw_data_is_complete(raw_data: Sequence[object]) -> bool:
    return all(value not in ("", None) for value in raw_data)


def raw_data_is_empty(raw_data: Sequence[object]) -> bool:
    return all(value in EMPTY_VALS for value in raw_data)


def has_entered_data(analysis_unit: AnalysisUnit) -> bool:
    return any(
        value not in EMPTY_VALS
        for group in analysis_unit.groups.values()
        for value in group.raw_data
    ) or any(
        value not in EMPTY_VALS
        for effect_groups in analysis_unit.effects.values()
        for effect_data in effect_groups.values()
        for value in effect_data.values()
    )


def has_study_entered_data(study: Study) -> bool:
    if study.name.strip():
        return True
    if study.year not in EMPTY_VALS and study.year != 0:
        return True
    if any(value not in EMPTY_VALS for value in study.covariate_values.values()):
        return True
    return any(
        has_entered_data(analysis_unit)
        for follow_ups in study.analysis_units_by_outcome.values()
        for analysis_unit in follow_ups.values()
    )


def included_studies_have_raw_data(
    studies: Sequence[Study],
    raw_data_for_study: Callable[[int, bool], Sequence[object]],
    one_arm: bool,
) -> bool:
    for index, study in enumerate(studies[:-1]):
        if study.include and not raw_data_is_complete(
            raw_data_for_study(index, one_arm)
        ):
            return False
    return True


def included_studies_have_effects(
    studies: Sequence[Study],
    effect_for_study: Callable[[int], Sequence[object]],
) -> bool:
    return all(
        all(value is not None for value in effect_for_study(index))
        for index, study in enumerate(studies[:-1])
        if study.include
    )
