# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Custom QTableView with copy, paste, undo, and redo support."""

from typing import TYPE_CHECKING, Protocol, cast

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QEvent, QObject, QRegularExpression, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QKeyEvent, QUndoCommand, QUndoStack
from PyQt6.QtWidgets import (
    QApplication,
    QItemDelegate,
    QLineEdit,
    QMenu,
    QMessageBox,
    QTableView,
    QWidget,
)

print("In ma_data_table_view: importing forms")
import binary_data_form
import continuous_data_form
import diagnostic_data_form
import app_error_handler
import qt_layout
from workspace_columns import WorkspaceColumnWidthController

if TYPE_CHECKING:
    from ma_data_table_model import DatasetModel


class MainGuiProtocol(Protocol):
    model: "DatasetModel"
    current_data_unsaved: bool | None
    oneArmMetricMenu: QMenu
    twoArmMetricMenu: QMenu

    def data_dirtied(self) -> None: ...
    def delete_study(self, study, *, study_index: int) -> None: ...
    def edit_group_name(self, group: str) -> None: ...
    def rename_covariate(self, covariate) -> None: ...
    def delete_covariate(self, covariate) -> None: ...
    def change_cov_type(self, covariate) -> None: ...
    def keyPressEvent(self, event: QKeyEvent | None) -> None: ...
    def metric_selected(self, metric: str, menu: QMenu) -> None: ...
    def enable_menu_options_that_require_dataset(self) -> None: ...
    def disable_menu_options_that_require_dataset(self) -> None: ...
    def set_model(self, dataset, state_dict=None) -> None: ...
    def data_error(self, message: str) -> None: ...

# it's a questionable practice to import the
# underlying model into the view, but sometimes
# it's easiest to manipulate the model directly
# on interaction rather than that table_model
# intermediary
import ma_dataset
from ma_dataset import *
from meta_globals import *
import qt_text
import tabular_data
from runtime_types import required

# for issue #169 -- normalizing new lines, e.g., for pasting
# This Qt6 regular expression site is behavior-owned by the table editing slice.
_newlines_re = QRegularExpression("(\r\n|\r|\r)")


def _connect_action(action, callback):
    parent = getattr(callback, "__self__", None)
    action.triggered.connect(
        app_error_handler.safe_slot(lambda checked=False: callback(), parent=parent)
    )


def _to_text(value):
    return qt_text.to_native_text(value)


def DebugHelper(function):
    def _DebugHelper(*args, **kw):
        print(("Entered %s" % function.__name__))
        res = function(*args, **kw)
        print(("Left %s" % function.__name__))
        return res

    return _DebugHelper


def _restore_table_selection(table, selected_cells, current_cell):
    model = table.model()
    selection_model = table.selectionModel()
    if model is None or selection_model is None:
        return
    selection_model.clearSelection()
    select = QtCore.QItemSelectionModel.SelectionFlag.Select
    for row, column in selected_cells:
        index = model.index(row, column)
        if index.isValid():
            selection_model.select(index, select)
    if current_cell is not None:
        index = model.index(*current_cell)
        if index.isValid():
            selection_model.setCurrentIndex(
                index, QtCore.QItemSelectionModel.SelectionFlag.NoUpdate
            )


