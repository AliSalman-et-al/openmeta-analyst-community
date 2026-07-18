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
    return _load_script("macos_embedded_r_adapter_behavior", "scripts/macos_embedded_r_adapter.py")


def load_inspector():
    return _load_script("inspect_macos_deployment_behavior", "scripts/inspect_macos_deployment.py")


def _framework(root: Path) -> Path:
    framework = root / "R.framework"
    resources = framework / "Versions/4.6-x86_64/Resources"
    (resources / "lib").mkdir(parents=True)
    (resources / "bin").mkdir()
    (resources / "lib/libR.dylib").write_bytes(b"libR")
    (resources / "bin/R").write_text("#!/bin/sh\n", encoding="utf-8")
    (framework / "Versions/Current").symlink_to(Path("4.6-x86_64"), target_is_directory=True)
    (framework / "Resources").symlink_to(Path("Versions/Current/Resources"), target_is_directory=True)
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


def test_adapter_plans_transitive_opt_r_closure_without_mutating(tmp_path, monkeypatch):
    adapter = load_embedded_r_adapter()
    framework = _framework(tmp_path)
    first = tmp_path / "opt/libfirst.dylib"
    second = tmp_path / "opt/libsecond.dylib"
    first.parent.mkdir()
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    initial = [{
        "path": "Versions/4.6-x86_64/Resources/lib/libR.dylib",
        "sha256": adapter.sha256_file(framework / "Resources/lib/libR.dylib"),
        "architectures": ["x86_64"],
        "install_id": None,
        "dependencies": ["/opt/R/x86_64/lib/libfirst.dylib"],
    }]
    monkeypatch.setattr(adapter, "macho_inventory", lambda *_: list(initial))
    monkeypatch.setattr(adapter, "is_macho_candidate", lambda path: path.is_file())
    monkeypatch.setattr(adapter, "architectures", lambda _path: ["x86_64"])
    monkeypatch.setattr(adapter, "install_id", lambda _path: None)
    monkeypatch.setattr(
        adapter,
        "dependencies",
        lambda path: ["/opt/R/x86_64/lib/libsecond.dylib"] if path == first else ["/usr/lib/libSystem.B.dylib"],
    )
    original_map = adapter._map_absolute

    def mapped(root, value, architecture):
        sources = {
            "/opt/R/x86_64/lib/libfirst.dylib": first,
            "/opt/R/x86_64/lib/libsecond.dylib": second,
        }
        if value in sources:
            return root / "Resources/vendor/opt-R/lib" / Path(value).name, sources[value]
        return original_map(root, value, architecture)

    monkeypatch.setattr(adapter, "_map_absolute", mapped)
    audit = adapter.pre_normalization_audit(framework, "x86_64")
    assert set(audit["planned_copies"]) == {
        "Resources/vendor/opt-R/lib/libfirst.dylib",
        "Resources/vendor/opt-R/lib/libsecond.dylib",
    }
    assert not (framework / "Resources/vendor").exists()


def test_adapter_normalizes_copy_and_install_names_and_rejects_collision(tmp_path, monkeypatch):
    adapter = load_embedded_r_adapter()
    framework = _framework(tmp_path)
    binary = framework / "Resources/lib/libR.dylib"
    source = tmp_path / "opt/libnative.dylib"
    source.parent.mkdir()
    source.write_bytes(b"native")
    target = framework / "Resources/vendor/opt-R/lib/libnative.dylib"
    relocated = False
    replacement = ""
    final_id = ""
    calls = []

    def inventory(_framework, _architecture):
        dep = replacement if relocated else "/opt/R/x86_64/lib/libnative.dylib"
        identity = final_id if relocated else "/Library/Frameworks/R.framework/Resources/lib/libR.dylib"
        records = [{"path": binary.resolve().relative_to(framework.resolve()).as_posix(), "sha256": adapter.sha256_file(binary), "architectures": ["x86_64"], "install_id": identity, "dependencies": [dep]}]
        if target.exists():
            records.append({"path": target.resolve().relative_to(framework.resolve()).as_posix(), "sha256": adapter.sha256_file(target), "architectures": ["x86_64"], "install_id": None, "dependencies": ["/usr/lib/libSystem.B.dylib"]})
        return records

    original_map = adapter._map_absolute
    monkeypatch.setattr(adapter, "macho_inventory", inventory)
    monkeypatch.setattr(adapter, "is_macho_candidate", lambda path: path.is_file())
    monkeypatch.setattr(adapter, "_map_absolute", lambda root, value, arch: (root / "Resources/vendor/opt-R/lib/libnative.dylib", source) if value.startswith("/opt/R/") else original_map(root, value, arch))

    def run(*args, **_kwargs):
        nonlocal relocated, replacement, final_id
        calls.append(args)
        if args[:2] == ("install_name_tool", "-id"):
            final_id = args[2]
        elif args[:2] == ("install_name_tool", "-change"):
            relocated = True
            replacement = args[3]
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(adapter, "_run", run)
    result = adapter.normalize_machos(framework, "x86_64")
    assert target.read_bytes() == source.read_bytes()
    assert any(call[1] == "-change" for call in calls)
    assert result["mach_o"][0]["dependencies"][0].startswith("@loader_path/")
    assert result["mach_o"][0]["install_id"].startswith("@loader_path/")
    target.write_bytes(b"collision")
    relocated = False
    with pytest.raises(adapter.AdapterError, match="collision"):
        adapter.normalize_machos(framework, "x86_64")


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
    assert json.loads(output.read_text(encoding="utf-8"))["r_dependency"].startswith("@loader_path/")
    monkeypatch.setattr(adapter, "audit_symlinks", lambda _root: [])
    monkeypatch.setattr(adapter, "macho_inventory", lambda *_: [{"path": "libR", "install_id": None, "dependencies": []}])
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
        [("keep", str(tmp_path / "keep.dylib"), "BINARY"), ("R", "/Library/Frameworks/R.framework/R", "BINARY")],
        {},
    )
    assert [item[0] for item in retained] == ["keep"]
    with pytest.raises(adapter.AdapterError, match="unmapped /opt/R"):
        adapter.filter_pyinstaller_r_binaries([("bad", "/opt/R/x86_64/lib/bad.dylib", "BINARY")], {})

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
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="wrong architecture"):
        inspector.inspect_unsigned_native_graph(app)
    monkeypatch.setattr(inspector, "require_macho_architecture", lambda _path, _arch: ["x86_64"])
    monkeypatch.setattr(inspector, "_dependencies", lambda path: ["@loader_path/missing.dylib"] if path == executable else [])
    monkeypatch.setattr(inspector, "_macho_load_metadata", lambda _path: {"install_id": None, "rpaths": [], "uuid": "a", "text_section_sha256": "b" * 64, "minimum_macos": "13.0"})
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="does not resolve uniquely"):
        inspector.inspect_unsigned_native_graph(app)
    monkeypatch.setattr(inspector, "_dependencies", lambda _path: [])
    monkeypatch.setattr(inspector, "_macho_load_metadata", lambda _path: {"install_id": "@rpath/duplicate", "rpaths": [], "uuid": "a", "text_section_sha256": "b" * 64, "minimum_macos": "13.0"})
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="duplicate Mach-O install identity"):
        inspector.inspect_unsigned_native_graph(app)


