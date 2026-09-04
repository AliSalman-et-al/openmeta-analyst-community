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
        self,
        outcome,
        raw_data=None,
        group_names=None,
        stable_id=None,
        group_stable_ids=None,
    ):
        """Create the analysis unit for one study outcome and follow-up.

        ``raw_data`` contains one list per group. Each list follows the raw-data
        layout for the outcome type.
        """
        self.is_diagnostic = outcome.data_type == DIAGNOSTIC
        self.outcome = outcome
        self.follow_up_id = None
        self.follow_up_label = None
        self.stable_id = stable_id or _new_identity()

        if group_names is None and not self.is_diagnostic:
            group_names = meta_globals.DEFAULT_GROUP_NAMES
        elif group_names is None:
            group_names = ["test 1"]

        # Group IDs keep effect entries stable when users rename groups.
        self._groups_by_id = {}

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

        self.entered_effects = {}
        self.derived_effect_previews = {}
        self.analysis_effects = {}

        if self.outcome.data_type == BINARY:
            for effect in (
                meta_globals.BINARY_TWO_ARM_METRICS
                + meta_globals.BINARY_ONE_ARM_METRICS
            ):
                self.entered_effects[effect] = {}
        elif self.outcome.data_type == CONTINUOUS:
            # Continuous display effects are limited to the implemented mean
            # difference and standardized mean difference metrics.
            for effect in (
                meta_globals.CONTINUOUS_TWO_ARM_METRICS
                + meta_globals.CONTINUOUS_ONE_ARM_METRICS
            ):
                self.entered_effects[effect] = {}
        elif self.outcome.data_type == DIAGNOSTIC:
            for effect in meta_globals.DIAGNOSTIC_METRICS:
                self.entered_effects[effect] = {}

        identities = group_stable_ids or [None] * len(group_names)
        for i, group in enumerate(group_names):
            self.add_group(group, stable_id=identities[i])
            self.groups[group].raw_data = raw_data[i]

    @property
    def groups_by_id(self):
        return self._groups_by_id

    @property
    def groups(self):
        return {group.name: group for group in self._groups_by_id.values()}

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
        existing_groups = self._groups_by_id
        for name, candidate_group in candidate.groups.items():
            group = existing_groups.get(candidate_group.stable_id)
            if group is None:
                group = next(
                    (item for item in existing_groups.values() if item.name == name),
                    None,
                )
            if group is None:
                group = copy.deepcopy(candidate_group)
            else:
                group.id = candidate_group.id
                group.name = candidate_group.name
                group.stable_id = candidate_group.stable_id
                group.raw_data[:] = copy.deepcopy(candidate_group.raw_data)
            existing_groups[group.stable_id] = group
        for identity, group in tuple(existing_groups.items()):
            if group.name not in candidate.groups:
                existing_groups.pop(identity)
        self.entered_effects = copy.deepcopy(candidate.entered_effects)
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

    def _store(self, source: EffectSource):
        return {
            "entered": self.entered_effects,
            "derived_preview": self.derived_effect_previews,
            "analysis": self.analysis_effects,
        }[source]

    def _entry(self, source: EffectSource, effect: str, group_comparison: str):
        return self._store(source).setdefault(effect, {}).setdefault(
            group_comparison, self._new_effect_entry()
        )

    def get_effect_for_source(
        self, source: EffectSource, effect: str, group_comparison: str
    ) -> EffectEstimate:
        entry = self._store(source).get(effect, {}).get(group_comparison, {})
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
                self.entered_effects[effect][new_group] = self._new_effect_entry()
            return
        else:
            return

        for effect in two_arm_metrics:
            for group in group_names:
                for group_comparison in (
                    "-".join((new_group, group)),
                    "-".join((group, new_group)),
                ):
                    self.entered_effects[effect][group_comparison] = self._new_effect_entry()
        for effect in one_arm_metrics:
            self.entered_effects[effect][new_group] = self._new_effect_entry()

    def calculate_se_if_possible(
        self,
        effect,
        group_comparison,
        est=None,
        lower=None,
        upper=None,
        confidence_multiplier=None,
        *,
        source: EffectSource = "entered",
    ):
        if confidence_multiplier is None:
            raise ValueError("Mult must be specified")

        entry = self._entry(source, effect, group_comparison)
        if est is None:
            est = entry["est"]
        if lower is None:
            lower = entry["lower"]
        if upper is None:
            upper = entry["upper"]

        if upper is not None and est is not None:
            return (upper - est) / confidence_multiplier
        if est is not None and lower is not None:
            return (est - lower) / confidence_multiplier
        if upper is not None and lower is not None:
            return (upper - lower) / (2 * confidence_multiplier)
        return None

    def set_effect(self, effect, group_comparison, value):
        self.entered_effects[effect][group_comparison]["est"] = value

    def set_lower(self, effect, group_comparison, lower):
        self.entered_effects[effect][group_comparison]["lower"] = lower

    def set_upper(self, effect, group_comparison, upper):
        self.entered_effects[effect][group_comparison]["upper"] = upper

    def set_standard_error(self, effect, group_comparison, se):
        self.entered_effects[effect][group_comparison]["SE"] = se

    def set_display_effect_for_source(
        self, source: EffectSource, effect, group_comparison, value
    ):
        self._entry(source, effect, group_comparison)["display_est"] = value

    def set_display_lower_for_source(
        self, source: EffectSource, effect, group_comparison, lower
    ):
        self._entry(source, effect, group_comparison)["display_lower"] = lower

    def set_display_upper_for_source(
        self, source: EffectSource, effect, group_comparison, upper
    ):
        self._entry(source, effect, group_comparison)["display_upper"] = upper

    def set_display_se_for_source(
        self, source: EffectSource, effect, group_comparison, se
    ):
        self._entry(source, effect, group_comparison)["display_se"] = se

    def calculate_display_effect_and_ci(
        self,
        effect,
        group_comparison,
        convert_to_display_scale,
        confidence_level=None,
        confidence_multiplier=None,
        check_if_necessary=False,
        *,
        source: EffectSource,
    ):
        if None in [confidence_level, confidence_multiplier]:
            raise ValueError("confidence level and multiplier must be specified")

        if (
            check_if_necessary
            and not self._should_calculate_display_effect_and_ci_and_se(
                effect,
                group_comparison,
                confidence_level,
                source=source,
            )
        ):
            return

        if convert_to_display_scale is None:
            raise ValueError("Display-scale conversion is unavailable")

        est, lower, upper = self.get_effect_and_ci_for_source(
            source, effect, group_comparison, confidence_multiplier
        )
        display_estimate, display_lower, display_upper = [
            convert_to_display_scale(x) for x in [est, lower, upper]
        ]
        se = self.get_se(source, effect, group_comparison, confidence_multiplier)
        display_standard_error = se

        self.set_display_effect_for_source(
            source, effect, group_comparison, display_estimate
        )
        self.set_display_lower_for_source(
            source, effect, group_comparison, display_lower
        )
        self.set_display_upper_for_source(
            source, effect, group_comparison, display_upper
        )
        self.set_display_se_for_source(
            source, effect, group_comparison, display_standard_error
        )
        self._entry(source, effect, group_comparison)[
            "display_conf_level"
        ] = confidence_level

    def get_display_effect_for_source(self, source: EffectSource, effect, group_comparison):
        return self._entry(source, effect, group_comparison).get("display_est")

    def get_display_lower_for_source(self, source: EffectSource, effect, group_comparison):
        return self._entry(source, effect, group_comparison).get("display_lower")

    def get_display_upper_for_source(self, source: EffectSource, effect, group_comparison):
        return self._entry(source, effect, group_comparison).get("display_upper")

    def get_display_se_for_source(self, source: EffectSource, effect, group_comparison):
        return self._entry(source, effect, group_comparison).get("display_se")

    def get_display_effect_and_ci_for_source(
        self, source: EffectSource, effect, group_comparison
    ):
        return (
            self.get_display_effect_for_source(source, effect, group_comparison),
            self.get_display_lower_for_source(source, effect, group_comparison),
            self.get_display_upper_for_source(source, effect, group_comparison),
        )

    def get_display_effect_and_se_for_source(
        self, source: EffectSource, effect, group_comparison
    ):
        return (
            self.get_display_effect_for_source(source, effect, group_comparison),
            self.get_display_se_for_source(source, effect, group_comparison),
        )

    def _should_calculate_display_effect_and_ci_and_se(
        self,
        effect,
        group_comparison,
        confidence_level=None,
        *,
        source: EffectSource,
    ):
        if confidence_level is None:
            raise ValueError("Confidence level must be specified")

        display_confidence_level = self._entry(
            source, effect, group_comparison
        ).get("display_conf_level")
        return display_confidence_level is None or not meta_globals.equal_close_enough(
            display_confidence_level, confidence_level
        )

    def get_estimate_for_source(self, source: EffectSource, effect, group_comparison):
        return self._entry(source, effect, group_comparison).get("est")

    def get_lower_for_source(
        self, source: EffectSource, effect, group_comparison, confidence_multiplier
    ):
        return self._helper_get_upper_lower(
            "lower", source, effect, group_comparison, confidence_multiplier
        )

    def get_upper_for_source(
        self, source: EffectSource, effect, group_comparison, confidence_multiplier
    ):
        return self._helper_get_upper_lower(
            "upper", source, effect, group_comparison, confidence_multiplier
        )

    def _helper_get_upper_lower(
        self,
        boundary,
        source: EffectSource,
        effect,
        group_comparison,
        confidence_multiplier=None,
    ):
        if confidence_multiplier is None:
            raise ValueError("Mult must be specified")

        if boundary not in ["upper", "lower"]:
            raise Exception("Boundary must be one of 'upper' or 'lower'")

        if self.get_se(source, effect, group_comparison, confidence_multiplier) is None:
            return self._entry(source, effect, group_comparison)[boundary]
        est = self.get_estimate_for_source(source, effect, group_comparison)
        se = self.get_se(source, effect, group_comparison, confidence_multiplier)
        if est is None or se is None:
            return None
        return (
            est - confidence_multiplier * se
            if boundary == "lower"
            else est + confidence_multiplier * se
        )

    def get_se(
        self, source: EffectSource, effect, group_comparison, confidence_multiplier
    ):
        entry = self._entry(source, effect, group_comparison)
        standard_error = entry.get("SE")
        if standard_error is not None:
            return standard_error
        return self.calculate_se_if_possible(
            effect,
            group_comparison,
            confidence_multiplier=confidence_multiplier,
            source=source,
        )

    def set_effect_and_ci(
        self, effect, group_comparison, est, lower, upper, confidence_multiplier
    ):
        # Raw-data calculations are previews.  They must not overwrite values
        # explicitly entered by the user or values published by a meta-analysis.
        self.set_effect_for_source(
            "derived_preview",
            effect,
            group_comparison,
            est,
            lower,
            upper,
        )

        if upper is not None and est is not None:
            se = (upper - est) / confidence_multiplier
        elif est is not None and lower is not None:
            se = (est - lower) / confidence_multiplier
        elif upper is not None and lower is not None:
            se = (upper - lower) / (2 * confidence_multiplier)
        else:
            se = None
        self.set_effect_for_source(
            "derived_preview",
            effect,
            group_comparison,
            est,
            lower,
            upper,
            standard_error=se,
        )

    def get_effect_and_ci_for_source(
        self,
        source: EffectSource,
        effect,
        group_comparison,
        confidence_multiplier,
    ):
        return (
            self.get_estimate_for_source(source, effect, group_comparison),
            self.get_lower_for_source(
                source, effect, group_comparison, confidence_multiplier
            ),
            self.get_upper_for_source(
                source, effect, group_comparison, confidence_multiplier
            ),
        )

    def get_effect_and_se_for_source(
        self,
        source: EffectSource,
        effect,
        group_comparison,
        confidence_multiplier,
    ):
        return (
            self.get_estimate_for_source(source, effect, group_comparison),
            self.get_se(source, effect, group_comparison, confidence_multiplier),
        )

    def get_entered_effect_and_ci(self, effect, group_comparison):
        entry = self.entered_effects[effect][group_comparison]
        return (
            entry["est"],
            entry["lower"],
            entry["upper"],
        )

    def get_group_strings(self, effect):
        return list(self.entered_effects[effect].keys())

    def get_effect_names(self):
        return list(self.entered_effects.keys())

    def add_group(self, name, raw_data=None, stable_id=None):
        if not self.groups:
            group_id = 0
        else:
            group_id = max(group.id for group in self._groups_by_id.values()) + 1
        if raw_data is None:
            raw_data = [""] * self.raw_data_length
        self._add_effect_entries_for_group(name)
        group = Group(group_id, name, raw_data, stable_id=stable_id)
        self._groups_by_id[group.stable_id] = group

    def remove_group(self, name):
        group = self.groups[name]
        self._groups_by_id.pop(group.stable_id, None)
        remaining_groups = list(self.groups)
        removed_keys = {name}
        for other in remaining_groups:
            removed_keys.update((f"{name}-{other}", f"{other}-{name}"))
        for store in (
            self.entered_effects,
            self.derived_effect_previews,
            self.analysis_effects,
        ):
            for effect_values in store.values():
                for key in removed_keys:
                    effect_values.pop(key, None)

    def rename_group(self, old_name, new_name):
        if old_name == new_name:
            return

        original_group_names = list(self.groups)
        group = self.groups[old_name]
        group.name = new_name
        self._groups_by_id.pop(group.stable_id)
        self._groups_by_id[group.stable_id] = group

        replacements = _group_key_replacements(
            original_group_names, old_name, new_name
        )
        for store in (
            self.entered_effects,
            self.derived_effect_previews,
            self.analysis_effects,
        ):
            for effect_values in store.values():
                _rename_effect_keys(effect_values, replacements)

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
        return [group.name for group in self._groups_by_id.values()]


def _group_key_replacements(group_names, old_name, new_name):
    """Build replacements without parsing names that may contain hyphens."""
    replacements = {old_name: new_name}
    for left_group in group_names:
        for right_group in group_names:
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
                replacements[old_key] = new_key
    return replacements


def _rename_effect_keys(effect_values, replacements):
    for old_key, new_key in replacements.items():
        if old_key in effect_values:
            effect_values[new_key] = effect_values.pop(old_key)


class Group:
    def __init__(self, id, name, raw_data, stable_id=None):
        self.id = id
        self.name = name
        self.raw_data = raw_data
        self.stable_id = stable_id or _new_identity()
