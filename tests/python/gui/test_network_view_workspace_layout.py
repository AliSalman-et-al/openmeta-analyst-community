import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6 import QtCore, QtGui, QtTest, QtWidgets, sip

pytestmark = [pytest.mark.gui, pytest.mark.qsettings]


ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RCMS_STUB_BACKEND", "1")
os.environ.setdefault("RCMS_QT6_BUILD_ROOT", str(ROOT / "build" / "qt6-verification"))
sys.path.insert(0, os.path.abspath("src/rc_metastudio"))
from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()


LONG_OUTCOME = "Cardiovascular mortality after extended follow-up"
LONG_FOLLOW_UP = "Twenty-four months after randomization"


class _NetworkModel:
    def __init__(self):
        self.current_outcome = LONG_OUTCOME
        self.dataset = SimpleNamespace(
            get_outcome_names=lambda: [LONG_OUTCOME, "Readmission"],
            get_follow_up_names=lambda: [LONG_FOLLOW_UP, "first"],
        )

    def get_current_follow_up_name(self):
        return LONG_FOLLOW_UP

    def get_outcome_type(self, _outcome, get_str=False):
        return "binary"


class _FakeScreen(QtCore.QObject):
    availableGeometryChanged = QtCore.pyqtSignal(QtCore.QRect)
    geometryChanged = QtCore.pyqtSignal(QtCore.QRect)
    logicalDotsPerInchChanged = QtCore.pyqtSignal(float)

    def __init__(self, available):
        super().__init__()
        self._available = QtCore.QRect(available)

    def availableGeometry(self):
        return QtCore.QRect(self._available)


def _clear_settings():
    import meta_globals

    QtCore.QCoreApplication.setOrganizationName(meta_globals.ORGANIZATION_NAME)
    QtCore.QCoreApplication.setApplicationName(meta_globals.APPLICATION_NAME)
    store = QtCore.QSettings()
    store.clear()
    store.sync()


def _network_dialog(qapp, tmp_path, monkeypatch, parent=None):
    import network_view

    image_path = tmp_path / "network.png"
    image = QtGui.QImage(640, 320, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor("white"))
    assert image.save(str(image_path))
    monkeypatch.setattr(
        network_view.meta_py_r,
        "ma_dataset_to_simple_network",
        lambda **_kwargs: str(image_path),
    )
    return network_view.ViewDialog(_NetworkModel(), parent=parent)


def _dispose(qapp, *widgets):
    for widget in widgets:
        if widget is None:
            continue
        if sip.isdeleted(widget):
            continue
        widget.close()
        widget.deleteLater()
    qapp.processEvents()


@pytest.mark.parametrize("screen_size", [(800, 600), (1024, 640), (1600, 1000)])
def test_network_view_first_use_tracks_owning_screen(
    qapp, tmp_path, monkeypatch, screen_size
):
    import adaptive_window

    _clear_settings()
    available = QtCore.QRect(0, 0, *screen_size)
    monkeypatch.setattr(
        adaptive_window,
        "available_geometry_for_window",
        lambda _window: QtCore.QRect(available),
    )
    dialog = _network_dialog(qapp, tmp_path, monkeypatch)
    try:
        state = adaptive_window.adaptive_window_state(dialog)
        assert state.policy.archetype is adaptive_window.WindowArchetype.WORKSPACE
        assert state.role is adaptive_window.WindowRole.NETWORK_VIEW
        assert dialog.frameGeometry().width() == pytest.approx(
            available.width() * 0.80, abs=8
        )
        assert dialog.frameGeometry().height() == pytest.approx(
            available.height() * 0.80, abs=8
        )
        assert available.contains(dialog.frameGeometry())
    finally:
        _dispose(qapp, dialog)


def test_network_viewport_owns_surplus_space_and_preserves_image_ratio(
    qapp, tmp_path, monkeypatch
):
    import network_view

    _clear_settings()
    dialog = _network_dialog(qapp, tmp_path, monkeypatch)
    try:
        dialog.resize(620, 420)
        dialog.show()
        qapp.processEvents()
        initial_viewport = dialog.network_viewer.viewport().size()
        initial_controls_height = dialog.frame.height()

        source = QtGui.QPixmap(1200, 600)
        source.fill(QtGui.QColor("navy"))
        source.setDevicePixelRatio(2.0)
        dialog.set_network_pixmap(source)
        qapp.processEvents()
        initial_scale = dialog.network_viewer.transform().m11()
        monkeypatch.setattr(
            network_view.meta_py_r,
            "ma_dataset_to_simple_network",
            lambda **_kwargs: pytest.fail("resize regenerated the graph"),
        )

        dialog.resize(920, 680)
        qapp.processEvents()

        assert dialog.network_viewer.viewport().width() > initial_viewport.width()
        assert dialog.network_viewer.viewport().height() > initial_viewport.height()
        assert dialog.frame.height() == initial_controls_height
        assert dialog.network_viewer.sizePolicy().horizontalPolicy() == (
            QtWidgets.QSizePolicy.Policy.Expanding
        )
        assert dialog.network_viewer.sizePolicy().verticalPolicy() == (
            QtWidgets.QSizePolicy.Policy.Expanding
        )
        item = dialog.network_viewer.scene().items()[0]
        assert item.pixmap().devicePixelRatioF() == pytest.approx(2.0)
        transform = dialog.network_viewer.transform()
        assert transform.m11() == pytest.approx(transform.m22())
        assert transform.m11() > initial_scale
        displayed = item.sceneBoundingRect()
        assert displayed.width() / displayed.height() == pytest.approx(2.0)
        viewport_rect = transform.mapRect(item.boundingRect())
        assert viewport_rect.width() <= dialog.network_viewer.viewport().width()
        assert viewport_rect.height() <= dialog.network_viewer.viewport().height()
    finally:
        _dispose(qapp, dialog)


