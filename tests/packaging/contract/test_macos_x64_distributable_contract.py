import errno
import hashlib
import importlib.util
import json
import os
import plistlib
import shutil
import stat
import struct
import subprocess
import sys
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


def load_embedded_r_adapter():
    path = ROOT / "scripts/macos_embedded_r_adapter.py"
    spec = importlib.util.spec_from_file_location("macos_embedded_r_adapter", path)
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


def load_macos_signer():
    path = ROOT / "scripts/sign_macos_app.py"
    spec = importlib.util.spec_from_file_location("sign_macos_app", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_macho_normalizer():
    path = ROOT / "scripts/normalize_macos_macho.py"
    spec = importlib.util.spec_from_file_location("normalize_macos_macho", path)
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


def minimal_java_class(
    *,
    class_name: bytes = b"Example",
    major: int = 52,
    minor: int = 0,
    attribute_body: bytes | None = None,
) -> bytes:
    constants = (
        b"\x01"
        + struct.pack(">H", len(class_name))
        + class_name
        + b"\x07\x00\x01"
        + b"\x01"
        + struct.pack(">H", len(b"java/lang/Object"))
        + b"java/lang/Object"
        + b"\x07\x00\x03"
    )
    constant_pool_count = 5
    attributes = struct.pack(">H", 0)
    if attribute_body is not None:
        attribute_name = b"TestAttribute"
        constants += b"\x01" + struct.pack(">H", len(attribute_name)) + attribute_name
        constant_pool_count = 6
        attributes = struct.pack(">HHI", 1, 5, len(attribute_body)) + attribute_body
    return (
        b"\xca\xfe\xba\xbe"
        + struct.pack(">HHH", minor, major, constant_pool_count)
        + constants
        + struct.pack(">HHHHHH", 0x0021, 2, 4, 0, 0, 0)
        + attributes
    )


def fat_x64_macho() -> bytes:
    thin = thin_macho(0x01000007, 3)
    offset = 4096
    header = struct.pack(">II", 0xCAFEBABE, 1)
    architecture = struct.pack(">IIIII", 0x01000007, 3, offset, len(thin), 12)
    return (
        header
        + architecture
        + b"\0" * (offset - len(header) - len(architecture))
        + thin
    )


def macos_code_bundle(
    root: Path, *, executable_name: str, framework: bool = False
) -> Path:
    if framework:
        executable = root / "Versions" / "A" / executable_name
        info = root / "Versions" / "A" / "Resources" / "Info.plist"
    else:
        executable = root / "Contents" / "MacOS" / executable_name
        info = root / "Contents" / "Info.plist"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(thin_macho(0x01000007, 3))
    info.parent.mkdir(parents=True, exist_ok=True)
    info.write_bytes(plistlib.dumps({"CFBundleExecutable": executable_name}))
    return executable


def test_macos_x64_uses_one_authoritative_pyinstaller_spec(tmp_path):
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
    assert all(f'"{name}"' in spec for name in ("PyQt5", "PySide2", "PySide6", "qtpy"))
    assert "project_schema_data" in spec
    assert "generated_form_modules" in spec
    assert 'os.environ.get("RCMS_PYINSTALLER_R_TOC")' in spec
    assert 'os.environ.get("RCMS_PYINSTALLER_R_MAP")' in spec
    assert 'a.datas.extend(' in spec
    assert 'entry["type"]' in spec
    assert '(direct_r_framework, "R.framework")' not in spec
    assert '"direct-r-spike.marker"' in spec
    assert '"_rinterface_cffi_api"' in spec
    assert (
        '"LSMinimumSystemVersion": os.environ.get("RCMS_MINIMUM_MACOS_VERSION", "13.0")'
        in spec
    )
    assert 'minimum_macos_version="14.0"' in build
    spike = text("scripts/package-macos-x64-direct-r-spike.sh")
    spike_workflow_text = text(".github/workflows/macos-x64-direct-r-spike.yml")
    spike_workflow = yaml.safe_load(spike_workflow_text)
    assert list(spike_workflow["jobs"]) == ["feasibility"]
    assert "verify_macos_r_pyinstaller_toc.py" in spike_workflow_text
    assert spike_workflow_text.index("verify_macos_r_pyinstaller_toc.py") < spike_workflow_text.index(
        "package-macos-x64-direct-r-spike.sh"
    )
    assert "produce-r-integration-kit" not in spike_workflow_text
    assert "r-integration-kit-producer.yml" not in spike_workflow_text
    manual_workflow = text(".github/workflows/package-verification.yml")
    assert "build_macos_direct_r_spike" in manual_workflow
    assert "uses: ./.github/workflows/macos-x64-direct-r-spike.yml" in manual_workflow
    for required in (
        "612bb00cb4c627721d6d80b0f5224227c0fcdefb4a5b6c917511480361c16571",
        'installed_framework="/Library/Frameworks/R.framework"',
        'current="$(readlink "$framework/Versions/Current")"',
        'ditto "$installed_framework" "$stage"',
        'require_x64 "$home/bin/Rscript"',
        'require_x64 "$home/bin/exec/R"',
        'require_x64 "$home/lib/libR.dylib"',
        '[ "$(head -n 1 "$home/bin/R")" = "#!/bin/sh" ]',
        'framework_symlinks "$installed_framework"',
        'framework_symlinks "$stage"',
        'staged-r-symlinks.diff',
        '"$home/bin/R" RHOME',
        '"$home/bin/Rscript" -e',
        "R.version$arch",
        'otool -L "$home/bin/Rscript"',
        'otool -L "$home/bin/exec/R"',
        'otool -D "$home/lib/libR.dylib"',
        'otool -L "$home/lib/libR.dylib"',
        "installed-r-identity.txt",
        "staged-r-identity.txt",
        "staged-r-identity.diff",
        "staging changed the official R.framework identities or load commands",
        "s#/Library/Frameworks/R.framework#<FRAMEWORK>#g",
        '"Resources/lib/libR.dylib"',
        'readlink "$home/R"',
        '"bin/R"',
        "--official-framework-layout",
        "profile_macos_embedded_r_runtime.py",
        "scripts/install-rcmetar-source.R",
        "RPY2_CFFI_MODE=API",
        "RCMS_PYINSTALLER_R_TOC",
        "RCMS_PYINSTALLER_R_MAP",
        "packaging/pyinstaller/rc-metastudio-macos.spec",
        'inspect_macos_deployment.py" inspect',
        "--automation-package-runtime-probe",
        "--automation-native-smoke",
        "finalize-smoke",
        "native-graph",
        "--direct-build-manifest",
        "extracted-direct-r-gate.json",
        "extracted-runtime-probe.json",
    ):
        assert required in spike
    assert "r_integration_kit.py" not in spike
    assert "relocate_macos_r_kit.py" not in spike
    assert "normalize_macos_macho.py" not in spike
    assert 'readlink "$resources/lib/libR.dylib"' not in spike
    assert 'require_x64 "$resources/bin/R"' not in spike
    assert 'ln -s "4.6" "$stage/Versions/Current"' not in spike
    assert "macos_embedded_r_adapter.py\" audit" in spike
    assert "macos_embedded_r_adapter.py\" normalize" in spike
    assert '--audit "$adapter_audit"' in spike
    assert "macos_embedded_r_adapter.py\" relocate-bridge" in spike
    assert "macos_embedded_r_adapter.py\" post-app" in spike
    assert "uv run --no-sync aqt" in spike
    assert "codesign --force --options runtime --sign - \"$app\"" not in spike
    assert "packaged-workflow:process-exit:0" in spike
    assert 'source "$repo/scripts/macos_host_r_isolation.sh"' in spike
    assert spike.count('rcms_isolate_host_r "$installed_framework"') == 2
    assert spike.count("rcms_restore_host_r") == 2
    assert "R.framework.rcms-host" not in spike
    assert "codesign --verify --strict --deep" in spike
    assert "extracted-codesign-verification.json" in spike
    assert spike.index("extracted-codesign-verification.json") < spike.rindex(
        'macos_embedded_r_adapter.py" post-app'
    )
    assert "--automation-package-surface-smoke" in spike
    assert "open -W -n \"$app\"" in spike
    assert "--require-direct-teardown" in spike
    assert "macOS R.framework PyInstaller preflight evidence is invalid" in spike
    assert spike.index("preflight evidence is invalid") < spike.index('rm -rf "$work"')
    isolation = text("scripts/macos_host_r_isolation.sh")
    isolation_begin = isolation[isolation.index("rcms_isolate_host_r()") :]
    assert isolation_begin.index("trap rcms_restore_host_r EXIT") < isolation_begin.index(
        'rcms_host_r_move "$source" "$candidate"'
    )
    assert isolation_begin.index('rcms_host_r_move "$source" "$candidate"') < isolation_begin.index(
        'RCMS_HOST_R_STATE="isolated"'
    ) < isolation_begin.index('Host R isolation did not converge')
    assert "No unique verified-absent host R backup path" in isolation
    assert "Host R restoration did not converge" in isolation
    assert "Restored host R identity changed" in isolation
    assert all(
        marker in text("src/rc_metastudio/launch.py")
        for marker in (
            "teardown:close:start",
            "teardown:close:return",
            "teardown:deferred-delete:complete",
            "teardown:top-level-windows:none",
            "teardown:app-quit:start",
            "teardown:app-quit:return",
            "packaged-workflow:return",
        )
    )

    adapter = load_embedded_r_adapter()
    framework_fixture = tmp_path / "fixture" / "R.framework"
    version_fixture = framework_fixture / "Versions/4.6-x86_64"
    resources_fixture = version_fixture / "Resources"
    (resources_fixture / "lib").mkdir(parents=True)
    (resources_fixture / "bin").mkdir()
    (resources_fixture / "lib/libR.dylib").write_bytes(b"libR")
    (resources_fixture / "bin/R").write_bytes(b"#!/bin/sh\n")
    (version_fixture / "R").symlink_to(Path("Resources/lib/libR.dylib"))
    (resources_fixture / "R").symlink_to(Path("bin/R"))
    (framework_fixture / "Versions/Current").symlink_to(
        "4.6-x86_64", target_is_directory=True
    )
    (framework_fixture / "Resources").symlink_to(
        Path("Versions/Current/Resources"), target_is_directory=True
    )
    (framework_fixture / "R").symlink_to(Path("Versions/Current/R"))
    links = adapter.audit_symlinks(framework_fixture)
    assert {record["path"] for record in links} >= {
        "Versions/Current",
        "Resources",
        "R",
        "Versions/4.6-x86_64/R",
        "Versions/4.6-x86_64/Resources/R",
    }
    toc = adapter.explicit_toc(framework_fixture)
    assert [record["destination"] for record in toc] == sorted(
        record["destination"] for record in toc
    )
    assert sum(record["type"] == "SYMLINK" for record in toc) == 5
    font_available = resources_fixture / "fontconfig/fonts/conf.avail"
    font_active = resources_fixture / "fontconfig/fonts/conf.d"
    font_available.mkdir(parents=True)
    font_active.mkdir()
    for index in range(17):
        target = font_available / f"{index:02d}-fixture.conf"
        target.write_text("fixture\n", encoding="utf-8")
        (font_active / target.name).symlink_to(
            f"/Library/Frameworks/R.framework/Resources/fontconfig/fonts/conf.avail/{target.name}"
        )
    font_plan = adapter.plan_fontconfig_links(framework_fixture)
    assert len(font_plan) == 17
    assert all(
        os.readlink(framework_fixture / record["path"]) == record["from"]
        for record in font_plan
    )
    audited_links = adapter.audit_pre_normalization_symlinks(
        framework_fixture, font_plan
    )
    assert sum("planned" in record for record in audited_links) == 17
    adapter.normalize_fontconfig_links(framework_fixture)
    assert all(
        not Path(os.readlink(framework_fixture / record["path"])).is_absolute()
        for record in font_plan
    )
    adapter.audit_symlinks(framework_fixture)
    bad_link = resources_fixture / "absolute-link"
    bad_link.symlink_to("/Library/Frameworks/R.framework/Resources/bin/R")
    with pytest.raises(adapter.AdapterError, match="absolute R symlink"):
        adapter.audit_symlinks(framework_fixture)
    bad_link.unlink()
    assert adapter._map_absolute(
        framework_fixture, "/opt/R/x86_64/lib/libgfortran.5.dylib", "x86_64"
    )[0] == framework_fixture / "Resources/vendor/opt-R/lib/libgfortran.5.dylib"
    with pytest.raises(adapter.AdapterError, match="unsupported non-system"):
        adapter._map_absolute(
            framework_fixture, "/opt/homebrew/lib/libgfortran.dylib", "x86_64"
        )

    inspector = load_inspector()
    app = tmp_path / "RCMetaStudio.app"
    marker = app / inspector.DIRECT_R_MARKER_RELATIVE
    marker.parent.mkdir(parents=True)
    marker.write_bytes((ROOT / "packaging/pyinstaller/direct-r-spike.marker").read_bytes())
    runtime_probe = {
        "r": {
            "direct_spike": True,
            "kit_sha256": None,
            "shared_library_sha256": "a" * 64,
        },
        "rpy2": {"api_bridge_sha256": "b" * 64},
    }
    identity = inspector.validate_r_delivery_identity(
        app,
        runtime_probe,
        target="macos-x64",
        architecture="x86_64",
        source_commit="c" * 40,
    )
    direct = identity["direct_r_build"]
    assert "r_integration_kit" not in identity
    assert direct["source_commit"] == "c" * 40
    assert direct["marker"]["sha256"] == inspector.DIRECT_R_MARKER_SHA256
    assert direct["runtime_probe_sha256"] == inspector._canonical_json_sha256(
        runtime_probe
    )
    input_record = {"sha256": "d" * 64, "size": 42}
    direct_manifest = {
        "schema_version": 1,
        "kind": "rc-metastudio-direct-macos-target-build",
        "target": "macos-x64",
        "source_commit": "c" * 40,
        "official_r": {
            "url": inspector.DIRECT_R_OFFICIAL_URL,
            "sha256": inspector.DIRECT_R_OFFICIAL_SHA256,
        },
        "ppm_snapshot": inspector.DIRECT_R_PPM_SNAPSHOT,
        "rpy2_api_bridge_source_sha256": "b" * 64,
        "inputs": {
            name: dict(input_record)
            for name in inspector.DIRECT_BUILD_INPUT_MEMBERS
        },
        "ppm_archives": [
            {"path": "digest/package.tgz", "sha256": "e" * 64, "size": 84}
        ],
        "hsroc_source_exception": {
            "name": "HSROC",
            "version": "2.1.9",
            "install_type": "source",
            "url": inspector.DIRECT_R_HSROC_URL,
            "sha256": inspector.DIRECT_R_HSROC_SHA256,
            "archive": {
                "sha256": inspector.DIRECT_R_HSROC_SHA256,
                "size": 2023525,
            },
        },
        "rcmetar_source": {
            "name": "RCMetaR",
            "version": "0.1.2",
            "source_commit": "c" * 40,
            "archive_sha256": "f" * 64,
            "archive": {"sha256": "f" * 64, "size": 4096},
        },
    }
    direct_manifest["inputs"]["hsroc_source_archive"] = dict(
        direct_manifest["hsroc_source_exception"]["archive"]
    )
    direct_manifest["inputs"]["rcmetar_source_archive"] = dict(
        direct_manifest["rcmetar_source"]["archive"]
    )
    assert (
        inspector.validate_direct_build_manifest(
            direct_manifest, target="macos-x64"
        )
        is direct_manifest
    )
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError, match="identity or target"
    ):
        inspector.validate_direct_build_manifest(
            direct_manifest, target="macos-arm64"
        )
    assert direct["official_r"]["url"] in spike
    assert direct["official_r"]["sha256"] in spike
    assert direct["ppm_snapshot"] in spike

    marker.unlink()
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError, match="marker.*probe disagree"
    ):
        inspector.validate_r_delivery_identity(
            app,
            runtime_probe,
            target="macos-x64",
            architecture="x86_64",
            source_commit="c" * 40,
        )

    marker.write_bytes((ROOT / "packaging/pyinstaller/direct-r-spike.marker").read_bytes())
    runtime_probe["r"]["direct_spike"] = False
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError, match="marker.*probe disagree"
    ):
        inspector.validate_r_delivery_identity(
            app,
            runtime_probe,
            target="macos-x64",
            architecture="x86_64",
            source_commit="c" * 40,
        )

    runtime_probe["r"]["direct_spike"] = True
    (app / "Contents/Resources/r-integration-kit").mkdir()
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError, match="mixes direct R spike"
    ):
        inspector.validate_r_delivery_identity(
            app,
            runtime_probe,
            target="macos-x64",
            architecture="x86_64",
            source_commit="c" * 40,
        )


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
    assert (
        'local timeout_seconds="${RCMS_PACKAGED_PROCESS_TIMEOUT_SECONDS:-900}"' in build
    )
    assert "RCMS_PACKAGED_PROCESS_TIMEOUT_SECONDS=60" in build
    assert '--timeout-seconds "$timeout_seconds"' in build
    assert "RCMS_PACKAGE_SMOKE_EVIDENCE" in build
    assert "RCMS_AUTOMATION_HANG_TRACE" in build
    assert "run_bounded_process.py" in build
    assert "from rc_metastudio.qt6_macos_feasibility import is_macho_candidate" in build
    assert "MACH_O_MAGICS" not in build
    assert 'open -W -n "$app_bundle" --args' in build
    assert "--automation-startup-completion-marker" in build
    assert '"$repo_root/scripts/sign_macos_app.py" "$app_bundle"' in build
    assert "--identity -" in build
    assert 'copy_tree "$r_runtime_root" "$r_version_root/Resources"' in build
    assert 'copy_tree "$r_runtime_root" "$app_root/R"' not in build
    assert "from rc_metastudio.r_runtime import macos_r_framework_version" in build
    assert "v$minor" not in build
    assert (
        'expected_r_home = app_root / "Contents/Frameworks/R.framework/Resources"'
        in text("scripts/inspect_macos_deployment.py")
    )
    assert 'mv "$r_version_root/Resources/lib/libR.dylib" "$r_version_root/R"' in build
    assert 'chmod +x "$r_version_root/R"' in build
    assert 'ln -s "../../R" "$r_version_root/Resources/lib/libR.dylib"' in build
    assert '"$python_exe" - "$r_version_root" > "$macho_manifest"' in build
    assert 'ln -s "$r_framework_version" "$r_framework/Versions/Current"' in build
    assert 'ln -s "Versions/Current/Resources" "$r_framework/Resources"' in build
    assert 'ln -s "Versions/Current/R" "$r_framework/R"' in build
    assert '"CFBundlePackageType": "FMWK"' in build
    assert (
        'python3 - "$zip_path" "$archive_root_name" "$skip_smoke" '
        '"$r_framework_version"' in build
    )
    assert 'f"{resources}/bin/Rscript"' in build
    assert "R.framework/Resources/bin/Rscript" not in build
    assert 'f"{framework}/Versions/Current": framework_version' in build
    assert 'f"{framework}/Resources": "Versions/Current/Resources"' in build
    assert "r_source_relative()" in build
    assert build.count('r_source_relative "$') == 4
    assert "/Library/Frameworks/R.framework/Resources/*)" in build
    assert "/Library/Frameworks/R.framework/Versions/*/Resources/*)" in build
    assert "/Library/Frameworks/R.framework/R|" in build
    assert "Unsupported source R framework dependency" in build
    assert "Unsupported source R framework install ID" in build
    assert "grep -F '/Library/Frameworks/R.framework/'" in build
    assert 'scripts/normalize_macos_macho.py"' in build
    assert '--manifest "$macho_manifest" --architecture "$expected_machine"' in build
    assert build.count('--target "macos-$architecture"') >= 3
    assert "find \"$app_bundle\" -type f -name '_rinterface_cffi_api*.so'" in build
    assert "forbidden rpy2 ABI-mode fallback bridge" in build
    assert "scripts/relocate_rpy2_api_bridge.py" in build
    assert "--api-bridge-transformation" in build
    assert '"cffi_mode": os.environ.get("RPY2_CFFI_MODE")' in text(
        "src/rc_metastudio/launch.py"
    )
    assert "codesign --force --deep" not in build
    signer = text("scripts/sign-notarize-macos-package.sh")
    assert 'scripts/sign_macos_app.py "$app"' in signer
    assert 'find "$app" -type f' not in signer
    assert "codesign --force --deep" not in signer
    assert 'signing_inventory="${output}.signing-inventory.json"' in signer
    assert (
        signer.index("scripts/sign_macos_app.py")
        < signer.index("r_kit_derivation.py finalize")
        < signer.index(
            'codesign --force --options runtime --timestamp --sign "$RCMS_APPLE_SIGNING_IDENTITY" "$app"'
        )
        < signer.index("notarytool submit")
    )
    release_workflow = text(".github/workflows/release-candidate.yml")
    assert "$env:ARTIFACT.signing-inventory.json" in release_workflow
    assert "release/*.signing-inventory.json" in release_workflow
    assert (
        build.index('if [ "$skip_clean" -eq 0 ]')
        < build.index('rm -rf "$qualification_root"')
        < build.index('mkdir -p "$qualification_root"')
    )
    assert "${{ inputs.artifact_name }}-evidence" in workflow_text
    assert "*-archive-inspection.json" in workflow_text
    assert "packaged-smoke*.log" in workflow_text
    assert "--expected-r-integration-kit-sha256" in text("scripts/package-macos.sh")
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


