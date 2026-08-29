import hashlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from typing import cast

import pytest
from PIL import Image
from PyQt6 import QtCore, QtGui
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("RCMS_QT6_BUILD_ROOT", str(ROOT / "build" / "qt6-verification"))

from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()


def _load_native_calculator_smoke():
    path = ROOT / "scripts" / "native_calculator_smoke.py"
    spec = importlib.util.spec_from_file_location("native_calculator_smoke_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _table_item(table: QTableWidget, row: int, column: int) -> QTableWidgetItem:
    item = table.item(row, column)
    assert item is not None
    return item


def _required(value, message: str = "expected Qt object"):
    assert value is not None, message
    return value


def test_native_calculator_capture_falls_back_when_screen_grab_is_null(tmp_path, qapp):
    smoke = _load_native_calculator_smoke()

    dialog = QDialog()
    dialog.setObjectName("fallbackCaptureDialog")
    dialog.resize(280, 140)
    layout = QVBoxLayout(dialog)
    label = QLabel("RC MetaStudio fallback capture 42", dialog)
    label.setObjectName("recognizableFallbackContent")
    label.setStyleSheet("background: #d31f45; color: #ffffff; font-size: 18px;")
    layout.addWidget(label)
    dialog.show()
    qapp.processEvents()

    class NullScreen:
        def grabWindow(self, _window_id):
            return QtGui.QPixmap()

    class RenderableDialogProxy:
        def __init__(self, widget):
            self.widget = widget
            self.widget_capture_calls = 0
            self.widget_render_calls = 0

        def screen(self):
            return NullScreen()

        def winId(self):
            return self.widget.winId()

        def grab(self):
            self.widget_capture_calls += 1
            return QtGui.QPixmap()

        def width(self):
            return self.widget.width()

        def height(self):
            return self.widget.height()

        def devicePixelRatioF(self):
            return self.widget.devicePixelRatioF()

        def render(self, painter):
            self.widget_render_calls += 1
            self.widget.render(painter)

    try:
        proxy = RenderableDialogProxy(dialog)
        pixmap, method = smoke.capture_visible_calculator(proxy)
        image = tmp_path / "fallback.png"

        assert dialog.isVisible()
        assert label.isVisible()
        assert method == "QWidget.render(QImage) fallback"
        assert proxy.widget_capture_calls == 1
        assert proxy.widget_render_calls == 1
        assert not pixmap.isNull()
        ratio = pixmap.devicePixelRatio()
        assert abs((pixmap.width() / ratio) - dialog.width()) <= 1
        assert abs((pixmap.height() / ratio) - dialog.height()) <= 1
        rendered = pixmap
        sampled_colors = {
            rendered.pixelColor(x, y).rgba()
            for x in range(0, rendered.width(), max(1, rendered.width() // 12))
            for y in range(0, rendered.height(), max(1, rendered.height() // 8))
        }
        assert len(sampled_colors) > 2
        smoke.encode_capture_png(pixmap, image)
        assert image.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        with Image.open(image) as encoded:
            encoded.load()
            assert encoded.format == "PNG"
            assert encoded.mode == "RGBA"
            colors = encoded.getcolors(maxcolors=encoded.width * encoded.height)
            assert colors is not None
            assert len(colors) > 2
    finally:
        dialog.close()
        qapp.processEvents()


def test_native_calculator_png_encoding_never_calls_qt_save(tmp_path):
    smoke = _load_native_calculator_smoke()

    class SaveFailingImage(QtGui.QImage):
        def save(self, *args, **kwargs):
            raise AssertionError("Qt image encoding must not be used")

    source = SaveFailingImage(7, 5, QtGui.QImage.Format.Format_RGBA8888)
    source.fill(QtGui.QColor("#d31f45"))
    source.setPixelColor(0, 0, QtGui.QColor("#2d72d9"))
    image_path = tmp_path / "pillow-encoded.png"

    smoke.encode_capture_png(source, image_path)

    with Image.open(image_path) as encoded:
        encoded.load()
        assert encoded.format == "PNG"
        assert encoded.mode == "RGBA"
        assert encoded.size == (7, 5)
        assert encoded.getpixel((0, 0)) == (45, 114, 217, 255)
        assert encoded.getpixel((6, 4)) == (211, 31, 69, 255)


def test_native_calculator_installs_stub_without_loading_real_rpy2(monkeypatch):
    smoke = _load_native_calculator_smoke()
    from rc_metastudio import r_backend

    def register_backend(backend):
        monkeypatch.setitem(sys.modules, "rc_metastudio.r_bridge", backend)
        return backend

    monkeypatch.setattr(r_backend, "_register_backend", register_backend)
    monkeypatch.delitem(sys.modules, "rpy2.rinterface", raising=False)
    backend = smoke.install_native_stub_backend()
    assert backend._rcms_stub_backend is True
    assert "rpy2.rinterface" not in sys.modules


def test_native_calculator_backend_contract_fails_closed_for_loaded_rpy2(monkeypatch):
    smoke = _load_native_calculator_smoke()
    monkeypatch.setitem(sys.modules, "rpy2.rinterface", object())

    with pytest.raises(RuntimeError, match="rpy2.rinterface"):
        smoke.install_native_stub_backend()


def test_verified_hard_exit_flushes_marker_before_success_exit():
    smoke = _load_native_calculator_smoke()
    events = []

    class RecordingStream:
        def __init__(self, name):
            self.name = name

        def write(self, value):
            events.append((self.name + "-write", value))
            return len(value)

        def flush(self):
            events.append(self.name + "-flush")

    class ExpectedExit(BaseException):
        pass

    def exit_process(code):
        events.append(("exit", code))
        raise ExpectedExit

    with pytest.raises(ExpectedExit):
        smoke.verified_hard_exit(
            0,
            stdout=RecordingStream("stdout"),
            stderr=RecordingStream("stderr"),
            disable_fault_handler=lambda: events.append("disable-faulthandler"),
            exit_process=exit_process,
        )

    assert events == [
        (
            "stdout-write",
            "RCMS_NATIVE_CALCULATOR_PHASE verified-hard-exit\n",
        ),
        "stdout-flush",
        "stderr-flush",
        "disable-faulthandler",
        ("exit", 0),
    ]


def test_verified_process_does_not_mask_failure_or_nonzero_status():
    smoke = _load_native_calculator_smoke()
    terminal_calls = []
    hard_exit_calls = []

    assert (
        smoke.verified_hard_exit(
            7,
            disable_fault_handler=lambda: hard_exit_calls.append("disable"),
            exit_process=lambda status: hard_exit_calls.append(status),
        )
        == 7
    )
    assert hard_exit_calls == []

    def terminal(status):
        terminal_calls.append(status)
        return status

    assert smoke.run_verified_process(run_smoke=lambda: 7, terminal=terminal) == 7
    assert terminal_calls == [7]

    def fail_before_terminal():
        raise RuntimeError("verification failed")

    def unexpected_terminal(status):
        terminal_calls.append(status)
        return status

    with pytest.raises(RuntimeError, match="verification failed"):
        smoke.run_verified_process(
            run_smoke=fail_before_terminal,
            terminal=unexpected_terminal,
        )
    assert terminal_calls == [7]


def test_native_calculator_teardown_disables_auto_quit_and_restores_on_error():
    smoke = _load_native_calculator_smoke()
    events = []

    class FakeApplication:
        def quitOnLastWindowClosed(self):
            events.append("read-auto-quit")
            return True

        def setQuitOnLastWindowClosed(self, enabled):
            events.append(("set-auto-quit", enabled))

    class FailingWindow:
        current_data_unsaved = True

        def close(self):
            events.append("close")
            raise RuntimeError("close failed")

    window = FailingWindow()
    with pytest.raises(RuntimeError, match="close failed"):
        smoke.close_automation_window(FakeApplication(), window)

    assert window.current_data_unsaved is False
    assert events == [
        "read-auto-quit",
        ("set-auto-quit", False),
        "close",
        ("set-auto-quit", True),
    ]


def test_native_calculator_evidence_is_relocatable_and_tamper_evident(tmp_path):
    smoke = _load_native_calculator_smoke()
    source = tmp_path / "source"
    source.mkdir()
    records = []
    capture_methods = (
        "QScreen.grabWindow",
        "QWidget.grab fallback",
        "QWidget.render(QImage) fallback",
    )
    for calculator, capture_method in zip(
        ("binary", "continuous", "diagnostic"), capture_methods, strict=True
    ):
        image = source / (calculator + ".png")
        rendered = QtGui.QImage(12, 8, QtGui.QImage.Format.Format_ARGB32)
        rendered.fill(QtGui.QColor("#2d72d9"))
        assert rendered.save(str(image), "PNG")
        payload = image.read_bytes()
        records.append(
            {
                "calculator": calculator,
                "capture_method": capture_method,
                "image": image.name,
                "image_size": len(payload),
                "image_sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    (source / "evidence.json").write_text(json.dumps(records), encoding="utf-8")

    relocated = tmp_path / "downloaded" / "native-calculator-evidence"
    shutil.copytree(source, relocated)
    assert smoke.validate_evidence_bundle(relocated) == records

    manifest = relocated / "evidence.json"
    tampered = json.loads(manifest.read_text(encoding="utf-8"))
    forged = b"not a PNG despite matching manifest integrity"
    forged_image = relocated / tampered[0]["image"]
    forged_image.write_bytes(forged)
    tampered[0]["image_size"] = len(forged)
    tampered[0]["image_sha256"] = hashlib.sha256(forged).hexdigest()
    manifest.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="image is not a PNG"):
        smoke.validate_evidence_bundle(relocated)

    shutil.copy2(source / "binary.png", relocated / "binary.png")
    shutil.copy2(source / "evidence.json", manifest)
    tampered = json.loads(manifest.read_text(encoding="utf-8"))
    tampered[0]["capture_method"] = "untrusted screenshot"
    manifest.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="capture method is invalid"):
        smoke.validate_evidence_bundle(relocated)

    shutil.copy2(source / "evidence.json", manifest)
    tampered = json.loads(manifest.read_text(encoding="utf-8"))
    tampered[0]["image"] = "../binary.png"
    manifest.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="relative and canonical"):
        smoke.validate_evidence_bundle(relocated)

    shutil.copy2(source / "evidence.json", manifest)
    tampered = json.loads(manifest.read_text(encoding="utf-8"))
    tampered[0]["image_size"] += 1
    manifest.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="size does not match"):
        smoke.validate_evidence_bundle(relocated)

    shutil.copy2(source / "evidence.json", manifest)
    hash_tampered = bytearray((relocated / "binary.png").read_bytes())
    hash_tampered[-1] ^= 1
    (relocated / "binary.png").write_bytes(hash_tampered)
    with pytest.raises(ValueError, match="SHA256 does not match"):
        smoke.validate_evidence_bundle(relocated)


def test_calculator_consumers_share_one_canonical_r_bridge_identity(monkeypatch):
    import importlib

    from rc_metastudio import (
        binary_data_dialog,
        calculator_routines,
        continuous_data_dialog,
        diagnostic_data_dialog,
        dataset_table_model,
    )

    canonical = importlib.import_module("rc_metastudio.r_bridge")
    for consumer in (
        binary_data_dialog,
        calculator_routines,
        continuous_data_dialog,
        diagnostic_data_dialog,
        dataset_table_model,
    ):
        assert consumer.r_bridge is canonical

    marker = object()
    monkeypatch.setattr(canonical, "_calculator_identity_marker", marker, raising=False)
    assert all(
        getattr(consumer.r_bridge, "_calculator_identity_marker", None) is marker
        for consumer in (
            binary_data_dialog,
            calculator_routines,
            continuous_data_dialog,
            diagnostic_data_dialog,
            dataset_table_model,
        )
    )


def test_calculator_cell_validators_accept_native_qt6_text():
    from rc_metastudio import binary_data_dialog
    from rc_metastudio import continuous_data_dialog
    from rc_metastudio import diagnostic_data_dialog

    binary_form = cast(binary_data_dialog.BinaryDataDialog, None)
    continuous_form = cast(continuous_data_dialog.ContinuousDataDialog, None)
    diagnostic_form = cast(diagnostic_data_dialog.DiagnosticDataDialog, None)
    assert (
        binary_data_dialog.BinaryDataDialog._cell_data_not_valid(binary_form, "  ")
        is None
    )
    assert (
        binary_data_dialog.BinaryDataDialog._cell_data_not_valid(binary_form, " 1 ")
        is None
    )
    assert (
        binary_data_dialog.BinaryDataDialog._cell_data_not_valid(binary_form, "1.5")
        == "Expected a whole number (count), but a decimal value was entered."
    )

    assert (
        continuous_data_dialog.ContinuousDataDialog._cell_data_not_valid(
            continuous_form, " 1.25 ", "mean"
        )
        is None
    )
    assert (
        continuous_data_dialog.ContinuousDataDialog._cell_data_not_valid(
            continuous_form, "", "mean"
        )
        is None
    )
    for value in ("5", "5.0", "5,0"):
        assert (
            continuous_data_dialog.ContinuousDataDialog._cell_data_not_valid(
                continuous_form, value, "N"
            )
            is None
        )
    for value in ("5.5", "5,5", "-1", "nan", "inf"):
        assert "N must be" in (
            continuous_data_dialog.ContinuousDataDialog._cell_data_not_valid(
                continuous_form, value, "N"
            )
            or ""
        ) or "numeric" in (
            continuous_data_dialog.ContinuousDataDialog._cell_data_not_valid(
                continuous_form, value, "N"
            )
            or ""
        )

    assert (
        diagnostic_data_dialog.DiagnosticDataDialog.cell_data_invalid(
            diagnostic_form, " 2 "
        )
        is None
    )
    assert (
        diagnostic_data_dialog.DiagnosticDataDialog.cell_data_invalid(
            diagnostic_form, "-1"
        )
        == "Counts cannot be negative."
    )


def test_calculator_numeric_input_uses_unambiguous_dot_or_comma_decimal():
    from rc_metastudio import calculator_routines

    for text in ("12.5", "12,5"):
        assert calculator_routines.numeric_value(text) == 12.5


def test_calculator_numeric_input_rejects_grouping_and_non_finite_values():
    from rc_metastudio import calculator_routines

    for text in ("1,234.5", "1.234,5", "1,2,3", "nan", "inf"):
        with pytest.raises(ValueError, match="unambiguous finite number"):
            calculator_routines.numeric_value(text)


def test_consistency_checker_uses_qt6_foreground_api(qapp):
    from rc_metastudio import calculator_routines as calc_fncs

    table = QTableWidget(3, 3)
    values = [
        [1, 2, 99],
        [3, 4, 7],
        [4, 6, 10],
    ]
    for row, row_values in enumerate(values):
        for col, value in enumerate(row_values):
            table.setItem(row, col, QTableWidgetItem(str(value)))

    checker = calc_fncs.ConsistencyChecker(
        fn_consistent=lambda: None,
        fn_inconsistent=lambda: None,
        table_2x2=table,
    )

    assert checker.run() == "Rows must sum!"
    assert _table_item(table, 0, 0).foreground().color() == calc_fncs.ERROR_COLOR

    _table_item(table, 0, 2).setText("3")
    assert checker.run() is None
    assert _table_item(table, 0, 0).foreground().color() == calc_fncs.OK_COLOR


def test_field_edit_command_replays_captured_states_once(qapp):
    from rc_metastudio import calculator_routines as calc_fncs

    restored = []
    refreshes = []

    class Owner:
        def enable_back_calculation_btn(self, engage=False):
            refreshes.append(engage)

    def restore_state(*state):
        restored.append(state)

    stack = QtGui.QUndoStack()
    calc_fncs.push_field_edit(
        stack,
        owner=Owner(),
        restore_state=restore_state,
        old_state=("old", 1),
        new_state=("new", 2),
    )

    assert restored == []
    assert refreshes == [False]
    stack.undo()
    assert restored == [("old", 1)]
    stack.redo()
    assert restored == [("old", 1), ("new", 2)]


def test_continuous_imputation_uses_r_keys_not_visible_headers(qapp, monkeypatch):
    from rc_metastudio import continuous_data_dialog

    captured = []

    def fake_impute_cont_data(params, alpha):
        captured.append(params.copy())
        return {"succeeded": False}

    monkeypatch.setattr(
        continuous_data_dialog.r_bridge, "impute_cont_data", fake_impute_cont_data
    )

    form = continuous_data_dialog.ContinuousDataDialog.__new__(
        continuous_data_dialog.ContinuousDataDialog
    )
    form.simple_table = QTableWidget(2, 8)
    form.simple_table.setHorizontalHeaderLabels(
        ["N", "Mean", "SD", "SE", "Variance", "Lower", "Upper", "P-Value"]
    )
    form.cur_groups = ["Group 1", "Group 2"]
    form.conf_level = 95.0
    form.analysis_unit = object()

    form.simple_table.setItem(0, 0, QTableWidgetItem("10"))
    form.simple_table.setItem(0, 1, QTableWidgetItem("94"))
    form.simple_table.setItem(0, 4, QTableWidgetItem("2.5"))
    form.simple_table.setItem(0, 5, QTableWidgetItem("90"))
    form.simple_table.setItem(0, 6, QTableWidgetItem("98"))

    form.impute_data()

    assert captured[0] == {
        "n": 10.0,
        "mean": 94.0,
        "var": 2.5,
        "low": 90.0,
        "high": 98.0,
    }


def test_row_header_signals_are_restored_when_calculator_opening_raises(
    qapp, monkeypatch
):
    from rc_metastudio import dataset_table_view

    class CalculatorOpenError(RuntimeError):
        pass

    class RaisingContinuousDialog:
        def __init__(self, *args, **kwargs):
            raise CalculatorOpenError("boom")

    class FakeModel(QtCore.QAbstractTableModel):
        dataset = [object()]
        current_txs = ["Group 1", "Group 2"]
        current_effect = "MD"

        def rowCount(self, parent=QtCore.QModelIndex()):
            return 1

        def columnCount(self, parent=QtCore.QModelIndex()):
            return 1

        def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
            return None

        def get_current_analysis_unit_for_study(self, study_index):
            return FakeAnalysisUnit()

        def get_cur_group_str(self):
            return "Group 1-Group 2"

        def get_current_outcome_type(self):
            return "continuous"

        def get_global_conf_level(self):
            return 95.0

    monkeypatch.setattr(
        dataset_table_view.continuous_data_dialog,
        "ContinuousDataDialog",
        RaisingContinuousDialog,
    )

    view = dataset_table_view.DatasetTableView()
    view.setModel(FakeModel())

    try:
        view.row_header_clicked(0)
    except CalculatorOpenError:
        pass

    assert not view.vert_header.signalsBlocked()


class FakeAnalysisUnit:
    def __init__(self):
        from rc_metastudio.meta_globals import BINARY_ONE_ARM_METRICS, BINARY_TWO_ARM_METRICS

        self.effects_dict = {
            metric: {} for metric in BINARY_ONE_ARM_METRICS + BINARY_TWO_ARM_METRICS
        }
        self.raw_data = {"Group 1": [6, 20], "Group 2": [8, 22]}

    def get_effect_names(self):
        return list(self.effects_dict.keys())

    def get_effects_dict(self):
        return self.effects_dict

    def get_raw_data_for_group(self, group):
        return self.raw_data[group]

    def get_raw_data_for_groups(self, groups):
        values = []
        for group in groups:
            values.extend(self.raw_data[group])
        return values

    def get_effect_and_ci(self, metric, group_str, mult):
        return 1.0, 0.5, 2.0

    def set_effect_and_ci(self, *args, **kwargs):
        pass

    def set_effect(self, *args, **kwargs):
        pass

    def set_lower(self, *args, **kwargs):
        pass

    def set_upper(self, *args, **kwargs):
        pass


def test_binary_calculator_uses_table_headers_and_friendly_two_arm_metric_labels(
    qapp, monkeypatch
):
    from rc_metastudio import binary_data_dialog

    monkeypatch.setattr(
        binary_data_dialog.r_bridge, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        binary_data_dialog.r_bridge,
        "binary_convert_scale",
        lambda x, *args, **kwargs: x,
    )
    monkeypatch.setattr(
        binary_data_dialog.r_bridge, "impute_bin_data", lambda data: {"FAIL": True}
    )

    form = binary_data_dialog.BinaryDataDialog(
        FakeAnalysisUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        "OR",
        conf_level=95.0,
    )

    table = _required(form.raw_data_table)
    assert not _required(table.horizontalHeader()).isHidden()
    assert not _required(table.verticalHeader()).isHidden()
    assert [
        _required(table.horizontalHeaderItem(col)).text()
        for col in range(table.columnCount())
    ] == ["Event", "No Event", "Total"]
    assert [
        _required(table.verticalHeaderItem(row)).text()
        for row in range(table.rowCount())
    ] == ["Group 1", "Group 2", "Total"]
    assert form.raw_data_table.maximumHeight() >= form.raw_data_table.minimumHeight()
    assert [
        form.effect_cbo_box.itemData(index)
        for index in range(form.effect_cbo_box.count())
    ] == ["OR", "RD", "RR", "AS", "YUQ", "YUY"]
    assert "Odds Ratio (OR)" in [
        form.effect_cbo_box.itemText(index)
        for index in range(form.effect_cbo_box.count())
    ]


def test_binary_calculator_table_layout_uses_real_headers_and_visible_total_row(
    qapp, monkeypatch
):
    from rc_metastudio import binary_data_dialog

    monkeypatch.setattr(
        binary_data_dialog.r_bridge, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        binary_data_dialog.r_bridge,
        "binary_convert_scale",
        lambda x, *args, **kwargs: x,
    )
    monkeypatch.setattr(
        binary_data_dialog.r_bridge, "impute_bin_data", lambda data: {"FAIL": True}
    )

    form = binary_data_dialog.BinaryDataDialog(
        FakeAnalysisUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        "OR",
        conf_level=95.0,
    )

    table = _required(form.raw_data_table)

    assert form.event_lbl_3.isHidden()
    assert table.maximumWidth() > table.minimumWidth()
    assert table.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding

    required_height = (
        _required(table.horizontalHeader()).height()
        + sum(table.rowHeight(row) for row in range(table.rowCount()))
        + 2 * table.frameWidth()
    )
    assert table.minimumHeight() >= required_height
    assert table.maximumHeight() >= required_height


def _assert_calculator_table_grid_fills_width(qapp, table):
    calculator = table.window()
    calculator.resize(calculator.width() + 180, calculator.height())
    calculator.show()
    qapp.processEvents()

    section_width = sum(
        _required(table.horizontalHeader()).sectionSize(column)
        for column in range(table.columnCount())
    )

    assert (
        _required(table.horizontalHeader()).sectionResizeMode(0)
        == QHeaderView.ResizeMode.Stretch
    )
    assert section_width >= table.viewport().width() - 1


def _assert_calculator_table_content_columns_fill_width(qapp, table):
    calculator = table.window()
    calculator.resize(calculator.width() + 180, calculator.height())
    calculator.show()
    qapp.processEvents()

    header = _required(table.horizontalHeader())
    section_width = sum(
        header.sectionSize(column) for column in range(table.columnCount())
    )

    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Interactive
    assert header.stretchLastSection()
    assert section_width >= table.viewport().width() - 1
    for column in range(table.columnCount()):
        assert table.columnWidth(column) >= table.sizeHintForColumn(column)


def _assert_effect_ci_fields_fit_signed_precision(qapp, form):
    from rc_metastudio import meta_globals

    signed_value = "-0." + ("8" * meta_globals.CALC_NUM_DIGITS)
    fields = [form.effect_txt_box, form.low_txt_box, form.high_txt_box]
    for field in fields:
        field.setText(signed_value)

    form.show()
    qapp.processEvents()

    for field in fields:
        assert isinstance(field, QLineEdit)
        text_width = field.fontMetrics().horizontalAdvance(signed_value)
        required_width = text_width + 12
        assert field.width() >= required_width
        assert field.maximumWidth() >= required_width


def test_calculator_effect_ci_fields_fit_valid_domain_samples(qapp, monkeypatch):
    from rc_metastudio import binary_data_dialog
    from rc_metastudio import continuous_data_dialog
    from rc_metastudio import diagnostic_data_dialog

    monkeypatch.setattr(
        binary_data_dialog.r_bridge, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        binary_data_dialog.r_bridge,
        "binary_convert_scale",
        lambda x, *args, **kwargs: x,
    )
    monkeypatch.setattr(
        binary_data_dialog.r_bridge, "impute_bin_data", lambda data: {"FAIL": True}
    )
    monkeypatch.setattr(
        continuous_data_dialog.r_bridge, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        continuous_data_dialog.r_bridge,
        "continuous_convert_scale",
        lambda x, *args, **kwargs: x,
    )
    monkeypatch.setattr(
        continuous_data_dialog.r_bridge,
        "impute_cont_data",
        lambda data, alpha: {"succeeded": False, "comment": "stub"},
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge,
        "diagnostic_convert_scale",
        lambda x, *args, **kwargs: x,
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge,
        "impute_diag_data",
        lambda data: {"TP": None, "FP": None, "FN": None, "TN": None},
    )

    forms_and_representatives = [
        (
            binary_data_dialog.BinaryDataDialog(
                FakeAnalysisUnit(),
                ["Group 1", "Group 2"],
                "Group 1-Group 2",
                "OR",
                conf_level=95.0,
            ),
            "-0.8888",
        ),
        (
            continuous_data_dialog.ContinuousDataDialog(
                FakeContinuousAnalysisUnit(),
                ["Group 1", "Group 2"],
                "Group 1-Group 2",
                "ROM",
                conf_level=95.0,
            ),
            "-0.8888",
        ),
        (
            diagnostic_data_dialog.DiagnosticDataDialog(
                FakeDiagnosticAnalysisUnit(),
                ["Group 1", "Group 2"],
                "Group 1-Group 2",
                conf_level=95.0,
            ),
            "1.0000",
        ),
    ]

    for form, representative in forms_and_representatives:
        fields = [form.effect_txt_box, form.low_txt_box, form.high_txt_box]
        for field in fields:
            field.setText(representative)
        form.show()
        qapp.processEvents()
        for field in fields:
            assert field.width() >= field.fontMetrics().horizontalAdvance(
                representative
            )


@pytest.mark.parametrize(
    ("metric", "representative"),
    [("MD", "-9999.9999"), ("SMD", "-10.9999"), ("TX Mean", "9999.9999")],
    ids=["md", "smd", "tx_mean"],
)
def test_continuous_effect_fields_fit_metric_domain_samples(
    qapp, monkeypatch, metric, representative
):
    from rc_metastudio import calculator_routines

    monkeypatch.setattr(
        calculator_routines.r_bridge,
        "continuous_convert_scale",
        lambda value, *args, **kwargs: value,
    )
    unit = FakeContinuousAnalysisUnit()
    fields = {name: QLineEdit() for name in ("effect", "lower", "upper")}
    calculator_routines.helper_set_current_effect(
        unit,
        fields,
        metric,
        "Group 1" if metric == "TX Mean" else "Group 1-Group 2",
        "continuous",
        mult=1.96,
    )
    for field in fields.values():
        margins = field.textMargins()
        frame = _required(field.style()).pixelMetric(
            QStyle.PixelMetric.PM_DefaultFrameWidth, None, field
        )
        required = (
            field.fontMetrics().horizontalAdvance(representative)
            + margins.left()
            + margins.right()
            + 2 * frame
        )
        assert field.minimumWidth() >= required
        assert field.maximumWidth() >= required


def test_binary_calculator_grid_columns_fill_expanded_table_width(qapp, monkeypatch):
    from rc_metastudio import binary_data_dialog

    monkeypatch.setattr(
        binary_data_dialog.r_bridge, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        binary_data_dialog.r_bridge,
        "binary_convert_scale",
        lambda x, *args, **kwargs: x,
    )
    monkeypatch.setattr(
        binary_data_dialog.r_bridge, "impute_bin_data", lambda data: {"FAIL": True}
    )

    form = binary_data_dialog.BinaryDataDialog(
        FakeAnalysisUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        "OR",
        conf_level=95.0,
    )

    form.show()
    qapp.processEvents()
    header = _required(_required(form.raw_data_table).horizontalHeader())
    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Interactive
    assert not header.stretchLastSection()
    for column in range(form.raw_data_table.columnCount()):
        assert header.sectionSize(column) >= header.sectionSizeHint(column)


def test_binary_effect_fields_follow_metric_display_domains(qapp, monkeypatch):
    from rc_metastudio import calculator_routines

    monkeypatch.setattr(
        calculator_routines.r_bridge,
        "binary_convert_scale",
        lambda value, *args, **kwargs: value,
    )

    widths = {}
    for metric in ("OR", "RD", "PR", "PLO", "AS"):
        fields = {name: QLineEdit() for name in ("effect", "lower", "upper")}
        calculator_routines.helper_set_current_effect(
            FakeAnalysisUnit(), fields, metric, "Group 1-Group 2", "binary", mult=1.96
        )
        field = fields["effect"]
        widths[metric] = field.minimumWidth()
        margins = field.textMargins()
        frame = _required(field.style()).pixelMetric(
            QStyle.PixelMetric.PM_DefaultFrameWidth, None, field
        )
        for sample in calculator_routines.binary_effect_display_samples(metric):
            required = (
                field.fontMetrics().horizontalAdvance(sample)
                + margins.left()
                + margins.right()
                + (2 * frame)
            )
            assert field.minimumWidth() >= required

    assert widths["OR"] > widths["RD"]
    assert widths["OR"] > widths["PR"]
    assert widths["PR"] == widths["PLO"]
    assert widths["AS"] >= widths["RD"]

    maximum_rendered_ratio = str(round(sys.float_info.max, 4))
    assert (
        calculator_routines.format_calculator_display_value(sys.float_info.max)
        == maximum_rendered_ratio
    )
    assert maximum_rendered_ratio in calculator_routines.binary_effect_display_samples(
        "OR"
    )
    ratio_field = QLineEdit()
    ratio_fields = {
        name: ratio_field if name == "effect" else QLineEdit()
        for name in ("effect", "lower", "upper")
    }
    calculator_routines.helper_set_current_effect(
        FakeAnalysisUnit(),
        ratio_fields,
        "OR",
        "Group 1-Group 2",
        "binary",
        mult=1.96,
    )
    text_margins = ratio_field.textMargins()
    frame_width = _required(ratio_field.style()).pixelMetric(
        QStyle.PixelMetric.PM_DefaultFrameWidth, None, ratio_field
    )
    required_rendered_width = (
        ratio_field.fontMetrics().horizontalAdvance(maximum_rendered_ratio)
        + text_margins.left()
        + text_margins.right()
        + (2 * frame_width)
    )
    assert ratio_field.minimumWidth() >= required_rendered_width


def test_binary_calculator_does_not_wire_raw_edits_to_consistency_checker(
    qapp, monkeypatch
):
    from rc_metastudio import binary_data_dialog

    def fail_if_constructed(*args, **kwargs):
        raise AssertionError("raw count edits must not use the consistency checker")

    monkeypatch.setattr(
        binary_data_dialog.r_bridge, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        binary_data_dialog.r_bridge,
        "binary_convert_scale",
        lambda x, *args, **kwargs: x,
    )
    monkeypatch.setattr(
        binary_data_dialog.r_bridge, "impute_bin_data", lambda data: {"FAIL": True}
    )
    monkeypatch.setattr(
        binary_data_dialog.calc_fncs, "ConsistencyChecker", fail_if_constructed
    )

    form = binary_data_dialog.BinaryDataDialog(
        FakeAnalysisUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        "OR",
        conf_level=95.0,
    )

    assert not hasattr(form, "check_table_consistency")


def test_binary_calculator_accepts_single_raw_count_edit_and_recomputes_margins(
    qapp, monkeypatch
):
    from rc_metastudio import binary_data_dialog

    warnings = []

    monkeypatch.setattr(
        binary_data_dialog.r_bridge, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        binary_data_dialog.r_bridge,
        "binary_convert_scale",
        lambda x, *args, **kwargs: x,
    )
    monkeypatch.setattr(
        binary_data_dialog.r_bridge, "impute_bin_data", lambda data: {"FAIL": True}
    )
    monkeypatch.setattr(
        binary_data_dialog.r_bridge,
        "effect_for_study",
        lambda *args, **kwargs: {"calc_scale": (1.2, 0.8, 1.8)},
    )
    monkeypatch.setattr(
        binary_data_dialog.r_bridge,
        "effect_triplet",
        lambda effect, scale, metric=None: effect[scale],
    )
    monkeypatch.setattr(
        binary_data_dialog.QMessageBox,
        "warning",
        lambda parent, title, message: warnings.append(message),
    )

    form = binary_data_dialog.BinaryDataDialog(
        FakeAnalysisUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        "OR",
        conf_level=95.0,
    )

    table = form.raw_data_table
    form.current_item_data = 6
    _table_item(table, 0, 0).setText("7")
    qapp.processEvents()

    assert warnings == []
    assert _table_item(table, 0, 0).text() == "7"
    assert _table_item(table, 0, 1).text() == "14"
    assert _table_item(table, 0, 2).text() == "21"
    assert _table_item(table, 2, 0).text() == "15"
    assert _table_item(table, 2, 1).text() == "28"
    assert _table_item(table, 2, 2).text() == "43"
    assert form.analysis_unit.get_raw_data_for_group("Group 1") == [7, 21]
    assert not form.inconsistencyLabel.isVisible()
    assert _required(
        form.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
    ).isEnabled()


class FakeDiagnosticAnalysisUnit:
    def __init__(self):
        self.raw_data = [1, 2, 3, 4]
        self.tx_groups = {"Group 1-Group 2": FakeDiagnosticGroup(self.raw_data)}

    def get_raw_data_for_group(self, group):
        return self.raw_data

    def get_effect_and_ci(self, metric, group_str, mult):
        return None, None, None

    def set_effect_and_ci(self, *args, **kwargs):
        pass

    def set_effect(self, *args, **kwargs):
        pass

    def set_lower(self, *args, **kwargs):
        pass

    def set_upper(self, *args, **kwargs):
        pass


class FakeDiagnosticGroup:
    def __init__(self, raw_data):
        self.raw_data = raw_data


def test_diagnostic_calculator_grid_columns_fill_expanded_table_width(
    qapp, monkeypatch
):
    from rc_metastudio import diagnostic_data_dialog

    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge,
        "diagnostic_convert_scale",
        lambda x, *args, **kwargs: x,
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge,
        "impute_diag_data",
        lambda data: {"TP": None, "FP": None, "FN": None, "TN": None},
    )

    form = diagnostic_data_dialog.DiagnosticDataDialog(
        FakeDiagnosticAnalysisUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        conf_level=95.0,
    )

    form.show()
    qapp.processEvents()
    table = _required(form.two_by_two_table)
    header = _required(table.horizontalHeader())
    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Interactive
    assert not header.stretchLastSection()
    for column in range(table.columnCount()):
        assert header.sectionSize(column) >= header.sectionSizeHint(column)


def test_diagnostic_calculator_does_not_wire_raw_edits_to_consistency_checker(
    qapp, monkeypatch
):
    from rc_metastudio import diagnostic_data_dialog

    def fail_if_constructed(*args, **kwargs):
        raise AssertionError("raw count edits must not use the consistency checker")

    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge,
        "diagnostic_convert_scale",
        lambda x, *args, **kwargs: x,
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge,
        "impute_diag_data",
        lambda data: {"TP": None, "FP": None, "FN": None, "TN": None},
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.calc_fncs, "ConsistencyChecker", fail_if_constructed
    )

    form = diagnostic_data_dialog.DiagnosticDataDialog(
        FakeDiagnosticAnalysisUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        conf_level=95.0,
    )

    assert not hasattr(form, "check_table_consistency")


def test_diagnostic_calculator_accepts_single_raw_count_edit_and_recomputes_margins(
    qapp, monkeypatch
):
    from rc_metastudio import diagnostic_data_dialog

    warnings = []

    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge,
        "diagnostic_convert_scale",
        lambda x, *args, **kwargs: x,
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge,
        "impute_diag_data",
        lambda data: {"TP": None, "FP": None, "FN": None, "TN": None},
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge,
        "diagnostic_effects_for_study",
        lambda *args, metrics, **kwargs: {
            metric: {"calc_scale": (0.5, 0.4, 0.6)} for metric in metrics
        },
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.r_bridge,
        "effect_triplet",
        lambda effect, scale, metric=None: effect[scale],
    )
    monkeypatch.setattr(
        diagnostic_data_dialog.QMessageBox,
        "warning",
        lambda parent, title, message: warnings.append(message),
    )

    form = diagnostic_data_dialog.DiagnosticDataDialog(
        FakeDiagnosticAnalysisUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        conf_level=95.0,
    )

    table = _required(form.two_by_two_table)
    form.current_item_data = 1
    _table_item(table, 0, 0).setText("5")
    qapp.processEvents()

    assert warnings == []
    assert _table_item(table, 0, 0).text() == "5"
    assert _table_item(table, 0, 2).text() == "8"
    assert _table_item(table, 1, 2).text() == "6"
    assert _table_item(table, 2, 0).text() == "7"
    assert _table_item(table, 2, 1).text() == "7"
    assert _table_item(table, 2, 2).text() == "14"
    assert form.analysis_unit.raw_data == [5.0, 2.0, 3.0, 4.0]
    assert not form.inconsistencyLabel.isVisible()
    assert _required(
        form.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
    ).isEnabled()


