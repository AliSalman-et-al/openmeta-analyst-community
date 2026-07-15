"""Run and validate the pre-codemod native macOS Qt6 feasibility proof."""

from __future__ import annotations

import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from typing import Any, NoReturn, cast


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_VERSIONS = {
    "python": "3.11.9",
    "pyqt6": "6.11.0",
    "qt": "6.11.1",
    "sip": "13.11.1",
    "r": "4.6.1",
    "rpy2": "3.6.7",
    "pyinstaller": "6.21.0",
}
TARGET_MACHINES = {"macos-x64": "x86_64", "macos-arm64": "arm64"}
DIAGNOSTIC_KEYS = {"source_smoke", "pyinstaller_build", "packaged_smoke"}
NATIVE_COMPONENT_KEYS = {
    "python",
    "pyqt6_qtcore",
    "qt6_core",
    "sip",
    "r",
    "rpy2",
    "rcc",
    "cocoa_plugin",
}
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
MAX_DEPLOYMENT_FILES = 10_000
MAX_DEPLOYMENT_BYTES = 1_000_000_000
MAX_RETAINED_NATIVE_BYTES = 100_000_000


class EvidenceError(RuntimeError):
    """Raised when native evidence cannot substantiate the locked contract."""


def _fail(message: str) -> NoReturn:
    raise EvidenceError(message)


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _retained_path(record: dict[str, Any], label: str, evidence_dir: Path) -> Path:
    raw_path = record.get("retained_path")
    if not isinstance(raw_path, str) or not raw_path:
        _fail(f"{label} has no retained path")
    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        _fail(f"{label} retained path must remain within the evidence directory")
    return evidence_dir / relative


def _validate_retained_file_record(
    record: dict[str, Any], label: str, evidence_dir: Path | None
) -> None:
    digest = record.get("sha256")
    size = record.get("size")
    if not isinstance(record.get("retained_path"), str) or not isinstance(
        digest, str
    ):
        _fail(f"{label} has no retained path or digest")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        _fail(f"{label} has an invalid retained size")
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        _fail(f"{label} has an invalid SHA-256 digest")
    if evidence_dir is not None:
        retained = _retained_path(record, label, evidence_dir)
        if (
            not retained.is_file()
            or retained.stat().st_size != size
            or _sha256(retained) != digest
        ):
            _fail(f"{label} does not match its retained bytes")
        architectures = record.get("architectures")
        if isinstance(architectures, list) and architectures:
            if _archs(retained) != architectures:
                _fail(f"{label} architectures do not match retained bytes")


