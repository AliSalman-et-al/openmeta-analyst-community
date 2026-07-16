"""Fail-closed mechanical tooling for RC MetaStudio's native Qt 6 port."""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import tokenize
from typing import Any, Iterable, Mapping, Sequence

import libcst as cst
from libcst import metadata


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "config" / "qt6-codemod-mappings.json"
_GENERATED_MARKERS = (
    "Form implementation generated from reading ui file",
    "Resource object code",
)
_BINDINGS = ("PyQt5", "PyQt6")
_FACADE_ROOTS = {"qtpy", "PySide2", "PySide6", "Qt5Compat"}
_RESOURCE_NAMES = {"qt_resource_data", "qInitResources", "qCleanupResources"}


@dataclass(frozen=True, slots=True)
class MappingManifest:
    schema_version: int
    binding_from: str
    binding_to: str
    moved_classes: Mapping[str, str]
    removed_apis: Mapping[str, str]
    method_rewrites: Mapping[str, str]
    scoped_enums: Mapping[str, str]
    class_scoped_enums: Mapping[str, str]
    ambiguous_enums: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class Diagnostic:
    file: str
    line: int
    column: int
    symbol: str
    action: str


@dataclass(frozen=True, slots=True)
class Transformation(Diagnostic):
    kind: str
    replacement: str


@dataclass(frozen=True, slots=True)
class MigrationResult:
    file: str
    code: str
    transformations: tuple[Transformation, ...]
    refusals: tuple[Diagnostic, ...]

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema_version": 1,
                "file": self.file,
                "changed": bool(self.transformations),
                "transformations": [asdict(item) for item in self.transformations],
                "refusals": [asdict(item) for item in self.refusals],
            },
            indent=2,
            sort_keys=True,
        ) + "\n"


class MigrationRefused(RuntimeError):
    """Raised when a source file contains a site requiring human judgment."""

    def __init__(self, result: MigrationResult) -> None:
        self.result = result
        locations = ", ".join(
            f"{item.file}:{item.line}:{item.column} {item.symbol}: {item.action}"
            for item in result.refusals
        )
        super().__init__(f"Qt6 migration refused: {locations}")


class MigrationTransactionError(RuntimeError):
    """Raised when a filesystem-safe multi-file migration cannot commit."""


@dataclass(frozen=True, slots=True)
class StrictFinding:
    file: str
    line: int
    column: int
    rule: str
    symbol: str
    action: str


@dataclass(frozen=True, slots=True)
class _InstanceBindings:
    qt: frozenset[str]
    non_qt: frozenset[str]
    ambiguous: frozenset[str]


@dataclass(frozen=True, slots=True)
class _DynamicImportSite:
    line: int
    column: int
    symbol: str
    rule: str
    action: str


@dataclass(frozen=True, slots=True)
class FileMigration:
    path: Path
    source_bytes: bytes
    target_bytes: bytes
    source_identity: tuple[int, int, int, int, int]
    mode: int
    encoding: str
    result: MigrationResult


def _require_string_map(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    ):
        raise ValueError(f"mapping manifest {field!r} must be a string-to-string object")
    return dict(value)


def _is_compatibility_path(name: str) -> bool:
    parts = name.split(".")
    if parts[0] in _FACADE_ROOTS:
        return True
    return any(
        part == "Qt5Compat" or re.fullmatch(r"Qt[A-Za-z0-9_]*5Compat", part)
        for part in parts
    )


def _is_qt_symbol(name: str) -> bool:
    return name.startswith(tuple(f"{binding}." for binding in _BINDINGS)) and not _is_compatibility_path(name)


