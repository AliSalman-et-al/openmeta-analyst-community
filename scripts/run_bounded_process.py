#!/usr/bin/env python3
"""Run one package-smoke process with bounded, process-tree-aware cleanup."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any, cast


_killpg = cast(Any, getattr(os, "killpg", None))
_getpgid = cast(Any, getattr(os, "getpgid", None))
_sigkill = cast(Any, getattr(signal, "SIGKILL", None))


def _process_group_exists(process_group_id: int) -> bool:
    try:
        _killpg(process_group_id, 0)
        return True
    except ProcessLookupError:
        return False


def _wait_for_group_exit(process_group_id: int, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not _process_group_exists(process_group_id):
            return True
        time.sleep(0.05)
    return not _process_group_exists(process_group_id)


def _terminate_posix_group(process: subprocess.Popen[bytes]) -> None:
    process_group_id = _getpgid(process.pid)
    try:
        _killpg(process_group_id, signal.SIGTERM)
    except ProcessLookupError:
        process.wait(timeout=1)
        return
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass
    if _process_group_exists(process_group_id):
        try:
            _killpg(process_group_id, _sigkill)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("package process-group leader survived SIGKILL") from exc
    if not _wait_for_group_exit(process_group_id, 5):
        raise RuntimeError("package process group remained alive after SIGKILL")


def _terminate_owned_pid(path: Path | None) -> None:
    if path is None or not path.is_file() or os.name != "posix":
        return
    raw = path.read_text(encoding="utf-8").strip()
    if not raw.isdigit():
        raise RuntimeError("owned package PID file is malformed")
    pid = int(raw)
    if pid <= 1:
        raise RuntimeError("owned package PID is unsafe")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    raise RuntimeError("owned package process remained alive after SIGKILL")


def run_bounded(
    command: list[str], *, timeout_seconds: int,
    stdout_path: Path | None = None, stderr_path: Path | None = None,
    owned_pid_path: Path | None = None,
) -> int:
    if not command:
        raise ValueError("a child command is required")
    if timeout_seconds < 1:
        raise ValueError("timeout must be positive")
    for path in (stdout_path, stderr_path):
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
    stdout_stream = stdout_path.open("ab") if stdout_path is not None else None
    stderr_stream = stderr_path.open("ab") if stderr_path is not None else None
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=stdout_stream,
            stderr=stderr_stream,
            start_new_session=os.name == "posix",
        )
        try:
            return process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            print(
                f"package process exceeded its {timeout_seconds}-second watchdog: {command!r}",
                file=sys.stderr,
            )
            if os.name == "posix":
                try:
                    _terminate_posix_group(process)
                finally:
                    _terminate_owned_pid(owned_pid_path)
            else:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            return 124
    finally:
        if stdout_stream is not None:
            stdout_stream.close()
        if stderr_stream is not None:
            stderr_stream.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--stdout", type=Path)
    parser.add_argument("--stderr", type=Path)
    parser.add_argument("--owned-pid-file", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        return run_bounded(
            command,
            timeout_seconds=args.timeout_seconds,
            stdout_path=args.stdout,
            stderr_path=args.stderr,
            owned_pid_path=args.owned_pid_file,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"bounded package process failed: {exc}", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
