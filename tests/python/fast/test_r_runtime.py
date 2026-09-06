# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from rc_metastudio import r_runtime


def test_windows_r_environment_drops_unsupported_posix_utf8_locale(monkeypatch):
    environment = {
        "LC_ALL": "C.UTF-8",
        "LC_CTYPE": "C.utf8",
        "LANG": "C.UTF-8",
        "LC_TIME": "de_DE.UTF-8",
    }
    monkeypatch.setattr(r_runtime.os, "environ", environment)
    monkeypatch.setattr(r_runtime.sys, "platform", "win32")
    monkeypatch.setattr(r_runtime.locale, "setlocale", lambda *_args: None)

    r_runtime._set_r_environment()

    assert "LC_ALL" not in environment
    assert "LC_CTYPE" not in environment
    assert "LANG" not in environment
    assert environment["LC_TIME"] == "de_DE.UTF-8"
    assert environment["LC_NUMERIC"] == "C"


def test_non_windows_r_environment_preserves_posix_utf8_locale(monkeypatch):
    environment = {"LC_ALL": "C.UTF-8", "LANG": "C.UTF-8"}
    monkeypatch.setattr(r_runtime.os, "environ", environment)
    monkeypatch.setattr(r_runtime.sys, "platform", "linux")
    monkeypatch.setattr(r_runtime.locale, "setlocale", lambda *_args: None)

    r_runtime._set_r_environment()

    assert environment["LC_ALL"] == "C.UTF-8"
    assert environment["LANG"] == "C.UTF-8"


def test_windows_r_environment_preserves_supported_locale(monkeypatch):
    environment = {
        "LC_ALL": "English_United States.utf8",
        "LC_CTYPE": "de_DE.UTF-8",
        "LANG": "en_US.UTF-8",
    }
    monkeypatch.setattr(r_runtime.os, "environ", environment)
    monkeypatch.setattr(r_runtime.sys, "platform", "win32")
    monkeypatch.setattr(r_runtime.locale, "setlocale", lambda *_args: None)

    r_runtime._set_r_environment()

    assert environment["LC_ALL"] == "English_United States.utf8"
    assert environment["LC_CTYPE"] == "de_DE.UTF-8"
    assert environment["LANG"] == "en_US.UTF-8"
