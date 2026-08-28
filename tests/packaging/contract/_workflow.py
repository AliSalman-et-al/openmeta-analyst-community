"""Small helpers for reading GitHub Actions workflow topology."""

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]


def load_workflow(*parts: str) -> dict[str, Any]:
    """Load a workflow, normalizing PyYAML's YAML 1.1 boolean ``on`` key."""

    workflow = yaml.safe_load(ROOT.joinpath(*parts).read_text(encoding="utf-8"))
    if True in workflow and "on" not in workflow:
        workflow["on"] = workflow.pop(True)
    return workflow
