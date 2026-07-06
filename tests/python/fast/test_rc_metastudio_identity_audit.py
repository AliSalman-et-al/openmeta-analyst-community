import importlib.util
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
AUDIT_SCRIPT = REPO_ROOT / "scripts" / "audit_rc_metastudio_identity.py"


def load_audit_module():
    spec = importlib.util.spec_from_file_location("rcms_identity_audit", AUDIT_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_audit(root):
    return subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT), "--root", str(root)],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def legacy_product_name():
    return "Open" + "MetaAnalyst"


def legacy_bracketed_product_name():
    return "OpenMeta" + "[Analyst]"


def retired_project_extension():
    return "." + "oma"


def retired_env_name():
    return "O" + "MA_STUB_BACKEND"


def legacy_r_package_name():
    return "Open" + "MetaR"


def legacy_r_facade_name():
    return "open" + "metar.run.analysis"


def test_identity_boundary_constants_define_rc_metastudio_names():
    audit = load_audit_module()

    assert audit.SUPPORTED_PROJECT_EXTENSION == ".rcms"
    assert audit.RETIRED_PROJECT_EXTENSIONS == {retired_project_extension()}
    assert audit.R_PACKAGE_NAME == "RCMetaR"
    assert audit.R_FACADE_PREFIX == "rcmetar."


def test_identity_audit_reports_forbidden_tokens_across_active_surfaces(tmp_path):
    write_text(tmp_path / "src" / "app.py", f'title = "{legacy_product_name()}"\n')
    write_text(
        tmp_path / "docs" / "usage.md",
        f"Save as project{retired_project_extension()}\n",
    )
    write_text(
        tmp_path / "scripts" / "run.ps1",
        f"$env:{retired_env_name()} = '1'\n",
    )
    write_text(
        tmp_path / "src" / "bridge.py",
        f'pkg = "{legacy_r_package_name()}"\ncall = "{legacy_r_facade_name()}"\n',
    )
    write_text(
        tmp_path / "src" / "forms" / "project.ui",
        f"<string>open meta files (*{retired_project_extension()})</string>\n",
    )

    result = run_audit(tmp_path)

    assert result.returncode == 1
    assert "legacy-product-compact" in result.stdout
    assert "legacy-project-extension" in result.stdout
    assert "legacy-env-prefix" in result.stdout
    assert "legacy-r-package" in result.stdout
    assert "legacy-r-facade" in result.stdout


def test_identity_audit_allows_history_provenance_and_original_headers(tmp_path):
    write_text(
        tmp_path / "docs" / "adr" / "0001-history.md",
        f"# Historical decision about {legacy_product_name()}\n",
    )
    write_text(
        tmp_path / "NOTICE.md",
        f"RC MetaStudio is derived from {legacy_bracketed_product_name()}.\n",
    )
    write_text(
        tmp_path / "docs" / "contexts" / "project-provenance" / "CONTEXT.md",
        f"Original {legacy_bracketed_product_name()} Project: historical provenance term.\n",
    )
    write_text(
        tmp_path / "src" / "module.py",
        f"# Original header: {legacy_bracketed_product_name()}\n"
        "# CEBM @ Brown\n"
        "\n"
        'PRODUCT_NAME = "RC MetaStudio"\n',
    )

    result = run_audit(tmp_path)

    assert result.returncode == 0, result.stdout
    assert "identity audit passed" in result.stdout


def test_identity_audit_accepts_current_project_and_rcmetar_boundaries(tmp_path):
    write_text(
        tmp_path / "src" / "bridge.py",
        'package = "RCMetaR"\n'
        'function_name = "rcmetar.run.analysis"\n'
        'sample_project = "amino.rcms"\n',
    )
    write_text(
        tmp_path / "pyproject.toml",
        'name = "rc-metastudio"\n'
        'description = "RC MetaStudio environment."\n',
    )

    result = run_audit(tmp_path)

    assert result.returncode == 0, result.stdout


def test_identity_audit_json_report_is_machine_readable(tmp_path):
    write_text(
        tmp_path / "tests" / "fixture.py",
        f'path = "sample{retired_project_extension()}"\n',
    )

    result = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT), "--root", str(tmp_path), "--json"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 1
    assert '"rule": "legacy-project-extension"' in result.stdout
    assert '"path": "tests/fixture.py"' in result.stdout
