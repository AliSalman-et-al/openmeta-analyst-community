"""Fail-closed contracts for the remaining native Qt6 surface inventory."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from PyQt6 import QtGui


ROOT = Path(__file__).resolve().parents[3]


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inventory_validator = _load_script("validate_qt6_surface_inventory")
native_smoke = _load_script("native_remaining_surfaces_smoke")


def _write_bundle(root: Path) -> None:
    inventory = inventory_validator.load_and_validate()
    contracts = {
        item["id"]: item
        for item in inventory["surfaces"]
        if item["evidence"] == "remaining-native"
    }
    for scale in native_smoke.SCALE_FACTORS:
        image_dir = root / ("scale-%s" % native_smoke._scale_label(scale))
        image_dir.mkdir(parents=True)
        surfaces = {}
        for surface_id, contract in contracts.items():
            image_path = image_dir / (surface_id + ".png")
            image = QtGui.QImage(40, 30, QtGui.QImage.Format.Format_ARGB32)
            image.fill(QtGui.QColor("white"))
            image.setPixelColor(20, 15, QtGui.QColor("navy"))
            assert image.save(str(image_path), "PNG")
            payload = image_path.read_bytes()
            action_contract = native_smoke.ACTION_CONTRACTS[surface_id]
            actions = {
                "none": {"contract": "none", "not_applicable": True},
                "close": {
                    "close_visible_enabled": True,
                    "contract": "close",
                    "rejected_observed": True,
                },
                "accept-cancel": {
                    "accepted_observed": True,
                    "cancel_visible_enabled": True,
                    "contract": "accept-cancel",
                    "default_accept_visible_enabled": True,
                    "reject_nonmutation": True,
                    "rejected_observed": True,
                },
                "wizard-next-cancel": {
                    "cancel_visible_enabled": True,
                    "contract": "wizard-next-cancel",
                    "default_next_visible_enabled": True,
                    "next_transition_observed": True,
                    "reject_nonmutation": True,
                    "rejected_observed": True,
                },
            }[action_contract]
            focus = (
                {
                    "after_tab": None,
                    "after_tab_descendant": False,
                    "after_tab_focusable": False,
                    "applicable": False,
                    "attempts": None,
                    "focusable_count": 0,
                    "initial": None,
                    "initial_descendant": False,
                    "moved": False,
                }
                if action_contract == "none"
                else {
                    "after_tab": "secondControl",
                    "after_tab_descendant": True,
                    "after_tab_focusable": True,
                    "applicable": True,
                    "attempts": 1,
                    "focusable_count": 2,
                    "initial": "firstControl",
                    "initial_descendant": True,
                    "moved": True,
                }
            )
            surfaces[surface_id] = {
                "accessibility": True,
                "actions": actions,
                "application_owns_geometry": contract["geometry_owner"]
                in {"application", "application-first-use"},
                "archetype": contract["archetype"],
                "capture": {
                    "path": image_path.relative_to(root).as_posix(),
                    "pixel_size": [40, 30],
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size_bytes": len(payload),
                    "varied_pixels": True,
                },
                "close_semantics": True,
                "device_pixel_ratio": scale,
                "first_use_behavior": "content_preferred",
                "focus": focus,
                "geometry_owner": contract["geometry_owner"],
                "logical_frame": {"x": 10, "y": 20, "width": 100, "height": 80},
                "overflow": contract["overflow"],
                "physical_frame": {
                    "x": round(10 * scale),
                    "y": round(20 * scale),
                    "width": round(100 * scale),
                    "height": round(80 * scale),
                },
                "role": contract["role"],
                "screen_geometry": {"x": 0, "y": 0, "width": 1600, "height": 1000},
                "screen_clamped": True,
            }
        native_smoke._record_path(root, scale).write_text(
            json.dumps({"qpa": "windows", "scale_factor": scale, "surfaces": surfaces}),
            encoding="utf-8",
        )


def test_surface_inventory_matches_canonical_forms_factories_tests_and_document():
    payload = inventory_validator.load_and_validate()

    assert len(payload["forms"]) == 29
    assert inventory_validator.render_markdown(payload) == inventory_validator.DOCUMENT_PATH.read_text(
        encoding="utf-8"
    )


def test_surface_inventory_rejects_canonical_form_drift(tmp_path):
    payload = inventory_validator.load_and_validate()
    payload["forms"].pop("welcome_page.ui")
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="29 canonical forms"):
        inventory_validator.load_and_validate(path)


def test_surface_inventory_rejects_unmaintained_evidence_command(tmp_path):
    payload = inventory_validator.load_and_validate()
    payload["evidence"]["remaining-native"]["command"] = "python arbitrary.py"
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="allowed maintained invocation"):
        inventory_validator.load_and_validate(path)


def test_surface_inventory_rejects_extra_or_mistyped_evidence(tmp_path):
    payload = inventory_validator.load_and_validate()
    payload["evidence"]["unused-native"] = {
        "issue": True,
        "command": "uv run python scripts/native_analysis_smoke.py",
        "artifact": "unused",
    }
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="audited closed world"):
        inventory_validator.load_and_validate(path)


def test_surface_inventory_rejects_mistyped_evidence_field(tmp_path):
    payload = inventory_validator.load_and_validate()
    payload["evidence"]["remaining-native"]["issue"] = True
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid field types"):
        inventory_validator.load_and_validate(path)


def test_surface_inventory_rejects_unreferenced_surface(tmp_path):
    payload = inventory_validator.load_and_validate()
    payload["forms"]["about_legal.ui"] = ["main-wizard"]
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="every and only declared surface"):
        inventory_validator.load_and_validate(path)


def test_surface_inventory_rejects_generic_or_unknown_factory(tmp_path):
    payload = inventory_validator.load_and_validate()
    payload["surfaces"][0]["factory"] = "adaptive_window.py:AdaptiveWindowController"
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="audited runtime allowlist"):
        inventory_validator.load_and_validate(path)


def test_surface_inventory_rejects_wrong_top_level_type(monkeypatch):
    monkeypatch.setitem(
        inventory_validator.FACTORY_ALLOWLIST,
        "about_legal_dialog.py:AboutLegalDialog",
        "main-window",
    )

    with pytest.raises(ValueError, match="wrong top-level type"):
        inventory_validator.load_and_validate()


def test_native_remaining_surface_evidence_accepts_relocated_four_scale_bundle(tmp_path):
    _write_bundle(tmp_path)

    records = native_smoke.validate_evidence(tmp_path)

    assert [record["scale_factor"] for record in records] == list(native_smoke.SCALE_FACTORS)


def test_native_remaining_surface_evidence_rejects_hash_tampering(tmp_path):
    _write_bundle(tmp_path)
    record_path = native_smoke._record_path(tmp_path, 1.0)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["surfaces"]["about-legal"]["capture"]["sha256"] = "0" * 64
    record_path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="PNG hash drifted"):
        native_smoke.validate_evidence(tmp_path)


def test_native_remaining_surface_evidence_rejects_mismatched_scale_surface_path(
    tmp_path,
):
    _write_bundle(tmp_path)
    record_path = native_smoke._record_path(tmp_path, 1.0)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["surfaces"]["add-group"]["capture"]["path"] = (
        "scale-1.25/add-group.png"
    )
    record_path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="does not match its scale and surface"):
        native_smoke.validate_evidence(tmp_path)


def test_native_remaining_surface_evidence_rejects_duplicate_capture_path(tmp_path):
    _write_bundle(tmp_path)
    record_path = native_smoke._record_path(tmp_path, 1.0)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["surfaces"]["add-group"]["capture"] = dict(
        record["surfaces"]["about-legal"]["capture"]
    )
    record_path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="capture path is duplicated"):
        native_smoke.validate_evidence(tmp_path)


def test_native_remaining_surface_evidence_rejects_unobserved_behavior(tmp_path):
    _write_bundle(tmp_path)
    record_path = native_smoke._record_path(tmp_path, 1.0)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    surface = record["surfaces"]["add-group"]
    surface["actions"]["accepted_observed"] = False
    record_path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="action behavior was not observed"):
        native_smoke.validate_evidence(tmp_path)


def test_native_remaining_surface_evidence_rejects_unmoved_focus(tmp_path):
    _write_bundle(tmp_path)
    record_path = native_smoke._record_path(tmp_path, 1.0)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    focus = record["surfaces"]["add-group"]["focus"]
    focus["after_tab"] = focus["initial"]
    focus["moved"] = False
    record_path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="focus traversal was not observed"):
        native_smoke.validate_evidence(tmp_path)
