import re
from pathlib import Path


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
    return set(re.findall(r"tests[/\\](?:python|analysis_regression|packaging|r_stack)(?:[/\\][A-Za-z_]+)?", text))


def pytest_option_tokens(text):
    return set(
        re.findall(r"(?<![A-Za-z0-9_-])(--dist|-n|loadfile|4)(?![A-Za-z0-9_-])", text)
    )


def project_dependencies():
    return set(re.findall(r'"([^"]+)"', read_repo_text("pyproject.toml")))


def test_windows_distributable_contract_is_declared():
    script = ps_contract("scripts", "build-windows-package.ps1")
    spec = read_repo_text("packaging", "pyinstaller", "rc-metastudio.spec")

    assert {"ArtifactName", "PythonExe", "RRuntimeRoot", "RPackageCacheRoot"} <= script[
        "params"
    ]
    assert {"SkipDependencyInstall", "SkipClean", "SkipSmoke"} <= script["params"]
    assert {
        "Resolve-CommandOrRepoPath",
        "Copy-DirectoryTree",
        "Assert-AppLayout",
        "Invoke-PackagedAppSmokeTest",
        "Invoke-PackagedWizardLayoutSmokeTest",
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
    assert {"icons_rc", "rpy2.robjects", "rpy2.rinterface"} <= script["hidden_imports"]
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
    assert "src\\rc_metastudio\\__main__.py" in script["paths"]
    assert "src/rc_metastudio/__main__.py" in spec
    assert "src\\rc_metastudio\\launch.py" not in script["text"]
    assert "src/rc_metastudio/launch.py" not in spec


def test_windows_r_cache_reinstalls_local_packages_after_cache_restore():
    script = ps_contract("scripts", "build-windows-package.ps1")["text"]

    assert relative_order(
        script,
        "Test-RDependencyPackages -RscriptExe $rscriptExe -Library $cacheLibrary",
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
        "Start-Process -FilePath $exePath -ArgumentList @($samplePath)",
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
        'Start-Process -FilePath $exePath -ArgumentList @("--automation-wizard-layout-smoke")'
        in script
    )
    assert '$env:QT_QPA_PLATFORM = "offscreen"' in script
    assert "WindowStyle Hidden" in script
    assert "RCMS_AUTOMATION_SMOKE_LOG = $env:RCMS_AUTOMATION_SMOKE_LOG" in script
    assert '$env:RCMS_AUTOMATION_SMOKE_LOG = $smokeLogPath' in script
    assert "automation-wizard-layout-smoke.log" in script
    assert "QT_QPA_PLATFORM = $env:QT_QPA_PLATFORM" in script


def test_fast_workflow_runs_smoke_before_fast_verification():
    workflow = workflow_contract(".github", "workflows", "fast-verification.yml")

    assert {
        "change-classifier",
        "smoke-verification",
        "fast-verification",
        "fast-verification-gate",
    } <= workflow["jobs"]
    assert workflow["needs"]["smoke-verification"] == {"change-classifier"}
    assert workflow["needs"]["fast-verification"] == {
        "change-classifier",
        "smoke-verification",
    }
    assert workflow["needs"]["fast-verification-gate"] == {
        "change-classifier",
        "smoke-verification",
        "fast-verification",
    }
    assert workflow["env"]["RCMS_CRAN_REPO"] == "https://cloud.r-project.org"
    assert workflow["events"] == {"workflow_dispatch", "push", "pull_request"}
    assert workflow["legacy_uses"] == []
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for _, ref, _ in workflow["uses"])
    assert "src/*" in workflow["text"]
    assert "tests/*" in workflow["text"]
    assert "docs/verification/RCMetaR-r-dependencies.json" in workflow["text"]
    assert "docs/verification/test-taxonomy.json" in workflow["text"]
    assert (
        ".\\scripts\\verify-smoke.ps1 -Sync -RequireREvidence"
        in workflow["runs"]
    )
    assert (
        ".\\scripts\\verify-fast.ps1 -Sync -RequireREvidence -StrictTaxonomy"
        in workflow["runs"]
    )
    assert workflow["restore_keys"] == []
    assert workflow["cache_paths"] == {"artifacts\\r-default-library-cache"}
    assert all(
        key.startswith("default-r-evidence-library-v2-windows-")
        for key in workflow["cache_keys"]
    )
    assert all(
        "scripts/verify_rcmetar_r_default.py" in key for key in workflow["cache_keys"]
    )
    assert all(
        "steps.r-cache-key.outputs.version" in key for key in workflow["cache_keys"]
    )
    assert "Fast Verification Change Classifier" in workflow["text"]
    assert "Fast Verification Gate" in workflow["text"]
    assert "pull-requests: read" in workflow["text"]
    assert "gh api --paginate" in workflow["text"]
    assert "branches:" in workflow["text"]
    assert "- master" in workflow["text"]
    assert 'if [ "$EVENT_NAME" = "push" ]; then' in workflow["text"]
    assert (
        "No fast verification inputs changed; Windows lanes intentionally skipped."
        in workflow["text"]
    )
    assert "timeout-minutes: 20" in workflow["text"]


