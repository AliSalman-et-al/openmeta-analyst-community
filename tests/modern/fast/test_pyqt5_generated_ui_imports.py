import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_representative_generated_ui_modules_import_with_pyqt5():
    sys.path[:0] = [str(ROOT / "src"), str(ROOT / "src" / "forms")]

    for module in ["ui_meta", "ui_results_window", "ui_binary_data_form"]:
        imported = importlib.import_module(module)
        assert imported.QtCore.PYQT_VERSION_STR.startswith("5.")
