# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#!/usr/bin/env python3
"""Run the maintained source verification lanes."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

if __package__:
    from . import r_verification_support as r_support
else:
    import r_verification_support as r_support


class VerificationError(RuntimeError):
    """A command-line or verification setup error."""


def discover_repo_root(start: Path | None = None) -> Path:
    """Find the repository containing both ``pyproject.toml`` and ``scripts``."""
    current = (start or Path(__file__).resolve()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "scripts"
        ).is_dir():
            return candidate
    raise VerificationError(f"could not discover repository root from {current}")


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = discover_repo_root(SCRIPT_DIR)
DEFAULT_BUILD_ROOT = REPO_ROOT / "build" / "qt6-verification"
DEFAULT_R_LIBRARY_CACHE = REPO_ROOT / "artifacts" / "r-default-library-cache"
FULL_R_LIBRARY_CACHE = REPO_ROOT / "artifacts" / "r-library-cache"
SMOKE_TESTS = (
    "tests/analysis_regression/golden/test_analysis_regression_compare.py::"
    "test_golden_summary_parser_reads_current_RCMetaR_summary_display",
    "tests/python/fast/test_project_format.py::"
    "test_all_committed_samples_match_the_frozen_semantics_and_round_trip",
    "tests/python/fast/test_qt6_build_slice.py::"
    "test_binary_resource_registers_and_exposes_icon_and_svg",
)


def write_step(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    """Run one child command and stop at the first failure."""
    write_step("$ " + " ".join(command))
    try:
        subprocess.run(command, cwd=REPO_ROOT, env=env, check=True)
    except FileNotFoundError as exc:
        raise VerificationError(f"command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise VerificationError(
            f"command failed with exit code {exc.returncode}: {' '.join(command)}"
        ) from exc


def sync_environment() -> None:
    write_step("Syncing locked verification environment with uv")
    run(["uv", "sync", "--locked"])


def prepare_qt_environment(build_root: Path) -> dict[str, str]:
    run(
        [
            sys.executable,
            "scripts/build_qt6.py",
            "generate",
            "--build-root",
            str(build_root),
        ]
    )
    generated_package = build_root / "generated" / "rc_metastudio"
    generated_forms = generated_package / "forms"
    env = dict(os.environ)
    env["RCMS_QT6_BUILD_ROOT"] = str(build_root)
    path_entries = [str(generated_package), str(generated_forms)]
    if env.get("PYTHONPATH"):
        path_entries.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(path_entries)
    return env


def preflight(env: dict[str, str]) -> None:
    write_step("Collecting pytest nodes with strict marker validation")
    run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--strict-markers",
            "tests",
            "--collect-only",
            "-qq",
        ],
        env=env,
    )


def bounded_workers(requested: int) -> int:
    if requested < 0:
        raise VerificationError("--fast-workers must be zero or greater")
    return min(requested, max(1, os.cpu_count() or 1), 8)


def run_pytest(nodes: list[str], *, env: dict[str, str], workers: int = 0) -> None:
    command = [sys.executable, "-m", "pytest", "--strict-markers", *nodes]
    worker_count = bounded_workers(workers)
    if worker_count > 1:
        command += ["--dist", "loadfile", "-n", str(worker_count)]
    run(command, env=env)


def selected_rscript(args: argparse.Namespace) -> str:
    requested = args.rscript
    if args.r_runtime_root:
        candidates = r_support.rscript_paths_for_r_home(args.r_runtime_root)
        for candidate in candidates:
            if candidate.exists():
                return str(candidate.resolve())
        if requested and requested != "Rscript":
            raise VerificationError(f"Rscript was not found at '{requested}'.")
        raise VerificationError(
            f"Rscript was not found in selected R runtime at '{args.r_runtime_root}'."
        )
    resolved = r_support.resolve_rscript(requested or "Rscript")
    if resolved is not None:
        return str(resolved)
    if requested and requested != "Rscript":
        raise VerificationError(f"Rscript was not found at '{requested}'.")
    return "Rscript"


def run_default_r_evidence(args: argparse.Namespace) -> None:
    command = [
        sys.executable,
        "scripts/verify_rcmetar_r_default.py",
        "--rscript",
        selected_rscript(args),
    ]
    if args.require_r_evidence:
        command += [
            "--require-r",
            "--require-installed-packages",
            "--install-missing",
            "--r-library-cache-root",
            str(args.r_library_cache_root or DEFAULT_R_LIBRARY_CACHE),
        ]
    write_step("Verifying Default R Evidence")
    run(command)


def run_source_lane(args: argparse.Namespace, *, smoke: bool) -> None:
    if args.sync:
        sync_environment()
    else:
        write_step("Skipping dependency sync for warm local verification")
    build_root = (REPO_ROOT / args.build_root).resolve()
    env = prepare_qt_environment(build_root)
    preflight(env)
    if smoke:
        write_step("Running smoke pytest nodes")
        run_pytest(list(SMOKE_TESTS), env=env)
        if not args.skip_r_evidence:
            run_default_r_evidence(args)
    else:
        write_step("Running fast and golden pytest lanes")
        run_pytest(
            ["tests/python/fast", "tests/analysis_regression/golden"],
            env=env,
            workers=args.fast_workers,
        )
        if not args.skip_r_evidence:
            run_default_r_evidence(args)


def run_full_r_stack(args: argparse.Namespace) -> None:
    if args.sync:
        sync_environment()
    else:
        write_step("Skipping dependency sync for warm local R verification")
    build_root = (REPO_ROOT / args.build_root).resolve()
    env = prepare_qt_environment(build_root)
    command = [
        sys.executable,
        "scripts/verify_rcmetar_r_stack.py",
        "--rscript",
        selected_rscript(args),
        "--r-library-cache-root",
        str(args.r_library_cache_root or FULL_R_LIBRARY_CACHE),
    ]
    write_step("Delegating Full R Stack Evidence")
    run(command, env=env)


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    subparsers = cli.add_subparsers(dest="lane", required=True)

    def add_rscript_options(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--rscript")
        subparser.add_argument("--r-runtime-root")
        subparser.add_argument(
            "--r-library-cache-root",
            "--r-package-cache-root",
            dest="r_library_cache_root",
            type=Path,
        )

    def add_source_options(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--sync", action="store_true")
        r_evidence = subparser.add_mutually_exclusive_group()
        r_evidence.add_argument("--require-r-evidence", action="store_true")
        r_evidence.add_argument("--skip-r-evidence", action="store_true")
        add_rscript_options(subparser)

    smoke = subparsers.add_parser("smoke", help="run the representative smoke lane")
    add_source_options(smoke)
    smoke.add_argument("--build-root", default=DEFAULT_BUILD_ROOT, type=Path)

    fast = subparsers.add_parser(
        "fast", help="run fast, golden, and Default R Evidence"
    )
    add_source_options(fast)
    fast.add_argument(
        "--fast-workers",
        default=os.environ.get("RCMS_FAST_WORKERS", "4"),
        type=int,
    )
    fast.add_argument("--build-root", default=DEFAULT_BUILD_ROOT, type=Path)

    r_stack = subparsers.add_parser("r-stack", help="run Full R Stack Evidence")
    r_stack.add_argument("--sync", action="store_true")
    add_rscript_options(r_stack)
    r_stack.add_argument("--build-root", default=DEFAULT_BUILD_ROOT, type=Path)
    return cli


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.lane == "smoke":
            run_source_lane(args, smoke=True)
        elif args.lane == "fast":
            run_source_lane(args, smoke=False)
        else:
            run_full_r_stack(args)
    except VerificationError as exc:
        print(f"verification failed: {exc}", file=sys.stderr)
        return 1
    write_step(f"{args.lane} verification complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
