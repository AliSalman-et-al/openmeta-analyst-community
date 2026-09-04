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


def test_group_rename_preserves_each_effect_authority_store():
    dataset = analysis_dataset.Dataset()
    dataset.add_study(analysis_dataset.Study(0, "Study"))
    dataset.add_outcome(analysis_dataset.Outcome("Outcome", meta_globals.BINARY))
    unit = dataset.studies[0].get_analysis_unit("Outcome", "first")
    left, right = unit.get_group_names()
    comparison = f"{left}-{right}"

    for source, estimate in (
        ("entered", 1.0),
        ("derived_preview", 2.0),
        ("analysis", 3.0),
    ):
        unit.set_effect_for_source(source, "OR", comparison, estimate, 0.5, 4.0)

    dataset.change_group_name(left, "renamed-arm")
    renamed_comparison = f"renamed-arm-{right}"

    assert all(
        unit.get_effect_for_source(source, "OR", renamed_comparison).estimate == estimate
        for source, estimate in (
            ("entered", 1.0),
            ("derived_preview", 2.0),
            ("analysis", 3.0),
        )
    )
    assert comparison not in unit.entered_effects["OR"]
    assert comparison not in unit.derived_effect_previews["OR"]
    assert comparison not in unit.analysis_effects["OR"]


def test_legacy_calculated_effects_are_published_as_previews():
    outcome = analysis_dataset.Outcome("Outcome", meta_globals.CONTINUOUS)
    unit = analysis_dataset.AnalysisUnit(outcome, group_names=["group 1"])

    unit.set_effect("TX Mean", "group 1", 1.0)
    unit.set_effect_and_ci("TX Mean", "group 1", 2.0, 1.5, 2.5, 1.96)

    assert unit.get_effect_for_source("entered", "TX Mean", "group 1").estimate == 1.0
    assert unit.get_effect_for_source(
        "derived_preview", "TX Mean", "group 1"
    ).estimate == 2.0
    assert unit.get_estimate_for_source("derived_preview", "TX Mean", "group 1") == 2.0


def test_entered_edit_does_not_hide_which_source_a_preview_belongs_to():
    outcome = analysis_dataset.Outcome("Outcome", meta_globals.CONTINUOUS)
    unit = analysis_dataset.AnalysisUnit(outcome, group_names=["group 1"])
    unit.set_effect_and_ci("TX Mean", "group 1", 2.0, 1.5, 2.5, 1.96)
    unit.set_effect("TX Mean", "group 1", 3.0)

    assert unit.get_effect_for_source("entered", "TX Mean", "group 1").estimate == 3.0
    assert unit.get_effect_for_source(
        "derived_preview", "TX Mean", "group 1"
    ).estimate == 2.0
