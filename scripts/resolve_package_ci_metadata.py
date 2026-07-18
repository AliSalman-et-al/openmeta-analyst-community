#!/usr/bin/env python3
"""Resolve cross-platform package metadata for GitHub Actions."""

from __future__ import annotations

import os
import argparse
import shutil
import subprocess
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def r_value(rscript: str, expression: str) -> str:
    return subprocess.check_output(
        [rscript, "-e", "cat(%s)" % expression], cwd=ROOT, text=True
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version-only", action="store_true",
        help="emit only pyproject project.version without locating or invoking Rscript",
    )
    args = parser.parse_args()
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        raise SystemExit("GITHUB_OUTPUT is required.")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    values = {"version": project["project"]["version"]}
    if not args.version_only:
        rscript = shutil.which("Rscript")
        if not rscript:
            raise SystemExit("Rscript is not available on PATH.")
        values.update({
            "r-version": r_value(rscript, "paste0('R-', getRversion())"),
            "r-runtime-root": r_value(
                rscript, "normalizePath(R.home(), winslash='/', mustWork=TRUE)"
            ),
            "rscript": Path(rscript).resolve(),
        })
    with Path(output_path).open("a", encoding="utf-8") as output:
        for key, value in values.items():
            output.write("%s=%s\n" % (key, value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
