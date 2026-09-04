from dataclasses import dataclass

import pytest

from rc_metastudio.workspace_editing import WorkspaceEditingService
from rc_metastudio.meta_globals import BINARY


class FakeBridge:
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


def test_transaction_rolls_back_a_failed_dataset_mutation():
    @dataclass
    class Dataset:
        value: int = 1

    dataset = Dataset()
    service = WorkspaceEditingService(FakeBridge())

    with pytest.raises(RuntimeError, match="preview failed"):
        with service.transaction(dataset):
            dataset.value = 2
            raise RuntimeError("preview failed")

    assert dataset.value == 1
