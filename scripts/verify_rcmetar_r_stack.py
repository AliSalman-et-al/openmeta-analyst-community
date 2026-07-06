"""Verify the RCMetaR R Stack Slice for the Modern CI Path."""

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
R_DEP_INSTALLER = Path("scripts") / "install-modern-r-deps.R"
R_SMOKE_TEST = Path("scripts") / "analysis-smoke-test.R"
R_MANIFEST_VALIDATOR = Path("scripts") / "validate_rcmetar_r_manifests.py"
BRIDGE_TESTS = (
    Path("tests") / "modern" / "r_stack" / "test_inprocess_rpy2_backend.py",
    Path("tests") / "modern" / "fast" / "test_rcmetar_r_manifest_validation.py",
)
DEFAULT_CRAN_REPO = "https://cloud.r-project.org"


class VerificationError(Exception):
    pass


def step(message: str) -> None:
    print(f"[RCMetaR-r-stack] {message}", flush=True)


def run(
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
        raise VerificationError(
            f"command failed with exit code {result.returncode}: {printable}"
        )


def run_json(
    command: list[str | Path], *, cwd: Path, env: dict[str, str] | None = None
) -> dict:
    printable = " ".join(str(part) for part in command)
    step(printable)
    result = subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        raise VerificationError(
            f"command failed with exit code {result.returncode}: {printable}\n{output}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise VerificationError(
            f"command did not emit JSON: {printable}\n{result.stdout}"
        ) from exc


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


def resolve_rscript(name: str, env: dict[str, str] | None = None) -> Path:
    env = env or os.environ
    explicit = name and name != "Rscript"
    if explicit:
        requested = Path(name)
        if requested.exists():
            return requested.resolve()
        resolved = shutil.which(name, path=env.get("PATH"))
        if resolved:
            return Path(resolved).resolve()
        raise VerificationError(f"Rscript was not found: {name}")

    for candidate in _common_rscript_candidates(env):
        if candidate.exists():
            return candidate.resolve()
    resolved = shutil.which(name or "Rscript", path=env.get("PATH"))
    if resolved:
        return Path(resolved).resolve()
    raise VerificationError(f"Rscript was not found: {name}")


def resolve_r_exe(rscript: Path, root: Path, env: dict[str, str]) -> Path:
    result = subprocess.run(
        [str(rscript), "-e", "cat(normalizePath(R.home('bin'), winslash='/'))"],
        cwd=root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise VerificationError(
            result.stderr.strip() or "could not resolve R home from Rscript"
        )
    executable = "R.exe" if os.name == "nt" else "R"
    r_exe = Path(result.stdout.strip()) / executable
    if not r_exe.exists():
        raise VerificationError(f"R executable was not found beside Rscript at {r_exe}")
    return r_exe


def resolve_r_home(rscript: Path, root: Path, env: dict[str, str]) -> Path:
    result = subprocess.run(
        [str(rscript), "-e", "cat(normalizePath(R.home(), winslash='/'))"],
        cwd=root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise VerificationError(
            result.stderr.strip() or "could not resolve R home from Rscript"
        )
    return Path(result.stdout.strip())


def isolated_r_env(
    base_env: dict[str, str], library: Path, r_home: Path | None = None
) -> dict[str, str]:
    env = dict(base_env)
    env["R_LIBS"] = str(library)
    env["R_LIBS_USER"] = str(library)
    if r_home is not None:
        env["R_HOME"] = str(r_home)
        r_path_entries = [r_home / "bin"]
        if os.name == "nt":
            r_path_entries.insert(0, r_home / "bin" / "x64")
        env["PATH"] = os.pathsep.join(
            [*(str(path) for path in r_path_entries), env.get("PATH", "")]
        )
    env.setdefault("RPY2_CFFI_MODE", "ABI")
    env.setdefault("_R_CHECK_FORCE_SUGGESTS_", "false")
    return env


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def r_version_key(rscript: Path, root: Path, env: dict[str, str]) -> str:
    result = subprocess.run(
        [str(rscript), "-e", "cat(paste0('R-', getRversion()))"],
        cwd=root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise VerificationError(result.stderr.strip() or "could not resolve R version")
    return "".join(
        character if character.isalnum() or character in "._-" else "_"
        for character in result.stdout.strip()
    )


def dependency_cache_key(
    root: Path, rscript: Path, env: dict[str, str], cran_repo: str
) -> str:
    digest = hashlib.sha256()
    for relative_path in (
        R_DEP_INSTALLER,
        Path("docs") / "modernization" / "RCMetaR-r-dependencies.json",
        RCMetaR_PACKAGE / "DESCRIPTION",
    ):
        digest.update(file_digest(root / relative_path).encode("ascii"))
    digest.update(cran_repo.encode("utf-8"))
    return f"{r_version_key(rscript, root, env)}-rdeps-{digest.hexdigest()[:12]}"


def copy_library(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def ensure_dependency_library(
    root: Path,
    rscript: Path,
    env: dict[str, str],
    python: str,
    cran_repo: str,
    cache_root: Path | None,
    work_dir: Path,
) -> Path:
    if cache_root is None:
        r_library = work_dir / "library"
        r_library.mkdir(parents=True)
        install_env = isolated_r_env(env, r_library)
        install_env["RCMS_CRAN_REPO"] = cran_repo
        step(f"Installing R dependencies into isolated library at {r_library}")
        run([rscript, R_DEP_INSTALLER], cwd=root, env=install_env)
        verify_manifest_versions(root, python, rscript, install_env)
        return r_library

    cache_library = (
        cache_root / dependency_cache_key(root, rscript, env, cran_repo) / "library"
    )
    if cache_library.exists():
        try:
            cache_env = isolated_r_env(env, cache_library)
            cache_env["RCMS_CRAN_REPO"] = cran_repo
            verify_manifest_versions(root, python, rscript, cache_env)
            step(f"Using cached R dependency library at {cache_library}")
        except VerificationError:
            shutil.rmtree(cache_library)
        else:
            r_library = work_dir / "library"
            copy_library(cache_library, r_library)
            return r_library

    cache_library.mkdir(parents=True, exist_ok=True)
    cache_env = isolated_r_env(env, cache_library)
    cache_env["RCMS_CRAN_REPO"] = cran_repo
    step(f"Installing R dependencies into cache library at {cache_library}")
    run([rscript, R_DEP_INSTALLER], cwd=root, env=cache_env)
    verify_manifest_versions(root, python, rscript, cache_env)

    r_library = work_dir / "library"
    copy_library(cache_library, r_library)
    return r_library


def built_RCMetaR_tarball(work_dir: Path) -> Path:
    tarballs = sorted(
        work_dir.glob("RCMetaR_*.tar.gz"), key=lambda path: path.stat().st_mtime
    )
    if not tarballs:
        raise VerificationError(
            f"R CMD build did not create an RCMetaR tarball in {work_dir}"
        )
    return tarballs[-1]


def verify_manifest_versions(
    root: Path, python: str, rscript: Path, env: dict[str, str]
) -> None:
    report = run_json(
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
    missing = sorted(
        name for name, version in report["packages"].items() if version is None
    )
    if missing:
        raise VerificationError(
            "manifest dependency packages are not installed: " + ", ".join(missing)
        )
    manifest = json.loads(
        (
            root / Path("docs") / "modernization" / "RCMetaR-r-dependencies.json"
        ).read_text(encoding="utf-8")
    )
    exact_versions = {
        dependency["name"]: dependency["installed_version"]
        for dependency in manifest["direct_RCMetaR_dependencies"]
        if dependency.get("source") == "cran-archive"
    }
    wrong_versions = {
        name: {"expected": expected, "actual": report["packages"].get(name)}
        for name, expected in exact_versions.items()
        if report["packages"].get(name) != expected
    }
    if wrong_versions:
        raise VerificationError(
            "manifest dependency versions do not match: "
            + json.dumps(wrong_versions, sort_keys=True)
        )
    step(
        "Manifest dependency versions are installed: "
        + json.dumps(report, sort_keys=True)
    )


def verify(args: argparse.Namespace) -> None:
    root = args.root.resolve()
    python = (
        str(Path(args.python).resolve()) if Path(args.python).exists() else args.python
    )
    rscript = resolve_rscript(args.rscript)
    base_env = dict(os.environ)
    cran_repo = args.cran_repo or base_env.get("RCMS_CRAN_REPO") or DEFAULT_CRAN_REPO
    base_env["RCMS_CRAN_REPO"] = cran_repo

    run([python, R_MANIFEST_VALIDATOR, "--root", root], cwd=root, env=base_env)

    with tempfile.TemporaryDirectory(
        prefix="RCMetaR-r-stack-", dir=args.work_dir
    ) as temp_name:
        work_dir = Path(temp_name)
        bootstrap_library = work_dir / "bootstrap-library"
        bootstrap_library.mkdir(parents=True)
        env = isolated_r_env(base_env, bootstrap_library)
        r_exe = resolve_r_exe(rscript, root, env)
        r_home = resolve_r_home(rscript, root, env)
        env = isolated_r_env(base_env, bootstrap_library, r_home)
        cache_root = (
            args.r_library_cache_root.resolve() if args.r_library_cache_root else None
        )
        r_library = ensure_dependency_library(
            root, rscript, env, python, cran_repo, cache_root, work_dir
        )
        env = isolated_r_env(base_env, r_library, r_home)
        env["RCMS_CRAN_REPO"] = cran_repo

        step(f"Using isolated R verification library at {r_library}")

        run(
            [r_exe, "CMD", "build", "--no-build-vignettes", root / RCMetaR_PACKAGE],
            cwd=work_dir,
            env=env,
        )
        tarball = built_RCMetaR_tarball(work_dir)
        run(
            [
                r_exe,
                "CMD",
                "check",
                "--no-manual",
                "--no-build-vignettes",
                f"--library={r_library}",
                tarball,
            ],
            cwd=work_dir,
            env=env,
        )
        run(
            [r_exe, "CMD", "INSTALL", f"--library={r_library}", tarball],
            cwd=root,
            env=env,
        )

        verify_manifest_versions(root, python, rscript, env)
        run([rscript, R_SMOKE_TEST], cwd=root, env=env)

        pytest_command = [args.pytest_runner, *map(str, BRIDGE_TESTS)]
        if args.pytest_runner == "uv":
            pytest_command = ["uv", "run", "pytest", *map(str, BRIDGE_TESTS)]
        run(pytest_command, cwd=root, env=env)

    step("RCMetaR R Stack Slice verification complete")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--rscript", default="Rscript")
    parser.add_argument("--pytest-runner", default="uv", choices=("uv", "pytest"))
    parser.add_argument("--work-dir", type=Path, default=None)
    parser.add_argument("--r-library-cache-root", type=Path, default=None)
    parser.add_argument("--cran-repo", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        verify(parse_args(argv))
    except VerificationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
