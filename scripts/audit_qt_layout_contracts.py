#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fail closed when canonical Qt layout contracts regress."""

import ast
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from collections.abc import Mapping, Sequence
from typing import TypeAlias, TypeVar
import xml.etree.ElementTree as ET

if __package__:
    from scripts import qt_window_ownership
else:
    import qt_window_ownership


LEGACY_HELPERS = (
    "center_dialog_over_parent",
    "exec_centered",
    "fit_application_dialog_to_contents",
    "fit_analysis_dialog_to_contents",
    "fit_option_groups_to_contents",
    "fit_text_to_contents",
    "configure_resizable_window",
    "sync_application_wizard_pages_to_body",
    "show_centered",
    "_adopt_fixed_direct_children_into_root_layout",
    "_direct_child_geometry_rows",
    "_fit_wizard_page_to_contents",
)

QT_CHROME_CLASSES = {"QMenuBar", "QStatusBar", "QToolBar"}
SIZE_PROPERTIES = {
    "minimumSize",
    "maximumSize",
    "minimumWidth",
    "maximumWidth",
    "minimumHeight",
    "maximumHeight",
}

GUARDED_GEOMETRY_METHODS = {
    "adjustSize",
    "fitInView",
    "move",
    "resize",
    "setFixedHeight",
    "setFixedSize",
    "setFixedWidth",
    "setGeometry",
    "setIconSize",
    "setMaximumHeight",
    "setMaximumSize",
    "setMaximumWidth",
    "setMinimumHeight",
    "setMinimumSize",
    "setMinimumWidth",
    "setSceneRect",
}

# Every source exception is local, categorical, and documented immediately
# above the call. Broad file or function exemptions are intentionally absent.
SOURCE_EXCEPTION_RULES = {
    "adaptive-window-policy": {
        "paths": {"adaptive_window.py"},
        "methods": {"move", "resize", "setMaximumSize", "setMinimumWidth"},
    },
    "bounded-native-popup": {
        "paths": {
            "adaptive_controls.py",
            "binary_data_dialog.py",
            "continuous_data_dialog.py",
        },
        "methods": {
            "move",
            "resize",
            "setMaximumHeight",
            "setMaximumSize",
            "setMaximumWidth",
            "setMinimumSize",
            "setMinimumWidth",
        },
    },
    "compact-table-overflow": {
        "paths": {
            "binary_data_dialog.py",
            "continuous_data_dialog.py",
            "diagnostic_data_dialog.py",
            "qt_layout.py",
        },
        "methods": {
            "setMaximumHeight",
            "setMinimumHeight",
            "setMinimumWidth",
        },
    },
    "content-overflow-control": {
        "paths": {
            "adaptive_controls.py",
            "binary_data_dialog.py",
            "continuous_data_dialog.py",
            "diagnostic_data_dialog.py",
            "analysis_setup_dialog.py",
            "main_window.py",
            "results_window.py",
        },
        "methods": {"setMaximumWidth", "setMinimumWidth"},
    },
    "intrinsic-ratio": {
        "paths": {"results_window.py"},
        "methods": {"fitInView", "setSceneRect"},
    },
    "numeric-domain-control": {
        "paths": {
            "calculator_routines.py",
            "continuous_data_dialog.py",
            "diagnostic_data_dialog.py",
        },
        "methods": {"setMaximumWidth", "setMinimumWidth"},
    },
    "persisted-workspace-placement": {
        "paths": {"settings.py"},
        "methods": {"setGeometry"},
    },
    "style-metric-control": {
        "paths": {"edit_dialog.py", "main_wizard.py", "qt_layout.py"},
        "methods": {"setFixedSize", "setIconSize", "setMinimumSize"},
    },
    "semantic-icon-control": {
        "paths": {"qt_layout.py"},
        "methods": {
            "setFixedSize",
            "setIconSize",
            "setMinimumHeight",
            "setMinimumSize",
        },
    },
    "verification-layout-fixture": {
        "paths": {"adaptive_layout_evidence.py", "automation.py"},
        "methods": {"adjustSize", "move", "resize"},
    },
}

UI_SEMANTIC_SIZE_CATEGORIES = {
    "intrinsic-ratio",
    "numeric-domain-control",
    "semantic-icon-control",
    "style-metric-control",
}