def _validate_deployment_inventory(
    value: object,
    expected_machine: str,
    executable: dict[str, Any],
    cocoa_plugin: dict[str, Any],
) -> None:
    inventory = _mapping(value, "deployment inventory")
    if set(inventory) != {"schema_version", "file_count", "total_bytes", "files"}:
        _fail("deployment inventory contains missing or unknown fields")
    files = inventory.get("files")
    if inventory.get("schema_version") != 1 or not isinstance(files, list):
        _fail("deployment inventory has an unsupported schema")
    if not files or len(files) > MAX_DEPLOYMENT_FILES:
        _fail("deployment inventory file count is empty or exceeds its bound")
    records: dict[str, dict[str, Any]] = {}
    total = 0
    for raw_record in files:
        record = _mapping(raw_record, "deployment inventory file")
        if set(record) != {"path", "size", "sha256", "architectures"}:
            _fail("deployment inventory file contains missing or unknown fields")
        path = record.get("path")
        size = record.get("size")
        digest = record.get("sha256")
        architectures = record.get("architectures")
        if (
            not isinstance(path, str)
            or not path
            or path.startswith("/")
            or ".." in Path(path).parts
            or path in records
        ):
            _fail("deployment inventory has an invalid or duplicate path")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            _fail(f"deployment inventory has an invalid size for {path}")
        if not isinstance(digest, str) or len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            _fail(f"deployment inventory has an invalid digest for {path}")
        if not isinstance(architectures, list) or not all(
            architecture in {"x86_64", "arm64"} for architecture in architectures
        ):
            _fail(f"deployment inventory has invalid architectures for {path}")
        records[path] = record
        total += size
    if inventory.get("file_count") != len(files) or inventory.get(
        "total_bytes"
    ) != total:
        _fail("deployment inventory totals do not match its files")
    if total > MAX_DEPLOYMENT_BYTES:
        _fail("deployment inventory exceeds the bounded feasibility deployment size")

    lowered = [path.lower() for path in records]
    forbidden = ("pyqt5", "pyside2", "pyside6", "qt5")
    if any(token in path for path in lowered for token in forbidden):
        _fail("deployment inventory contains an alternate or legacy Qt binding")
    qt_roots = {
        path[: path.lower().index("/pyqt6/qt6/") + len("/PyQt6/Qt6")]
        for path in records
        if "/pyqt6/qt6/" in path.lower()
    }
    if len(qt_roots) != 1:
        _fail("deployment inventory does not contain one coherent PyQt6 Qt root")
    if not any("/pyqt6/qtcore" in path for path in lowered):
        _fail("deployment inventory is missing the PyQt6 QtCore extension")
    if not any("rinterface" in path for path in lowered):
        _fail("deployment inventory is missing the packaged rpy2 native bridge")
    cocoa_paths = [path for path in records if path.endswith("libqcocoa.dylib")]
    if len(cocoa_paths) != 1:
        _fail("deployment inventory must contain exactly one Cocoa platform plugin")
    for label, artifact in (("executable", executable), ("Cocoa plugin", cocoa_plugin)):
        deployment_path = artifact.get("deployment_path")
        if not isinstance(deployment_path, str) or deployment_path not in records:
            _fail(f"packaged {label} is absent from the deployment inventory")
        inventory_record = records[deployment_path]
        if inventory_record["sha256"] != artifact.get("sha256"):
            _fail(f"packaged {label} digest disagrees with the deployment inventory")
    if cocoa_paths[0] != cocoa_plugin.get("deployment_path"):
        _fail("packaged Cocoa plugin path disagrees with the deployment inventory")
    if records[cast(str, executable["deployment_path"])]["architectures"] != [
        expected_machine
    ]:
        _fail("deployment inventory does not prove a thin packaged executable")


def _validate_pyinstaller_build_plan(value: object) -> None:
    plan = _mapping(value, "PyInstaller build plan")
    if set(plan) != {"schema_version", "builder", "arguments", "manual_qt_inputs"}:
        _fail("PyInstaller build plan contains missing or unknown fields")
    arguments = plan.get("arguments")
    if (
        plan.get("schema_version") != 1
        or plan.get("builder") != "PyInstaller"
        or plan.get("manual_qt_inputs") != []
        or not isinstance(arguments, list)
        or not all(isinstance(argument, str) for argument in arguments)
    ):
        _fail("PyInstaller build plan is malformed")
    collection_options = {
        "--add-binary",
        "--collect-all",
        "--collect-binaries",
        "--collect-data",
        "--collect-submodules",
        "--hidden-import",
    }
    normalized_options = {
        argument.partition("=")[0]
        for argument in arguments
        if argument.startswith("--")
    }
    if normalized_options & collection_options:
        _fail("PyInstaller build plan contains a manual Qt collection mechanism")
    expected_options = [
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        "--target-architecture",
        "--distpath",
        "--workpath",
        "--specpath",
        "--add-data",
        "--copy-metadata",
    ]
    if [argument for argument in arguments if argument.startswith("--")] != expected_options:
        _fail("PyInstaller build plan does not match the allowlisted invocation")
    if len(arguments) != 19:
        _fail("PyInstaller build plan does not match the allowlisted invocation")
    if (
        arguments[4:6] != ["--name", "Qt6MacFeasibility"]
        or arguments[6] != "--target-architecture"
        or arguments[7] not in {"x86_64", "arm64"}
        or arguments[8] != "--distpath"
        or arguments[10] != "--workpath"
        or arguments[12] != "--specpath"
        or arguments[14] != "--add-data"
        or not arguments[15].endswith("icons.rcc:resources")
        or arguments[16:18] != ["--copy-metadata", "rpy2"]
        or not arguments[18].endswith("entry.py")
    ):
        _fail("PyInstaller build plan contains unexpected manual inputs")
    for path_argument in (arguments[9], arguments[11], arguments[13], arguments[18]):
        if not Path(path_argument).is_absolute():
            _fail("PyInstaller build plan paths must be absolute")


