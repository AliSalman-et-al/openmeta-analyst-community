import json
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


def read_repo_text(*parts):
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def ps_contract(*parts):
    text = read_repo_text(*parts)
    return {
        "text": text,
        "params": set(re.findall(r"\[(?:string|switch)\]\$([A-Za-z0-9_]+)", text)),
        "functions": set(re.findall(r"(?m)^function\s+([A-Za-z0-9_-]+)", text)),
        "commands": set(
            re.findall(
                r"(?m)^\s*(?:\$[A-Za-z0-9_]+\s+=\s+)?(uv|robocopy|Start-Process|Move-Item|Copy-Item)\b",
                text,
            )
        ),
        "env_writes": set(re.findall(r"\$env:([A-Za-z0-9_]+)\s*=", text)),
        "paths": set(
            re.findall(
                r'"([^"]+(?:\.(?:rcms|html|exe|dll|bat|ps1|py|json|R|sh)|DESCRIPTION))"',
                text,
            )
        ),
        "hidden_imports": set(re.findall(r'"--hidden-import",\s+"([^"]+)"', text)),
    }


def sh_contract(*parts):
    text = read_repo_text(*parts)
    return {
        "text": text,
        "case_options": set(re.findall(r"(?m)^\s+(--[a-z0-9-]+)\)", text)),
        "functions": set(re.findall(r"(?m)^([a-zA-Z0-9_]+)\(\)\s+\{", text)),
        "env_names": set(re.findall(r"\b([A-Z][A-Z0-9_]+)=", text)),
        "pyinstaller_options": set(
            re.findall(r"^\s+(--[a-z0-9-]+)(?:\s|$)", text, re.MULTILINE)
        ),
        "paths": set(re.findall(r'"([^"]+\.(?:oma|html|app|command|sh|R|zip))"', text)),
        "app_paths": set(re.findall(r'"\$app_root/([^"]+)"', text)),
    }


def workflow_contract(*parts):
    text = read_repo_text(*parts)
    trigger_text = text[text.index("on:") : text.index("\npermissions:")]
    jobs = set(re.findall(r"(?m)^  ([A-Za-z0-9_-]+):$", text))
    steps_by_job = {}
    needs_by_job = {}
    current_job = None
    for line in text.splitlines():
        job_match = re.match(r"^  ([A-Za-z0-9_-]+):$", line)
        if job_match:
            current_job = job_match.group(1)
            steps_by_job[current_job] = []
            continue
        needs_scalar_match = re.match(r"^    needs:\s+([A-Za-z0-9_-]+)$", line)
        if needs_scalar_match and current_job:
            needs_by_job[current_job] = {needs_scalar_match.group(1)}
            continue
        needs_list_match = re.match(r"^      - ([A-Za-z0-9_-]+)$", line)
        if needs_list_match and current_job and current_job in needs_by_job:
            needs_by_job[current_job].add(needs_list_match.group(1))
            continue
        if re.match(r"^    needs:\s*$", line) and current_job:
            needs_by_job[current_job] = set()
            continue
        step_match = re.match(r"^\s{6}- name: (.+)$", line)
        if step_match and current_job:
            steps_by_job[current_job].append(step_match.group(1))
    return {
        "text": text,
        "jobs": jobs,
        "steps_by_job": steps_by_job,
        "uses": re.findall(
            r"uses:\s+([^@\s]+)@([0-9a-f]{40})(?:\s+#\s+([^\s]+))?", text
        ),
        "legacy_uses": re.findall(r"uses:\s+[^@\s]+@v\d+", text),
        "runs": re.findall(r"run:\s+(.+)", text),
        "paths": set(re.findall(r'^\s+- "([^"]+)"$', text, re.MULTILINE)),
        "events": set(re.findall(r"(?m)^  ([a-z_]+):(?:$|\n)", trigger_text)),
        "cache_keys": re.findall(r"key:\s+(.+)", text),
        "cache_paths": set(re.findall(r"(?m)^\s+path:\s+(.+)$", text)),
        "restore_keys": re.findall(r"restore-keys:", text),
        "env": dict(re.findall(r"(?m)^  ([A-Z0-9_]+):\s+(.+)$", text)),
        "needs": needs_by_job,
    }


def relative_order(text, *needles):
    positions = [text.index(needle) for needle in needles]
    return positions == sorted(positions)


def pytest_path_tokens(text):
    return set(
        re.findall(
            r"tests[/\\](?:python|analysis_regression|packaging|r_stack)(?:[/\\][A-Za-z_]+)?",
            text,
        )
    )


def pytest_option_tokens(text):
    return set(
        re.findall(r"(?<![A-Za-z0-9_-])(--dist|-n|loadfile|4)(?![A-Za-z0-9_-])", text)
    )


def project_dependencies():
    return set(re.findall(r'"([^"]+)"', read_repo_text("pyproject.toml")))


def test_windows_distributable_contract_is_declared():
    script = ps_contract("scripts", "build-windows-package.ps1")
    spec = read_repo_text("packaging", "pyinstaller", "rc-metastudio.spec")

    assert {
        "ArtifactName",
        "ArchiveRootName",
        "PythonExe",
        "RRuntimeRoot",
        "RPackageCacheRoot",
    } <= script["params"]
    assert {"SkipDependencyInstall", "SkipClean", "SkipSmoke"} <= script["params"]
    assert {
        "Resolve-CommandOrRepoPath",
        "Copy-DirectoryTree",
        "Assert-AppLayout",
        "Invoke-PackagedAppSmokeTest",
        "Invoke-PackagedWizardLayoutSmokeTest",
        "Get-ProjectVersion",
        "Get-RPackageCacheKey",
        "Test-BundledRPackages",
        "Copy-RLibraryPackages",
        "Assert-RCMetaRSummaryFormatting",
        "Install-LocalRPackagesFromSource",
        "Install-BundledRPackages",
    } <= script["functions"]
    assert {"robocopy", "Start-Process", "Move-Item"} <= script["commands"]
    assert {
        "RCMS_REQUIRE_IN_PROCESS_RPY2",
        "RCMS_STARTUP_PROJECT_SMOKE",
        "RPY2_CFFI_MODE",
    } <= script["env_writes"]
    assert all(name in spec for name in ("rpy2.robjects", "rpy2.rinterface"))
    assert '"icons_rc"' not in spec
    assert {
        "RCMetaStudio.exe",
        "sample_projects\\BCG.rcms",
        "sample_projects\\amino.rcms",
        "R\\bin\\x64\\R.dll",
        "R\\library\\RCMetaR\\DESCRIPTION",
        "LaunchRCMetaStudio.bat",
        "scripts\\install-r-deps.R",
        "docs\\verification\\RCMetaR-r-dependencies.json",
        "r\\RCMetaR\\DESCRIPTION",
    } <= script["paths"]
    assert "doc\\openMA_help.html" not in script["paths"]
    assert "Bundled help" not in script["text"]
    assert "packaging\\pyinstaller\\rc-metastudio.spec" in script["text"]
    assert "__main__.py" in spec
    assert (ROOT / "packaging" / "pyinstaller" / "rc-metastudio.spec").exists()
    assert "sole authoritative" in script["text"]
    assert "src\\rc_metastudio\\launch.py" not in script["text"]
    assert "tomllib.loads" in script["text"]
    assert (
        'if ($ArchiveRootName) { $ArchiveRootName } else { "RCMetaStudio-$projectVersion-windows-x64" }'
        in script["text"]
    )
    assert "ArchiveRootName must be a single portable directory name" in script["text"]
    assert '$archiveStagingRoot = Join-Path $workRoot "zip-staging"' in script["text"]
    assert (
        "Copy-DirectoryTree -Source $SourceDirectory -Destination $ArchiveRootDirectory"
        in script["text"]
    )
    assert "CreateFromDirectory($ArchiveStagingRoot, $tmpZipPath" in script["text"]
    assert (
        "Assert-ZipLayout -Path $zipPath -ArchiveRootName $archiveRootName"
        in script["text"]
    )
    assert 'if (-not $entryName.StartsWith("$ArchiveRootName\\"))' in script["text"]
    assert "$ArchiveRootName\\_internal\\PyQt6\\" in script["text"]


