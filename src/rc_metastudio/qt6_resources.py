"""Register the application-owned Qt 6 binary resource collection."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys

from PyQt6.QtCore import QResource


RESOURCE_ENV = "RCMS_QT6_RESOURCE"
BUILD_ROOT_ENV = "RCMS_QT6_BUILD_ROOT"
_registration: ResourceRegistration | None = None


@dataclass
class ResourceRegistration:
    """Own one successful binary-resource registration."""

    path: Path
    _closed: bool = False

    def close(self) -> None:
        if self._closed:
            return
        if not QResource.unregisterResource(str(self.path)):
            raise RuntimeError(f"Qt refused to unregister binary resource: {self.path}")
        self._closed = True


def register_binary_resource(path: Path) -> ResourceRegistration:
    """Register a compiled ``.rcc`` file or fail before application startup."""

    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise RuntimeError(f"Qt 6 binary resource does not exist: {resolved}")
    if not QResource.registerResource(str(resolved)):
        raise RuntimeError(f"Qt refused to register binary resource: {resolved}")
    return ResourceRegistration(resolved)


def _default_resource_path() -> Path:
    configured = os.environ.get(RESOURCE_ENV)
    if configured:
        return Path(configured)
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root is not None:
        return Path(bundle_root) / "resources/icons.rcc"
    configured_build = os.environ.get(BUILD_ROOT_ENV)
    if configured_build:
        return Path(configured_build).expanduser().resolve() / "resources/icons.rcc"
    return Path(__file__).resolve().parents[2] / "build/qt6/resources/icons.rcc"


def ensure_application_resources() -> ResourceRegistration:
    """Register the build-produced application resource exactly once."""

    global _registration
    if _registration is None or _registration._closed:
        _registration = register_binary_resource(_default_resource_path())
    return _registration
