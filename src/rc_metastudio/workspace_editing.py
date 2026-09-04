# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qt-free editing operations for the dataset workspace.

The table model owns Qt roles, indexes, and presentation.  This module owns
the backend boundary used while an edit is being validated or previewed.
Keeping that boundary here also gives non-Qt callers a small, testable way to
calculate the same raw-data preview as the table.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from statistics import NormalDist
from typing import Protocol

from rc_metastudio import r_backend, r_bridge
from rc_metastudio.dataset_analysis_domain import (
    ScaleBridge,
    calculate_raw_effects,
    make_display_scale_converter,
    to_calculation_scale,
)
from rc_metastudio.meta_globals import validate_confidence_level


@dataclass(frozen=True, slots=True)
class ConfidenceSettings:
    """Validated confidence level and multiplier used by one edit session."""

    level: float
    multiplier: float


class _InclusionTarget(Protocol):
    include: bool
    manually_excluded: bool


class WorkspaceEditingService:
    """Perform backend-facing edit work without importing Qt.

    ``bridge`` is injectable for deterministic tests and for applications that
    provide another analysis backend.  The default remains the production
    RCMetaR bridge, preserving the existing statistical contract.
    """

    def __init__(self, bridge: ScaleBridge | None = None) -> None:
        self.bridge = r_bridge if bridge is None else bridge

    @staticmethod
    def update_inclusion_after_edit(
        study: _InclusionTarget,
        *,
        diagnostic: bool,
        inclusion_column: bool,
        outcome_selected: bool,
        effect: Mapping[str, object],
        data_type: object,
        outcome_subtype: str | None,
    ) -> None:
        """Apply the durable inclusion rule after a successful cell edit."""
        if diagnostic or inclusion_column or not outcome_selected:
            return
        if not study.manually_excluded:
            study.include = True
        required = (
            ("est", "SE")
            if data_type == "continuous" and outcome_subtype == "generic_effect"
            else ("upper", "lower", "est")
        )
        if any(effect[key] is None for key in required):
            study.include = False

    def confidence_settings(self, level: object) -> ConfidenceSettings:
        validated = validate_confidence_level(level)
        if r_backend.is_backend_installed():
            multiplier = self.bridge.get_confidence_multiplier_from_r(validated)
        else:
            tail = (1.0 + validated / 100.0) / 2.0
            multiplier = NormalDist().inv_cdf(tail)
        return ConfidenceSettings(float(validated), float(multiplier))

    def set_backend_confidence_level(self, level: float) -> None:
        if r_backend.is_backend_installed():
            self.bridge.set_confidence_level(level)

    def preview_raw_effects(
        self,
        data_type: object,
        effect: str | None,
        raw_data: tuple[object, ...] | list[object],
        confidence_level: float,
    ):
        """Calculate raw effects for a candidate edit."""
        return calculate_raw_effects(
            self.bridge, data_type, effect, raw_data, confidence_level
        )

    def to_calculation_scale(
        self,
        value: object,
        data_type: object,
        effect: str | None,
        n1: object = None,
    ):
        return to_calculation_scale(self.bridge, value, data_type, effect, n1)

    def display_scale_converter(
        self,
        data_type: object,
        effect: str | None,
        n1: object = None,
    ):
        return make_display_scale_converter(self.bridge, data_type, effect, n1)
