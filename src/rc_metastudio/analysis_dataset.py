# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""UI-independent dataset model for studies, outcomes, follow-ups, and groups."""

import copy
import uuid

from rc_metastudio import two_way_dict
from rc_metastudio.analysis_unit import AnalysisUnit
from rc_metastudio import meta_globals

BINARY = meta_globals.BINARY
CONTINUOUS = meta_globals.CONTINUOUS
DIAGNOSTIC = meta_globals.DIAGNOSTIC
EMPTY_VALS = meta_globals.EMPTY_VALS
FACTOR = meta_globals.FACTOR
TYPE_TO_STR_DICT = meta_globals.TYPE_TO_STR_DICT


def _unique_in_first_seen_order(values):
    seen = set()
    ordered = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _cmp(left, right):
    return (left > right) - (left < right)


class Dataset:
    def __len__(self):
        return len(self.studies)

    def __init__(self, title=None, is_diagnostic=False, summary=None):
        self.title = title
        self.summary = summary
        self.studies = []
        self.is_diagnostic = is_diagnostic
        self.follow_ups_by_outcome = {}
        self.follow_up_stable_ids_by_outcome = {}
        # Identity-owned relationships are authoritative.  The label-keyed
        # maps above remain a presentation index for the existing table model;
        # rename operations never mutate these identity maps.
        self.outcomes_by_id = {}
        self.follow_ups_by_outcome_id = {}

        self.notes = ""

        self.covariates = []

    def copy(self):
        return copy.deepcopy(self)

    def get_outcome_names(self):
        if self.outcomes_by_id:
            return sorted(outcome.name for outcome in self.outcomes_by_id.values())
        return sorted(self.follow_ups_by_outcome.keys())

    def change_group_name(
        self, old_group_name, new_group_name, outcome=None, follow_up=None
    ):
        if (outcome is None and follow_up is not None) or (
            follow_up is None and outcome is not None
        ):
            raise ValueError(
                "outcome and follow_up must either both be provided or both be omitted"
            )

        for study in self.studies:
            if outcome is None and follow_up is None:
                units = study.analysis_units
            else:
                units = [study.get_analysis_unit(outcome, follow_up)]
            for analysis_unit in units:
                analysis_unit.rename_group(old_group_name, new_group_name)

    def change_outcome_name(self, old_outcome_name, new_outcome_name):
        self.follow_ups_by_outcome[new_outcome_name] = self.follow_ups_by_outcome.pop(
            old_outcome_name
        )
        self.follow_up_stable_ids_by_outcome[new_outcome_name] = (
            self.follow_up_stable_ids_by_outcome.pop(old_outcome_name)
        )
        for study in self.studies:
            study.analysis_units_by_outcome[new_outcome_name] = (
                study.analysis_units_by_outcome.pop(old_outcome_name)
            )
            for outcome in study.outcomes:
                if outcome.name == old_outcome_name:
                    outcome.name = new_outcome_name

    def add_study(self, study, study_index=None):
        # Empty outcomes and follow-ups remain valid until analysis execution.
        for covariate in self.covariates:
            study.covariate_values.setdefault(covariate.name, None)
            study.covariate_values_by_id.setdefault(covariate.stable_id, None)
        if study_index is None:
            self.studies.append(study)
        else:
            self.studies.insert(study_index, study)

    def remove_study(self, studyid):
        self.studies = [study for study in self.studies if study.id != studyid]

    def get_outcome_type(self, outcome_name, get_string=False):
        outcome = self.get_outcome_obj(outcome_name)
        if outcome is None:
            return None
        return (
            outcome.data_type if not get_string else TYPE_TO_STR_DICT[outcome.data_type]
        )

    def get_outcome_subtype(self, outcome_name):
        outcome = self.get_outcome_obj(outcome_name)
        if outcome is None or not hasattr(outcome, "sub_type"):
            return None
        return outcome.sub_type

    def get_outcome_obj(self, outcome_name):
        outcome = next(
            (outcome for outcome in self.outcomes_by_id.values() if outcome.name == outcome_name),
            None,
        )
        if outcome is not None:
            return outcome
        for study in self.studies:
            outcome = study.get_outcome(outcome_name)
            if outcome is not None:
                return outcome
        return None

    def max_study_id(self):
        if not self.studies:
            return -1
        return max(study.id for study in self.studies)

    def remove_covariate(self, covariate):
        covariate_index = None
        covariate_name = (
            covariate.name if isinstance(covariate, Covariate) else covariate
        )
        removed_covariate = next(
            (item for item in self.covariates if item.name == covariate_name), None
        )
        for i, cov in enumerate(self.covariates):
            if cov.name == covariate_name:
                self.covariates.remove(cov)
                covariate_index = i
                break
        for study in self.studies:
            if covariate_name in study.covariate_values:
                study.covariate_values.pop(covariate_name)
            if removed_covariate is not None:
                study.covariate_values_by_id.pop(removed_covariate.stable_id, None)
        return covariate_index

    def add_covariate(self, covariate, covariate_values=None, covariate_index=None):
        if covariate_index is None:
            self.covariates.append(covariate)
        else:
            self.covariates.insert(covariate_index, covariate)

        if covariate_values is None:
            for study in self.studies:
                study.covariate_values[covariate.name] = None
                study.covariate_values_by_id[covariate.stable_id] = None
        else:
            for study in self.studies:
                if study.name in covariate_values:
                    study.covariate_values[covariate.name] = covariate_values[
                        study.name
                    ]
                    study.covariate_values_by_id[covariate.stable_id] = covariate_values[
                        study.name
                    ]
                else:
                    study.covariate_values[covariate.name] = None
                    study.covariate_values_by_id[covariate.stable_id] = None

    def change_covariate_name(self, old_covariate, new_covariate_name):
        covariate_values = copy.deepcopy(self.get_covariate_values(old_covariate.name))
        stable_id = getattr(old_covariate, "stable_id", None)
        covariate_index = self.remove_covariate(old_covariate)
        self.add_covariate(
            Covariate(
                new_covariate_name,
                TYPE_TO_STR_DICT[old_covariate.data_type],
                stable_id=stable_id,
            ),
            covariate_values=covariate_values,
            covariate_index=covariate_index,
        )

    def get_covariate(self, covariate_name):
        for cov in self.covariates:
            if cov.name == covariate_name:
                return cov

    def get_covariate_values(self, covariate, ids_for_keys=False):
        """Return non-empty covariate values keyed by study name or stable ID."""
        covariate_name = covariate
        if isinstance(covariate, Covariate):
            covariate_name = covariate.name
        covariate_values = {}
        for study in self.studies:
            if (
                covariate_name in study.covariate_values
                and study.covariate_values[covariate_name] is not None
            ):
                value = study.covariate_values[covariate_name]
                if ids_for_keys:
                    covariate_values[study.id] = value
                else:
                    covariate_values[study.name] = value
        return covariate_values

    def get_covariate_names(self):
        return [cov.name for cov in self.covariates]

    def add_outcome(self, outcome):
        current_group_names = self.get_group_names()
        if not current_group_names:
            current_group_names = None

        follow_up = "first"
        self.follow_ups_by_outcome[outcome.name] = two_way_dict.TwoWayDict()
        self.follow_ups_by_outcome[outcome.name][0] = follow_up
        self.follow_up_stable_ids_by_outcome[outcome.name] = {follow_up: _new_stable_id()}
        self.outcomes_by_id[outcome.stable_id] = outcome
        follow_up_id = next(iter(self.follow_up_stable_ids_by_outcome[outcome.name].values()))
        self.follow_ups_by_outcome_id[outcome.stable_id] = {
            follow_up_id: FollowUp(follow_up_id, follow_up)
        }

        for study in self.studies:
            study.add_outcome(
                outcome,
                follow_up,
                group_names=current_group_names,
                follow_up_id=follow_up_id,
            )

    def remove_outcome(self, outcome_name):
        if outcome_name is None:
            return
        outcome = self.get_outcome_obj(outcome_name)
        self.follow_ups_by_outcome.pop(outcome_name)
        self.follow_up_stable_ids_by_outcome.pop(outcome_name, None)
        if outcome is not None:
            self.outcomes_by_id.pop(outcome.stable_id, None)
            self.follow_ups_by_outcome_id.pop(outcome.stable_id, None)
        for study in self.studies:
            study.remove_outcome(outcome_name)

    def add_group(self, group_name, outcome_name, follow_up_name=None):
        # A group applies to every follow-up for the selected outcome unless one
        # follow-up is explicitly requested.
        outcome = self.get_outcome_obj(outcome_name)
        group_names = self.get_group_names()
        if not group_names:
            group_names = None
        for study in self.studies:
            if outcome_name not in study.analysis_units_by_outcome:
                study.add_outcome(
                    outcome,
                    group_names=group_names,
                    follow_up_id=self.get_follow_up_stable_id(
                        outcome_name, "first"
                    ),
                )
                for follow_up in list(
                    self.follow_ups_by_outcome[outcome_name].values()
                ):
                    if follow_up not in study.analysis_units_by_outcome[outcome_name]:
                        study.add_outcome_at_follow_up(
                            outcome,
                            follow_up,
                            follow_up_id=self.get_follow_up_stable_id(
                                outcome_name, follow_up
                            ),
                        )
            analysis_units = study.analysis_units_by_outcome[outcome_name]
            if follow_up_name is None:
                for analysis_unit in list(analysis_units.values()):
                    analysis_unit.add_group(group_name)
            else:
                analysis_unit = analysis_units[follow_up_name]
                analysis_unit.add_group(group_name)

    def remove_group(self, group_name):
        for study in self.studies:
            for analysis_units_by_follow_up in study.analysis_units_by_outcome.values():
                for analysis_unit in analysis_units_by_follow_up.values():
                    analysis_unit.remove_group(group_name)

    def add_follow_up(self, follow_up_name):
        for outcome in self.get_outcome_names():
            self.add_follow_up_to_outcome(outcome, follow_up_name)

    def remove_follow_up(self, follow_up_name):
        for outcome in self.get_outcome_names():
            self.remove_follow_up_from_outcome(follow_up_name, outcome)

    def add_follow_up_to_outcome(self, outcome_name, follow_up_name):
        outcome = self.get_outcome_obj(outcome_name)
        current_group_names = self.get_group_names()
        if not current_group_names:
            current_group_names = None

        previous_index = max(self.follow_ups_by_outcome[outcome.name].keys())
        next_index = previous_index + 1

        self.follow_ups_by_outcome[outcome.name][next_index] = follow_up_name
        follow_up_id = _new_stable_id()
        self.follow_up_stable_ids_by_outcome.setdefault(outcome.name, {})[
            follow_up_name
        ] = follow_up_id
        self.follow_ups_by_outcome_id.setdefault(outcome.stable_id, {})[
            follow_up_id
        ] = FollowUp(follow_up_id, follow_up_name)

        for study in self.studies:
            study.add_follow_up_to_outcome(
                outcome,
                follow_up_name,
                group_names=current_group_names,
                follow_up_id=follow_up_id,
            )

    def remove_follow_up_from_outcome(self, follow_up_name, outcome_name):
        follow_up_index = self.follow_ups_by_outcome[outcome_name].get_key(
            follow_up_name
        )

        self.follow_ups_by_outcome[outcome_name].pop(follow_up_index)
        stable_id = self.follow_up_stable_ids_by_outcome.get(outcome_name, {}).pop(
            follow_up_name, None
        )
        outcome = self.get_outcome_obj(outcome_name)
        if outcome is not None and stable_id is not None:
            self.follow_ups_by_outcome_id.get(outcome.stable_id, {}).pop(stable_id, None)
        for study in self.studies:
            study.remove_follow_up_from_outcome(outcome_name, follow_up_name)

    def get_group_names(self):
        group_names = []
        for study in self.studies:
            for analysis_unit in study.analysis_units:
                group_names.extend(analysis_unit.get_group_names())
        return _unique_in_first_seen_order(group_names)

    def get_group_names_for_outcome_follow_up(self, outcome_name, follow_up):
        group_names = []
        for study in self.studies:
            try:
                analysis_unit = study.get_analysis_unit(outcome_name, follow_up)
            except KeyError:
                continue
            group_names.extend(analysis_unit.get_group_names())
        return _unique_in_first_seen_order(group_names)

    def change_follow_up_name(self, outcome, old_name, new_name):
        if new_name in self.get_follow_up_names_for_outcome(outcome):
            raise ValueError(f"follow-up {new_name!r} already exists for this outcome")
        for study in self.studies:
            study.analysis_units_by_outcome[outcome][new_name] = (
                study.analysis_units_by_outcome[outcome].pop(old_name)
            )
        follow_up_key = self.follow_ups_by_outcome[outcome].get_key(old_name)
        self.follow_ups_by_outcome[outcome][follow_up_key] = new_name
        stable_id = self.follow_up_stable_ids_by_outcome.get(outcome, {}).pop(
            old_name, _new_stable_id()
        )
        self.follow_up_stable_ids_by_outcome.setdefault(outcome, {})[new_name] = (
            stable_id
        )
        outcome_obj = self.get_outcome_obj(outcome)
        if outcome_obj is not None:
            follow_up = self.follow_ups_by_outcome_id.get(outcome_obj.stable_id, {}).get(stable_id)
            if follow_up is not None:
                follow_up.label = new_name
            for study in self.studies:
                for unit in study.analysis_units:
                    if unit.outcome is outcome_obj and getattr(unit, "follow_up_id", None) == stable_id:
                        unit.follow_up_label = new_name

    def get_follow_up_names(self):
        return _unique_in_first_seen_order(
            follow_up.label
            for follow_ups in self.follow_ups_by_outcome_id.values()
            for follow_up in follow_ups.values()
        )

    def get_study_names(self):
        return [study.name for study in self.studies]

    def get_follow_up_names_for_outcome(self, outcome):
        outcome_obj = self.get_outcome_obj(outcome)
        if outcome_obj is None:
            return []
        return [
            follow_up.label
            for follow_up in self.follow_ups_by_outcome_id[outcome_obj.stable_id].values()
        ]

    def get_follow_up_stable_id(self, outcome, follow_up):
        """Return identity independent of the editable follow-up label."""
        outcome_obj = self.get_outcome_obj(outcome)
        if outcome_obj is None:
            raise KeyError(outcome)
        for identity, candidate in self.follow_ups_by_outcome_id.setdefault(
            outcome_obj.stable_id, {}
        ).items():
            if candidate.label == follow_up:
                return identity
        identity = _new_stable_id()
        self.follow_ups_by_outcome_id[outcome_obj.stable_id][identity] = FollowUp(
            identity, follow_up
        )
        return identity

    def analysis_unit_has_edge_between_groups(self, analysis_unit, groups):
        comp_str = "-".join(groups)
        for effect in analysis_unit.get_effect_names():
            comp_str_present = comp_str in analysis_unit.get_group_strings(effect)
            try:
                estimate_is_present = (
                    analysis_unit.get_estimate(effect, comp_str) is not None
                )
            except KeyError:
                estimate_is_present = False
            if comp_str_present and estimate_is_present:
                return True

        for group in groups:
            if "" in analysis_unit.get_raw_data_for_group(group):
                return False
        return True

    def cmp_studies(
        self,
        compare_by="name",
        reverse=True,
        ordered_list=None,
        directions_to_analysis_unit=None,
        confidence_multiplier=None,
    ):
        """Compare studies in various ways -- pass the returned function
        to the (built-in) sort function.

        compare_by is either 'name', 'year' or 'ordered list'; if it's anything else,
        we assume it's a covariate and sort by that. ordered_list allows
        you to sort arbitrarily in the order specified by the list.
        """
        if directions_to_analysis_unit is not None:
            keys = [
                "outcome_name",
                "follow_up",
                "current_groups",
                "data_index",
                "current_effect",
                "group_comparison",
                "outcome_type",
            ]
            (
                outcome_name,
                follow_up,
                current_groups,
                data_index,
                current_effect,
                group_comparison,
                outcome_type,
            ) = [directions_to_analysis_unit.get(key) for key in keys]

        if compare_by == "name":
            return lambda study_a, study_b: self._meta_cmp_wrapper(
                study_a, study_b, study_a.name, study_b.name, reverse
            )
        elif compare_by == "year":
            return lambda study_a, study_b: self._meta_cmp_wrapper(
                study_a, study_b, study_a.year, study_b.year, reverse
            )
        elif compare_by == "raw_data":

            def compare_raw_data(study_a, study_b):
                analysis_unit_a = study_a.get_analysis_unit(outcome_name, follow_up)
                analysis_unit_b = study_b.get_analysis_unit(outcome_name, follow_up)
                raw_data_a = analysis_unit_a.get_raw_data_for_groups(current_groups)
                raw_data_b = analysis_unit_b.get_raw_data_for_groups(current_groups)
                study_a_val = raw_data_a[data_index]
                study_b_val = raw_data_b[data_index]
                return self._meta_cmp_wrapper(
                    study_a, study_b, study_a_val, study_b_val, reverse
                )

            return compare_raw_data
        elif compare_by == "outcomes":
            if confidence_multiplier is None:
                raise ValueError("confidence multiplier must be specified")
            from rc_metastudio import r_bridge

            def compare_outcomes(study_a, study_b):
                analysis_unit_a = study_a.get_analysis_unit(outcome_name, follow_up)
                analysis_unit_b = study_b.get_analysis_unit(outcome_name, follow_up)
                outcome_data_a = []
                outcome_data_b = []

                if outcome_type is BINARY:

                    def to_display_scale(x):
                        return r_bridge.binary_convert_scale(
                            x, current_effect, convert_to="display.scale"
                        )
                elif outcome_type is CONTINUOUS:

                    def to_display_scale(x):
                        return r_bridge.continuous_convert_scale(
                            x, current_effect, convert_to="display.scale"
                        )
                elif outcome_type is DIAGNOSTIC:

                    def to_display_scale(x):
                        return r_bridge.diagnostic_convert_scale(
                            x, current_effect, convert_to="display.scale"
                        )
                else:
                    raise ValueError(f"Unsupported outcome type: {outcome_type!r}")

                if outcome_type in (BINARY, CONTINUOUS):
                    outcome_data_a = analysis_unit_a.get_effect_and_ci(
                        current_effect, group_comparison, confidence_multiplier
                    )
                    outcome_data_b = analysis_unit_b.get_effect_and_ci(
                        current_effect, group_comparison, confidence_multiplier
                    )
                    outcome_data_a = [
                        to_display_scale(c_val) for c_val in outcome_data_a
                    ]
                    outcome_data_b = [
                        to_display_scale(c_val) for c_val in outcome_data_b
                    ]
                elif outcome_type == DIAGNOSTIC:
                    for diagnostic_metric in ("Sens", "Spec"):
                        estimate_and_ci_a = analysis_unit_a.get_effect_and_ci(
                            diagnostic_metric, group_comparison, confidence_multiplier
                        )
                        estimate_and_ci_b = analysis_unit_b.get_effect_and_ci(
                            diagnostic_metric, group_comparison, confidence_multiplier
                        )
                        estimate_and_ci_a = [
                            to_display_scale(c_val) for c_val in estimate_and_ci_a
                        ]
                        estimate_and_ci_b = [
                            to_display_scale(c_val) for c_val in estimate_and_ci_b
                        ]

                        outcome_data_a.extend(estimate_and_ci_a)
                        outcome_data_b.extend(estimate_and_ci_b)
                study_a_val = outcome_data_a[data_index]
                study_b_val = outcome_data_b[data_index]

                return self._meta_cmp_wrapper(
                    study_a, study_b, study_a_val, study_b_val, reverse
                )

            return compare_outcomes

        elif compare_by == "ordered_list":
            # Compare positions in the caller-provided order.
            if ordered_list is None:
                raise ValueError("ordered_list must be specified")
            return lambda study_a, study_b: self._meta_cmp_wrapper(
                study_a,
                study_b,
                ordered_list.index(study_a.name),
                ordered_list.index(study_b.name),
                reverse=False,
            )
        else:
            # then we assume that we're sorting by a covariate
            # always want missing values at the 'bottom'
            missing_val = float("-infinity") if reverse else float("infinity")

            def missing_to_zero(d, s):
                return d[s] if s in d else missing_val

            return lambda study_a, study_b: self._meta_cmp_wrapper(
                study_a,
                study_b,
                missing_to_zero(study_a.covariate_values, compare_by),
                missing_to_zero(study_b.covariate_values, compare_by),
                reverse,
            )

    def _both_empty(self, a, b):
        return a in EMPTY_VALS and b in EMPTY_VALS

    def _meta_cmp_wrapper(self, study_a, study_b, study_a_val, study_b_val, reverse):
        """This is a bit kludgey -- we wrap the cmp wrapper in cases where the study names are not
        being compared. This is to avoid comparisons of two empty values. For example, if we are
        sorting by a covariate, and it is empty in two studies, we want to then sort these studies by
        their names.
        """
        if self._both_empty(study_a_val, study_b_val):
            # both values being compared are empty; sort by study names
            return self._cmp_wrapper(study_a.name, study_b.name, reverse)
        else:
            # at least one has a value; proceed as usual.
            return self._cmp_wrapper(study_a_val, study_b_val, reverse)

    def _cmp_wrapper(self, study_a_val, study_b_val, reverse):
        """Wraps the default compare method to assert that "" (i.e., empty studies)
        are greater than non-empties
        """
        flip_sign = -1 if reverse else 1
        if study_a_val in EMPTY_VALS:
            return flip_sign * 1
        elif study_b_val in EMPTY_VALS:
            return flip_sign * -1
        else:
            return _cmp(study_a_val, study_b_val)


