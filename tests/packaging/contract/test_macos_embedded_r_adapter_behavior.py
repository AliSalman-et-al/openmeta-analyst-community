import json
import builtins
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import types
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _load_script(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_embedded_r_adapter():
    return _load_script(
        "macos_embedded_r_adapter_behavior", "scripts/macos_embedded_r_adapter.py"
    )


def load_inspector():
    return _load_script(
        "inspect_macos_deployment_behavior", "scripts/inspect_macos_deployment.py"
    )


def _framework(root: Path) -> Path:
    framework = root / "R.framework"
    resources = framework / "Versions/4.6-x86_64/Resources"
    (resources / "lib").mkdir(parents=True)
    (resources / "bin").mkdir()
    (resources / "lib/libR.dylib").write_bytes(b"libR")
    (resources / "bin/R").write_text("#!/bin/sh\n", encoding="utf-8")
    (framework / "Versions/Current").symlink_to(
        Path("4.6-x86_64"), target_is_directory=True
    )
    (framework / "Resources").symlink_to(
        Path("Versions/Current/Resources"), target_is_directory=True
    )
    (framework / "R").symlink_to(Path("Versions/Current/R"))
    (framework / "Versions/4.6-x86_64/R").symlink_to(Path("Resources/lib/libR.dylib"))
    (resources / "R").symlink_to(Path("bin/R"))
    available = resources / "fontconfig/fonts/conf.avail"
    active = resources / "fontconfig/fonts/conf.d"
    available.mkdir(parents=True)
    active.mkdir()
    for index in range(17):
        target = available / f"{index}.conf"
        target.write_text("font\n", encoding="utf-8")
        (active / target.name).symlink_to(
            f"/Library/Frameworks/R.framework/Resources/fontconfig/fonts/conf.avail/{target.name}"
        )
    return framework


def test_adapter_relocates_bridge_and_rejects_displaced_libr(tmp_path, monkeypatch):
    adapter = load_embedded_r_adapter()
    app = tmp_path / "RCMetaStudio.app"
    framework = _framework(app / "Contents/Frameworks")
    bridge = app / "Contents/Frameworks/python/_rinterface_cffi_api.so"
    bridge.parent.mkdir(parents=True)
    bridge.write_bytes(b"bridge")
    dependency = ["/Library/Frameworks/R.framework/Resources/lib/libR.dylib"]
    monkeypatch.setattr(adapter, "is_macho_candidate", lambda path: path.is_file())
    monkeypatch.setattr(adapter, "architectures", lambda _path: ["x86_64"])
    monkeypatch.setattr(adapter, "dependencies", lambda _path: list(dependency))

    def run(*args, **_kwargs):
        if args[:2] == ("install_name_tool", "-change"):
            dependency[:] = [args[3]]
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(adapter, "_run", run)
    output = tmp_path / "bridge.json"
    adapter.relocate_bridge(framework, bridge, "x86_64", output)
    assert json.loads(output.read_text(encoding="utf-8"))["r_dependency"].startswith(
        "@loader_path/"
    )
    monkeypatch.setattr(adapter, "audit_symlinks", lambda _root: [])
    monkeypatch.setattr(
        adapter,
        "macho_inventory",
        lambda *_: [{"path": "libR", "install_id": None, "dependencies": []}],
    )
    monkeypatch.setattr(adapter, "validate_relocated_inventory", lambda *_: None)
    adapter.post_app_gate(app, "x86_64", tmp_path / "post.json")
    displaced = app / "Contents/Frameworks/displaced/libR.dylib"
    displaced.parent.mkdir()
    displaced.symlink_to(framework / "Resources/lib/libR.dylib")
    with pytest.raises(adapter.AdapterError, match="duplicate or displaced"):
        adapter.post_app_gate(app, "x86_64", tmp_path / "post-bad.json")


def test_host_binary_filter_and_unsigned_graph_fail_closed(tmp_path, monkeypatch):
    adapter = load_embedded_r_adapter()
    retained = adapter.filter_pyinstaller_r_binaries(
        [
            ("keep", str(tmp_path / "keep.dylib"), "BINARY"),
            ("R", "/Library/Frameworks/R.framework/R", "BINARY"),
        ],
        {},
    )
    assert [item[0] for item in retained] == ["keep"]
    with pytest.raises(adapter.AdapterError, match="unmapped /opt/R"):
        adapter.filter_pyinstaller_r_binaries(
            [("bad", "/opt/R/x86_64/lib/bad.dylib", "BINARY")], {}
        )

    inspector = load_inspector()
    app = tmp_path / "Graph.app"
    executable = app / "Contents/MacOS/RCMetaStudio"
    library = app / "Contents/Frameworks/libA.dylib"
    executable.parent.mkdir(parents=True)
    library.parent.mkdir(parents=True)
    executable.write_bytes(b"exe")
    library.write_bytes(b"lib")
    monkeypatch.setattr(inspector, "_is_macho", lambda _path: True)
    monkeypatch.setattr(
        inspector,
        "require_macho_architecture",
        lambda _path, _arch: (_ for _ in ()).throw(
            inspector.MacOSDeploymentInspectionError("wrong architecture")
        ),
    )
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError, match="wrong architecture"
    ):
        inspector.inspect_unsigned_native_graph(app)
    monkeypatch.setattr(
        inspector, "require_macho_architecture", lambda _path, _arch: ["x86_64"]
    )
    monkeypatch.setattr(
        inspector,
        "_dependencies",
        lambda path: ["@loader_path/missing.dylib"] if path == executable else [],
    )
    monkeypatch.setattr(
        inspector,
        "_macho_load_metadata",
        lambda _path: {
            "install_id": None,
            "rpaths": [],
            "uuid": "a",
            "text_section_sha256": "b" * 64,
            "minimum_macos": "13.0",
        },
    )
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError, match="does not resolve uniquely"
    ):
        inspector.inspect_unsigned_native_graph(app)
    monkeypatch.setattr(inspector, "_dependencies", lambda _path: [])
    monkeypatch.setattr(
        inspector,
        "_macho_load_metadata",
        lambda _path: {
            "install_id": "@rpath/duplicate",
            "rpaths": [],
            "uuid": "a",
            "text_section_sha256": "b" * 64,
            "minimum_macos": "13.0",
        },
    )
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError,
        match="duplicate Mach-O install identity",
    ):
        inspector.inspect_unsigned_native_graph(app)


