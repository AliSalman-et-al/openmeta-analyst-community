# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run developer-only application-shell lifecycle checks with a local backend."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _install_local_backend() -> None:
    """Keep shell checks independent of an installed R runtime."""
    from rc_metastudio import app_error_handler, r_backend, r_bridge
    from scripts.local_r_test_backend import create

    backend = create()
    for name, implementation in vars(backend).items():
        setattr(r_bridge, name, implementation)
    setattr(r_backend, "install_r_backend", lambda: r_bridge)
    setattr(app_error_handler, "install_global_exception_handler", lambda: None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--failure-stage", choices=("r-load", "meta-form"))
    args = parser.parse_args(argv)

    _install_local_backend()
    from tests.python.gui.support import automation_scenarios

    if args.failure_stage is not None:
        return automation_scenarios.start_shell_failure_smoke(args.failure_stage)
    return automation_scenarios.start_shell_smoke(
        require_native_window=args.native
    )


if __name__ == "__main__":
    raise SystemExit(main())