def test_windows_r_cache_reinstalls_local_packages_after_cache_restore():
    script = ps_contract("scripts", "build-windows-package.ps1")["text"]

    assert relative_order(
        script,
        "Invoke-StrictRDependencyPolicy -RscriptExe $rscriptExe -Library $cacheLibrary",
        "Copy-RLibraryPackages -Source $cacheLibrary -Destination $rLibrary",
        "Install-LocalRPackagesFromSource -Root $Root",
    )
    assert relative_order(
        script,
        "Installing bundled R package dependencies",
        "Test-RDependencyPackages -RscriptExe $rscriptExe -Library $rLibrary",
        "Caching bundled R dependency library at $cacheLibrary",
        "Installing local RCMetaR package",
    )


def test_packaged_smoke_launches_with_positional_project_argument():
    script = ps_contract("scripts", "build-windows-package.ps1")["text"]

    assert relative_order(
        script,
        '$env:RCMS_STARTUP_PROJECT_SMOKE = "1"',
        "Invoke-BoundedPackageProcess -FilePath $exePath -ArgumentList @($quotedSamplePath)",
    )


def test_packaged_smoke_launches_visual_wizard_layout_gate():
    script = ps_contract("scripts", "build-windows-package.ps1")["text"]

    assert relative_order(
        script,
        "function Invoke-PackagedAppSmokeTest",
        "function Invoke-PackagedWizardLayoutSmokeTest",
        "Invoke-PackagedAppSmokeTest -Root $appDir",
        "Invoke-PackagedWizardLayoutSmokeTest -Root $appDir",
    )
    assert (
        'Invoke-BoundedPackageProcess -FilePath $exePath -ArgumentList @("--automation-wizard-layout-smoke")'
        in script
    )
    assert '$env:QT_QPA_PLATFORM = "offscreen"' in script
    assert '$startArguments.WindowStyle = "Hidden"' in script
    assert "RCMS_AUTOMATION_SMOKE_LOG = $env:RCMS_AUTOMATION_SMOKE_LOG" in script
    assert "$env:RCMS_AUTOMATION_SMOKE_LOG = $smokeLogPath" in script
    assert "automation-wizard-layout-smoke.log" in script
    assert "QT_QPA_PLATFORM = $env:QT_QPA_PLATFORM" in script


def test_fast_workflow_runs_smoke_before_fast_verification():
    workflow = workflow_contract(".github", "workflows", "fast-verification.yml")

    assert {
        "change-classifier",
        "qt6-verification",
        "source-fast-targets",
        "windows-package-qualification",
        "fast-verification-gate",
    } <= workflow["jobs"]
    assert workflow["needs"]["source-fast-targets"] == {"change-classifier"}
    assert workflow["needs"]["fast-verification-gate"] == {
        "change-classifier",
        "qt6-verification",
        "source-fast-targets",
        "windows-package-qualification",
    }
    assert workflow["events"] == {"workflow_dispatch", "push", "pull_request"}
    assert workflow["legacy_uses"] == []
    assert all(
        ref.startswith("./") or re.fullmatch(r"[0-9a-f]{40}", ref)
        for _, ref, _ in workflow["uses"]
    )
    assert "src/*" in workflow["text"]
    assert "tests/*" in workflow["text"]
    assert (
        ".github/workflows/*|.python-version|pyproject.toml|uv.lock|config/*|"
        "docs/verification/*|r/*|scripts/*|src/*|tests/*"
        in workflow["text"]
    )
    for critical_input in (
        "config/qt6-ty-ignore-allowlist.json",
        "scripts/import_qt_modules.py",
        "src/rc_metastudio/qt6_cutover.py",
    ):
        top_level = critical_input.split("/", 1)[0]
        assert f"{top_level}/*" in workflow["text"]
    assert workflow["text"].count(
        "needs.change-classifier.outputs.run-windows == 'true'"
    ) == 2
    assert "needs.change-classifier.outputs.run-windows-package == 'true'" in workflow["text"]
    for package_input in (
        "sample_projects/*",
        "scripts/build_qt6.py",
        "scripts/test-bounded-package-process.ps1",
        "scripts/verify_package_release.py",
        "scripts/resolve_package_ci_metadata.py",
        "scripts/validate_adaptive_layout_evidence.py",
        "docs/verification/RCMetaR-r-dependencies.json",
        "delivery/targets.json",
        "tests/python/fast/test_qt6_cutover_finalization.py",
        "tests/python/fast/test_qt6_build_slice.py",
        "tests/python/fast/test_project_format.py",
        "tests/python/fast/test_qt_text_boundaries.py",
        "tests/python/gui/test_metaform_automation_launch.py",
    ):
        assert package_input in workflow["text"]
    assert "Required Windows x64 Package Qualification" in workflow["text"]
    assert "Required Windows x64 package qualification result" in workflow["text"]
    assert "docs/verification/*" in workflow["text"]
    assert ".\\scripts\\verify-smoke.ps1 -Sync" in workflow["text"]
    assert ".\\scripts\\verify-fast.ps1 -StrictTaxonomy" in workflow["text"]
    assert "bash ./scripts/verify-smoke.sh --sync" in workflow["text"]
    assert "bash ./scripts/verify-fast.sh --strict-taxonomy" in workflow["text"]
    for target in ("windows-x64", "macos-x64", "macos-arm64"):
        assert target in workflow["text"]
    assert "Qt6 Verification Change Classifier" in workflow["text"]
    assert "Qt6 Integration Verification Gate" in workflow["text"]
    assert "pull-requests: read" in workflow["text"]
    assert "gh api --paginate" in workflow["text"]
    assert "branches:" in workflow["text"]
    assert "- master" in workflow["text"]
    assert 'if [ "$EVENT_NAME" = "push" ]; then' in workflow["text"]
    assert (
        "No Qt6 verification inputs changed; Windows lane intentionally skipped."
        in workflow["text"]
    )
    assert "timeout-minutes: 45" in workflow["text"]
    assert workflow["text"].count("fetch-depth: 0") == 2
    assert "brew install libpng pkg-config" in workflow["text"]
    assert 'libpng_prefix="$(brew --prefix libpng)"' in workflow["text"]
    assert 'mkdir -p "$HOME/.R"' in workflow["text"]
    assert '>> "$HOME/.R/Makevars"' in workflow["text"]
    assert "CPPFLAGS += -I%s/include" in workflow["text"]
    assert "LDFLAGS += -L%s/lib" in workflow["text"]
    for variable in ("CPPFLAGS", "LDFLAGS", "PKG_CONFIG_PATH"):
        assert f"{variable}=" in workflow["text"]
    assert "qt-sdk-6.11.1-${{ matrix.target }}" in workflow["text"]
    assert "uv run aqt install-qt mac desktop 6.11.1 clang_64" in workflow["text"]
    assert "qt6_macos_feasibility.py resolve-rcc" in workflow["text"]
    assert '--sdk-root "$PWD/build/qt-sdk/6.11.1/macos"' in workflow["text"]
    assert '--github-env "$GITHUB_ENV"' in workflow["text"]
    assert workflow["env"]["RCMS_CRAN_REPO"] == "https://packagemanager.posit.co/cran/2026-07-16"
    assert "r-default-evidence-v2-${{ matrix.target }}-r-4.6.1-public-ppm-2026-07-16" in workflow["text"]
    assert "use-public-rspm: true" in workflow["text"]


