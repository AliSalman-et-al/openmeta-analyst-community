import ast
import os
from pathlib import Path
import sys
import threading


sys.path.insert(0, os.path.abspath("src"))

from rc_metastudio import r_call_serialization


def test_application_code_uses_only_serialized_r_backend_entrypoints():
    root = Path(__file__).resolve().parents[3]
    allowed = {
        "meta_py_r.py",
        "meta_py_r_backend.py",
        "launch.py",
        "qt6_macos_feasibility.py",
    }
    offenders = []

    for path in (root / "src").rglob("*.py"):
        if path.name in allowed:
            continue
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(module):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id in {
                "execute_r_string",
                "execute_r_function",
            }:
                offenders.append(f"{path.relative_to(root)}:{node.lineno}")
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "r"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "ro"
            ):
                offenders.append(f"{path.relative_to(root)}:{node.lineno}")

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


def test_nested_result_parsing_remains_inside_one_reentrant_transaction():
    observations = []

    @r_call_serialization.serialized_r_call
    def parse_summary():
        observations.append(r_call_serialization.r_transaction_active())

    @r_call_serialization.serialized_r_call
    def analyze_and_parse():
        observations.append(r_call_serialization.r_transaction_active())
        parse_summary()
        observations.append(r_call_serialization.r_transaction_active())

    analyze_and_parse()
    assert observations == [True, True, True]
    assert r_call_serialization.r_transaction_active() is False


def test_direct_rpy2_access_requires_gateway_transaction():
    try:
        r_call_serialization.require_r_transaction()
    except RuntimeError as exc:
        assert "R transaction" in str(exc)
    else:
        raise AssertionError("direct rpy2 access was accepted outside the gateway")


def test_packaged_r_gateway_rejects_background_thread(monkeypatch):
    monkeypatch.setenv("RCMS_ENFORCE_R_MAIN_THREAD", "1")
    errors = []

    @r_call_serialization.serialized_r_call
    def guarded_call():
        return None

    thread = threading.Thread(target=lambda: _capture_error(guarded_call, errors))
    thread.start()
    thread.join(timeout=2)
    assert len(errors) == 1
    assert "main thread" in str(errors[0])


def _capture_error(function, errors):
    try:
        function()
    except Exception as exc:
        errors.append(exc)
