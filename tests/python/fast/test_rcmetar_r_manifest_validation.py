import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = REPO_ROOT / "scripts" / "validate_RCMetaR_r_manifests.py"
DEPENDENCY_MANIFEST = Path("config/r-dependencies.json")
DRIFT_MANIFEST = Path("config/r-statistical-drift.json")
RCMetaR_PACKAGE = REPO_ROOT / "r" / "RCMetaR"
RCMetaR_R_DIR = RCMetaR_PACKAGE / "R"
RCMetaR_DESCRIPTION = RCMetaR_PACKAGE / "DESCRIPTION"
RCMetaR_NAMESPACE = RCMetaR_PACKAGE / "NAMESPACE"

LEGACY_EXPORT_PATTERN = re.compile(
    r"^([A-Za-z][A-Za-z0-9._]*)\s*<-\s*function\s*\(", re.MULTILINE
)


def load_r_verification_support():
    spec = importlib.util.spec_from_file_location(
        "r_verification_support", REPO_ROOT / "scripts" / "r_verification_support.py"
    )
    support = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(support)
    return support


def test_shared_r_verification_support_resolves_home_and_normalizes_windows_locale(
    tmp_path,
):
    support = load_r_verification_support()
    r_home = tmp_path / "R"
    rscript = r_home / "bin" / support.candidate_rscript_names()[0]
    rscript.parent.mkdir(parents=True)
    rscript.write_text("", encoding="utf-8")

    assert (
        support.resolve_rscript("Rscript", env={"RCMS_R_HOME": str(r_home), "PATH": ""})
        == rscript.resolve()
    )
    source = {
        "LC_ALL": "C.UTF-8",
        "LC_CTYPE": "C.utf8",
        "LANG": "C.UTF-8",
        "RCMS_SENTINEL": "preserved",
    }
    assert support.verification_base_env(source, platform_name="nt") == {
        "RCMS_SENTINEL": "preserved"
    }
    assert support.verification_base_env(source, platform_name="posix") == source


def test_full_r_verifier_drops_unsupported_posix_locale_on_windows():
    verifier_path = REPO_ROOT / "scripts" / "verify_rcmetar_r_stack.py"
    spec = importlib.util.spec_from_file_location(
        "verify_rcmetar_r_stack", verifier_path
    )
    verifier = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(verifier)

    source = {
        "LC_ALL": "C.UTF-8",
        "LC_CTYPE": "C.utf8",
        "LANG": "C.UTF-8",
        "RCMS_SENTINEL": "preserved",
    }

    assert verifier.verification_base_env(source, platform_name="nt") == {
        "RCMS_SENTINEL": "preserved"
    }
    assert verifier.verification_base_env(source, platform_name="posix") == source


def test_full_r_stack_orchestration_prepares_and_propagates_qt_environment(
    monkeypatch, tmp_path
):
    verifier_path = REPO_ROOT / "scripts" / "verify.py"
    spec = importlib.util.spec_from_file_location("verify", verifier_path)
    verifier = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(verifier)

    captured = {}

    def prepare_qt_environment(build_root):
        captured["build_root"] = build_root
        return {"RCMS_QT6_BUILD_ROOT": str(build_root), "PYTHONPATH": "generated"}

    def selected_rscript(_args):
        return "Rscript"

    def run(command, *, env=None):
        captured["command"] = command
        captured["env"] = env

    monkeypatch.setattr(verifier, "prepare_qt_environment", prepare_qt_environment)
    monkeypatch.setattr(verifier, "selected_rscript", selected_rscript)
    monkeypatch.setattr(verifier, "run", run)

    args = argparse.Namespace(
        sync=False,
        build_root=tmp_path,
        rscript=None,
        r_runtime_root=None,
        r_library_cache_root=None,
    )
    verifier.run_full_r_stack(args)

    assert captured["build_root"] == tmp_path.resolve()
    assert captured["env"]["RCMS_QT6_BUILD_ROOT"] == str(tmp_path.resolve())
    assert captured["env"]["PYTHONPATH"] == "generated"
    assert captured["command"][-1] == str(verifier.FULL_R_LIBRARY_CACHE)


