import string
from functools import cmp_to_key
from typing import TYPE_CHECKING

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QMessageBox

from rc_metastudio.meta_globals import CONTINUOUS, COV_INTS_TO_STRS, FACTOR
from rc_metastudio import app_error_handler
from rc_metastudio import adaptive_window
from rc_metastudio.analysis_dataset import Covariate
from rc_metastudio import qt_layout
from rc_metastudio import qt_text

if TYPE_CHECKING:
    import ui_covariate_type_dialog as _ui_covariate_type_dialog
else:
    from rc_metastudio.forms import (
        ui_covariate_type_dialog as _ui_covariate_type_dialog,
    )


def _to_native_text(value):
    return qt_text.to_native_text(value)


def _to_double(value):
    if hasattr(value, "toDouble"):
        return value.toDouble()
    try:
        return float(value), True
    except (TypeError, ValueError):
        return 0.0, False


def _new_covariate_value(covariate, value):
    if covariate.data_type == FACTOR:
        return _to_native_text(value), True
    if _to_native_text(value).strip() == "":
        return None, True
    return _to_double(value)


class CovariateTypeDialog(QDialog, _ui_covariate_type_dialog.Ui_CovariateTypeDialog):
    def __init__(self, dataset, cov, parent=None):
        super(CovariateTypeDialog, self).__init__(parent)
        self.setupUi(self)
        self.dataset = dataset
        self.cov_model = CovariateTypeModel(dataset, cov)
        self.cov_model.dataError.connect(
            app_error_handler.safe_slot(self.data_error, parent=self)
        )
        self.covariate_preview_table.setModel(self.cov_model)
        self.covariate_preview_table.setTabKeyNavigation(False)
        self.covariate_preview_table.resizeColumnsToContents()
        qt_layout.configure_spreadsheet_table_view(self.covariate_preview_table)
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )

    def data_error(self, msg):
        QMessageBox.warning(self, "Warning", msg)


class CovariateTypeModel(QAbstractTableModel):
    """Expose covariate values and type conversion through a table model."""

    dataError = pyqtSignal(str)

    def __init__(self, dataset, covariate, filename=""):
        super(CovariateTypeModel, self).__init__()
        self.dataset = dataset
        self.covariate = covariate

        # now we add a covariate with the new type
        self.new_data_type = CONTINUOUS if covariate.data_type == FACTOR else FACTOR

        # first sort the studies by the cov. of interest
        self.dataset.studies.sort(
            key=cmp_to_key(self.dataset.cmp_studies(compare_by=self.covariate.name))
        )

        self.update_included_studies()
        self.add_covariate_with_new_type()

        self.refresh_covariate_values()

        self.STUDY_COL, self.ORIG_VAL, self.NEW_VAL = list(range(3))

    def reset_model(self):
        self.beginResetModel()
        self.endResetModel()

    def reject_edit(self, msg):
        self.dataError.emit(msg)
        return False

    def add_covariate_with_new_type(self):
        new_name = self.covariate.name
        if self.new_data_type == CONTINUOUS:
            new_name += " (continuous)"
        else:
            new_name += " (factor)"

        guessed_vals = self.guess_at_values()  # try and infer sensible values
        self.new_covariate = Covariate(new_name, COV_INTS_TO_STRS[self.new_data_type])

        self.dataset.add_covariate(self.new_covariate, covariate_values=guessed_vals)
        self.reset_model()

    def guess_at_values(self):
        covariate_values = self.dataset.get_covariate_values(
            self.covariate
        )  # original values
        guessed_vals_d = self.vals_to_new_vals(covariate_values)

        studies_to_guessed_vals = {}
        for study in self.included_studies:
            if study.name in covariate_values:
                orig_val = covariate_values[study.name]
                studies_to_guessed_vals[study.name] = guessed_vals_d[orig_val]
            else:
                studies_to_guessed_vals[study.name] = None

        return studies_to_guessed_vals

    def vals_to_new_vals(self, covariate_values):
        unique_values = list(dict.fromkeys(covariate_values.values()))
        unique_values.sort()
        mapping = {}
        for i, val in enumerate(unique_values):
            if self.new_data_type == FACTOR:
                mapping[val] = self._to_alphabet_str(i)
            else:
                mapping[val] = i

        return mapping

    def _to_alphabet_str(self, x):
        # base conversion.
        alphabet = string.ascii_lowercase
        alpha_str = ""
        x_left = x
        while x_left >= 0:
            if x_left > 25:
                alpha_str += "a"
                x_left -= 26
            else:
                alpha_str += alphabet[x_left]
                x_left = -1

        return alpha_str

    def refresh_covariate_values(self):
        self.dataset.studies.sort(
            key=cmp_to_key(self.dataset.cmp_studies(compare_by=self.covariate.name))
        )

        self.update_included_studies()
        covariate_values = self.dataset.get_covariate_values(self.covariate)
        new_cov_d = self.dataset.get_covariate_values(self.new_covariate)

        self.orig_cov_list, self.new_cov_list = [], []
        for study in self.included_studies:
            if study.name in covariate_values:
                self.orig_cov_list.append(covariate_values[study.name])
                self.new_cov_list.append(new_cov_d[study.name])
            else:
                self.orig_cov_list.append(None)
                self.new_cov_list.append(None)
        self.orig_cov_list.append("")

        self.reset_model()

    def update_included_studies(self):
        study_list = []
        for study in self.dataset.studies:
            if study.include:
                study_list.append(study)
        self.included_studies = study_list

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):

        if not index.isValid() or not (0 <= index.row() < len(self.included_studies)):
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            row, column = index.row(), index.column()
            if column == self.STUDY_COL:
                return self.included_studies[row].name
            elif column == self.ORIG_VAL:
                if self.covariate.data_type == FACTOR:
                    return _to_native_text(self.orig_cov_list[row])
                return self.orig_cov_list[row]
            elif column == self.NEW_VAL:
                if self.new_covariate.data_type == FACTOR:
                    return _to_native_text(self.new_cov_list[row])
                return self.new_cov_list[row]
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        del parent
        return len(self.included_studies)  # don't show blank study!

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        del parent
        return 3  # study, orig_val, new_val

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        # don't allow users to mess with the original
        # covariate.
        if index.isValid() and 0 <= index.row() < len(self.dataset):
            column = index.column()

            if column == self.NEW_VAL:
                # then a (new) covariate value has been edited.
                study = self.included_studies[index.row()]  # associated study
                new_value, converted_ok = _new_covariate_value(
                    self.new_covariate, value
                )
                if not converted_ok:
                    return self.reject_edit(
                        "Covariate values for continuous covariates need to be numeric."
                    )
                study.set_covariate_value(self.new_covariate, new_value)
                self.refresh_covariate_values()
                return True
        return self.reject_edit("Cannot edit that cell.")

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled
        return Qt.ItemFlag(
            QAbstractTableModel.flags(self, index) | Qt.ItemFlag.ItemIsEditable
        )

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if section == self.STUDY_COL:
                return "study"
            elif section == self.ORIG_VAL:
                return self.covariate.name
            elif section == self.NEW_VAL:
                return self.new_covariate.name
