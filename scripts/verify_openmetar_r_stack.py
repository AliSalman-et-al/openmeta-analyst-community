"""Verify the OpenMetaR R Stack Slice for the Modern CI Path."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


OPENMETAR_PACKAGE = Path("src") / "R" / "OpenMetaR"
R_DEP_INSTALLER = Path("scripts") / "install-modern-r-deps.R"
R_SMOKE_TEST = Path("scripts") / "analysis-smoke-test.R"
R_MANIFEST_VALIDATOR = Path("scripts") / "validate_openmetar_r_manifests.py"
BRIDGE_TESTS = (
    Path("tests") / "modern" / "test_inprocess_rpy2_backend.py",
    Path("tests") / "modern" / "test_openmetar_r_manifest_validation.py",
)


class VerificationError(Exception):
    pass


def step(message: str) -> None:
    print(f"[OpenMetaR-r-stack] {message}", flush=True)


def run(command: list[str | Path], *, cwd: Path, env: dict[str, str] | None = None) -> None:
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
        raise VerificationError(f"command failed with exit code {result.returncode}: {printable}")


def run_json(command: list[str | Path], *, cwd: Path, env: dict[str, str] | None = None) -> dict:
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
        raise VerificationError(f"command failed with exit code {result.returncode}: {printable}\n{output}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"command did not emit JSON: {printable}\n{result.stdout}") from exc


def resolve_rscript(name: str) -> Path:
    resolved = shutil.which(name) if not Path(name).is_absolute() else name
    if not resolved:
        raise VerificationError(f"Rscript was not found: {name}")
    return Path(resolved).resolve()


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
        raise VerificationError(result.stderr.strip() or "could not resolve R home from Rscript")
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
        raise VerificationError(result.stderr.strip() or "could not resolve R home from Rscript")
    return Path(result.stdout.strip())


def isolated_r_env(base_env: dict[str, str], library: Path, r_home: Path | None = None) -> dict[str, str]:
    env = dict(base_env)
    env["R_LIBS"] = str(library)
    env["R_LIBS_USER"] = str(library)
    if r_home is not None:
        env["R_HOME"] = str(r_home)
        r_path_entries = [r_home / "bin"]
        if os.name == "nt":
            r_path_entries.insert(0, r_home / "bin" / "x64")
        env["PATH"] = os.pathsep.join([*(str(path) for path in r_path_entries), env.get("PATH", "")])
    env.setdefault("RPY2_CFFI_MODE", "ABI")
    env.setdefault("_R_CHECK_FORCE_SUGGESTS_", "false")
    return env


def built_OpenMetaR_tarball(work_dir: Path) -> Path:
    tarballs = sorted(work_dir.glob("OpenMetaR_*.tar.gz"), key=lambda path: path.stat().st_mtime)
    if not tarballs:
        raise VerificationError(f"R CMD build did not create an OpenMetaR tarball in {work_dir}")
    return tarballs[-1]


def verify_manifest_versions(root: Path, python: str, rscript: Path, env: dict[str, str]) -> None:
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
    missing = sorted(name for name, version in report["packages"].items() if version is None)
    if missing:
        raise VerificationError("manifest dependency packages are not installed: " + ", ".join(missing))
    manifest = json.loads((root / Path("docs") / "modernization" / "OpenMetaR-r-dependencies.json").read_text(encoding="utf-8"))
    exact_versions = {
        dependency["name"]: dependency["installed_version"]
        for dependency in manifest["direct_OpenMetaR_dependencies"]
        if dependency.get("source") == "cran-archive"
    }
    wrong_versions = {
        name: {"expected": expected, "actual": report["packages"].get(name)}
        for name, expected in exact_versions.items()
        if report["packages"].get(name) != expected
    }
    if wrong_versions:
        raise VerificationError("manifest dependency versions do not match: " + json.dumps(wrong_versions, sort_keys=True))
    step("Manifest dependency versions are installed: " + json.dumps(report, sort_keys=True))


def verify(args: argparse.Namespace) -> None:
    root = args.root.resolve()
    python = str(Path(args.python).resolve()) if Path(args.python).exists() else args.python
    rscript = resolve_rscript(args.rscript)
    base_env = dict(os.environ)

    run([python, R_MANIFEST_VALIDATOR, "--root", root], cwd=root, env=base_env)

    with tempfile.TemporaryDirectory(prefix="OpenMetaR-r-stack-", dir=args.work_dir) as temp_name:
        work_dir = Path(temp_name)
        r_library = work_dir / "library"
        r_library.mkdir(parents=True)
        env = isolated_r_env(base_env, r_library)
        r_exe = resolve_r_exe(rscript, root, env)
        r_home = resolve_r_home(rscript, root, env)
        env = isolated_r_env(base_env, r_library, r_home)

        step(f"Using isolated R library at {r_library}")
        run([rscript, R_DEP_INSTALLER], cwd=root, env=env)

        run([r_exe, "CMD", "build", "--no-build-vignettes", root / OPENMETAR_PACKAGE], cwd=work_dir, env=env)
        tarball = built_OpenMetaR_tarball(work_dir)
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
        run([r_exe, "CMD", "INSTALL", f"--library={r_library}", tarball], cwd=root, env=env)

        verify_manifest_versions(root, python, rscript, env)
        run([rscript, R_SMOKE_TEST], cwd=root, env=env)

        pytest_command = [args.pytest_runner, *map(str, BRIDGE_TESTS)]
        if args.pytest_runner == "uv":
            pytest_command = ["uv", "run", "pytest", *map(str, BRIDGE_TESTS)]
        run(pytest_command, cwd=root, env=env)

    step("OpenMetaR R Stack Slice verification complete")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--rscript", default="Rscript")
    parser.add_argument("--pytest-runner", default="uv", choices=("uv", "pytest"))
    parser.add_argument("--work-dir", type=Path, default=None)
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
