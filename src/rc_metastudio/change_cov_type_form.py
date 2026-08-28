# import pdb
import string
from functools import cmp_to_key

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QMessageBox

from meta_globals import *
import app_error_handler
import adaptive_window
from forms.ui_change_cov_type import Ui_ChangeCovTypeForm
from ma_dataset import Covariate
import qt_layout
import qt_text


def _to_native_text(value):
    return qt_text.to_native_text(value)


def _to_double(value):
    if hasattr(value, "toDouble"):
        return value.toDouble()
    try:
        return float(value), True
    except (TypeError, ValueError):
        return 0.0, False


class ChangeCovTypeForm(QDialog, Ui_ChangeCovTypeForm):
    def __init__(self, dataset, cov, parent=None):
        super(ChangeCovTypeForm, self).__init__(parent)
        self.setupUi(self)
        self.dataset = dataset
        self.cov_model = CovModel(dataset, cov)
        self.cov_model.dataError.connect(
            app_error_handler.safe_slot(self.data_error, parent=self)
        )
        self.cov_prev_table.setModel(self.cov_model)
        self.cov_prev_table.setTabKeyNavigation(False)
        self.cov_prev_table.resizeColumnsToContents()
        qt_layout.configure_spreadsheet_table_view(self.cov_prev_table)
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )

    def data_error(self, msg):
        QMessageBox.warning(self, "Warning", msg)


class CovModel(QAbstractTableModel):
    dataError = pyqtSignal(str)
    """
    This module mediates between the dataset class and 
    the TableView used in the ui.
    """

    def __init__(self, dataset, covariate, filename=""):
        super(CovModel, self).__init__()
        self.dataset = dataset
        self.covariate = covariate

        # now we add a covariate with the new type
        self.new_data_type = CONTINUOUS if covariate.data_type == FACTOR else FACTOR

        # first sort the studies by the cov. of interest
        self.dataset.studies.sort(
            key=cmp_to_key(self.dataset.cmp_studies(compare_by=self.covariate.name))
        )

        self.update_included_studies()
        self.add_cov_with_new_type()

        self.refresh_cov_values()

        self.STUDY_COL, self.ORIG_VAL, self.NEW_VAL = list(range(3))

    def reset_model(self):
        self.beginResetModel()
        self.endResetModel()

    def reject_edit(self, msg):
        self.dataError.emit(msg)
        return False

    def add_cov_with_new_type(self):
        new_name = self.covariate.name
        if self.new_data_type == CONTINUOUS:
            new_name += " (continuous)"
        else:
            new_name += " (factor)"

        guessed_vals = self.guess_at_values()  # try and infer sensible values
        self.new_covariate = Covariate(new_name, COV_INTS_TO_STRS[self.new_data_type])

        self.dataset.add_covariate(self.new_covariate, cov_values=guessed_vals)
        self.reset_model()

    def guess_at_values(self):
        cov_d = self.dataset.get_values_for_cov(self.covariate)  # original values
        guessed_vals_d = self.vals_to_new_vals(cov_d)

        studies_to_guessed_vals = {}
        for study in self.included_studies:
            if study.name in cov_d:
                orig_val = cov_d[study.name]
                studies_to_guessed_vals[study.name] = guessed_vals_d[orig_val]
            else:
                studies_to_guessed_vals[study.name] = None

        return studies_to_guessed_vals

    def vals_to_new_vals(self, cov_d):
        unique_values = list(dict.fromkeys(cov_d.values()))
        # fix for issue #155
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

    def refresh_cov_values(self):
        self.dataset.studies.sort(
            key=cmp_to_key(self.dataset.cmp_studies(compare_by=self.covariate.name))
        )

        self.update_included_studies()
        cov_d = self.dataset.get_values_for_cov(self.covariate)
        new_cov_d = self.dataset.get_values_for_cov(self.new_covariate)

        self.orig_cov_list, self.new_cov_list = [], []
        for study in self.included_studies:
            if study.name in cov_d:
                self.orig_cov_list.append(cov_d[study.name])
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
                # pyqtRemoveInputHook()
                # pdb.set_trace()
                study = self.included_studies[index.row()]  # associated study
                cov_name = self.new_covariate.name
                new_value = None
                if self.new_covariate.data_type == FACTOR:
                    new_value = _to_native_text(value)
                else:
                    # continuous
                    if _to_native_text(value).strip() == "":
                        new_value = None
                    else:
                        new_value, converted_ok = _to_double(value)
                        if not converted_ok:
                            return self.reject_edit(
                                "Covariate values for continuous covariates need to be numeric."
                            )
                study.covariate_dict[cov_name] = new_value
                self.refresh_cov_values()
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
