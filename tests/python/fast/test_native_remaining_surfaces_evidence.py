# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Behavioral contracts for native Qt surface evidence."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from PyQt6 import QtCore, QtGui, QtWidgets


ROOT = Path(__file__).resolve().parents[3]


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts" / (name + ".py")
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


native_smoke = _load_script("native_remaining_surfaces_smoke")

EXPECTED_SURFACES = {
    "about-legal": (
        "close",
        "TRANSACTIONAL",
        "transactional",
        "application-first-use",
        "text-browser",
        "content_preferred",
    ),
    "change-covariate-type": (
        "accept-cancel",
        "TRANSACTIONAL",
        "transactional",
        "application-first-use",
        "bounded-table",
        "content_preferred",
    ),
    "edit-group-name": (
        "accept-cancel",
        "TRANSACTIONAL",
        "transactional",
        "application-first-use",
        "content-preferred",
        "content_preferred",
    ),
    "edit-covariate-name": (
        "accept-cancel",
        "TRANSACTIONAL",
        "transactional",
        "application-first-use",
        "content-preferred",
        "content_preferred",
    ),
    "main-wizard": (
        "wizard-next-cancel",
        "WORKFLOW",
        "workflow",
        "window-manager-after-first-show",
        "page-scroll-area",
        "content_preferred",
    ),
    "confidence-level": (
        "accept-cancel",
        "CONFIDENCE_LEVEL",
        "transactional",
        "application-first-use",
        "content-preferred",
        "content_preferred",
    ),
    "add-covariate": (
        "accept-cancel",
        "TRANSACTIONAL",
        "transactional",
        "application-first-use",
        "content-preferred",
        "content_preferred",
    ),
    "add-follow-up": (
        "accept-cancel",
        "TRANSACTIONAL",
        "transactional",
        "application-first-use",
        "content-preferred",
        "content_preferred",
    ),
    "add-group": (
        "accept-cancel",
        "TRANSACTIONAL",
        "transactional",
        "application-first-use",
        "content-preferred",
        "content_preferred",
    ),
    "add-outcome": (
        "accept-cancel",
        "TRANSACTIONAL",
        "transactional",
        "application-first-use",
        "content-preferred",
        "content_preferred",
    ),
    "add-study": (
        "accept-cancel",
        "TRANSACTIONAL",
        "transactional",
        "application-first-use",
        "content-preferred",
        "content_preferred",
    ),
    "import-progress": (
        "none",
        "TRANSIENT",
        "transient",
        "application",
        "content-preferred",
        "content_preferred",
    ),
    "shared-progress": (
        "none",
        "TRANSIENT",
        "transient",
        "application",
        "content-preferred",
        "content_preferred",
    ),
    "startup-splash": (
        "none",
        "TRANSIENT",
        "transient",
        "application",
        "screen-bounded-pixmap",
        "content_preferred",
    ),
}


def test_layout_contract_rules_cover_each_distinct_surface_behavior():
    assert set(native_smoke.ACTION_CONTRACTS) == set(EXPECTED_SURFACES)
    for surface_id, (action, *layout) in EXPECTED_SURFACES.items():
        assert native_smoke.ACTION_CONTRACTS[surface_id] == action
        assert native_smoke._expected_layout_contract(surface_id) == tuple(layout)


def _write_bundle(root: Path) -> None:
    contracts = {}
    for surface_id, expected in EXPECTED_SURFACES.items():
        action, role, archetype, geometry_owner, overflow, first_use_behavior = expected
        contracts[surface_id] = {
            "action": action,
            "archetype": archetype,
            "first_use_behavior": first_use_behavior,
            "geometry_owner": geometry_owner,
            "overflow": overflow,
            "role": role,
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
            action_contract = contract["action"]
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
                    "focusables": [],
                    "initial": None,
                    "initial_descendant": False,
                    "moved": False,
                    "steps": [],
                    "traversed": [],
                }
                if action_contract == "none"
                else {
                    "after_tab": "secondControl",
                    "after_tab_descendant": True,
                    "after_tab_focusable": True,
                    "applicable": True,
                    "attempts": 1,
                    "focusable_count": 2,
                    "focusables": ["firstControl", "secondControl"],
                    "initial": "firstControl",
                    "initial_descendant": True,
                    "moved": True,
                    "steps": [
                        {
                            "direction": "forward",
                            "focus": "secondControl",
                            "kind": "key-event",
                            "returned": None,
                        }
                    ],
                    "traversed": ["firstControl", "secondControl"],
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
                "first_use_behavior": contract["first_use_behavior"],
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
            json.dumps(
                {
                    "qpa": "windows",
                    "scale_factor": scale,
                    "surfaces": surfaces,
                    "tab_focus_behavior": "TabFocusAllControls",
                }
            ),
            encoding="utf-8",
        )


def test_native_remaining_surface_evidence_accepts_relocated_scale_bundle(
    tmp_path,
):
    _write_bundle(tmp_path)

    records = native_smoke.validate_evidence(tmp_path)

    assert [record["scale_factor"] for record in records] == list(
        native_smoke.SCALE_FACTORS
    )


