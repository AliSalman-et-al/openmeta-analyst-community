# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Domain operations shared by the dataset table adapter."""

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, TypeAlias, runtime_checkable

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


@runtime_checkable
class ScaleBridge(Protocol):
    def get_confidence_multiplier_from_r(self, confidence_level: object) -> float: ...
    def set_confidence_level(self, confidence_level: object) -> None: ...
    def binary_convert_scale(self, value: object, effect: object, *, convert_to: str, n1: object = None) -> object: ...
    def continuous_convert_scale(self, value: object, effect: object, *, convert_to: str) -> object: ...
    def diagnostic_convert_scale(self, value: object, effect: object, *, convert_to: str) -> object: ...
    def effect_for_study(self, *args: object, **kwargs: object) -> object: ...
    def continuous_effect_for_study(self, *args: object, **kwargs: object) -> object: ...
    def effect_triplet(self, value: object, scale: str, *, metric: object) -> tuple[Scalar, Scalar, Scalar]: ...
    def diagnostic_effects_for_study(self, *args: object, **kwargs: object) -> Mapping[str, object]: ...


def _checked_bridge(value: object) -> ScaleBridge:
    if not isinstance(value, ScaleBridge):
        raise TypeError("analysis boundary requires a scale bridge")
    return value


def ensure_analysis_unit(
    dataset: Dataset,
    study: Study,
    outcome: str,
    follow_up: str,
    groups: Sequence[str],
) -> AnalysisUnit:
    """Return the selected unit, creating missing structure for new studies."""
    try:
        analysis_unit = study.get_analysis_unit(outcome, follow_up)
    except KeyError:
        study.add_outcome(
            dataset.get_outcome_obj(outcome),
            group_names=dataset.get_group_names(),
            follow_up_id=dataset.get_follow_up_stable_id(outcome, follow_up),
        )
        try:
            analysis_unit = study.get_analysis_unit(outcome, follow_up)
        except KeyError:
            study.add_outcome_at_follow_up(
                dataset.get_outcome_obj(outcome),
                follow_up,
                follow_up_id=dataset.get_follow_up_stable_id(outcome, follow_up),
            )
            analysis_unit = study.get_analysis_unit(outcome, follow_up)
    for group in groups:
        if group not in analysis_unit.get_group_names():
            analysis_unit.add_group(group)
    return analysis_unit


def make_display_scale_converter(
    bridge: object, data_type: object, effect: str | None, n1: object = None
) -> Callable[[object], object]:
    """Build the calculation-to-display conversion for one outcome family."""
    checked = _checked_bridge(bridge)
    if data_type == BINARY:
        return lambda value: checked.binary_convert_scale(
            value, effect, convert_to="display.scale", n1=n1
        )
    if data_type == CONTINUOUS:
        return lambda value: checked.continuous_convert_scale(
            value, effect, convert_to="display.scale"
        )
    if data_type == DIAGNOSTIC:
        return lambda value: checked.diagnostic_convert_scale(
            value, effect, convert_to="display.scale"
        )
    raise ValueError(f"Unsupported outcome type: {data_type!r}")


def to_calculation_scale(
    bridge: object,
    value: object,
    data_type: object,
    effect: str | None,
    n1: object = None,
) -> object:
    """Convert a user-facing value to the backend's calculation scale."""
    checked = _checked_bridge(bridge)
    if data_type == BINARY:
        return checked.binary_convert_scale(
            value, effect, convert_to="calc.scale", n1=n1
        )
    if data_type == CONTINUOUS:
        return checked.continuous_convert_scale(value, effect, convert_to="calc.scale")
    if data_type == DIAGNOSTIC:
        return checked.diagnostic_convert_scale(value, effect, convert_to="calc.scale")
    raise ValueError(f"Unsupported outcome type: {data_type!r}")


def calculate_raw_effects(
    bridge: object,
    data_type: object,
    effect: str | None,
    raw_data: Sequence[object],
    confidence_level: float,
) -> tuple[tuple[Scalar, Scalar, Scalar], object] | dict[str, tuple[Scalar, Scalar, Scalar]]:
    """Calculate backend effects from one study's raw data."""
    checked = _checked_bridge(bridge)
    if data_type == BINARY:
        return _binary_raw_effect(checked, effect, raw_data, confidence_level)
    if data_type == CONTINUOUS:
        return _continuous_raw_effect(checked, effect, raw_data, confidence_level)
    if data_type == DIAGNOSTIC:
        return _diagnostic_raw_effect(checked, raw_data, confidence_level)
    raise ValueError(f"Unsupported outcome type: {data_type!r}")


def _effect_triplet(checked: ScaleBridge, result: object, effect: str | None) -> tuple[Scalar, Scalar, Scalar]:
    if result is None:
        return (None, None, None)
    return checked.effect_triplet(result, "calc_scale", metric=effect)


def _binary_raw_effect(
    checked: ScaleBridge,
    effect: str | None,
    raw_data: Sequence[object],
    confidence_level: float,
) -> tuple[tuple[Scalar, Scalar, Scalar], object]:
    e1, n1, e2, n2 = raw_data
    if effect in BINARY_TWO_ARM_METRICS:
        result = checked.effect_for_study(e1, n1, e2, n2, metric=effect, confidence_level=confidence_level)
    else:
        result = checked.effect_for_study(e1, n1, two_arm=False, metric=effect, confidence_level=confidence_level)
    return _effect_triplet(checked, result, effect), n1


def _continuous_raw_effect(
    checked: ScaleBridge,
    effect: str | None,
    raw_data: Sequence[object],
    confidence_level: float,
) -> tuple[tuple[Scalar, Scalar, Scalar], object]:
    n1, m1, sd1, n2, m2, sd2 = raw_data
    if effect in CONTINUOUS_TWO_ARM_METRICS:
        result = checked.continuous_effect_for_study(
            n1, m1, sd1, n2=n2, m2=m2, sd2=sd2, metric=effect, confidence_level=confidence_level
        )
    else:
        result = checked.continuous_effect_for_study(
            n1, m1, sd1, two_arm=False, metric=effect, confidence_level=confidence_level
        )
    return _effect_triplet(checked, result, effect), n1


def _diagnostic_raw_effect(
    checked: ScaleBridge,
    raw_data: Sequence[object],
    confidence_level: float,
) -> dict[str, tuple[Scalar, Scalar, Scalar]]:
    tp, fn, fp, tn = raw_data
    results = checked.diagnostic_effects_for_study(
        tp, fn, fp, tn, metrics=DIAGNOSTIC_METRICS, confidence_level=confidence_level
    )
    return {
        metric: checked.effect_triplet(results[metric], "calc_scale", metric=metric)
        for metric in DIAGNOSTIC_METRICS
    }


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
        for effect_groups in analysis_unit.entered_effects.values()
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
