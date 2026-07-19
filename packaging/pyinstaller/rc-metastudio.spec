# -*- mode: python ; coding: utf-8 -*-
"""Authoritative PyInstaller definition for the Windows x64 application."""

import os
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata


repo_root = Path(SPECPATH).resolve().parents[1]
app_source = repo_root / "src" / "rc_metastudio"
pyqt_root = Path(os.environ["RCMS_PYQT_ROOT"]).resolve()
qt6_build_root = Path(os.environ["RCMS_QT6_BUILD_ROOT"]).resolve()
generated_package = qt6_build_root / "generated" / "rc_metastudio"
generated_forms = generated_package / "forms"
binary_resource = qt6_build_root / "resources" / "icons.rcc"
project_schema_root = app_source / "project_schemas" / "v1"
project_schema_data = [
    (
        str(path),
        str(Path("rc_metastudio") / "project_schemas" / "v1"),
    )
    for path in sorted(project_schema_root.glob("*.schema.json"))
]
generated_form_modules = sorted(path.stem for path in generated_forms.glob("ui_*.py"))
required_plugins = (
    "platforms/qwindows.dll",
    "imageformats/qico.dll",
    "imageformats/qjpeg.dll",
    "imageformats/qsvg.dll",
    "iconengines/qsvgicon.dll",
    "styles/qmodernwindowsstyle.dll",
    "tls/qschannelbackend.dll",
)
qt_plugin_binaries = [
    (
        str(pyqt_root / "Qt6" / "plugins" / relative),
        str(Path("PyQt6") / "Qt6" / "plugins" / Path(relative).parent),
    )
    for relative in required_plugins
]

a = Analysis(
    [str(app_source / "__main__.py")],
    pathex=[
        str(generated_package),
        str(generated_forms),
        str(app_source),
        str(app_source / "forms"),
    ],
    binaries=qt_plugin_binaries,
    datas=[
        *copy_metadata("rpy2"),
        (str(binary_resource), "resources"),
        *project_schema_data,
    ],
    hiddenimports=[
        "rpy2.robjects",
        "rpy2.rinterface",
        "_rinterface_cffi_api",
        "PyQt6.QtNetwork",
        "PyQt6.QtSvg",
        "PyQt6.QtSvgWidgets",
        *generated_form_modules,
        *(f"forms.{name}" for name in generated_form_modules),
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PySide2", "PySide6", "qtpy", "_rinterface_cffi_abi"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RCMetaStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=[str(app_source / "images" / "rc-metastudio-app-icon.ico")],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="RCMetaStudio",
)
