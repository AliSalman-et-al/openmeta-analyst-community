import os
from pathlib import Path
import sys
import threading


sys.path.insert(0, os.path.abspath("src"))

import r_call_serialization


def test_application_code_does_not_bypass_serialized_r_backend_entrypoints():
    root = Path(__file__).resolve().parents[3]
    offenders = []

    for path in (root / "src").glob("*.py"):
        if path.name in {"meta_py_r.py", "meta_py_r_backend.py"}:
            continue
        text = path.read_text(encoding="utf-8")
        if "meta_py_r.ro.r" in text:
            offenders.append(str(path.relative_to(root)))

    assert offenders == []


def test_r_backend_calls_are_serialized_across_threads():
    entered_first_call = threading.Event()
    release_first_call = threading.Event()
    second_call_attempted = threading.Event()
    second_call_entered = threading.Event()
    active_calls = 0
    max_active_calls = 0

    @r_call_serialization.serialized_r_call
    def guarded_call(name):
        nonlocal active_calls, max_active_calls

        active_calls += 1
        max_active_calls = max(max_active_calls, active_calls)
        try:
            if name == "first":
                entered_first_call.set()
                assert release_first_call.wait(timeout=2)
            else:
                second_call_entered.set()
        finally:
            active_calls -= 1

    def run_second_call():
        second_call_attempted.set()
        guarded_call("second")

    first_thread = threading.Thread(target=guarded_call, args=("first",))
    second_thread = threading.Thread(target=run_second_call)

    first_thread.start()
    assert entered_first_call.wait(timeout=2)
    second_thread.start()
    assert second_call_attempted.wait(timeout=2)
    assert second_call_entered.wait(timeout=0.1) is False
    release_first_call.set()

    first_thread.join(timeout=2)
    second_thread.join(timeout=2)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert second_call_entered.is_set()
    assert max_active_calls == 1
