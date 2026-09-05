# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qt-free editing operations for the dataset workspace.

The table model owns Qt roles, indexes, and presentation.  This module owns
the backend boundary used while an edit is being validated or previewed.
Keeping that boundary here also gives non-Qt callers a small, testable way to
calculate the same raw-data preview as the table.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass, field
from statistics import NormalDist
from typing import Callable, Protocol

from rc_metastudio import calculator_routines, qt_text
from rc_metastudio import r_backend, r_bridge
from rc_metastudio.analysis_dataset import Dataset, Study
from rc_metastudio.analysis_unit import AnalysisUnit, EffectEstimate
from rc_metastudio.dataset_analysis_domain import (
    BINARY,
    CONTINUOUS,
    DIAGNOSTIC,
    ScaleBridge,
    calculate_raw_effects,
    raw_data_is_complete,
    raw_data_is_empty,
    make_display_scale_converter,
    to_calculation_scale,
)
from rc_metastudio.meta_globals import (
    BINARY_ONE_ARM_METRICS,
    CONTINUOUS_ONE_ARM_METRICS,
    DIAGNOSTIC_METRICS,
    FACTOR,
    is_a_float,
    is_an_int,
    is_empty,
    validate_confidence_level,
)


@dataclass(frozen=True, slots=True)
class ConfidenceSettings:
    """Validated confidence level and multiplier used by one edit session."""

    level: float
    multiplier: float


class _InclusionTarget(Protocol):
    include: bool
    manually_excluded: bool


def _effect_value(effect: Mapping[str, object] | EffectEstimate, field: str):
    if isinstance(effect, EffectEstimate):
        return {
            "est": effect.estimate,
            "lower": effect.lower,
            "upper": effect.upper,
            "SE": effect.standard_error,
        }[field]
    return effect[field]


@dataclass(frozen=True, slots=True)
class WorkspaceEditingContext:
    """Domain values needed to edit one visible workspace."""

    outcome_name: str | None
    follow_up_name: str | None
    current_groups: tuple[str, ...]
    current_effect: str | None
    data_type: object
    outcome_subtype: str | None
    group_comparison: str
    raw_columns: tuple[int, ...]
    outcome_columns: tuple[int, ...]
    include_column: int
    name_column: int
    year_column: int
    confidence_level: float
    confidence_multiplier: float
    covariate_name: str | None = None
    covariate_type: object | None = None
    covariate: object | None = None


@dataclass(slots=True)
class WorkspaceViewState:
    """Serializable selection and confidence state for the workspace."""

    current_outcome_name: str | None = None
    current_follow_up_index: int = 0
    current_groups: list[str] = field(default_factory=list)
    previous_groups: list[str] = field(default_factory=list)
    current_effect: str | None = None
    confidence_level: float = 95.0
    confidence_multiplier: float = 1.96


@dataclass(frozen=True, slots=True)
class WorkspaceEditTarget:
    row: int
    column: int
    old_value: object


@dataclass(frozen=True, slots=True)
class AppliedWorkspaceEdit:
    added_study_id: int | None = None
    error: str | None = None

    @property
    def applied(self) -> bool:
        return self.error is None