def test_package_workflow_builds_path_aware_artifacts():
    workflow = workflow_contract(".github", "workflows", "package-verification.yml")
    target = workflow_contract(".github", "workflows", "package-target.yml")

    assert {
        "windows-package",
        "macos-package-intel",
        "macos-package-arm64",
    } <= workflow["jobs"]
    assert target["env"]["RCMS_CRAN_REPO"] == "https://packagemanager.posit.co/cran/2026-07-16"
    assert target["env"]["RCMS_CRAN_REPO_KEY"] == "public-ppm-2026-07-16"
    assert workflow["events"] == {"workflow_dispatch"}
    assert workflow["legacy_uses"] == []
    pinned_uses = workflow["uses"] + target["uses"]
    assert all(
        ref.startswith("./") or re.fullmatch(r"[0-9a-f]{40}", ref)
        for _, ref, _ in pinned_uses
    )
    assert workflow["paths"] == set()
    assert re.search(
        r"- name: Check out repository\s+"
        r"uses: actions/checkout@[0-9a-f]{40} # v6\s+"
        r"with:\s+fetch-depth: 0",
        target["text"],
    )
    assert target["text"].count("fetch-depth: 0") == 1
    assert "artifacts/${{ inputs.artifact_name }}.zip" in target["text"]
    assert "artifacts/${{ inputs.artifact_name }}-evidence.json" in target["text"]
    assert any("RCMetaStudio-macos-x64" in run for run in workflow["text"].splitlines())
    assert any(
        "RCMetaStudio-macos-arm64" in run for run in workflow["text"].splitlines()
    )
    assert (
        "build/windows-package/dist/RCMetaStudio/automation-wizard-layout-smoke.log"
        in target["text"]
    )
    assert all("RCMS_CRAN_REPO_KEY" in key for key in target["cache_keys"])
    assert workflow["restore_keys"] == []
    assert all(key.startswith("bundled-r-library-v4-") for key in target["cache_keys"])
    assert "use-public-rspm: true" in target["text"]
    assert all(
        "steps.package-metadata.outputs.r-version" in key for key in target["cache_keys"]
    )
    assert "-RRuntimeRoot" in target["text"]
    assert "--r-runtime-root" in target["text"]
    assert "Resolve shared package metadata" in target["text"]
    assert "scripts/resolve_package_ci_metadata.py" in target["text"]
    assert (
        "-ArchiveRootName \"RCMetaStudio-${{ steps.package-metadata.outputs.version }}-${{ inputs.archive_platform }}\""
        in target["text"]
    )
    assert (
        "--archive-root-name \"RCMetaStudio-${{ steps.package-metadata.outputs.version }}-${{ inputs.archive_platform }}\""
        in target["text"]
    )
    assert "if: ${{ inputs.build_windows }}" in workflow["text"]
    assert "if: ${{ inputs.build_macos }}" in workflow["text"]
    assert "publish_release:" not in workflow["text"]
    assert "release_tag:" not in workflow["text"]
    assert "gh release" not in workflow["text"]
    assert "contents: write" not in workflow["text"]
    assert "timeout-minutes: 60" in target["text"]
    assert "timeout-minutes: 60" in workflow["text"]


def test_lane_named_local_scripts_replace_old_workflow_wrappers():
    smoke = ps_contract("scripts", "verify-smoke.ps1")
    fast = ps_contract("scripts", "verify-fast.ps1")
    smoke_sh = sh_contract("scripts", "verify-smoke.sh")
    fast_sh = sh_contract("scripts", "verify-fast.sh")
    package = ps_contract("scripts", "package-windows.ps1")

    assert {
        "Sync",
        "RecreateVenv",
        "RequireREvidence",
        "RRuntimeRoot",
        "Rscript",
    } <= smoke["params"]
    assert {
        "Sync",
        "RecreateVenv",
        "RequireREvidence",
        "StrictTaxonomy",
        "FastWorkers",
        "RRuntimeRoot",
        "Rscript",
    } <= fast["params"]
    assert {"--rscript", "--r-runtime-root"} <= smoke_sh["case_options"]
    assert {"--rscript", "--r-runtime-root"} <= fast_sh["case_options"]
    assert "RHOME" in smoke["text"]
    assert "RHOME" in fast["text"]
    assert "Current Version" in smoke["text"]
    assert "Current Version" in fast["text"]
    assert "ProgramFiles" not in smoke["text"]
    assert "ProgramFiles" not in fast["text"]
    assert {"ArchiveRootName", "RPackageCacheRoot", "RRuntimeRoot"} <= package["params"]
    assert {"Resolve-RRuntimeRoot", "Resolve-RscriptFromRuntime"} <= package[
        "functions"
    ]
    assert "--rscript" in package["text"]
    assert "RRuntimeRoot = $resolvedRRuntimeRoot" in package["text"]
    assert "r-default-library-cache" in smoke["text"]
    assert "r-default-library-cache" in fast["text"]
    assert '"r-library-cache"' not in smoke["text"]
    assert '"r-library-cache"' not in fast["text"]
    assert {
        "tests\\python\\fast",
        "tests\\analysis_regression\\golden",
        "tests\\packaging\\contract",
    } <= pytest_path_tokens(fast["text"])
    assert {"--dist", "loadfile", "-n", "4"} <= pytest_option_tokens(fast["text"])
    assert "pytest-xdist==3.8.0" in project_dependencies()
    assert relative_order(
        fast["text"],
        "validate_golden_baseline_manifests.py",
        "validate_test_taxonomy.py",
        "Running parallel fast verification pytest lanes",
        "verify_rcmetar_r_default.py",
    )
    assert not (ROOT / "src" / "building").exists()


