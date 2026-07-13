# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Adaptive sizing and placement policy for explicitly migrated windows."""

from dataclasses import dataclass
from enum import Enum

from PyQt5.QtCore import (
    QEvent,
    QMargins,
    QObject,
    QPoint,
    QRect,
    QSize,
    QTimer,
    Qt,
    pyqtSignal,
)
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import QApplication, QLayout, QSizePolicy, QWIDGETSIZE_MAX


class WindowArchetype(str, Enum):
    """User-facing window roles with distinct geometry ownership."""

    WORKSPACE = "workspace"
    WORKFLOW = "workflow"
    TRANSACTIONAL = "transactional"
    TRANSIENT = "transient"


class WindowRole(str, Enum):
    """Explicit roles that refine first-use behavior within an archetype."""

    MAIN = "main"
    RESULTS = "results"
    EDIT_DATASET = "edit_dataset"
    NETWORK_VIEW = "network_view"
    WORKFLOW = "workflow"
    TRANSACTIONAL = "transactional"
    CONFIDENCE_LEVEL = "confidence_level"
    TRANSIENT = "transient"


class FirstUseBehavior(str, Enum):
    MAXIMIZED = "maximized"
    SCREEN_FRACTION = "screen_fraction"
    CONTENT_PREFERRED = "content_preferred"


@dataclass(frozen=True)
class WindowPolicy:
    archetype: WindowArchetype
    first_use_behavior: FirstUseBehavior
    maximum_screen_fraction: float
    application_owns_geometry: bool


WINDOW_POLICIES = {
    WindowRole.MAIN: WindowPolicy(
        WindowArchetype.WORKSPACE, FirstUseBehavior.MAXIMIZED, 1.00, False
    ),
    WindowRole.RESULTS: WindowPolicy(
        WindowArchetype.WORKSPACE, FirstUseBehavior.MAXIMIZED, 1.00, False
    ),
    WindowRole.EDIT_DATASET: WindowPolicy(
        WindowArchetype.WORKSPACE, FirstUseBehavior.SCREEN_FRACTION, 0.80, False
    ),
    WindowRole.NETWORK_VIEW: WindowPolicy(
        WindowArchetype.WORKSPACE, FirstUseBehavior.SCREEN_FRACTION, 0.80, False
    ),
    WindowRole.WORKFLOW: WindowPolicy(
        WindowArchetype.WORKFLOW, FirstUseBehavior.CONTENT_PREFERRED, 0.90, False
    ),
    WindowRole.TRANSACTIONAL: WindowPolicy(
        WindowArchetype.TRANSACTIONAL,
        FirstUseBehavior.CONTENT_PREFERRED,
        0.90,
        True,
    ),
    WindowRole.CONFIDENCE_LEVEL: WindowPolicy(
        WindowArchetype.TRANSACTIONAL,
        FirstUseBehavior.CONTENT_PREFERRED,
        0.90,
        True,
    ),
    WindowRole.TRANSIENT: WindowPolicy(
        WindowArchetype.TRANSIENT, FirstUseBehavior.CONTENT_PREFERRED, 1.00, True
    ),
}


def centered_bounded_geometry(
    preferred_size, available_geometry, center, maximum_fraction=0.90
):
    """Return centered outer-frame geometry bounded to a logical screen area."""
    available = QRect(available_geometry)
    if not available.isValid():
        return QRect(QPoint(0, 0), QSize())

    fraction = max(0.0, min(float(maximum_fraction), 1.0))
    maximum_size = QSize(
        max(1, int(available.width() * fraction)),
        max(1, int(available.height() * fraction)),
    )
    preferred = QSize(preferred_size)
    bounded_size = QSize(
        max(1, min(preferred.width(), maximum_size.width())),
        max(1, min(preferred.height(), maximum_size.height())),
    )
    centered = QRect(QPoint(0, 0), bounded_size)
    centered.moveCenter(QPoint(center))
    return clamp_frame_geometry(centered, available)


