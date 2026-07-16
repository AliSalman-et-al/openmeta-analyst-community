"""Bootstrap deterministic build-generated Qt6 form imports."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import os
from pathlib import Path
import sys

from rc_metastudio.qt6_build import CANONICAL_FORMS


BUILD_ROOT_ENV = "RCMS_QT6_BUILD_ROOT"


@dataclass(frozen=True, slots=True)
class GeneratedUiLayout:
    build_root: Path
    package_root: Path
    forms_root: Path


def default_build_root() -> Path:
    configured = os.environ.get(BUILD_ROOT_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "build/qt6"


def _validate_generated_forms(package_root: Path) -> None:
    expected = {
        package_root / destination.relative_to("rc_metastudio")
        for destination in CANONICAL_FORMS.values()
    }
    actual = set(package_root.rglob("ui_*.py")) if package_root.is_dir() else set()
    if actual != expected:
        missing = sorted(path.as_posix() for path in expected - actual)
        extra = sorted(path.as_posix() for path in actual - expected)
        raise RuntimeError(
            "Qt6 generated form set does not match the canonical manifest; "
            f"missing={missing}, extra={extra}. Run "
            "'uv run python scripts/build_qt6.py generate --build-root build/qt6'."
        )
    for path in sorted(expected):
        source = path.read_text(encoding="utf-8")
        valid = (
            "Created by: PyQt6 UI code generator 6.11.0" in source
            and "from PyQt6" in source
            and "PyQt5" not in source
            and "connectSlotsByName" not in source
            and "icons_rc" not in source
        )
        if not valid:
            raise RuntimeError(f"invalid generated Qt6 form: {path}")


def prepare_generated_ui_imports(
    build_root: Path | None = None,
) -> GeneratedUiLayout:
    """Validate and prepend the sole generated-form import layout.

    Source and development launches consume ``build/qt6/generated``. Frozen
    packages must preserve the same ``rc_metastudio`` and ``forms`` module
    names in the PyInstaller import archive and call this boundary only during
    source execution; packaging qualification owns that frozen-layout proof.
    """

    if getattr(sys, "frozen", False):
        missing = []
        for destination in CANONICAL_FORMS.values():
            relative = destination.relative_to("rc_metastudio").with_suffix("")
            module = ".".join(relative.parts)
            if importlib.util.find_spec(module) is None:
                missing.append(module)
        if missing:
            raise RuntimeError(
                "Frozen Qt6 package is missing generated form modules: "
                + ", ".join(sorted(missing))
            )
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return GeneratedUiLayout(bundle_root, bundle_root, bundle_root / "forms")
    resolved_build = (build_root or default_build_root()).expanduser().resolve()
    package_root = resolved_build / "generated/rc_metastudio"
    forms_root = package_root / "forms"
    _validate_generated_forms(package_root)

    loaded_forms = sys.modules.get("forms")
    loaded_file = getattr(loaded_forms, "__file__", None)
    if loaded_file is not None and package_root not in Path(loaded_file).resolve().parents:
        raise RuntimeError(
            "forms was imported before the Qt6 generated-form bootstrap; restart "
            "through the maintained rc-metastudio entry point"
        )
    for path in reversed((package_root, forms_root)):
        text = str(path)
        if text in sys.path:
            sys.path.remove(text)
        sys.path.insert(0, text)
    return GeneratedUiLayout(resolved_build, package_root, forms_root)
