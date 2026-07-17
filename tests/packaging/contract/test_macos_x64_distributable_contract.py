import errno
import importlib.util
import json
import os
import signal
import stat
import struct
import sys
import time
import zipfile
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def load_inspector():
    path = ROOT / "scripts/inspect_macos_deployment.py"
    spec = importlib.util.spec_from_file_location("inspect_macos_deployment", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_bounded_runner():
    path = ROOT / "scripts/run_bounded_process.py"
    spec = importlib.util.spec_from_file_location("run_bounded_process", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_package_policy():
    path = ROOT / "scripts/package_input_policy.py"
    spec = importlib.util.spec_from_file_location("package_input_policy", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def zip_info(name: str, mode: int) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    info.create_system = 3
    info.external_attr = mode << 16
    return info


def thin_macho(cpu_type: int, cpu_subtype: int) -> bytes:
    return b"\xcf\xfa\xed\xfe" + struct.pack("<II", cpu_type, cpu_subtype) + b"\0" * 20


def test_macos_x64_uses_one_authoritative_pyinstaller_spec():
    build = text("scripts/build-macos-package.sh")
    spec = text("packaging/pyinstaller/rc-metastudio-macos.spec")

    assert "packaging/pyinstaller/rc-metastudio-macos.spec" in build
    assert '"$python_exe" -m PyInstaller' in build
    assert "--hidden-import" not in build
    assert "--collect" not in build
    assert "macdeployqt" not in build.lower()
    assert "Analysis(" in spec
    assert "BUNDLE(" in spec
    assert 'target_arch=os.environ.get("RCMS_TARGET_ARCHITECTURE", "x86_64")' in spec
    assert '"PyQt5", "PySide2", "PySide6", "qtpy"' in spec
    assert "project_schema_data" in spec
    assert "generated_form_modules" in spec
    assert '"LSMinimumSystemVersion": "13.0"' in spec


def test_macos_packager_qualifies_deployment_smoke_archive_and_evidence():
    build = text("scripts/build-macos-package.sh")
    workflow_text = text(".github/workflows/package-target.yml")
    workflow = yaml.safe_load(workflow_text)
    steps = workflow["jobs"]["package"]["steps"]
    steps_by_name = {step["name"]: step for step in steps}

    for command in ("inspect", "finalize-smoke", "archive", "evidence"):
        assert f'inspect_macos_deployment.py" {command}' in build
    for value in ("1.25", "1.50", "1.75"):
        assert value in build
    assert "--automation-package-runtime-probe" in build
    assert "--automation-package-surface-smoke" in build
    assert "RCMS_PACKAGE_SMOKE_EVIDENCE" in build
    assert "RCMS_AUTOMATION_HANG_TRACE" in build
    assert "run_bounded_process.py" in build
    assert 'open -W -n "$app_bundle" --args' in build
    assert "--automation-startup-completion-marker" in build
    assert 'codesign --force --deep --options runtime --sign - "$app_bundle"' in build
    assert build.index('if [ "$skip_clean" -eq 0 ]') < build.index(
        'rm -rf "$qualification_root"'
    ) < build.index('mkdir -p "$qualification_root"')
    assert "${{ inputs.artifact_name }}-evidence" in workflow_text
    assert "*-archive-inspection.json" in workflow_text
    assert "packaged-smoke*.log" in workflow_text
    assert '2>&1 | tee "$shared_verification_log"' in text("scripts/package-macos.sh")
    assert "shared-release-verification.log" in workflow_text
    sdk_cache = steps_by_name["Cache official Qt SDK on macOS"]
    assert sdk_cache["if"] == "${{ inputs.target_os == 'macos' }}"
    assert sdk_cache["id"] == "macos_qt_sdk_cache"
    assert sdk_cache["with"] == {
        "path": "build/qt-sdk",
        "key": "qt-sdk-6.11.1-${{ inputs.archive_platform }}",
    }
    sdk_install = steps_by_name["Install official Qt SDK on macOS"]
    assert sdk_install["if"] == (
        "${{ inputs.target_os == 'macos' && "
        "steps.macos_qt_sdk_cache.outputs.cache-hit != 'true' }}"
    )
    assert "uv run aqt install-qt mac desktop 6.11.1 clang_64" in sdk_install["run"]
    rcc_resolve = steps_by_name["Resolve official Qt rcc on macOS"]
    assert rcc_resolve["if"] == "${{ inputs.target_os == 'macos' }}"
    assert "qt6_macos_feasibility.py resolve-rcc" in rcc_resolve["run"]
    assert '--sdk-root "$PWD/build/qt-sdk/6.11.1/macos"' in rcc_resolve["run"]
    assert '--github-env "$GITHUB_ENV"' in rcc_resolve["run"]
    assert steps.index(rcc_resolve) < steps.index(steps_by_name["Build macOS package"])


def test_macos_surface_smoke_exercises_native_acceptance_surfaces():
    launch = text("src/rc_metastudio/launch.py")

    assert 'platform_name != "cocoa"' in launch
    assert '"native_menu": native_menu' in launch
    assert '"native_file_dialog": native_file_dialog' in launch
    assert '"accessibility": accessibility' in launch
    assert "DontUseNativeDialog" in launch
    assert "isNativeMenuBar" in launch
    assert "accessible_control.setFocus()" in launch
    assert "accessible_control.setFocus(QtCore.Qt.FocusReason" not in launch
    assert 'if sys.platform == "darwin" else {}' in launch


def test_macho_parser_rejects_arm_and_universal_payloads_for_x64(tmp_path):
    inspector = load_inspector()
    x64 = tmp_path / "x64"
    arm = tmp_path / "arm"
    x64.write_bytes(thin_macho(0x01000007, 3))
    arm.write_bytes(thin_macho(0x0100000C, 0))

    assert inspector.macho_architectures(x64) == ["x86_64"]
    assert inspector.macho_architectures(arm) == ["arm64"]
    inspector.require_x64_macho(x64)
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="x86_64-only"):
        inspector.require_x64_macho(arm)


def test_archive_inspection_rejects_case_collisions(tmp_path):
    inspector = load_inspector()
    archive = tmp_path / "package.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(zip_info("root/RCMetaStudio.app/a", stat.S_IFREG | 0o644), b"a")
        bundle.writestr(zip_info("root/RCMetaStudio.app/A", stat.S_IFREG | 0o644), b"b")

    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="case-colliding"):
        inspector.inspect_archive(archive, archive_root_name="root", embedded_files={})


def test_smoke_finalizer_requires_the_post_close_marker(tmp_path):
    inspector = load_inspector()
    evidence = tmp_path / "smoke.json"
    log = tmp_path / "smoke.log"
    evidence.write_text(json.dumps({"passed": True}), encoding="utf-8")
    log.write_text("packaged-workflow:start\n", encoding="utf-8")

    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="post-close"):
        inspector.finalize_smoke_evidence(evidence, log)


