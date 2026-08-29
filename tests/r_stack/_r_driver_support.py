# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared execution and bootstrap helpers for direct RCMetaR R drivers."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap

import pytest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_REQUIRED = os.getenv("RCMS_R_STACK_REQUIRED") == "1"

RCMETAR_BOOTSTRAP = textwrap.dedent(
    r"""
    repo <- normalizePath(__REPO_ROOT__, winslash = "/")
    suppressPackageStartupMessages(source(file.path(repo, "r/RCMetaR/R/classes.R")))
    suppressPackageStartupMessages(source(file.path(repo, "r/RCMetaR/R/utilities.R")))
    suppressPackageStartupMessages(source(file.path(repo, "r/RCMetaR/R/rcmetar-core.R")))
    suppressPackageStartupMessages(source(file.path(repo, "r/RCMetaR/R/diagnostic_methods.R")))
    """
).strip()


def build_r_driver(driver: str) -> str:
    """Expand the canonical direct-source bootstrap into an R driver."""

    bootstrap = RCMETAR_BOOTSTRAP.replace(
        "__REPO_ROOT__", repr(REPO_ROOT).replace("\\", "/")
    )
    return textwrap.dedent(driver).replace("__RCMETAR_BOOTSTRAP__", bootstrap)


def run_r_driver(driver: str) -> None:
    """Run a direct R driver, skipping locally but failing in the required lane."""

    rscript = shutil.which("Rscript")
    if not rscript:
        message = "Rscript executable not found"
        if _REQUIRED:
            pytest.fail(message)
        pytest.skip(message)

    result = subprocess.run(
        [rscript, "-"],
        cwd=REPO_ROOT,
        input=driver,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if result.returncode == 42:
        message = result.stdout.strip() or "R driver prerequisites are unavailable"
        if _REQUIRED:
            pytest.fail(message)
        pytest.skip(message)

    assert result.returncode == 0, "driver failed (rc=%s)\nSTDOUT:\n%s\nSTDERR:\n%s" % (
        result.returncode,
        result.stdout[-2000:],
        result.stderr[-2000:],
    )
    assert "OK" in result.stdout


def run_python_driver(
    driver: str, *, env: dict[str, str]
) -> subprocess.CompletedProcess:
    """Run an embedded-Python driver with the same required-lane policy."""

    result = subprocess.run(
        [sys.executable, "-c", driver],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=env,
    )
    if result.returncode == 42:
        message = (
            result.stdout.strip() or "Python/R bridge prerequisites are unavailable"
        )
        if _REQUIRED:
            pytest.fail(message)
        pytest.skip(message)

    assert result.returncode == 0, "driver failed (rc=%s)\nSTDOUT:\n%s\nSTDERR:\n%s" % (
        result.returncode,
        result.stdout[-2000:],
        result.stderr[-2000:],
    )
    assert "OK" in result.stdout
    return result
