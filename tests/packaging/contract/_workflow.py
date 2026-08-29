# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Small helpers for reading GitHub Actions workflow topology."""

from importlib import util
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]


def load_workflow(*parts: str) -> dict[str, Any]:
    """Load a workflow, normalizing PyYAML's YAML 1.1 boolean ``on`` key."""

    workflow = yaml.safe_load(ROOT.joinpath(*parts).read_text(encoding="utf-8"))
    if True in workflow and "on" not in workflow:
        workflow["on"] = workflow.pop(True)
    return workflow


def load_module_from_path(name: str, path: Path) -> ModuleType:
    """Load a Python module from a file after validating its import spec."""

    spec = util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module {name!r} from {path}")
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
