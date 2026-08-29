# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Focused contracts for the typed analysis request boundary."""

from __future__ import annotations

import pytest
from collections.abc import Mapping
from typing import TypedDict

from rc_metastudio import r_backend

r_backend.install_r_backend()

from rc_metastudio.analysis_adapter import make_analysis_request


class RequestKwargs(TypedDict):
    data_type: str
    workflow: str | None
    method: str
    metric: str
    parameters: Mapping[str, object]


def _request_kwargs() -> RequestKwargs:
    return {
        "data_type": "binary",
        "workflow": "standard",
        "method": "random",
        "metric": "OR",
        "parameters": {},
    }


@pytest.mark.parametrize("data_type", ["", "unknown", "Binary"])
def test_analysis_request_rejects_unknown_family(data_type: str) -> None:
    values = _request_kwargs()
    values["data_type"] = data_type
    with pytest.raises(ValueError, match="unsupported analysis data family"):
        make_analysis_request(**values)


def test_analysis_request_rejects_unknown_workflow() -> None:
    values = _request_kwargs()
    values["workflow"] = "unknown"
    with pytest.raises(ValueError, match="unsupported analysis workflow"):
        make_analysis_request(**values)


def test_analysis_request_rejects_empty_metric() -> None:
    values = _request_kwargs()
    values["metric"] = ""
    with pytest.raises(ValueError, match="metric must be a non-empty string"):
        make_analysis_request(**values)


def test_analysis_request_rejects_cross_family_metric() -> None:
    values = _request_kwargs()
    values["metric"] = "MD"
    with pytest.raises(ValueError, match="not valid for binary analysis"):
        make_analysis_request(**values)


def test_diagnostic_metric_conversion_failure_does_not_discard_other_metrics(
    monkeypatch,
):
    from rc_metastudio import analysis_adapter
    from rc_metastudio.analysis_errors import DiagnosticExecutionError

    def convert_metric(_model, metric):
        if metric == "Sens":
            raise DiagnosticExecutionError("Sens conversion failed")

    monkeypatch.setattr(
        analysis_adapter.r_bridge,
        "dataset_to_simple_diagnostic_r_object",
        convert_metric,
    )
    monkeypatch.setattr(
        analysis_adapter,
        "_run_diagnostic_backend",
        lambda _workflow, _methods, parameter_values: {
            "texts": {"Spec Summary": parameter_values[0]["measure"]},
            "images": {},
        },
    )
    requests = tuple(
        make_analysis_request(
            data_type="diagnostic",
            workflow="standard",
            method="diagnostic.random",
            metric=metric,
            parameters={"measure": metric},
        )
        for metric in ("Sens", "Spec")
    )
    model = type(
        "Model",
        (),
        {
            "included_studies_have_raw_data": lambda self: False,
            "included_studies_have_point_estimates": lambda self, effect: True,
        },
    )()

    result = analysis_adapter.execute_analysis_requests(model, requests)

    assert result["texts"] == {
        "Sens Error": "Sens conversion failed",
        "Spec Summary": "Spec",
    }