def clamp_frame_geometry(frame_geometry, available_geometry):
    """Clamp an outer frame minimally, preserving reachable size and position."""
    frame = QRect(frame_geometry)
    available = QRect(available_geometry)
    if not available.isValid() or not frame.isValid():
        return frame

    width = min(frame.width(), available.width())
    height = min(frame.height(), available.height())
    maximum_left = available.right() - width + 1
    maximum_top = available.bottom() - height + 1
    left = _clamp(frame.left(), available.left(), maximum_left)
    top = _clamp(frame.top(), available.top(), maximum_top)
    return QRect(left, top, width, height)


def client_size_for_frame_size(frame_size, frame_margins):
    """Convert a bounded outer-frame size to the corresponding client size."""
    size = QSize(frame_size)
    margins = QMargins(frame_margins)
    return QSize(
        max(1, size.width() - margins.left() - margins.right()),
        max(1, size.height() - margins.top() - margins.bottom()),
    )


def available_geometry_for_window(window):
    """Return the available Logical Layout Space on a window's owning screen."""
    screen = owning_screen(window)
    return QRect(screen.availableGeometry()) if screen is not None else QRect()


def first_use_screen(window, archetype, active_window_provider=None):
    """Resolve first-use ownership, including the active Workspace screen."""
    parent = window.parentWidget()
    if parent is not None:
        return owning_screen(window)

    if WindowArchetype(archetype) == WindowArchetype.WORKSPACE:
        provider = active_window_provider or QApplication.activeWindow
        active_window = provider()
        if active_window is not None and active_window is not window:
            handle = active_window.windowHandle()
            if handle is not None and handle.screen() is not None:
                return handle.screen()
    return owning_screen(window)


def place_window_on_screen(window, screen):
    """Associate an unshown top-level window with its first-use screen."""
    if screen is None:
        return
    if window.windowHandle() is None:
        window.winId()
    handle = window.windowHandle()
    if handle is not None and handle.screen() is not screen:
        handle.setScreen(screen)
    window.move(screen.availableGeometry().topLeft())


def owning_screen(window):
    """Resolve the owning screen, preferring the parent before first display."""
    parent = window.parentWidget()
    if parent is not None:
        parent_window = parent.window()
        parent_handle = parent_window.windowHandle()
        if parent_handle is not None and parent_handle.screen() is not None:
            return parent_handle.screen()
        parent_geometry = parent_window.frameGeometry()
        screen = QGuiApplication.screenAt(parent_geometry.center())
        if screen is not None:
            return screen

    handle = window.windowHandle()
    if handle is not None and handle.screen() is not None:
        return handle.screen()
    return QGuiApplication.primaryScreen()


def register_adaptive_window(
    window,
    role,
    available_geometry_provider=None,
    first_use_screen_provider=None,
    screen_placer=None,
):
    """Register one migrated window with the replacement adaptive policy."""
    controller = AdaptiveWindowController(
        window,
        role,
        available_geometry_provider=available_geometry_provider,
        first_use_screen_provider=first_use_screen_provider,
        screen_placer=screen_placer,
    )
    window._adaptive_window_controller = controller
    controller.apply_first_use_geometry()
    return controller


