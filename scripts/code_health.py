#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Emit deterministic Python and R code-health metrics and changed-code gates.

The command uses the locked development analyzers for Python and a deterministic
token pass for R. Its JSON output is the durable evidence; the text report is a
short review aid.
"""

from __future__ import annotations

import argparse
import ast
import copy
import fnmatch
import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import tokenize
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterable, TypedDict, cast

from complexipy import code_complexity
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


TypingCounts = dict[str, int]


class ComparisonMetric(TypedDict, total=False):
    baseline: object
    current: object
    delta: object


class BaselineComparison(TypedDict):
    path: str
    baseline_head: object
    metrics: dict[str, ComparisonMetric]


def _relative_artifact_path(root: Path, path: Path) -> str:
    """Return a stable repository-relative path when the artifact is inside it."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


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


def resolve_revision(root: Path, revision: str) -> str:
    """Resolve a user-supplied Git name to one immutable commit SHA."""
    try:
        return run_git(root, "rev-parse", "--verify", f"{revision}^{{commit}}").strip()
    except CodeHealthError as exc:
        raise CodeHealthError(f"cannot resolve revision {revision!r}") from exc


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


def load_baseline(path: Path) -> dict[str, object]:
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CodeHealthError(f"invalid code-health baseline: {path}") from exc
    if not isinstance(baseline, dict) or baseline.get("schema_version") != 1:
        raise CodeHealthError("code-health baseline schema_version must be 1")
    return baseline


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


def _scan_r_string(source: str, index: int, line: int) -> tuple[int, int]:
    quote = source[index]
    index += 1
    while index < len(source):
        char = source[index]
        if char == "\\":
            index += 2
            continue
        index += 1
        if char == quote:
            break
        if char == "\n":
            line += 1
    return index, line


def _scan_r_identifier(source: str, index: int) -> tuple[str, int]:
    start = index
    while index < len(source) and (source[index].isalnum() or source[index] in "._"):
        index += 1
    return source[start:index], index


def _r_tokens(source: str) -> list[tuple[str, int]]:
    """Tokenize R structure without interpreting executable source text."""
    tokens: list[tuple[str, int]] = []
    index = 0
    line = 1
    while index < len(source):
        token, index, line = _next_r_token(source, index, line)
        if token is not None:
            tokens.append((token, line))
    return tokens


def _next_r_token(source: str, index: int, line: int) -> tuple[str | None, int, int]:
    char = source[index]
    simple = _next_r_layout(source, index, line)
    if simple is not None:
        return simple
    if char in "'\"`":
        start_line = line
        index, line = _scan_r_string(source, index, line)
        return "<string>", index, start_line
    if char.isalpha() or char in "._":
        return (*_scan_r_identifier(source, index), line)
    pair = source[index:index + 2]
    if pair in {"<-", "->", "&&", "||"}:
        return pair, index + 2, line
    return char, index + 1, line


def _next_r_layout(source: str, index: int, line: int) -> tuple[str | None, int, int] | None:
    char = source[index]
    if char == "\n":
        return None, index + 1, line + 1
    if char.isspace():
        return None, index + 1, line
    if char == "#":
        newline = source.find("\n", index)
        return None, len(source) if newline < 0 else newline, line
    return None


def _r_function_span(tokens: list[tuple[str, int]], start: int) -> tuple[int, int] | None:
    opening = next((position for position in range(start + 3, len(tokens)) if tokens[position][0] == "{"), None)
    if opening is None:
        return None
    depth = 0
    for position in range(opening, len(tokens)):
        token = tokens[position][0]
        depth += token == "{"
        depth -= token == "}"
        if depth == 0:
            return opening, position
    return None


def r_function_metrics(root: Path, paths: Iterable[str], revision: str | None = None) -> list[FunctionMetric]:
    """Measure named R functions from balanced lexical structure."""
    metrics: list[FunctionMetric] = []
    for relative in paths:
        if not relative.lower().endswith((".r",)):
            continue
        source = run_git(root, "show", f"{revision}:{relative}") if revision else (root / relative).read_text(encoding="utf-8")
        tokens = _r_tokens(source)
        for index in range(len(tokens) - 3):
            name, line = tokens[index]
            metric = _r_metric_at(tokens, index, relative, name, line)
            if metric is not None:
                metrics.append(metric)
    return metrics


