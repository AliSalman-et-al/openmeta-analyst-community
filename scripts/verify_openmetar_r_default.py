"""Run no-network Default R Evidence for the Fast Verification Lane."""

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
R_MANIFEST_VALIDATOR = Path("scripts") / "validate_openmetar_r_manifests.py"


class DefaultREvidenceError(Exception):
    pass


def step(message: str) -> None:
    print(f"[OpenMetaR-default-r] {message}", flush=True)


def run(command: list[str | Path], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
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


def require_success(result: subprocess.CompletedProcess[str], label: str) -> None:
    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        raise DefaultREvidenceError(f"{label} failed with exit code {result.returncode}: {output}")


def resolve_rscript(name: str) -> Path | None:
    resolved = shutil.which(name) if not Path(name).is_absolute() else name
    return Path(resolved).resolve() if resolved else None


def installed_version_report(root: Path, python: str, rscript: Path, env: dict[str, str]) -> dict:
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
        raise DefaultREvidenceError("installed package version report did not emit JSON") from exc


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
        raise DefaultREvidenceError(f"R executable was not found beside Rscript at {r_exe}")
    return r_exe


def direct_archive_versions(root: Path) -> dict[str, str]:
    manifest = json.loads(
        (root / Path("docs") / "modernization" / "OpenMetaR-r-dependencies.json").read_text(encoding="utf-8")
    )
    return {
        dependency["name"]: dependency["installed_version"]
        for dependency in manifest["direct_OpenMetaR_dependencies"]
        if dependency.get("source") == "cran-archive"
    }


def install_and_load_openmetar(root: Path, rscript: Path, env: dict[str, str]) -> None:
    with tempfile.TemporaryDirectory(prefix="OpenMetaR-default-r-") as temp_name:
        library = Path(temp_name) / "library"
        library.mkdir()
        r_exe = resolve_r_exe(root, rscript, env)
        install_env = dict(env)
        existing_libs = install_env.get("R_LIBS")
        install_env["R_LIBS"] = str(library) if not existing_libs else str(library) + os.pathsep + existing_libs
        install_env["R_LIBS_USER"] = str(library)
        install_env.setdefault("RPY2_CFFI_MODE", "ABI")

        result = run(
            [
                r_exe,
                "CMD",
                "INSTALL",
                f"--library={library}",
                root / OPENMETAR_PACKAGE,
            ],
            cwd=root,
            env=install_env,
        )
        require_success(result, "local OpenMetaR source install")

        smoke = run(
            [
                rscript,
                "-e",
                (
                    "library(OpenMetaR); "
                    "stopifnot(!is.null(getS3method('print','summary.display',optional=TRUE))); "
                    "stopifnot(!is.null(getS3method('print','summary.data',optional=TRUE))); "
                    "cat('OK\\n')"
                ),
            ],
            cwd=root,
            env=install_env,
        )
        require_success(smoke, "local OpenMetaR load smoke")


def verify(args: argparse.Namespace) -> None:
    root = args.root.resolve()
    python = str(Path(args.python).resolve()) if Path(args.python).exists() else args.python
    base_env = dict(os.environ)

    manifest_result = run([python, R_MANIFEST_VALIDATOR, "--root", root], cwd=root, env=base_env)
    require_success(manifest_result, "manifest validation")

    rscript = resolve_rscript(args.rscript)
    if rscript is None:
        message = f"Rscript was not found: {args.rscript}; Default R Evidence limited to manifest validation"
        if args.require_r:
            raise DefaultREvidenceError(message)
        step(message)
        return

    report = installed_version_report(root, python, rscript, base_env)
    missing = sorted(name for name, version in report["packages"].items() if version is None)
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
            message_parts.append("wrong direct R package versions: " + json.dumps(wrong_versions, sort_keys=True))
        message = "; ".join(message_parts) + "; Default R Evidence limited to manifest validation"
        if args.require_installed_packages:
            raise DefaultREvidenceError(message)
        step(message)
        return

    install_and_load_openmetar(root, rscript, base_env)
    step("Default R Evidence complete")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--rscript", default="Rscript")
    parser.add_argument("--require-r", action="store_true")
    parser.add_argument("--require-installed-packages", action="store_true")
    args = parser.parse_args(argv)
    try:
        verify(args)
    except DefaultREvidenceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
