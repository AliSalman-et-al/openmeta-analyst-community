"""Focused contracts for the typed analysis request boundary."""

from __future__ import annotations

import pytest
from collections.abc import Mapping
from typing import TypedDict

import test_backend_compat

test_backend_compat.install()

from rc_metastudio.analysis_adapter import make_analysis_request


class RequestKwargs(TypedDict):
    data_type: str
    workflow: str | None
    method: str
    metric: str | None
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


def test_analysis_request_rejects_missing_metric() -> None:
    values = _request_kwargs()
    values["metric"] = None
    with pytest.raises(ValueError, match="metric must be a non-empty string"):
        make_analysis_request(**values)


def test_analysis_request_rejects_cross_family_metric() -> None:
    values = _request_kwargs()
    values["metric"] = "MD"
    with pytest.raises(ValueError, match="not valid for binary analysis"):
        make_analysis_request(**values)
