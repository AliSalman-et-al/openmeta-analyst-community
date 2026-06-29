# PyQt5 UI Regeneration

Regenerate the checked-in Python UI modules from the canonical Qt Designer files with:

```powershell
python scripts/regenerate-pyqt5-ui.py
```

The script compiles `src/*.ui` and `src/forms/*.ui` with PyQt5 and rebuilds `src/forms/icons_rc.py` from `src/images/icons.qrc`.
