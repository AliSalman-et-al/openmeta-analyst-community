"""Local boundary doubles for Python application tests.

The real R bridge is exercised by ``tests/r_stack``.  Application tests inject
only the narrow calls they need so importing the GUI does not silently replace
the production bridge for every test process.
"""

from __future__ import annotations

import pytest

from rc_metastudio import r_bridge
from rc_metastudio.r_backend import AnalysisBackendUnavailableError
from rc_metastudio.study_effect_shapes import (
    effect_triplet,
    normalize_diagnostic_effects,
    normalize_effect_result,
)


def _unavailable(*_args: object, **_kwargs: object) -> None:
    raise AnalysisBackendUnavailableError("R test double has no operation")


def _scale(value: object, *_args: object, **_kwargs: object) -> object:
    return value


def _effect(*_args: object, **_kwargs: object) -> dict[str, tuple[float, float, float]]:
    return {"calc_scale": (1.0, 0.5, 1.5)}


def _diagnostic_effects(
    *_args: object, metrics: tuple[str, ...] = ("Spec", "Sens"), **_kwargs: object
) -> dict[str, dict[str, tuple[float, float, float]]]:
    return {metric: {"calc_scale": (1.0, 0.5, 1.5)} for metric in metrics}


def _confidence(_level: object) -> float:
    return 1.96


def _identity(value: object, *_args: object, **_kwargs: object) -> object:
    return value


class _TestObjects:
    @staticmethod
    def r(_expression: object) -> list[float]:
        return [95.0]


class _TestLoader:
    def load_meta(self) -> None:
        pass

    def load_metafor(self) -> None:
        pass

    def load_rcmetar(self) -> None:
        pass

    def load_grid(self) -> None:
        pass


@pytest.fixture
def inject_python_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject a local, explicit test capability at the R boundary."""
    functions = {
        "get_confidence_multiplier_from_r": _confidence,
        "set_confidence_level": lambda level: float(level),
        "get_r_library_paths": lambda: [],
        "get_r_version_string": lambda: None,
        "get_r_package_version": lambda _name: None,
        "reset_r_working_directory": lambda: None,
        "execute_r_string": lambda _expression: [95.0],
        "execute_r_function": lambda _name, *_args, **_kwargs: [95.0],
        "binary_convert_scale": _scale,
        "continuous_convert_scale": _scale,
        "diagnostic_convert_scale": _scale,
        "effect_for_study": _effect,
        "continuous_effect_for_study": _effect,
        "diagnostic_effects_for_study": _diagnostic_effects,
        "effect_triplet": effect_triplet,
        "normalize_effect_result": normalize_effect_result,
        "normalize_diagnostic_effects": normalize_diagnostic_effects,
        "impute_binary_data": lambda _data: {"FAIL": True},
        "impute_continuous_data": lambda _data, _alpha: {"succeeded": False},
        "impute_pre_post_continuous_data": lambda _data, _corr, _alpha: {
            "succeeded": False
        },
        "back_calculate_continuous_data": lambda *_args, **_kwargs: {"FAIL": True},
        "impute_diagnostic_data": lambda _data: {
            "TP": None,
            "TN": None,
            "FP": None,
            "FN": None,
        },
        "get_analysis_plot_capabilities": lambda *_args, **_kwargs: [],
        "dataset_to_simple_binary_r_object": _unavailable,
        "dataset_to_simple_continuous_r_object": _unavailable,
        "dataset_to_simple_diagnostic_r_object": _unavailable,
        "get_available_methods": _unavailable,
        "get_params": _unavailable,
        "get_method_description": _unavailable,
        "run_small_study_effects": _unavailable,
        "regenerate_small_study_effects_funnel": _unavailable,
        "generate_small_study_effects_funnel": _unavailable,
        "run_diagnostic_multi": _unavailable,
        "run_diagnostic_workflow": _unavailable,
        "run_versioned_analysis_request": lambda _request: {
            "version": 1,
            "texts": {},
            "images": {},
            "sections": [],
        },
        "run_versioned_analysis_requests": lambda _requests: {
            "version": 1,
            "texts": {},
            "images": {},
            "sections": [],
        },
    }
    for name, function in functions.items():
        monkeypatch.setattr(r_bridge, name, function, raising=False)
    monkeypatch.setattr(r_bridge, "ro", _TestObjects, raising=False)
    monkeypatch.setattr(r_bridge, "RLibraryLoader", _TestLoader, raising=False)


@pytest.fixture
def inject_calculator_boundary(
    inject_python_boundary: None,
) -> None:
    """Expose the canonical boundary to direct R-dependent test seams."""
    from rc_metastudio import (
        calculator_routines,
        dataset_table_model,
    )

    for module in (
        dataset_table_model,
        calculator_routines,
    ):
        module.r_bridge = r_bridge
