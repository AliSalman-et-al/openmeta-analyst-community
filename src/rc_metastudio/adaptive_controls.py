# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Semantic sizing policies for values and choices in adaptive forms."""

from PyQt5.QtCore import QEvent, QObject, QPoint, QRect, QTimer, Qt
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QListView,
    QSizePolicy,
    QStyle,
    QWIDGETSIZE_MAX,
)


VALUE_SELECTOR_VISIBLE_CHARACTERS = 18


def available_geometry_for_choice_control(combo):
    """Return the owning screen's available Logical Layout Space."""
    window = combo.window()
    handle = window.windowHandle() if window is not None else None
    if handle is not None and handle.screen() is not None:
        return QRect(handle.screen().availableGeometry())
    center = combo.mapToGlobal(combo.rect().center())
    screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
    return QRect(screen.availableGeometry()) if screen is not None else QRect()


class ChoiceListView(QListView):
    """Popup view preserving complete values and horizontal access."""

    def __init__(self, parent=None):
        super(ChoiceListView, self).__init__(parent)
        self.choice_controller = None


class AdaptiveComboBox(QComboBox):
    """Choice control with one native-safe popup measurement/clamp path."""

    def showPopup(self):
        controller = getattr(self, "_adaptive_choice_controller", None)
        if controller is None:
            return super(AdaptiveComboBox, self).showPopup()
        controller._prepare_popup_show()
        super(AdaptiveComboBox, self).showPopup()
        controller._adopt_popup()
        controller._apply_popup_clamp_after_show()


