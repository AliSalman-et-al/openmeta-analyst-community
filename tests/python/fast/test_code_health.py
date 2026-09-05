from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from complexipy import code_complexity

from scripts.code_health import (
    build_evidence,
    changed_lines,
    compare_to_baseline,
    gate,
    git_as_of,
    history_for_path,
    load_config,
    python_metrics,
    runtime_changed_function_keys,
    typing_measurement,
)


ROOT = Path(__file__).resolve().parents[3]


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(cwd: Path, message: str, timestamp: str) -> str:
    env = os.environ | {
        "GIT_AUTHOR_NAME": "Code Health Test",
        "GIT_AUTHOR_EMAIL": "code-health@example.test",
        "GIT_COMMITTER_NAME": "Code Health Test",
        "GIT_COMMITTER_EMAIL": "code-health@example.test",
        "GIT_AUTHOR_DATE": timestamp,
        "GIT_COMMITTER_DATE": timestamp,
    }
    subprocess.run(["git", "add", "src/pkg.py"], cwd=cwd, check=True, env=env)
    subprocess.run(["git", "commit", "-m", message], cwd=cwd, check=True, env=env, capture_output=True)
    return _git(cwd, "rev-parse", "HEAD")


def test_code_health_emits_machine_readable_evidence_and_report(tmp_path: Path) -> None:
    output = tmp_path / "evidence.json"
    report = tmp_path / "report.txt"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/code_health.py",
            "--base",
            "4aa0740",
            "--head",
            "HEAD",
            "--output",
            str(output),
            "--report",
            str(report),
            "--allow-fail",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert set(payload["files"][0]["churn"]) == {"30", "90", "180"}
    assert "hotspot_score" in payload["files"][0]
    assert {"coupling", "cycles", "cognitive_complexity", "maintainability", "defect_history", "gate"} <= payload.keys()
    assert payload["typing"]["tool"] == "ast"
    assert payload["typing"]["revision"] == payload["head"]
    assert payload["requested_head"] == "HEAD"
    assert {
        "total_parameters",
        "total_functions",
        "annotated_parameters",
        "annotated_returns",
        "parameter_coverage",
        "return_coverage",
        "any_annotations",
        "type_ignore_directives",
        "cast_to_any",
    } <= payload["typing"].keys()
    assert payload["dependency_tooling"]["tool"] == "grimp"
    assert "Code health" in report.read_text(encoding="utf-8")
    assert "Code health" in result.stdout


def test_baseline_comparison_uses_recorded_artifact_measurements() -> None:
    def snapshot(edges: int) -> dict[str, object]:
        return {
            "schema_version": 1,
            "head": "recorded-head",
            "scope": ["src/pkg.py"],
            "files": [{"path": "src/pkg.py", "hotspot_score": 0.25}],
            "coupling": {"modules": 1, "edges": edges},
            "cycles": [],
            "cognitive_complexity": {"total": 2, "maximum": 2},
            "maintainability": {"mean_function_lines": 4.0},
            "defect_history": {"commits": 1},
            "typing": {
                "total_parameters": 1,
                "total_functions": 1,
                "annotated_parameters": 1,
                "annotated_returns": 1,
                "parameter_coverage": 1.0,
                "return_coverage": 1.0,
                "any_annotations": 0,
                "type_ignore_directives": 0,
                "cast_to_any": 0,
            },
        }

    comparison = compare_to_baseline(
        snapshot(3), snapshot(1), "artifacts/code-health/baseline.json"
    )

    assert comparison["path"] == "artifacts/code-health/baseline.json"
    assert comparison["baseline_head"] == "recorded-head"
    assert comparison["metrics"]["coupling.edges"] == {
        "baseline": 1,
        "current": 3,
        "delta": 2,
    }


def test_history_for_path_stops_at_measured_revision(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "src").mkdir()
    source = tmp_path / "src/pkg.py"
    source.write_text("value = 1\n", encoding="utf-8")
    _commit(tmp_path, "Add source", "2025-01-01T00:00:00+00:00")
    source.write_text("value = 2\n", encoding="utf-8")
    baseline = _commit(tmp_path, "Fix baseline", "2025-01-10T00:00:00+00:00")
    source.write_text("value = 3\n", encoding="utf-8")
    head = _commit(tmp_path, "Fix later branch", "2025-01-20T00:00:00+00:00")

    as_of = git_as_of(tmp_path, None, baseline)
    churn, defects = history_for_path(tmp_path, "src/pkg.py", as_of, baseline)
    head_as_of = git_as_of(tmp_path, None, head)
    head_churn, head_defects = history_for_path(tmp_path, "src/pkg.py", head_as_of, head)

    assert defects == 1
    assert churn["180"] < head_churn["180"]
    assert head_defects == 2


def test_python_metrics_uses_complexipy_at_each_revision(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "src").mkdir()
    source = tmp_path / "src/pkg.py"
    source.write_text("def measure(value):\n    return value\n", encoding="utf-8")
    baseline = _commit(tmp_path, "Add source", "2025-01-01T00:00:00+00:00")
    source.write_text(
        "def measure(value):\n"
        "    if value:\n"
        "        if value > 1:\n"
        "            return value\n"
        "    return 0\n",
        encoding="utf-8",
    )
    head = _commit(tmp_path, "Increase cognitive complexity", "2025-01-02T00:00:00+00:00")

    baseline_metric = python_metrics(tmp_path, ["src/pkg.py"], baseline)[0]
    head_metric = python_metrics(tmp_path, ["src/pkg.py"], head)[0]
    baseline_source = _git(tmp_path, "show", f"{baseline}:src/pkg.py")
    head_source = _git(tmp_path, "show", f"{head}:src/pkg.py")

    assert baseline_metric.cognitive == code_complexity(baseline_source).functions[0].complexity
    assert head_metric.cognitive == code_complexity(head_source).functions[0].complexity
    assert head_metric.cognitive > baseline_metric.cognitive


