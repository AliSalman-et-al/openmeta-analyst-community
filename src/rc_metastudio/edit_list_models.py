# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Proxy models between dataset objects and editing dialogs."""

# import pdb

# core libraries
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal

import name_validation
import qt_text
from ma_dataset import Dataset


def _require_dataset(dataset: Dataset | None) -> Dataset:
    if dataset is None:
        raise ValueError("edit-list models require a Dataset")
    return dataset


def _to_native_text(value):
    return qt_text.to_native_text(value)


def _without_current_name(names, current_name):
    remaining = list(names)
    if current_name in remaining:
        remaining.remove(current_name)
    return remaining


class ResettableTableModel(QAbstractTableModel):
    dataError = pyqtSignal(str)
    dataset: Dataset

    def reset_model(self):
        self.beginResetModel()
        self.endResetModel()

    def reject_edit(self, msg):
        self.dataError.emit(msg)
        return False

    def editable_row(self, index, row_count, role):
        if role != Qt.ItemDataRole.EditRole:
            return None
        if not self.valid_index(index, row_count):
            return None
        row = index.row()
        return row if 0 <= row < row_count else None

    def valid_index(self, index, row_count=None):
        if not index.isValid() or index.model() is not self or index.column() != 0:
            return False
        limit = self.rowCount() if row_count is None else row_count
        return 0 <= index.row() < limit

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            valid_section = 0 <= section < self.columnCount()
        elif orientation == Qt.Orientation.Vertical:
            valid_section = 0 <= section < self.rowCount()
        else:
            valid_section = False
        if not valid_section:
            return None
        # These one-column dialog models intentionally display no headers.
        return None

    def commit_edit(self, index):
        self.dataChanged.emit(
            index,
            index,
            [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole],
        )
        return True


class TXGroupsModel(ResettableTableModel):
    """
    This module mediates between the classes comprising a dataset
    (i.e., study & ma_unit objects) and the view. In particular, we
    subclass the QAbstractTableModel and provide the fields of interest
    to the view.
    """

    def __init__(self, filename="", dataset=None, outcome=None, follow_up=None):
        super(TXGroupsModel, self).__init__()
        self.dataset = _require_dataset(dataset)
        self.current_outcome = outcome
        self.current_follow_up = follow_up
        self.refresh_group_list(outcome, follow_up)

    def refresh_group_list(self, outcome, follow_up):
        self.group_list = self.dataset.get_group_names_for_outcome_fu(
            outcome, follow_up
        )
        print("\ngroup names are: %s" % self.group_list)
        self.reset_model()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not self.valid_index(index, len(self.group_list)):
            return None
        group_name = self.group_list[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return group_name
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.group_list)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return 1

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        row = self.editable_row(index, len(self.group_list), role)
        if row is None:
            return self.reject_edit("Cannot edit that group.")
        old_name = self.group_list[row]
        try:
            new_name = name_validation.validate_unique_name(
                "group",
                value,
                _without_current_name(self.dataset.get_group_names(), old_name),
            )
        except ValueError as exc:
            return self.reject_edit(str(exc))

        self.dataset.change_group_name(old_name, new_name)  # , \
        # outcome=self.current_outcome, follow_up=self.current_follow_up)
        self.group_list[row] = new_name
        return self.commit_edit(index)

    def flags(self, index):
        if not self.valid_index(index, len(self.group_list)):
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag(
            QAbstractTableModel.flags(self, index) | Qt.ItemFlag.ItemIsEditable
        )


class OutcomesModel(ResettableTableModel):
    """
    A simple table model for editing/deleting/adding outcomes.
    Subclasses the QAbstractTableModel and provide the fields of interest
    to the view.
    """

    def __init__(self, filename="", dataset=None):
        super(OutcomesModel, self).__init__()
        self.dataset = _require_dataset(dataset)
        self.current_outcome = None
        self.outcome_list = self.dataset.get_outcome_names()

    def refresh_outcome_list(self):
        self.outcome_list = self.dataset.get_outcome_names()
        self.reset_model()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        self.outcome_list = self.dataset.get_outcome_names()
        if not self.valid_index(index, len(self.outcome_list)):
            return None
        outcome_name = self.outcome_list[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return outcome_name
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.outcome_list)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return 1

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        row = self.editable_row(index, len(self.outcome_list), role)
        if row is None:
            return self.reject_edit("Cannot edit that outcome.")
        old_outcome_name = self.outcome_list[row]
        try:
            new_outcome_name = name_validation.validate_unique_name(
                "outcome",
                value,
                _without_current_name(
                    self.dataset.get_outcome_names(), old_outcome_name
                ),
            )
        except ValueError as exc:
            return self.reject_edit(str(exc))

        self.dataset.change_outcome_name(old_outcome_name, new_outcome_name)
        # issue #130: if we change an outcome name, set the current outcome
        # to said outcome
        self.current_outcome = new_outcome_name
        self.outcome_list[row] = new_outcome_name
        return self.commit_edit(index)

    def flags(self, index):
        if not self.valid_index(index, len(self.outcome_list)):
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag(
            QAbstractTableModel.flags(self, index) | Qt.ItemFlag.ItemIsEditable
        )


