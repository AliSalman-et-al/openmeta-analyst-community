import os
import sys
import traceback
from datetime import datetime

from PyQt5.QtWidgets import QApplication, QMessageBox

import settings


UNEXPECTED_ERROR_TITLE = "Unexpected error"
UNEXPECTED_ERROR_MESSAGE = (
    "Sorry, an unexpected error occurred. OpenMeta[Analyst] is still running, "
    "but the action could not be completed.\n\nDetails: {details}"
)

_previous_excepthook = None
_handling_exception = False


def exception_log_path():
    base_path = settings.get_base_path()
    os.makedirs(base_path, exist_ok=True)
    return os.path.join(base_path, "openmeta-analyst-error.log")


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


def safe_slot(callback, parent=None):
    def _safe_slot(*args, **kwargs):
        try:
            return callback(*args, **kwargs)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            handle_exception(type(e), e, e.__traceback__, parent=_resolve_parent(parent))
            return None

    return _safe_slot


def connect_safely(signal, callback, parent=None):
    signal.connect(safe_slot(callback, parent=parent))


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
            return super(SafeApplication, self).notify(receiver, event)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            handle_exception(type(e), e, e.__traceback__, parent=receiver)
            return False


def get_or_create_application(argv):
    install_global_exception_handler()
    return QApplication.instance() or SafeApplication(argv)
