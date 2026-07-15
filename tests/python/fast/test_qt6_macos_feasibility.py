import copy
import hashlib
import json
from pathlib import Path
import tomllib

import pytest
import yaml

from rc_metastudio.qt6_macos_feasibility import (
    EvidenceError,
    discover_rpy2_native_extensions,
    validate_evidence,
)


ROOT = Path(__file__).resolve().parents[3]


def _valid_evidence(target: str = "macos-arm64") -> dict:
    machine = "arm64" if target == "macos-arm64" else "x86_64"
    return {
        "schema_version": 1,
        "target": target,
        "status": "passed",
        "runner": {
            "system": "Darwin",
            "release": "24.5.0",
            "platform": f"macOS-15.5-{machine}",
            "machine": machine,
            "python_machine": machine,
            "rosetta_translated": False,
            "github_runner_os": "macOS",
            "github_runner_arch": "ARM64" if machine == "arm64" else "X64",
            "runner_image": "macos-14" if machine == "arm64" else "macos-15-intel",
        },
        "dependencies": {
            "python": "3.11.9",
            "pyqt6": "6.11.0",
            "qt": "6.11.1",
            "sip": "13.11.1",
            "r": "4.6.1",
            "rpy2": "3.6.7",
            "pyinstaller": "6.21.0",
        },
        "source_smoke": {
            "qpa": "cocoa",
            "visible": True,
            "form": "AboutLegalDialog",
            "resource_registered": True,
            "svg_rendered": True,
            "clean_exit": True,
            "plugin_path": "/wheel/PyQt6/Qt6/plugins",
        },
        "r_call": {"expression": "sum(c(1.25, 2.5, 3.75))", "result": 7.5},
        "package": {
            "target_arch": machine,
            "qpa": "cocoa",
            "visible": True,
            "resource_registered": True,
            "svg_rendered": True,
            "r_result": 7.5,
            "clean_exit": True,
            "qt_dependency_collector": "PyInstaller",
            "cocoa_plugin": "Qt/plugins/platforms/libqcocoa.dylib",
            "executable": {
                "retained_path": "package-probe/Qt6MacFeasibility",
                "deployment_path": "Contents/MacOS/Qt6MacFeasibility",
                "size": 10,
                "sha256": "d" * 64,
                "architectures": [machine],
            },
            "cocoa_plugin_artifact": {
                "retained_path": "package-probe/libqcocoa.dylib",
                "deployment_path": "Contents/Frameworks/PyQt6/Qt6/plugins/platforms/libqcocoa.dylib",
                "size": 10,
                "sha256": "e" * 64,
                "architectures": [machine],
            },
            "inventory": {
                "retained_path": "pyinstaller-deployment-inventory.json",
                "size": 10,
                "sha256": "f" * 64,
            },
            "build_plan": {
                "retained_path": "pyinstaller-build-plan.json",
                "size": 10,
                "sha256": "0" * 64,
            },
            "dependencies": {
                "pyqt6": "6.11.0",
                "qt": "6.11.1",
                "r": "4.6.1",
                "rpy2": "3.6.7",
            },
        },
        "diagnostics": {
            "source_smoke": {"path": "source-smoke.json", "sha256": "a" * 64},
            "pyinstaller_build": {"path": "pyinstaller-build.log", "sha256": "b" * 64},
            "packaged_smoke": {"path": "packaged-smoke.json", "sha256": "c" * 64},
        },
        "native_components": {
            name: {
                "source_paths": [f"/native/{name}"],
                "retained": [
                    {
                        "retained_path": f"native-components/{name}/00-{name}",
                        "size": 10,
                        "architectures": [machine],
                        "sha256": character * 64,
                    }
                ],
            }
            for name, character in {
                "python": "1",
                "pyqt6_qtcore": "2",
                "qt6_core": "8",
                "sip": "3",
                "r": "4",
                "rpy2": "5",
                "rcc": "6",
                "cocoa_plugin": "7",
            }.items()
        },
    }


