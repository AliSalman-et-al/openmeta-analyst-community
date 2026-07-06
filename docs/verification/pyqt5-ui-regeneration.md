# PyQt5 UI Regeneration

Regenerate the checked-in Python UI modules from the canonical Qt Designer files with:

```powershell
python scripts/regenerate-pyqt5-ui.py
```

The script compiles Qt Designer files under `src/rc_metastudio/forms/*.ui` with PyQt5 and rebuilds `src/rc_metastudio/forms/icons_rc.py` from `src/rc_metastudio/images/icons.qrc`.
