import io
import pickle


class ProjectFileFormatError(ValueError):
    pass


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
            return _unpickle_serialized_qt_value

        constructor = _serialized_qt_constructor(module, name)
        if constructor is not None:
            return constructor
        if _is_serialized_old_qt_module(module):
            raise _unsupported_serialized_qt_value(module, name)

        return super(ProjectFileUnpickler, self).find_class(module, name)


def _unpickle_serialized_qt_value(module, name, args):
    module = _to_text(module)
    name = _to_text(name)
    constructor = _serialized_qt_constructor(module, name)
    if constructor is None:
        raise _unsupported_serialized_qt_value(module, name)
    return constructor(*args)


def _unsupported_serialized_qt_value(module, name):
    return ProjectFileFormatError(
        "This project contains serialized Qt data from an older RC MetaStudio "
        "release that this version cannot migrate: %s.%s" % (module, name)
    )


def _serialized_qt_constructor(module, name):
    if not _is_serialized_old_qt_module(module):
        return None

    constructor = _OLD_QTCORE_VALUE_CONSTRUCTORS.get((module, name))
    if constructor is not None:
        return constructor

    return _current_qt_value_class(module, name)


def _is_serialized_old_qt_module(module):
    return isinstance(module, str) and module.startswith(_old_qt_package() + ".")


def _old_qt_package():
    return "Py" + "Qt4"


def _old_qt_module(name):
    return _old_qt_package() + "." + name


def _current_qt_value_class(module, name):
    if module == _old_qt_module("QtCore"):
        from PyQt5 import QtCore

        return getattr(QtCore, name, None)
    if module == _old_qt_module("QtGui"):
        from PyQt5 import QtGui

        return getattr(QtGui, name, None)
    return None


def _construct_text(value=""):
    return _to_text(value)


def _construct_text_list(value=None):
    if value is None:
        return []
    if isinstance(value, (str, bytes, bytearray, memoryview)):
        return [_to_text(value)]
    return [_to_text(item) for item in value]


def _construct_variant(value=None):
    return _normalize_project_value(value)


def _construct_byte_array(value=b""):
    from PyQt5 import QtCore

    return QtCore.QByteArray(_to_bytes(value))


def _normalize_project_value(value):
    if isinstance(value, tuple):
        return tuple(_normalize_project_value(item) for item in value)
    if isinstance(value, list):
        return [_normalize_project_value(item) for item in value]
    if isinstance(value, dict):
        return {
            _normalize_project_value(key): _normalize_project_value(item)
            for key, item in value.items()
        }
    return value


def _to_text(value):
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin1")
    return str(value)


def _to_bytes(value):
    if value is None:
        return b""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    return bytes(value)


_OLD_QTCORE_VALUE_CONSTRUCTORS = {
    (_old_qt_module("QtCore"), "Q" + "String"): _construct_text,
    (_old_qt_module("QtCore"), "Q" + "StringList"): _construct_text_list,
    (_old_qt_module("QtCore"), "Q" + "Variant"): _construct_variant,
    (_old_qt_module("QtCore"), "Q" + "ByteArray"): _construct_byte_array,
}