def test_package_workflow_builds_path_aware_artifacts():
    workflow = workflow_contract(".github", "workflows", "package-verification.yml")

    assert {
        "windows-package",
        "macos-package-intel",
        "macos-package-arm64",
        "publish-release-assets",
    } <= workflow["jobs"]
    assert workflow["env"]["RCMS_CRAN_REPO"] == "https://cloud.r-project.org"
    assert workflow["events"] == {"workflow_dispatch", "push"}
    assert workflow["legacy_uses"] == []
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for _, ref, _ in workflow["uses"])
    assert workflow["paths"] == {"v*"}
    assert any(
        "RCMetaStudio-windows-x64.zip" in run
        for run in workflow["text"].splitlines()
    )
    assert any(
        "RCMetaStudio-macos-x64" in run
        for run in workflow["text"].splitlines()
    )
    assert any(
        "RCMetaStudio-macos-arm64" in run
        for run in workflow["text"].splitlines()
    )
    assert (
        "build\\windows-package\\dist\\RCMetaStudio\\automation-wizard-layout-smoke.log"
        in workflow["text"]
    )
    assert all("RCMS_CRAN_REPO_KEY" in key for key in workflow["cache_keys"])
    assert workflow["restore_keys"] == []
    assert all(
        key.startswith("bundled-r-library-v2-") for key in workflow["cache_keys"]
    )
    assert all(
        "steps.r-cache-key.outputs.version" in key for key in workflow["cache_keys"]
    )
    assert "-RRuntimeRoot" in workflow["text"]
    assert "--r-runtime-root" in workflow["text"]
    assert "if: ${{ github.event_name == 'push' || inputs.build_windows }}" in workflow["text"]
    assert "if: ${{ github.event_name == 'push' || inputs.build_macos }}" in workflow["text"]
    assert "${{ github.event_name == 'push' || inputs.build_windows }}" in workflow["text"]
    assert "${{ github.event_name == 'push' || inputs.build_macos }}" in workflow["text"]
    assert "RELEASE_TAG: ${{ github.event_name == 'push' && github.ref_name || inputs.release_tag }}" in workflow["text"]
    assert "publish_release:" in workflow["text"]
    assert "release_tag:" in workflow["text"]
    assert "Publish Release Assets" in workflow["text"]
    assert "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093" in workflow["text"]
    assert 'gh release upload "$RELEASE_TAG" "${assets[@]}" --clobber' in workflow["text"]
    assert "contents: write" in workflow["text"]
    assert "timeout-minutes: 45" in workflow["text"]
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
    assert {"RPackageCacheRoot", "RRuntimeRoot"} <= package["params"]
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
        "--bundle-identifier",
        "--r-package-cache-root",
    } <= script["case_options"]
    assert {
        "require_free_space_gb",
        "repo_path",
        "resolve_existing_dir",
        "copy_tree",
        "sha256_file",
        "sha256_stdin_12",
        "test_r_dependency_packages",
        "copy_r_library_packages",
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
        'bundle_identifier="org.researchconsultancy.rc-metastudio"'
        in local_script["text"]
    )
    assert "org.RCMetaStudio.community" not in script["text"]
    assert "org.RCMetaStudio.community" not in local_script["text"]


def test_local_macos_package_script_uses_shared_build_script():
    script = sh_contract("scripts", "package-macos.sh")

    assert {
        "--architecture",
        "--artifact-name",
        "--bundle-identifier",
        "--r-package-cache-root",
        "--r-runtime-root",
    } <= script["case_options"]
    assert relative_order(
        script["text"],
        "uv sync --locked",
        "uv run pytest tests/python/fast/test_pyqt5_verification_path.py tests/python/fast/test_pyqt5_generated_ui_imports.py tests/python/fast/test_project_pickle_migration.py tests/python/fast/test_qt_text_boundaries.py",
        '--r-runtime-root "$r_runtime_root"',
        'bash "$repo_root/scripts/build-macos-package.sh"',
    )


def test_shared_r_dependency_installer_is_used_by_packagers():
    installer = read_repo_text("scripts", "install-r-deps.R")
    windows = ps_contract("scripts", "build-windows-package.ps1")
    macos = sh_contract("scripts", "build-macos-package.sh")

    cran_default = re.search(
        r'Sys.getenv\("RCMS_CRAN_REPO",\s+"([^"]+)"\)', installer
    ).group(1)
    archive_url = re.search(r'HSROC\s+=\s+"([^"]+)"', installer).group(1)

    assert cran_default == "https://cloud.r-project.org"
    assert archive_url.endswith("/Archive/HSROC/HSROC_2.1.9.tar.gz")
    assert "cran_package_install_types <- function()" in installer
    assert '.Platform$pkgType != "source"' in installer
    assert 'return(c("binary", "source"))' in installer
    assert 'install.packages(missing, lib = lib, dependencies = NA, type = package_install_type)' in installer
    assert 'Sys.info()[["sysname"]]' not in installer
    assert {
        "Get-RPackageCacheKey",
        "Get-Sha256FileHash",
        "Test-RDependencyPackages",
    } <= windows["functions"]
    assert "docs\\verification\\RCMetaR-r-dependencies.json" in windows["paths"]
    assert "Get-Sha256FileHash -Path $installDeps" in windows["text"]
    assert "RCMetaR/DESCRIPTION" in macos["text"]
    assert "RCMS_CRAN_REPO" in windows["text"]
    assert "RCMS_CRAN_REPO" in macos["text"]


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


def test_windows_packager_restores_smoke_environment():
    script = ps_contract("scripts", "build-windows-package.ps1")["text"]

    assert relative_order(
        script,
        "$previousEnv = @{",
        'Start-Process -FilePath $exePath -ArgumentList @("--automation-smoke", $samplePath)',
        "foreach ($name in $previousEnv.Keys)",
    )


def test_windows_packager_uses_clean_directory_copies_for_incremental_builds():
    script = ps_contract("scripts", "build-windows-package.ps1")["text"]

    assert relative_order(
        script,
        "function Copy-DirectoryTree",
        'Copy-DirectoryTree -Source (Join-Path $repoRoot "sample_projects")',
    )
    assert relative_order(
        script,
        "function Copy-DirectoryTree",
        'Copy-DirectoryTree -Source $Root -Destination (Join-Path $DestinationRoot "R")',
    )
