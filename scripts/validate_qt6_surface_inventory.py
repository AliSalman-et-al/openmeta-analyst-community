#!/usr/bin/env python3
"""Validate and render the authoritative Native Qt6 surface inventory."""

from __future__ import annotations

import argparse
import ast
import importlib
import inspect
import json
import os
from pathlib import Path
import re
import sys
from typing import Never, cast


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "docs/verification/native-qt6-surface-inventory.json"
DOCUMENT_PATH = ROOT / "docs/verification/native-qt6-remaining-surfaces.md"
os.environ.setdefault("RCMS_STUB_BACKEND", "1")
os.environ.setdefault("RCMS_QT6_BUILD_ROOT", str(ROOT / "build/qt6-verification"))

EVIDENCE_ALLOWLIST = {
    "shell-native": {
        "issue": 333,
        "command": "uv run rc-metastudio --automation-native-shell-smoke",
        "artifact": "native application-shell smoke",
    },
    "workspace-native": {
        "issue": 335,
        "command": "uv run pytest -W error tests/python/gui/test_main_workspace_window.py tests/python/gui/test_metaform_data_workflows.py",
        "artifact": "workspace GUI evidence",
    },
    "calculator-native": {
        "issue": 336,
        "command": "uv run python scripts/native_calculator_smoke.py",
        "artifact": "build/qt6-verification/native-calculators",
    },
    "analysis-native": {
        "issue": 337,
        "command": "uv run python scripts/native_analysis_smoke.py",
        "artifact": "build/qt6-verification/native-analysis",
    },
    "results-native": {
        "issue": 338,
        "command": "uv run python scripts/native_results_smoke.py",
        "artifact": "build/qt6-verification/native-results",
    },
    "remaining-native": {
        "issue": 339,
        "command": "uv run python scripts/native_remaining_surfaces_smoke.py",
        "artifact": "build/qt6-verification/native-remaining-surfaces",
    },
}

_DIALOG_FACTORIES = {
    "about_legal_dialog.py:AboutLegalDialog",
    "binary_data_form.py:BinaryDataForm2",
    "binary_data_form.py:ChooseBackCalcResultForm",
    "change_cov_type_form.py:ChangeCovTypeForm",
    "conf_level_dialog.py:ChangeConfLevelDlg",
    "continuous_data_form.py:ChooseBackCalcResultForm",
    "continuous_data_form.py:ContinuousDataForm",
    "diag_metrics.py:Diag_Metrics",
    "diagnostic_data_form.py:DiagnosticDataForm",
    "edit_dialog.py:EditDialog",
    "edit_group_name_form.py:EditCovariateName",
    "edit_group_name_form.py:EditGroupName",
    "ma_specs.py:MA_Specs",
    "ma_specs.py:MetaProgress",
    "meta_form.py:ImportProgress",
    "meta_reg_form.py:MetaRegForm",
    "meta_subgroup_form.py:MetaSubgroupForm",
    "network_view.py:ViewDialog",
    "progress_bar.py:MetaProgress",
    "results_window.py:EditPlotDialog",
    "add_new_dialogs.py:AddNewCovariateForm",
    "add_new_dialogs.py:AddNewFollowUpForm",
    "add_new_dialogs.py:AddNewGroupForm",
    "add_new_dialogs.py:AddNewOutcomeForm",
    "add_new_dialogs.py:AddNewStudyForm",
}
FACTORY_ALLOWLIST = {
    **{factory: "dialog" for factory in _DIALOG_FACTORIES},
    "main_wizard.py:MainWizard": "wizard",
    "meta_form.py:MetaForm": "main-window",
    "results_window.py:ResultsWindow": "main-window",
    "launch.py:create_startup_splash": "splash-factory",
}

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/rc_metastudio"))
sys.path.insert(0, str(ROOT / "scripts"))
from rc_metastudio.qt6_build import CANONICAL_FORMS  # noqa: E402
from audit_qt_layout_contracts import TOP_LEVEL_FORM_INVENTORY  # noqa: E402


