# -*- mode: python ; coding: utf-8 -*-
# ruff: noqa: F821
"""Native feasibility bundle with one PyInstaller-owned Qt graph and explicit R."""

import importlib.util
import json
import os
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata


repo_root = Path(SPECPATH).resolve().parents[1]
adapter_spec = importlib.util.spec_from_file_location(
    "rcms_macos_embedded_r_adapter", repo_root / "scripts/macos_embedded_r_adapter.py"
)
adapter = importlib.util.module_from_spec(adapter_spec)
adapter_spec.loader.exec_module(adapter)
entry = Path(os.environ["RCMS_FEASIBILITY_ENTRY"]).resolve(strict=True)
resource = Path(os.environ["RCMS_FEASIBILITY_RESOURCE"]).resolve(strict=True)
toc = json.loads(
    Path(os.environ["RCMS_FEASIBILITY_R_TOC"]).read_text(encoding="utf-8")
)["entries"]
staged_framework = Path(os.environ["RCMS_FEASIBILITY_R_FRAMEWORK"]).resolve(strict=True)
if not toc or not all(item["destination"].startswith("R.framework/") for item in toc):
    raise ValueError("feasibility R TOC is empty or escapes R.framework")

a = Analysis(
    [str(entry)],
    pathex=[str(entry.parent)],
    binaries=[],
    datas=[*copy_metadata("rpy2"), (str(resource), "resources")],
    hiddenimports=["rpy2.robjects", "_rinterface_cffi_api", "PyQt6.QtSvg"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PySide2", "PySide6", "qtpy", "_rinterface_cffi_abi"],
    noarchive=False,
    optimize=0,
)
# The explicit framework TOC owns all R and compiler-runtime members. Remove
# PyInstaller's flattened copies from the system framework dependency walk.
a.binaries = adapter.filter_pyinstaller_r_binaries(list(a.binaries), staged_framework)
a.datas.extend((item["destination"], item["source"], item["type"]) for item in toc)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Qt6MacFeasibility",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
    target_arch=os.environ["RCMS_TARGET_ARCHITECTURE"],
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Qt6MacFeasibility",
)
app = BUNDLE(
    coll,
    name="Qt6MacFeasibility.app",
    bundle_identifier="org.researchconsultancy.rc-metastudio.feasibility",
    version="1.0.0",
    info_plist={
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        "NSPrincipalClass": "NSApplication",
    },
)
