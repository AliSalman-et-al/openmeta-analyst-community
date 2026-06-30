from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_modern_windows_distributable_contract_is_declared():
    script = (ROOT / "scripts" / "build-modern-windows-binary.ps1").read_text()

    for expected in [
        "$PythonExe",
        "uv sync --locked",
        "launch.py",
        "OpenMetaAnalyst.exe",
        "_internal\\PyQt5",
        "sample_data\\BCG.oma",
        "sample_data\\amino.oma",
        "doc\\openMA_help.html",
        "R\\bin\\x64\\R.dll",
        "R\\library\\OpenMetaR\\DESCRIPTION",
        "r-library-cache",
        "scripts\\install-modern-r-deps.R",
        "Install-LocalRPackagesFromSource",
        "Assert-OpenMetaRSummaryFormatting",
        "print.summary.display",
        "print.summary.data",
        "LaunchOpenMetaAnalyst.bat",
        "Invoke-PackagedAppSmokeTest",
        "OMA_REQUIRE_IN_PROCESS_RPY2",
        "OMA_STARTUP_PROJECT_SMOKE",
        "RPY2_CFFI_MODE",
        "Resolve-CommandOrRepoPath",
        "Copy-DirectoryTree",
        "robocopy",
        "SkipClean",
        "SkipSmoke",
        '"--hidden-import", "icons_rc"',
        '"--hidden-import", "rpy2.robjects"',
        "sample_data\\amino.oma",
    ]:
        assert expected in script


def test_modern_windows_r_cache_reinstalls_local_packages_after_cache_restore():
    script = (ROOT / "scripts" / "build-modern-windows-binary.ps1").read_text()
    cache_hit = "if (Test-BundledRPackages -RscriptExe $rscriptExe -Library $cacheLibrary) {"
    cache_hit_index = script.index(cache_hit)
    install_index = script.index("Install-LocalRPackagesFromSource -Root $Root")

    assert install_index > cache_hit_index
    assert "Using cached bundled R library" in script
    assert "return\n    }\n\n    $installDeps" not in script


def test_packaged_smoke_launches_with_positional_project_argument():
    script = (ROOT / "scripts" / "build-modern-windows-binary.ps1").read_text()

    smoke_env_index = script.index('$env:OMA_STARTUP_PROJECT_SMOKE = "1"')
    positional_launch_index = script.index("ArgumentList @($samplePath)")

    assert positional_launch_index > smoke_env_index
    assert "Packaged startup project smoke test failed" in script


def test_modern_fast_workflow_runs_default_fast_verification_lane():
    workflow = (ROOT / ".github" / "workflows" / "modern-fast.yml").read_text()

    assert "Fast Verification Lane" in workflow
    assert ".\\scripts\\verify-modern-fast.ps1" in workflow
    assert "setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b" in workflow
    assert "uv python install 3.11" in workflow
    assert "uv cache prune --ci" in workflow
    assert "build-modern-windows-binary.ps1" not in workflow
    assert "upload-artifact" not in workflow


def test_modern_package_workflow_builds_path_aware_artifacts():
    workflow = (ROOT / ".github" / "workflows" / "modern-package.yml").read_text()

    assert "Windows Packaging Lane" in workflow
    assert "workflow_dispatch:" in workflow
    assert "branches:" in workflow
    assert '"**"' in workflow
    assert "paths:" in workflow
    assert "scripts/package-modern-windows.ps1" in workflow
    assert "scripts/package-modern-macos.sh" in workflow
    assert "scripts/build-modern-windows-binary.ps1" in workflow
    assert "scripts/build-modern-macos-binary.sh" in workflow
    assert "scripts/install-modern-r-deps.R" in workflow
    assert "src/R/**" in workflow
    assert "src/launch.py" in workflow
    assert "OpenMetaAnalyst-modern-windows-x64.zip" in workflow
    assert "OpenMetaAnalyst-windows-x64.zip" not in workflow
    assert "macos-package-intel:" in workflow
    assert "macos-package-arm64:" in workflow
    assert "macos-15-intel" in workflow
    assert "macos-14" in workflow
    assert "OpenMetaAnalyst-modern-macos-x64" in workflow
    assert "OpenMetaAnalyst-modern-macos-arm64" in workflow
    assert "github.event_name == 'workflow_dispatch' && inputs.build_macos }}" in workflow
    assert "github.event_name == 'workflow_dispatch' && inputs.build_macos_arm64 }}" in workflow


def test_lane_named_local_scripts_replace_old_workflow_wrappers():
    fast = (ROOT / "scripts" / "verify-modern-fast.ps1").read_text()
    package = (ROOT / "scripts" / "package-modern-windows.ps1").read_text()

    for expected in [
        "uv sync --locked",
        "uv run python scripts\\validate_golden_baseline_manifests.py",
        "uv run python scripts\\validate_test_taxonomy.py",
        'uv run pytest tests\\modern -m "fast or golden or packaging_contract"',
        "uv run python scripts\\verify_openmetar_r_default.py",
    ]:
        assert expected in fast

    for expected in [
        "uv run python scripts\\verify_openmetar_r_stack.py",
        "$buildArgs = @{",
        "ArtifactName = $ArtifactName",
        "PythonExe = $pythonExe",
        "SkipDependencyInstall = $true",
        "$buildArgs.SkipClean = $true",
        "$buildArgs.SkipSmoke = $true",
    ]:
        assert expected in package

    assert not (ROOT / "scripts" / "run-modern-workflow-local.ps1").exists()
    assert not (ROOT / "scripts" / "run-modern-workflow-local.sh").exists()
    assert not (ROOT / "src" / "building").exists()


