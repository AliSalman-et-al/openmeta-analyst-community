# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Edit the presentation and output path of a generated plot."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QColorDialog, QDialog, QDialogButtonBox, QFileDialog
from typing import TYPE_CHECKING

from rc_metastudio import adaptive_window, app_error_handler, plot_capabilities, qt_text
from rc_metastudio.plot_defaults import FOREST_ARM_LABELS
from rc_metastudio.plot_text import (
    apply_plot_text_input_limits,
    plot_text_value,
    set_plot_text_value,
)

if TYPE_CHECKING:
    from ui_edit_plot_dialog import Ui_EditPlotDialog
else:
    from rc_metastudio.forms.ui_edit_plot_dialog import Ui_EditPlotDialog


PLOT_EDITOR_SAVE_FILTER = "Plot images (*.pdf *.png *.tif *.tiff *.svg);;All files (*)"
FOREST_STYLE_LABELS = {
    "default": "Default (metafor)",
    "revman": "RevMan",
    "bmj": "BMJ",
}
FOREST_STYLE_VALUES = {label: value for value, label in FOREST_STYLE_LABELS.items()}
FOREST_STYLE_DEFAULT_COLORS = {
    "default": "#2f5597",
    "revman": "#000000",
    "bmj": "#6b58a6",
}