class AdaptiveWindowController(QObject):
    """Own local sizing and reachability work for one registered window."""

    refitApplied = pyqtSignal()
    runtimeClampApplied = pyqtSignal()

    def __init__(
        self,
        window,
        role,
        available_geometry_provider=None,
        first_use_screen_provider=None,
        screen_placer=None,
    ):
        super(AdaptiveWindowController, self).__init__(window)
        self.window = window
        self.role = WindowRole(role)
        self.policy = WINDOW_POLICIES[self.role]
        self._available_geometry_provider = (
            available_geometry_provider or available_geometry_for_window
        )
        self._first_use_screen_provider = first_use_screen_provider or (
            lambda target, archetype: first_use_screen(target, archetype)
        )
        self._screen_placer = screen_placer or place_window_on_screen
        self._content_refit_pending = False
        self._runtime_clamp_pending = False
        self._first_show_pending = True
        self._normal_frame_geometry = QRect()
        self._window_handle = None
        self._runtime_screen = None

        window.setProperty("RCMS_window_archetype", self.policy.archetype.value)
        window.setProperty("RCMS_window_role", self.role.value)
        window.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
        window.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        if window.layout() is not None:
            constraint = (
                QLayout.SetMinimumSize
                if self.policy.application_owns_geometry
                else QLayout.SetNoConstraint
            )
            window.layout().setSizeConstraint(constraint)
        window.installEventFilter(self)

    def eventFilter(self, watched, event):
        if (
            watched is self.window
            and event.type() in (QEvent.Move, QEvent.Resize)
            and not self.window.isMaximized()
            and not self.window.isFullScreen()
        ):
            self._normal_frame_geometry = QRect(self.window.frameGeometry())
        if watched is self.window and event.type() == QEvent.Show:
            if self._first_show_pending:
                self._first_show_pending = False
                self.apply_first_use_geometry()
            self._connect_window_handle()
            self.request_runtime_clamp()
        return super(AdaptiveWindowController, self).eventFilter(watched, event)

    def apply_first_use_geometry(self):
        """Apply the registered role's sizing behavior before user ownership."""
        screen = self._first_use_screen_provider(self.window, self.policy.archetype)
        if (
            self.window.parentWidget() is None
            and self.policy.archetype == WindowArchetype.WORKSPACE
        ):
            self._screen_placer(self.window, screen)
        if self.policy.first_use_behavior == FirstUseBehavior.MAXIMIZED:
            self.window.setWindowState(self.window.windowState() | Qt.WindowMaximized)
            self.refitApplied.emit()
            return

        available = self._available_geometry()
        if not available.isValid():
            return
        if self.policy.first_use_behavior == FirstUseBehavior.SCREEN_FRACTION:
            outer_size = QSize(
                max(1, int(available.width() * self.policy.maximum_screen_fraction)),
                max(1, int(available.height() * self.policy.maximum_screen_fraction)),
            )
        else:
            outer_size = self._preferred_outer_frame_size()
        target = centered_bounded_geometry(
            outer_size,
            available,
            self._first_use_center(available),
            maximum_fraction=self.policy.maximum_screen_fraction,
        )
        self._set_outer_frame_geometry(target)
        self.refitApplied.emit()

    def request_content_refit(self):
        """Coalesce content-driven first-use policy work to one event-loop turn."""
        if self._content_refit_pending:
            return
        self._content_refit_pending = True
        QTimer.singleShot(0, self._run_content_refit)

    def request_runtime_clamp(self):
        """Coalesce reachability checks without restoring first-use placement."""
        if self._runtime_clamp_pending:
            return
        self._runtime_clamp_pending = True
        QTimer.singleShot(0, self._run_runtime_clamp)

    def restore_frame_geometry(self, frame_geometry):
        """Restore a validated outer-frame rectangle for a workspace window."""
        target = QRect(frame_geometry)
        self._first_show_pending = False
        self._set_outer_frame_geometry(target)
        self._normal_frame_geometry = target

    def consume_first_use(self):
        """Suppress first-use sizing when a valid persisted state will restore."""
        self._first_show_pending = False

    def normal_frame_geometry(self):
        """Return the last user-owned non-maximized outer-frame rectangle."""
        return QRect(self._normal_frame_geometry)

    def handle_screen_assignment_change(self, screen):
        """Adopt a new runtime screen and reconnect its metric signals."""
        self._connect_runtime_screen(screen)
        self.request_runtime_clamp()

    def handle_screen_metrics_change(self, *_args):
        """Clamp after available geometry or effective DPI changes."""
        self.request_runtime_clamp()

    def _run_content_refit(self):
        if not self._content_refit_pending:
            return
        self._content_refit_pending = False
        if self._first_show_pending:
            self.apply_first_use_geometry()
        elif self.policy.application_owns_geometry:
            self._apply_visible_content_refit()
        else:
            self._apply_runtime_clamp()

    def _run_runtime_clamp(self):
        if not self._runtime_clamp_pending:
            return
        self._runtime_clamp_pending = False
        self._apply_runtime_clamp()

    def _apply_visible_content_refit(self):
        available = self._available_geometry()
        if not available.isValid():
            return
        preferred = self._preferred_outer_frame_size()
        maximum = QSize(
            max(1, int(available.width() * self.policy.maximum_screen_fraction)),
            max(1, int(available.height() * self.policy.maximum_screen_fraction)),
        )
        bounded = QSize(
            min(preferred.width(), maximum.width()),
            min(preferred.height(), maximum.height()),
        )
        target = QRect(self.window.frameGeometry().topLeft(), bounded)
        target = clamp_frame_geometry(target, available)
        self._set_outer_frame_geometry(target)
        self.refitApplied.emit()

    def _apply_runtime_clamp(self):
        available = self._available_geometry()
        if available.isValid():
            current = self.window.frameGeometry()
            target = clamp_frame_geometry(current, available)
            if target != current:
                self._set_outer_frame_geometry(target)
        self.runtimeClampApplied.emit()

    def _available_geometry(self):
        if self._runtime_screen is not None:
            try:
                return QRect(self._runtime_screen.availableGeometry())
            except RuntimeError:
                self._runtime_screen = None
        try:
            return QRect(self._available_geometry_provider(self.window))
        except RuntimeError:
            return QRect()

    def _preferred_outer_frame_size(self):
        preferred = self.window.sizeHint()
        if not preferred.isValid():
            preferred = self.window.minimumSizeHint()
        if not preferred.isValid() and self.window.size().isValid():
            preferred = self.window.size()
        if not preferred.isValid():
            preferred = QSize(1, 1)
        minimum = self.window.minimumSizeHint()
        if minimum.isValid():
            preferred = preferred.expandedTo(minimum)
        margins = self._frame_margins()
        return QSize(
            preferred.width() + margins.left() + margins.right(),
            preferred.height() + margins.top() + margins.bottom(),
        )

    def _first_use_center(self, available):
        parent = self.window.parentWidget()
        if parent is None:
            return available.center()
        geometry = parent.window().frameGeometry()
        if geometry.isNull():
            geometry = parent.window().geometry()
        return geometry.center()

    def _frame_margins(self):
        frame = self.window.frameGeometry()
        client = self.window.geometry()
        horizontal = max(0, frame.width() - self.window.width())
        vertical = max(0, frame.height() - self.window.height())
        left = _clamp(client.left() - frame.left(), 0, horizontal)
        top = _clamp(client.top() - frame.top(), 0, vertical)
        return QMargins(left, top, horizontal - left, vertical - top)

    def _set_outer_frame_geometry(self, target):
        target = QRect(target)
        self.window.resize(
            client_size_for_frame_size(target.size(), self._frame_margins())
        )
        self.window.move(target.topLeft())
        actual_top_left = self.window.frameGeometry().topLeft()
        if actual_top_left != target.topLeft():
            correction = target.topLeft() - actual_top_left
            self.window.move(self.window.pos() + correction)

    def _connect_window_handle(self):
        handle = self.window.windowHandle()
        if handle is None:
            return
        if handle is not self._window_handle:
            if self._window_handle is not None:
                try:
                    self._window_handle.screenChanged.disconnect(
                        self.handle_screen_assignment_change
                    )
                except (TypeError, RuntimeError):
                    pass
            self._window_handle = handle
            handle.screenChanged.connect(self.handle_screen_assignment_change)
        self._connect_runtime_screen(handle.screen())

    def _connect_runtime_screen(self, screen):
        if screen is self._runtime_screen:
            return
        if self._runtime_screen is not None:
            for signal_name in (
                "availableGeometryChanged",
                "geometryChanged",
                "logicalDotsPerInchChanged",
            ):
                try:
                    getattr(self._runtime_screen, signal_name).disconnect(
                        self.handle_screen_metrics_change
                    )
                except (AttributeError, TypeError, RuntimeError):
                    pass
        self._runtime_screen = screen
        if screen is None:
            return
        for signal_name in (
            "availableGeometryChanged",
            "geometryChanged",
            "logicalDotsPerInchChanged",
        ):
            signal = getattr(screen, signal_name, None)
            if signal is not None:
                signal.connect(self.handle_screen_metrics_change)


def _clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))