def _materialize_retained_evidence(evidence: dict, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)

    def write_record(record: dict, payload: bytes) -> None:
        path = root / record["retained_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        record["size"] = len(payload)
        record["sha256"] = hashlib.sha256(payload).hexdigest()

    for name, record in evidence["diagnostics"].items():
        path = root / record["path"]
        path.write_bytes(f"diagnostic:{name}".encode())
        record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name, component in evidence["native_components"].items():
        write_record(component["retained"][0], f"native:{name}".encode())

    executable = evidence["package"]["executable"]
    cocoa = evidence["package"]["cocoa_plugin_artifact"]
    write_record(executable, b"thin executable")
    write_record(cocoa, b"native cocoa plugin")
    inventory_files = [
        {
            "path": executable["deployment_path"],
            "size": executable["size"],
            "sha256": executable["sha256"],
            "architectures": executable["architectures"],
        },
        {
            "path": cocoa["deployment_path"],
            "size": cocoa["size"],
            "sha256": cocoa["sha256"],
            "architectures": cocoa["architectures"],
        },
        {
            "path": "Contents/Frameworks/PyQt6/QtCore.abi3.so",
            "size": 4,
            "sha256": hashlib.sha256(b"core").hexdigest(),
            "architectures": executable["architectures"],
        },
        {
            "path": "Contents/Frameworks/PyQt6/Qt6/lib/QtCore.framework/Versions/A/QtCore",
            "size": 7,
            "sha256": hashlib.sha256(b"qt core").hexdigest(),
            "architectures": executable["architectures"],
        },
        {
            "path": "Contents/Frameworks/_rinterface_cffi_api.abi3.so",
            "size": 4,
            "sha256": hashlib.sha256(b"rpy2").hexdigest(),
            "architectures": executable["architectures"],
        },
    ]
    inventory = {
        "schema_version": 1,
        "file_count": len(inventory_files),
        "total_bytes": sum(record["size"] for record in inventory_files),
        "files": inventory_files,
    }
    write_record(
        evidence["package"]["inventory"],
        (json.dumps(inventory, sort_keys=True) + "\n").encode(),
    )
    build_plan = {
        "schema_version": 1,
        "builder": "PyInstaller",
        "arguments": [
            "--noconfirm",
            "--clean",
            "--windowed",
            "--onedir",
            "--name",
            "Qt6MacFeasibility",
            "--target-architecture",
            "arm64",
            "--distpath",
            str((root / "dist").resolve()),
            "--workpath",
            str((root / "work").resolve()),
            "--specpath",
            str((root / "spec").resolve()),
            "--add-data",
            f"{(root / 'icons.rcc').resolve()}:resources",
            "--copy-metadata",
            "rpy2",
            str((root / "entry.py").resolve()),
        ],
        "manual_qt_inputs": [],
    }
    write_record(
        evidence["package"]["build_plan"],
        (json.dumps(build_plan, sort_keys=True) + "\n").encode(),
    )


@pytest.mark.parametrize("target", ["macos-x64", "macos-arm64"])
def test_native_macos_evidence_accepts_the_complete_locked_contract(target):
    validate_evidence(_valid_evidence(target), target)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data["runner"].__setitem__("rosetta_translated", True), "Rosetta"),
        (lambda data: data["runner"].pop("release"), "runner identity"),
        (lambda data: data["runner"].__setitem__("system", "Linux"), "Darwin"),
        (lambda data: data["runner"].__setitem__("release", "unknown"), "malformed"),
        (lambda data: data["dependencies"].__setitem__("qt", "6.11.2"), "qt"),
        (lambda data: data["source_smoke"].__setitem__("qpa", "offscreen"), "Cocoa"),
        (lambda data: data["r_call"].__setitem__("result", 7.0), "R result"),
        (
            lambda data: data["package"].__setitem__(
                "executable",
                {
                    **data["package"]["executable"],
                    "architectures": ["x86_64", "arm64"],
                },
            ),
            "thin",
        ),
        (
            lambda data: data["package"].__setitem__(
                "qt_dependency_collector", "manual-copy"
            ),
            "PyInstaller",
        ),
        (lambda data: data["diagnostics"].pop("pyinstaller_build"), "diagnostic"),
        (
            lambda data: data["native_components"]["r"].__setitem__(
                "retained",
                [
                    {
                        **data["native_components"]["r"]["retained"][0],
                        "architectures": ["x86_64"],
                    }
                ],
            ),
            "native component r",
        ),
    ],
    ids=[
        "rosetta",
        "missing-runner-field",
        "unknown-runner-system",
        "malformed-runner-release",
        "qt-version",
        "source-qpa",
        "r-result",
        "universal-package",
        "manual-qt-collection",
        "missing-diagnostic",
        "wrong-r-architecture",
    ],
)
def test_native_macos_evidence_fails_closed_on_incomplete_or_mismatched_proof(
    mutation, message
):
    evidence = copy.deepcopy(_valid_evidence())
    mutation(evidence)

    with pytest.raises(EvidenceError, match=message):
        validate_evidence(evidence, "macos-arm64")