def validate_evidence(
    evidence: object, target: str, *, evidence_dir: Path | None = None
) -> None:
    """Fail closed unless *evidence* proves one complete native target."""

    if target not in TARGET_MACHINES:
        _fail(f"unsupported target {target!r}")
    root = _mapping(evidence, "evidence")
    expected_root_keys = {
        "schema_version",
        "target",
        "status",
        "runner",
        "dependencies",
        "source_smoke",
        "r_call",
        "package",
        "diagnostics",
        "native_components",
    }
    if set(root) != expected_root_keys:
        _fail("evidence contains missing or unknown top-level fields")
    if root.get("schema_version") != 1 or root.get("status") != "passed":
        _fail("evidence must be a passed schema version 1 record")
    if root.get("target") != target:
        _fail(f"target mismatch: expected {target}")

    expected_machine = TARGET_MACHINES[target]
    runner = _mapping(root.get("runner"), "runner")
    if set(runner) != RUNNER_KEYS:
        _fail("runner identity contains missing or unknown fields")
    if runner.get("system") != "Darwin":
        _fail("runner system must be Darwin")
    if not isinstance(runner.get("release"), str) or not re.fullmatch(
        r"[0-9]+(?:\.[0-9]+){1,3}", runner["release"]
    ):
        _fail("runner release is missing or malformed")
    if not isinstance(runner.get("platform"), str) or not runner["platform"].startswith(
        "macOS-"
    ):
        _fail("runner platform is not a recognized macOS identity")
    if runner.get("machine") != expected_machine:
        _fail(f"runner architecture must be {expected_machine}")
    if runner.get("python_machine") != expected_machine:
        _fail(f"Python architecture must be {expected_machine}")
    if runner.get("rosetta_translated") is not False:
        _fail("Rosetta translation is forbidden")
    expected_github_arch = "ARM64" if target == "macos-arm64" else "X64"
    if runner.get("github_runner_os") != "macOS" or runner.get(
        "github_runner_arch"
    ) != expected_github_arch:
        _fail("GitHub runner OS or architecture identity is inconsistent")
    if not isinstance(runner.get("runner_image"), str) or not re.fullmatch(
        r"macos-[0-9]+(?:-intel)?", runner["runner_image"]
    ):
        _fail("runner image identity is missing or malformed")

    dependencies = _mapping(root.get("dependencies"), "dependencies")
    if dependencies != EXPECTED_VERSIONS:
        differing = sorted(
            key
            for key, value in EXPECTED_VERSIONS.items()
            if dependencies.get(key) != value
        )
        _fail(f"locked dependency mismatch: {', '.join(differing) or 'unexpected keys'}")

    source = _mapping(root.get("source_smoke"), "source_smoke")
    if source.get("qpa") != "cocoa":
        _fail("source smoke did not load the Cocoa platform plugin")
    for key in (
        "visible",
        "resource_registered",
        "svg_rendered",
        "clean_exit",
    ):
        if source.get(key) is not True:
            _fail(f"source smoke did not prove {key}")
    if source.get("form") != "AboutLegalDialog":
        _fail("source smoke did not launch the generated form")
    if not isinstance(source.get("plugin_path"), str):
        _fail("source smoke did not record the Qt plugin path")

    r_call = _mapping(root.get("r_call"), "r_call")
    if r_call.get("expression") != "sum(c(1.25, 2.5, 3.75))" or r_call.get(
        "result"
    ) != 7.5:
        _fail("R result did not match the representative rpy2 call")

    package = _mapping(root.get("package"), "package")
    if package.get("target_arch") != expected_machine:
        _fail(f"packaged target architecture must be {expected_machine}")
    if package.get("qt_dependency_collector") != "PyInstaller":
        _fail("PyInstaller must be the sole Qt dependency collector")
    if package.get("qpa") != "cocoa" or not str(package.get("cocoa_plugin", "")).endswith(
        "libqcocoa.dylib"
    ):
        _fail("packaged smoke did not load its Cocoa platform plugin")
    if package.get("dependencies") != {
        key: EXPECTED_VERSIONS[key] for key in ("pyqt6", "qt", "r", "rpy2")
    }:
        _fail("packaged dependency identities do not match the locked stack")
    for key in (
        "visible",
        "resource_registered",
        "svg_rendered",
        "clean_exit",
    ):
        if package.get(key) is not True:
            _fail(f"packaged smoke did not prove {key}")
    if package.get("r_result") != 7.5:
        _fail("packaged R result did not match the representative call")

    executable = _mapping(package.get("executable"), "package.executable")
    cocoa_plugin = _mapping(package.get("cocoa_plugin_artifact"), "package.cocoa_plugin_artifact")
    if executable.get("architectures") != [expected_machine]:
        _fail("packaged executable must be a thin native binary")
    if expected_machine not in cocoa_plugin.get("architectures", []):
        _fail("packaged Cocoa plugin has no native architecture slice")
    for label, record in (("executable", executable), ("Cocoa plugin", cocoa_plugin)):
        _validate_retained_file_record(record, label, evidence_dir)

    inventory_record = _mapping(package.get("inventory"), "package.inventory")
    build_plan_record = _mapping(package.get("build_plan"), "package.build_plan")
    _validate_retained_file_record(inventory_record, "deployment inventory", evidence_dir)
    _validate_retained_file_record(build_plan_record, "PyInstaller build plan", evidence_dir)
    if evidence_dir is not None:
        inventory = json.loads(
            _retained_path(inventory_record, "deployment inventory", evidence_dir).read_text(
                encoding="utf-8"
            )
        )
        _validate_deployment_inventory(
            inventory, expected_machine, executable, cocoa_plugin
        )
        build_plan = json.loads(
            _retained_path(build_plan_record, "PyInstaller build plan", evidence_dir).read_text(
                encoding="utf-8"
            )
        )
        _validate_pyinstaller_build_plan(build_plan)

    diagnostics = _mapping(root.get("diagnostics"), "diagnostics")
    if set(diagnostics) != DIAGNOSTIC_KEYS:
        _fail("diagnostic inventory is incomplete or contains unknown records")
    for name, raw_record in diagnostics.items():
        record = _mapping(raw_record, f"diagnostics.{name}")
        digest = record.get("sha256")
        if not isinstance(record.get("path"), str) or not isinstance(digest, str):
            _fail(f"diagnostic {name} has no path or digest")
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            _fail(f"diagnostic {name} has an invalid SHA-256 digest")
        if evidence_dir is not None:
            relative = Path(record["path"])
            if relative.is_absolute() or ".." in relative.parts:
                _fail(f"diagnostic {name} path must remain within the evidence directory")
            diagnostic_path = evidence_dir / relative
            if not diagnostic_path.is_file() or _sha256(diagnostic_path) != digest:
                _fail(f"diagnostic {name} digest does not match retained bytes")

    components = _mapping(root.get("native_components"), "native_components")
    if set(components) != NATIVE_COMPONENT_KEYS:
        _fail("native component inventory is incomplete or contains unknown records")
    for name, raw_record in components.items():
        record = _mapping(raw_record, f"native_components.{name}")
        retained = record.get("retained")
        source_paths = record.get("source_paths")
        if not isinstance(retained, list) or not retained or not isinstance(
            source_paths, list
        ) or len(source_paths) != len(retained):
            _fail(f"native component {name} has an incomplete retained inventory")
        for item in retained:
            item_record = _mapping(item, f"native_components.{name}.retained")
            if expected_machine not in item_record.get("architectures", []):
                _fail(f"native component {name} has no {expected_machine} slice")
            _validate_retained_file_record(item_record, f"native component {name}", evidence_dir)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _archs(path: Path) -> list[str]:
    output = _run(["lipo", "-archs", str(path)]).stdout.strip().split()
    return sorted(output)


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

    result = float(cast(Any, ro.r("sum(c(1.25, 2.5, 3.75))"))[0])
    r_version = str(
        cast(Any, ro.r("paste(R.version$major, R.version$minor, sep='.')"))[0]
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
                    "architectures": _archs(destination),
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
    files = []
    total_bytes = 0
    for path in sorted(candidate for candidate in app_root.rglob("*") if candidate.is_file()):
        relative = path.relative_to(app_root).as_posix()
        size = path.stat().st_size
        total_bytes += size
        files.append(
            {
                "path": relative,
                "size": size,
                "sha256": _sha256(path),
                "architectures": _maybe_archs(path),
            }
        )
        if len(files) > MAX_DEPLOYMENT_FILES or total_bytes > MAX_DEPLOYMENT_BYTES:
            raise RuntimeError("minimal PyInstaller deployment exceeded its inventory bound")
    inventory = {
        "schema_version": 1,
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


def _retained_record(path: Path, evidence_dir: Path, *, architectures: bool) -> dict[str, object]:
    return {
        "retained_path": path.relative_to(evidence_dir).as_posix(),
        "size": path.stat().st_size,
        "sha256": _sha256(path),
        **({"architectures": _archs(path)} if architectures else {}),
    }


PACKAGED_ENTRY = r'''from __future__ import annotations
import json
import os
from pathlib import Path
import sys
from importlib import metadata
from PyQt6 import QtCore, QtGui, QtWidgets
from generated_form import Ui_AboutLegalDialog
import rpy2.robjects as ro

root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
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
raise SystemExit(exit_code)
'''


def run_feasibility(target: str, evidence_dir: Path) -> dict[str, Any]:
    if sys.platform != "darwin":
        raise RuntimeError("native macOS feasibility can run only on macOS")
    expected_machine = TARGET_MACHINES[target]
    machine = platform.machine().lower()
    if machine != expected_machine or _rosetta_translated():
        raise RuntimeError(
            f"native target mismatch: expected {expected_machine}, got {machine}, "
            f"Rosetta={_rosetta_translated()}"
        )

    evidence_dir.mkdir(parents=True, exist_ok=True)
    build_root = ROOT / "build" / "qt6-macos-feasibility" / target
    if build_root.exists():
        shutil.rmtree(build_root)
    build_root.mkdir(parents=True)

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
    work = build_root / "package-source"
    work.mkdir()
    shutil.copy2(generated, work / "generated_form.py")
    (work / "entry.py").write_text(PACKAGED_ENTRY, encoding="utf-8", newline="\n")
    pyinstaller_log = evidence_dir / "pyinstaller-build.log"
    target_arch = "x86_64" if target == "macos-x64" else "arm64"
    pyinstaller_arguments = [
            "--noconfirm",
            "--clean",
            "--windowed",
            "--onedir",
            "--name",
            "Qt6MacFeasibility",
            "--target-architecture",
            target_arch,
            "--distpath",
            str(build_root / "dist"),
            "--workpath",
            str(build_root / "work"),
            "--specpath",
            str(build_root),
            "--add-data",
            f"{resource}:resources",
            "--copy-metadata",
            "rpy2",
            str(work / "entry.py"),
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
    _run(
        [sys.executable, "-m", "PyInstaller", *pyinstaller_arguments],
        environment=environment,
        log=pyinstaller_log,
    )
    executable = (
        build_root
        / "dist/Qt6MacFeasibility.app/Contents/MacOS/Qt6MacFeasibility"
    )
    packaged_report = evidence_dir / "packaged-smoke.json"
    package_environment = environment.copy()
    package_environment["RCMS_FEASIBILITY_REPORT"] = str(packaged_report)
    _run([str(executable)], environment=package_environment)
    package = json.loads(packaged_report.read_text(encoding="utf-8"))
    plugin = Path(package["cocoa_plugin"])
    app_root = build_root / "dist/Qt6MacFeasibility.app"
    if not plugin.is_file() or app_root not in plugin.parents:
        raise RuntimeError(f"Cocoa plugin was not collected inside the app: {plugin}")
    package["cocoa_plugin"] = plugin.relative_to(app_root).as_posix()
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

    evidence: dict[str, Any] = {
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
        "source_smoke": source_log,
        "pyinstaller_build": pyinstaller_log,
        "packaged_smoke": packaged_report,
    }.items():
        evidence["diagnostics"][key] = {
            "path": path.name,
            "sha256": _sha256(path),
        }
    validate_evidence(evidence, target, evidence_dir=evidence_dir)
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
    return parser


def main(arguments: list[str] | None = None) -> int:
    options = _parser().parse_args(arguments)
    if options.command == "run":
        run_feasibility(options.target, options.evidence_dir.resolve())
        return 0
    evidence = json.loads(options.evidence.read_text(encoding="utf-8"))
    validate_evidence(evidence, options.target, evidence_dir=options.evidence.parent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
