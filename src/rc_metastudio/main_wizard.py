# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

import forms.ui_choose_metric_page
import forms.ui_csv_import_page
import forms.ui_data_type_page
import forms.ui_outcome_name_page
import forms.ui_welcome_page

from typing import TypedDict

from PyQt6.QtCore import QEvent, QObject, QSize, Qt, QTimer
from PyQt6.QtGui import (
    QAction,
    QCloseEvent,
    QHideEvent,
    QIcon,
    QPalette,
    QShowEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QAbstractButton,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QScrollArea,
    QStyle,
    QTableWidgetItem,
    QWizard,
    QWizardPage,
)
import meta_globals
import app_error_handler
import adaptive_window
import qt_layout
import qt_text
import tabular_data
from ma_data_table_model import DatasetModel
from settings import get_default_open_directory


class DatasetInfo(TypedDict, total=False):
    arms: str | None
    data_type: str | None
    sub_type: str | None
    effect: str | None
    metric_choices: list[str]
    name: str | None


class MainWizardPage(QWizardPage):
    def wizard(self) -> "MainWizard":
        wizard = super().wizard()
        if not isinstance(wizard, MainWizard):
            raise RuntimeError(
                "RC MetaStudio wizard pages require MainWizard ownership"
            )
        return wizard


class WelcomePage(MainWizardPage, forms.ui_welcome_page.Ui_WizardPage):
    def __init__(self, parent=None, recent_datasets=[]):
        super(WelcomePage, self).__init__(parent)
        self.setupUi(self)

        self.recent_datasets = recent_datasets
        self.selected_dataset = None
        qt_layout.configure_primary_action_buttons(
            (
                self.create_new_btn,
                self.import_csv_btn,
                self.open_recent_btn,
                self.open_btn,
            )
        )
        self._setup_connections()

    def initializePage(self):
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
                action_item.triggered[bool].connect(
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
        action = action_item or self.sender()
        if not isinstance(action, QAction):
            raise RuntimeError("recent-project selection requires a QAction sender")
        dataset_path = action.text()
        dataset_path = qt_text.to_native_text(dataset_path)
        self.selected_dataset = dataset_path
        self.wizard().set_selected_dataset(self.selected_dataset)
        self.wizard().accept()

    def open_dataset(self):
        self.wizard().set_wizard_path("open")

        self.selected_dataset = QFileDialog.getOpenFileName(
            parent=self,
            caption="RCMetaStudio - Open Project",
            directory=get_default_open_directory(self.recent_datasets),
            filter="RC MetaStudio Project (*.rcms)",
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


class DataTypePage(MainWizardPage, forms.ui_data_type_page.Ui_DataTypePage):
    _ICON_NAMES = {
        "onearm_proportion_Button": "one-arm-proportion.svg",
        "onearm_mean_Button": "one-arm-mean.svg",
        "onearm_single_reg_coef_Button": "single-regression-coefficient.svg",
        "onearm_generic_effect_size_Button": "generic-effect-size.svg",
        "twoarm_proportions_Button": "two-arm-proportions.svg",
        "twoarm_means_Button": "two-arm-means.svg",
        "twoarm_smds_Button": "standardized-mean-difference.svg",
        "diagnostic_Button": "diagnostic-data.svg",
    }

    def __init__(self, parent=None):
        super(DataTypePage, self).__init__(parent)
        self.setupUi(self)

        self.selected_datatype = None
        self.summary: DatasetInfo = dict(
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

        self._configure_data_type_buttons()

    def initializePage(self):
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

    def _configure_data_type_buttons(self):
        buttons = self._data_type_buttons()
        self._data_type_icon_themes = {}
        for button in buttons:
            self._apply_theme_icon(button)
            button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
            self._reserve_button_icon_and_text_height(button)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.installEventFilter(self)
        self.diagnostic_Button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self.diagnosticDataTypeLayout.setStretch(0, 1)
        self.diagnosticDataTypeLayout.setStretch(1, 1)
        for current, following in zip(buttons, buttons[1:]):
            self.setTabOrder(current, following)

    def eventFilter(  # ty: ignore[invalid-method-override] -- PyQt6 stub rejects the binding's valid override
        self,
        watched: QObject | None,
        event: QEvent | None,
    ) -> bool:
        if (
            event is not None
            and event.type() == QEvent.Type.PaletteChange
            and isinstance(watched, QAbstractButton)
            and watched in self._data_type_buttons()
        ):
            self._apply_theme_icon(watched)
        return super().eventFilter(watched, event)

    def _reserve_button_icon_and_text_height(self, button):
        """Keep multiline Required Content below the icon at native font scales."""
        line_count = max(1, len(button.text().splitlines()))
        text_height = line_count * button.fontMetrics().lineSpacing()
        margin = max(
            0,
            button.style().pixelMetric(
                QStyle.PixelMetric.PM_ButtonMargin, None, button
            ),
        )
        frame = max(
            0,
            button.style().pixelMetric(
                QStyle.PixelMetric.PM_DefaultFrameWidth, None, button
            ),
        )
        required = QSize(
            button.sizeHint().width(),
            button.iconSize().height() + text_height + (2 * margin) + (2 * frame),
        )
        # layout-audit: allow=style-metric-control; reason=icon and multiline Required Content need a native-metric minimum
        button.setMinimumSize(button.minimumSizeHint().expandedTo(required))

    def _apply_theme_icon(self, button):
        foreground = button.palette().color(QPalette.ColorRole.ButtonText)
        theme = "dark" if foreground.lightness() >= 128 else "light"
        icon_name = self._ICON_NAMES.get(button.objectName())
        if not icon_name:
            return
        self._data_type_icon_themes[button.objectName()] = theme
        button.setIcon(QIcon(f":/icons/dataset-types/{theme}/{icon_name}"))

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
            self.summary["sub_type"] = "generic_effect"
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
        if self.buttonGroup.checkedButton() is None:
            return Page_ChooseMetric
        dataset_info = self.wizard().get_dataset_info()
        if dataset_info is not None and dataset_info["data_type"] == "diagnostic":
            return Page_OutcomeName
        else:  # normal case
            return Page_ChooseMetric


###############################################################################
class ChooseMetricPage(MainWizardPage, forms.ui_choose_metric_page.Ui_WizardPage):
    def __init__(self, parent=None):
        super(ChooseMetricPage, self).__init__(parent)
        self.setupUi(self)

        self.metric_cbo_box.currentIndexChanged[int].connect(
            app_error_handler.safe_slot(self._metric_choice_changed, parent=self)
        )

    def initializePage(self):
        dataset_info = self.wizard().require_dataset_info()
        data_type = dataset_info["data_type"]
        metric_choices = dataset_info["metric_choices"]
        default_effect = dataset_info["effect"]

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
            self.metric_cbo_box.blockSignals(False)

    def _metric_choice_changed(self, newindex):
        self.wizard().set_effect(_qt_item_text(self.metric_cbo_box.itemData(newindex)))

    def nextId(self):
        return Page_OutcomeName


###############################################################################

import csv


def _qt_item_text(value):
    return qt_text.to_native_text(value)


class CsvImportPage(MainWizardPage, forms.ui_csv_import_page.Ui_WizardPage):
    def __init__(self, parent=None):
        super(CsvImportPage, self).__init__(parent)
        self.setupUi(self)

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
                item = self.required_fmt_table.item(row, col)
                if item is None:
                    raise RuntimeError("CSV format preview item was not created")
                item.setFlags(Qt.ItemFlag.NoItemFlags)
        qt_layout.configure_compact_table(self.required_fmt_table, stretch_columns=True)

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
            caption="RCMetaStudio - Import CSV",
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
                    item.setFlags(Qt.ItemFlag.NoItemFlags)
                    self.preview_table.setItem(row, col, item)
            self.preview_table.resizeColumnsToContents()
            self.preview_table.resizeRowsToContents()
            qt_layout.configure_compact_table(self.preview_table, stretch_columns=True)

            # Validate table entries
            self._validate_imported_data()
            self.completeChanged.emit()
        except Exception as e:
            QMessageBox.warning(
                self,
                "Could not import CSV",
                "RC MetaStudio could not preview the selected CSV file.\n\n"
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

        dataset_info = self.wizard().require_dataset_info()
        data_type = dataset_info["data_type"]
        data_subtype = dataset_info["sub_type"]
        effect = dataset_info["effect"]
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
            return None

    def _handle_covariates_in_extracted_data(
        self, num_rows, num_cols, headers=[], expected_headers=[]
    ):
        if num_cols > len(expected_headers):  # Do we have covariates?
            num_covariates = num_cols - len(expected_headers)
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
        self.print_extracted_data()

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
        for row in self.imported_data:
            pass

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
class OutcomeNamePage(MainWizardPage, forms.ui_outcome_name_page.Ui_WizardPage):
    def __init__(self, parent=None):
        super(OutcomeNamePage, self).__init__(parent)
        self.setupUi(self)

        self.registerField("outcomeName*", self.outcome_name_LineEdit)

    def initializePage(self):
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
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        self.setButtonLayout(
            [
                QWizard.WizardButton.Stretch,
                QWizard.WizardButton.BackButton,
                QWizard.WizardButton.NextButton,
                QWizard.WizardButton.FinishButton,
                QWizard.WizardButton.CancelButton,
            ]
        )

        self.info_d: dict[str, object] = {}
        self._outcome_info: DatasetInfo | None = None
        self.info_d["path"] = path
        self.setPage(Page_Welcome, WelcomePage(recent_datasets=recent_datasets))
        self.setPage(Page_DataType, DataTypePage())
        self.setPage(Page_ChooseMetric, ChooseMetricPage())
        self.setPage(Page_OutcomeName, OutcomeNamePage())
        self.setPage(Page_CsvImport, CsvImportPage())

        if path is None:
            self.setStartId(Page_Welcome)
            self.setWindowTitle("RCMetaStudio")
        elif path == "csv_import":
            self.setStartId(Page_DataType)
            self.setWindowTitle("Import a CSV")
        elif path == "new_dataset":
            self.setStartId(Page_DataType)
            self.setWindowTitle("Create a New Dataset")

        self._layout_controller = adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.WORKFLOW
        )
        self._focus_reveal_connected = False
        self.currentIdChanged.connect(self._schedule_default_action_sync)
        for page_id in self.pageIds():
            page = self.page(page_id)
            if page is None:
                raise RuntimeError(f"MainWizard is missing registered page {page_id}")
            page.completeChanged.connect(self._schedule_default_action_sync)

    def showEvent(  # ty: ignore[invalid-method-override] -- PyQt6's QWizard and inherited QDialog stubs conflict for this runtime-supported override.
        self, event: QShowEvent | None
    ) -> None:
        """Scope focus observation to the wizard's visible lifetime."""
        if event is None:
            return
        super(MainWizard, self).showEvent(event)
        self._schedule_default_action_sync()
        app = QApplication.instance()
        if isinstance(app, QApplication) and not self._focus_reveal_connected:
            app.focusChanged.connect(self._reveal_focused_control)
            self._focus_reveal_connected = True

    def _schedule_default_action_sync(self, _page_id=None):
        """Restore the visible forward action as the dialog's Return default."""
        QTimer.singleShot(0, self._synchronize_default_action)

    def _synchronize_default_action(self):
        forward_buttons = [
            self.button(QWizard.WizardButton.NextButton),
            self.button(QWizard.WizardButton.FinishButton),
        ]
        for button in forward_buttons:
            if isinstance(button, QPushButton):
                button.setDefault(False)
        for button in forward_buttons:
            if (
                isinstance(button, QPushButton)
                and button.isVisible()
                and button.isEnabled()
            ):
                button.setAutoDefault(True)
                button.setDefault(True)
                break

    def hideEvent(  # ty: ignore[invalid-method-override] -- PyQt6's QWizard and inherited QWidget stubs conflict for this runtime-supported override.
        self, event: QHideEvent | None
    ) -> None:
        self._disconnect_focus_reveal()
        if event is None:
            return
        super(MainWizard, self).hideEvent(event)

    def closeEvent(  # ty: ignore[invalid-method-override] -- PyQt6's QWizard and inherited QDialog stubs conflict for this runtime-supported override.
        self, event: QCloseEvent | None
    ) -> None:
        self._disconnect_focus_reveal()
        if event is None:
            return
        super(MainWizard, self).closeEvent(event)

    def _disconnect_focus_reveal(self):
        if not self._focus_reveal_connected:
            return
        app = QApplication.instance()
        if isinstance(app, QApplication):
            try:
                app.focusChanged.disconnect(self._reveal_focused_control)
            except (TypeError, RuntimeError):
                pass
        self._focus_reveal_connected = False

    def _reveal_focused_control(self, _previous, current):
        """Keep keyboard focus reachable within the current Overflow Boundary."""
        page = self.currentPage()
        if page is None or current is None:
            return
        overflow = page.findChild(QScrollArea, "pageScrollArea")
        overflow_content = overflow.widget() if overflow is not None else None
        if (
            overflow is not None
            and overflow_content is not None
            and overflow_content.isAncestorOf(current)
        ):
            overflow.ensureWidgetVisible(current)

    def set_wizard_path(self, path):
        self.info_d["path"] = path

    def get_wizard_path(self):
        if "path" in self.info_d:
            return self.info_d["path"]
        else:
            return None

    def set_dataset_info(self, outcome_info: DatasetInfo) -> None:
        self._outcome_info = outcome_info

    def get_dataset_info(self) -> DatasetInfo | None:
        return self._outcome_info

    def require_dataset_info(self) -> DatasetInfo:
        if self._outcome_info is None:
            raise RuntimeError("dataset information has not been selected")
        return self._outcome_info

    def set_selected_dataset(self, dataset):
        self.info_d["selected_dataset"] = dataset

    def get_selected_dataset(self):
        if "selected_dataset" in self.info_d:
            return self.info_d["selected_dataset"]
        else:
            return None

    def set_effect(self, effect_name):
        self.require_dataset_info()["effect"] = effect_name

    def get_effect(self):
        return self.require_dataset_info()["effect"]

    def set_csv_data(self, csv_data):
        self.info_d["csv_data"] = csv_data

    def get_csv_data(self):
        if "csv_data" in self.info_d:
            return self.info_d["csv_data"]
        else:
            return None

    def get_results(self):
        information: dict[str, object] = {}
        path = self.get_wizard_path()
        outcome_info = self.get_dataset_info()
        if path in {"new_dataset", "csv_import"} and outcome_info is None:
            raise RuntimeError(
                f"dataset information is required for the {path!r} wizard path"
            )
        information["path"] = path
        information["outcome_info"] = outcome_info
        # set outcome name
        if outcome_info is not None:
            outcome_info["name"] = _qt_item_text(self.field("outcomeName"))
        information["selected_dataset"] = self.get_selected_dataset()
        information["csv_data"] = self.get_csv_data()

        return information


if __name__ == "__main__":
    import sys

    app = app_error_handler.get_or_create_application(sys.argv)
    wizard = MainWizard()
    wizard.show()
    sys.exit(app.exec())