SOURCE_EXCEPTION_RE = re.compile(
    r"^\s*# layout-audit: allow=(?P<category>[a-z0-9-]+); "
    r"reason=(?P<reason>\S.*)\s*$"
)


@dataclass(frozen=True)
class Finding:
    path: Path
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.path}: {self.rule}: {self.detail}"


_Scope: TypeAlias = ast.AST
_Assignment: TypeAlias = tuple[int, ast.expr, bool]
_NodeScopes: TypeAlias = dict[ast.AST, _Scope]
_NodeConditions: TypeAlias = dict[ast.AST, bool]
_ScopeParents: TypeAlias = dict[_Scope, _Scope | None]
_Assignments: TypeAlias = dict[_Scope, dict[str, list[_Assignment]]]
_Bindings: TypeAlias = dict[str, list[ast.expr]]
_Definition: TypeAlias = tuple[int, str, bool]
_Definitions: TypeAlias = dict[_Scope, dict[str, list[_Definition]]]
_ReachingValue = TypeVar("_ReachingValue")


def _managed_root(top_widget: ET.Element) -> bool:
    if top_widget.find("layout") is not None:
        return True
    if top_widget.get("class") == "QMainWindow":
        central = top_widget.find("widget[@name='centralwidget']")
        return central is not None and central.find("layout") is not None
    return False


def _is_scroll_area_content(
    widget: ET.Element, parent_map: Mapping[ET.Element, ET.Element]
) -> bool:
    parent = parent_map.get(widget)
    return (
        parent is not None
        and parent.tag == "widget"
        and parent.get("class") == "QScrollArea"
    )


def _dimension_values(prop: ET.Element) -> list[int]:
    values: list[int] = []
    for tag in ("width", "height", "number"):
        for node in prop.iter(tag):
            try:
                values.append(int(node.text or "0"))
            except ValueError:
                pass
    return values


def _ui_semantic_size_justification(
    widget: ET.Element,
) -> tuple[str, str] | None:
    prop = widget.find("property[@name='RCMS_semantic_size_invariant']/string")
    value = (prop.text or "").strip() if prop is not None else ""
    category, separator, reason = value.partition(":")
    if (
        not separator
        or category.strip() not in UI_SEMANTIC_SIZE_CATEGORIES
        or not reason.strip()
    ):
        return None
    return category.strip(), reason.strip()


def _size_pair(widget: ET.Element, property_name: str) -> tuple[int, int] | None:
    prop = widget.find(f"property[@name='{property_name}']")
    if prop is None:
        return None
    values = _dimension_values(prop)
    return (values[0], values[1]) if len(values) >= 2 else None


def _scalar_dimension(widget: ET.Element, property_name: str) -> int | None:
    prop = widget.find(f"property[@name='{property_name}']")
    values = _dimension_values(prop) if prop is not None else []
    return values[0] if values else None