def _fail(message: str) -> Never:
    raise ValueError(message)


def load_and_validate(path: Path = INVENTORY_PATH) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if set(payload) != {
        "schema_version",
        "scale_factors",
        "evidence",
        "forms",
        "handwritten_surfaces",
        "surfaces",
    }:
        _fail("surface inventory top-level fields drifted")
    if payload.get("schema_version") != 1:
        _fail("surface inventory schema_version must be 1")
    if payload.get("scale_factors") != [1.0, 1.25, 1.5, 1.75]:
        _fail("surface inventory must require exactly 1.0, 1.25, 1.5, and 1.75")

    canonical = {entry.name for entry in CANONICAL_FORMS}
    forms = payload.get("forms")
    if not isinstance(forms, dict) or set(forms) != canonical:
        _fail(
            "surface form set does not match the 29 canonical forms: "
            f"missing={sorted(canonical - set(forms or {}))}, "
            f"extra={sorted(set(forms or {}) - canonical)}"
        )
    for form_name, surface_ids in forms.items():
        if (
            not isinstance(form_name, str)
            or not isinstance(surface_ids, list)
            or not surface_ids
            or any(not isinstance(surface_id, str) for surface_id in surface_ids)
        ):
            _fail(f"canonical form registration is malformed: {form_name!r}")

    evidence = payload.get("evidence")
    surfaces = payload.get("surfaces")
    _validate_evidence_registry(evidence)
    if not isinstance(surfaces, list) or not surfaces:
        _fail("surface inventory has no surfaces")
    by_id = {}
    factory_tuples = {}
    for surface in surfaces:
        required = {
            "id",
            "form",
            "factory",
            "role",
            "archetype",
            "geometry_owner",
            "overflow",
            "evidence",
            "test",
        }
        if not isinstance(surface, dict) or set(surface) != required:
            _fail(f"surface entry has invalid fields: {surface!r}")
        surface_id = surface["id"]
        if (
            not isinstance(surface_id, str)
            or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", surface_id) is None
            or not isinstance(surface["factory"], str)
            or not isinstance(surface["role"], str)
            or not isinstance(surface["archetype"], str)
            or not isinstance(surface["geometry_owner"], str)
            or not isinstance(surface["overflow"], str)
            or not isinstance(surface["evidence"], str)
            or not isinstance(surface["test"], str)
            or (surface["form"] is not None and not isinstance(surface["form"], str))
        ):
            _fail(f"surface entry has invalid field types: {surface!r}")
        if surface_id in by_id:
            _fail(f"duplicate surface id: {surface_id}")
        by_id[surface_id] = surface
        if surface["evidence"] not in evidence:
            _fail(f"surface {surface_id} references unknown evidence")
        _validate_test_node(surface["test"])
        factory_ref = surface["factory"]
        source_name, separator, symbol = factory_ref.partition(":")
        if not separator:
            _fail(f"surface {surface_id} has an invalid factory")
        _validate_factory(factory_ref)
        factory_tuple = (source_name, symbol)
        if factory_tuple in factory_tuples:
            _fail(f"duplicate runtime factory mapping: {factory_ref}")
        factory_tuples[factory_tuple] = surface

    declared_factories = {surface["factory"] for surface in surfaces}
    if declared_factories != set(FACTORY_ALLOWLIST):
        _fail("surface factories must match the complete audited runtime allowlist")

    handwritten_surfaces = payload["handwritten_surfaces"]
    if handwritten_surfaces != ["main-wizard", "startup-splash"]:
        _fail("handwritten top-level surface registration drifted")
    referenced = {
        surface_id for values in forms.values() for surface_id in values
    } | set(handwritten_surfaces)
    if referenced != set(by_id):
        _fail(
            "form registrations must reference every and only declared surface: "
            f"missing={sorted(set(by_id) - referenced)}, "
            f"extra={sorted(referenced - set(by_id))}"
        )
    referenced_evidence = {surface["evidence"] for surface in surfaces}
    if referenced_evidence != set(evidence):
        _fail(
            "evidence registry must contain every and only referenced entry: "
            f"unreferenced={sorted(set(evidence) - referenced_evidence)}, "
            f"missing={sorted(referenced_evidence - set(evidence))}"
        )
    direct_forms = {
        surface["form"] for surface in surfaces if surface["form"] is not None
    }
    top_level_forms = set(TOP_LEVEL_FORM_INVENTORY)
    if direct_forms != top_level_forms:
        _fail(
            "direct surface forms do not match top-level form inventory: "
            f"missing={sorted(top_level_forms - direct_forms)}, "
            f"extra={sorted(direct_forms - top_level_forms)}"
        )
    for form_name, registrations in TOP_LEVEL_FORM_INVENTORY.items():
        expected_ids = set(forms[form_name])
        actual_ids = set()
        for source_name, symbol, role in registrations:
            surface = factory_tuples.get((source_name, symbol))
            if surface is None:
                _fail(f"missing runtime surface for {source_name}:{symbol}")
            if surface["form"] != form_name or surface["role"] != role:
                _fail(f"runtime mapping drifted for {source_name}:{symbol}")
            actual_ids.add(surface["id"])
        if actual_ids != expected_ids:
            _fail(
                f"form {form_name} runtime set drifted: "
                f"expected={sorted(expected_ids)}, actual={sorted(actual_ids)}"
            )
    for form_name in canonical - top_level_forms:
        if forms[form_name] != ["main-wizard"]:
            _fail(f"wizard page {form_name} must inherit main-wizard evidence")
    if {surface["id"] for surface in surfaces if surface["form"] is None} != {
        "main-wizard",
        "startup-splash",
    }:
        _fail("handwritten top-level surface set drifted")
    return payload