def test_smoke_finalizer_authenticates_launchservices_completion(tmp_path):
    inspector = load_inspector()
    evidence = tmp_path / "smoke.json"
    log = tmp_path / "smoke.log"
    marker = tmp_path / "launchservices.json"
    evidence.write_text(json.dumps({"passed": True}), encoding="utf-8")
    log.write_text("packaged-workflow:post-close\n", encoding="utf-8")
    marker.write_text(
        json.dumps({
            "schema_version": 1,
            "pid": 123,
            "platform_plugin": "cocoa",
            "project": "amino.rcms",
            "post_close": True,
        }),
        encoding="utf-8",
    )

    finalized = inspector.finalize_smoke_evidence(evidence, log, marker)
    assert finalized["execution"]["launchservices_completion_marker"] is True
    marker.write_text(marker.read_text().replace('"cocoa"', '"offscreen"'), encoding="utf-8")
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="LaunchServices"):
        inspector.finalize_smoke_evidence(evidence, log, marker)


def test_dependency_graph_rejects_missing_target(tmp_path):
    inspector = load_inspector()
    executable = tmp_path / "Contents/MacOS/RCMetaStudio"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"exe")
    records = [{
        "path": "Contents/MacOS/RCMetaStudio",
        "architectures": ["x86_64"],
        "install_id": None,
        "rpaths": [],
        "dependencies": ["@loader_path/missing.dylib"],
    }]
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="resolve uniquely"):
        inspector.validate_dependency_graph(records, app_root=tmp_path)


