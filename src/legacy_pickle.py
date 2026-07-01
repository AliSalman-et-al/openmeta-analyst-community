import io
import pickle

from PyQt5 import QtCore, QtGui


PYQT4_PREFIX = "Py" + "Qt4."
PYQT4_QTCORE = PYQT4_PREFIX + "QtCore"
PYQT4_QTGUI = PYQT4_PREFIX + "QtGui"


def load_legacy_pickle(path):
    return load_project_pickle(path)


def loads_legacy_pickle(data):
    return loads_project_pickle(data)


def load_project_pickle(path):
    with open(path, "rb") as handle:
        return loads_project_pickle(handle.read())


def loads_project_pickle(data):
    try:
        return _loads(data)
    except (
        pickle.UnpicklingError,
        EOFError,
        ValueError,
        TypeError,
        AttributeError,
        ImportError,
        UnicodeError,
    ):
        return _loads(data.replace(b"\r\n", b"\n"))


def _loads(data):
    return ProjectFileUnpickler(io.BytesIO(data), encoding="latin1").load()


class ProjectFileUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module == "sip" and name == "_unpickle_type":
            return _unpickle_qt4_sip_type

        replacement = _qt4_replacement(module, name)
        if replacement is not None:
            return replacement

        return super(ProjectFileUnpickler, self).find_class(module, name)


LegacyProjectUnpickler = ProjectFileUnpickler


def _unpickle_qt4_sip_type(module, name, args):
    replacement = _qt4_replacement(module, name)
    if replacement is None:
        return _coerce_constructor_args(args)
    return replacement(*args)


def _qt4_replacement(module, name):
    if not module.startswith(PYQT4_PREFIX):
        return None

    replacements = _QT4_CLASS_REPLACEMENTS.get((module, name))
    if replacements is not None:
        return replacements

    if module == PYQT4_QTCORE:
        return getattr(QtCore, name, None)
    if module == PYQT4_QTGUI:
        return getattr(QtGui, name, None)
    return None


def _construct_text(value=""):
    return _to_text(value)


def _construct_text_list(value=None):
    if value is None:
        return []
    if isinstance(value, (str, bytes, bytearray, memoryview, QtCore.QByteArray)):
        return [_to_text(value)]
    return [_to_text(item) for item in value]


def _construct_variant(value=None):
    return _normalize_qt_value(value)


def _construct_byte_array(value=b""):
    return QtCore.QByteArray(_to_bytes(value))


def _coerce_constructor_args(args):
    if not args:
        return None
    if len(args) == 1:
        return _normalize_qt_value(args[0])
    return tuple(_normalize_qt_value(arg) for arg in args)


def _normalize_qt_value(value):
    if isinstance(value, QtCore.QByteArray):
        return value
    if isinstance(value, tuple):
        return tuple(_normalize_qt_value(item) for item in value)
    if isinstance(value, list):
        return [_normalize_qt_value(item) for item in value]
    if isinstance(value, dict):
        return {
            _normalize_qt_value(key): _normalize_qt_value(item)
            for key, item in value.items()
        }
    return value


def _to_text(value):
    if value is None:
        return ""
    if isinstance(value, QtCore.QByteArray):
        value = bytes(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin1")
    if hasattr(value, "toString"):
        return _to_text(value.toString())
    return str(value)


def _to_bytes(value):
    if value is None:
        return b""
    if isinstance(value, QtCore.QByteArray):
        return bytes(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    return bytes(value)


_QT4_CLASS_REPLACEMENTS = {
    (PYQT4_QTCORE, "QString"): _construct_text,
    (PYQT4_QTCORE, "QStringList"): _construct_text_list,
    (PYQT4_QTCORE, "QVariant"): _construct_variant,
    (PYQT4_QTCORE, "QByteArray"): _construct_byte_array,
}