def load_mapping_manifest(path: Path = DEFAULT_MANIFEST) -> MappingManifest:
    """Load and validate the authoritative mechanical rewrite manifest."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version",
        "binding",
        "moved_classes",
        "removed_apis",
        "method_rewrites",
        "scoped_enums",
        "class_scoped_enums",
        "ambiguous_enums",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("mapping manifest has missing or unknown top-level fields")
    binding = payload["binding"]
    if binding != {"from": "PyQt5", "to": "PyQt6"}:
        raise ValueError("mapping manifest must describe the PyQt5-to-PyQt6 hard cutover")
    if payload["schema_version"] != 1:
        raise ValueError("unsupported mapping manifest schema version")
    return MappingManifest(
        schema_version=1,
        binding_from=binding["from"],
        binding_to=binding["to"],
        moved_classes=_require_string_map(payload["moved_classes"], "moved_classes"),
        removed_apis=_require_string_map(payload["removed_apis"], "removed_apis"),
        method_rewrites=_require_string_map(payload["method_rewrites"], "method_rewrites"),
        scoped_enums=_require_string_map(payload["scoped_enums"], "scoped_enums"),
        class_scoped_enums=_require_string_map(
            payload["class_scoped_enums"], "class_scoped_enums"
        ),
        ambiguous_enums=_require_string_map(payload["ambiguous_enums"], "ambiguous_enums"),
    )


def _dotted_name(node: cst.CSTNode | None) -> str:
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr.value}" if parent else node.attr.value
    return ""


def _local_import_name(alias: cst.ImportAlias) -> str:
    if alias.asname is not None:
        if not isinstance(alias.asname.name, cst.Name):
            raise ValueError("import aliases must use a simple local name")
        return alias.asname.name.value
    return _dotted_name(alias.name).split(".", 1)[0]


class _ImportBindings(cst.CSTVisitor):
    def __init__(self) -> None:
        self.qt_aliases: set[str] = set()
        self.module_aliases: dict[str, str] = {}

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        module = _dotted_name(node.module)
        if module not in _BINDINGS and not any(
            module.startswith(f"{binding}.") for binding in _BINDINGS
        ):
            return
        if isinstance(node.names, cst.ImportStar):
            return
        for alias in node.names:
            imported = _dotted_name(alias.name)
            local = _local_import_name(alias)
            qualified = f"{module}.{imported}"
            self.module_aliases[local] = qualified
            if module.endswith(".QtCore") and imported == "Qt":
                self.qt_aliases.add(local)
            elif module in _BINDINGS and imported == "QtCore":
                self.module_aliases[local] = qualified

    def visit_Import(self, node: cst.Import) -> None:
        for alias in node.names:
            imported = _dotted_name(alias.name)
            if imported in _BINDINGS or any(
                imported.startswith(f"{binding}.") for binding in _BINDINGS
            ):
                bound = imported if alias.asname is not None else imported.split(".", 1)[0]
                self.module_aliases[_local_import_name(alias)] = bound


def _qualified_expression(node: cst.BaseExpression, bindings: _ImportBindings) -> str:
    dotted = _dotted_name(node)
    root, separator, remainder = dotted.partition(".")
    resolved = bindings.module_aliases.get(root, root)
    if separator:
        resolved = f"{resolved}.{remainder}"
    return resolved


def _qt_owner(node: cst.BaseExpression, bindings: _ImportBindings) -> bool:
    dotted = _dotted_name(node)
    if dotted in bindings.qt_aliases:
        return True
    return _qualified_expression(node, bindings) in {
        "PyQt5.QtCore.Qt",
        "PyQt6.QtCore.Qt",
    }


class _RefusalVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (metadata.PositionProvider, metadata.ParentNodeProvider)

    def __init__(
        self,
        filename: str,
        manifest: MappingManifest,
        bindings: _ImportBindings,
        instances: _InstanceBindings,
    ) -> None:
        self.filename = filename
        self.manifest = manifest
        self.bindings = bindings
        self.instances = instances
        self.refusals: list[Diagnostic] = []
        self._scopes = {
            target.split(".", 1)[0] for target in manifest.scoped_enums.values()
        }

    def _add(self, node: cst.CSTNode, symbol: str, action: str) -> None:
        position = self.get_metadata(metadata.PositionProvider, node).start
        self.refusals.append(
            Diagnostic(self.filename, position.line, position.column + 1, symbol, action)
        )

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        module = _dotted_name(node.module)
        if _is_compatibility_path(module):
            self._add(
                node,
                module,
                "remove the Qt5 compatibility or alternate binding import",
            )
        if isinstance(node.names, cst.ImportStar):
            if module == self.manifest.binding_from or module.startswith(
                f"{self.manifest.binding_from}."
            ):
                self._add(
                    node,
                    f"{module}.*",
                    "replace the wildcard with explicit imports before migration",
                )
            return
        destinations = {
            (
                self.manifest.moved_classes.get(
                    f"{module}.{_dotted_name(alias.name)}"
                )
                or f"{_replace_root(module, self.manifest)}.{_dotted_name(alias.name)}"
            ).rpartition(".")[0]
            for alias in node.names
        }
        requires_split = len(destinations) > 1
        if requires_split and (
            module == self.manifest.binding_from
            or module.startswith(f"{self.manifest.binding_from}.")
        ):
            rendered = cst.Module([]).code_for_node(node)
            canonical = (
                f"from {module} import "
                + ", ".join(_alias_text(alias) for alias in node.names)
            )
            if rendered != canonical:
                self._add(
                    node,
                    module,
                    "split or normalize this moved-class import manually so formatting and comments remain lossless",
                )
        parent = self.get_metadata(metadata.ParentNodeProvider, node)
        if (
            module == self.manifest.binding_from
            or module.startswith(f"{self.manifest.binding_from}.")
        ) and (
            not isinstance(parent, cst.SimpleStatementLine) or len(parent.body) != 1
        ):
            self._add(
                node,
                module,
                "put the Qt import on its own statement before migration",
            )
        for alias in node.names:
            symbol = f"{module}.{_dotted_name(alias.name)}"
            if not _is_compatibility_path(module) and _is_compatibility_path(symbol):
                self._add(
                    alias,
                    symbol,
                    "remove the Qt5 compatibility or alternate binding import",
                )
            action = _removed_action(symbol, self.manifest)
            if action is not None:
                self._add(node, symbol, action)

    def visit_Import(self, node: cst.Import) -> None:
        for alias in node.names:
            module = _dotted_name(alias.name)
            if _is_compatibility_path(module):
                self._add(
                    alias,
                    module,
                    "remove the Qt5 compatibility or alternate binding import",
                )
            if (
                module.startswith(f"{self.manifest.binding_from}.")
                and alias.asname is None
            ):
                self._add(
                    alias,
                    module,
                    "add an explicit alias before migration because dotted imports bind the PyQt5 root name",
                )

    def visit_Attribute(self, node: cst.Attribute) -> None:
        qualified = _qualified_expression(node, self.bindings)
        if _class_enum_replacement(qualified, self.manifest) is not None:
            return
        removed_action = _removed_action(qualified, self.manifest)
        if removed_action is not None:
            self._add(node, qualified, removed_action)
            return
        moved_target = _moved_target(qualified, self.manifest)
        if moved_target is not None and qualified != moved_target:
            self._add(
                node,
                qualified,
                f"import or reference this class from {moved_target}",
            )
            return
        if node.attr.value in self.manifest.method_rewrites:
            receiver = _qt_receiver_symbol(node.value, self.bindings)
            local = _dotted_name(node.value)
            if _is_qt_symbol(receiver) or local in self.instances.qt:
                return
            if local in self.instances.non_qt:
                return
            self._add(
                node,
                f"{local}.{node.attr.value}" if local else node.attr.value,
                "prove the receiver's Qt constructor assignment or migrate this exec_ call manually",
            )
            return
        if not _qt_owner(node.value, self.bindings):
            return
        name = node.attr.value
        owner = _dotted_name(node.value)
        if name in self.manifest.ambiguous_enums:
            self._add(node, f"{owner}.{name}", self.manifest.ambiguous_enums[name])
        elif name not in self.manifest.scoped_enums and name not in self._scopes:
            self._add(
                node,
                f"{owner}.{name}",
                "add an explicit scoped-enum mapping or migrate this site manually",
            )


def _replace_root(module: str, manifest: MappingManifest) -> str:
    if module == manifest.binding_from:
        return manifest.binding_to
    prefix = f"{manifest.binding_from}."
    return f"{manifest.binding_to}.{module[len(prefix):]}" if module.startswith(prefix) else module


def _normalize_qt5(symbol: str, manifest: MappingManifest) -> str:
    if symbol == manifest.binding_to:
        return manifest.binding_from
    prefix = f"{manifest.binding_to}."
    if symbol.startswith(prefix):
        return f"{manifest.binding_from}.{symbol[len(prefix):]}"
    return symbol


def _moved_target(symbol: str, manifest: MappingManifest) -> str | None:
    return manifest.moved_classes.get(_normalize_qt5(symbol, manifest))


def _removed_action(symbol: str, manifest: MappingManifest) -> str | None:
    return manifest.removed_apis.get(_normalize_qt5(symbol, manifest))


def _class_enum_replacement(
    symbol: str, manifest: MappingManifest
) -> str | None:
    return manifest.class_scoped_enums.get(_normalize_qt5(symbol, manifest))


def _alias_text(alias: cst.ImportAlias) -> str:
    imported = _dotted_name(alias.name)
    if alias.asname is not None:
        if not isinstance(alias.asname.name, cst.Name):
            raise ValueError("import aliases must use a simple local name")
        return f"{imported} as {alias.asname.name.value}"
    return imported


def _qt_receiver_symbol(
    node: cst.BaseExpression, bindings: _ImportBindings
) -> str:
    if isinstance(node, cst.Call):
        return _qualified_expression(node.func, bindings)
    return _qualified_expression(node, bindings)


def _resolve_ast_symbol(name: str, aliases: Mapping[str, str]) -> str:
    root, separator, remainder = name.partition(".")
    resolved = aliases.get(root, root)
    return f"{resolved}.{remainder}" if separator else resolved


def _build_instance_bindings(
    source: str, bindings: _ImportBindings | Mapping[str, str]
) -> _InstanceBindings:
    tree = ast.parse(source)
    assignments: dict[str, list[str]] = {}
    aliases = bindings.module_aliases if isinstance(bindings, _ImportBindings) else bindings

    def record(name: str, value: ast.AST | None) -> None:
        kind = "ambiguous"
        if isinstance(value, ast.Call):
            constructor = _resolve_ast_symbol(_ast_name(value.func), aliases)
            if _is_qt_symbol(constructor):
                kind = "qt"
            elif constructor.rsplit(".", 1)[-1][:1].isupper():
                kind = "non_qt"
        assignments.setdefault(name, []).append(kind)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    record(target.id, node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            record(node.target.id, node.value)
        elif isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name):
            record(node.target.id, node.value)
        elif isinstance(node, ast.arg):
            assignments.setdefault(node.arg, []).append("ambiguous")

    qt: set[str] = set()
    non_qt: set[str] = set()
    ambiguous: set[str] = set()
    for name, kinds in assignments.items():
        if kinds == ["qt"]:
            qt.add(name)
        elif kinds == ["non_qt"]:
            non_qt.add(name)
        else:
            ambiguous.add(name)
    return _InstanceBindings(frozenset(qt), frozenset(non_qt), frozenset(ambiguous))


def _dynamic_import_sites(source: str) -> tuple[_DynamicImportSite, ...]:
    tree = ast.parse(source)
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for imported in node.names:
                local = imported.asname or imported.name.split(".", 1)[0]
                aliases[local] = imported.name if imported.asname else imported.name.split(".", 1)[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            for imported in node.names:
                aliases[imported.asname or imported.name] = f"{node.module}.{imported.name}"
    intrinsic_names = {
        local
        for local, target in aliases.items()
        if target in {
            "importlib",
            "builtins",
            "importlib.import_module",
            "builtins.__import__",
        }
    } | {"__import__"}
    shadowed: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            if node.id in intrinsic_names:
                shadowed.add(node.id)
        elif isinstance(node, ast.arg) and node.arg in intrinsic_names:
            shadowed.add(node.arg)
    sites: list[_DynamicImportSite] = []

    def constant_string(node: ast.AST | None) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None

    def import_module_target(node: ast.Call) -> tuple[str | None, str | None]:
        if len(node.args) > 2 or any(keyword.arg is None for keyword in node.keywords):
            return None, "unsupported or expanded import_module arguments"
        values: dict[str, ast.AST] = {}
        if node.args:
            values["name"] = node.args[0]
        if len(node.args) == 2:
            values["package"] = node.args[1]
        for keyword in node.keywords:
            if keyword.arg not in {"name", "package"}:
                return None, f"unsupported import_module keyword {keyword.arg!r}"
            if keyword.arg in values:
                return None, f"duplicate import_module {keyword.arg} argument"
            values[keyword.arg] = keyword.value
        name = constant_string(values.get("name"))
        if name is None:
            return None, "missing or nonconstant import_module name"
        package_node = values.get("package")
        package = constant_string(package_node)
        if package_node is not None and package is None:
            return None, "nonconstant import_module package"
        if name.startswith("."):
            if not package:
                return None, "relative import_module name requires a constant package"
            try:
                return importlib.util.resolve_name(name, package), None
            except (ImportError, ValueError) as exc:
                return None, f"invalid relative import_module target: {exc}"
        return name, None

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = _resolve_ast_symbol(_ast_name(node.func), aliases)
        if function not in {
            "importlib.import_module",
            "__import__",
            "builtins.__import__",
        }:
            continue
        raw_root = _ast_name(node.func).split(".", 1)[0]
        argument = node.args[0] if node.args else None
        target = constant_string(argument)
        ambiguity: str | None = None
        resolved_target = target
        if function == "importlib.import_module":
            resolved_target, ambiguity = import_module_target(node)
        display = (
            f"{function}({json.dumps(target)})"
            if target is not None
            else f"{function}(<dynamic>)"
        )
        if raw_root in shadowed:
            sites.append(
                _DynamicImportSite(
                    node.lineno,
                    node.col_offset + 1,
                    f"{function}(<shadowed>)",
                    "dynamic-binding-import",
                    "rename or remove the shadowed dynamic import intrinsic before Qt migration",
                )
            )
        elif ambiguity is not None or resolved_target is None:
            sites.append(
                _DynamicImportSite(
                    node.lineno,
                    node.col_offset + 1,
                    display,
                    "dynamic-binding-import",
                    "replace the ambiguous dynamic import with explicit imports before Qt migration"
                    + (f": {ambiguity}" if ambiguity else ""),
                )
            )
        elif resolved_target == "PyQt5" or resolved_target.startswith("PyQt5."):
            sites.append(
                _DynamicImportSite(
                    node.lineno,
                    node.col_offset + 1,
                    display,
                    "pyqt5-import",
                    "replace the runtime PyQt5 import with a direct PyQt6 import",
                )
            )
        elif _is_compatibility_path(resolved_target):
            sites.append(
                _DynamicImportSite(
                    node.lineno,
                    node.col_offset + 1,
                    display,
                    "binding-facade",
                    "remove the runtime compatibility or alternate binding import",
                )
            )
    return tuple(sorted(sites, key=lambda item: (item.line, item.column, item.symbol)))


class _Qt6Transformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (metadata.PositionProvider,)

    def __init__(
        self,
        filename: str,
        manifest: MappingManifest,
        bindings: _ImportBindings,
        instances: _InstanceBindings,
    ) -> None:
        self.filename = filename
        self.manifest = manifest
        self.bindings = bindings
        self.instances = instances
        self.transformations: list[Transformation] = []

    def _record(
        self,
        node: cst.CSTNode,
        *,
        kind: str,
        symbol: str,
        replacement: str,
    ) -> None:
        position = self.get_metadata(metadata.PositionProvider, node).start
        self.transformations.append(
            Transformation(
                self.filename,
                position.line,
                position.column + 1,
                symbol,
                "review the mechanical rewrite in its behavioral slice",
                kind,
                replacement,
            )
        )

    def leave_Import(
        self, original_node: cst.Import, updated_node: cst.Import
    ) -> cst.Import:
        changed = False
        names: list[cst.ImportAlias] = []
        for original_alias, updated_alias in zip(original_node.names, updated_node.names):
            module = _dotted_name(original_alias.name)
            replacement = _replace_root(module, self.manifest)
            if replacement != module:
                changed = True
                updated_alias = updated_alias.with_changes(
                    name=cst.parse_expression(replacement)
                )
                self._record(
                    original_alias,
                    kind="binding-import",
                    symbol=module,
                    replacement=replacement,
                )
            names.append(updated_alias)
        return updated_node.with_changes(names=names) if changed else updated_node

    def leave_SimpleStatementLine(
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> cst.BaseStatement | cst.FlattenSentinel[cst.BaseStatement]:
        if len(original_node.body) != 1 or not isinstance(
            original_node.body[0], cst.ImportFrom
        ):
            return updated_node
        original_import = original_node.body[0]
        if isinstance(original_import.names, cst.ImportStar):
            return updated_node
        module = _dotted_name(original_import.module)
        if module != self.manifest.binding_from and not module.startswith(
            f"{self.manifest.binding_from}."
        ):
            return updated_node

        groups: dict[str, list[cst.ImportAlias]] = {}
        records: list[tuple[cst.ImportAlias, str, str, str]] = []
        for alias in original_import.names:
            source = f"{module}.{_dotted_name(alias.name)}"
            target = self.manifest.moved_classes.get(source)
            if target is not None:
                destination, _, target_name = target.rpartition(".")
                replacement_alias = alias.with_changes(name=cst.Name(target_name))
                kind = "moved-class-import"
                replacement = target
            else:
                destination = _replace_root(module, self.manifest)
                replacement_alias = alias
                kind = "binding-import"
                replacement = f"{destination}.{_dotted_name(alias.name)}"
            groups.setdefault(destination, []).append(replacement_alias)
            records.append((alias, kind, source, replacement))

        for alias, kind, source, replacement in records:
            self._record(
                alias, kind=kind, symbol=source, replacement=replacement
            )

        if len(groups) == 1:
            destination, aliases = next(iter(groups.items()))
            preserved = original_import.with_changes(
                module=cst.parse_expression(destination),
                names=tuple(aliases),
            )
            return updated_node.with_changes(body=(preserved,))

        statements: list[cst.SimpleStatementLine] = []
        for index, (destination, aliases) in enumerate(groups.items()):
            rendered = ", ".join(_alias_text(alias) for alias in aliases)
            parsed = cst.ensure_type(
                cst.parse_statement(f"from {destination} import {rendered}\n"),
                cst.SimpleStatementLine,
            )
            statements.append(
                parsed.with_changes(
                    leading_lines=original_node.leading_lines if index == 0 else (),
                    trailing_whitespace=(
                        original_node.trailing_whitespace
                        if index == len(groups) - 1
                        else parsed.trailing_whitespace
                    ),
                )
            )
        return cst.FlattenSentinel(statements)

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        qualified = _qualified_expression(original_node, self.bindings)
        class_replacement = _class_enum_replacement(qualified, self.manifest)
        if class_replacement is not None:
            expression: cst.BaseExpression = updated_node.value
            for part in class_replacement.split("."):
                expression = cst.Attribute(value=expression, attr=cst.Name(part))
            self._record(
                original_node,
                kind="class-scoped-enum",
                symbol=_dotted_name(original_node),
                replacement=_dotted_name(expression),
            )
            return expression
        if _qt_owner(original_node.value, self.bindings):
            replacement = self.manifest.scoped_enums.get(original_node.attr.value)
            if replacement is not None:
                expression: cst.BaseExpression = updated_node.value
                for part in replacement.split("."):
                    expression = cst.Attribute(value=expression, attr=cst.Name(part))
                self._record(
                    original_node,
                    kind="scoped-enum",
                    symbol=_dotted_name(original_node),
                    replacement=_dotted_name(expression),
                )
                return expression
        method = self.manifest.method_rewrites.get(original_node.attr.value)
        receiver = _qt_receiver_symbol(original_node.value, self.bindings)
        local = _dotted_name(original_node.value)
        if method is not None and (
            _is_qt_symbol(receiver) or local in self.instances.qt
        ):
            replacement_node = updated_node.with_changes(attr=cst.Name(method))
            self._record(
                original_node,
                kind="method",
                symbol=f"{receiver}.{original_node.attr.value}",
                replacement=f"{receiver}.{method}",
            )
            return replacement_node
        return updated_node


def _shadowing_diagnostics(
    source: str, filename: str, bindings: _ImportBindings
) -> tuple[Diagnostic, ...]:
    aliases = set(bindings.module_aliases) | bindings.qt_aliases
    if not aliases:
        return ()
    tree = ast.parse(source, filename=filename)
    diagnostics: list[Diagnostic] = []
    for node in ast.walk(tree):
        name: str | None = None
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            name = node.id
        elif isinstance(node, ast.arg):
            name = node.arg
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
        elif isinstance(node, ast.Import):
            for imported in node.names:
                local = imported.asname or imported.name.split(".", 1)[0]
                if local in aliases and not imported.name.startswith(_BINDINGS):
                    name = local
                    break
        elif isinstance(node, ast.ImportFrom) and node.module:
            if not node.module.startswith(_BINDINGS):
                for imported in node.names:
                    local = imported.asname or imported.name
                    if local in aliases:
                        name = local
                        break
        if name in aliases:
            diagnostics.append(
                Diagnostic(
                    filename,
                    getattr(node, "lineno", 1),
                    getattr(node, "col_offset", 0) + 1,
                    name,
                    "rename the shadowing or reassigned Qt import alias before migration",
                )
            )
    return tuple(
        sorted(diagnostics, key=lambda item: (item.line, item.column, item.symbol))
    )


def migrate_source(
    source: str,
    *,
    filename: str = "<memory>",
    manifest: MappingManifest | None = None,
) -> MigrationResult:
    """Return a formatting-preserving migration or refuse every ambiguous site."""

    manifest = manifest or load_mapping_manifest()
    if any(marker in source[:1500] for marker in _GENERATED_MARKERS):
        result = MigrationResult(
            filename,
            source,
            (),
            (
                Diagnostic(
                    filename,
                    1,
                    1,
                    "generated Qt Python",
                    "regenerate this module from its canonical .ui or .qrc input",
                ),
            ),
        )
        raise MigrationRefused(result)
    try:
        module = cst.parse_module(source)
    except cst.ParserSyntaxError as exc:
        result = MigrationResult(
            filename,
            source,
            (),
            (Diagnostic(filename, exc.raw_line, exc.raw_column, "invalid Python", str(exc)),),
        )
        raise MigrationRefused(result) from exc

    bindings = _ImportBindings()
    module.visit(bindings)
    instances = _build_instance_bindings(source, bindings)
    shadowing = _shadowing_diagnostics(source, filename, bindings)
    dynamic_refusals = tuple(
        Diagnostic(filename, item.line, item.column, item.symbol, item.action)
        for item in _dynamic_import_sites(source)
    )
    refusal_visitor = _RefusalVisitor(filename, manifest, bindings, instances)
    metadata.MetadataWrapper(module).visit(refusal_visitor)
    refusals = tuple(
        sorted(
            [*shadowing, *dynamic_refusals, *refusal_visitor.refusals],
            key=lambda item: (item.line, item.column, item.symbol),
        )
    )
    if refusals:
        raise MigrationRefused(MigrationResult(filename, source, (), refusals))

    transformer = _Qt6Transformer(filename, manifest, bindings, instances)
    transformed = metadata.MetadataWrapper(module).visit(transformer)
    return MigrationResult(
        filename,
        transformed.code,
        tuple(transformer.transformations),
        (),
    )


def _ast_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _ast_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Call):
        return _ast_name(node.func)
    return ""


def _scan_python(
    path: Path, relative: str, text: str, manifest: MappingManifest
) -> list[StrictFinding]:
    findings: list[StrictFinding] = []

    def add(node: ast.AST, rule: str, symbol: str, action: str) -> None:
        findings.append(
            StrictFinding(
                relative,
                getattr(node, "lineno", 1),
                getattr(node, "col_offset", 0) + 1,
                rule,
                symbol,
                action,
            )
        )

    try:
        tree = ast.parse(text, filename=relative)
    except SyntaxError as exc:
        return [
            StrictFinding(
                relative,
                exc.lineno or 1,
                exc.offset or 1,
                "syntax-error",
                "invalid Python",
                exc.msg,
            )
        ]
    qt_aliases: set[str] = set()
    module_aliases: dict[str, str] = {}
    if path.stem.lower() in {"qt_compat", "qt_binding", "qt_facade"}:
        findings.append(
            StrictFinding(
                relative,
                1,
                1,
                "binding-facade",
                path.name,
                "delete the facade and use direct PyQt6 imports",
            )
        )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                local = alias.asname or root
                module_aliases[local] = alias.name if alias.asname else root
                if root == "PyQt5":
                    add(node, "pyqt5-import", alias.name, "import directly from PyQt6")
                if root in _FACADE_ROOTS or _is_compatibility_path(alias.name):
                    add(node, "binding-facade", alias.name, "use direct PyQt6 imports")
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".", 1)[0]
            if root == "PyQt5":
                add(node, "pyqt5-import", node.module, "import directly from PyQt6")
            if root in _FACADE_ROOTS or _is_compatibility_path(node.module):
                add(node, "binding-facade", node.module, "use direct PyQt6 imports")
            for alias in node.names:
                local = alias.asname or alias.name
                module_aliases[local] = f"{node.module}.{alias.name}"
                if node.module in {"PyQt5.QtCore", "PyQt6.QtCore"} and alias.name == "Qt":
                    qt_aliases.add(local)
                qualified = f"{node.module}.{alias.name}"
                if not _is_compatibility_path(node.module) and _is_compatibility_path(qualified):
                    add(
                        node,
                        "binding-facade",
                        qualified,
                        "use direct native PyQt6 modules",
                    )
                removed_action = _removed_action(qualified, manifest)
                if removed_action is not None:
                    add(node, "removed-api", qualified, removed_action)
                moved_target = _moved_target(qualified, manifest)
                if moved_target is not None and qualified != moved_target:
                    add(
                        node,
                        "removed-api",
                        qualified,
                        f"import the class from {moved_target}",
                    )
                if node.module in {"PyQt5.uic", "PyQt6.uic"} and alias.name == "loadUi":
                    add(node, "runtime-form-loading", qualified, "generate canonical forms at build time")

    instances = _build_instance_bindings(text, module_aliases)
    scopes = {target.split(".", 1)[0] for target in manifest.scoped_enums.values()}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            owner = _ast_name(node.value)
            root, separator, remainder = owner.partition(".")
            resolved = module_aliases.get(root, root)
            if separator:
                resolved = f"{resolved}.{remainder}"
            is_qt = owner in qt_aliases or resolved in {
                "PyQt5.QtCore.Qt",
                "PyQt6.QtCore.Qt",
            }
            if is_qt and node.attr not in scopes:
                add(node, "short-enum", f"{owner}.{node.attr}", "use an explicit Qt6 enum scope")
            qualified = f"{resolved}.{node.attr}" if resolved else node.attr
            if _class_enum_replacement(qualified, manifest) is not None:
                add(
                    node,
                    "short-class-enum",
                    qualified,
                    "use the explicit native Qt6 class enum scope",
                )
            removed_action = _removed_action(qualified, manifest)
            if removed_action is not None:
                add(node, "removed-api", qualified, removed_action)
            moved_target = _moved_target(qualified, manifest)
            if moved_target is not None and qualified != moved_target:
                add(
                    node,
                    "removed-api",
                    qualified,
                    f"reference the class from {moved_target}",
                )
            if (
                node.attr in manifest.method_rewrites
                and (
                    _is_qt_symbol(resolved)
                    or owner in instances.qt
                    or owner not in instances.non_qt
                )
            ):
                if owner in instances.non_qt:
                    continue
                action = (
                    f"use {manifest.method_rewrites[node.attr]} on the verified Qt receiver"
                    if _is_qt_symbol(resolved) or owner in instances.qt
                    else "prove the receiver's Qt constructor assignment or migrate this exec_ call manually"
                )
                add(
                    node,
                    "removed-api",
                    qualified,
                    action,
                )
            if node.attr == "loadUi" and resolved in {"PyQt5.uic", "PyQt6.uic"}:
                add(node, "runtime-form-loading", f"{owner}.loadUi", "generate canonical forms at build time")
        elif isinstance(node, ast.Name) and node.id in _RESOURCE_NAMES:
            if isinstance(getattr(node, "ctx", None), ast.Store):
                add(node, "generated-python-resource", node.id, "compile and register a binary .rcc resource")

    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type != tokenize.COMMENT:
            continue
        for marker in _GENERATED_MARKERS:
            if marker in token.string:
                findings.append(
                    StrictFinding(
                        relative,
                        token.start[0],
                        token.start[1] + 1,
                        "stale-generator",
                        marker,
                        "regenerate from canonical Qt6 inputs outside version control",
                    )
                )
    for site in _dynamic_import_sites(text):
        findings.append(
            StrictFinding(
                relative,
                site.line,
                site.column,
                site.rule,
                site.symbol,
                site.action,
            )
        )
    return findings


def scan_paths(
    paths: Iterable[Path],
    *,
    root: Path = ROOT,
    manifest: MappingManifest | None = None,
) -> tuple[StrictFinding, ...]:
    """Scan active source and dependency inputs for forbidden Qt migration patterns."""

    manifest = manifest or load_mapping_manifest()
    findings: list[StrictFinding] = []
    for path in sorted((Path(item) for item in paths), key=lambda item: item.as_posix()):
        relative = path.resolve().relative_to(root.resolve()).as_posix()
        text = path.read_text(encoding="utf-8", errors="strict")
        if path.suffix == ".py":
            findings.extend(_scan_python(path, relative, text, manifest))
        elif path.suffix.lower() in {".toml", ".lock", ".txt", ".in"}:
            for line_number, line in enumerate(text.splitlines(), 1):
                if re.search(r"\bPyQt5(?:-Qt5|-sip)?\b", line, re.IGNORECASE):
                    findings.append(
                        StrictFinding(
                            relative,
                            line_number,
                            1,
                            "pyqt5-requirement",
                            line.strip(),
                            "remove the active PyQt5 dependency declaration",
                        )
                    )
                if re.search(r"\b(?:qtpy|PySide2|PySide6|Qt5Compat)\b", line, re.IGNORECASE):
                    findings.append(
                        StrictFinding(
                            relative,
                            line_number,
                            1,
                            "alternate-binding-requirement",
                            line.strip(),
                            "remove the alternate or compatibility Qt binding declaration",
                        )
                    )
    unique = {
        (item.file, item.line, item.column, item.rule, item.symbol): item
        for item in findings
    }
    return tuple(unique[key] for key in sorted(unique))


def _identity(path: Path) -> tuple[int, int, int, int, int]:
    details = path.stat(follow_symlinks=False)
    return (
        details.st_dev,
        details.st_ino,
        details.st_size,
        details.st_mtime_ns,
        stat.S_IMODE(details.st_mode),
    )


def _detect_encoding(payload: bytes) -> str:
    try:
        encoding, _lines = tokenize.detect_encoding(io.BytesIO(payload).readline)
    except SyntaxError as exc:
        raise MigrationTransactionError(f"cannot detect Python source encoding: {exc}") from exc
    return encoding


def prepare_file_migration(
    path: Path, *, manifest: MappingManifest | None = None
) -> FileMigration:
    """Plan one migration against an immutable byte and filesystem identity."""

    path = path.resolve(strict=False) if not path.is_symlink() else path.absolute()
    if path.is_symlink():
        raise MigrationTransactionError(f"refusing symbolic link migration target: {path}")
    if not path.is_file():
        raise MigrationTransactionError(f"migration target is not a regular file: {path}")
    before = _identity(path)
    source_bytes = path.read_bytes()
    after = _identity(path)
    if before != after or len(source_bytes) != after[2]:
        raise MigrationTransactionError(f"migration target changed while planning: {path}")
    encoding = _detect_encoding(source_bytes)
    try:
        source = source_bytes.decode(encoding)
    except UnicodeError as exc:
        raise MigrationTransactionError(f"cannot decode {path} as {encoding}: {exc}") from exc
    result = migrate_source(source, filename=path.as_posix(), manifest=manifest)
    try:
        target_bytes = result.code.encode(encoding)
    except UnicodeError as exc:
        raise MigrationTransactionError(f"cannot encode migrated {path} as {encoding}: {exc}") from exc
    return FileMigration(
        path=path,
        source_bytes=source_bytes,
        target_bytes=target_bytes,
        source_identity=after,
        mode=stat.S_IMODE(path.stat(follow_symlinks=False).st_mode),
        encoding=encoding,
        result=result,
    )


def _verify_plan_source(plan: FileMigration) -> None:
    if plan.path.is_symlink() or not plan.path.is_file():
        raise MigrationTransactionError(
            f"migration target changed after planning: {plan.path}"
        )
    if _identity(plan.path) != plan.source_identity or plan.path.read_bytes() != plan.source_bytes:
        raise MigrationTransactionError(
            f"migration target changed after planning: {plan.path}"
        )


def _temporary_payload(path: Path, role: str, payload: bytes, mode: int) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".rcms-qt6-{role}-", suffix=".tmp", dir=path.parent
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.chmod(temporary, mode)
            os.fsync(stream.fileno())
        return temporary
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise


def write_atomic_text(path: Path, content: str) -> None:
    """Atomically replace a UTF-8 report without following a target symlink."""

    path = path.absolute()
    if path.is_symlink():
        raise MigrationTransactionError(f"refusing symbolic link report target: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    if existed and not path.is_file():
        raise MigrationTransactionError(f"report target is not a regular file: {path}")
    identity = _identity(path) if existed else None
    original = path.read_bytes() if existed else None
    mode = stat.S_IMODE(path.stat().st_mode) if existed else 0o644
    temporary: Path | None = None
    backup: Path | None = None
    recovery_backup: Path | None = None
    replaced = False
    try:
        temporary = _temporary_payload(path, "report", content.encode("utf-8"), mode)
        if original is not None:
            backup = _temporary_payload(path, "backup", original, mode)
        if path.is_symlink() or path.exists() != existed:
            raise MigrationTransactionError(f"report target changed before replace: {path}")
        if existed and (
            _identity(path) != identity or path.read_bytes() != original
        ):
            raise MigrationTransactionError(f"report target changed before replace: {path}")
        os.replace(temporary, path)
        replaced = True
        _sync_directory(path.parent)
    except BaseException as exc:
        restoration_error: BaseException | None = None
        restored_content = False
        if replaced:
            try:
                if backup is not None:
                    os.replace(backup, path)
                else:
                    path.unlink()
                restored_content = True
                _sync_directory(path.parent)
            except BaseException as restore_exc:
                restoration_error = restore_exc
        detail = f"atomic report write failed for {path}: {exc}"
        if restoration_error is not None:
            if restored_content:
                detail += (
                    "; destination content restored but restoration durability failed: "
                    f"{restoration_error}"
                )
            else:
                if backup is not None and backup.exists():
                    recovery_backup = backup
                detail += (
                    "; restoration failed and destination may be mutated: "
                    f"{restoration_error}"
                )
                if recovery_backup is not None:
                    detail += f"; recovery backup retained at {recovery_backup}"
        raise MigrationTransactionError(detail) from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if backup is not None and backup != recovery_backup:
            backup.unlink(missing_ok=True)


def _sync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def apply_migration_transaction(plans: Sequence[FileMigration]) -> None:
    """Atomically replace all changed files, rolling back on a later failure."""

    changed = [plan for plan in plans if plan.source_bytes != plan.target_bytes]
    paths = [plan.path for plan in changed]
    if len(paths) != len(set(paths)):
        raise MigrationTransactionError("migration transaction contains duplicate paths")
    staged: dict[Path, Path] = {}
    backups: dict[Path, Path] = {}
    replaced: list[FileMigration] = []
    preserve_temporaries: set[Path] = set()
    try:
        for plan in changed:
            _verify_plan_source(plan)
            staged[plan.path] = _temporary_payload(
                plan.path, "stage", plan.target_bytes, plan.mode
            )
            backups[plan.path] = _temporary_payload(
                plan.path, "backup", plan.source_bytes, plan.mode
            )
        for plan in changed:
            _verify_plan_source(plan)
        for plan in changed:
            _verify_plan_source(plan)
            os.replace(staged[plan.path], plan.path)
            replaced.append(plan)
            _sync_directory(plan.path.parent)
    except BaseException as exc:
        rollback_errors: list[str] = []
        for plan in reversed(replaced):
            backup = backups.get(plan.path)
            if backup is None or not backup.exists():
                rollback_errors.append(f"missing rollback payload for {plan.path}")
                continue
            try:
                os.replace(backup, plan.path)
                _sync_directory(plan.path.parent)
            except OSError as rollback_error:
                rollback_errors.append(f"{plan.path}: {rollback_error}")
                preserve_temporaries.add(backup)
        detail = f"Qt6 migration transaction failed: {exc}"
        if rollback_errors:
            detail += "; rollback failures: " + "; ".join(rollback_errors)
        raise MigrationTransactionError(detail) from exc
    finally:
        for temporary in [*staged.values(), *backups.values()]:
            if temporary not in preserve_temporaries:
                temporary.unlink(missing_ok=True)


def report_findings(findings: Sequence[StrictFinding]) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "passed": not findings,
            "findings": [asdict(item) for item in findings],
        },
        indent=2,
        sort_keys=True,
    ) + "\n"


def findings_snapshot(findings: Sequence[StrictFinding]) -> dict[str, object]:
    """Return a compact cryptographic contract for a temporary migration backlog."""

    canonical = json.dumps(
        [asdict(item) for item in findings],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    counts: dict[str, int] = {}
    for item in findings:
        counts[item.rule] = counts.get(item.rule, 0) + 1
    return {
        "schema_version": 1,
        "purpose": "Exact strict-source migration state; any drift fails closed.",
        "finding_count": len(findings),
        "counts_by_rule": dict(sorted(counts.items())),
        "findings_sha256": hashlib.sha256(canonical).hexdigest(),
    }
