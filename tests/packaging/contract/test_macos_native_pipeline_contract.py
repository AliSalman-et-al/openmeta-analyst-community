from __future__ import annotations

import json
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "resolve_macos_package_target", ROOT / "scripts/resolve_macos_package_target.py"
)
TARGETS = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(TARGETS)


def test_shared_target_manifest_defines_both_native_macos_builds():
    x64 = TARGETS.load_target("x64")
    arm64 = TARGETS.load_target("arm64")

    assert x64["machine"] == "x86_64"
    assert x64["runner"] == "macos-15-intel"
    assert arm64["machine"] == "arm64"
    assert arm64["runner"] == "macos-15"
    assert x64["minimum_macos"] == arm64["minimum_macos"] == "14.0"
    assert x64["r_url"].endswith("R-4.6.1-x86_64.pkg")
    assert arm64["r_url"].endswith("R-4.6.1-arm64.pkg")
    assert arm64["r_component_identifier"] == "org.R-project.R.fw.pkg"
    assert arm64["r_sha256"] == (
        "67f6eea4ced4ce48f0a0d4fa3a1cac43d1859a05a88993ee3dff7c52e7edbc4b"
    )


def test_target_manifest_rejects_silent_architecture_drift(tmp_path: Path):
    manifest = json.loads(
        (ROOT / "config/macos-package-targets.json").read_text(encoding="utf-8")
    )
    manifest["targets"]["arm64"]["delivery_target"] = "macos-x64"
    path = tmp_path / "targets.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(TARGETS.TargetError, match="does not match architecture"):
        TARGETS.load_target("arm64", path)


def test_public_macos_command_accepts_both_architectures_from_the_manifest():
    wrapper = (ROOT / "scripts/package-macos.sh").read_text(encoding="utf-8")

    assert "resolve_macos_package_target.py" in wrapper
    assert 'x64|arm64)' in wrapper
    assert "Issue #342 packages macOS Intel only" not in wrapper


def test_reusable_workflow_is_a_two_architecture_native_matrix():
    workflow = (ROOT / ".github/workflows/package-target.yml").read_text(
        encoding="utf-8"
    )

    assert "target: macos-x64" in workflow
    assert "target: macos-arm64" in workflow
    assert "runner: macos-15-intel" in workflow
    assert "runner: macos-15" in workflow
    assert "scripts/package-macos.sh --architecture \"${{ matrix.architecture }}\"" in workflow


def test_first_green_gate_uses_the_bcg_packaged_workflow():
    build = (ROOT / "scripts/build-macos-package.sh").read_text(encoding="utf-8")

    assert 'sample_path="$sample_root/BCG.rcms"' in build
    assert '--automation-native-smoke "$extracted_app/Contents/Resources/sample_projects/BCG.rcms"' in build
    assert '--automation-smoke-log "$extracted_smoke_log" "$extracted_app/Contents/Resources/sample_projects/BCG.rcms"' in build
    assert "--automation-native-smoke" in build
    assert "RCMS_REQUIRE_IN_PROCESS_RPY2=1" in build


def test_source_r_packages_link_against_the_private_staged_runtime():
    build = (ROOT / "scripts/build-macos-package.sh").read_text(encoding="utf-8")

    assert 'r_makevars="$work_root/private-r.Makevars"' in build
    assert "LDFLAGS = -L%s/lib\\nLIBR = -L%s/lib -lR\\n" in build
    assert build.count('R_MAKEVARS_USER="$r_makevars"') == 2