def test_macos_distributable_contract_is_declared():
    script = sh_contract("scripts", "build-macos-package.sh")
    local_script = sh_contract("scripts", "package-macos.sh")

    assert {
        "--architecture",
        "--archive-root-name",
        "--bundle-identifier",
        "--r-package-cache-root",
    } <= script["case_options"]
    assert {
        "require_free_space_gb",
        "repo_path",
        "resolve_existing_dir",
        "project_version",
        "copy_tree",
        "sha256_file",
        "sha256_stdin_12",
        "test_r_dependency_packages",
        "copy_r_library_packages",
        "configure_relocatable_r_launchers",
        "relocate_bundled_r_runtime",
    } <= script["functions"]
    assert {"--windowed", "--target-architecture", "--osx-bundle-identifier"} <= script[
        "pyinstaller_options"
    ]
    assert {
        "QT_QPA_PLATFORM",
        "RCMS_REQUIRE_IN_PROCESS_RPY2",
        "RCMS_STARTUP_PROJECT_SMOKE",
        "RPY2_CFFI_MODE",
    } <= script["env_names"]
    assert {
        "sample_projects/amino.rcms",
        "R/library/RCMetaR/DESCRIPTION",
        "LaunchRCMetaStudio.command",
    } <= script["app_paths"]
    assert "doc/openMA_help.html" not in script["app_paths"]
    assert "Bundling sample projects, help, and R runtime" not in script["text"]
    assert "scripts/install-r-deps.R" in script["text"]
    assert "src/rc_metastudio/__main__.py" in script["text"]
    assert "src/rc_metastudio/launch.py" not in script["text"]
    assert 'bundle_identifier="org.researchconsultancy.rc-metastudio"' in script["text"]
    assert (
        "--archive-root-name must be a single portable directory name" in script["text"]
    )
    assert "tomllib.loads" in script["text"]
    assert 'archive_root_name="${archive_root_name:-RCMetaStudio-$resolved_project_version-macos-$architecture}"' in script["text"]
    assert 'archive_staging_root="$work_root/zip-staging"' in script["text"]
    assert (
        'copy_tree "$app_bundle" "$archive_root_dir/RCMetaStudio.app"' in script["text"]
    )
    assert 'cd "$archive_staging_root"' in script["text"]
    assert 'zip -qry "$tmp_zip_path" "$archive_root_name"' in script["text"]
    assert (
        'name for name in names if name and not name.startswith(f"{archive_root_name}/")'
        in script["text"]
    )
    assert (
        'f"{archive_root_name}/RCMetaStudio.app/Contents/MacOS/RCMetaStudio"'
        in script["text"]
    )
    assert (
        'bundle_identifier="org.researchconsultancy.rc-metastudio"'
        in local_script["text"]
    )
    assert "org.RCMetaStudio.community" not in script["text"]
    assert "org.RCMetaStudio.community" not in local_script["text"]


def test_local_macos_package_script_uses_shared_build_script():
    script = sh_contract("scripts", "package-macos.sh")

    assert {
        "--architecture",
        "--archive-root-name",
        "--artifact-name",
        "--bundle-identifier",
        "--r-package-cache-root",
        "--r-runtime-root",
    } <= script["case_options"]
    assert relative_order(
        script["text"],
        "uv sync --locked",
        '"$python_exe" scripts/verify_package_release.py',
        '--r-runtime-root "$r_runtime_root"',
        'build_args+=(--archive-root-name "$archive_root_name")',
        'bash "$repo_root/scripts/build-macos-package.sh"',
    )