class FakeContinuousAnalysisUnit:
    def __init__(self):
        self.raw_data = {
            "Group 1": [10, 94, 2],
            "Group 2": [12, 90, 3],
        }

    def get_effect_names(self):
        return ["ROM"]

    def get_raw_data_for_group(self, group):
        return self.raw_data[group]

    def get_raw_data_for_groups(self, groups):
        values = []
        for group in groups:
            values.extend(self.raw_data[group])
        return values

    def get_se(self, *args, **kwargs):
        return None

    def get_effect_and_ci(self, *args, **kwargs):
        return None, None, None

    def set_effect_and_ci(self, *args, **kwargs):
        pass

    def set_effect(self, *args, **kwargs):
        pass

    def set_lower(self, *args, **kwargs):
        pass

    def set_upper(self, *args, **kwargs):
        pass


def test_continuous_calculator_grid_columns_keep_internal_overflow(qapp, monkeypatch):
    from rc_metastudio import continuous_data_dialog

    monkeypatch.setattr(
        continuous_data_dialog.r_bridge, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        continuous_data_dialog.r_bridge,
        "continuous_convert_scale",
        lambda x, *args, **kwargs: x,
    )
    monkeypatch.setattr(
        continuous_data_dialog.r_bridge,
        "impute_cont_data",
        lambda data, alpha: {"succeeded": False, "comment": "stub"},
    )

    form = continuous_data_dialog.ContinuousDataDialog(
        FakeContinuousAnalysisUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        "ROM",
        conf_level=95.0,
    )

    form.resize(360, form.height())
    form.show()
    qapp.processEvents()
    table = _required(form.simple_table)
    header = _required(table.horizontalHeader())
    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Interactive
    assert not header.stretchLastSection()
    assert (
        table.horizontalScrollBarPolicy() == QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )
    assert (
        sum(header.sectionSize(column) for column in range(table.columnCount()))
        > table.viewport().width()
    )


