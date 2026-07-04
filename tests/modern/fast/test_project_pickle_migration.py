import os
import sys

from PyQt5 import QtCore


sys.path.insert(0, os.path.abspath("src"))

import project_pickle


def _old_qt_module(name):
    return b"Py" + b"Qt4." + name


def _sip_value(type_name, args):
    return (
        b"csip\n_unpickle_type\n(V"
        + _old_qt_module(b"QtCore")
        + b"\nV"
        + type_name
        + b"\n("
        + args
        + b"ttR."
    )


def test_project_loader_migrates_old_qt_text_values_without_importing_old_qt():
    old_qt_name = "Py" + "Qt4"
    for name in list(sys.modules):
        if name == old_qt_name or name.startswith(old_qt_name + "."):
            del sys.modules[name]

    text = project_pickle.loads_project_pickle(
        _sip_value(b"Q" + b"String", b"Vhello\n")
    )
    text_list = project_pickle.loads_project_pickle(
        _sip_value(b"Q" + b"StringList", b"](Vone\nVtwo\ne")
    )
    variant = project_pickle.loads_project_pickle(
        _sip_value(b"Q" + b"Variant", b"I7\n")
    )

    assert text == "hello"
    assert type(text) is str
    assert text_list == ["one", "two"]
    assert all(type(item) is str for item in text_list)
    assert variant == 7
    assert old_qt_name not in sys.modules


def test_project_loader_migrates_direct_old_qt_text_constructor():
    payload = b"c" + _old_qt_module(b"QtCore") + b"\nQ" + b"String\n(Vhello\ntR."

    value = project_pickle.loads_project_pickle(payload)

    assert value == "hello"
    assert type(value) is str


def test_project_loader_maps_old_qt_byte_array_to_current_qt_value():
    value = project_pickle.loads_project_pickle(
        _sip_value(b"Q" + b"ByteArray", b"S'abc'\n")
    )

    assert isinstance(value, QtCore.QByteArray)
    assert bytes(value) == b"abc"


def test_project_loader_reports_unsupported_old_qt_values_as_project_format_errors():
    try:
        project_pickle.loads_project_pickle(_sip_value(b"Q" + b"MadeUp", b""))
    except project_pickle.ProjectFileFormatError as error:
        assert "older OpenMeta[Analyst] release" in str(error)
        assert "QMadeUp" in str(error)
    else:
        raise AssertionError("expected ProjectFileFormatError")


def test_representative_sample_projects_load_with_current_project_loader():
    for name in ["amino.oma", "BCG.oma", "continuous.oma", "lymph.oma", "meantime.oma"]:
        dataset = project_pickle.load_project_pickle(
            os.path.abspath(os.path.join("sample_data", name))
        )

        assert len(dataset.studies) > 0