def test_native_macos_workflow_uses_two_strict_native_jobs_and_retains_evidence():
    workflow_path = ROOT / ".github/workflows/qt6-macos-feasibility.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    job = workflow["jobs"]["native-macos-feasibility"]
    targets = job["strategy"]["matrix"]["include"]

    assert targets == [
        {"target": "macos-x64", "runner": "macos-15-intel", "machine": "x86_64"},
        {"target": "macos-arm64", "runner": "macos-14", "machine": "arm64"},
    ]
    assert job["strategy"]["fail-fast"] is False
    assert job["continue-on-error"] is False
    assert job["runs-on"] == "${{ matrix.runner }}"
    assert any(
        step.get("uses", "").startswith("actions/upload-artifact@")
        and step.get("if") == "${{ always() }}"
        and step["with"]["if-no-files-found"] == "error"
        for step in job["steps"]
    )

    script_steps = "\n".join(str(step.get("run", "")) for step in job["steps"])
    assert "uv sync --locked" in script_steps
    assert "uv run aqt install-qt mac desktop" in script_steps
    assert workflow["env"]["R_VERSION"] == "4.6.1"
    assert "qt6_macos_feasibility.py run" in script_steps
    assert "qt6_macos_feasibility.py validate" in script_steps
    assert "continue-on-error" not in script_steps

    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "aqtinstall==3.3.0" in metadata["dependency-groups"]["dev"]


def test_locked_rpy2_runtime_discovers_concrete_native_extensions():
    extensions = discover_rpy2_native_extensions()

    assert extensions
    assert all(path.is_file() for path in extensions)
    assert all(path.suffix.lower() in {".dylib", ".pyd", ".so"} for path in extensions)
    assert any("rinterface" in path.name.lower() or "rinterface_lib" in path.as_posix() for path in extensions)


def test_native_macos_evidence_recomputes_retained_diagnostic_hashes(
    tmp_path, monkeypatch
):
    evidence = _valid_evidence()
    _materialize_retained_evidence(evidence, tmp_path)
    monkeypatch.setattr(
        "rc_metastudio.qt6_macos_feasibility._archs", lambda _path: ["arm64"]
    )
    validate_evidence(evidence, "macos-arm64", evidence_dir=tmp_path)

    (tmp_path / "source-smoke.json").write_bytes(b"tampered")
    with pytest.raises(EvidenceError, match="retained bytes"):
        validate_evidence(evidence, "macos-arm64", evidence_dir=tmp_path)


def test_native_macos_evidence_rejects_invented_hashes_and_missing_artifacts(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "rc_metastudio.qt6_macos_feasibility._archs", lambda _path: ["arm64"]
    )
    invented = _valid_evidence()
    invented_root = tmp_path / "invented"
    _materialize_retained_evidence(invented, invented_root)
    invented["package"]["executable"]["sha256"] = "a" * 64
    with pytest.raises(EvidenceError, match="retained bytes"):
        validate_evidence(invented, "macos-arm64", evidence_dir=invented_root)

    missing = _valid_evidence()
    missing_root = tmp_path / "missing"
    _materialize_retained_evidence(missing, missing_root)
    (missing_root / missing["native_components"]["rcc"]["retained"][0]["retained_path"]).unlink()
    with pytest.raises(EvidenceError, match="native component rcc"):
        validate_evidence(missing, "macos-arm64", evidence_dir=missing_root)

    tampered = _valid_evidence()
    tampered_root = tmp_path / "tampered"
    _materialize_retained_evidence(tampered, tampered_root)
    (tampered_root / tampered["package"]["inventory"]["retained_path"]).write_text(
        "{}", encoding="utf-8"
    )
    with pytest.raises(EvidenceError, match="deployment inventory"):
        validate_evidence(tampered, "macos-arm64", evidence_dir=tampered_root)


def test_pyinstaller_plan_rejects_split_equals_and_ambiguous_collection_options(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "rc_metastudio.qt6_macos_feasibility._archs", lambda _path: ["arm64"]
    )
    forbidden_arguments = [
        ["--add-binary", "/tmp/QtCore:/Qt"],
        ["--add-binary=/tmp/QtCore:/Qt"],
        ["--collect-all", "PyQt6"],
        ["--collect-all=PyQt6"],
        ["--hidden-import", "PySide6"],
        ["--hidden-import=PySide6"],
        ["--collect-binaries=PyQt6"],
        ["--runtime-hook=/tmp/ambiguous-qt-hook.py"],
    ]
    for index, injected in enumerate(forbidden_arguments):
        evidence = _valid_evidence()
        root = tmp_path / str(index)
        _materialize_retained_evidence(evidence, root)
        record = evidence["package"]["build_plan"]
        plan_path = root / record["retained_path"]
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["arguments"].extend(injected)
        plan_path.write_text(json.dumps(plan, sort_keys=True), encoding="utf-8")
        record["size"] = plan_path.stat().st_size
        record["sha256"] = hashlib.sha256(plan_path.read_bytes()).hexdigest()

        with pytest.raises(EvidenceError, match="PyInstaller build plan"):
            validate_evidence(evidence, "macos-arm64", evidence_dir=root)
