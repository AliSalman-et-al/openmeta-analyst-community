# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Diagnostic outcome data entry dialog."""

import copy
from contextlib import ExitStack
from functools import partial
from typing import TYPE_CHECKING

from PyQt6.QtCore import QEvent, QObject, QSignalBlocker, QTimer, Qt
from PyQt6.QtGui import QAction, QKeySequence, QPalette, QUndoStack
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QHeaderView,
    QSizePolicy,
    QStyle,
    QTableWidgetItem,
    QWidget,
    QWIDGETSIZE_MAX,
)

from rc_metastudio import r_bridge
from rc_metastudio import app_error_handler
from rc_metastudio import adaptive_window
from rc_metastudio import tabular_data
from rc_metastudio.meta_globals import (
    DIAGNOSTIC_METRICS,
    DIAG_FIELDS_TO_RAW_INDICES,
    EMPTY_VALS,
    is_nan,
    is_a_float,
    is_empty,
)
from rc_metastudio import calculator_routines as calc_fncs
from rc_metastudio.runtime_types import required

if TYPE_CHECKING:
    import ui_diagnostic_data_dialog as _ui_diagnostic_data_dialog
else:
    from rc_metastudio.forms import ui_diagnostic_data_dialog as _ui_diagnostic_data_dialog

BACK_CALCULATABLE_DIAGNOSTIC_EFFECTS = ["Sens", "Spec"]
DIAGNOSTIC_RAW_COUNT_CELLS = frozenset(((0, 0), (0, 1), (1, 0), (1, 1)))


