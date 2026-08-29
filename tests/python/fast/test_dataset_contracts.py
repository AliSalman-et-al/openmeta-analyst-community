# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from rc_metastudio import analysis_dataset


def _dataset(data_type=analysis_dataset.DIAGNOSTIC):
    dataset = analysis_dataset.Dataset(
        title="Contract dataset",
        is_diagnostic=data_type == analysis_dataset.DIAGNOSTIC,
        summary={"data_type": "diagnostic"},
    )
    dataset.notes = "dataset notes"
    dataset.add_study(analysis_dataset.Study(1, "Study 1", year=2026))
    dataset.add_outcome(analysis_dataset.Outcome("Outcome", data_type))
    dataset.add_covariate(
        analysis_dataset.Covariate("Region", "factor"), {"Study 1": "north"}
    )
    unit = dataset.studies[0].analysis_units_by_outcome["Outcome"]["first"]
    groups = unit.get_group_names()
    unit.groups[groups[0]].raw_data[0] = 3
    effect_group = (
        groups[0] if data_type == analysis_dataset.DIAGNOSTIC else "-".join(groups)
    )
    effect = "Sens" if data_type == analysis_dataset.DIAGNOSTIC else "OR"
    unit.effects[effect][effect_group]["est"] = 0.75
    return dataset


def test_copy_preserves_and_isolates_the_complete_dataset_graph():
    source = _dataset()
    cloned = source.copy()

    assert cloned is not source
    assert cloned.title == source.title
    assert cloned.is_diagnostic is source.is_diagnostic
    assert cloned.summary == source.summary
    assert cloned.notes == source.notes
    assert cloned.covariates[0].name == "Region"
    assert cloned.studies[0].name == "Study 1"

    cloned.summary["data_type"] = "changed"
    cloned.notes = "changed"
    cloned.covariates[0].name = "Changed region"
    cloned.studies[0].name = "Changed study"
    cloned_unit = cloned.studies[0].analysis_units_by_outcome["Outcome"]["first"]
    cloned_unit.groups[cloned_unit.get_group_names()[0]].raw_data[0] = 99
    cloned_unit.effects["Sens"][cloned_unit.get_group_names()[0]]["est"] = 0.2

    source_unit = source.studies[0].analysis_units_by_outcome["Outcome"]["first"]
    assert source.summary["data_type"] == "diagnostic"
    assert source.notes == "dataset notes"
    assert source.covariates[0].name == "Region"
    assert source.studies[0].name == "Study 1"
    assert source_unit.groups[source_unit.get_group_names()[0]].raw_data[0] == 3
    assert source_unit.effects["Sens"][source_unit.get_group_names()[0]]["est"] == 0.75


def test_group_deletion_is_a_no_op_for_empty_datasets():
    dataset = analysis_dataset.Dataset()

    dataset.remove_group("missing")

    assert dataset.studies == []
    assert dataset.get_group_names() == []


def test_rename_group_preserves_effects_when_the_name_contains_a_hyphen():
    dataset = _dataset(analysis_dataset.BINARY)
    unit = dataset.studies[0].analysis_units_by_outcome["Outcome"]["first"]
    original_groups = unit.get_group_names()
    dataset.change_group_name(original_groups[0], "Usual-care")
    pair_key = "-".join(("Usual-care", original_groups[1]))
    unit.effects["OR"][pair_key]["est"] = 0.75

    dataset.change_group_name("Usual-care", "Control")

    renamed_key = "-".join(("Control", original_groups[1]))
    assert unit.get_group_names() == [original_groups[1], "Control"]
    assert unit.groups["Control"].name == "Control"
    assert unit.effects["OR"][renamed_key]["est"] == 0.75
    assert pair_key not in unit.effects["OR"]
