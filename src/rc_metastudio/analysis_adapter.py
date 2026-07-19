# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Typed, Qt-independent requests at the Analysis Adapter boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, TypeAlias


AnalysisValue: TypeAlias = bool | int | float | str | None


@dataclass(frozen=True)
class AnalysisParameter:
    """One normalized value passed to the R analysis boundary."""

    name: str
    value: AnalysisValue


@dataclass(frozen=True)
class AnalysisRequest:
    """A complete, locale-independent analysis invocation."""

    data_type: str
    workflow: str
    method: str
    metric: str | None
    parameters: tuple[AnalysisParameter, ...]

    def parameter_values(self) -> dict[str, AnalysisValue]:
        return {parameter.name: parameter.value for parameter in self.parameters}


def make_analysis_request(
    *,
    data_type: str,
    workflow: str | None,
    method: str,
    metric: str | None,
    parameters: Mapping[str, object],
) -> AnalysisRequest:
    """Validate and freeze values selected by a user-facing configuration."""

    normalized_data_type = _required_text("data type", data_type)
    normalized_method = _required_text("analysis method", method)
    normalized_workflow = _required_text("workflow", workflow or "standard")
    normalized_metric = None if metric is None else _required_text("metric", metric)
    normalized_parameters = tuple(
        AnalysisParameter(_required_text("parameter name", name), _native_value(value))
        for name, value in sorted(parameters.items())
    )
    return AnalysisRequest(
        data_type=normalized_data_type,
        workflow=normalized_workflow,
        method=normalized_method,
        metric=normalized_metric,
        parameters=normalized_parameters,
    )


def _required_text(label: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _native_value(value: object) -> AnalysisValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise TypeError(
        "analysis parameters must be native bool, int, float, str, or None values; "
        f"received {type(value).__name__}"
    )