def test_shared_package_verifier_names_only_existing_qt6_test_paths():
    import importlib.util

    path = ROOT / "scripts" / "verify_package_release.py"
    spec = importlib.util.spec_from_file_location("verify_package_release", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.PACKAGE_TEST_PATHS
    assert all((ROOT / test_path).exists() for test_path in module.PACKAGE_TEST_PATHS)
    assert all("pyqt5" not in test_path.lower() for test_path in module.PACKAGE_TEST_PATHS)
    source = path.read_text(encoding="utf-8")
    assert '"scripts/build_qt6.py"' in source
    assert 'os.environ["RCMS_QT6_BUILD_ROOT"]' in source


def test_shared_r_dependency_installer_is_used_by_packagers():
    installer = read_repo_text("scripts", "install-r-deps.R")
    policy_runtime = read_repo_text("scripts", "r_binary_policy.R")
    policy_loader = read_repo_text("scripts", "r_dependency_policy.py")
    windows = ps_contract("scripts", "build-windows-package.ps1")
    macos = sh_contract("scripts", "build-macos-package.sh")

    assert "load_rcms_r_binary_policy" in installer
    assert "install_rcms_binary_packages" in installer
    assert "install_rcms_source_exception" in installer
    assert 'type = "binary"' in policy_runtime
    assert 'type = "source"' in policy_runtime
    assert "type = \"both\"" not in policy_runtime
    assert "available.packages" in policy_runtime
    assert "Required native R binaries unavailable" in policy_runtime
    assert "install.packages.compile.from.source = \"never\"" in policy_runtime
    assert "HSROC source archive SHA256 mismatch" in policy_runtime
    assert "HSROC 2.1.9 must be the sole pinned source exception" in policy_loader
    assert "https://packagemanager.posit.co/cran/2026-07-16" in policy_loader
    assert {
        "Get-RPackageCacheKey",
        "Get-Sha256FileHash",
        "Invoke-StrictRDependencyPolicy",
        "Test-RDependencyPackages",
    } <= windows["functions"]
    assert "docs\\verification\\RCMetaR-r-dependencies.json" in windows["paths"]
    assert "Get-Sha256FileHash -Path $installDeps" in windows["text"]
    assert "RCMetaR/DESCRIPTION" in macos["text"]
    assert "RCMS_CRAN_REPO" in windows["text"]
    assert "RCMS_CRAN_REPO" in macos["text"]
    assert "RCMS_POLICY_PYTHON" in windows["text"]
    assert "RCMS_POLICY_PYTHON" in macos["text"]
    assert "RCMS_CRAN_REPO must match the manifest snapshot" in windows["text"]
    assert "RCMS_CRAN_REPO must match the manifest snapshot" in macos["text"]
    assert relative_order(
        windows["text"],
        "if (Test-Path $cacheLibrary)",
        "Invoke-StrictRDependencyPolicy -RscriptExe $rscriptExe -Library $cacheLibrary",
        "Copy-RLibraryPackages -Source $cacheLibrary -Destination $rLibrary",
    )
    assert relative_order(
        macos["text"],
        'if [ -d "$cache_library" ]',
        'run_strict_r_dependency_policy "$cache_library"',
        'copy_r_library_packages "$cache_library" "$r_lib"',
    )


def test_macos_packager_resolves_relative_python_before_changing_directory():
    script = sh_contract("scripts", "build-macos-package.sh")["text"]

    assert relative_order(
        script,
        'python_exe="$(repo_path "$python_exe")"',
        'cd "$repo_root"\n  pyinstaller_args=(',
        '"$python_exe" -m PyInstaller',
    )


def test_macos_packager_copies_resolved_r_runtime_contents():
    script = sh_contract("scripts", "build-macos-package.sh")["text"]

    assert relative_order(
        script,
        'r_runtime_root="$(resolve_existing_dir "$r_runtime_root" "Source R runtime")"',
        'copy_tree "$r_runtime_root" "$app_root/R"',
        'if [ ! -x "$rscript" ] || [ ! -x "$r_binary" ]; then',
    )


def test_macos_packager_relocates_every_bundled_r_macho_before_use():
    script = sh_contract("scripts", "build-macos-package.sh")["text"]

    assert 'local macho_manifest="$work_root/bundled-r-mach-o-files.list"' in script
    assert "MACH_O_MAGICS = {" in script
    assert 'sys.stdout.buffer.write(os.fsencode(path) + b"\\0")' in script
    assert 'done < "$macho_manifest"' in script
    assert 'find "$r_home" -type f -print0' not in script
    assert "file \"$binary\" | grep -q 'Mach-O'" not in script
    assert "otool -D \"$binary\"" in script
    assert 'install_name_tool -id "@rpath/$source_relative" "$binary"' in script
    assert "otool -L \"$binary\"" in script
    assert 'install_name_tool -change "$dependency" "@loader_path/$relative_target"' in script
    assert "Bundled R runtime retains an absolute source-framework dependency" in script
    assert "Bundled R launchers retain an absolute source-framework path" in script
    assert 'exec "$R_HOME/bin/exec/R" --no-echo --no-restore "$@"' in script
    assert relative_order(
        script,
        'copy_tree "$r_runtime_root" "$app_root/R"',
        "install_local_r_packages",
        'if ! test_bundled_r_packages "$r_lib"',
        'step "Configuring relocatable bundled R launchers"',
        'step "Relocating completed bundled R runtime dependencies"',
        'cat > "$app_root/LaunchRCMetaStudio.command"',
    )


def test_windows_packager_restores_smoke_environment():
    script = ps_contract("scripts", "build-windows-package.ps1")["text"]

    assert relative_order(
        script,
        "$previousEnv = @{",
        "Invoke-BoundedPackageProcess -FilePath $exePath",
        "foreach ($name in $previousEnv.Keys)",
    )


def test_windows_packager_uses_clean_directory_copies_for_incremental_builds():
    script = ps_contract("scripts", "build-windows-package.ps1")["text"]

    assert relative_order(
        script,
        "function Copy-DirectoryTree",
        'Copy-DirectoryTree -Source (Join-Path $repoRoot "sample_projects")',
    )


def test_windows_packager_qualifies_qt6_deployment_and_packaged_surfaces():
    script = ps_contract("scripts", "build-windows-package.ps1")["text"]
    spec = read_repo_text("packaging", "pyinstaller", "rc-metastudio.spec")

    assert "windeployqt" not in script.lower()
    assert "inspect_windows_deployment.py inspect" in script
    assert "inspect_windows_deployment.py evidence" in script
    assert "qualification\\deployment-manifest.json" in script
    assert "qualification\\packaged-smoke.json" in script
    assert "RCMS_PACKAGE_SMOKE_EVIDENCE" in script
    assert "--automation-package-surface-smoke" in script
    runtime_probe_function = script.split(
        "function Invoke-PackagedRuntimeProbe", 1
    )[1].split("function Invoke-StrictRDependencyPolicy", 1)[0]
    assert relative_order(
        runtime_probe_function,
        'QT_SCALE_FACTOR = $env:QT_SCALE_FACTOR',
        'Remove-Item "Env:\\QT_SCALE_FACTOR" -ErrorAction SilentlyContinue',
        '"--automation-package-runtime-probe", $quotedProbePath',
        "foreach ($name in $previousEnv.Keys)",
    )
    assert "function Invoke-BoundedPackageProcess" in script
    assert "$processHandle = $process.Handle" in script
    assert "$process.Refresh()" in script
    assert "exited without a readable exit code" in script
    assert "test-bounded-package-process.ps1" in script
    assert "function Stop-BoundedPackageProcessTree" in script
    assert "taskkill exceeded its $TimeoutMilliseconds-millisecond cleanup bound" in script
    assert "-Wait -PassThru" not in script
    process_test = read_repo_text("scripts", "test-bounded-package-process.ps1")
    assert "Invoke-BoundedPackageProcess" in process_test
    assert "@(0, 7)" in process_test
    assert "Redirected stdout did not complete" in process_test
    assert "Redirected stderr did not complete" in process_test
    assert "exceeded its 1-second watchdog" in process_test
    assert "RcmsThrowingHandleProcess" in process_test
    assert "Handle acquisition failure did not trigger child cleanup" in process_test
    assert "$startArguments.RedirectStandardOutput = $StandardOutputPath" in script
    assert "$startArguments.RedirectStandardError = $StandardErrorPath" in script
    assert "RCMS_AUTOMATION_HANG_TRACE" in script
    assert "packaged-smoke.stdout.log" in script
    assert "packaged-smoke.stderr.log" in script
    assert "packaged-smoke.hang-trace.log" in script
    assert "packaged-smoke*.log" in read_repo_text(
        ".github", "workflows", "package-target.yml"
    )
    assert "function Remove-BundledRInstallerResidue" in script
    assert "(?i)^unins000\\..+$" in script
    assert "Remove-Item -LiteralPath $file.FullName -Force" in script
    assert "Windows R installer residue remained in the portable bundle" in script
    for required_r_file in (
        '"bin\\R.exe"',
        '"bin\\Rscript.exe"',
        '"bin\\x64\\R.dll"',
    ):
        assert required_r_file in script
    assert relative_order(
        script,
        "Copy-RRuntime -Root $resolvedRRuntimeRoot -DestinationRoot $appDir",
        "Remove-BundledRInstallerResidue -Root $appDir",
        "Install-BundledRPackages -Root $appDir",
        "Inspecting coherent Windows x64 deployment",
    )
    assert "WaitForExit($TimeoutSeconds * 1000)" in script
    assert "Start-Process -FilePath taskkill.exe" in script
    assert '"/PID", $ProcessId, "/T", "/F"' in script
    assert "watchdog cleanup failed" in script
    assert "$process.WaitForExit(30000)" in script
    for scale in ('"1.25"', '"1.50"', '"1.75"'):
        assert scale in script
    for plugin in (
        "platforms/qwindows.dll",
        "imageformats/qjpeg.dll",
        "imageformats/qsvg.dll",
        "iconengines/qsvgicon.dll",
        "styles/qmodernwindowsstyle.dll",
        "tls/qschannelbackend.dll",
    ):
        assert plugin in spec
    assert 'copy_metadata("rpy2")' in spec
    assert '(str(binary_resource), "resources")' in spec
    assert 'project_schema_root = app_source / "project_schemas" / "v1"' in spec
    assert 'project_schema_root.glob("*.schema.json")' in spec
    assert 'str(Path("rc_metastudio") / "project_schemas" / "v1")' in spec
    assert '*(f"forms.{name}" for name in generated_form_modules)' in spec
    assert 'excludes=["PyQt5", "PySide2", "PySide6", "qtpy"]' in spec
    assert spec.count("upx=False") == 2
    assert "upx=True" not in spec
    assert "upx_exclude" not in spec
    assert relative_order(
        script,
        "function Copy-DirectoryTree",
        'Copy-DirectoryTree -Source $Root -Destination (Join-Path $DestinationRoot "R")',
    )


def _load_windows_deployment_inspector():
    import importlib.util

    path = ROOT / "scripts" / "inspect_windows_deployment.py"
    spec = importlib.util.spec_from_file_location("inspect_windows_deployment", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_pe(path, machine=0x8664):
    import struct

    payload = bytearray(256)
    payload[0:2] = b"MZ"
    payload[0x3C:0x40] = struct.pack("<I", 0x80)
    payload[0x80:0x84] = b"PE\0\0"
    payload[0x84:0x86] = struct.pack("<H", machine)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _windows_deployment_fixture(tmp_path):
    app = tmp_path / "RCMetaStudio"
    qt = app / "_internal" / "PyQt6" / "Qt6"
    _write_pe(app / "RCMetaStudio.exe")
    for name in (
        "Qt6Core.dll",
        "Qt6Gui.dll",
        "Qt6Network.dll",
        "Qt6Svg.dll",
        "Qt6SvgWidgets.dll",
        "Qt6Widgets.dll",
    ):
        _write_pe(qt / "bin" / name)
    required = {
        "platforms": ("qwindows.dll",),
        "imageformats": ("qico.dll", "qjpeg.dll", "qsvg.dll"),
        "iconengines": ("qsvgicon.dll",),
        "styles": ("qmodernwindowsstyle.dll",),
        "tls": ("qschannelbackend.dll",),
    }
    for family, names in required.items():
        for name in names:
            _write_pe(qt / "plugins" / family / name)
    schema_root = app / "_internal" / "rc_metastudio" / "project_schemas" / "v1"
    source_schema_root = ROOT / "src" / "rc_metastudio" / "project_schemas" / "v1"
    schema_root.mkdir(parents=True)
    for source in source_schema_root.glob("*.schema.json"):
        (schema_root / source.name).write_bytes(source.read_bytes())
    return app


def _windows_runtime_probe(app):
    qt = app / "_internal" / "PyQt6" / "Qt6"
    return {
        "schema_version": 1,
        "frozen": True,
        "python": {
            "version": "3.11.9",
            "executable": str(app / "RCMetaStudio.exe"),
            "architecture": "AMD64",
            "bundle_root": str(app / "_internal"),
        },
        "qt": {
            "pyqt_version": "6.11.0",
            "compiled_qt_version": "6.11.0",
            "runtime_qt_version": "6.11.1",
            "sip_runtime_version": "6.15.2",
            "platform_plugin": "windows",
            "plugins_path": str(qt / "plugins"),
            "library_paths": [str(qt / "plugins")],
            "scale_factor_environment": None,
            "baseline_device_pixel_ratio": 1.0,
            "baseline_logical_dpi": 96.0,
        },
        "rpy2": {"distribution_version": "3.6.7"},
        "project_schemas": {
            "version": 1,
            "validated_members": ["manifest.json", "project.json", "state.json"],
        },
        "r": {
            "version": "4.6.1",
            "home": str(app / "R"),
            "library_paths": [str(app / "R" / "library")],
            "configured_home": str(app / "R"),
            "configured_library": str(app / "R" / "library"),
        },
    }


def test_windows_deployment_inspector_accepts_one_coherent_x64_qt6_stack(
    tmp_path, monkeypatch
):
    inspector = _load_windows_deployment_inspector()
    app = _windows_deployment_fixture(tmp_path)
    qt_root = app / "_internal" / "PyQt6" / "Qt6"
    _write_pe(qt_root / "plugins" / "imageformats" / "qpdf.dll")
    _write_pe(app / "R" / "library" / "qpdf" / "libs" / "x64" / "qpdf.dll")
    versions = {
        "python": "3.11.9",
        "pyqt6": "6.11.0",
        "qt": "6.11.1",
        "sip": "13.11.1",
        "sip_runtime": "6.15.2",
        "r": "4.6.1",
        "rpy2": "3.6.7",
        "pyinstaller": "6.21.0",
    }

    manifest = inspector.inspect_deployment(
        app,
        versions=versions,
        source_commit="a" * 40,
        runtime_probe=_windows_runtime_probe(app),
        locked_qt_root=qt_root,
    )

    assert manifest["target"] == "windows-x64"
    assert manifest["minimum_os"] == "Windows 10 version 1809"
    assert manifest["collector"] == {
        "name": "PyInstaller",
        "version": "6.21.0",
        "provenance": "build-time-only",
        "definition": "packaging/pyinstaller/rc-metastudio.spec",
    }
    assert manifest["stack"] == versions
    assert manifest["plugins"]["platforms"] == ["qwindows.dll"]
    assert set(manifest["qt_plugins"]) == {
        "platforms/qwindows.dll",
        "imageformats/qico.dll",
        "imageformats/qjpeg.dll",
        "imageformats/qsvg.dll",
        "imageformats/qpdf.dll",
        "iconengines/qsvgicon.dll",
        "styles/qmodernwindowsstyle.dll",
        "tls/qschannelbackend.dll",
    }
    assert all(item["machine"] == "x86_64" for item in manifest["native_files"])
    assert set(manifest["project_schema_resources"]) == {
        "manifest.schema.json",
        "project.schema.json",
        "state.schema.json",
    }

    missing_schema = (
        app
        / "_internal"
        / "rc_metastudio"
        / "project_schemas"
        / "v1"
        / "project.schema.json"
    )
    missing_schema.unlink()
    with pytest.raises(
        inspector.DeploymentInspectionError,
        match="missing required project schema resources",
    ):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=qt_root,
        )

    runtime_probe_path = tmp_path / "runtime-probe.json"
    runtime_probe_path.write_text(
        json.dumps(_windows_runtime_probe(app)), encoding="utf-8"
    )
    output = tmp_path / "deployment-manifest.json"
    captured = {}

    def inspect_from_cli(app_root, **kwargs):
        captured["app_root"] = app_root
        captured.update(kwargs)
        return {"target": "windows-x64", "stack": kwargs["versions"]}

    monkeypatch.setattr(inspector, "inspect_deployment", inspect_from_cli)
    monkeypatch.setattr(
        inspector.sys,
        "argv",
        [
            "inspect_windows_deployment.py",
            "inspect",
            "--app-root", str(app),
            "--output", str(output),
            "--source-commit", "a" * 40,
            "--runtime-probe", str(runtime_probe_path),
            "--locked-qt-root", str(app / "_internal" / "PyQt6" / "Qt6"),
            "--python-version", versions["python"],
            "--pyqt6-version", versions["pyqt6"],
            "--qt-version", versions["qt"],
            "--sip-version", versions["sip"],
            "--sip-runtime-version", versions["sip_runtime"],
            "--r-version", versions["r"],
            "--rpy2-version", versions["rpy2"],
            "--pyinstaller-version", versions["pyinstaller"],
        ],
    )

    assert inspector._main() == 0
    assert captured["versions"] == versions
    assert captured["runtime_probe"] == _windows_runtime_probe(app)
    assert json.loads(output.read_text(encoding="utf-8"))["stack"] == versions


def test_windows_deployment_inspector_rejects_legacy_duplicate_and_wrong_architecture(tmp_path):
    import shutil

    inspector = _load_windows_deployment_inspector()
    versions = {
        "python": "3.11.9",
        "pyqt6": "6.11.0",
        "qt": "6.11.1",
        "sip": "13.11.1",
        "sip_runtime": "6.15.2",
        "r": "4.6.1",
        "rpy2": "3.6.7",
        "pyinstaller": "6.21.0",
    }

    app = _windows_deployment_fixture(tmp_path / "legacy")
    _write_pe(app / "_internal" / "PyQt5" / "Qt5Core.dll")
    with pytest.raises(inspector.DeploymentInspectionError, match="mixed or legacy"):
        inspector.inspect_deployment(
            app, versions=versions, source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )

    app = _windows_deployment_fixture(tmp_path / "duplicate")
    _write_pe(app / "other" / "Qt6Core.dll")
    with pytest.raises(inspector.DeploymentInspectionError, match="duplicate Qt6"):
        inspector.inspect_deployment(
            app, versions=versions, source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )

    app = _windows_deployment_fixture(tmp_path / "architecture")
    _write_pe(app / "bad.dll", machine=0x014C)
    with pytest.raises(inspector.DeploymentInspectionError, match="non-x64"):
        inspector.inspect_deployment(
            app, versions=versions, source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )

    for binding in ("PySide2", "PySide6", "qtpy"):
        app = _windows_deployment_fixture(tmp_path / f"mixed-{binding}")
        _write_pe(app / "_internal" / binding / "binding.pyd")
        with pytest.raises(inspector.DeploymentInspectionError, match="mixed or legacy"):
            inspector.inspect_deployment(
                app, versions=versions, source_commit="a" * 40,
                runtime_probe=_windows_runtime_probe(app),
                locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
            )

    required_plugin = {
        "platforms": "qwindows.dll",
        "imageformats": "qjpeg.dll",
        "iconengines": "qsvgicon.dll",
        "styles": "qmodernwindowsstyle.dll",
        "tls": "qschannelbackend.dll",
    }
    for family, name in required_plugin.items():
        app = _windows_deployment_fixture(tmp_path / f"missing-{family}")
        (app / "_internal" / "PyQt6" / "Qt6" / "plugins" / family / name).unlink()
        with pytest.raises(inspector.DeploymentInspectionError, match="missing required Qt"):
            inspector.inspect_deployment(
                app, versions=versions, source_commit="a" * 40,
                runtime_probe=_windows_runtime_probe(app),
                locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
            )

    app = _windows_deployment_fixture(tmp_path / "duplicate-plugin")
    _write_pe(app / "_internal" / "plugins" / "qwindows.dll")
    with pytest.raises(inspector.DeploymentInspectionError, match="plugin root"):
        inspector.inspect_deployment(
            app, versions=versions, source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )

    for generated in ("forms/ui_dialog.py", "icons_rc.pyc"):
        app = _windows_deployment_fixture(tmp_path / ("generated-" + generated.replace("/", "-")))
        path = app / generated
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("generated", encoding="utf-8")
        with pytest.raises(inspector.DeploymentInspectionError, match="generated sources"):
            inspector.inspect_deployment(
                app, versions=versions, source_commit="a" * 40,
                runtime_probe=_windows_runtime_probe(app),
                locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
            )

    app = _windows_deployment_fixture(tmp_path / "stack-mismatch")
    mismatched = dict(versions, qt="6.11.0")
    with pytest.raises(inspector.DeploymentInspectionError, match="differs from the locked"):
        inspector.inspect_deployment(
            app, versions=mismatched, source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )

    app = _windows_deployment_fixture(tmp_path / "misplaced-library")
    source = app / "_internal" / "PyQt6" / "Qt6" / "bin" / "Qt6Network.dll"
    destination = app / "_internal" / "other" / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)
    with pytest.raises(inspector.DeploymentInspectionError, match="outside the authoritative"):
        inspector.inspect_deployment(
            app, versions=versions, source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )

    app = _windows_deployment_fixture(tmp_path / "runtime-probe-mismatch")
    probe = _windows_runtime_probe(app)
    probe["qt"]["runtime_qt_version"] = "6.11.0"
    with pytest.raises(inspector.DeploymentInspectionError, match="frozen Qt runtime"):
        inspector.inspect_deployment(
            app, versions=versions, source_commit="a" * 40,
            runtime_probe=probe,
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )

    app = _windows_deployment_fixture(tmp_path / "schema-runtime-probe-mismatch")
    probe = _windows_runtime_probe(app)
    probe["project_schemas"]["validated_members"].remove("state.json")
    with pytest.raises(
        inspector.DeploymentInspectionError,
        match="runtime did not validate the required project schemas",
    ):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=probe,
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )

    app = _windows_deployment_fixture(tmp_path / "locked-identity-mismatch")
    locked_qt = tmp_path / "locked-qt"
    shutil.copytree(app / "_internal" / "PyQt6" / "Qt6", locked_qt)
    with (locked_qt / "bin" / "Qt6Core.dll").open("ab") as stream:
        stream.write(b"different")
    with pytest.raises(inspector.DeploymentInspectionError, match="identity differs"):
        inspector.inspect_deployment(
            app, versions=versions, source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app), locked_qt_root=locked_qt,
        )

    app = _windows_deployment_fixture(tmp_path / "locked-plugin-mismatch")
    locked_qt = tmp_path / "locked-plugin-qt"
    shutil.copytree(app / "_internal" / "PyQt6" / "Qt6", locked_qt)
    with (locked_qt / "plugins" / "platforms" / "qwindows.dll").open("ab") as stream:
        stream.write(b"different")
    with pytest.raises(inspector.DeploymentInspectionError, match="plugin identity differs"):
        inspector.inspect_deployment(
            app, versions=versions, source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app), locked_qt_root=locked_qt,
        )

    app = _windows_deployment_fixture(tmp_path / "extra-qt-library")
    locked_qt = tmp_path / "extra-qt-library-locked"
    shutil.copytree(app / "_internal" / "PyQt6" / "Qt6", locked_qt)
    _write_pe(app / "_internal" / "PyQt6" / "Qt6" / "bin" / "Qt6Concurrent.dll")
    with pytest.raises(inspector.DeploymentInspectionError, match="library identity differs"):
        inspector.inspect_deployment(
            app, versions=versions, source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app), locked_qt_root=locked_qt,
        )

    app = _windows_deployment_fixture(tmp_path / "extra-plugin")
    locked_qt = tmp_path / "extra-plugin-locked"
    shutil.copytree(app / "_internal" / "PyQt6" / "Qt6", locked_qt)
    _write_pe(app / "_internal" / "PyQt6" / "Qt6" / "plugins" / "networkinformation" / "qnetworklistmanager.dll")
    with pytest.raises(inspector.DeploymentInspectionError, match="plugin identity differs"):
        inspector.inspect_deployment(
            app, versions=versions, source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app), locked_qt_root=locked_qt,
        )

    app = _windows_deployment_fixture(tmp_path / "mismatched-non-required-plugin")
    locked_qt = tmp_path / "mismatched-non-required-plugin-locked"
    shutil.copytree(app / "_internal" / "PyQt6" / "Qt6", locked_qt)
    locked_extra = locked_qt / "plugins" / "networkinformation" / "qnetworklistmanager.dll"
    _write_pe(locked_extra)
    packaged_extra = app / "_internal" / "PyQt6" / "Qt6" / "plugins" / "networkinformation" / "qnetworklistmanager.dll"
    _write_pe(packaged_extra)
    with packaged_extra.open("ab") as stream:
        stream.write(b"different")
    with pytest.raises(inspector.DeploymentInspectionError, match="plugin identity differs"):
        inspector.inspect_deployment(
            app, versions=versions, source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app), locked_qt_root=locked_qt,
        )

    app = _windows_deployment_fixture(tmp_path / "duplicate-non-required-plugin")
    locked_qt = tmp_path / "duplicate-non-required-plugin-locked"
    shutil.copytree(app / "_internal" / "PyQt6" / "Qt6", locked_qt)
    locked_extra = locked_qt / "plugins" / "networkinformation" / "qnetworklistmanager.dll"
    packaged_extra = app / "_internal" / "PyQt6" / "Qt6" / "plugins" / "networkinformation" / "qnetworklistmanager.dll"
    _write_pe(locked_extra)
    _write_pe(packaged_extra)
    _write_pe(app / "_internal" / "plugins" / "qnetworklistmanager.dll")
    with pytest.raises(inspector.DeploymentInspectionError, match="plugin root"):
        inspector.inspect_deployment(
            app, versions=versions, source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app), locked_qt_root=locked_qt,
        )

    app = _windows_deployment_fixture(tmp_path / "misplaced-unknown-plugin")
    _write_pe(app / "_internal" / "plugins" / "qcustomplugin.dll")
    with pytest.raises(inspector.DeploymentInspectionError, match="outside the authoritative plugin"):
        inspector.inspect_deployment(
            app, versions=versions, source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )

    app = _windows_deployment_fixture(tmp_path / "alternate-qpdf-plugin-tree")
    qt_root = app / "_internal" / "PyQt6" / "Qt6"
    _write_pe(qt_root / "plugins" / "imageformats" / "qpdf.dll")
    _write_pe(app / "_internal" / "plugins" / "imageformats" / "qpdf.dll")
    with pytest.raises(inspector.DeploymentInspectionError, match="plugin root"):
        inspector.inspect_deployment(
            app, versions=versions, source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app), locked_qt_root=qt_root,
        )

    app = _windows_deployment_fixture(tmp_path / "scaled-runtime-probe")
    probe = _windows_runtime_probe(app)
    probe["qt"]["scale_factor_environment"] = "1.25"
    with pytest.raises(inspector.DeploymentInspectionError, match="frozen Qt runtime"):
        inspector.inspect_deployment(
            app, versions=versions, source_commit="a" * 40,
            runtime_probe=probe,
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )


