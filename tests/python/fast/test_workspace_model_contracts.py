"""Native PyQt6 contracts for the workspace's supporting list models."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QModelIndex, Qt

from rc_metastudio import edit_list_models


class WorkspaceDataset:
    def __init__(self):
        self.groups = ["Control"]
        self.outcomes = ["Mortality"]
        self.follow_ups = ["6 months"]
        self.studies = [SimpleNamespace(name="Alpha")]
        self.covariates = [SimpleNamespace(name="Age")]

    def get_group_names_for_outcome_follow_up(self, _outcome, _follow_up):
        return list(self.groups)

    def get_group_names(self):
        return list(self.groups)

    def change_group_name(self, old, new):
        self.groups[self.groups.index(old)] = new

    def get_outcome_names(self):
        return list(self.outcomes)

    def change_outcome_name(self, old, new):
        self.outcomes[self.outcomes.index(old)] = new

    def get_follow_up_names_for_outcome(self, _outcome):
        return list(self.follow_ups)

    def change_follow_up_name(self, _outcome, old, new):
        self.follow_ups[self.follow_ups.index(old)] = new

    def get_covariate_names(self):
        return [covariate.name for covariate in self.covariates]

    def change_covariate_name(self, covariate, new):
        covariate.name = new


def _models(dataset):
    return (
        edit_list_models.TXGroupsModel(
            dataset=dataset, outcome="Mortality", follow_up="6 months"
        ),
        edit_list_models.OutcomesModel(dataset=dataset),
        edit_list_models.FollowUpsModel(dataset=dataset, outcome="Mortality"),
        edit_list_models.StudiesModel(dataset=dataset),
        edit_list_models.CovariatesModel(dataset=dataset),
    )


@pytest.mark.parametrize("model_index", range(5))
def test_supporting_models_return_none_and_reject_every_invalid_edit(model_index):
    models = _models(WorkspaceDataset())
    model = models[model_index]
    invalid = QModelIndex()
    foreign = models[(model_index + 1) % len(models)].index(0, 0)
    wrong_column = model.createIndex(0, 1)
    wrong_row = model.createIndex(model.rowCount(), 0)
    errors = []
    model.dataError.connect(errors.append)

    bad_indexes = (invalid, foreign, wrong_column, wrong_row)
    for bad_index in bad_indexes:
        for role in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.EditRole,
            Qt.ItemDataRole.CheckStateRole,
            Qt.ItemDataRole.DecorationRole,
        ):
            assert model.data(bad_index, role) is None
        assert model.flags(bad_index) == Qt.ItemFlag.NoItemFlags
    assert model.data(model.index(0, 0), Qt.ItemDataRole.DecorationRole) is None
    for bad_index in bad_indexes:
        assert model.setData(bad_index, "ignored") is False
    assert (
        model.setData(model.index(0, 0), "ignored", Qt.ItemDataRole.DisplayRole)
        is False
    )
    assert len(errors) == 5

    parent = model.index(0, 0)
    assert model.rowCount(parent) == 0
    assert model.columnCount(parent) == 0
    assert model.index(0, 0, parent).isValid() is False

    for section in (-1, model.columnCount()):
        assert model.headerData(section, Qt.Orientation.Horizontal) is None
    for section in (-1, model.rowCount()):
        assert model.headerData(section, Qt.Orientation.Vertical) is None
    assert (
        model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DecorationRole)
        is None
    )


def test_supporting_model_edit_emits_one_narrow_change():
    replacements = (
        (0, "Treatment"),
        (1, "Recovery"),
        (2, "12 months"),
        (3, "Beta"),
        (4, "Dose"),
    )
    for model_index, replacement in replacements:
        model = _models(WorkspaceDataset())[model_index]
        index = model.index(0, 0)
        changes = []
        resets = []
        model.dataChanged.connect(
            lambda top, bottom, roles: changes.append((top, bottom, roles))
        )
        model.modelReset.connect(lambda: resets.append(True))

        assert model.setData(index, replacement) is True

        assert model.data(index, Qt.ItemDataRole.DisplayRole) == replacement
        assert len(changes) == 1
        assert changes[0][0] == index == changes[0][1]
        assert changes[0][2] == [
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.EditRole,
        ]
        assert resets == []