def test_dependency_graph_requires_declared_rpath_reachability(tmp_path):
    inspector = load_inspector()
    executable = tmp_path / "Contents/MacOS/RCMetaStudio"
    dependent = tmp_path / "Contents/Frameworks/nested/libdependent.dylib"
    target = tmp_path / "Contents/Frameworks/libfoo.dylib"
    executable.parent.mkdir(parents=True)
    dependent.parent.mkdir(parents=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(b"exe")
    dependent.write_bytes(b"dependent")
    target.write_bytes(b"target")
    records = [
        {
            "path": "Contents/MacOS/RCMetaStudio",
            "architectures": ["x86_64"],
            "install_id": None,
            "rpaths": ["@loader_path/../Frameworks"],
            "dependencies": [],
        },
        {
            "path": "Contents/Frameworks/nested/libdependent.dylib",
            "architectures": ["x86_64"],
            "install_id": "@rpath/libdependent.dylib",
            "rpaths": [],
            "dependencies": ["@rpath/libfoo.dylib"],
        },
        {
            "path": "Contents/Frameworks/libfoo.dylib",
            "architectures": ["x86_64"],
            "install_id": "@rpath/libfoo.dylib",
            "rpaths": [],
            "dependencies": [],
        },
    ]

    inspector.validate_dependency_graph(records, app_root=tmp_path)

    target.unlink()
    wrong_relative_target = tmp_path / "Contents/Frameworks/Frameworks/libfoo.dylib"
    wrong_relative_target.parent.mkdir(parents=True)
    wrong_relative_target.write_bytes(b"wrong-relative-target")
    records[2]["path"] = "Contents/Frameworks/Frameworks/libfoo.dylib"
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="resolve uniquely"):
        inspector.validate_dependency_graph(records, app_root=tmp_path)


def test_dependency_graph_rejects_duplicate_identity(tmp_path):
    inspector = load_inspector()
    for relative in ("Contents/MacOS/one.dylib", "Contents/Frameworks/two.dylib"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"native")
    records = [
        {"path": relative, "architectures": ["x86_64"], "install_id": "@rpath/duplicate.dylib", "rpaths": [], "dependencies": []}
        for relative in ("Contents/MacOS/one.dylib", "Contents/Frameworks/two.dylib")
    ]
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="duplicate Mach-O install identity"):
        inspector.validate_dependency_graph(records, app_root=tmp_path)


def test_dependency_graph_rejects_mismatched_x64_target(tmp_path):
    inspector = load_inspector()
    executable = tmp_path / "Contents/MacOS/RCMetaStudio"
    target = tmp_path / "Contents/MacOS/libtarget.dylib"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"exe")
    target.write_bytes(b"target")
    records = [
        {"path": "Contents/MacOS/RCMetaStudio", "architectures": ["x86_64"], "install_id": None, "rpaths": [], "dependencies": ["@loader_path/libtarget.dylib"]},
        {"path": "Contents/MacOS/libtarget.dylib", "architectures": ["arm64"], "install_id": "@rpath/libtarget.dylib", "rpaths": [], "dependencies": []},
    ]
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="not x86_64-only"):
        inspector.validate_dependency_graph(records, app_root=tmp_path)


def test_locked_qt_inventory_rejects_identity_mutation(tmp_path, monkeypatch):
    inspector = load_inspector()
    source = tmp_path / "plugins/platforms/libqcocoa.dylib"
    source.parent.mkdir(parents=True)
    source.write_bytes(thin_macho(0x01000007, 3))
    monkeypatch.setattr(
        inspector,
        "_macho_load_metadata",
        lambda _path: {
            "uuid": "locked", "install_id": None, "rpaths": [],
            "text_section_sha256": "locked-code",
        },
    )
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="locked wheel identity"):
        inspector.validate_locked_qt_inventory(
            [{
                "qt_relative_path": "plugins/platforms/libqcocoa.dylib",
                "architectures": ["x86_64"], "uuid": "locked",
                "text_section_sha256": "mutated-code", "sha256": "0" * 64,
            }],
            locked_qt_root=tmp_path,
        )


