"""Command entry point for RC MetaStudio."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_transitional_source_path() -> None:
    src_root = Path(__file__).resolve().parents[1]
    src_root_text = str(src_root)
    if src_root_text not in sys.path:
        sys.path.insert(0, src_root_text)


def main() -> int:
    _ensure_transitional_source_path()
    import launch

    return launch.start() or 0


if __name__ == "__main__":
    raise SystemExit(main())