class MADataTable(QtWidgets.QTableView):
    dataDirtied = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        # the main gui is assumed to be the form
        # that owns this table view, i.e., the 'main'
        # user interface/form. it is assumed that this
        # is set elsewhere.
        self.main_gui: MainGuiProtocol | None = None

        # None maps to the special, no outcome/no follow up
        # undo stack
        self.undo_stack_dict = {None: QUndoStack(self)}
        self.undoStack = QUndoStack(self)

        header = required(self.horizontalHeader(), "workspace column header")
        header.sectionClicked.connect(
            app_error_handler.safe_slot(self.header_clicked, parent=self)
        )

        self.vert_header = required(self.verticalHeader(), "workspace row header")

        self.vert_header.sectionClicked.connect(
            app_error_handler.safe_slot(self.row_header_clicked, parent=self)
        )

        # Additional covariate sort columns are registered as they become visible.
        self.reverse_column_sorts = {0: False, 1: False}
        self.setAlternatingRowColors(True)

        ### horizontal (row) header
        self.contextMenuEvent = self._make_context_menu()

        ### vertical (column) header
        headers = required(self.horizontalHeader(), "workspace column header")
        headers.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        headers.customContextMenuRequested.connect(
            app_error_handler.safe_slot(self.header_context_menu, parent=self)
        )
        qt_layout.configure_spreadsheet_table_view(self)
        self._column_widths = WorkspaceColumnWidthController(self)
        self._column_model = None

    def model(self) -> "DatasetModel":
        """Return the concrete model required by the maintained workspace view."""
        from ma_data_table_model import DatasetModel

        model = super().model()
        if model is None:
            raise RuntimeError("MADataTable requires a model")
        return cast(DatasetModel, model)

    def _main_gui(self) -> MainGuiProtocol:
        return required(self.main_gui, "workspace owner")

    def setModel(self, model):
        self._disconnect_column_model()
        self._column_widths.begin_schema_change()
        try:
            super(MADataTable, self).setModel(model)
        finally:
            self._column_widths.end_schema_change()
        self._column_model = model
        if model is not None:
            model.modelAboutToBeReset.connect(self._begin_column_schema_change)
            model.modelReset.connect(self._end_column_schema_change)
            model.columnsAboutToBeInserted.connect(self._begin_column_schema_change)
            model.columnsInserted.connect(self._end_column_schema_change)
            model.columnsAboutToBeRemoved.connect(self._begin_column_schema_change)
            model.columnsRemoved.connect(self._end_column_schema_change)
            model.headerDataChanged.connect(self.synchronize_column_widths)
        self.synchronize_column_widths()

    def _disconnect_column_model(self):
        if self._column_model is None:
            return
        connections = (
            (self._column_model.modelAboutToBeReset, self._begin_column_schema_change),
            (self._column_model.modelReset, self._end_column_schema_change),
            (
                self._column_model.columnsAboutToBeInserted,
                self._begin_column_schema_change,
            ),
            (self._column_model.columnsInserted, self._end_column_schema_change),
            (
                self._column_model.columnsAboutToBeRemoved,
                self._begin_column_schema_change,
            ),
            (self._column_model.columnsRemoved, self._end_column_schema_change),
            (self._column_model.headerDataChanged, self.synchronize_column_widths),
        )
        for signal, callback in connections:
            try:
                signal.disconnect(callback)
            except (TypeError, RuntimeError):
                pass
        self._column_model = None

    def _begin_column_schema_change(self, *_args):
        self._column_widths.begin_schema_change()

    def _end_column_schema_change(self, *_args):
        self._column_widths.end_schema_change()

    def synchronize_column_widths(self, *_args):
        self._column_widths.synchronize_schema()

    def auto_fit_columns(self):
        self._column_widths.auto_fit_all()

    def restore_column_widths(self, widths):
        self._column_widths.restore(widths)

    def column_width_state(self):
        return self._column_widths.state()

    def _make_context_menu(self):
        def _context_menu(event):
            context_menu = QMenu(self)
            study_index = self.rowAt(event.y())

            ### if this is a dummy row, it doesn't make
            # sense to provide a context-menu
            if study_index >= len(self.model().dataset.studies):
                return None

            ### delete study
            study = self.model().dataset.studies[study_index]
            action = QAction("Delete Study %s" % study.name, self)
            _connect_action(
                action,
                lambda: self._main_gui().delete_study(study, study_index=study_index),
            )
            context_menu.addAction(action)

            ### copy
            action = QAction("Copy", self)
            _connect_action(action, self.copy)
            context_menu.addAction(action)

            ### paste
            action = QAction("Paste", self)
            _connect_action(action, self.paste)
            context_menu.addAction(action)

            app_error_handler.popup_context_menu(
                context_menu, event.globalPos(), parent=self, event=event
            )

        return _context_menu

    def header_context_menu(self, pos):
        """
        here is where the context menus for column header
        right-clicks are built.
        """
        column_clicked = self.columnAt(pos.x())
        covariate_columns = self.get_covariate_columns()
        raw_data_columns = self.model().RAW_DATA
        outcomes_columns = self.model().OUTCOMES

        sort_by_col = self.model().get_current_outcome_type()
        data_type = self.model().get_current_outcome_type()

        print("right click @ column: %s" % column_clicked)
        context_menu = QMenu(self)

        # add a covariate anywhere
        if column_clicked == 0:
            # option to (de-)select / include all studies
            # per Ethan (issue #100)
            action = QAction("Include All", self)
            _connect_action(action, self.include_all_studies)
            if self.model().all_studies_are_included():
                action.setEnabled(False)
            context_menu.addAction(action)

            action = QAction("Exclude All", self)
            _connect_action(action, self.exclude_all_studies)
            if self.model().all_studies_are_excluded():
                action.setEnabled(False)
            context_menu.addAction(action)

            app_error_handler.popup_context_menu(
                context_menu, self.mapToGlobal(pos), parent=self
            )
        elif column_clicked in (1, 2):
            col_name = {1: "Study Name", 2: "Year"}[column_clicked]
            action_sort = QAction("Sort Studies by %s" % col_name, self)

            _connect_action(action_sort, lambda: self.sort_by_col(column_clicked))
            context_menu.addAction(action_sort)

        elif column_clicked in raw_data_columns and not data_type == "diagnostic":
            corresponding_tx_group = self.model().current_txs[0]
            if data_type == "binary":
                if column_clicked in raw_data_columns[2:]:
                    corresponding_tx_group = self.model().current_txs[1]
            elif data_type == "continuous":
                if column_clicked in raw_data_columns[3:]:
                    corresponding_tx_group = self.model().current_txs[1]

            # renaming
            action_rename = QAction("Rename Group %s" % corresponding_tx_group, self)
            _connect_action(
                action_rename,
                lambda: self._main_gui().edit_group_name(corresponding_tx_group),
            )
            context_menu.addAction(action_rename)
            # sorting
            col_name = _to_text(self.model().headerData(column_clicked, Qt.Orientation.Horizontal))
            action_sort = QAction("Sort Studies by %s" % col_name, self)
            _connect_action(action_sort, lambda: self.sort_by_col(column_clicked))
            context_menu.addAction(action_sort)
        elif column_clicked in raw_data_columns and data_type == "diagnostic":
            # sorting
            col_name = _to_text(self.model().headerData(column_clicked, Qt.Orientation.Horizontal))
            action_sort = QAction("Sort Studies by %s" % col_name, self)
            _connect_action(action_sort, lambda: self.sort_by_col(column_clicked))
            context_menu.addAction(action_sort)
        elif column_clicked in outcomes_columns:
            # sorting
            col_name = _to_text(self.model().headerData(column_clicked, Qt.Orientation.Horizontal))
            action_sort = QAction("Sort Studies by %s" % col_name, self)
            _connect_action(action_sort, lambda: self.sort_by_col(column_clicked))
            context_menu.addAction(action_sort)
        elif column_clicked in covariate_columns:
            cov = self.model().get_cov(column_clicked)

            # and for sorting (issue #142)
            action_sort = QAction("Sort Studies by %s" % cov.name, self)
            _connect_action(action_sort, lambda: self.sort_by_col(column_clicked))
            context_menu.addAction(action_sort)

            action_ren = QAction("Rename Covariate %s" % cov.name, self)
            _connect_action(action_ren, lambda: self._main_gui().rename_covariate(cov))
            context_menu.addAction(action_ren)

            # allow deletion of covariate
            action_del = QAction("Delete Covariate %s" % cov.name, self)
            _connect_action(action_del, lambda: self._main_gui().delete_covariate(cov))
            context_menu.addAction(action_del)

            convert_to_str = "*continuous*"
            if cov.data_type == CONTINUOUS:
                convert_to_str = "*factor*"

            action_change = QAction(
                "Create a %s Copy of %s" % (convert_to_str, cov.name), self
            )
            _connect_action(action_change, lambda: self._main_gui().change_cov_type(cov))
            context_menu.addAction(action_change)

        app_error_handler.popup_context_menu(
            context_menu, self.mapToGlobal(pos), parent=self
        )

    def include_all_studies(self):
        self.model().include_all_studies()
        self.model().reset_model()

    def exclude_all_studies(self):
        self.model().exclude_all_studies()
        self.model().reset_model()

    def keyPressEvent(  # ty: ignore[invalid-method-override] -- PyQt6's QTableView stub rejects this runtime-supported nullable event override.
        self, event: QKeyEvent | None
    ) -> None:
        if event is None:
            return
        if event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            ## undo/redo

            if event.key() == QtCore.Qt.Key.Key_Z:
                self.undoStack.undo()
            elif event.key() == QtCore.Qt.Key.Key_Y:
                self.undoStack.redo()
            ### copy/paste
            elif event.key() == QtCore.Qt.Key.Key_C:
                # ctrl + c = copy
                self.copy()
            elif event.key() == QtCore.Qt.Key.Key_V:
                # ctrl + v = paste
                self.paste()
            elif event.key() == QtCore.Qt.Key.Key_A:
                self.selectAll()
                event.accept()
            else:
                ###
                # if the command hasn't anything to do with the table view
                # in particular, we pass the event up to the main UI
                self._main_gui().keyPressEvent(event)
        elif self._is_return_key(event):
            self._move_current_index_vertically(
                -1 if event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier else 1
            )
            event.accept()
        elif self._is_clear_key(event):
            if self.clear_selected_cells():
                event.accept()
            else:
                QTableView.keyPressEvent(self, event)
        else:
            # This is a call to the default keyPressEvent function,
            # which preserves table navigation behavior for keys we do not
            # handle explicitly.
            QTableView.keyPressEvent(self, event)

    def _is_return_key(self, event):
        return event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter)

    def _is_clear_key(self, event):
        return event.key() in (QtCore.Qt.Key.Key_Delete, QtCore.Qt.Key.Key_Backspace)

    def clear_selected_cells(self):
        model = self.model()
        selection_model = self.selectionModel()
        if model is None or selection_model is None:
            return False

        indexes = selection_model.selectedIndexes()
        if not indexes:
            indexes = [self.currentIndex()]

        editable_indexes = []
        seen = set()
        for index in indexes:
            if index is None or not index.isValid():
                continue
            key = (index.row(), index.column())
            if key in seen:
                continue
            seen.add(key)
            if model.flags(index) & Qt.ItemFlag.ItemIsEditable:
                editable_indexes.append(index)

        if not editable_indexes:
            return False

        failed_messages = []
        for index in sorted(editable_indexes, key=lambda i: (i.row(), i.column())):
            if not model.setData(index, ""):
                failed_messages.append(self._model_data_error_message())

        model.reset_model()
        if failed_messages:
            self._report_model_data_error(failed_messages[0])
        self._enable_analysis_menus_if_appropriate()
        return True

    def _move_current_index_vertically(self, row_delta):
        self._move_index_vertically_from(self.currentIndex(), row_delta)

    def _move_index_vertically_from(self, index, row_delta):
        model = self.model()
        if index is None or not index.isValid() or model is None:
            return

        target_row = min(max(index.row() + row_delta, 0), model.rowCount() - 1)
        target = model.index(target_row, index.column())
        if target.isValid():
            self.setCurrentIndex(target)
            self.scrollTo(target)

    def copy(self):
        selected_indexes = required(self.selectionModel(), "workspace selection model").selectedIndexes()
        if not selected_indexes:
            return
        upper_left_index = self._upper_left(selected_indexes)
        lower_right_index = self._lower_right(selected_indexes)
        self.copy_contents_in_range(
            upper_left_index, lower_right_index, to_clipboard=True
        )

    def paste(self):
        selected_indexes = required(self.selectionModel(), "workspace selection model").selectedIndexes()
        if not selected_indexes:
            return
        upper_left_index = self._upper_left(selected_indexes)
        lower_right_index = self._lower_right(selected_indexes)

        self.paste_from_clipboard(upper_left_index)
        self._enable_analysis_menus_if_appropriate()

    def row_header_clicked(self, row):
        if row > len(self.model().dataset) - 1:
            return

        # Prevent row-header signals while the edit dialog mutates row state.
        self.vert_header.blockSignals(True)

        try:
            # dispatch on the data type
            form = None
            study_index = row
            # Snapshot the MA unit so dialog cancellation can restore it.
            ma_unit = copy.deepcopy(
                self.model().get_current_ma_unit_for_study(study_index)
            )
            old_ma_unit = copy.deepcopy(ma_unit)
            cur_txs = self.model().current_txs
            cur_effect = self.model().current_effect
            cur_group_str = self.model().get_cur_group_str()
            data_type = self.model().get_current_outcome_type()

            ####
            # here we implement undo/redo.
            # in particular, we cache the raw data prior to editing;
            # then undo will simply overwrite the new raw data
            if data_type == "binary":
                ### need to back up
                cur_raw_data_dict = {}
                for group in cur_txs:
                    cur_raw_data_dict[group] = list(
                        ma_unit.get_raw_data_for_group(group)
                    )

                form = binary_data_form.BinaryDataForm2(
                    ma_unit,
                    cur_txs,
                    cur_group_str,
                    cur_effect,
                    conf_level=self.model().get_global_conf_level(),
                    parent=self,
                )
                if form.exec():
                    # push the edit even
                    ma_edit = CommandEditMAUnit(self, study_index, ma_unit, old_ma_unit)
                    self.undoStack.push(ma_edit)
            elif data_type == "continuous":
                cur_raw_data_dict = {}
                for group_name in cur_txs:
                    cur_raw_data_dict[group_name] = list(
                        ma_unit.get_raw_data_for_group(group_name)
                    )

                # old_raw_data_dict = copy.deepcopy(cur_raw_data_dict)
                form = continuous_data_form.ContinuousDataForm(
                    ma_unit,
                    cur_txs,
                    cur_group_str,
                    cur_effect,
                    conf_level=self.model().get_global_conf_level(),
                    parent=self,
                )
                if form.exec():
                    # update the model; push this event onto the stack
                    ma_edit = CommandEditMAUnit(self, study_index, ma_unit, old_ma_unit)
                    self.undoStack.push(ma_edit)
            else:
                # then this is diagnostic data
                cur_raw_data_dict = {}
                for group in cur_txs:
                    cur_raw_data_dict[group] = list(
                        ma_unit.get_raw_data_for_group(group)
                    )

                form = diagnostic_data_form.DiagnosticDataForm(
                    ma_unit,
                    cur_txs,
                    cur_group_str,
                    conf_level=self.model().get_global_conf_level(),
                    parent=self,
                )
                if form.exec():
                    ma_edit = CommandEditMAUnit(self, study_index, ma_unit, old_ma_unit)
                    self.undoStack.push(ma_edit)
        finally:
            self.vert_header.blockSignals(False)

    def rowMoved(self, row, oldIndex, newIndex):
        pass

    def displayed_ma_changed(self):
        cur_outcome = self.model().current_outcome
        cur_follow_up = self.model().current_time_point

    def cell_content_changed(self, edit):
        index = edit.index
        old_val = edit.old_value
        new_val = edit.new_value
        study_added = edit.added_study_id
        # Only make a cell edit if the old values and new values are different
        try:
            print(("Old val: %s, new val: %s" % (_to_text(old_val), _to_text(new_val))))
        except AttributeError:
            print(("old val: %s, new val: %s" % (str(old_val), str(new_val))))

        if not self._new_eq_old(old_val, new_val):
            cell_edit = CommandCellEdit(
                self, index, old_val, new_val, added_study=study_added
            )
            self.undoStack.push(cell_edit)
        self._enable_analysis_menus_if_appropriate()

        # make analysis menus change even when checkbox is (un)checked
        self._enable_analysis_menus_if_appropriate()

    def _new_eq_old(self, old, new):
        """None and "" are the same for table-edit comparisons."""

        if hasattr(old, "include") or hasattr(new, "include"):
            return old == new

        blank_vals = meta_globals.EMPTY_VALS

        # transform into normal string:
        if old is not None:
            old = _to_text(old)
        if new is not None:
            new = _to_text(new)

        if old in blank_vals and new in blank_vals:
            return True

        return old == new

    def change_metric_if_appropriate(self):
        """
        if:
            1) there are at least 2 studies, and
            2) none of them have data for two-arms, and,
            3) the current metric is a two-arm metric
        then:
            we automatically change the metric to single-arm

        returns a tuple, wherein the first element is a boolean
        indicating whether or not the metric was indeed changed,
        and the second is the original metric
        """
        original_metric = self.model().current_effect

        if len(self.model().dataset) > 2:
            data_type = self.model().get_current_outcome_type()
            if data_type == "binary" or data_type == "continuous":
                default_metric = {
                    "binary": BINARY_ONE_ARM_METRICS[0],
                    "continuous": CONTINUOUS_ONE_ARM_METRICS[0],
                }[data_type]

                if (
                    default_metric != original_metric
                    and self.model().data_for_only_one_arm()
                ):
                    self.set_metric_in_ui(default_metric)
                    return (True, original_metric)
        return (False, original_metric)

    def get_covariate_columns(self):
        return list(range(self.model().OUTCOMES[-1] + 1, self.model().columnCount()))

    def header_clicked(self, column):
        can_sort_by = [self.model().NAME, self.model().YEAR]
        ## plus we can sort by any covariates, which correspond to those columns that are
        # beyond the last outcome
        covariate_columns = self.get_covariate_columns()
        can_sort_by.extend(covariate_columns)

    def sort_by_col(self, column):
        # if a covariate column was clicked, it may not yet have an entry in the
        # reverse_column_sorts dictionary; thus we insert one here
        #
        # This uses the visible column number because sort state is owned by the
        # current table view; rebuild it when covariate columns move or vanish.
        if column not in self.reverse_column_sorts:
            self.reverse_column_sorts[column] = False
        sort_command = CommandSort(
            self.model(), column, self.reverse_column_sorts[column]
        )
        self.undoStack.push(sort_command)
        self.reverse_column_sorts[column] = not self.reverse_column_sorts[column]

    def _normalize_newlines(self, qstr_text):
        if isinstance(qstr_text, str):
            return qstr_text.replace("\r\n", "\n").replace("\r", "\n")
        return qstr_text.replace(_newlines_re, "\n")

    def paste_from_clipboard(self, upper_left_index):
        """pastes the data in the clipboard starting at the currently selected cell."""

        clipboard = required(QApplication.clipboard(), "application clipboard")
        clipboard_text = clipboard.text()

        # Some spreadsheet applications use carriage returns between copied
        # rows; normalize them before parsing.
        clipboard_text = self._normalize_newlines(clipboard_text)

        new_content = self._str_to_matrix(clipboard_text)

        # Drop a trailing blank row commonly included in copied spreadsheet data.
        if self._is_blank_row(new_content[-1]):
            new_content = new_content[:-1]
        new_content = self._normalize_matrix_rows(new_content)
        if not new_content:
            return False

        valid, message = self._preflight_paste(upper_left_index, new_content)
        if not valid:
            self._report_model_data_error(message)
            return False

        lower_row = upper_left_index.row() + len(new_content)
        lower_col = upper_left_index.column() + len(new_content[0])
        print("lower row: %s, lower col: %s" % (lower_row, lower_col))
        num_studies_pre_paste = len(self.model().dataset)
        studies_pre_paste = list(self.model().dataset.studies)
        lower_right_index = self.model().createIndex(lower_row - 1, lower_col - 1)
        old_content = self._str_to_matrix(
            self.copy_contents_in_range(
                upper_left_index, lower_right_index, to_clipboard=False
            )
        )

        print("old content: %s" % old_content)
        print("new content: %s" % new_content)
        print("upper left index:")
        print(self._print_index(upper_left_index))

        paste_command = CommandPaste(
            self,
            new_content,
            old_content,
            upper_left_index,
            studies_pre_paste,
            self.column_widths(),
            "paste %s" % new_content,
        )
        self._last_paste_committed = True
        self.undoStack.push(paste_command)
        return self._last_paste_committed

    def _preflight_paste(self, upper_left_index, content):
        model = self.model()
        if model is None or upper_left_index is None or not upper_left_index.isValid():
            return False, "Select a valid workspace cell before pasting."
        if not content or not content[0]:
            return False, "The clipboard does not contain a rectangular range."
        width = len(content[0])
        if any(len(row) != width for row in content):
            return False, "Clipboard rows must form one rectangular range."
        if upper_left_index.column() + width > model.columnCount():
            return False, "Clipboard data extends beyond the workspace columns."
        if upper_left_index.row() + len(content) > model.rowCount():
            return False, "Clipboard data extends beyond the workspace rows."

        candidate = type(model)(dataset=copy.deepcopy(model.dataset), add_blank_study=False)
        candidate.set_state(copy.deepcopy(model.get_stateful_dict()))
        for row_offset, row in enumerate(content):
            for column_offset, value in enumerate(row):
                index = candidate.index(
                    upper_left_index.row() + row_offset,
                    upper_left_index.column() + column_offset,
                )
                if not candidate.setData(index, value):
                    return False, (
                        getattr(candidate, "last_data_error", None)
                        or "The clipboard data could not be validated."
                    )
        return True, None

    def copy_contents_in_range(self, upper_left_index, lower_right_index, to_clipboard):
        """
        copy the (textual) content of the cells in provided cell_range -- the copied contents will be
        cast to python Unicode strings and returned. If the to_clipboard flag is true, the contents will
        also be copied to the system clipboard
        """
        print(
            "upper left index: %s, upper right index: %s"
            % (
                self._print_index(upper_left_index),
                self._print_index(lower_right_index),
            )
        )
        text_matrix = []

        # +1s are because range() is right interval exclusive
        for row in range(upper_left_index.row(), lower_right_index.row() + 1):
            current_row = []
            for col in range(upper_left_index.column(), lower_right_index.column() + 1):
                cur_index = self.model().createIndex(row, col)
                cur_data = self.model().data(cur_index)
                if cur_data is not None:
                    cur_str = _to_text(cur_data)
                    current_row.append(cur_str)
                else:
                    current_row.append("")
            text_matrix.append(current_row)

        copied_str = self._matrix_to_str(text_matrix)

        if to_clipboard:
            clipboard = required(QApplication.clipboard(), "application clipboard")
            clipboard.setText(copied_str)
        print("copied str: %s" % copied_str)
        return copied_str

    def paste_contents(self, upper_left_index, source_content):
        """
        paste the content in source_content into the matrix starting at the upper_left_coord
        cell. new rows will be added as needed; existing data will be overwritten
        """
        origin_row, origin_col = upper_left_index.row(), upper_left_index.column()
        source_content = self._normalize_matrix_rows(source_content)
        if not source_content:
            return True

        if (
            isinstance(source_content[-1], list)
            and len(" ".join(source_content[-1])) == 0
        ):
            # then there's a blank line; Excel has a habit
            # of appending blank lines (\ns) to copied
            # text -- we get rid of it here
            source_content = source_content[:-1]
            source_content = self._normalize_matrix_rows(source_content)
            if not source_content:
                return True

        # temporarily disable sorting to prevent automatic sorting of pasted data.
        # (note: this is consistent with Excel's approach.)
        original_dataset = copy.deepcopy(self.model().dataset)
        original_state_dict = copy.deepcopy(self.model().get_stateful_dict())
        original_model = self.model()
        original_unsaved = (
            self._main_gui().current_data_unsaved
            if self.main_gui is not None
            else None
        )
        original_model.blockSignals(True)
        failure = None
        try:
            for src_row in range(len(source_content)):
                # do we need to append a row?
                cur_row_count = self.model().rowCount()
                if cur_row_count <= origin_row + src_row:
                    self._add_new_row()

                for src_col in range(len(source_content[0])):
                    # note that we treat all of the data pasted as
                    # one event; i.e., when undo is called, it undos the
                    # whole paste
                    index = self.model().createIndex(
                        origin_row + src_row, origin_col + src_col
                    )
                    if not self.model().setData(
                        index, source_content[src_row][src_col]
                    ):
                        failure = self._model_data_error_message()
                        break
                if failure is not None:
                    break
        except Exception as exc:
            failure = "Exception while pasting: %s" % exc
        finally:
            original_model.blockSignals(False)

        if failure is not None:
            if self.main_gui is not None:
                self._main_gui().set_model(
                    original_dataset, state_dict=original_state_dict
                )
                self._main_gui().current_data_unsaved = original_unsaved
            else:
                original_model.dataset = original_dataset
                original_model.set_state(original_state_dict)
                original_model.reset_model()
            self._report_model_data_error(failure)
            return False
        self.model().reset_model()
        return True

    def set_data_in_model(self, index, val):
        if not self.model().setData(index, val):
            self._report_model_data_error(self._model_data_error_message())
        self.model().reset_model()

    def _model_data_error_message(self):
        return (
            getattr(self.model(), "last_data_error", None)
            or "The entered value could not be used."
        )

    def _report_model_data_error(self, msg):
        if self.main_gui is not None and hasattr(self.main_gui, "data_error"):
            self._main_gui().data_error(msg)
        else:
            QMessageBox.warning(self, "Warning", msg)

    def column_widths(self):
        """returns the current column widths"""
        return [
            self.columnWidth(col_index)
            for col_index in range(self.model().columnCount())
        ]

    def set_metric_in_ui(self, metric):
        """
        calls the method on the UI to change
        the current metric -- this is the same
        method binded to the menu items, so call
        this to programmatically change the metric.
        """
        owner = self._main_gui()
        menu = owner.oneArmMetricMenu
        if metric in TWO_ARM_METRICS:
            menu = owner.twoArmMetricMenu
        owner.metric_selected(metric, menu)

    def _enable_analysis_menus_if_appropriate(self):

        if (
            len(self.model().dataset) >= 2
            and self._get_number_of_included_studies() >= 2
        ):
            self._main_gui().enable_menu_options_that_require_dataset()
        else:
            self._main_gui().disable_menu_options_that_require_dataset()

    def _get_number_of_included_studies(self):
        studies = self.model().dataset.studies
        num_included = 0
        for study in studies:
            if study.include and (not study.manually_excluded):
                num_included += 1
            print(
                (
                    "included: %s, manually excluded: %s"
                    % (str(study.include), str(study.manually_excluded))
                )
            )
        print(("num included: %d" % num_included))
        return num_included

    def _print_index(self, index):
        print("(%s, %s)" % (index.row(), index.column()))

    def _add_new_row(self):
        """
        add a new row to the dataTable; note that we briefly toggle sorting off so the row
        is beneath the existing rows.
        """
        model = self.model()
        cur_row_count = model.rowCount()
        model.insertRow(cur_row_count)

    def _str_to_matrix(self, text, col_delimiter="\t", row_delimiter="\n"):
        """transforms raw text (e.g., from the clipboard) to a structured matrix"""
        m = []
        rows = text.split(row_delimiter)
        for row in rows:
            cur_row = row.split(col_delimiter)
            m.append(cur_row)
        return m

    def _normalize_matrix_rows(self, matrix):
        return tabular_data.normalize_rows(matrix)

    def _is_blank_row(self, r):
        return len(r) == 1 and r[0] == ""

    def _matrix_to_str(
        self, m, col_delimiter="\t", row_delimiter="\n", append_new_line=False
    ):
        """takes a matrix of data (i.e., a nested list) and converts to a string representation"""
        m_str = []
        for row in m:
            m_str.append(col_delimiter.join(row))
        return_str = row_delimiter.join(m_str)
        if append_new_line:
            return_str += row_delimiter
        return return_str

    def _upper_left(self, indexes):
        """returns the upper most index object in the indexes list."""
        if len(indexes) > 0:
            upper_left = indexes[0]
            for index in indexes[1:]:
                if (
                    index.row() < upper_left.row()
                    or index.column() < upper_left.column()
                ):
                    upper_left = index
            return upper_left
        return None

    def _lower_right(self, indexes):
        if len(indexes) > 0:
            lower_right = indexes[0]
            for index in indexes[1:]:
                if (
                    index.row() > lower_right.row()
                    or index.column() > lower_right.column()
                ):
                    lower_right = index
            return lower_right
        return None

    def _add_studies_if_necessary(self, upper_left_index, content):
        """
        if there are not enough studies to contain the content, this will
        add them.
        """
        origin_row, origin_col = upper_left_index.row(), upper_left_index.column()
        num_existing_studies = len(self.model().dataset)

        num_to_add = len(content) - num_existing_studies - origin_row

        last_id = -1
        for i in range(num_to_add):
            # first let's give this a default study name, in case
            # none has been provided
            tmp_study_name = "study %s" % (num_existing_studies + i)
            study_index = self.model().createIndex(
                num_existing_studies + i, self.model().NAME
            )
            study_id = self.model().dataset.max_study_id() + 1
            new_study = Study(study_id)
            self.model().dataset.add_study(new_study)

        # now append a blank study if studies were added.
        if num_to_add > 0:
            new_study = Study(self.model().dataset.max_study_id() + 1)
            # Newly appended placeholder studies remain excluded until populated.
            new_study.include = False
            self.model().dataset.add_study(new_study)
            self.model().study_auto_added = int(new_study.id)

        self.model().reset_model()


