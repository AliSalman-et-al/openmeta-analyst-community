"""Bootstrap deterministic build-generated Qt6 form imports."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import importlib.util
import os
from pathlib import Path
import sys

from rc_metastudio.ui_form_manifest import CANONICAL_FORMS


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
    """Validate and register the sole generated-form package layout.

    Source and development launches consume ``build/qt6/generated``. Frozen
    packages must preserve the same ``rc_metastudio`` and ``forms`` module
    names in the PyInstaller import archive and call this boundary only during
    source execution; packaging qualification owns that frozen-layout proof.
    """
    if getattr(sys, "frozen", False):
        missing = []
        for destination in CANONICAL_FORMS.values():
            relative = destination.relative_to("rc_metastudio").with_suffix("")
            module = ".".join(("rc_metastudio",) + relative.parts)
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

    import rc_metastudio

    package_paths = list(rc_metastudio.__path__)
    if str(package_root) not in package_paths:
        package_paths.insert(0, str(package_root))
        rc_metastudio.__path__ = package_paths

    generated_forms = importlib.import_module("rc_metastudio.forms")
    form_paths = list(generated_forms.__path__)
    if str(forms_root) not in form_paths:
        form_paths.insert(0, str(forms_root))
        generated_forms.__path__ = form_paths
    return GeneratedUiLayout(resolved_build, package_root, forms_root)
