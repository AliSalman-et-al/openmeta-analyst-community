# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Main RC MetaStudio desktop window."""

from __future__ import annotations

import os
from functools import cmp_to_key
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QCloseEvent, QKeyEvent, QKeySequence, QResizeEvent, QTextDocument, QUndoCommand
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QLabel,
    QMessageBox,
    QTableView,
)
import copy
from typing import cast

## hand-rolled modules
import ui_meta
import ma_data_table_view
import ma_data_table_model
import meta_globals
from meta_globals import *
import ma_dataset
import app_error_handler
import meta_py_r_backend
import progress_bar as progress_dialog
import qt_layout
import adaptive_window
import qt_text
import name_validation
import project_adapter
import project_format
import tabular_data
from settings import *
from runtime_types import required

# additional forms
import add_new_dialogs
import results_window
import ma_specs
import diag_metrics
import meta_subgroup_form
import edit_dialog
import edit_group_name_form
import change_cov_type_form
import network_view
import conf_level_dialog
import main_wizard
import about_legal_dialog

import forms.ui_running


def _qt_item_text(value):
    return qt_text.to_native_text(value)


def _resolve_open_file_path(file_path):
    if file_path in [None, ""] or os.path.exists(file_path):
        return file_path

    normalized_path = os.path.normpath(file_path).replace("/", os.sep)
    path_parts = [part.lower() for part in normalized_path.split(os.sep)]
    if "sample_projects" not in path_parts:
        return file_path

    sample_file = os.path.basename(file_path)
    candidates = [
        os.path.join(get_sample_projects_path(), sample_file),
        os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), os.pardir, "sample_projects", sample_file
            )
        ),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    return file_path


def _load_structured_project(file_path):
    document = project_format.load_project(file_path)
    dataset = project_adapter.project_to_dataset(document.project)
    state = project_adapter.state_to_model_state(dataset, document.state)
    restored_selection = document.state["active_outcome"] is not None
    return dataset, state, restored_selection


class InvalidProjectFileError(ValueError):
    pass


def _validate_open_project_dataset(dataset):
    if isinstance(dataset, ma_dataset.Dataset):
        return dataset
    raise InvalidProjectFileError(
        "This file is not a valid RC MetaStudio project file."
    )


def _format_open_project_error(file_path, exception):
    if isinstance(
        exception,
        (
            InvalidProjectFileError,
            project_adapter.ProjectAdapterError,
            project_format.ProjectFormatError,
        ),
    ):
        return "Could not open %s.\n\n%s" % (file_path, exception)
    return "Could not open %s.\n\nDetails: %s: %s" % (
        file_path,
        exception.__class__.__name__,
        exception,
    )


def _qt_dialog_path(value):
    value = value[0] if isinstance(value, tuple) else value
    return qt_text.to_native_text(value)


def _qt_text(value):
    return qt_text.to_native_text(value)


def _connect_action(action, callback):
    parent = getattr(callback, "__self__", None)
    action.triggered[bool].connect(
        app_error_handler.safe_slot(lambda checked=False: callback(), parent=parent)
    )


def _format_confidence_level_status(conf_level):
    if conf_level is None:
        return "Confidence Level: not set"
    return "Confidence Level: {:.1%}".format(float(conf_level) / 100.0)


class ElidingStatusLabel(QLabel):
    """A status label whose content cannot claim window geometry."""

    def __init__(self, text="", parent=None):
        super(ElidingStatusLabel, self).__init__(parent)
        self._full_text = ""
        # layout-audit: allow=content-overflow-control; reason=required content may consume available layout width
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setText(text)

    def setText(  # ty: ignore[invalid-method-override] -- PyQt6's QLabel overload stubs conflict with this semantic text override.
        self, text: str | None
    ) -> None:
        text = qt_text.to_native_text(text)
        if "<" in text and ">" in text:
            document = QTextDocument()
            document.setHtml(text)
            text = document.toPlainText()
        self._full_text = text
        self.setToolTip(self._full_text)
        self._refresh_elision()

    def text(self):
        """Return the semantic status text, not its width-dependent paint form."""

        return self._full_text

    def resizeEvent(  # ty: ignore[invalid-method-override] -- PyQt6's QLabel and QWidget stubs conflict for this runtime-supported override.
        self, event: QResizeEvent | None
    ) -> None:
        super(ElidingStatusLabel, self).resizeEvent(event)
        self._refresh_elision()

    def _refresh_elision(self):
        width = max(0, self.contentsRect().width())
        elided = self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideRight, width)
        QLabel.setText(self, elided)


class ImportProgress(QDialog, forms.ui_running.Ui_running):
    def __init__(self, parent=None, min_=0, max_=10):
        super(ImportProgress, self).__init__(parent)
        self.setupUi(self)

        self.setWindowTitle("Importing from CSV...")
        self.progress_bar.setRange(min_, max_)
        self._layout_controller = adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSIENT
        )

    def setValue(self, value):
        if self.progress_bar.minimum() <= value <= self.progress_bar.maximum():
            self.progress_bar.setValue(value)

    def minimum(self):
        return self.progress_bar.minimum()

    def maximum(self):
        return self.progress_bar.maximum()

    def value(self):
        return self.progress_bar.value()


###############################################################################


