# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Small typing helpers for Qt test seams.

Qt's generated stubs correctly model nullable lookups, while these tests
usually establish the widgets before using them.  Keeping the assertion in a
single helper makes that invariant explicit without weakening Ty globally.
"""

from collections.abc import Callable
from typing import TypeVar, cast

from PyQt6 import QtCore, QtTest
from PyQt6.QtWidgets import QWidget


T = TypeVar("T")


def required(value: T | None, name: str = "value") -> T:
    """Return a required value, failing the test setup when it is missing."""

    assert value is not None, f"Expected {name} to exist"
    return value


def key_click(
    widget: QWidget,
    key: QtCore.Qt.Key,
    modifiers: QtCore.Qt.KeyboardModifier = QtCore.Qt.KeyboardModifier.NoModifier,
) -> None:
    """Invoke Qt's overloaded keyClick API through its runtime signature."""

    cast(Callable[..., None], QtTest.QTest.keyClick)(widget, key, modifiers)


def key_clicks(widget: QWidget, sequence: str) -> None:
    """Invoke Qt's overloaded keyClicks API through its runtime signature."""

    cast(Callable[..., None], QtTest.QTest.keyClicks)(widget, sequence)


def mouse_click(widget: QWidget, button: QtCore.Qt.MouseButton) -> None:
    """Invoke Qt's overloaded mouseClick API through its runtime signature."""

    cast(Callable[..., None], QtTest.QTest.mouseClick)(widget, button)


def wait(milliseconds: int) -> None:
    """Wait through Qt's generated test API."""

    cast(Callable[..., None], QtTest.QTest.qWait)(milliseconds)
