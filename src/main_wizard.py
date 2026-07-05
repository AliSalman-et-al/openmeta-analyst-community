import forms.ui_choose_metric_page
import forms.ui_csv_import_page
import forms.ui_data_type_page
import forms.ui_outcome_name_page
import forms.ui_welcome_page

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QFileDialog,
    QAbstractButton,
    QMenu,
    QMessageBox,
    QWIDGETSIZE_MAX,
    QSizePolicy,
    QTableWidgetItem,
    QWizard,
    QWizardPage,
)
import meta_globals
import app_error_handler
import qt_layout
import qt_text
import tabular_data
from ma_data_table_model import DatasetModel
from settings import get_default_open_directory


class WelcomePage(QWizardPage, forms.ui_welcome_page.Ui_WizardPage):
    def __init__(self, parent=None, recent_datasets=[]):
        super(WelcomePage, self).__init__(parent)
        self.setupUi(self)

        self.recent_datasets = recent_datasets
        self.selected_dataset = None
        self.setPixmap(
            QWizard.BackgroundPixmap,
            QPixmap(":/wizard_images/wizard_images/forest.jpg"),
        )
        self._setup_connections()
        qt_layout.fit_text_to_contents(self, adjust_root=False)

    def initializePage(self):
        # self.wizard().adjustSize()
        pass

    def isComplete(self):  # disable next/back buttons
        return False

    def nextId(self):
        # print("wizard path is: %s" % str(self.wizard().get_wizard_path()))
        if self.wizard().get_wizard_path() == "open":
            return -1
        else:
            return Page_DataType

    def _setup_connections(self):
        self.create_new_btn.clicked.connect(
            app_error_handler.safe_slot(
                lambda _checked=False: self.new_dataset(), parent=self
            )
        )
        self.open_btn.clicked.connect(
            app_error_handler.safe_slot(
                lambda _checked=False: self.open_dataset(), parent=self
            )
        )
        self._setup_open_recent_btn()
        self.import_csv_btn.clicked.connect(
            app_error_handler.safe_slot(
                lambda _checked=False: self.import_csv(), parent=self
            )
        )

    def _setup_open_recent_btn(self):
        if len(self.recent_datasets) > 0:
            ###
            # then add a drop-down to the 'open recent'
            # button with the recent datasets.
            qm = QMenu()
            for dataset in self.recent_datasets[
                ::-1
            ]:  # most recent dataset is last in list
                action_item = QAction(dataset, qm)
                qm.addAction(action_item)
                # I wanted to handle this with lambdas, but the method would
                # inexplicably always be invoked with the last dataset as the
                # argument. Instead, I've opted to use the .sender method to
                # retrieve the action_item, i.e., dataset, selected (see
                # the dataset_selected routine).
                action_item.triggered.connect(
                    app_error_handler.safe_slot(
                        lambda _checked=False, action_item=action_item: (
                            self.dataset_selected(action_item)
                        ),
                        parent=self,
                    )
                )
            self.open_recent_btn.setMenu(qm)
        else:
            self.open_recent_btn.setEnabled(False)

    def dataset_selected(self, action_item=None):
        self.wizard().set_wizard_path("open")

        # we use the sender method to see which menu item was
        # triggered
        dataset_path = (action_item or self.sender()).text()
        dataset_path = qt_text.to_native_text(dataset_path)
        self.selected_dataset = dataset_path
        self.wizard().set_selected_dataset(self.selected_dataset)
        self.wizard().accept()

    def open_dataset(self):
        self.wizard().set_wizard_path("open")

        self.selected_dataset = QFileDialog.getOpenFileName(
            parent=self,
            caption="OpenMetaAnalyst - Open File",
            directory=get_default_open_directory(self.recent_datasets),
            filter="open meta files (*.oma)",
        )
        if isinstance(self.selected_dataset, tuple):
            self.selected_dataset = self.selected_dataset[0]
        self.selected_dataset = qt_text.to_native_text(self.selected_dataset)

        if self.selected_dataset != "":
            self.wizard().set_selected_dataset(self.selected_dataset)
            self.wizard().accept()

    def import_csv(self):
        self.wizard().set_wizard_path("csv_import")
        self.wizard().next()

    def new_dataset(self):
        self.wizard().set_wizard_path("new_dataset")
        self.wizard().next()