def test_signing_derivation_resolves_framework_api_bridge_from_final_path(tmp_path):
    app = tmp_path / "RCMetaStudio.app"
    app_root = app / "Contents/MacOS"
    bridge = app / "Contents/Frameworks/python/_rinterface_cffi_api.so"
    shared_r = app / "Contents/Frameworks/R.framework/Versions/4.6/R"
    bridge.parent.mkdir(parents=True)
    shared_r.parent.mkdir(parents=True)
    app_root.mkdir(parents=True)
    bridge.write_bytes(b"bridge")
    shared_r.write_bytes(b"R")
    derivation = tmp_path / "derivation.json"
    derivation.write_text(
        json.dumps(
            {
                "final": {
                    "api_bridge": {
                        "path": os.path.relpath(bridge, app_root).replace("\\", "/")
                    },
                    "r_shared_library": {
                        "path": os.path.relpath(shared_r, app_root).replace("\\", "/")
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/r_kit_derivation.py",
            "resolve-final",
            "--app-root",
            str(app_root),
            "--derivation",
            str(derivation),
            "--name",
            "api_bridge",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert Path(completed.stdout.strip()) == bridge.resolve()
    signer = text("scripts/sign-notarize-macos-package.sh")
    assert "resolve-final" in signer
    assert signer.index("r_kit_derivation.py finalize") < signer.index(
        'codesign --force --options runtime --timestamp --sign "$RCMS_APPLE_SIGNING_IDENTITY" "$app"'
    )


def test_r_relocation_maps_versioned_and_canonical_framework_load_commands():
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is required to execute the production relocation mapper")
    build = text("scripts/build-macos-package.sh")
    start = build.index("r_source_relative() {")
    end = build.index("\n}\n\nrelocate_bundled_r_runtime()", start) + 3
    function = build[start:end]
    runtime_root = "/Library/Frameworks/R.framework/Versions/4.6/Resources"
    paths = [
        f"{runtime_root}/lib/libR.dylib",
        "/Library/Frameworks/R.framework/Versions/4.6/Resources/lib/libR.dylib",
        "/Library/Frameworks/R.framework/Resources/lib/libR.dylib",
        "/Library/Frameworks/R.framework/R",
        "/Library/Frameworks/R.framework/Versions/4.6/R",
        "/opt/R/x86_64/lib/libgfortran.5.dylib",
        "/opt/R/x86_64/lib/libtcl8.6.dylib",
        "/opt/X11/lib/libX11.6.dylib",
        "/opt/R/x86_64/include/unsupported.h",
        "/opt/X11/include/unsupported.h",
        "/Library/Frameworks/R.framework/PrivateHeaders/unsupported.h",
        "/usr/lib/libSystem.B.dylib",
    ]
    command = (
        function
        + r"""
r_runtime_root="$1"
shift
for path in "$@"; do
  if relative="$(r_source_relative "$path")"; then
    printf '0:%s\n' "$relative"
  else
    printf '%s:\n' "$?"
  fi
done
"""
    )
    completed = subprocess.run(
        [bash, "-c", command, "relocation-test", runtime_root, *paths],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.splitlines() == [
        "0:lib/libR.dylib",
        "0:lib/libR.dylib",
        "0:lib/libR.dylib",
        "0:lib/libR.dylib",
        "0:lib/libR.dylib",
        "0:lib/libgfortran.5.dylib",
        "2:",
        "1:",
        "2:",
        "1:",
        "2:",
        "1:",
    ]


def test_macos_packager_profiles_optional_x11_r_surfaces_before_relocation():
    build = text("scripts/build-macos-package.sh")

    assert "bundle_external_r_runtime_dylibs()" in build
    assert 'case "$dependency" in' in build
    assert "/opt/R/*/lib/*.dylib)" in build
    assert "/opt/X11/lib/*.dylib" not in build
    assert "profile_macos_embedded_r_runtime.py" in build
    assert "Applying the explicit non-X11 embedded R product profile" in build
    assert build.index("profile_macos_embedded_r_runtime.py") < build.rindex(
        "relocate_bundled_r_runtime"
    )
    assert "libtcl*.dylib|libtk*.dylib" in build
    assert 'target="$r_home/$source_relative"' in build
    assert 'cp -p "$dependency" "$target"' in build
    assert 'write_bundled_r_macho_manifest "$macho_manifest"' in build
    assert "External R runtime dependency closure exceeded 16 passes" in build
    assert "normalize_macos_macho.py" in build
    assert "grep -F '/opt/R/'" in build
    assert "grep -F '/opt/X11/'" in build


def test_r_macho_normalizer_thins_universal_and_rejects_unusable_slices(
    monkeypatch, tmp_path
):
    normalizer = load_macho_normalizer()
    universal = tmp_path / "universal.dylib"
    thin = tmp_path / "thin.dylib"
    arm_only = tmp_path / "arm-only.dylib"
    failed = tmp_path / "failed-thin.dylib"
    universal.write_text("x86_64 arm64:universal", encoding="utf-8")
    thin.write_text("x86_64:thin", encoding="utf-8")
    arm_only.write_text("arm64:arm", encoding="utf-8")
    failed.write_text("x86_64 arm64:fail", encoding="utf-8")
    universal.chmod(0o751)
    original_mode = stat.S_IMODE(universal.stat().st_mode)

    def fake_lipo(arguments):
        if arguments[0] == "-archs":
            path = Path(arguments[1])
            architectures = path.read_text(encoding="utf-8").split(":", 1)[0]
            return subprocess.CompletedProcess(arguments, 0, architectures + "\n", "")
        assert arguments[:2] == ["-thin", "x86_64"]
        source = Path(arguments[2])
        output = Path(arguments[4])
        if source == failed:
            raise normalizer.MachONormalizationError("controlled thinning failure")
        output.write_text("x86_64:thinned", encoding="utf-8")
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(normalizer, "_run_lipo", fake_lipo)
    manifest = tmp_path / "r-machos.list"
    manifest.write_bytes(os.fsencode(universal) + b"\0" + os.fsencode(thin) + b"\0")

    assert normalizer.normalize_manifest(manifest) == 2
    assert universal.read_text(encoding="utf-8") == "x86_64:thinned"
    assert stat.S_IMODE(universal.stat().st_mode) == original_mode
    assert thin.read_text(encoding="utf-8") == "x86_64:thin"

    with pytest.raises(normalizer.MachONormalizationError, match="no x86_64 slice"):
        normalizer.normalize_macho(arm_only)
    with pytest.raises(
        normalizer.MachONormalizationError, match="controlled thinning failure"
    ):
        normalizer.normalize_macho(failed)
    assert failed.read_text(encoding="utf-8") == "x86_64 arm64:fail"
    assert not list(tmp_path.glob(".failed-thin.dylib.thin-*"))


def test_macos_inventory_allows_only_the_rpy2_api_native_bridge():
    inspector = load_inspector()
    support_record = {
        "path": (
            "Contents/Frameworks/rpy2/rinterface_lib/"
            "_bufferprotocol.cpython-311-darwin.so"
        ),
        "kind": "file",
        "architectures": ["x86_64"],
    }
    api_record = {
        "path": "Contents/Frameworks/_rinterface_cffi_api.abi3.so",
        "kind": "file",
        "architectures": ["x86_64"],
    }
    inspector.validate_rpy2_api_payload([support_record, api_record])
    abi_record = {"path": "Contents/Frameworks/_rinterface_cffi_abi.py", "kind": "file"}
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError,
        match="forbidden rpy2 ABI-mode fallback bridge",
    ):
        inspector.validate_rpy2_api_payload([support_record, api_record, abi_record])
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError,
        match="exactly one rpy2 API-mode bridge",
    ):
        inspector.validate_rpy2_api_payload([])


def test_macos_surface_smoke_exercises_native_acceptance_surfaces():
    launch = text("src/rc_metastudio/launch.py")
    native_dialog_bridge = launch.split("def _native_file_dialog_observation", 1)[
        1
    ].split("def start_package_surface_smoke", 1)[0]

    assert 'platform_name != "cocoa"' in launch
    assert '"native_menu": native_menu' in launch
    assert '"native_file_dialog": native_file_dialog' in launch
    assert '"accessibility": accessibility' in launch
    assert "DontUseNativeDialog" in launch
    assert "NATIVE_FILE_DIALOG_TIMEOUT_MS = 10_000" in launch
    assert "setWindowModality(QtCore.Qt.WindowModality.WindowModal)" in launch
    assert "file_dialog.open()" in launch
    assert "file_dialog.windowModality().name" in launch
    assert '"window_modality": "window-modal"' not in launch
    assert "event_loop.exec()" in launch
    assert "file_dialog.exec()" not in launch
    assert "app.processEvents()" not in native_dialog_bridge
    assert "file_dialog.close()" not in native_dialog_bridge
    assert '"native-file-dialog"' in launch
    assert '"surface_progress"' in launch
    assert 'checkpoint("native-file-dialog:open:start")' in launch
    assert 'checkpoint("native-file-dialog:open:return")' in launch
    assert 'checkpoint("native-file-dialog:timeout")' in launch
    assert 'evidence.pop("surface_progress", None)' in launch
    assert "CRITICAL_DIALOG_TIMEOUT_MS = 5_000" in launch
    assert "QMessageBox.Option.DontUseNativeDialog" in launch
    assert "ApplicationAttribute.AA_DontUseNativeDialogs" in launch
    assert "WidgetAttribute.WA_DontShowOnScreen" in launch
    assert 'observation["native_helper_active"] = (' in launch
    assert 'checkpoint("critical-dialog:show:start")' in launch
    assert 'checkpoint("critical-dialog:timeout")' in launch
    assert "QCoreApplication.sendPostedEvents" in launch
    assert "QEvent.Type.DeferredDelete" in launch
    assert 'checkpoint("cleanup:application-quit")' in launch
    assert "isNativeMenuBar" in launch
    assert "accessible_control.setFocus()" in launch
    assert "accessible_control.setFocus(QtCore.Qt.FocusReason" not in launch
    assert 'if sys.platform == "darwin" else {}' in launch
    assert 'legacy_selector = "accessibilityAttributeValue:"' in launch
    assert 'children_attribute = ns_string("AXChildren")' in launch
    assert "roots, bridge_supported = qnsview_children(native_view)" in launch
    assert '"title": text_message(receiver, "accessibilityTitle")' in launch
    assert '"description": text_message(receiver, "accessibilityLabel")' in launch
    assert 'receiver, "accessibilityIsIgnored"' in launch
    assert "isAccessibilityElement" not in launch
    assert 'expected_role="AXButton"' in launch
    assert 'get("role") != "AXButton"' in launch
    assert "roots = [native_view]" not in launch
    assert "_persist_package_surface_failure(" in launch
    assert '"packaged-surface:failed:"' in launch
    assert '"error_message": bounded_error_message(error)' in launch


def test_frozen_runtime_discovers_r_in_macos_framework(monkeypatch, tmp_path):
    from rc_metastudio import r_runtime

    macos_root = tmp_path / "RCMetaStudio.app" / "Contents" / "MacOS"
    r_home = (
        tmp_path
        / "RCMetaStudio.app"
        / "Contents"
        / "Frameworks"
        / "R.framework"
        / "Resources"
    )
    macos_root.mkdir(parents=True)
    (r_home / "bin").mkdir(parents=True)
    (r_home / "library" / "RCMetaR").mkdir(parents=True)
    isolated_environment = dict(os.environ)
    for name in ("RCMS_R_HOME", "RCMS_R_LIBS", "R_HOME", "R_LIBS", "R_LIBS_USER"):
        isolated_environment.pop(name, None)
    monkeypatch.setattr(r_runtime.os, "environ", isolated_environment)
    monkeypatch.setattr(r_runtime, "_DLL_DIRECTORY_HANDLES", [])
    monkeypatch.setattr(r_runtime, "_RUNTIME_IDENTITY", None)

    configured = r_runtime.configure_bundled_r_environment(str(macos_root))

    assert Path(configured["R_HOME"]).resolve() == r_home.resolve()
    assert Path(configured["R_LIBS"]).resolve() == (r_home / "library").resolve()
    assert configured["cffi_mode"] == "API"
    assert isolated_environment["R_ENVIRON_USER"] == os.devnull
    assert isolated_environment["R_PROFILE_USER"] == os.devnull


def test_frozen_runtime_ignores_poisoned_system_r_overrides(monkeypatch, tmp_path):
    from rc_metastudio import r_runtime

    app_root = tmp_path / "RCMetaStudio.app" / "Contents" / "MacOS"
    private = app_root.parent / "Frameworks" / "R.framework" / "Resources"
    (private / "bin").mkdir(parents=True)
    (private / "library" / "RCMetaR").mkdir(parents=True)
    shared_r = private / "lib" / "libR.dylib"
    shared_r.parent.mkdir(parents=True)
    shared_r.write_bytes(b"libR")
    api_bridge = app_root / "_rinterface_cffi_api.so"
    api_bridge.parent.mkdir(parents=True, exist_ok=True)
    api_bridge.write_bytes(b"api")
    metadata = app_root.parent / "Resources" / "r-integration-kit"
    metadata.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "kind": "rc-metastudio-r-integration-kit",
        "target": "macos-x64",
        "architecture": "x86_64",
        "cffi_mode": "API",
        "versions": {"r": "4.6.1", "python": "3.11.9", "rpy2": "3.6.7"},
        "files": [
            {
                "path": "bridge/_rinterface_cffi_api.so",
                "kind": "file",
                "sha256": hashlib.sha256(b"api").hexdigest(),
            },
            {
                "path": "runtime/Versions/4.6/R",
                "kind": "file",
                "sha256": hashlib.sha256(b"libR").hexdigest(),
            },
        ],
    }
    manifest["kit_sha256"] = r_runtime._canonical_manifest_digest(manifest)
    (metadata / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    derivation = {
        "schema_version": 1,
        "target": "macos-x64",
        "kit_sha256": manifest["kit_sha256"],
        "source": {
            "api_bridge": {
                "path": "bridge/_rinterface_cffi_api.so",
                "sha256": hashlib.sha256(b"api").hexdigest(),
            },
            "r_shared_library": {
                "path": "runtime/Versions/4.6/R",
                "sha256": hashlib.sha256(b"libR").hexdigest(),
            },
        },
        "pre_sign": {
            "api_bridge": {
                "path": "_rinterface_cffi_api.so",
                "sha256": hashlib.sha256(b"api").hexdigest(),
                "signing_identity": "unsigned",
            },
            "r_shared_library": {
                "path": "../Frameworks/R.framework/Resources/lib/libR.dylib",
                "sha256": hashlib.sha256(b"libR").hexdigest(),
                "signing_identity": "org.r-project.R",
            },
        },
        "final": {
            "api_bridge": {
                "path": "_rinterface_cffi_api.so",
                "sha256": hashlib.sha256(b"api").hexdigest(),
                "signing_identity": "_rinterface_cffi_api",
            },
            "r_shared_library": {
                "path": "../Frameworks/R.framework/Resources/lib/libR.dylib",
                "sha256": hashlib.sha256(b"libR").hexdigest(),
                "signing_identity": "org.r-project.R",
            },
        },
    }
    (metadata / "derivation.json").write_text(json.dumps(derivation), encoding="utf-8")
    poisoned = dict(
        os.environ,
        RCMS_R_HOME=str(tmp_path / "system-R"),
        RCMS_R_LIBS=str(tmp_path / "user-library"),
        PATH=str(tmp_path / "system-R/bin"),
    )
    monkeypatch.setattr(r_runtime.os, "environ", poisoned)
    monkeypatch.setattr(r_runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(r_runtime.sys, "platform", "darwin")
    monkeypatch.setattr(__import__("platform"), "machine", lambda: "x86_64")
    monkeypatch.setattr(r_runtime, "_RUNTIME_IDENTITY", None)
    monkeypatch.setattr(r_runtime, "_BOOTSTRAP_THREAD_ID", None)
    configured = r_runtime.configure_bundled_r_environment(str(app_root))
    assert Path(configured["R_HOME"]).resolve() == private.resolve()
    assert Path(configured["R_LIBS"]).resolve() == (private / "library").resolve()
    assert configured["cffi_mode"] == "API"
    assert str(tmp_path / "system-R/bin") not in poisoned["PATH"]
    derivation["pre_sign"]["api_bridge"]["sha256"] = "0" * 64
    (metadata / "derivation.json").write_text(json.dumps(derivation), encoding="utf-8")
    monkeypatch.setattr(r_runtime, "_RUNTIME_IDENTITY", None)
    monkeypatch.setattr(r_runtime, "_BOOTSTRAP_THREAD_ID", None)
    with pytest.raises(RuntimeError, match="derivation chain"):
        r_runtime.configure_bundled_r_environment(str(app_root))


def test_frozen_runtime_rejects_missing_kit_before_rpy2_import(monkeypatch, tmp_path):
    from rc_metastudio import r_runtime

    app_root = tmp_path / "RCMetaStudio.app" / "Contents" / "MacOS"
    app_root.mkdir(parents=True)
    monkeypatch.setattr(r_runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(r_runtime.sys, "platform", "darwin")
    monkeypatch.setattr(r_runtime, "_RUNTIME_IDENTITY", None)
    monkeypatch.setattr(r_runtime, "_BOOTSTRAP_THREAD_ID", None)
    isolated = dict(os.environ, RCMS_DIRECT_R_SPIKE="1")
    monkeypatch.setattr(r_runtime.os, "environ", isolated)
    with pytest.raises(RuntimeError, match="integration-kit identity"):
        r_runtime.configure_bundled_r_environment(str(app_root))

    private = app_root.parent / "Frameworks" / "R.framework" / "Resources"
    (private / "bin").mkdir(parents=True)
    (private / "library" / "RCMetaR").mkdir(parents=True)
    marker = app_root.parent / "Resources" / "direct-r-spike.marker"
    marker.parent.mkdir(parents=True)
    marker.write_text("non-release spike", encoding="utf-8")
    monkeypatch.setattr(
        r_runtime, "_configure_private_runtime_directories", lambda _root: None
    )
    configured = r_runtime.configure_bundled_r_environment(str(app_root))
    assert configured["direct_spike"] is True
    assert configured["kit_sha256"] is None
    assert Path(configured["R_HOME"]).resolve() == private.resolve()


def test_frozen_macos_sample_projects_use_bundle_resources(monkeypatch):
    import rc_metastudio.settings as settings

    monkeypatch.setattr(settings.sys, "frozen", True, raising=False)
    monkeypatch.setattr(settings.sys, "platform", "darwin")
    monkeypatch.setattr(
        settings.sys,
        "executable",
        "/Applications/RCMetaStudio.app/Contents/MacOS/RCMetaStudio",
    )

    assert settings.get_sample_projects_path() == (
        "/Applications/RCMetaStudio.app/Contents/Resources/sample_projects"
    )


def test_frozen_windows_sample_projects_remain_colocated(monkeypatch):
    import rc_metastudio.settings as settings

    monkeypatch.setattr(settings.sys, "frozen", True, raising=False)
    monkeypatch.setattr(settings.sys, "platform", "win32")
    monkeypatch.setattr(settings.sys, "executable", r"C:\RCMetaStudio\RCMetaStudio.exe")

    assert settings.get_sample_projects_path() == r"C:\RCMetaStudio\sample_projects"


def test_macho_parser_rejects_arm_and_universal_payloads_for_x64(tmp_path):
    inspector = load_inspector()
    x64 = tmp_path / "x64"
    arm = tmp_path / "arm"
    x64.write_bytes(thin_macho(0x01000007, 3))
    arm.write_bytes(thin_macho(0x0100000C, 0))

    assert inspector.macho_architectures(x64) == ["x86_64"]
    assert inspector.macho_architectures(arm) == ["arm64"]
    inspector.require_x64_macho(x64)
    inspector.require_macho_architecture(arm, "arm64")
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="x86_64-only"):
        inspector.require_x64_macho(arm)
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="arm64-only"):
        inspector.require_macho_architecture(x64, "arm64")


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("cmd LC_BUILD_VERSION\n minos 14.0\n sdk 15.0", "14.0"),
        ("cmd LC_VERSION_MIN_MACOSX\n version 13.0\n sdk 14.0", "13.0"),
    ],
)
def test_macho_deployment_target_parses_modern_and_legacy_commands(command, expected):
    inspector = load_inspector()
    assert inspector._minimum_macos_from_load_commands(command) == expected


def test_macho_discriminator_excludes_java_without_trusting_extensions(
    monkeypatch, tmp_path
):
    inspector = load_inspector()
    import rc_metastudio.qt6_macos_feasibility as feasibility

    java_class = tmp_path / "getsp.class"
    disguised_java = tmp_path / "libjava.dylib"
    java_class.write_bytes(minimal_java_class())
    disguised_java.write_bytes(minimal_java_class())
    for path in (java_class, disguised_java):
        assert feasibility.is_valid_java_class(path)
        assert not feasibility.is_macho_candidate(path)

    preview_class = tmp_path / "preview.class"
    preview_class.write_bytes(minimal_java_class(major=56, minor=0xFFFF))
    assert feasibility.is_valid_java_class(preview_class)
    assert not feasibility.is_macho_candidate(preview_class)

    malformed_java_payloads = {
        "preview-before-java-12": minimal_java_class(major=55, minor=0xFFFF),
        "nonzero-legacy-minor": minimal_java_class(major=46, minor=1),
        "raw-nul": minimal_java_class(class_name=b"Exa\x00ple"),
        "bad-continuation": minimal_java_class(class_name=b"Ex\xc2mple"),
        "overlong-non-null": minimal_java_class(class_name=b"Ex\xc0\x81ple"),
        "four-byte-standard-utf8": minimal_java_class(
            class_name=b"\xf0\x90\x80\x80abc"
        ),
    }
    for name, payload in malformed_java_payloads.items():
        malformed_java = tmp_path / f"{name}.class"
        malformed_java.write_bytes(payload)
        assert not feasibility.is_valid_java_class(malformed_java)
        assert feasibility.is_macho_candidate(malformed_java)

    large_attribute = tmp_path / "large-attribute.class"
    large_attribute.write_bytes(minimal_java_class(attribute_body=b"x" * 1_000_000))
    original_read = feasibility._read_java_bytes

    def reject_unbounded_read(stream, size, label):
        assert size < 100_000, f"attribute body was materialized: {size}"
        return original_read(stream, size, label)

    monkeypatch.setattr(feasibility, "_read_java_bytes", reject_unbounded_read)
    assert feasibility.is_valid_java_class(large_attribute)
    assert not feasibility.is_macho_candidate(large_attribute)

    thin_with_java_extension = tmp_path / "native.class"
    thin_with_java_extension.write_bytes(thin_macho(0x01000007, 3))
    assert feasibility.is_macho_candidate(thin_with_java_extension)
    assert inspector.macho_architectures(thin_with_java_extension) == ["x86_64"]

    fat_with_java_extension = tmp_path / "universal.class"
    fat_with_java_extension.write_bytes(fat_x64_macho())
    assert feasibility.is_macho_candidate(fat_with_java_extension)
    assert inspector.macho_architectures(fat_with_java_extension) == ["x86_64"]

    malformed_collision = tmp_path / "malformed.class"
    malformed_collision.write_bytes(b"\xca\xfe\xba\xbe\x00\x00\x00\x01")
    assert not feasibility.is_valid_java_class(malformed_collision)
    assert feasibility.is_macho_candidate(malformed_collision)
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="truncated"):
        inspector.macho_architectures(malformed_collision)

    unreadable = tmp_path / "unreadable"
    unreadable.write_bytes(thin_macho(0x01000007, 3))
    original_open = Path.open

    def deny_target(path, *args, **kwargs):
        if path == unreadable:
            raise PermissionError("denied by test")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_target)
    with pytest.raises(PermissionError, match="denied by test"):
        feasibility.is_macho_candidate(unreadable)
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError, match="cannot classify"
    ):
        inspector._is_macho(unreadable)