def test_codesign_observation_requires_runtime_and_no_entitlements(tmp_path, monkeypatch):
    inspector = load_inspector()
    monkeypatch.setattr(inspector.sys, "platform", "darwin")

    class Completed:
        def __init__(self, returncode=0, stdout=b"", stderr=b""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    responses = iter([
        Completed(stdout="", stderr=""),
        Completed(stdout="", stderr="flags=0x10000(runtime)"),
        Completed(stdout=b"", stderr=b""),
    ])
    monkeypatch.setattr(inspector.subprocess, "run", lambda *args, **kwargs: next(responses))
    assert inspector._codesign_observation(tmp_path) == {
        "verified": True, "runtime": True, "entitlements": {}
    }

    responses = iter([
        Completed(stdout="", stderr=""),
        Completed(stdout="", stderr="flags=0x0(none)"),
    ])
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="hardened-runtime"):
        inspector._codesign_observation(tmp_path)
    responses = iter([
        Completed(stdout="", stderr=""),
        Completed(stdout="", stderr="flags=0x10000(runtime)"),
        Completed(
            stdout=__import__("plistlib").dumps(
                {"com.apple.security.cs.disable-library-validation": True}
            ),
            stderr=b"",
        ),
    ])
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="unreviewed"):
        inspector._codesign_observation(tmp_path)


def test_archive_rejects_traversal_oversize_symlink_and_mode_mutations(tmp_path, monkeypatch):
    inspector = load_inspector()
    traversal = tmp_path / "traversal.zip"
    with zipfile.ZipFile(traversal, "w") as bundle:
        bundle.writestr(zip_info("root/../escape", stat.S_IFREG | 0o644), b"x")
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="traversal"):
        inspector.inspect_archive(traversal, archive_root_name="root", embedded_files={})

    oversized = tmp_path / "oversized.zip"
    with zipfile.ZipFile(oversized, "w") as bundle:
        bundle.writestr(zip_info("root/file", stat.S_IFREG | 0o644), b"xx")
    monkeypatch.setattr(inspector, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 1)
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="uncompressed-byte"):
        inspector.inspect_archive(oversized, archive_root_name="root", embedded_files={})
    monkeypatch.setattr(inspector, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 3_000_000_000)

    manifest = tmp_path / "deployment-manifest.json"
    payload = b"executable"
    manifest.write_text(json.dumps({"inventory": {"files": [{
        "path": "Contents/MacOS/RCMetaStudio", "kind": "file", "size": len(payload),
        "mode": 0o755, "sha256": __import__("hashlib").sha256(payload).hexdigest(),
    }]}}), encoding="utf-8")
    for name, mode, expected in (
        ("symlink.zip", stat.S_IFLNK | 0o755, "ZIP file differs"),
        ("mode.zip", stat.S_IFREG | 0o644, "ZIP file differs"),
    ):
        archive = tmp_path / name
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr(zip_info("root/qualification/deployment-manifest.json", stat.S_IFREG | 0o644), manifest.read_bytes())
            bundle.writestr(zip_info("root/RCMetaStudio.app/Contents/MacOS/RCMetaStudio", mode), payload)
        with pytest.raises(inspector.MacOSDeploymentInspectionError, match=expected):
            inspector.inspect_archive(
                archive,
                archive_root_name="root",
                embedded_files={"qualification/deployment-manifest.json": manifest},
            )


def test_archive_root_rejects_dot_dot_and_nonportable_names():
    inspector = load_inspector()
    for value in (".", "..", "a/b", "a\\b", "CON", "trailing.", "bad:name"):
        with pytest.raises(inspector.MacOSDeploymentInspectionError, match="portable"):
            inspector.validate_archive_root_name(value)


