# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Binary outcome data entry dialog."""

import copy
from contextlib import ExitStack
from functools import partial

from PyQt6.QtCore import QEvent, QObject, QSignalBlocker, QTimer, Qt
from PyQt6.QtGui import QAction, QBrush, QColor, QKeySequence, QPalette, QUndoStack
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

from rc_metastudio import meta_py_r
import tabular_data
from meta_globals import *
import calculator_routines as calc_fncs

import forms.ui_binary_data_form
import forms.ui_choose_back_calc_result_form
import app_error_handler
import adaptive_window
from runtime_types import required

# this is the maximum size of a residual that we're willing to accept
# when computing 2x2 data
THRESHOLD = 1e-5
BINARY_RAW_COUNT_CELLS = frozenset(((0, 0), (0, 1), (1, 0), (1, 1)))
BINARY_ARM_TOTAL_CELLS = frozenset(((0, 2), (1, 2)))


class BinaryDataForm2(QDialog, forms.ui_binary_data_form.Ui_BinaryDataForm):
    def __init__(
        self, ma_unit, cur_txs, cur_group_str, cur_effect, conf_level=None, parent=None
    ):
        super(BinaryDataForm2, self).__init__(parent)
        self.setupUi(self)
        self._configure_raw_data_table()
        self._configure_focus_revelation()
        self._layout_controller = adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )

        if conf_level is None:
            raise ValueError("Confidence level must be specified")
        self.global_conf_level = conf_level
        self.mult = meta_py_r.get_mult_from_r(self.global_conf_level)
        self.current_item_data: int | None = None

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
        self._fit_raw_data_columns_for_first_display()
        self.enable_back_calculation_btn()
        self.raw_data_table.setCurrentCell(0, 0)
        self.raw_data_table.setFocus()
        required(
            self.buttonBox.button(QDialogButtonBox.StandardButton.Ok),
            "binary calculator OK button",
        ).setDefault(True)
        self._request_content_refit()

    def _configure_raw_data_table(self):
        table = self.raw_data_table
        table.setHorizontalHeaderLabels(["Event", "No Event", "Total"])
        table.setVerticalHeaderLabels(["Group 1", "Group 2", "Total"])
        horizontal_header = required(table.horizontalHeader(), "binary table header")
        vertical_header = required(table.verticalHeader(), "binary row header")
        horizontal_header.setVisible(True)
        vertical_header.setVisible(True)
        horizontal_header.setHighlightSections(False)
        vertical_header.setHighlightSections(False)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # layout-audit: allow=compact-table-overflow; reason=compact table keeps rows visible and owns excess overflow
        table.setMinimumWidth(0)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        horizontal_header.setStretchLastSection(False)
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        table_height = (
            horizontal_header.sizeHint().height()
            + sum(table.rowHeight(row) for row in range(table.rowCount()))
            + 2 * table.frameWidth()
        )
        # layout-audit: allow=compact-table-overflow; reason=compact table keeps rows visible and owns excess overflow
        table.setMinimumHeight(table_height)
        # layout-audit: allow=compact-table-overflow; reason=compact table keeps rows visible and owns excess overflow
        table.setMaximumHeight(table_height)
        for label in (
            self.event_lbl_3,
            self.label_18,
            self.label_19,
            self.label_20,
            self.label_21,
            self.label_22,
        ):
            label.setVisible(False)

    def _fit_raw_data_columns_for_first_display(self):
        """Choose sensible initial widths, then leave sections user-adjustable."""
        for column in range(self.raw_data_table.columnCount()):
            self._grow_raw_data_column_to_contents(column)

    def _grow_raw_data_column_to_contents(self, column):
        table = self.raw_data_table
        header = required(table.horizontalHeader(), "binary table header")
        required_width = max(
            header.sectionSizeHint(column),
            table.sizeHintForColumn(column),
        )
        if required_width > table.columnWidth(column):
            header.resizeSection(column, required_width)

    def _configure_focus_revelation(self):
        """Reveal focused calculator controls within this dialog's overflow."""
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
        return super(BinaryDataForm2, self).eventFilter(watched, event)

    def _request_content_refit(self):
        controller = getattr(self, "_layout_controller", None)
        if controller is not None:
            controller.request_content_refit()

    def initialize_form(self):
        """Initialize all cells to empty items"""

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

            if new_data_in_op1:
                changed = True
                if "op2" in imputed:
                    comparison1 = [
                        new_item_available(old_data[i], new_data[1][i])
                        for i in range(len(old_data))
                    ]
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
            self._request_content_refit()
            return None
        else:
            self.back_calc_btn.setVisible(True)
            self._request_content_refit()

        bin_data = build_back_calc_args_dict()

        imputed = meta_py_r.impute_bin_data(bin_data.copy())

        # Leave if nothing was imputed
        if "FAIL" in imputed:
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
        try:
            if len(list(imputed.keys())) > 1:
                dialog = ChooseBackCalcResultForm(imputed, parent=self)
                if dialog.exec():
                    choice = dialog.getChoice()
                else:  # don't do anything if cancelled
                    return None
            else:  # only one option
                choice = "op1"

            # The nested choice is part of this transaction. Do not clear or
            # rewrite either the table or its copied model until it accepts.
            for x in range(3):
                self.clear_column(x)
            with QSignalBlocker(self.raw_data_table):
                group_1_events = int(round(imputed[choice]["a"]))
                group_1_total = int(round(imputed[choice]["b"]))
                group_2_events = int(round(imputed[choice]["c"]))
                group_2_total = int(round(imputed[choice]["d"]))
                self._set_val(0, 0, group_1_events)
                self._set_val(0, 1, group_1_total - group_1_events)
                self._set_val(1, 0, group_2_events)
                self._set_val(1, 1, group_2_total - group_2_events)

            self._update_data_table()
            self._update_ma_unit()  # save in ma_unit
        except BaseException:
            self.restore_ma_unit_and_table(old_ma_unit, old_table)
            raise
        # self.set_clear_btn_color()

        # for undo/redo
        new_ma_unit, new_table = self._save_ma_unit_and_table_state(
            table=self.raw_data_table, ma_unit=self.ma_unit, use_old_value=False
        )
        restore_old_f = lambda: self.restore_ma_unit_and_table(old_ma_unit, old_table)
        restore_new_f = lambda: self.restore_ma_unit_and_table(new_ma_unit, new_table)
        command = calc_fncs.CommandFieldChanged(
            restore_new_f=restore_new_f,
            restore_old_f=restore_old_f,
            parent=self,
            refresh_on_initial_redo=False,
        )
        self.undoStack.push(command)

    def setup_back_calculation_feedback(self):
        inconsistency_palette = QPalette()
        inconsistency_palette.setColor(
            QPalette.ColorRole.WindowText, Qt.GlobalColor.red
        )
        self.inconsistencyLabel.setPalette(inconsistency_palette)
        self.inconsistencyLabel.setVisible(False)
        self._request_content_refit()

    def _mark_table_consistent(self):
        self.inconsistencyLabel.setVisible(False)
        required(
            self.buttonBox.button(QDialogButtonBox.StandardButton.Ok),
            "binary calculator OK button",
        ).setEnabled(True)
        self._request_content_refit()

    def _mark_table_invalid(self, message):
        self.inconsistencyLabel.setText(str(message))
        self.inconsistencyLabel.setVisible(True)
        required(
            self.buttonBox.button(QDialogButtonBox.StandardButton.Ok),
            "binary calculator OK button",
        ).setEnabled(False)
        self._request_content_refit()
        self.inconsistencyLabel.updateGeometry()
        content_layout = self.content_widget.layout()
        if content_layout is not None:
            content_layout.activate()
        self._reveal_validation_message()
        QTimer.singleShot(
            0,
            self._reveal_validation_message,
        )

    def _reveal_validation_message(self):
        self.content_scroll.ensureWidgetVisible(self.inconsistencyLabel, 12, 12)
        center = self.inconsistencyLabel.mapTo(
            self.content_widget, self.inconsistencyLabel.rect().center()
        )
        self.content_scroll.ensureVisible(center.x(), center.y(), 12, 12)

    def _raw_count_cell_is_editable(self, row, col):
        if (row, col) in BINARY_RAW_COUNT_CELLS:
            return True
        if (row, col) in BINARY_ARM_TOTAL_CELLS:
            return any(self._is_empty(row, inner_col) for inner_col in (0, 1))
        return False

    def _refresh_raw_data_editability(self):
        with QSignalBlocker(self.raw_data_table):
            for row in range(self.raw_data_table.rowCount()):
                for col in range(self.raw_data_table.columnCount()):
                    calc_fncs.set_table_item_editable(
                        self.raw_data_table.item(row, col),
                        self._raw_count_cell_is_editable(row, col),
                    )

    def on_raw_data_table_currentCellChanged(
        self, currentRow, currentColumn, previousRow, previousColumn
    ):
        self.current_item_data = self._get_int(currentRow, currentColumn)

    def _setup_signals_and_slots(self):
        self.raw_data_table.cellChanged.connect(
            app_error_handler.safe_slot(self.cell_changed, parent=self)
        )
        self.raw_data_table.currentCellChanged.connect(
            app_error_handler.safe_slot(
                self.on_raw_data_table_currentCellChanged, parent=self
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
        with QSignalBlocker(self.effect_cbo_box):
            self.effect_cbo_box.clear()
            for effect in q_effects:
                self.effect_cbo_box.addItem(
                    self._effect_display_label(effect), userData=effect
                )
            # layout-audit: allow=content-overflow-control; reason=required content may consume available layout width
            self.effect_cbo_box.setMinimumWidth(0)
            # layout-audit: allow=content-overflow-control; reason=required content may consume available layout width
            self.effect_cbo_box.setMaximumWidth(QWIDGETSIZE_MAX)
            self.effect_cbo_box.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            self.effect_cbo_box.setCurrentIndex(q_effects.index(str(self.cur_effect)))
        self._update_effect_choice_accessibility()
        self._request_content_refit()

    def _update_effect_choice_accessibility(self):
        combo = self.effect_cbo_box
        if combo.count() == 0:
            return
        full_text = combo.currentText()
        combo.setToolTip(full_text)
        text_width = max(
            combo.fontMetrics().horizontalAdvance(combo.itemText(index))
            for index in range(combo.count())
        )
        scrollbar_width = required(
            combo.style(), "binary metric combo style"
        ).pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent, None, combo)
        # layout-audit: allow=bounded-native-popup; reason=native choice popup is bounded to the owning screen
        required(combo.view(), "binary metric combo popup").setMinimumWidth(
            text_width + scrollbar_width + 24
        )

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
                item = required(item, f"binary table cell ({row}, {col})")
                if curr_effect_is_one_arm:
                    item.setBackground(QBrush(QColor(Qt.GlobalColor.gray)))
                else:
                    # just reset the item
                    text = item.text()
                    with QSignalBlocker(self.raw_data_table):
                        popped_item = self.raw_data_table.takeItem(row, col)
                    del popped_item
                    self._set_val(row, col, text)

    def effect_changed(self):
        """Called when a new effect is selected in the combo box"""

        self.cur_effect = self._selected_effect()
        self.group_str = self.get_cur_group_str()

        self.try_to_update_cur_outcome()
        self.set_current_effect()

        self.enable_back_calculation_btn()
        self._update_effect_choice_accessibility()

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
            with ExitStack() as signal_blockers:
                for widget in self.entry_widgets:
                    signal_blockers.enter_context(QSignalBlocker(widget))
                if val_str == "est":
                    self.effect_txt_box.setFocus()
                elif val_str == "lower":
                    self.low_txt_box.setFocus()
                elif val_str == "upper":
                    self.high_txt_box.setFocus()
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

        for row, group in enumerate(self.cur_groups):
            events, total = self.ma_unit.get_raw_data_for_group(group)
            no_events = None
            if events not in EMPTY_VALS and total not in EMPTY_VALS:
                no_events = total - events
            self._set_val(row, 0, events)
            self._set_val(row, 1, no_events)
            self._set_val(row, 2, total)

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
            total = self._get_int(row, 2)
            if events not in EMPTY_VALS and no_events not in EMPTY_VALS:
                total = events + no_events
            raw_data = self.ma_unit.get_raw_data_for_group(self.cur_groups[row])
            raw_data[0] = events
            raw_data[1] = total

    def _cell_data_not_valid(self, celldata_string):
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

    def restore_ma_unit(self, old_ma_unit):
        """Restores the ma_unit data and resets the form"""
        self.ma_unit.__dict__ = copy.deepcopy(old_ma_unit.__dict__)

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
                self._set_val(row, col, old_table[row][col])
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

        self._grow_raw_data_column_to_contents(col)

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
                required(
                    self.raw_data_table.item(row, col),
                    f"binary table cell ({row}, {col})",
                ).text()
            )
            if warning_msg:
                raise ValueError(warning_msg)

            self._update_data_table()  # calculate derived margins from raw counts
            self._mark_table_consistent()
        except Exception as e:
            msg = e.args[0]
            QMessageBox.warning(self, "Warning", msg)  # popup warning
            self.restore_ma_unit_and_table(
                old_ma_unit, old_table
            )  # brings things back to the way they were
            self._mark_table_invalid(msg)
            return  # and leave

        try:
            self._update_ma_unit()  # table widget --> ma_unit
            self.try_to_update_cur_outcome()  # update metric in ma_unit and in table
        except Exception as e:
            msg = "Could not compute study effects from the edited raw data: %s" % e
            QMessageBox.warning(self, "Warning", msg)
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
            self._set_val(row, col, None)

        self._update_ma_unit()

    def _set_vals(self, computed_d):
        """Sets values in table widget"""
        with QSignalBlocker(self.raw_data_table):
            self._set_val(0, 0, computed_d["c11"])
            self._set_val(0, 1, computed_d["c12"])
            self._set_val(1, 0, computed_d["c21"])
            self._set_val(1, 1, computed_d["c22"])
            self._set_val(0, 2, computed_d["r1sum"])
            self._set_val(1, 2, computed_d["r2sum"])
            self._set_val(2, 0, computed_d["c1sum"])
            self._set_val(2, 1, computed_d["c2sum"])
            self._set_val(2, 2, computed_d["total"])

    def _set_val(self, row, col, val):
        if is_NaN(val):  # get out quick
            return

        with QSignalBlocker(self.raw_data_table):
            str_val = "" if val in EMPTY_VALS else str(int(val))
            if self.raw_data_table.item(row, col) == None:
                self.raw_data_table.setItem(row, col, QTableWidgetItem(str_val))
            else:
                required(
                    self.raw_data_table.item(row, col),
                    f"binary table cell ({row}, {col})",
                ).setText(str_val)
            calc_fncs.set_table_item_editable(
                self.raw_data_table.item(row, col),
                self._raw_count_cell_is_editable(row, col),
            )

    def _update_data_table(self):
        """Fill in 2x2 table from other entries in the table"""

        with QSignalBlocker(self.raw_data_table):
            params = self._get_table_vals()
            computed_params = calc_fncs.compute_2x2_table_from_inner_counts(params)
            for total_name in ("r1sum", "r2sum"):
                if computed_params[total_name] in EMPTY_VALS:
                    computed_params[total_name] = params[total_name]
            if (
                computed_params["total"] in EMPTY_VALS
                and computed_params["r1sum"] not in EMPTY_VALS
                and computed_params["r2sum"] not in EMPTY_VALS
            ):
                computed_params["total"] = (
                    computed_params["r1sum"] + computed_params["r2sum"]
                )
            if computed_params:
                self._set_vals(computed_params)  # computed --> table widget

    def _is_empty(self, i, j):
        val = self.raw_data_table.item(i, j)
        return val is None or val.text() == ""

    def _get_int(self, i, j):
        """Get value from cell specified by row=i, col=j as an integer"""
        if not self._is_empty(i, j):
            text = required(
                self.raw_data_table.item(i, j), f"binary table cell ({i}, {j})"
            ).text()
            try:
                val = int(text)
            except ValueError:
                val = int(calc_fncs.numeric_value(text))
            # print("Val from _get_int: %d" % val)
            return val
        else:
            return None  # its good to be explicit

    def _isBlank(self, x):
        return x is None or x == ""

    def try_to_update_cur_outcome(self):
        e1, n1, e2, n2 = self.ma_unit.get_raw_data_for_groups(self.cur_groups)

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
        self._refresh_raw_data_editability()
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

    def get_cur_group_str(self):
        # Inspired from get_cur_group_str of ma_data_table_model

        if self.cur_effect in BINARY_ONE_ARM_METRICS:
            group_str = self.cur_groups[0]
        else:
            group_str = "-".join(self.cur_groups)
        return group_str

    ####### Undo framework ############
    def undo(self):
        self.undoStack.undo()

    def redo(self):
        self.undoStack.redo()

    #################################


################################################################################
class ChooseBackCalcResultForm(
    QDialog, forms.ui_choose_back_calc_result_form.Ui_ChooseBackCalcResultForm
):
    def __init__(self, imputed_data, parent=None):
        super(ChooseBackCalcResultForm, self).__init__(parent)
        self.setupUi(self)
        for widget in self.content_widget.findChildren(QWidget):
            widget.installEventFilter(self)
        self._layout_controller = adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )

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

        self._layout_controller.request_content_refit()

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
        return super(ChooseBackCalcResultForm, self).eventFilter(watched, event)

    def getChoice(self):
        choices = ["op1", "op2"]

        if self.choice1_btn.isChecked():
            return choices[0]  # op1
        else:
            return choices[1]  # op2
