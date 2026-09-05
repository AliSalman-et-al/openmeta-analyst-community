# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Small helpers for reading GitHub Actions workflow topology."""

from importlib import util
from pathlib import Path
from types import ModuleType
from collections.abc import Iterator
from typing import Protocol, TypeAlias, cast

import yaml


ROOT = Path(__file__).resolve().parents[3]
YamlValue: TypeAlias = None | bool | int | float | str | list["YamlValue"] | dict[str, "YamlValue"]


class WorkflowNode(Protocol):
    def __getitem__(self, key: str | int) -> "WorkflowNode": ...

    def get(
        self, key: str, default: object = None
    ) -> "WorkflowNode": ...

    def __iter__(self) -> Iterator["WorkflowNode"]: ...

    def __len__(self) -> int: ...

    def __contains__(self, value: object) -> bool: ...

    def __add__(self, other: "WorkflowNode") -> "WorkflowNode": ...


def load_workflow(*parts: str) -> WorkflowNode:
    """Load a workflow, normalizing PyYAML's YAML 1.1 boolean ``on`` key."""

    loaded = yaml.safe_load(ROOT.joinpath(*parts).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("workflow must contain a mapping")
    if True in loaded and "on" not in loaded:
        loaded["on"] = loaded.pop(True)
    workflow = _narrow_yaml(loaded)
    if not isinstance(workflow, dict):
        raise ValueError("workflow must contain a mapping")
    return cast(WorkflowNode, workflow)


def _narrow_yaml(value: object) -> YamlValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_narrow_yaml(item) for item in value]
    if isinstance(value, dict):
        result: dict[str, YamlValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("workflow keys must be strings")
            result[key] = _narrow_yaml(item)
        return result
    raise ValueError("workflow contains an unsupported value")


def load_module_from_path(name: str, path: Path) -> ModuleType:
    """Load a Python module from a file after validating its import spec."""

    spec = util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module {name!r} from {path}")
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
