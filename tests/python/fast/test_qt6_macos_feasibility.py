import copy
import hashlib
import json
import posixpath
import tomllib
from pathlib import Path

import pytest
import yaml

from rc_metastudio.qt6_macos_feasibility import (
    EvidenceError,
    _archs,
    append_github_env,
    discover_macos_rcc,
    discover_rpy2_native_extensions,
    validate_evidence,
)


ROOT = Path(__file__).resolve().parents[3]


def _thin_macho(
    cpu_type: int,
    subtype: int,
    magic: bytes = b"\xcf\xfa\xed\xfe",
) -> bytes:
    byte_order = (
        "little" if magic in {b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe"} else "big"
    )
    header_size = 32 if magic in {b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe"} else 28
    return (
        magic
        + cpu_type.to_bytes(4, byte_order)
        + subtype.to_bytes(4, byte_order)
        + bytes(header_size - 12)
    )


def _fat_macho(
    architectures: list[tuple[int, int, bytes]],
    magic: bytes = b"\xca\xfe\xba\xbe",
    *,
    reserved: int = 0,
) -> bytes:
    byte_order = (
        "little" if magic in {b"\xbe\xba\xfe\xca", b"\xbf\xba\xfe\xca"} else "big"
    )
    entry_size = 32 if magic in {b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"} else 20
    table_end = 8 + entry_size * len(architectures)
    offset = (table_end + 15) // 16 * 16
    entries = bytearray()
    slices = bytearray(offset - table_end)
    for cpu_type, subtype, payload in architectures:
        entries.extend(cpu_type.to_bytes(4, byte_order))
        entries.extend(subtype.to_bytes(4, byte_order))
        field_size = 8 if entry_size == 32 else 4
        entries.extend(offset.to_bytes(field_size, byte_order))
        entries.extend(len(payload).to_bytes(field_size, byte_order))
        entries.extend((4).to_bytes(4, byte_order))
        if entry_size == 32:
            entries.extend(reserved.to_bytes(4, byte_order))
        slices.extend(payload)
        offset += len(payload)
    return magic + len(architectures).to_bytes(4, byte_order) + entries + slices


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
            "r_home": "Contents/Frameworks/R.framework/Resources",
            "rpy2_mode": "API",
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
            "r_profile_quarantine": {
                "path": "r-profile-quarantine.json",
                "sha256": "7" * 64,
            },
            "source_smoke": {"path": "source-smoke.json", "sha256": "a" * 64},
            "pyinstaller_build": {"path": "pyinstaller-build.log", "sha256": "b" * 64},
            "packaged_smoke": {"path": "packaged-smoke.json", "sha256": "c" * 64},
            "packaged_phases": {"path": "packaged-phases.jsonl", "sha256": "9" * 64},
            "packaged_r_graph": {"path": "packaged-r-graph.json", "sha256": "8" * 64},
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
            "kind": "file",
            "size": executable["size"],
            "sha256": executable["sha256"],
            "architectures": executable["architectures"],
        },
        {
            "path": cocoa["deployment_path"],
            "kind": "file",
            "size": cocoa["size"],
            "sha256": cocoa["sha256"],
            "architectures": cocoa["architectures"],
        },
        {
            "path": "Contents/Frameworks/PyQt6/QtCore.abi3.so",
            "kind": "file",
            "size": 4,
            "sha256": hashlib.sha256(b"core").hexdigest(),
            "architectures": executable["architectures"],
        },
        {
            "path": "Contents/Frameworks/PyQt6/Qt6/lib/QtCore.framework/Versions/A/QtCore",
            "kind": "file",
            "size": 7,
            "sha256": hashlib.sha256(b"qt core").hexdigest(),
            "architectures": executable["architectures"],
        },
        {
            "path": "Contents/Frameworks/_rinterface_cffi_api.abi3.so",
            "kind": "file",
            "size": 4,
            "sha256": hashlib.sha256(b"rpy2").hexdigest(),
            "architectures": executable["architectures"],
        },
        {
            "path": "Contents/Frameworks/R.framework/Resources/lib/libR.dylib",
            "kind": "file",
            "size": 4,
            "sha256": hashlib.sha256(b"libR").hexdigest(),
            "architectures": executable["architectures"],
        },
        {
            "path": "Contents/Frameworks/R.framework/Resources/etc/Renviron",
            "kind": "file",
            "size": 8,
            "sha256": hashlib.sha256(b"Renviron").hexdigest(),
            "architectures": [],
        },
        {
            "path": "Contents/Frameworks/R.framework/Resources/include/R.h",
            "kind": "file",
            "size": 3,
            "sha256": hashlib.sha256(b"R.h").hexdigest(),
            "architectures": [],
        },
        {
            "path": "Contents/Frameworks/PyQt6/Qt6/lib/QtCore.framework/QtCore",
            "kind": "symlink",
            "size": 17,
            "link_target": "Versions/A/QtCore",
            "resolved_path": "Contents/Frameworks/PyQt6/Qt6/lib/QtCore.framework/Versions/A/QtCore",
        },
        {
            "path": "Contents/Frameworks/QtCore",
            "kind": "file",
            "size": 7,
            "sha256": hashlib.sha256(b"qt core").hexdigest(),
            "architectures": executable["architectures"],
        },
        {
            "path": "Contents/Resources/QtCore",
            "kind": "file",
            "size": 7,
            "sha256": hashlib.sha256(b"qt core").hexdigest(),
            "architectures": executable["architectures"],
        },
        {
            "path": "Contents/Resources/PyQt6/Qt6/translations/qt_en.qm",
            "kind": "file",
            "size": 11,
            "sha256": hashlib.sha256(b"translation").hexdigest(),
            "architectures": [],
        },
        {
            "path": "Contents/Frameworks/PyQt6/Qt6/translations",
            "kind": "symlink",
            "size": 41,
            "link_target": "../../../Resources/PyQt6/Qt6/translations",
            "resolved_path": "Contents/Resources/PyQt6/Qt6/translations",
        },
        {
            "path": "Contents/Resources/PyQt6/Qt6/lib",
            "kind": "symlink",
            "size": 35,
            "link_target": "../../../Frameworks/PyQt6/Qt6/lib",
            "resolved_path": "Contents/Frameworks/PyQt6/Qt6/lib",
        },
        {
            "path": "Contents/Resources/PyQt6/Qt6/plugins",
            "kind": "symlink",
            "size": 39,
            "link_target": "../../../Frameworks/PyQt6/Qt6/plugins",
            "resolved_path": "Contents/Frameworks/PyQt6/Qt6/plugins",
        },
    ]
    inventory = {
        "schema_version": 2,
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
            "--distpath",
            str((root / "dist").resolve()),
            "--workpath",
            str((root / "work").resolve()),
            str((root / "packaging/pyinstaller/qt6-macos-feasibility.spec").resolve()),
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


def test_macho_architecture_parser_reads_thin_and_universal_without_lipo(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "rc_metastudio.qt6_macos_feasibility.subprocess.run",
        lambda *_args, **_kwargs: pytest.fail("Mach-O parsing must not invoke lipo"),
    )
    for index, magic in enumerate((b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe")):
        thin = tmp_path / f"thin64-{index}"
        thin.write_bytes(_thin_macho(0x0100000C, 0, magic))
        assert _archs(thin) == ["arm64"]
    for index, magic in enumerate((b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe")):
        unsupported_thin = tmp_path / f"thin32-{index}"
        unsupported_thin.write_bytes(_thin_macho(7, 3, magic))
        with pytest.raises(EvidenceError, match="unsupported CPU type"):
            _archs(unsupported_thin)
    for index, magic in enumerate(
        (
            b"\xca\xfe\xba\xbe",
            b"\xbe\xba\xfe\xca",
            b"\xca\xfe\xba\xbf",
            b"\xbf\xba\xfe\xca",
        )
    ):
        universal = tmp_path / f"universal-{index}"
        universal.write_bytes(
            _fat_macho(
                [
                    (0x01000007, 3, _thin_macho(0x01000007, 3)),
                    (0x0100000C, 0, _thin_macho(0x0100000C, 0)),
                ],
                magic,
            )
        )
        assert _archs(universal) == ["arm64", "x86_64"]


def test_macho_architecture_parser_rejects_malformed_or_tampered_files(tmp_path):
    valid_arm = _thin_macho(0x0100000C, 0)
    malformed = [
        b"",
        b"not-macho",
        b"\xcf\xfa\xed\xfe" + (0x0100000C).to_bytes(4, "little"),
        b"\xcf\xfa\xed\xfe" + (1).to_bytes(4, "little") + bytes(24),
        b"\xca\xfe\xba\xbe" + (17).to_bytes(4, "big"),
        b"\xca\xfe\xba\xbe" + (2).to_bytes(4, "big") + bytes(20),
        (
            b"\xca\xfe\xba\xbe"
            + (1).to_bytes(4, "big")
            + (0x0100000C).to_bytes(4, "big")
            + bytes(4)
            + (4096).to_bytes(4, "big")
            + len(valid_arm).to_bytes(4, "big")
            + bytes(4)
        ),
        _fat_macho([(0x01000007, 3, valid_arm)]),
        _fat_macho(
            [
                (0x0100000C, 0, valid_arm),
                (0x0100000C, 0, valid_arm),
            ]
        ),
    ]
    for index, payload in enumerate(malformed):
        path = tmp_path / str(index)
        path.write_bytes(payload)
        with pytest.raises(EvidenceError, match="Mach-O file"):
            _archs(path)


def test_macho_architecture_parser_rejects_subtype_and_fat64_tampering(tmp_path):
    malformed = [
        (_thin_macho(0x01000007, 8), "unsupported x86_64 CPU subtype"),
        (_thin_macho(0x01000007, 0x40000003), "unsupported x86_64 CPU subtype"),
        (
            _fat_macho([(0x01000007, 3, _thin_macho(0x01000007, 0x80000003))]),
            "mismatched fat slice CPU identity",
        ),
        (
            _fat_macho([(0x01000007, 3, _thin_macho(0x01000007, 8))]),
            "unsupported x86_64 CPU subtype",
        ),
        (
            _fat_macho(
                [(0x0100000C, 0, _thin_macho(0x0100000C, 0))],
                b"\xca\xfe\xba\xbf",
                reserved=1,
            ),
            "nonzero fat64 reserved field",
        ),
    ]
    for index, (payload, expected_error) in enumerate(malformed):
        path = tmp_path / str(index)
        path.write_bytes(payload)
        with pytest.raises(EvidenceError, match=expected_error):
            _archs(path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda data: data["runner"].__setitem__("rosetta_translated", True),
            "Rosetta",
        ),
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


def test_native_macos_workflow_uses_one_ordered_native_package_matrix():
    workflow_path = ROOT / ".github/workflows/package-target.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    job = workflow["jobs"]["package"]
    targets = job["strategy"]["matrix"]["include"]

    assert targets == [
        {
            "target": "macos-x64",
            "architecture": "x64",
            "runner": "macos-15-intel",
            "artifact": "RCMetaStudio-macos-x64",
        },
        {
            "target": "macos-arm64",
            "architecture": "arm64",
            "runner": "macos-15",
            "artifact": "RCMetaStudio-macos-arm64",
        },
    ]
    assert job["strategy"]["fail-fast"] is False
    assert job["strategy"]["max-parallel"] == 2
    assert job["runs-on"] == "${{ matrix.runner }}"
    steps = {step["name"]: step for step in job["steps"]}
    assert (
        steps["Upload immutable unsigned package"]["with"]["if-no-files-found"]
        == "error"
    )
    evidence_upload = steps["Upload bring-up evidence and failure diagnostics"]
    assert evidence_upload["if"] == "${{ always() }}"
    assert evidence_upload["with"]["if-no-files-found"] == "warn"

    script_steps = "\n".join(str(step.get("run", "")) for step in job["steps"])
    assert "aqt install-qt mac desktop" in script_steps
    assert "qt6_macos_feasibility.py resolve-rcc" in script_steps
    assert "scripts/package-macos.sh --architecture" in script_steps
    assert "continue-on-error" not in script_steps
    assert not (ROOT / ".github/workflows/qt6-macos-feasibility.yml").exists()

    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "aqtinstall==3.3.0" in metadata["dependency-groups"]["dev"]


def test_locked_rpy2_runtime_discovers_concrete_native_extensions():
    extensions = discover_rpy2_native_extensions()

    assert extensions
    assert all(path.is_file() for path in extensions)
    assert all(path.suffix.lower() in {".dylib", ".pyd", ".so"} for path in extensions)
    assert any(
        "rinterface" in path.name.lower() or "rinterface_lib" in path.as_posix()
        for path in extensions
    )


def test_macos_sdk_rcc_discovery_uses_qt6_libexec_layout_and_fails_ambiguous(
    tmp_path,
):
    sdk_root = tmp_path / "6.11.1/macos"
    libexec_rcc = sdk_root / "libexec/rcc"
    libexec_rcc.parent.mkdir(parents=True)
    libexec_rcc.write_bytes(b"official macOS rcc")

    assert discover_macos_rcc(sdk_root) == libexec_rcc.resolve()

    bin_rcc = sdk_root / "bin/rcc"
    bin_rcc.parent.mkdir()
    bin_rcc.write_bytes(b"different rcc")
    with pytest.raises(RuntimeError, match="ambiguous"):
        discover_macos_rcc(sdk_root)

    libexec_rcc.unlink()
    bin_rcc.unlink()
    (sdk_root / "unexpected/rcc").parent.mkdir()
    (sdk_root / "unexpected/rcc").write_bytes(b"unrecognized")
    with pytest.raises(RuntimeError, match="recognized layout"):
        discover_macos_rcc(sdk_root)


def test_macos_sdk_rcc_discovery_supports_every_allowlisted_layout(tmp_path):
    layouts = [
        "libexec/rcc",
        "libexec/rcc.app/Contents/MacOS/rcc",
        "bin/rcc",
        "bin/rcc.app/Contents/MacOS/rcc",
    ]
    for index, relative in enumerate(layouts):
        sdk_root = tmp_path / str(index) / "6.11.1/macos"
        candidate = sdk_root / relative
        candidate.parent.mkdir(parents=True)
        candidate.write_bytes(relative.encode())

        assert discover_macos_rcc(sdk_root) == candidate.resolve()


def test_macos_sdk_rcc_discovery_deduplicates_aliases_and_rejects_escape(
    tmp_path,
):
    sdk_root = tmp_path / "sdk/6.11.1/macos"
    libexec_rcc = sdk_root / "libexec/rcc"
    libexec_rcc.parent.mkdir(parents=True)
    libexec_rcc.write_bytes(b"one official rcc")
    bin_rcc = sdk_root / "bin/rcc"
    bin_rcc.parent.mkdir()
    try:
        bin_rcc.symlink_to(libexec_rcc)
    except OSError as exc:
        pytest.skip(f"file symlinks unavailable: {exc}")

    assert discover_macos_rcc(sdk_root) == libexec_rcc.resolve()

    bin_rcc.unlink()
    outside = tmp_path / "outside-rcc"
    outside.write_bytes(b"escaping rcc")
    bin_rcc.symlink_to(outside)
    with pytest.raises(RuntimeError, match="escapes the declared SDK root"):
        discover_macos_rcc(sdk_root)


def test_github_env_export_rejects_newlines_and_preserves_exact_utf8(tmp_path):
    github_env = tmp_path / "github-env"
    value = str((tmp_path / "Qt SDK/libexec/rcc-µ").resolve())
    append_github_env(github_env, "RCMS_QT6_RCC", value)

    assert github_env.read_bytes() == f"RCMS_QT6_RCC={value}\n".encode("utf-8")
    for unsafe in (f"{value}\nINJECTED=1", f"{value}\rINJECTED=1"):
        with pytest.raises(RuntimeError, match="CR or LF"):
            append_github_env(github_env, "RCMS_QT6_RCC", unsafe)
    assert github_env.read_bytes() == f"RCMS_QT6_RCC={value}\n".encode("utf-8")


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
    (
        missing_root
        / missing["native_components"]["rcc"]["retained"][0]["retained_path"]
    ).unlink()
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


def test_pyinstaller_plan_accepts_native_macos_paths_when_validated_on_any_host(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "rc_metastudio.qt6_macos_feasibility._archs", lambda _path: ["arm64"]
    )
    evidence = _valid_evidence()
    _materialize_retained_evidence(evidence, tmp_path)
    record = evidence["package"]["build_plan"]
    plan_path = tmp_path / record["retained_path"]
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    arguments = plan["arguments"]
    arguments[3] = "/Users/runner/work/app/dist"
    arguments[5] = "/Users/runner/work/app/work"
    arguments[6] = (
        "/Users/runner/work/app/packaging/pyinstaller/qt6-macos-feasibility.spec"
    )
    plan_path.write_text(json.dumps(plan, sort_keys=True), encoding="utf-8")
    record["size"] = plan_path.stat().st_size
    record["sha256"] = hashlib.sha256(plan_path.read_bytes()).hexdigest()

    validate_evidence(evidence, "macos-arm64", evidence_dir=tmp_path)


def test_pyinstaller_plan_rejects_noncanonical_feasibility_specification(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "rc_metastudio.qt6_macos_feasibility._archs", lambda _path: ["arm64"]
    )
    unsafe_specifications = [
        "relative/qt6-macos-feasibility.spec",
        r"C:relative\qt6-macos-feasibility.spec",
        "/workspace/alternate.spec",
        r"C:\work\alternate.spec",
    ]
    for index, specification in enumerate(unsafe_specifications):
        evidence = _valid_evidence()
        root = tmp_path / str(index)
        _materialize_retained_evidence(evidence, root)
        record = evidence["package"]["build_plan"]
        plan_path = root / record["retained_path"]
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["arguments"][6] = specification
        plan_path.write_text(json.dumps(plan, sort_keys=True), encoding="utf-8")
        record["size"] = plan_path.stat().st_size
        record["sha256"] = hashlib.sha256(plan_path.read_bytes()).hexdigest()

        with pytest.raises(EvidenceError, match="unexpected manual inputs"):
            validate_evidence(evidence, "macos-arm64", evidence_dir=root)


def test_deployment_inventory_rejects_incoherent_qt_payloads_and_aliases(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "rc_metastudio.qt6_macos_feasibility._archs", lambda _path: ["arm64"]
    )

    def second_payload(files):
        files.append(
            {
                "path": "Contents/Frameworks/SecondQt/QtCore",
                "kind": "file",
                "size": 6,
                "sha256": hashlib.sha256(b"second").hexdigest(),
                "architectures": ["arm64"],
            }
        )

    def alternate_binding(files):
        files.append(
            {
                "path": "Contents/Frameworks/PySide6/QtCore.abi3.so",
                "kind": "file",
                "size": 7,
                "sha256": hashlib.sha256(b"pyside6").hexdigest(),
                "architectures": ["arm64"],
            }
        )

    def mismatched_alias_hash(files):
        next(item for item in files if item["path"] == "Contents/Frameworks/QtCore")[
            "sha256"
        ] = "1" * 64

    def mismatched_alias_architecture(files):
        next(item for item in files if item["path"] == "Contents/Resources/QtCore")[
            "architectures"
        ] = ["x86_64"]

    def missing_authoritative_root(files):
        files[:] = [
            item
            for item in files
            if not item["path"].startswith("Contents/Frameworks/PyQt6/Qt6/")
        ]

    def multiple_cocoa_plugins(files):
        files.append(
            {
                "path": "Contents/Frameworks/Other/libqcocoa.dylib",
                "kind": "file",
                "size": 5,
                "sha256": hashlib.sha256(b"other").hexdigest(),
                "architectures": ["arm64"],
            }
        )

    def escaping_qt_alias(files):
        next(
            item
            for item in files
            if item["path"] == "Contents/Frameworks/PyQt6/Qt6/translations"
        )["resolved_path"] = "Contents/Other/translations"

    def add_qt_file(files, path):
        files.append(
            {
                "path": path,
                "kind": "file",
                "size": len(path),
                "sha256": hashlib.sha256(path.encode()).hexdigest(),
                "architectures": ["arm64"],
            }
        )

    def qt6_unversioned_dylib(files):
        add_qt_file(files, "Contents/Frameworks/libQt6Core.dylib")

    def qt6_versioned_dylib(files):
        add_qt_file(files, "Contents/Frameworks/libQt6Core.6.dylib")

    def second_framework(files):
        add_qt_file(
            files,
            "Contents/Frameworks/QtGui.framework/Versions/A/QtGui",
        )

    def second_platform_plugin(files):
        add_qt_file(
            files,
            "Contents/Frameworks/Other/plugins/platforms/libqoffscreen.dylib",
        )

    def pyside_platform_plugin(files):
        add_qt_file(
            files,
            "Contents/Frameworks/PySide6/Qt/plugins/platforms/libqcocoa.dylib",
        )

    def authoritative_qt_dylib(files):
        add_qt_file(
            files,
            "Contents/Frameworks/PyQt6/Qt6/lib/libQt6Core.dylib",
        )

    def displaced_offscreen_plugin(files):
        add_qt_file(files, "Contents/Frameworks/Other/libqoffscreen.dylib")

    def lowercase_qt_dylib(files):
        add_qt_file(files, "Contents/Frameworks/libqt6core.dylib")

    def unprefixed_qt_dylib(files):
        add_qt_file(files, "Contents/Frameworks/QtCore.dylib")

    def shiboken_runtime(files):
        add_qt_file(files, "Contents/Frameworks/libshiboken6.abi3.6.10.dylib")

    def pyside_runtime(files):
        add_qt_file(files, "Contents/Frameworks/libpyside6.abi3.6.10.dylib")

    def case_variant_pyqt6_root(files):
        add_qt_file(files, "Contents/Frameworks/pyqt6/qtcore.abi3.so")

    def shiboken_package_extension(files):
        add_qt_file(files, "Contents/Frameworks/shiboken6/Shiboken.abi3.so")

    def top_level_shiboken_extension(files):
        add_qt_file(files, "Contents/Frameworks/Shiboken.abi3.so")

    def shiboken6_extension(files):
        add_qt_file(files, "Contents/Frameworks/shiboken6.abi3.so")

    def libshiboken6_extension(files):
        add_qt_file(files, "Contents/Frameworks/libshiboken6.abi3.so")

    def debug_qt_dylib(files):
        add_qt_file(files, "Contents/Frameworks/QtCore_debug.dylib")

    def debug_versioned_qt_dylib(files):
        add_qt_file(files, "Contents/Frameworks/libQt6Core_debug.6.abi3.dylib")

    def shiboken_cpython_extension(files):
        add_qt_file(files, "Contents/Frameworks/Shiboken.cpython-311-darwin.so")

    def shiboken_debug_runtime(files):
        add_qt_file(files, "Contents/Frameworks/libshiboken6_debug.dylib")

    def shiboken_debug_versioned_extension(files):
        add_qt_file(files, "Contents/Frameworks/libshiboken_debug.6.10.so")

    mutations = [
        second_payload,
        alternate_binding,
        mismatched_alias_hash,
        mismatched_alias_architecture,
        missing_authoritative_root,
        multiple_cocoa_plugins,
        escaping_qt_alias,
        qt6_unversioned_dylib,
        qt6_versioned_dylib,
        second_framework,
        second_platform_plugin,
        pyside_platform_plugin,
        authoritative_qt_dylib,
        displaced_offscreen_plugin,
        lowercase_qt_dylib,
        unprefixed_qt_dylib,
        shiboken_runtime,
        pyside_runtime,
        case_variant_pyqt6_root,
        shiboken_package_extension,
        top_level_shiboken_extension,
        shiboken6_extension,
        libshiboken6_extension,
        debug_qt_dylib,
        debug_versioned_qt_dylib,
        shiboken_cpython_extension,
        shiboken_debug_runtime,
        shiboken_debug_versioned_extension,
    ]
    for index, mutation in enumerate(mutations):
        evidence = _valid_evidence()
        root = tmp_path / str(index)
        _materialize_retained_evidence(evidence, root)
        record = evidence["package"]["inventory"]
        inventory_path = root / record["retained_path"]
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        mutation(inventory["files"])
        inventory["file_count"] = len(inventory["files"])
        inventory["total_bytes"] = sum(item["size"] for item in inventory["files"])
        inventory_path.write_text(
            json.dumps(inventory, sort_keys=True), encoding="utf-8"
        )
        record["size"] = inventory_path.stat().st_size
        record["sha256"] = hashlib.sha256(inventory_path.read_bytes()).hexdigest()

        with pytest.raises(EvidenceError):
            validate_evidence(evidence, "macos-arm64", evidence_dir=root)


def test_deployment_inventory_requires_exact_qt_directory_aliases(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "rc_metastudio.qt6_macos_feasibility._archs", lambda _path: ["arm64"]
    )

    def wrong_target(files):
        alias = next(
            item
            for item in files
            if item["path"] == "Contents/Frameworks/PyQt6/Qt6/translations"
        )
        alias["link_target"] = "plugins"
        alias["resolved_path"] = "Contents/Frameworks/PyQt6/Qt6/plugins"

    def escaping_target(files):
        alias = next(
            item
            for item in files
            if item["path"] == "Contents/Frameworks/PyQt6/Qt6/translations"
        )
        alias["link_target"] = "../../../../../outside"

    def extra_directory_alias(files):
        files.append(
            {
                "path": "Contents/Frameworks/PyQt6/Qt6/resources",
                "kind": "symlink",
                "size": 41,
                "link_target": "../../../Resources/PyQt6/Qt6/translations",
                "resolved_path": "Contents/Resources/PyQt6/Qt6/translations",
            }
        )

    def missing_one_alias(files):
        files[:] = [
            item
            for item in files
            if item["path"] != "Contents/Frameworks/PyQt6/Qt6/translations"
        ]

    def missing_all_aliases(files):
        aliases = {
            "Contents/Frameworks/PyQt6/Qt6/translations",
            "Contents/Resources/PyQt6/Qt6/lib",
            "Contents/Resources/PyQt6/Qt6/plugins",
        }
        files[:] = [item for item in files if item["path"] not in aliases]

    def regular_file_substitution(files):
        alias = next(
            item
            for item in files
            if item["path"] == "Contents/Frameworks/PyQt6/Qt6/translations"
        )
        alias.clear()
        alias.update(
            {
                "path": "Contents/Frameworks/PyQt6/Qt6/translations",
                "kind": "file",
                "size": 12,
                "sha256": hashlib.sha256(b"translations").hexdigest(),
                "architectures": [],
            }
        )

    for index, (mutation, expected_error) in enumerate(
        [
            (wrong_target, "targets the wrong canonical root"),
            (escaping_target, "escapes the virtual bundle"),
            (extra_directory_alias, "unrecognized payload inside the authoritative"),
            (missing_one_alias, "incomplete Qt directory alias set"),
            (missing_all_aliases, "incomplete Qt directory alias set"),
            (regular_file_substitution, "must be a symlink"),
        ]
    ):
        evidence = _valid_evidence()
        root = tmp_path / str(index)
        _materialize_retained_evidence(evidence, root)
        record = evidence["package"]["inventory"]
        inventory_path = root / record["retained_path"]
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        mutation(inventory["files"])
        inventory["file_count"] = len(inventory["files"])
        inventory["total_bytes"] = sum(item["size"] for item in inventory["files"])
        inventory_path.write_text(
            json.dumps(inventory, sort_keys=True), encoding="utf-8"
        )
        record["size"] = inventory_path.stat().st_size
        record["sha256"] = hashlib.sha256(inventory_path.read_bytes()).hexdigest()

        with pytest.raises(EvidenceError, match=expected_error):
            validate_evidence(evidence, "macos-arm64", evidence_dir=root)


def test_deployment_inventory_rejects_displaced_runtime_symlinks(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "rc_metastudio.qt6_macos_feasibility._archs", lambda _path: ["arm64"]
    )
    forged_paths = [
        "Contents/Frameworks/shiboken6/Shiboken.abi3.so",
        "Contents/Frameworks/Shiboken.abi3.so",
        "Contents/Frameworks/shiboken6.abi3.so",
        "Contents/Frameworks/libshiboken6.abi3.so",
        "Contents/Frameworks/QtCore_debug.dylib",
        "Contents/Frameworks/libQt6Core_debug.6.abi3.dylib",
        "Contents/Frameworks/Shiboken.cpython-311-darwin.so",
        "Contents/Frameworks/libshiboken6_debug.dylib",
        "Contents/Frameworks/libshiboken_debug.6.10.so",
    ]
    for index, forged_path in enumerate(forged_paths):
        evidence = _valid_evidence()
        root = tmp_path / str(index)
        _materialize_retained_evidence(evidence, root)
        record = evidence["package"]["inventory"]
        inventory_path = root / record["retained_path"]
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        link_target = posixpath.relpath(
            "Contents/Resources/QtCore", posixpath.dirname(forged_path)
        )
        inventory["files"].append(
            {
                "path": forged_path,
                "kind": "symlink",
                "size": len(link_target.encode()),
                "link_target": link_target,
                "resolved_path": "Contents/Resources/QtCore",
            }
        )
        inventory["file_count"] = len(inventory["files"])
        inventory["total_bytes"] = sum(item["size"] for item in inventory["files"])
        inventory_path.write_text(
            json.dumps(inventory, sort_keys=True), encoding="utf-8"
        )
        record["size"] = inventory_path.stat().st_size
        record["sha256"] = hashlib.sha256(inventory_path.read_bytes()).hexdigest()

        with pytest.raises(EvidenceError, match="unrecognized Qt deployment symlink"):
            validate_evidence(evidence, "macos-arm64", evidence_dir=root)


def test_deployment_inventory_allows_unrelated_shiboken_prose_and_data(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "rc_metastudio.qt6_macos_feasibility._archs", lambda _path: ["arm64"]
    )
    evidence = _valid_evidence()
    _materialize_retained_evidence(evidence, tmp_path)
    record = evidence["package"]["inventory"]
    inventory_path = tmp_path / record["retained_path"]
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    for path in (
        "Contents/Resources/Shiboken.cpython-311-darwin.txt",
        "Contents/Resources/libshiboken6_debug.json",
    ):
        payload = path.encode()
        inventory["files"].append(
            {
                "path": path,
                "kind": "file",
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "architectures": [],
            }
        )
    inventory["file_count"] = len(inventory["files"])
    inventory["total_bytes"] = sum(item["size"] for item in inventory["files"])
    inventory_path.write_text(json.dumps(inventory, sort_keys=True), encoding="utf-8")
    record["size"] = inventory_path.stat().st_size
    record["sha256"] = hashlib.sha256(inventory_path.read_bytes()).hexdigest()

    validate_evidence(evidence, "macos-arm64", evidence_dir=tmp_path)


def test_deployment_inventory_rejects_noncanonical_record_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "rc_metastudio.qt6_macos_feasibility._archs", lambda _path: ["arm64"]
    )
    forged_paths = [
        "",
        "/Contents/MacOS/Qt6MacFeasibility",
        "C:/Contents/MacOS/Qt6MacFeasibility",
        "Contents\\MacOS\\Qt6MacFeasibility",
        "Contents/MacOS/Qt6MacFeasibility\0suffix",
        "Contents//MacOS/Qt6MacFeasibility",
        "Contents/./MacOS/Qt6MacFeasibility",
        "Contents/../MacOS/Qt6MacFeasibility",
        "Contents/MacOS/Qt6MacFeasibility/",
    ]
    for index, forged_path in enumerate(forged_paths):
        evidence = _valid_evidence()
        root = tmp_path / str(index)
        _materialize_retained_evidence(evidence, root)
        record = evidence["package"]["inventory"]
        inventory_path = root / record["retained_path"]
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        inventory["files"][0]["path"] = forged_path
        inventory_path.write_text(
            json.dumps(inventory, sort_keys=True), encoding="utf-8"
        )
        record["size"] = inventory_path.stat().st_size
        record["sha256"] = hashlib.sha256(inventory_path.read_bytes()).hexdigest()

        with pytest.raises(EvidenceError, match="record path"):
            validate_evidence(evidence, "macos-arm64", evidence_dir=root)


def test_deployment_inventory_rejects_noncanonical_resolved_paths(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "rc_metastudio.qt6_macos_feasibility._archs", lambda _path: ["arm64"]
    )
    forged_paths = [
        "/Contents/Frameworks/PyQt6",
        "C:/Contents/Frameworks/PyQt6",
        "Contents\\Frameworks\\PyQt6",
        "Contents//Frameworks/PyQt6",
        "Contents/./Frameworks/PyQt6",
        "Contents/../Frameworks/PyQt6",
    ]
    for index, forged_path in enumerate(forged_paths):
        evidence = _valid_evidence()
        root = tmp_path / str(index)
        _materialize_retained_evidence(evidence, root)
        record = evidence["package"]["inventory"]
        inventory_path = root / record["retained_path"]
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        alias = next(
            item
            for item in inventory["files"]
            if item["path"] == "Contents/Frameworks/PyQt6/Qt6/translations"
        )
        alias["resolved_path"] = forged_path
        inventory_path.write_text(
            json.dumps(inventory, sort_keys=True), encoding="utf-8"
        )
        record["size"] = inventory_path.stat().st_size
        record["sha256"] = hashlib.sha256(inventory_path.read_bytes()).hexdigest()

        with pytest.raises(EvidenceError, match="resolved path"):
            validate_evidence(evidence, "macos-arm64", evidence_dir=root)


def test_deployment_inventory_resolves_a_long_symlink_chain_iteratively(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "rc_metastudio.qt6_macos_feasibility._archs", lambda _path: ["arm64"]
    )
    evidence = _valid_evidence()
    _materialize_retained_evidence(evidence, tmp_path)
    record = evidence["package"]["inventory"]
    inventory_path = tmp_path / record["retained_path"]
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    target = "Contents/Resources/QtCore"
    for index in range(1_100):
        link_target = f"{index + 1:04d}" if index < 1_099 else "../QtCore"
        inventory["files"].append(
            {
                "path": f"Contents/Resources/chain/{index:04d}",
                "kind": "symlink",
                "size": len(link_target.encode()),
                "link_target": link_target,
                "resolved_path": target,
            }
        )
    inventory["file_count"] = len(inventory["files"])
    inventory["total_bytes"] = sum(item["size"] for item in inventory["files"])
    inventory_path.write_text(json.dumps(inventory, sort_keys=True), encoding="utf-8")
    record["size"] = inventory_path.stat().st_size
    record["sha256"] = hashlib.sha256(inventory_path.read_bytes()).hexdigest()

    validate_evidence(evidence, "macos-arm64", evidence_dir=tmp_path)


def test_deployment_inventory_resolves_symlink_graph_and_rejects_forgery(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "rc_metastudio.qt6_macos_feasibility._archs", lambda _path: ["arm64"]
    )

    def forged_escape(files):
        alias = next(
            item
            for item in files
            if item["path"] == "Contents/Frameworks/PyQt6/Qt6/translations"
        )
        alias["link_target"] = "../../../../../outside"

    def wrong_component(files):
        files.append(
            {
                "path": "Contents/Frameworks/PyQt6/Qt6/lib/QtGui.framework/Versions/A/QtGui",
                "kind": "file",
                "size": 5,
                "sha256": hashlib.sha256(b"qtgui").hexdigest(),
                "architectures": ["arm64"],
            }
        )
        alias = next(
            item
            for item in files
            if item["path"]
            == "Contents/Frameworks/PyQt6/Qt6/lib/QtCore.framework/QtCore"
        )
        alias["link_target"] = "../QtGui.framework/Versions/A/QtGui"
        alias["resolved_path"] = (
            "Contents/Frameworks/PyQt6/Qt6/lib/QtGui.framework/Versions/A/QtGui"
        )

    def cyclic(files):
        files.extend(
            [
                {
                    "path": "Contents/Resources/cycle-a",
                    "kind": "symlink",
                    "size": 7,
                    "link_target": "cycle-b",
                    "resolved_path": "Contents/Resources/cycle-b",
                },
                {
                    "path": "Contents/Resources/cycle-b",
                    "kind": "symlink",
                    "size": 7,
                    "link_target": "cycle-a",
                    "resolved_path": "Contents/Resources/cycle-a",
                },
            ]
        )

    def dangling(files):
        files.append(
            {
                "path": "Contents/Resources/dangling",
                "kind": "symlink",
                "size": 7,
                "link_target": "missing",
                "resolved_path": "Contents/Resources/missing",
            }
        )

    def absolute_target(files):
        alias = next(
            item
            for item in files
            if item["path"] == "Contents/Frameworks/PyQt6/Qt6/translations"
        )
        alias["link_target"] = "/Contents/Resources/PyQt6/Qt6/translations"

    def normalization_trick(files):
        alias = next(
            item
            for item in files
            if item["path"] == "Contents/Frameworks/PyQt6/Qt6/translations"
        )
        alias["link_target"] = "../../.././Resources/PyQt6/Qt6/translations"

    for index, (mutation, expected_error) in enumerate(
        [
            (forged_escape, "escapes the virtual bundle"),
            (wrong_component, "wrong canonical component"),
            (cyclic, "cyclic symlink"),
            (dangling, "dangling symlink"),
            (absolute_target, "unsafe symlink target"),
            (normalization_trick, "unsafe symlink target"),
        ]
    ):
        evidence = _valid_evidence()
        root = tmp_path / str(index)
        _materialize_retained_evidence(evidence, root)
        record = evidence["package"]["inventory"]
        inventory_path = root / record["retained_path"]
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        mutation(inventory["files"])
        inventory["file_count"] = len(inventory["files"])
        inventory["total_bytes"] = sum(item["size"] for item in inventory["files"])
        inventory_path.write_text(
            json.dumps(inventory, sort_keys=True), encoding="utf-8"
        )
        record["size"] = inventory_path.stat().st_size
        record["sha256"] = hashlib.sha256(inventory_path.read_bytes()).hexdigest()

        with pytest.raises(EvidenceError, match=expected_error):
            validate_evidence(evidence, "macos-arm64", evidence_dir=root)
