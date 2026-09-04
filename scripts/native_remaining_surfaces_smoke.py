"""Capture and validate the remaining native Qt6 top-level surfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from collections.abc import Callable, Collection
from pathlib import Path, PurePosixPath
from typing import Protocol, TypeAlias, TypeGuard


SCALE_FACTORS = (1.0, 1.5)
TOLERANCE = 0.02
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE_ROOT = ROOT / "build/qt6-verification/native-remaining-surfaces"
os.environ.setdefault("RCMS_QT6_BUILD_ROOT", str(ROOT / "build/qt6-verification"))

from PyQt6 import QtCore, QtGui, QtWidgets

ACTION_CONTRACTS = {
    "about-legal": "close",
    "change-covariate-type": "accept-cancel",
    "edit-group-name": "accept-cancel",
    "edit-covariate-name": "accept-cancel",
    "main-wizard": "wizard-next-cancel",
    "confidence-level": "accept-cancel",
    "add-covariate": "accept-cancel",
    "add-follow-up": "accept-cancel",
    "add-group": "accept-cancel",
    "add-outcome": "accept-cancel",
    "add-study": "accept-cancel",
    "import-progress": "none",
    "shared-progress": "none",
    "startup-splash": "none",
}

TRANSIENT_SURFACES = frozenset({"import-progress", "shared-progress", "startup-splash"})
SPECIAL_OVERFLOW = {
    "about-legal": "text-browser",
    "change-covariate-type": "bounded-table",
    "main-wizard": "page-scroll-area",
    "startup-splash": "screen-bounded-pixmap",
}

SurfaceFactory: TypeAlias = Callable[[], QtWidgets.QWidget]


class _ZeroArgumentFactory(Protocol):
    def __call__(self) -> object: ...


def _is_zero_argument_factory(value: object) -> TypeGuard[_ZeroArgumentFactory]:
    return callable(value)


def _slug(scale: float) -> str:
    return str(scale).replace(".", "_")


def _scale_label(scale: float) -> str:
    labels = {1.0: "1.0", 1.5: "1.5"}
    try:
        return labels[scale]
    except KeyError as exc:
        raise ValueError("scale is not a canonical remaining-surface factor") from exc


def _capture_relative_path(scale: float, surface_id: str) -> PurePosixPath:
    return PurePosixPath("scale-%s" % _scale_label(scale), surface_id + ".png")


def _record_path(root: Path, scale: float) -> Path:
    return root / ("scale-%s.json" % _slug(scale))


def _surface_record_path(root: Path, scale: float, surface_id: str) -> Path:
    return root / ".surface-records" / ("scale-%s-%s.json" % (_slug(scale), surface_id))


def _surface_capture_order() -> tuple[str, ...]:
    surfaces = _remaining_surface_ids()
    if "main-wizard" not in surfaces:
        raise RuntimeError("remaining-surface inventory has no Main Wizard")
    return ("main-wizard", *sorted(surfaces - {"main-wizard"}))


def _qt_message_handler(
    message_type: QtCore.QtMsgType,
    context: QtCore.QMessageLogContext,
    message: str | None,
) -> None:
    """Keep native Qt diagnostics visible even when a warning is fatal."""
    location = ""
    if context.file:
        location = " (%s:%s)" % (context.file, context.line)
    payload = "Qt %s%s: %s\n" % (message_type.name, location, message or "")
    os.write(2, payload.encode("utf-8", errors="backslashreplace"))


def _rect(rect: QtCore.QRect) -> dict[str, int]:
    return {
        "x": rect.x(),
        "y": rect.y(),
        "width": rect.width(),
        "height": rect.height(),
    }


def _has_variation(image: QtGui.QImage) -> bool:
    converted = image.convertToFormat(image.Format.Format_ARGB32)
    if converted.isNull():
        return False
    first = converted.pixel(0, 0)
    x_step = max(1, converted.width() // 32)
    y_step = max(1, converted.height() // 32)
    return any(
        converted.pixel(x, y) != first
        for y in range(0, converted.height(), y_step)
        for x in range(0, converted.width(), x_step)
    )


def _remaining_surface_ids() -> set[str]:
    return set(ACTION_CONTRACTS)


def _expected_layout_contract(surface_id: str) -> tuple[str, str, str, str, str]:
    """Return the durable layout semantics for one captured surface."""
    if surface_id not in ACTION_CONTRACTS:
        raise ValueError("unknown remaining native surface: %s" % surface_id)
    if surface_id in TRANSIENT_SURFACES:
        role, archetype, owner = "TRANSIENT", "transient", "application"
    elif surface_id == "main-wizard":
        role, archetype, owner = (
            "WORKFLOW",
            "workflow",
            "window-manager-after-first-show",
        )
    else:
        role = (
            "CONFIDENCE_LEVEL" if surface_id == "confidence-level" else "TRANSACTIONAL"
        )
        archetype, owner = "transactional", "application-first-use"
    overflow = SPECIAL_OVERFLOW.get(surface_id, "content-preferred")
    return role, archetype, owner, overflow, "content_preferred"


def _canonical_member(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("remaining-surface evidence path is not canonical")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or "." in relative.parts
        or ".." in relative.parts
        or any(":" in part for part in relative.parts)
        or relative.suffix.lower() != ".png"
    ):
        raise ValueError("remaining-surface evidence path is not canonical")
    result = (root / Path(*relative.parts)).resolve()
    if not result.is_relative_to(root.resolve()) or not result.is_file():
        raise ValueError("remaining-surface evidence image is missing")
    return result


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("remaining-surface evidence %s is not finite" % label)
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("remaining-surface evidence %s is not finite" % label)
    return result


def _object_dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("remaining-surface evidence %s is malformed" % label)
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError("remaining-surface evidence %s has a non-text key" % label)
        result[key] = item
    return result


def _validated_integral_fields(
    mapping: dict[str, object], label: str
) -> dict[str, int]:
    result: dict[str, int] = {}
    for key, item in mapping.items():
        if type(item) is not int:
            raise ValueError("remaining-surface evidence %s is not integral" % label)
        result[key] = item
    return result


def _validated_rect(value: object, label: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError("remaining-surface evidence %s is malformed" % label)
    mapping = _object_dict(value, label)
    required = {"x", "y", "width", "height"}
    if set(mapping) != required:
        raise ValueError("remaining-surface evidence %s is not integral" % label)
    result = _validated_integral_fields(mapping, label)
    if result["width"] < 1 or result["height"] < 1:
        raise ValueError("remaining-surface evidence %s is empty" % label)
    return result


def validate_evidence(root: Path = DEFAULT_EVIDENCE_ROOT) -> list[dict[str, object]]:
    """Validate relocated native evidence at standard and fractional scale."""
    from PyQt6 import QtGui

    expected_ids = _remaining_surface_ids()
    records = []
    seen_capture_paths: set[str] = set()
    for scale in SCALE_FACTORS:
        record = json.loads(_record_path(root, scale).read_text(encoding="utf-8"))
        if set(record) != {
            "qpa",
            "scale_factor",
            "surfaces",
            "tab_focus_behavior",
        }:
            raise ValueError("remaining-surface evidence record fields drifted")
        qpa = record["qpa"]
        if qpa not in {"windows", "cocoa"}:
            raise ValueError("remaining-surface evidence is not native hosted Qt")
        if record["tab_focus_behavior"] != "TabFocusAllControls":
            raise ValueError(
                "remaining-surface evidence lacks all-control keyboard navigation"
            )
        if abs(_number(record["scale_factor"], "scale") - scale) > TOLERANCE:
            raise ValueError("remaining-surface evidence scale does not match")
        surfaces = record["surfaces"]
        if not isinstance(surfaces, dict) or set(surfaces) != expected_ids:
            raise ValueError("remaining-surface evidence inventory is incomplete")
        for surface_id, surface in surfaces.items():
            required = {
                "accessibility",
                "actions",
                "application_owns_geometry",
                "archetype",
                "capture",
                "close_semantics",
                "device_pixel_ratio",
                "first_use_behavior",
                "focus",
                "geometry_owner",
                "logical_frame",
                "overflow",
                "physical_frame",
                "screen_geometry",
                "screen_clamped",
                "role",
            }
            if not isinstance(surface, dict) or set(surface) != required:
                raise ValueError("remaining-surface %s fields drifted" % surface_id)
            if surface["accessibility"] is not True:
                raise ValueError(
                    "remaining-surface %s accessibility failed" % surface_id
                )
            _validate_focus_observation(surface_id, surface["focus"])
            _validate_action_observation(surface_id, surface["actions"])
            if surface["close_semantics"] is not True:
                raise ValueError(
                    "remaining-surface %s did not close cleanly" % surface_id
                )
            if surface["screen_clamped"] is not True:
                raise ValueError("remaining-surface %s escaped its screen" % surface_id)
            contract = tuple(
                surface[field]
                for field in (
                    "role",
                    "archetype",
                    "geometry_owner",
                    "overflow",
                    "first_use_behavior",
                )
            )
            if any(not isinstance(value, str) or not value for value in contract):
                raise ValueError(
                    "remaining-surface %s layout contract is malformed" % surface_id
                )
            if contract != _expected_layout_contract(surface_id):
                raise ValueError(
                    "remaining-surface %s layout contract drifted" % surface_id
                )
            expected_application_owner = surface["geometry_owner"] in {
                "application",
                "application-first-use",
            }
            if surface["application_owns_geometry"] is not expected_application_owner:
                raise ValueError(
                    "remaining-surface %s geometry policy drifted" % surface_id
                )
            expected_first_use = {
                "EDIT_DATASET": "screen_fraction",
                "MAIN": "maximized",
                "RESULTS": "maximized",
            }.get(surface["role"], "content_preferred")
            if surface["first_use_behavior"] != expected_first_use:
                raise ValueError(
                    "remaining-surface %s first-use behavior drifted" % surface_id
                )
            dpr = _number(surface["device_pixel_ratio"], "device pixel ratio")
            if abs(dpr - scale) > TOLERANCE:
                raise ValueError("remaining-surface %s DPR does not match" % surface_id)
            logical = _validated_rect(surface["logical_frame"], "logical frame")
            physical = _validated_rect(surface["physical_frame"], "physical frame")
            screen = _validated_rect(surface["screen_geometry"], "screen geometry")
            if not (
                screen["x"] <= logical["x"]
                and screen["y"] <= logical["y"]
                and logical["x"] + logical["width"] <= screen["x"] + screen["width"]
                and logical["y"] + logical["height"] <= screen["y"] + screen["height"]
            ):
                raise ValueError(
                    "remaining-surface %s logical frame escaped" % surface_id
                )
            for dimension in ("width", "height"):
                if abs(physical[dimension] - round(logical[dimension] * dpr)) > 2:
                    raise ValueError(
                        "remaining-surface %s physical frame drifted" % surface_id
                    )
            if (
                abs(physical["x"] - round((logical["x"] - screen["x"]) * dpr)) > 2
                or abs(physical["y"] - round((logical["y"] - screen["y"]) * dpr)) > 2
            ):
                raise ValueError(
                    "remaining-surface %s physical origin drifted" % surface_id
                )
            capture = surface["capture"]
            if not isinstance(capture, dict) or set(capture) != {
                "path",
                "pixel_size",
                "sha256",
                "size_bytes",
                "varied_pixels",
            }:
                raise ValueError(
                    "remaining-surface %s capture fields drifted" % surface_id
                )
            expected_relative = _capture_relative_path(scale, surface_id).as_posix()
            capture_path = capture["path"]
            if isinstance(capture_path, str) and capture_path in seen_capture_paths:
                raise ValueError(
                    "remaining-surface evidence capture path is duplicated"
                )
            if capture_path != expected_relative:
                raise ValueError(
                    "remaining-surface %s capture path does not match its scale and surface"
                    % surface_id
                )
            seen_capture_paths.add(expected_relative)
            path = _canonical_member(root, capture["path"])
            payload = path.read_bytes()
            image = QtGui.QImage(str(path), "PNG")
            if not payload.startswith(b"\x89PNG\r\n\x1a\n") or image.isNull():
                raise ValueError("remaining-surface %s PNG is invalid" % surface_id)
            if capture["sha256"] != hashlib.sha256(payload).hexdigest():
                raise ValueError("remaining-surface %s PNG hash drifted" % surface_id)
            if capture["size_bytes"] != len(payload):
                raise ValueError("remaining-surface %s PNG size drifted" % surface_id)
            if capture["pixel_size"] != [image.width(), image.height()]:
                raise ValueError(
                    "remaining-surface %s PNG dimensions drifted" % surface_id
                )
            if capture["varied_pixels"] is not True or not _has_variation(image):
                raise ValueError("remaining-surface %s PNG is blank" % surface_id)
        records.append(record)
    if len(seen_capture_paths) != len(SCALE_FACTORS) * len(expected_ids):
        raise ValueError("remaining-surface evidence capture count is incomplete")
    return records


_FOCUS_FIELDS = frozenset(
    {
        "after_tab",
        "after_tab_descendant",
        "after_tab_focusable",
        "applicable",
        "attempts",
        "focusable_count",
        "focusables",
        "initial",
        "initial_descendant",
        "moved",
        "steps",
        "traversed",
    }
)
_FOCUS_EXEMPT_SURFACES = frozenset(
    {"import-progress", "shared-progress", "startup-splash"}
)


def _focus_failure(surface_id: str) -> ValueError:
    return ValueError(
        "remaining-surface %s focus traversal was not observed" % surface_id
    )


def _require_focus_values(
    surface_id: str,
    focus: dict[str, object],
    keys: tuple[str, ...],
    expected: object,
) -> None:
    for key in keys:
        if focus[key] != expected:
            raise ValueError("remaining-surface %s focus exemption is malformed" % surface_id)


def _validate_focus_exemption(surface_id: str, focus: dict[str, object]) -> None:
    if surface_id not in _FOCUS_EXEMPT_SURFACES:
        raise ValueError(
            "remaining-surface %s unexpectedly lacks focus traversal" % surface_id
        )
    _require_focus_values(
        surface_id, focus, ("after_tab", "attempts", "initial"), None
    )
    _require_focus_values(
        surface_id,
        focus,
        ("after_tab_descendant", "after_tab_focusable", "initial_descendant", "moved"),
        False,
    )
    _require_focus_values(surface_id, focus, ("focusable_count",), 0)
    _require_focus_values(surface_id, focus, ("focusables", "steps", "traversed"), [])


def _focus_strings(
    focus: dict[str, object], key: str, surface_id: str
) -> list[str]:
    value = focus[key]
    if not isinstance(value, list):
        raise _focus_failure(surface_id)
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise _focus_failure(surface_id)
        result.append(item)
    return result


def _focus_objects(focus: dict[str, object], key: str, surface_id: str) -> list[object]:
    value = focus[key]
    if not isinstance(value, list):
        raise _focus_failure(surface_id)
    result: list[object] = []
    result.extend(value)
    return result


def _focus_text(focus: dict[str, object], key: str, surface_id: str) -> str:
    value = focus[key]
    if not isinstance(value, str) or not value:
        raise _focus_failure(surface_id)
    return value


def _focus_count(focus: dict[str, object], key: str, surface_id: str) -> int:
    value = focus[key]
    if type(value) is not int or value < 1:
        raise _focus_failure(surface_id)
    return value


def _require_focus_true(focus: dict[str, object], key: str, surface_id: str) -> None:
    if focus[key] is not True:
        raise _focus_failure(surface_id)


def _validate_focus_summary(
    surface_id: str,
    focus: dict[str, object],
    focusables: list[str],
    traversed: list[str],
) -> int:
    initial = _focus_text(focus, "initial", surface_id)
    after_tab = _focus_text(focus, "after_tab", surface_id)
    if initial == after_tab:
        raise _focus_failure(surface_id)
    attempts = _focus_count(focus, "attempts", surface_id)
    count = _focus_count(focus, "focusable_count", surface_id)
    _validate_focus_counts(surface_id, count, attempts, focusables)
    _validate_focus_flags(surface_id, focus)
    _validate_focus_path(surface_id, initial, after_tab, attempts, focusables, traversed)
    return attempts


def _validate_focus_counts(
    surface_id: str, count: int, attempts: int, focusables: list[str]
) -> None:
    if count < 2 or len(focusables) != count:
        raise _focus_failure(surface_id)
    if len(set(focusables)) != count or attempts > count * 2:
        raise _focus_failure(surface_id)


def _validate_focus_flags(surface_id: str, focus: dict[str, object]) -> None:
    for key in ("initial_descendant", "after_tab_descendant", "after_tab_focusable", "moved"):
        _require_focus_true(focus, key, surface_id)


def _validate_focus_path(
    surface_id: str,
    initial: str,
    after_tab: str,
    attempts: int,
    focusables: list[str],
    traversed: list[str],
) -> None:
    if len(traversed) != attempts + 1:
        raise _focus_failure(surface_id)
    if traversed[0] != initial or traversed[-1] != after_tab:
        raise _focus_failure(surface_id)
    if any(item not in focusables for item in traversed):
        raise _focus_failure(surface_id)


def _validate_focus_step_fields(
    surface_id: str, step: dict[str, object], expected_direction: str
) -> None:
    if step["direction"] != expected_direction:
        raise ValueError("remaining-surface %s focus traversal step drifted" % surface_id)
    if step["kind"] != "key-event" or step["returned"] is not None:
        raise ValueError("remaining-surface %s focus traversal step drifted" % surface_id)


def _validate_focus_step_transition(
    surface_id: str,
    step: dict[str, object],
    index: int,
    steps: list[object],
    focusables: list[str],
    traversed: list[str],
) -> None:
    if step["focus"] != traversed[index + 1] or step["focus"] not in focusables:
        raise ValueError("remaining-surface %s focus traversal step drifted" % surface_id)
    if (step["focus"] != traversed[index]) != (index == len(steps) - 1):
        raise ValueError("remaining-surface %s key traversal protocol drifted" % surface_id)


def _validate_focus_step(
    surface_id: str,
    raw_step: object,
    index: int,
    steps: list[object],
    focusables: list[str],
    traversed: list[str],
) -> None:
    if not isinstance(raw_step, dict) or set(raw_step) != {
        "direction", "focus", "kind", "returned"
    }:
        raise ValueError("remaining-surface %s focus traversal step drifted" % surface_id)
    step = _object_dict(raw_step, "focus traversal step")
    expected_direction = "forward" if index % 2 == 0 else "backward"
    _validate_focus_step_fields(surface_id, step, expected_direction)
    _validate_focus_step_transition(
        surface_id, step, index, steps, focusables, traversed
    )


def _validate_focus_steps(
    surface_id: str,
    focus: dict[str, object],
    focusables: list[str],
    traversed: list[str],
    attempts: int,
) -> None:
    steps = _focus_objects(focus, "steps", surface_id)
    if len(steps) != attempts:
        raise _focus_failure(surface_id)
    for index, raw_step in enumerate(steps):
        _validate_focus_step(surface_id, raw_step, index, steps, focusables, traversed)


def _validate_focus_traversal(surface_id: str, focus: dict[str, object]) -> None:
    focusables = _focus_strings(focus, "focusables", surface_id)
    traversed = _focus_strings(focus, "traversed", surface_id)
    attempts = _validate_focus_summary(surface_id, focus, focusables, traversed)
    _validate_focus_steps(surface_id, focus, focusables, traversed, attempts)


def _validate_focus_observation(surface_id: str, observation: object) -> None:
    if not isinstance(observation, dict) or set(observation) != _FOCUS_FIELDS:
        raise ValueError("remaining-surface %s focus observation drifted" % surface_id)
    focus = _object_dict(observation, "focus observation")
    applicable = focus["applicable"]
    if applicable is False:
        _validate_focus_exemption(surface_id, focus)
        return
    if applicable is not True:
        raise ValueError("remaining-surface %s focus applicability is invalid" % surface_id)
    _validate_focus_traversal(surface_id, focus)


def _validate_action_observation(surface_id: str, observation: object) -> None:
    contract = ACTION_CONTRACTS[surface_id]
    if not isinstance(observation, dict):
        raise ValueError("remaining-surface %s action contract drifted" % surface_id)
    actions = _object_dict(observation, "action observation")
    if actions.get("contract") != contract:
        raise ValueError("remaining-surface %s action contract drifted" % surface_id)
    expected_fields = {
        "none": {"contract", "not_applicable"},
        "close": {"close_visible_enabled", "contract", "rejected_observed"},
        "accept-cancel": {
            "accepted_observed",
            "cancel_visible_enabled",
            "contract",
            "default_accept_visible_enabled",
            "reject_nonmutation",
            "rejected_observed",
        },
        "wizard-next-cancel": {
            "cancel_visible_enabled",
            "contract",
            "default_next_visible_enabled",
            "next_transition_observed",
            "reject_nonmutation",
            "rejected_observed",
        },
    }[contract]
    if set(actions) != expected_fields:
        raise ValueError("remaining-surface %s action fields drifted" % surface_id)
    for key, value in actions.items():
        if key != "contract" and value is not True:
            raise ValueError(
                "remaining-surface %s action behavior was not observed" % surface_id
            )


def _surface_factories() -> dict[str, SurfaceFactory]:
    from rc_metastudio import (
        about_legal_dialog,
        add_new_dialogs,
        covariate_type_dialog,
        confidence_level_dialog,
        edit_name_dialogs,
        launch,
        main_wizard,
        main_window,
        progress_dialog,
    )

    class PreviewModel(QtGui.QStandardItemModel):
        dataError = QtCore.pyqtSignal(str)

        def __init__(self, _dataset: object, _covariate: object) -> None:
            super().__init__(2, 3)

    setattr(covariate_type_dialog, "CovariateTypeModel", PreviewModel)

    def checked_factory(candidate: object, name: str) -> SurfaceFactory:
        if not _is_zero_argument_factory(candidate):
            raise RuntimeError("native surface %s factory is not callable" % name)

        def factory() -> QtWidgets.QWidget:
            result = candidate()
            if not isinstance(result, QtWidgets.QWidget):
                raise RuntimeError("native surface %s factory returned a non-widget" % name)
            return result

        return factory

    return {
        "about-legal": checked_factory(about_legal_dialog.AboutLegalDialog, "about-legal"),
        "change-covariate-type": checked_factory(
            lambda: covariate_type_dialog.CovariateTypeDialog(
            object(), object()
            ),
            "change-covariate-type",
        ),
        "edit-group-name": checked_factory(
            lambda: edit_name_dialogs.EditGroupNameDialog("Treatment group"),
            "edit-group-name",
        ),
        "edit-covariate-name": checked_factory(
            lambda: edit_name_dialogs.EditCovariateNameDialog("Baseline risk"),
            "edit-covariate-name",
        ),
        "main-wizard": checked_factory(
            lambda: main_wizard.MainWizard(path="new_dataset"), "main-wizard"
        ),
        "confidence-level": checked_factory(
            confidence_level_dialog.ConfidenceLevelDialog, "confidence-level"
        ),
        "add-covariate": checked_factory(add_new_dialogs.AddCovariateDialog, "add-covariate"),
        "add-follow-up": checked_factory(add_new_dialogs.AddFollowUpDialog, "add-follow-up"),
        "add-group": checked_factory(add_new_dialogs.AddGroupDialog, "add-group"),
        "add-outcome": checked_factory(add_new_dialogs.AddOutcomeDialog, "add-outcome"),
        "add-study": checked_factory(add_new_dialogs.AddStudyDialog, "add-study"),
        "import-progress": checked_factory(main_window.ImportProgressDialog, "import-progress"),
        "shared-progress": checked_factory(progress_dialog.AnalysisProgressDialog, "shared-progress"),
        "startup-splash": checked_factory(launch.create_startup_splash, "startup-splash"),
    }


def _capture(window: QtWidgets.QWidget, destination: Path, evidence_root: Path) -> dict[str, object]:
    # QWidget.grab() synchronously paints the real hosted widget without
    # depending on desktop/screen-recording permissions in macOS CI.
    pixmap = window.grab()
    if pixmap.isNull() or not _has_variation(pixmap.toImage()):
        raise RuntimeError("native capture is blank for %s" % window.objectName())
    if not pixmap.save(str(destination), "PNG"):
        raise RuntimeError("failed to save %s" % destination)
    payload = destination.read_bytes()
    return {
        "path": destination.relative_to(evidence_root).as_posix(),
        "pixel_size": [pixmap.width(), pixmap.height()],
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
        "varied_pixels": True,
    }


def _process_events(app: QtWidgets.QApplication) -> None:
    for _ in range(3):
        app.processEvents()


def _prepare_wizard(app: QtWidgets.QApplication, wizard: QtWidgets.QWizard) -> None:
    visible_choices = [
        button
        for button in wizard.findChildren(QtWidgets.QAbstractButton)
        if button.isVisible() and button.isEnabled() and button.isCheckable()
    ]
    if not visible_choices:
        raise RuntimeError("native wizard has no enabled data-type choice")
    visible_choices[0].click()
    _process_events(app)


def _show_and_prepare(
    app: QtWidgets.QApplication, window: QtWidgets.QWidget
) -> None:
    window.show()
    window.activateWindow()
    window.raise_()
    _process_events(app)
    if isinstance(window, QtWidgets.QWizard):
        _prepare_wizard(app, window)


def _widget_identity(window: QtWidgets.QWidget, widget: QtWidgets.QWidget | None) -> str:
    if widget is None or widget is window or not window.isAncestorOf(widget):
        return ""
    if widget.objectName():
        return widget.objectName()
    siblings = window.findChildren(type(widget))
    return "%s[%s]" % (type(widget).__name__, siblings.index(widget))


def _observe_focus_traversal(
    app: QtWidgets.QApplication,
    window: QtWidgets.QWidget,
    *_legacy_qt_modules: object,
) -> dict[str, object]:
    focusables = _focusable_widgets(window)
    if not focusables:
        return _no_focus_observation()
    window.raise_()
    window.activateWindow()
    focusables[0].setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    app.processEvents()
    initial_widget = app.focusWidget()
    focusable_identities = [_widget_identity(window, widget) for widget in focusables]
    initial = _widget_identity(window, initial_widget)
    current, after, attempts, steps, traversed = _walk_focus_traversal(
        app, window, initial_widget, focusables, initial
    )
    return {
        "after_tab": after or None,
        "after_tab_descendant": bool(after),
        "after_tab_focusable": current in focusables,
        "applicable": True,
        "attempts": attempts,
        "focusable_count": len(focusables),
        "focusables": focusable_identities,
        "initial": initial or None,
        "initial_descendant": bool(initial),
        "moved": bool(after) and current is not initial_widget,
        "steps": steps,
        "traversed": traversed,
    }


def _focusable_widgets(window: QtWidgets.QWidget) -> list[QtWidgets.QWidget]:
    tab_focus = QtCore.Qt.FocusPolicy.TabFocus
    return [
        widget
        for widget in window.findChildren(QtWidgets.QWidget)
        if widget.focusPolicy() & tab_focus
        and widget.isVisible()
        and widget.isEnabled()
    ]


def _no_focus_observation() -> dict[str, object]:
    return {
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


def _send_focus_key(
    app: QtWidgets.QApplication,
    window: QtWidgets.QWidget,
    key: QtCore.Qt.Key,
    modifiers: QtCore.Qt.KeyboardModifier,
) -> QtWidgets.QWidget | None:
    for event_type in (
        QtCore.QEvent.Type.KeyPress,
        QtCore.QEvent.Type.KeyRelease,
    ):
        event = QtGui.QKeyEvent(event_type, key, modifiers)
        # Deliver at the top-level surface so Cocoa cannot consume Tab in a
        # native child editor before QWidget's focus-chain handling sees it.
        QtCore.QCoreApplication.sendEvent(window, event)
    app.processEvents()
    return app.focusWidget()


def _walk_focus_traversal(
    app: QtWidgets.QApplication,
    window: QtWidgets.QWidget,
    initial_widget: QtWidgets.QWidget | None,
    focusables: list[QtWidgets.QWidget],
    initial: str,
) -> tuple[
    QtWidgets.QWidget | None,
    str,
    int,
    list[dict[str, object]],
    list[str],
]:
    current = initial_widget
    after = ""
    attempts = 0
    traversed = [initial] if initial else []
    steps: list[dict[str, object]] = []
    keys = (
        (QtCore.Qt.Key.Key_Tab, QtCore.Qt.KeyboardModifier.NoModifier),
        (QtCore.Qt.Key.Key_Backtab, QtCore.Qt.KeyboardModifier.ShiftModifier),
    )
    for attempts in range(1, len(focusables) * 2 + 1):
        key, modifiers = keys[(attempts - 1) % len(keys)]
        direction = "forward" if (attempts - 1) % len(keys) == 0 else "backward"
        current = _send_focus_key(app, window, key, modifiers)
        after = _widget_identity(window, current)
        traversed.append(after)
        steps.append(
            {
                "direction": direction,
                "focus": after,
                "kind": "key-event",
                "returned": None,
            }
        )
        if after and current is not initial_widget:
            break
    return current, after, attempts, steps, traversed


def _snapshot_edit_state(window: QtWidgets.QWidget) -> tuple[tuple[object, ...], ...]:
    editors = tuple(
        (editor.objectName(), editor.text())
        for editor in window.findChildren(QtWidgets.QLineEdit)
    )
    combos = tuple(
        (combo.objectName(), combo.currentIndex(), combo.currentText())
        for combo in window.findChildren(QtWidgets.QComboBox)
    )
    spins = tuple(
        (spin.objectName(), spin.value())
        for spin in window.findChildren(QtWidgets.QAbstractSpinBox)
        if isinstance(spin, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox))
    )
    views: list[tuple[str, int, int]] = []
    for view in window.findChildren(QtWidgets.QAbstractItemView):
        model = view.model()
        if model is not None:
            views.append((view.objectName(), model.rowCount(), model.columnCount()))
    return (editors, combos, spins, tuple(views))


def _delete_window(app: QtWidgets.QApplication, window: QtWidgets.QWidget) -> None:
    window.close()
    window.deleteLater()
    QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()


def _button_for_roles(
    box: QtWidgets.QDialogButtonBox,
    roles: Collection[QtWidgets.QDialogButtonBox.ButtonRole],
) -> QtWidgets.QAbstractButton | None:
    return next(
        (button for button in box.buttons() if box.buttonRole(button) in roles),
        None,
    )


def _dialog_box(dialog: QtWidgets.QDialog, label: str) -> QtWidgets.QDialogButtonBox:
    box = dialog.findChild(QtWidgets.QDialogButtonBox)
    if box is None:
        raise RuntimeError("%s surface has no button box" % label)
    return box


def _is_default_button(button: QtWidgets.QAbstractButton) -> bool:
    return isinstance(button, QtWidgets.QPushButton) and button.isDefault()


def _observe_close_action(
    app: QtWidgets.QApplication, factory: SurfaceFactory
) -> dict[str, object]:
    dialog = factory()
    if not isinstance(dialog, QtWidgets.QDialog):
        raise RuntimeError("close surface factory did not return a dialog")
    try:
        _show_and_prepare(app, dialog)
        close_button = _dialog_box(dialog, "close").button(
            QtWidgets.QDialogButtonBox.StandardButton.Close
        )
        if close_button is None:
            raise RuntimeError("close surface has no close action")
        rejected: list[bool] = []
        dialog.rejected.connect(lambda: rejected.append(True))
        visible_enabled = close_button.isVisible() and close_button.isEnabled()
        close_button.click()
        app.processEvents()
        return {
            "close_visible_enabled": visible_enabled,
            "contract": "close",
            "rejected_observed": rejected == [True] and not dialog.isVisible(),
        }
    finally:
        _delete_window(app, dialog)


def _observe_wizard_next(
    app: QtWidgets.QApplication, wizard: QtWidgets.QWizard
) -> tuple[bool, bool]:
    _show_and_prepare(app, wizard)
    next_button = wizard.button(QtWidgets.QWizard.WizardButton.NextButton)
    if next_button is None:
        raise RuntimeError("wizard surface has no next action")
    before_page = wizard.currentId()
    default_next = (
        next_button.isVisible()
        and next_button.isEnabled()
        and _is_default_button(next_button)
    )
    return_target = app.focusWidget()
    if return_target is None or not wizard.isAncestorOf(return_target):
        raise RuntimeError("native wizard Return target is not a descendant")
    for event_type in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.KeyRelease):
        QtCore.QCoreApplication.sendEvent(
            wizard,
            QtGui.QKeyEvent(
                event_type,
                QtCore.Qt.Key.Key_Return,
                QtCore.Qt.KeyboardModifier.NoModifier,
            ),
        )
    app.processEvents()
    return default_next, wizard.currentId() != before_page


def _observe_wizard_cancel(
    app: QtWidgets.QApplication, wizard: QtWidgets.QWizard, default_next: bool, transitioned: bool
) -> dict[str, object]:
    _show_and_prepare(app, wizard)
    cancel = wizard.button(QtWidgets.QWizard.WizardButton.CancelButton)
    if cancel is None:
        raise RuntimeError("wizard surface has no cancel action")
    rejected: list[bool] = []
    wizard.rejected.connect(lambda: rejected.append(True))
    before = _snapshot_edit_state(wizard)
    cancel_visible = cancel.isVisible() and cancel.isEnabled()
    cancel.click()
    app.processEvents()
    return {
        "cancel_visible_enabled": cancel_visible,
        "contract": "wizard-next-cancel",
        "default_next_visible_enabled": default_next,
        "next_transition_observed": transitioned,
        "reject_nonmutation": before == _snapshot_edit_state(wizard),
        "rejected_observed": rejected == [True] and not wizard.isVisible(),
    }


def _observe_wizard_actions(
    app: QtWidgets.QApplication, factory: SurfaceFactory
) -> dict[str, object]:
    wizard = factory()
    if not isinstance(wizard, QtWidgets.QWizard):
        raise RuntimeError("wizard surface factory did not return a wizard")
    try:
        default_next, transitioned = _observe_wizard_next(app, wizard)
    finally:
        _delete_window(app, wizard)
    reject_wizard = factory()
    if not isinstance(reject_wizard, QtWidgets.QWizard):
        raise RuntimeError("wizard surface factory did not return a wizard")
    try:
        return _observe_wizard_cancel(app, reject_wizard, default_next, transitioned)
    finally:
        _delete_window(app, reject_wizard)


def _observe_accept_action(
    app: QtWidgets.QApplication, factory: SurfaceFactory
) -> tuple[bool, bool]:
    accept_dialog = factory()
    if not isinstance(accept_dialog, QtWidgets.QDialog):
        raise RuntimeError("accept surface factory did not return a dialog")
    try:
        _show_and_prepare(app, accept_dialog)
        accept = _button_for_roles(
            _dialog_box(accept_dialog, "accept-cancel"),
            {
                QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole,
                QtWidgets.QDialogButtonBox.ButtonRole.YesRole,
            },
        )
        if not isinstance(accept, QtWidgets.QPushButton):
            raise RuntimeError("accept-cancel surface has no accept action")
        accepted: list[bool] = []
        accept_dialog.accepted.connect(lambda: accepted.append(True))
        default_accept = accept.isVisible() and accept.isEnabled() and accept.isDefault()
        accept.click()
        app.processEvents()
        accepted_observed = accepted == [True] and not accept_dialog.isVisible()
    finally:
        _delete_window(app, accept_dialog)
    return default_accept, accepted_observed


def _observe_cancel_action(
    app: QtWidgets.QApplication,
    factory: SurfaceFactory,
    accepted_observed: bool,
    default_accept: bool,
) -> dict[str, object]:
    reject_dialog = factory()
    if not isinstance(reject_dialog, QtWidgets.QDialog):
        raise RuntimeError("cancel surface factory did not return a dialog")
    try:
        _show_and_prepare(app, reject_dialog)
        cancel = _button_for_roles(
            _dialog_box(reject_dialog, "accept-cancel"),
            {
                QtWidgets.QDialogButtonBox.ButtonRole.NoRole,
                QtWidgets.QDialogButtonBox.ButtonRole.RejectRole,
            },
        )
        if not isinstance(cancel, QtWidgets.QPushButton):
            raise RuntimeError("accept-cancel surface has no cancel action")
        rejected: list[bool] = []
        reject_dialog.rejected.connect(lambda: rejected.append(True))
        before = _snapshot_edit_state(reject_dialog)
        cancel_visible = cancel.isVisible() and cancel.isEnabled()
        cancel.click()
        app.processEvents()
        return {
            "accepted_observed": accepted_observed,
            "cancel_visible_enabled": cancel_visible,
            "contract": "accept-cancel",
            "default_accept_visible_enabled": default_accept,
            "reject_nonmutation": before == _snapshot_edit_state(reject_dialog),
            "rejected_observed": rejected == [True] and not reject_dialog.isVisible(),
        }
    finally:
        _delete_window(app, reject_dialog)


def _observe_accept_cancel_actions(
    app: QtWidgets.QApplication, factory: SurfaceFactory
) -> dict[str, object]:
    default_accept, accepted_observed = _observe_accept_action(app, factory)
    return _observe_cancel_action(app, factory, accepted_observed, default_accept)


def _observe_actions(
    app: QtWidgets.QApplication,
    factory: SurfaceFactory,
    surface_id: str,
    *_legacy_qt_modules: object,
) -> dict[str, object]:
    contract = ACTION_CONTRACTS[surface_id]
    if contract == "none":
        return {"contract": contract, "not_applicable": True}
    if contract == "close":
        return _observe_close_action(app, factory)
    if contract == "wizard-next-cancel":
        return _observe_wizard_actions(app, factory)
    return _observe_accept_cancel_actions(app, factory)


def _has_visible_descendant(
    window: QtWidgets.QWidget,
    widget_type: type[QtWidgets.QWidget],
) -> bool:
    return any(view.isVisible() for view in window.findChildren(widget_type))


def _observe_overflow(window: QtWidgets.QWidget) -> str:
    if isinstance(window, QtWidgets.QSplashScreen):
        if window.pixmap().isNull():
            raise RuntimeError("splash overflow evidence has no pixmap")
        return "screen-bounded-pixmap"
    for widget_type, overflow in (
        (QtWidgets.QTextBrowser, "text-browser"),
        (QtWidgets.QTableView, "bounded-table"),
    ):
        if _has_visible_descendant(window, widget_type):
            return overflow
    visible_scrolls = _has_visible_descendant(window, QtWidgets.QScrollArea)
    if isinstance(window, QtWidgets.QWizard) and visible_scrolls:
        return "page-scroll-area"
    if not visible_scrolls:
        return "content-preferred"
    raise RuntimeError("remaining surface overflow behavior is not classified")


def _observe_window_contract(window: QtWidgets.QWidget) -> dict[str, object]:
    from rc_metastudio import adaptive_window

    controller = getattr(window, "_adaptive_window_controller", None)
    if not isinstance(controller, adaptive_window.AdaptiveWindowController):
        raise RuntimeError("remaining surface has no live adaptive controller")
    state = controller.state
    policy = state.policy
    if policy.application_owns_geometry:
        owner = (
            "application"
            if state.role is adaptive_window.WindowRole.TRANSIENT
            else "application-first-use"
        )
    else:
        owner = "window-manager-after-first-show"
    return {
        "application_owns_geometry": policy.application_owns_geometry,
        "archetype": policy.archetype.value,
        "first_use_behavior": policy.first_use_behavior.value,
        "geometry_owner": owner,
        "role": state.role.name,
    }


def _capture_surface(scale: float, evidence_root: Path, surface_id: str) -> None:
    from rc_metastudio.qt6_ui import prepare_generated_ui_imports

    prepare_generated_ui_imports()
    QtCore.qInstallMessageHandler(_qt_message_handler)
    from scripts.local_r_test_backend import create
    backend_fake = create()
    from rc_metastudio import r_bridge, qt6_resources
    for name, implementation in vars(backend_fake).items():
        setattr(r_bridge, name, implementation)
    qt6_resources.ensure_application_resources()
    from rc_metastudio import app_error_handler

    app = app_error_handler.get_or_create_application([])
    # Evidence failures must terminate the gate, never block behind the app's
    # interactive unexpected-error dialog.
    sys.excepthook = sys.__excepthook__
    if app.platformName() not in {"windows", "cocoa"}:
        raise RuntimeError("remaining-surface smoke requires qwindows or cocoa")
    tab_focus_behavior = app.styleHints().tabFocusBehavior().name
    if tab_focus_behavior != "TabFocusAllControls":
        raise RuntimeError(
            "remaining-surface smoke requires all-control keyboard navigation; got %s"
            % tab_focus_behavior
        )
    factories = _surface_factories()
    if set(factories) != _remaining_surface_ids():
        raise RuntimeError("native remaining-surface factory inventory drifted")
    if surface_id not in factories:
        raise ValueError("surface is not in the remaining-surface inventory")
    image_dir = evidence_root / ("scale-%s" % _scale_label(scale))
    image_dir.mkdir(parents=True, exist_ok=True)
    records = {}
    for surface_id, factory in [(surface_id, factories[surface_id])]:
        print("capturing %s at %s" % (surface_id, scale), flush=True)
        window = factory()
        try:
            _show_and_prepare(app, window)
            frame = window.frameGeometry()
            screen_object = window.screen()
            if screen_object is None:
                raise RuntimeError("remaining surface has no screen")
            screen = screen_object.availableGeometry()
            observed_contract = _observe_window_contract(window)
            observed_overflow = _observe_overflow(window)
            focus = _observe_focus_traversal(app, window)
            accessible = True
            for view in window.findChildren(QtWidgets.QAbstractItemView):
                if (
                    view.isVisible()
                    and not isinstance(view, QtWidgets.QHeaderView)
                    and not view.accessibleName().strip()
                ):
                    accessible = False
            for button in window.findChildren(QtWidgets.QAbstractButton):
                if (
                    button.isVisible()
                    and not button.icon().isNull()
                    and not button.text().strip()
                    and not button.accessibleName().strip()
                ):
                    accessible = False
            destination = image_dir / (surface_id + ".png")
            capture = _capture(window, destination, evidence_root)
            dpr = float(window.devicePixelRatioF())
            logical = _rect(frame)
            physical = {
                "x": round((frame.x() - screen.x()) * dpr),
                "y": round((frame.y() - screen.y()) * dpr),
                "width": round(frame.width() * dpr),
                "height": round(frame.height() * dpr),
            }
            window.close()
            app.processEvents()
            # Finish the capture instance before action probes construct their
            # own top-level windows. Keeping a captured QWizard alive while two
            # more MainWizard trees were created caused an intermittent Windows
            # native fast-fail (0xC0000409) despite each evidence surface already
            # having its own process.
            actions = _observe_actions(
                app, factory, surface_id
            )
            records[surface_id] = {
                "accessibility": accessible,
                "actions": actions,
                "application_owns_geometry": observed_contract[
                    "application_owns_geometry"
                ],
                "archetype": observed_contract["archetype"],
                "capture": capture,
                "close_semantics": not window.isVisible(),
                "device_pixel_ratio": dpr,
                "first_use_behavior": observed_contract["first_use_behavior"],
                "focus": focus,
                "geometry_owner": observed_contract["geometry_owner"],
                "logical_frame": logical,
                "overflow": observed_overflow,
                "physical_frame": physical,
                "role": observed_contract["role"],
                "screen_geometry": _rect(screen),
                "screen_clamped": screen.contains(frame),
            }
        finally:
            window.close()
            window.deleteLater()
            QtWidgets.QApplication.sendPostedEvents(
                None, QtCore.QEvent.Type.DeferredDelete
            )
            app.processEvents()
    record = {
        "qpa": app.platformName(),
        "scale_factor": scale,
        "surfaces": records,
        "tab_focus_behavior": tab_focus_behavior,
    }
    record_path = _surface_record_path(evidence_root, scale, surface_id)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _run_scale(scale: float, evidence_root: Path) -> None:
    environment = os.environ.copy()
    for surface_id in _surface_capture_order():
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--scale",
                str(scale),
                "--surface",
                surface_id,
                "--evidence-root",
                str(evidence_root),
            ],
            cwd=ROOT,
            env=environment,
            check=True,
        )
    fragments = [
        json.loads(
            _surface_record_path(evidence_root, scale, surface_id).read_text(
                encoding="utf-8"
            )
        )
        for surface_id in _surface_capture_order()
    ]
    if not fragments:
        raise RuntimeError("remaining-surface inventory is empty")
    common = {
        key: fragments[0][key] for key in ("qpa", "scale_factor", "tab_focus_behavior")
    }
    if any(
        any(fragment[key] != value for key, value in common.items())
        for fragment in fragments
    ):
        raise RuntimeError("isolated remaining-surface runtime identity drifted")
    surfaces = {}
    for fragment in fragments:
        if len(fragment["surfaces"]) != 1:
            raise RuntimeError("isolated remaining-surface record is not singular")
        surfaces.update(fragment["surfaces"])
    evidence_root.mkdir(parents=True, exist_ok=True)
    _record_path(evidence_root, scale).write_text(
        json.dumps({**common, "surfaces": surfaces}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for surface_id in _surface_capture_order():
        _surface_record_path(evidence_root, scale, surface_id).unlink()
    _surface_record_path(evidence_root, scale, "placeholder").parent.rmdir()


def _native_dpr() -> float:
    environment = os.environ.copy()
    environment.pop("QT_SCALE_FACTOR", None)
    environment.pop("QT_SCALE_FACTOR_ROUNDING_POLICY", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from PyQt6.QtWidgets import QApplication; app=QApplication([]); "
            "print(app.primaryScreen().devicePixelRatio())",
        ],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return float(completed.stdout.strip().splitlines()[-1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--scale", type=float)
    parser.add_argument("--surface")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        validate_evidence(args.evidence_root)
        return 0
    if args.scale is not None:
        if args.scale not in SCALE_FACTORS:
            raise ValueError("scale must be a required native evidence factor")
        if args.surface is not None:
            _capture_surface(args.scale, args.evidence_root, args.surface)
            return 0
        _run_scale(args.scale, args.evidence_root)
        return 0
    if args.surface is not None:
        raise ValueError("surface requires scale")
    native_dpr = _native_dpr()
    if native_dpr <= 0:
        raise RuntimeError("native Qt reported an invalid device pixel ratio")
    for scale in SCALE_FACTORS:
        environment = os.environ.copy()
        environment["QT_SCALE_FACTOR"] = str(scale / native_dpr)
        environment["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--scale",
                str(scale),
                "--evidence-root",
                str(args.evidence_root),
            ],
            cwd=ROOT,
            env=environment,
            check=True,
        )
    validate_evidence(args.evidence_root)
    print(
        "validated %s remaining native Qt6 surfaces at %s"
        % (len(_remaining_surface_ids()), ", ".join(map(str, SCALE_FACTORS)))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
