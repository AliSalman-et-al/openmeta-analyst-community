# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass

from rc_metastudio.workspace_editing import WorkspaceEditingService
from rc_metastudio.workspace_editing import WorkspaceEditingContext, WorkspaceEditTarget
from rc_metastudio.analysis_dataset import Dataset, Study as DomainStudy
from rc_metastudio.meta_globals import BINARY


class FakeBridge:
    def get_confidence_multiplier_from_r(self, confidence_level):
        return 1.96

    def set_confidence_level(self, confidence_level):
        return None

    def effect_for_study(self, *args, **kwargs):
        return {"calc_scale": 0.5}

    def effect_triplet(self, value, scale, *, metric):
        return (value[scale], None, None)

    def binary_convert_scale(self, value, effect, *, convert_to, n1=None):
        return value

    continuous_convert_scale = binary_convert_scale
    diagnostic_convert_scale = binary_convert_scale
    continuous_effect_for_study = effect_for_study
    diagnostic_effects_for_study = effect_for_study


def test_raw_preview_is_available_without_qt():
    service = WorkspaceEditingService(FakeBridge())

    result, n1 = service.preview_raw_effects(
        BINARY, "OR", [5, 10, 4, 10], 95.0
    )

    assert result == (0.5, None, None)
    assert n1 == 10


@dataclass
class Study:
    include: bool = False
    manually_excluded: bool = False


def test_inclusion_policy_is_owned_by_the_qt_free_service():
    study = Study()

    WorkspaceEditingService.update_inclusion_after_edit(
        study,
        diagnostic=False,
        inclusion_column=False,
        outcome_selected=True,
        effect={"est": 0.8, "lower": 0.6, "upper": 1.1},
        data_type="binary",
        outcome_subtype=None,
    )

    assert study.include is True


def test_edit_service_validates_and_mutates_year_without_qt():
    dataset = Dataset()
    dataset.add_study(DomainStudy(1, name="Alpha"))
    context = WorkspaceEditingContext(
        outcome_name=None,
        follow_up_name=None,
        current_groups=(),
        current_effect=None,
        data_type=None,
        outcome_subtype=None,
        group_comparison="",
        raw_columns=(),
        outcome_columns=(),
        include_column=0,
        name_column=1,
        year_column=2,
        confidence_level=95.0,
        confidence_multiplier=1.96,
    )
    service = WorkspaceEditingService(FakeBridge())

    applied = service.apply_edit(
        dataset, WorkspaceEditTarget(0, 2, None), context, "2026"
    )
    rejected = service.apply_edit(
        dataset, WorkspaceEditTarget(0, 2, 2026), context, "not-a-year"
    )

    assert applied.applied is True
    assert dataset.studies[0].year == 2026
    assert rejected.error == "Years need to be integers."