class CommandCellEdit(QUndoCommand):
    """
    Here we make use of QT's undo/redo framework. This is an UndoCommand for individual
    cell edits (as opposed to paste actions, which are represented by CommandPaste objects,
    defined below).
    """

    def __init__(
        self,
        ma_data_table_view,
        index,
        original_content,
        new_content,
        ####metric_changed=False, old_metric=None, new_metric=None, # DELETE IF ALL IS WELL
        added_study=None,
        description="",
    ):
        super(CommandCellEdit, self).__init__(description)
        self.first_call = True
        if original_content == None:
            self.original_content = ""
        else:
            self.original_content = original_content
        self.new_content = new_content
        self.row, self.col = index.row(), index.column()
        self.ma_data_table_view = ma_data_table_view
        self.added_study = added_study
        self.something_else = added_study
        self.selection = [
            (selected.row(), selected.column())
            for selected in ma_data_table_view.selectionModel().selectedIndexes()
        ]
        current = ma_data_table_view.currentIndex()
        self.current_cell = (
            (current.row(), current.column()) if current.isValid() else None
        )

        debug_params = dict(
            first_call=True,
            original_content=original_content,
            new_content=new_content,
            row=index.row(),
            col=index.column(),
            ma_data_table_view=ma_data_table_view,
            added_study=added_study,
            something_else=added_study,
        )

        print(("CommandCellEdit created with parameters: %s" % str(debug_params)))

    @DebugHelper
    def redo(self):
        index = self._get_index()

        if self.first_call:
            self.first_call = False
            ###
            # the self.added_study should be true if and only if
            # the event being done *caused* a study to be added.
            # in this case, we'll need to remove the added study
            # on the undo() call

            # self.added_study = self.ma_data_table_view.model().study_auto_added
            # note: previously (10/14/11) there was a call here to set the
            # model's study_auto_added field to None. I don't know why it was
            # here, and removed it.
            #     > self.ma_data_table_view.model().study_auto_added = None
        else:
            model = self.ma_data_table_view.model()
            # here we block signals from the model. this is
            # to prevent memory access problems on the c
            # side of things, when the model emits
            # the data edited signal.
            model.blockSignals(True)
            edit_ok = self._apply_content(model, index, self.new_content)
            self.added_study = self.ma_data_table_view.model().study_auto_added
            self.ma_data_table_view.model().study_auto_added = None

            model.blockSignals(False)
            if not edit_ok:
                self.ma_data_table_view._report_model_data_error(
                    self.ma_data_table_view._model_data_error_message()
                )
            # make the view reflect the update
            self.ma_data_table_view.model().reset_model()

        self.ma_data_table_view._enable_analysis_menus_if_appropriate()
        self.ma_data_table_view.synchronize_column_widths()

        # let everyone know that the data is dirty
        self.ma_data_table_view.dataDirtied.emit()
        self._restore_selection()

    @DebugHelper
    def undo(self):
        # in this case, the original editing action
        # had the effect of appending a row to the spreadsheet.
        # here we remove it.
        if self.added_study is not None:
            self.ma_data_table_view.model().remove_study(self.added_study)

        index = self._get_index()
        model = self.ma_data_table_view.model()

        # as in the redo method, we block signals before
        # editing the model data
        model.blockSignals(True)
        edit_ok = self._apply_content(
            model, index, self.original_content, allow_empty_names=True
        )

        model.blockSignals(False)
        if not edit_ok:
            self.ma_data_table_view._report_model_data_error(
                self.ma_data_table_view._model_data_error_message()
            )
        self.ma_data_table_view.model().reset_model()

        # here is where we check if there are enough studies to actually
        # perform an analysis.
        self.ma_data_table_view._enable_analysis_menus_if_appropriate()
        self.ma_data_table_view.synchronize_column_widths()
        self.ma_data_table_view.dataDirtied.emit()
        self._restore_selection()

    def _get_index(self):
        return self.ma_data_table_view.model().createIndex(self.row, self.col)

    def _apply_content(self, model, index, content, allow_empty_names=False):
        if index.column() == model.INCLUDE_STUDY and hasattr(
            content, "manually_excluded"
        ):
            study = model.dataset.studies[index.row()]
            study.include = bool(content.include)
            study.manually_excluded = bool(content.manually_excluded)
            return True
        return model.setData(
            index, content, allow_empty_names=allow_empty_names
        )

    def _restore_selection(self):
        _restore_table_selection(
            self.ma_data_table_view,
            self.selection,
            self.current_cell,
        )