class ChoiceControlController(QObject):
    """Keep one choice popup screen-bounded and current with live Qt metrics."""

    _METRIC_EVENTS = {
        QEvent.ApplicationFontChange,
        QEvent.FontChange,
        QEvent.PaletteChange,
        QEvent.StyleChange,
    }
    if hasattr(QEvent, "ScreenChangeInternal"):
        _METRIC_EVENTS.add(QEvent.ScreenChangeInternal)

    def __init__(self, combo, visible_characters):
        super(ChoiceControlController, self).__init__(combo)
        self.combo = combo
        self.visible_characters = visible_characters
        self._window_handle = None
        self._screen = None
        self._measurement_dirty = False
        self._measurement_pending = False
        self._clamp_pending = False
        self.measurement_applied_count = 0
        self.tooltip_scan_applied_count = 0
        self.popup_clamp_applied_count = 0
        if not isinstance(combo.view(), ChoiceListView):
            combo.setView(ChoiceListView(combo))
        combo.view().choice_controller = self
        self._popup = combo.view().window()
        combo.installEventFilter(self)
        model = combo.model()
        model.rowsInserted.connect(self._invalidate_measurements)
        model.rowsRemoved.connect(self._invalidate_measurements)
        model.modelReset.connect(self._invalidate_measurements)
        combo.currentTextChanged.connect(self._selected_text_changed)
        self._refresh_measurements()

    def reconfigure(self, visible_characters):
        self.visible_characters = visible_characters
        self._invalidate_measurements()

    def eventFilter(self, watched, event):
        event_type = event.type()
        if watched is self.combo and event_type in self._METRIC_EVENTS:
            self._invalidate_measurements()
        return super(ChoiceControlController, self).eventFilter(watched, event)

    def refresh(self, *_args):
        self._invalidate_measurements()

    def _invalidate_measurements(self, *_args):
        self._measurement_dirty = True
        if not self.combo.isVisible() or self._measurement_pending:
            return
        self._measurement_pending = True
        QTimer.singleShot(0, self._apply_pending_measurements)

    def _apply_pending_measurements(self):
        self._measurement_pending = False
        if not self._measurement_dirty or not self.combo.isVisible():
            return
        self._refresh_measurements()
        if self._popup.isVisible():
            self._schedule_popup_clamp()

    def _prepare_popup_show(self):
        self._adopt_popup()
        self._refresh_measurements()

    def _refresh_measurements(self):
        self._measurement_dirty = False
        self.measurement_applied_count += 1
        combo = self.combo
        combo.setMaximumWidth(QWIDGETSIZE_MAX)
        combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(max(1, int(self.visible_characters)))
        combo.setSizePolicy(QSizePolicy.Expanding, combo.sizePolicy().verticalPolicy())

        view = combo.view()
        view.setTextElideMode(Qt.ElideNone)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        view.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._install_complete_value_tooltips()
        self._selected_text_changed(combo.currentText())

        available = available_geometry_for_choice_control(combo)
        requested_width = self._requested_popup_width()
        if available.isValid():
            frame_extent = 2 * self._popup.style().pixelMetric(
                QStyle.PM_DefaultFrameWidth, None, self._popup
            )
            client_width = max(1, available.width() - frame_extent)
            client_height = max(1, available.height() - frame_extent)
            requested_width = min(requested_width, client_width)
            view.setMaximumWidth(client_width)
            view.setMaximumHeight(client_height)
            self._popup.setMaximumWidth(client_width)
            self._popup.setMaximumHeight(client_height)
        else:
            view.setMaximumWidth(QWIDGETSIZE_MAX)
            view.setMaximumHeight(QWIDGETSIZE_MAX)
            self._popup.setMaximumWidth(QWIDGETSIZE_MAX)
            self._popup.setMaximumHeight(QWIDGETSIZE_MAX)
        view.setMinimumWidth(max(1, requested_width))
        self._connect_screen()

    def _requested_popup_width(self):
        combo = self.combo
        metrics = combo.fontMetrics()
        text_width = max(
            (
                metrics.horizontalAdvance(str(combo.itemText(index)))
                for index in range(combo.count())
            ),
            default=0,
        )
        chrome = (
            combo.style().pixelMetric(QStyle.PM_ScrollBarExtent, None, combo)
            + combo.style().pixelMetric(QStyle.PM_LayoutLeftMargin, None, combo)
            + combo.style().pixelMetric(QStyle.PM_LayoutRightMargin, None, combo)
        )
        return max(combo.width(), text_width + chrome)

    def _install_complete_value_tooltips(self):
        self.tooltip_scan_applied_count += 1
        model = self.combo.model()
        root = self.combo.rootModelIndex()
        column = self.combo.modelColumn()
        for row in range(self.combo.count()):
            index = model.index(row, column, root)
            model.setData(index, str(self.combo.itemText(row)), Qt.ToolTipRole)

    def _selected_text_changed(self, text):
        self.combo.setToolTip(str(text))

    def _connect_screen(self):
        window = self.combo.window()
        handle = window.windowHandle() if window is not None else None
        if handle is not self._window_handle:
            if self._window_handle is not None:
                try:
                    self._window_handle.screenChanged.disconnect(self._screen_changed)
                except (TypeError, RuntimeError):
                    pass
            self._window_handle = handle
            if handle is not None:
                handle.screenChanged.connect(self._screen_changed)
        screen = handle.screen() if handle is not None else None
        if screen is self._screen:
            return
        if self._screen is not None:
            for name in ("availableGeometryChanged", "logicalDotsPerInchChanged"):
                try:
                    getattr(self._screen, name).disconnect(
                        self._screen_metrics_changed
                    )
                except (AttributeError, TypeError, RuntimeError):
                    pass
        self._screen = screen
        if screen is not None:
            for name in ("availableGeometryChanged", "logicalDotsPerInchChanged"):
                signal = getattr(screen, name, None)
                if signal is not None:
                    signal.connect(self._screen_metrics_changed)

    def _screen_changed(self, _screen):
        self._connect_screen()
        self._invalidate_measurements()

    def _screen_metrics_changed(self, *_args):
        self._invalidate_measurements()

    def _adopt_popup(self):
        popup = self.combo.view().window()
        if popup is self._popup:
            return
        self._popup = popup

    def _schedule_popup_clamp(self):
        if self._clamp_pending:
            return
        self._clamp_pending = True
        QTimer.singleShot(0, self._apply_pending_popup_clamp)

    def _apply_popup_clamp_after_show(self):
        if self._clamp_pending:
            return
        self._clamp_pending = True
        self._bound_visible_popup(require_visible=False)
        QTimer.singleShot(0, self._release_popup_clamp_guard)

    def _release_popup_clamp_guard(self):
        self._clamp_pending = False

    def _apply_pending_popup_clamp(self):
        try:
            self._bound_visible_popup()
        finally:
            self._clamp_pending = False

    def _bound_visible_popup(self, require_visible=True):
        popup = self._popup
        if require_visible and not popup.isVisible():
            return
        available = available_geometry_for_choice_control(self.combo)
        if not available.isValid():
            return
        self.popup_clamp_applied_count += 1
        frame = popup.frameGeometry()
        width = min(frame.width(), available.width())
        height = min(frame.height(), available.height())
        frame_extra_width = max(0, frame.width() - popup.width())
        frame_extra_height = max(0, frame.height() - popup.height())
        view = self.combo.view()
        client_width = max(1, width - frame_extra_width)
        client_height = max(1, height - frame_extra_height)
        view.setMinimumWidth(min(view.minimumWidth(), client_width))
        popup.setMinimumSize(0, 0)
        popup.resize(
            client_width,
            client_height,
        )
        frame = popup.frameGeometry()
        left = max(
            available.left(),
            min(frame.left(), available.right() - frame.width() + 1),
        )
        top = max(
            available.top(),
            min(frame.top(), available.bottom() - frame.height() + 1),
        )
        popup.move(popup.pos() + QPoint(left, top) - frame.topLeft())
        final_frame = popup.frameGeometry()
        left_excess = max(0, available.left() - final_frame.left())
        right_excess = max(0, final_frame.right() - available.right())
        top_excess = max(0, available.top() - final_frame.top())
        bottom_excess = max(0, final_frame.bottom() - available.bottom())
        if left_excess or right_excess or top_excess or bottom_excess:
            corrected_width = max(1, popup.width() - left_excess - right_excess)
            corrected_height = max(1, popup.height() - top_excess - bottom_excess)
            view.setMinimumWidth(min(view.minimumWidth(), corrected_width))
            popup.resize(corrected_width, corrected_height)
            realized = popup.frameGeometry()
            corrected_left = max(
                available.left(),
                min(
                    realized.left(),
                    available.right() - realized.width() + 1,
                ),
            )
            corrected_top = max(
                available.top(),
                min(
                    realized.top(),
                    available.bottom() - realized.height() + 1,
                ),
            )
            popup.move(
                popup.pos()
                + QPoint(corrected_left, corrected_top)
                - realized.topLeft()
            )
        overflow = max(0, view.sizeHintForColumn(0) - view.viewport().width())
        view.horizontalScrollBar().setRange(0, overflow)
        view.horizontalScrollBar().setPageStep(max(1, view.viewport().width()))