################################################################################


class DataTypePage(QWizardPage, forms.ui_data_type_page.Ui_DataTypePage):
    def __init__(self, parent=None):
        super(DataTypePage, self).__init__(parent)
        self.setupUi(self)

        self.selected_datatype = None
        self.summary = dict(
            arms=None,
            data_type=None,
            sub_type=None,
            effect=None,
            metric_choices=[],
            name=None,
        )  # ProjectInfo()

        self.buttonGroup.buttonClicked[QAbstractButton].connect(
            app_error_handler.safe_slot(self._button_selected, parent=self)
        )

        self.setPixmap(
            QWizard.BackgroundPixmap,
            QPixmap(":/wizard_images/wizard_images/laplace.jpg"),
        )
        self._normalize_data_type_button_sizes()
        qt_layout.fit_text_to_contents(self, adjust_root=False)
        self._fit_page_to_data_type_contents()

    def initializePage(self):
        # self.wizard().adjustSize()
        self.setFocus()

    def _data_type_buttons(self):
        return [
            self.onearm_proportion_Button,
            self.onearm_mean_Button,
            self.onearm_single_reg_coef_Button,
            self.onearm_generic_effect_size_Button,
            self.twoarm_proportions_Button,
            self.twoarm_means_Button,
            self.twoarm_smds_Button,
            self.diagnostic_Button,
        ]

    def _normalize_data_type_button_sizes(self):
        buttons = self._data_type_buttons()
        for button in buttons:
            button.setMinimumSize(QSize(0, 0))
            button.setMaximumSize(QSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX))

        common_size = QSize(
            max(button.sizeHint().width() for button in buttons),
            max(button.sizeHint().height() for button in buttons),
        )
        for button in buttons:
            button.setFixedSize(common_size)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def _fit_page_to_data_type_contents(self):
        layout = self.layout()
        if layout is not None:
            layout.activate()
        self.setMinimumSize(self.minimumSize().expandedTo(self.sizeHint()))

    def _button_selected(self, button):
        # print("button clicked %s" % str(button))

        if button == self.onearm_proportion_Button:
            self.summary["arms"] = "one"
            self.summary["data_type"] = "binary"
            self.summary["sub_type"] = "proportion"
            self.summary["effect"] = "PR"  # default effect
            self.summary["metric_choices"] = meta_globals.BINARY_ONE_ARM_METRICS
        elif button == self.onearm_mean_Button:
            self.summary["arms"] = "one"
            self.summary["data_type"] = "continuous"
            self.summary["sub_type"] = "mean"
            self.summary["effect"] = meta_globals.DEFAULT_CONTINUOUS_ONE_ARM
            self.summary["metric_choices"] = meta_globals.CONTINUOUS_ONE_ARM_METRICS
        elif button == self.onearm_single_reg_coef_Button:
            self.summary["arms"] = "one"
            self.summary["data_type"] = "continuous"
            self.summary["sub_type"] = "reg_coef"
            self.summary["effect"] = meta_globals.DEFAULT_CONTINUOUS_ONE_ARM
            self.summary["metric_choices"] = meta_globals.CONTINUOUS_ONE_ARM_METRICS
        elif button == self.onearm_generic_effect_size_Button:
            self.summary["arms"] = "one"
            self.summary["data_type"] = "continuous"
            self.summary["sub_type"] = (
                "generic_effect"  # TODO: Should disable_two-arm metrics for generic effect
            )
            self.summary["effect"] = meta_globals.DEFAULT_CONTINUOUS_ONE_ARM
            self.summary["metric_choices"] = meta_globals.CONTINUOUS_ONE_ARM_METRICS
        # twoarm
        elif button == self.twoarm_proportions_Button:
            self.summary["arms"] = "two"
            self.summary["data_type"] = "binary"
            self.summary["sub_type"] = "proportions"
            self.summary["effect"] = "OR"
            self.summary["metric_choices"] = meta_globals.BINARY_TWO_ARM_METRICS
        elif button == self.twoarm_means_Button:
            self.summary["arms"] = "two"
            self.summary["data_type"] = "continuous"
            self.summary["sub_type"] = "means"
            self.summary["effect"] = "MD"
            self.summary["metric_choices"] = meta_globals.CONTINUOUS_TWO_ARM_METRICS
        elif button == self.twoarm_smds_Button:
            self.summary["arms"] = "two"
            self.summary["data_type"] = "continuous"
            self.summary["sub_type"] = "smd"
            self.summary["effect"] = "SMD"
            self.summary["metric_choices"] = meta_globals.CONTINUOUS_TWO_ARM_METRICS
        # diagnostic
        elif button == self.diagnostic_Button:
            self.summary["data_type"] = "diagnostic"

        # Put information from pressing the button into the wizard storage area
        self.wizard().set_dataset_info(self.summary)
        self.completeChanged.emit()

    def isComplete(self):
        # print(self.buttonGroup.checkedButton())

        if self.buttonGroup.checkedButton():
            return True
        else:
            return False

    def nextId(self):
        if (
            self.wizard().get_dataset_info()
            and self.wizard().get_dataset_info()["data_type"] == "diagnostic"
        ):
            return Page_OutcomeName
        else:  # normal case
            return Page_ChooseMetric