def _validate_test_node(node_id: object) -> None:
    if not isinstance(node_id, str) or "::" not in node_id:
        _fail(f"invalid executable test node: {node_id!r}")
    relative, function_name = node_id.split("::", 1)
    path = ROOT / relative
    if not path.is_file():
        _fail(f"surface test file does not exist: {relative}")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    if function_name not in names:
        _fail(f"surface test node does not exist: {node_id}")


def _validate_evidence_registry(evidence: object) -> None:
    if not isinstance(evidence, dict) or set(evidence) != set(EVIDENCE_ALLOWLIST):
        _fail("surface inventory evidence registry is not the audited closed world")
    registry = cast(dict[str, object], evidence)
    for name, expected in EVIDENCE_ALLOWLIST.items():
        entry = registry[name]
        if not isinstance(entry, dict) or set(entry) != {"issue", "command", "artifact"}:
            _fail(f"evidence {name} has invalid fields")
        fields = cast(dict[str, object], entry)
        if (
            type(fields["issue"]) is not int
            or not isinstance(fields["command"], str)
            or not isinstance(fields["artifact"], str)
        ):
            _fail(f"evidence {name} has invalid field types")
        if fields != expected:
            _fail(f"evidence {name} is not an allowed maintained invocation")
        command = fields["command"].split()
        if command[:3] == ["uv", "run", "python"]:
            script = ROOT / command[3]
            if not script.is_file() or script.suffix != ".py":
                _fail(f"evidence {name} script is not executable source")
        elif command[:4] == ["uv", "run", "pytest", "-W"]:
            for token in command[5:]:
                if not (ROOT / token).is_file():
                    _fail(f"evidence {name} test invocation references a missing file")
        elif command[:3] == ["uv", "run", "rc-metastudio"]:
            pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
            if "rc-metastudio =" not in pyproject:
                _fail("maintained rc-metastudio entry point is not declared")
        else:
            _fail(f"evidence {name} command is not an allowed executable invocation")


