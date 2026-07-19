"""Command entry point for RC MetaStudio."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_transitional_source_path() -> None:
    package_root = Path(__file__).resolve().parent
    forms_root = package_root / "forms"
    for path in (package_root, forms_root):
        path_text = str(path)
        if path_text not in sys.path:
            sys.path.insert(0, path_text)


def main() -> int:
    _ensure_transitional_source_path()
    from rc_metastudio.qt6_ui import prepare_generated_ui_imports

    prepare_generated_ui_imports()
    import launch

    return launch.start() or 0


if __name__ == "__main__":
    raise SystemExit(main())