###############################################################################
class ChooseMetricPage(QWizardPage, forms.ui_choose_metric_page.Ui_WizardPage):
    def __init__(self, parent=None):
        super(ChooseMetricPage, self).__init__(parent)
        self.setupUi(self)

        self.metric_cbo_box.currentIndexChanged[int].connect(
            app_error_handler.safe_slot(self._metric_choice_changed, parent=self)
        )
        qt_layout.fit_text_to_contents(self, adjust_root=False)

    def initializePage(self):
        data_type = self.wizard().get_dataset_info()["data_type"]
        metric_choices = self.wizard().get_dataset_info()["metric_choices"]
        default_effect = self.wizard().get_dataset_info()["effect"]

        # Add metric choices to combo box
        self.metric_cbo_box.blockSignals(True)
        self.metric_cbo_box.clear()
        self.metric_cbo_box.blockSignals(False)
        if data_type != "diagnostic":
            self.metric_cbo_box.blockSignals(True)
            for metric in metric_choices:
                metric_pretty_name = meta_globals.ALL_METRIC_NAMES[metric]
                self.metric_cbo_box.addItem(
                    metric + ": " + metric_pretty_name, userData=str(metric)
                )
            index_of_default = self.metric_cbo_box.findData(str(default_effect))
            if index_of_default < 0:
                raise ValueError(
                    "Default metric %r is not available for %r"
                    % (default_effect, data_type)
                )
            self.metric_cbo_box.setCurrentIndex(index_of_default)

            default_item_text = self.metric_cbo_box.itemText(index_of_default)
            default_item_text += " (DEFAULT)"
            self.metric_cbo_box.setItemText(index_of_default, default_item_text)
            # Resize the dialog
            self.metric_cbo_box.blockSignals(False)
            qt_layout.fit_text_to_contents(self, adjust_root=False)

        self.setPixmap(
            QWizard.BackgroundPixmap, QPixmap(":/wizard_images/wizard_images/airy.jpg")
        )
        # self.wizard().adjustSize()

    def _metric_choice_changed(self, newindex):
        self.wizard().set_effect(_qt_item_text(self.metric_cbo_box.itemData(newindex)))

    def nextId(self):
        return Page_OutcomeName


###############################################################################

import csv


def _qt_item_text(value):
    return qt_text.to_native_text(value)