def test_explicit_codesign_plan_ignores_dotted_resources_and_covers_native_code(
    tmp_path,
):
    signer = load_macos_signer()
    app = tmp_path / "RCMetaStudio.app"
    app_executable = macos_code_bundle(app, executable_name="RCMetaStudio")
    r_framework = app / "Contents" / "Frameworks" / "R.framework"
    r_executable = macos_code_bundle(r_framework, executable_name="R", framework=True)
    qt_framework = app / "Contents" / "Frameworks" / "QtCore.framework"
    framework_executable = macos_code_bundle(
        qt_framework, executable_name="QtCore", framework=True
    )
    dotted_resource = (
        app
        / "Contents"
        / "Resources"
        / "R"
        / "library"
        / "rmarkdown"
        / "rmd"
        / "h"
        / "navigation-1.1"
    )
    dotted_resource.mkdir(parents=True)
    for resource_name in (
        "codefolding-lua.css",
        "codefolding.js",
        "sourceembed.js",
        "tabsets.js",
    ):
        (dotted_resource / resource_name).write_text("data", encoding="utf-8")
    resource_bundle = dotted_resource / "assets.bundle"
    resource_bundle.mkdir()
    (resource_bundle / "Info.plist").write_text("not bundle metadata", encoding="utf-8")

    plan = signer.build_signing_plan(app)

    assert set(plan.native_files) == {
        app_executable,
        r_executable,
        framework_executable,
    }
    assert set(plan.nested_bundles) == {qt_framework, r_framework}
    assert dotted_resource not in plan.signing_targets
    assert resource_bundle not in plan.signing_targets
    assert all(dotted_resource not in path.parents for path in plan.signing_targets)