def _r_metric_at(tokens: list[tuple[str, int]], index: int, path: str, name: str, line: int) -> FunctionMetric | None:
    if tokens[index + 1][0] not in {"<-", "="} or tokens[index + 2][0] != "function":
        return None
    span = _r_function_span(tokens, index)
    if span is None:
        return None
    opening, closing = span
    body = [token for token, _line in tokens[opening + 1:closing]]
    branches = sum(token in {"if", "for", "while", "switch", "&&", "||", "?"} for token in body)
    end_line = tokens[closing][1]
    return FunctionMetric(path, name, line, end_line, end_line - line + 1, 1 + branches, branches, 0)


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
        cognitive_metrics = {
            (block.name.rsplit("::", 1)[-1], block.line_start): block.complexity
            for block in code_complexity(source).functions
        }
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


def _typing_module_imports(tree: ast.AST) -> list[ast.alias]:
    aliases: list[ast.alias] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import):
            continue
        aliases.extend(alias for alias in node.names if alias.name in {"typing", "typing_extensions"})
    return aliases


def _typing_from_imports(tree: ast.AST) -> list[ast.alias]:
    aliases: list[ast.alias] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in {"typing", "typing_extensions"}:
            aliases.extend(node.names)
    return aliases


def _typing_aliases(tree: ast.AST) -> tuple[set[str], set[str], set[str]]:
    any_names = {"Any"}
    cast_names = {"cast"}
    typing_names = {"typing", "typing_extensions"}
    imports = _typing_module_imports(tree)
    from_imports = _typing_from_imports(tree)
    for alias in imports:
        typing_names.add(alias.asname or alias.name.split(".")[0])
    for alias in from_imports:
        if alias.name == "Any":
            any_names.add(alias.asname or alias.name)
        elif alias.name == "cast":
            cast_names.add(alias.asname or alias.name)
    return any_names, cast_names, typing_names


def _is_any_annotation(node: ast.AST, any_names: set[str], typing_names: set[str]) -> bool:
    return any(
        isinstance(child, ast.Name) and child.id in any_names
        or (
            isinstance(child, ast.Attribute)
            and child.attr == "Any"
            and isinstance(child.value, ast.Name)
            and child.value.id in typing_names
        )
        for child in ast.walk(node)
    )


def _type_ignore_count(source: str) -> int:
    return sum(
        token.type == tokenize.COMMENT
        and re.match(r"#\s*type:\s*ignore\b", token.string) is not None
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
    )


def _parameter_nodes(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.arg]:
    parameters = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    if node.args.vararg is not None:
        parameters.append(node.args.vararg)
    if node.args.kwarg is not None:
        parameters.append(node.args.kwarg)
    return parameters


def _function_typing_counts(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    any_names: set[str],
    typing_names: set[str],
) -> TypingCounts:
    parameters = _parameter_nodes(node)
    annotated = [parameter.annotation for parameter in parameters if parameter.annotation is not None]
    any_count = sum(_is_any_annotation(annotation, any_names, typing_names) for annotation in annotated)
    if node.returns is not None:
        any_count += _is_any_annotation(node.returns, any_names, typing_names)
    return {
        "files": 0,
        "total_parameters": len(parameters),
        "total_functions": 1,
        "annotated_parameters": len(annotated),
        "annotated_returns": node.returns is not None,
        "any_annotations": any_count,
        "type_ignore_directives": 0,
        "cast_to_any": 0,
    }


def _is_cast_to_any(node: ast.Call, any_names: set[str], cast_names: set[str], typing_names: set[str]) -> bool:
    function = node.func
    named_cast = isinstance(function, ast.Name) and function.id in cast_names
    qualified_cast = (
        isinstance(function, ast.Attribute)
        and function.attr == "cast"
        and isinstance(function.value, ast.Name)
        and function.value.id in typing_names
    )
    return (named_cast or qualified_cast) and bool(node.args) and _is_any_annotation(node.args[0], any_names, typing_names)


def _add_typing_counts(target: TypingCounts, source: TypingCounts) -> None:
    for key in target:
        target[key] += source[key]