class CommandPaste(QUndoCommand):
    """
    We again make use of QT's undo/redo framework. this implementation handles the paste action;
    the redo is just repasting the former contents into the same cells.
    """

    def __init__(
        self,
        ma_data_table_view,
        new_content,
        old_content,
        upper_left_coord,
        old_studies,
        old_col_widths,
        description,
    ):
        super(CommandPaste, self).__init__(description)
        self.new_content, self.old_content = new_content, old_content
        self.upper_left_coord = upper_left_coord
        self.old_column_widths = old_col_widths
        self.ma_data_table_view = ma_data_table_view
        self.added_study = None
        self.metric_changed = None
        self.old_metric = None
        self.new_metric = None
        self.selection = [
            (index.row(), index.column())
            for index in ma_data_table_view.selectionModel().selectedIndexes()
        ]
        current = ma_data_table_view.currentIndex()
        self.current_cell = (
            (current.row(), current.column()) if current.isValid() else None
        )
        # is this the first time?
        self.first_call = True

        print("CommandPaste created")

    @DebugHelper
    def redo(self):
        # Snapshot before any row growth so every paste mutation shares one
        # rollback boundary.
        self.original_dataset = copy.deepcopy(self.ma_data_table_view.model().dataset)
        self.original_state_dict = copy.deepcopy(
            self.ma_data_table_view.model().get_stateful_dict()
        )
        self.original_unsaved = self.ma_data_table_view.main_gui.current_data_unsaved

        try:
            self.ma_data_table_view._add_studies_if_necessary(
                self.upper_left_coord, self.new_content
            )
            committed = self.ma_data_table_view.paste_contents(
                self.upper_left_coord, self.new_content
            )
            if not committed:
                self._rollback_failed_redo()
                return

            if self.first_call:
                # On the first application, record any automatic metric change.
                self.metric_changed, self.old_metric = (
                    self.ma_data_table_view.change_metric_if_appropriate()
                )

                if self.metric_changed:
                    self.new_metric = self.ma_data_table_view.model().current_effect
                self.first_call = False
            elif self.metric_changed:
                self.ma_data_table_view.set_metric_in_ui(self.new_metric)

            self.ma_data_table_view.model().reset_model()
            self.ma_data_table_view._enable_analysis_menus_if_appropriate()
            self.ma_data_table_view.dataDirtied.emit()
            self.ma_data_table_view.synchronize_column_widths()
            self._restore_selection()
        except Exception as exc:
            self._rollback_failed_redo("Exception while pasting: %s" % exc)

    def _rollback_failed_redo(self, message=None):
        self.ma_data_table_view.main_gui.set_model(
            self.original_dataset, state_dict=self.original_state_dict
        )
        self.ma_data_table_view.main_gui.current_data_unsaved = self.original_unsaved
        self.ma_data_table_view._last_paste_committed = False
        self.setObsolete(True)
        self._restore_selection()
        if message is not None:
            self.ma_data_table_view._report_model_data_error(message)

    @DebugHelper
    def undo(self):
        if self.added_study is not None:
            self.ma_data_table_view.model().remove_study(self.added_study)
        self.ma_data_table_view.main_gui.set_model(
            self.original_dataset, state_dict=self.original_state_dict
        )

        # did we change the metric automatically (e.g., because it
        # looked like the user was exploring single-arm data?) if
        # so, change it back
        if self.metric_changed:
            self.ma_data_table_view.set_metric_in_ui(self.old_metric)

        self.ma_data_table_view.model().reset_model()
        self.ma_data_table_view._enable_analysis_menus_if_appropriate()
        self.ma_data_table_view.dataDirtied.emit()
        self._restore_selection()

    def _restore_selection(self):
        _restore_table_selection(
            self.ma_data_table_view,
            self.selection,
            self.current_cell,
        )