class MetaForm(QtWidgets.QMainWindow, ui_meta.Ui_MainWindow):
    model: ma_data_table_model.DatasetModel
    tableView: ma_data_table_view.MADataTable

    def __init__(self, parent=None):
        # We follow the advice given by Mark Summerfield in his Python QT book:
        # Namely, we use multiple inheritance to gain access to the ui. We take
        # this approach throughout the application.
        super(MetaForm, self).__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setupUi(self)
        qt_layout.configure_analysis_menu(self.menuAnalysis)
        for action, icon_name in (
            (self.action_go, "meta-analysis"),
            (self.action_cum_ma, "cumulative-analysis"),
            (self.action_loo_ma, "leave-one-out-analysis"),
            (self.action_subgroup_ma, "subgroup-analysis"),
            (self.action_meta_regression, "meta-regression"),
        ):
            qt_layout.configure_analysis_action_icon(action, icon_name)
        qt_layout.configure_main_toolbar(self.toolBar)
        dataset_file_label = ElidingStatusLabel(
            self.dataset_file_lbl.text(), self.centralwidget
        )
        self.verticalLayout_3.replaceWidget(self.dataset_file_lbl, dataset_file_label)
        self.dataset_file_lbl.deleteLater()
        self.dataset_file_lbl = dataset_file_label
        qt_layout.configure_navigation_tool_buttons(
            (
                self.nav_left_btn,
                self.nav_up_btn,
                self.nav_down_btn,
                self.nav_right_btn,
                self.nav_add_btn,
            )
        )
        adaptive_window.register_adaptive_window(self, adaptive_window.WindowRole.MAIN)
        table_view = ma_data_table_view.MADataTable(self.nav_frame)
        self.verticalLayout.replaceWidget(self.tableView, table_view)
        self.tableView.deleteLater()
        self.tableView = table_view
        self.tableView.restore_column_widths(load_main_column_widths())

        self.cl_label = ElidingStatusLabel(
            _format_confidence_level_status(meta_globals.DEFAULT_CONF_LEVEL)
        )
        self.cl_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.statusbar.addWidget(self.cl_label, 1)

        # Command-line dataset loading can be added here if headless startup
        # needs to open a project directly in the GUI.
        self.new_dataset()

        # flag maintaining whether the current dataset
        # has been saved
        self.current_data_unsaved = False

        self.tableView.setModel(self.model)
        # attach a delegate for editing
        self.tableView.setItemDelegate(ma_data_table_view.StudyDelegate(self.tableView))

        # the nav_lbl text corresponds to the currently selected
        # 'dimension', e.g., outcome or treatment. New points
        # can then be added to this dimension, or it can be traveled
        # along using the horizontal nav arrows (the vertical arrows
        # navigate along the *dimensions*)
        self.dimensions = ["outcome", "follow-up", "group"]
        self.cur_dimension_index = 0
        self.update_dimension()
        self._model_signal_connections = []
        self._setup_connections()
        self.tableView.undoStack.cleanChanged.connect(self._undo_clean_changed)
        self._configure_standard_shortcuts()
        self.tableView.setSelectionMode(QTableView.SelectionMode.ContiguousSelection)
        self.model.reset_model()
        ##
        # we hand off a reference of the main gui to the table view
        # so that it can do things like pass suitable events 'up'
        # to the main form
        self.tableView.main_gui = cast(ma_data_table_view.MainGuiProtocol, self)
        self.tableView.synchronize_column_widths()

        self.out_path = None  # path to output file
        self.metric_menu_is_set_for = None  # BINARY, CONTINUOUS, or DIAGNOSTIC

        # by default, disable meta-regression (until we have covariates)
        self.action_meta_regression.setEnabled(False)

        load_settings()
        self.populate_open_recent_menu()

        if DISABLE_NETWORK_STUFF:
            self.action_view_network.setEnabled(False)
        else:
            self.action_view_network.setEnabled(False)

    def createPopupMenu(self):
        return None

    def start(self):
        # show the welcome dialog
        start_up_wizard = main_wizard.MainWizard(
            parent=self, recent_datasets=get_setting("recent_files")
        )

        if start_up_wizard.exec():
            wizard_data = start_up_wizard.get_results()
            self._handle_wizard_results(wizard_data)

    def closeEvent(  # ty: ignore[invalid-method-override] -- PyQt6's QMainWindow and QWidget stubs conflict for this runtime-supported override.
        self, event: QCloseEvent | None
    ) -> None:
        if event is None:
            return
        if not self._confirm_close():
            event.ignore()
            return
        self._disconnections()
        save_main_window_placement(self, self.tableView.column_width_state())
        save_settings()
        event.accept()

    def _confirm_close(self):
        if not self.current_data_unsaved:
            return True
        choice = self.prompt_to_save_unsaved_data()
        if choice == QMessageBox.StandardButton.Yes:
            return self.save() is True
        return choice == QMessageBox.StandardButton.No

    def _authorize_destructive_project_action(self):
        """Return whether New/Open/Import may replace the current project."""

        if not self.current_data_unsaved:
            return True
        choice = self.prompt_to_save_unsaved_data()
        if choice == QMessageBox.StandardButton.Yes:
            return self.save() is True
        return choice == QMessageBox.StandardButton.No

    def _capture_project_install_state(self):
        action_states = {
            action: action.isEnabled()
            for action in (
                self.action_go,
                self.action_cum_ma,
                self.action_loo_ma,
                self.action_meta_regression,
                self.action_subgroup_ma,
            )
        }
        current = self.tableView.currentIndex()
        return {
            "model": self.model,
            "table_model": self.tableView.model(),
            "out_path": self.out_path,
            "dirty": self.current_data_unsaved,
            "dataset_label": self.dataset_file_lbl.text(),
            "outcome_label": self.cur_outcome_lbl.text(),
            "follow_up_label": self.cur_time_lbl.text(),
            "confidence_label": self.cl_label.text(),
            "metric_menu_type": self.metric_menu_is_set_for,
            "metric_menu": self._capture_metric_menu_state(),
            "action_states": action_states,
            "current_index": (current.row(), current.column()),
            "selection": [
                (index.row(), index.column())
                for index in required(self.tableView.selectionModel(), "workspace selection model").selectedIndexes()
            ],
        }

    def _capture_metric_menu_state(self):
        submenus = []
        for menu_action in self.menuMetric.actions():
            submenu = menu_action.menu()
            if submenu is None:
                continue
            submenus.append(
                {
                    "title": submenu.title(),
                    "actions": [
                        {
                            "metric": _qt_item_text(action.data()),
                            "checked": action.isChecked(),
                            "enabled": action.isEnabled(),
                        }
                        for action in submenu.actions()
                    ],
                }
            )
        return {"enabled": self.menuMetric.isEnabled(), "submenus": submenus}

    def _restore_metric_menu_state(self, snapshot):
        self.menuMetric.clear()
        self.menuMetric.setEnabled(snapshot["enabled"])
        for submenu_state in snapshot["submenus"]:
            submenu = self.add_sub_metric_menu(submenu_state["title"])
            if submenu_state["title"] == "two-arm":
                self.twoArmMetricMenu = submenu
            elif submenu_state["title"] == "one-arm":
                self.oneArmMetricMenu = submenu
            for action_state in submenu_state["actions"]:
                action = self.add_metric_action(action_state["metric"], submenu)
                action.blockSignals(True)
                action.setChecked(action_state["checked"])
                action.setEnabled(action_state["enabled"])
                action.blockSignals(False)

    def _restore_project_install_state(self, previous, primary_error):
        rollback_errors = []

        def guarded(phase, operation):
            try:
                operation()
            except Exception as exc:
                rollback_errors.append((phase, exc))

        old_model = previous["model"]
        if self.model is not old_model:
            def disconnect_candidate():
                for connection in self._model_signal_connections:
                    try:
                        connection.disconnect()
                    except Exception as exc:
                        rollback_errors.append(("disconnect candidate signal", exc))
                self._model_signal_connections = []

            guarded("disconnect candidate model", disconnect_candidate)
            guarded(
                "restore table model",
                lambda: QTableView.setModel(self.tableView, previous["table_model"]),
            )
            self.model = old_model
            guarded(
                "restore model signal connections",
                lambda: self._setup_connections(menu_actions=False),
            )
        self.out_path = previous["out_path"]
        self.current_data_unsaved = previous["dirty"]
        guarded(
            "restore project label",
            lambda: self.dataset_file_lbl.setText(previous["dataset_label"]),
        )
        guarded(
            "restore outcome label",
            lambda: self.cur_outcome_lbl.setText(previous["outcome_label"]),
        )
        guarded(
            "restore follow-up label",
            lambda: self.cur_time_lbl.setText(previous["follow_up_label"]),
        )
        guarded(
            "restore Confidence Level label",
            lambda: self.cl_label.setText(previous["confidence_label"]),
        )
        self.metric_menu_is_set_for = previous["metric_menu_type"]
        guarded(
            "restore metric menu",
            lambda: self._restore_metric_menu_state(previous["metric_menu"]),
        )
        for action, enabled in previous["action_states"].items():
            guarded(
                "restore action availability",
                lambda action=action, enabled=enabled: action.setEnabled(enabled),
            )

        def restore_selection():
            selection_model = required(self.tableView.selectionModel(), "workspace selection model")
            selection_model.clearSelection()
            for row, column in previous["selection"]:
                selection_model.select(
                    old_model.index(row, column),
                    QtCore.QItemSelectionModel.SelectionFlag.Select,
                )
            row, column = previous["current_index"]
            if row >= 0 and column >= 0:
                self.tableView.setCurrentIndex(old_model.index(row, column))

        guarded("restore table selection", restore_selection)
        for phase, exc in rollback_errors:
            primary_error.add_note(f"rollback {phase} also failed: {exc}")
            try:
                app_error_handler.log_exception(type(exc), exc, exc.__traceback__)
            except Exception:
                pass

    def _update_recent_project_nonfatal(self, path, operation):
        try:
            add_file_to_recent_files(path)
            self.populate_open_recent_menu()
        except Exception as exc:
            try:
                app_error_handler.log_exception(type(exc), exc, exc.__traceback__)
            except Exception:
                pass
            try:
                QMessageBox.warning(
                    self,
                    "Recent Projects Not Updated",
                    "The project was %s successfully, but RC MetaStudio could not "
                    "update the machine-local recent-project list.\n\nDetails: %s: %s"
                    % (operation, exc.__class__.__name__, exc),
                )
            except Exception:
                pass

    def _report_durability_uncertain_save(self, destination, exception):
        try:
            app_error_handler.log_exception(
                type(exception), exception, exception.__traceback__
            )
        except Exception:
            pass
        try:
            QMessageBox.warning(
                self,
                "Project Saved; Durability Uncertain",
                "RC MetaStudio installed the saved project at %s, but the operating "
                "system could not confirm final directory durability. The document "
                "is treated as saved so later actions do not discard work by retrying "
                "a replacement.\n\nDetails: %s"
                % (destination, exception),
            )
        except Exception:
            pass

    def _configure_standard_shortcuts(self):
        """Use platform-native shortcuts for the maintained shell actions."""
        for action, standard_key in (
            (self.action_new_dataset, QKeySequence.StandardKey.New),
            (self.action_open, QKeySequence.StandardKey.Open),
            (self.action_save, QKeySequence.StandardKey.Save),
            (self.action_quit, QKeySequence.StandardKey.Quit),
        ):
            action.setShortcut(QKeySequence(standard_key))

    def _model_about_to_be_reset(self):
        """Call all the functions here that should be called when the model is
        about to be reset"""
        self._recalculate_display_scale_values()

    def _recalculate_display_scale_values(self):
        print("got to recalc disp scale values")

        self.tableView.model().recalculate_display_scale()

    def create_new_dataset(self, use_undo_framework=True):
        if not self._authorize_destructive_project_action():
            return

        wizard = main_wizard.MainWizard(parent=self, path="new_dataset")
        if wizard.exec():
            wizard_data = wizard.get_results()
            self._handle_wizard_results(wizard_data)

    def new_dataset(
        self, name=DEFAULT_DATASET_NAME, is_diag=False, use_undo_framework=True
    ):

        data_model = ma_dataset.Dataset(title=name, is_diag=is_diag)
        existing_model = getattr(self, "model", None)
        if existing_model is not None:
            if use_undo_framework:
                original_dataset = copy.deepcopy(existing_model.dataset)
                old_state_dict = self.tableView.model().get_stateful_dict()
                undo_f = lambda: self.set_model(original_dataset, old_state_dict)
                redo_f = lambda: self.set_model(data_model)
                edit_command = meta_globals.CommandGenericDo(redo_f, undo_f)
                self.tableView.undoStack.push(edit_command)
            else:  # CSV import manages its own undo boundary.
                self.set_model(data_model)
        else:
            self.model = ma_data_table_model.DatasetModel(dataset=data_model)
            # no dataset; disable saving, editing, etc.
            self.disable_menu_options_that_require_dataset()
        # set the out_path to None; this (new) dataset is unsaved.
        self.out_path = None

    def _notify_user_that_data_is_unsaved(self):
        if self.out_path is None:
            self.dataset_file_lbl.setText(
                "<font color='red'>careful! your data isn't saved yet</font>"
            )
        else:
            self.dataset_file_lbl.setText(
                "Open Project: <font color='red'>%s</font>" % self.out_path
            )

    def toggle_menu_options_that_require_dataset(self, enable):
        self.action_go.setEnabled(enable)
        self.action_cum_ma.setEnabled(enable)
        self.action_loo_ma.setEnabled(enable)
        self._enable_action_meta_regression(enable)
        self._enable_action_subgroup_ma(enable)

    def _enable_action_meta_regression(self, dataset_analysis_enabled=None):
        """Enables action_meta_regression if analysis can run and covariates exist."""
        if dataset_analysis_enabled is None:
            dataset_analysis_enabled = self.action_go.isEnabled()
        has_covariates = bool(self.model and self.model.dataset.covariates)
        self.action_meta_regression.setEnabled(
            dataset_analysis_enabled and has_covariates
        )

    def _enable_action_subgroup_ma(self, dataset_analysis_enabled=None):
        """Enables action_subgroup_ma if there are suitable covariate(s)
        i.e. of type Factor"""
        if dataset_analysis_enabled is None:
            dataset_analysis_enabled = self.action_go.isEnabled()
        has_factor_covariates = bool(
            self.model
            and any(
                cov.get_data_type() == meta_globals.FACTOR
                for cov in self.model.dataset.covariates
            )
        )
        self.action_subgroup_ma.setEnabled(
            dataset_analysis_enabled and has_factor_covariates
        )

    def disable_menu_options_that_require_dataset(self):
        self.toggle_menu_options_that_require_dataset(False)

    def enable_menu_options_that_require_dataset(self):
        self.toggle_menu_options_that_require_dataset(True)

    def keyPressEvent(  # ty: ignore[invalid-method-override] -- PyQt6's QMainWindow and QWidget stubs conflict for this runtime-supported override.
        self, event: QKeyEvent | None
    ) -> None:
        if event is None:
            return
        if event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            if event.key() == QtCore.Qt.Key.Key_S:
                # ctrl + s = save
                print("saving..")
                self.save()
            elif event.key() == QtCore.Qt.Key.Key_O:
                # ctrl + o = open
                self.open()

    def _disconnections(self):
        """
        disconnects model-related signs/slots. this should be called prior to swapping
        in a new model, e.g., when a dataset is loaded, to tear down the relevant connections.
        _setup_connections (with menu_actiosn set to False) should subsequently be invoked.
        """

        for connection in self._model_signal_connections:
            connection.disconnect()
        self._model_signal_connections = []

    def data_error(self, msg):
        QMessageBox.warning(self, "Warning", msg)

    def set_edit_focus(self, index):
        """sets edit focus to the row,col specified by index."""
        if not index.isValid():
            return
        self.tableView.setCurrentIndex(index)
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        self.tableView.edit(index)

    def populate_open_recent_menu(self):
        recent_datasets = get_setting("recent_files")
        recent_datasets.reverse()  # most-recent first
        # qt designer inexplicably forcing the _2. not sure why;
        # gave up struggling with it. grr.
        self.action_open_recent_2.clear()
        for dataset in recent_datasets:
            action_item = QAction(str(dataset), self.action_open_recent_2)
            self.action_open_recent_2.addAction(action_item)
            _connect_action(
                action_item, lambda dataset=dataset: self.dataset_selected(dataset)
            )

    def dataset_selected(self, dataset_path):
        self.open(file_path=dataset_path)

    def _change_global_ci(self):
        print("Changing global confidence level:")
        prev_conf_level = self.model.get_global_conf_level()

        dialog = conf_level_dialog.ChangeConfLevelDlg(prev_conf_level, self)
        if dialog.exec():
            new_conf_level = dialog.get_value()
            change_cl_command = Command_Change_Conf_Level(
                prev_conf_level, new_conf_level, mainform=self
            )
            self.tableView.undoStack.push(change_cl_command)

    def _import_csv(self):
        """Import data from csv file"""
        if not self._authorize_destructive_project_action():
            return
        wizard = main_wizard.MainWizard(parent=self, path="csv_import")
        if wizard.exec():
            wizard_data = wizard.get_results()
            self._handle_wizard_results(wizard_data)

    def _setup_connections(self, menu_actions=True):
        """Signals & slots"""
        model = self.tableView.model()
        self._model_signal_connections.append(
            app_error_handler.connect_safely(
                model.workspaceEditCommitted,
                self.tableView.cell_content_changed,
                parent=self,
            )
        )
        self._model_signal_connections.append(
            app_error_handler.connect_safely(
                model.outcomeChanged,
                self.tableView.displayed_ma_changed,
                parent=self,
            )
        )
        self._model_signal_connections.append(
            app_error_handler.connect_safely(
                model.followUpChanged,
                self.tableView.displayed_ma_changed,
                parent=self,
            )
        )

        ###
        # this is not ideal, but I couldn't get the rowsInserted methods working.
        # basically, the modelReset (which is custom to this app; not a QT thing, per se)
        # is emitted when a model refresh was called but the edit focus should be set back to
        # where it was before this refresh (refresh clears the current editor).
        # this index is the QModelIndex. this is used, e.g., when a new study is added.
        # Restore focus after model refreshes that clear the current editor.
        self._model_signal_connections.append(
            app_error_handler.connect_safely(
                model.editFocusRequested, self.set_edit_focus, parent=self
            )
        )

        # Recalculate display-scale values before model resets.
        self._model_signal_connections.append(
            app_error_handler.connect_safely(
                model.modelAboutToBeReset, self._model_about_to_be_reset, parent=self
            )
        )

        ###
        # this listens to the model regarding errors in data entry --
        # such data will be rejected (e.g., strings for counts, or whatever),
        # and this hook allows the model to pass along error messages to the
        # user. the data checking happens in ma_dataset (specifically, in the
        # setData method)
        self._model_signal_connections.append(
            app_error_handler.connect_safely(
                model.dataError, self.data_error, parent=self
            )
        )

        self._model_signal_connections.append(
            app_error_handler.connect_safely(
                self.tableView.dataDirtied, self.data_dirtied, parent=self
            )
        )
        if menu_actions:
            self.nav_add_btn.pressed.connect(
                app_error_handler.safe_slot(self.add_new, parent=self)
            )
            self.nav_right_btn.pressed.connect(
                app_error_handler.safe_slot(self.next, parent=self)
            )
            self.nav_left_btn.pressed.connect(
                app_error_handler.safe_slot(self.previous, parent=self)
            )
            self.nav_up_btn.pressed.connect(
                app_error_handler.safe_slot(self.next_dimension, parent=self)
            )
            self.nav_down_btn.pressed.connect(
                app_error_handler.safe_slot(self.previous_dimension, parent=self)
            )

            _connect_action(self.action_save, self.save)
            _connect_action(self.action_save_as, self.save_as)
            _connect_action(self.action_open, self.open)
            _connect_action(self.action_new_dataset, self.create_new_dataset)
            _connect_action(self.action_quit, self.quit)
            _connect_action(self.action_go, self.go)
            _connect_action(self.action_cum_ma, self.cum_ma)
            _connect_action(self.action_loo_ma, self.loo_ma)

            _connect_action(self.action_undo, self.undo)
            _connect_action(self.action_redo, self.redo)
            _connect_action(self.action_copy, self.tableView.copy)
            _connect_action(self.action_paste, self.tableView.paste)
            _connect_action(
                self.action_auto_fit_columns, self.tableView.auto_fit_columns
            )

            _connect_action(self.action_edit, self.edit_dataset)
            _connect_action(self.action_view_network, self.view_network)
            _connect_action(self.action_add_covariate, self.add_covariate)

            _connect_action(self.action_meta_regression, self.meta_reg)
            _connect_action(self.action_subgroup_ma, self.meta_subgroup_get_cov)

            _connect_action(self.action_about_legal, self.show_about_legal)
            _connect_action(self.action_change_conf_level, self._change_global_ci)
            _connect_action(self.action_import_csv, self._import_csv)

    def _change_conf_level_label(self):
        conf_level = self.model.get_global_conf_level()
        self.cl_label.setText(_format_confidence_level_status(conf_level))

    def go(self):
        form = None
        if self.model.get_current_outcome_type() != "diagnostic":
            # in the binary and continuous case, we go straight
            # to selecting the metric/parameters here.
            #
            # note that the spec form gets *this* form as a parameter.
            # this allows the spec form to callback to this
            # module when specifications have been provided.
            form = self._build_analysis_specs_dialog(
                conf_level=self.model.get_global_conf_level()
            )
        else:
            # diagnostic data; we first have the user select metric(s),
            # and only then the model, &etc.
            form = diag_metrics.Diag_Metrics(self.model, parent=self)
        if form is None:
            return
        form.show()

    def meta_reg(self):
        form = self._build_analysis_specs_dialog(
            meta_f_str="meta-regression",
            conf_level=self.model.get_global_conf_level(),
        )
        if form is None:
            return
        form.show()

    def data_dirtied(self):
        self._notify_user_that_data_is_unsaved()
        self.current_data_unsaved = True

    def _undo_clean_changed(self, is_clean):
        """Keep project dirty state aligned with the active undo history."""
        self.current_data_unsaved = not bool(is_clean)
        if not is_clean:
            self._notify_user_that_data_is_unsaved()

    def meta_subgroup_get_cov(self):
        form = meta_subgroup_form.MetaSubgroupForm(self.model, parent=self)
        form.show()

    ####
    # Here are the calls to ma_specs with so-called `meta-methods`
    # which operate over the output of meta-analytic methods. Note
    # that we don't care what sort of data we're operating over here;
    # ma_specs takes care of that. The convention is that each meta
    # Repeated-analysis actions pass workflow names to the RCMetaR core facade.
    # implementation.
    # Repeated-analysis workflow names are intentionally explicit until the R
    # facade exposes richer method metadata.
    def cum_ma(self):
        # NOTE that we do not allow cumulative meta-analysis on
        # Diagnostic data are not routed through cumulative MA here.
        # if we're dealing with diag data.
        form = None
        # note that the spec form gets *this* form as a parameter.
        # this allows the spec form to callback to this
        # module when specifications have been provided.
        if self.model.get_current_outcome_type() != "diagnostic":
            form = self._build_analysis_specs_dialog(
                meta_f_str="cumulative", conf_level=self.model.get_global_conf_level()
            )
        else:
            # diagnostic data; we first have the user select metric(s),
            # and only then the model, &etc.
            """
            Diagnostic cumulative analysis is not implemented; callers should
            not reach this branch for diagnostic data.
            """
            form = diag_metrics.Diag_Metrics(
                self.model, meta_f_str="cumulative", parent=self
            )

        if form is None:
            return
        form.show()

    def loo_ma(self):
        form = None
        if self.model.get_current_outcome_type() != "diagnostic":
            # in the binary and continuous case, we go straight
            # to selecting the metric/parameters here.
            #
            # note that the spec form gets *this* form as a parameter.
            # this allows the spec form to callback to this
            # module when specifications have been provided.
            form = self._build_analysis_specs_dialog(
                meta_f_str="leave-one-out",
                conf_level=self.model.get_global_conf_level(),
            )
        else:
            # diagnostic data; we first have the user select metric(s),
            # and only then the model, &etc.
            form = diag_metrics.Diag_Metrics(
                self.model, meta_f_str="leave-one-out", parent=self
            )

        if form is None:
            return
        form.show()

    def show_about_legal(self):
        return about_legal_dialog.AboutLegalDialog(self).exec()

    def meta_subgroup(self, selected_cov):
        form = None
        if self.model.get_current_outcome_type() != "diagnostic":
            # in the binary and continuous case, we go straight
            # to selecting the metric/parameters here.
            #
            # note that the spec form gets *this* form as a parameter.
            # this allows the spec form to callback to this
            # module when specifications have been provided.
            form = self._build_analysis_specs_dialog(
                meta_f_str="subgroup",
                external_params={"cov_name": selected_cov},
                conf_level=self.model.get_global_conf_level(),
            )
        else:
            # diagnostic data; we first have the user select metric(s),
            # and only then the model, &etc.
            form = diag_metrics.Diag_Metrics(
                self.model,
                meta_f_str="subgroup",
                parent=self,
                external_params={"cov_name": selected_cov},
            )

        if form is None:
            return
        form.show()

    def _build_analysis_specs_dialog(
        self, meta_f_str=None, external_params=None, diag_metrics=None, conf_level=None
    ):
        try:
            kwargs = {
                "meta_f_str": meta_f_str,
                "parent": self,
                "conf_level": conf_level,
            }
            if external_params is not None:
                kwargs["external_params"] = external_params
            if diag_metrics is not None:
                kwargs["diag_metrics"] = diag_metrics
            return ma_specs.MA_Specs(self.model, **kwargs)
        except Exception as e:
            self._show_analysis_specs_error(e)
            return None

    def _show_analysis_specs_error(self, exception):
        if isinstance(exception, meta_py_r_backend.AnalysisBackendUnavailableError):
            self._show_analysis_backend_error(exception)
        else:
            self._show_analysis_preparation_error(exception)

    def _show_analysis_backend_error(self, exception):
        message = (
            "The analysis backend could not be reached, so "
            "RC MetaStudio cannot build the Method & Parameters dialog.\n\n"
            "Details: %s: %s" % (exception.__class__.__name__, exception)
        )
        QMessageBox.critical(self, "Analysis Backend Unavailable", message)

    def _show_analysis_preparation_error(self, exception):
        message = (
            "RC MetaStudio could not prepare the Method & Parameters dialog "
            "for this analysis.\n\n"
            "Details: %s: %s" % (exception.__class__.__name__, exception)
        )
        QMessageBox.critical(self, "Could Not Prepare Analysis", message)

    def undo(self):
        self.tableView.undoStack.undo()

    def redo(self):
        self.tableView.undoStack.redo()

    def edit_dataset(self):
        cur_dataset = copy.deepcopy(self.model.dataset)
        edit_window = edit_dialog.EditDialog(cur_dataset, parent=self)

        if edit_window.exec():
            # if we edited the current dataset when there was no
            # outcome yet, then we want to default to an outcome
            # that was added.

            ### get stateful dictionary here, update, pass to
            old_state_dict = self.tableView.model().get_stateful_dict()
            new_state_dict = copy.deepcopy(old_state_dict)

            # update the new state dict to reflect the currently selected
            # outcomes, etc.
            outcome_model = edit_window.outcomes_model
            edited_outcomes = outcome_model.outcome_list
            if outcome_model.current_outcome is not None:
                new_state_dict["current_outcome"] = outcome_model.current_outcome
            elif old_state_dict["current_outcome"] in edited_outcomes:
                new_state_dict["current_outcome"] = old_state_dict["current_outcome"]
            elif edited_outcomes:
                # If the current outcome was removed, select the first remaining one.
                new_state_dict["current_outcome"] = edited_outcomes[0]
            else:
                new_state_dict["current_outcome"] = None

            new_state_dict["current_time_point"] = max(
                edit_window.follow_up_list.currentIndex().row(), 0
            )
            grp_list = edit_window.groups_model.group_list

            if len(grp_list) >= 2:
                new_state_dict["current_txs"] = grp_list[:2]
            else:
                # new_state_dict["current_txs"] = ["tx A", "tx B"]
                new_state_dict["current_txs"] = meta_globals.DEFAULT_GROUP_NAMES
            modified_dataset = edit_window.dataset

            redo_f = lambda: self.set_model(modified_dataset, new_state_dict)
            original_dataset = copy.deepcopy(self.model.dataset)
            undo_f = lambda: self.set_model(original_dataset, old_state_dict)
            edit_command = meta_globals.CommandGenericDo(redo_f, undo_f)
            self.tableView.undoStack.push(edit_command)

    def populate_metrics_menu(self, metric_to_check=None):
        """
        Populates the `metric` sub-menu with available metrics for the
        current datatype.
        """

        # Clearing a checked QAction emits ``toggled(False)`` while Qt tears the
        # old submenu down.  Those actions are connected to ``metric_selected``,
        # which would otherwise recalculate every study just because a restored
        # project's menu is being rebuilt.  A document open must preserve the
        # persisted effects rather than treating menu destruction as a user edit.
        for menu_action in self.menuMetric.actions():
            menu_action.blockSignals(True)
            submenu = menu_action.menu()
            if submenu is not None:
                for action in submenu.actions():
                    action.blockSignals(True)
        self.menuMetric.clear()
        self.menuMetric.setDisabled(False)

        if self.model.get_current_outcome_type() == "binary":
            self.add_binary_metrics(metric_to_check=metric_to_check)
            self.metric_menu_is_set_for = meta_globals.BINARY

        elif self.model.get_current_outcome_type() == "continuous":
            self.add_continuous_metrics(metric_to_check=metric_to_check)
            self.metric_menu_is_set_for = meta_globals.CONTINUOUS

        else:
            # diagnostic data; deactive metrics option
            # we always show sens. + spec. for diag. data.
            self.menuMetric.setDisabled(True)
            self.metric_menu_is_set_for = meta_globals.DIAGNOSTIC

    def add_binary_metrics(self, metric_to_check=None):
        self.add_metrics(
            meta_globals.BINARY_ONE_ARM_METRICS,
            meta_globals.BINARY_TWO_ARM_METRICS,
            metric_to_check=metric_to_check,
        )

    def add_continuous_metrics(self, metric_to_check=None):
        self.add_metrics(
            meta_globals.CONTINUOUS_ONE_ARM_METRICS,
            meta_globals.CONTINUOUS_TWO_ARM_METRICS,
            metric_to_check=metric_to_check,
        )

    def add_metrics(self, one_arm_metrics, two_arm_metrics, metric_to_check=None):
        # we'll add sub-menus for two-arm and one-arm metrics
        self.twoArmMetricMenu = self.add_sub_metric_menu("two-arm")
        self.oneArmMetricMenu = self.add_sub_metric_menu("one-arm")

        for i, metric in enumerate(two_arm_metrics):
            metric_action = self.add_metric_action(metric, self.twoArmMetricMenu)
            if metric == metric_to_check or (metric_to_check is None and i == 0):
                # arbitrarily check the first metric in the case that none
                # is specificied
                metric_action.blockSignals(True)
                metric_action.setChecked(True)
                metric_action.blockSignals(False)

        # now add the one-arm metrics
        for metric in one_arm_metrics:
            metric_action = self.add_metric_action(metric, self.oneArmMetricMenu)
            if metric == metric_to_check:
                metric_action.blockSignals(True)
                metric_action.setChecked(True)
                metric_action.blockSignals(False)

    def add_sub_metric_menu(self, name):
        sub_menu = QtWidgets.QMenu(str(name), self.menuMetric)
        self.menuMetric.addAction(sub_menu.menuAction())
        return sub_menu

    def add_metric_action(self, metric, menu):
        metric_names = meta_globals.ALL_METRIC_NAMES

        metric_action = QAction(str(metric + ": " + metric_names[metric]), self)
        try:
            if str(metric) in metric_names:
                metric_action.setToolTip(
                    metric_names[metric]
                )  # doesn't do anything in OSX?
                metric_action.setStatusTip(metric_names[metric])
                metric_action.setData(metric)  # store code for metric in here
        except:
            print("Could not set metric name tooltip")
        metric_action.setCheckable(True)
        metric_action.toggled.connect(
            app_error_handler.safe_slot(
                lambda checked=False, metric=metric, menu=menu: self.metric_selected(
                    metric, menu
                ),
                parent=self,
            )
        )
        menu.addAction(metric_action)
        return metric_action

    def deselect_all_metrics(self):
        # de-selects all metrics
        # it doesn't appear that there is a more
        # straight forward way of doing this,
        # unfortunately.
        data_type = self.tableView.model().get_current_outcome_type(get_str=False)
        if data_type in (meta_globals.BINARY, meta_globals.CONTINUOUS):
            # then there are sub-menus (one-group, two-group)
            for menu_action in self.menuMetric.actions():
                sub_menu = menu_action.menu()
                if sub_menu is None:
                    continue
                for action in sub_menu.actions():
                    action.blockSignals(True)
                    action.setChecked(False)
                    action.blockSignals(False)

    def metric_selected(self, metric_name, menu):
        # first deselect the previous metric
        self.deselect_all_metrics()

        # now select the newly chosen one.
        prev_metric_name = self.tableView.model().current_effect
        for action in menu.actions():
            # action_text = action.text()
            action_data = _qt_item_text(action.data())
            # if action_text == metric_name:
            if action_data == metric_name:
                action.blockSignals(True)
                action.setChecked(True)
                action.blockSignals(False)

        self.tableView.model().set_current_metric(metric_name)
        self.model.try_to_update_outcomes()
        self.model.reset_model()
        self.tableView.synchronize_column_widths()

    def view_network(self):
        view_window = network_view.ViewDialog(self.model, parent=self)
        view_window.show()

    def analysis(self, results):
        if results is None:
            return  # Analysis failed
        try:
            form = results_window.ResultsWindow(results, parent=self)
        except Exception as e:
            app_error_handler.log_exception(type(e), e, e.__traceback__)
            QMessageBox.critical(
                self,
                "Could Not Display Analysis Results",
                "The analysis completed, but RC MetaStudio could not display "
                "the results.\n\nDetails: %s: %s" % (e.__class__.__name__, e),
            )
            return
        form.show()

    def edit_group_name(self, cur_group_name):
        orig_group_name = copy.copy(cur_group_name)
        edit_group_form = edit_group_name_form.EditGroupName(
            cur_group_name, parent=self
        )
        if edit_group_form.exec():
            try:
                existing_groups = list(self.model.dataset.get_group_names())
                if orig_group_name in existing_groups:
                    existing_groups.remove(orig_group_name)
                new_group_name = name_validation.validate_unique_name(
                    "group", edit_group_form.group_name_le.text(), existing_groups
                )
            except ValueError as exc:
                QMessageBox.warning(self, "Warning", str(exc))
                return

            redo_f = lambda: self.model.rename_group(orig_group_name, new_group_name)
            undo_f = lambda: self.model.rename_group(new_group_name, orig_group_name)

            rename_group_command = meta_globals.CommandGenericDo(redo_f, undo_f)
            self.tableView.undoStack.push(rename_group_command)

    def add_covariate(self):
        form = add_new_dialogs.AddNewCovariateForm(self)
        form.covariate_name_le.setFocus()
        if form.exec():
            # then the user clicked 'ok'.
            try:
                new_covariate_name = ma_data_table_model.validate_new_covariate_name(
                    self.model.dataset, form.covariate_name_le.text()
                )
            except ValueError as exc:
                QMessageBox.warning(self, "Warning", str(exc))
                return

            # fix for issue #59; do not allow the user to create two covariates with
            # the same name!
            new_covariate_type = str(form.datatype_cbo_box.currentText()).lower()
            self.tableView.undoStack.push(
                self._make_add_covariate_command(
                    new_covariate_name, new_covariate_type
                )
            )

    def _make_add_covariate_command(self, cov_name, cov_type):
        state = {"stable_id": None}

        def redo():
            covariate = self._add_new_covariate(
                cov_name, cov_type, stable_id=state["stable_id"]
            )
            state["stable_id"] = covariate.stable_id

        def undo():
            self._undo_add_new_covariate(cov_name)

        return meta_globals.CommandGenericDo(
            redo, undo, description="Add covariate %s" % cov_name
        )

    def _add_new_covariate(self, cov_name, cov_type, stable_id=None):
        covariate = self.model.add_covariate(
            cov_name, cov_type, stable_id=stable_id
        )
        print("New Covariate Name: %s with type %s" % (cov_name, cov_type))
        self.tableView.synchronize_column_widths()
        self._refresh_advanced_analysis_actions()
        return covariate

    def _undo_add_new_covariate(self, cov_name):
        self.model.remove_covariate(cov_name)
        self.tableView.synchronize_column_widths()
        self._refresh_advanced_analysis_actions()

    def add_new(self, startup_outcome=None):
        redo_f, undo_f = None, None
        if self.cur_dimension == "outcome" and not startup_outcome:
            form = add_new_dialogs.AddNewOutcomeForm(
                parent=self, is_diag=self.model.is_diag()
            )
            form.outcome_name_le.setFocus()
            if form.exec():
                # then the user clicked ok and has added a new outcome.
                # here we want to add the outcome to the dataset, and then
                # display it
                try:
                    new_outcome_name = ma_data_table_model.validate_new_outcome_name(
                        self.model.dataset, form.outcome_name_le.text()
                    )
                except ValueError as exc:
                    QMessageBox.warning(self, "Warning", str(exc))
                    return
                # the outcome type is one of the enumerated types; we don't worry about
                # unicode encoding
                new_outcome_type = str(form.datatype_cbo_box.currentText())
                redo_f = lambda: self._add_new_outcome(
                    new_outcome_name, new_outcome_type
                )
                prev_outcome = str(self.model.current_outcome)
                undo_f = lambda: self._undo_add_new_outcome(
                    new_outcome_name, prev_outcome
                )
        elif (
            self.cur_dimension == "outcome" and startup_outcome
        ):  # For dealing with outcomes from the startup form
            new_outcome_name = qt_text.to_native_text(startup_outcome["name"])
            new_outcome_type = str(startup_outcome["data_type"])
            try:
                new_outcome_subtype = startup_outcome["sub_type"]
            except:
                print("ERROR: No outcome subtype detected.")
                # pyqtRemoveInputHook()
                # pdb.set_trace()
            print("Startup Outcome", startup_outcome)
            redo_f = lambda: self._add_new_outcome(
                new_outcome_name, new_outcome_type, new_outcome_subtype
            )
            prev_outcome = str(self.model.current_outcome)
            undo_f = lambda: self._undo_add_new_outcome(new_outcome_name, prev_outcome)
        elif self.cur_dimension == "group":
            form = add_new_dialogs.AddNewGroupForm(self)
            form.group_name_le.setFocus()
            if form.exec():
                try:
                    new_group_name = ma_data_table_model.validate_new_group_name(
                        self.model.dataset, form.group_name_le.text()
                    )
                except ValueError as exc:
                    QMessageBox.warning(self, "Warning", str(exc))
                    return
                cur_groups = list(self.model.get_current_groups())
                redo_f = lambda: self._add_new_group(new_group_name)
                undo_f = lambda: self._undo_add_new_group(new_group_name, cur_groups)
        else:
            # then the dimension is follow-up
            form = add_new_dialogs.AddNewFollowUpForm(self)
            form.follow_up_name_le.setFocus()
            if form.exec():
                try:
                    follow_up_lbl = ma_data_table_model.validate_new_follow_up_name(
                        self.model.dataset,
                        self.model.current_outcome,
                        form.follow_up_name_le.text(),
                    )
                except ValueError as exc:
                    QMessageBox.warning(self, "Warning", str(exc))
                    return
                redo_f = lambda: self._add_new_follow_up_for_cur_outcome(follow_up_lbl)
                previous_follow_up = self.model.get_current_follow_up_name()
                undo_f = lambda: self._undo_add_follow_up_for_cur_outcome(
                    previous_follow_up, follow_up_lbl
                )

        if redo_f is not None:
            next_command = meta_globals.CommandGenericDo(redo_f, undo_f)
            self.tableView.undoStack.push(next_command)

    def _add_new_group(self, new_group_name):
        self.model.add_new_group(new_group_name)
        print("\nok. added new group: %s" % new_group_name)
        cur_groups = list(self.model.get_current_groups())
        cur_groups[1] = new_group_name
        self.model.set_current_groups(cur_groups)
        # Refresh the displayed group columns after renaming.
        self.display_groups(cur_groups)

    def _undo_add_new_group(self, added_group, previously_displayed_groups):
        self.model.remove_group(added_group)
        print("\nremoved group %s" % added_group)
        print("attempting to display groups: %s" % previously_displayed_groups)
        self.model.set_current_groups(previously_displayed_groups)
        self.display_groups(previously_displayed_groups)

    def _undo_add_new_outcome(self, added_outcome, previously_displayed_outcome):
        print("removing added outcome: %s" % added_outcome)
        self.model.remove_outcome(added_outcome)
        print("trying to display: %s" % previously_displayed_outcome)
        ##
        # RESOLVED previously, if previous outcome was None, this threw up
        # Historical issue 4 from the original project.
        self.display_outcome(previously_displayed_outcome)

    def _add_new_outcome(self, outcome_name, outcome_type, sub_type=None):
        self.model.add_new_outcome(outcome_name, outcome_type, sub_type=sub_type)
        self.display_outcome(outcome_name)

    def _add_new_follow_up_for_cur_outcome(self, follow_up_lbl):
        self.model.add_follow_up_to_current_outcome(follow_up_lbl)
        self.display_follow_up(self.model.get_t_point_for_follow_up_name(follow_up_lbl))

    def _undo_add_follow_up_for_cur_outcome(self, prev_follow_up, follow_up_to_del):
        self.model.remove_follow_up_from_outcome(
            follow_up_to_del, str(self.model.current_outcome)
        )
        self.display_follow_up(
            self.model.get_t_point_for_follow_up_name(prev_follow_up)
        )

    def next(self):
        # Disable navigation when there is no next item in this dimension.
        # if there is only one point (e.g., outcome). otherwise you end
        # up enqueueing a bunch of pointless undo/redos.
        redo_f, undo_f = None, None
        if self.cur_dimension == "outcome":
            old_outcome = self.model.current_outcome
            ##
            # note that we have to cache the currently displayed
            # groups, as well. these groups may or may not be available
            # on the next outcome; the next_outcome call may therefore
            # default to displaying some other group(s). however, this
            # would cause problems when the 'next' action is undone, as in
            # such a case the previous (current) outcome will be displayed,
            # but the groups being displayed may be other than what they
            # should be (i.e., than what they are currently)
            previous_groups = self.model.get_current_groups()
            next_outcome = self.model.get_next_outcome_name()
            redo_f = lambda: self.display_outcome(next_outcome)
            previous_follow_up = self.model.get_current_follow_up_name()
            undo_f = lambda: self.display_outcome(
                old_outcome,
                follow_up_name=previous_follow_up,
                group_names=previous_groups,
            )
        elif self.cur_dimension == "group":
            previous_groups = self.model.get_current_groups()
            new_groups = self.model.next_groups()
            redo_f = lambda: self.display_groups(new_groups)
            undo_f = lambda: self.display_groups(previous_groups)
        elif self.cur_dimension == "follow-up":
            old_follow_up_t_point = self.model.current_time_point
            next_follow_up_t_point = self.model.get_next_follow_up()[0]
            redo_f = lambda: self.display_follow_up(next_follow_up_t_point)
            undo_f = lambda: self.display_follow_up(old_follow_up_t_point)

        if redo_f is not None and undo_f is not None:
            next_command = meta_globals.CommandGenericDo(redo_f, undo_f)
            self.tableView.undoStack.push(next_command)

    def previous(self):
        redo_f, undo_f = None, None
        if self.cur_dimension == "outcome":
            old_outcome = self.model.current_outcome
            next_outcome = self.model.get_prev_outcome_name()
            redo_f = lambda: self.display_outcome(next_outcome)
            undo_f = lambda: self.display_outcome(old_outcome)
        elif self.cur_dimension == "group":
            cur_groups = self.model.get_current_groups()
            prev_groups = self.model.get_previous_groups()
            redo_f = lambda: self.display_groups(prev_groups)
            undo_f = lambda: self.display_groups(cur_groups)
        elif self.cur_dimension == "follow-up":
            old_follow_up_t_point = self.model.current_time_point
            previous_follow_up_t_point = self.model.get_previous_follow_up()[0]
            redo_f = lambda: self.display_follow_up(previous_follow_up_t_point)
            undo_f = lambda: self.display_follow_up(old_follow_up_t_point)

        if redo_f is not None and undo_f is not None:
            prev_command = meta_globals.CommandGenericDo(redo_f, undo_f)
            self.tableView.undoStack.push(prev_command)

    def next_dimension(self):
        """
        In keeping with the dimensions metaphor, wherein the various
        components that can comprise a dataset are 'dimensions' (e.g.,
        outcomes), this function iterates over the dimensions. So if you call
        this method, then 'next()', the next method will step forward in the
        dimension made active here.
        """
        if self.cur_dimension_index == len(self.dimensions) - 1:
            self.cur_dimension_index = 0
        else:
            self.cur_dimension_index += 1
        self.update_dimension()

    def previous_dimension(self):
        if self.cur_dimension_index == 0:
            self.cur_dimension_index = len(self.dimensions) - 1
        else:
            self.cur_dimension_index -= 1
        self.update_dimension()

    def update_dimension(self):
        self.cur_dimension = self.dimensions[self.cur_dimension_index]
        self.nav_lbl.setText(self.cur_dimension)

    def display_groups(self, groups):
        print("displaying groups: %s" % groups)
        self.model.set_current_groups(groups)
        self.model.try_to_update_outcomes()
        self.model.reset_model()
        self.tableView.synchronize_column_widths()

    def display_outcome(self, outcome_name, group_names=None, follow_up_name=None):
        print("displaying outcome: %s" % outcome_name)
        ###
        # We need to update which groups & follow-ups are current
        # in order to avoid attempting to display a group/fu that
        # do not belong to the outcome_name.
        self.model.set_current_outcome(outcome_name)
        self.populate_metrics_menu()

        # first ascertain if the currently displayed follow up is
        # available for this outcome
        if follow_up_name is not None:
            self.model.set_current_follow_up(follow_up_name)
        else:
            # If a follow up isn't explicitly passed in, attempt to use
            # the current follow up. If this does not exist for the outcome
            # to be displayed, then display a different follow up.
            cur_follow_up = self.model.get_current_follow_up_name()
            if not self.model.outcome_has_follow_up(outcome_name, cur_follow_up):
                # then the outcome does not have this follow up and we have to
                # step on to the next one.
                next_follow_up = self.model.get_next_follow_up()[1]
                self.model.set_current_follow_up(next_follow_up)

        # now we check the groups.
        if group_names is not None:
            self.model.set_current_groups(group_names)
        else:
            # then no group names were explicitly passed in; ascertain
            # that the outcome/fu contains the current groups; if not,
            # set them to something else.
            cur_groups = self.model.get_current_groups()
            if not all(
                [
                    self.model.outcome_fu_has_group(
                        outcome_name, self.model.get_current_follow_up_name(), group
                    )
                    for group in cur_groups
                ]
            ):
                self.model.set_current_groups(self.model.next_groups())

        self.cur_outcome_lbl.setText("<font color='Blue'>%s</font>" % outcome_name)
        self.cur_time_lbl.setText(
            "<font color='Blue'>%s</font>" % self.model.get_current_follow_up_name()
        )
        self.model.reset_model()
        self.tableView.synchronize_column_widths()

    def display_follow_up(self, time_point):
        print("follow up")
        self.model.current_time_point = time_point
        self.update_follow_up_label()
        self.model.reset_model()
        self.tableView.synchronize_column_widths()

    def update_follow_up_label(self):
        self.cur_time_lbl.setText(
            "<font color='Blue'>%s</font>" % self.model.get_current_follow_up_name()
        )

    def open(self, file_path=None, raise_on_error=False):
        """
        Open a validated structured project and restore its durable working state.

        Opening a project is a document boundary, not an undoable edit. The undo stack is
        reset after a successful load so Ctrl+Z cannot step back into the previously open
        dataset.
        """

        if not self._authorize_destructive_project_action():
            return

        # if no file path is provided, prompt the user.
        if file_path is None:
            file_path = QFileDialog.getOpenFileName(
                parent=self,
                caption="RCMetaStudio - Open Project",
                directory=get_default_open_directory(),
                filter="RC MetaStudio Project (*.rcms)",
            )
            file_path = _qt_dialog_path(file_path)

            # if the user didn't select anything, we return false.
            if file_path == "":
                return False

        file_path = _resolve_open_file_path(file_path)

        data_model = None
        print("loading %s..." % file_path)
        try:
            data_model, state_dict, restored_selection = _load_structured_project(file_path)
            data_model = _validate_open_project_dataset(data_model)
            print("successfully loaded data")
        except Exception as e:
            msg = _format_open_project_error(file_path, e)
            print(msg)
            if raise_on_error:
                raise RuntimeError(msg) from e
            QMessageBox.critical(self, "Could Not Open Project", msg)
            return None

        previous = self._capture_project_install_state()
        try:
            self.set_model(
                data_model,
                state_dict,
                check_for_appropriate_metric=not restored_selection,
                preserve_state_selection=restored_selection,
                recalculate_outcomes=False,
            )
            self.model.analysis_source_path = file_path
            self.dataset_file_lbl.setText("Open Project: %s" % file_path)
        except Exception as e:
            self._restore_project_install_state(previous, e)
            msg = _format_open_project_error(file_path, e)
            try:
                app_error_handler.log_exception(type(e), e, e.__traceback__)
            except Exception:
                pass
            if raise_on_error:
                raise RuntimeError(msg) from e
            QMessageBox.critical(self, "Could Not Open Project", msg)
            return None
        self.out_path = file_path
        self.tableView.undoStack.clear()
        # we just opened it, so it's 'saved'
        self.current_data_unsaved = False
        self._update_recent_project_nonfatal(file_path, "opened")

        return True

    def delete_study(self, study, study_index=None):
        undo_f = lambda: self._add_study(study, study_index=study_index)
        redo_f = lambda: self._remove_study(study)
        delete_command = meta_globals.CommandGenericDo(redo_f, undo_f)
        self.tableView.undoStack.push(delete_command)

    def change_cov_type(self, covariate):
        cur_dataset = copy.deepcopy(self.model.dataset)
        # keep the current study order, because we're going to sort the studies
        # on the change_cov_form but we want to revert to the ordering
        # they came in with when we're done.
        original_study_order = [study.name for study in self.model.dataset.studies]

        change_type_form = change_cov_type_form.ChangeCovTypeForm(
            cur_dataset, covariate, parent=self
        )

        if change_type_form.exec():
            modified_dataset = change_type_form.dataset
            # revert to original study ordering
            modified_dataset.studies.sort(
                key=cmp_to_key(
                    modified_dataset.cmp_studies(
                        compare_by="ordered_list",
                        ordered_list=original_study_order,
                        mult=self.model.get_mult(),
                    )
                )
            )

            ### use the same state dict as before.
            old_state_dict = self.tableView.model().get_stateful_dict()
            new_state_dict = copy.deepcopy(old_state_dict)

            redo_f = lambda: self.set_model(modified_dataset, new_state_dict)
            original_dataset = copy.deepcopy(self.model.dataset)
            undo_f = lambda: self.set_model(original_dataset, old_state_dict)
            edit_command = meta_globals.CommandGenericDo(redo_f, undo_f)
            self.tableView.undoStack.push(edit_command)

    def rename_covariate(self, covariate):
        orig_cov_name = copy.copy(covariate.name)
        # The group-name editor is also used for covariate labels.
        edit_cov_form = edit_group_name_form.EditCovariateName(
            orig_cov_name, parent=self
        )
        if edit_cov_form.exec():
            # the field names are also poorly named, in this case. here we mean the
            # **covariate name**, of course.
            try:
                existing_covariates = list(self.model.dataset.get_cov_names())
                if orig_cov_name in existing_covariates:
                    existing_covariates.remove(orig_cov_name)
                new_cov = name_validation.validate_unique_name(
                    "covariate",
                    edit_cov_form.group_name_le.text(),
                    existing_covariates,
                )
            except ValueError as exc:
                QMessageBox.warning(self, "Warning", str(exc))
                return

            ###
            # The model owns the actual covariate rename and undo operation.
            redo_f = lambda: self.model.rename_covariate(orig_cov_name, new_cov)
            undo_f = lambda: self.model.rename_covariate(new_cov, orig_cov_name)

            rename_cov_command = meta_globals.CommandGenericDo(redo_f, undo_f)
            self.tableView.undoStack.push(rename_cov_command)

    def delete_covariate(self, covariate):
        cov_vals_d = self.model.dataset.get_values_for_cov(covariate.name)
        stable_id = getattr(covariate, "stable_id", None)

        def undo_f():
            self.model.add_covariate(
                covariate.name,
                meta_globals.COV_INTS_TO_STRS[covariate.data_type],
                cov_values=cov_vals_d,
                stable_id=stable_id,
            )
            self._refresh_advanced_analysis_actions()

        def redo_f():
            self.model.remove_covariate(covariate)
            self._refresh_advanced_analysis_actions()

        delete_command = meta_globals.CommandGenericDo(redo_f, undo_f)
        self.tableView.undoStack.push(delete_command)

    def _refresh_advanced_analysis_actions(self):
        self._enable_action_meta_regression()
        self._enable_action_subgroup_ma()

    def _add_study(self, study, study_index=None):
        print("adding study: %s" % study.name)
        self.model.dataset.add_study(study, study_index=study_index)
        self.model.reset_model()
        self.data_dirtied()

    def _remove_study(self, study):
        print("deleting study: %s" % study.name)
        self.model.dataset.studies.remove(study)
        self.model.reset_model()
        self.data_dirtied()

    def set_model(
        self,
        data_model,
        state_dict=None,
        check_for_appropriate_metric=False,
        preserve_state_selection=False,
        recalculate_outcomes=True,
    ):
        ##
        # we explicitly append a blank study to the
        # dataset iff there is fewer than 1 study
        # in the dataset. in this case, the only
        # row is essentially a blank study.
        add_blank_study = len(data_model) < 1
        self.model = ma_data_table_model.DatasetModel(
            dataset=data_model, add_blank_study=add_blank_study
        )

        self._disconnections()
        if len(data_model) >= 2:
            self.enable_menu_options_that_require_dataset()
        else:
            self.disable_menu_options_that_require_dataset()

        self._enable_action_meta_regression(len(data_model) >= 2)

        self.tableView.setModel(self.model)

        ## moving the statefulendess
        # update below the model swap-out
        # to fix issue #62
        if state_dict is not None:
            self.model.set_state(state_dict)

        print("calling update col indices from meta form set_model()")
        self.tableView.model().update_column_indices()
        self.tableView.synchronize_column_widths()

        if check_for_appropriate_metric:
            self.tableView.change_metric_if_appropriate()

        #        if self.model.get_current_outcome_type() == "diagnostic":
        #            # no cumulative MA for diagnostic data
        #            self.action_cum_ma.setEnabled(False)
        #        else:
        #            self.action_cum_ma.setEnabled(True)

        self.model_updated(
            preserve_selection=preserve_state_selection,
            recalculate_outcomes=recalculate_outcomes,
        )
        self.data_dirtied()
        print("ok -- model set.")

    def model_updated(self, preserve_selection=False, recalculate_outcomes=True):
        """Call me when the model is changed."""
        if preserve_selection:
            group_names = self.model.dataset.get_group_names()
            if self.model.current_txs:
                self.model.tx_index_a = group_names.index(self.model.current_txs[0])
                if len(self.model.current_txs) > 1:
                    self.model.tx_index_b = group_names.index(self.model.current_txs[1])
                else:
                    self.model.tx_index_b = self.model.tx_index_a
            self.model.previous_txs = list(self.model.current_txs)
        else:
            self.model.update_current_group_names()
            self.model.update_current_outcome()
            self.model.update_current_time_points()

        if (
            recalculate_outcomes
            and self.model.current_outcome is not None
            and not self.model.is_diag()
        ):
            self.model.try_to_update_outcomes()

        # This is kind of subtle. We have to reconnect
        # our signals and slots when the underlying model
        # changes, because otherwise the antiquated/replaced
        # model (which was connected to the slots of interest)
        # remains, which is useless. However, we do not
        # reconnect the menu_action options; this will cause those
        # methods to be called x times! (x being the number of times
        # _setup_connections is invoked)
        self._setup_connections(menu_actions=False)
        self.tableView.synchronize_column_widths()
        self.update_outcome_lbl()
        self.update_follow_up_label()

        ####
        # adding check to ascertain that the menu
        # isn't already ready for the current kind of data
        cur_data_type = self.tableView.model().get_current_outcome_type(get_str=False)
        if self.metric_menu_is_set_for != cur_data_type:
            self.populate_metrics_menu(
                metric_to_check=self.tableView.model().current_effect
            )

        self.model.reset_model()
        self._change_conf_level_label()

    def update_outcome_lbl(self):
        self.cur_outcome_lbl.setText(
            "<font color='Blue'>%s</font>" % self.model.current_outcome
        )

    def quit(self):
        self.close()

    def prompt_to_save_unsaved_data(self):
        choice = QMessageBox.warning(
            self,
            "Warning",
            "You've made unsaved changes to your data. Do you want to save your changes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
        )
        return choice

    def save_as(self):
        return self.save(save_as=True)

    def save(self, save_as=False):

        docs_path = get_user_documents_path()
        destination = self.out_path
        if self.out_path is None or save_as:
            # use current out_path otherwise base it on the current dataset name
            if self.out_path:
                out_f = str(self.out_path)
            else:
                out_f = os.path.join(docs_path, self.model.get_name())

            out_f = QFileDialog.getSaveFileName(
                parent=self,
                caption="RCMetaStudio - Save Project",
                directory=out_f,
                filter="RC MetaStudio Project (*.rcms)",
            )
            out_f = _qt_dialog_path(out_f)
            if out_f == "" or out_f == None:
                return None
            destination = out_f

        destination = str(destination)
        if not destination.lower().endswith(".rcms"):
            destination += ".rcms"
            print("added proper file extension")

        durability_error = None
        try:
            print("trying to write data out to: %s" % destination)
            project = project_adapter.dataset_to_project(self.model.dataset)
            state = project_adapter.model_to_state(self.model)
            project_format.save_project(destination, project, state)
        except project_format.ProjectDurabilityError as e:
            # Atomic replacement already happened. Treat the installed document
            # as the current saved project while reporting durability uncertainty.
            durability_error = e
        except Exception as e:
            app_error_handler.log_exception(type(e), e, e.__traceback__)
            QMessageBox.critical(
                self,
                "Could Not Save Project",
                "RC MetaStudio could not save %s.\n\nDetails: %s: %s"
                % (destination, e.__class__.__name__, e),
            )
            return False

        # The durable document commit is complete. Machine-local recent-project
        # bookkeeping must never turn this successful save into a false failure.
        self.out_path = destination
        self.model.analysis_source_path = destination
        self.dataset_file_lbl.setText("Open Project: %s" % destination)
        self.tableView.undoStack.setClean()
        self.current_data_unsaved = False
        if durability_error is not None:
            self._report_durability_uncertain_save(destination, durability_error)
        self._update_recent_project_nonfatal(destination, "saved")
        return True

    def _make_new_dataset_and_setup_spreadsheet(self, dataset_info):
        is_diag = dataset_info["data_type"] == "diagnostic"
        self.new_dataset(is_diag=is_diag)
        self.model.dataset.summary = copy.deepcopy(dataset_info)

        tmp = self.cur_dimension
        self.cur_dimension = "outcome"
        self.add_new(dataset_info)  # add the outcome
        self.cur_dimension = tmp

        if dataset_info["data_type"] in ["binary", "continuous"]:
            self.model.current_effect = dataset_info["effect"]  # set current effect
            self.populate_metrics_menu(metric_to_check=self.model.current_effect)
            self.model.try_to_update_outcomes()
            self.model.reset_model()

    def _handle_wizard_results(self, wizard_data):
        path = wizard_data["path"]  # route through wizard

        dataset_info = wizard_data["outcome_info"]

        if path == "open":
            self.open(file_path=wizard_data["selected_dataset"])
        elif path == "new_dataset":
            self._make_new_dataset_and_setup_spreadsheet(dataset_info)

        elif path == "csv_import":
            csv_data = wizard_data["csv_data"]

            # Back-up original dataset
            original_dataset = copy.deepcopy(self.model.dataset)
            old_state_dict = self.tableView.model().get_stateful_dict()

            self._make_new_dataset_and_setup_spreadsheet(dataset_info)

            new_dataset = copy.deepcopy(self.model.dataset)
            new_state_dict = self.tableView.model().get_stateful_dict()

            imported_data = csv_data["data"]
            # Note: may want at some point to access the headers provided in the CSV;
            #     these are accessible at csv_data['headers'] and
            #     csv_data['expected_headers']
            covariate_names = csv_data["covariate_names"]
            covariate_types = csv_data["covariate_types"]

            print(
                (
                    "Data to import: %s\ncovariate names: %s\ncovariate_types: %s"
                    % (str(imported_data), str(covariate_names), str(covariate_types))
                )
            )

            # Undo/redo stuff
            importcsv_command = CommandImportCSV(
                original_dataset=original_dataset,
                old_state_dict=old_state_dict,
                new_dataset=new_dataset,
                new_state_dict=new_state_dict,
                imported_data=imported_data,
                main_form=self,
                covariate_names=covariate_names,
                covariate_types=covariate_types,
            )
            self.tableView.undoStack.push(importcsv_command)


