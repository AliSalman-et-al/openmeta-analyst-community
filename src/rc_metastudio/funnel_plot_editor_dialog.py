# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Edit presentation-only parameters for a persisted funnel artifact."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QColorDialog, QDialog, QDialogButtonBox, QFileDialog

from rc_metastudio import adaptive_window, app_error_handler, qt_text
from rc_metastudio.plot_text import (
    apply_plot_text_input_limits,
    plot_text_value,
)
from rc_metastudio.publication_bias import (
    FUNNEL_STYLE_LABELS,
    FUNNEL_STYLE_PRESETS,
    FunnelStyle,
)

if TYPE_CHECKING:
    from ui_funnel_plot_editor_dialog import Ui_FunnelPlotEditorDialog
else:
    from rc_metastudio.forms import (
        ui_funnel_plot_editor_dialog as _ui_funnel_plot_editor_dialog,
    )

    Ui_FunnelPlotEditorDialog = _ui_funnel_plot_editor_dialog.Ui_FunnelPlotEditorDialog


PLOT_EDITOR_SAVE_FILTER = "Plot images (*.pdf *.png *.tif *.tiff *.svg);;All files (*)"
LABEL_VALUES = {
    "None": "none",
    "Outside pseudo-confidence region": "outside-pseudo-confidence-region",
    "All": "all",
}
POINT_SYMBOL_VALUES = {
    "Filled circle": 19,
    "Open circle": 1,
    "Square": 15,
    "Triangle": 17,
    "Diamond": 18,
}
POINT_SYMBOL_LABELS = {value: label for label, value in POINT_SYMBOL_VALUES.items()}


