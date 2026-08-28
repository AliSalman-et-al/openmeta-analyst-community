# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared runtime mechanics for the maintained RCMetaR verification lanes."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path


DEPENDENCY_MANIFEST = Path("config/r-dependencies.json")
R_BINARY_POLICY = Path("scripts") / "r_binary_policy.R"
R_POLICY_LOADER = Path("scripts") / "r_dependency_policy.py"


class RVerificationSupportError(Exception):
    """An error from shared R runtime discovery or identity checks."""


def candidate_rscript_names(*, platform_name: str = os.name) -> list[str]:
    return ["Rscript.exe", "Rscript"] if platform_name == "nt" else ["Rscript"]


def rscript_paths_for_r_home(
    r_home: str | Path | None, *, platform_name: str = os.name
) -> list[Path]:
    if not r_home:
        return []
    root = Path(r_home)
    names = candidate_rscript_names(platform_name=platform_name)
    return [root / "bin" / name for name in names] + [
        root / "bin" / "x64" / name for name in names
    ]


def r_home_from_r_command(
    env: dict[str, str], *, platform_name: str = os.name
) -> Path | None:
    del platform_name  # Kept for a uniform, testable runtime-probing interface.
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


def windows_registry_r_homes(*, platform_name: str = os.name) -> list[Path]:
    if platform_name != "nt":
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


def common_rscript_candidates(env: dict[str, str] | None = None) -> list[Path]:
    active_env = dict(os.environ) if env is None else env
    candidates: list[Path] = []
    if active_env.get("RCMS_RSCRIPT"):
        candidates.append(Path(active_env["RCMS_RSCRIPT"]))
    for variable in ("RCMS_R_HOME", "R_HOME"):
        candidates.extend(rscript_paths_for_r_home(active_env.get(variable)))
    r_home = r_home_from_r_command(active_env)
    candidates.extend(rscript_paths_for_r_home(r_home))
    for r_home in windows_registry_r_homes():
        candidates.extend(rscript_paths_for_r_home(r_home))
    return candidates


def resolve_rscript(name: str, env: dict[str, str] | None = None) -> Path | None:
    active_env = dict(os.environ) if env is None else env
    explicit = bool(name and name != "Rscript")
    if explicit:
        requested = Path(name)
        if requested.exists():
            return requested.resolve()
        resolved = shutil.which(name, path=active_env.get("PATH"))
        return Path(resolved).resolve() if resolved else None

    for candidate in common_rscript_candidates(active_env):
        if candidate.exists():
            return candidate.resolve()
    resolved = shutil.which(name or "Rscript", path=active_env.get("PATH"))
    return Path(resolved).resolve() if resolved else None


def _r_probe(
    rscript: Path, root: Path, env: dict[str, str], expression: str, label: str
) -> str:
    result = subprocess.run(
        [str(rscript), "-e", expression],
        cwd=root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RVerificationSupportError(
            result.stderr.strip() or f"could not resolve {label}"
        )
    return result.stdout.strip()


def resolve_r_exe(rscript: Path, root: Path, env: dict[str, str]) -> Path:
    r_bin = _r_probe(
        rscript,
        root,
        env,
        "cat(normalizePath(R.home('bin'), winslash='/'))",
        "R executable",
    )
    executable = "R.exe" if os.name == "nt" else "R"
    r_exe = Path(r_bin) / executable
    if not r_exe.exists():
        raise RVerificationSupportError(
            f"R executable was not found beside Rscript at {r_exe}"
        )
    return r_exe


def resolve_r_home(rscript: Path, root: Path, env: dict[str, str]) -> Path:
    return Path(
        _r_probe(
            rscript,
            root,
            env,
            "cat(normalizePath(R.home(), winslash='/'))",
            "R home",
        )
    )


def verification_base_env(
    source: dict[str, str], *, platform_name: str = os.name
) -> dict[str, str]:
    env = dict(source)
    if platform_name == "nt":
        for name in (
            "LC_ALL",
            "LC_COLLATE",
            "LC_CTYPE",
            "LC_MONETARY",
            "LC_TIME",
            "LANG",
        ):
            if env.get(name, "").lower() in {"c.utf-8", "c.utf8"}:
                env.pop(name)
    return env


def r_version_key(rscript: Path, root: Path, env: dict[str, str]) -> str:
    version = _r_probe(
        rscript,
        root,
        env,
        "cat(paste0('R-', getRversion(), '-', R.version$arch, '-', .Platform$pkgType))",
        "R version",
    )
    return "".join(
        character if character.isalnum() or character in "._-" else "_"
        for character in version
    )


def dependency_cache_key(
    root: Path,
    rscript: Path,
    env: dict[str, str],
    cran_repo: str,
    identity_paths: Iterable[Path],
    suffix: str,
) -> str:
    digest = hashlib.sha256()
    for relative_path in identity_paths:
        digest.update((root / relative_path).read_bytes())
    digest.update(cran_repo.encode("utf-8"))
    return f"{r_version_key(rscript, root, env)}-{suffix}-{digest.hexdigest()[:12]}"


def load_binary_dependency_policy(root: Path) -> dict:
    helper = root / R_POLICY_LOADER
    spec = importlib.util.spec_from_file_location("rcms_r_dependency_policy", helper)
    if spec is None or spec.loader is None:
        raise RVerificationSupportError(
            f"cannot load R dependency policy helper: {helper}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        return module.load_policy(root / DEPENDENCY_MANIFEST)
    except module.PolicyError as exc:
        raise RVerificationSupportError(str(exc)) from exc
