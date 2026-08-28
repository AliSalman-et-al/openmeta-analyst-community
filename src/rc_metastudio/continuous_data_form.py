# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Continuous outcome data entry dialog."""

# Continuous and binary data forms still share some interaction patterns; keep
# refactoring opportunities small so imputation behavior stays explicit.
#
# Note that we don't make use of the table/custom model
# design here. Rather, we edit the ma_unit object
# directly, based on what the user inputs. This seemed a more
# straightforward approach, because the table itself displays
# many fields that do not ultimately belong in the raw_data --
# it's mostly imputation going on here.
# import pdb
import copy
from contextlib import ExitStack

from PyQt6.QtCore import QEvent, QObject, QSignalBlocker, QTimer, Qt
from PyQt6.QtGui import QAction, QKeySequence, QPalette, QUndoStack
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QMessageBox,
    QSizePolicy,
    QStyle,
    QTableWidgetItem,
    QTreeView,
    QWidget,
    QWIDGETSIZE_MAX,
)
from functools import partial
import calculator_routines as calc_fncs

import app_error_handler
import adaptive_window
from rc_metastudio import meta_py_r
import tabular_data
from meta_globals import *
import forms.ui_continuous_data_form
import forms.ui_continuous_back_calc_result_form
from runtime_types import required

CONTINUOUS_IMPUTATION_FIELD_NAMES = {
    "n": "n",
    "N": "n",
    "Mean": "mean",
    "mean": "mean",
    "sd": "sd",
    "SD": "sd",
    "se": "se",
    "SE": "se",
    "Variance": "var",
    "var": "var",
    "Lower": "low",
    "low": "low",
    "Upper": "high",
    "high": "high",
    "P-Value": "pval",
    "p-value": "pval",
    "pval": "pval",
}


def continuous_imputation_field_name(visible_header):
    return CONTINUOUS_IMPUTATION_FIELD_NAMES.get(
        str(visible_header), str(visible_header)
    )


class _BackCalculationCancelled(Exception):
    """Internal control flow for a nested choice that rejects the transaction."""


# because the output from R is a string ("TRUE"/"FALSE")
# Remove this? GD
_is_true = lambda x: x == "TRUE"


def is_list(x):
    try:
        list(x)
        return True
    except:
        return False