def test_explicit_codesign_signs_inside_out_and_verifies_fail_closed(
    monkeypatch, tmp_path
):
    signer = load_macos_signer()
    app = tmp_path / "RCMetaStudio.app"
    app_executable = macos_code_bundle(app, executable_name="RCMetaStudio")
    native = app / "Contents" / "Frameworks" / "libR.dylib"
    native.parent.mkdir(parents=True)
    native.write_bytes(thin_macho(0x01000007, 3))
    framework = app / "Contents" / "Frameworks" / "QtCore.framework"
    framework_executable = macos_code_bundle(
        framework, executable_name="QtCore", framework=True
    )
    calls = []
    monkeypatch.setattr(
        signer, "_run_codesign", lambda arguments: calls.append(arguments)
    )

    plan = signer.sign_and_verify(app, identity="Developer ID Application: Example")

    sign_calls = [call for call in calls if "--sign" in call]
    signed_targets = [Path(call[-1]) for call in sign_calls]
    assert set(signed_targets[:-2]) == {app_executable, native, framework_executable}
    assert signed_targets[-2:] == [framework, app]
    assert signed_targets.index(framework_executable) < signed_targets.index(framework)
    assert signed_targets.index(framework) < signed_targets.index(app)
    assert all("--deep" not in call for call in sign_calls)
    assert all("--options" in call and "runtime" in call for call in sign_calls)
    assert all("--timestamp" in call for call in sign_calls)
    assert set(plan.native_files) == {app_executable, native, framework_executable}

    verify_calls = [call for call in calls if "--verify" in call]
    assert any("--deep" in call and Path(call[-1]) == app for call in verify_calls)
    individually_verified = {
        Path(call[-1]) for call in verify_calls if "--deep" not in call
    }
    assert individually_verified == {
        app_executable,
        native,
        framework_executable,
        framework,
        app,
    }

    calls.clear()
    signer.sign_and_verify(app, identity="-")
    ad_hoc_sign_calls = [call for call in calls if "--sign" in call]
    assert all("--timestamp" not in call for call in ad_hoc_sign_calls)

    def reject_verification(arguments):
        if "--verify" in arguments:
            raise signer.MacOSSigningError("verification rejected")

    monkeypatch.setattr(signer, "_run_codesign", reject_verification)
    with pytest.raises(signer.MacOSSigningError, match="verification rejected"):
        signer.sign_and_verify(app, identity="-")