def configure_choice_control(combo, visible_characters=VALUE_SELECTOR_VISIBLE_CHARACTERS):
    """Apply and return one reusable screen-bounded choice-control controller."""
    if not isinstance(combo, AdaptiveComboBox):
        raise TypeError(
            "Screen-bounded choice controls must use AdaptiveComboBox so native "
            "popup opening cannot bypass the measurement and clamp seam."
        )
    controller = getattr(combo, "_adaptive_choice_controller", None)
    if controller is None:
        controller = ChoiceControlController(combo, visible_characters)
        combo._adaptive_choice_controller = controller
        combo.setProperty("RCMS_choice_control_configured", True)
    else:
        controller.reconfigure(visible_characters)
    return controller


def refresh_choice_popup_width(combo):
    """Refresh a configured choice control after local content reflow."""
    controller = getattr(combo, "_adaptive_choice_controller", None)
    if controller is not None:
        controller.refresh()


def configure_numeric_value_control(control):
    """Use the editor's value range as its Semantic Size Invariant."""
    control.setMaximumWidth(QWIDGETSIZE_MAX)
    control.setSizePolicy(QSizePolicy.Minimum, control.sizePolicy().verticalPolicy())


def configure_text_value_control(control):
    """Allow editable Required Content to consume the available row width."""
    control.setMaximumWidth(QWIDGETSIZE_MAX)
    control.setSizePolicy(QSizePolicy.Expanding, control.sizePolicy().verticalPolicy())
