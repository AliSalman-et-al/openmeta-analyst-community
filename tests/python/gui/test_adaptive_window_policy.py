import os
from pathlib import Path
import subprocess
import sys

from PyQt6 import QtCore, QtGui, QtWidgets

from test_types import required


ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RCMS_QT6_BUILD_ROOT", str(ROOT / "build" / "qt6-verification"))
from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()


class FakeScreen(QtCore.QObject):
    availableGeometryChanged = QtCore.pyqtSignal(QtCore.QRect)
    geometryChanged = QtCore.pyqtSignal(QtCore.QRect)
    logicalDotsPerInchChanged = QtCore.pyqtSignal(float)

    def __init__(self, available):
        super(FakeScreen, self).__init__()
        self._available = QtCore.QRect(available)

    def availableGeometry(self):
        return QtCore.QRect(self._available)

    def change_available_geometry(self, available):
        self._available = QtCore.QRect(available)
        self.availableGeometryChanged.emit(QtCore.QRect(available))


class FakeWindowHandle(object):
    def __init__(self, screen):
        self._screen = screen

    def screen(self):
        return self._screen


class FakeActiveWindow(object):
    def __init__(self, screen):
        self._handle = FakeWindowHandle(screen)

    def windowHandle(self):
        return self._handle


def _dialog_with_content(text="Content"):
    dialog = QtWidgets.QDialog()
    dialog.setLayout(QtWidgets.QVBoxLayout())
    required(dialog.layout(), "dialog layout").addWidget(QtWidgets.QLabel(text))
    return dialog


