"""Run no-network Default R Evidence for the Fast Verification Lane."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__:
    from scripts import r_verification_support as r_support
else:
    import r_verification_support as r_support


RCMetaR_PACKAGE = Path("r") / "RCMetaR"
DEFAULT_R_VERIFIER = Path("scripts") / "verify_rcmetar_r_default.py"
R_MANIFEST_VALIDATOR = Path("scripts") / "validate_rcmetar_r_manifests.py"
R_BINARY_POLICY = Path("scripts") / "r_binary_policy.R"
R_POLICY_LOADER = Path("scripts") / "r_dependency_policy.py"
R_VERIFICATION_SUPPORT = Path("scripts") / "r_verification_support.py"


class DefaultREvidenceError(Exception):
    pass


def step(message: str) -> None:
    print(f"[RCMetaR-default-r] {message}", flush=True)


def run(
    command: list[str | Path], *, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    printable = " ".join(str(part) for part in command)
    step(printable)
    return subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_streamed(
    command: list[str | Path], *, cwd: Path, env: dict[str, str] | None = None
) -> None:
    printable = " ".join(str(part) for part in command)
    step(printable)
    result = subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        env=env,
        text=True,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise DefaultREvidenceError(
            f"R dependency installation failed with exit code {result.returncode}: {printable}"
        )


def require_success(result: subprocess.CompletedProcess[str], label: str) -> None:
    if result.returncode != 0:
        output = "\n".join(
            part for part in (result.stdout.strip(), result.stderr.strip()) if part
        )
        raise DefaultREvidenceError(
            f"{label} failed with exit code {result.returncode}: {output}"
        )


def installed_version_report(
    root: Path, python: str, rscript: Path, env: dict[str, str]
) -> dict:
    result = run(
        [
            python,
            R_MANIFEST_VALIDATOR,
            "--root",
            root,
            "--report-installed-versions",
            "--rscript",
            rscript,
        ],
        cwd=root,
        env=env,
    )
    require_success(result, "installed package version report")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise DefaultREvidenceError(
            "installed package version report did not emit JSON"
        ) from exc


def resolve_r_exe(root: Path, rscript: Path, env: dict[str, str]) -> Path:
    try:
        return r_support.resolve_r_exe(rscript, root, env)
    except r_support.RVerificationSupportError as exc:
        raise DefaultREvidenceError(str(exc)) from exc


def dependency_cache_key(
    root: Path, rscript: Path, env: dict[str, str], cran_repo: str
) -> str:
    try:
        return r_support.dependency_cache_key(
            root,
            rscript,
            env,
            cran_repo,
            (
                DEFAULT_R_VERIFIER,
                R_BINARY_POLICY,
                R_POLICY_LOADER,
                R_VERIFICATION_SUPPORT,
                r_support.DEPENDENCY_MANIFEST,
                RCMetaR_PACKAGE / "DESCRIPTION",
            ),
            "default-rdeps",
        )
    except r_support.RVerificationSupportError as exc:
        raise DefaultREvidenceError(str(exc)) from exc


def direct_archive_versions(root: Path) -> dict[str, str]:
    manifest = json.loads(
        (root / "config/r-dependencies.json").read_text(encoding="utf-8")
    )
    return {
        dependency["name"]: dependency["installed_version"]
        for dependency in manifest["direct_RCMetaR_dependencies"]
        if dependency.get("source") == "cran-archive"
    }


def binary_dependency_policy(root: Path) -> dict:
    try:
        return r_support.load_binary_dependency_policy(root)
    except r_support.RVerificationSupportError as exc:
        raise DefaultREvidenceError(str(exc)) from exc


def direct_dependency_policy(root: Path) -> tuple[list[str], dict[str, str]]:
    manifest = json.loads(
        (root / "config/r-dependencies.json").read_text(encoding="utf-8")
    )
    cran_packages = []
    archive_packages = {}
    for dependency in manifest["direct_RCMetaR_dependencies"]:
        source = dependency.get("source")
        name = dependency["name"]
        if source == "cran":
            cran_packages.append(name)
        elif source == "cran-archive":
            archive_packages[name] = dependency["installed_version"]
    return sorted(cran_packages), archive_packages


def install_direct_dependencies(
    root: Path, rscript: Path, library: Path, cran_repo: str, env: dict[str, str]
) -> None:
    policy = binary_dependency_policy(root)
    if cran_repo != policy["repository"]:
        raise DefaultREvidenceError(
            f"R dependency repository must match the manifest snapshot: {policy['repository']}"
        )
    r_code = """
