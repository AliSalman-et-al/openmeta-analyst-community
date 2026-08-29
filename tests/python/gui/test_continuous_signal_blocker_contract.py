# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Signal-state contracts for continuous data-entry updates."""

import os
from pathlib import Path
from typing import cast

import pytest
from PyQt6 import QtWidgets


REPO_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault(
    "RCMS_QT6_BUILD_ROOT", str(REPO_ROOT / "build" / "qt6-verification")
)

from rc_metastudio.qt6_ui import prepare_generated_ui_imports
from test_types import required

prepare_generated_ui_imports()


@pytest.mark.parametrize("initially_blocked", [False, True])
def test_continuous_set_val_restores_table_signal_state(initially_blocked):
    from rc_metastudio import continuous_data_dialog

    app = required(
        QtWidgets.QApplication.instance() or QtWidgets.QApplication([]), "application"
    )
    table = QtWidgets.QTableWidget(1, 1)

    class StubDialog:
        simple_table = table

        @staticmethod
        def float_to_str(value):
            return str(value)

    table.blockSignals(initially_blocked)
    continuous_data_dialog.ContinuousDataDialog._set_val(
        cast(continuous_data_dialog.ContinuousDataDialog, StubDialog()), 0, 0, 3
    )

    assert table.signalsBlocked() is initially_blocked
    table.deleteLater()
    app.processEvents()


def test_continuous_set_val_restores_blocked_state_when_item_update_fails(monkeypatch):
    from rc_metastudio import continuous_data_dialog

    app = required(
        QtWidgets.QApplication.instance() or QtWidgets.QApplication([]), "application"
    )
    table = QtWidgets.QTableWidget(1, 1)
    table.setItem(0, 0, QtWidgets.QTableWidgetItem("old"))

    class StubDialog:
        simple_table = table

        @staticmethod
        def float_to_str(value):
            return str(value)

    def fail(*_args, **_kwargs):
        raise RuntimeError("injected item update failure")

    monkeypatch.setattr(continuous_data_dialog, "required", fail)
    table.blockSignals(True)
    with pytest.raises(RuntimeError, match="injected item update failure"):
        continuous_data_dialog.ContinuousDataDialog._set_val(
            cast(continuous_data_dialog.ContinuousDataDialog, StubDialog()), 0, 0, 3
        )

    assert table.signalsBlocked()
    table.deleteLater()
    app.processEvents()
