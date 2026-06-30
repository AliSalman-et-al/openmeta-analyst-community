import os
import sys

from PyQt5 import QtCore


sys.path.insert(0, os.path.abspath("src"))


import legacy_pickle


def test_loader_converts_sip_qt4_qstring_to_python3_str():
    value = legacy_pickle.loads_project_pickle(
        b"csip\n_unpickle_type\n(VPyQt4.QtCore\nVQString\n(Vhello\nttR."
    )

    assert value == "hello"
    assert type(value) is str


def test_loader_converts_direct_qt4_qstring_constructor_to_python3_str():
    value = legacy_pickle.loads_project_pickle(
        b"cPyQt4.QtCore\nQString\n(Vhello\ntR."
    )

    assert value == "hello"
    assert type(value) is str


def test_loader_converts_qt4_qstring_list_and_qvariant_to_native_values():
    string_list = legacy_pickle.loads_project_pickle(
        b"csip\n_unpickle_type\n(VPyQt4.QtCore\nVQStringList\n(](Vone\nVtwo\nettR."
    )
    variant = legacy_pickle.loads_project_pickle(
        b"csip\n_unpickle_type\n(VPyQt4.QtCore\nVQVariant\n(I7\nttR."
    )

    assert string_list == ["one", "two"]
    assert all(type(item) is str for item in string_list)
    assert variant == 7


def test_loader_maps_qt4_qbytearray_to_pyqt5_qbytearray():
    value = legacy_pickle.loads_project_pickle(
        b"csip\n_unpickle_type\n(VPyQt4.QtCore\nVQByteArray\n(S'abc'\nttR."
    )

    assert isinstance(value, QtCore.QByteArray)
    assert bytes(value) == b"abc"


def test_loader_maps_other_qt4_qtcore_types_to_pyqt5_classes():
    value = legacy_pickle.loads_project_pickle(
        b"csip\n_unpickle_type\n(VPyQt4.QtCore\nVQSize\n(I640\nI480\nttR."
    )

    assert isinstance(value, QtCore.QSize)
    assert value.width() == 640
    assert value.height() == 480


def test_loader_opens_representative_qt4_project_without_pyqt4_module():
    sys.modules.pop("PyQt4", None)

    dataset = legacy_pickle.load_project_pickle(os.path.abspath("sample_data/meantime.oma"))
    values = [study.covariate_dict["treatment group"] for study in dataset.studies]

    assert set(value for value in values if value is not None) == {"1", "2", "3", "4"}
    assert all(type(value) is str for value in values if value is not None)
    assert "PyQt4" not in sys.modules