def test_host_r_isolation_state_machine_restores_exact_identity(tmp_path):
    bash = shutil.which("bash") or r"C:\Program Files\Git\bin\bash.exe"
    if not Path(bash).is_file():
        pytest.skip("bash is unavailable")
    framework = _framework(tmp_path)
    helper = Path(__file__).resolve().parents[3] / "scripts/macos_host_r_isolation.sh"
    script = r"""
to_posix() { if command -v cygpath >/dev/null 2>&1; then cygpath -u "$1"; else printf '%s\n' "$1"; fi; }
source "$(to_posix "$HELPER")"
source_path="$(to_posix "$SOURCE_FRAMEWORK")"
export RCMS_HOST_R_USE_SUDO=0
before="$(rcms_host_r_identity "$source_path")"
rcms_isolate_host_r "$source_path"
[ "$RCMS_HOST_R_STATE" = isolated ] && [ ! -e "$source_path" ] && [ -d "$RCMS_HOST_R_BACKUP" ]
mkdir "$source_path"
if rcms_restore_host_r; then exit 31; fi
rmdir "$source_path"
rcms_restore_host_r
[ "$RCMS_HOST_R_STATE" = idle ] && [ ! -e "$RCMS_HOST_R_BACKUP" ]
[ "$(rcms_host_r_identity "$source_path")" = "$before" ]
( rcms_isolate_host_r "$source_path" )
[ -d "$source_path" ]
eval "$(declare -f rcms_host_r_identity | sed '1s/rcms_host_r_identity/rcms_real_host_r_identity/')"
rcms_host_r_identity() {
  case "$1" in
    *.rcms-isolated.*) return 1 ;;
    *) rcms_real_host_r_identity "$1" ;;
  esac
}
if rcms_isolate_host_r "$source_path"; then exit 32; fi
[ "$RCMS_HOST_R_STATE" = isolated ] && [ ! -e "$source_path" ] && [ -d "$RCMS_HOST_R_BACKUP" ]
rcms_restore_host_r
[ -d "$source_path" ] && [ "$(rcms_real_host_r_identity "$source_path")" = "$before" ]
if ( rcms_isolate_host_r "$source_path" ); then exit 33; fi
[ -d "$source_path" ] && [ "$(rcms_real_host_r_identity "$source_path")" = "$before" ]
if compgen -G "${source_path}.rcms-isolated.*" >/dev/null; then exit 34; fi
"""
    completed = subprocess.run(
        [bash],
        input=script,
        text=True,
        capture_output=True,
        env={**os.environ, "HELPER": str(helper), "SOURCE_FRAMEWORK": str(framework)},
    )
    assert completed.returncode == 0, completed.stderr