class CsvImportPage(QWizardPage, forms.ui_csv_import_page.Ui_WizardPage):
    def __init__(self, parent=None):
        super(CsvImportPage, self).__init__(parent)
        self.setupUi(self)
        qt_layout.fit_option_groups_to_contents(self, adjust_root=False)

        self.select_file_btn.clicked.connect(
            app_error_handler.safe_slot(
                lambda _checked=False: self._select_file(), parent=self
            )
        )
        self.from_excel_chkbx.stateChanged.connect(
            app_error_handler.safe_slot(
                lambda _state: self._rebuild_display(), parent=self
            )
        )
        self.has_headers_chkbx.stateChanged.connect(
            app_error_handler.safe_slot(
                lambda _state: self._rebuild_display(), parent=self
            )
        )

        self.setPixmap(
            QWizard.BackgroundPixmap,
            QPixmap(":/wizard_images/wizard_images/cochran.jpg"),
        )

    def initializePage(self):
        ######################################################
        self.file_path = None
        self._reset_data()
        ######################################################

        self.required_header_labels = self._get_required_header_labels()
        self.required_fmt_table.setRowCount(2)
        self.required_fmt_table.setColumnCount(len(self.required_header_labels))

        self.required_fmt_table.setHorizontalHeaderLabels(self.required_header_labels)
        self.required_fmt_table.resizeColumnsToContents()
        self.required_fmt_table.resizeRowsToContents()

        # Set up preview format table
        for row in range(self.required_fmt_table.rowCount()):
            for col in range(self.required_fmt_table.columnCount()):
                self.required_fmt_table.setItem(row, col, QTableWidgetItem(""))
                self.required_fmt_table.item(row, col).setFlags(Qt.NoItemFlags)
        qt_layout.configure_compact_table(
            self.required_fmt_table, stretch_columns=True
        )

    def isComplete(self):
        # We must have a file selected
        if not self.file_path:
            return False

        if self.imported_data_ok:
            self.wizard().set_csv_data(self.csv_data())  # stick csv data into wizard
            return True
        else:
            return False

    def _reset_data(self):
        self.preview_table.clear()
        self.headers = []
        self.covariate_names = []
        self.covariate_types = []
        self.imported_data = []
        self.imported_data_ok = True

    def _select_file(self):
        self.file_path = QFileDialog.getOpenFileName(
            parent=self,
            caption="OpenMetaAnalyst - Import CSV",
            directory=".",
            filter="csv files (*.csv)",
        )
        self.file_path = (
            self.file_path[0] if isinstance(self.file_path, tuple) else self.file_path
        )
        self.file_path = qt_text.to_native_text(self.file_path)

        if self.file_path:
            self.file_path_lbl.setText(self.file_path)

        if self.file_path:
            self._rebuild_display()

    def _rebuild_display(self):
        self._reset_data()
        try:
            self.extract_data()
            if len(self.imported_data) == 0:
                QMessageBox.warning(self, "Warning", "No data in CSV. Try again.")
                self.imported_data_ok = False
                return False

            num_rows = len(self.imported_data)
            num_cols = len(self.imported_data[0])
            self._handle_covariates_in_extracted_data(
                num_rows,
                num_cols,
                headers=self.headers,
                expected_headers=self.required_header_labels,
            )

            # set up table
            self.preview_table.setRowCount(num_rows)
            self.preview_table.setColumnCount(num_cols)
            if self.headers != []:
                self.preview_table.setHorizontalHeaderLabels(self.headers)
            else:
                preview_header_labels = self.required_header_labels[:]
                preview_header_labels.extend(self.covariate_names)
                self.preview_table.setHorizontalHeaderLabels(preview_header_labels)

            # copy extracted data to table
            for row in range(num_rows):
                for col in range(num_cols):
                    item = QTableWidgetItem(self.imported_data[row][col])
                    item.setFlags(Qt.NoItemFlags)
                    self.preview_table.setItem(row, col, item)
            self.preview_table.resizeColumnsToContents()
            self.preview_table.resizeRowsToContents()
            qt_layout.configure_compact_table(self.preview_table, stretch_columns=True)

            # Validate table entries
            self._validate_imported_data()
            self.completeChanged.emit()
        except Exception as e:
            print(e)
            QMessageBox.warning(
                self,
                "Could not import CSV",
                "OpenMeta[Analyst] could not preview the selected CSV file.\n\n"
                "Details: %s: %s" % (e.__class__.__name__, e),
            )
            self.imported_data_ok = False
            return False

    def _validate_imported_data(self):
        # Make sure there are at least as many columns as required columns
        # (additional columns are covariates hopefully)
        #        if self.preview_table.columnCount() < self.required_fmt_table.columnCount():
        #            QMessageBox.warning(self, "Warning", "There are two few columns in the imported csv, try again with a properly formatted CSV.")
        #            self._reset_data
        #            return False

        # Are the years integers?
        for row in range(len(self.imported_data)):
            try:
                # -1 since the imported data doesn't have an 'include' column
                int(self.imported_data[row][DatasetModel.YEAR - 1])
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Warning",
                    "The year at row " + str(row + 1) + " is not an integer number.",
                )
                self.imported_data_ok = False
                return False
        # More validation??

    def _get_required_header_labels(self):
        """
        Provides column header labels based on chosen datatype and subtype
        ** Must be updated if header_data() is ma_data_table_model is changed
        """

        data_type = self.wizard().get_dataset_info()["data_type"]
        data_subtype = self.wizard().get_dataset_info()["sub_type"]
        effect = self.wizard().get_dataset_info()["effect"]
        raw_cols, outcome_cols = DatasetModel.get_column_indices(
            data_type, data_subtype
        )

        header_labels = []

        model_cols = [DatasetModel.NAME, DatasetModel.YEAR]
        model_cols.extend(raw_cols)
        model_cols.extend(outcome_cols)

        for col in model_cols:
            col_name = DatasetModel.helper_basic_horizontal_headerData(
                section=col,
                data_type=meta_globals.STR_TO_TYPE_DICT[data_type],
                sub_type=data_subtype,
                raw_columns=raw_cols,
                outcome_columns=outcome_cols,
                current_effect=effect,
                groups=meta_globals.DEFAULT_GROUP_NAMES,
            )
            col_name = _qt_item_text(col_name)
            header_labels.append(col_name)
        return header_labels

    def csv_data(self):
        """Imported data is a list of rows. A row is a list of
        cell contents (as strings)"""

        if self.imported_data_ok:
            return {
                "headers": self.headers,
                "data": self.imported_data,
                "expected_headers": self.required_header_labels,
                "covariate_names": self.covariate_names,
                "covariate_types": self.covariate_types,
            }
        else:
            print("Something went wrong while trying to import from csv")
            return None

    def _handle_covariates_in_extracted_data(
        self, num_rows, num_cols, headers=[], expected_headers=[]
    ):
        if num_cols > len(expected_headers):  # Do we have covariates?
            num_covariates = num_cols - len(expected_headers)
            print(("There are %d covariates" % num_covariates))
        else:
            return None  # no covariates to deal with

        def covariate_name(index, given_name):
            if str(given_name).strip() == "":
                return "Covariate " + str(index + 1)
            else:
                return given_name

        if self._hasHeaders():
            covariate_names = headers[len(expected_headers) :]
        else:
            covariate_names = [""] * num_covariates
        self.covariate_names = [
            covariate_name(i, name) for i, name in enumerate(covariate_names)
        ]

        def covariate_type(data):
            for x in data:
                try:
                    float(x)
                except ValueError:
                    return "factor"  # these types are important to get right (look in covariate constructor)
            return "continuous"  #

        index_offset = len(expected_headers)
        for cov_index in range(len(covariate_names)):
            cov_data = [
                self.imported_data[row][index_offset + cov_index]
                for row in range(num_rows)
            ]
            self.covariate_types.append(covariate_type(cov_data))

    def extract_data(self):
        with open(self._get_filepath(), newline="") as csvfile:
            args_csv_reader = {
                "delimiter": self._get_delimter(),
                "quotechar": self._get_quotechar(),
            }
            if self._isFromExcel():
                args_csv_reader = {}
                args_csv_reader["dialect"] = "excel"

            # set up reader object
            reader = csv.reader(csvfile, **args_csv_reader)

            self.headers = []
            self.imported_data = []
            if self._hasHeaders():
                self.headers = next(reader, [])
            for row in reader:
                self.imported_data.append(row)
        self._normalize_imported_rows()
        self.print_extracted_data()  # just for debugging

    def _normalize_imported_rows(self):
        self.imported_data = tabular_data.normalize_rows(
            self.imported_data, minimum_width=len(self.headers)
        )
        if self.headers:
            num_cols = (
                len(self.imported_data[0]) if self.imported_data else len(self.headers)
            )
            self.headers = self.headers + [""] * (num_cols - len(self.headers))

    def print_extracted_data(self):
        print("Data extracted from csv:")
        print((self.headers))
        for row in self.imported_data:
            print((str(row)))

    def _get_filepath(self):
        return self.file_path

    def _isFromExcel(self):
        return self.from_excel_chkbx.isChecked()

    def _hasHeaders(self):
        return self.has_headers_chkbx.isChecked()

    def _get_delimter(self):
        return str(self.delimter_le.text())

    def _get_quotechar(self):
        return str(self.quotechar_le.text())


