# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Binary outcome data entry dialog."""

import copy
from functools import partial

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor, QKeySequence, QPalette
from PyQt5.QtWidgets import (
    QAction,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QTableWidgetItem,
    QUndoStack,
)

import meta_py_r
import qt_layout
import tabular_data
from meta_globals import *
import calculator_routines as calc_fncs

import forms.ui_binary_data_form
import forms.ui_choose_back_calc_result_form
import app_error_handler

# this is the maximum size of a residual that we're willing to accept
# when computing 2x2 data
THRESHOLD = 1e-5
BINARY_RAW_COUNT_CELLS = frozenset(((0, 0), (0, 1), (1, 0), (1, 1)))


class BinaryDataForm2(QDialog, forms.ui_binary_data_form.Ui_BinaryDataForm):
    def __init__(
        self, ma_unit, cur_txs, cur_group_str, cur_effect, conf_level=None, parent=None
    ):
        super(BinaryDataForm2, self).__init__(parent)
        self.setupUi(self)
        self._configure_raw_data_table()

        if conf_level is None:
            raise ValueError("Confidence level must be specified")
        self.global_conf_level = conf_level
        self.mult = meta_py_r.get_mult_from_r(self.global_conf_level)

        self._setup_signals_and_slots()

        # Assign stuff
        self.ma_unit = ma_unit
        self.cur_groups = cur_txs
        self.group_str = cur_group_str
        self.cur_effect = cur_effect
        self.entry_widgets = [
            self.raw_data_table,
            self.low_txt_box,
            self.high_txt_box,
            self.effect_txt_box,
        ]
        self.text_boxes = [self.low_txt_box, self.high_txt_box, self.effect_txt_box]

        self.ci_label.setText(
            "{0:.1f}% Confidence Interval".format(self.global_conf_level)
        )
        self.initialize_form()  # initialize all cell to empty items
        self.setup_back_calculation_feedback()
        self.undoStack = QUndoStack(self)

        # self.setup_clear_button_palettes()    # Color for clear_button_pallette
        self._update_raw_data()  # ma_unit --> table
        self._populate_effect_data()  # make combo boxes for effects
        self.set_current_effect()  # fill in current effect data in line edits
        self._update_data_table()  # fill in 2x2
        self.enable_back_calculation_btn()
        qt_layout.fit_analysis_dialog_to_contents(self)

    def _configure_raw_data_table(self):
        table = self.raw_data_table
        table.setHorizontalHeaderLabels(["Event", "No Event", "Total"])
        table.setVerticalHeaderLabels(["Group 1", "Group 2", "Total"])
        table.horizontalHeader().setVisible(True)
        table.verticalHeader().setVisible(True)
        table.horizontalHeader().setHighlightSections(False)
        table.verticalHeader().setHighlightSections(False)
        qt_layout.configure_compact_table(table, stretch_columns=True)
        for label in (
            self.event_lbl_3,
            self.label_18,
            self.label_19,
            self.label_20,
            self.label_21,
            self.label_22,
        ):
            label.setVisible(False)

    def initialize_form(self):
        """Initialize all cells to empty items"""
        print("Entering initialize_table_items")

        nrows = self.raw_data_table.rowCount()
        ncols = self.raw_data_table.columnCount()

        for row in range(nrows):
            for col in range(ncols):
                self._set_val(row, col, None)

        for txt_box in self.text_boxes:
            txt_box.setText("")

    #    def setup_clear_button_palettes(self):
    #        # Color for clear_button_pallette
    #        self.orig_palette = self.clear_Btn.palette()
    #        self.pushme_palette = QPalette()
    #        self.pushme_palette.setColor(QPalette.ButtonText, Qt.red)
    #        #self.set_clear_btn_color()

    #    def set_clear_btn_color(self):
    #        if calc_fncs._input_fields_disabled(self.raw_data_table, self.text_boxes):
    #            self.clear_Btn.setPalette(self.pushme_palette)
    #        else:
    #            self.clear_Btn.setPalette(self.orig_palette)

    def print_effects_dict_from_ma_unit(self):
        print(self.ma_unit.get_effects_dict())

    def enable_back_calculation_btn(self, engage=False):
        # For undo/redo
        old_ma_unit, old_table = self._save_ma_unit_and_table_state(
            table=self.raw_data_table, ma_unit=self.ma_unit, use_old_value=False
        )

        def build_back_calc_args_dict():

            d = {}
            d["metric"] = str(self.cur_effect)

            est, lower, upper = self.ma_unit.get_effect_and_ci(
                self.cur_effect, self.group_str, self.mult
            )
            conv_to_disp_scale = lambda x: meta_py_r.binary_convert_scale(
                x, self.cur_effect, convert_to="display.scale"
            )
            d_est, d_lower, d_upper = [
                conv_to_disp_scale(x) for x in [est, lower, upper]
            ]
            for i, R_key in enumerate(["estimate", "lower", "upper"]):
                try:
                    d["%s" % R_key] = float([d_est, d_lower, d_upper][i])
                except:
                    d["%s" % R_key] = None

            d["conf.level"] = self.global_conf_level

            d["Ev_A"] = float(self._get_int(0, 0)) if not self._is_empty(0, 0) else None
            d["N_A"] = float(self._get_int(0, 2)) if not self._is_empty(0, 2) else None
            d["Ev_B"] = float(self._get_int(1, 0)) if not self._is_empty(1, 0) else None
            d["N_B"] = float(self._get_int(1, 2)) if not self._is_empty(1, 2) else None

            return d

        def new_data(bin_data, imputed):
            changed = False
            old_data = (
                bin_data["Ev_A"],
                bin_data["N_A"],
                bin_data["Ev_B"],
                bin_data["N_B"],
            )
            new_data = []
            new_data.append(
                (
                    int(round(imputed["op1"]["a"])),
                    int(round(imputed["op1"]["b"])),
                    int(round(imputed["op1"]["c"])),
                    int(round(imputed["op1"]["d"])),
                )
            )
            if "op2" in imputed:
                new_data.append(
                    (
                        int(round(imputed["op2"]["a"])),
                        int(round(imputed["op2"]["b"])),
                        int(round(imputed["op2"]["c"])),
                        int(round(imputed["op2"]["d"])),
                    )
                )

            def new_item_available(old, new):
                isBlank = lambda x: x in EMPTY_VALS
                no_longer_blank = isBlank(old) and not isBlank(new)
                return no_longer_blank

            comparison0 = [
                new_item_available(old_data[i], new_data[0][i])
                for i in range(len(old_data))
            ]
            new_data_in_op1 = any(comparison0)
            print(("Comparison0:", comparison0))

            if new_data_in_op1:
                changed = True
                if "op2" in imputed:
                    comparison1 = [
                        new_item_available(old_data[i], new_data[1][i])
                        for i in range(len(old_data))
                    ]
                    print(("Comparison1:", comparison1))
                    new_data_in_op2 = any(comparison1)
                    if not new_data_in_op2:
                        changed = False
            else:
                changed = False

            return changed

        ### end of new_data() definition ####

        # Makes no sense to show the button on a form where the back
        # calculation is not implemented
        if not self.cur_effect in ["OR", "RR", "RD"]:
            self.back_calc_btn.setVisible(False)
            return None
        else:
            self.back_calc_btn.setVisible(True)

        bin_data = build_back_calc_args_dict()
        print(("Binary data for back-calculation:", bin_data))

        imputed = meta_py_r.impute_bin_data(bin_data.copy())
        print(("Imputed data: %s", imputed))

        # Leave if nothing was imputed
        if "FAIL" in imputed:
            print("Fail to impute")
            self.back_calc_btn.setEnabled(False)
            return None

        if new_data(bin_data, imputed):
            self.back_calc_btn.setEnabled(True)
        else:
            self.back_calc_btn.setEnabled(False)

        # self.set_clear_btn_color()

        if not engage:
            return None
        ########################################################################
        # Actually do stuff with imputed data here if we are 'engaged'
        ########################################################################
        for x in range(3):
            self.clear_column(x)  # clear out the table

        if len(list(imputed.keys())) > 1:
            dialog = ChooseBackCalcResultForm(imputed, parent=self)
            if dialog.exec():
                choice = dialog.getChoice()
            else:  # don't do anything if cancelled
                return None
        else:  # only one option
            choice = "op1"

        # set values in table & save in ma_unit
        self.raw_data_table.blockSignals(True)
        group_1_events = int(round(imputed[choice]["a"]))
        group_1_total = int(round(imputed[choice]["b"]))
        group_2_events = int(round(imputed[choice]["c"]))
        group_2_total = int(round(imputed[choice]["d"]))
        self._set_val(0, 0, group_1_events)
        self._set_val(0, 1, group_1_total - group_1_events)
        self._set_val(1, 0, group_2_events)
        self._set_val(1, 1, group_2_total - group_2_events)
        self.raw_data_table.blockSignals(False)

        self._update_data_table()
        self._update_ma_unit()  # save in ma_unit
        # self.set_clear_btn_color()

        # for undo/redo
        new_ma_unit, new_table = self._save_ma_unit_and_table_state(
            table=self.raw_data_table, ma_unit=self.ma_unit, use_old_value=False
        )
        restore_old_f = lambda: self.restore_ma_unit_and_table(old_ma_unit, old_table)
        restore_new_f = lambda: self.restore_ma_unit_and_table(new_ma_unit, new_table)
        command = calc_fncs.CommandFieldChanged(
            restore_new_f=restore_new_f, restore_old_f=restore_old_f, parent=self
        )
        self.undoStack.push(command)

    def setup_back_calculation_feedback(self):
        inconsistency_palette = QPalette()
        inconsistency_palette.setColor(QPalette.WindowText, Qt.red)
        self.inconsistencyLabel.setPalette(inconsistency_palette)
        self.inconsistencyLabel.setVisible(False)

    def _mark_table_consistent(self):
        self.inconsistencyLabel.setVisible(False)
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)

    def _raw_count_cell_is_editable(self, row, col):
        return (row, col) in BINARY_RAW_COUNT_CELLS

    def on_raw_data_table_currentCellChanged(
        self, currentRow, currentColumn, previousRow, previousColumn
    ):
        self.current_item_data = self._get_int(currentRow, currentColumn)
        print("Current Item Data:", self.current_item_data)

    def _setup_signals_and_slots(self):
        self.raw_data_table.cellChanged.connect(
            app_error_handler.safe_slot(self.cell_changed, parent=self)
        )

        self.effect_cbo_box.currentIndexChanged[str].connect(
            app_error_handler.safe_slot(
                lambda _text: self.effect_changed(), parent=self
            )
        )
        self.clear_Btn.clicked.connect(
            app_error_handler.safe_slot(self.clear_form, parent=self)
        )
        self.back_calc_btn.clicked.connect(
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

        # Add undo/redo actions
        undo = QAction(self)
        redo = QAction(self)
        undo.setShortcut(QKeySequence.Undo)
        redo.setShortcut(QKeySequence.Redo)
        self.addAction(undo)
        self.addAction(redo)
        undo.triggered.connect(
            app_error_handler.safe_slot(lambda _checked=False: self.undo(), parent=self)
        )
        redo.triggered.connect(
            app_error_handler.safe_slot(lambda _checked=False: self.redo(), parent=self)
        )

    def _populate_effect_data(self):
        available_effects = set(
            str(effect) for effect in self.ma_unit.effects_dict.keys()
        )
        metric_family = (
            BINARY_ONE_ARM_METRICS
            if self.cur_effect in BINARY_ONE_ARM_METRICS
            else BINARY_TWO_ARM_METRICS
        )
        q_effects = [effect for effect in metric_family if effect in available_effects]
        if self.cur_effect not in q_effects:
            q_effects.append(str(self.cur_effect))
        self.effect_cbo_box.blockSignals(True)
        self.effect_cbo_box.clear()
        for effect in q_effects:
            self.effect_cbo_box.addItem(
                self._effect_display_label(effect), userData=effect
            )
        self.effect_cbo_box.setMaximumWidth(260)
        self.effect_cbo_box.setMinimumWidth(self.effect_cbo_box.sizeHint().width())
        self.effect_cbo_box.setCurrentIndex(q_effects.index(str(self.cur_effect)))
        self.effect_cbo_box.blockSignals(False)

    def get_effect_names(self):
        return self.ma_unit.get_effect_names()

    def _effect_display_label(self, effect):
        return "%s (%s)" % (BINARY_METRIC_NAMES.get(effect, effect), effect)

    def _selected_effect(self):
        effect = self.effect_cbo_box.currentData()
        if effect is None:
            effect = self.effect_cbo_box.currentText()
        return str(effect)

    def set_current_effect(self):
        """Fills in text boxes with data from ma unit"""

        txt_boxes = dict(
            effect=self.effect_txt_box, lower=self.low_txt_box, upper=self.high_txt_box
        )
        calc_fncs.helper_set_current_effect(
            ma_unit=self.ma_unit,
            txt_boxes=txt_boxes,
            current_effect=self.cur_effect,
            group_str=self.group_str,
            data_type="binary",
            mult=self.mult,
        )

        self.change_row_color_according_to_metric()

    def change_row_color_according_to_metric(self):
        # Change color of bottom rows of table according one or two-arm metric
        curr_effect_is_one_arm = self.cur_effect in BINARY_ONE_ARM_METRICS
        for row in (1, 2):
            for col in range(3):
                item = self.raw_data_table.item(row, col)
                if curr_effect_is_one_arm:
                    item.setBackground(QBrush(QColor(Qt.gray)))
                else:
                    # just reset the item
                    text = item.text()
                    self.raw_data_table.blockSignals(True)
                    popped_item = self.raw_data_table.takeItem(row, col)
                    self.raw_data_table.blockSignals(False)
                    del popped_item
                    self._set_val(row, col, text)

    def effect_changed(self):
        """Called when a new effect is selected in the combo box"""

        self.cur_effect = self._selected_effect()
        self.group_str = self.get_cur_group_str()

        self.try_to_update_cur_outcome()
        self.set_current_effect()

        self.enable_txt_box_input()
        self.enable_back_calculation_btn()

    def _text_box_value_is_between_bounds(self, val_str, new_text):
        display_scale_val = ""

        get_disp_scale_val_if_valid = partial(
            calc_fncs.evaluate,
            new_text=new_text,
            ma_unit=self.ma_unit,
            curr_effect=self.cur_effect,
            group_str=self.group_str,
            conv_to_disp_scale=partial(
                meta_py_r.binary_convert_scale,
                metric_name=self.cur_effect,
                convert_to="display.scale",
            ),
            parent=self,
            mult=self.mult,
        )

        calc_fncs.block_signals(self.entry_widgets, True)
        try:
            if val_str == "est" and not is_empty(new_text):
                display_scale_val = get_disp_scale_val_if_valid(ci_param="est")
            elif val_str == "lower" and not is_empty(new_text):
                display_scale_val = get_disp_scale_val_if_valid(ci_param="low")
            elif val_str == "upper" and not is_empty(new_text):
                display_scale_val = get_disp_scale_val_if_valid(ci_param="high")
        except Exception:
            calc_fncs.block_signals(self.entry_widgets, False)
            return False, False
        calc_fncs.block_signals(self.entry_widgets, False)
        print(("Val_str: %s" % val_str))
        return True, display_scale_val

    def _get_txt_from_val_str(self, val_str):
        if val_str == "est":
            return str(self.effect_txt_box.text())
        elif val_str == "lower":
            return str(self.low_txt_box.text())
        elif val_str == "upper":
            return str(self.high_txt_box.text())
        return None  # Unknown value key.

    def val_changed(self, val_str):
        # Backup form state
        old_ma_unit, old_table = self._save_ma_unit_and_table_state(
            table=self.raw_data_table, ma_unit=self.ma_unit, use_old_value=False
        )

        new_text = self._get_txt_from_val_str(val_str)

        no_errors, display_scale_val = self._text_box_value_is_between_bounds(
            val_str, new_text
        )
        if no_errors is False:  # There are errors
            self.restore_ma_unit_and_table(old_ma_unit, old_table)
            calc_fncs.block_signals(self.entry_widgets, True)
            if val_str == "est":
                self.effect_txt_box.setFocus()
            elif val_str == "lower":
                self.low_txt_box.setFocus()
            elif val_str == "upper":
                self.high_txt_box.setFocus()
            calc_fncs.block_signals(self.entry_widgets, False)
            return

        # If we got to this point it means everything is ok so far
        try:
            if display_scale_val not in EMPTY_VALS:
                display_scale_val = float(display_scale_val)
            else:
                display_scale_val = None
        except ValueError:
            # Ignore incomplete numeric input while the user is still editing.
            print("fail.")
            return None

        calc_scale_val = meta_py_r.binary_convert_scale(
            display_scale_val, self.cur_effect, convert_to="calc.scale"
        )

        if val_str == "est":
            self.ma_unit.set_effect(self.cur_effect, self.group_str, calc_scale_val)
        elif val_str == "lower":
            self.ma_unit.set_lower(self.cur_effect, self.group_str, calc_scale_val)
        elif val_str == "upper":
            self.ma_unit.set_upper(self.cur_effect, self.group_str, calc_scale_val)

        new_ma_unit, new_table = self._save_ma_unit_and_table_state(
            table=self.raw_data_table, ma_unit=self.ma_unit, use_old_value=False
        )
        restore_old_f = lambda: self.restore_ma_unit_and_table(old_ma_unit, old_table)
        restore_new_f = lambda: self.restore_ma_unit_and_table(new_ma_unit, new_table)
        command = calc_fncs.CommandFieldChanged(
            restore_new_f=restore_new_f, restore_old_f=restore_old_f, parent=self
        )
        self.undoStack.push(command)

    def _update_raw_data(self):
        """Generates the 2x2 table with whatever parametric data was provided"""
        """Sets events and non-events from stored events and arm totals."""

        print("_update_raw_data:")
        for row, group in enumerate(self.cur_groups):
            events, total = self.ma_unit.get_raw_data_for_group(group)
            no_events = None
            if events not in EMPTY_VALS and total not in EMPTY_VALS:
                no_events = total - events
            self._set_val(row, 0, events)
            self._set_val(row, 1, no_events)

    def _update_ma_unit(self):
        """Copy data from binary data table to the MA_unit"""
        """ 
        Walk over the entries in the matrix (which may have been updated
        via imputation in the cell_changed method) corresponding to the 
        raw data in the underlying meta-analytic unit and update the values.
        """
        for row in range(2):
            events = self._get_int(row, 0)
            no_events = self._get_int(row, 1)
            total = None
            if events not in EMPTY_VALS and no_events not in EMPTY_VALS:
                total = events + no_events
            raw_data = self.ma_unit.get_raw_data_for_group(self.cur_groups[row])
            raw_data[0] = events
            raw_data[1] = total

            print("%s events: %s, total: %s" % (row, events, total))
        print(
            "ok -- raw data is now: %s"
            % calc_fncs.get_raw_data(self.ma_unit, self.cur_groups)
        )

    def _cell_data_not_valid(self, celldata_string):
        # ignore blank entries
        if calc_fncs.cell_text_is_blank(celldata_string):
            return None

        if not is_a_float(celldata_string):
            return "Raw data needs to be numeric."

        if not is_an_int(celldata_string):
            return "Expected a whole number (count), but a decimal value was entered."

        if int(celldata_string) < 0:
            return "Counts cannot be negative."
        return None

    def restore_ma_unit(self, old_ma_unit):
        """Restores the ma_unit data and resets the form"""
        self.ma_unit.__dict__ = copy.deepcopy(old_ma_unit.__dict__)
        print(
            (
                "Restored ma_unit data: %s"
                % str(self.ma_unit.get_raw_data_for_groups(self.cur_groups))
            )
        )

        self.initialize_form()  # clear form first
        self._update_raw_data()
        self.set_current_effect()
        self._update_data_table()
        self.enable_back_calculation_btn()
        # self.set_clear_btn_color()

    def restore_table(self, old_table):
        old_table = tabular_data.normalize_rows(old_table)
        if not old_table:
            return
        nrows = min(len(old_table), self.raw_data_table.rowCount())
        ncols = min(len(old_table[0]), self.raw_data_table.columnCount())

        for row in range(nrows):
            for col in range(ncols):
                self.raw_data_table.blockSignals(True)
                self._set_val(row, col, old_table[row][col])
                self.raw_data_table.blockSignals(False)
        self._update_data_table()
        self._mark_table_consistent()

    def restore_ma_unit_and_table(self, old_ma_unit, old_table):
        self.restore_ma_unit(old_ma_unit)
        self.restore_table(old_table)

    def _save_ma_unit_and_table_state(
        self, table, ma_unit, row=None, col=None, old_value=None, use_old_value=True
    ):
        # Make backup of table info...
        old_table = calc_fncs.save_table_data(table)
        if use_old_value:
            old_table[row][col] = old_value  # ...from BEFORE the cell changed

        # Make backup copy of ma_unit
        old_ma_unit = copy.deepcopy(ma_unit)
        return old_ma_unit, old_table

    def cell_changed(self, row, col):
        # tries to make sense of user input before passing
        # on to the R routine

        if not self._raw_count_cell_is_editable(row, col):
            self._update_data_table()
            self._mark_table_consistent()
            return

        old_ma_unit, old_table = self._save_ma_unit_and_table_state(
            table=self.raw_data_table,
            ma_unit=self.ma_unit,
            old_value=self.current_item_data,
            row=row,
            col=col,
            use_old_value=True,
        )

        try:
            # Test if entered data is valid (a number)
            warning_msg = self._cell_data_not_valid(
                self.raw_data_table.item(row, col).text()
            )
            if warning_msg:
                raise Exception("Invalid Cell Data")

            self._update_data_table()  # calculate derived margins from raw counts
            self._mark_table_consistent()
        except Exception as e:
            msg = e.args[0]
            QMessageBox.warning(self.parent(), "Warning", msg)  # popup warning
            self.restore_ma_unit_and_table(
                old_ma_unit, old_table
            )  # brings things back to the way they were
            return  # and leave

        try:
            self._update_ma_unit()  # table widget --> ma_unit
            self.try_to_update_cur_outcome()  # update metric in ma_unit and in table
        except Exception as e:
            msg = "Could not compute study effects from the edited raw data: %s" % e
            QMessageBox.warning(self.parent(), "Warning", msg)
            self.restore_ma_unit_and_table(old_ma_unit, old_table)
            return

        new_ma_unit, new_table = self._save_ma_unit_and_table_state(
            table=self.raw_data_table,
            ma_unit=self.ma_unit,
            row=row,
            col=col,
            use_old_value=False,
        )
        # restore_f = self.restore_ma_unit_and_table
        # command = calc_fncs.CommandFieldChanged(old_ma_unit, new_ma_unit, old_table, new_table, restore_f=restore_f, parent=self)
        restore_old_f = lambda: self.restore_ma_unit_and_table(old_ma_unit, old_table)
        restore_new_f = lambda: self.restore_ma_unit_and_table(new_ma_unit, new_table)
        command = calc_fncs.CommandFieldChanged(
            restore_new_f=restore_new_f, restore_old_f=restore_old_f, parent=self
        )
        self.undoStack.push(command)

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

    def clear_column(self, col):
        """Clears out column in table and ma_unit"""

        for row in range(3):
            self.raw_data_table.blockSignals(True)
            self._set_val(row, col, None)
            self.raw_data_table.blockSignals(False)

        self._update_ma_unit()

    def _set_vals(self, computed_d):
        """Sets values in table widget"""
        self.raw_data_table.blockSignals(True)
        self._set_val(0, 0, computed_d["c11"])
        self._set_val(0, 1, computed_d["c12"])
        self._set_val(1, 0, computed_d["c21"])
        self._set_val(1, 1, computed_d["c22"])
        self._set_val(0, 2, computed_d["r1sum"])
        self._set_val(1, 2, computed_d["r2sum"])
        self._set_val(2, 0, computed_d["c1sum"])
        self._set_val(2, 1, computed_d["c2sum"])
        self._set_val(2, 2, computed_d["total"])
        self.raw_data_table.blockSignals(False)

    def _set_val(self, row, col, val):
        if is_NaN(val):  # get out quick
            print("%s is not a number" % val)
            return

        try:
            self.raw_data_table.blockSignals(True)
            str_val = "" if val in EMPTY_VALS else str(int(val))
            if self.raw_data_table.item(row, col) == None:
                self.raw_data_table.setItem(row, col, QTableWidgetItem(str_val))
            else:
                self.raw_data_table.item(row, col).setText(str_val)
            calc_fncs.set_table_item_editable(
                self.raw_data_table.item(row, col),
                self._raw_count_cell_is_editable(row, col),
            )
            print(("    setting (%d,%d) to '%s'" % (row, col, str_val)))

            #            # disable item
            #            if str_val != "":
            #                item = self.raw_data_table.item(row, col)
            #                newflags = item.flags() & ~Qt.ItemIsEditable
            #                item.setFlags(newflags)

            self.raw_data_table.blockSignals(False)
        except:
            print(
                (
                    "    Got to except in _set_val when trying to set (%d,%d)"
                    % (row, col)
                )
            )
            raise

    def _update_data_table(self):
        """Fill in 2x2 table from other entries in the table"""

        self.raw_data_table.blockSignals(True)

        params = self._get_table_vals()
        computed_params = calc_fncs.compute_2x2_table_from_inner_counts(params)
        print("Computed Params", computed_params)
        if computed_params:
            self._set_vals(computed_params)  # computed --> table widget

        self.raw_data_table.blockSignals(False)

    def _is_empty(self, i, j):
        val = self.raw_data_table.item(i, j)
        return val is None or val.text() == ""

    def _get_int(self, i, j):
        """Get value from cell specified by row=i, col=j as an integer"""
        if not self._is_empty(i, j):
            val = int(float(self.raw_data_table.item(i, j).text()))
            # print("Val from _get_int: %d" % val)
            return val
        else:
            return None  # its good to be explicit

    def _isBlank(self, x):
        return x is None or x == ""

    def try_to_update_cur_outcome(self):
        e1, n1, e2, n2 = self.ma_unit.get_raw_data_for_groups(self.cur_groups)
        print(("e1: %s, n1: %s, e2: %s, n2: %s" % (str(e1), str(n1), str(e2), str(n2))))

        two_arm_raw_data_ok = not any([self._isBlank(x) for x in [e1, n1, e2, n2]])
        one_arm_raw_data_ok = not any([self._isBlank(x) for x in [e1, n1]])
        curr_effect_is_one_arm = self.cur_effect in BINARY_ONE_ARM_METRICS
        curr_effect_is_two_arm = self.cur_effect in BINARY_TWO_ARM_METRICS

        # Leave current effects untouched when raw data are incomplete.
        if two_arm_raw_data_ok or (curr_effect_is_one_arm and one_arm_raw_data_ok):
            if curr_effect_is_two_arm:
                est_and_ci_d = meta_py_r.effect_for_study(
                    e1,
                    n1,
                    e2,
                    n2,
                    metric=self.cur_effect,
                    conf_level=self.global_conf_level,
                )
            else:
                # binary, one-arm
                est_and_ci_d = meta_py_r.effect_for_study(
                    e1,
                    n1,
                    two_arm=False,
                    metric=self.cur_effect,
                    conf_level=self.global_conf_level,
                )

            est, low, high = meta_py_r.effect_triplet(
                est_and_ci_d,
                "calc_scale",
                metric=self.cur_effect,
            )
            self.ma_unit.set_effect_and_ci(
                self.cur_effect, self.group_str, est, low, high, mult=self.mult
            )
            self.set_current_effect()

    def clear_form(self):
        # For undo/redo
        old_ma_unit, old_table = self._save_ma_unit_and_table_state(
            table=self.raw_data_table, ma_unit=self.ma_unit, use_old_value=False
        )

        blank_vals = {
            "c11": "",
            "c12": "",
            "r1sum": "",
            "c21": "",
            "c22": "",
            "r2sum": "",
            "c1sum": "",
            "c2sum": "",
            "total": "",
        }

        self._set_vals(blank_vals)
        self._update_ma_unit()

        # clear out effects stuff
        for metric in BINARY_ONE_ARM_METRICS + BINARY_TWO_ARM_METRICS:
            if (
                self.cur_effect in BINARY_TWO_ARM_METRICS
                and metric in BINARY_TWO_ARM_METRICS
            ) or (
                self.cur_effect in BINARY_ONE_ARM_METRICS
                and metric in BINARY_ONE_ARM_METRICS
            ):
                self.ma_unit.set_effect_and_ci(
                    metric, self.group_str, None, None, None, mult=self.mult
                )
            else:
                # Future work: handle remapping if group labels become editable here.
                pass

        # clear line edits
        self.set_current_effect()
        calc_fncs.set_table_cells_editable(self.raw_data_table, BINARY_RAW_COUNT_CELLS)
        ####self.enable_txt_box_input()

        new_ma_unit, new_table = self._save_ma_unit_and_table_state(
            table=self.raw_data_table, ma_unit=self.ma_unit, use_old_value=False
        )
        restore_old_f = lambda: self.restore_ma_unit_and_table(old_ma_unit, old_table)
        restore_new_f = lambda: self.restore_ma_unit_and_table(new_ma_unit, new_table)
        command = calc_fncs.CommandFieldChanged(
            restore_new_f=restore_new_f, restore_old_f=restore_old_f, parent=self
        )
        self.undoStack.push(command)

    def enable_txt_box_input(self):
        # meta_globals.enable_txt_box_input(self.effect_txt_box, self.low_txt_box,
        #                                  self.high_txt_box)
        # print("Enabled text box input")
        pass

    def get_cur_group_str(self):
        # Inspired from get_cur_group_str of ma_data_table_model

        if self.cur_effect in BINARY_ONE_ARM_METRICS:
            group_str = self.cur_groups[0]
        else:
            group_str = "-".join(self.cur_groups)
        return group_str

    ####### Undo framework ############
    def undo(self):
        print("undoing....")
        self.undoStack.undo()

    def redo(self):
        print("redoing....")
        self.undoStack.redo()

    #################################


################################################################################
class ChooseBackCalcResultForm(
    QDialog, forms.ui_choose_back_calc_result_form.Ui_ChooseBackCalcResultForm
):
    def __init__(self, imputed_data, parent=None):
        super(ChooseBackCalcResultForm, self).__init__(parent)
        self.setupUi(self)

        op1 = imputed_data["op1"]  # option 1 data
        a, b, c, d = op1["a"], op1["b"], op1["c"], op1["d"]
        a, b, c, d = int(round(a)), int(round(b)), int(round(c)), int(round(d))
        option1_txt = (
            "Group 1:\n  #events: %d\n  Total: %d\n\nGroup 2:\n  #events: %d\n  Total: %d"
            % (a, b, c, d)
        )

        op2 = imputed_data["op2"]
        a, b, c, d = op2["a"], op2["b"], op2["c"], op2["d"]
        a, b, c, d = int(round(a)), int(round(b)), int(round(c)), int(round(d))
        option2_txt = (
            "Group 1:\n  #events: %d\n  Total: %d\n\nGroup 2:\n  #events: %d\n  Total: %d"
            % (a, b, c, d)
        )

        self.choice1_btn.setText(option1_txt)
        self.choice2_btn.setText(option2_txt)
        self.info_label.setText(
            "The back-calculation has resulted in two "
            "possible sets of choices for the counts. Please"
            " choose one from below. These choices do not "
            "reflect possible corrections for zero counts."
        )

        qt_layout.fit_analysis_dialog_to_contents(self)

    def getChoice(self):
        choices = ["op1", "op2"]

        if self.choice1_btn.isChecked():
            return choices[0]  # op1
        else:
            return choices[1]  # op2