class CommandEditMAUnit(QUndoCommand):
    def __init__(
        self,
        table_view,
        study_index,
        new_ma_unit,
        old_ma_unit,
        description="MA unit edit",
    ):
        super(CommandEditMAUnit, self).__init__(description)
        self.model = table_view.model()
        self.old_ma_unit = old_ma_unit
        self.new_ma_unit = new_ma_unit
        self.table_view = table_view
        self.study_index = study_index
        self.ma_data_table_view = table_view

        print("CommandEditMAunit created")

    @DebugHelper
    def undo(self):
        self.model.set_current_ma_unit_for_study(self.study_index, self.old_ma_unit)
        self.model.reset_model()
        self.table_view.synchronize_column_widths()
        self.ma_data_table_view.dataDirtied.emit()

    @DebugHelper
    def redo(self):
        self.model.set_current_ma_unit_for_study(self.study_index, self.new_ma_unit)
        self.model.reset_model()
        self.model.try_to_update_outcomes()

        # self.table_view.model().reset_model()
        self.table_view.synchronize_column_widths()
        self.ma_data_table_view.dataDirtied.emit()


class CommandSort(QUndoCommand):
    def __init__(self, ma_data_table_model, col, reverse_order, description="Sort"):
        super(CommandSort, self).__init__(description)
        self.model = ma_data_table_model
        self.col = col
        self.reverse = reverse_order
        self.previous_order = None

        print("CommandSort created")

    def redo(self):
        self.previous_order = self.model.get_ordered_study_ids()
        self.model.sort_studies(self.col, self.reverse)
        self.model.reset_model()

    def undo(self):
        self.model.order_studies(self.previous_order)
        self.model.reset_model()