def test_continuous_calculator_keeps_long_imputed_values_compact(qapp, monkeypatch):
    from rc_metastudio import continuous_data_dialog

    long_imputed = {
        "n": 10,
        "mean": 92.89482413483651,
        "sd": 2.604729426373378,
        "se": 8.75360686626884e-310,
        "var": 3.4972319657703745e-249,
        "pval": 0.12345678912345678,
        "low": 91.11111111111111,
        "high": 94.99999999999999,
    }

    monkeypatch.setattr(
        continuous_data_dialog.r_bridge, "get_mult_from_r", lambda conf: 1.96
    )
    monkeypatch.setattr(
        continuous_data_dialog.r_bridge,
        "continuous_convert_scale",
        lambda x, *args, **kwargs: x,
    )
    monkeypatch.setattr(
        continuous_data_dialog.r_bridge,
        "impute_cont_data",
        lambda data, alpha: {"succeeded": True, "output": long_imputed},
    )

    form = continuous_data_dialog.ContinuousDataDialog(
        FakeContinuousAnalysisUnit(),
        ["Group 1", "Group 2"],
        "Group 1-Group 2",
        "ROM",
        conf_level=95.0,
    )

    form.show()
    qapp.processEvents()

    displayed_values = [
        _table_item(form.simple_table, 0, column).text()
        for column in range(form.simple_table.columnCount())
    ]
    assert "2.604729426373378" not in displayed_values
    assert "3.4972319657703745e-249" not in displayed_values
    assert _table_item(form.simple_table, 0, 2).text() == "2.6047"

    natural_width = sum(
        max(
            _required(_required(form.simple_table).horizontalHeader()).sectionSizeHint(
                column
            ),
            _required(form.simple_table).sizeHintForColumn(column),
        )
        for column in range(_required(form.simple_table).columnCount())
    )
    assert form.simple_table.minimumWidth() < natural_width * 2
    assert (
        form.frameGeometry().width() < qapp.primaryScreen().availableGeometry().width()
    )