def test_modern_macos_distributable_contract_is_declared():
    script = (ROOT / "scripts" / "build-modern-macos-binary.sh").read_text()

    for expected in [
        "--architecture",
        "--bundle-identifier",
        "OpenMetaAnalyst-modern-macos-x64",
        "OpenMetaAnalyst-modern-macos-arm64",
        "PyInstaller",
        "--windowed",
        "--target-architecture",
        "--osx-bundle-identifier",
        "--hidden-import icons_rc",
        "--hidden-import rpy2.robjects",
        "OpenMetaAnalyst.app",
        "Contents/MacOS",
        "sample_data/amino.oma",
        "doc/openMA_help.html",
        "scripts/install-modern-r-deps.R",
        "R/bin/Rscript",
        "R/library/OpenMetaR/DESCRIPTION",
        "LaunchOpenMetaAnalyst.command",
        "resolve_existing_dir",
        "copy_tree",
        "require_free_space_gb",
        "rsync -a --delete",
        "repo_path",
        "skip_clean",
        "QT_QPA_PLATFORM",
        "OMA_REQUIRE_IN_PROCESS_RPY2",
        "OMA_STARTUP_PROJECT_SMOKE",
        "RPY2_CFFI_MODE",
    ]:
        assert expected in script


def test_local_modern_macos_package_script_uses_shared_build_script():
    script = (ROOT / "scripts" / "package-modern-macos.sh").read_text()

    for expected in [
        "uv sync --locked",
        "uv run pytest tests/modern/test_pyqt5_ci_path.py tests/modern/test_pyqt5_generated_ui_imports.py tests/modern/test_project_pickle_loader.py",
        "build-modern-macos-binary.sh",
        "--architecture",
        "--bundle-identifier",
        "--skip-dependency-install",
        "--skip-clean",
        "--skip-smoke",
    ]:
        assert expected in script


def test_shared_modern_r_dependency_installer_is_used_by_packagers():
    installer = (ROOT / "scripts" / "install-modern-r-deps.R").read_text()
    windows = (ROOT / "scripts" / "build-modern-windows-binary.ps1").read_text()
    macos = (ROOT / "scripts" / "build-modern-macos-binary.sh").read_text()

    assert "R_LIBS_USER must point at the target bundled R library" in installer
    assert "install_cran_packages(" in installer
    assert "install_archive_package(" in installer
    assert "src/contrib/Archive/HSROC/HSROC_2.1.9.tar.gz" in installer
    assert "repos = NULL" in installer
    for archived_pin in [
        '"metafor", "1.9-9"',
        '"igraph", "1.0.1"',
        '"lme4", "1.1-12"',
    ]:
        assert archived_pin not in installer
    assert '"HSROC"' in installer
    assert '"2.1.9"' in installer
    assert '"OpenMetaR"' not in installer
    assert "install-modern-r-deps.R" in windows
    assert "install-modern-r-deps.R" in macos
    assert "OpenMetaR-r-dependencies.json" in windows
    assert "OpenMetaR-r-dependencies.json" in macos
    assert "-rdeps-" in windows
    assert "-rdeps-" in macos


def test_macos_packager_resolves_relative_python_before_changing_directory():
    script = (ROOT / "scripts" / "build-modern-macos-binary.sh").read_text()

    resolve_index = script.index('python_exe="$(repo_path "$python_exe")"')
    cd_src_index = script.index('cd "$src_dir"')
    pyinstaller_index = script.index('"$python_exe" -m PyInstaller')

    assert resolve_index < cd_src_index < pyinstaller_index
    assert "command -v \"$path\"" in script


def test_macos_packager_copies_resolved_r_runtime_contents():
    script = (ROOT / "scripts" / "build-modern-macos-binary.sh").read_text()

    resolve_r_index = script.index('r_runtime_root="$(resolve_existing_dir "$r_runtime_root" "Source R runtime")"')
    copy_r_index = script.index('copy_tree "$r_runtime_root" "$app_root/R"')
    rscript_check_index = script.index('if [ ! -x "$rscript" ] || [ ! -x "$r_binary" ]; then')

    assert resolve_r_index < copy_r_index < rscript_check_index
    assert 'rsync -a --delete "$source"/ "$destination"/' in script


def test_windows_packager_restores_smoke_environment():
    script = (ROOT / "scripts" / "build-modern-windows-binary.ps1").read_text()

    previous_env_index = script.index("$previousEnv = @{")
    smoke_index = script.index('Start-Process -FilePath $exePath -ArgumentList @("--automation-smoke", $samplePath)')
    restore_index = script.index("foreach ($name in $previousEnv.Keys)")

    assert previous_env_index < smoke_index < restore_index


def test_windows_packager_uses_clean_directory_copies_for_incremental_builds():
    script = (ROOT / "scripts" / "build-modern-windows-binary.ps1").read_text()

    helper_index = script.index("function Copy-DirectoryTree")
    sample_copy_index = script.index('Copy-DirectoryTree -Source (Join-Path $repoRoot "sample_data")')
    r_copy_index = script.index('Copy-DirectoryTree -Source $Root -Destination (Join-Path $DestinationRoot "R")')

    assert helper_index < sample_copy_index
    assert helper_index < r_copy_index
    assert "robocopy $Source $Destination /MIR" in script
