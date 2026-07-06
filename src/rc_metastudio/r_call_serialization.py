import threading
from functools import wraps


_r_call_lock = threading.RLock()


def serialized_r_call(function):
    @wraps(function)
    def _serialized_r_call(*args, **kwargs):
        with _r_call_lock:
            return function(*args, **kwargs)

    return _serialized_r_call
