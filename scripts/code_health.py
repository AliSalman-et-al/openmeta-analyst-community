#!/usr/bin/env python3
"""Emit deterministic code-health metrics and changed-code gates.

The command deliberately uses only the Python standard library and Git.  Its
JSON output is the durable evidence; the text report is a short review aid.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterable, TypedDict, cast

from complexipy import file_complexity
from grimp import build_graph
from radon.complexity import cc_visit_ast
from radon.metrics import mi_visit


class CodeHealthError(RuntimeError):
    """Raised when evidence cannot be produced safely."""


@dataclass(frozen=True)
class FunctionMetric:
    path: str
    name: str
    line: int
    end_line: int
    lines: int
    cyclomatic: int
    cognitive: int
    nesting: int

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "name": self.name,
            "line": self.line,
            "end_line": self.end_line,
            "lines": self.lines,
            "cyclomatic": self.cyclomatic,
            "cognitive": self.cognitive,
            "nesting": self.nesting,
        }


class GateConfig(TypedDict):
    max_changed_cyclomatic: int
    max_changed_cognitive: int
    max_changed_nesting: int
    block_new_cycles: bool
    block_forbidden_imports: bool


class HealthConfig(TypedDict):
    schema_version: int
    source_roots: list[str]
    python_suffixes: list[str]
    r_suffixes: list[str]
    exclude_globs: list[str]
    forbidden_imports: dict[str, list[str]]
    complexity_exceptions: dict[str, dict[str, str]]
    gates: GateConfig


def run_git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CodeHealthError(f"git {' '.join(args)} failed") from exc
    return result.stdout


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_config(root: Path) -> HealthConfig:
    config_path = root / "config" / "code-health.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CodeHealthError(f"invalid code-health config: {config_path}") from exc
    if not isinstance(config, dict) or config.get("schema_version") != 1:
        raise CodeHealthError("code-health config schema_version must be 1")
    return cast(HealthConfig, config)


def tracked_paths(root: Path, config: HealthConfig, revision: str | None = None) -> list[str]:
    roots = tuple(value.rstrip("/") + "/" for value in config["source_roots"])
    suffixes = tuple(config["python_suffixes"] + config["r_suffixes"])
    excluded = tuple(config["exclude_globs"])
    paths = []
    listing = run_git(root, "ls-tree", "-r", "--name-only", "-z", revision) if revision else run_git(root, "ls-files", "-z")
    for raw in listing.split("\0"):
        if not raw or not raw.startswith(roots) or not raw.endswith(suffixes):
            continue
        if any(fnmatch.fnmatchcase(raw, pattern) for pattern in excluded):
            continue
        paths.append(raw)
    return sorted(paths)


def branch(node: ast.AST) -> int:
    if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler)):
        return 1
    if isinstance(node, ast.BoolOp):
        return max(0, len(node.values) - 1)
    if isinstance(node, ast.comprehension):
        return 1 + len(node.ifs)
    if isinstance(node, ast.Match):
        return max(0, len(node.cases) - 1)
    return 0


def is_control(node: ast.AST) -> bool:
    return isinstance(
        node,
        (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler, ast.With, ast.AsyncWith, ast.Match),
    )


def function_metric(path: str, node: ast.FunctionDef | ast.AsyncFunctionDef, cyclomatic: int = 1, cognitive_override: int | None = None) -> FunctionMetric:
    cognitive = 0
    max_nesting = 0

    def visit(current: ast.AST, depth: int) -> None:
        nonlocal cyclomatic, cognitive, max_nesting
        if current is not node:
            cyclomatic += branch(current)
        next_depth = depth
        if is_control(current):
            cognitive += 1 + depth
            next_depth += 1
            max_nesting = max(max_nesting, next_depth)
        for child in ast.iter_child_nodes(current):
            visit(child, next_depth)

    for child in ast.iter_child_nodes(node):
        visit(child, 0)
    if cognitive_override is not None:
        cognitive = cognitive_override
    start = node.lineno
    end = getattr(node, "end_lineno", start)
    return FunctionMetric(path, node.name, start, end, end - start + 1, cyclomatic, cognitive, max_nesting)


def python_metrics(root: Path, paths: Iterable[str], revision: str | None = None) -> list[FunctionMetric]:
    metrics = []
    for relative in paths:
        if not relative.endswith(".py"):
            continue
        try:
            source = run_git(root, "show", f"{revision}:{relative}") if revision else (root / relative).read_text(encoding="utf-8")
            tree = ast.parse(source, filename=relative)
        except (OSError, SyntaxError) as exc:
            raise CodeHealthError(f"cannot parse {relative}") from exc
        radon_metrics = {
            (block.name, block.lineno): block.complexity
            for block in cc_visit_ast(tree)
        }
        cognitive_metrics: dict[tuple[str, int], int] = {}
        if revision is None:
            for block in file_complexity(str(root / relative)).functions:
                name = block.name.rsplit("::", 1)[-1]
                cognitive_metrics[(name, block.line_start)] = block.complexity
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                metrics.append(
                    function_metric(
                        relative,
                        node,
                        radon_metrics.get((node.name, node.lineno), 1),
                        cognitive_metrics.get((node.name, node.lineno)),
                    )
                )
    return metrics


def module_name(path: str) -> str:
    module = path[:-3].replace("/", ".")
    return module[4:] if module.startswith("src.") else module


def git_as_of(root: Path, requested: str | None) -> datetime:
    if requested:
        try:
            return datetime.fromisoformat(requested).replace(tzinfo=UTC)
        except ValueError as exc:
            raise CodeHealthError("--as-of must be ISO-8601 date or datetime") from exc
    stamp = run_git(root, "show", "-s", "--format=%cI", "HEAD").strip()
    try:
        return datetime.fromisoformat(stamp)
    except ValueError as exc:
        raise CodeHealthError("HEAD has no usable commit timestamp") from exc


def history_for_path(root: Path, path: str, as_of: datetime) -> tuple[dict[str, int], int]:
    result = {"30": 0, "90": 0, "180": 0}
    since = (as_of - timedelta(days=180)).date().isoformat()
    output = run_git(root, "log", "--follow", "--since", since, "--numstat", "--format=%ct%x00%s", "--", path)
    commit_timestamp: int | None = None
    defect_commits = 0
    for line in output.splitlines():
        if "\x00" in line:
            timestamp, subject = line.split("\x00", 1)
            if timestamp.isdigit():
                commit_timestamp = int(timestamp)
                if any(word in subject.lower() for word in ("fix", "bug", "regression", "crash")):
                    defect_commits += 1
            continue
        parts = line.split("\t")
        if commit_timestamp is None or len(parts) != 3:
            continue
        added, deleted = parts[:2]
        if not (added.isdigit() and deleted.isdigit()):
            continue
        churn = int(added) + int(deleted)
        age_days = (as_of - datetime.fromtimestamp(commit_timestamp, tz=UTC)).days
        for days in result:
            if age_days <= int(days):
                result[days] += churn
    return result, defect_commits


def import_name(node: ast.Import | ast.ImportFrom) -> str:
    if isinstance(node, ast.Import):
        return node.names[0].name.split(".")[0]
    return (node.module or "").split(".")[0]


def python_import_graph(root: Path, paths: list[str], config: HealthConfig, revision: str | None = None) -> tuple[dict[str, set[str]], list[str]]:
    modules = {module_name(path) for path in paths if path.endswith(".py")}
    graph = {module: set() for module in modules}
    forbidden: list[str] = []
    forbidden_rules = config["forbidden_imports"]
    for relative in paths:
        if not relative.endswith(".py"):
            continue
        module = module_name(relative)
        if revision is None:
            source = (root / relative).read_text(encoding="utf-8")
        else:
            try:
                source = run_git(root, "show", f"{revision}:{relative}")
            except CodeHealthError:
                # A new source file has no baseline revision; it is still
                # measured at head and simply contributes no baseline edge.
                continue
        tree = ast.parse(source, filename=relative)
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        for node in imports:
            imported = import_name(node)
            if imported in {"PyQt6", "rpy2"}:
                for pattern, names in forbidden_rules.items():
                    if fnmatch.fnmatchcase(relative, pattern) and imported in names:
                        forbidden.append(f"{relative}: {imported}")
            if isinstance(node, ast.ImportFrom) and node.level:
                prefix = ".".join(module.split(".")[:-node.level])
                target = ".".join(part for part in (prefix, node.module or "") if part)
                if target in modules:
                    graph[module].add(target)
            elif imported and any(candidate == imported or candidate.startswith(imported + ".") for candidate in modules):
                graph[module].add(imported)
    return graph, sorted(set(forbidden))


def cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    found: set[tuple[str, ...]] = set()
    stack: list[str] = []
    active: set[str] = set()

    def visit(node: str) -> None:
        if node in active:
            cycle = tuple(stack[stack.index(node) :])
            found.add(min(cycle[i:] + cycle[:i] for i in range(len(cycle))))
            return
        stack.append(node)
        active.add(node)
        for target in sorted(graph.get(node, ())):
            visit(target)
        active.remove(node)
        stack.pop()

    for node in sorted(graph):
        visit(node)
    return [list(cycle) for cycle in sorted(found)]


def grimp_evidence() -> dict[str, object] | None:
    """Collect package-level coupling from the locked Grimp analyzer."""
    try:
        package_graph = build_graph("rc_metastudio", include_external_packages=False)
    except (ImportError, ModuleNotFoundError):
        return None
    edges = sum(
        len(package_graph.find_modules_directly_imported_by(module))
        for module in package_graph.modules
    )
    return {
        "tool": "grimp",
        "modules": len(package_graph.modules),
        "edges": edges,
        "cycle_breakers": len(package_graph.nominate_cycle_breakers("rc_metastudio")),
    }


def changed_lines(root: Path, base: str, head: str) -> dict[str, set[int]]:
    output = run_git(root, "diff", "--unified=0", base, head, "--", "*.py")
    changed: dict[str, set[int]] = {}
    current: str | None = None
    for line in output.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            changed.setdefault(current, set())
        elif current and line.startswith("@@"):
            marker = line.split("+")[1].split(" ")[0]
            if "," in marker:
                start_text, count_text = marker.split(",", 1)
                start, count = int(start_text), int(count_text)
            else:
                start, count = int(marker), 1
            changed[current].update(range(start, start + count))
    return changed


def gate(metrics: list[FunctionMetric], changed: dict[str, set[int]], config: HealthConfig, cycle_list: list[list[str]], baseline_cycles: list[list[str]], forbidden: list[str], baseline_forbidden: list[str]) -> dict[str, object]:
    limits = config["gates"]
    changed_functions = [metric for metric in metrics if any(metric.line <= line <= metric.end_line for line in changed.get(metric.path, set()))]
    exceptions = config.get("complexity_exceptions", {})
    violations = [
        metric.as_dict()
        for metric in changed_functions
        if metric.name not in exceptions.get(metric.path, {})
        if metric.cyclomatic > limits["max_changed_cyclomatic"]
        or metric.cognitive > limits["max_changed_cognitive"]
        or metric.nesting > limits["max_changed_nesting"]
    ]
    new_cycles = [cycle for cycle in cycle_list if cycle not in baseline_cycles]
    failures = []
    if limits["block_new_cycles"] and new_cycles:
        failures.append("new dependency cycles")
    new_forbidden = [item for item in forbidden if item not in baseline_forbidden]
    if limits["block_forbidden_imports"] and new_forbidden:
        failures.append("forbidden imports")
    if violations:
        failures.append("changed-code complexity")
    return {
        "passed": not failures,
        "failures": failures,
        "changed_functions": [metric.as_dict() for metric in changed_functions],
        "complexity_violations": violations,
        "complexity_exceptions": {
            path: names for path, names in sorted(exceptions.items())
            if any(metric.path == path for metric in changed_functions)
        },
        "new_cycles": new_cycles,
        "forbidden_imports": forbidden,
        "new_forbidden_imports": new_forbidden,
    }


def build_evidence(root: Path, base: str, head: str, as_of: datetime, config: HealthConfig) -> dict[str, object]:
    current_revision = run_git(root, "rev-parse", "HEAD").strip()
    head_revision = None if head in {"HEAD", current_revision} else head
    paths = tracked_paths(root, config, head_revision or current_revision)
    functions = python_metrics(root, paths, head_revision)
    graph, forbidden = python_import_graph(root, paths, config, head_revision)
    cycle_list = cycles(graph)
    baseline_revision = None if base in {"HEAD", current_revision} else base
    baseline_paths = tracked_paths(root, config, baseline_revision or current_revision)
    baseline_graph, baseline_forbidden = python_import_graph(root, baseline_paths, config, baseline_revision)
    baseline_cycle_list = cycles(baseline_graph)
    file_metrics = []
    for path in paths:
        try:
            source = run_git(root, "show", f"{head}:{path}") if head_revision else (root / path).read_text(encoding="utf-8")
        except CodeHealthError:
            source = ""
        line_count = len(source.splitlines())
        churn, defect_count = history_for_path(root, path, as_of)
        function_subset = [metric for metric in functions if metric.path == path]
        total_cyclomatic = sum(metric.cyclomatic for metric in function_subset)
        complexity_density = total_cyclomatic / max(line_count, 1)
        normalized_churn = churn["180"] / max(line_count, 1)
        file_metrics.append({
            "path": path,
            "lines": line_count,
            "churn": churn,
            "complexity": {"functions": len(function_subset), "cyclomatic": total_cyclomatic, "density": complexity_density},
            "maintainability_index": mi_visit(source, multi=True) if path.endswith(".py") else None,
            "hotspot_score": normalized_churn * complexity_density,
            "defect_history": defect_count,
        })
    file_metrics.sort(key=lambda item: (-item["hotspot_score"], item["path"]))
    tooling = grimp_evidence()
    return {
        "schema_version": 1,
        "generated_at": as_of.isoformat(),
        "base": base,
        "head": head,
        "scope": paths,
        "files": file_metrics,
        "functions": [metric.as_dict() for metric in functions],
        "coupling": {"modules": len(graph), "edges": sum(len(edges) for edges in graph.values()), "out_degree": {key: len(value) for key, value in sorted(graph.items())}},
        "dependency_tooling": tooling,
        "cycles": cycle_list,
        "cognitive_complexity": {"functions": len(functions), "total": sum(metric.cognitive for metric in functions), "maximum": max((metric.cognitive for metric in functions), default=0)},
        "maintainability": {"note": "trend indicator; not a merge gate", "mean_function_lines": sum(metric.lines for metric in functions) / max(len(functions), 1)},
        "defect_history": {"files_with_defect_fixes": sum(1 for item in file_metrics if item["defect_history"]), "commits": sum(int(item["defect_history"]) for item in file_metrics)},
        "gate": gate(functions, changed_lines(root, base, head), config, cycle_list, baseline_cycle_list, forbidden, baseline_forbidden),
    }


def text_report(evidence: dict[str, object]) -> str:
    files = cast(list[dict[str, object]], evidence["files"])[:5]
    scope = cast(list[str], evidence["scope"])
    coupling = cast(dict[str, int], evidence["coupling"])
    cycles_found = cast(list[list[str]], evidence["cycles"])
    cognitive = cast(dict[str, int], evidence["cognitive_complexity"])
    defects = cast(dict[str, int], evidence["defect_history"])
    result_gate = cast(dict[str, object], evidence["gate"])
    failures = cast(list[str], result_gate["failures"])
    lines = [
        f"Code health ({evidence['base']}..{evidence['head']})",
        f"Scope: {len(scope)} files; as of {evidence['generated_at']}",
    ]
    lines.append(f"Coupling: {coupling['modules']} modules, {coupling['edges']} edges")
    lines.append(f"Cycles: {len(cycles_found)}; cognitive complexity total/max: {cognitive['total']}/{cognitive['maximum']}")
    lines.append(f"Defect history: {defects['commits']} matching commits across {defects['files_with_defect_fixes']} files")
    lines.append(f"Gate: {'PASS' if result_gate['passed'] else 'FAIL (' + ', '.join(failures) + ')'}")
    lines.append("Hotspots (180-day normalized churn × complexity density):")
    lines.extend(f"  {item['path']}: {cast(float, item['hotspot_score']):.4f}" for item in files)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD~1")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--as-of")
    parser.add_argument("--output", type=Path, default=Path("artifacts/code-health/evidence.json"))
    parser.add_argument("--report", type=Path, default=Path("artifacts/code-health/report.txt"))
    parser.add_argument("--allow-fail", action="store_true", help="emit evidence without returning a gate failure")
    args = parser.parse_args()
    root = repo_root()
    config = load_config(root)
    evidence = build_evidence(root, args.base, args.head, git_as_of(root, args.as_of), config)
    output = (root / args.output).resolve() if not args.output.is_absolute() else args.output
    report = (root / args.report).resolve() if not args.report.is_absolute() else args.report
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report.write_text(text_report(evidence), encoding="utf-8")
    print(text_report(evidence), end="")
    result_gate = cast(dict[str, object], evidence["gate"])
    return 0 if bool(result_gate["passed"]) or args.allow_fail else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CodeHealthError as exc:
        print(f"code-health: {exc}", file=sys.stderr)
        raise SystemExit(2)
