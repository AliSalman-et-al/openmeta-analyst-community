"""Command-line entry point for native macOS Qt6 feasibility evidence."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.qt6_macos_feasibility_impl import main


if __name__ == "__main__":
    raise SystemExit(main())

