# Qt6 UI and resource generation

Generate every canonical Qt Designer form and the binary resource collection
into the ignored build tree with the locked PyQt6 and official Qt 6 tools:

```powershell
uv run python scripts/build_qt6.py generate --build-root build/qt6
```

The `.ui` files under `src/rc_metastudio/forms/` and
`src/rc_metastudio/images/icons.qrc` are authoritative. Generated Python form
modules and Python resource bytes are not checked into version control. The
generated forms omit automatic object-name connections and rely on the
application's handwritten binary `QResource` loader.

Source launches must run generation first and then enter through
`python -m rc_metastudio` or the installed `rc-metastudio` command. The
central bootstrap validates the exact generated module set and locked PyQt6
provenance before placing `build/qt6/generated/rc_metastudio` and its `forms`
directory ahead of legacy source paths. `RCMS_QT6_BUILD_ROOT` selects an
explicit build root for automation; UI imports never generate files at runtime.

Future PyInstaller specifications must add the generated package root to their
analysis path so the frozen import archive contains the same top-level
`ui_meta`, `ui_results_window`, and `forms.ui_*` module names. Frozen startup
validates all 29 names before importing handwritten windows, while packaged
qualification separately verifies the binary resource and deployment manifest.