class FollowUpsModel(ResettableTableModel):
    """
    A simple table model for editing/deleting/adding follow-ups.
    Subclasses the QAbstractTableModel and provide the fields of interest
    to the view.
    """

    def __init__(self, filename="", dataset=None, outcome=None):
        super(FollowUpsModel, self).__init__()
        self.dataset = _require_dataset(dataset)
        ## we maintain a current outcome string variable because
        # the follow-ups are outcome specific
        self.current_outcome = outcome
        self.follow_up_list = self._follow_up_names_for_current_outcome()

    def _follow_up_names_for_current_outcome(self):
        if self.current_outcome is None:
            return []
        return self.dataset.get_follow_up_names_for_outcome(self.current_outcome)

    def refresh_follow_up_list(self):
        self.follow_up_list = self._follow_up_names_for_current_outcome()
        self.reset_model()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not self.valid_index(index, len(self.follow_up_list)):
            return None
        follow_up_name = self.follow_up_list[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return follow_up_name
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.follow_up_list)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return 1

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        row = self.editable_row(index, len(self.follow_up_list), role)
        if row is None:
            return self.reject_edit("Cannot edit that follow-up.")
        old_follow_up_name = self.follow_up_list[row]
        try:
            new_follow_up_name = name_validation.validate_unique_name(
                "follow-up",
                value,
                _without_current_name(
                    self.dataset.get_follow_up_names_for_outcome(self.current_outcome),
                    old_follow_up_name,
                ),
            )
        except ValueError as exc:
            return self.reject_edit(str(exc))
        self.dataset.change_follow_up_name(
            self.current_outcome, old_follow_up_name, new_follow_up_name
        )
        self.follow_up_list[row] = new_follow_up_name
        return self.commit_edit(index)

    def flags(self, index):
        if not self.valid_index(index, len(self.follow_up_list)):
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag(
            QAbstractTableModel.flags(self, index) | Qt.ItemFlag.ItemIsEditable
        )


class StudiesModel(ResettableTableModel):
    """
    Table model implementation for studies list.
    """

    def __init__(self, filename="", dataset=None):
        super(StudiesModel, self).__init__()
        self.dataset = _require_dataset(dataset)
        self.update_study_list()

    def update_study_list(self):
        self.studies_list = self.dataset.studies
        self.reset_model()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not self.valid_index(index, len(self.studies_list)):
            return None
        study_name = self.studies_list[index.row()].name
        if role == Qt.ItemDataRole.DisplayRole:
            return study_name
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.studies_list)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return 1

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        row = self.editable_row(index, len(self.studies_list), role)
        if row is None:
            return self.reject_edit("Cannot edit that study.")
        study_object = self.studies_list[row]
        try:
            new_name = name_validation.validate_required_name("study", value)
        except ValueError as exc:
            return self.reject_edit(str(exc))

        study_object.name = new_name
        return self.commit_edit(index)

    def flags(self, index):
        if not self.valid_index(index, len(self.studies_list)):
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag(
            QAbstractTableModel.flags(self, index) | Qt.ItemFlag.ItemIsEditable
        )


class CovariatesModel(ResettableTableModel):
    """
    Table model implementation for covariates.
    """

    def __init__(self, filename="", dataset=None):
        super(CovariatesModel, self).__init__()
        self.dataset = _require_dataset(dataset)
        self.update_covariates_list()

    def update_covariates_list(self):
        self.covariates_list = self.dataset.covariates
        self.reset_model()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not self.valid_index(index, len(self.covariates_list)):
            return None
        cov_name = self.covariates_list[index.row()].name
        if role == Qt.ItemDataRole.DisplayRole:
            return cov_name
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.covariates_list)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return 1

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        row = self.editable_row(index, len(self.covariates_list), role)
        if row is None:
            return self.reject_edit("Cannot edit that covariate.")
        cov_object = self.covariates_list[row]
        try:
            new_name = name_validation.validate_unique_name(
                "covariate",
                value,
                _without_current_name(self.dataset.get_cov_names(), cov_object.name),
            )
        except ValueError as exc:
            return self.reject_edit(str(exc))

        self.dataset.change_covariate_name(cov_object, new_name)
        self.covariates_list = self.dataset.covariates
        return self.commit_edit(index)

    def flags(self, index):
        if not self.valid_index(index, len(self.covariates_list)):
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag(
            QAbstractTableModel.flags(self, index) | Qt.ItemFlag.ItemIsEditable
        )
