# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run and validate the pre-codemod native macOS Qt6 feasibility proof."""

from __future__ import annotations

import argparse
import importlib.util
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from typing import Callable, cast

from scripts.macos_evidence import (
    EXPECTED_VERSIONS,
    _archs as _evidence_archs,
    MAX_DEPLOYMENT_BYTES,
    MAX_DEPLOYMENT_FILES,
    MAX_RETAINED_NATIVE_BYTES,
    TARGET_MACHINES,
    _sha256,
    validate_evidence as _validate_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
QT_RCC_VERSION = EXPECTED_VERSIONS["qt"]
RUNNER_KEYS = {
    "system",
    "release",
    "platform",
    "machine",
    "python_machine",
    "rosetta_translated",
    "github_runner_os",
    "github_runner_arch",
    "runner_image",
}


def _run(
    command: list[str],
    *,
    environment: dict[str, str] | None = None,
    log: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if log is not None:
        log.write_text(completed.stdout, encoding="utf-8", newline="\n")
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed with exit {completed.returncode}: {' '.join(command)}\n"
            f"{completed.stdout}"
        )
    return completed


def _rosetta_translated() -> bool:
    completed = subprocess.run(
        ["sysctl", "-in", "sysctl.proc_translated"],
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "1"


def _dependency_versions() -> tuple[dict[str, str], float]:
    from PyQt6 import QtCore
    import rpy2.robjects as ro

    def first_r_value(value: object, expression: str) -> object:
        get_item = getattr(value, "__getitem__", None)
        if not callable(get_item):
            raise RuntimeError(f"rpy2 expression did not return a vector: {expression}")
        try:
            return get_item(0)
        except (IndexError, KeyError, TypeError) as exc:
            raise RuntimeError(
                f"rpy2 expression returned no first value: {expression}"
            ) from exc

    raw_result = first_r_value(ro.r("sum(c(1.25, 2.5, 3.75))"), "sum")
    if not isinstance(raw_result, (int, float)):
        raise RuntimeError("rpy2 sum expression did not return a number")
    result = float(raw_result)
    r_version = str(
        first_r_value(
            ro.r("paste(R.version$major, R.version$minor, sep='.')"),
            "R.version",
        )
    )
    versions = {
        "python": platform.python_version(),
        "pyqt6": QtCore.PYQT_VERSION_STR,
        "qt": QtCore.qVersion(),
        "sip": metadata.version("PyQt6-sip"),
        "r": r_version,
        "rpy2": metadata.version("rpy2"),
        "pyinstaller": metadata.version("pyinstaller"),
    }
    if versions != EXPECTED_VERSIONS:
        raise RuntimeError(f"locked dependency mismatch: {versions!r}")
    if result != 7.5:
        raise RuntimeError(f"representative rpy2 result mismatch: {result!r}")
    return versions, result


def discover_rpy2_native_extensions() -> list[Path]:
    """Return concrete native files owned by locked ``rpy2-rinterface``."""
    import rpy2.rinterface_lib as rinterface_lib

    distribution = metadata.distribution("rpy2-rinterface")
    concrete_roots = {Path(path).resolve() for path in rinterface_lib.__path__}
    candidates = {
        Path(str(distribution.locate_file(file))).resolve()
        for file in distribution.files or []
        if Path(str(file)).suffix.lower() in {".dylib", ".pyd", ".so"}
    }
    extensions = sorted(path for path in candidates if path.is_file())
    if not extensions:
        roots = ", ".join(str(root) for root in sorted(concrete_roots))
        raise RuntimeError(
            "rpy2-rinterface installed no concrete native extension; "
            f"searched distribution files associated with {roots}"
        )
    return extensions


def discover_macos_rcc(sdk_root: Path) -> Path:
    """Resolve one recognized Qt macOS SDK ``rcc`` layout, fail closed otherwise."""
    root = sdk_root.resolve()
    relative_candidates = (
        Path("libexec/rcc"),
        Path("libexec/rcc.app/Contents/MacOS/rcc"),
        Path("bin/rcc"),
        Path("bin/rcc.app/Contents/MacOS/rcc"),
    )
    candidates = set()
    for relative in relative_candidates:
        candidate = root / relative
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if not resolved.is_relative_to(root):
            raise RuntimeError(
                f"Qt macOS SDK rcc escapes the declared SDK root: {candidate} -> "
                f"{resolved}"
            )
        candidates.add(resolved)
    if not candidates:
        searched = ", ".join(relative.as_posix() for relative in relative_candidates)
        raise RuntimeError(
            f"Qt macOS SDK contains no rcc in a recognized layout under {root}; "
            f"searched {searched}"
        )
    if len(candidates) != 1:
        raise RuntimeError(
            "Qt macOS SDK contains ambiguous distinct rcc executables: "
            + ", ".join(str(candidate) for candidate in sorted(candidates))
        )
    return candidates.pop()


def validate_macos_rcc(
    rcc: Path,
    *,
    expected_version: str = QT_RCC_VERSION,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    host_machine: Callable[[], str] = platform.machine,
) -> list[str]:
    """Validate an official macOS SDK rcc without importing Qt build dependencies."""
    completed = command_runner(
        [str(rcc), "--version"], check=True, capture_output=True, text=True
    )
    reported = completed.stdout.strip() or completed.stderr.strip()
    if reported != f"rcc {expected_version}":
        raise RuntimeError(
            f"rcc version mismatch: expected 'rcc {expected_version}', got {reported!r}"
        )
    architectures = command_runner(
        ["/usr/bin/lipo", "-archs", str(rcc)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    supported = {"arm64", "x86_64"}
    unique_architectures = set(architectures)
    if (
        not unique_architectures
        or len(architectures) != len(unique_architectures)
        or not unique_architectures <= supported
    ):
        raise RuntimeError(f"rcc has invalid architecture slices: {architectures!r}")
    host = host_machine().lower()
    if host != "arm64" or host not in architectures:
        raise RuntimeError(
            f"rcc architecture mismatch: host {host!r}, slices {architectures!r}"
        )
    return sorted(architectures)


def append_github_env(github_env: Path, name: str, value: str) -> None:
    """Append one safe, exact UTF-8 GitHub environment-file assignment."""
    if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", name):
        raise RuntimeError(f"invalid GitHub environment variable name: {name!r}")
    if "\r" in value or "\n" in value:
        raise RuntimeError("GitHub environment variable value contains CR or LF")
    github_env.parent.mkdir(parents=True, exist_ok=True)
    with github_env.open("ab") as stream:
        stream.write(f"{name}={value}\n".encode("utf-8"))


def resolve_macos_rcc(
    sdk_root: Path,
    github_env: Path,
    diagnostic: Path,
    *,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    host_machine: Callable[[], str] = platform.machine,
) -> dict[str, object]:
    """Validate, record, and export the exact official SDK ``rcc`` executable."""
    rcc = discover_macos_rcc(sdk_root)
    architectures = validate_macos_rcc(
        rcc, command_runner=command_runner, host_machine=host_machine
    )
    record: dict[str, object] = {
        "path": str(rcc),
        "version": EXPECTED_VERSIONS["qt"],
        "sha256": _sha256(rcc),
        "architectures": architectures,
    }
    diagnostic.parent.mkdir(parents=True, exist_ok=True)
    diagnostic.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    append_github_env(github_env, "RCMS_QT6_RCC", str(rcc))
    return record


def _native_component_paths() -> dict[str, list[Path]]:
    from PyQt6 import QtCore, sip

    r_home = Path(_run(["R", "RHOME"]).stdout.strip())
    rcc_value = os.environ.get("RCMS_QT6_RCC")
    if not rcc_value:
        raise RuntimeError("RCMS_QT6_RCC must identify the pinned official Qt SDK rcc")
    plugin_root = Path(
        QtCore.QLibraryInfo.path(QtCore.QLibraryInfo.LibraryPath.PluginsPath)
    )
    library_root = Path(
        QtCore.QLibraryInfo.path(QtCore.QLibraryInfo.LibraryPath.LibrariesPath)
    )
    return {
        "python": [Path(sys.executable)],
        "pyqt6_qtcore": [Path(QtCore.__file__)],
        "qt6_core": [library_root / "QtCore.framework/Versions/A/QtCore"],
        "sip": [Path(sip.__file__)],
        "r": [r_home / "bin/exec/R"],
        "rpy2": discover_rpy2_native_extensions(),
        "rcc": [Path(rcc_value)],
        "cocoa_plugin": [plugin_root / "platforms/libqcocoa.dylib"],
    }


def _retain_native_components(evidence_dir: Path) -> dict[str, dict[str, object]]:
    inventory: dict[str, dict[str, object]] = {}
    total_size = 0
    for name, source_paths in _native_component_paths().items():
        retained_records = []
        resolved_sources = []
        for index, source in enumerate(source_paths):
            resolved = source.resolve()
            if not resolved.is_file():
                raise RuntimeError(f"native component does not exist: {resolved}")
            destination = (
                evidence_dir
                / "native-components"
                / name
                / f"{index:02d}-{resolved.name}"
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(resolved, destination)
            total_size += destination.stat().st_size
            if total_size > MAX_RETAINED_NATIVE_BYTES:
                raise RuntimeError("retained native components exceed the 100 MB bound")
            resolved_sources.append(str(resolved))
            retained_records.append(
                {
                    "retained_path": destination.relative_to(evidence_dir).as_posix(),
                    "size": destination.stat().st_size,
                    "sha256": _sha256(destination),
                    "architectures": _evidence_archs(destination),
                }
            )
        inventory[name] = {
            "source_paths": resolved_sources,
            "retained": retained_records,
        }
    return inventory


def _maybe_archs(path: Path) -> list[str]:
    completed = subprocess.run(
        ["lipo", "-archs", str(path)], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        return []
    return sorted(completed.stdout.strip().split())


def _write_deployment_inventory(app_root: Path, destination: Path) -> dict[str, object]:
    root = app_root.resolve()
    files, total_bytes = _collect_deployment_files(root)
    files.sort(key=lambda record: record["path"])
    inventory = {
        "schema_version": 2,
        "file_count": len(files),
        "total_bytes": total_bytes,
        "files": files,
    }
    destination.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return inventory


def _collect_deployment_files(
    root: Path,
) -> tuple[list[dict[str, object]], int]:
    files: list[dict[str, object]] = []
    total_bytes = 0
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        entries, entry_bytes = _collect_deployment_directory(
            current_path, directories, filenames, root
        )
        files.extend(entries)
        total_bytes += entry_bytes
        if len(files) > MAX_DEPLOYMENT_FILES or total_bytes > MAX_DEPLOYMENT_BYTES:
            raise RuntimeError(
                "minimal PyInstaller deployment exceeded its inventory bound"
            )
    return files, total_bytes


def _collect_deployment_directory(
    current: Path,
    directories: list[str],
    filenames: list[str],
    root: Path,
) -> tuple[list[dict[str, object]], int]:
    records: list[dict[str, object]] = []
    total_bytes = 0
    for name in list(directories):
        path = current / name
        if not path.is_symlink():
            continue
        directories.remove(name)
        record = _deployment_symlink_record(path, root)
        records.append(record)
        total_bytes += cast(int, record["size"])
    for name in filenames:
        path = current / name
        record = _deployment_file_record(path, root)
        records.append(record)
        total_bytes += cast(int, record["size"])
    return records, total_bytes


def _deployment_symlink_record(path: Path, root: Path) -> dict[str, object]:
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise RuntimeError(f"packaged symlink escapes the app bundle: {path}")
    return {
        "path": path.relative_to(root).as_posix(),
        "kind": "symlink",
        "size": path.lstat().st_size,
        "link_target": os.readlink(path),
        "resolved_path": resolved.relative_to(root).as_posix(),
    }


def _deployment_file_record(path: Path, root: Path) -> dict[str, object]:
    if path.is_symlink():
        return _deployment_symlink_record(path, root)
    return {
        "path": path.relative_to(root).as_posix(),
        "kind": "file",
        "size": path.stat().st_size,
        "sha256": _sha256(path),
        "architectures": _maybe_archs(path),
    }


def _retained_record(
    path: Path, evidence_dir: Path, *, architectures: bool
) -> dict[str, object]:
    return {
        "retained_path": path.relative_to(evidence_dir).as_posix(),
        "size": path.stat().st_size,
        "sha256": _sha256(path),
        **({"architectures": _evidence_archs(path)} if architectures else {}),
    }


PACKAGED_ENTRY = r"""from __future__ import annotations
import json
import os
from pathlib import Path
import sys
from importlib import metadata

phases = Path(os.environ["RCMS_FEASIBILITY_PHASES"])
def phase(name):
    with phases.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"phase": name}) + "\n")
        stream.flush()
        os.fsync(stream.fileno())

phase("python-entry")
root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
r_home = root / "R.framework" / "Resources"
if not (r_home / "lib/libR.dylib").is_file() or not (r_home / "etc/Renviron").is_file():
    raise SystemExit(f"private bundled R_HOME is incomplete: {r_home}")
os.environ["R_HOME"] = str(r_home)
os.environ["R_SHARE_DIR"] = str(r_home / "share")
os.environ["R_INCLUDE_DIR"] = str(r_home / "include")
os.environ["R_DOC_DIR"] = str(r_home / "doc")
phase("private-r-owned")
from PyQt6 import QtCore, QtGui, QtWidgets
phase("qt-imported")
from generated_form import Ui_AboutLegalDialog
import rpy2.robjects as ro
from rpy2.rinterface_lib import openrlib
phase("rpy2-api-imported")

resource = root / "resources" / "icons.rcc"
registered = QtCore.QResource.registerResource(str(resource))
app = QtWidgets.QApplication(["qt6-macos-feasibility"])
dialog = QtWidgets.QDialog()
Ui_AboutLegalDialog().setupUi(dialog)
svg = QtGui.QIcon(":/icons/actions/about-legal.svg").pixmap(QtCore.QSize(24, 24))
dialog.show()
app.processEvents()
plugin_root = Path(QtCore.QLibraryInfo.path(QtCore.QLibraryInfo.LibraryPath.PluginsPath))
cocoa = plugin_root / "platforms" / "libqcocoa.dylib"
report = {
    "qpa": app.platformName(),
    "visible": dialog.isVisible(),
    "resource_registered": registered,
    "svg_rendered": not svg.isNull(),
    "r_result": float(ro.r("sum(c(1.25, 2.5, 3.75))")[0]),
    "r_home": str(r_home),
    "rpy2_mode": openrlib.cffi_mode.name,
    "cocoa_plugin": str(cocoa),
    "dependencies": {
        "pyqt6": QtCore.PYQT_VERSION_STR,
        "qt": QtCore.qVersion(),
        "r": str(ro.r("paste(R.version$major, R.version$minor, sep='.')")[0]),
        "rpy2": metadata.version("rpy2"),
    },
}
QtCore.QTimer.singleShot(100, app.quit)
exit_code = app.exec()
report["clean_exit"] = exit_code == 0 and QtCore.QResource.unregisterResource(str(resource))
Path(os.environ["RCMS_FEASIBILITY_REPORT"]).write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
phase("clean-exit")
raise SystemExit(exit_code)
"""


def _prepare_private_r_framework(
    build_root: Path, evidence_dir: Path, architecture: str
) -> tuple[Path, Path]:
    r_home = Path(subprocess.check_output(["R", "RHOME"], text=True).strip()).resolve(
        strict=True
    )
    source_framework = next(
        (
            parent
            for parent in (r_home, *r_home.parents)
            if parent.name == "R.framework"
        ),
        None,
    )
    if source_framework is None:
        raise RuntimeError(f"R RHOME is not inside the official R.framework: {r_home}")
    staged_framework = build_root / "staged/R.framework"
    staged_framework.parent.mkdir(parents=True)
    shutil.copytree(source_framework, staged_framework, symlinks=True)
    staged_resources = staged_framework / "Resources"
    _run(
        [
            sys.executable,
            str(ROOT / "scripts/profile_macos_embedded_r_runtime.py"),
            "quarantine",
            "--resources",
            str(staged_resources),
            "--evidence",
            str(evidence_dir / "r-profile-quarantine.json"),
            "--dependency-manifest",
            str(ROOT / "config/r-dependencies.json"),
            "--r-version",
            EXPECTED_VERSIONS["r"],
            "--architecture",
            architecture,
            "--source-resources",
            str(r_home),
            "--official-framework-layout",
        ]
    )
    _run(
        [
            sys.executable,
            str(ROOT / "scripts/configure_macos_r_launchers.py"),
            "--resources",
            str(staged_resources),
            "--runtime-only",
        ]
    )
    _run(
        [
            "bash",
            str(ROOT / "scripts/relocate_macos_r_runtime.sh"),
            "--resources",
            str(staged_resources),
            "--architecture",
            architecture,
            "--python",
            sys.executable,
            "--allowed-root",
            str(build_root),
            "--normalizer",
            str(ROOT / "scripts/normalize_macos_macho.py"),
        ]
    )
    bridge_spec = importlib.util.find_spec("_rinterface_cffi_api")
    if bridge_spec is None or bridge_spec.origin is None:
        raise RuntimeError("locked rpy2 API bridge is unavailable")
    bridge = Path(bridge_spec.origin).resolve(strict=True)
    _run(
        [
            sys.executable,
            str(ROOT / "scripts/macos_embedded_r_adapter.py"),
            "relocate-bridge",
            "--framework",
            str(staged_framework),
            "--bridge",
            str(bridge),
            "--architecture",
            architecture,
            "--output",
            str(evidence_dir / "source-rpy2-relocation.json"),
        ]
    )
    toc = evidence_dir / "feasibility-r-toc.json"
    _run(
        [
            sys.executable,
            str(ROOT / "scripts/macos_embedded_r_adapter.py"),
            "finalize-toc",
            "--framework",
            str(staged_framework),
            "--architecture",
            architecture,
            "--output",
            str(evidence_dir / "feasibility-r-framework.json"),
            "--toc-output",
            str(toc),
        ]
    )
    return staged_framework, toc


def _native_target(target: str) -> tuple[str, str]:
    if sys.platform != "darwin":
        raise RuntimeError("native macOS feasibility can run only on macOS")
    expected_machine = TARGET_MACHINES[target]
    machine = platform.machine().lower()
    if machine != expected_machine or _rosetta_translated():
        raise RuntimeError(
            f"native target mismatch: expected {expected_machine}, got {machine}, "
            f"Rosetta={_rosetta_translated()}"
        )
    return expected_machine, machine


def _feasibility_build_root(target: str, evidence_dir: Path) -> Path:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    build_root = ROOT / "build" / "qt6-macos-feasibility" / target
    if build_root.exists():
        shutil.rmtree(build_root)
    build_root.mkdir(parents=True)
    return build_root


def _packaged_bridge(app_root: Path) -> Path:
    packaged_bridges = list(app_root.rglob("_rinterface_cffi_api*.so"))
    if len(packaged_bridges) != 1:
        raise RuntimeError(
            f"packaged feasibility app must contain one rpy2 API bridge: {packaged_bridges}"
        )
    return packaged_bridges[0]


def _validate_packaged_smoke(
    package: dict[str, object], app_root: Path
) -> Path:
    plugin_value = package.get("cocoa_plugin")
    r_home_value = package.get("r_home")
    if not isinstance(plugin_value, str) or not isinstance(r_home_value, str):
        raise RuntimeError("packaged smoke omitted its path fields")
    plugin = Path(plugin_value)
    private_r_home = app_root / "Contents/Frameworks/R.framework/Resources"
    if Path(r_home_value) != private_r_home:
        raise RuntimeError("packaged smoke did not own its explicit private R_HOME")
    if package.get("rpy2_mode") != "API":
        raise RuntimeError("packaged smoke did not load the rpy2 API bridge")
    if not plugin.is_file() or app_root not in plugin.parents:
        raise RuntimeError(f"Cocoa plugin was not collected inside the app: {plugin}")
    package["r_home"] = private_r_home.relative_to(app_root).as_posix()
    package["cocoa_plugin"] = plugin.relative_to(app_root).as_posix()
    return plugin


def run_feasibility(target: str, evidence_dir: Path) -> dict[str, object]:
    expected_machine, machine = _native_target(target)

    build_root = _feasibility_build_root(target, evidence_dir)

    versions, r_result = _dependency_versions()
    components = _retain_native_components(evidence_dir)
    environment = os.environ.copy()
    environment.pop("QT_QPA_PLATFORM", None)
    source_log = evidence_dir / "source-smoke.json"
    source_completed = _run(
        [
            sys.executable,
            str(ROOT / "scripts/build_qt6.py"),
            "native-smoke",
            "--build-root",
            str(build_root / "source"),
            "--exit-after-ms",
            "100",
        ],
        environment=environment,
    )
    source_log.write_text(source_completed.stdout, encoding="utf-8", newline="\n")
    source = json.loads(source_completed.stdout)

    generated = build_root / "source/generated/rc_metastudio/forms/ui_about_legal.py"
    resource = build_root / "source/resources/icons.rcc"
    target_arch = "arm64"
    staged_r_framework, r_toc = _prepare_private_r_framework(
        build_root, evidence_dir, target_arch
    )
    work = build_root / "package-source"
    work.mkdir()
    shutil.copy2(generated, work / "generated_form.py")
    (work / "entry.py").write_text(PACKAGED_ENTRY, encoding="utf-8", newline="\n")
    pyinstaller_log = evidence_dir / "pyinstaller-build.log"
    feasibility_spec = ROOT / "packaging/pyinstaller/qt6-macos-feasibility.spec"
    pyinstaller_arguments = [
        "--noconfirm",
        "--clean",
        "--distpath",
        str(build_root / "dist"),
        "--workpath",
        str(build_root / "work"),
        str(feasibility_spec),
    ]
    build_plan_path = evidence_dir / "pyinstaller-build-plan.json"
    build_plan = {
        "schema_version": 1,
        "builder": "PyInstaller",
        "arguments": pyinstaller_arguments,
        "manual_qt_inputs": [],
    }
    build_plan_path.write_text(
        json.dumps(build_plan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    environment.update(
        {
            "RCMS_FEASIBILITY_ENTRY": str(work / "entry.py"),
            "RCMS_FEASIBILITY_RESOURCE": str(resource),
            "RCMS_FEASIBILITY_R_FRAMEWORK": str(staged_r_framework),
            "RCMS_FEASIBILITY_R_TOC": str(r_toc),
            "RCMS_TARGET_ARCHITECTURE": target_arch,
        }
    )
    _run(
        [sys.executable, "-m", "PyInstaller", *pyinstaller_arguments],
        environment=environment,
        log=pyinstaller_log,
    )
    executable = (
        build_root / "dist/Qt6MacFeasibility.app/Contents/MacOS/Qt6MacFeasibility"
    )
    app_root = build_root / "dist/Qt6MacFeasibility.app"
    packaged_bridge = _packaged_bridge(app_root)
    _run(
        [
            sys.executable,
            str(ROOT / "scripts/macos_embedded_r_adapter.py"),
            "relocate-bridge",
            "--framework",
            str(app_root / "Contents/Frameworks/R.framework"),
            "--bridge",
            str(packaged_bridge),
            "--architecture",
            target_arch,
            "--output",
            str(evidence_dir / "packaged-rpy2-relocation.json"),
        ]
    )
    packaged_r_graph = evidence_dir / "packaged-r-graph.json"
    _run(
        [
            sys.executable,
            str(ROOT / "scripts/macos_embedded_r_adapter.py"),
            "post-app",
            "--app",
            str(app_root),
            "--architecture",
            target_arch,
            "--output",
            str(packaged_r_graph),
        ]
    )
    packaged_report = evidence_dir / "packaged-smoke.json"
    packaged_phases = evidence_dir / "packaged-phases.jsonl"
    package_environment = environment.copy()
    package_environment["RCMS_FEASIBILITY_REPORT"] = str(packaged_report)
    package_environment["RCMS_FEASIBILITY_PHASES"] = str(packaged_phases)
    _run([str(executable)], environment=package_environment)
    package = json.loads(packaged_report.read_text(encoding="utf-8"))
    plugin = _validate_packaged_smoke(package, app_root)
    probe_root = evidence_dir / "package-probe"
    probe_root.mkdir()
    retained_executable = probe_root / "Qt6MacFeasibility"
    retained_plugin = probe_root / "libqcocoa.dylib"
    shutil.copy2(executable, retained_executable)
    shutil.copy2(plugin, retained_plugin)
    inventory_path = evidence_dir / "pyinstaller-deployment-inventory.json"
    _write_deployment_inventory(app_root, inventory_path)
    package.update(
        {
            "target_arch": expected_machine,
            "qt_dependency_collector": "PyInstaller",
            "executable": {
                **_retained_record(
                    retained_executable, evidence_dir, architectures=True
                ),
                "deployment_path": executable.relative_to(app_root).as_posix(),
            },
            "cocoa_plugin_artifact": {
                **_retained_record(retained_plugin, evidence_dir, architectures=True),
                "deployment_path": plugin.relative_to(app_root).as_posix(),
            },
            "inventory": _retained_record(
                inventory_path, evidence_dir, architectures=False
            ),
            "build_plan": _retained_record(
                build_plan_path, evidence_dir, architectures=False
            ),
        }
    )

    evidence: dict[str, object] = {
        "schema_version": 1,
        "target": target,
        "status": "passed",
        "runner": {
            "system": platform.system(),
            "release": platform.release(),
            "platform": platform.platform(),
            "machine": machine,
            "python_machine": platform.machine().lower(),
            "rosetta_translated": False,
            "github_runner_os": os.environ.get("RUNNER_OS", ""),
            "github_runner_arch": os.environ.get("RUNNER_ARCH", ""),
            "runner_image": os.environ.get("RCMS_RUNNER_IMAGE", ""),
        },
        "dependencies": versions,
        "source_smoke": {
            "qpa": source["qpa"],
            "visible": source["visible"],
            "form": source["form"],
            "resource_registered": source["resource_registered"],
            "svg_rendered": source["svg_icon"],
            "clean_exit": source["clean_exit"],
            "plugin_path": source["plugin_path"],
        },
        "r_call": {
            "expression": "sum(c(1.25, 2.5, 3.75))",
            "result": r_result,
        },
        "package": package,
        "diagnostics": {},
        "native_components": components,
    }
    for key, path in {
        "r_profile_quarantine": evidence_dir / "r-profile-quarantine.json",
        "source_smoke": source_log,
        "pyinstaller_build": pyinstaller_log,
        "packaged_smoke": packaged_report,
        "packaged_phases": packaged_phases,
        "packaged_r_graph": packaged_r_graph,
    }.items():
        evidence["diagnostics"][key] = {
            "path": path.name,
            "sha256": _sha256(path),
        }
    _validate_evidence(evidence, target, evidence_dir=evidence_dir)
    output = evidence_dir / "evidence.json"
    output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return evidence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--target", choices=sorted(TARGET_MACHINES), required=True)
    run.add_argument("--evidence-dir", type=Path, required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--target", choices=sorted(TARGET_MACHINES), required=True)
    validate.add_argument("--evidence", type=Path, required=True)
    resolve = subparsers.add_parser("resolve-rcc")
    resolve.add_argument("--sdk-root", type=Path, required=True)
    resolve.add_argument("--github-env", type=Path, required=True)
    resolve.add_argument("--diagnostic", type=Path, required=True)
    return parser


def main(arguments: list[str] | None = None) -> int:
    options = _parser().parse_args(arguments)
    if options.command == "run":
        run_feasibility(options.target, options.evidence_dir.resolve())
        return 0
    if options.command == "resolve-rcc":
        record = resolve_macos_rcc(
            options.sdk_root.resolve(),
            options.github_env.resolve(),
            options.diagnostic.resolve(),
        )
        print(json.dumps(record, sort_keys=True))
        return 0
    evidence = json.loads(options.evidence.read_text(encoding="utf-8"))
    _validate_evidence(evidence, options.target, evidence_dir=options.evidence.parent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