def test_frozen_application_entry_configures_r_before_rpy2_import(monkeypatch):
    from rc_metastudio import __main__ as application_entry
    from rc_metastudio import meta_py_r_backend

    events = []
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("RCMS_REQUIRE_IN_PROCESS_RPY2", "1")
    monkeypatch.delenv("RCMS_STUB_BACKEND", raising=False)
    import rc_metastudio

    monkeypatch.delattr(rc_metastudio, "meta_py_r", raising=False)
    for name in tuple(sys.modules):
        if (
            name == "meta_py_r"
            or name == "rc_metastudio.meta_py_r"
            or name.startswith("rpy2")
        ):
            monkeypatch.delitem(sys.modules, name, raising=False)

    fake_runtime = types.ModuleType("r_runtime")

    def configure():
        import threading

        assert threading.current_thread() is threading.main_thread()
        assert not any(name.startswith("rpy2") for name in sys.modules)
        events.append("configure-bundled-r")

    setattr(fake_runtime, "configure_bundled_r_environment", configure)
    monkeypatch.setitem(sys.modules, "r_runtime", fake_runtime)
    fake_qt_ui = types.ModuleType("rc_metastudio.qt6_ui")
    setattr(
        fake_qt_ui, "prepare_generated_ui_imports", lambda: events.append("prepare-ui")
    )
    monkeypatch.setitem(sys.modules, "rc_metastudio.qt6_ui", fake_qt_ui)
    real_import = builtins.__import__

    def observing_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "rc_metastudio" and "meta_py_r" in (fromlist or ()):
            assert events[-1] == "configure-bundled-r"
            events.append("rpy2-import")
            fake_backend = types.ModuleType("rc_metastudio.meta_py_r")
            monkeypatch.setitem(sys.modules, "rc_metastudio.meta_py_r", fake_backend)
            monkeypatch.setitem(sys.modules, "meta_py_r", fake_backend)
            import rc_metastudio

            monkeypatch.setattr(rc_metastudio, "meta_py_r", fake_backend, raising=False)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", observing_import)
    fake_launch = types.ModuleType("launch")
    setattr(
        fake_launch,
        "start",
        lambda: (meta_py_r_backend.install_meta_py_r_backend(), 0)[1],
    )
    monkeypatch.setitem(sys.modules, "launch", fake_launch)
    assert application_entry.main() == 0
    assert events == ["prepare-ui", "configure-bundled-r", "rpy2-import"]


def test_pkgutil_signature_parser_handles_certificate_chain_and_rejectable_team():
    spec = importlib.util.spec_from_file_location(
        "pkg_signature", ROOT / "scripts" / "macos_pkg_signature.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    payload = module.parse_pkgutil_signature(
        "Package: R-4.6.1-x86_64.pkg\n   Status: signed by a certificate trusted by macOS\n   1. Developer ID Installer: R for macOS (VZLD955F6P)\n   2. Developer ID Certification Authority\n",
        "",
        0,
    )
    assert payload["team_id"] == "VZLD955F6P"
    assert payload["signer"] == "Developer ID Installer: R for macOS (VZLD955F6P)"
    assert payload["certificate"]
    assert payload["status_line"] == "signed by a certificate trusted by macOS"
    bad = module.parse_pkgutil_signature(
        "Status: signed\n   1. Developer ID Installer: Other (AAAAAAAAAA)\n", "", 0
    )
    assert bad["team_id"] != "VZLD955F6P"