################################################################################
class OutcomeNamePage(QWizardPage, forms.ui_outcome_name_page.Ui_WizardPage):
    def __init__(self, parent=None):
        super(OutcomeNamePage, self).__init__(parent)
        self.setupUi(self)

        self.setPixmap(
            QWizard.BackgroundPixmap,
            QPixmap(":/wizard_images/wizard_images/fisher.jpg"),
        )

        self.registerField("outcomeName*", self.outcome_name_LineEdit)
        qt_layout.fit_text_to_contents(self, adjust_root=False)

    def initializePage(self):
        # self.wizard().adjustSize()
        pass

    def nextId(self):
        if self.wizard().get_wizard_path() == "csv_import":
            return Page_CsvImport
        else:  # normal case
            return -1


################################################################################
Page_Welcome, Page_DataType, Page_ChooseMetric, Page_OutcomeName, Page_CsvImport = list(
    range(5)
)


class MainWizard(QWizard):
    def __init__(self, parent=None, path=None, recent_datasets=[]):
        super(MainWizard, self).__init__(parent)
        qt_layout.configure_application_wizard(self)

        self.info_d = {}
        self.info_d["path"] = path
        self.setPage(Page_Welcome, WelcomePage(recent_datasets=recent_datasets))
        self.setPage(Page_DataType, DataTypePage())
        self.setPage(Page_ChooseMetric, ChooseMetricPage())
        self.setPage(Page_OutcomeName, OutcomeNamePage())
        self.setPage(Page_CsvImport, CsvImportPage())

        if path is None:
            self.setStartId(Page_Welcome)
            self.setWindowTitle("OpenMetaAnalyst")
        elif path == "csv_import":
            self.setStartId(Page_DataType)
            self.setWindowTitle("Import a CSV")
        elif path == "new_dataset":
            self.setStartId(Page_DataType)
            self.setWindowTitle("Create a New Dataset")

        # self.setPixmap(QtWidgets.QWizard.BannerPixmap,
        #        QtGui.QPixmap(':/misc/meta.png'))
        # self.setPixmap(QtWidgets.QWizard.BackgroundPixmap,
        #               QtGui.QPixmap(':/misc/meta.png'))

        # make the displayed size of the pages reasonable
        self.currentIdChanged.connect(
            app_error_handler.safe_slot(self._change_size, parent=self)
        )
        qt_layout.fit_application_dialog_to_contents(self)

    def _change_size(self, pageid):
        self._fit_current_page_to_contents()

    def _fit_current_page_to_contents(self):
        current_page = self.currentPage()
        if current_page is None:
            return
        qt_layout.fit_text_to_contents(current_page, adjust_root=False)
        qt_layout.reset_stable_fit_size(self)
        qt_layout.fit_application_dialog_to_contents(self)

    def set_wizard_path(self, path):
        self.info_d["path"] = path

    def get_wizard_path(self):
        if "path" in self.info_d:
            return self.info_d["path"]
        else:
            return None

    def set_dataset_info(self, outcome_info):
        self.info_d["outcome_info"] = outcome_info

    def get_dataset_info(self):
        if "outcome_info" in self.info_d:
            return self.info_d["outcome_info"]
        else:
            return None

    def set_selected_dataset(self, dataset):
        self.info_d["selected_dataset"] = dataset

    def get_selected_dataset(self):
        if "selected_dataset" in self.info_d:
            return self.info_d["selected_dataset"]
        else:
            return None

    def set_effect(self, effect_name):
        self.info_d["outcome_info"]["effect"] = effect_name

    def get_effect(self):
        return self.info_d["outcome_info"]["effect"]

    def set_csv_data(self, csv_data):
        self.info_d["csv_data"] = csv_data

    def get_csv_data(self):
        if "csv_data" in self.info_d:
            return self.info_d["csv_data"]
        else:
            return None

    def get_results(self):
        information = {}
        information["path"] = self.get_wizard_path()
        information["outcome_info"] = self.get_dataset_info()
        # set outcome name
        if information["outcome_info"] is not None:
            information["outcome_info"]["name"] = _qt_item_text(
                self.field("outcomeName")
            )
        information["selected_dataset"] = self.get_selected_dataset()
        information["csv_data"] = self.get_csv_data()

        print(("Information from wizard: %s" % str(information)))
        return information


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    wizard = MainWizard()
    wizard.show()
    sys.exit(app.exec())
