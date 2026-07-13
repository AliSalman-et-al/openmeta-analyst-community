#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fail closed when canonical Qt layout contracts regress."""

import ast
from dataclasses import dataclass
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


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

# A canonical form is authoritative only when every runtime surface that owns it
# explicitly registers the stated role. Wizard pages inherit the Workflow Window
# contract from MainWizard and are therefore intentionally absent here.
TOP_LEVEL_FORM_INVENTORY = {
    "about_legal.ui": (("about_legal_dialog.py", "AboutLegalDialog", "TRANSACTIONAL"),),
    "binary_data_form2.ui": (
        ("binary_data_form.py", "BinaryDataForm2", "TRANSACTIONAL"),
    ),
    "change_cov_type_form.ui": (
        ("change_cov_type_form.py", "ChangeCovTypeForm", "TRANSACTIONAL"),
    ),
    "change_group_name_dlg.ui": (
        ("edit_group_name_form.py", "EditGroupName", "TRANSACTIONAL"),
        ("edit_group_name_form.py", "EditCovariateName", "TRANSACTIONAL"),
    ),
    "choose_back_calc_result_form.ui": (
        ("binary_data_form.py", "ChooseBackCalcResultForm", "TRANSACTIONAL"),
    ),
    "conf_level_dialog.ui": (
        ("conf_level_dialog.py", "ChangeConfLevelDlg", "CONFIDENCE_LEVEL"),
    ),
    "continuous_back_calc_result_form.ui": (
        ("continuous_data_form.py", "ChooseBackCalcResultForm", "TRANSACTIONAL"),
    ),
    "continuous_data_form.ui": (
        ("continuous_data_form.py", "ContinuousDataForm", "TRANSACTIONAL"),
    ),
    "cov_reg_dlg2.ui": (("meta_reg_form.py", "MetaRegForm", "TRANSACTIONAL"),),
    "cov_subgroup_dlg.ui": (
        ("meta_subgroup_form.py", "MetaSubgroupForm", "TRANSACTIONAL"),
    ),
    "diagnostic_data_form.ui": (
        ("diagnostic_data_form.py", "DiagnosticDataForm", "TRANSACTIONAL"),
    ),
    "diagnostic_metrics.ui": (("diag_metrics.py", "Diag_Metrics", "TRANSACTIONAL"),),
    "edit_dialog2.ui": (("edit_dialog.py", "EditDialog", "EDIT_DATASET"),),
    "edit_forest_plot.ui": (("results_window.py", "EditPlotDialog", "TRANSACTIONAL"),),
    "ma_specs2.ui": (("ma_specs.py", "MA_Specs", "TRANSACTIONAL"),),
    "meta.ui": (("meta_form.py", "MetaForm", "MAIN"),),
    "network_view_window.ui": (("network_view.py", "ViewDialog", "NETWORK_VIEW"),),
    "new_covariate_dlg.ui": (
        ("add_new_dialogs.py", "AddNewCovariateForm", "TRANSACTIONAL"),
    ),
    "new_follow_up_dlg.ui": (
        ("add_new_dialogs.py", "AddNewFollowUpForm", "TRANSACTIONAL"),
    ),
    "new_group_dlg.ui": (("add_new_dialogs.py", "AddNewGroupForm", "TRANSACTIONAL"),),
    "new_outcome_dlg.ui": (
        ("add_new_dialogs.py", "AddNewOutcomeForm", "TRANSACTIONAL"),
    ),
    "new_study_dlg.ui": (("add_new_dialogs.py", "AddNewStudyForm", "TRANSACTIONAL"),),
    "results_window.ui": (("results_window.py", "ResultsWindow", "RESULTS"),),
    "running.ui": (
        ("ma_specs.py", "MetaProgress", "TRANSIENT"),
        ("meta_form.py", "ImportProgress", "TRANSIENT"),
        ("progress_bar.py", "MetaProgress", "TRANSIENT"),
    ),
}

