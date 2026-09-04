from rc_metastudio import analysis_dataset, meta_globals


def test_editable_labels_do_not_change_domain_identities():
    dataset = analysis_dataset.Dataset()
    outcome = analysis_dataset.Outcome("Outcome", meta_globals.CONTINUOUS)
    study = analysis_dataset.Study(0, "Study")
    dataset.add_study(study)
    dataset.add_outcome(outcome)
    dataset.add_follow_up_to_outcome("Outcome", "week 2")
    unit = study.get_analysis_unit("Outcome", "week 2")
    group_id = unit.groups["tx A"].stable_id
    outcome_id = outcome.stable_id
    study_id = study.stable_id
    follow_up_id = dataset.get_follow_up_stable_id("Outcome", "week 2")
    unit_id = unit.stable_id

    assert dataset.outcomes_by_id[outcome_id] is outcome
    assert dataset.follow_ups_by_outcome_id[outcome_id][follow_up_id].label == "week 2"
    assert study.analysis_units_by_id[unit_id] is unit
    assert unit.groups_by_id[group_id] is unit.groups["tx A"]

    dataset.change_outcome_name("Outcome", "Renamed outcome")
    dataset.change_follow_up_name("Renamed outcome", "week 2", "Renamed follow-up")
    dataset.change_group_name("tx A", "Renamed group")
    outcome = dataset.get_outcome_obj("Renamed outcome")

    assert outcome is not None and outcome.stable_id == outcome_id
    assert study.stable_id == study_id
    assert dataset.get_follow_up_stable_id("Renamed outcome", "Renamed follow-up") == (
        follow_up_id
    )
    assert study.get_analysis_unit("Renamed outcome", "Renamed follow-up").groups[
        "Renamed group"
    ].stable_id == group_id
    assert dataset.outcomes_by_id[outcome_id] is outcome
    assert dataset.follow_ups_by_outcome_id[outcome_id][follow_up_id].label == (
        "Renamed follow-up"
    )
    assert study.analysis_units_by_id[unit_id] is unit
    assert unit.groups_by_id[group_id] is unit.groups["Renamed group"]


def test_effect_authority_is_explicit_and_preview_is_not_entered_data():
    outcome = analysis_dataset.Outcome("Outcome", meta_globals.CONTINUOUS)
    unit = analysis_dataset.AnalysisUnit(outcome, group_names=["group 1"])
    unit.set_effect_for_source("entered", "TX Mean", "group 1", 1.0, 0.5, 1.5)
    unit.set_effect_for_source(
        "derived_preview", "TX Mean", "group 1", 2.0, 1.5, 2.5
    )

    assert unit.get_effect_for_source("entered", "TX Mean", "group 1").estimate == 1.0
    assert unit.get_effect_for_source(
        "derived_preview", "TX Mean", "group 1"
    ).estimate == 2.0
    assert unit.get_entered_effect_and_ci("TX Mean", "group 1") == (1.0, 0.5, 1.5)