def test_bounded_process_preserves_exit_code_and_redirected_output(tmp_path):
    import sys

    runner = load_bounded_runner()
    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    code = runner.run_bounded(
        [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(7)"],
        timeout_seconds=10,
        stdout_path=stdout,
        stderr_path=stderr,
    )

    assert code == 7
    assert stdout.read_text().strip() == "out"
    assert stderr.read_text().strip() == "err"


def test_bounded_process_times_out(tmp_path):
    import sys

    runner = load_bounded_runner()
    code = runner.run_bounded(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        timeout_seconds=1,
        stdout_path=tmp_path / "stdout.log",
        stderr_path=tmp_path / "stderr.log",
    )

    assert code == 124


def test_process_group_probe_interprets_posix_errnos(monkeypatch):
    runner = load_bounded_runner()

    def raise_errno(value):
        def failing_killpg(_process_group_id, _signal):
            raise OSError(value, os.strerror(value))
        return failing_killpg

    monkeypatch.setattr(runner, "_killpg", raise_errno(errno.ESRCH))
    assert runner._process_group_exists(123) is False
    monkeypatch.setattr(runner, "_killpg", raise_errno(errno.EPERM))
    assert runner._process_group_exists(123) is True
    monkeypatch.setattr(runner, "_killpg", raise_errno(errno.EINVAL))
    with pytest.raises(OSError) as exc_info:
        runner._process_group_exists(123)
    assert exc_info.value.errno == errno.EINVAL


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group contract")
def test_bounded_process_kills_stubborn_grandchild(tmp_path):
    runner = load_bounded_runner()
    child_pid = tmp_path / "child.pid"
    child_code = (
        "import os,signal,time,pathlib; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"pathlib.Path({str(child_pid)!r}).write_text(str(os.getpid())); "
        "time.sleep(30)"
    )
    parent_code = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable,'-c',{child_code!r}]); time.sleep(30)"
    )
    code = runner.run_bounded(
        [sys.executable, "-c", parent_code],
        timeout_seconds=2,
        stdout_path=tmp_path / "stdout.log",
        stderr_path=tmp_path / "stderr.log",
    )
    assert code == 124
    pid = int(child_pid.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_macos_surface_evidence_rejects_observation_mutations():
    inspector = load_inspector()
    base = {
        "platform_plugin": "cocoa", "clipboard": True, "critical_dialog": True,
        "binary_resources": True, "native_menu": {"is_native": True, "menu_count": 1, "action_count": 1},
        "native_file_dialog": {"dont_use_native_dialog": False, "visible_before_cancel": True, "result": 0, "rejected_value": 0},
        "accessibility": {
            "focus_before": "packagedAccessibilityControl",
            "focus_after_tab": "packagedKeyboardTraversalTarget",
            "accessible_name": "Packaged accessibility control",
            "accessible_description": "Verifies packaged Qt accessibility metadata.",
            "native": {"role": "AXButton", "is_element": True},
        },
        "available_styles": ["macOS"], "active_style": "macos", "tls_backends": ["cert-only"],
        "image_formats": ["jpeg", "svg"], "baseline_device_pixel_ratio": 1.0,
        "dpr_tolerance": 0.05,
    }
    records = [
        {
            **base, "requested": value, "qt_scale_factor": value,
            "device_pixel_ratio": float(value),
            "expected_device_pixel_ratio": float(value),
        }
        for value in ("1.25", "1.50", "1.75")
    ]
    inspector.validate_macos_surface_records(records)
    mutations = [
        ("native_menu", {"is_native": False, "menu_count": 1, "action_count": 1}),
        ("native_file_dialog", {"dont_use_native_dialog": False, "visible_before_cancel": False, "result": 0, "rejected_value": 0}),
        ("accessibility", {
            "focus_before": "packagedAccessibilityControl",
            "focus_after_tab": "packagedKeyboardTraversalTarget",
            "accessible_name": "Packaged accessibility control",
            "accessible_description": "Verifies packaged Qt accessibility metadata.",
            "native": {"role": "", "is_element": False},
        }),
    ]
    for key, value in mutations:
        mutated = [dict(item) for item in records]
        mutated[0][key] = value
        with pytest.raises(inspector.MacOSDeploymentInspectionError, match="surface evidence"):
            inspector.validate_macos_surface_records(mutated)


def test_package_classifier_and_gate_cover_all_direct_macos_inputs():
    policy = load_package_policy()
    direct_inputs = [
        "scripts/validate_test_taxonomy.py", "scripts/verify_rcmetar_r_stack.py",
        "docs/verification/test-taxonomy.json", "scripts/delivery.py",
        "scripts/inspect_macos_deployment.py", "scripts/qt6_macos_feasibility.py",
        "packaging/pyinstaller/rc-metastudio-macos.spec",
    ]
    assert all(policy.requires_package_qualification([path]) for path in direct_inputs)
    assert policy.requires_package_qualification(["docs/user-guide.md"]) is False
    workflow = text(".github/workflows/fast-verification.yml")
    assert "macos-x64-package-qualification" in workflow
    assert "MACOS_X64_PACKAGE_RESULT" in workflow
    assert workflow.index('if [ "$RUN_WINDOWS" != "true" ]') < workflow.index('if [ "$RUN_MACOS_X64_PACKAGE" = "true" ]')
