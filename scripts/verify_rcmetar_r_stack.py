"""Verify RCMetaR as Full R Stack Evidence."""

from __future__ import annotations

import argparse
import csv
from importlib import metadata
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__:
    from scripts import r_verification_support as r_support
else:
    import r_verification_support as r_support


RCMetaR_PACKAGE = Path("r") / "RCMetaR"
R_DEP_INSTALLER = Path("scripts") / "install-r-deps.R"
R_BINARY_POLICY = Path("scripts") / "r_binary_policy.R"
R_POLICY_LOADER = Path("scripts") / "r_dependency_policy.py"
R_VERIFICATION_SUPPORT = Path("scripts") / "r_verification_support.py"
R_SMOKE_TEST = Path("scripts") / "analysis-smoke-test.R"
R_REITSMA_VISUAL_QA = Path("scripts") / "verify_reitsma_visual_qa.R"
R_MANIFEST_VALIDATOR = Path("scripts") / "validate_rcmetar_r_manifests.py"
R_STACK_TESTS = (Path("tests") / "r_stack",)
BRIDGE_TESTS = R_STACK_TESTS
REQUIRED_RPY2_IDENTITIES = {
    "rpy2": "3.6.7",
    "rpy2-rinterface": "3.6.6",
    "rpy2-robjects": "3.6.5",
}
REITSMA_VISUAL_CASE_COUNT = 21
REITSMA_VISUAL_DETERMINISTIC_EXTENSIONS = {"svg", "svgz", "png", "tif", "tiff"}


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
        (root / "config/r-dependencies.json").read_text(encoding="utf-8")
    )
    exact_versions = {
        dependency["name"]: dependency["installed_version"]
        for dependency in manifest["direct_RCMetaR_dependencies"]
        if dependency.get("source") in {"cran", "cran-archive"}
        and dependency.get("installed_version") not in {None, "latest-compatible"}
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


def _read_reitsma_visual_manifest(root: Path) -> tuple[list[dict[str, str]], dict]:
    manifest_path = root / "manifest.csv"
    descriptor_path = root / "descriptor-contract.json"
    if not manifest_path.is_file() or not descriptor_path.is_file():
        raise VerificationError(
            "Reitsma visual QA did not produce its manifest and descriptor contract"
        )
    with manifest_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    try:
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationError("Reitsma descriptor contract is not valid JSON") from exc
    if len(rows) != REITSMA_VISUAL_CASE_COUNT:
        raise VerificationError(
            f"Reitsma visual QA expected {REITSMA_VISUAL_CASE_COUNT} cases, observed {len(rows)}"
        )
    if len({row.get("case", "") for row in rows}) != REITSMA_VISUAL_CASE_COUNT:
        raise VerificationError("Reitsma visual QA manifest contains duplicate case identifiers")
    required = {
        "case", "family", "kind", "workflow", "style", "scenario", "extension",
        "image", "bytes", "sha256", "pdf_contract", "error",
    }
    if any(not required.issubset(row) for row in rows):
        raise VerificationError("Reitsma visual QA manifest is missing release contract columns")
    failures = [
        row["case"]
        for row in rows
        if row.get("error", "").strip() not in {"", "NA"}
    ]
    if failures:
        raise VerificationError("Reitsma visual QA failures: " + ", ".join(failures))
    for row in rows:
        image = Path(row["image"])
        if not image.is_file() or int(float(row["bytes"])) <= 1000:
            raise VerificationError(f"Reitsma visual QA artifact is missing or empty: {row['case']}")
        extension = row["extension"].lower()
        if extension in REITSMA_VISUAL_DETERMINISTIC_EXTENSIONS and len(row["sha256"]) != 64:
            raise VerificationError(f"Missing deterministic hash for Reitsma case: {row['case']}")
        if extension == "pdf":
            try:
                contract = json.loads(row["pdf_contract"])
            except json.JSONDecodeError as exc:
                raise VerificationError(f"Invalid PDF contract for Reitsma case: {row['case']}") from exc
            if (
                contract.get("signature") != "%PDF-"
                or contract.get("pages") != 1
                or contract.get("has_xref_or_xref_stream") is not True
                or contract.get("has_eof") is not True
            ):
                raise VerificationError(f"PDF semantic contract failed for Reitsma case: {row['case']}")
    if descriptor.get("schema_version") != 1 or set(descriptor.get("descriptors", {})) != {
        "sroc", "coefficient_forest"
    }:
        raise VerificationError("Reitsma descriptor contract has unexpected coverage")
    return rows, descriptor


def verify_reitsma_visual_evidence(
    root: Path, rscript: Path, env: dict[str, str], work_dir: Path
) -> None:
    """Run and compare the maintained 21-case visual release harness twice.

    Raster/SVG outputs are deterministic release artifacts and must retain
    stable SHA-256 values. PDFs are intentionally checked through their
    normalized semantic contract because producers may embed timestamps.
    """
    # The release gate must exercise the package that was just built and
    # installed above.  The visual script deliberately supports a source mode
    # for local development, but this integrated gate must never silently fall
    # back to pkgload::load_all() from the workspace.
    visual_env = dict(env)
    visual_env["RCMS_REITSMA_VISUAL_QA_MODE"] = "installed"
    visual_env["RCMS_REITSMA_VISUAL_QA_LIBRARY"] = env["R_LIBS"]
    evidence = []
    for index in (1, 2):
        output = work_dir / f"reitsma-visual-qa-{index}"
        output.mkdir(parents=True, exist_ok=True)
        run([rscript, R_REITSMA_VISUAL_QA, output], cwd=root, env=visual_env)
        evidence.append(_read_reitsma_visual_manifest(output))
    first_rows, first_descriptor = evidence[0]
    second_rows, second_descriptor = evidence[1]
    if first_descriptor != second_descriptor:
        raise VerificationError("Reitsma normalized descriptor contract is not deterministic")
    first_by_case = {row["case"]: row for row in first_rows}
    second_by_case = {row["case"]: row for row in second_rows}
    if set(first_by_case) != set(second_by_case):
        raise VerificationError("Reitsma visual QA case inventory changed between runs")
    for case, first in first_by_case.items():
        second = second_by_case[case]
        extension = first["extension"].lower()
        if extension in REITSMA_VISUAL_DETERMINISTIC_EXTENSIONS and first["sha256"] != second["sha256"]:
            raise VerificationError(f"Reitsma deterministic visual hash drifted: {case}")
        if extension == "pdf" and first["pdf_contract"] != second["pdf_contract"]:
            raise VerificationError(f"Reitsma PDF semantic contract drifted: {case}")
    step("Reitsma visual release evidence verified: 21 cases, deterministic hashes and normalized PDF/descriptor contracts")


def bridge_test_command(python: str, pytest_runner: str) -> list[str | Path]:
    # Always invoke the exact interpreter selected by --python.  In
    # particular, `uv run` can resolve a different project interpreter and
    # invalidate the rpy2 identity and installed-R-library checks above.
    del pytest_runner
    return [python, "-m", "pytest", *map(str, BRIDGE_TESTS)]


def verify(args: argparse.Namespace) -> None:
    root = args.root.resolve()
    python = (
        str(Path(args.python).absolute()) if Path(args.python).exists() else args.python
    )
    rscript = resolve_rscript(args.rscript)
    base_env = r_support.verification_base_env(dict(os.environ))
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

    work_dir_parent = args.work_dir.resolve() if args.work_dir else None
    if work_dir_parent is not None:
        work_dir_parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="RCMetaR-r-stack-", dir=work_dir_parent
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
        verify_reitsma_visual_evidence(root, rscript, env, work_dir)

        env["RCMS_R_STACK_REQUIRED"] = "1"
        pytest_command = bridge_test_command(python, args.pytest_runner)
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
