"""Verify RCMetaR as Full R Stack Evidence."""

from __future__ import annotations

import argparse
import importlib.util
from importlib import metadata
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any


def load_r_support() -> ModuleType:
    support_path = Path(__file__).resolve().parent / "r_verification_support.py"
    spec = importlib.util.spec_from_file_location("rcms_r_verification_support", support_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load shared R verification support: {support_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


r_support: Any = load_r_support()


RCMetaR_PACKAGE = Path("r") / "RCMetaR"
R_DEP_INSTALLER = Path("scripts") / "install-r-deps.R"
R_BINARY_POLICY = Path("scripts") / "r_binary_policy.R"
R_POLICY_LOADER = Path("scripts") / "r_dependency_policy.py"
R_VERIFICATION_SUPPORT = Path("scripts") / "r_verification_support.py"
R_SMOKE_TEST = Path("scripts") / "analysis-smoke-test.R"
R_MANIFEST_VALIDATOR = Path("scripts") / "validate_rcmetar_r_manifests.py"
R_STACK_TESTS = (Path("tests") / "r_stack",)
BRIDGE_TESTS = (
    *R_STACK_TESTS,
    Path("tests") / "python" / "fast" / "test_rcmetar_r_manifest_validation.py",
)
REQUIRED_RPY2_IDENTITIES = {
    "rpy2": "3.6.7",
    "rpy2-rinterface": "3.6.6",
    "rpy2-robjects": "3.6.5",
}


class VerificationError(Exception):
    pass


def step(message: str) -> None:
    print(f"[RCMetaR-r-stack] {message}", flush=True)


def verify_rpy2_identities() -> dict[str, str]:
    observed = {}
    for distribution, required in REQUIRED_RPY2_IDENTITIES.items():
        try:
            version = metadata.version(distribution)
        except metadata.PackageNotFoundError as exc:
            raise VerificationError(
                f"required distribution is missing: {distribution}"
            ) from exc
        if version != required:
            raise VerificationError(
                f"{distribution} identity mismatch: expected {required}, observed {version}"
            )
        observed[distribution] = version
    step("Locked rpy2 identities verified: " + json.dumps(observed, sort_keys=True))
    return observed


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


def resolve_rscript(name: str, env: dict[str, str] | None = None) -> Path:
    resolved = r_support.resolve_rscript(name, env)
    if resolved is None:
        raise VerificationError(f"Rscript was not found: {name}")
    return resolved


def _candidate_rscript_names() -> list[str]:
    return r_support.candidate_rscript_names()


def resolve_r_exe(rscript: Path, root: Path, env: dict[str, str]) -> Path:
    try:
        return r_support.resolve_r_exe(rscript, root, env)
    except r_support.RVerificationSupportError as exc:
        raise VerificationError(str(exc)) from exc


def resolve_r_home(rscript: Path, root: Path, env: dict[str, str]) -> Path:
    try:
        return r_support.resolve_r_home(rscript, root, env)
    except r_support.RVerificationSupportError as exc:
        raise VerificationError(str(exc)) from exc


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
    env.setdefault("RPY2_CFFI_MODE", "API")
    env.setdefault("_R_CHECK_FORCE_SUGGESTS_", "false")
    return env


def verification_base_env(
    source: dict[str, str], *, platform_name: str = os.name
) -> dict[str, str]:
    return r_support.verification_base_env(source, platform_name=platform_name)


def r_version_key(rscript: Path, root: Path, env: dict[str, str]) -> str:
    try:
        return r_support.r_version_key(rscript, root, env)
    except r_support.RVerificationSupportError as exc:
        raise VerificationError(str(exc)) from exc


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
                R_DEP_INSTALLER,
                R_BINARY_POLICY,
                R_POLICY_LOADER,
                R_VERIFICATION_SUPPORT,
                r_support.DEPENDENCY_MANIFEST,
                RCMetaR_PACKAGE / "DESCRIPTION",
            ),
            "rdeps",
        )
    except r_support.RVerificationSupportError as exc:
        raise VerificationError(str(exc)) from exc


def binary_dependency_policy(root: Path) -> dict:
    try:
        return r_support.load_binary_dependency_policy(root)
    except r_support.RVerificationSupportError as exc:
        raise VerificationError(str(exc)) from exc


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
        install_env["RCMS_POLICY_PYTHON"] = python
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
            cache_env["RCMS_POLICY_PYTHON"] = python
            run([rscript, R_DEP_INSTALLER], cwd=root, env=cache_env)
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
    cache_env["RCMS_POLICY_PYTHON"] = python
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
            root / Path("docs") / "verification" / "RCMetaR-r-dependencies.json"
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
        str(Path(args.python).absolute()) if Path(args.python).exists() else args.python
    )
    rscript = resolve_rscript(args.rscript)
    base_env = verification_base_env(dict(os.environ))
    policy = binary_dependency_policy(root)
    configured_repo = args.cran_repo or base_env.get("RCMS_CRAN_REPO")
    if configured_repo and configured_repo != policy["repository"]:
        raise VerificationError(
            f"R dependency repository must match the manifest snapshot: {policy['repository']}"
        )
    cran_repo = policy["repository"]
    base_env["RCMS_CRAN_REPO"] = cran_repo
    base_env["RCMS_POLICY_PYTHON"] = python

    verify_rpy2_identities()

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

        env["RCMS_R_STACK_REQUIRED"] = "1"
        pytest_command = [args.pytest_runner, *map(str, BRIDGE_TESTS)]
        if args.pytest_runner == "uv":
            pytest_command = ["uv", "run", "pytest", *map(str, BRIDGE_TESTS)]
        run(pytest_command, cwd=root, env=env)
        run(
            [
                python,
                "scripts/verify_golden_compatibility.py",
                "--root",
                root,
                "--output-root",
                "build/qt6-verification/golden-compatibility-r-stack-v2",
            ],
            cwd=root,
            env=env,
        )

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