args <- commandArgs(trailingOnly = TRUE)
repo_root <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)
lib <- normalizePath(args[[2]], winslash = "/", mustWork = FALSE)
dir.create(lib, recursive = TRUE, showWarnings = FALSE)
.libPaths(c(lib, .libPaths()))
source(file.path(repo_root, "scripts", "r_binary_policy.R"), local = TRUE)
policy <- load_rcms_r_binary_policy(repo_root)
install_rcms_binary_packages(policy, lib)
install_rcms_source_exception(policy, lib)
"""
    with tempfile.TemporaryDirectory(prefix="RCMetaR-default-r-install-") as temp_name:
        install_script = Path(temp_name) / "install-default-r-deps.R"
        install_script.write_text(r_code, encoding="utf-8")
        install_env = dict(env)
        install_env["RCMS_POLICY_PYTHON"] = sys.executable
        install_env["RCMS_CRAN_REPO"] = policy["repository"]
        run_streamed(
            [
                rscript,
                install_script,
                root,
                library,
            ],
            cwd=root,
            env=install_env,
        )


def install_and_load_RCMetaR(root: Path, rscript: Path, env: dict[str, str]) -> None:
    with tempfile.TemporaryDirectory(prefix="RCMetaR-default-r-") as temp_name:
        library = Path(temp_name) / "library"
        library.mkdir()
        r_exe = resolve_r_exe(root, rscript, env)
        install_env = dict(env)
        existing_libs = install_env.get("R_LIBS")
        install_env["R_LIBS"] = (
            str(library)
            if not existing_libs
            else str(library) + os.pathsep + existing_libs
        )
        install_env.setdefault("RPY2_CFFI_MODE", "API")

        result = run(
            [
                r_exe,
                "CMD",
                "INSTALL",
                f"--library={library}",
                root / RCMetaR_PACKAGE,
            ],
            cwd=root,
            env=install_env,
        )
        require_success(result, "local RCMetaR source install")

        smoke = run(
            [
                rscript,
                "-e",
                (
                    "library(RCMetaR); "
                    "stopifnot(!is.null(getS3method('print','summary.display',optional=TRUE))); "
                    "stopifnot(!is.null(getS3method('print','summary.data',optional=TRUE))); "
                    "cat('OK\\n')"
                ),
            ],
            cwd=root,
            env=install_env,
        )
        require_success(smoke, "local RCMetaR load smoke")


def verify(args: argparse.Namespace) -> None:
    root = args.root.resolve()
    python = (
        str(Path(args.python).absolute()) if Path(args.python).exists() else args.python
    )
    base_env = r_support.verification_base_env(dict(os.environ))
    policy = binary_dependency_policy(root)
    configured_repo = args.cran_repo or base_env.get("RCMS_CRAN_REPO")
    if configured_repo and configured_repo != policy["repository"]:
        raise DefaultREvidenceError(
            f"R dependency repository must match the manifest snapshot: {policy['repository']}"
        )
    cran_repo = policy["repository"]
    base_env["RCMS_CRAN_REPO"] = cran_repo
    base_env["RCMS_POLICY_PYTHON"] = python

    manifest_result = run(
        [python, R_MANIFEST_VALIDATOR, "--root", root], cwd=root, env=base_env
    )
    require_success(manifest_result, "manifest validation")

    rscript = r_support.resolve_rscript(args.rscript)
    if rscript is None:
        message = f"Rscript was not found: {args.rscript}; Default R Evidence limited to manifest validation"
        if args.require_r:
            raise DefaultREvidenceError(message)
        step(message)
        return

    if args.r_library_cache_root:
        cache_library = (
            args.r_library_cache_root.resolve()
            / dependency_cache_key(root, rscript, base_env, cran_repo)
            / "library"
        )
        cache_library.mkdir(parents=True, exist_ok=True)
        base_env["R_LIBS"] = str(cache_library)
        base_env["R_LIBS_USER"] = str(cache_library)

    if args.install_missing and args.r_library_cache_root:
        step("Preflighting manifest-owned native binary policy and dependency cache")
        install_direct_dependencies(
            root, rscript, Path(base_env["R_LIBS_USER"]), cran_repo, base_env
        )

    report = installed_version_report(root, python, rscript, base_env)
    missing = sorted(
        name for name, version in report["packages"].items() if version is None
    )
    wrong_versions = {
        name: {"expected": expected, "actual": report["packages"].get(name)}
        for name, expected in direct_archive_versions(root).items()
        if report["packages"].get(name) != expected
    }
    if missing or wrong_versions:
        message_parts = []
        if missing:
            message_parts.append("missing direct R packages: " + ", ".join(missing))
        if wrong_versions:
            message_parts.append(
                "wrong direct R package versions: "
                + json.dumps(wrong_versions, sort_keys=True)
            )
        message = (
            "; ".join(message_parts)
            + "; Default R Evidence limited to manifest validation"
        )
        if args.install_missing and args.r_library_cache_root:
            report = installed_version_report(root, python, rscript, base_env)
            missing = sorted(
                name for name, version in report["packages"].items() if version is None
            )
            wrong_versions = {
                name: {"expected": expected, "actual": report["packages"].get(name)}
                for name, expected in direct_archive_versions(root).items()
                if report["packages"].get(name) != expected
            }
            if not missing and not wrong_versions:
                install_and_load_RCMetaR(root, rscript, base_env)
                step("Default R Evidence complete")
                return
        if args.require_installed_packages:
            raise DefaultREvidenceError(message)
        step(message)
        return

    install_and_load_RCMetaR(root, rscript, base_env)
    step("Default R Evidence complete")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--rscript", default="Rscript")
    parser.add_argument("--require-r", action="store_true")
    parser.add_argument("--require-installed-packages", action="store_true")
    parser.add_argument("--r-library-cache-root", type=Path, default=None)
    parser.add_argument("--install-missing", action="store_true")
    parser.add_argument("--cran-repo", default=None)
    args = parser.parse_args(argv)
    try:
        verify(args)
    except DefaultREvidenceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