def _audit_form(path: Path) -> list[Finding]:
    findings = []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return [Finding(path, "invalid-ui-xml", str(exc))]
    top = root.find("widget")
    if top is None:
        return [Finding(path, "managed-content-root", "form has no top-level widget")]

    if not _managed_root(top):
        findings.append(
            Finding(
                path, "managed-content-root", "top-level content is not layout managed"
            )
        )

    geometry = top.find("property[@name='geometry']/rect")
    if geometry is not None:
        width = int(geometry.findtext("width", "0"))
        height = int(geometry.findtext("height", "0"))
        if width or height:
            findings.append(
                Finding(
                    path,
                    "historical-root-geometry",
                    f"root carries a {width}x{height} historical design size",
                )
            )

    parent_map = {child: parent for parent in root.iter() for child in parent}
    for widget in top.iter("widget"):
        if widget is top:
            continue
        child_geometry = widget.find("property[@name='geometry']")
        if (
            child_geometry is not None
            and widget.get("class") not in QT_CHROME_CLASSES
            and not _is_scroll_area_content(widget, parent_map)
        ):
            findings.append(
                Finding(
                    path,
                    "unmanaged-content-geometry",
                    f"{widget.get('name', '<unnamed>')} has absolute content geometry",
                )
            )
    for widget in top.iter("widget"):
        minimum = _size_pair(widget, "minimumSize")
        maximum = _size_pair(widget, "maximumSize")
        if (
            minimum
            and maximum
            and any(minimum[index] > maximum[index] for index in range(2))
        ):
            findings.append(
                Finding(
                    path,
                    "contradictory-constraint",
                    f"{widget.get('name', '<unnamed>')} has minimumSize above maximumSize",
                )
            )
        for axis in ("Width", "Height"):
            minimum_scalar = _scalar_dimension(widget, f"minimum{axis}")
            maximum_scalar = _scalar_dimension(widget, f"maximum{axis}")
            if (
                minimum_scalar is not None
                and maximum_scalar is not None
                and minimum_scalar > maximum_scalar
            ):
                findings.append(
                    Finding(
                        path,
                        "contradictory-constraint",
                        f"{widget.get('name', '<unnamed>')} has minimum{axis} above maximum{axis}",
                    )
                )
        justification = _ui_semantic_size_justification(widget)
        for prop in widget.findall("property"):
            if (
                prop.get("name") in SIZE_PROPERTIES
                and any(_dimension_values(prop))
                and justification is None
            ):
                findings.append(
                    Finding(
                        path,
                        "unjustified-hard-dimension",
                        f"{widget.get('name', '<unnamed>')} declares {prop.get('name')}",
                    )
                )

    for font in root.findall(".//font"):
        family = font.find("family")
        if family is not None and (family.text or "").strip():
            findings.append(Finding(path, "platform-font", "hard-coded font family"))
        for tag in ("pointsize", "pixelsize"):
            if font.find(tag) is not None:
                findings.append(Finding(path, "platform-font", f"hard-coded {tag}"))
    for prop in root.findall(".//property[@name='styleSheet']"):
        if STYLESHEET_FONT_RE.search("".join(prop.itertext())):
            findings.append(
                Finding(path, "platform-font", "hard-coded stylesheet font")
            )
    return findings


def _relative_source_path(path: Path, source_dir: Path) -> str:
    return path.relative_to(source_dir).as_posix()


def _is_generated_source(path: Path, source_dir: Path) -> bool:
    relative = _relative_source_path(path, source_dir)
    parts = set(Path(relative).parts)
    return (
        relative
        in {
            "ui_main_window.py",
            "ui_results_window.py",
            "forms/icons_rc.py",
        }
        or relative.startswith("forms/ui_")
        or bool(parts & {"_vendor", "third_party", "vendor"})
    )


def _source_exception(
    call: ast.Call, lines: Sequence[str], relative_path: str
) -> tuple[str, str] | None:
    candidate_lines: list[str] = []
    if 1 <= call.lineno <= len(lines):
        candidate_lines.append(lines[call.lineno - 1])
    if call.lineno >= 2:
        candidate_lines.append(lines[call.lineno - 2])
    annotation = next(
        (
            SOURCE_EXCEPTION_RE.match(line)
            for line in candidate_lines
            if SOURCE_EXCEPTION_RE.match(line)
        ),
        None,
    )
    if annotation is None:
        return None
    category = annotation.group("category")
    reason = annotation.group("reason").strip()
    rule = SOURCE_EXCEPTION_RULES.get(category)
    method = _call_name(call)
    if (
        not reason
        or rule is None
        or relative_path not in rule["paths"]
        or method not in rule["methods"]
    ):
        return None
    return category, reason


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _static_strings(
    node: ast.AST,
    bindings: Mapping[str, Sequence[ast.expr]],
    resolving: set[str] | None = None,
) -> set[str]:
    resolving = set() if resolving is None else resolving
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return {
            left + right
            for left in _static_strings(node.left, bindings, resolving)
            for right in _static_strings(node.right, bindings, resolving)
        }
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                return set()
            parts.append(value.value)
        return {"".join(parts)}
    if isinstance(node, ast.IfExp):
        return _static_strings(node.body, bindings, resolving) | _static_strings(
            node.orelse, bindings, resolving
        )
    if isinstance(node, ast.Name) and node.id not in resolving:
        values = set()
        for candidate in bindings.get(node.id, []):
            values.update(_static_strings(candidate, bindings, resolving | {node.id}))
        return values
    return set()


