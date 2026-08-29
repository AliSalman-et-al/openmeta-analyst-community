"""Command entry point for RC MetaStudio."""

from __future__ import annotations

def main() -> int:
    from rc_metastudio.qt6_ui import prepare_generated_ui_imports

    prepare_generated_ui_imports()
    from rc_metastudio import launch

    return launch.start() or 0


if __name__ == "__main__":
    raise SystemExit(main())