def _typing_file_counts(source: str, relative: str) -> TypingCounts:
    try:
        tree = ast.parse(source, filename=relative)
    except SyntaxError as exc:
        raise CodeHealthError(f"cannot parse {relative}") from exc
    any_names, cast_names, typing_names = _typing_aliases(tree)
    counts: TypingCounts = {
        "files": 1,
        "total_parameters": 0,
        "total_functions": 0,
        "annotated_parameters": 0,
        "annotated_returns": 0,
        "any_annotations": 0,
        "type_ignore_directives": _type_ignore_count(source),
        "cast_to_any": 0,
    }
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _add_typing_counts(counts, _function_typing_counts(node, any_names, typing_names))
    counts["cast_to_any"] = sum(
        _is_cast_to_any(node, any_names, cast_names, typing_names)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    )
    return counts


def _coverage(annotated: int, total: int) -> float:
    return annotated / max(total, 1)


def typing_measurement(root: Path, paths: Iterable[str], revision: str) -> dict[str, object]:
    """Measure typing signals from the exact Python snapshot being analyzed."""
    counts: TypingCounts = {
        "files": 0,
        "total_parameters": 0,
        "total_functions": 0,
        "annotated_parameters": 0,
        "annotated_returns": 0,
        "any_annotations": 0,
        "type_ignore_directives": 0,
        "cast_to_any": 0,
    }
    for relative in paths:
        if not relative.endswith(".py"):
            continue
        source = _source_at_revision(root, relative, revision)
        if source is None:
            raise CodeHealthError(f"cannot read {relative} at {revision}")
        _add_typing_counts(counts, _typing_file_counts(source, relative))
    return {
        "tool": "ast",
        "revision": revision,
        **counts,
        "parameter_coverage": _coverage(counts["annotated_parameters"], counts["total_parameters"]),
        "return_coverage": _coverage(counts["annotated_returns"], counts["total_functions"]),
    }


def module_name(path: str) -> str:
    module = path[:-3].replace("/", ".")
    return module[4:] if module.startswith("src.") else module


def _resolve_imported_module(module: str, imported: str, modules: set[str]) -> str | None:
    candidates = [imported]
    if imported == module.split(".")[0]:
        candidates.extend(f"{module.split('.')[0]}.{part}" for part in imported.split(".")[1:])
    for candidate in candidates:
        if candidate in modules:
            return candidate
        matches = sorted(item for item in modules if item.startswith(candidate + "."))
        if matches:
            return matches[0]
    return None


def git_as_of(root: Path, requested: str | None, revision: str = "HEAD") -> datetime:
    if requested:
        try:
            return datetime.fromisoformat(requested).replace(tzinfo=UTC)
        except ValueError as exc:
            raise CodeHealthError("--as-of must be ISO-8601 date or datetime") from exc
    stamp = run_git(root, "show", "-s", "--format=%cI", revision).strip()
    try:
        return datetime.fromisoformat(stamp)
    except ValueError as exc:
        raise CodeHealthError(f"{revision} has no usable commit timestamp") from exc


def history_for_path(root: Path, path: str, as_of: datetime, revision: str = "HEAD") -> tuple[dict[str, int], int]:
    result = {"30": 0, "90": 0, "180": 0}
    since = (as_of - timedelta(days=180)).date().isoformat()
    output = run_git(root, "log", revision, "--follow", "--since", since, "--numstat", "--format=%ct%x00%s", "--", path)
    commit_timestamp: int | None = None
    defect_commits = 0
    as_of_timestamp = as_of.timestamp()
    for line in output.splitlines():
        if "\x00" in line:
            timestamp, subject = line.split("\x00", 1)
            if timestamp.isdigit():
                commit_timestamp = int(timestamp)
                if commit_timestamp <= as_of_timestamp and any(word in subject.lower() for word in ("fix", "bug", "regression", "crash")):
                    defect_commits += 1
            continue
        parts = line.split("\t")
        if commit_timestamp is None or commit_timestamp > as_of_timestamp or len(parts) != 3:
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