def test_explicit_codesign_rejects_native_inventory_drift(monkeypatch, tmp_path):
    signer = load_macos_signer()
    app = tmp_path / "RCMetaStudio.app"
    macos_code_bundle(app, executable_name="RCMetaStudio")
    injected = app / "Contents" / "MacOS" / "late.dylib"
    calls = 0

    def mutate_after_first_sign(arguments):
        nonlocal calls
        calls += 1
        if calls == 1:
            injected.write_bytes(thin_macho(0x01000007, 3))

    monkeypatch.setattr(signer, "_run_codesign", mutate_after_first_sign)

    with pytest.raises(signer.MacOSSigningError, match="inventory changed"):
        signer.sign_and_verify(app, identity="-")


def test_explicit_codesign_rejects_malformed_native_bundle(tmp_path):
    signer = load_macos_signer()
    old_layout = tmp_path / "OldLayout.app"
    macos_code_bundle(old_layout, executable_name="RCMetaStudio")
    old_r_data = old_layout / "Contents" / "MacOS" / "R" / "library" / "data.txt"
    old_r_data.parent.mkdir(parents=True)
    old_r_data.write_text("data", encoding="utf-8")
    with pytest.raises(signer.MacOSSigningError, match="non-code payload"):
        signer.build_signing_plan(old_layout)

    app = tmp_path / "RCMetaStudio.app"
    macos_code_bundle(app, executable_name="RCMetaStudio")
    malformed = app / "Contents" / "PlugIns" / "Broken.bundle"
    native = malformed / "Contents" / "MacOS" / "Broken"
    native.parent.mkdir(parents=True)
    native.write_bytes(thin_macho(0x01000007, 3))

    with pytest.raises(signer.MacOSSigningError, match="malformed nested code bundle"):
        signer.build_signing_plan(app)