def test_host_r_isolation_state_machine_restores_exact_identity(tmp_path):
    bash = shutil.which("bash") or r"C:\Program Files\Git\bin\bash.exe"
    if not Path(bash).is_file():
        pytest.skip("bash is unavailable")
    framework = _framework(tmp_path)
    helper = Path(__file__).resolve().parents[3] / "scripts/macos_host_r_isolation.sh"
    script = r'''
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
'''
    completed = subprocess.run(
        [bash], input=script, text=True, capture_output=True,
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
        if name == "meta_py_r" or name == "rc_metastudio.meta_py_r" or name.startswith("rpy2"):
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
    setattr(fake_qt_ui, "prepare_generated_ui_imports", lambda: events.append("prepare-ui"))
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
    setattr(fake_launch, "start", lambda: (meta_py_r_backend.install_meta_py_r_backend(), 0)[1])
    monkeypatch.setitem(sys.modules, "launch", fake_launch)
    assert application_entry.main() == 0
    assert events == ["prepare-ui", "configure-bundled-r", "rpy2-import"]


def test_direct_manifest_binds_archived_inputs_and_runner(tmp_path):
    inspector = load_inspector()
    ppm_archives = [{"path": "pkg.tgz", "sha256": "e" * 64, "size": 12}]
    runner = json.dumps({
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
    }).encode()
    ppm = json.dumps({
        "schema_version": 1,
        "repository": inspector.DIRECT_R_PPM_SNAPSHOT,
        "archives": ppm_archives,
    }).encode()
    preflight = json.dumps({
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
    }).encode()
    hsroc_payload = b"fixture HSROC source archive"
    rcmetar_payload = b"fixture RCMetaR source archive"
    hsroc_sha = hashlib.sha256(hsroc_payload).hexdigest()
    inspector.DIRECT_R_HSROC_SHA256 = hsroc_sha
    payload_by_relative = {
        relative: (
            runner if label == "runner_environment"
            else ppm if label == "ppm_archive_inventory"
            else preflight if label == "pyinstaller_toc_preflight_report"
            else hsroc_payload if label == "hsroc_source_archive"
            else rcmetar_payload if label == "rcmetar_source_archive"
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
        "official_r": {"url": inspector.DIRECT_R_OFFICIAL_URL, "sha256": inspector.DIRECT_R_OFFICIAL_SHA256},
        "ppm_snapshot": inspector.DIRECT_R_PPM_SNAPSHOT,
        "ppm_archives": ppm_archives,
        "rpy2_api_bridge_source_sha256": "b" * 64,
        "inputs": inputs,
        "hsroc_source_exception": {
            "name": "HSROC", "version": "2.1.9", "install_type": "source",
            "url": inspector.DIRECT_R_HSROC_URL, "sha256": hsroc_sha,
            "archive": {"sha256": hsroc_sha, "size": len(hsroc_payload)},
        },
        "rcmetar_source": {
            "name": "RCMetaR", "version": "0.1.2", "source_commit": "c" * 40,
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


def test_direct_smoke_finalizer_requires_executed_teardown_surface_and_launch(tmp_path):
    inspector = load_inspector()
    validated_scales = []
    inspector.validate_macos_surface_records = lambda records: validated_scales.extend(records)
    evidence = tmp_path / "smoke.json"
    log = tmp_path / "smoke.log"
    marker = tmp_path / "launch.json"
    evidence.write_text(json.dumps({
        "failures": [],
        "surface_progress": [],
        "scales": [{"requested": scale} for scale in ("1.25", "1.50", "1.75")],
    }), encoding="utf-8")
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
    marker.write_text(json.dumps({
        "schema_version": 1,
        "platform_plugin": "cocoa",
        "project": "amino.rcms",
        "post_close": True,
        "pid": 123,
    }), encoding="utf-8")
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


@pytest.mark.skipif(sys.platform != "darwin", reason="requires native PyInstaller BUNDLE")
def test_pyinstaller_preserves_miniature_cran_framework_toc():
    script = Path(__file__).resolve().parents[3] / "scripts/verify_macos_r_pyinstaller_toc.py"
    subprocess.run([sys.executable, str(script)], check=True)