def test_typing_measurement_reads_the_named_revision(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "src").mkdir()
    source = tmp_path / "src/pkg.py"
    source.write_text("def measure(value):\n    return value\n", encoding="utf-8")
    baseline = _commit(tmp_path, "Add source", "2025-01-01T00:00:00+00:00")
    source.write_text(
        "from typing import Any, cast\n\n"
        "def measure(value: Any) -> Any:  # type: ignore\n"
        "    return cast(Any, value)\n",
        encoding="utf-8",
    )
    head = _commit(tmp_path, "Add typing signals", "2025-01-02T00:00:00+00:00")

    before = typing_measurement(tmp_path, ["src/pkg.py"], baseline)
    after = typing_measurement(tmp_path, ["src/pkg.py"], head)

    assert before["total_parameters"] == 1
    assert after["total_parameters"] == 1
    assert before["annotated_parameters"] == 0
    assert after["annotated_parameters"] == 1
    assert after["annotated_returns"] == 1
    assert after["any_annotations"] == 2
    assert after["type_ignore_directives"] == 1
    assert after["cast_to_any"] == 1


def test_head_evidence_ignores_dirty_tracked_source(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "config").mkdir()
    (tmp_path / "src/rc_metastudio").mkdir(parents=True)
    (tmp_path / "config/code-health.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_roots": ["src/rc_metastudio"],
                "python_suffixes": [".py"],
                "r_suffixes": [],
                "exclude_globs": [],
                "forbidden_imports": {},
                "complexity_exceptions": {},
                "gates": {
                    "max_changed_cyclomatic": 15,
                    "max_changed_cognitive": 20,
                    "max_changed_nesting": 4,
                    "block_new_cycles": True,
                    "block_forbidden_imports": True,
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "src/rc_metastudio/__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src/rc_metastudio/dep.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "src/rc_metastudio/extra.py").write_text("VALUE = 2\n", encoding="utf-8")
    source = tmp_path / "src/rc_metastudio/pkg.py"
    source.write_text(
        "from .dep import VALUE\n\n"
        "def measure(value: int) -> int:\n"
        "    return value\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    commit_env = os.environ | {
        "GIT_AUTHOR_NAME": "Code Health Test",
        "GIT_AUTHOR_EMAIL": "code-health@example.test",
        "GIT_COMMITTER_NAME": "Code Health Test",
        "GIT_COMMITTER_EMAIL": "code-health@example.test",
        "GIT_AUTHOR_DATE": "2025-01-01T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2025-01-01T00:00:00+00:00",
    }
    subprocess.run(
        ["git", "commit", "-m", "Add package"],
        cwd=tmp_path,
        check=True,
        env=commit_env,
        capture_output=True,
    )
    commit = _git(tmp_path, "rev-parse", "HEAD")
    config = load_config(tmp_path)
    clean = build_evidence(tmp_path, "HEAD", "HEAD", git_as_of(tmp_path, None, "HEAD"), config)

    source.write_text(
        "from .extra import VALUE\n\n"
        "def measure(value):\n"
        "    if value:\n"
        "        return value\n"
        "    return VALUE\n",
        encoding="utf-8",
    )
    dirty = build_evidence(tmp_path, "HEAD", "HEAD", git_as_of(tmp_path, None, "HEAD"), config)

    assert clean["head"] == commit
    assert dirty["head"] == commit
    assert dirty["requested_head"] == "HEAD"
    assert dirty["functions"] == clean["functions"]
    assert dirty["coupling"] == clean["coupling"]
    assert dirty["typing"] == clean["typing"]


def test_gate_ignores_annotation_only_function_changes(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "src").mkdir()
    source = tmp_path / "src/pkg.py"
    body = "\n".join(["    if value:", "        value += 1"] * 16)
    source.write_text(f"def calculate(value):\n{body}\n    return value\n", encoding="utf-8")
    baseline = _commit(tmp_path, "Add complex function", "2025-01-01T00:00:00+00:00")
    source.write_text(
        "from typing import Any, cast\n\n"
        f"def calculate(value: Any) -> int:\n{body}\n    return cast(int, value)\n",
        encoding="utf-8",
    )
    head = _commit(tmp_path, "Refine type annotations", "2025-01-02T00:00:00+00:00")

    metrics = python_metrics(tmp_path, ["src/pkg.py"], head)
    changed = changed_lines(tmp_path, baseline, head)
    runtime_changed = runtime_changed_function_keys(tmp_path, baseline, head, metrics, changed)
    result = gate(metrics, changed, load_config(ROOT), [], [], [], [], runtime_changed)

    assert metrics[0].cyclomatic > 15
    assert runtime_changed == set()
    assert result["passed"] is True

    source.write_text(
        "from typing import Any, cast\n\n"
        f"def calculate(value: Any) -> int:\n{body}\n    return cast(int, value + 1)\n",
        encoding="utf-8",
    )
    runtime_head = _commit(tmp_path, "Change runtime result", "2025-01-03T00:00:00+00:00")
    runtime_metrics = python_metrics(tmp_path, ["src/pkg.py"], runtime_head)
    runtime_diff = changed_lines(tmp_path, head, runtime_head)

    assert runtime_changed_function_keys(tmp_path, head, runtime_head, runtime_metrics, runtime_diff)