def test_explicit_codesign_rejects_loose_native_code_in_resources(tmp_path):
    signer = load_macos_signer()
    app = tmp_path / "RCMetaStudio.app"
    macos_code_bundle(app, executable_name="RCMetaStudio")
    loose_native = app / "Contents" / "Resources" / "R" / "lib" / "libR.dylib"
    loose_native.parent.mkdir(parents=True)
    loose_native.write_bytes(thin_macho(0x01000007, 3))

    with pytest.raises(
        signer.MacOSSigningError,
        match="Contents/Resources contains native code outside a validated nested code bundle",
    ):
        signer.build_signing_plan(app)


def test_archive_inspection_rejects_case_collisions(tmp_path):
    inspector = load_inspector()
    archive = tmp_path / "package.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(zip_info("root/RCMetaStudio.app/a", stat.S_IFREG | 0o644), b"a")
        bundle.writestr(zip_info("root/RCMetaStudio.app/A", stat.S_IFREG | 0o644), b"b")

    with pytest.raises(
        inspector.MacOSDeploymentInspectionError, match="case-colliding"
    ):
        inspector.inspect_archive(archive, archive_root_name="root", embedded_files={})


def test_archive_inspection_enforces_canonical_r_framework_symlinks_and_members(
    tmp_path,
):
    inspector = load_inspector()
    assert inspector.macos_r_framework_version("4.6.1") == "4.6"
    framework = "Contents/Frameworks/R.framework"
    version_root = f"{framework}/Versions/4.6"
    resources = f"{version_root}/Resources"
    payloads = {
        "Contents/MacOS/RCMetaStudio": b"app",
        f"{resources}/bin/Rscript": b"rscript",
        f"{resources}/library/RCMetaR/DESCRIPTION": b"package",
        f"{resources}/Info.plist": b"plist",
        f"{version_root}/R": b"libR",
    }
    link_targets = {
        f"{framework}/Versions/Current": "4.6",
        f"{framework}/Resources": "Versions/Current/Resources",
        f"{resources}/lib/libR.dylib": "../../R",
        f"{framework}/R": "Versions/Current/R",
    }
    resolved_links = {
        f"{framework}/Versions/Current": version_root,
        f"{framework}/Resources": resources,
        f"{resources}/lib/libR.dylib": f"{version_root}/R",
        f"{framework}/R": f"{version_root}/R",
    }

    def make_records(*, missing: str | None = None, wrong_link: str | None = None):
        records = []
        for path, payload in payloads.items():
            if path == missing:
                continue
            record = {
                "path": path,
                "kind": "file",
                "size": len(payload),
                "mode": (
                    0o755 if path.endswith(("RCMetaStudio", "Rscript", "/R")) else 0o644
                ),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            if path in {
                "Contents/MacOS/RCMetaStudio",
                f"{version_root}/R",
            }:
                record["architectures"] = ["x86_64"]
            records.append(record)
        for path, target in link_targets.items():
            actual_target = "Versions/4.5/Resources" if path == wrong_link else target
            records.append(
                {
                    "path": path,
                    "kind": "symlink",
                    "size": len(actual_target),
                    "mode": 0o777,
                    "link_target": actual_target,
                    "resolved_path": resolved_links[path],
                }
            )
        return records

    kit_records = make_records()
    direct_version_root = f"{framework}/Versions/4.6-x86_64"
    direct_resources = f"{direct_version_root}/Resources"
    direct_records = []
    for path, payload, native in (
        (f"{direct_resources}/bin/R", b"#!/bin/sh\n", False),
        (f"{direct_resources}/bin/Rscript", b"rscript", True),
        (f"{direct_resources}/bin/exec/R", b"r-exec", True),
        (f"{direct_resources}/lib/libR.dylib", b"libR", True),
        (f"{direct_resources}/library/RCMetaR/DESCRIPTION", b"package", False),
        (f"{direct_resources}/Info.plist", b"plist", False),
    ):
        record = {
            "path": path,
            "kind": "file",
            "size": len(payload),
            "mode": 0o755 if "/bin/" in path or native else 0o644,
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        if native:
            record["architectures"] = ["x86_64"]
        if path.endswith("/bin/R"):
            record["shebang"] = "#!/bin/sh"
        direct_records.append(record)
    for path, target, resolved in (
        (f"{framework}/Versions/Current", "4.6-x86_64", direct_version_root),
        (
            f"{framework}/Resources",
            "Versions/Current/Resources",
            direct_resources,
        ),
        (
            f"{framework}/R",
            "Versions/Current/R",
            f"{direct_resources}/lib/libR.dylib",
        ),
        (
            f"{direct_version_root}/R",
            "Resources/lib/libR.dylib",
            f"{direct_resources}/lib/libR.dylib",
        ),
        (f"{direct_resources}/R", "bin/R", f"{direct_resources}/bin/R"),
    ):
        direct_records.append(
            {
                "path": path,
                "kind": "symlink",
                "size": len(target),
                "mode": 0o777,
                "link_target": target,
                "resolved_path": resolved,
            }
        )
    inspector.validate_r_framework_inventory(
        direct_records, delivery_kind="direct-spike", architecture="x86_64"
    )
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError,
        match="missing its concrete versioned member",
    ):
        inspector.validate_r_framework_inventory(
            direct_records, delivery_kind="integration-kit", architecture="x86_64"
        )
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError,
        match="shell front-end",
    ):
        inspector.validate_r_framework_inventory(
            kit_records, delivery_kind="direct-spike", architecture="x86_64"
        )

    def write_fixture(name: str, records: list[dict]):
        archive = tmp_path / f"{name}.zip"
        manifest = tmp_path / f"{name}-deployment.json"
        signing = tmp_path / f"{name}-signing.json"
        native_files = sorted(
            record["path"] for record in records if "architectures" in record
        )
        signing_payload = {
            "schema_version": 1,
            "app": "RCMetaStudio.app",
            "identity": "ad-hoc",
            "native_files": native_files,
            "nested_bundles": [framework],
            "verification": {"individual_strict": True, "outer_deep_strict": True},
        }
        signing.write_text(json.dumps(signing_payload), encoding="utf-8")
        manifest.write_text(
            json.dumps(
                {
                    "target": "macos-x64",
                    "r_integration_kit": {"kit_sha256": "a" * 64},
                    "signing_inventory": {
                        "path": "qualification/ad-hoc-signing-inventory.json",
                        "sha256": hashlib.sha256(signing.read_bytes()).hexdigest(),
                        "identity": "ad-hoc",
                        "native_files": native_files,
                        "nested_bundles": [framework],
                    },
                    "inventory": {"files": records},
                }
            ),
            encoding="utf-8",
        )
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr(
                zip_info(
                    "root/qualification/deployment-manifest.json",
                    stat.S_IFREG | 0o644,
                ),
                manifest.read_bytes(),
            )
            bundle.writestr(
                zip_info(
                    "root/qualification/ad-hoc-signing-inventory.json",
                    stat.S_IFREG | 0o644,
                ),
                signing.read_bytes(),
            )
            for record in records:
                payload = (
                    record["link_target"].encode("utf-8")
                    if record["kind"] == "symlink"
                    else payloads[record["path"]]
                )
                bundle.writestr(
                    zip_info(
                        f"root/RCMetaStudio.app/{record['path']}",
                        (stat.S_IFLNK if record["kind"] == "symlink" else stat.S_IFREG)
                        | record["mode"],
                    ),
                    payload,
                )
        return archive, manifest, signing

    valid = write_fixture("valid", make_records())
    assert (
        inspector.inspect_archive(
            valid[0],
            archive_root_name="root",
            embedded_files={
                "qualification/deployment-manifest.json": valid[1],
                "qualification/ad-hoc-signing-inventory.json": valid[2],
            },
        )["target"]
        == "macos-x64"
    )

    missing = write_fixture(
        "missing-versioned-rscript",
        make_records(missing=f"{resources}/bin/Rscript"),
    )
    wrong = write_fixture(
        "wrong-resources-link",
        make_records(wrong_link=f"{framework}/Resources"),
    )
    for fixture, expected in (
        (missing, "missing its concrete versioned member"),
        (wrong, "alias is missing or noncanonical"),
    ):
        with pytest.raises(inspector.MacOSDeploymentInspectionError, match=expected):
            inspector.inspect_archive(
                fixture[0],
                archive_root_name="root",
                embedded_files={
                    "qualification/deployment-manifest.json": fixture[1],
                    "qualification/ad-hoc-signing-inventory.json": fixture[2],
                },
            )


def test_smoke_finalizer_requires_the_post_close_marker(tmp_path):
    inspector = load_inspector()
    evidence = tmp_path / "smoke.json"
    log = tmp_path / "smoke.log"
    evidence.write_text(json.dumps({"passed": True}), encoding="utf-8")
    log.write_text("packaged-workflow:start\n", encoding="utf-8")

    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="post-close"):
        inspector.finalize_smoke_evidence(evidence, log)

    evidence.write_text(
        json.dumps({"passed": True, "failures": [{"stage": "accessibility"}]}),
        encoding="utf-8",
    )
    log.write_text("packaged-workflow:post-close\n", encoding="utf-8")
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError,
        match="failed native observations",
    ):
        inspector.finalize_smoke_evidence(evidence, log)

    evidence.write_text(
        json.dumps(
            {
                "passed": True,
                "surface_progress": {
                    "requested": "1.25",
                    "stage": "native-file-dialog:open:start",
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError,
        match="failed native observations",
    ):
        inspector.finalize_smoke_evidence(evidence, log)


def test_smoke_finalizer_authenticates_launchservices_completion(tmp_path):
    inspector = load_inspector()
    evidence = tmp_path / "smoke.json"
    log = tmp_path / "smoke.log"
    marker = tmp_path / "launchservices.json"
    evidence.write_text(json.dumps({"passed": True}), encoding="utf-8")
    log.write_text("packaged-workflow:post-close\n", encoding="utf-8")
    marker.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pid": 123,
                "platform_plugin": "cocoa",
                "project": "amino.rcms",
                "post_close": True,
            }
        ),
        encoding="utf-8",
    )

    finalized = inspector.finalize_smoke_evidence(evidence, log, marker)
    assert finalized["execution"]["launchservices_completion_marker"] is True
    marker.write_text(
        marker.read_text().replace('"cocoa"', '"offscreen"'), encoding="utf-8"
    )
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError, match="LaunchServices"
    ):
        inspector.finalize_smoke_evidence(evidence, log, marker)


