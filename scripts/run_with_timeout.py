"""Run one verification command with inherited output and a hard timeout."""

from __future__ import annotations

import argparse
import os
import shlex
import signal
import subprocess
import sys


TIMEOUT_EXIT_CODE = 124


def _display_command(command: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        terminated = subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if terminated.returncode != 0:
            details = "\n".join(
                part.strip()
                for part in (terminated.stdout, terminated.stderr)
                if part.strip()
            )
            raise RuntimeError(
                f"taskkill /T /F failed for process tree {process.pid} "
                f"with exit code {terminated.returncode}: {details or 'no diagnostics'}"
            )
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(
                f"taskkill reported success but process {process.pid} remained alive"
            ) from error
        return

    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass

    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        group_remains = False
    else:
        group_remains = True
    if group_remains:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.wait(timeout=5)


def run(command: list[str], *, timeout_seconds: float, label: str) -> int:
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        creationflags=creationflags,
        start_new_session=os.name != "nt",
    )
    try:
        return process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        print(
            f"{label} timed out after {timeout_seconds:g} seconds: "
            f"{_display_command(command)}",
            file=sys.stderr,
            flush=True,
        )
        _terminate_process_tree(process)
        return TIMEOUT_EXIT_CODE
    except BaseException:
        _terminate_process_tree(process)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    return run(command, timeout_seconds=args.timeout_seconds, label=args.label)


if __name__ == "__main__":
    raise SystemExit(main())
