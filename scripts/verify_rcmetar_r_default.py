"""Run no-network Default R Evidence for the Fast Verification Lane."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


RCMetaR_PACKAGE = Path("r") / "RCMetaR"
DEFAULT_R_VERIFIER = Path("scripts") / "verify_rcmetar_r_default.py"
R_MANIFEST_VALIDATOR = Path("scripts") / "validate_rcmetar_r_manifests.py"
DEFAULT_CRAN_REPO = "https://cloud.r-project.org"


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


def _candidate_rscript_names() -> list[str]:
    return ["Rscript.exe", "Rscript"] if os.name == "nt" else ["Rscript"]


def _rscript_paths_for_r_home(r_home: str | Path | None) -> list[Path]:
    if not r_home:
        return []
    root = Path(r_home)
    return [root / "bin" / name for name in _candidate_rscript_names()] + [
        root / "bin" / "x64" / name for name in _candidate_rscript_names()
    ]


def _r_home_from_r_command(env: dict[str, str]) -> Path | None:
    r_command = shutil.which("R", path=env.get("PATH"))
    if not r_command:
        return None
    result = subprocess.run(
        [r_command, "RHOME"],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    r_home = result.stdout.strip()
    return Path(r_home) if result.returncode == 0 and r_home else None


def _windows_registry_r_homes() -> list[Path]:
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []

    homes: list[Path] = []
    roots = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
    keys = (
        r"Software\R-core\R",
        r"Software\WOW6432Node\R-core\R",
    )
    for root in roots:
        for key_name in keys:
            try:
                with winreg.OpenKey(root, key_name) as key:
                    try:
                        install_path, _ = winreg.QueryValueEx(key, "InstallPath")
                    except OSError:
                        install_path = None
                    if install_path:
                        homes.append(Path(install_path))
                    try:
                        current_version, _ = winreg.QueryValueEx(key, "Current Version")
                    except OSError:
                        current_version = None
                    if current_version:
                        try:
                            with winreg.OpenKey(key, current_version) as version_key:
                                version_install_path, _ = winreg.QueryValueEx(
                                    version_key, "InstallPath"
                                )
                                if version_install_path:
                                    homes.append(Path(version_install_path))
                        except OSError:
                            pass
                    index = 0
                    while True:
                        try:
                            version = winreg.EnumKey(key, index)
                        except OSError:
                            break
                        index += 1
                        try:
                            with winreg.OpenKey(key, version) as version_key:
                                version_install_path, _ = winreg.QueryValueEx(
                                    version_key, "InstallPath"
                                )
                                if version_install_path:
                                    homes.append(Path(version_install_path))
                        except OSError:
                            continue
            except OSError:
                continue
    return homes


def _common_rscript_candidates(env: dict[str, str] | None = None) -> list[Path]:
    env = env or os.environ
    candidates: list[Path] = []
    if env.get("RCMS_RSCRIPT"):
        candidates.append(Path(env["RCMS_RSCRIPT"]))
    for variable in ("RCMS_R_HOME", "R_HOME"):
        candidates.extend(_rscript_paths_for_r_home(env.get(variable)))
    r_home = _r_home_from_r_command(env)
    candidates.extend(_rscript_paths_for_r_home(r_home))
    for r_home in _windows_registry_r_homes():
        candidates.extend(_rscript_paths_for_r_home(r_home))
    return candidates


def resolve_rscript(name: str, env: dict[str, str] | None = None) -> Path | None:
    env = env or os.environ
    explicit = name and name != "Rscript"
    if explicit:
        requested = Path(name)
        if requested.exists():
            return requested.resolve()
        resolved = shutil.which(name, path=env.get("PATH"))
        return Path(resolved).resolve() if resolved else None

    for candidate in _common_rscript_candidates(env):
        if candidate.exists():
            return candidate.resolve()
    resolved = shutil.which(name or "Rscript", path=env.get("PATH"))
    if resolved:
        return Path(resolved).resolve()
    return None


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
    result = run(
        [rscript, "-e", "cat(normalizePath(R.home('bin'), winslash='/'))"],
        cwd=root,
        env=env,
    )
    require_success(result, "R executable resolution")
    executable = "R.exe" if os.name == "nt" else "R"
    r_exe = Path(result.stdout.strip()) / executable
    if not r_exe.exists():
        raise DefaultREvidenceError(
            f"R executable was not found beside Rscript at {r_exe}"
        )
    return r_exe


def r_version_key(root: Path, rscript: Path, env: dict[str, str]) -> str:
    result = run([rscript, "-e", "cat(paste0('R-', getRversion()))"], cwd=root, env=env)
    require_success(result, "R version resolution")
    return "".join(
        character if character.isalnum() or character in "._-" else "_"
        for character in result.stdout.strip()
    )


def dependency_cache_key(
    root: Path, rscript: Path, env: dict[str, str], cran_repo: str
) -> str:
    digest = hashlib.sha256()
    for relative_path in (
        DEFAULT_R_VERIFIER,
        Path("docs") / "verification" / "RCMetaR-r-dependencies.json",
        RCMetaR_PACKAGE / "DESCRIPTION",
    ):
        digest.update((root / relative_path).read_bytes())
    digest.update(cran_repo.encode("utf-8"))
    return (
        f"{r_version_key(root, rscript, env)}-default-rdeps-{digest.hexdigest()[:12]}"
    )


def direct_archive_versions(root: Path) -> dict[str, str]:
    manifest = json.loads(
        (
            root / Path("docs") / "verification" / "RCMetaR-r-dependencies.json"
        ).read_text(encoding="utf-8")
    )
    return {
        dependency["name"]: dependency["installed_version"]
        for dependency in manifest["direct_RCMetaR_dependencies"]
        if dependency.get("source") == "cran-archive"
    }


def direct_dependency_policy(root: Path) -> tuple[list[str], dict[str, str]]:
    manifest = json.loads(
        (
            root / Path("docs") / "verification" / "RCMetaR-r-dependencies.json"
        ).read_text(encoding="utf-8")
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
    cran_packages, archive_packages = direct_dependency_policy(root)
    archive_url_by_package = {
        "HSROC": "https://cran.r-project.org/src/contrib/Archive/HSROC/HSROC_2.1.9.tar.gz"
    }
    archive_cran_dependencies = {
        "HSROC": ["coda", "MCMCpack"],
    }
    cran_packages = sorted(
        {
            *cran_packages,
            *(
                dependency
                for package in archive_packages
                for dependency in archive_cran_dependencies.get(package, [])
            ),
        }
    )
    r_code = """