class WorkspaceEditingService:
    """Perform backend-facing edit work without importing Qt.

    ``bridge`` is injectable for deterministic tests and for applications that
    provide another analysis backend.  The default remains the production
    RCMetaR bridge, preserving the existing statistical contract.
    """

    def __init__(self, bridge: ScaleBridge | None = None) -> None:
        self.bridge = r_bridge if bridge is None else bridge

    @staticmethod
    def update_inclusion_after_edit(
        study: _InclusionTarget,
        *,
        diagnostic: bool,
        inclusion_column: bool,
        outcome_selected: bool,
        effect: Mapping[str, object] | EffectEstimate,
        data_type: object,
        outcome_subtype: str | None,
    ) -> None:
        """Apply the durable inclusion rule after a successful cell edit."""
        if diagnostic:
            return
        if inclusion_column:
            return
        if not outcome_selected:
            return
        if not study.manually_excluded:
            study.include = True
        if not WorkspaceEditingService._effect_is_complete(
            effect, data_type, outcome_subtype
        ):
            study.include = False

    @staticmethod
    def _effect_is_complete(effect, data_type, outcome_subtype) -> bool:
        if data_type == "continuous" and outcome_subtype == "generic_effect":
            return all(_effect_value(effect, key) is not None for key in ("est", "SE"))
        return all(
            _effect_value(effect, key) is not None
            for key in ("upper", "lower", "est")
        )

    def confidence_settings(self, level: object) -> ConfidenceSettings:
        validated = validate_confidence_level(level)
        if r_backend.is_backend_installed():
            multiplier = self.bridge.get_confidence_multiplier_from_r(validated)
        else:
            tail = (1.0 + validated / 100.0) / 2.0
            multiplier = NormalDist().inv_cdf(tail)
        return ConfidenceSettings(float(validated), float(multiplier))

    def set_backend_confidence_level(self, level: float) -> None:
        if r_backend.is_backend_installed():
            self.bridge.set_confidence_level(level)

    def preview_raw_effects(
        self,
        data_type: object,
        effect: str | None,
        raw_data: tuple[object, ...] | list[object],
        confidence_level: float,
    ):
        """Calculate raw effects for a candidate edit."""
        return calculate_raw_effects(
            self.bridge, data_type, effect, raw_data, confidence_level
        )

    def to_calculation_scale(
        self,
        value: object,
        data_type: object,
        effect: str | None,
        n1: object = None,
    ):
        return to_calculation_scale(self.bridge, value, data_type, effect, n1)

    def display_scale_converter(
        self,
        data_type: object,
        effect: str | None,
        n1: object = None,
    ):
        return make_display_scale_converter(self.bridge, data_type, effect, n1)

    def apply_edit(
        self,
        dataset: Dataset,
        target: WorkspaceEditTarget,
        context: WorkspaceEditingContext,
        value: object,
        *,
        allow_empty_names: bool = False,
        import_csv: bool = False,
        append_blank_study: bool = False,
        recalculate: Callable[[int], None] | None = None,
    ) -> AppliedWorkspaceEdit:
        """Validate and apply one edit to the durable dataset graph."""
        if target.row < 0 or target.column < 0:
            return AppliedWorkspaceEdit(error="Cannot edit that cell.")

        study = self._study_for_edit(dataset, target, context, value, allow_empty_names)
        if study is None:
            return AppliedWorkspaceEdit(error=self._last_error)

        if target.column == context.name_column:
            return self._edit_study_name(
                dataset, study, target, context, value, allow_empty_names, append_blank_study
            )
        if target.column == context.year_column:
            return self._edit_year(study, value)
        result = self._apply_analysis_edit(
            dataset, study, target, context, value, import_csv, recalculate
        )
        self._update_inclusion(
            dataset, study, target, context, result, import_csv=import_csv
        )
        return result

    def _apply_analysis_edit(
        self, dataset, study, target, context, value, import_csv, recalculate
    ) -> AppliedWorkspaceEdit:
        if context.outcome_name is not None and target.column in context.raw_columns:
            return self._edit_raw_data(dataset, study, target, context, value, recalculate)
        if target.column in context.outcome_columns:
            return self._edit_outcome(dataset, study, target, context, value, import_csv)
        if target.column == context.include_column:
            return self._edit_inclusion(study, value)
        return self._edit_covariate(study, context, value)

    @staticmethod
    def _edit_inclusion(study: Study, value: object) -> AppliedWorkspaceEdit:
        included, valid = WorkspaceEditingService._parse_inclusion(value)
        if not valid:
            return AppliedWorkspaceEdit(
                error="Study inclusion must be checked or unchecked."
            )
        study.include = included
        study.manually_excluded = not included
        return AppliedWorkspaceEdit()

    def _update_inclusion(
        self,
        dataset,
        study,
        target,
        context,
        result: AppliedWorkspaceEdit,
        *,
        import_csv: bool = False,
    ) -> None:
        if (
            not result.applied
            or context.outcome_name is None
            or context.data_type == DIAGNOSTIC
            or target.column == context.include_column
            or import_csv
        ):
            return
        unit = self._analysis_unit(dataset, study, context)
        effect = unit.get_effect_for_source(
            "entered", context.current_effect or "", context.group_comparison
        )
        self.update_inclusion_after_edit(
            study,
            diagnostic=context.data_type == DIAGNOSTIC,
            inclusion_column=False,
            outcome_selected=True,
            effect=effect,
            data_type=context.data_type,
            outcome_subtype=context.outcome_subtype,
        )

    _last_error: str | None = None

    @staticmethod
    def _parse_inclusion(value: object) -> tuple[bool, bool]:
        if type(value) is bool:
            return value, True
        if type(value) is int and value in (0, 2):
            return value == 2, True
        return False, False

    def _study_for_edit(
        self,
        dataset: Dataset,
        target: WorkspaceEditTarget,
        context: WorkspaceEditingContext,
        value: object,
        allow_empty_names: bool,
    ) -> Study | None:
        self._last_error = None
        if target.row >= len(dataset):
            return self._new_study_for_edit(
                dataset, target, context, value, allow_empty_names
            )
        study = dataset.studies[target.row]
        if self._edit_requires_name(study, target, context, value, allow_empty_names):
            self._last_error = "Please enter a study name before entering study data."
            return None
        return study

    def _new_study_for_edit(
        self, dataset, target, context, value, allow_empty_names
    ) -> Study | None:
        if target.column != context.name_column:
            self._last_error = "Please enter a study name before entering study data."
            return None
        if qt_text.to_native_text(value) == "" and not allow_empty_names:
            self._last_error = "Please enter a study name before entering study data."
            return None
        while len(dataset) <= target.row:
            dataset.add_study(Study(dataset.max_study_id() + 1))
        return dataset.studies[target.row]

    @staticmethod
    def _edit_requires_name(study, target, context, value, allow_empty_names):
        return (
            not allow_empty_names
            and not study.name.strip()
            and WorkspaceEditingService._requires_named_study(target, context, value)
        )

    @staticmethod
    def _requires_named_study(
        target: WorkspaceEditTarget, context: WorkspaceEditingContext, value: object
    ) -> bool:
        if target.column in (context.name_column, context.year_column):
            return False
        if context.outcome_name is not None and target.column in context.raw_columns:
            return not qt_text.is_blank(value)
        if target.column in context.outcome_columns:
            return not qt_text.is_blank(value)
        return not qt_text.is_blank(value)

    def _edit_study_name(
        self,
        dataset: Dataset,
        study: Study,
        target: WorkspaceEditTarget,
        context: WorkspaceEditingContext,
        value: object,
        allow_empty_names: bool,
        append_blank_study: bool,
    ) -> AppliedWorkspaceEdit:
        name = qt_text.to_native_text(value)
        if name == "" and not allow_empty_names:
            return AppliedWorkspaceEdit(
                error="Please enter a study name before entering study data."
            )
        if name in dataset.get_study_names() and name != study.name:
            return AppliedWorkspaceEdit(error="Duplicate study names not allowed")
        added_study_id = None
        if append_blank_study and name != "":
            new_study = Study(dataset.max_study_id() + 1)
            new_study.include = False
            dataset.add_study(new_study)
            added_study_id = int(new_study.id)
        study.name = name
        return AppliedWorkspaceEdit(added_study_id=added_study_id)

    @staticmethod
    def _edit_year(study: Study, value: object) -> AppliedWorkspaceEdit:
        text = qt_text.to_native_text(value)
        if not qt_text.is_blank(text) and not is_an_int(text):
            return AppliedWorkspaceEdit(error="Years need to be integers.")
        try:
            study.year = int(float(text)) if not qt_text.is_blank(text) else 0
        except (TypeError, ValueError):
            return AppliedWorkspaceEdit(error="Years need to be integers.")
        return AppliedWorkspaceEdit()

    def _analysis_unit(self, dataset: Dataset, study: Study, context: WorkspaceEditingContext) -> AnalysisUnit:
        if context.outcome_name is None or context.follow_up_name is None:
            raise ValueError("an outcome and follow-up are required for analysis edits")
        from rc_metastudio.dataset_analysis_domain import ensure_analysis_unit

        return ensure_analysis_unit(
            dataset,
            study,
            context.outcome_name,
            context.follow_up_name,
            context.current_groups,
        )

    def _raw_data(self, dataset: Dataset, study: Study, context: WorkspaceEditingContext):
        return self._analysis_unit(dataset, study, context).get_raw_data_for_groups(
            context.current_groups
        )

    def _verify_raw_data(
        self, dataset: Dataset, study: Study, target: WorkspaceEditTarget, context: WorkspaceEditingContext, value: object
    ) -> str | None:
        text, numeric_valid = qt_text.normalize_decimal_text(value)
        if not numeric_valid:
            return "Raw data needs to be numeric."
        if qt_text.is_blank(text):
            return None
        if not is_a_float(text):
            return "Raw data needs to be numeric."
        error = self._verify_raw_number(text, context.data_type)
        if error:
            return error
        raw_data = self._raw_data(dataset, study, context)
        position = context.raw_columns.index(target.column)
        return self._verify_raw_bounds(text, raw_data, position, context.data_type)

    @staticmethod
    def _verify_raw_number(text: str, data_type: object) -> str | None:
        if data_type not in (BINARY, DIAGNOSTIC):
            return None
        if not is_an_int(text):
            return "Expected a whole number (count), but a decimal value was entered."
        if int(float(text)) < 0:
            return "Counts cannot be negative."
        return None

    @staticmethod
    def _verify_raw_bounds(
        text: str, raw_data, position: int, data_type: object
    ) -> str | None:
        if data_type == BINARY:
            return WorkspaceEditingService._verify_binary_bounds(text, raw_data, position)
        if data_type == CONTINUOUS:
            return WorkspaceEditingService._verify_continuous_bounds(text, position)
        return None

    @staticmethod
    def _verify_binary_bounds(text, raw_data, position: int) -> str | None:
        if position in (0, 2):
            sample = raw_data[position + 1]
            if is_an_int(sample) and int(float(text)) > int(float(sample)):
                return "Number of events cannot be greater than number of samples."
        if position in (1, 3):
            event = raw_data[position - 1]
            if is_an_int(event) and int(float(text)) < int(float(event)):
                return "Number of events cannot be greater than number of samples."
        return None

    @staticmethod
    def _verify_continuous_bounds(text, position: int) -> str | None:
        if float(text) > 0:
            return None
        if position in (0, 3):
            return "Count cannot be zero or negative"
        if position in (2, 5):
            return "Standard Deviation cannot be zero or negative"
        return None

    def _verify_outcome_data(
        self, dataset: Dataset, study: Study, target: WorkspaceEditTarget, context: WorkspaceEditingContext, value: object, import_csv: bool
    ) -> str | None:
        text, numeric_valid = qt_text.normalize_decimal_text(value)
        if not numeric_valid:
            return "Outcomes must be numeric."
        if qt_text.is_blank(text):
            return None
        if not is_a_float(text):
            return "Outcomes must be numeric."
        unit = self._analysis_unit(dataset, study, context)
        previous_display = self._previous_display_outcome(
            dataset, study, target, context, unit
        )
        raw_data = self._raw_data(dataset, study, context)
        if not import_csv and not all(is_empty(item) for item in raw_data):
            error = self._verify_raw_override(text, previous_display, target, context)
            if error:
                return error
        return self._verify_outcome_value(text, previous_display, target, context)

    def _previous_display_outcome(
        self, dataset, study, target, context, unit: AnalysisUnit
    ) -> tuple[object, object, object]:
        if context.data_type == DIAGNOSTIC:
            metric = "Sens" if target.column in context.outcome_columns[:3] else "Spec"
            effect = unit.get_effect_and_ci_for_source(
                "entered", metric, context.group_comparison, context.confidence_multiplier
            )
            converter = self.display_scale_converter(DIAGNOSTIC, metric)
        else:
            n1 = self._raw_data(dataset, study, context)[1] if context.current_effect == "PFT" else None
            effect = unit.get_effect_and_ci_for_source(
                "entered", context.current_effect or "", context.group_comparison, context.confidence_multiplier
            )
            converter = self.display_scale_converter(context.data_type, context.current_effect, n1)
        return tuple(converter(item) for item in effect)

    @staticmethod
    def _verify_raw_override(text, previous_display, target, context) -> str | None:
        outcome_index = context.outcome_columns.index(target.column) % 3
        previous = previous_display[outcome_index]
        delta = abs(float(text) - previous) if previous is not None else float("-inf")
        if delta > 10e-6:
            return "You have already entered raw data for this study. If you want to enter the outcome directly, delete the raw data first."
        return None

    @staticmethod
    def _verify_outcome_value(text, previous_display, target, context) -> str | None:
        number = float(text)
        if context.current_effect in ("OR", "RR") and number < 0:
            return "Ratios cannot be negative."
        outcome_index = context.outcome_columns.index(target.column) % 3
        if context.outcome_subtype == "generic_effect":
            generic_index = context.outcome_columns.index(target.column) % 2
            if context.data_type == CONTINUOUS and generic_index == 1 and number < 0:
                return "Standard Error cannot be negative"
            return None
        candidate = list(previous_display)
        candidate[outcome_index] = number
        ok, message = calculator_routines.between_bounds(
            est=candidate[0], low=candidate[1], high=candidate[2]
        )
        return None if ok else message

    def _edit_raw_data(
        self,
        dataset: Dataset,
        study: Study,
        target: WorkspaceEditTarget,
        context: WorkspaceEditingContext,
        value: object,
        recalculate: Callable[[int], None] | None,
    ) -> AppliedWorkspaceEdit:
        error = self._verify_raw_data(dataset, study, target, context, value)
        if error:
            return AppliedWorkspaceEdit(error=error)
        unit = self._analysis_unit(dataset, study, context)
        old_unit = copy.deepcopy(unit)
        try:
            position = context.raw_columns.index(target.column)
            per_group = len(unit.get_raw_data_for_group(context.current_groups[0]))
            group = context.current_groups[0] if position < per_group else context.current_groups[1]
            unit.get_raw_data_for_group(group)[position % per_group] = (
                "" if qt_text.is_blank(value) else float(qt_text.normalize_decimal_text(value)[0])
            )
            if recalculate is None:
                self.update_outcome_if_possible(dataset, target.row, context)
            else:
                recalculate(target.row)
        except Exception as exc:
            unit.__dict__.clear()
            unit.__dict__.update(copy.deepcopy(old_unit.__dict__))
            return AppliedWorkspaceEdit(error=f"Could not compute study effects from the edited raw data: {exc}")
        return AppliedWorkspaceEdit()

    def _edit_outcome(
        self, dataset: Dataset, study: Study, target: WorkspaceEditTarget, context: WorkspaceEditingContext, value: object, import_csv: bool
    ) -> AppliedWorkspaceEdit:
        error = self._verify_outcome_data(dataset, study, target, context, value, import_csv)
        if error:
            return AppliedWorkspaceEdit(error=error)
        unit = self._analysis_unit(dataset, study, context)
        normalized_value, _ = qt_text.normalize_decimal_text(value)
        display_value = None if qt_text.is_blank(value) else float(normalized_value)
        metric, outcome_index = self._outcome_metric(target, context)
        if metric is None:
            return AppliedWorkspaceEdit(error="No effect metric is selected.")
        n1 = self._outcome_sample_size(dataset, study, context)
        calculation_value = self.to_calculation_scale(
            display_value, context.data_type, metric, n1
        )
        self._set_entered_outcome(
            unit, metric, outcome_index, calculation_value, context
        )
        self._recalculate_entered_outcome(unit, metric, context)
        unit.calculate_display_effect_and_ci(
            metric,
            context.group_comparison,
            self.display_scale_converter(context.data_type, metric, n1),
            confidence_level=context.confidence_level,
            confidence_multiplier=context.confidence_multiplier,
            source="entered",
        )
        return AppliedWorkspaceEdit()

    @staticmethod
    def _outcome_metric(
        target: WorkspaceEditTarget, context: WorkspaceEditingContext
    ) -> tuple[str | None, int]:
        outcome_index = context.outcome_columns.index(target.column)
        if context.data_type == DIAGNOSTIC:
            return ("Spec" if outcome_index >= 3 else "Sens", outcome_index % 3)
        return context.current_effect, outcome_index

    def _outcome_sample_size(self, dataset, study, context):
        if context.current_effect != "PFT":
            return None
        return self._raw_data(dataset, study, context)[1]

    @staticmethod
    def _set_entered_outcome(
        unit: AnalysisUnit,
        metric: str,
        outcome_index: int,
        calculation_value,
        context: WorkspaceEditingContext,
    ) -> None:
        entered = unit.get_effect_for_source("entered", metric, context.group_comparison)
        if outcome_index == 0:
            values = (calculation_value, entered.lower, entered.upper, entered.standard_error)
        elif outcome_index == 1 and context.outcome_subtype == "generic_effect":
            values = (entered.estimate, entered.lower, entered.upper, calculation_value)
        elif outcome_index == 1:
            values = (entered.estimate, calculation_value, entered.upper, entered.standard_error)
        else:
            values = (entered.estimate, entered.lower, calculation_value, entered.standard_error)
        unit.set_effect_for_source("entered", metric, context.group_comparison, *values)

    @staticmethod
    def _recalculate_entered_outcome(
        unit: AnalysisUnit, metric: str, context: WorkspaceEditingContext
    ) -> None:
        if context.outcome_subtype == "generic_effect":
            return
        entered = unit.get_effect_for_source("entered", metric, context.group_comparison)
        values = (entered.estimate, entered.lower, entered.upper)
        se = unit.calculate_se_if_possible(
            metric,
            context.group_comparison,
            confidence_multiplier=context.confidence_multiplier,
            source="entered",
        ) if None not in values else None
        unit.set_effect_for_source(
            "entered", metric, context.group_comparison,
            entered.estimate, entered.lower, entered.upper, se,
        )

    def _edit_covariate(self, study: Study, context: WorkspaceEditingContext, value: object) -> AppliedWorkspaceEdit:
        if context.covariate_name is None:
            return AppliedWorkspaceEdit(error="Cannot edit that cell.")
        if context.covariate_type == FACTOR:
            converted = qt_text.to_native_text(value)
        elif qt_text.is_blank(value):
            converted = None
        else:
            converted, valid = self._number(value)
            if not valid:
                return AppliedWorkspaceEdit(error="Covariate values for continuous covariates need to be numeric.")
        if context.covariate is None:
            return AppliedWorkspaceEdit(error="Cannot edit that cell.")
        study.set_covariate_value(context.covariate, converted)
        return AppliedWorkspaceEdit()

    @staticmethod
    def _number(value: object) -> tuple[float | None, bool]:
        text, valid = qt_text.normalize_decimal_text(value)
        if not valid or qt_text.is_blank(text):
            return None, False
        try:
            return float(text), True
        except ValueError:
            return None, False

    def update_outcome_if_possible(
        self,
        dataset: Dataset,
        study_index: int,
        context: WorkspaceEditingContext,
        *,
        update_inclusion: bool = True,
    ) -> None:
        if context.outcome_name is None or context.follow_up_name is None:
            return
        study = dataset.studies[study_index]
        unit = self._analysis_unit(dataset, study, context)
        raw_data = self._raw_data(dataset, study, context)
        complete = self._raw_data_is_complete_for_context(raw_data, context)
        if update_inclusion and self._should_clear_inclusion(unit, context):
            study.include = False
        if complete:
            self._calculate_complete_outcome(
                study, unit, raw_data, context, update_inclusion=update_inclusion
            )
        elif not raw_data_is_empty(raw_data):
            self._clear_incomplete_outcome(unit, context)

    @staticmethod
    def _raw_data_is_complete_for_context(raw_data, context) -> bool:
        if raw_data_is_complete(raw_data):
            return True
        one_arm = context.current_effect in BINARY_ONE_ARM_METRICS + CONTINUOUS_ONE_ARM_METRICS
        return one_arm and raw_data_is_complete(raw_data[: len(raw_data) // 2])

    def _should_clear_inclusion(self, unit: AnalysisUnit, context) -> bool:
        return context.data_type == DIAGNOSTIC or not self._has_point_estimate(unit, context)

    def _calculate_complete_outcome(
        self, study, unit, raw_data, context, *, update_inclusion=True
    ) -> None:
        if update_inclusion and not study.manually_excluded:
            study.include = True
        calculated = self.preview_raw_effects(
            context.data_type, context.current_effect, raw_data, context.confidence_level
        )
        if context.data_type == DIAGNOSTIC:
            if not isinstance(calculated, dict):
                raise TypeError("diagnostic effects must be a metric mapping")
            for metric, (est, lower, upper) in calculated.items():
                self._set_calculated(unit, metric, context, est, lower, upper)
            return
        if not isinstance(calculated, tuple):
            raise TypeError("non-diagnostic effects must be a result tuple")
        (est, lower, upper), n1 = calculated
        self._set_calculated(unit, context.current_effect, context, est, lower, upper, n1)

    def _clear_incomplete_outcome(self, unit, context) -> None:
        metrics = (
            DIAGNOSTIC_METRICS
            if context.data_type == DIAGNOSTIC
            else (context.current_effect,)
        )
        for metric in metrics:
            self._clear_effect_and_display_ci(unit, metric, context)

    @staticmethod
    def _has_point_estimate(unit: AnalysisUnit, context: WorkspaceEditingContext) -> bool:
        return None not in unit.get_effect_and_se_for_source(
            "entered",
            context.current_effect or "",
            context.group_comparison,
            context.confidence_multiplier,
        )

    def _set_calculated(
        self, unit: AnalysisUnit, metric: str | None, context: WorkspaceEditingContext,
        estimate: object, lower: object, upper: object, n1: object = None,
    ) -> None:
        if metric is None:
            return
        unit.set_effect_and_ci(metric, context.group_comparison, estimate, lower, upper, confidence_multiplier=context.confidence_multiplier)
        unit.calculate_display_effect_and_ci(
            metric,
            context.group_comparison,
            self.display_scale_converter(context.data_type, metric, n1),
            confidence_level=context.confidence_level,
            confidence_multiplier=context.confidence_multiplier,
            source="derived_preview",
        )

    @staticmethod
    def _clear_effect_and_display_ci(unit: AnalysisUnit, metric: str | None, context: WorkspaceEditingContext) -> None:
        if metric is None:
            return
        unit.set_effect_for_source("derived_preview", metric, context.group_comparison, None, None, None, None)
        unit.set_display_effect_for_source("derived_preview", metric, context.group_comparison, None)
        unit.set_display_lower_for_source("derived_preview", metric, context.group_comparison, None)
        unit.set_display_upper_for_source("derived_preview", metric, context.group_comparison, None)
        unit.set_display_se_for_source("derived_preview", metric, context.group_comparison, None)
