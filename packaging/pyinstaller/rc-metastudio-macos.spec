# -*- mode: python ; coding: utf-8 -*-
"""Authoritative PyInstaller definition for the native macOS Intel app."""

import os
import hashlib
import importlib.util
import json
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata


repo_root = Path(SPECPATH).resolve().parents[1]
adapter_spec = importlib.util.spec_from_file_location(
    "rcms_macos_embedded_r_adapter", repo_root / "scripts" / "macos_embedded_r_adapter.py"
)
adapter_module = importlib.util.module_from_spec(adapter_spec)
adapter_spec.loader.exec_module(adapter_module)
app_source = repo_root / "src" / "rc_metastudio"
qt6_build_root = Path(os.environ["RCMS_QT6_BUILD_ROOT"]).resolve()
generated_package = qt6_build_root / "generated" / "rc_metastudio"
generated_forms = generated_package / "forms"
binary_resource = qt6_build_root / "resources" / "icons.rcc"
project_schema_root = app_source / "project_schemas" / "v1"
project_schema_data = [
    (str(path), str(Path("rc_metastudio") / "project_schemas" / "v1"))
    for path in sorted(project_schema_root.glob("*.schema.json"))
]
generated_form_modules = sorted(path.stem for path in generated_forms.glob("ui_*.py"))
direct_r_toc_path = os.environ.get("RCMS_PYINSTALLER_R_TOC")
direct_r_map_path = os.environ.get("RCMS_PYINSTALLER_R_MAP")
direct_r_datas = []
direct_r_toc = []
direct_r_map = {}
expected_bridge_sha256 = os.environ.get("RCMS_RPY2_API_BRIDGE_SHA256")
if direct_r_toc_path:
    direct_r_toc = json.loads(Path(direct_r_toc_path).read_text(encoding="utf-8"))["entries"]
    direct_r_map = json.loads(Path(direct_r_map_path).read_text(encoding="utf-8"))["mapped_sources"]
    direct_r_datas.append(
        (str(repo_root / "packaging" / "pyinstaller" / "direct-r-spike.marker"), ".")
    )
    bridge_source = Path(importlib.util.find_spec("_rinterface_cffi_api").origin).resolve(strict=True)
    bridge_sha256 = hashlib.sha256(bridge_source.read_bytes()).hexdigest()
    if bridge_sha256 != expected_bridge_sha256:
        raise ValueError("rpy2 API bridge changed before PyInstaller Analysis")

a = Analysis(
    [str(app_source / "__main__.py")],
    pathex=[
        str(generated_package),
        str(generated_forms),
        str(app_source),
        str(app_source / "forms"),
    ],
    binaries=[],
    datas=[
        *copy_metadata("rpy2"),
        (str(binary_resource), "resources"),
        *project_schema_data,
        *direct_r_datas,
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
    excludes=[
        "PyQt5",
        "PySide2",
        "PySide6",
        "qtpy",
        "_rinterface_cffi_abi",
    ],
    noarchive=False,
    optimize=0,
)
if direct_r_toc:
    a.binaries = adapter_module.filter_pyinstaller_r_binaries(
        list(a.binaries), direct_r_map
    )
    a.datas.extend(
        (entry["destination"], entry["source"], entry["type"])
        for entry in direct_r_toc
    )
    if hashlib.sha256(bridge_source.read_bytes()).hexdigest() != expected_bridge_sha256:
        raise ValueError("rpy2 API bridge changed during PyInstaller Analysis")
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
    argv_emulation=False,
    target_arch=os.environ.get("RCMS_TARGET_ARCHITECTURE", "x86_64"),
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="RCMetaStudio",
)
app = BUNDLE(
    coll,
    name="RCMetaStudio.app",
    bundle_identifier=os.environ.get(
        "RCMS_BUNDLE_IDENTIFIER", "org.researchconsultancy.rc-metastudio"
    ),
    version=os.environ.get("RCMS_PROJECT_VERSION", "0.1.2"),
    info_plist={
        "LSMinimumSystemVersion": os.environ.get("RCMS_MINIMUM_MACOS_VERSION", "13.0"),
        "NSHighResolutionCapable": True,
        "NSPrincipalClass": "NSApplication",
    },
)