def test_private_r_framework_is_completed_as_a_signable_code_bundle():
    build = (ROOT / "scripts/build-macos-package.sh").read_text(encoding="utf-8")

    complete = build.index('info["CFBundleExecutable"] = "R"')
    package = build.index("run_strict_r_dependency_policy")
    collect = build.index('"packaging/pyinstaller/rc-metastudio-macos.spec"')
    assert complete < package < collect
    assert 'existing not in (None, "R")' in build
    canonicalize = build.index('runtime_library.replace(main_executable)')
    staged_canonicalization = build.index('canonicalize_r_framework "$r_framework"')
    inject = build.index('copy_tree "$staged_r_framework" "$r_framework"')
    inspect = build.index('inspect_macos_deployment.py" native-graph')
    assert canonicalize < staged_canonicalization < collect
    assert collect < inject < inspect
    assert build.count('canonicalize_r_framework "$r_framework"') == 1
    assert 'RCMS_STAGED_R_FRAMEWORK="$r_framework"' in build
    assert 'macos_embedded_r_adapter.py" post-app' in build
    assert 'runtime_library.symlink_to(Path("../../R"))' in build
    assert 'info_plist.is_file() or info_plist.is_symlink()' in build
    assert '("Headers", "Libraries", "PrivateHeaders")' in build
    assert 'root_members != {"R", "Resources", "Versions"}' in build
    assert '"@loader_path/Resources/lib/$dependency_name" "$framework_main"' in build
    assert "awk 'NR > 2 { print $1 }'" in build
    assert 'codesign --force --options runtime --sign - "$app_bundle"' not in build
    assert 'codesign --verify --strict --deep --verbose=2 "$app_bundle"' in build


def test_rpy2_bridge_is_relocated_before_it_is_imported():
    build = (ROOT / "scripts/build-macos-package.sh").read_text(encoding="utf-8")

    locate = build.index('glob("_rinterface_cffi_api*.so")')
    relocate = build.index('relocate_rpy2_api_bridge "$rpy2_api_bridge"')
    api_proof = build.index("from rpy2 import robjects")
    assert locate < relocate < api_proof
    assert "import _rinterface_cffi_api as m" not in build
    assert '@loader_path/*.dylib)' in build
    assert 'source_relative="lib/${dependency#@loader_path/}"' in build
    assert '@rpath/*.dylib)' in build
    assert 'source_relative="lib/${dependency#@rpath/}"' in build
    assert "grep -E '@rpath/|" in build
    assert build.count('relocate_rpy2_api_bridge "$rpy2_api_bridge"') == 2
    assert build.rindex('relocate_rpy2_api_bridge "$rpy2_api_bridge"') < build.index(
        'inspect_macos_deployment.py" native-graph'
    )


def test_nested_r_extensions_rebase_broken_loader_relative_runtime_edges():
    relocator = (ROOT / "scripts/relocate_macos_r_runtime.sh").read_text(
        encoding="utf-8"
    )

    assert 'loader_target="$(dirname "$binary")/${dependency#@loader_path/}"' in relocator
    assert 'target="$resources/lib/${dependency##*/}"' in relocator
    assert 'install_name_tool -change "$dependency" "$replacement" "$binary"' in relocator
    assert 'canonical_id="@loader_path/$(basename "$binary")"' in relocator


def test_arm64_framework_component_is_selected_by_its_real_package_identifier(
    tmp_path: Path,
):
    spec = importlib.util.spec_from_file_location(
        "resolve_macos_r_framework_component",
        ROOT / "scripts/resolve_macos_r_framework_component.py",
    )
    resolver = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(resolver)
    component = tmp_path / "R-fw.pkg"
    framework = component / "Payload/R.framework"
    framework.mkdir(parents=True)
    (component / "PackageInfo").write_text(
        '<pkg-info identifier="org.R-project.R.fw.pkg" '
        'install-location="/Library/Frameworks" version="4.6.1"/>',
        encoding="utf-8",
    )

    assert resolver.resolve_framework(
        tmp_path, "4.6.1", "org.R-project.R.fw.pkg"
    ) == framework.resolve()


def test_arm64_launcher_adapter_rejects_intel_build_metadata():
    spec = importlib.util.spec_from_file_location(
        "configure_macos_r_launchers",
        ROOT / "scripts/configure_macos_r_launchers.py",
    )
    launchers = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(launchers)

    wrapper = launchers.private_config("arm64")
    assert "/opt/R/arm64/lib" in wrapper
    assert "/opt/R/x86_64/lib" not in wrapper
