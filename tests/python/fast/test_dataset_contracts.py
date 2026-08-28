import copy
import os
import sys


sys.path.insert(0, os.path.abspath("src/rc_metastudio"))

import ma_dataset


def _dataset(data_type=ma_dataset.DIAGNOSTIC):
    dataset = ma_dataset.Dataset(
        title="Contract dataset",
        is_diag=data_type == ma_dataset.DIAGNOSTIC,
        summary={"data_type": "diagnostic"},
    )
    dataset.notes = "dataset notes"
    dataset.num_outcomes = 1
    dataset.num_follow_ups = 1
    dataset.num_treatments = 1
    dataset.add_study(ma_dataset.Study(1, "Study 1", year=2026))
    dataset.add_outcome(ma_dataset.Outcome("Outcome", data_type))
    dataset.add_covariate(
        ma_dataset.Covariate("Region", "factor"), {"Study 1": "north"}
    )
    unit = dataset.studies[0].outcomes_to_follow_ups["Outcome"]["first"]
    groups = unit.get_group_names()
    unit.tx_groups[groups[0]].raw_data[0] = 3
    effect_group = groups[0] if data_type == ma_dataset.DIAGNOSTIC else "-".join(groups)
    effect = "Sens" if data_type == ma_dataset.DIAGNOSTIC else "OR"
    unit.effects_dict[effect][effect_group]["est"] = 0.75
    return dataset


def test_copy_preserves_and_isolates_the_complete_dataset_graph():
    source = _dataset()
    cloned = source.copy()

    assert cloned is not source
    assert cloned.title == source.title
    assert cloned.is_diag is source.is_diag
    assert cloned.summary == source.summary
    assert cloned.notes == source.notes
    assert cloned.num_outcomes == source.num_outcomes
    assert cloned.num_follow_ups == source.num_follow_ups
    assert cloned.num_treatments == source.num_treatments
    assert cloned.covariates[0].name == "Region"
    assert cloned.studies[0].name == "Study 1"

    cloned.summary["data_type"] = "changed"
    cloned.notes = "changed"
    cloned.covariates[0].name = "Changed region"
    cloned.studies[0].name = "Changed study"
    cloned_unit = cloned.studies[0].outcomes_to_follow_ups["Outcome"]["first"]
    cloned_unit.tx_groups[cloned_unit.get_group_names()[0]].raw_data[0] = 99
    cloned_unit.effects_dict["Sens"][cloned_unit.get_group_names()[0]]["est"] = 0.2

    source_unit = source.studies[0].outcomes_to_follow_ups["Outcome"]["first"]
    assert source.summary["data_type"] == "diagnostic"
    assert source.notes == "dataset notes"
    assert source.covariates[0].name == "Region"
    assert source.studies[0].name == "Study 1"
    assert source_unit.tx_groups[source_unit.get_group_names()[0]].raw_data[0] == 3
    assert (
        source_unit.effects_dict["Sens"][source_unit.get_group_names()[0]]["est"]
        == 0.75
    )


def test_group_deletion_is_a_no_op_for_empty_datasets():
    dataset = ma_dataset.Dataset()

    dataset.delete_group("missing")
    dataset.remove_group("missing")

    assert dataset.studies == []
    assert dataset.get_group_names() == []


def test_delete_group_and_remove_group_have_equivalent_mutations():
    deleted = _dataset(ma_dataset.BINARY)
    removed = copy.deepcopy(deleted)
    group = deleted.get_group_names()[0]

    deleted.delete_group(group)
    removed.remove_group(group)

    for left_study, right_study in zip(deleted.studies, removed.studies):
        left_unit = left_study.outcomes_to_follow_ups["Outcome"]["first"]
        right_unit = right_study.outcomes_to_follow_ups["Outcome"]["first"]
        assert left_unit.get_group_names() == right_unit.get_group_names()
        assert left_unit.get_effects_dict() == right_unit.get_effects_dict()


def test_rename_group_preserves_effects_when_the_name_contains_a_hyphen():
    dataset = _dataset(ma_dataset.BINARY)
    unit = dataset.studies[0].outcomes_to_follow_ups["Outcome"]["first"]
    original_groups = unit.get_group_names()
    dataset.change_group_name(original_groups[0], "Usual-care")
    pair_key = "-".join(("Usual-care", original_groups[1]))
    unit.effects_dict["OR"][pair_key]["est"] = 0.75

    dataset.change_group_name("Usual-care", "Control")

    renamed_key = "-".join(("Control", original_groups[1]))
    assert unit.get_group_names() == [original_groups[1], "Control"]
    assert unit.tx_groups["Control"].name == "Control"
    assert unit.effects_dict["OR"][renamed_key]["est"] == 0.75
    assert pair_key not in unit.effects_dict["OR"]