class ContinuousDataForm(QDialog, forms.ui_continuous_data_form.Ui_ContinuousDataForm):
    def __init__(
        self, ma_unit, cur_txs, cur_group_str, cur_effect, conf_level=None, parent=None
    ):
        super(ContinuousDataForm, self).__init__(parent)
        self.setupUi(self)
        self._configure_tables()
        self._configure_semantic_fields()
        self._configure_focus_revelation()
        self._layout_controller = adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )
        self.setup_signals_and_slots()

        if conf_level is None:
            QMessageBox.critical(
                self, "Insufficient Arguments", "Confidence interval must be specified"
            )
            raise ValueError("Confidence interval must be specified")
        self.conf_level = conf_level
        self.mult = meta_py_r.get_mult_from_r(self.conf_level)

        self.ma_unit = ma_unit
        self.cur_groups = cur_txs
        self.cur_effect = cur_effect
        self.group_str = cur_group_str
        self.metric_parameter = None
        self.entry_widgets = [
            self.simple_table,
            self.g1_pre_post_table,
            self.g2_pre_post_table,
            self.effect_txt_box,
            self.low_txt_box,
            self.high_txt_box,
            self.correlation_pre_post,
        ]
        self.text_boxes = [
            self.low_txt_box,
            self.high_txt_box,
            self.effect_txt_box,
            self.correlation_pre_post,
        ]
        self.ci_label.setText("{0:.1f}% Confidence Interval".format(self.conf_level))
        self.current_item_data = {}

        # Set the table headers to reflect the group names
        groups_names = [str(group_name) for group_name in self.cur_groups]
        self.simple_table.setVerticalHeaderLabels(groups_names)

        self.tables = [
            self.simple_table,
            self.g1_pre_post_table,
            self.g2_pre_post_table,
        ]
        self.grp_1_lbl.setText(str(self.cur_groups[0]))
        self.grp_2_lbl.setText(str(self.cur_groups[1]))

        self.setup_clear_button_palettes()  # Color for clear_button_pallette
        self.initialize_form()  # initialize cells to empty items
        self.undoStack = QUndoStack(self)

        self.update_raw_data()
        self._populate_effect_data()
        self.set_current_effect()
        self.impute_data()
        self.enable_back_calculation_btn()

        # Hide pre-post for SMD until it is implemented
        if self.cur_effect not in ["MD", "SMD"]:
            self.grp_box_pre_post.setVisible(False)

        self.current_correlation = self._get_correlation_str()
        self.simple_table.setCurrentCell(0, 0)
        self.simple_table.setFocus()
        required(
            self.buttonBox.button(QDialogButtonBox.StandardButton.Ok),
            "continuous calculator OK button",
        ).setDefault(True)
        self._request_initial_content_refit()

    def _configure_tables(self):
        """Give each data grid its own overflow and user-adjustable columns."""
        for table in (
            self.simple_table,
            self.g1_pre_post_table,
            self.g2_pre_post_table,
        ):
            # layout-audit: allow=compact-table-overflow; reason=compact table keeps rows visible and owns excess overflow
            table.setMinimumWidth(0)
            table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            header = table.horizontalHeader()
            header = required(header, "continuous table header")
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            header.setStretchLastSection(False)
            table.resizeColumnsToContents()
            table.resizeRowsToContents()
            height = (
                header.sizeHint().height()
                + sum(table.rowHeight(row) for row in range(table.rowCount()))
                + 2 * table.frameWidth()
                + required(table.horizontalScrollBar(), "continuous table scrollbar")
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
        effect_view = QTreeView(self.effect_cbo_box)
        effect_view.setHeaderHidden(True)
        effect_view.setRootIsDecorated(False)
        self.effect_cbo_box.setView(effect_view)
        effect_view.setTextElideMode(Qt.TextElideMode.ElideNone)
        effect_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._effect_popup = required(effect_view.window(), "continuous metric popup")
        self._effect_popup.installEventFilter(self)
        correlation_width = (
            self.correlation_pre_post.fontMetrics().horizontalAdvance("-1.0000")
            + self.correlation_pre_post.textMargins().left()
            + self.correlation_pre_post.textMargins().right()
            + 2
            * required(
                self.correlation_pre_post.style(), "correlation field style"
            ).pixelMetric(
                QStyle.PixelMetric.PM_DefaultFrameWidth, None, self.correlation_pre_post
            )
            + 12
        )
        # layout-audit: allow=numeric-domain-control; reason=editor width follows representative values from its numeric domain
        self.correlation_pre_post.setMinimumWidth(correlation_width)
        # layout-audit: allow=numeric-domain-control; reason=editor width follows representative values from its numeric domain
        self.correlation_pre_post.setMaximumWidth(QWIDGETSIZE_MAX)
        self.correlation_pre_post.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed
        )

    def _configure_focus_revelation(self):
        for widget in self.content_widget.findChildren(QWidget):
            widget.installEventFilter(self)

    def eventFilter(  # ty: ignore[invalid-method-override] -- PyQt6's QDialog stub rejects this runtime-supported QObject override.
        self, watched: QObject | None, event: QEvent | None
    ) -> bool:
        if event is None:
            return super(ContinuousDataForm, self).eventFilter(watched, event)
        if watched is self._effect_popup and event.type() == QEvent.Type.Show:
            QTimer.singleShot(0, self._bound_effect_popup_to_screen)
        if (
            isinstance(watched, QWidget)
            and event.type() == QEvent.Type.FocusIn
            and self.content_widget.isAncestorOf(watched)
        ):
            self.content_scroll.ensureWidgetVisible(watched)
            QTimer.singleShot(
                0, lambda target=watched: self._ensure_content_widget_visible(target)
            )
        return super(ContinuousDataForm, self).eventFilter(watched, event)

    def _ensure_content_widget_visible(self, widget):
        try:
            self.content_scroll.ensureWidgetVisible(widget)
            center = widget.mapTo(self.content_widget, widget.rect().center())
            self.content_scroll.ensureVisible(center.x(), center.y(), 12, 12)
        except RuntimeError:
            pass

    def _request_initial_content_refit(self):
        controller = self.__dict__.get("_layout_controller")
        if controller is not None and not self.isVisible():
            controller.request_content_refit()

    def _content_layout_changed(self):
        """Relayout dynamic content without taking visible root geometry ownership."""
        content_layout = self.__dict__.get("content_layout")
        content_widget = self.__dict__.get("content_widget")
        if content_layout is not None:
            content_layout.invalidate()
        if content_widget is not None:
            content_widget.updateGeometry()
        self._request_initial_content_refit()

    def _update_effect_choice_accessibility(self):
        combo = self.effect_cbo_box
        if combo.count() == 0:
            return
        full_text = combo.currentText()
        combo.setToolTip(full_text)
        for index in range(combo.count()):
            combo.setItemData(index, combo.itemText(index), Qt.ItemDataRole.ToolTipRole)
        view = combo.view()
        if not isinstance(view, QTreeView):
            raise RuntimeError("Continuous metric combo requires a tree view")
        view.resizeColumnToContents(0)

    def _bound_effect_popup_to_screen(self):
        """Keep the native metric popup local to the dialog's owning screen."""
        try:
            combo = self.effect_cbo_box
            view = combo.view()
            if not isinstance(view, QTreeView):
                raise RuntimeError("Continuous metric combo requires a tree view")
            popup = view.window()
            popup = required(popup, "continuous metric popup")
            available = adaptive_window.available_geometry_for_window(self)
            content_width = view.columnWidth(0) + 2 * required(
                self.effect_cbo_box.style(), "continuous metric combo style"
            ).pixelMetric(QStyle.PixelMetric.PM_DefaultFrameWidth)
            popup_width = min(available.width(), max(combo.width(), content_width))
            popup_height = min(available.height(), popup.height())
            # layout-audit: allow=bounded-native-popup; reason=native choice popup is bounded to the owning screen
            popup.setMaximumSize(available.size())
            # layout-audit: allow=bounded-native-popup; reason=native choice popup is bounded to the owning screen
            popup.resize(popup_width, popup_height)

            frame = popup.frameGeometry()
            bounded_x = min(
                max(frame.x(), available.left()),
                available.right() - frame.width() + 1,
            )
            bounded_y = min(
                max(frame.y(), available.top()),
                available.bottom() - frame.height() + 1,
            )
            # layout-audit: allow=bounded-native-popup; reason=native choice popup is bounded to the owning screen
            popup.move(bounded_x, bounded_y)
        except RuntimeError:
            pass

    def _grow_table_column_to_contents(self, table, column):
        header = required(table.horizontalHeader(), "continuous table header")
        required_width = max(
            header.sectionSizeHint(column), table.sizeHintForColumn(column)
        )
        if required_width > table.columnWidth(column):
            header.resizeSection(column, required_width)

    def _fit_tables_to_contents(self):
        for table in self.__dict__.get("tables", (self.simple_table,)):
            for column in range(table.columnCount()):
                self._grow_table_column_to_contents(table, column)
        self._content_layout_changed()

    def initialize_form(self, table=None):
        """Initialize all cells to empty items
        If table is specified, only clear that table, leave the others alone"""

        if table is None:
            for target in (
                self.simple_table,
                self.g1_pre_post_table,
                self.g2_pre_post_table,
            ):
                for row in range(target.rowCount()):
                    for col in range(target.columnCount()):
                        self._set_val(row, col, None, target)
        else:
            for row in range(table.rowCount()):
                for col in range(table.columnCount()):
                    self._set_val(row, col, None, table)

        for txt_box in self.text_boxes:
            txt_box.setText("")
            if txt_box == self.correlation_pre_post:
                txt_box.setText("0.0")

    def setup_signals_and_slots(self):
        self.simple_table.cellChanged.connect(
            app_error_handler.safe_slot(self._cell_changed, parent=self)
        )
        self.simple_table.currentCellChanged.connect(
            app_error_handler.safe_slot(
                self.on_simple_table_currentCellChanged, parent=self
            )
        )
        self.g1_pre_post_table.cellChanged.connect(
            app_error_handler.safe_slot(
                lambda row, col: self.impute_pre_post_data(
                    self.g1_pre_post_table, 0, row, col
                ),
                parent=self,
            )
        )
        self.g1_pre_post_table.currentCellChanged.connect(
            app_error_handler.safe_slot(
                self.on_g1_pre_post_table_currentCellChanged, parent=self
            )
        )
        self.g2_pre_post_table.cellChanged.connect(
            app_error_handler.safe_slot(
                lambda row, col: self.impute_pre_post_data(
                    self.g2_pre_post_table, 1, row, col
                ),
                parent=self,
            )
        )
        self.g2_pre_post_table.currentCellChanged.connect(
            app_error_handler.safe_slot(
                self.on_g2_pre_post_table_currentCellChanged, parent=self
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
        self.correlation_pre_post.editingFinished.connect(
            app_error_handler.safe_slot(
                lambda: self.val_changed("correlation_pre_post"), parent=self
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

    def _populate_effect_data(self):
        available_effects = set(
            str(effect_str) for effect_str in self.ma_unit.get_effect_names()
        )
        metric_family = (
            CONTINUOUS_ONE_ARM_METRICS
            if self.cur_effect in CONTINUOUS_ONE_ARM_METRICS
            else CONTINUOUS_TWO_ARM_METRICS
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
            self.effect_cbo_box.setCurrentIndex(q_effects.index(str(self.cur_effect)))
        self._update_effect_choice_accessibility()

    def effect_changed(self):
        self.cur_effect = self._selected_effect()

        # hide pre-post for SMD
        if self.cur_effect not in ["MD", "SMD"]:
            self.grp_box_pre_post.setVisible(False)
        else:
            self.grp_box_pre_post.setVisible(True)
        self._update_effect_choice_accessibility()
        self._content_layout_changed()

        self.group_str = self.get_cur_group_str()

        self.try_to_update_cur_outcome()
        self.set_current_effect()

        self.metric_parameter = None  # zusammen
        self.enable_back_calculation_btn()  # zusammen

    def _text_box_value_is_between_bounds(self, val_str, new_text):
        display_scale_val = ""

        get_disp_scale_val_if_valid = partial(
            calc_fncs.evaluate,
            new_text=new_text,
            ma_unit=self.ma_unit,
            curr_effect=self.cur_effect,
            group_str=self.group_str,
            conv_to_disp_scale=partial(
                meta_py_r.continuous_convert_scale,
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
                elif val_str == "correlation_pre_post" and not is_empty(new_text):
                    get_disp_scale_val_if_valid(
                        opt_cmp_fn=lambda x: -1 <= calc_fncs.numeric_value(x) <= 1,
                        opt_cmp_msg="Correlation must be between -1 and +1",
                    )
            except:
                return False, False
        return True, display_scale_val

    def _get_txt_from_val_str(self, val_str):
        if val_str == "est":
            return str(self.effect_txt_box.text())
        elif val_str == "lower":
            return str(self.low_txt_box.text())
        elif val_str == "upper":
            return str(self.high_txt_box.text())
        elif val_str == "correlation_pre_post":
            return str(self.correlation_pre_post.text())
        return None  # Unknown value key.

    def val_changed(self, val_str):
        # Backup form state
        old_ma_unit, old_tables_data = self._save_ma_unit_and_table_states(
            tables=[self.simple_table, self.g1_pre_post_table, self.g2_pre_post_table],
            ma_unit=self.ma_unit,
            use_old_value=False,
        )
        old_correlation = self.current_correlation

        new_text = self._get_txt_from_val_str(val_str)

        no_errors, display_scale_val = self._text_box_value_is_between_bounds(
            val_str, new_text
        )
        if no_errors is False:
            self.restore_ma_unit_and_tables(
                old_ma_unit, old_tables_data, old_correlation
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
                elif val_str == "correlation_pre_post":
                    self.correlation_pre_post.setFocus()
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

        calc_scale_val = meta_py_r.continuous_convert_scale(
            display_scale_val, self.cur_effect, convert_to="calc.scale"
        )

        if val_str == "est":
            self.ma_unit.set_effect(self.cur_effect, self.group_str, calc_scale_val)
        elif val_str == "lower":
            self.ma_unit.set_lower(self.cur_effect, self.group_str, calc_scale_val)
        elif val_str == "upper":
            self.ma_unit.set_upper(self.cur_effect, self.group_str, calc_scale_val)
        elif val_str == "correlation_pre_post":
            # Recompute the estimates
            self.impute_pre_post_data(self.g1_pre_post_table, 0)
            self.impute_pre_post_data(self.g2_pre_post_table, 1)

        self.impute_data()  #### experimental

        new_ma_unit, new_tables_data = self._save_ma_unit_and_table_states(
            tables=[self.simple_table, self.g1_pre_post_table, self.g2_pre_post_table],
            ma_unit=self.ma_unit,
            use_old_value=False,
        )
        new_correlation = self._get_correlation_str()
        restore_old_f = lambda: self.restore_ma_unit_and_tables(
            old_ma_unit, old_tables_data, old_correlation
        )
        restore_new_f = lambda: self.restore_ma_unit_and_tables(
            new_ma_unit, new_tables_data, new_correlation
        )
        command = calc_fncs.CommandFieldChanged(
            restore_new_f=restore_new_f,
            restore_old_f=restore_old_f,
            parent=self,
        )
        self.undoStack.push(command)

        self.current_correlation = new_correlation

    def setup_clear_button_palettes(self):
        # Color for clear_button_pallette
        self.orig_palette = self.clear_Btn.palette()
        self.pushme_palette = QPalette()
        self.pushme_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.red)
        self.set_clear_btn_color()

    def set_clear_btn_color(self):
        if calc_fncs._input_fields_disabled(
            self.simple_table,
            [self.effect_txt_box, self.low_txt_box, self.high_txt_box],
        ):
            self.clear_Btn.setPalette(self.pushme_palette)
        else:
            self.clear_Btn.setPalette(self.orig_palette)

    def set_current_effect(self):
        txt_boxes = dict(
            effect=self.effect_txt_box, lower=self.low_txt_box, upper=self.high_txt_box
        )
        calc_fncs.helper_set_current_effect(
            ma_unit=self.ma_unit,
            txt_boxes=txt_boxes,
            current_effect=self.cur_effect,
            group_str=self.group_str,
            data_type="continuous",
            mult=self.mult,
        )

        self.change_row_color_according_to_metric()

    def change_row_color_according_to_metric(self):
        """Expose only the data rows that participate in the selected metric."""
        curr_effect_is_one_arm = self.cur_effect in CONTINUOUS_ONE_ARM_METRICS
        self.simple_table.setRowHidden(1, curr_effect_is_one_arm)

    def update_raw_data(self):
        """Updates table widget with data from ma_unit"""

        with QSignalBlocker(self.simple_table):
            for row_index, group_name in enumerate(self.cur_groups):
                grp_raw_data = self.ma_unit.get_raw_data_for_group(group_name)
                for col in range(len(grp_raw_data)):
                    self._set_val(row_index, col, grp_raw_data[col], self.simple_table)
                # also insert the SEs, if we have them
                se_col = 3
                se = self.ma_unit.get_se(self.cur_effect, self.group_str, self.mult)
                self._set_val(row_index, se_col, se, self.simple_table)
        self.impute_data()

    def _cell_data_not_valid(self, celldata_string, cell_header=None):
        # ignore blank entries
        if calc_fncs.cell_text_is_blank(celldata_string):
            return None

        try:
            value = calc_fncs.numeric_value(celldata_string)
        except ValueError:
            return "Raw data needs to be numeric."

        field_name = continuous_imputation_field_name(cell_header)
        if field_name == "n" and (value < 0 or not value.is_integer()):
            return "N must be a non-negative whole number."
        if field_name in ["n", "sd", "se", "var", "pval"] and value < 0:
            return "%s cannot be negative." % (field_name,)

        if field_name == "pval" and not (0 <= value <= 1):
            return "pval must be between 0 and 1"
        return None

    def _get_correlation_str(self):
        return str(self.correlation_pre_post.text())

    def _cell_changed(self, row, col):

        old_ma_unit, old_tables_data = self._save_ma_unit_and_table_states(
            tables=self.tables,
            ma_unit=self.ma_unit,
            table=self.simple_table,
            row=row,
            col=col,
            old_value=self.current_item_data[self.simple_table],
            use_old_value=True,
        )
        old_correlation = self._get_correlation_str()

        # The simple table owns these column headers.
        column_headers = self.get_column_header_strs()
        try:
            warning_msg = self._cell_data_not_valid(
                required(
                    self.simple_table.item(row, col),
                    f"continuous table cell ({row}, {col})",
                ).text(),
                column_headers[col],
            )
            if warning_msg:
                QMessageBox.warning(self, "Warning", warning_msg)
                self._set_val(
                    row,
                    col,
                    self.current_item_data[self.simple_table],
                    self.simple_table,
                )
                return
            self.impute_data()
        except Exception as e:
            msg = e.args[0]
            QMessageBox.warning(self, "Warning", msg)
            self.restore_ma_unit_and_tables(
                old_ma_unit, old_tables_data, old_correlation
            )
            return

        try:
            self._copy_raw_data_from_table_to_ma_unit()  # table --> ma_unit
            self.try_to_update_cur_outcome()
        except Exception as e:
            msg = "Could not compute study effects from the edited raw data: %s" % e
            QMessageBox.warning(self, "Warning", msg)
            self.restore_ma_unit_and_tables(
                old_ma_unit, old_tables_data, old_correlation
            )
            return

        new_ma_unit, new_tables_data = self._save_ma_unit_and_table_states(
            tables=self.tables,
            ma_unit=self.ma_unit,
            table=self.simple_table,
            row=row,
            col=col,
            use_old_value=False,
        )
        new_correlation = self._get_correlation_str()
        restore_old_f = lambda: self.restore_ma_unit_and_tables(
            old_ma_unit, old_tables_data, old_correlation
        )
        restore_new_f = lambda: self.restore_ma_unit_and_tables(
            new_ma_unit, new_tables_data, new_correlation
        )
        command = calc_fncs.CommandFieldChanged(
            restore_new_f=restore_new_f, restore_old_f=restore_old_f, parent=self
        )
        self.undoStack.push(command)

        ###self.enable_txt_box_input() # if the effect was imputed
        ###self.set_clear_btn_color()

    def _set_val(self, row_index, var_index, val, table=None):
        if table == None:
            table = self.simple_table

        row, col = row_index, var_index
        if is_NaN(val):  # get out quick
            return

        try:
            with QSignalBlocker(table):
                str_val = "" if val in EMPTY_VALS else self.float_to_str(float(val))
                if table.item(row, col) is None:
                    table.setItem(row, col, QTableWidgetItem(str_val))
                else:
                    required(
                        table.item(row, col), f"continuous table cell ({row}, {col})"
                    ).setText(str_val)

                ###self._disable_row_if_filled(table, row, col)
        except:
            pass
            # raise

    def _disable_row_if_filled(self, table, row, col):
        # if str_val != "": #disable item
        with QSignalBlocker(table):
            N_col = table.columnCount()

            if self._table_row_filled(table, row):
                for col in range(N_col):
                    self._disable_cell(table, row, col)

    def _disable_cell(self, table, row, col):
        with QSignalBlocker(table):
            item = table.item(row, col)
            newflags = item.flags() & ~Qt.ItemFlag.ItemIsEditable
            item.setFlags(newflags)

    def _table_row_filled(self, table, row):
        N_col = table.columnCount()
        row_filled = True
        for col in range(N_col):
            item = table.item(row, col)
            if item is None or item.text() == "":
                row_filled = False
        return row_filled

    def _copy_raw_data_from_table_to_ma_unit(self):
        for row_index, group_name in enumerate(self.cur_groups):
            grp_raw_data = self.ma_unit.get_raw_data_for_group(group_name)
            for col_index in range(len(grp_raw_data)):
                cur_val = self._get_float(row_index, col_index)
                self.ma_unit.get_raw_data_for_group(group_name)[col_index] = cur_val

            ## also check if SEs have been entered directly
            ##se_index = 3
            ##se = self._get_float(row_index, se_index)
            ##self.ma_unit.set_SE(self.cur_effect, self.group_str, se):

    def restore_ma_unit(self, old_ma_unit):
        """Restores the ma_unit data and resets the form"""
        self.ma_unit.__dict__ = copy.deepcopy(old_ma_unit.__dict__)

        self.initialize_form()  # clear form first
        self.update_raw_data()
        self.set_current_effect()
        self.impute_data()
        self.enable_back_calculation_btn()
        # self.set_clear_btn_color()

    def restore_tables(self, old_tables_data):
        """Assumes old tables data given in follow order:
        simple_table, g1_pre_post_table, g2_pre_post_table
        """

        for i, old_table_data in enumerate(old_tables_data):
            old_table_data = tabular_data.normalize_rows(old_table_data)
            if not old_table_data:
                continue
            table = self.tables[i]
            nrows = min(len(old_table_data), table.rowCount())
            ncols = min(len(old_table_data[0]), table.columnCount())

            for row in range(nrows):
                for col in range(ncols):
                    self._set_val(row, col, old_table_data[row][col], table=table)
        self._fit_tables_to_contents()

    def restore_ma_unit_and_tables(self, old_ma_unit, old_tables_data, old_correlation):
        self.restore_ma_unit(old_ma_unit)
        self.restore_tables(old_tables_data)
        self.correlation_pre_post.setText(old_correlation)

    def save_tables_data(self):
        old_tables_data = []
        for table in self.tables:
            old_tables_data.append(calc_fncs.save_table_data(table))
        return old_tables_data

    def _save_ma_unit_and_table_states(
        self,
        tables,
        ma_unit,
        table=None,
        row=None,
        col=None,
        old_value=None,
        use_old_value=True,
    ):
        # Make backup of tables info...
        old_tables_data = self.save_tables_data()
        if use_old_value:
            # From before most recently changed cell changed
            old_tables_data[self._get_index_of_table(table)][row][col] = old_value

        # Make backup copy of ma_unit
        old_ma_unit = copy.deepcopy(ma_unit)
        return old_ma_unit, old_tables_data

    def _get_index_of_table(self, table):
        index = -1
        for i, x in enumerate(self.tables):
            if table is x:
                index = i
        return index

    def impute_data(self):
        """compute what we can for each study from what has been given in the table"""

        var_names = self.get_column_header_strs()
        for row_index, group_name in enumerate(self.cur_groups):
            # assemble the fields in a dictionary; pass off to meta_py_r
            cur_dict = {}
            for var_index, var_name in enumerate(var_names):
                var_value = self._get_float(row_index, var_index)
                if var_value is not None:
                    cur_dict[self._imputation_field_name(var_name)] = var_value

            # now pass off what we have for this study to the
            # imputation routine
            alpha = self.conf_level_to_alpha()
            results_from_r = meta_py_r.impute_cont_data(cur_dict, alpha)

            if results_from_r["succeeded"]:
                computed_vals = results_from_r["output"]
                # and then iterate over the columns again,
                # populating the table with any available
                # computed fields

                for var_index, var_name in enumerate(var_names):
                    self._set_val(
                        row_index,
                        var_index,
                        computed_vals[self._imputation_field_name(var_name)],
                    )
                self._copy_raw_data_from_table_to_ma_unit()
        self._fit_tables_to_contents()

    def conf_level_to_alpha(self):
        alpha = 1 - self.conf_level / 100.0
        return alpha

    def _imputation_field_name(self, visible_header):
        return continuous_imputation_field_name(visible_header)

    def impute_pre_post_data(self, table, group_index, row=None, col=None):
        """
        The row index corresponds to the group that will be
        affected by the data edits. E.g., a row index of 0 will result
        in the data for the first group (row 0 in the simple_table)
        being modified.
        """

        old_ma_unit = old_tables_data = old_correlation = None
        if not (row, col) == (
            None,
            None,
        ):  # means this was called through user interaction, not programmatically
            old_ma_unit, old_tables_data = self._save_ma_unit_and_table_states(
                tables=self.tables,
                ma_unit=self.ma_unit,
                table=table,
                row=row,
                col=col,
                old_value=self.current_item_data[table],
                use_old_value=True,
            )
            old_correlation = self._get_correlation_str()

            column_headers = self.get_column_header_strs(table)
            warning_msg = self._cell_data_not_valid(
                required(
                    table.item(row, col), f"continuous pre/post cell ({row}, {col})"
                ).text(),
                column_headers[col],
            )
            if warning_msg:
                QMessageBox.warning(self, "Warning", warning_msg)
                self.restore_ma_unit_and_tables(
                    old_ma_unit, old_tables_data, old_correlation
                )
                return None

        group_name = self.cur_groups[group_index]
        var_names = self.get_column_header_strs_pre_post()
        params_dict = {}
        # A, B correspond to pre, post
        for a_b_index, a_b_name in enumerate(["A", "B"]):
            # assemble the fields in a dictionary; pass off to meta_py_r
            for var_index, var_name in enumerate(var_names):
                var_value = self._get_float(a_b_index, var_index, table)
                if var_value is not None:
                    params_dict[
                        "%s.%s" % (self._imputation_field_name(var_name), a_b_name)
                    ] = var_value
        params_dict["metric"] = "'%s'" % self.cur_effect

        # now pass off what we have for this study to the
        # imputation routine
        results_from_r = meta_py_r.impute_pre_post_cont_data(
            params_dict,
            calc_fncs.numeric_value(self.correlation_pre_post.text()),
            self.conf_level_to_alpha(),
        )

        if not results_from_r["succeeded"]:
            if (
                old_ma_unit is not None
                and old_tables_data is not None
                and old_correlation is not None
            ):
                self.restore_ma_unit_and_tables(
                    old_ma_unit, old_tables_data, old_correlation
                )
            self._fit_tables_to_contents()
            return None

        ###
        # first update the simple table
        computed_vals = results_from_r["output"]

        for var_index, var_name in enumerate(self.get_column_header_strs()):
            field_name = self._imputation_field_name(var_name)
            val = computed_vals[field_name]
            self._set_val(group_index, var_index, val)

            # update the raw data for N, mean and SD fields (this is all that is actually stored)
            if var_index < 3:
                self.ma_unit.get_raw_data_for_group(group_name)[var_index] = (
                    computed_vals[field_name]
                )  #

        try:
            self.try_to_update_cur_outcome()
        except Exception as e:
            if (
                old_ma_unit is not None
                and old_tables_data is not None
                and old_correlation is not None
            ):
                msg = "Could not compute study effects from the edited raw data: %s" % e
                QMessageBox.warning(self, "Warning", msg)
                self.restore_ma_unit_and_tables(
                    old_ma_unit, old_tables_data, old_correlation
                )
                return
            raise

        ###
        # also update the pre/post tables
        pre_vals = results_from_r["pre"]
        post_vals = results_from_r["post"]
        for var_index, var_name in enumerate(var_names):
            field_name = self._imputation_field_name(var_name)
            pre_val = pre_vals[field_name]
            post_val = post_vals[field_name]
            self._set_val(0, var_index, pre_val, table)
            self._set_val(1, var_index, post_val, table)

        self._copy_raw_data_from_table_to_ma_unit()
        self.set_clear_btn_color()
        self._fit_tables_to_contents()

        # function was invoked as a result of user interaction, not
        # programmatically
        if not (row, col) == (None, None):
            new_ma_unit, new_tables_data = self._save_ma_unit_and_table_states(
                tables=self.tables,
                ma_unit=self.ma_unit,
                table=table,
                row=row,
                col=col,
                use_old_value=False,
            )
            new_correlation = self._get_correlation_str()
            restore_old_f = lambda: self.restore_ma_unit_and_tables(
                old_ma_unit, old_tables_data, old_correlation
            )
            restore_new_f = lambda: self.restore_ma_unit_and_tables(
                new_ma_unit, new_tables_data, new_correlation
            )
            command = calc_fncs.CommandFieldChanged(
                restore_new_f=restore_new_f, restore_old_f=restore_old_f, parent=self
            )
            self.undoStack.push(command)

    def float_to_str(self, float_val):
        float_str = ""
        if not is_NaN(float_val):
            # Keep this compact in the imputation dialog; analysis output uses
            # the configured result precision elsewhere.
            float_str = str(round(float_val, 4))
        return float_str

    def get_column_header_strs(self, table=None):
        if table is None:
            table = self.simple_table

        return [
            str(required(h_item, "continuous table header item").text())
            for h_item in [
                table.horizontalHeaderItem(col) for col in range(table.columnCount())
            ]
        ]

    def get_column_header_strs_pre_post(self):
        return self.get_column_header_strs(table=self.g1_pre_post_table)

    def on_simple_table_currentCellChanged(
        self, currentRow, currentColumn, previousRow, previousColumn
    ):
        self.current_item_data[self.simple_table] = self._get_float(
            currentRow, currentColumn
        )
        ###print "Current Item Data:",self.current_item_data

    def on_g1_pre_post_table_currentCellChanged(
        self, currentRow, currentColumn, previousRow, previousColumn
    ):
        self.current_item_data[self.g1_pre_post_table] = self._get_float(
            currentRow, currentColumn, self.g1_pre_post_table
        )
        ###print "Current Item Data:",self.current_item_data

    def on_g2_pre_post_table_currentCellChanged(
        self, currentRow, currentColumn, previousRow, previousColumn
    ):
        self.current_item_data[self.g2_pre_post_table] = self._get_float(
            currentRow, currentColumn, self.g2_pre_post_table
        )
        ###print "Current Item Data:",self.current_item_data

    def _is_empty(self, i, j, table):
        val = table.item(i, j)
        return val is None or val.text() == ""

    def _get_float(self, i, j, table=None):
        if table is None:
            table = self.simple_table
        item = table.item(i, j)
        if item is None:
            return None
        try:
            return calc_fncs.numeric_value(item.text())
        except ValueError:
            return None

    def no_val(self, x):
        return x is None or x == ""

    def try_to_update_cur_outcome(self):
        n1, m1, sd1, n2, m2, sd2 = self.ma_unit.get_raw_data_for_groups(self.cur_groups)
        se1, se2 = self._get_float(0, 3), self._get_float(1, 3)

        # here we check whether or not we have sufficient data to compute an outcome
        if (
            not any([self.no_val(x) for x in [n1, m1, sd1, n2, m2, sd2]])
            or not any([self.no_val(x) for x in [m1, se1, m2, se2]])
            and self.cur_effect == "MD"
            or not any([self.no_val(x) for x in [n1, m1, sd1]])
            and self.cur_effect in CONTINUOUS_ONE_ARM_METRICS
        ):
            est_and_ci_d = None
            if self.cur_effect in CONTINUOUS_TWO_ARM_METRICS:
                est_and_ci_d = meta_py_r.continuous_effect_for_study(
                    n1,
                    m1,
                    sd1,
                    se1=se1,
                    n2=n2,
                    m2=m2,
                    sd2=sd2,
                    se2=se2,
                    metric=self.cur_effect,
                    conf_level=self.conf_level,
                )
            else:
                # continuous, one-arm metric
                est_and_ci_d = meta_py_r.continuous_effect_for_study(
                    n1,
                    m1,
                    sd1,
                    two_arm=False,
                    metric=self.cur_effect,
                    conf_level=self.conf_level,
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

    def _capture_back_calculation_state(self):
        return {
            "ma_unit": copy.deepcopy(self.ma_unit),
            "tables": self.save_tables_data(),
            "correlation": self.correlation_pre_post.text(),
            "metric_parameter": self.metric_parameter,
            "button": {
                "enabled": self.back_calc_btn.isEnabled(),
                "text": self.back_calc_btn.text(),
                "hidden": self.back_calc_btn.isHidden(),
                "checked": self.back_calc_btn.isChecked(),
                "down": self.back_calc_btn.isDown(),
            },
        }

    def _restore_back_calculation_state(self, state):
        """Restore directly without invoking R, imputation, or calculator setters."""
        self.ma_unit.__dict__ = copy.deepcopy(state["ma_unit"].__dict__)
        for table, rows in zip(self.tables, state["tables"]):
            blocked = table.blockSignals(True)
            try:
                for row_index, row in enumerate(rows):
                    for column_index, text in enumerate(row):
                        item = table.item(row_index, column_index)
                        if item is None:
                            item = QTableWidgetItem()
                            table.setItem(row_index, column_index, item)
                        item.setText(text)
            finally:
                table.blockSignals(blocked)

        blocked = self.correlation_pre_post.blockSignals(True)
        try:
            self.correlation_pre_post.setText(state["correlation"])
        finally:
            self.correlation_pre_post.blockSignals(blocked)
        self.metric_parameter = state["metric_parameter"]
        button = state["button"]
        blocked = self.back_calc_btn.blockSignals(True)
        try:
            self.back_calc_btn.setText(button["text"])
            self.back_calc_btn.setEnabled(button["enabled"])
            self.back_calc_btn.setVisible(not button["hidden"])
            self.back_calc_btn.setChecked(button["checked"])
            self.back_calc_btn.setDown(button["down"])
        finally:
            self.back_calc_btn.blockSignals(blocked)

    def _restore_back_calculation_undo_state(self, count, index, clean, commands):
        if self.undoStack.index() != index:
            self.undoStack.setIndex(index)
        if self.undoStack.count() != count:
            if count == 0:
                self.undoStack.clear()
            else:
                raise RuntimeError(
                    "Back-calculation could not restore the prior undo history"
                )
        if any(
            self.undoStack.command(command_index) is not command
            for command_index, command in enumerate(commands)
        ):
            raise RuntimeError(
                "Back-calculation changed the identity of prior undo commands"
            )
        if clean:
            self.undoStack.setClean()
        elif self.undoStack.isClean():
            self.undoStack.resetClean()

    def _rollback_back_calculation_transaction(self, state, undo_state):
        errors = []
        try:
            self._restore_back_calculation_undo_state(*undo_state)
        except BaseException as error:
            errors.append(error)
        try:
            self._restore_back_calculation_state(state)
        except BaseException as error:
            errors.append(error)
        return errors

    def _back_calculation_state_matches(self, expected):
        try:
            current = self._capture_back_calculation_state()
            return (
                current["tables"] == expected["tables"]
                and current["correlation"] == expected["correlation"]
                and current["metric_parameter"] == expected["metric_parameter"]
                and current["button"] == expected["button"]
                and current["ma_unit"].__dict__ == expected["ma_unit"].__dict__
            )
        except BaseException:
            return False

    def _back_calculation_command_is_committed(
        self, command, token, committed_state, prior_index
    ):
        expected_index = prior_index + 1
        if (
            self.undoStack.index() != expected_index
            or self.undoStack.count() != expected_index
            or self.undoStack.isClean()
        ):
            return False
        published = self.undoStack.command(prior_index)
        identity_matches = published is command or (
            getattr(published, "_back_calculation_commit_token", None) is token
        )
        return identity_matches and self._back_calculation_state_matches(
            committed_state
        )

    def _publish_back_calculation_command(self, command, committed_state, prior_index):
        token = object()
        command._back_calculation_commit_token = token
        try:
            self.undoStack.push(command)
        except BaseException:
            if self._back_calculation_command_is_committed(
                command, token, committed_state, prior_index
            ):
                return
            raise

    def enable_back_calculation_btn(self, engage=False):
        if not engage:
            return self._enable_back_calculation_btn_impl(engage=False)

        state = self._capture_back_calculation_state()
        undo_state = (
            self.undoStack.count(),
            self.undoStack.index(),
            self.undoStack.isClean(),
            tuple(
                self.undoStack.command(command_index)
                for command_index in range(self.undoStack.count())
            ),
        )
        try:
            return self._enable_back_calculation_btn_impl(
                engage=True, transaction_state=state
            )
        except _BackCalculationCancelled:
            rollback_errors = self._rollback_back_calculation_transaction(
                state, undo_state
            )
            if rollback_errors:
                raise RuntimeError(
                    "Back-calculation cancellation rollback failed"
                ) from (rollback_errors[0])
            return None
        except BaseException as error:
            rollback_errors = self._rollback_back_calculation_transaction(
                state, undo_state
            )
            if rollback_errors:
                # Qt does not expose removal of one arbitrary command. If a
                # push changed an existing branch but cannot be proven to have
                # committed this transaction, discard the compromised history
                # so no ghost redo command can reapply it later.
                self.undoStack.clear()
                self.undoStack.resetClean()
            for rollback_error in rollback_errors:
                error.add_note("Rollback error: %s" % rollback_error)
            raise

    def _enable_back_calculation_btn_impl(self, engage=False, transaction_state=None):
        # For undo/redo
        old_ma_unit, old_tables_data = self._save_ma_unit_and_table_states(
            tables=[self.simple_table, self.g1_pre_post_table, self.g2_pre_post_table],
            ma_unit=self.ma_unit,
            use_old_value=False,
        )
        # Choose metric parameter if not already chosen
        if (
            engage
            and self.metric_parameter is None
            and self.cur_effect in ["MD", "SMD"]
        ):
            if self.cur_effect == "MD":
                info = (
                    "Back-calculation depends on the relationship between the "
                    "two population standard deviations.\n\n"
                    "Should RC MetaStudio assume they are equal?"
                )
                option0_txt = "Yes (default)"
                option1_txt = "No"
                dialog = ChooseBackCalcResultForm(info, option0_txt, option1_txt)
                dialog.setWindowTitle("Population standard deviations")
                if not dialog.exec():
                    raise _BackCalculationCancelled()
                self.metric_parameter = True if dialog.getChoice() == 0 else False
            elif self.cur_effect == "SMD":
                info = (
                    "Which standardized mean difference should RC MetaStudio use "
                    "for back-calculation?"
                )
                option0_txt = "Hedges' g (default)"
                option1_txt = "Cohen's d"
                dialog = ChooseBackCalcResultForm(info, option0_txt, option1_txt)
                dialog.setWindowTitle("Standardized mean difference")
                if not dialog.exec():
                    raise _BackCalculationCancelled()
                self.metric_parameter = True if dialog.getChoice() == 0 else False

        def build_data_dicts():
            var_names = self.get_column_header_strs()
            tmp = []
            for row_index in range(2):
                value = lambda x: self._get_float(row_index, x)
                tmp.append(
                    [
                        (self._imputation_field_name(var_name), value(i))
                        for i, var_name in enumerate(var_names)
                        if value(i) is not None
                    ]
                )
            group1_data = dict(tmp[0])
            group2_data = dict(tmp[1])

            tmp = self.ma_unit.get_effect_and_ci(
                self.cur_effect, self.group_str, self.mult
            )
            effect_data = {
                "est": tmp[0],
                "low": tmp[1],
                "high": tmp[2],
                "metric": self.cur_effect,
                "met.param": self.metric_parameter,
            }

            # print("Group 1 Data: ", group1_data)
            # print("Group 2 Data: ", group2_data)
            # print("Effect Data: ", effect_data)

            return (group1_data, group2_data, effect_data)

        def new_data(g1_data, g2_data, imputed):
            changed = False

            new_data = (
                imputed["n1"],
                imputed["sd1"],
                imputed["mean1"],
                imputed["n2"],
                imputed["sd2"],
                imputed["mean2"],
            )
            old_data = (
                g1_data["n"] if "n" in g1_data else None,
                g1_data["sd"] if "sd" in g1_data else None,
                g1_data["mean"] if "mean" in g1_data else None,
                g2_data["n"] if "n" in g2_data else None,
                g2_data["sd"] if "sd" in g2_data else None,
                g2_data["mean"] if "mean" in g2_data else None,
            )
            new_item_available = lambda old, new: (old is None) and (new is not None)
            comparison = [
                new_item_available(old_data[i], new_data[i])
                for i in range(len(new_data))
            ]
            if any(comparison):
                changed = True
            else:
                changed = False
            return changed

        if self.cur_effect not in ["MD", "SMD"]:
            was_hidden = self.back_calc_btn.isHidden()
            self.back_calc_btn.setVisible(False)
            if not was_hidden:
                self._content_layout_changed()
            return None
        else:
            was_hidden = self.back_calc_btn.isHidden()
            self.back_calc_btn.setVisible(True)
            if was_hidden:
                self._content_layout_changed()

        (group1_data, group2_data, effect_data) = build_data_dicts()

        # The metric-specific assumption is chosen only after the user clicks.
        # Probe both choices here so the button can become reachable without
        # prematurely committing either assumption to the form.
        if not engage and self.metric_parameter is None:
            for candidate in (True, False):
                candidate_effect_data = dict(effect_data)
                candidate_effect_data["met.param"] = candidate
                candidate_imputed = meta_py_r.back_calc_cont_data(
                    group1_data,
                    group2_data,
                    candidate_effect_data,
                    self.conf_level,
                )
                if "FAIL" not in candidate_imputed and new_data(
                    group1_data, group2_data, candidate_imputed
                ):
                    self.back_calc_btn.setEnabled(True)
                    self.set_clear_btn_color()
                    return None
            self.back_calc_btn.setEnabled(False)
            self.set_clear_btn_color()
            return None

        imputed = meta_py_r.back_calc_cont_data(
            group1_data, group2_data, effect_data, self.conf_level
        )

        # Leave if there was a failure
        if "FAIL" in imputed:
            self.back_calc_btn.setEnabled(False)
            return None

        if new_data(group1_data, group2_data, imputed):
            self.back_calc_btn.setEnabled(True)
        else:
            self.back_calc_btn.setEnabled(False)
        self.set_clear_btn_color()

        if not engage:
            return None

        ########################################################################
        # Actually do stuff with imputed data here if we are 'engaged'
        ########################################################################
        # Choose one of the values if multiple ones were returned in the output
        keys_to_names = {
            "n1": "group 1 sample size",
            "n2": "group 2 sample size",
            "sd1": "group 1 standard deviation",
            "sd2": "group 2 standard deviation",
            "mean1": "group 1 mean",
            "mean2": "group 2 mean",
        }
        for key, value in imputed.items():
            # The R imputation code can theoretically yield up to four values
            # for n1 and n2, but empirical testing shows that path is unused.
            # ChooseBackCalcResultForm options can be generated dynamically if
            # multi-value n1/n2 results are later exposed.

            if is_list(value):
                info = (
                    "The back calculation has resulted in multiple results for "
                    + keys_to_names[key]
                    + "\n\nPlease choose one of the following:"
                )
                option0_txt = keys_to_names[key] + " = " + str(value[0])
                option1_txt = keys_to_names[key] + " = " + str(value[1])

                dialog = ChooseBackCalcResultForm(info, option0_txt, option1_txt)
                if dialog.exec():
                    imputed[key] = value[0] if dialog.getChoice() == 0 else value[1]
                else:  # pressed cancel
                    raise _BackCalculationCancelled()

        # Write the data to the table
        var_names = self.get_column_header_strs()
        group1_data = {
            "n": imputed["n1"],
            "sd": imputed["sd1"],
            "mean": imputed["mean1"],
        }
        group2_data = {
            "n": imputed["n2"],
            "sd": imputed["sd2"],
            "mean": imputed["mean2"],
        }
        for row in range(len(self.cur_groups)):
            for var_index, var_name in enumerate(var_names):
                field_name = self._imputation_field_name(var_name)
                if field_name not in ["n", "sd", "mean"]:
                    continue
                val = group1_data[field_name] if row == 0 else group2_data[field_name]
                if field_name == "n" and val not in EMPTY_VALS:
                    val = int(round(val))  # convert float to integer
                self._set_val(row, var_index, val, self.simple_table)

        self.impute_data()
        self._copy_raw_data_from_table_to_ma_unit()
        # self.set_clear_btn_color()

        # The committed result has filled every value exposed by this
        # back-calculation, so no second R probe is needed to refresh the button.
        self.back_calc_btn.setEnabled(False)
        new_state = self._capture_back_calculation_state()
        restore_old_f = lambda: self._restore_back_calculation_state(transaction_state)
        restore_new_f = lambda: self._restore_back_calculation_state(new_state)
        command = calc_fncs.CommandFieldChanged(
            restore_new_f=restore_new_f,
            restore_old_f=restore_old_f,
            parent=self,
            description="Apply continuous back-calculation",
            refresh_on_initial_redo=False,
        )
        self._publish_back_calculation_command(
            command, new_state, self.undoStack.index()
        )

    def clear_form(self):
        # For undo/redo
        old_ma_unit, old_tables_data = self._save_ma_unit_and_table_states(
            tables=[self.simple_table, self.g1_pre_post_table, self.g2_pre_post_table],
            ma_unit=self.ma_unit,
            use_old_value=False,
        )
        old_correlation = self._get_correlation_str()

        self.metric_parameter = None

        with ExitStack() as signal_blockers:
            for widget in self.entry_widgets:
                signal_blockers.enter_context(QSignalBlocker(widget))
            # reset tables
            for table in self.tables:
                for row_index in range(len(self.cur_groups)):
                    for var_index in range(table.columnCount()):
                        self._set_val(row_index, var_index, "", table=table)

        self._copy_raw_data_from_table_to_ma_unit()

        # clear out effects stuff
        for metric in CONTINUOUS_ONE_ARM_METRICS + CONTINUOUS_TWO_ARM_METRICS:
            if (
                self.cur_effect in CONTINUOUS_TWO_ARM_METRICS
                and metric in CONTINUOUS_TWO_ARM_METRICS
            ) or (
                self.cur_effect in CONTINUOUS_ONE_ARM_METRICS
                and metric in CONTINUOUS_ONE_ARM_METRICS
            ):
                self.ma_unit.set_effect_and_ci(
                    metric, self.group_str, None, None, None, mult=self.mult
                )
            else:
                # Future work: handle remapping if group labels become editable here.
                pass

        # clear line edits
        self.set_current_effect()
        with ExitStack() as signal_blockers:
            for widget in self.entry_widgets:
                signal_blockers.enter_context(QSignalBlocker(widget))
            self.correlation_pre_post.setText("0.0")

        # For undo/redo
        self.enable_back_calculation_btn()
        new_ma_unit, new_tables_data = self._save_ma_unit_and_table_states(
            tables=[self.simple_table, self.g1_pre_post_table, self.g2_pre_post_table],
            ma_unit=self.ma_unit,
            use_old_value=False,
        )
        new_correlation = self._get_correlation_str()
        restore_old_f = lambda: self.restore_ma_unit_and_tables(
            old_ma_unit, old_tables_data, old_correlation
        )
        restore_new_f = lambda: self.restore_ma_unit_and_tables(
            new_ma_unit, new_tables_data, new_correlation
        )
        command = calc_fncs.CommandFieldChanged(
            restore_new_f=restore_new_f, restore_old_f=restore_old_f, parent=self
        )
        self.undoStack.push(command)

    def get_effect_names(self):
        effects = self.ma_unit.get_effect_names()
        return effects

    def _effect_display_label(self, effect):
        return "%s (%s)" % (CONTINUOUS_METRIC_NAMES.get(effect, effect), effect)

    def _selected_effect(self):
        effect = self.effect_cbo_box.currentData()
        if effect is None:
            effect = self.effect_cbo_box.currentText()
        return str(effect)

    def get_cur_group_str(self):
        # Inspired from get_cur_group_str of ma_data_table_model

        if self.cur_effect in CONTINUOUS_ONE_ARM_METRICS:
            group_str = self.cur_groups[0]
        else:
            group_str = "-".join(self.cur_groups)
        return group_str

    ####### Undo framework ############
    def undo(self):
        self.undoStack.undo()

    def redo(self):
        self.undoStack.redo()


################################################################################
class ChooseBackCalcResultForm(
    QDialog,
    forms.ui_continuous_back_calc_result_form.Ui_ContinuousBackCalcResultForm,
):
    def __init__(
        self, info_text, op1_txt, op2_txt, parent=None, op3_txt=None, op4_txt=None
    ):
        super(ChooseBackCalcResultForm, self).__init__(parent)
        self.setupUi(self)

        for widget in self.content_widget.findChildren(QWidget):
            widget.installEventFilter(self)
        self._layout_controller = adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )

        ####self.choice1_lbl.setText(op1_txt)
        ####self.choice2_lbl.setText(op2_txt)

        self.choice1_label.setText(op1_txt)
        self.choice2_label.setText(op2_txt)

        self.info_label.setText(info_text)
        self._layout_controller.request_content_refit()

    def eventFilter(  # ty: ignore[invalid-method-override] -- PyQt6's QDialog stub rejects this runtime-supported QObject override.
        self, watched: QObject | None, event: QEvent | None
    ) -> bool:
        if event is None:
            return super(ChooseBackCalcResultForm, self).eventFilter(watched, event)
        if event.type() == QEvent.Type.MouseButtonRelease:
            if watched is self.choice1_label:
                self.choice1_btn.setChecked(True)
                return True
            if watched is self.choice2_label:
                self.choice2_btn.setChecked(True)
                return True
        if (
            isinstance(watched, QWidget)
            and event.type() == QEvent.Type.FocusIn
            and self.content_widget.isAncestorOf(watched)
        ):
            self.content_scroll.ensureWidgetVisible(watched)
            QTimer.singleShot(
                0, lambda target=watched: self._ensure_content_widget_visible(target)
            )
        return super(ChooseBackCalcResultForm, self).eventFilter(watched, event)

    def _ensure_content_widget_visible(self, widget):
        try:
            self.content_scroll.ensureWidgetVisible(widget)
            center = widget.mapTo(self.content_widget, widget.rect().center())
            self.content_scroll.ensureVisible(center.x(), center.y(), 12, 12)
        except RuntimeError:
            pass

    def getChoice(self):
        # Choice data to be returned is index of data item
        if self.choice1_btn.isChecked():
            return 0
        else:
            return 1


################################################################################
