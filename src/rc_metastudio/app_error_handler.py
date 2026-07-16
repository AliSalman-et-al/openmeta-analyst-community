import os
import inspect
import sys
import traceback
from datetime import datetime

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox

import settings


UNEXPECTED_ERROR_TITLE = "Unexpected error"
UNEXPECTED_ERROR_MESSAGE = (
    "Sorry, an unexpected error occurred. RC MetaStudio is still running, "
    "but the action could not be completed.\n\nDetails: {details}"
)

_previous_excepthook = None
_handling_exception = False
_active_context_menu = None


def enable_qt_native_high_dpi():
    """Enable Qt's logical-pixel scaling before constructing an application."""
    # Qt 6 enables high-DPI scaling and pixmaps natively.  This retained entry
    # point intentionally has no Qt 5 application attributes to toggle.
    return None


enable_qt_native_high_dpi()


def exception_log_path():
    base_path = settings.get_base_path()
    os.makedirs(base_path, exist_ok=True)
    return os.path.join(base_path, "rc-metastudio-error.log")


def log_exception(exc_type, exc_value, exc_traceback):
    path = exception_log_path()
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(path, "a", encoding="utf-8") as log_file:
        log_file.write("\n[%s] Unhandled exception\n" % timestamp)
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=log_file)
    return path


def show_unexpected_error(exc_value, parent=None):
    details = str(exc_value) or exc_value.__class__.__name__
    try:
        log_path = exception_log_path()
        message = UNEXPECTED_ERROR_MESSAGE.format(details=details)
        message += "\n\nA diagnostic trace was written to:\n%s" % log_path
    except Exception:
        message = UNEXPECTED_ERROR_MESSAGE.format(details=details)
    QMessageBox.critical(parent, UNEXPECTED_ERROR_TITLE, message)


def handle_exception(exc_type, exc_value, exc_traceback, parent=None):
    global _handling_exception
    if issubclass(exc_type, KeyboardInterrupt):
        if _previous_excepthook is not None:
            _previous_excepthook(exc_type, exc_value, exc_traceback)
        else:
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    if _handling_exception:
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        return

    _handling_exception = True
    try:
        log_exception(exc_type, exc_value, exc_traceback)
        app = QApplication.instance()
        if app is not None:
            show_unexpected_error(exc_value, parent=parent)
        else:
            traceback.print_exception(exc_type, exc_value, exc_traceback)
    finally:
        _handling_exception = False


def install_global_exception_handler():
    global _previous_excepthook
    if sys.excepthook is handle_exception:
        return
    _previous_excepthook = sys.excepthook
    sys.excepthook = handle_exception


def _call_with_compatible_signal_args(callback, args, kwargs):
    try:
        signature = inspect.signature(callback)
    except (TypeError, ValueError):
        return callback(*args, **kwargs)

    parameters = list(signature.parameters.values())
    accepts_varargs = any(
        parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in parameters
    )
    accepts_varkwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters
    )

    if not accepts_varargs:
        positional_parameters = [
            parameter
            for parameter in parameters
            if parameter.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        args = args[: len(positional_parameters)]

    if not accepts_varkwargs:
        keyword_names = {
            parameter.name
            for parameter in parameters
            if parameter.kind
            in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        }
        kwargs = {
            name: value for name, value in kwargs.items() if name in keyword_names
        }

    return callback(*args, **kwargs)


def safe_slot(callback, parent=None):
    def _safe_slot(*args, **kwargs):
        try:
            return _call_with_compatible_signal_args(callback, args, kwargs)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            handle_exception(
                type(e), e, e.__traceback__, parent=_resolve_parent(parent)
            )
            return None

    return _safe_slot


class SafeSignalConnection(object):
    def __init__(self, signal, callback, parent=None):
        self.signal = signal
        self.parent = parent
        self.slot = None
        self.replace(callback, parent=parent)

    def disconnect(self):
        if self.slot is None:
            return
        try:
            self.signal.disconnect(self.slot)
        except (TypeError, RuntimeError):
            pass
        self.slot = None

    def replace(self, callback, parent=None):
        self.disconnect()
        if parent is not None:
            self.parent = parent
        self.slot = safe_slot(callback, parent=self.parent)
        self.signal.connect(self.slot)
        return self


def connect_safely(signal, callback, parent=None):
    return SafeSignalConnection(signal, callback, parent=parent)


def _clear_active_context_menu(menu):
    global _active_context_menu
    if _active_context_menu is menu:
        _active_context_menu = None


def is_context_menu_active():
    popup = QApplication.activePopupWidget()
    if isinstance(popup, QMenu):
        return True
    return _active_context_menu is not None


def popup_context_menu(menu, pos, parent=None, event=None):
    global _active_context_menu

    if is_context_menu_active():
        if event is not None:
            event.accept()
        return False

    _active_context_menu = menu
    try:
        menu.aboutToHide.connect(lambda: _clear_active_context_menu(menu))
        if hasattr(menu, "destroyed"):
            menu.destroyed.connect(lambda *_args: _clear_active_context_menu(menu))
        menu.popup(pos)
        if event is not None:
            event.accept()
        return True
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        _clear_active_context_menu(menu)
        handle_exception(type(e), e, e.__traceback__, parent=_resolve_parent(parent))
        if event is not None:
            event.accept()
        return False


def should_suppress_context_menu_event(event):
    return event.type() == QEvent.Type.ContextMenu and is_context_menu_active()


def _resolve_parent(parent):
    if callable(parent):
        try:
            return parent()
        except Exception:
            return None
    return parent


class SafeApplication(QApplication):
    def notify(self, receiver, event):
        try:
            if should_suppress_context_menu_event(event):
                event.accept()
                return True
            return super(SafeApplication, self).notify(receiver, event)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            handle_exception(type(e), e, e.__traceback__, parent=receiver)
            return False


def get_or_create_application(argv):
    install_global_exception_handler()
    return QApplication.instance() or SafeApplication(argv)