def test_r_verifiers_preserve_symlinked_python_identity(monkeypatch, tmp_path):
    base_python = tmp_path / "uv-python-dir" / "python3.11"
    base_python.parent.mkdir()
    base_python.write_bytes(b"base interpreter")
    venv_python = tmp_path / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    try:
        venv_python.symlink_to(base_python)
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")
    expected_python = str(venv_python.absolute())

    class StopAfterFirstChild(Exception):
        pass

    for script_name in ("verify_rcmetar_r_stack.py", "verify_rcmetar_r_default.py"):
        spec = importlib.util.spec_from_file_location(
            f"symlink_identity_{script_name.removesuffix('.py')}",
            REPO_ROOT / "scripts" / script_name,
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        captured = {}

        def stop_after_first_child(command, *, cwd, env):
            captured["command"] = command
            captured["env"] = env
            raise StopAfterFirstChild

        with monkeypatch.context() as patch:
            patch.setattr(
                module,
                "binary_dependency_policy",
                lambda _root: {
                    "repository": "https://packagemanager.posit.co/cran/2026-07-16"
                },
            )
            if hasattr(module, "verify_rpy2_identities"):
                patch.setattr(module, "verify_rpy2_identities", lambda: None)
            patch.setattr(module, "run", stop_after_first_child)
            args = argparse.Namespace(
                root=REPO_ROOT,
                python=str(venv_python),
                rscript="Rscript",
                pytest_runner="uv",
                work_dir=None,
                r_library_cache_root=None,
                cran_repo=None,
                require_r=False,
                require_installed_packages=False,
                install_missing=False,
            )
            with pytest.raises(StopAfterFirstChild):
                module.verify(args)

        assert captured["command"][0] == expected_python
        assert captured["env"]["RCMS_POLICY_PYTHON"] == expected_python


LEGACY_ALIAS_PATTERN = re.compile(
    r"^([A-Za-z][A-Za-z0-9._]*)\s*<-\s*([A-Za-z][A-Za-z0-9._]*)\s*$", re.MULTILINE
)
S4_CLASS_PATTERN = re.compile(r"setClass\(\s*[\"']([^\"']+)[\"']")
RCMetaR_PUBLIC_EXPORTS = {
    "rcmetar.analysis.methods",
    "rcmetar.analysis.plot.capabilities",
    "rcmetar.available.methods",
    "rcmetar.back.calculate.continuous",
    "rcmetar.binary.study.effect",
    "rcmetar.continuous.study.effect",
    "rcmetar.convert.scale",
    "rcmetar.create.binary.data",
    "rcmetar.create.continuous.data",
    "rcmetar.create.covariate.values",
    "rcmetar.create.diagnostic.data",
    "rcmetar.diagnostic.study.effects",
    "rcmetar.draw.forest.plot",
    "rcmetar.draw.regression.plot",
    "rcmetar.get.mult.from.conf.level",
    "rcmetar.graphics.off",
    "rcmetar.impute.binary",
    "rcmetar.impute.continuous.prepost",
    "rcmetar.impute.continuous.study",
    "rcmetar.impute.diagnostic",
    "rcmetar.method.description",
    "rcmetar.method.parameters",
    "rcmetar.method.references",
    "rcmetar.prepare.analysis.data",
    "rcmetar.regenerate.plot.data",
    "rcmetar.regenerate.regression.plot.data",
    "rcmetar.run.analysis",
    "rcmetar.run.diagnostic.analyses",
    "rcmetar.run.permutation",
    "rcmetar.save.plot.data",
    "rcmetar.set.global.conf.level",
    "rcmetar.validate.analysis.request",
}


def copy_manifest_config(tmp_path):
    config_root = tmp_path / "config"
    config_root.mkdir()
    shutil.copyfile(REPO_ROOT / DEPENDENCY_MANIFEST, tmp_path / DEPENDENCY_MANIFEST)
    shutil.copyfile(REPO_ROOT / DRIFT_MANIFEST, tmp_path / DRIFT_MANIFEST)
    return tmp_path


def run_validator(root, *args):
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--root", str(root), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_RCMetaR_r_manifests_validate():
    result = run_validator(REPO_ROOT)

    assert result.returncode == 0, result.stderr
    assert "validated RCMetaR R dependency and drift manifests" in result.stdout
    manifest = json.loads((REPO_ROOT / DEPENDENCY_MANIFEST).read_text(encoding="utf-8"))
    policy = manifest["binary_package_policy"]
    assert manifest["target_runtime"]["r"] == "4.6.1"
    assert policy["repository"] == "https://packagemanager.posit.co/cran/2026-07-16"
    assert policy["normal_install_type"] == "binary"
    assert policy["source_fallback"] is False
    assert len(policy["required_normal_packages"]) == 54
    assert policy["source_exceptions"] == [
        {
            "name": "HSROC",
            "version": "2.1.9",
            "url": "https://cran.r-project.org/src/contrib/Archive/HSROC/HSROC_2.1.9.tar.gz",
            "sha256": "5476fa76d7723717e203925a1da442813e3645790ef9b633a145cbc04a08b874",
            "dependencies": ["lattice", "coda", "MASS", "MCMCpack"],
            "install_type": "source",
            "repos": None,
            "dependencies_install": False,
        }
    ]


def test_direct_and_app_bundle_dependencies_must_stay_separate(tmp_path):
    root = copy_manifest_config(tmp_path)
    manifest_path = root / DEPENDENCY_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["app_r_bundle_dependencies"].append(
        {
            "name": "metafor",
            "source": "cran",
            "reason": "invalid duplicate across manifest sections",
            "evidence": ["test"],
        }
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_validator(root)

    assert result.returncode == 1
    assert "dependencies must be separated" in result.stderr
    assert "metafor" in result.stderr


def test_drift_manifest_preserves_review_record_schema(tmp_path):
    root = copy_manifest_config(tmp_path)
    manifest_path = root / DRIFT_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["reviewed_drift_required_fields"].remove("independent_validation_signal")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_validator(root)

    assert result.returncode == 1
    assert (
        "reviewed_drift_required_fields missing independent_validation_signal"
        in result.stderr
    )


def test_manifest_records_empty_direct_build_dependency_scope(tmp_path):
    root = copy_manifest_config(tmp_path)
    manifest_path = root / DEPENDENCY_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for dependency in manifest["direct_RCMetaR_dependencies"]:
        if dependency["name"] == "roxygen2":
            dependency["scope"] = ["documentation"]
    del manifest["empty_scope_rationale"]["build"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_validator(root)

    assert result.returncode == 1
    assert "empty_scope_rationale.build" in result.stderr


def test_cran_archive_dependencies_must_pin_exact_versions(tmp_path):
    root = copy_manifest_config(tmp_path)
    manifest_path = root / DEPENDENCY_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for dependency in manifest["direct_RCMetaR_dependencies"]:
        if dependency["name"] == "HSROC":
            dependency["installed_version"] = "latest-compatible"
            break
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_validator(root)

    assert result.returncode == 1
    assert "archived CRAN packages must declare an exact version" in result.stderr

    manifest = json.loads((REPO_ROOT / DEPENDENCY_MANIFEST).read_text(encoding="utf-8"))
    manifest["binary_package_policy"]["source_exceptions"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = run_validator(root)
    assert result.returncode == 1
    assert "sole pinned source exception" in result.stderr


def test_installed_version_report_parses_rscript_output(monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "validate_RCMetaR_r_manifests", VALIDATOR
    )
    validator = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(validator)

    def fake_run(command, text, stdout, stderr, check):
        assert command[:2] == ["Rscript", "-e"]
        assert command[3:] == ["R", "metafor", "HSROC"]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="R\t4.6.0\nR\t4.6.0\nmetafor\t4.9-17\nHSROC\tNA\n",
            stderr="",
        )

    monkeypatch.setattr(validator.subprocess, "run", fake_run)

    report = validator.report_installed_versions("Rscript", ["R", "metafor", "HSROC"])

    assert report == {
        "r_version": "4.6.0",
        "packages": {
            "R": "4.6.0",
            "metafor": "4.9-17",
            "HSROC": None,
        },
    }


def test_report_installed_versions_surfaces_rscript_failure(monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "validate_RCMetaR_r_manifests", VALIDATOR
    )
    validator = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(validator)

    def fake_run(command, text, stdout, stderr, check):
        return subprocess.CompletedProcess(
            command, 1, stdout="", stderr="R is unavailable"
        )

    monkeypatch.setattr(validator.subprocess, "run", fake_run)

    with pytest.raises(validator.ValidationError, match="R is unavailable"):
        validator.report_installed_versions("Rscript", ["metafor"])


def test_default_r_dependency_install_uses_script_file_and_archive_triples(
    monkeypatch, tmp_path
):
    import importlib.util

    verifier_path = REPO_ROOT / "scripts" / "verify_rcmetar_r_default.py"
    spec = importlib.util.spec_from_file_location(
        "verify_rcmetar_r_default", verifier_path
    )
    verifier = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(verifier)

    captured = {}

    def fake_run_streamed(command, cwd, env):
        install_script = Path(command[1])
        assert install_script.exists()
        assert install_script.suffix == ".R"
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        captured["source"] = install_script.read_text(encoding="utf-8")

    monkeypatch.setattr(verifier, "run_streamed", fake_run_streamed)

    library = tmp_path / "library"
    verifier.install_direct_dependencies(
        REPO_ROOT,
        Path("Rscript"),
        library,
        "https://packagemanager.posit.co/cran/2026-07-16",
        {"R_LIBS_USER": str(library)},
    )

    assert captured["cwd"] == REPO_ROOT
    assert captured["env"]["R_LIBS_USER"] == str(library)
    assert captured["command"][0] == Path("Rscript")
    assert captured["command"][2:] == [REPO_ROOT, library]
    assert captured["env"]["RCMS_CRAN_REPO"].endswith("/cran/2026-07-16")
    assert captured["env"]["RCMS_POLICY_PYTHON"] == sys.executable
    source = captured["source"]
    assert "r_binary_policy.R" in source
    assert "install_rcms_binary_packages" in source
    assert "install_rcms_source_exception" in source


def test_native_r_binary_policy_fails_closed_without_source_fallback(tmp_path):
    rscript = shutil.which("Rscript")
    if rscript is None and sys.platform == "win32":
        candidate = Path("C:/Program Files/R/R-4.6.1/bin/Rscript.exe")
        rscript = str(candidate) if candidate.is_file() else None
    assert rscript is not None, (
        "Rscript 4.6.1 is required by the Fast verification environment"
    )

    checked_installer = subprocess.run(
        [rscript, str(REPO_ROOT / "scripts" / "install-rcmetar-source.R")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert checked_installer.returncode != 0
    assert "requires exactly SOURCE and LIBRARY arguments" in checked_installer.stderr

    helper = (REPO_ROOT / "scripts" / "r_binary_policy.R").as_posix()
    root = REPO_ROOT.as_posix()
    library = tmp_path.as_posix()
    r_code = f"""
source({json.dumps(helper)})
policy <- load_rcms_r_binary_policy({json.dumps(root)})
expect_error <- function(expression, pattern) {{
  error <- tryCatch({{ force(expression); NULL }}, error = identity)
  if (is.null(error) || !grepl(pattern, conditionMessage(error), fixed = TRUE)) {{
    stop("Expected error containing '", pattern, "'")
  }}
}}
expect_error(assert_rcms_binary_runtime(policy, r_version = "4.6.0"), "requires R 4.6.1")
expect_error(assert_rcms_binary_runtime(policy, arch = "unsupported"), "Unsupported R binary target")
expect_error(assert_rcms_binary_runtime(policy, pkg_type = "source"), "Unexpected native R binary type")

empty_db <- matrix(character(), nrow = 0, ncol = 3,
  dimnames = list(character(), c("Depends", "Imports", "LinkingTo")))
install_called <- FALSE
expect_error(
  install_rcms_binary_packages(
    policy,
    {json.dumps(library)},
    database = empty_db,
    install_binary = function(...) {{ install_called <<- TRUE }}
  ),
  "Required native R binaries unavailable"
)
if (install_called) stop("missing binary preflight attempted an install")

platform <- assert_rcms_binary_runtime(policy)
archive_extension <- rcms_binary_archive_extension(platform)
one_archive <- tempfile(fileext = paste0(".", archive_extension))
file.create(one_archive)
one_row_no_dimnames <- matrix(c("root", one_archive), nrow = 1L)
if (!identical(normalize_rcms_downloaded_archives(one_row_no_dimnames, 1L, platform), one_archive)) {{
  stop("one-row download result without dimnames was not normalized positionally")
}}
two_archives <- c(
  tempfile(fileext = paste0(".", archive_extension)),
  tempfile(fileext = paste0(".", archive_extension))
)
file.create(two_archives)
multi_row <- matrix(c("root", two_archives[[1]], "transitive", two_archives[[2]]), nrow = 2L, byrow = TRUE)
if (!identical(normalize_rcms_downloaded_archives(multi_row, 2L, platform), two_archives)) {{
  stop("multi-row download result was not normalized positionally")
}}
expect_error(
  normalize_rcms_downloaded_archives(matrix(c("missing", tempfile()), nrow = 1L), 1L, platform),
  "PPM retained binary archive is missing"
)
mismatched_extension <- if (identical(archive_extension, "zip")) ".tgz" else ".zip"
mismatched_archive <- tempfile(fileext = mismatched_extension)
file.create(mismatched_archive)
expect_error(
  normalize_rcms_downloaded_archives(
    matrix(c("wrong-format", mismatched_archive), nrow = 1L), 1L, platform
  ),
  paste0("non-.", archive_extension, " archive")
)

binary_type <- NULL
binary_dependencies <- NULL
installed_packages <- "root"
globally_available_packages <- c("root", "transitive")
binary_policy <- policy
binary_policy$normal_packages <- "root"
binary_db <- matrix("", nrow = 2, ncol = 3,
  dimnames = list(c("root", "transitive"), c("Depends", "Imports", "LinkingTo")))
binary_db["root", "Imports"] <- "transitive"
install_rcms_binary_packages(
  binary_policy,
  {json.dumps(library)},
  database = binary_db,
  install_binary = function(packages, lib, dependencies, type) {{
    binary_type <<- type
    binary_dependencies <<- dependencies
    installed_packages <<- union(installed_packages, packages)
  }},
  installed_in_target = function() installed_packages,
  package_loadable = function(package) package %in% installed_packages
)
if (!identical(binary_type, "binary")) stop("ordinary package install was not binary-only")
if (!identical(binary_dependencies, FALSE)) stop("closure install attempted dependency resolution")
if (!"transitive" %in% installed_packages) {{
  stop("globally available transitive dependency was not installed into the target library")
}}

installed_packages <- "root"
evidence <- tempfile()
Sys.setenv(RCMS_R_BINARY_EVIDENCE = evidence)
expect_error(
  install_rcms_binary_packages(
    binary_policy,
    {json.dumps(library)},
    database = binary_db,
    install_binary = function(...) NULL,
    installed_in_target = function() installed_packages,
    package_loadable = function(package) package %in% globally_available_packages
  ),
  "Complete binary closure missing from target library"
)
if (file.exists(evidence) && file.info(evidence)$size > 0) {{
  stop("incomplete target-local closure emitted cacheable evidence")
}}
Sys.unsetenv("RCMS_R_BINARY_EVIDENCE")

tamper_policy <- policy
tamper_policy$source_exception$dependencies <- "stats"
source_called <- FALSE
expect_error(
  install_rcms_source_exception(
    tamper_policy,
    {json.dumps(library)},
    download = function(url, destination, ...) writeBin(charToRaw("tampered"), destination),
    install_source = function(...) {{ source_called <<- TRUE }},
    sha256 = function(path) paste(rep("0", 64), collapse = "")
  ),
  "SHA256 mismatch"
)
if (source_called) stop("digest mismatch attempted the HSROC source install")
"""
    env = dict(os.environ)
    env["RCMS_POLICY_PYTHON"] = sys.executable
    env["RCMS_CRAN_REPO"] = "https://packagemanager.posit.co/cran/2026-07-16"
    policy_test = tmp_path / "native-binary-policy-test.R"
    policy_test.write_text(r_code, encoding="utf-8")
    result = subprocess.run(
        [rscript, str(policy_test)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_default_r_verifier_resolves_rscript_from_r_home(tmp_path):
    import importlib.util

    verifier_path = REPO_ROOT / "scripts" / "verify_rcmetar_r_default.py"
    spec = importlib.util.spec_from_file_location(
        "verify_rcmetar_r_default", verifier_path
    )
    verifier = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(verifier)

    r_home = tmp_path / "R"
    rscript = r_home / "bin" / verifier._candidate_rscript_names()[0]
    rscript.parent.mkdir(parents=True)
    rscript.write_text("", encoding="utf-8")

    resolved = verifier.resolve_rscript(
        "Rscript", env={"RCMS_R_HOME": str(r_home), "PATH": ""}
    )

    assert resolved == rscript.resolve()


def test_default_r_verifier_resolves_rscript_from_r_command(monkeypatch, tmp_path):
    import importlib.util

    verifier_path = REPO_ROOT / "scripts" / "verify_rcmetar_r_default.py"
    spec = importlib.util.spec_from_file_location(
        "verify_rcmetar_r_default", verifier_path
    )
    verifier = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(verifier)

    r_home = tmp_path / "R"
    rscript = r_home / "bin" / verifier._candidate_rscript_names()[0]
    rscript.parent.mkdir(parents=True)
    rscript.write_text("", encoding="utf-8")
    fake_r = (
        tmp_path
        / "bin"
        / verifier._candidate_rscript_names()[0].replace("Rscript", "R")
    )
    fake_r.parent.mkdir(parents=True)
    fake_r.write_text("", encoding="utf-8")

    def fake_which(name, path=None):
        if name == "R":
            return str(fake_r)
        return None

    def fake_run(command, env, text, stdout, stderr, check):
        assert command == [str(fake_r), "RHOME"]
        return subprocess.CompletedProcess(command, 0, stdout=str(r_home), stderr="")

    monkeypatch.setattr(verifier.r_support.shutil, "which", fake_which)
    monkeypatch.setattr(verifier.r_support.subprocess, "run", fake_run)

    resolved = verifier.resolve_rscript("Rscript", env={"PATH": ""})

    assert resolved == rscript.resolve()


def test_default_r_RCMetaR_install_preserves_dependency_libraries(
    monkeypatch, tmp_path
):
    import importlib.util

    verifier_path = REPO_ROOT / "scripts" / "verify_rcmetar_r_default.py"
    spec = importlib.util.spec_from_file_location(
        "verify_rcmetar_r_default", verifier_path
    )
    verifier = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(verifier)

    dependency_library = tmp_path / "dependency-library"
    dependency_library.mkdir()
    r_exe = tmp_path / "R.exe"
    r_exe.write_text("", encoding="utf-8")
    captured_envs = []

    monkeypatch.setattr(verifier, "resolve_r_exe", lambda root, rscript, env: r_exe)

    def fake_run(command, cwd, env):
        captured_envs.append(dict(env))
        return subprocess.CompletedProcess(command, 0, stdout="OK\n", stderr="")

    monkeypatch.setattr(verifier, "run", fake_run)

    verifier.install_and_load_RCMetaR(
        REPO_ROOT,
        Path("Rscript"),
        {
            "R_LIBS": str(dependency_library),
            "R_LIBS_USER": str(dependency_library),
        },
    )

    assert len(captured_envs) == 2
    install_env = captured_envs[0]
    install_library, preserved_library = install_env["R_LIBS"].split(
        verifier.os.pathsep
    )
    assert Path(install_library).name == "library"
    assert preserved_library == str(dependency_library)
    assert install_env["R_LIBS_USER"] == str(dependency_library)


def read_description_fields():
    fields = {}
    current_key = None
    for line in RCMetaR_DESCRIPTION.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        if line[0].isspace() and current_key is not None:
            fields[current_key] += " " + line.strip()
            continue
        key, value = line.split(":", 1)
        current_key = key
        fields[key] = value.strip()
    return fields


def parse_packages(field_value):
    packages = set()
    for entry in field_value.split(","):
        name = entry.strip().split(" ", 1)[0]
        if name:
            packages.add(name)
    return packages


def legacy_exported_functions_from_source():
    names = set()
    for path in RCMetaR_R_DIR.glob("*.R"):
        text = path.read_text(encoding="utf-8")
        names.update(LEGACY_EXPORT_PATTERN.findall(text))
        names.update(match.group(1) for match in LEGACY_ALIAS_PATTERN.finditer(text))
    return names


def s4_classes_from_source():
    names = set()
    for path in RCMetaR_R_DIR.glob("*.R"):
        names.update(S4_CLASS_PATTERN.findall(path.read_text(encoding="utf-8")))
    return names


def namespace_entries(directive):
    text = RCMetaR_NAMESPACE.read_text(encoding="utf-8")
    entries = set()
    for match in re.finditer(rf"^{directive}\(([^)]*)\)$", text, flags=re.MULTILINE):
        entries.update(
            name.strip() for name in match.group(1).split(",") if name.strip()
        )
    return entries


def test_RCMetaR_description_declares_only_direct_package_dependencies():
    fields = read_description_fields()

    assert parse_packages(fields["Depends"]) == {"R"}
    assert parse_packages(fields["Imports"]) == {
        "boot",
        "grDevices",
        "graphics",
        "HSROC",
        "lme4",
        "methods",
        "metafor",
        "pdftools",
        "rsvg",
        "stats",
        "svglite",
        "tiff",
        "utils",
        "xml2",
    }
    assert parse_packages(fields["Suggests"]) == {"coda", "roxygen2", "testthat"}
    assert "igraph" not in fields["Imports"]
    assert "Hmisc" not in fields["Imports"]
    assert "exportPattern" not in RCMetaR_NAMESPACE.read_text(encoding="utf-8")


def test_RCMetaR_namespace_exports_only_core_interface():
    actual_exports = namespace_entries("export")

    assert actual_exports == RCMetaR_PUBLIC_EXPORTS
    assert all(name.startswith("rcmetar.") for name in actual_exports)
    assert (
        not {
            "binary.random",
            "binary.random.parameters",
            "diagnostic.hsroc.pretty.names",
            "forest.plot",
            "gimpute.cont.data",
            "set.global.conf.level",
        }
        & actual_exports
    )


def test_RCMetaR_namespace_preserves_s4_classes_explicitly():
    expected_classes = s4_classes_from_source()
    actual_classes = namespace_entries("exportClasses")

    assert actual_classes == expected_classes