def test_direct_manifest_binds_archived_inputs_and_runner(tmp_path):
    inspector = load_inspector()
    ppm_payload = b"fixture PPM archive"
    ppm_archives = [
        {
            "path": "pkg_1.0.tgz",
            "package": "pkg",
            "version": "1.0",
            "archive_url": inspector.DIRECT_R_PPM_SNAPSHOT
            + "/bin/macosx/big-sur-x86_64/contrib/4.6/pkg_1.0.tgz",
            "sha256": hashlib.sha256(ppm_payload).hexdigest(),
            "size": len(ppm_payload),
        }
    ]
    runner = json.dumps(
        {
            "schema_version": 1,
            "github_actions": "true",
            "runner_image": "macos-15-intel",
            "runner_os": "macOS",
            "runner_arch": "X64",
            "macos_version": "15.5",
            "macos_build": "24F74",
            "uname_system": "Darwin",
            "uname_machine": "x86_64",
            "python_machine": "x86_64",
        }
    ).encode()
    valid_local_runner = {
        "schema_version": 1,
        "github_actions": "false",
        "runner_image": "local",
        "runner_os": "macOS",
        "runner_arch": "x86_64",
        "macos_version": "15.5",
        "macos_build": "24F74",
        "uname_system": "Darwin",
        "uname_machine": "x86_64",
        "python_machine": "x86_64",
    }
    inspector.validate_direct_build_runner(valid_local_runner, target="macos-x64")
    inspector.validate_direct_build_runner(json.loads(runner), target="macos-x64")
    valid_local_runner["uname_machine"] = "arm64"
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError, match="native macos-x64"
    ):
        inspector.validate_direct_build_runner(valid_local_runner, target="macos-x64")
    ppm = json.dumps(
        {
            "schema_version": 1,
            "repository": inspector.DIRECT_R_PPM_SNAPSHOT,
            "archives": ppm_archives,
        }
    ).encode()
    preflight = json.dumps(
        {
            "schema_version": 1,
            "source_commit": "c" * 40,
            "pyinstaller_version": "6.21.0",
            "system": "Darwin",
            "machine": "x86_64",
            "aliases": {
                "Versions/Current": "4.6-x86_64",
                "Resources": "Versions/Current/Resources",
                "R": "Versions/Current/R",
                "Versions/4.6-x86_64/R": "Resources/lib/libR.dylib",
                "Versions/4.6-x86_64/Resources/R": "bin/R",
            },
            "passed": True,
        }
    ).encode()
    signature = json.dumps(
        {
            "schema_version": 1,
            "status": 0,
            "status_line": "signed by a certificate trusted by macOS",
            "team_id": "VZLD955F6P",
            "signer": "Developer ID Installer: R for macOS (VZLD955F6P)",
            "certificate": "Developer ID Installer: R for macOS (VZLD955F6P)",
            "stdout": "Status: signed by a certificate trusted by macOS\n   1. Developer ID Installer: R for macOS (VZLD955F6P)",
            "stderr": "",
        }
    ).encode()
    hsroc_payload = b"fixture HSROC source archive"
    rcmetar_payload = b"fixture RCMetaR source archive"
    signing_payload = b'{"identity":"ad-hoc","phase":"signing"}\n'
    post_sign_payload = b'{"identity":"ad-hoc","phase":"post-final-outer-codesign"}\n'
    hsroc_sha = hashlib.sha256(hsroc_payload).hexdigest()
    inspector.DIRECT_R_HSROC_SHA256 = hsroc_sha
    payload_by_relative = {
        relative: (
            runner
            if label == "runner_environment"
            else ppm
            if label == "ppm_archive_inventory"
            else preflight
            if label == "pyinstaller_toc_preflight_report"
            else signature
            if label == "official_r_signature"
            else signing_payload
            if label == "signing_inventory"
            else post_sign_payload
            if label == "post_sign_native_inventory"
            else hsroc_payload
            if label == "hsroc_source_archive"
            else rcmetar_payload
            if label == "rcmetar_source_archive"
            else f"evidence:{relative}\n".encode()
        )
        for label, relative in inspector.DIRECT_BUILD_INPUT_MEMBERS.items()
    }
    inputs = {
        label: {
            "sha256": hashlib.sha256(payload_by_relative[relative]).hexdigest(),
            "size": len(payload_by_relative[relative]),
        }
        for label, relative in inspector.DIRECT_BUILD_INPUT_MEMBERS.items()
    }
    manifest = {
        "schema_version": 1,
        "kind": "rc-metastudio-direct-macos-target-build",
        "target": "macos-x64",
        "source_commit": "c" * 40,
        "official_r": {
            "url": inspector.DIRECT_R_OFFICIAL_URL,
            "sha256": inspector.DIRECT_R_OFFICIAL_SHA256,
        },
        "ppm_snapshot": inspector.DIRECT_R_PPM_SNAPSHOT,
        "ppm_archives": ppm_archives,
        "rpy2_api_bridge_source_sha256": "b" * 64,
        "inputs": inputs,
        "hsroc_source_exception": {
            "name": "HSROC",
            "version": "2.1.9",
            "install_type": "source",
            "url": inspector.DIRECT_R_HSROC_URL,
            "sha256": hsroc_sha,
            "archive": {"sha256": hsroc_sha, "size": len(hsroc_payload)},
        },
        "rcmetar_source": {
            "name": "RCMetaR",
            "version": "0.2.0",
            "source_commit": "c" * 40,
            "url": "https://github.com/ResearchConsultancy/rc-metastudio/tree/"
            + "c" * 40
            + "/r/RCMetaR",
            "archive_sha256": hashlib.sha256(rcmetar_payload).hexdigest(),
            "archive": {
                "sha256": hashlib.sha256(rcmetar_payload).hexdigest(),
                "size": len(rcmetar_payload),
            },
        },
    }
    inspector.validate_direct_build_manifest(manifest, target="macos-x64")
    archive = tmp_path / "inputs.zip"
    prefix = "artifact/"
    with zipfile.ZipFile(archive, "w") as bundle:
        for relative, payload in payload_by_relative.items():
            bundle.writestr(prefix + relative, payload)
        bundle.writestr(prefix + "qualification/ppm-archives/pkg_1.0.tgz", ppm_payload)
    with zipfile.ZipFile(archive) as bundle:
        inspector.validate_direct_build_archive_inputs(
            bundle,
            prefix=prefix,
            names=bundle.namelist(),
            manifest=manifest,
            target="macos-x64",
        )
        manifest["inputs"]["adapter_script"]["sha256"] = "0" * 64
        with pytest.raises(inspector.MacOSDeploymentInspectionError, match="differs"):
            inspector.validate_direct_build_archive_inputs(
                bundle,
                prefix=prefix,
                names=bundle.namelist(),
                manifest=manifest,
                target="macos-x64",
            )
        manifest["inputs"]["adapter_script"] = inputs["adapter_script"]
        del manifest["inputs"]["runtime_probe"]
        with pytest.raises(
            inspector.MacOSDeploymentInspectionError,
            match="complete hashed input inventory",
        ):
            inspector.validate_direct_build_manifest(manifest, target="macos-x64")
        manifest["inputs"]["runtime_probe"] = {
            "sha256": hashlib.sha256(
                payload_by_relative[
                    inspector.DIRECT_BUILD_INPUT_MEMBERS["runtime_probe"]
                ]
            ).hexdigest(),
            "size": len(
                payload_by_relative[
                    inspector.DIRECT_BUILD_INPUT_MEMBERS["runtime_probe"]
                ]
            ),
        }
        manifest["ppm_archives"] = []
        with pytest.raises(
            inspector.MacOSDeploymentInspectionError, match="PPM archive inventory"
        ):
            inspector.validate_direct_build_manifest(manifest, target="macos-x64")
        manifest["ppm_archives"] = ppm_archives
        manifest["hsroc_source_exception"]["archive"]["sha256"] = "0" * 64
        with pytest.raises(
            inspector.MacOSDeploymentInspectionError, match="HSROC source provenance"
        ):
            inspector.validate_direct_build_manifest(manifest, target="macos-x64")
        manifest["hsroc_source_exception"]["archive"]["sha256"] = hsroc_sha
        adapter_payload = payload_by_relative[
            inspector.DIRECT_BUILD_INPUT_MEMBERS["adapter_script"]
        ]
        manifest["inputs"]["adapter_script"] = {
            "sha256": hashlib.sha256(adapter_payload).hexdigest(),
            "size": len(adapter_payload),
        }
        assert (
            inspector.DIRECT_BUILD_INPUT_MEMBERS["signing_inventory"]
            != inspector.DIRECT_BUILD_INPUT_MEMBERS["post_sign_native_inventory"]
        )
        missing = tmp_path / "missing-post-sign.zip"
        with zipfile.ZipFile(missing, "w") as missing_bundle:
            for relative, payload in payload_by_relative.items():
                if (
                    relative
                    != inspector.DIRECT_BUILD_INPUT_MEMBERS[
                        "post_sign_native_inventory"
                    ]
                ):
                    missing_bundle.writestr(prefix + relative, payload)
            missing_bundle.writestr(
                prefix + "qualification/ppm-archives/pkg_1.0.tgz", ppm_payload
            )
        with (
            zipfile.ZipFile(missing) as missing_bundle,
            pytest.raises(
                inspector.MacOSDeploymentInspectionError,
                match="post-sign-native-inventory",
            ),
        ):
            inspector.validate_direct_build_archive_inputs(
                missing_bundle,
                prefix=prefix,
                names=missing_bundle.namelist(),
                manifest=manifest,
                target="macos-x64",
            )
        substituted = tmp_path / "substituted-post-sign.zip"
        with zipfile.ZipFile(substituted, "w") as substituted_bundle:
            for relative, payload in payload_by_relative.items():
                if (
                    relative
                    == inspector.DIRECT_BUILD_INPUT_MEMBERS[
                        "post_sign_native_inventory"
                    ]
                ):
                    payload = signing_payload
                substituted_bundle.writestr(prefix + relative, payload)
            substituted_bundle.writestr(
                prefix + "qualification/ppm-archives/pkg_1.0.tgz", ppm_payload
            )
        with (
            zipfile.ZipFile(substituted) as substituted_bundle,
            pytest.raises(inspector.MacOSDeploymentInspectionError, match="differs"),
        ):
            inspector.validate_direct_build_archive_inputs(
                substituted_bundle,
                prefix=prefix,
                names=substituted_bundle.namelist(),
                manifest=manifest,
                target="macos-x64",
            )


