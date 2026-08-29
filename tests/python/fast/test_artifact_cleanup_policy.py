import fnmatch
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
APP_PACKAGE = ROOT / "src" / "rc_metastudio"
RETIRED_PRODUCT_SPEC_PATTERN = "OpenMeta" + "Analyst*.spec"
CURRENT_PRODUCT_SPEC_PATTERNS = (
    "RCMetaStudio*.spec",
    "src/RCMetaStudio*.spec",
)
RETIRED_ARTIFACT_PATTERNS = (
    RETIRED_PRODUCT_SPEC_PATTERN,
    "src/" + RETIRED_PRODUCT_SPEC_PATTERN,
    "open" + "metar_1.0.tar.gz",
    "open" + "metar_1.0.zip",
)

TRACKED_ARTIFACT_PATTERNS = (
    "*.pyc",
    "*.pyo",
    "*/__pycache__/*",
    ".pytest_cache/*",
    ".ruff_cache/*",
    ".mypy_cache/*",
    ".tox/*",
    ".coverage",
    "coverage.xml",
    "htmlcov/*",
    "build/*",
    "dist/*",
    "artifacts/*",
    "r_tmp/*",
    "src/build/*",
    "src/dist/*",
    "*.egg-info/*",
    *CURRENT_PRODUCT_SPEC_PATTERNS,
    "HSROC_2.0.5.tar.gz",
    "RCMetaR_*.tar.gz",
    "RCMetaR_*.zip",
)

REQUIRED_GITIGNORE_PATTERNS = set(TRACKED_ARTIFACT_PATTERNS) | {
    ".venv/",
    ".DS_Store",
    "Thumbs.db",
    ".codex-tmp/",
}

REQUIRED_GITATTRIBUTES = {
    "* text=auto",
    "*.sh text eol=lf",
    "*.ps1 text eol=crlf",
    "*.md text eol=lf",
    "*.py text eol=lf",
    "*.r text eol=lf",
    "*.R text eol=lf",
    "*.json text eol=lf",
    "*.toml text eol=lf",
    "*.yml text eol=lf",
    "*.yaml text eol=lf",
    "*.ui text eol=lf",
    "*.qrc text eol=lf",
    "*.rcms binary",
    "*.png binary",
    "*.ico binary",
}


def _tracked_files():
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _non_comment_lines(path):
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_no_tracked_generated_cache_build_or_runtime_artifacts():
    offenders = []
    for tracked_path in _tracked_files():
        normalized = tracked_path.replace("\\", "/")
        if any(
            fnmatch.fnmatch(normalized, pattern)
            for pattern in TRACKED_ARTIFACT_PATTERNS + RETIRED_ARTIFACT_PATTERNS
        ):
            offenders.append(normalized)

    assert offenders == []


def test_gitignore_blocks_generated_cache_build_and_runtime_artifacts():
    ignored = _non_comment_lines(ROOT / ".gitignore")
    assert sorted(REQUIRED_GITIGNORE_PATTERNS - ignored) == []


def test_gitattributes_normalizes_text_and_keeps_rcms_fixtures_binary():
    attributes = _non_comment_lines(ROOT / ".gitattributes")
    assert sorted(REQUIRED_GITATTRIBUTES - attributes) == []


def test_headless_and_golden_analysis_use_managed_scratch_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("RCMS_ANALYSIS_SCRATCH_DIR", str(tmp_path / "scratch"))

    from rc_metastudio import golden_analysis
    from rc_metastudio import headless_analysis
    from rc_metastudio import analysis_adapter

    created = []
    captured_params = []
    monkeypatch.setattr(
        headless_analysis.settings,
        "make_r_tmp",
        lambda: (
            created.append(headless_analysis.settings.get_r_tmp_path(normalize=True))
            or created[-1]
        ),
    )
    monkeypatch.setattr(
        headless_analysis,
        "load_dataset_model",
        lambda _path: type(
            "Model",
            (),
            {
                "dataset": object(),
                "set_current_metric": lambda self, _metric: None,
                "get_current_outcome_type": lambda self, get_str=False: (
                    headless_analysis.meta_globals.BINARY
                ),
            },
        )(),
    )
    monkeypatch.setattr(
        analysis_adapter.r_bridge,
        "dataset_to_simple_binary_r_object",
        lambda _model, **_kwargs: None,
    )

    def fake_run_binary_analysis(_method, params):
        captured_params.append(params)
        return {"texts": {}, "images": {}}

    monkeypatch.setattr(
        analysis_adapter.r_bridge,
        "run_binary_analysis",
        fake_run_binary_analysis,
    )

    bundle = golden_analysis.curated_golden_bundles(root_dir=ROOT)[0]
    case = headless_analysis.HeadlessAnalysisCase(
        dataset_path=ROOT / "sample_projects" / "amino.rcms",
        method="binary.random",
        parameters=bundle["parameters"],
        metric="OR",
    )
    headless_analysis.run_headless_analysis(case)

    scratch = (tmp_path / "scratch").resolve()
    assert captured_params
    fp_outpath = Path(captured_params[0]["fp_outpath"]).resolve()
    bundle_fp_outpath = Path(bundle["parameters"]["fp_outpath"]).resolve()
    assert created
    assert sorted(set(created)) == [str(scratch)]
    assert fp_outpath.parent == scratch
    assert bundle_fp_outpath.parent == scratch
    assert (ROOT / "r_tmp").resolve() not in fp_outpath.parents