def test_dependency_graph_rejects_missing_target(tmp_path):
    inspector = load_inspector()
    executable = tmp_path / "Contents/MacOS/RCMetaStudio"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"exe")
    records = [
        {
            "path": "Contents/MacOS/RCMetaStudio",
            "architectures": ["x86_64"],
            "install_id": None,
            "rpaths": [],
            "dependencies": ["@loader_path/missing.dylib"],
        }
    ]
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError, match="resolve uniquely"
    ):
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
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError, match="resolve uniquely"
    ):
        inspector.validate_dependency_graph(records, app_root=tmp_path)


def test_dependency_graph_rejects_duplicate_identity(tmp_path):
    inspector = load_inspector()
    for relative in ("Contents/MacOS/one.dylib", "Contents/Frameworks/two.dylib"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"native")
    records = [
        {
            "path": relative,
            "architectures": ["x86_64"],
            "install_id": "@rpath/duplicate.dylib",
            "rpaths": [],
            "dependencies": [],
        }
        for relative in ("Contents/MacOS/one.dylib", "Contents/Frameworks/two.dylib")
    ]
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError,
        match="duplicate Mach-O install identity",
    ):
        inspector.validate_dependency_graph(records, app_root=tmp_path)


def test_dependency_graph_rejects_mismatched_x64_target(tmp_path):
    inspector = load_inspector()
    executable = tmp_path / "Contents/MacOS/RCMetaStudio"
    target = tmp_path / "Contents/MacOS/libtarget.dylib"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"exe")
    target.write_bytes(b"target")
    records = [
        {
            "path": "Contents/MacOS/RCMetaStudio",
            "architectures": ["x86_64"],
            "install_id": None,
            "rpaths": [],
            "dependencies": ["@loader_path/libtarget.dylib"],
        },
        {
            "path": "Contents/MacOS/libtarget.dylib",
            "architectures": ["arm64"],
            "install_id": "@rpath/libtarget.dylib",
            "rpaths": [],
            "dependencies": [],
        },
    ]
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError, match="not x86_64-only"
    ):
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
            "uuid": "locked",
            "install_id": None,
            "rpaths": [],
            "text_section_sha256": "locked-code",
        },
    )
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError, match="locked wheel identity"
    ):
        inspector.validate_locked_qt_inventory(
            [
                {
                    "qt_relative_path": "plugins/platforms/libqcocoa.dylib",
                    "architectures": ["x86_64"],
                    "uuid": "locked",
                    "text_section_sha256": "mutated-code",
                    "sha256": "0" * 64,
                }
            ],
            locked_qt_root=tmp_path,
        )


def test_codesign_observation_requires_runtime_and_no_entitlements(
    tmp_path, monkeypatch
):
    inspector = load_inspector()
    monkeypatch.setattr(inspector.sys, "platform", "darwin")

    class Completed:
        def __init__(self, returncode=0, stdout=b"", stderr=b""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    responses = iter(
        [
            Completed(stdout="", stderr=""),
            Completed(stdout="", stderr="flags=0x10000(runtime)"),
            Completed(stdout=b"", stderr=b""),
        ]
    )
    monkeypatch.setattr(
        inspector.subprocess, "run", lambda *args, **kwargs: next(responses)
    )
    assert inspector._codesign_observation(tmp_path) == {
        "verified": True,
        "runtime": True,
        "entitlements": {},
    }

    responses = iter(
        [
            Completed(stdout="", stderr=""),
            Completed(stdout="", stderr="flags=0x0(none)"),
        ]
    )
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError, match="hardened-runtime"
    ):
        inspector._codesign_observation(tmp_path)
    responses = iter(
        [
            Completed(stdout="", stderr=""),
            Completed(stdout="", stderr="flags=0x10000(runtime)"),
            Completed(
                stdout=__import__("plistlib").dumps(
                    {"com.apple.security.cs.disable-library-validation": True}
                ),
                stderr=b"",
            ),
        ]
    )
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="unreviewed"):
        inspector._codesign_observation(tmp_path)