def test_network_selectors_keep_content_and_refresh_only_the_graph(
    qapp, tmp_path, monkeypatch
):
    _clear_settings()
    dialog = _network_dialog(qapp, tmp_path, monkeypatch)
    try:
        dialog.show()
        qapp.processEvents()
        original_frame = QtCore.QRect(dialog.frameGeometry())

        assert dialog.outcome_cbo_box.currentText() == LONG_OUTCOME
        assert dialog.follow_up_cbo_box.currentText() == LONG_FOLLOW_UP
        assert [
            dialog.outcome_cbo_box.itemText(index)
            for index in range(dialog.outcome_cbo_box.count())
        ] == [LONG_OUTCOME, "Readmission"]

        graph_calls = []
        monkeypatch.setattr(
            dialog,
            "graph_network",
            lambda outcome, follow_up: graph_calls.append((outcome, follow_up)),
        )
        dialog.outcome_cbo_box.setCurrentText("Readmission")
        qapp.processEvents()

        assert graph_calls == [("Readmission", LONG_FOLLOW_UP)]
        assert dialog.scene.items()
        assert len(dialog.scene.items()) == 1
        assert dialog.frameGeometry() == original_frame
        assert dialog.frame.sizePolicy().verticalPolicy() == (
            QtWidgets.QSizePolicy.Policy.Fixed
        )
    finally:
        _dispose(qapp, dialog)


def test_network_selectors_are_usable_with_large_font_on_constrained_screen(
    qapp, tmp_path, monkeypatch
):
    import adaptive_window

    _clear_settings()
    available = QtCore.QRect(0, 0, 800, 600)
    monkeypatch.setattr(
        adaptive_window,
        "available_geometry_for_window",
        lambda _window: QtCore.QRect(available),
    )
    old_font = QtGui.QFont(qapp.font())
    large_font = QtGui.QFont(old_font)
    large_font.setPointSize(max(large_font.pointSize() + 6, 16))
    qapp.setFont(large_font)
    dialog = _network_dialog(qapp, tmp_path, monkeypatch)
    try:
        dialog.show()
        qapp.processEvents()
        assert dialog.frame.width() <= dialog.contentsRect().width()
        assert dialog.frame.height() == dialog.frame.sizeHint().height()
        assert dialog.network_viewer.viewport().height() > 0
        for combo in (dialog.outcome_cbo_box, dialog.follow_up_cbo_box):
            assert combo.width() >= dialog.frame.contentsRect().width() * 0.65
            assert combo.toolTip() == combo.currentText()
            for index in range(combo.count()):
                assert combo.itemData(
                    index, QtCore.Qt.ItemDataRole.ToolTipRole
                ) == combo.itemText(index)
    finally:
        qapp.setFont(old_font)
        _dispose(qapp, dialog)


def test_network_view_restores_independent_placement(qapp, tmp_path, monkeypatch):
    _clear_settings()
    available = QtCore.QRect(qapp.primaryScreen().availableGeometry())
    first = _network_dialog(qapp, tmp_path, monkeypatch)
    first.show()
    qapp.processEvents()
    first.setGeometry(
        available.left() + 40,
        available.top() + 40,
        min(600, available.width() - 100),
        min(440, available.height() - 100),
    )
    qapp.processEvents()
    remembered = QtCore.QRect(first.frameGeometry())
    first.close()
    qapp.processEvents()

    restored = _network_dialog(qapp, tmp_path, monkeypatch)
    restored.show()
    qapp.processEvents()
    try:
        assert restored.frameGeometry() == remembered
    finally:
        _dispose(qapp, restored, first)