class _RuntimeNormalizer(ast.NodeTransformer):
    """Remove Python constructs that do not change executable function bodies."""

    def __init__(self, tree: ast.AST) -> None:
        super().__init__()
        self.cast_names = {"cast"}
        self.typing_names = {"typing", "typing_extensions"}
        self.type_checking_names = {"TYPE_CHECKING"}
        self.type_only_constructors: set[str] = set()
        self._collect_type_names(tree)

    def _collect_type_names(self, tree: ast.AST) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self._collect_typing_imports(node)
            elif isinstance(node, ast.ImportFrom):
                self._collect_typing_from_import(node)
            elif isinstance(node, ast.ClassDef) and self._is_typed_dict(node):
                self.type_only_constructors.add(node.name)

    def _collect_typing_imports(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name in self.typing_names:
                self.typing_names.add(alias.asname or alias.name.split(".")[0])

    def _collect_typing_from_import(self, node: ast.ImportFrom) -> None:
        if node.module not in self.typing_names:
            return
        for alias in node.names:
            if alias.name == "cast":
                self.cast_names.add(alias.asname or alias.name)
            elif alias.name == "TYPE_CHECKING":
                self.type_checking_names.add(alias.asname or alias.name)

    def _is_typed_dict(self, node: ast.ClassDef) -> bool:
        return any(
            isinstance(base, ast.Name) and base.id == "TypedDict"
            or isinstance(base, ast.Attribute) and base.attr == "TypedDict"
            for base in node.bases
        )

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.FunctionDef | ast.AsyncFunctionDef:
        node.returns = None
        node.type_comment = None
        for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            argument.annotation = None
            argument.type_comment = None
        if node.args.vararg:
            node.args.vararg.annotation = None
            node.args.vararg.type_comment = None
        if node.args.kwarg:
            node.args.kwarg.annotation = None
            node.args.kwarg.type_comment = None
        normalized = cast(ast.FunctionDef | ast.AsyncFunctionDef, self.generic_visit(node))
        normalized.body = self._collapse_typed_dict_temps(normalized.body)
        for statement in normalized.body:
            self._collapse_nested_statement_lists(statement)
        return normalized

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        return cast(ast.FunctionDef, self._visit_function(node))

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        return cast(ast.AsyncFunctionDef, self._visit_function(node))

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.Assign | None:
        if node.value is None:
            return None
        return ast.Assign(targets=[node.target], value=self.visit(node.value), type_comment=None)

    def visit_If(self, node: ast.If) -> ast.If | None:
        if self._is_type_checking_test(node.test):
            return None
        return cast(ast.If, self.generic_visit(node))

    def visit_Expr(self, node: ast.Expr) -> ast.Expr | None:
        if isinstance(node.value, ast.Call) and self._is_type_only_call(node.value):
            return None
        return cast(ast.Expr, self.generic_visit(node))

    def visit_Call(self, node: ast.Call) -> ast.Call | ast.expr:
        cast_value = self._cast_value(node)
        if cast_value is not None:
            return cast_value
        typed_dict = self._typed_dict_value(node)
        if typed_dict is not None:
            return typed_dict
        return cast(ast.Call, self.generic_visit(node))

    def _cast_value(self, node: ast.Call) -> ast.expr | None:
        if not self._is_cast_call(node) or len(node.args) < 2 or node.keywords:
            return None
        return cast(ast.expr, self.visit(node.args[1]))

    def _typed_dict_value(self, node: ast.Call) -> ast.Dict | None:
        if not self._is_typed_dict_call(node):
            return None
        result = ast.Dict(
            keys=[ast.Constant(keyword.arg) for keyword in node.keywords],
            values=[cast(ast.expr, self.visit(keyword.value)) for keyword in node.keywords],
        )
        setattr(result, "_type_only_dict", True)
        return result

    def _is_typed_dict_call(self, node: ast.Call) -> bool:
        return (
            isinstance(node.func, ast.Name)
            and node.func.id in self.type_only_constructors
            and not node.args
            and all(keyword.arg is not None for keyword in node.keywords)
        )

    def _collapse_typed_dict_temps(self, body: list[ast.stmt]) -> list[ast.stmt]:
        result: list[ast.stmt] = []
        index = 0
        while index < len(body):
            assignment = body[index]
            following = body[index + 1] if index + 1 < len(body) else None
            if self._typed_dict_temp_pair(assignment, following):
                assert isinstance(following, ast.Expr)
                assert isinstance(assignment, ast.Assign)
                assert isinstance(following.value, ast.Call)
                following.value.args[0] = assignment.value
                result.append(following)
                index += 2
                continue
            result.append(assignment)
            index += 1
        return result

    def _typed_dict_temp_pair(self, assignment: ast.stmt, following: ast.stmt | None) -> bool:
        target = self._typed_dict_assignment_target(assignment)
        if target is None or not isinstance(following, ast.Expr):
            return False
        return self._is_append_of(following.value, target.id)

    def _typed_dict_assignment_target(self, node: ast.stmt) -> ast.Name | None:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            return None
        target = node.targets[0]
        value = node.value
        if not isinstance(target, ast.Name) or not isinstance(value, ast.Dict):
            return None
        return target if getattr(value, "_type_only_dict", False) else None

    def _is_append_of(self, node: ast.expr, target: str) -> bool:
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            return False
        if node.func.attr != "append" or len(node.args) != 1 or node.keywords:
            return False
        value = node.args[0]
        return isinstance(value, ast.Name) and value.id == target

    def _collapse_nested_statement_lists(self, node: ast.AST) -> None:
        for field, value in ast.iter_fields(node):
            if isinstance(value, list) and all(isinstance(item, ast.stmt) for item in value):
                statements = self._collapse_typed_dict_temps(value)
                setattr(node, field, statements)
                for statement in statements:
                    self._collapse_nested_statement_lists(statement)
            elif isinstance(value, ast.AST):
                self._collapse_nested_statement_lists(value)

    def _is_type_checking_test(self, node: ast.expr) -> bool:
        return isinstance(node, ast.Name) and node.id in self.type_checking_names or (
            isinstance(node, ast.Attribute)
            and node.attr == "TYPE_CHECKING"
            and isinstance(node.value, ast.Name)
            and node.value.id in self.typing_names
        )

    def _is_cast_call(self, node: ast.Call) -> bool:
        function = node.func
        return isinstance(function, ast.Name) and function.id in self.cast_names or (
            isinstance(function, ast.Attribute)
            and function.attr == "cast"
            and isinstance(function.value, ast.Name)
            and function.value.id in self.typing_names
        )

    def _is_type_only_call(self, node: ast.Call) -> bool:
        function = node.func
        return isinstance(function, ast.Attribute) and function.attr in {"assert_type", "reveal_type"} and isinstance(function.value, ast.Name) and function.value.id in self.typing_names


def _source_at_revision(root: Path, path: str, revision: str | None) -> str | None:
    if revision is None:
        try:
            return (root / path).read_text(encoding="utf-8")
        except OSError:
            return None
    try:
        return run_git(root, "show", f"{revision}:{path}")
    except CodeHealthError:
        return None


def _runtime_function_bodies(source: str) -> dict[str, list[str]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    normalized = _RuntimeNormalizer(tree).visit(copy.deepcopy(tree))
    bodies: dict[str, list[str]] = {}
    for node in ast.walk(normalized):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = ast.Module(body=node.body, type_ignores=[])
            bodies.setdefault(node.name, []).append(ast.dump(body, annotate_fields=True, include_attributes=False))
    return bodies


def runtime_changed_function_keys(
    root: Path,
    base: str,
    head: str,
    metrics: list[FunctionMetric],
    changed: dict[str, set[int]],
) -> set[tuple[str, str, int, int]]:
    """Return changed functions whose normalized executable bodies differ."""
    base_revision, head_revision = _measurement_revisions(base, head)
    paths = {metric.path for metric in metrics if metric.path.endswith(".py")}
    baseline_bodies = _bodies_for_paths(root, paths, base_revision)
    head_bodies = _bodies_for_paths(root, paths, head_revision)
    result: set[tuple[str, str, int, int]] = set()
    for metric in metrics:
        if _runtime_metric_changed(metric, changed, baseline_bodies, head_bodies):
            result.add((metric.path, metric.name, metric.line, metric.end_line))
    return result


def _measurement_revisions(base: str, head: str) -> tuple[str, str]:
    return base, head


def _bodies_for_paths(root: Path, paths: set[str], revision: str | None) -> dict[str, dict[str, list[str]]]:
    result: dict[str, dict[str, list[str]]] = {}
    for path in paths:
        source = _source_at_revision(root, path, revision)
        if source is not None:
            result[path] = _runtime_function_bodies(source)
    return result


def _runtime_metric_changed(
    metric: FunctionMetric,
    changed: dict[str, set[int]],
    baseline: dict[str, dict[str, list[str]]],
    head: dict[str, dict[str, list[str]]],
) -> bool:
    lines = changed.get(metric.path, set())
    if not any(metric.line <= line <= metric.end_line for line in lines):
        return False
    if not metric.path.endswith(".py"):
        return True
    return baseline.get(metric.path, {}).get(metric.name) != head.get(metric.path, {}).get(metric.name)


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
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    prefix = ".".join(module.split(".")[:-node.level])
                    target = ".".join(part for part in (prefix, node.module or "") if part)
                    resolved = _resolve_imported_module(module, target, modules)
                    if resolved:
                        graph[module].add(resolved)
                    for alias in node.names:
                        resolved_name = _resolve_imported_module(module, f"{target}.{alias.name}", modules)
                        if resolved_name:
                            graph[module].add(resolved_name)
                else:
                    target = node.module or ""
                    resolved = _resolve_imported_module(module, target, modules)
                    if resolved:
                        graph[module].add(resolved)
                    for alias in node.names:
                        resolved_name = _resolve_imported_module(module, f"{target}.{alias.name}", modules)
                        if resolved_name:
                            graph[module].add(resolved_name)
            elif imported:
                resolved = _resolve_imported_module(module, imported, modules)
                if resolved:
                    graph[module].add(resolved)
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


def grimp_evidence(root: Path | None = None, revision: str | None = None) -> dict[str, object] | None:
    """Collect package-level coupling from the locked Grimp analyzer."""
    root = root or repo_root()
    try:
        package_graph = _grimp_graph(root, revision)
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


def _grimp_graph(root: Path, revision: str | None):
    if revision is None:
        return _grimp_snapshot_graph(str(root / "src"))
    return _grimp_revision_graph(root, revision)


def _grimp_revision_graph(root: Path, revision: str):
    with tempfile.TemporaryDirectory(prefix="code-health-") as temporary:
        archive = subprocess.run(
            ["git", "archive", "--format=tar", revision, "--", "src/rc_metastudio"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
            tar.extractall(temporary)
        return _grimp_snapshot_graph(str(Path(temporary) / "src"))


def _grimp_snapshot_graph(package_root: str):
    saved_modules = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if name == "rc_metastudio" or name.startswith("rc_metastudio.")
    }
    sys.path.insert(0, package_root)
    try:
        return build_graph("rc_metastudio", include_external_packages=False)
    finally:
        sys.path.remove(package_root)
        for name in list(sys.modules):
            if name == "rc_metastudio" or name.startswith("rc_metastudio."):
                sys.modules.pop(name)
        sys.modules.update(saved_modules)


def changed_lines(root: Path, base: str, head: str) -> dict[str, set[int]]:
    output = run_git(
        root,
        "diff",
        "-M20%",
        "--unified=0",
        base,
        head,
        "--",
        "*.py",
        "*.R",
        "*.r",
    )
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


def gate(
    metrics: list[FunctionMetric],
    changed: dict[str, set[int]],
    config: HealthConfig,
    cycle_list: list[list[str]],
    baseline_cycles: list[list[str]],
    forbidden: list[str],
    baseline_forbidden: list[str],
    runtime_changed: set[tuple[str, str, int, int]] | None = None,
) -> dict[str, object]:
    limits = config["gates"]
    changed_functions = [metric for metric in metrics if any(metric.line <= line <= metric.end_line for line in changed.get(metric.path, set()))]
    if runtime_changed is not None:
        changed_functions = [metric for metric in changed_functions if (metric.path, metric.name, metric.line, metric.end_line) in runtime_changed]
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


def _comparison_metrics(evidence: dict[str, object]) -> dict[str, object]:
    files = cast(list[dict[str, object]], evidence["files"])
    coupling = cast(dict[str, object], evidence["coupling"])
    cycles_found = cast(list[list[str]], evidence["cycles"])
    cognitive = cast(dict[str, object], evidence["cognitive_complexity"])
    maintainability = cast(dict[str, object], evidence["maintainability"])
    defects = cast(dict[str, object], evidence["defect_history"])
    typing = cast(dict[str, object], evidence["typing"])
    return {
        "scope.files": len(cast(list[str], evidence["scope"])),
        "coupling.modules": coupling["modules"],
        "coupling.edges": coupling["edges"],
        "cycles": cycles_found,
        "cognitive_complexity.total": cognitive["total"],
        "cognitive_complexity.maximum": cognitive["maximum"],
        "maintainability.mean_function_lines": maintainability["mean_function_lines"],
        "defect_history.commits": defects["commits"],
        "typing.total_parameters": typing["total_parameters"],
        "typing.total_functions": typing["total_functions"],
        "typing.annotated_parameters": typing["annotated_parameters"],
        "typing.annotated_returns": typing["annotated_returns"],
        "typing.parameter_coverage": typing["parameter_coverage"],
        "typing.return_coverage": typing["return_coverage"],
        "typing.any_annotations": typing["any_annotations"],
        "typing.type_ignore_directives": typing["type_ignore_directives"],
        "typing.cast_to_any": typing["cast_to_any"],
        "hotspots.top5": [
            {"path": item["path"], "score": item["hotspot_score"]}
            for item in files[:5]
        ],
    }


def compare_to_baseline(
    evidence: dict[str, object], baseline: dict[str, object], baseline_path: str
) -> BaselineComparison:
    """Compare deterministic measurements with the recorded baseline artifact."""
    current_metrics = _comparison_metrics(evidence)
    baseline_metrics = _comparison_metrics(baseline)
    metrics: dict[str, ComparisonMetric] = {}
    for name in sorted(current_metrics):
        current = current_metrics[name]
        recorded = baseline_metrics.get(name)
        item: ComparisonMetric = {"baseline": recorded, "current": current}
        if (
            isinstance(recorded, (int, float))
            and not isinstance(recorded, bool)
            and isinstance(current, (int, float))
            and not isinstance(current, bool)
        ):
            item["delta"] = current - recorded
        metrics[name] = item
    return {
        "path": baseline_path,
        "baseline_head": baseline.get("head"),
        "metrics": metrics,
    }


def build_evidence(
    root: Path,
    base: str,
    head: str,
    as_of: datetime,
    config: HealthConfig,
    baseline: Path | None = None,
) -> dict[str, object]:
    requested_base = base
    requested_head = head
    base = resolve_revision(root, base)
    head = resolve_revision(root, head)
    baseline_data = load_baseline(baseline) if baseline is not None else None
    paths = tracked_paths(root, config, head)
    functions = python_metrics(root, paths, head)
    functions.extend(r_function_metrics(root, paths, head))
    graph, forbidden = python_import_graph(root, paths, config, head)
    cycle_list = cycles(graph)
    baseline_paths = tracked_paths(root, config, base)
    baseline_graph, baseline_forbidden = python_import_graph(root, baseline_paths, config, base)
    baseline_cycle_list = cycles(baseline_graph)
    gate_baseline_cycles = baseline_cycle_list
    gate_baseline_forbidden = baseline_forbidden
    if baseline_data is not None:
        recorded_cycles = baseline_data.get("cycles")
        if isinstance(recorded_cycles, list):
            gate_baseline_cycles = cast(list[list[str]], recorded_cycles)
        recorded_gate = baseline_data.get("gate")
        if isinstance(recorded_gate, dict):
            recorded_forbidden = cast(dict[str, object], recorded_gate).get("forbidden_imports")
            if isinstance(recorded_forbidden, list):
                gate_baseline_forbidden = cast(list[str], recorded_forbidden)
    file_metrics = []
    for path in paths:
        try:
            source = run_git(root, "show", f"{head}:{path}")
        except CodeHealthError:
            source = ""
        line_count = len(source.splitlines())
        churn, defect_count = history_for_path(root, path, as_of, head)
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
            "language": "python" if path.endswith(".py") else "r",
            "hotspot_score": normalized_churn * complexity_density,
            "defect_history": defect_count,
        })
    file_metrics.sort(key=lambda item: (-item["hotspot_score"], item["path"]))
    tooling = grimp_evidence(root, head)
    typing = typing_measurement(root, paths, head)
    changed = changed_lines(root, base, head)
    runtime_changed = runtime_changed_function_keys(root, base, head, functions, changed)
    evidence: dict[str, object] = {
        "schema_version": 1,
        "generated_at": as_of.isoformat(),
        "base": base,
        "head": head,
        "requested_base": requested_base,
        "requested_head": requested_head,
        "scope": paths,
        "files": file_metrics,
        "functions": [metric.as_dict() for metric in functions],
        "coupling": {"modules": len(graph), "edges": sum(len(edges) for edges in graph.values()), "out_degree": {key: len(value) for key, value in sorted(graph.items())}},
        "dependency_tooling": tooling,
        "cycles": cycle_list,
        "typing": typing,
        "cognitive_complexity": {"functions": len(functions), "total": sum(metric.cognitive for metric in functions), "maximum": max((metric.cognitive for metric in functions), default=0)},
        "maintainability": {"note": "trend indicator; not a merge gate", "mean_function_lines": sum(metric.lines for metric in functions) / max(len(functions), 1)},
        "defect_history": {"files_with_defect_fixes": sum(1 for item in file_metrics if item["defect_history"]), "commits": sum(int(item["defect_history"]) for item in file_metrics)},
        "gate": gate(
            functions,
            changed,
            config,
            cycle_list,
            gate_baseline_cycles,
            forbidden,
            gate_baseline_forbidden,
            runtime_changed,
        ),
    }
    if baseline_data is not None:
        evidence["baseline_comparison"] = compare_to_baseline(
            evidence,
            baseline_data,
            _relative_artifact_path(root, baseline or Path("baseline.json")),
        )
    return evidence


def text_report(evidence: dict[str, object]) -> str:
    files = cast(list[dict[str, object]], evidence["files"])[:5]
    scope = cast(list[str], evidence["scope"])
    coupling = cast(dict[str, int], evidence["coupling"])
    cycles_found = cast(list[list[str]], evidence["cycles"])
    cognitive = cast(dict[str, int], evidence["cognitive_complexity"])
    defects = cast(dict[str, int], evidence["defect_history"])
    typing = cast(dict[str, object], evidence["typing"])
    result_gate = cast(dict[str, object], evidence["gate"])
    failures = cast(list[str], result_gate["failures"])
    lines = [
        f"Code health ({evidence['base']}..{evidence['head']})",
        f"Scope: {len(scope)} files; as of {evidence['generated_at']}",
    ]
    lines.append(f"Coupling: {coupling['modules']} modules, {coupling['edges']} edges")
    lines.append(f"Cycles: {len(cycles_found)}; cognitive complexity total/max: {cognitive['total']}/{cognitive['maximum']}")
    lines.append(
        f"Typing: {typing['annotated_parameters']}/{typing['total_parameters']} "
        f"parameters ({cast(float, typing['parameter_coverage']):.1%}), "
        f"{typing['annotated_returns']}/{typing['total_functions']} returns "
        f"({cast(float, typing['return_coverage']):.1%}), {typing['any_annotations']} Any "
        f"annotations, {typing['type_ignore_directives']} type: ignores, "
        f"{typing['cast_to_any']} casts to Any ({typing['revision']})"
    )
    lines.append(f"Defect history: {defects['commits']} matching commits across {defects['files_with_defect_fixes']} files")
    comparison = evidence.get("baseline_comparison")
    if isinstance(comparison, dict):
        comparison_data = cast(dict[str, object], comparison)
        lines.append(
            f"Baseline comparison: {comparison_data['path']} "
            f"(recorded head {comparison_data['baseline_head']})"
        )
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
    parser.add_argument(
        "--baseline",
        type=Path,
        help="compare final measurements with a recorded baseline evidence JSON",
    )
    parser.add_argument("--allow-fail", action="store_true", help="emit evidence without returning a gate failure")
    args = parser.parse_args()
    root = repo_root()
    config = load_config(root)
    baseline = None
    if args.baseline is not None:
        baseline = (root / args.baseline).resolve() if not args.baseline.is_absolute() else args.baseline
    evidence = build_evidence(
        root,
        args.base,
        args.head,
        git_as_of(root, args.as_of, args.head),
        config,
        baseline,
    )
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
