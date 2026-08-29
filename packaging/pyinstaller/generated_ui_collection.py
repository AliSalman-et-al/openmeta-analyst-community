# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Collect generated Qt modules into PyInstaller's canonical package archive."""

from pathlib import Path


def pyinstaller_module_entries(
    qt6_build_root: str | Path,
) -> tuple[tuple[str, str, str], ...]:
    package_root = Path(qt6_build_root).resolve() / "generated" / "rc_metastudio"
    forms_root = package_root / "forms"
    modules = [
        (f"rc_metastudio.{path.stem}", str(path), "PYMODULE")
        for path in sorted(package_root.glob("ui_*.py"))
    ]
    modules.extend(
        (f"rc_metastudio.forms.{path.stem}", str(path), "PYMODULE")
        for path in sorted(forms_root.glob("ui_*.py"))
    )
    if not modules:
        raise ValueError(f"no generated Qt modules found under {package_root}")
    return tuple(modules)