def _source_scope_index(
    tree: ast.AST,
) -> tuple[_NodeScopes, _NodeConditions, _ScopeParents, _Assignments]:
    """Index simple assignments without leaking constants across lexical scopes."""
    node_scopes: _NodeScopes = {}
    node_conditions: _NodeConditions = {}
    scope_parents: _ScopeParents = {tree: None}
    assignments: _Assignments = {tree: {}}

    class ScopeIndexer(ast.NodeVisitor):
        def __init__(self) -> None:
            self.scope: _Scope = tree
            self.conditional_depth = 0

        def generic_visit(self, node: ast.AST) -> None:
            node_scopes[node] = self.scope
            node_conditions[node] = bool(self.conditional_depth)
            super().generic_visit(node)

        def _visit_scope(
            self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ) -> None:
            node_scopes[node] = self.scope
            node_conditions[node] = bool(self.conditional_depth)
            for decorator in node.decorator_list:
                self.visit(decorator)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.visit(node.args)
                if node.returns is not None:
                    self.visit(node.returns)
            else:
                for base in node.bases:
                    self.visit(base)
                for keyword in node.keywords:
                    self.visit(keyword)
            parent_scope = self.scope
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and isinstance(
                parent_scope, ast.ClassDef
            ):
                parent_scope = scope_parents[parent_scope]
            scope_parents[node] = parent_scope
            assignments[node] = {}
            previous = self.scope
            previous_conditional_depth = self.conditional_depth
            self.scope = node
            self.conditional_depth = 0
            for statement in node.body:
                self.visit(statement)
            self.scope = previous
            self.conditional_depth = previous_conditional_depth

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._visit_scope(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._visit_scope(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self._visit_scope(node)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            node_scopes[node] = self.scope
            node_conditions[node] = bool(self.conditional_depth)
            self.visit(node.args)
            scope_parents[node] = self.scope
            assignments[node] = {}
            previous = self.scope
            previous_conditional_depth = self.conditional_depth
            self.scope = node
            self.conditional_depth = 0
            self.visit(node.body)
            self.scope = previous
            self.conditional_depth = previous_conditional_depth

        def visit_Assign(self, node: ast.Assign) -> None:
            node_scopes[node] = self.scope
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[self.scope].setdefault(target.id, []).append(
                        (node.lineno, node.value, bool(self.conditional_depth))
                    )
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            node_scopes[node] = self.scope
            if isinstance(node.target, ast.Name) and node.value is not None:
                assignments[self.scope].setdefault(node.target.id, []).append(
                    (node.lineno, node.value, bool(self.conditional_depth))
                )
            self.generic_visit(node)

        def visit_If(self, node: ast.If) -> None:
            node_scopes[node] = self.scope
            node_conditions[node] = bool(self.conditional_depth)
            self.visit(node.test)
            self._visit_conditional_statements((*node.body, *node.orelse))

        def _visit_conditional_statements(
            self, statements: tuple[ast.AST, ...]
        ) -> None:
            self.conditional_depth += 1
            for statement in statements:
                self.visit(statement)
            self.conditional_depth -= 1

        def _visit_loop(self, node: ast.For | ast.AsyncFor) -> None:
            node_scopes[node] = self.scope
            node_conditions[node] = bool(self.conditional_depth)
            self.visit(node.iter)
            self._visit_conditional_statements((node.target, *node.body, *node.orelse))

        def visit_For(self, node: ast.For) -> None:
            self._visit_loop(node)

        def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
            self._visit_loop(node)

        def visit_While(self, node: ast.While) -> None:
            node_scopes[node] = self.scope
            node_conditions[node] = bool(self.conditional_depth)
            self.visit(node.test)
            self._visit_conditional_statements((*node.body, *node.orelse))

        def _visit_try(self, node: ast.Try | ast.TryStar) -> None:
            node_scopes[node] = self.scope
            node_conditions[node] = bool(self.conditional_depth)
            statements: tuple[ast.AST, ...] = tuple(
                [*node.body, *node.orelse, *node.finalbody]
            )
            for handler in node.handlers:
                statements += tuple(handler.body)
            self._visit_conditional_statements(statements)

        def visit_Try(self, node: ast.Try) -> None:
            self._visit_try(node)

        def visit_TryStar(self, node: ast.TryStar) -> None:
            self._visit_try(node)

        def visit_Match(self, node: ast.Match) -> None:
            node_scopes[node] = self.scope
            node_conditions[node] = bool(self.conditional_depth)
            self.visit(node.subject)
            self._visit_conditional_statements(
                tuple(statement for case in node.cases for statement in case.body)
            )

        def _visit_with(self, node: ast.With | ast.AsyncWith) -> None:
            node_scopes[node] = self.scope
            node_conditions[node] = bool(self.conditional_depth)
            for item in node.items:
                self.visit(item.context_expr)
            self._visit_conditional_statements(tuple(node.body))

        def visit_With(self, node: ast.With) -> None:
            self._visit_with(node)

        def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
            self._visit_with(node)

    ScopeIndexer().visit(tree)
    return node_scopes, node_conditions, scope_parents, assignments


def _may_reaching(
    candidates: Sequence[tuple[int, _ReachingValue, bool]], cutoff: int | None = None
) -> list[_ReachingValue]:
    reaching: list[_ReachingValue] = []
    for lineno, value, conditional in sorted(candidates, key=lambda item: item[0]):
        if cutoff is not None and lineno >= cutoff:
            continue
        reaching = reaching + [value] if conditional else [value]
    return reaching


def _visible_bindings(
    call: ast.Call,
    node_scopes: _NodeScopes,
    scope_parents: _ScopeParents,
    assignments: _Assignments,
) -> _Bindings:
    scopes: list[_Scope] = []
    scope = node_scopes[call]
    while scope is not None:
        scopes.append(scope)
        scope = scope_parents[scope]

    visible: _Bindings = {}
    for candidate_scope in reversed(scopes):
        for name, candidates in assignments[candidate_scope].items():
            cutoff = call.lineno if candidate_scope is node_scopes[call] else None
            reaching = _may_reaching(candidates, cutoff)
            if reaching:
                visible[name] = reaching
    return visible


def _qfont_definitions(
    tree: ast.AST, node_scopes: _NodeScopes, node_conditions: _NodeConditions
) -> _Definitions:
    definitions: _Definitions = {}
    for node in ast.walk(tree):
        scope = node_scopes.get(node)
        if scope is None:
            continue
        if isinstance(node, ast.ImportFrom):
            for imported in node.names:
                provenance = (
                    "qfont"
                    if node.module == "PyQt6.QtGui" and imported.name == "QFont"
                    else "qtgui"
                    if node.module == "PyQt6" and imported.name == "QtGui"
                    else "other"
                )
                definitions.setdefault(scope, {}).setdefault(
                    imported.asname or imported.name, []
                ).append((node.lineno, provenance, node_conditions[node]))
        elif isinstance(node, ast.Import):
            for imported in node.names:
                bound_name = imported.asname or imported.name.split(".")[0]
                provenance = (
                    "qtgui"
                    if imported.name == "PyQt6.QtGui" and imported.asname
                    else "pyqt6"
                    if imported.name in {"PyQt6", "PyQt6.QtGui"}
                    else "other"
                )
                definitions.setdefault(scope, {}).setdefault(bound_name, []).append(
                    (node.lineno, provenance, node_conditions[node])
                )
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    definitions.setdefault(scope, {}).setdefault(target.id, []).append(
                        (node.lineno, "other", node_conditions[node])
                    )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
            if node.args.vararg:
                arguments += (node.args.vararg,)
            if node.args.kwarg:
                arguments += (node.args.kwarg,)
            for argument in arguments:
                definitions.setdefault(node, {}).setdefault(argument.arg, []).append(
                    (-1, "other", False)
                )
    return definitions


def _symbol_provenance(
    call: ast.Call,
    name: str,
    definitions: _Definitions,
    node_scopes: _NodeScopes,
    scope_parents: _ScopeParents,
) -> set[str]:
    scope = node_scopes[call]
    while scope is not None:
        scoped = definitions.get(scope, {}).get(name)
        if scoped is not None:
            cutoff = call.lineno if scope is node_scopes[call] else None
            return set(_may_reaching(scoped, cutoff))
        scope = scope_parents[scope]
    return set()


def _attribute_chain(node: ast.AST) -> tuple[str, ...]:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return tuple(reversed(parts))
    return ()


def _is_qfont_constructor(
    call: ast.Call,
    definitions: _Definitions,
    node_scopes: _NodeScopes,
    scope_parents: _ScopeParents,
) -> bool:
    chain = _attribute_chain(call.func)
    if not chain and isinstance(call.func, ast.Name):
        chain = (call.func.id,)
    if not chain:
        return False
    provenance = _symbol_provenance(
        call, chain[0], definitions, node_scopes, scope_parents
    )
    if len(chain) == 1:
        return "qfont" in provenance
    if chain[1:] == ("QFont",):
        return "qtgui" in provenance
    return chain[1:] == ("QtGui", "QFont") and "pyqt6" in provenance


STYLESHEET_FONT_RE = re.compile(
    r"(?:\bfont-family\s*:|\bfont-size\s*:|(?<![-\w])font\s*:)", re.I
)


def _audit_source_fonts(
    path: Path, tree: ast.AST, lines: list[str], relative_path: str
) -> list[Finding]:
    findings = []
    node_scopes, node_conditions, scope_parents, assignments = _source_scope_index(tree)
    qfont_definitions = _qfont_definitions(tree, node_scopes, node_conditions)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        bindings = _visible_bindings(node, node_scopes, scope_parents, assignments)
        if name == "setStyleSheet" and node.args:
            values = _static_strings(node.args[0], bindings)
            if any(STYLESHEET_FONT_RE.search(value) for value in values):
                findings.append(
                    Finding(
                        path,
                        "platform-font",
                        f"hard-coded stylesheet font at line {node.lineno}",
                    )
                )
        if _is_qfont_constructor(node, qfont_definitions, node_scopes, scope_parents):
            families = _static_strings(node.args[0], bindings) if node.args else set()
            family_keyword = next(
                (
                    keyword.value
                    for keyword in node.keywords
                    if keyword.arg is not None and keyword.arg.casefold() == "family"
                ),
                None,
            )
            if family_keyword is not None:
                families.update(_static_strings(family_keyword, bindings))
            if any(family.strip() for family in families):
                findings.append(
                    Finding(
                        path,
                        "platform-font",
                        f"{name} hard-codes a family at line {node.lineno}",
                    )
                )
            sized_keyword = any(
                keyword.arg is not None
                and keyword.arg.casefold() in {"pixelsize", "pointsize", "pointsizef"}
                for keyword in node.keywords
            )
            if len(node.args) >= 2 or sized_keyword:
                findings.append(
                    Finding(
                        path,
                        "platform-font",
                        f"{name} hard-codes an absolute size at line {node.lineno}",
                    )
                )
        elif name == "setFamily" and node.args:
            families = _static_strings(node.args[0], bindings)
            if any(family.strip() for family in families):
                findings.append(
                    Finding(
                        path,
                        "platform-font",
                        f"setFamily hard-codes a family at line {node.lineno}",
                    )
                )
        elif name in {"setPixelSize", "setPointSize", "setPointSizeF"}:
            if _source_exception(node, lines, relative_path) is None:
                findings.append(
                    Finding(
                        path,
                        "platform-font",
                        f"{name} at line {node.lineno} lacks a valid semantic exception",
                    )
                )
    return findings


def _audit_sources(source_dir: Path) -> list[Finding]:
    findings = []
    if not source_dir.exists():
        return findings
    for path in source_dir.rglob("*.py"):
        if _is_generated_source(path, source_dir):
            continue
        relative = _relative_source_path(path, source_dir)
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        for helper in LEGACY_HELPERS:
            if re.search(rf"\b{re.escape(helper)}\b", text):
                findings.append(
                    Finding(path, "legacy-sizing-helper", f"retired helper {helper}")
                )
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            findings.append(Finding(path, "invalid-python", str(exc)))
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(
                node.func, ast.Attribute
            ):
                continue
            if node.func.attr not in GUARDED_GEOMETRY_METHODS:
                continue
            if _source_exception(node, lines, relative) is None:
                findings.append(
                    Finding(
                        path,
                        "unjustified-geometry-call",
                        f"{node.func.attr} at line {node.lineno} lacks a valid semantic exception",
                    )
                )
        findings.extend(_audit_source_fonts(path, tree, lines, relative))
    return findings


def audit_repository(root: Path) -> list[Finding]:
    root = Path(root)
    source_dir = root / "src" / "rc_metastudio"
    forms_dir = source_dir / "forms"
    findings = []
    for path in sorted(forms_dir.glob("*.ui")):
        findings.extend(_audit_form(path))
    findings.extend(_audit_sources(source_dir))
    findings.extend(
        Finding(finding.path, "window-archetype", finding.detail)
        for finding in qt_window_ownership.audit_top_level_form_ownership(
            forms_dir, source_dir
        )
    )
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(args[0]) if args else Path(__file__).resolve().parents[1]
    findings = audit_repository(root)
    for finding in findings:
        print(finding)
    if findings:
        print(f"Qt layout contract audit failed with {len(findings)} finding(s).")
        return 1
    print("Qt layout contract audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
