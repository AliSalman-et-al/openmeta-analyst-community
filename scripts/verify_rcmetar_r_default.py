"""Run no-network Default R Evidence for the Fast Verification Lane."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
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
R_BINARY_POLICY = Path("scripts") / "r_binary_policy.R"
R_POLICY_LOADER = Path("scripts") / "r_dependency_policy.py"


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
    resolved_env = dict(os.environ) if env is None else env
    candidates: list[Path] = []
    if resolved_env.get("RCMS_RSCRIPT"):
        candidates.append(Path(resolved_env["RCMS_RSCRIPT"]))
    for variable in ("RCMS_R_HOME", "R_HOME"):
        candidates.extend(_rscript_paths_for_r_home(resolved_env.get(variable)))
    r_home = _r_home_from_r_command(resolved_env)
    candidates.extend(_rscript_paths_for_r_home(r_home))
    for r_home in _windows_registry_r_homes():
        candidates.extend(_rscript_paths_for_r_home(r_home))
    return candidates


def resolve_rscript(name: str, env: dict[str, str] | None = None) -> Path | None:
    resolved_env = dict(os.environ) if env is None else env
    explicit = name and name != "Rscript"
    if explicit:
        requested = Path(name)
        if requested.exists():
            return requested.resolve()
        resolved = shutil.which(name, path=resolved_env.get("PATH"))
        return Path(resolved).resolve() if resolved else None

    for candidate in _common_rscript_candidates(resolved_env):
        if candidate.exists():
            return candidate.resolve()
    resolved = shutil.which(name or "Rscript", path=resolved_env.get("PATH"))
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
    result = run(
        [
            rscript,
            "-e",
            "cat(paste0('R-', getRversion(), '-', R.version$arch, '-', .Platform$pkgType))",
        ],
        cwd=root,
        env=env,
    )
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
        R_BINARY_POLICY,
        R_POLICY_LOADER,
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


def binary_dependency_policy(root: Path) -> dict:
    helper = root / R_POLICY_LOADER
    spec = importlib.util.spec_from_file_location("rcms_r_dependency_policy", helper)
    if spec is None or spec.loader is None:
        raise DefaultREvidenceError(f"cannot load R dependency policy helper: {helper}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        return module.load_policy(
            root / "docs" / "verification" / "RCMetaR-r-dependencies.json"
        )
    except module.PolicyError as exc:
        raise DefaultREvidenceError(str(exc)) from exc


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
    base_env = dict(os.environ)
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