class EditPlotDialog(QDialog, Ui_EditPlotDialog):
    applied = pyqtSignal()

    def __init__(self, plot_params, image_path, parent=None, plot_type="forest"):
        super(EditPlotDialog, self).__init__(parent)
        self.setupUi(self)
        apply_plot_text_input_limits(self)
        self._loading_style = False
        self._params = dict(plot_params or {})
        self.plot_type = plot_type
        self._option_groups = plot_capabilities.option_groups(plot_type)

        self.color_btn.clicked.connect(
            app_error_handler.safe_slot(self._choose_color, parent=self)
        )
        self.save_btn.clicked.connect(
            app_error_handler.safe_slot(self._browse_image_path, parent=self)
        )
        self.style_cbo.currentTextChanged.connect(
            app_error_handler.safe_slot(self._style_changed, parent=self)
        )
        apply_button = self.buttonBox.button(QDialogButtonBox.StandardButton.Apply)
        if apply_button is not None:
            apply_button.clicked.connect(self.applied.emit)
        ok_button = self.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.clicked.connect(self.applied.emit)

        self._load_params(image_path)
        self._configure_option_groups()
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )

    def _configure_option_groups(self):
        self.groupBox.setVisible("columns" in self._option_groups)
        self.default_panel.setVisible("forest" in self._option_groups)
        self.label_16.setVisible("summary" in self._option_groups)
        self.show_summary_line.setVisible("summary" in self._option_groups)
        self.regression_group.setVisible("regression" in self._option_groups)

    def _load_params(self, image_path):
        self._loading_style = True
        try:
            style = self._normalized_style(
                self._params.get(self._param_name("style"), "default")
            )
            self.style_cbo.setCurrentText(FOREST_STYLE_LABELS[style])
            self._set_text(
                self.col1_str_edit, self._params.get("fp_col1_str", "Study or Subgroup")
            )
            self._set_text(
                self.col2_str_edit, self._params.get("fp_col2_str", "[default]")
            )
            self._set_text(
                self.col3_str_edit,
                self._params.get("fp_col3_str", FOREST_ARM_LABELS[0]),
            )
            self._set_text(
                self.col4_str_edit,
                self._params.get("fp_col4_str", FOREST_ARM_LABELS[1]),
            )
            self.show_1.setChecked(self._bool_param("fp_show_col1", True))
            self.show_2.setChecked(self._bool_param("fp_show_col2", True))
            self.show_3.setChecked(self._bool_param("fp_show_col3", True))
            self.show_4.setChecked(self._bool_param("fp_show_col4", True))
            self.show_raw_counts.setChecked(
                self._bool_param("fp_show_raw_counts", True)
            )
            self.show_headers.setChecked(self._bool_param("fp_show_headers", True))
            self.show_annotation.setChecked(
                self._bool_param("fp_show_annotation", True)
            )
            self._set_text(
                self.x_lbl_le, self._params.get(self._param_name("xlabel"), "[default]")
            )
            self._set_text(
                self.plot_lb_le,
                self._params.get(self._param_name("plot_lb"), "[default]"),
            )
            self._set_text(
                self.plot_ub_le,
                self._params.get(self._param_name("plot_ub"), "[default]"),
            )
            ticks_name = "bp_xticks" if self.plot_type == "regression" else "fp_xticks"
            self._set_text(self.x_ticks_le, self._params.get(ticks_name, "[default]"))
            self.show_summary_line.setChecked(
                self._bool_param("fp_show_summary_line", True)
            )
            self._set_text(
                self.image_path,
                image_path or self._params.get(self._param_name("outpath"), ""),
            )
            color = (
                self._params.get(self._param_name("accent_color"))
                or FOREST_STYLE_DEFAULT_COLORS[style]
            )
            self._set_accent_color(color)
            self.point_size_multiplier.setValue(
                self._float_param(self._param_name("point_size_multiplier"), 1.0)
            )
            self.show_regression_line.setChecked(
                self._bool_param("bp_show_regression_line", True)
            )
            self.show_confidence_band.setChecked(
                self._bool_param("bp_show_confidence_band", True)
            )
            self.show_prediction_interval.setChecked(
                self._bool_param("bp_show_prediction_interval", False)
            )
            self.show_legend.setChecked(self._bool_param("bp_show_legend", False))
        finally:
            self._loading_style = False

    def _style_changed(self, label):
        if self._loading_style:
            return
        style = FOREST_STYLE_VALUES.get(str(label), "default")
        self._set_accent_color(FOREST_STYLE_DEFAULT_COLORS[style])

    def _choose_color(self):
        current = QColor(self.accent_color.text())
        color = QColorDialog.getColor(current, self, "Plot Accent Color")
        if color.isValid():
            self._set_accent_color(color.name())

    def _browse_image_path(self):
        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save %s Plot Image" % self.plot_type.title(),
            qt_text.to_native_text(self.image_path.text()),
            PLOT_EDITOR_SAVE_FILTER,
        )
        if selected_path:
            self.image_path.setText(selected_path)

    def _set_accent_color(self, color):
        text = str(color or FOREST_STYLE_DEFAULT_COLORS["default"])
        self.accent_color.setText(text)
        self.color_btn.setStyleSheet("background-color: %s;" % text)

    def _set_text(self, widget, value):
        set_plot_text_value(widget, self._scalar(value))

    def _scalar(self, value):
        if isinstance(value, (list, tuple)) and value:
            return value[0]
        return value

    def _bool_param(self, name, default):
        value = self._scalar(self._params.get(name, default))
        if isinstance(value, str):
            return value.lower() in ("true", "t", "1", "yes")
        return bool(value)

    def _float_param(self, name, default):
        try:
            return float(self._scalar(self._params.get(name, default)))
        except (TypeError, ValueError):
            return default

    def _normalized_style(self, style):
        style = str(self._scalar(style) or "default").strip().lower()
        return style if style in FOREST_STYLE_LABELS else "default"

    def _param_name(self, suffix):
        return "%s_%s" % ("bp" if self.plot_type == "regression" else "fp", suffix)

    def plot_params(self):
        style = FOREST_STYLE_VALUES.get(str(self.style_cbo.currentText()), "default")
        params = {
            "fp_style": style,
            "fp_show_col1": self.show_1.isChecked(),
            "fp_col1_str": qt_text.to_native_text(plot_text_value(self.col1_str_edit)),
            "fp_show_col2": self.show_2.isChecked(),
            "fp_col2_str": qt_text.to_native_text(plot_text_value(self.col2_str_edit)),
            "fp_show_col3": self.show_3.isChecked(),
            "fp_col3_str": qt_text.to_native_text(plot_text_value(self.col3_str_edit)),
            "fp_show_col4": self.show_4.isChecked(),
            "fp_col4_str": qt_text.to_native_text(plot_text_value(self.col4_str_edit)),
            "fp_show_raw_counts": self.show_raw_counts.isChecked(),
            "fp_show_headers": self.show_headers.isChecked(),
            "fp_show_annotation": self.show_annotation.isChecked(),
            "fp_accent_color": qt_text.to_native_text(self.accent_color.text()),
            "fp_point_size_multiplier": self.point_size_multiplier.value(),
            "fp_xlabel": qt_text.to_native_text(plot_text_value(self.x_lbl_le)),
            "fp_plot_lb": qt_text.to_native_text(self.plot_lb_le.text()),
            "fp_plot_ub": qt_text.to_native_text(self.plot_ub_le.text()),
            "fp_xticks": qt_text.to_native_text(self.x_ticks_le.text()),
            "fp_show_summary_line": self.show_summary_line.isChecked(),
            "fp_outpath": qt_text.to_native_text(self.image_path.text()),
        }
        forest_display_path = self._scalar(self._params.get("fp_display_path", ""))
        if forest_display_path:
            params["fp_display_path"] = forest_display_path
        if self.plot_type == "regression":
            params = {
                "bp_style": style,
                "bp_accent_color": qt_text.to_native_text(self.accent_color.text()),
                "bp_point_size_multiplier": self.point_size_multiplier.value(),
                "bp_xlabel": qt_text.to_native_text(plot_text_value(self.x_lbl_le)),
                "bp_plot_lb": qt_text.to_native_text(self.plot_lb_le.text()),
                "bp_plot_ub": qt_text.to_native_text(self.plot_ub_le.text()),
                "bp_xticks": qt_text.to_native_text(self.x_ticks_le.text()),
                "bp_show_regression_line": self.show_regression_line.isChecked(),
                "bp_show_confidence_band": self.show_confidence_band.isChecked(),
                "bp_show_prediction_interval": self.show_prediction_interval.isChecked(),
                "bp_show_legend": self.show_legend.isChecked(),
                "bp_outpath": qt_text.to_native_text(self.image_path.text()),
            }
            regression_display_path = self._scalar(
                self._params.get("bp_display_path", "")
            )
            if regression_display_path:
                params["bp_display_path"] = regression_display_path
        return params