def test_windows_qualification_evidence_authenticates_complete_packaged_smoke(tmp_path):
    import json
    import zipfile

    inspector = _load_windows_deployment_inspector()
    archive = tmp_path / "RCMetaStudio-windows-x64.zip"
    runtime_probe = tmp_path / "runtime-probe.json"
    runtime_value = {"frozen": True}
    runtime_probe.write_text(json.dumps(runtime_value), encoding="utf-8")
    runtime_canonical = json.dumps(runtime_value, sort_keys=True, separators=(",", ":")) + "\n"
    import hashlib
    deployment = tmp_path / "deployment-manifest.json"
    deployment.write_text(
        json.dumps(
            {
                "target": "windows-x64",
                "stack": inspector.EXPECTED_VERSIONS,
                "runtime_probe_canonical_sha256": hashlib.sha256(runtime_canonical.encode()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    smoke = tmp_path / "packaged-smoke.json"
    smoke_log = tmp_path / "packaged-smoke.log"
    smoke_log.write_text(
        "\n".join(
            (
                "packaged-workflow:evidence-written",
                "packaged-runtime-probe:passed",
                "packaged-workflow:shell-created",
                "packaged-workflow:project-open:start",
                "packaged-workflow:project-open:return",
                "packaged-workflow:paint:complete",
                "packaged-workflow:project-exercise:complete",
                "packaged-workflow:post-close",
                "packaged-surface:scale-1.25-passed",
                "packaged-surface:scale-1.50-passed",
                "packaged-surface:scale-1.75-passed",
                "startup-project:normal-entry-point-passed",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    smoke.write_text(
        json.dumps(
            {
                "passed": True,
                "workflows": {
                    "automation_entry_point": True,
                    "converted_sample": "amino.rcms",
                    "representative_edit": True,
                    "real_r_analysis": True,
                    "result_text": True,
                    "expected_summary_sha256": inspector.EXPECTED_SUMMARY_SHA256,
                    "summary_sha256": inspector.EXPECTED_SUMMARY_SHA256,
                    "svg_sha256": {"Forest Plot": "a" * 64},
                    "locale_variants": [
                        {
                            "locale": "en_US", "input": "7.0", "canonical_value": 7.0,
                            "summary_sha256": inspector.EXPECTED_SUMMARY_SHA256,
                            "svg_sha256": {"Forest Plot": "a" * 64},
                        },
                        {
                            "locale": "de_DE", "input": "7,0", "canonical_value": 7.0,
                            "summary_sha256": inspector.EXPECTED_SUMMARY_SHA256,
                            "svg_sha256": {"Forest Plot": "a" * 64},
                        },
                    ],
                    "save_reopen": True,
                    "analysis_after_reopen": True,
                },
                "execution": {
                    "automation_exit_code": 0,
                    "positional_user_entry_exit_code": 0,
                    "scale_exit_codes": {"1.25": 0, "1.50": 0, "1.75": 0},
                    "post_close_marker": True,
                    "clean_exit": True,
                },
                "scales": [
                    {
                        "requested": scale,
                        "qt_scale_factor": scale,
                        "device_pixel_ratio": float(scale),
                        "baseline_device_pixel_ratio": 1.0,
                        "expected_device_pixel_ratio": float(scale),
                        "dpr_tolerance": 0.05,
                        "clipboard": True,
                        "critical_dialog": True,
                        "binary_resources": True,
                        "locale": "de_DE",
                        "platform_plugin": "windows",
                        "tls_backends": ["schannel"],
                        "active_style": "windows11",
                        "available_styles": ["Windows11", "Windows"],
                        "image_formats": ["ico", "jpeg", "svg"],
                    }
                    for scale in ("1.25", "1.50", "1.75")
                ],
            }
        ),
        encoding="utf-8",
    )
    root = "RCMetaStudio-0.1.2-windows-x64"
    embedded = {
        "qualification/deployment-manifest.json": deployment,
        "qualification/runtime-probe.json": runtime_probe,
        "qualification/packaged-smoke.json": smoke,
        "qualification/packaged-smoke.log": smoke_log,
    }
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(f"{root}/RCMetaStudio.exe", b"MZ")
        for relative, source in embedded.items():
            bundle.writestr(f"{root}/{relative}", source.read_bytes())
    archive_report = inspector.inspect_archive(
        archive, archive_root_name=root, embedded_files=embedded
    )
    archive_inspection = tmp_path / "archive-inspection.json"
    archive_inspection.write_text(json.dumps(archive_report), encoding="utf-8")

    evidence = inspector.write_qualification_evidence(
        archive=archive,
        deployment_manifest=deployment,
        smoke_evidence=smoke,
        smoke_log=smoke_log,
        runtime_probe=runtime_probe,
        archive_inspection=archive_inspection,
        output=tmp_path / "evidence.json",
    )

    assert evidence["passed"] is True
    assert evidence["artifact"]["sha256"] == inspector.sha256_file(archive)
    assert evidence["runner"]["runner_arch"]
    assert evidence["logs"][0]["sha256"] == inspector.sha256_file(smoke_log)

    mutated = json.loads(smoke.read_text(encoding="utf-8"))
    mutated["scales"][0]["device_pixel_ratio"] = 1.0
    smoke.write_text(json.dumps(mutated), encoding="utf-8")
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(f"{root}/RCMetaStudio.exe", b"MZ")
        for relative, source in embedded.items():
            bundle.writestr(f"{root}/{relative}", source.read_bytes())
    archive_report = inspector.inspect_archive(
        archive, archive_root_name=root, embedded_files=embedded
    )
    archive_inspection.write_text(json.dumps(archive_report), encoding="utf-8")
    with pytest.raises(inspector.DeploymentInspectionError, match="incomplete"):
        inspector.write_qualification_evidence(
            archive=archive, deployment_manifest=deployment, smoke_evidence=smoke,
            smoke_log=smoke_log, runtime_probe=runtime_probe,
            archive_inspection=archive_inspection, output=tmp_path / "mutated.json",
        )

    for member_names in (
        (f"{root}/../escape.txt",),
        (f"{root}\\qualification\\runtime-probe.json",),
        (f"{root}/A.txt", f"{root}/a.txt"),
    ):
        bad_archive = tmp_path / ("bad-" + str(len(member_names)) + ".zip")
        with zipfile.ZipFile(bad_archive, "w") as bundle:
            for name in member_names:
                bundle.writestr(name, b"bad")
        with pytest.raises(inspector.DeploymentInspectionError):
            inspector.inspect_archive(
                bad_archive, archive_root_name=root, embedded_files=embedded
            )
