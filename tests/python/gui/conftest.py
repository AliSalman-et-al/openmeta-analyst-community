"""Explicit R-boundary injection for GUI behavior tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def inject_gui_boundary(inject_python_boundary, monkeypatch: pytest.MonkeyPatch):
    from rc_metastudio import binary_data_dialog, continuous_data_dialog, diagnostic_data_dialog, r_bridge

    for dialog_module in (binary_data_dialog, continuous_data_dialog, diagnostic_data_dialog):
        monkeypatch.setattr(dialog_module, "r_bridge", r_bridge, raising=False)
