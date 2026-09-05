"""Maintained command-line entry point for the native Qt6 build slice."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.qt6_build_impl import main


if __name__ == "__main__":
    raise SystemExit(main())