def test_direct_smoke_finalizer_requires_executed_teardown_surface_and_launch(tmp_path):
    inspector = load_inspector()
    validated_scales = []
    inspector.validate_macos_surface_records = lambda records: validated_scales.extend(
        records
    )
    evidence = tmp_path / "smoke.json"
    log = tmp_path / "smoke.log"
    marker = tmp_path / "launch.json"
    evidence.write_text(
        json.dumps(
            {
                "failures": [],
                "surface_progress": [],
                "scales": [{"requested": scale} for scale in ("1.25", "1.50", "1.75")],
            }
        ),
        encoding="utf-8",
    )
    markers = (
        "packaged-workflow:teardown:close:start",
        "packaged-workflow:teardown:close:return",
        "packaged-workflow:teardown:deferred-delete:complete",
        "packaged-workflow:teardown:top-level-windows:none",
        "packaged-workflow:teardown:app-quit:start",
        "packaged-workflow:teardown:app-quit:return",
        "packaged-workflow:post-close",
        "packaged-workflow:return",
        "packaged-workflow:process-exit:0",
    )
    log.write_text("\n".join(markers) + "\n", encoding="utf-8")
    marker.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "platform_plugin": "cocoa",
                "project": "BCG.rcms",
                "post_close": True,
                "pid": 123,
            }
        ),
        encoding="utf-8",
    )
    finalized = inspector.finalize_smoke_evidence(
        evidence, log, marker, require_direct_teardown=True
    )
    execution = finalized["execution"]
    assert execution["surface_scale_exit_codes"] == {
        "1.25": 0,
        "1.50": 0,
        "1.75": 0,
    }
    assert "positional_user_entry_exit_code" not in execution
    assert [record["requested"] for record in validated_scales] == [
        "1.25",
        "1.50",
        "1.75",
    ]
    log.write_text("\n".join(markers[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="teardown"):
        inspector.finalize_smoke_evidence(
            evidence, log, marker, require_direct_teardown=True
        )


@pytest.mark.skipif(
    sys.platform != "darwin", reason="requires native PyInstaller BUNDLE"
)
def test_pyinstaller_preserves_miniature_cran_framework_toc():
    script = (
        Path(__file__).resolve().parents[3]
        / "scripts/verify_macos_r_pyinstaller_toc.py"
    )
    subprocess.run([sys.executable, str(script)], check=True)
