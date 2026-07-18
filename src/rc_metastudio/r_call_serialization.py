import os
import sys
import threading
from contextlib import contextmanager
from functools import wraps


_r_call_lock = threading.RLock()
_transaction_state = threading.local()


def _main_thread_required():
    return (
        getattr(sys, "frozen", False)
        or os.environ.get("RCMS_ENFORCE_R_MAIN_THREAD") == "1"
    )


def _assert_main_thread():
    if (
        _main_thread_required()
        and threading.current_thread() is not threading.main_thread()
    ):
        raise RuntimeError(
            "In-process R operations must execute on the application main thread."
        )


@contextmanager
def r_transaction():
    """Serialize one complete R operation, including Python-side result parsing."""
    _assert_main_thread()
    with _r_call_lock:
        depth = getattr(_transaction_state, "depth", 0)
        _transaction_state.depth = depth + 1
        try:
            yield
        finally:
            _transaction_state.depth = depth


def r_transaction_active():
    return getattr(_transaction_state, "depth", 0) > 0


def require_r_transaction():
    if not r_transaction_active():
        raise RuntimeError(
            "Direct rpy2 access is permitted only inside an R transaction."
        )


def serialized_r_call(function):
    @wraps(function)
    def _serialized_r_call(*args, **kwargs):
        with r_transaction():
            return function(*args, **kwargs)

    return _serialized_r_call
