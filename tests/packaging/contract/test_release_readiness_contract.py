import importlib.util
import shutil
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
RCMetaR_DESCRIPTION = ROOT / "r" / "RCMetaR" / "DESCRIPTION"


def read_text(*parts):
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


def read_description_fields(path):
    fields = {}
    current_key = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        if line[0].isspace() and current_key is not None:
            fields[current_key] += " " + line.strip()
            continue
        key, value = line.split(":", 1)
        current_key = key
        fields[key] = value.strip()
    return fields


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def retired_r_artifact_stem():
    return "open" + "metar_1.0"


def retired_spec_pattern():
    return "Open" + "MetaAnalyst*.spec"


def test_rc_metastudio_and_rcmetar_versions_are_aligned_for_release():
    pyproject = tomllib.loads(read_text("pyproject.toml"))
    project_version = pyproject["project"]["version"]
    package = load_module(
        "rc_metastudio_for_release_contract", SRC / "rc_metastudio" / "__init__.py"
    )
    meta_globals = load_module(
        "meta_globals_for_release_contract", SRC / "rc_metastudio" / "meta_globals.py"
    )
    rcmetar_fields = read_description_fields(RCMetaR_DESCRIPTION)

    assert package.__version__ == project_version
    assert str(meta_globals.VERSION) == project_version
    assert rcmetar_fields["Version"] == project_version


def test_version_bump_script_updates_all_release_version_surfaces(tmp_path):
    paths_to_copy = [
        "pyproject.toml",
        "uv.lock",
        "CHANGELOG.md",
        "src/rc_metastudio/__init__.py",
        "src/rc_metastudio/meta_globals.py",
        "r/RCMetaR/DESCRIPTION",
    ]
    for relative_path in paths_to_copy:
        source = ROOT / relative_path
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    bump_version = load_module(
        "bump_version_for_release_contract", ROOT / "scripts" / "bump_version.py"
    )
    result = bump_version.main(
        ["0.2.0", "--root", str(tmp_path), "--date", "2026-08-09"]
    )

    assert result == 0
    pyproject = tomllib.loads((tmp_path / "pyproject.toml").read_text("utf-8"))
    package = load_module(
        "rc_metastudio_after_bump", tmp_path / "src" / "rc_metastudio" / "__init__.py"
    )
    meta_globals = load_module(
        "meta_globals_after_bump",
        tmp_path / "src" / "rc_metastudio" / "meta_globals.py",
    )
    rcmetar_fields = read_description_fields(tmp_path / "r" / "RCMetaR" / "DESCRIPTION")
    lockfile = (tmp_path / "uv.lock").read_text("utf-8")
    changelog = (tmp_path / "CHANGELOG.md").read_text("utf-8")

    assert pyproject["project"]["version"] == "0.2.0"
    assert package.__version__ == "0.2.0"
    assert meta_globals.VERSION == "0.2.0"
    assert rcmetar_fields["Version"] == "0.2.0"
    assert rcmetar_fields["Date"] == "2026-08-09"
    assert 'name = "rc-metastudio"\nversion = "0.2.0"' in lockfile
    assert "## 0.2.0 - Unreleased" in changelog


def test_active_rcmetar_package_metadata_uses_current_maintainer_identity():
    fields = read_description_fields(RCMetaR_DESCRIPTION)
    description = RCMetaR_DESCRIPTION.read_text(encoding="utf-8")
    package_rd = read_text("r", "RCMetaR", "man", "rcmetar-package.Rd")

    assert fields["Maintainer"] == "Ali Salman <alisalman.et.al@gmail.com>"
    assert 'person("Ali", "Salman"' in fields["Authors@R"]
    assert 'role = c("aut", "cre")' in fields["Authors@R"]
    assert "Research Consultancy" in fields["Authors@R"]
    assert "tuftsmedicalcenter.org" not in description
    assert "tuftsmedicalcenter.org" not in package_rd
    retired_package_maintainer = "Paul " + "Trow"
    retired_package_author = "Byron " + "Wallace"
    assert f"{retired_package_maintainer} <" not in description
    assert f"{retired_package_maintainer} \\email" not in package_rd
    assert f"{retired_package_author} \\email" not in package_rd


def test_release_readiness_text_does_not_invert_current_identity():
    changelog = read_text("CHANGELOG.md")
    inventory = read_text("docs", "release", "third-party-inventory.md")

    assert "Original RC MetaStudio Project" not in changelog
    assert "Original RC MetaStudio Project" not in inventory
    assert "away from `.rcms`, RCMetaR" not in changelog
    assert "Original OpenMeta[Analyst] Project" in changelog
    assert "Original OpenMeta[Analyst] Project" in inventory


def test_gitignore_uses_current_release_artifact_patterns():
    ignored = {
        line.strip()
        for line in read_text(".gitignore").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "RCMetaR_*.tar.gz" in ignored
    assert "RCMetaR_*.zip" in ignored
    assert retired_r_artifact_stem() + ".tar.gz" not in ignored
    assert retired_r_artifact_stem() + ".zip" not in ignored
    assert retired_spec_pattern() not in ignored
    assert "src/" + retired_spec_pattern() not in ignored