def _validate_factory(factory_ref: str) -> None:
    expected_type = FACTORY_ALLOWLIST.get(factory_ref)
    if expected_type is None:
        _fail(f"surface factory is not in the audited runtime allowlist: {factory_ref}")
    source_name, symbol = factory_ref.split(":", 1)
    path = ROOT / "src/rc_metastudio" / source_name
    if not path.is_file():
        _fail(f"surface factory source does not exist: {source_name}")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }
    if symbol not in names:
        _fail(f"surface factory does not exist: {source_name}:{symbol}")
    try:
        from PyQt6 import QtWidgets
        from rc_metastudio.qt6_ui import prepare_generated_ui_imports
        from rc_metastudio import meta_py_r_backend

        prepare_generated_ui_imports()
        meta_py_r_backend.install_stub_meta_py_r()
        module = importlib.import_module(source_name.removesuffix(".py"))
        target = getattr(module, symbol)
    except (ImportError, AttributeError, RuntimeError) as exc:
        _fail(f"surface factory is not importable: {factory_ref}: {exc}")
    expected_base = {
        "dialog": QtWidgets.QDialog,
        "wizard": QtWidgets.QWizard,
        "main-window": QtWidgets.QMainWindow,
    }.get(expected_type)
    if expected_base is not None:
        if not inspect.isclass(target) or not issubclass(target, expected_base):
            _fail(f"surface factory has the wrong top-level type: {factory_ref}")
    elif expected_type == "splash-factory":
        if (
            not inspect.isfunction(target)
            or inspect.signature(target).return_annotation
            is not QtWidgets.QSplashScreen
        ):
            _fail(f"surface splash factory has the wrong top-level type: {factory_ref}")
    else:
        _fail(f"surface factory type allowlist is invalid: {factory_ref}")


def render_markdown(payload: dict) -> str:
    evidence = payload["evidence"]
    surfaces = payload["surfaces"]
    lines = [
        "# Native Qt6 Surface Inventory",
        "",
        "This file is rendered from `native-qt6-surface-inventory.json`. The validator",
        "fails if this table, the exact 29 canonical forms, runtime factories, adaptive",
        "roles, executable tests, or evidence registry drift independently.",
        "",
        "Required native scale factors: `1.0`, `1.25`, `1.5`, and `1.75`.",
        "For these remaining surfaces, the four-factor native gate supersedes the",
        "older two-factor adaptive-layout capture scripts.",
        "Each retained capture has the closed-world path",
        "`scale-{factor}/{surface-id}.png`; all 60 paths must be unique.",
        "Focus, actions, geometry ownership, archetype, and overflow are observed",
        "from live Qt controls and adaptive controllers rather than copied metadata.",
        "",
        "| Surface | Canonical form | Contract | Native evidence |",
        "| --- | --- | --- | --- |",
    ]
    for surface in surfaces:
        native = evidence[surface["evidence"]]
        form = f"`{surface['form']}`" if surface["form"] else "handwritten"
        fields = {**surface, **native, "form": form}
        lines.append(
            "| `{id}` | {form} | `{archetype}` / `{role}`; `{geometry_owner}`; "
            "`{overflow}` | #{issue} `{artifact}` |".format(**fields)
        )
    lines.extend(
        [
            "",
            "Wizard page forms inherit the one `main-wizard` Workflow Window entry.",
            "All other canonical forms map exactly to the top-level registration audited",
            "by `audit_qt_layout_contracts.py`. The two handwritten top-level factories",
            "are `MainWizard` and the startup splash.",
            "Factories, executable test nodes, commands, and evidence ownership are",
            "validated directly from the machine-readable inventory.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=INVENTORY_PATH)
    parser.add_argument("--print-document", action="store_true")
    parser.add_argument("--check-document", action="store_true")
    args = parser.parse_args()
    payload = load_and_validate(args.inventory)
    rendered = render_markdown(payload)
    if args.print_document:
        print(rendered, end="")
    if args.check_document and DOCUMENT_PATH.read_text(encoding="utf-8") != rendered:
        _fail("rendered Native Qt6 surface document drifted from the manifest")
    print("validated Native Qt6 surface inventory", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