class FunnelPlotEditorDialog(QDialog, Ui_FunnelPlotEditorDialog):
    """Keep funnel editing separate from forest and regression controls."""

    applied = pyqtSignal()

    def __init__(self, plot_params, image_path, parent=None, plot_type="funnel"):
        super().__init__(parent)
        self.setupUi(self)
        apply_plot_text_input_limits(self)
        self._params = dict(plot_params or {})
        self._dirty = False
        self._pending_ok = False
        self._allow_close = True
        try:
            self._funnel_index = max(
                1, int(self._scalar(self._params.get("funnel.index", 1)))
            )
        except (TypeError, ValueError):
            self._funnel_index = 1
        self.plot_type = str(plot_type)
        self._validate_kind_descriptor()
        self.kind = self._kind_from_params()
        self.kind_label.setText(f"Funnel kind: {self.kind}")
        self._load_params(image_path)
        self._configure_kind()
        self.style_combo.currentTextChanged.connect(self._apply_style)
        for edit, button, title in (
            (self.point_color_edit, self.point_color_button, "Choose point color"),
            (
                self.reference_color_edit,
                self.reference_color_button,
                "Choose reference or regression color",
            ),
            (
                self.region_color_edit,
                self.region_color_button,
                "Choose confidence or contour color",
            ),
            (
                self.background_color_edit,
                self.background_color_button,
                "Choose plot background color",
            ),
        ):
            edit.textChanged.connect(
                lambda _text, color_edit=edit, color_button=button: self._update_color_button(
                    color_edit, color_button
                )
            )
            button.clicked.connect(
                lambda _checked=False, color_edit=edit, color_button=button, dialog_title=title: self._choose_color(
                    color_edit, color_button, dialog_title
                )
            )
            self._update_color_button(edit, button)
        self.browse_button.clicked.connect(
            app_error_handler.safe_slot(self._browse_image_path, parent=self)
        )
        self.button_box.clicked.connect(self._button_clicked)
        self._connect_dirty_signals()
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )

    def _connect_dirty_signals(self):
        for control in (
            self.style_combo,
            self.label_policy_combo,
            self.point_symbol_combo,
            self.point_size_spin,
            self.point_color_edit,
            self.reference_color_edit,
            self.region_color_edit,
            self.background_color_edit,
            self.reference_visible_check,
            self.regression_visible_check,
            self.pooled_overlay_check,
            self.sampling_confidence_spin,
            self.include_tau2_check,
            self.sampling_region_check,
            self.contour_levels_edit,
            self.x_label_edit,
            self.y_label_edit,
            self.x_lower_edit,
            self.x_upper_edit,
            self.x_ticks_edit,
            self.path_edit,
        ):
            signal = getattr(control, "currentTextChanged", None)
            if signal is None:
                signal = getattr(control, "textChanged", None)
            if signal is None:
                signal = getattr(control, "valueChanged", None)
            if signal is None:
                signal = getattr(control, "toggled", None)
            if signal is not None:
                signal.connect(self._mark_dirty)

    def _mark_dirty(self, *_args):
        self._dirty = True

    def _button_clicked(self, button):
        button_type = self.button_box.standardButton(button)
        if button_type == QDialogButtonBox.StandardButton.Apply:
            self._commit()
        elif button_type == QDialogButtonBox.StandardButton.Ok and self._dirty:
            self._pending_ok = True
            self._allow_close = False
            self._commit()

    def _commit(self):
        self.applied.emit()

    def mark_commit_succeeded(self):
        """Clear dirty state after the synchronous Results regeneration succeeds."""
        self._params = self.plot_params()
        self._dirty = False
        self._allow_close = True

    def mark_commit_failed(self):
        """Keep edits pending when Results regeneration fails."""
        self._allow_close = False

    def accept(self):
        if self._pending_ok and not self._allow_close:
            return
        super().accept()

    def _kind_from_params(self):
        kind = self._scalar(self._params.get("funnel.kind"))
        if kind:
            return str(kind)
        return {
            "contour_funnel": "contour",
            "deeks_funnel": "deeks",
            "trimfill_funnel": "trimfill",
        }.get(self.plot_type, "ordinary")

    def _validate_kind_descriptor(self):
        expected = {
            "funnel": "ordinary",
            "contour_funnel": "contour",
            "deeks_funnel": "deeks",
            "trimfill_funnel": "trimfill",
        }.get(self.plot_type)
        if expected is None:
            raise ValueError(f"unsupported funnel plot descriptor: {self.plot_type}")
        persisted = self._scalar(self._params.get("funnel.kind"))
        if persisted is not None and str(persisted) != expected:
            raise ValueError(
                f"funnel plot descriptor kind {persisted!r} does not match {expected!r}"
            )

    def _load_params(self, image_path):
        try:
            style_code = FunnelStyle(str(self._value("funnel.style", "default")))
        except ValueError:
            style_code = FunnelStyle.DEFAULT
        style_label = FUNNEL_STYLE_LABELS[style_code]
        style = FUNNEL_STYLE_PRESETS[style_code]
        self.style_combo.setCurrentText(style_label)
        self.label_policy_combo.setCurrentText(
            {
                "none": "None",
                "outside-pseudo-confidence-region": "Outside pseudo-confidence region",
                "all": "All",
            }.get(str(self._value("funnel.label.policy", "none")), "None")
        )
        symbol = self._value(
            "funnel.point.symbol", style["point_symbol"]
        )
        try:
            symbol = int(symbol)
        except (TypeError, ValueError):
            symbol = 19
        self.point_symbol_combo.setCurrentText(
            next(
                (
                    label
                    for label, value in POINT_SYMBOL_VALUES.items()
                    if value == symbol
                ),
                "Filled circle",
            )
        )
        self.point_size_spin.setValue(
            self._float("funnel.point.size", self._float("point.size", 1.0))
        )
        self.point_color_edit.setText(
            str(self._value("funnel.point.color", style["point_color"]))
        )
        self.reference_color_edit.setText(
            str(self._value("funnel.reference.color", style["reference_color"]))
        )
        self.region_color_edit.setText(
            str(self._value("funnel.region.color", style["region_color"]))
        )
        self.background_color_edit.setText(
            str(self._value("funnel.background.color", style["background_color"]))
        )
        self.reference_visible_check.setChecked(
            self._bool("funnel.reference.visible", True)
        )
        self.regression_visible_check.setChecked(
            self._bool("funnel.regression.visible", True)
        )
        self.pooled_overlay_check.setChecked(
            self._bool("funnel.pooled.overlay.visible", True)
        )
        self.sampling_confidence_spin.setValue(
            self._float("funnel.sampling.conf.level", self._float("conf.level", 95.0))
        )
        self.include_tau2_check.setChecked(self._bool("funnel.include.tau2", False))
        self.sampling_region_check.setChecked(
            self._bool("funnel.sampling.region.visible", True)
        )
        levels = self._value("funnel.contour.levels", "90,95,99")
        if isinstance(levels, (list, tuple)):
            levels = ",".join(str(value) for value in levels)
        self.contour_levels_edit.setText(str(levels))
        default_x_label = (
            "1/sqrt(ESS)"
            if self.kind == "deeks"
            else self._value("axis.label", "[default]")
        )
        default_y_label = (
            "Log diagnostic odds ratio" if self.kind == "deeks" else "Standard error"
        )
        self.x_label_edit.setText(
            str(self._value("funnel.xlab", default_x_label))
        )
        self.y_label_edit.setText(
            str(self._value("funnel.ylab", default_y_label))
        )
        self.x_lower_edit.setText(str(self._value("funnel.xlim.lower", "[default]")))
        self.x_upper_edit.setText(str(self._value("funnel.xlim.upper", "[default]")))
        ticks = self._value("funnel.xticks", "[default]")
        if isinstance(ticks, (list, tuple)):
            ticks = ",".join(str(value) for value in ticks)
        self.x_ticks_edit.setText(str(ticks))
        persisted_outpath = self._value("funnel.outpath", "")
        self.path_edit.setText(str(persisted_outpath or image_path or ""))

    def _configure_kind(self):
        contour = self.kind == "contour"
        deeks = self.kind == "deeks"
        trimfill = self.kind == "trimfill"
        if deeks:
            outside_index = self.label_policy_combo.findText(
                "Outside pseudo-confidence region"
            )
            if outside_index >= 0:
                self.label_policy_combo.removeItem(outside_index)
            if self.label_policy_combo.currentText() not in ("None", "All"):
                self.label_policy_combo.setCurrentText("None")
            self.label_policy_combo.setToolTip(
                "The Deeks funnel has no pseudo-confidence region; choose None or All."
            )
        self.contour_levels_edit.setEnabled(contour)
        self.contour_levels_label.setEnabled(contour)
        self.contour_levels_edit.setToolTip(
            "Available only for contour-enhanced funnels."
            if not contour
            else "Null-centered contour significance levels, comma separated."
        )
        self.sampling_confidence_spin.setEnabled(not deeks)
        self.sampling_confidence_label.setEnabled(not deeks)
        self.sampling_region_check.setEnabled(not deeks and not contour)
        self.sampling_region_check.setToolTip(
            "Contour levels replace the single pseudo-confidence region."
            if contour
            else "Show or hide the sampling-error pseudo-confidence region."
        )
        self.include_tau2_check.setEnabled(not deeks)
        self.include_tau2_check.setToolTip(
            "Not applicable to the Deeks effective-sample-size funnel."
            if deeks
            else "Include tau² in the pseudo-confidence region."
        )
        self.pooled_overlay_check.setEnabled(not deeks)
        self.pooled_overlay_label.setEnabled(not deeks)
        self.regression_visible_check.setEnabled(deeks)
        self.regression_visible_label.setEnabled(deeks)
        self.regression_visible_check.setToolTip(
            "Deeks regression line visibility; statistical fitting is unchanged."
            if deeks
            else "Only the Deeks funnel has an editable regression-line setting."
        )
        if trimfill:
            self.rerun_note.setText(
                "Only augmented-funnel presentation can be edited here. The trim-and-fill "
                "estimator, side, model, imputed studies, and eligible study set require a full rerun."
            )

    def _browse_image_path(self):
        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save funnel plot image",
            qt_text.to_native_text(self.path_edit.text()),
            PLOT_EDITOR_SAVE_FILTER,
        )
        if selected_path:
            self.path_edit.setText(selected_path)

    def _apply_style(self, style_name):
        style = next(
            (
                code
                for code, label in FUNNEL_STYLE_LABELS.items()
                if label == style_name
            ),
            None,
        )
        if style is None:
            return
        preset = FUNNEL_STYLE_PRESETS[style]
        self.point_symbol_combo.setCurrentText(
            POINT_SYMBOL_LABELS[int(preset["point_symbol"])]
        )
        self.point_color_edit.setText(str(preset["point_color"]))
        self.reference_color_edit.setText(str(preset["reference_color"]))
        self.region_color_edit.setText(str(preset["region_color"]))
        self.background_color_edit.setText(str(preset["background_color"]))

    def _choose_color(self, edit, button, title):
        initial = QColor(qt_text.to_native_text(edit.text()))
        color = QColorDialog.getColor(
            initial if initial.isValid() else QColor("black"), self, title
        )
        if color.isValid():
            edit.setText(color.name(QColor.NameFormat.HexRgb).upper())
            self._update_color_button(edit, button)

    @staticmethod
    def _update_color_button(edit, button):
        color = QColor(qt_text.to_native_text(edit.text()))
        if not color.isValid():
            button.setStyleSheet("")
            return
        foreground = "#000000" if color.lightness() > 150 else "#FFFFFF"
        button.setStyleSheet(
            f"background-color: {color.name()}; color: {foreground};"
        )

    @staticmethod
    def _scalar(value):
        if isinstance(value, (list, tuple)) and value:
            return value[0]
        return value

    def _value(self, name, default):
        value = self._params.get(name, default)
        if isinstance(value, (list, tuple)) and value:
            return value[min(self._funnel_index - 1, len(value) - 1)]
        return value

    def _bool(self, name, default):
        value = self._value(name, default)
        if isinstance(value, str):
            return value.lower() in ("true", "t", "1", "yes")
        return bool(value)

    def _float(self, name, default):
        try:
            return float(self._value(name, default))
        except (TypeError, ValueError):
            return float(default)

    def plot_params(self):
        """Return the original run params plus presentation-only edits."""
        params = dict(self._params)
        edits = {
            "funnel.style": next(
                code.value
                for code, label in FUNNEL_STYLE_LABELS.items()
                if label == self.style_combo.currentText()
            ),
            "funnel.label.policy": LABEL_VALUES[self.label_policy_combo.currentText()],
            "funnel.point.symbol": POINT_SYMBOL_VALUES[
                self.point_symbol_combo.currentText()
            ],
            "funnel.point.size": self.point_size_spin.value(),
            "funnel.point.color": qt_text.to_native_text(self.point_color_edit.text()),
            "funnel.reference.color": qt_text.to_native_text(self.reference_color_edit.text()),
            "funnel.region.color": qt_text.to_native_text(self.region_color_edit.text()),
            "funnel.background.color": qt_text.to_native_text(
                self.background_color_edit.text()
            ),
            "funnel.reference.visible": self.reference_visible_check.isChecked(),
            "funnel.regression.visible": self.regression_visible_check.isChecked(),
            "funnel.pooled.overlay.visible": self.pooled_overlay_check.isChecked(),
            "funnel.sampling.conf.level": self.sampling_confidence_spin.value(),
            "funnel.sampling.region.visible": self.sampling_region_check.isChecked(),
            "funnel.include.tau2": self.include_tau2_check.isChecked(),
            "funnel.contour.levels": qt_text.to_native_text(self.contour_levels_edit.text()),
            "funnel.xlab": qt_text.to_native_text(plot_text_value(self.x_label_edit)),
            "funnel.ylab": qt_text.to_native_text(plot_text_value(self.y_label_edit)),
            "funnel.xlim.lower": qt_text.to_native_text(self.x_lower_edit.text()),
            "funnel.xlim.upper": qt_text.to_native_text(self.x_upper_edit.text()),
            "funnel.xticks": qt_text.to_native_text(self.x_ticks_edit.text()),
            "funnel.outpath": qt_text.to_native_text(self.path_edit.text()),
        }
        for name, value in edits.items():
            previous = self._params.get(name)
            if isinstance(previous, (list, tuple)) and previous:
                values = list(previous)
                values[min(self._funnel_index - 1, len(values) - 1)] = value
                params[name] = values
            else:
                params[name] = value
        return params