args <- commandArgs(trailingOnly = TRUE)
lib <- normalizePath(args[[1]], winslash = "/", mustWork = FALSE)
repo <- args[[2]]
cran <- strsplit(args[[3]], ",", fixed = TRUE)[[1]]
cran <- cran[nzchar(cran)]
archive_args <- args[-(1:3)]

dir.create(lib, recursive = TRUE, showWarnings = FALSE)
.libPaths(c(lib, .libPaths()))
options(repos = c(CRAN = repo), timeout = 600, install.packages.check.source = "no")

installed_names <- function() {
  rownames(utils::installed.packages(lib.loc = lib))
}

missing <- setdiff(cran, installed_names())
if (length(missing)) {
  message("Installing CRAN packages into Default R Evidence cache: ", paste(missing, collapse = ", "))
  utils::install.packages(
    missing,
    lib = lib,
    dependencies = NA,
    type = if (.Platform$OS.type == "windows") "binary" else "source"
  )
}

missing <- setdiff(cran, installed_names())
if (length(missing)) {
  stop("CRAN packages still missing after install: ", paste(missing, collapse = ", "))
}

if (length(archive_args)) {
  if (length(archive_args) %% 3 != 0) {
    stop("Archive package arguments must be package/version/url triples")
  }
  for (index in seq(1, length(archive_args), by = 3)) {
    package <- archive_args[[index]]
    expected <- archive_args[[index + 1]]
    url <- archive_args[[index + 2]]
    installed <- utils::installed.packages(lib.loc = lib)
    if (!package %in% rownames(installed) || installed[package, "Version"] != expected) {
      message("Installing archived package into Default R Evidence cache: ", package, " ", expected)
      utils::install.packages(url, lib = lib, repos = NULL, type = "source")
    }
    installed <- utils::installed.packages(lib.loc = lib)
    if (!package %in% rownames(installed)) {
      stop(package, " was not installed from ", url)
    }
    actual <- installed[package, "Version"]
    if (actual != expected) {
      stop(package, " installed at version ", actual, ", expected ", expected)
    }
  }
}
"""
    archive_args: list[str] = []
    for name, version in sorted(archive_packages.items()):
        archive_args.extend([name, version, archive_url_by_package[name]])
    with tempfile.TemporaryDirectory(
        prefix="RCMetaR-default-r-install-"
    ) as temp_name:
        install_script = Path(temp_name) / "install-default-r-deps.R"
        install_script.write_text(r_code, encoding="utf-8")
        run_streamed(
            [
                rscript,
                install_script,
                library,
                cran_repo,
                ",".join(cran_packages),
                *archive_args,
            ],
            cwd=root,
            env=env,
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
        install_env.setdefault("RPY2_CFFI_MODE", "ABI")

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
        str(Path(args.python).resolve()) if Path(args.python).exists() else args.python
    )
    base_env = dict(os.environ)
    cran_repo = args.cran_repo or base_env.get("RCMS_CRAN_REPO") or DEFAULT_CRAN_REPO
    base_env["RCMS_CRAN_REPO"] = cran_repo

    manifest_result = run(
        [python, R_MANIFEST_VALIDATOR, "--root", root], cwd=root, env=base_env
    )
    require_success(manifest_result, "manifest validation")

    rscript = resolve_rscript(args.rscript)
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
            step(message + "; installing direct R dependencies into cache")
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
