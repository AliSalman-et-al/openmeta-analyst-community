import importlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
APP_PACKAGE = ROOT / "src" / "rc_metastudio"


def test_representative_generated_ui_modules_import_with_pyqt5():
    sys.path[:0] = [str(APP_PACKAGE), str(APP_PACKAGE / "forms")]

    for module in ["ui_meta", "ui_results_window", "ui_binary_data_form"]:
        imported = importlib.import_module(module)
        assert imported.QtCore.PYQT_VERSION_STR.startswith("5.")


def test_qt_resource_manifest_references_existing_image_files():
    image_root = APP_PACKAGE / "images"
    qrc_path = image_root / "icons.qrc"
    tree = ET.parse(qrc_path)

    missing_files = []
    for file_node in tree.findall(".//file"):
        relative_path = file_node.text
        if relative_path and not (image_root / relative_path).exists():
            missing_files.append(relative_path)

    assert missing_files == []
