import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = REPO_ROOT / "scripts" / "validate_RCMetaR_r_manifests.py"
DEPENDENCY_MANIFEST = Path("docs") / "verification" / "RCMetaR-r-dependencies.json"
DRIFT_MANIFEST = Path("docs") / "verification" / "RCMetaR-statistical-drift.json"
RCMetaR_PACKAGE = REPO_ROOT / "r" / "RCMetaR"
RCMetaR_R_DIR = RCMetaR_PACKAGE / "R"
RCMetaR_DESCRIPTION = RCMetaR_PACKAGE / "DESCRIPTION"
RCMetaR_NAMESPACE = RCMetaR_PACKAGE / "NAMESPACE"
APP_SRC = REPO_ROOT / "src" / "rc_metastudio"

LEGACY_EXPORT_PATTERN = re.compile(
    r"^([A-Za-z][A-Za-z0-9._]*)\s*<-\s*function\s*\(", re.MULTILINE
)
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


def copy_verification_docs(tmp_path):
    docs_root = tmp_path / "docs" / "verification"
    shutil.copytree(REPO_ROOT / "docs" / "verification", docs_root)
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


def test_direct_and_app_bundle_dependencies_must_stay_separate(tmp_path):
    root = copy_verification_docs(tmp_path)
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
    root = copy_verification_docs(tmp_path)
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
    root = copy_verification_docs(tmp_path)
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
    root = copy_verification_docs(tmp_path)
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

    monkeypatch.setattr(
        verifier,
        "direct_dependency_policy",
        lambda root: (["metafor", "testthat"], {"HSROC": "2.1.9"}),
    )
    captured = {}

    def fake_run_streamed(command, cwd, env):
        install_script = Path(command[1])
        assert install_script.exists()
        assert install_script.suffix == ".R"
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env

    monkeypatch.setattr(verifier, "run_streamed", fake_run_streamed)

    library = tmp_path / "library"
    verifier.install_direct_dependencies(
        REPO_ROOT,
        Path("Rscript"),
        library,
        "https://cloud.r-project.org",
        {"R_LIBS_USER": str(library)},
    )

    assert captured["cwd"] == REPO_ROOT
    assert captured["env"]["R_LIBS_USER"] == str(library)
    assert captured["command"][0] == Path("Rscript")
    assert captured["command"][2:5] == [
        library,
        "https://cloud.r-project.org",
        "MCMCpack,coda,metafor,testthat",
    ]
    assert captured["command"][5:] == [
        "HSROC",
        "2.1.9",
        "https://cran.r-project.org/src/contrib/Archive/HSROC/HSROC_2.1.9.tar.gz",
    ]


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

    monkeypatch.setattr(verifier.shutil, "which", fake_which)
    monkeypatch.setattr(verifier.subprocess, "run", fake_run)

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


def test_custom_grid_forest_engine_is_retired():
    source_text = "\n".join(
        path.read_text(encoding="utf-8") for path in RCMetaR_R_DIR.glob("*.R")
    )

    retired_function_defs = {
        "forest.plot",
        "draw.forest.plot",
        "draw.data.col",
        "two.forest.plots",
        "create.grobs",
        "calc.viewport.layout",
        "calc.forest.plot.size",
        "draw.normal.CI",
        "draw.summary.CI",
        "draw.summary.CI.no.scaled.diamond",
    }
    defined_functions = set(LEGACY_EXPORT_PATTERN.findall(source_text))

    assert defined_functions.isdisjoint(retired_function_defs)
    assert "fp_legacy_renderer" not in source_text
    assert re.search(r"\b(?:grid\.|grid[A-Z_a-z])", source_text) is None


def test_RCMetaR_source_uses_namespace_imports_instead_of_attach_calls():
    package_attach_pattern = re.compile(r"\b(?:library|require)\s*\(")

    offenders = []
    for path in RCMetaR_R_DIR.glob("*.R"):
        if package_attach_pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(path.relative_to(REPO_ROOT).as_posix())

    assert offenders == []


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


def test_python_app_calls_r_through_meta_py_r_adapter():
    offenders = []
    for path in APP_SRC.glob("*.py"):
        if path.name in {
            "meta_py_r.py",
            # The native macOS feasibility probe is deployment qualification,
            # not an application analysis path. It must prove rpy2 directly in
            # both source and the frozen probe before the app adapter is loaded.
            "qt6_macos_feasibility.py",
        }:
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"\b(?:execute_r_string|execute_r_function)\s*\(|\bro\.r\b", text):
            offenders.append(path.relative_to(REPO_ROOT).as_posix())

    assert offenders == []


def test_meta_py_r_uses_core_constructors_instead_of_s4_slots():
    text = (APP_SRC / "meta_py_r.py").read_text(encoding="utf-8")

    assert "new('BinaryData'" not in text
    assert "new('ContinuousData'" not in text
    assert "new('DiagnosticData'" not in text
    assert "new('CovariateValues'" not in text
    assert "rcmetar.create.binary.data" in text
    assert "rcmetar.create.continuous.data" in text
    assert "rcmetar.create.diagnostic.data" in text
    assert "rcmetar.create.covariate.values" in text


def test_meta_py_r_does_not_interpolate_user_text_into_r_source():
    text = (APP_SRC / "meta_py_r.py").read_text(encoding="utf-8")
    risky_patterns = [
        r"execute_r_string\([^\n]*(?:%|\.format|\+)",
        r"ro\.r\([^\n]*(?:%|\.format|\+)",
        r"textConnection",
        r"read\.table",
        r"load\('%s",
        r"save\(.*'%s",
        r"png\('%s",
        r"method\.parameters\('%s",
        r"method\.description\('%s",
        r"available\.methods\(.*%s",
    ]

    offenders = [pattern for pattern in risky_patterns if re.search(pattern, text)]

    assert offenders == []


def test_meta_py_r_retired_obsolete_latin1_bridge_hacks():
    text = (APP_SRC / "meta_py_r.py").read_text(encoding="utf-8")

    obsolete_tokens = [
        "_sanitize_for_R",
        "_cchar_to_str_with_latin1_fallback",
        '.decode("latin-1"',
        '.decode("latin1"',
        '.encode("latin-1"',
        '.encode("latin1"',
    ]

    offenders = [token for token in obsolete_tokens if token in text]

    assert offenders == []
