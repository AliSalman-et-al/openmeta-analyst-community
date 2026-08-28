# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""List handwritten modules that use PyQt6."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def qt_modules(root: Path) -> list[Path]:
    """Return active Python files that import PyQt6."""
    root = root.resolve()
    paths: list[Path] = []
    for base in (root / "src/rc_metastudio", root / "scripts"):
        for path in base.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports_qt = any(
                (
                    isinstance(node, ast.Import)
                    and any(
                        alias.name.split(".", 1)[0] == "PyQt6" for alias in node.names
                    )
                )
                or (
                    isinstance(node, ast.ImportFrom)
                    and node.module is not None
                    and node.module.split(".", 1)[0] == "PyQt6"
                )
                for node in ast.walk(tree)
            )
            if imports_qt:
                paths.append(path)
    return sorted(paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    for path in qt_modules(args.root):
        print(path.relative_to(args.root.resolve()).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