def test_native_remaining_surface_evidence_accepts_cocoa_focus_sequences(tmp_path):
    _write_bundle(tmp_path)
    for scale in native_smoke.SCALE_FACTORS:
        record_path = native_smoke._record_path(tmp_path, scale)
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["qpa"] = "cocoa"
        record_path.write_text(json.dumps(record), encoding="utf-8")

    records = native_smoke.validate_evidence(tmp_path)

    assert {record["qpa"] for record in records} == {"cocoa"}


def test_native_remaining_surface_evidence_rejects_semantic_layout_drift(tmp_path):
    _write_bundle(tmp_path)
    for scale in native_smoke.SCALE_FACTORS:
        record_path = native_smoke._record_path(tmp_path, scale)
        record = json.loads(record_path.read_text(encoding="utf-8"))
        surface = record["surfaces"]["add-covariate"]
        surface.update(
            {
                "archetype": "bogus",
                "first_use_behavior": "bogus",
                "geometry_owner": "bogus",
                "overflow": "bogus",
                "role": "bogus",
            }
        )
        record_path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="layout contract drifted"):
        native_smoke.validate_evidence(tmp_path)


def test_focus_observer_does_not_accept_programmatic_fallback_after_consumed_tab(qapp):
    class TabConsumingDialog(QtWidgets.QDialog):
        def event(  # ty: ignore[invalid-method-override] - PyQt6 test-double stub mismatch.
            self, event: QtCore.QEvent | None
        ) -> bool:
            if (
                isinstance(event, QtGui.QKeyEvent)
                and event.type()
                in {
                    QtCore.QEvent.Type.KeyPress,
                    QtCore.QEvent.Type.KeyRelease,
                }
                and event.key() in {QtCore.Qt.Key.Key_Tab, QtCore.Qt.Key.Key_Backtab}
            ):
                event.accept()
                return True
            return super().event(event)

    dialog = TabConsumingDialog()
    layout = QtWidgets.QVBoxLayout(dialog)
    first = QtWidgets.QLineEdit(dialog)
    first.setObjectName("firstControl")
    second = QtWidgets.QPushButton("Second", dialog)
    second.setObjectName("secondControl")
    layout.addWidget(first)
    layout.addWidget(second)
    dialog.show()
    qapp.processEvents()
    try:
        observation = native_smoke._observe_focus_traversal(
            qapp, dialog
        )
    finally:
        dialog.close()
        qapp.processEvents()

    assert observation["moved"] is False
    assert set(observation["traversed"]) == {"firstControl"}
    assert {step["kind"] for step in observation["steps"]} == {"key-event"}


def test_wizard_action_observer_uses_fresh_factory_choice_timing_and_return(qapp):
    from rc_metastudio.qt6_ui import prepare_generated_ui_imports

    prepare_generated_ui_imports()
    from rc_metastudio import main_wizard

    actions = native_smoke._observe_actions(
        qapp,
        lambda: main_wizard.MainWizard(path="new_dataset"),
        "main-wizard",
    )

    assert actions == {
        "cancel_visible_enabled": True,
        "contract": "wizard-next-cancel",
        "default_next_visible_enabled": True,
        "next_transition_observed": True,
        "reject_nonmutation": True,
        "rejected_observed": True,
    }
    assert native_smoke._surface_capture_order()[0] == "main-wizard"
    assert set(native_smoke._surface_capture_order()) == set(
        native_smoke._remaining_surface_ids()
    )


def test_native_remaining_surface_evidence_rejects_programmatic_focus_movement(
    tmp_path,
):
    _write_bundle(tmp_path)
    record_path = native_smoke._record_path(tmp_path, 1.0)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    focus = record["surfaces"]["add-covariate"]["focus"]
    focus["steps"][0]["kind"] = "focus-next-prev-child"
    focus["steps"][0]["returned"] = True
    record_path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="focus traversal step drifted"):
        native_smoke.validate_evidence(tmp_path)


def test_native_remaining_surface_evidence_rejects_direction_tampering(tmp_path):
    _write_bundle(tmp_path)
    record_path = native_smoke._record_path(tmp_path, 1.0)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    focus = record["surfaces"]["add-covariate"]["focus"]
    focus["steps"][0]["direction"] = "backward"
    record_path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="focus traversal step drifted"):
        native_smoke.validate_evidence(tmp_path)


def test_native_remaining_surface_evidence_rejects_restricted_tab_focus(tmp_path):
    _write_bundle(tmp_path)
    record_path = native_smoke._record_path(tmp_path, 1.0)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["qpa"] = "cocoa"
    record["tab_focus_behavior"] = "TabFocusTextControls"
    record_path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="lacks all-control keyboard navigation"):
        native_smoke.validate_evidence(tmp_path)


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
    record["surfaces"]["add-group"]["capture"]["path"] = "scale-1.5/add-group.png"
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


@pytest.mark.parametrize(
    "invalid",
    [[], ["firstControl", ""], ["firstControl"], ["firstControl", "globalControl"]],
)
def test_native_remaining_surface_evidence_rejects_invalid_focus_sequence(
    tmp_path, invalid
):
    _write_bundle(tmp_path)
    record_path = native_smoke._record_path(tmp_path, 1.0)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["qpa"] = "cocoa"
    record["surfaces"]["about-legal"]["focus"]["traversed"] = invalid
    record_path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="focus traversal was not observed"):
        native_smoke.validate_evidence(tmp_path)
