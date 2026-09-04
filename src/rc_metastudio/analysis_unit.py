# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Analysis values and group data for one study outcome and follow-up."""

from __future__ import annotations

from dataclasses import dataclass
import copy
from typing import Literal, NewType
import uuid

from rc_metastudio import meta_globals

BINARY = meta_globals.BINARY
CONTINUOUS = meta_globals.CONTINUOUS
DIAGNOSTIC = meta_globals.DIAGNOSTIC
StableIdentity = NewType("StableIdentity", str)
EffectSource = Literal["entered", "derived_preview", "analysis"]


def _new_identity() -> StableIdentity:
    return StableIdentity(uuid.uuid4().hex)


@dataclass(frozen=True, slots=True)
class EffectEstimate:
    """One immutable effect value crossing an explicit authority boundary."""

    estimate: float | None
    lower: float | None
    upper: float | None
    standard_error: float | None = None


class AnalysisUnit:
    """Store one outcome at one follow-up, potentially across several groups."""

    def __init__(
        self, outcome, raw_data=None, group_names=None, stable_id=None
    ):
        """Create the analysis unit for one study outcome and follow-up.

        ``raw_data`` contains one list per group. Each list follows the raw-data
        layout for the outcome type.
        """
        self.is_diagnostic = outcome.data_type == DIAGNOSTIC
        self.outcome = outcome
        self.stable_id = stable_id or _new_identity()

        if group_names is None and not self.is_diagnostic:
            group_names = meta_globals.DEFAULT_GROUP_NAMES
        elif group_names is None:
            group_names = ["test 1"]

        # Group IDs keep effect entries stable when users rename groups.
        self.groups = {}

        self.raw_data_length = 0
        if outcome.data_type == BINARY:
            self.raw_data_length = 2
        elif outcome.data_type == CONTINUOUS:
            self.raw_data_length = 3
        elif outcome.data_type == DIAGNOSTIC:
            self.raw_data_length = 4
        else:
            raise ValueError(f"unrecognized outcome data type: {outcome.data_type!r}")

        raw_data = raw_data or [[""] * self.raw_data_length for _ in group_names]

        self.effects = {}
        self.entered_effects = self.effects
        self.derived_effect_previews = {}
        self.analysis_effects = {}

        if self.outcome.data_type == BINARY:
            for effect in (
                meta_globals.BINARY_TWO_ARM_METRICS
                + meta_globals.BINARY_ONE_ARM_METRICS
            ):
                self.effects[effect] = {}
        elif self.outcome.data_type == CONTINUOUS:
            # Continuous display effects are limited to the implemented mean
            # difference and standardized mean difference metrics.
            for effect in (
                meta_globals.CONTINUOUS_TWO_ARM_METRICS
                + meta_globals.CONTINUOUS_ONE_ARM_METRICS
            ):
                self.effects[effect] = {}
        elif self.outcome.data_type == DIAGNOSTIC:
            for effect in meta_globals.DIAGNOSTIC_METRICS:
                self.effects[effect] = {}

        for i, group in enumerate(group_names):
            self.add_group(group)
            self.groups[group].raw_data = raw_data[i]

    def adopt_calculated_state(self, candidate: "AnalysisUnit") -> None:
        """Publish a validated candidate while preserving this unit's identity.

        Table edits calculate against an isolated copy.  Once calculation has
        succeeded, callers can publish the complete state without mutating the
        live object during validation or relying on implementation-level
        ``__dict__`` restoration.
        """
        self.is_diagnostic = candidate.is_diagnostic
        self.outcome = candidate.outcome
        self.stable_id = candidate.stable_id
        self.raw_data_length = candidate.raw_data_length
        existing_groups = self.groups
        for name, candidate_group in candidate.groups.items():
            group = existing_groups.get(name)
            if group is None:
                group = copy.deepcopy(candidate_group)
            else:
                group.id = candidate_group.id
                group.name = candidate_group.name
                group.stable_id = candidate_group.stable_id
                group.raw_data[:] = copy.deepcopy(candidate_group.raw_data)
            existing_groups[name] = group
        for name in tuple(existing_groups):
            if name not in candidate.groups:
                del existing_groups[name]
        self.effects = copy.deepcopy(candidate.effects)
        self.entered_effects = self.effects
        self.derived_effect_previews = copy.deepcopy(candidate.derived_effect_previews)
        self.analysis_effects = copy.deepcopy(candidate.analysis_effects)

    def _new_effect_entry(self):
        return {
            "est": None,
            "lower": None,
            "upper": None,
            "SE": None,
            "display_est": None,
            "display_lower": None,
            "display_upper": None,
        }

    @staticmethod
    def _effect_entry(store, effect, group_comparison):
        return store.setdefault(effect, {}).setdefault(
            group_comparison,
            {
                "est": None,
                "lower": None,
                "upper": None,
                "SE": None,
            },
        )

    def set_effect_for_source(
        self,
        source: EffectSource,
        effect: str,
        group_comparison: str,
        estimate: float | None,
        lower: float | None = None,
        upper: float | None = None,
        standard_error: float | None = None,
    ) -> None:
        """Store a value without conflating entered, preview, and analysis data."""
        stores = {
            "entered": self.entered_effects,
            "derived_preview": self.derived_effect_previews,
            "analysis": self.analysis_effects,
        }
        entry = self._effect_entry(stores[source], effect, group_comparison)
        entry.update(
            {
                "est": estimate,
                "lower": lower,
                "upper": upper,
                "SE": standard_error,
            }
        )

    def get_effect_for_source(
        self, source: EffectSource, effect: str, group_comparison: str
    ) -> EffectEstimate:
        stores = {
            "entered": self.entered_effects,
            "derived_preview": self.derived_effect_previews,
            "analysis": self.analysis_effects,
        }
        entry = stores[source].get(effect, {}).get(group_comparison, {})
        return EffectEstimate(
            entry.get("est"),
            entry.get("lower"),
            entry.get("upper"),
            entry.get("SE"),
        )

    def _add_effect_entries_for_group(self, new_group):
        group_names = list(self.groups)
        if self.outcome.data_type == BINARY:
            two_arm_metrics = meta_globals.BINARY_TWO_ARM_METRICS
            one_arm_metrics = meta_globals.BINARY_ONE_ARM_METRICS
        elif self.outcome.data_type == CONTINUOUS:
            two_arm_metrics = meta_globals.CONTINUOUS_TWO_ARM_METRICS
            one_arm_metrics = meta_globals.CONTINUOUS_ONE_ARM_METRICS
        elif self.outcome.data_type == DIAGNOSTIC:
            for effect in meta_globals.DIAGNOSTIC_METRICS:
                self.effects[effect][new_group] = self._new_effect_entry()
            return
        else:
            return

        for effect in two_arm_metrics:
            for group in group_names:
                for group_comparison in (
                    "-".join((new_group, group)),
                    "-".join((group, new_group)),
                ):
                    self.effects[effect][group_comparison] = self._new_effect_entry()
        for effect in one_arm_metrics:
            self.effects[effect][new_group] = self._new_effect_entry()

    def calculate_se_if_possible(
        self,
        effect,
        group_comparison,
        est=None,
        lower=None,
        upper=None,
        confidence_multiplier=None,
    ):
        if confidence_multiplier is None:
            raise ValueError("Mult must be specified")

        if est is None:
            est = self.effects[effect][group_comparison]["est"]
        if lower is None:
            lower = self.effects[effect][group_comparison]["lower"]
        if upper is None:
            upper = self.effects[effect][group_comparison]["upper"]

        if upper is not None and est is not None:
            return (upper - est) / confidence_multiplier
        if est is not None and lower is not None:
            return (est - lower) / confidence_multiplier
        if upper is not None and lower is not None:
            return (upper - lower) / (2 * confidence_multiplier)
        return None

    def set_effect(self, effect, group_comparison, value):
        self.effects[effect][group_comparison]["est"] = value

    def set_lower(self, effect, group_comparison, lower):
        self.effects[effect][group_comparison]["lower"] = lower

    def set_upper(self, effect, group_comparison, upper):
        self.effects[effect][group_comparison]["upper"] = upper

    def set_standard_error(self, effect, group_comparison, se):
        self.effects[effect][group_comparison]["SE"] = se

    def set_display_effect(self, effect, group_comparison, value):
        self.effects[effect][group_comparison]["display_est"] = value

    def set_display_lower(self, effect, group_comparison, lower):
        self.effects[effect][group_comparison]["display_lower"] = lower

    def set_display_upper(self, effect, group_comparison, upper):
        self.effects[effect][group_comparison]["display_upper"] = upper

    def set_display_se(self, effect, group_comparison, se):
        self.effects[effect][group_comparison]["display_se"] = se

    def calculate_display_effect_and_ci(
        self,
        effect,
        group_comparison,
        convert_to_display_scale,
        confidence_level=None,
        confidence_multiplier=None,
        check_if_necessary=False,
    ):
        if None in [confidence_level, confidence_multiplier]:
            raise ValueError("confidence level and multiplier must be specified")

        if (
            check_if_necessary
            and not self._should_calculate_display_effect_and_ci_and_se(
                effect, group_comparison, confidence_level
            )
        ):
            return

        if convert_to_display_scale is None:
            raise ValueError("Display-scale conversion is unavailable")

        est, lower, upper = self.get_effect_and_ci(
            effect, group_comparison, confidence_multiplier
        )
        display_estimate, display_lower, display_upper = [
            convert_to_display_scale(x) for x in [est, lower, upper]
        ]
        se = self.get_se(effect, group_comparison, confidence_multiplier)
        display_standard_error = se

        self.set_display_effect(effect, group_comparison, display_estimate)
        self.set_display_lower(effect, group_comparison, display_lower)
        self.set_display_upper(effect, group_comparison, display_upper)
        self.set_display_se(effect, group_comparison, display_standard_error)
        self.effects[effect][group_comparison]["display_conf_level"] = confidence_level

    def get_display_effect(self, effect, group_comparison):
        return self.effects[effect][group_comparison].get("display_est")

    def get_display_lower(self, effect, group_comparison):
        return self.effects[effect][group_comparison].get("display_lower")

    def get_display_upper(self, effect, group_comparison):
        return self.effects[effect][group_comparison].get("display_upper")

    def get_display_se(self, effect, group_comparison):
        return self.effects[effect][group_comparison].get("display_se")

    def get_display_effect_and_ci(self, effect, group_comparison):
        return (
            self.get_display_effect(effect, group_comparison),
            self.get_display_lower(effect, group_comparison),
            self.get_display_upper(effect, group_comparison),
        )

    def get_display_effect_and_se(self, effect, group_comparison):
        return (
            self.get_display_effect(effect, group_comparison),
            self.get_display_se(effect, group_comparison),
        )

    def _should_calculate_display_effect_and_ci_and_se(
        self, effect, group_comparison, confidence_level=None
    ):
        if confidence_level is None:
            raise ValueError("Confidence level must be specified")

        display_confidence_level = self.effects[effect][group_comparison].get(
            "display_conf_level"
        )
        return display_confidence_level is None or not meta_globals.equal_close_enough(
            display_confidence_level, confidence_level
        )

    def get_estimate(self, effect, group_comparison):
        return self.effects[effect][group_comparison].get("est")

    def get_lower(self, effect, group_comparison, confidence_multiplier):
        return self._helper_get_upper_lower(
            "lower", effect, group_comparison, confidence_multiplier
        )

    def get_upper(self, effect, group_comparison, confidence_multiplier):
        return self._helper_get_upper_lower(
            "upper", effect, group_comparison, confidence_multiplier
        )

    def _helper_get_upper_lower(
        self, boundary, effect, group_comparison, confidence_multiplier=None
    ):
        if confidence_multiplier is None:
            raise ValueError("Mult must be specified")

        if boundary not in ["upper", "lower"]:
            raise Exception("Boundary must be one of 'upper' or 'lower'")

        if self.get_se(effect, group_comparison, confidence_multiplier) is None:
            return self.effects[effect][group_comparison][boundary]
        est = self.get_estimate(effect, group_comparison)
        se = self.get_se(effect, group_comparison, confidence_multiplier)
        if est is None or se is None:
            return None
        return (
            est - confidence_multiplier * se
            if boundary == "lower"
            else est + confidence_multiplier * se
        )

    def get_se(self, effect, group_comparison, confidence_multiplier):
        standard_error = self.effects[effect][group_comparison].get("SE")
        if standard_error is not None:
            return standard_error
        return self.calculate_se_if_possible(
            effect, group_comparison, confidence_multiplier=confidence_multiplier
        )

    def set_effect_and_ci(
        self, effect, group_comparison, est, lower, upper, confidence_multiplier
    ):
        self.set_effect(effect, group_comparison, est)
        self.effects[effect][group_comparison]["lower"] = lower
        self.effects[effect][group_comparison]["upper"] = upper

        se = self.calculate_se_if_possible(
            effect,
            group_comparison,
            est,
            lower,
            upper,
            confidence_multiplier=confidence_multiplier,
        )
        self.set_standard_error(effect, group_comparison, se)

    def get_effect_and_ci(self, effect, group_comparison, confidence_multiplier):
        return (
            self.get_estimate(effect, group_comparison),
            self.get_lower(effect, group_comparison, confidence_multiplier),
            self.get_upper(effect, group_comparison, confidence_multiplier),
        )

    def get_effect_and_se(self, effect, group_comparison, confidence_multiplier):
        return (
            self.get_estimate(effect, group_comparison),
            self.get_se(effect, group_comparison, confidence_multiplier),
        )

    def get_entered_effect_and_ci(self, effect, group_comparison):
        return (
            self.effects[effect][group_comparison]["est"],
            self.effects[effect][group_comparison]["lower"],
            self.effects[effect][group_comparison]["upper"],
        )

    def get_group_strings(self, effect):
        return list(self.effects[effect].keys())

    def get_effect_names(self):
        return list(self.effects.keys())

    def add_group(self, name, raw_data=None):
        if not self.groups:
            group_id = 0
        else:
            group_id = max(group.id for group in self.groups.values()) + 1
        if raw_data is None:
            raw_data = [""] * self.raw_data_length
        self._add_effect_entries_for_group(name)
        self.groups[name] = Group(group_id, name, raw_data)

    def remove_group(self, name):
        self.groups.pop(name)

    def rename_group(self, old_name, new_name):
        if old_name == new_name:
            return

        original_group_names = list(self.groups)
        group = self.groups.pop(old_name)
        group.name = new_name
        self.groups[new_name] = group

        # Effect keys are persisted as either one group name or an ordered
        # ``left-right`` pair. Build the known keys from the group collection;
        # splitting on "-" corrupts legitimate names such as "Usual-care".
        key_replacements = {old_name: new_name}
        for left_group in original_group_names:
            for right_group in original_group_names:
                if left_group == right_group:
                    continue
                old_key = "-".join((left_group, right_group))
                new_key = "-".join(
                    (
                        new_name if left_group == old_name else left_group,
                        new_name if right_group == old_name else right_group,
                    )
                )
                if old_key != new_key:
                    key_replacements[old_key] = new_key

        for effect_values in self.effects.values():
            for old_key, new_key in key_replacements.items():
                if old_key in effect_values:
                    effect_values[new_key] = effect_values.pop(old_key)

    def get_raw_data_for_group(self, group_name):
        return self.groups[group_name].raw_data

    def set_raw_data_for_group(self, group_name, raw_data):
        self.groups[group_name].raw_data = raw_data
        self.derived_effect_previews.clear()

    def get_raw_data_for_groups(self, groups):
        if len(groups) == 1:
            return self.get_raw_data_for_group(groups[0])
        raw_data = []
        for group in groups:
            raw_data.extend(self.get_raw_data_for_group(group))
        return raw_data

    def set_raw_data_for_groups(self, groups, raw_data_list):
        # note: raw_data_list should be a *nested list*, where entry
        # i is the raw data for groups[i].
        for i, group in enumerate(groups):
            self.set_raw_data_for_group(group, raw_data_list[i])

    def get_group_names(self):
        return list(self.groups.keys())


class Group:
    def __init__(self, id, name, raw_data, stable_id=None):
        self.id = id
        self.name = name
        self.raw_data = raw_data
        self.stable_id = stable_id or _new_identity()
