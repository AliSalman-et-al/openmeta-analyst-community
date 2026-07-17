"""Build and exercise the first native Qt6 vertical slice.

The generated form and binary resource live below ``build/``.  They are build
products, never Python sources owned by the application package.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
from typing import Mapping, Protocol, cast
import urllib.request

import py7zr
from PyQt6 import QtCore, QtGui, QtWidgets


ROOT = Path(__file__).resolve().parents[2]
CANONICAL_FORMS = {
    Path("src/rc_metastudio/forms/about_legal.ui"): Path("rc_metastudio/forms/ui_about_legal.py"),
    Path("src/rc_metastudio/forms/binary_data_form2.ui"): Path("rc_metastudio/forms/ui_binary_data_form.py"),
    Path("src/rc_metastudio/forms/change_cov_type_form.ui"): Path("rc_metastudio/forms/ui_change_cov_type.py"),
    Path("src/rc_metastudio/forms/change_group_name_dlg.ui"): Path("rc_metastudio/forms/ui_edit_group_name.py"),
    Path("src/rc_metastudio/forms/choose_back_calc_result_form.ui"): Path("rc_metastudio/forms/ui_choose_back_calc_result_form.py"),
    Path("src/rc_metastudio/forms/choose_metric_page.ui"): Path("rc_metastudio/forms/ui_choose_metric_page.py"),
    Path("src/rc_metastudio/forms/conf_level_dialog.ui"): Path("rc_metastudio/forms/ui_conf_level_dialog.py"),
    Path("src/rc_metastudio/forms/continuous_back_calc_result_form.ui"): Path("rc_metastudio/forms/ui_continuous_back_calc_result_form.py"),
    Path("src/rc_metastudio/forms/continuous_data_form.ui"): Path("rc_metastudio/forms/ui_continuous_data_form.py"),
    Path("src/rc_metastudio/forms/cov_reg_dlg2.ui"): Path("rc_metastudio/forms/ui_meta_reg.py"),
    Path("src/rc_metastudio/forms/cov_subgroup_dlg.ui"): Path("rc_metastudio/forms/ui_cov_subgroup_dlg.py"),
    Path("src/rc_metastudio/forms/csv_import_page.ui"): Path("rc_metastudio/forms/ui_csv_import_page.py"),
    Path("src/rc_metastudio/forms/data_type_page.ui"): Path("rc_metastudio/forms/ui_data_type_page.py"),
    Path("src/rc_metastudio/forms/diagnostic_data_form.ui"): Path("rc_metastudio/forms/ui_diagnostic_data_form.py"),
    Path("src/rc_metastudio/forms/diagnostic_metrics.ui"): Path("rc_metastudio/forms/ui_diagnostic_metrics.py"),
    Path("src/rc_metastudio/forms/edit_dialog2.ui"): Path("rc_metastudio/forms/ui_edit_dialog.py"),
    Path("src/rc_metastudio/forms/edit_forest_plot.ui"): Path("rc_metastudio/forms/ui_edit_forest_plot.py"),
    Path("src/rc_metastudio/forms/ma_specs2.ui"): Path("rc_metastudio/forms/ui_ma_specs.py"),
    Path("src/rc_metastudio/forms/meta.ui"): Path("rc_metastudio/ui_meta.py"),
    Path("src/rc_metastudio/forms/network_view_window.ui"): Path("rc_metastudio/forms/ui_network_view.py"),
    Path("src/rc_metastudio/forms/new_covariate_dlg.ui"): Path("rc_metastudio/forms/ui_new_covariate.py"),
    Path("src/rc_metastudio/forms/new_follow_up_dlg.ui"): Path("rc_metastudio/forms/ui_new_follow_up.py"),
    Path("src/rc_metastudio/forms/new_group_dlg.ui"): Path("rc_metastudio/forms/ui_new_group.py"),
    Path("src/rc_metastudio/forms/new_outcome_dlg.ui"): Path("rc_metastudio/forms/ui_new_outcome.py"),
    Path("src/rc_metastudio/forms/new_study_dlg.ui"): Path("rc_metastudio/forms/ui_new_study.py"),
    Path("src/rc_metastudio/forms/outcome_name_page.ui"): Path("rc_metastudio/forms/ui_outcome_name_page.py"),
    Path("src/rc_metastudio/forms/results_window.ui"): Path("rc_metastudio/ui_results_window.py"),
    Path("src/rc_metastudio/forms/running.ui"): Path("rc_metastudio/forms/ui_running.py"),
    Path("src/rc_metastudio/forms/welcome_page.ui"): Path("rc_metastudio/forms/ui_welcome_page.py"),
}
CANONICAL_RESOURCE = Path("src/rc_metastudio/images/icons.qrc")
DEFAULT_BUILD_ROOT = ROOT / "build" / "qt6"

# The PyQt6-Qt6 wheel intentionally contains the runtime and not the Qt SDK
# command-line tools. This immutable official Qt package supplies matching rcc.
QT_RCC_VERSION = "6.11.1"
QT_RCC_PACKAGE = (
    "6.11.1-0-202605090529qtbase-Windows-Windows_11_24H2-MSVC2022-"
    "Windows-Windows_11_24H2-X86_64.7z"
)
QT_RCC_PACKAGE_URL = (
    "https://download.qt.io/online/qtsdkrepository/windows_x86/desktop/"
    "qt6_6111/qt6_6111_msvc2022_64/qt.qt6.6111.win64_msvc2022_64/"
    + QT_RCC_PACKAGE
)
QT_RCC_PACKAGE_SIZE = 39_469_569
QT_RCC_PACKAGE_SHA256 = "7f97edc3937fec7383eb865e010ed5128155bf9c80a563abca450860f3e9bef5"
QT_RCC_SHA256 = "912f4565e9486243200517be9e7e8dddc76ea63cd426278e944ba36ad8ff14e7"
QT_RCC_CORE_SHA256 = "fae4778a42e93adc82b831c879c886a05147e9cc26760808d21116be5547259b"
WINDOWS_X64_PE_MACHINE = 0x8664


def validate_form_manifest(
    manifest: Mapping[Path, Path], discovered: set[Path]
) -> None:
    """Reject canonical-form drift and unsafe or colliding build destinations."""

    declared = set(manifest)
    if declared != discovered:
        missing = sorted(path.as_posix() for path in discovered - declared)
        extra = sorted(path.as_posix() for path in declared - discovered)
        raise RuntimeError(
            f"Canonical form manifest does not match discovery: missing={missing}, extra={extra}"
        )
    destinations = list(manifest.values())
    if len(destinations) != len(set(destinations)):
        raise RuntimeError("Canonical form manifest has a destination collision")
    for destination in destinations:
        parts = destination.parts
        canonical = (
            not destination.is_absolute()
            and ".." not in parts
            and destination.suffix == ".py"
            and destination.name.startswith("ui_")
            and parts[:1] == ("rc_metastudio",)
            and (
                len(parts) == 2
                or (len(parts) == 3 and parts[1] == "forms")
            )
        )
        if not canonical:
            raise RuntimeError(
                f"Canonical form manifest has non-canonical destination: {destination}"
            )


class _GeneratedForm(Protocol):
    def setupUi(self, dialog: QtWidgets.QDialog) -> None: ...


def _run(command: list[str], *, cwd: Path = ROOT) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def _belongs_to_selected_python_environment(
    candidate: Path, scripts_directory: Path
) -> bool:
    selected_scripts = scripts_directory.resolve()
    return (
        candidate.parent.resolve() == selected_scripts
        and candidate.resolve().parent == selected_scripts
    )


def _resolve_pyuic6() -> str:
    scripts_directory = Path(sys.executable).absolute().parent
    entrypoint_name = "pyuic6.exe" if os.name == "nt" else "pyuic6"
    adjacent = scripts_directory / entrypoint_name
    if adjacent.is_file():
        if _belongs_to_selected_python_environment(adjacent, scripts_directory):
            return str(adjacent)
        raise RuntimeError(
            "pyuic6 adjacent to the selected interpreter resolves outside the "
            f"locked Python environment: {adjacent}"
        )

    executable = shutil.which("pyuic6")
    if executable is None:
        raise RuntimeError("pyuic6 is not available from the locked PyQt6 environment")
    candidate = Path(executable).absolute()
    if not _belongs_to_selected_python_environment(candidate, scripts_directory):
        raise RuntimeError(
            "pyuic6 resolved outside the selected locked Python environment: "
            f"{candidate} (expected {scripts_directory})"
        )
    return str(candidate)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pe_machine(path: Path) -> int:
    with path.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise RuntimeError(f"rcc is not a Windows PE executable: {path}")
        stream.seek(0x3C)
        pe_offset_bytes = stream.read(4)
        if len(pe_offset_bytes) != 4:
            raise RuntimeError(f"rcc has a truncated PE header: {path}")
        pe_offset = struct.unpack("<I", pe_offset_bytes)[0]
        stream.seek(pe_offset)
        if stream.read(4) != b"PE\0\0":
            raise RuntimeError(f"rcc has an invalid PE signature: {path}")
        machine_bytes = stream.read(2)
        if len(machine_bytes) != 2:
            raise RuntimeError(f"rcc has no PE architecture field: {path}")
        return struct.unpack("<H", machine_bytes)[0]


def validate_rcc(
    rcc: Path,
    *,
    expected_digest: str = QT_RCC_SHA256,
    expected_version: str = QT_RCC_VERSION,
) -> None:
    """Fail closed unless *rcc* is the pinned official Windows x64 compiler."""

    actual_digest = _sha256(rcc)
    if actual_digest != expected_digest:
        raise RuntimeError(
            f"rcc digest mismatch: expected {expected_digest}, got {actual_digest}"
        )
    machine = _pe_machine(rcc)
    if machine != WINDOWS_X64_PE_MACHINE:
        raise RuntimeError(
            f"rcc architecture mismatch: expected PE machine 0x8664, got 0x{machine:04x}"
        )
    completed = subprocess.run(
        [str(rcc), "--version"], check=True, capture_output=True, text=True
    )
    reported = completed.stdout.strip() or completed.stderr.strip()
    if reported != f"rcc {expected_version}":
        raise RuntimeError(
            f"rcc version mismatch: expected 'rcc {expected_version}', got {reported!r}"
        )
    core = rcc.with_name("Qt6Core.dll")
    if not core.is_file() or _sha256(core) != QT_RCC_CORE_SHA256:
        raise RuntimeError("rcc is not paired with the pinned official Qt6Core.dll")


def validate_macos_rcc(rcc: Path, *, expected_version: str = QT_RCC_VERSION) -> None:
    """Validate the official macOS SDK rcc selected by the native CI job."""

    completed = subprocess.run(
        [str(rcc), "--version"], check=True, capture_output=True, text=True
    )
    reported = completed.stdout.strip() or completed.stderr.strip()
    if reported != f"rcc {expected_version}":
        raise RuntimeError(
            f"rcc version mismatch: expected 'rcc {expected_version}', got {reported!r}"
        )
    architectures = subprocess.run(
        ["lipo", "-archs", str(rcc)], check=True, capture_output=True, text=True
    ).stdout.split()
    host = platform.machine().lower()
    if host not in architectures:
        raise RuntimeError(
            f"rcc architecture mismatch: host {host!r}, slices {architectures!r}"
        )


def download_pinned_archive(
    url: str,
    destination: Path,
    *,
    expected_size: int,
    expected_digest: str,
) -> None:
    """Download an immutable archive while enforcing length before its digest."""

    temporary = destination.with_suffix(".download")
    temporary.unlink(missing_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            content_length = response.headers.get("Content-Length")
            if content_length is not None and int(content_length) > expected_size:
                raise RuntimeError(
                    "Official Qt archive Content-Length exceeds the pinned byte size"
                )
            total = 0
            with temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > expected_size:
                        raise RuntimeError(
                            "Official Qt archive stream exceeds the pinned byte size"
                        )
                    output.write(chunk)
        if total != expected_size:
            raise RuntimeError(
                f"Official Qt archive byte count mismatch: expected {expected_size}, "
                f"got {total}"
            )
        if _sha256(temporary) != expected_digest:
            raise RuntimeError("Official Qt archive digest did not match the pin")
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _download_official_rcc(tool_root: Path) -> Path:
    cache = tool_root / "cache" / QT_RCC_PACKAGE
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.is_file() and (
        cache.stat().st_size != QT_RCC_PACKAGE_SIZE
        or _sha256(cache) != QT_RCC_PACKAGE_SHA256
    ):
        cache.unlink()
    if not cache.is_file():
        download_pinned_archive(
            QT_RCC_PACKAGE_URL,
            cache,
            expected_size=QT_RCC_PACKAGE_SIZE,
            expected_digest=QT_RCC_PACKAGE_SHA256,
        )

    install_root = tool_root / QT_RCC_VERSION / "msvc2022_64"
    rcc = install_root / "bin" / "rcc.exe"
    if not rcc.is_file():
        staging = tool_root / f".{QT_RCC_VERSION}-extracting"
        if staging.exists():
            shutil.rmtree(staging)
        with py7zr.SevenZipFile(cache) as archive:
            archive.extract(
                path=staging, targets=["bin/rcc.exe", "bin/Qt6Core.dll"]
            )
        install_root.parent.mkdir(parents=True, exist_ok=True)
        if install_root.exists():
            shutil.rmtree(install_root)
        staging.replace(install_root)
    return rcc


def _resolve_rcc() -> Path:
    configured = os.environ.get("RCMS_QT6_RCC")
    if configured:
        rcc = Path(configured).expanduser().resolve()
        if not rcc.is_file():
            raise RuntimeError(f"RCMS_QT6_RCC does not name a file: {rcc}")
        if sys.platform == "darwin":
            validate_macos_rcc(rcc)
        else:
            validate_rcc(rcc)
        return rcc

    if sys.platform == "darwin":
        raise RuntimeError(
            "macOS requires RCMS_QT6_RCC from the pinned official Qt SDK"
        )
    if sys.platform != "win32":
        raise RuntimeError("The official rcc slice supports Windows and macOS only")
    rcc = _download_official_rcc(ROOT / "build" / "qt-rcc")
    validate_rcc(rcc)
    return rcc


def _write_package_marker(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8", newline="\n")


def _render_form(build_root: Path, source: Path, destination: Path) -> Path:
    module = build_root / "generated" / destination
    module.parent.mkdir(parents=True, exist_ok=True)
    temporary = module.with_suffix(".py.tmp")
    _run(
        [
            _resolve_pyuic6(),
            source.as_posix(),
            "--output",
            str(temporary),
        ]
    )
    generated = temporary.read_text(encoding="utf-8")
    generated = "".join(
        line
        for line in generated.splitlines(keepends=True)
        if "QtCore.QMetaObject.connectSlotsByName(" not in line
        and not line.strip().endswith("import icons_rc")
    )
    module.write_text(generated, encoding="utf-8", newline="\n")
    temporary.unlink()
    _write_package_marker(build_root / "generated/rc_metastudio/__init__.py")
    _write_package_marker(build_root / "generated/rc_metastudio/forms/__init__.py")
    return module


def _compile_resource(build_root: Path) -> Path:
    resource = build_root / "resources/icons.rcc"
    resource.parent.mkdir(parents=True, exist_ok=True)
    temporary = resource.with_suffix(".rcc.tmp")
    _run(
        [
            str(_resolve_rcc()),
            "--binary",
            CANONICAL_RESOURCE.as_posix(),
            "--output",
            str(temporary),
        ]
    )
    temporary.replace(resource)
    return resource


def generate(build_root: Path) -> tuple[Path, Path]:
    """Generate every canonical form and the shared binary resource."""

    discovered = {
        path.relative_to(ROOT)
        for path in (ROOT / "src/rc_metastudio/forms").glob("*.ui")
    }
    validate_form_manifest(CANONICAL_FORMS, discovered)
    modules = {
        source: _render_form(build_root, source, destination)
        for source, destination in CANONICAL_FORMS.items()
    }
    representative = modules[Path("src/rc_metastudio/forms/about_legal.ui")]
    return representative, _compile_resource(build_root)


def _load_generated_form(module_path: Path) -> type[_GeneratedForm]:
    spec = importlib.util.spec_from_file_location("rcms_generated_about_legal", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot create an import specification for {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(type[_GeneratedForm], module.Ui_AboutLegalDialog)


def smoke(
    build_root: Path,
    exit_after_ms: int,
    *,
    expected_qpa: str | None = None,
) -> dict[str, str | bool]:
    """Launch a visible native Qt6 form and return user-observable evidence."""

    module_path, resource_path = generate(build_root)
    if not QtCore.QResource.registerResource(str(resource_path)):
        raise RuntimeError(f"Qt refused to register binary resource {resource_path}")

    application = cast(
        QtWidgets.QApplication | None, QtWidgets.QApplication.instance()
    )
    owns_application = application is None
    if application is None:
        application = QtWidgets.QApplication(["rc-metastudio-qt6-smoke"])
    qpa = application.platformName()
    if expected_qpa is not None and qpa != expected_qpa:
        raise RuntimeError(f"Qt QPA mismatch: expected {expected_qpa!r}, got {qpa!r}")
    architecture = platform.machine().lower()
    if expected_qpa == "windows" and architecture not in {"amd64", "x86_64"}:
        raise RuntimeError(
            f"Native Windows smoke requires x64 Python, got {platform.machine()!r}"
        )
    if expected_qpa == "cocoa" and architecture not in {"x86_64", "arm64"}:
        raise RuntimeError(
            f"Native macOS smoke requires x86_64 or arm64 Python, got {platform.machine()!r}"
        )

    dialog = QtWidgets.QDialog()
    form_type = _load_generated_form(module_path)
    form = form_type()
    form.setupUi(dialog)
    app_icon = QtGui.QIcon(":/misc/meta.png")
    svg_icon = QtGui.QIcon(":/icons/actions/about-legal.svg")
    app_icon_pixmap = app_icon.pixmap(QtCore.QSize(32, 32))
    svg_icon_pixmap = svg_icon.pixmap(QtCore.QSize(24, 24))
    if app_icon_pixmap.isNull() or svg_icon_pixmap.isNull():
        raise RuntimeError("The registered binary resource did not expose required icons")
    application.setWindowIcon(app_icon)
    dialog.setWindowIcon(app_icon)
    dialog.show()
    application.processEvents()
    visible = dialog.isVisible()
    if not visible:
        raise RuntimeError("The Qt6 smoke dialog did not become visible")
    QtCore.QTimer.singleShot(exit_after_ms, application.quit)
    exit_code = application.exec()
    dialog.close()
    unregistered = QtCore.QResource.unregisterResource(str(resource_path))
    if exit_code != 0 or not unregistered:
        raise RuntimeError(
            f"Qt6 smoke did not shut down cleanly: exit={exit_code}, "
            f"resource_unregistered={unregistered}"
        )

    # QApplication cannot be recreated in a process; this flag documents why
    # the smoke command is intentionally a standalone process.
    if not owns_application:
        raise RuntimeError("Qt6 smoke requires ownership of its QApplication")
    return {
        "pyqt": QtCore.PYQT_VERSION_STR,
        "qt": QtCore.qVersion(),
        "form": dialog.objectName(),
        "app_icon": not app_icon_pixmap.isNull(),
        "resource_registered": True,
        "architecture": platform.machine(),
        "svg_icon": not svg_icon_pixmap.isNull(),
        "clean_exit": True,
        "native": qpa in {"windows", "cocoa"},
        "plugin_path": QtCore.QLibraryInfo.path(
            QtCore.QLibraryInfo.LibraryPath.PluginsPath
        ),
        "qpa": qpa,
        "visible": visible,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("generate", "smoke", "native-smoke"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--build-root", type=Path, default=DEFAULT_BUILD_ROOT)
        if command in {"smoke", "native-smoke"}:
            subparser.add_argument("--exit-after-ms", type=int, default=100)
    return parser


def main(arguments: list[str] | None = None) -> int:
    options = _parser().parse_args(arguments)
    build_root = options.build_root.resolve()
    if options.command == "generate":
        module, resource = generate(build_root)
        print(json.dumps({"form": str(module), "resource": str(resource)}, sort_keys=True))
        return 0
    expected_qpa = None
    if options.command == "native-smoke":
        expected_qpa = "cocoa" if sys.platform == "darwin" else "windows"
    report = smoke(build_root, options.exit_after_ms, expected_qpa=expected_qpa)
    print(json.dumps(report, sort_keys=True))
    return 0
