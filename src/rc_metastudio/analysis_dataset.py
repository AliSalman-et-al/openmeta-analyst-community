# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""UI-independent dataset model for studies, outcomes, follow-ups, and groups."""

import copy
import uuid

from rc_metastudio import two_way_dict
from rc_metastudio import meta_globals

from rc_metastudio import r_backend

r_backend.install_r_backend()
from rc_metastudio import r_bridge

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

    def __init__(self, title=None, is_diag=False, summary=None):
        self.title = title
        self.summary = summary
        self.studies = []
        self.is_diag = is_diag
        self.num_outcomes = 0
        self.num_follow_ups = 0
        self.outcome_names_to_follow_ups = {}
        self.num_treatments = 0

        self.notes = ""

        # this will hold a list of covariate objects. each study will
        # have a dictionary with values for that study corresponding
        # to each of the covariate objects here.
        self.covariates = []

    def copy(self):
        return copy.deepcopy(self)

    def get_outcome_names(self):
        return sorted(self.outcome_names_to_follow_ups.keys())

    def change_group_name(
        self, old_group_name, new_group_name, outcome=None, follow_up=None
    ):
        if (outcome is None and follow_up is not None) or (
            follow_up is None and outcome is not None
        ):
            raise Exception(
                "dataset -- change_group_name -- either both outcome and follow_up should be None, \
                                            or else neither should."
            )

        for study in self.studies:
            if outcome is None and follow_up is None:
                # if no outcome/follow-up was specified, we change *all* occurrences of
                # the old_group_name to the new_group_name
                for outcome_name in list(study.outcomes_to_follow_ups.keys()):
                    cur_outcome = study.outcomes_to_follow_ups[outcome_name]
                    for analysis_unit in list(cur_outcome.values()):
                        analysis_unit.rename_group(old_group_name, new_group_name)
            else:
                analysis_unit = study.outcomes_to_follow_ups[outcome][follow_up]
                analysis_unit.rename_group(old_group_name, new_group_name)

    def change_outcome_name(self, old_outcome_name, new_outcome_name):
        self.outcome_names_to_follow_ups[new_outcome_name] = (
            self.outcome_names_to_follow_ups.pop(old_outcome_name)
        )
        for study in self.studies:
            study.outcomes_to_follow_ups[new_outcome_name] = (
                study.outcomes_to_follow_ups.pop(old_outcome_name)
            )
            for outcome in study.outcomes:
                if outcome.name == old_outcome_name:
                    outcome.name = new_outcome_name

    def delete_group(self, group_name):
        self._remove_group_data(group_name)

    def _remove_group_data(self, group_name):
        for study in self.studies:
            for outcome_name in list(study.outcomes_to_follow_ups.keys()):
                cur_outcome = study.outcomes_to_follow_ups[outcome_name]
                for analysis_unit in list(cur_outcome.values()):
                    analysis_unit.remove_group(group_name)

    def add_study(self, study, study_index=None):
        # Empty outcomes and follow-ups remain valid until analysis execution.
        if study_index is None:
            self.studies.append(study)
        else:
            self.studies.insert(study_index, study)

    def remove_study(self, studyid):
        self.studies = [study for study in self.studies if study.id != studyid]

    def num_studies(self):
        return len(self.studies)

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
        for study in self.studies:
            outcome_obj = study.get_outcome(outcome_name)
            if outcome_obj is not None:
                return outcome_obj
        return None

    def max_study_id(self):
        if len(self.studies) == 0:
            return -1
        return max([study.id for study in self.studies])

    def remove_covariate(self, covariate):
        cov_index = None  # keep record of the remvoed covariate's index.
        covariate_name = (
            covariate.name if isinstance(covariate, Covariate) else covariate
        )
        # first remove the covariate from the list of
        # covariate objects for this dataset
        for i, cov in enumerate(self.covariates):
            if cov.name == covariate_name:
                self.covariates.remove(cov)
                cov_index = i
                break
        # now remove the covariate from all of the studies
        # in the dataset
        for study in self.studies:
            if covariate_name in study.covariate_dict:
                study.covariate_dict.pop(covariate_name)
        return cov_index

    def add_covariate(self, covariate, cov_values=None, cov_index=None):
        """Adds the parametric covariate to: 1) the list of covariate objects
        associated with this dataset and 2) the covariate dictionaries of each
        of the studies this dataset contains. Note: the covariate argument
        needs to be a Covariate object (not a string)!
        """
        if cov_index is None:
            self.covariates.append(covariate)
        else:
            self.covariates.insert(cov_index, covariate)

        if cov_values is None:
            for study in self.studies:
                study.covariate_dict[covariate.name] = None
        else:
            # in this case, a dictionary mapping studies to
            # values for this covariate was passed in.
            # this will occur in this case, e.g., that a
            # covariate was removed from the dataset, but then
            # the user clicked 'redo' -- we want to repopulate
            # the dataset with the previous covariate values.
            for study in self.studies:
                if study.name in cov_values:
                    study.covariate_dict[covariate.name] = cov_values[study.name]
                else:
                    study.covariate_dict[covariate.name] = None

    def change_covariate_name(self, old_covariate, new_covariate_name):
        # get the values for this covariate for all studies
        cov_val_dict = copy.deepcopy(self.get_values_for_cov(old_covariate.name))
        stable_id = getattr(old_covariate, "stable_id", None)
        cov_index = self.remove_covariate(old_covariate)
        # Preserve both the values and the original column position.
        self.add_covariate(
            Covariate(
                new_covariate_name,
                TYPE_TO_STR_DICT[old_covariate.data_type],
                stable_id=stable_id,
            ),
            cov_values=cov_val_dict,
            cov_index=cov_index,
        )

    def get_cov_obj_from_name(self, cov_name):
        for cov in self.covariates:
            if cov.name == cov_name:
                return cov

    def get_values_for_cov(self, covariate, ids_for_keys=False):
        """Returns a dictionary mapping study names to values for
        the given covariate -- BEWARE these (study names) aren't
        necessarily unique! safer to set the ids_for_keys flag.
        """
        cov_name = covariate
        if isinstance(covariate, Covariate):
            cov_name = covariate.name
        cov_d = {}
        for study in self.studies:
            if (
                cov_name in study.covariate_dict
                and study.covariate_dict[cov_name] is not None
            ):
                if ids_for_keys:
                    cov_d[study.id] = study.covariate_dict[cov_name]
                else:
                    cov_d[study.name] = study.covariate_dict[cov_name]
        return cov_d

    def get_cov_names(self):
        return [cov.name for cov in self.covariates]

    def add_outcome(self, outcome):
        cur_group_names = self.get_group_names()
        if len(cur_group_names) == 0:
            cur_group_names = None

        follow_up = "first"
        self.outcome_names_to_follow_ups[outcome.name] = two_way_dict.TwoWayDict()
        self.outcome_names_to_follow_ups[outcome.name][0] = follow_up

        for study in self.studies:
            study.add_outcome(outcome, follow_up, group_names=cur_group_names)

    def remove_outcome(self, outcome_name):
        if outcome_name is None:
            return
        self.outcome_names_to_follow_ups.pop(outcome_name)
        for study in self.studies:
            study.remove_outcome(outcome_name)

    def add_group(self, group_name, outcome_name, follow_up_name=None):
        # A note on adding new groups: per consultation with the wise sir
        # Thomas Trikalinos, a decision has been made that when a
        # group is added to an outcome, it is added by default to all
        # the follow ups belonging to said outcome. It is not, however
        # added to all the *outcomes*.
        #
        # However, if the follow_up_name argument is not None, the
        # group will only be added to the specified follow up.
        outcome = self.get_outcome_obj(outcome_name)
        group_names = self.get_group_names()
        if len(group_names) == 0:
            group_names = None
        for study in self.studies:
            if outcome_name not in study.outcomes_to_follow_ups:
                study.add_outcome(outcome, group_names=group_names)
                for follow_up in list(
                    self.outcome_names_to_follow_ups[outcome_name].values()
                ):
                    if follow_up not in study.outcomes_to_follow_ups[outcome_name]:
                        study.add_outcome_at_follow_up(outcome, follow_up)
            cur_outcome = study.outcomes_to_follow_ups[outcome_name]
            if follow_up_name is None:
                for analysis_unit in list(cur_outcome.values()):
                    analysis_unit.add_group(group_name)
            else:
                analysis_unit = cur_outcome[follow_up_name]
                analysis_unit.add_group(group_name)

    def remove_group(self, group_name):
        self._remove_group_data(group_name)

    def add_follow_up(self, follow_up_name):
        """Adds the follow-up to *all* outcomes"""
        for outcome in self.get_outcome_names():
            self.add_follow_up_to_outcome(outcome, follow_up_name)

    def remove_follow_up(self, follow_up_name):
        """Removes the follow-up from *all* outcomes"""
        for outcome in self.get_outcome_names():
            self.remove_follow_up_from_outcome(follow_up_name, outcome)

    def add_follow_up_to_outcome(self, outcome_name, follow_up_name):
        outcome = self.get_outcome_obj(outcome_name)
        cur_group_names = self.get_group_names()
        if len(cur_group_names) == 0:
            cur_group_names = None

        prev_index = max(self.outcome_names_to_follow_ups[outcome.name].keys())
        next_index = prev_index + 1

        self.outcome_names_to_follow_ups[outcome.name][next_index] = follow_up_name

        for study in self.studies:
            study.add_follow_up_to_outcome(
                outcome, follow_up_name, group_names=cur_group_names
            )

    def remove_follow_up_from_outcome(self, follow_up_name, outcome_name):
        time_point = self.outcome_names_to_follow_ups[outcome_name].get_key(
            follow_up_name
        )

        self.outcome_names_to_follow_ups[outcome_name].pop(time_point)
        for study in self.studies:
            study.remove_follow_up_from_outcome(outcome_name, follow_up_name)

    def get_group_names(self):
        group_names = []
        for study in self.studies:
            for outcome_name in list(study.outcomes_to_follow_ups.keys()):
                cur_outcome = study.outcomes_to_follow_ups[outcome_name]
                for analysis_unit in list(cur_outcome.values()):
                    group_names.extend(analysis_unit.get_group_names())
        return _unique_in_first_seen_order(group_names)

    def get_group_names_for_outcome_fu(self, outcome_name, follow_up):
        group_names = []
        for study in self.studies:
            if outcome_name in study.outcomes_to_follow_ups:
                if follow_up in study.outcomes_to_follow_ups[outcome_name]:
                    cur_analysis_unit = study.outcomes_to_follow_ups[outcome_name][
                        follow_up
                    ]
                    group_names.extend(cur_analysis_unit.get_group_names())
        return _unique_in_first_seen_order(group_names)

    def change_follow_up_name(self, outcome, old_name, new_name):
        # make sure that the follow up doesn't already exist
        if new_name in self.get_follow_up_names_for_outcome(outcome):
            raise Exception("follow up name %s alerady exists for outcome!" % new_name)
        for study in self.studies:
            study.outcomes_to_follow_ups[outcome][new_name] = (
                study.outcomes_to_follow_ups[outcome].pop(old_name)
            )
        # also update the outcomes -> follow-ups dictionary
        follow_up_key = self.outcome_names_to_follow_ups[outcome].get_key(old_name)
        self.outcome_names_to_follow_ups[outcome][follow_up_key] = new_name

    def get_follow_up_names(self):
        """Returns *all* known follow-up names"""
        follow_up_names = []
        for outcome_d in list(self.outcome_names_to_follow_ups.values()):
            follow_up_names.extend(list(outcome_d.values()))
        return _unique_in_first_seen_order(follow_up_names)

    def get_study_names(self):
        return [study.name for study in self.studies]

    def get_follow_up_names_for_outcome(self, outcome):
        return list(self.outcome_names_to_follow_ups[outcome].values())

    def get_network(self, outcome, time_point):
        node_list = []  # list of all nodes
        adjacency_list = []  # list of edges
        for study in self.studies:
            analysis_unit = study.outcomes_to_follow_ups[outcome][time_point]
            group_names = analysis_unit.get_group_names()
            for g1 in group_names:
                node_list.append(g1)
                for g2 in [group for group in group_names if group != g1]:
                    if (
                        self.analysis_unit_has_edge_between_groups(
                            analysis_unit, [g1, g2]
                        )
                        and (g1, g2) not in adjacency_list
                        and (g2, g1) not in adjacency_list
                    ):
                        adjacency_list.append((g1, g2))

        return (_unique_in_first_seen_order(node_list), adjacency_list)

    def analysis_unit_has_edge_between_groups(self, analysis_unit, groups):
        # first check the effects. if *any* effect contains data
        # comparing these two groups, we return true.
        comp_str = "-".join(groups)
        for effect in analysis_unit.get_effect_names():
            comp_str_present = comp_str in analysis_unit.get_group_strings(effect)
            # fix for issue where for some reason we were trying to get
            try:
                estimate_is_present = (
                    analysis_unit.get_estimate(effect, comp_str) is not None
                )
            except KeyError:
                estimate_is_present = False
            if comp_str_present and estimate_is_present:
                return True

        # now check if they all have raw data
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
        mult=None,
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
                "group_str",
                "outcome_type",
            ]
            (
                outcome_name,
                follow_up,
                current_groups,
                data_index,
                current_effect,
                group_str,
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
            if mult is None:
                raise ValueError("mult must be specified")

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
                        current_effect, group_str, mult
                    )
                    outcome_data_b = analysis_unit_b.get_effect_and_ci(
                        current_effect, group_str, mult
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
                            diagnostic_metric, group_str, mult
                        )
                        estimate_and_ci_b = analysis_unit_b.get_effect_and_ci(
                            diagnostic_metric, group_str, mult
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
                missing_to_zero(study_a.covariate_dict, compare_by),
                missing_to_zero(study_b.covariate_dict, compare_by),
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


class Study:
    """Store a study's metadata, covariates, and analysis units."""

    def __init__(self, id, name="", year=None, include=True):
        # Auto-added studies start with the caller's include flag; callers should
        # exclude placeholder rows until sufficient data exists.
        self.id = id
        self.year = year
        self.name = name

        self.N = None
        self.notes = ""
        # this dictionary maps outcome names to dictionaries
        # which in turn map follow up ids to MetaAnalysisUnit
        # objects.
        self.outcomes_to_follow_ups = {}
        # also maintain a list of the known outcome objects
        self.outcomes = []
        # whether or not this study will be included in any
        # conducted analyses
        self.include = include
        # an empty dictionary that will map covariate names
        # to their values for *this* study.
        self.covariate_dict = {}
        self.manually_excluded = False

    def __str__(self):
        return self.name

    def get_analysis_unit(
        self,
        outcome,
        follow_up,
    ):
        try:
            return self.outcomes_to_follow_ups[outcome][follow_up]
        except KeyError as exc:
            raise KeyError(
                f"No analysis unit exists for outcome {outcome!r} at {follow_up!r}"
            ) from exc

    def add_outcome(self, outcome, follow_up_name="first", group_names=None):
        """Adds a new, blank outcome (i.e., no raw data)"""
        if outcome.name in list(self.outcomes_to_follow_ups.keys()):
            raise Exception("Study already contains an outcome named %s" % outcome.name)
        self.outcomes_to_follow_ups[outcome.name] = {}
        self.outcomes_to_follow_ups[outcome.name][follow_up_name] = MetaAnalysisUnit(
            outcome, group_names=group_names
        )
        self.outcomes.append(outcome)

    def remove_outcome(self, outcome_name):
        self.outcomes_to_follow_ups.pop(outcome_name)
        for outcome in self.outcomes:
            if outcome.name == outcome_name:
                self.outcomes.remove(outcome)

    def add_outcome_at_follow_up(self, outcome, follow_up):
        self.outcomes_to_follow_ups[outcome.name][follow_up] = MetaAnalysisUnit(outcome)

    def get_outcome(self, outcome_name):
        for outcome in self.outcomes:
            if outcome.name == outcome_name:
                return outcome
        return None

    def get_outcome_names(self):
        return [outcome.name for outcome in self.outcomes]

    def add_follow_up_to_outcome(self, outcome, follow_up_name, group_names=None):
        self.outcomes_to_follow_ups[outcome.name][follow_up_name] = MetaAnalysisUnit(
            outcome, group_names=group_names
        )

    def remove_follow_up_from_outcome(self, outcome, follow_up_name):
        outcome_name = outcome
        if isinstance(outcome, Outcome):
            outcome_name = outcome.name

        self.outcomes_to_follow_ups[outcome_name].pop(follow_up_name)


class MetaAnalysisUnit:
    """Store one outcome at one follow-up, potentially across several groups."""

    def __init__(self, outcome, raw_data=None, group_names=None):
        """Instantiate a new MetaAnalysisUnit, which is specific to a
        given study/outcome pair.

        @params:
        ===
        outcome -- Outcome object, this tells us what sort of data type
                            we have
        raw_data -- If provided, it is assumed to be a nested list, where
                    the first sublist is the raw data (num_events, num_total)
                    for the treated group and the second corresponds to the
                    control group (if applicable)
        """
        # diagnostic outcome?
        self.is_diag = outcome.data_type == DIAGNOSTIC
        self.outcome = outcome

        if group_names is None and not self.is_diag:
            group_names = meta_globals.DEFAULT_GROUP_NAMES
        elif group_names is None:
            group_names = ["test 1"]

        # TreatmentGroup ids to effect scalars.
        self.tx_groups = {}

        self.raw_data_length = 0
        if outcome.data_type == BINARY:
            self.raw_data_length = 2
        elif outcome.data_type == CONTINUOUS:
            self.raw_data_length = 3
        elif outcome.data_type == DIAGNOSTIC:
            self.raw_data_length = 4
        else:
            raise Exception(
                "Unrecognized outcome data type, '%s' was given" % outcome.data_type
            )

        # Makes list of (empty lists of length of raw_data):
        raw_data = raw_data or [
            ["" for n in range(self.raw_data_length)] for group in group_names
        ]

        self.effects_dict = {}

        # now we initialize the outcome dictionaries.
        if self.outcome.data_type == BINARY:
            for effect in (
                meta_globals.BINARY_TWO_ARM_METRICS
                + meta_globals.BINARY_ONE_ARM_METRICS
            ):
                self.effects_dict[effect] = {}
        elif self.outcome.data_type == CONTINUOUS:
            # Continuous display effects are limited to the implemented mean
            # difference and standardized mean difference metrics.
            for effect in (
                meta_globals.CONTINUOUS_TWO_ARM_METRICS
                + meta_globals.CONTINUOUS_ONE_ARM_METRICS
            ):
                self.effects_dict[effect] = {}
        elif self.outcome.data_type == DIAGNOSTIC:
            for effect in meta_globals.DIAGNOSTIC_METRICS:
                self.effects_dict[effect] = {}

        # Raw data belongs to groups, including the default treatment and control.
        for i, group in enumerate(group_names):
            self.add_group(group)
            self.tx_groups[group].raw_data = raw_data[i]

    def get_init_effect_d(self):
        # these are the dictionaries that actually hold the effects (estimate,
        # CI, etc.). note: *always* copy this dictionary, never use it directly.
        return {
            "est": None,
            "lower": None,
            "upper": None,
            "SE": None,
            "display_est": None,
            "display_lower": None,
            "display_upper": None,
        }

    def update_effects_dict_with_group(self, new_group):
        """When a new group is added, the effects dictionary will not contain
        entries for it. Thus this method must be called to update the dictionary
        with keys corresponding to this group (for one-arm metrics) and
        keys corresponding to pairwise combinations of this with other groups.
        """
        group_names = list(self.tx_groups.keys())  # existing groups
        if self.outcome.data_type == BINARY:
            # we assume that an entry for each effect already exists!
            for effect in meta_globals.BINARY_TWO_ARM_METRICS:
                for group in group_names:
                    # A directly entered effect belongs to an ordered group pair.
                    # We take care of this by mapping strings `txA-txB` to effect dictionaries
                    groups_str = "-".join((new_group, group))
                    self.effects_dict[effect][groups_str] = self.get_init_effect_d()
                    # ... and the reverse (see above comment)
                    groups_str = "-".join((group, new_group))
                    self.effects_dict[effect][groups_str] = self.get_init_effect_d()
            for effect in meta_globals.BINARY_ONE_ARM_METRICS:
                self.effects_dict[effect][new_group] = self.get_init_effect_d()
        elif self.outcome.data_type == CONTINUOUS:
            for effect in meta_globals.CONTINUOUS_TWO_ARM_METRICS:
                for group in group_names:
                    groups_str = "-".join((new_group, group))
                    self.effects_dict[effect][groups_str] = self.get_init_effect_d()
                    # and the reverse
                    groups_str = "-".join((group, new_group))
                    self.effects_dict[effect][groups_str] = self.get_init_effect_d()
            for effect in meta_globals.CONTINUOUS_ONE_ARM_METRICS:
                self.effects_dict[effect][new_group] = self.get_init_effect_d()
        elif self.outcome.data_type == DIAGNOSTIC:
            # diagnostic data
            for effect in meta_globals.DIAGNOSTIC_METRICS:
                self.effects_dict[effect][new_group] = self.get_init_effect_d()

    def calculate_se_if_possible(
        self, effect, group_str, est=None, lower=None, upper=None, mult=None
    ):
        if mult is None:
            raise ValueError("Mult must be specified")

        # get SE
        if est is None:
            est = self.effects_dict[effect][group_str]["est"]
        if lower is None:
            lower = self.effects_dict[effect][group_str]["lower"]
        if upper is None:
            upper = self.effects_dict[effect][group_str]["upper"]

        if upper is not None and est is not None:
            return (upper - est) / mult
        if est is not None and lower is not None:
            return (est - lower) / mult
        if upper is not None and lower is not None:
            return (upper - lower) / (2 * mult)
        return None

    def set_effect(self, effect, group_str, value):
        self.effects_dict[effect][group_str]["est"] = value

    def set_lower(self, effect, group_str, lower):
        self.effects_dict[effect][group_str]["lower"] = lower

    def set_upper(self, effect, group_str, upper):
        self.effects_dict[effect][group_str]["upper"] = upper

    def set_standard_error(self, effect, group_str, se):
        self.effects_dict[effect][group_str]["SE"] = se

    def set_display_effect(self, effect, group_str, value):
        self.effects_dict[effect][group_str]["display_est"] = value

    def set_display_lower(self, effect, group_str, lower):
        self.effects_dict[effect][group_str]["display_lower"] = lower

    def set_display_upper(self, effect, group_str, upper):
        self.effects_dict[effect][group_str]["display_upper"] = upper

    # Should this exist?
    def set_display_se(self, effect, group_str, se):
        self.effects_dict[effect][group_str]["display_se"] = se

    def calculate_display_effect_and_ci(
        self,
        effect,
        group_str,
        convert_to_display_scale,
        conf_level=None,
        mult=None,
        check_if_necessary=False,
        n1=None,
    ):
        if None in [conf_level, mult]:
            raise ValueError("confidence level & mult must be specified")

        if check_if_necessary and not self._should_calculate_display_effect_and_ci_and_se(
            effect, group_str, conf_level
        ):
            return

        if convert_to_display_scale is None:
            raise ValueError("Display-scale conversion is unavailable")

        est, lower, upper = self.get_effect_and_ci(effect, group_str, mult)
        d_est, d_lower, d_upper = [
            convert_to_display_scale(x) for x in [est, lower, upper]
        ]
        se = self.get_se(effect, group_str, mult)
        d_se = se

        self.set_display_effect(effect, group_str, d_est)
        self.set_display_lower(effect, group_str, d_lower)
        self.set_display_upper(effect, group_str, d_upper)
        self.set_display_se(effect, group_str, d_se)
        self.effects_dict[effect][group_str]["display_conf_level"] = conf_level

    def get_display_effect(self, effect, group_str):
        return self.effects_dict[effect][group_str].get("display_est")

    def get_display_lower(self, effect, group_str):
        if "display_lower" in self.effects_dict[effect][group_str]:
            return self.effects_dict[effect][group_str]["display_lower"]
        else:
            return None

    def get_display_upper(self, effect, group_str):
        if "display_upper" in self.effects_dict[effect][group_str]:
            return self.effects_dict[effect][group_str]["display_upper"]
        else:
            return None

    def get_display_se(self, effect, group_str):
        if "display_se" in self.effects_dict[effect][group_str]:
            return self.effects_dict[effect][group_str]["display_se"]
        else:
            return None

    def get_display_effect_and_ci(
        self, effect, group_str, convert_to_display_scale=None
    ):
        return (
            self.get_display_effect(effect, group_str),
            self.get_display_lower(effect, group_str),
            self.get_display_upper(effect, group_str),
        )

    def get_display_effect_and_se(
        self, effect, group_str, convert_to_display_scale=None
    ):
        return (
            self.get_display_effect(effect, group_str),
            self.get_display_se(effect, group_str),
        )

    def _should_calculate_display_effect_and_ci_and_se(
        self, effect, group_str, conf_level=None
    ):
        if conf_level is None:
            raise ValueError("Confidence level must be specified")

        existing_display_conf_level = "display_conf_level" in list(
            self.effects_dict[effect][group_str].keys()
        )
        if existing_display_conf_level:
            display_cl = self.effects_dict[effect][group_str][
                "display_conf_level"
            ]  # conf level @ which display values were computed
            disp_cl_eq_global_cl = meta_globals.equal_close_enough(
                display_cl, conf_level
            )
            if disp_cl_eq_global_cl:
                result = False  # we are ok, don't have to do anything special
            else:
                result = True
        else:
            result = True
        return result

    def get_estimate(self, effect, group_str):
        if "est" in self.effects_dict[effect][group_str]:
            return self.effects_dict[effect][group_str]["est"]
        else:
            return None

    def get_lower(self, effect, group_str, mult):
        return self._helper_get_upper_lower("lower", effect, group_str, mult)

    def get_upper(self, effect, group_str, mult):
        return self._helper_get_upper_lower("upper", effect, group_str, mult)

    def _helper_get_upper_lower(self, boundary, effect, group_str, mult=None):
        if mult is None:
            raise ValueError("Mult must be specified")

        if boundary not in ["upper", "lower"]:
            raise Exception("Boundary must be one of 'upper' or 'lower'")

        if self.get_se(effect, group_str, mult) is None:
            return self.effects_dict[effect][group_str][boundary]
        est = self.get_estimate(effect, group_str)
        se = self.get_se(effect, group_str, mult)
        if est is None or se is None:
            return None
        if boundary == "lower":
            return est - mult * se
        elif boundary == "upper":
            return est + mult * se
        else:
            raise Exception("BOUNDARY NOT RECOGNIZED")

    def get_se(self, effect, group_str, mult):
        if "SE" in self.effects_dict[effect][group_str]:
            se = self.effects_dict[effect][group_str]["SE"]
            if se is None:
                new_se = self.calculate_se_if_possible(effect, group_str, mult=mult)
                return new_se
            return se
        else:
            return self.calculate_se_if_possible(effect, group_str, mult=mult)

    def set_effect_and_ci(self, effect, group_str, est, lower, upper, mult):
        """Also calculated se if possible"""
        self.set_effect(effect, group_str, est)
        self.effects_dict[effect][group_str]["lower"] = lower
        self.effects_dict[effect][group_str]["upper"] = upper

        se = self.calculate_se_if_possible(
            effect, group_str, est, lower, upper, mult=mult
        )
        self.set_standard_error(effect, group_str, se)

    def get_effect_and_ci(self, effect, group_str, mult):
        return (
            self.get_estimate(effect, group_str),
            self.get_lower(effect, group_str, mult),
            self.get_upper(effect, group_str, mult),
        )

    def get_effect_and_se(self, effect, group_str, mult):
        return (
            self.get_estimate(effect, group_str),
            self.get_se(effect, group_str, mult),
        )

    def get_entered_effect_and_ci(self, effect, group_str):
        return (
            self.effects_dict[effect][group_str]["est"],
            self.effects_dict[effect][group_str]["lower"],
            self.effects_dict[effect][group_str]["upper"],
        )

    def get_group_strings(self, effect):
        return list(self.effects_dict[effect].keys())

    def get_effects_dict(self):
        """Be careful with using this because this returns the actual effects
        dict, not a copy
        """
        return self.effects_dict

    def get_effect_names(self):
        return list(self.effects_dict.keys())

    def type(self):
        return self.outcome.data_type

    def add_group(self, name, raw_data=None):
        if len(list(self.tx_groups.keys())) == 0:
            grp_id = 0
        else:
            grp_id = max([group.id for group in list(self.tx_groups.values())]) + 1
        if raw_data is None:
            raw_data = ["" for x in range(self.raw_data_length)]
        # Here we add this group to the set of group keys --
        # see inline documentation in this method for details
        self.update_effects_dict_with_group(name)
        self.tx_groups[name] = TreatmentGroup(grp_id, name, raw_data)

    def remove_group(self, name):
        self.tx_groups.pop(name)

    def rename_group(self, old_name, new_name):
        if old_name == new_name:
            return

        original_group_names = list(self.tx_groups)
        group = self.tx_groups.pop(old_name)
        group.name = new_name
        self.tx_groups[new_name] = group

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

        for effect_values in self.effects_dict.values():
            for old_key, new_key in key_replacements.items():
                if old_key in effect_values:
                    effect_values[new_key] = effect_values.pop(old_key)

    def get_raw_data_for_group(self, group_name):
        return self.tx_groups[group_name].raw_data

    def set_raw_data_for_group(self, group_name, raw_data):
        self.tx_groups[group_name].raw_data = raw_data

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
        return list(self.tx_groups.keys())


class TreatmentGroup:
    def __init__(self, id, name, raw_data):
        self.id = id
        self.name = name
        self.raw_data = raw_data


class Outcome:
    """Holds a few fields that define outcomes."""

    def __init__(self, name, data_type, links=None, sub_type=None):
        self.name = name
        self.data_type = data_type
        self.links = links
        self.sub_type = sub_type


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

    def get_data_type(self):
        return self.data_type


class Link:
    pass