class StudyDelegate(QItemDelegate):
    def __init__(self, parent=None):
        super(StudyDelegate, self).__init__(parent)

    def eventFilter(  # ty: ignore[invalid-method-override] -- PyQt6's delegate stub rejects this runtime-supported QObject override.
        self, editor: QObject | None, event: QEvent | None
    ) -> bool:
        if (
            isinstance(editor, QWidget)
            and isinstance(event, QKeyEvent)
            and event.type() == QtCore.QEvent.Type.KeyPress
            and event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter)
            and not event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier
        ):
            direction = -1 if event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier else 1
            table = self._table_for_editor(editor)
            edited_index = table.currentIndex() if table is not None else None
            self.commitData.emit(editor)
            self.closeEditor.emit(editor, QtWidgets.QAbstractItemDelegate.EndEditHint.NoHint)
            if table is not None:
                QtCore.QTimer.singleShot(
                    0,
                    lambda: table._move_index_vertically_from(edited_index, direction),
                )
            event.accept()
            return True
        return super(StudyDelegate, self).eventFilter(editor, event)

    def createEditor(self, parent, *args):
        le = QLineEdit(parent)
        return le

    def _table_for_editor(self, editor):
        delegate_parent = self.parent()
        if hasattr(delegate_parent, "_move_current_index_vertically"):
            return delegate_parent

        parent = editor.parent()
        while parent is not None:
            if hasattr(parent, "_move_current_index_vertically"):
                return parent
            parent = parent.parent()
        return None

    def setEditorData(self, editor, index):
        # used to be Qt.DisplayRole
        text = index.model().data(index, Qt.ItemDataRole.EditRole)
        editor.setText(_to_text(text))