######################### Undo Command for Import CSV #########################
class CommandImportCSV(QUndoCommand):
    def __init__(
        self,
        original_dataset=None,
        old_state_dict=None,
        new_dataset=None,
        new_state_dict=None,
        main_form=None,
        imported_data=None,
        covariate_names=None,
        covariate_types=None,
        description="Import a CSV file",
    ):
        super(CommandImportCSV, self).__init__(description)
        if main_form is None:
            raise ValueError("CSV import requires a main form")
        self.imported_data = _normalize_imported_csv_rows(imported_data or [])
        self.covariate_names = list(covariate_names or [])
        self.covariate_types = list(covariate_types or [])
        self.main_form: MetaForm = main_form

        # Undo / redo stuff
        self.original_dataset = original_dataset
        self.old_state_dict = old_state_dict
        self.new_dataset = new_dataset
        self.new_state_dict = new_state_dict

        self.new_dataset_has_imported_data = False

    def redo(self):
        if (
            self.new_dataset_has_imported_data
        ):  # already imported once before, this is a real 'redo'
            self.main_form.set_model(self.new_dataset, self.new_state_dict)
        else:  # this a first run
            self._import_data_into_new_dataset()
            self.new_dataset = copy.deepcopy(self.main_form.model.dataset)
            self.new_state_dict = self.main_form.tableView.model().get_stateful_dict()
            self.new_dataset_has_imported_data = True

    def undo(self):
        self.main_form.set_model(self.original_dataset, self.old_state_dict)
        self.main_form.model.reset_model()
        QApplication.processEvents()

    def _import_data_into_new_dataset(self):
        self.main_form.set_model(self.new_dataset, self.new_state_dict)

        # Set data in model:
        num_rows = len(self.imported_data)
        if num_rows == 0:
            return
        num_cols = len(self.imported_data[0])

        # Handle covariates
        if self.covariate_names != []:
            for name, cov_type in zip(self.covariate_names, self.covariate_types):
                self.main_form._add_new_covariate(name, cov_type)

        # Copy data into table
        progress_bar = ImportProgress(self.main_form, 0, num_rows * num_cols - 1)

        progress_bar.setValue(0)
        progress_bar.show()
        try:
            for row in range(num_rows):
                for col in range(num_cols):
                    progress_bar.setValue(row * num_cols + col)
                    QApplication.processEvents()
                    print(
                        (
                            "bar_ value: %s"
                            % str(
                                [
                                    progress_bar.value(),
                                    progress_bar.minimum(),
                                    progress_bar.maximum(),
                                ]
                            )
                        )
                    )
                    value = str(self.imported_data[row][col])
                    self.main_form.model.setData(
                        self.main_form.model.index(row, col + 1), value, import_csv=True
                    )

        finally:
            progress_dialog.hide_once(progress_bar)