def test_application_bootstrap_enables_qt_high_dpi_before_construction():
    script = """
from PyQt6 import QtWidgets
from rc_metastudio import app_error_handler

assert QtWidgets.QApplication.instance() is None
app = app_error_handler.get_or_create_application([])
assert app is QtWidgets.QApplication.instance()
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(ROOT / "src"),
            str(ROOT / "build" / "qt6-verification" / "generated"),
        ]
    )
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["RCMS_QT6_BUILD_ROOT"] = str(ROOT / "build" / "qt6-verification")

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_geometry_helpers_bound_the_outer_frame_in_logical_space():
    from rc_metastudio import adaptive_window

    available = QtCore.QRect(100, 50, 800, 600)
    geometry = adaptive_window.centered_bounded_geometry(
        QtCore.QSize(1200, 900), available, QtCore.QPoint(860, 620)
    )
    client_size = adaptive_window.client_size_for_frame_size(
        geometry.size(), QtCore.QMargins(8, 30, 8, 8)
    )

    assert geometry.size() == QtCore.QSize(720, 540)
    assert client_size == QtCore.QSize(704, 502)
    assert available.contains(geometry)
    assert geometry.right() == available.right()
    assert geometry.bottom() == available.bottom()


def test_workspace_roles_apply_maximized_or_eighty_percent_first_use(qapp):
    from rc_metastudio import adaptive_window

    available = QtCore.QRect(100, 50, 1000, 800)

    def provider(_window):
        return QtCore.QRect(available)

    main = QtWidgets.QMainWindow()
    results = QtWidgets.QMainWindow()
    edit_dataset = _dialog_with_content()
    network = QtWidgets.QMainWindow()

    adaptive_window.register_adaptive_window(
        main, adaptive_window.WindowRole.MAIN, provider
    )
    adaptive_window.register_adaptive_window(
        results, adaptive_window.WindowRole.RESULTS, provider
    )
    adaptive_window.register_adaptive_window(
        edit_dataset, adaptive_window.WindowRole.EDIT_DATASET, provider
    )
    adaptive_window.register_adaptive_window(
        network, adaptive_window.WindowRole.NETWORK_VIEW, provider
    )

    assert main.windowState() & QtCore.Qt.WindowState.WindowMaximized
    assert results.windowState() & QtCore.Qt.WindowState.WindowMaximized
    assert edit_dataset.frameGeometry().size() == QtCore.QSize(800, 640)
    assert network.frameGeometry().size() == QtCore.QSize(800, 640)
    assert (
        adaptive_window.adaptive_window_state(edit_dataset).policy.archetype
        is adaptive_window.WindowArchetype.WORKSPACE
    )
    assert (
        adaptive_window.adaptive_window_state(edit_dataset).role
        is adaptive_window.WindowRole.EDIT_DATASET
    )


def test_unparented_workspace_uses_active_screen_before_maximizing(qapp):
    from rc_metastudio import adaptive_window

    active_screen = FakeScreen(QtCore.QRect(1600, 100, 1200, 900))
    main = QtWidgets.QMainWindow()
    selected = adaptive_window.first_use_screen(
        main,
        adaptive_window.WindowArchetype.WORKSPACE,
        active_window_provider=lambda: FakeActiveWindow(active_screen),
    )
    placements = []

    adaptive_window.register_adaptive_window(
        main,
        adaptive_window.WindowRole.MAIN,
        available_geometry_provider=lambda _window: active_screen.availableGeometry(),
        first_use_screen_provider=lambda _window, _archetype: active_screen,
        screen_placer=lambda window, screen: placements.append(
            (screen, bool(window.windowState() & QtCore.Qt.WindowState.WindowMaximized))
        ),
    )

    assert selected is active_screen
    assert placements == [(active_screen, False)]
    assert main.windowState() & QtCore.Qt.WindowState.WindowMaximized


def test_maximized_workspace_does_not_reapply_window_state_during_show(qapp):
    from rc_metastudio import adaptive_window

    window = QtWidgets.QMainWindow()
    controller = adaptive_window.register_adaptive_window(
        window,
        adaptive_window.WindowRole.MAIN,
        available_geometry_provider=lambda _window: QtCore.QRect(0, 0, 1200, 800),
    )
    refits_after_registration = []
    controller.refitApplied.connect(lambda: refits_after_registration.append(True))

    try:
        assert not window.size().isEmpty()
        window.showMaximized()
        qapp.processEvents()

        assert refits_after_registration == []
        assert window.isVisible()
        assert window.windowHandle() is not None
        assert required(window.windowHandle(), "window handle").isVisible()
    finally:
        window.close()
        qapp.processEvents()


def test_content_refit_requests_are_local_and_coalesced(qapp):
    from rc_metastudio import adaptive_window

    dialog = _dialog_with_content()
    controller = adaptive_window.register_adaptive_window(
        dialog,
        adaptive_window.WindowRole.TRANSACTIONAL,
        available_geometry_provider=lambda _window: QtCore.QRect(0, 0, 800, 600),
    )
    refits = []
    controller.refitApplied.connect(lambda: refits.append(dialog.frameGeometry()))

    controller.request_content_refit()
    controller.request_content_refit()
    controller.request_content_refit()
    qapp.processEvents()

    assert len(refits) == 1


def test_visible_transactional_content_refit_preserves_placement(qapp):
    from rc_metastudio import adaptive_window

    dialog = _dialog_with_content("Short")
    controller = adaptive_window.register_adaptive_window(
        dialog,
        adaptive_window.WindowRole.TRANSACTIONAL,
    )
    dialog.show()
    qapp.processEvents()
    available = dialog.windowHandle().screen().availableGeometry()
    dialog.move(available.left() + 40, available.top() + 100)
    qapp.processEvents()
    before = QtCore.QRect(dialog.frameGeometry())
    dialog.layout().addWidget(QtWidgets.QPushButton("A Newly Revealed Option"))

    controller.request_content_refit()
    qapp.processEvents()

    after = dialog.frameGeometry()
    assert after.topLeft() == before.topLeft()
    assert after.width() > before.width()
    assert available.contains(after)


def test_visible_user_owned_windows_do_not_reclaim_geometry(qapp):
    from rc_metastudio import adaptive_window

    available = QtCore.QRect(0, 0, 1400, 1000)
    for role in (
        adaptive_window.WindowRole.EDIT_DATASET,
        adaptive_window.WindowRole.WORKFLOW,
    ):
        window = _dialog_with_content("Short")
        controller = adaptive_window.register_adaptive_window(
            window,
            role,
            available_geometry_provider=lambda _window: QtCore.QRect(available),
        )
        window.show()
        qapp.processEvents()
        window.resize(430, 310)
        window.move(260, 220)
        qapp.processEvents()
        before = QtCore.QRect(window.frameGeometry())
        window.findChild(QtWidgets.QLabel).setText("Longer dynamic content " * 20)

        controller.request_content_refit()
        qapp.processEvents()

        assert window.frameGeometry() == before
        window.close()


def test_runtime_clamp_preserves_user_geometry_without_recentering(qapp):
    from rc_metastudio import adaptive_window

    available = QtCore.QRect(0, 0, 800, 600)
    dialog = _dialog_with_content()
    controller = adaptive_window.register_adaptive_window(
        dialog,
        adaptive_window.WindowRole.TRANSACTIONAL,
        available_geometry_provider=lambda _window: QtCore.QRect(available),
    )
    dialog.show()
    qapp.processEvents()
    dialog.resize(300, 150)
    dialog.move(420, 300)
    qapp.processEvents()
    reachable_geometry = QtCore.QRect(dialog.frameGeometry())
    clamps = []
    controller.runtimeClampApplied.connect(lambda: clamps.append(True))

    controller.request_runtime_clamp()
    qapp.processEvents()
    assert dialog.frameGeometry() == reachable_geometry

    dialog.move(700, 520)
    qapp.processEvents()
    outer_size = QtCore.QSize(dialog.frameGeometry().size())
    controller.request_runtime_clamp()
    controller.request_runtime_clamp()
    qapp.processEvents()

    assert len(clamps) == 2
    assert dialog.frameGeometry().size() == outer_size
    assert available.contains(dialog.frameGeometry())
    assert dialog.frameGeometry().center() != available.center()


def test_screen_metric_changes_clamp_and_reconnect_to_new_screen(qapp):
    from rc_metastudio import adaptive_window

    initial = QtCore.QRect(0, 0, 1200, 900)
    first_screen = FakeScreen(initial)
    second_screen = FakeScreen(QtCore.QRect(1200, 0, 800, 600))
    dialog = _dialog_with_content()
    controller = adaptive_window.register_adaptive_window(
        dialog,
        adaptive_window.WindowRole.TRANSACTIONAL,
        available_geometry_provider=lambda _window: QtCore.QRect(initial),
    )
    dialog.show()
    qapp.processEvents()
    controller.handle_screen_assignment_change(first_screen)
    qapp.processEvents()
    dialog.resize(320, 180)
    dialog.move(850, 650)
    clamps = []
    controller.runtimeClampApplied.connect(lambda: clamps.append(True))

    first_screen.logicalDotsPerInchChanged.emit(144.0)
    qapp.processEvents()
    assert initial.contains(dialog.frameGeometry())
    assert len(clamps) == 1

    controller.handle_screen_assignment_change(second_screen)
    qapp.processEvents()
    assert second_screen.availableGeometry().contains(dialog.frameGeometry())
    assignment_clamps = len(clamps)

    first_screen.change_available_geometry(QtCore.QRect(0, 0, 640, 480))
    qapp.processEvents()
    assert len(clamps) == assignment_clamps

    second_screen.change_available_geometry(QtCore.QRect(1200, 0, 640, 480))
    qapp.processEvents()
    assert len(clamps) == assignment_clamps + 1
    assert second_screen.availableGeometry().contains(dialog.frameGeometry())


def test_confidence_level_is_a_compact_transactional_dialog(qapp):
    from rc_metastudio import adaptive_window
    from rc_metastudio import confidence_level_dialog

    parent = QtWidgets.QWidget()
    parent.setGeometry(120, 80, 700, 480)
    parent.show()
    dialog = confidence_level_dialog.ConfidenceLevelDialog(95.0, parent)
    dialog.show()
    qapp.processEvents()

    try:
        handle = required(parent.windowHandle(), "parent window handle")
        available = required(handle.screen(), "parent screen").availableGeometry()
        assert (
            adaptive_window.adaptive_window_state(dialog).policy.archetype
            is adaptive_window.WindowArchetype.TRANSACTIONAL
        )
        assert (
            adaptive_window.adaptive_window_state(dialog).role
            is adaptive_window.WindowRole.CONFIDENCE_LEVEL
        )
        assert (
            required(dialog.layout(), "dialog layout").sizeConstraint()
            == QtWidgets.QLayout.SizeConstraint.SetMinimumSize
        )
        assert not dialog.findChildren(QtWidgets.QScrollArea)
        assert available.contains(dialog.frameGeometry())
        assert dialog.confidence_level_spinbox.value() == 95.0
    finally:
        dialog.close()
        parent.close()


def test_confidence_level_handles_representative_long_text_and_enlarged_font(qapp):
    from rc_metastudio import confidence_level_dialog

    dialog = confidence_level_dialog.ConfidenceLevelDialog(95.0)
    font = QtGui.QFont(qapp.font())
    font.setPointSize(max(18, font.pointSize() + 8))
    dialog.setFont(font)
    dialog.confidence_level_label.setText(
        "Global Confidence Level Used to Calculate Confidence Intervals "
        "for All Outcomes:"
    )
    dialog.request_layout_refit()
    dialog.show()
    qapp.processEvents()

    try:
        handle = required(dialog.windowHandle(), "dialog window handle")
        available = required(handle.screen(), "dialog screen").availableGeometry()
        assert available.contains(dialog.frameGeometry())
        assert dialog.confidence_level_label.wordWrap()
        assert dialog.confidence_level_label.height() >= dialog.fontMetrics().height()
        assert dialog.button_box.isVisible()
        assert dialog.button_box.geometry().bottom() <= dialog.rect().bottom()
    finally:
        dialog.close()