def _new_stable_id() -> str:
    return uuid.uuid4().hex


class FollowUp:
    """Editable follow-up label owned by one immutable identity."""

    def __init__(self, stable_id, label):
        self.stable_id = stable_id
        self.label = label

    @property
    def identity(self):
        return self.stable_id

    @property
    def name(self):
        return self.label

    @name.setter
    def name(self, value):
        self.label = value


class Study:
    """Store a study's metadata, covariates, and analysis units."""

    def __init__(self, id, name="", year=None, include=True, stable_id=None):
        self.id = id
        self.stable_id = stable_id or _new_stable_id()
        self.year = year
        self.name = name

        self.sample_size = None
        self.notes = ""
        self.analysis_units_by_outcome = {}
        self.analysis_units_by_id = {}
        self.analysis_units = []
        self.outcomes = []
        self.include = include
        self.covariate_values = {}
        self.covariate_values_by_id = {}
        self.manually_excluded = False

    def __str__(self):
        return self.name

    @property
    def identity(self):
        return self.stable_id

    def get_analysis_unit(
        self,
        outcome,
        follow_up,
    ):
        outcome_id = outcome.stable_id if isinstance(outcome, Outcome) else None
        for unit in self.analysis_units:
            if outcome_id is not None and unit.outcome.stable_id != outcome_id:
                continue
            if outcome_id is None and unit.outcome.name != outcome:
                continue
            if follow_up in {
                getattr(unit, "follow_up_id", None),
                getattr(unit, "follow_up_label", None),
            }:
                return unit
            # The mutable outcome owns no label map; the presentation index
            # remains the only place that translates an identity to a label.
            if follow_up == "first" and getattr(unit, "follow_up_id", None) is None:
                return unit
        try:
            return self.analysis_units_by_outcome[outcome][follow_up]
        except KeyError as exc:
            raise KeyError(
                f"No analysis unit exists for outcome {outcome!r} at {follow_up!r}"
            ) from exc

    def add_outcome(
        self, outcome, follow_up_name="first", group_names=None, follow_up_id=None
    ):
        if outcome.name in self.analysis_units_by_outcome:
            raise ValueError(f"study already contains outcome {outcome.name!r}")
        self.analysis_units_by_outcome[outcome.name] = {}
        unit = AnalysisUnit(
            outcome, group_names=group_names
        )
        unit.follow_up_id = follow_up_id
        unit.follow_up_label = follow_up_name
        self.analysis_units_by_outcome[outcome.name][follow_up_name] = unit
        self.analysis_units_by_id[unit.stable_id] = unit
        self.analysis_units.append(unit)
        self.outcomes.append(outcome)

    def remove_outcome(self, outcome_name):
        removed = self.analysis_units_by_outcome.pop(outcome_name)
        for unit in removed.values():
            self.analysis_units_by_id.pop(unit.stable_id, None)
            if unit in self.analysis_units:
                self.analysis_units.remove(unit)
        for outcome in self.outcomes:
            if outcome.name == outcome_name:
                self.outcomes.remove(outcome)

    def add_outcome_at_follow_up(self, outcome, follow_up, follow_up_id=None):
        unit = AnalysisUnit(outcome)
        unit.follow_up_id = follow_up_id
        unit.follow_up_label = follow_up
        self.analysis_units_by_outcome[outcome.name][follow_up] = unit
        self.analysis_units_by_id[unit.stable_id] = unit
        self.analysis_units.append(unit)

    def get_outcome(self, outcome_name):
        for outcome in self.outcomes:
            if outcome.name == outcome_name:
                return outcome
        return None

    def get_outcome_names(self):
        return [outcome.name for outcome in self.outcomes]

    def add_follow_up_to_outcome(
        self, outcome, follow_up_name, group_names=None, follow_up_id=None
    ):
        unit = AnalysisUnit(
            outcome, group_names=group_names
        )
        unit.follow_up_id = follow_up_id
        unit.follow_up_label = follow_up_name
        self.analysis_units_by_outcome[outcome.name][follow_up_name] = unit
        self.analysis_units_by_id[unit.stable_id] = unit
        self.analysis_units.append(unit)

    def replace_analysis_unit(self, outcome, follow_up, unit):
        """Update the label index and identity-owned unit reference together."""
        self.analysis_units_by_outcome[outcome][follow_up] = unit
        self.analysis_units_by_id[unit.stable_id] = unit
        for index, current in enumerate(self.analysis_units):
            if current.stable_id == unit.stable_id:
                self.analysis_units[index] = unit
                return
        self.analysis_units.append(unit)

    def remove_follow_up_from_outcome(self, outcome, follow_up_name):
        outcome_name = outcome
        if isinstance(outcome, Outcome):
            outcome_name = outcome.name

        unit = self.analysis_units_by_outcome[outcome_name].pop(follow_up_name)
        self.analysis_units_by_id.pop(unit.stable_id, None)
        if unit in self.analysis_units:
            self.analysis_units.remove(unit)


class Outcome:
    """Holds a few fields that define outcomes."""

    def __init__(self, name, data_type, links=None, sub_type=None, stable_id=None):
        self.name = name
        self.stable_id = stable_id or _new_stable_id()
        self.data_type = data_type
        self.links = links
        self.sub_type = sub_type

    @property
    def identity(self):
        return self.stable_id


class Covariate:
    """Meta-data about covariates."""

    def __init__(self, name, data_type, stable_id=None):
        if data_type not in ("factor", "continuous"):
            raise Exception(
                "covariates need to have associated type factor or continuous; %s was given"
                % data_type
            )
        self.name = name
        self.data_type = CONTINUOUS if data_type == "continuous" else FACTOR
        self.stable_id = stable_id or uuid.uuid4().hex

    def get_type_str(self):
        return {CONTINUOUS: "continuous", FACTOR: "factor"}[self.data_type]

    @property
    def identity(self):
        return self.stable_id

    def get_data_type(self):
        return self.data_type


class Link:
    pass