class DiagnosticDataDialog(QDialog, _ui_diagnostic_data_dialog.Ui_DiagnosticDataDialog):
    def __init__(
        self, analysis_unit, cur_txs, cur_group_str, conf_level=None, parent=None
    ):
        super(DiagnosticDataDialog, self).__init__(parent)
        self.setupUi(self)
        self._configure_raw_data_table()
        self._configure_semantic_fields()
        self._configure_focus_revelation()
        self._layout_controller = adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )

        if conf_level is None:
            raise ValueError("Confidence level must be specified")
        self.global_conf_level = conf_level
        self.mult = r_bridge.get_mult_from_r(self.global_conf_level)
        self.current_item_data: int | None = None

        self.setup_signals_and_slots()

        self.analysis_unit = analysis_unit
        self.cur_groups = cur_txs
        self.group_str = cur_group_str
        self.cur_effect = "Sens"  # arbitrary
        self.entry_widgets = [
            self.two_by_two_table,
            self.prevalence_txt_box,
            self.low_txt_box,
            self.high_txt_box,
            self.effect_txt_box,
        ]
        self.text_boxes = [
            self.low_txt_box,
            self.high_txt_box,
            self.effect_txt_box,
            self.prevalence_txt_box,
        ]

        self.ci_label.setText(
            "{0:.1f}% Confidence Interval".format(self.global_conf_level)
        )
        self.initialize_form()
        self.setup_back_calculation_feedback()
        self.undoStack = QUndoStack(self)

        self._update_raw_data()  # analysis_unit -> table
        self._populate_effect_cmbo_box()  # make cmbo box entries for effects
        self.set_current_effect()  # fill in current effect data in line edits
        self._update_data_table()  # fill in the rest of the data table
        self._fit_raw_data_columns_for_first_display()
        self.enable_back_calculation_btn()

        self.current_prevalence = self._get_prevalence_str()
        self.two_by_two_table.setCurrentCell(0, 0)
        self.two_by_two_table.setFocus()
        required(
            self.buttonBox.button(QDialogButtonBox.StandardButton.Ok),
            "diagnostic calculator OK button",
        ).setDefault(True)
        self._request_initial_content_refit()

    def _configure_raw_data_table(self):
        """Give the diagnostic grid internal overflow and semantic row height."""
        table = self.two_by_two_table
        # layout-audit: allow=compact-table-overflow; reason=compact table keeps rows visible and owns excess overflow
        table.setMinimumWidth(0)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        header = required(table.horizontalHeader(), "diagnostic table header")
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        height = (
            header.sizeHint().height()
            + sum(table.rowHeight(row) for row in range(table.rowCount()))
            + 2 * table.frameWidth()
            + required(table.horizontalScrollBar(), "diagnostic table scrollbar")
            .sizeHint()
            .height()
        )
        # layout-audit: allow=compact-table-overflow; reason=compact table keeps rows visible and owns excess overflow
        table.setMinimumHeight(height)
        # layout-audit: allow=compact-table-overflow; reason=compact table keeps rows visible and owns excess overflow
        table.setMaximumHeight(height)

    def _configure_semantic_fields(self):
        # layout-audit: allow=content-overflow-control; reason=required content may consume available layout width
        self.effect_cbo_box.setMinimumWidth(0)
        # layout-audit: allow=content-overflow-control; reason=required content may consume available layout width
        self.effect_cbo_box.setMaximumWidth(QWIDGETSIZE_MAX)
        self.effect_cbo_box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._size_line_edit_for_samples(self.prevalence_txt_box, ("0.0000", "1.0000"))

    @staticmethod
    def _size_line_edit_for_samples(line_edit, samples):
        margins = line_edit.textMargins()
        frame = required(line_edit.style(), "diagnostic field style").pixelMetric(
            QStyle.PixelMetric.PM_DefaultFrameWidth, None, line_edit
        )
        required_width = (
            max(line_edit.fontMetrics().horizontalAdvance(value) for value in samples)
            + margins.left()
            + margins.right()
            + 2 * frame
            + 12
        )
        # layout-audit: allow=numeric-domain-control; reason=editor width follows representative values from its numeric domain
        line_edit.setMinimumWidth(required_width)
        # layout-audit: allow=numeric-domain-control; reason=editor width follows representative values from its numeric domain
        line_edit.setMaximumWidth(required_width)
        line_edit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _configure_focus_revelation(self):
        for widget in self.content_widget.findChildren(QWidget):
            widget.installEventFilter(self)

    def eventFilter(  # ty: ignore[invalid-method-override] -- PyQt6's QDialog stub rejects this runtime-supported QObject override.
        self, watched: QObject | None, event: QEvent | None
    ) -> bool:
        if (
            isinstance(watched, QWidget)
            and event is not None
            and event.type() == QEvent.Type.FocusIn
            and self.content_widget.isAncestorOf(watched)
        ):
            self.content_scroll.ensureWidgetVisible(watched)
        return super(DiagnosticDataDialog, self).eventFilter(watched, event)

    def _fit_raw_data_columns_for_first_display(self):
        self._grow_all_raw_data_columns_to_contents()

    def _grow_all_raw_data_columns_to_contents(self):
        for column in range(self.two_by_two_table.columnCount()):
            self._grow_raw_data_column_to_contents(column)

    def _grow_raw_data_column_to_contents(self, column):
        table = self.two_by_two_table
        header = required(table.horizontalHeader(), "diagnostic table header")
        required_width = max(
            header.sectionSizeHint(column), table.sizeHintForColumn(column)
        )
        if required_width > table.columnWidth(column):
            header.resizeSection(column, required_width)

    def _request_initial_content_refit(self):
        controller = self.__dict__.get("_layout_controller")
        if controller is not None and not self.isVisible():
            controller.request_content_refit()

    def initialize_form(self):
        """Initialize all cells to empty items"""
        nrows = self.two_by_two_table.rowCount()
        ncols = self.two_by_two_table.columnCount()

        for row in range(nrows):
            for col in range(ncols):
                self._set_val(row, col, None)

        for txt_box in self.text_boxes:
            txt_box.setText("")

    def setup_signals_and_slots(self):
        self.two_by_two_table.cellChanged.connect(
            app_error_handler.safe_slot(self.cell_changed, parent=self)
        )
        self.two_by_two_table.currentCellChanged.connect(
            app_error_handler.safe_slot(
                self.on_two_by_two_table_currentCellChanged, parent=self
            )
        )
        self.effect_cbo_box.currentTextChanged.connect(
            app_error_handler.safe_slot(
                lambda _text: self.effect_changed(), parent=self
            )
        )
        self.clear_Btn.clicked.connect(
            app_error_handler.safe_slot(self.clear_form, parent=self)
        )
        self.back_calc_Btn.clicked.connect(
            app_error_handler.safe_slot(
                lambda: self.enable_back_calculation_btn(engage=True), parent=self
            )
        )

        self.effect_txt_box.editingFinished.connect(
            app_error_handler.safe_slot(lambda: self.val_changed("est"), parent=self)
        )
        self.low_txt_box.editingFinished.connect(
            app_error_handler.safe_slot(lambda: self.val_changed("lower"), parent=self)
        )
        self.high_txt_box.editingFinished.connect(
            app_error_handler.safe_slot(lambda: self.val_changed("upper"), parent=self)
        )
        self.prevalence_txt_box.editingFinished.connect(
            app_error_handler.safe_slot(
                lambda: self.val_changed("prevalence"), parent=self
            )
        )

        # Add undo/redo actions
        undo = QAction(self)
        redo = QAction(self)
        undo.setShortcut(QKeySequence.StandardKey.Undo)
        redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.addAction(undo)
        self.addAction(redo)
        undo.triggered.connect(
            app_error_handler.safe_slot(lambda _checked=False: self.undo(), parent=self)
        )
        redo.triggered.connect(
            app_error_handler.safe_slot(lambda _checked=False: self.redo(), parent=self)
        )

    def on_two_by_two_table_currentCellChanged(
        self, currentRow, currentColumn, previousRow, previousColumn
    ):
        self.current_item_data = self._get_int(currentRow, currentColumn)

    def setup_back_calculation_feedback(self):
        inconsistency_palette = QPalette()
        inconsistency_palette.setColor(
            QPalette.ColorRole.WindowText, Qt.GlobalColor.red
        )
        self.inconsistencyLabel.setPalette(inconsistency_palette)
        self.inconsistencyLabel.setVisible(False)

    def _mark_table_consistent(self):
        self.inconsistencyLabel.setVisible(False)
        required(
            self.buttonBox.button(QDialogButtonBox.StandardButton.Ok),
            "diagnostic calculator OK button",
        ).setEnabled(True)

    def _mark_table_invalid(self, message):
        self.inconsistencyLabel.setText(str(message))
        self.inconsistencyLabel.setVisible(True)
        # The rejected edit has already been rolled back to a valid state, so
        # acceptance must remain available while the inline guidance is shown.
        required(
            self.buttonBox.button(QDialogButtonBox.StandardButton.Ok),
            "diagnostic calculator OK button",
        ).setEnabled(True)
        self.content_layout.invalidate()
        self.content_widget.updateGeometry()
        self.content_scroll.ensureWidgetVisible(self.inconsistencyLabel)
        QTimer.singleShot(
            0,
            lambda: self._ensure_content_widget_visible(self.inconsistencyLabel),
        )

    def _ensure_content_widget_visible(self, widget):
        try:
            self.content_scroll.ensureWidgetVisible(widget)
            center = widget.mapTo(self.content_widget, widget.rect().center())
            self.content_scroll.ensureVisible(center.x(), center.y(), 12, 12)
        except RuntimeError:
            pass

    def _raw_count_cell_is_editable(self, row, col):
        return (row, col) in DIAGNOSTIC_RAW_COUNT_CELLS

    def _get_int(self, i, j):
        try:
            if not self._is_empty(i, j):
                text = required(
                    self.two_by_two_table.item(i, j),
                    f"diagnostic table cell ({i}, {j})",
                ).text()
                try:
                    int_val = int(text)
                except ValueError:
                    int_val = int(calc_fncs.numeric_value(text))
                return int_val
        except (ArithmeticError, TypeError, ValueError) as exc:
            msg = "Could not convert %s to integer" % self.two_by_two_table.item(i, j)
            QMessageBox.warning(self, "Warning", msg)
            raise ValueError(
                "Could not convert %s to int" % self.two_by_two_table.item(i, j)
            ) from exc

    def cell_data_invalid(self, celldata_string):
        # ignore blank entries
        if calc_fncs.cell_text_is_blank(celldata_string):
            return None

        try:
            value = calc_fncs.numeric_value(celldata_string)
        except ValueError:
            return "Raw data needs to be numeric."

        if not value.is_integer():
            return "Expected a whole number (count), but a decimal value was entered."

        if value < 0:
            return "Counts cannot be negative."
        return None

    def _is_empty(self, i, j):
        val = self.two_by_two_table.item(i, j)
        return val is None or val.text() == "" or val.text() is None

    def _set_val(self, row, col, val):
        if is_nan(val):  # get out quick
            return

        str_val = "" if val in EMPTY_VALS else str(int(val))
        with QSignalBlocker(self.two_by_two_table):
            if self.two_by_two_table.item(row, col) is None:
                self.two_by_two_table.setItem(row, col, QTableWidgetItem(str_val))
            else:
                required(
                    self.two_by_two_table.item(row, col),
                    f"diagnostic table cell ({row}, {col})",
                ).setText(str_val)
            calc_fncs.set_table_item_editable(
                self.two_by_two_table.item(row, col),
                self._raw_count_cell_is_editable(row, col),
            )

    def _set_vals(self, computed_d):
        """Sets values in table widget"""
        with QSignalBlocker(self.two_by_two_table):
            self._set_val(0, 0, computed_d["c11"])
            self._set_val(0, 1, computed_d["c12"])
            self._set_val(1, 0, computed_d["c21"])
            self._set_val(1, 1, computed_d["c22"])
            self._set_val(0, 2, computed_d["r1sum"])
            self._set_val(1, 2, computed_d["r2sum"])
            self._set_val(2, 0, computed_d["c1sum"])
            self._set_val(2, 1, computed_d["c2sum"])
            self._set_val(2, 2, computed_d["total"])

    def _get_prevalence_str(self):
        return str(self.prevalence_txt_box.text())

    def cell_changed(self, row, col):
        if not self._raw_count_cell_is_editable(row, col):
            self._update_data_table()
            self._mark_table_consistent()
            return

        old_analysis_unit, old_table = self._save_analysis_unit_and_table_state(
            table=self.two_by_two_table,
            analysis_unit=self.analysis_unit,
            old_value=self.current_item_data,
            row=row,
            col=col,
            use_old_value=True,
        )
        old_prevalence = self._get_prevalence_str()

        try:
            # Test if entered data is valid (a number)
            warning_msg = self.cell_data_invalid(
                required(
                    self.two_by_two_table.item(row, col),
                    f"diagnostic table cell ({row}, {col})",
                ).text()
            )
            if warning_msg:
                raise ValueError(warning_msg)

            self._update_data_table()  # calculate derived margins from raw counts
            self._mark_table_consistent()
        except Exception as e:
            msg = e.args[0]
            QMessageBox.warning(self, "Warning", msg)  # popup warning
            self.restore_analysis_unit_and_table(
                old_analysis_unit, old_table, old_prevalence
            )  # brings things back to the way they were
            self._mark_table_invalid(msg)
            return  # and leave

        # if we got here, everything seems ok
        try:
            self._update_analysis_unit()  # 2x2 table --> analysis_unit
            self.impute_effects_in_analysis_unit()  # effects   --> analysis_unit
            self.set_current_effect()  # analysis_unit   --> effects
        except Exception as e:
            msg = "Could not compute study effects from the edited raw data: %s" % e
            QMessageBox.warning(self, "Warning", msg)
            self.restore_analysis_unit_and_table(
                old_analysis_unit, old_table, old_prevalence
            )
            return

        new_analysis_unit, new_table = self._save_analysis_unit_and_table_state(
            table=self.two_by_two_table,
            analysis_unit=self.analysis_unit,
            row=row,
            col=col,
            use_old_value=False,
        )
        new_prevalence = self._get_prevalence_str()

        calc_fncs.push_field_edit(
            self.undoStack,
            owner=self,
            restore_state=self.restore_analysis_unit_and_table,
            old_state=(old_analysis_unit, old_table, old_prevalence),
            new_state=(new_analysis_unit, new_table, new_prevalence),
        )

    def restore_analysis_unit(self, old_analysis_unit):
        """Restores the analysis_unit data and resets the form"""
        self.analysis_unit.__dict__ = copy.deepcopy(old_analysis_unit.__dict__)

        self.initialize_form()  # clear form first
        self._update_raw_data()
        self.set_current_effect()
        self._update_data_table()
        self.enable_back_calculation_btn()

    def restore_table(self, old_table_data):
        old_table_data = tabular_data.normalize_rows(old_table_data)
        if not old_table_data:
            return
        nrows = min(len(old_table_data), self.two_by_two_table.rowCount())
        ncols = min(len(old_table_data[0]), self.two_by_two_table.columnCount())

        for row in range(nrows):
            for col in range(ncols):
                self._set_val(row, col, old_table_data[row][col])
        self._update_data_table()
        self._mark_table_consistent()

    def restore_analysis_unit_and_table(
        self, old_analysis_unit, old_table, old_prevalence
    ):
        self.restore_analysis_unit(old_analysis_unit)
        self.restore_table(old_table)
        self.prevalence_txt_box.setText(old_prevalence)

    def _save_analysis_unit_and_table_state(
        self,
        table,
        analysis_unit,
        row=None,
        col=None,
        old_value=None,
        use_old_value=True,
    ):
        # Make backup of table info...
        old_table = calc_fncs.save_table_data(table)
        if use_old_value:
            old_table[row][col] = old_value  # ...from BEFORE the cell changed

        # Make backup copy of analysis_unit
        old_analysis_unit = copy.deepcopy(analysis_unit)
        return old_analysis_unit, old_table

    def get_total_subjects(self):
        return self._get_int(2, 2)

    def _get_table_vals(self):
        """Package table from 2x2 table in to a dictionary"""
        vals_d = {}
        vals_d["c11"] = self._get_int(0, 0)
        vals_d["c12"] = self._get_int(0, 1)
        vals_d["c21"] = self._get_int(1, 0)
        vals_d["c22"] = self._get_int(1, 1)
        vals_d["r1sum"] = self._get_int(0, 2)
        vals_d["r2sum"] = self._get_int(1, 2)
        vals_d["c1sum"] = self._get_int(2, 0)
        vals_d["c2sum"] = self._get_int(2, 1)
        vals_d["total"] = self._get_int(2, 2)
        return vals_d

    def impute_effects_in_analysis_unit(self):
        """Calculate and store values for effects in analysis_unit based on values in 2x2 table"""
        # diagnostic data
        counts = self.get_raw_diag_data()
        tp, fn, fp, tn = counts["TP"], counts["FN"], counts["FP"], counts["TN"]

        # Do what we can if we don't have all the counts
        can_calculate_sens, can_calculate_spec = True, True
        if None in [tp, fn]:
            can_calculate_sens = False
            tp, fn = 0, 0  # dummy data
        if None in [tn, fp]:
            can_calculate_spec = False
            tn, fp = 0, 0  # dummy data

        # sensitivity and specificity
        ests_and_cis = r_bridge.diagnostic_effects_for_study(
            tp,
            fn,
            fp,
            tn,
            metrics=DIAGNOSTIC_METRICS,
            conf_level=self.global_conf_level,
        )

        # now we're going to set the effect estimate/CI on the MA object.
        for metric in DIAGNOSTIC_METRICS:
            if metric.lower() == "sens" and not can_calculate_sens:
                continue
            elif metric.lower() == "spec" and not can_calculate_spec:
                continue

            est, lower, upper = r_bridge.effect_triplet(
                ests_and_cis[metric],
                "calc_scale",
                metric=metric,
            )
            self.analysis_unit.set_effect_and_ci(
                metric, self.group_str, est, lower, upper, mult=self.mult
            )

    def _get_row_col(self, field):
        row = 0 if field in ("FP", "TP") else 1
        col = 1 if field in ("FP", "TN") else 0
        return (row, col)

    def update_2x2_table(self, imputed_dict):
        """Fill in entries in 2x2 table and add data to analysis_unit"""
        # reset relevant column and sums column if we have new data
        if imputed_dict["TP"] and imputed_dict["FN"]:
            self.clear_column(0)
            self.clear_column(2)
        if imputed_dict["TN"] and imputed_dict["FP"]:
            self.clear_column(1)
            self.clear_column(2)

        for field in ["FP", "TP", "TN", "FN"]:
            if (field in imputed_dict) and (imputed_dict[field] is not None):
                row, col = self._get_row_col(field)
                self._set_val(row, col, imputed_dict[field])
                # Update the analysis unit with the completed counts.
                raw_data_index = DIAG_FIELDS_TO_RAW_INDICES[field]

                # Preserve blanks while storing the imputed count.
                self.analysis_unit.tx_groups[self.group_str].raw_data[
                    raw_data_index
                ] = (
                    None
                    if not is_a_float(imputed_dict[field])
                    else float(imputed_dict[field])
                )

    def _update_analysis_unit(self):
        """Copy the table values to the analysis unit."""
        raw_dict = self.get_raw_diag_data()  # values are floats or None
        for field in raw_dict.keys():
            i = DIAG_FIELDS_TO_RAW_INDICES[field]
            self.analysis_unit.tx_groups[self.group_str].raw_data[i] = raw_dict[field]

    def get_raw_diag_data(self, convert_none_to_na_string=False):
        """Return TP, FN, FP, and TN values from the table."""
        empty_value = "NA" if convert_none_to_na_string else None

        d = {}
        d["TP"] = (
            float(self._get_int(0, 0)) if not self._is_empty(0, 0) else empty_value
        )
        d["FN"] = (
            float(self._get_int(1, 0)) if not self._is_empty(1, 0) else empty_value
        )
        d["FP"] = (
            float(self._get_int(0, 1)) if not self._is_empty(0, 1) else empty_value
        )
        d["TN"] = (
            float(self._get_int(1, 1)) if not self._is_empty(1, 1) else empty_value
        )
        return d

    def _text_box_value_is_between_bounds(self, val_str, new_text):
        display_scale_val = ""

        get_disp_scale_val_if_valid = partial(
            calc_fncs.evaluate,
            new_text=new_text,
            analysis_unit=self.analysis_unit,
            curr_effect=self.cur_effect,
            group_str=self.group_str,
            conv_to_disp_scale=partial(
                r_bridge.diagnostic_convert_scale,
                metric_name=self.cur_effect,
                convert_to="display.scale",
            ),
            parent=self,
            mult=self.mult,
        )

        with ExitStack() as signal_blockers:
            for widget in self.entry_widgets:
                signal_blockers.enter_context(QSignalBlocker(widget))
            try:
                if val_str == "est" and not is_empty(new_text):
                    display_scale_val = get_disp_scale_val_if_valid(ci_param="est")
                elif val_str == "lower" and not is_empty(new_text):
                    display_scale_val = get_disp_scale_val_if_valid(ci_param="low")
                elif val_str == "upper" and not is_empty(new_text):
                    display_scale_val = get_disp_scale_val_if_valid(ci_param="high")
                elif val_str == "prevalence" and not is_empty(new_text):
                    get_disp_scale_val_if_valid(
                        opt_cmp_fn=lambda x: 0 <= calc_fncs.numeric_value(x) <= 1,
                        opt_cmp_msg="Prevalence must be between 0 and 1.",
                    )
            # Scale conversion crosses the optional R backend boundary. Any
            # backend failure makes the user-entered value invalid here.
            except Exception:
                return False, False
        return True, display_scale_val

    def _get_txt_from_val_str(self, val_str):
        if val_str == "est":
            return str(self.effect_txt_box.text())
        elif val_str == "lower":
            return str(self.low_txt_box.text())
        elif val_str == "upper":
            return str(self.high_txt_box.text())
        elif val_str == "prevalence":
            return str(self.prevalence_txt_box.text())
        return None  # Unknown value key.

    def val_changed(self, val_str):
        # Backup form state
        old_analysis_unit, old_table = self._save_analysis_unit_and_table_state(
            table=self.two_by_two_table,
            analysis_unit=self.analysis_unit,
            use_old_value=False,
        )
        old_prevalence = self.current_prevalence

        new_text = self._get_txt_from_val_str(val_str)

        no_errors, display_scale_val = self._text_box_value_is_between_bounds(
            val_str, new_text
        )
        if no_errors is False:  # There are errors
            guidance = self._validation_guidance(val_str, new_text)
            self.restore_analysis_unit_and_table(
                old_analysis_unit, old_table, old_prevalence
            )
            with ExitStack() as signal_blockers:
                for widget in self.entry_widgets:
                    signal_blockers.enter_context(QSignalBlocker(widget))
                if val_str == "est":
                    self.effect_txt_box.setFocus()
                elif val_str == "lower":
                    self.low_txt_box.setFocus()
                elif val_str == "upper":
                    self.high_txt_box.setFocus()
                elif val_str == "prevalence":
                    self.prevalence_txt_box.setFocus()
            self._mark_table_invalid(guidance)
            return

        # If we got to this point it means everything is ok so far
        try:
            if display_scale_val not in EMPTY_VALS:
                display_scale_val = float(display_scale_val)
            else:
                display_scale_val = None
        except ValueError:
            # Ignore incomplete numeric input while the user is still editing.
            return None

        calc_scale_val = r_bridge.diagnostic_convert_scale(
            display_scale_val, self.cur_effect, convert_to="calc.scale"
        )

        if val_str == "est":
            self.analysis_unit.set_effect(
                self.cur_effect, self.group_str, calc_scale_val
            )
        elif val_str == "lower":
            self.analysis_unit.set_lower(
                self.cur_effect, self.group_str, calc_scale_val
            )
        elif val_str == "upper":
            self.analysis_unit.set_upper(
                self.cur_effect, self.group_str, calc_scale_val
            )
        elif val_str == "prevalence":
            pass

        new_analysis_unit, new_table = self._save_analysis_unit_and_table_state(
            table=self.two_by_two_table,
            analysis_unit=self.analysis_unit,
            use_old_value=False,
        )
        new_prevalence = self._get_prevalence_str()

        calc_fncs.push_field_edit(
            self.undoStack,
            owner=self,
            restore_state=self.restore_analysis_unit_and_table,
            old_state=(old_analysis_unit, old_table, old_prevalence),
            new_state=(new_analysis_unit, new_table, new_prevalence),
        )

        self.current_prevalence = new_prevalence
        self._mark_table_consistent()

    def _validation_guidance(self, val_str, new_text):
        labels = {
            "est": "Effect estimate",
            "lower": "Lower confidence limit",
            "upper": "Upper confidence limit",
            "prevalence": "Prevalence",
        }
        label = labels.get(val_str, "Entered value")
        try:
            value = calc_fncs.numeric_value(new_text)
        except ValueError:
            return "{} must be numeric.".format(label)
        if val_str == "prevalence" and not 0 <= value <= 1:
            return "Prevalence must be between 0 and 1."

        values = {
            "est": self.effect_txt_box.text(),
            "lower": self.low_txt_box.text(),
            "upper": self.high_txt_box.text(),
        }
        good, message = calc_fncs.between_bounds(
            est=values["est"], low=values["lower"], high=values["upper"]
        )
        if not good and message:
            return str(message).replace("!", ".")
        return "Enter a valid diagnostic effect estimate and confidence interval."

    def effect_changed(self):
        self.cur_effect = str(self.effect_cbo_box.currentText())
        self.set_current_effect()

        self.enable_back_calculation_btn()
        self._mark_table_consistent()

    def _update_raw_data(self):
        """Populates the 2x2 table with whatever parametric data was provided"""
        with QSignalBlocker(self.two_by_two_table):
            field_index = 0
            for col in (0, 1):
                for row in (0, 1):
                    val = self.analysis_unit.get_raw_data_for_group(self.group_str)[
                        field_index
                    ]
                    if val is not None:
                        try:
                            val = str(int(val))
                        except (TypeError, ValueError, OverflowError):
                            val = str(val)
                        item = QTableWidgetItem(val)
                        self.two_by_two_table.setItem(row, col, item)
                    field_index += 1

    def _populate_effect_cmbo_box(self):
        # Back-calculation is currently supported for sensitivity/specificity.
        effects = BACK_CALCULATABLE_DIAGNOSTIC_EFFECTS
        with QSignalBlocker(self.effect_cbo_box):
            self.effect_cbo_box.addItems(effects)
            self.effect_cbo_box.setCurrentIndex(0)

    def set_current_effect(self):
        """Fill in effect text boxes with data from analysis_unit"""
        txt_boxes = dict(
            effect=self.effect_txt_box, lower=self.low_txt_box, upper=self.high_txt_box
        )
        calc_fncs.helper_set_current_effect(
            analysis_unit=self.analysis_unit,
            txt_boxes=txt_boxes,
            current_effect=self.cur_effect,
            group_str=self.group_str,
            data_type="diagnostic",
            mult=self.mult,
        )

    def _update_data_table(self):
        """Try to calculate rest of 2x2 table from existing cells"""
        with ExitStack() as signal_blockers:
            for widget in self.entry_widgets:
                signal_blockers.enter_context(QSignalBlocker(widget))
            params = self._get_table_vals()
            computed_params = calc_fncs.compute_2x2_table_from_inner_counts(params)
            if computed_params:
                self._set_vals(computed_params)  # computed --> table widget

            # Compute prevalence if possible
            if (computed_params["c1sum"] not in EMPTY_VALS) and (
                computed_params["total"] not in EMPTY_VALS
            ):
                prevalence = float(computed_params["c1sum"]) / float(
                    computed_params["total"]
                )
                prev_str = str(prevalence)[:7]
                self.prevalence_txt_box.setText("%s" % prev_str)
        self._grow_all_raw_data_columns_to_contents()

    def clear_column(self, col):
        """Clears out column in table and analysis_unit"""
        for row in range(3):
            self._set_val(row, col, None)

        self._update_analysis_unit()

    def clear_form(self):
        # For undo/redo
        old_analysis_unit, old_table = self._save_analysis_unit_and_table_state(
            table=self.two_by_two_table,
            analysis_unit=self.analysis_unit,
            use_old_value=False,
        )
        old_prevalence = self._get_prevalence_str()

        keys = ["c11", "c12", "r1sum", "c21", "c22", "r2sum", "c1sum", "c2sum", "total"]
        blank_vals = dict(list(zip(keys, [""] * len(keys))))

        self._set_vals(blank_vals)
        self._update_analysis_unit()

        for metric in DIAGNOSTIC_METRICS:
            self.analysis_unit.set_effect_and_ci(
                metric, self.group_str, None, None, None, mult=self.mult
            )

        # clear line edits
        self.set_current_effect()
        with QSignalBlocker(self.prevalence_txt_box):
            self.prevalence_txt_box.setText("")

        calc_fncs.set_table_cells_editable(
            self.two_by_two_table, DIAGNOSTIC_RAW_COUNT_CELLS
        )

        new_analysis_unit, new_table = self._save_analysis_unit_and_table_state(
            table=self.two_by_two_table,
            analysis_unit=self.analysis_unit,
            use_old_value=False,
        )
        new_prevalence = self._get_prevalence_str()

        calc_fncs.push_field_edit(
            self.undoStack,
            owner=self,
            restore_state=self.restore_analysis_unit_and_table,
            old_state=(old_analysis_unit, old_table, old_prevalence),
            new_state=(new_analysis_unit, new_table, new_prevalence),
        )

    def enable_back_calculation_btn(self, engage=False):
        # For undo/redo
        old_analysis_unit, old_table = self._save_analysis_unit_and_table_state(
            table=self.two_by_two_table,
            analysis_unit=self.analysis_unit,
            use_old_value=False,
        )
        old_prevalence = self._get_prevalence_str()

        def build_dict():
            d = {}

            for effect in BACK_CALCULATABLE_DIAGNOSTIC_EFFECTS:
                est, lower, upper = self.analysis_unit.get_effect_and_ci(
                    effect, self.group_str, self.mult
                )

                def conv_to_disp_scale(x):
                    return r_bridge.diagnostic_convert_scale(
                        x, effect, convert_to="display.scale"
                    )

                d_est, d_lower, d_upper = [
                    conv_to_disp_scale(x) for x in [est, lower, upper]
                ]
                for i, r_subkey in enumerate(["", ".lb", ".ub"]):
                    try:
                        d["%s%s" % (effect.lower(), r_subkey)] = float(
                            [d_est, d_lower, d_upper][i]
                        )
                    except (TypeError, ValueError):
                        pass

            x = self.get_total_subjects()
            d["total"] = float(x) if is_a_float(x) else None

            x = self.prevalence_txt_box.text()
            try:
                d["prev"] = calc_fncs.numeric_value(x)
            except ValueError:
                d["prev"] = None

            d["conf.level"] = self.global_conf_level

            # now grab the raw data, if available
            d.update(self.get_raw_diag_data())

            return d

        def new_data(diag_data, imputed):
            new_data = (imputed["TP"], imputed["FP"], imputed["FN"], imputed["TN"])
            old_data = (
                self._get_int(0, 0),
                self._get_int(0, 1),
                self._get_int(1, 0),
                self._get_int(1, 1),
            )

            def is_blank(x):
                return x in EMPTY_VALS

            def new_item_available(old, new):
                return is_blank(old) and not is_blank(new)

            comparison = [
                new_item_available(old_data[i], new_data[i])
                for i in range(len(new_data))
            ]
            if any(comparison):
                changed = True
            else:
                changed = False
            return changed

        diag_data = build_dict()

        imputed = r_bridge.impute_diag_data(diag_data)

        # Leave if nothing was imputed
        if not (imputed["TP"] or imputed["TN"] or imputed["FP"] or imputed["FN"]):
            self.back_calc_Btn.setEnabled(False)
            return None

        if new_data(diag_data, imputed):
            self.back_calc_Btn.setEnabled(True)
        else:
            self.back_calc_Btn.setEnabled(False)

        if not engage:
            return None
        self.update_2x2_table(imputed)
        self._update_data_table()
        self._update_analysis_unit()

        # For undo/redo
        new_analysis_unit, new_table = self._save_analysis_unit_and_table_state(
            table=self.two_by_two_table,
            analysis_unit=self.analysis_unit,
            use_old_value=False,
        )
        new_prevalence = self._get_prevalence_str()

        calc_fncs.push_field_edit(
            self.undoStack,
            owner=self,
            restore_state=self.restore_analysis_unit_and_table,
            old_state=(old_analysis_unit, old_table, old_prevalence),
            new_state=(new_analysis_unit, new_table, new_prevalence),
        )

    def undo(self):
        self.undoStack.undo()

    def redo(self):
        self.undoStack.redo()