@pytest.mark.parametrize("owner_kind", ["parent", "active_workspace"])
def test_network_workspace_policy_uses_injected_owning_screen(qapp, owner_kind):
    import adaptive_window

    available = QtCore.QRect(1000, 100, 1000, 700)
    screen = _FakeScreen(available)
    parent = QtWidgets.QWidget() if owner_kind == "parent" else None
    if parent is not None:
        parent.setGeometry(1120, 180, 500, 400)
    window = QtWidgets.QDialog(parent)
    QtWidgets.QVBoxLayout(window).addWidget(QtWidgets.QLabel("Network", window))
    ownership_calls = []
    placement_calls = []

    def resolve_owning_screen(target, archetype):
        ownership_calls.append((target, archetype))
        return screen

    adaptive_window.register_adaptive_window(
        window,
        adaptive_window.WindowRole.NETWORK_VIEW,
        available_geometry_provider=lambda _window: QtCore.QRect(available),
        first_use_screen_provider=resolve_owning_screen,
        screen_placer=lambda target, target_screen: placement_calls.append(
            (target, target_screen)
        ),
    )
    try:
        assert ownership_calls == [(window, adaptive_window.WindowArchetype.WORKSPACE)]
        assert window.frameGeometry().width() == pytest.approx(800, abs=8)
        assert window.frameGeometry().height() == pytest.approx(560, abs=8)
        if owner_kind == "active_workspace":
            assert placement_calls == [(window, screen)]
        else:
            assert placement_calls == []
    finally:
        _dispose(qapp, window, parent)


def test_network_workspace_screen_transition_preserves_valid_and_clamps_invalid(qapp):
    import adaptive_window

    available = QtCore.QRect(0, 0, 900, 700)
    screen = _FakeScreen(available)
    window = QtWidgets.QDialog()
    QtWidgets.QVBoxLayout(window).addWidget(QtWidgets.QLabel("Network", window))
    controller = adaptive_window.register_adaptive_window(
        window,
        adaptive_window.WindowRole.NETWORK_VIEW,
        available_geometry_provider=lambda _window: QtCore.QRect(available),
        first_use_screen_provider=lambda _window, _archetype: screen,
        screen_placer=lambda _window, _screen: None,
    )
    window.show()
    qapp.processEvents()
    try:
        window.setGeometry(120, 90, 620, 460)
        qapp.processEvents()
        valid_frame = QtCore.QRect(window.frameGeometry())
        controller.handle_screen_assignment_change(screen)
        qapp.processEvents()
        assert window.frameGeometry() == valid_frame

        window.move(available.right() - 20, available.bottom() - 20)
        qapp.processEvents()
        invalid_frame = QtCore.QRect(window.frameGeometry())
        expected = adaptive_window.clamp_frame_geometry(invalid_frame, available)
        controller.handle_screen_assignment_change(screen)
        qapp.processEvents()
        assert window.frameGeometry() == expected
    finally:
        _dispose(qapp, window)


def test_network_viewport_refit_is_local_and_coalesced(qapp, tmp_path, monkeypatch):
    _clear_settings()
    dialog = _network_dialog(qapp, tmp_path, monkeypatch)
    try:
        qapp.processEvents()
        refits = QtTest.QSignalSpy(dialog.viewportRefitApplied)
        dialog.schedule_viewport_refit()
        dialog.schedule_viewport_refit()
        dialog.schedule_viewport_refit()
        assert len(refits) == 0
        qapp.processEvents()
        assert len(refits) == 1
    finally:
        _dispose(qapp, dialog)


def test_repeated_network_view_close_releases_owned_qt_objects(
    qapp, tmp_path, monkeypatch
):
    _clear_settings()
    parent = QtWidgets.QWidget()
    parent.show()
    try:
        for _index in range(3):
            dialog = _network_dialog(qapp, tmp_path, monkeypatch, parent=parent)
            dialog_destroyed = QtTest.QSignalSpy(dialog.destroyed)
            scene = dialog.network_viewer.scene()
            scene_destroyed = QtTest.QSignalSpy(scene.destroyed)
            dialog.show()
            qapp.processEvents()
            assert dialog.testAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
            assert len(scene.items()) == 1

            dialog.close()
            QtWidgets.QApplication.sendPostedEvents(
                None, QtCore.QEvent.Type.DeferredDelete
            )
            qapp.processEvents()

            assert len(dialog_destroyed) == 1
            assert len(scene_destroyed) == 1
            assert parent.findChildren(QtWidgets.QDialog) == []
    finally:
        _dispose(qapp, parent)


def test_network_view_canonical_form_is_managed_and_platform_native():
    path = Path("src/rc_metastudio/forms/network_view_window.ui")
    text = path.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    top_widget = root.find("widget")

    assert top_widget is not None
    assert top_widget.find("layout") is not None
    root_rect = top_widget.find("property[@name='geometry']/rect")
    assert root_rect is not None
    assert root_rect.findtext("width") == "0"
    assert root_rect.findtext("height") == "0"
    assert top_widget.find("property[@name='maximumSize']") is None
    assert top_widget.find("property[@name='font']") is None
    assert top_widget.find(".//layout[@class='QFormLayout']") is not None
    for child in top_widget.iter("widget"):
        if child is not top_widget:
            assert child.find("property[@name='geometry']") is None

    implementation = Path("src/rc_metastudio/network_view.py").read_text(
        encoding="utf-8"
    )
    assert "qt_layout" not in implementation
    assert "PageSize" not in implementation