TOP_LEVEL_CLASSES = {"QDialog", "QMainWindow"}
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
        "methods": {"move", "resize", "setMaximumSize"},
    },
    "bounded-native-popup": {
        "paths": {
            "adaptive_controls.py",
            "binary_data_form.py",
            "continuous_data_form.py",
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
            "binary_data_form.py",
            "continuous_data_form.py",
            "diagnostic_data_form.py",
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
            "binary_data_form.py",
            "continuous_data_form.py",
            "diagnostic_data_form.py",
            "ma_specs.py",
            "meta_form.py",
            "results_window.py",
        },
        "methods": {"setMaximumWidth", "setMinimumWidth"},
    },
    "intrinsic-ratio": {
        "paths": {"network_view.py", "results_window.py"},
        "methods": {"fitInView", "setSceneRect"},
    },
    "numeric-domain-control": {
        "paths": {
            "calculator_routines.py",
            "continuous_data_form.py",
            "diagnostic_data_form.py",
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
    "verification-layout-fixture": {
        "paths": {"adaptive_layout_evidence.py", "launch.py"},
        "methods": {"adjustSize", "move", "resize"},
    },
}

UI_SEMANTIC_SIZE_CATEGORIES = {
    "intrinsic-ratio",
    "numeric-domain-control",
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

    def __str__(self):
        return f"{self.path}: {self.rule}: {self.detail}"


def _managed_root(top_widget):
    if top_widget.find("layout") is not None:
        return True
    if top_widget.get("class") == "QMainWindow":
        central = top_widget.find("widget[@name='centralwidget']")
        return central is not None and central.find("layout") is not None
    return False


def _is_scroll_area_content(widget, parent_map):
    parent = parent_map.get(widget)
    return (
        parent is not None
        and parent.tag == "widget"
        and parent.get("class") == "QScrollArea"
    )


def _dimension_values(prop):
    values = []
    for tag in ("width", "height", "number"):
        for node in prop.iter(tag):
            try:
                values.append(int(node.text or "0"))
            except ValueError:
                pass
    return values


def _ui_semantic_size_justification(widget):
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


def _size_pair(widget, property_name):
    prop = widget.find(f"property[@name='{property_name}']")
    if prop is None:
        return None
    values = _dimension_values(prop)
    return tuple(values[:2]) if len(values) >= 2 else None


def _scalar_dimension(widget, property_name):
    prop = widget.find(f"property[@name='{property_name}']")
    values = _dimension_values(prop) if prop is not None else []
    return values[0] if values else None


def _audit_form(path):
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
            findings.append(Finding(path, "platform-font", "hard-coded stylesheet font"))
    return findings


def _relative_source_path(path, source_dir):
    return path.relative_to(source_dir).as_posix()


def _is_generated_source(path, source_dir):
    relative = _relative_source_path(path, source_dir)
    parts = set(Path(relative).parts)
    return (
        relative
        in {
            "ui_meta.py",
            "ui_results_window.py",
            "forms/icons_rc.py",
        }
        or relative.startswith("forms/ui_")
        or bool(parts & {"_vendor", "third_party", "vendor"})
    )


def _source_exception(call, lines, relative_path):
    candidate_lines = []
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


def _call_name(call):
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _static_strings(node, bindings, resolving=None):
    resolving = set() if resolving is None else resolving
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return {
            left + right
            for left in _static_strings(node.left, bindings, resolving)
            for right in _static_strings(node.right, bindings, resolving)
        }
    if isinstance(node, ast.JoinedStr) and all(
        isinstance(value, ast.Constant) and isinstance(value.value, str)
        for value in node.values
    ):
        return {"".join(value.value for value in node.values)}
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


def _source_scope_index(tree):
    """Index simple assignments without leaking constants across lexical scopes."""

    node_scopes = {}
    node_conditions = {}
    scope_parents = {tree: None}
    assignments = {tree: {}}

    class ScopeIndexer(ast.NodeVisitor):
        def __init__(self):
            self.scope = tree
            self.conditional_depth = 0

        def generic_visit(self, node):
            node_scopes[node] = self.scope
            node_conditions[node] = bool(self.conditional_depth)
            super().generic_visit(node)

        def _visit_scope(self, node):
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

        def visit_FunctionDef(self, node):
            self._visit_scope(node)

        def visit_AsyncFunctionDef(self, node):
            self._visit_scope(node)

        def visit_ClassDef(self, node):
            self._visit_scope(node)

        def visit_Lambda(self, node):
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

        def visit_Assign(self, node):
            node_scopes[node] = self.scope
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[self.scope].setdefault(target.id, []).append(
                        (node.lineno, node.value, bool(self.conditional_depth))
                    )
            self.generic_visit(node)

        def visit_AnnAssign(self, node):
            node_scopes[node] = self.scope
            if isinstance(node.target, ast.Name) and node.value is not None:
                assignments[self.scope].setdefault(node.target.id, []).append(
                    (node.lineno, node.value, bool(self.conditional_depth))
                )
            self.generic_visit(node)

        def visit_If(self, node):
            node_scopes[node] = self.scope
            node_conditions[node] = bool(self.conditional_depth)
            self.visit(node.test)
            self._visit_conditional_statements((*node.body, *node.orelse))

        def _visit_conditional_statements(self, statements):
            self.conditional_depth += 1
            for statement in statements:
                self.visit(statement)
            self.conditional_depth -= 1

        def visit_For(self, node):
            node_scopes[node] = self.scope
            node_conditions[node] = bool(self.conditional_depth)
            self.visit(node.iter)
            self._visit_conditional_statements((node.target, *node.body, *node.orelse))

        visit_AsyncFor = visit_For

        def visit_While(self, node):
            node_scopes[node] = self.scope
            node_conditions[node] = bool(self.conditional_depth)
            self.visit(node.test)
            self._visit_conditional_statements((*node.body, *node.orelse))

        def visit_Try(self, node):
            node_scopes[node] = self.scope
            node_conditions[node] = bool(self.conditional_depth)
            statements = [*node.body, *node.orelse, *node.finalbody]
            for handler in node.handlers:
                statements.extend(handler.body)
            self._visit_conditional_statements(statements)

        visit_TryStar = visit_Try

        def visit_Match(self, node):
            node_scopes[node] = self.scope
            node_conditions[node] = bool(self.conditional_depth)
            self.visit(node.subject)
            self._visit_conditional_statements(
                tuple(statement for case in node.cases for statement in case.body)
            )

        def visit_With(self, node):
            node_scopes[node] = self.scope
            node_conditions[node] = bool(self.conditional_depth)
            for item in node.items:
                self.visit(item.context_expr)
            self._visit_conditional_statements(tuple(node.body))

        visit_AsyncWith = visit_With

    ScopeIndexer().visit(tree)
    return node_scopes, node_conditions, scope_parents, assignments


def _may_reaching(candidates, cutoff=None):
    reaching = []
    for lineno, value, conditional in sorted(candidates, key=lambda item: item[0]):
        if cutoff is not None and lineno >= cutoff:
            continue
        reaching = reaching + [value] if conditional else [value]
    return reaching


def _visible_bindings(call, node_scopes, scope_parents, assignments):
    scopes = []
    scope = node_scopes[call]
    while scope is not None:
        scopes.append(scope)
        scope = scope_parents[scope]

    visible = {}
    for candidate_scope in reversed(scopes):
        for name, candidates in assignments[candidate_scope].items():
            cutoff = call.lineno if candidate_scope is node_scopes[call] else None
            reaching = _may_reaching(candidates, cutoff)
            if reaching:
                visible[name] = reaching
    return visible


def _qfont_definitions(tree, node_scopes, node_conditions):
    definitions = {}
    for node in ast.walk(tree):
        scope = node_scopes.get(node)
        if scope is None:
            continue
        if isinstance(node, ast.ImportFrom):
            for imported in node.names:
                provenance = (
                    "qfont"
                    if node.module == "PyQt5.QtGui" and imported.name == "QFont"
                    else "qtgui"
                    if node.module == "PyQt5" and imported.name == "QtGui"
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
                    if imported.name == "PyQt5.QtGui" and imported.asname
                    else "pyqt5"
                    if imported.name in {"PyQt5", "PyQt5.QtGui"}
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


def _symbol_provenance(call, name, definitions, node_scopes, scope_parents):
    scope = node_scopes[call]
    while scope is not None:
        scoped = definitions.get(scope, {}).get(name)
        if scoped is not None:
            cutoff = call.lineno if scope is node_scopes[call] else None
            return set(_may_reaching(scoped, cutoff))
        scope = scope_parents[scope]
    return set()


def _attribute_chain(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return list(reversed(parts))
    return []


def _is_qfont_constructor(call, definitions, node_scopes, scope_parents):
    chain = _attribute_chain(call.func)
    if not chain and isinstance(call.func, ast.Name):
        chain = [call.func.id]
    if not chain:
        return False
    provenance = _symbol_provenance(
        call, chain[0], definitions, node_scopes, scope_parents
    )
    if len(chain) == 1:
        return "qfont" in provenance
    if chain[1:] == ["QFont"]:
        return "qtgui" in provenance
    return chain[1:] == ["QtGui", "QFont"] and "pyqt5" in provenance


STYLESHEET_FONT_RE = re.compile(
    r"(?:\bfont-family\s*:|\bfont-size\s*:|(?<![-\w])font\s*:)", re.I
)


def _audit_source_fonts(path, tree, lines, relative_path):
    findings = []
    node_scopes, node_conditions, scope_parents, assignments = _source_scope_index(tree)
    qfont_definitions = _qfont_definitions(tree, node_scopes, node_conditions)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        bindings = _visible_bindings(
            node, node_scopes, scope_parents, assignments
        )
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


def _audit_sources(source_dir):
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
        for call in (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in GUARDED_GEOMETRY_METHODS
        ):
            if _source_exception(call, lines, relative) is None:
                findings.append(
                    Finding(
                        path,
                        "unjustified-geometry-call",
                        f"{call.func.attr} at line {call.lineno} lacks a valid semantic exception",
                    )
                )
        findings.extend(_audit_source_fonts(path, tree, lines, relative))
    return findings


def _audit_inventory(forms_dir, source_dir):
    findings = []
    actual_top_levels = set()
    for path in forms_dir.glob("*.ui"):
        top = ET.parse(path).getroot().find("widget")
        if top is not None and top.get("class") in TOP_LEVEL_CLASSES:
            actual_top_levels.add(path.name)
    expected = set(TOP_LEVEL_FORM_INVENTORY)
    for missing in sorted(actual_top_levels - expected):
        findings.append(
            Finding(
                forms_dir / missing,
                "window-archetype",
                "top-level form has no authoritative inventory entry",
            )
        )
    for stale in sorted(expected - actual_top_levels):
        findings.append(
            Finding(
                forms_dir / stale,
                "window-archetype",
                "inventory entry is not a canonical top-level form",
            )
        )
    parsed_sources = {}
    for form_name, registrations in TOP_LEVEL_FORM_INVENTORY.items():
        for source_name, class_name, role in registrations:
            source = source_dir / source_name
            if source not in parsed_sources:
                parsed_sources[source] = (
                    ast.parse(source.read_text(encoding="utf-8"))
                    if source.exists()
                    else None
                )
            tree = parsed_sources[source]
            target_class = next(
                (
                    node
                    for node in (tree.body if tree is not None else ())
                    if isinstance(node, ast.ClassDef) and node.name == class_name
                ),
                None,
            )
            exact_registration = (
                any(
                    _is_exact_window_registration(node, role)
                    for node in ast.walk(target_class)
                )
                if target_class is not None
                else False
            )
            if not exact_registration:
                findings.append(
                    Finding(
                        source,
                        "window-archetype",
                        f"{class_name} for {form_name} does not explicitly register {role}",
                    )
                )
    return findings


def _is_exact_window_registration(node, expected_role):
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    if (
        node.func.attr != "register_adaptive_window"
        or not isinstance(node.func.value, ast.Name)
        or node.func.value.id != "adaptive_window"
        or not node.args
        or not isinstance(node.args[0], ast.Name)
        or node.args[0].id != "self"
    ):
        return False
    role_node = (
        node.args[1]
        if len(node.args) >= 2
        else next(
            (keyword.value for keyword in node.keywords if keyword.arg == "role"), None
        )
    )
    return (
        isinstance(role_node, ast.Attribute)
        and role_node.attr == expected_role
        and isinstance(role_node.value, ast.Attribute)
        and role_node.value.attr == "WindowRole"
        and isinstance(role_node.value.value, ast.Name)
        and role_node.value.value.id == "adaptive_window"
    )


def audit_repository(root, require_inventory=True):
    root = Path(root)
    source_dir = root / "src" / "rc_metastudio"
    forms_dir = source_dir / "forms"
    findings = []
    for path in sorted(forms_dir.glob("*.ui")):
        findings.extend(_audit_form(path))
    findings.extend(_audit_sources(source_dir))
    if require_inventory:
        findings.extend(_audit_inventory(forms_dir, source_dir))
    return findings


def main(argv=None):
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