def _normalize_imported_csv_rows(rows):
    return tabular_data.normalize_rows(rows)


####################### END Undo Command for Import CSV #######################


class CommandNext(QUndoCommand):
    """
    This is an undo command for user navigation
    """

    def __init__(self, redo_f, undo_f, description="command:: next dimension"):
        super(CommandNext, self).__init__(description)
        self.redo_f = redo_f
        self.undo_f = undo_f

    def redo(self):
        self.redo_f()

    def undo(self):
        self.undo_f()


class Command_Change_Conf_Level(QUndoCommand):
    """Undo command for chnaging the confidence level"""

    def __init__(
        self,
        old_conf_lvl,
        new_conf_lvl,
        mainform,
        description="Change confidence level",
    ):
        super(Command_Change_Conf_Level, self).__init__(description)

        self.old_cl = old_conf_lvl
        self.new_cl = new_conf_lvl
        self.mainform = mainform

    def redo(self):
        self._set_conf_level(self.new_cl)

    def undo(self):
        self._set_conf_level(self.old_cl)

    def _set_conf_level(self, conf_level):
        self.mainform.model.set_conf_level(conf_level)
        self.mainform.cl_label.setText(_format_confidence_level_status(conf_level))
        self.mainform.model.reset_model()
        print(
            (
                "Global Confidence level is now: %f"
                % self.mainform.model.get_global_conf_level()
            )
        )