def test_archive_rejects_traversal_oversize_symlink_and_mode_mutations(
    tmp_path, monkeypatch
):
    inspector = load_inspector()
    traversal = tmp_path / "traversal.zip"
    with zipfile.ZipFile(traversal, "w") as bundle:
        bundle.writestr(zip_info("root/../escape", stat.S_IFREG | 0o644), b"x")
    with pytest.raises(inspector.MacOSDeploymentInspectionError, match="traversal"):
        inspector.inspect_archive(
            traversal, archive_root_name="root", embedded_files={}
        )

    oversized = tmp_path / "oversized.zip"
    with zipfile.ZipFile(oversized, "w") as bundle:
        bundle.writestr(zip_info("root/file", stat.S_IFREG | 0o644), b"xx")
    monkeypatch.setattr(inspector, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 1)
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError, match="uncompressed-byte"
    ):
        inspector.inspect_archive(
            oversized, archive_root_name="root", embedded_files={}
        )
    monkeypatch.setattr(inspector, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 3_000_000_000)

    manifest = tmp_path / "deployment-manifest.json"
    signing = tmp_path / "ad-hoc-signing-inventory.json"
    payload = b"executable"
    signing_payload = {
        "schema_version": 1,
        "app": "RCMetaStudio.app",
        "identity": "ad-hoc",
        "native_files": ["Contents/MacOS/RCMetaStudio"],
        "nested_bundles": [],
        "verification": {"individual_strict": True, "outer_deep_strict": True},
    }
    signing.write_text(json.dumps(signing_payload), encoding="utf-8")
    signing_sha = __import__("hashlib").sha256(signing.read_bytes()).hexdigest()
    manifest.write_text(
        json.dumps(
            {
                "target": "macos-x64",
                "signing_inventory": {
                    "path": "qualification/ad-hoc-signing-inventory.json",
                    "sha256": signing_sha,
                    "identity": "ad-hoc",
                    "native_files": ["Contents/MacOS/RCMetaStudio"],
                    "nested_bundles": [],
                },
                "inventory": {
                    "files": [
                        {
                            "path": "Contents/MacOS/RCMetaStudio",
                            "kind": "file",
                            "size": len(payload),
                            "mode": 0o755,
                            "sha256": __import__("hashlib").sha256(payload).hexdigest(),
                            "architectures": ["x86_64"],
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    for name, mode, expected in (
        ("symlink.zip", stat.S_IFLNK | 0o755, "ZIP file differs"),
        ("mode.zip", stat.S_IFREG | 0o644, "ZIP file differs"),
    ):
        archive = tmp_path / name
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr(
                zip_info(
                    "root/qualification/deployment-manifest.json", stat.S_IFREG | 0o644
                ),
                manifest.read_bytes(),
            )
            bundle.writestr(
                zip_info(
                    "root/qualification/ad-hoc-signing-inventory.json",
                    stat.S_IFREG | 0o644,
                ),
                signing.read_bytes(),
            )
            bundle.writestr(
                zip_info("root/RCMetaStudio.app/Contents/MacOS/RCMetaStudio", mode),
                payload,
            )
        with pytest.raises(inspector.MacOSDeploymentInspectionError, match=expected):
            inspector.inspect_archive(
                archive,
                archive_root_name="root",
                embedded_files={
                    "qualification/deployment-manifest.json": manifest,
                    "qualification/ad-hoc-signing-inventory.json": signing,
                },
            )

    missing_signing = tmp_path / "missing-signing.zip"
    with zipfile.ZipFile(missing_signing, "w") as bundle:
        bundle.writestr(
            zip_info(
                "root/qualification/deployment-manifest.json", stat.S_IFREG | 0o644
            ),
            manifest.read_bytes(),
        )
        bundle.writestr(
            zip_info(
                "root/RCMetaStudio.app/Contents/MacOS/RCMetaStudio",
                stat.S_IFREG | 0o755,
            ),
            payload,
        )
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError, match="missing or changed"
    ):
        inspector.inspect_archive(
            missing_signing,
            archive_root_name="root",
            embedded_files={
                "qualification/deployment-manifest.json": manifest,
                "qualification/ad-hoc-signing-inventory.json": signing,
            },
        )

    tampered_signing = tmp_path / "tampered-signing.zip"
    with zipfile.ZipFile(tampered_signing, "w") as bundle:
        bundle.writestr(
            zip_info(
                "root/qualification/deployment-manifest.json", stat.S_IFREG | 0o644
            ),
            manifest.read_bytes(),
        )
        bundle.writestr(
            zip_info(
                "root/qualification/ad-hoc-signing-inventory.json", stat.S_IFREG | 0o644
            ),
            b"{}",
        )
        bundle.writestr(
            zip_info(
                "root/RCMetaStudio.app/Contents/MacOS/RCMetaStudio",
                stat.S_IFREG | 0o755,
            ),
            payload,
        )
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError, match="missing or changed"
    ):
        inspector.inspect_archive(
            tampered_signing,
            archive_root_name="root",
            embedded_files={
                "qualification/deployment-manifest.json": manifest,
                "qualification/ad-hoc-signing-inventory.json": signing,
            },
        )

    drift_signing = tmp_path / "drift-signing.json"
    drift_payload = {**signing_payload, "native_files": []}
    drift_signing.write_text(json.dumps(drift_payload), encoding="utf-8")
    drift_archive = tmp_path / "drift-signing.zip"
    with zipfile.ZipFile(drift_archive, "w") as bundle:
        bundle.writestr(
            zip_info(
                "root/qualification/deployment-manifest.json", stat.S_IFREG | 0o644
            ),
            manifest.read_bytes(),
        )
        bundle.writestr(
            zip_info(
                "root/qualification/ad-hoc-signing-inventory.json", stat.S_IFREG | 0o644
            ),
            drift_signing.read_bytes(),
        )
        bundle.writestr(
            zip_info(
                "root/RCMetaStudio.app/Contents/MacOS/RCMetaStudio",
                stat.S_IFREG | 0o755,
            ),
            payload,
        )
    with pytest.raises(
        inspector.MacOSDeploymentInspectionError,
        match="authoritative native deployment",
    ):
        inspector.inspect_archive(
            drift_archive,
            archive_root_name="root",
            embedded_files={
                "qualification/deployment-manifest.json": manifest,
                "qualification/ad-hoc-signing-inventory.json": drift_signing,
            },
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
        [
            sys.executable,
            "-c",
            "import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(7)",
        ],
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
        "platform_plugin": "cocoa",
        "locale": "de_DE",
        "clipboard": True,
        "critical_dialog": {
            "dont_use_native_dialog": False,
            "application_dont_use_native_dialogs": False,
            "dont_show_on_screen_before_show": False,
            "dont_show_on_screen_after_show": True,
            "native_helper_active": True,
            "window_modality": "WindowModal",
            "visible_before_close": True,
            "critical_icon": True,
            "finished_signal": True,
            "result": 1,
            "accepted_value": 1,
            "timed_out": False,
            "timeout_ms": 5_000,
        },
        "cleanup": {"close_accepted": True, "window_visible": False},
        "binary_resources": True,
        "native_menu": {"is_native": True, "menu_count": 1, "action_count": 1},
        "native_file_dialog": {
            "dont_use_native_dialog": False,
            "window_modality": "WindowModal",
            "visible_before_cancel": True,
            "cancel_requested": True,
            "finished_signal": True,
            "rejected_signal": True,
            "result": 0,
            "rejected_value": 0,
            "timed_out": False,
            "timeout_ms": 10_000,
        },
        "accessibility": {
            "focus_before": "packagedAccessibilityControl",
            "focus_after_tab": "packagedKeyboardTraversalTarget",
            "accessible_name": "Packaged accessibility control",
            "accessible_description": "Verifies packaged Qt accessibility metadata.",
            "native": {
                "role": "AXButton",
                "title": "Packaged accessibility control",
                "description": "Verifies packaged Qt accessibility metadata.",
                "is_ignored": False,
                "exposed": True,
                "source": "accessibility-tree",
                "bridge": "accessibilityAttributeValue:AXChildren",
                "bridge_supported": True,
                "root_count": 1,
            },
        },
        "available_styles": ["macOS"],
        "active_style": "macos",
        "tls_backends": ["cert-only"],
        "image_formats": ["jpeg", "svg"],
        "baseline_device_pixel_ratio": 1.0,
        "dpr_tolerance": 0.05,
    }
    records = [
        {
            **base,
            "requested": value,
            "qt_scale_factor": value,
            "device_pixel_ratio": float(value),
            "expected_device_pixel_ratio": float(value),
        }
        for value in ("1.25", "1.50", "1.75")
    ]
    inspector.validate_macos_surface_records(records)
    mutations = [
        ("locale", "C"),
        ("native_menu", {"is_native": False, "menu_count": 1, "action_count": 1}),
        (
            "native_file_dialog",
            {
                "dont_use_native_dialog": False,
                "window_modality": "WindowModal",
                "visible_before_cancel": True,
                "cancel_requested": True,
                "finished_signal": False,
                "rejected_signal": False,
                "result": None,
                "rejected_value": 0,
                "timed_out": True,
                "timeout_ms": 10_000,
                "error_type": "TimeoutError",
                "error_message": "native file dialog exceeded its internal bound",
            },
        ),
        (
            "native_file_dialog",
            {
                **base["native_file_dialog"],
                "window_modality": "ApplicationModal",
            },
        ),
        (
            "critical_dialog",
            {
                **base["critical_dialog"],
                "finished_signal": False,
                "result": None,
                "timed_out": True,
            },
        ),
        (
            "critical_dialog",
            {
                **base["critical_dialog"],
                "dont_use_native_dialog": True,
                "native_helper_active": False,
            },
        ),
        (
            "critical_dialog",
            {
                **base["critical_dialog"],
                "application_dont_use_native_dialogs": True,
                "native_helper_active": False,
            },
        ),
        (
            "critical_dialog",
            {
                **base["critical_dialog"],
                "dont_show_on_screen_before_show": True,
                "native_helper_active": False,
            },
        ),
        (
            "critical_dialog",
            {
                **base["critical_dialog"],
                "dont_show_on_screen_after_show": False,
                "native_helper_active": False,
            },
        ),
        ("cleanup", {"close_accepted": True, "window_visible": True}),
        (
            "accessibility",
            {
                "focus_before": "packagedAccessibilityControl",
                "focus_after_tab": "packagedKeyboardTraversalTarget",
                "accessible_name": "Packaged accessibility control",
                "accessible_description": "Verifies packaged Qt accessibility metadata.",
                "native": {
                    "role": "",
                    "title": "",
                    "description": "",
                    "is_ignored": None,
                    "exposed": False,
                },
            },
        ),
    ]
    for key, value in mutations:
        mutated = [dict(item) for item in records]
        mutated[0][key] = value
        with pytest.raises(
            inspector.MacOSDeploymentInspectionError, match="surface evidence"
        ):
            inspector.validate_macos_surface_records(mutated)

    native_mutations = [
        ("role", "AXCheckBox"),
        ("title", "Changed accessible name"),
        ("description", "Changed accessible description"),
        ("is_ignored", True),
        ("is_ignored", None),
        ("exposed", False),
        ("bridge", "accessibilityChildren"),
        ("bridge_supported", False),
        ("root_count", 0),
    ]
    for key, value in native_mutations:
        mutated = [dict(item) for item in records]
        accessibility = dict(mutated[0]["accessibility"])
        native = dict(accessibility["native"])
        native[key] = value
        accessibility["native"] = native
        mutated[0]["accessibility"] = accessibility
        with pytest.raises(
            inspector.MacOSDeploymentInspectionError,
            match="surface evidence",
        ):
            inspector.validate_macos_surface_records(mutated)


def test_cocoa_accessibility_finds_exact_exposed_descendant_fail_closed():
    from rc_metastudio.cocoa_accessibility import (
        bounded_error_message,
        find_accessibility_element,
    )

    tree = {1: [2], 2: [3], 3: [1]}
    observations = {
        1: {
            "role": "",
            "title": "",
            "description": "",
            "is_ignored": None,
        },
        2: {
            "role": "AXCheckBox",
            "title": "Packaged accessibility control",
            "description": "Verifies packaged Qt accessibility metadata.",
            "is_ignored": False,
        },
        3: {
            "role": "AXButton",
            "title": "Packaged accessibility control",
            "description": "Verifies packaged Qt accessibility metadata.",
            "is_ignored": False,
        },
    }
    observed = find_accessibility_element(
        [1],
        expected_role="AXButton",
        expected_title="Packaged accessibility control",
        expected_description="Verifies packaged Qt accessibility metadata.",
        observe=observations.__getitem__,
        children=lambda node: tree[node],
    )
    assert observed["title"] == "Packaged accessibility control"
    assert observed["description"] == "Verifies packaged Qt accessibility metadata."
    assert observed["is_ignored"] is False
    assert observed["exposed"] is True
    assert observed["source"] == "accessibility-tree"
    assert observed["visited_nodes"] == 3

    missing = find_accessibility_element(
        [1],
        expected_role="AXButton",
        expected_title="Changed title",
        expected_description="Changed description",
        observe=observations.__getitem__,
        children=lambda node: tree[node],
    )
    assert missing["is_ignored"] is None
    assert missing["exposed"] is False
    assert missing["visited_nodes"] == 3

    for ignored_state in (True, None):
        matching_but_unexposed = {
            **observations[3],
            "is_ignored": ignored_state,
        }
        rejected = find_accessibility_element(
            [3],
            expected_role="AXButton",
            expected_title="Packaged accessibility control",
            expected_description="Verifies packaged Qt accessibility metadata.",
            observe=lambda _node: matching_but_unexposed,
            children=lambda _node: [],
        )
        assert rejected["exposed"] is False
        assert rejected["visited_nodes"] == 1
    with pytest.raises(RuntimeError, match="exceeded its node bound"):
        find_accessibility_element(
            [1],
            expected_role="AXButton",
            expected_title="Changed title",
            expected_description="Changed description",
            observe=observations.__getitem__,
            children=lambda node: tree[node],
            max_nodes=2,
        )

    diagnostic = bounded_error_message(
        RuntimeError("AXChildren bridge unavailable\n" + "x" * 500)
    )
    assert diagnostic.startswith("AXChildren bridge unavailable ")
    assert "\n" not in diagnostic
    assert len(diagnostic) == 240


def test_package_classifier_and_gate_cover_all_direct_macos_inputs():
    policy = load_package_policy()
    direct_inputs = [
        "scripts/validate_test_taxonomy.py",
        "scripts/verify_rcmetar_r_stack.py",
        "docs/verification/test-taxonomy.json",
        "scripts/delivery.py",
        "scripts/inspect_macos_deployment.py",
        "scripts/qt6_macos_feasibility.py",
        "scripts/sign_macos_app.py",
        "scripts/sign-notarize-macos-package.sh",
        "scripts/normalize_macos_macho.py",
        "scripts/install-rcmetar-source.R",
        "scripts/package-macos-x64-direct-r-spike.sh",
        "scripts/macos_embedded_r_adapter.py",
        "scripts/macos_host_r_isolation.sh",
        "scripts/verify_macos_r_pyinstaller_toc.py",
        ".github/workflows/macos-x64-direct-r-spike.yml",
        ".github/workflows/package-verification.yml",
        ".github/workflows/release-candidate.yml",
        "packaging/pyinstaller/rc-metastudio-macos.spec",
    ]
    assert all(policy.requires_package_qualification([path]) for path in direct_inputs)
    assert policy.requires_package_qualification(["docs/user-guide.md"]) is False
    workflow = text(".github/workflows/fast-verification.yml")
    assert "macos-x64-package-qualification" in workflow
    assert "MACOS_X64_PACKAGE_RESULT" in workflow
    assert workflow.index('if [ "$RUN_WINDOWS" != "true" ]') < workflow.index(
        'if [ "$RUN_MACOS_X64_PACKAGE" = "true" ]'
    )
