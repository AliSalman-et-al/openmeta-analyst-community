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


def test_packaged_automation_smoke_asserts_formatted_summary_output():
    launch = (ROOT / "src" / "launch.py").read_text()

    for expected in [
        "_assert_standard_binary_summary_is_formatted",
        "binary.random",
        "Binary Random-Effects Model",
        " Model Results",
        "Heterogeneity",
        "$model.title",
        "$arrays",
        'attr(,"class")',
    ]:
        assert expected in launch


def test_packaged_smoke_launches_with_positional_project_argument():
    script = (ROOT / "scripts" / "build-modern-windows-binary.ps1").read_text()

    smoke_env_index = script.index('$env:OMA_STARTUP_PROJECT_SMOKE = "1"')
    positional_launch_index = script.index("ArgumentList @($samplePath)")

    assert positional_launch_index > smoke_env_index
    assert "Packaged startup project smoke test failed" in script


def test_launch_resolves_frozen_startup_project_arguments():
    launch = (ROOT / "src" / "launch.py").read_text()

    for expected in [
        "_resolve_startup_argv",
        "_native_windows_command_line_argv",
        "CommandLineToArgvW",
        "_startup_project_path(startup_argv)",
        "OMA_STARTUP_PROJECT_SMOKE",
    ]:
        assert expected in launch


def test_modern_windows_workflow_builds_separate_artifact():
    workflow = (ROOT / ".github" / "workflows" / "modern-python.yml").read_text()

    assert "windows-modern" in workflow
    assert "Verify OpenMetaR R Stack Slice" in workflow
    assert "uv run python scripts/verify_openmetar_r_stack.py" in workflow
    assert "build-modern-windows-binary.ps1" in workflow
    assert "OpenMetaAnalyst-modern-windows-x64.zip" in workflow
    assert "OpenMetaAnalyst-windows-x64.zip" not in workflow
    assert "workflow_dispatch:" in workflow
    assert "build_macos:" in workflow
    assert "build_macos_arm64:" in workflow
    assert "macos-modern-intel:" in workflow
    assert "macos-modern-arm64:" in workflow
    assert "macos-15-intel" in workflow
    assert "macos-14" in workflow
    assert "OpenMetaAnalyst-modern-macos-x64" in workflow
    assert "OpenMetaAnalyst-modern-macos-arm64" in workflow
    assert "github.event_name == 'workflow_dispatch' && inputs.build_macos }}" in workflow
    assert "github.event_name == 'workflow_dispatch' && inputs.build_macos_arm64 }}" in workflow


def test_local_modern_workflow_uses_uv():
    script = (ROOT / "scripts" / "run-modern-workflow-local.ps1").read_text()

    for expected in [
        "uv sync --locked",
        "uv run pytest tests\\modern\\test_metaform_automation_launch.py",
        "uv run pytest tests\\modern",
        "--ignore=tests\\modern\\test_metaform_automation_launch.py",
        "uv run python scripts\\verify_openmetar_r_stack.py",
        "OpenMetaR R Stack Slice verification failed.",
        '"-PythonExe", $pythonExe',
        "-SkipDependencyInstall",
        "-SkipClean",
        "-SkipSmoke",
    ]:
        assert expected in script


def test_modern_macos_distributable_contract_is_declared():
    script = (ROOT / "scripts" / "build-modern-macos-binary.sh").read_text()

    for expected in [
        "--architecture",
        "OpenMetaAnalyst-modern-macos-x64",
        "OpenMetaAnalyst-modern-macos-arm64",
        "PyInstaller",
        "--windowed",
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
        "rsync -a --delete",
        "repo_path",
        "skip_clean",
        "QT_QPA_PLATFORM",
        "OMA_REQUIRE_IN_PROCESS_RPY2",
        "OMA_STARTUP_PROJECT_SMOKE",
        "RPY2_CFFI_MODE",
    ]:
        assert expected in script


def test_local_modern_macos_workflow_uses_shared_build_script():
    script = (ROOT / "scripts" / "run-modern-workflow-local.sh").read_text()

    for expected in [
        "uv sync --locked",
        "uv run pytest tests/modern/test_metaform_automation_launch.py",
        "uv run pytest tests/modern --ignore=tests/modern/test_metaform_automation_launch.py",
        "build-modern-macos-binary.sh",
        "--architecture",
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
    assert "install_archive" not in installer
    assert "src/contrib/Archive" not in installer
    assert "repos = NULL" not in installer
    for archived_pin in [
        '"metafor", "1.9-9"',
        '"igraph", "1.0.1"',
        '"lme4", "1.1-12"',
    ]:
        assert archived_pin not in installer
    assert '"HSROC"' not in installer
    assert '"OpenMetaR"' not in installer
    assert "install-modern-r-deps.R" in windows
    assert "install-modern-r-deps.R" in macos
    assert "OpenMetaR-r-dependencies.json" in windows
    assert "OpenMetaR-r-dependencies.json" in macos
    assert "-rdeps-" in windows
    assert "-rdeps-" in macos


def test_openmetar_r_stack_verifier_declares_issue_114_gate_sequence():
    script = (ROOT / "scripts" / "verify_openmetar_r_stack.py").read_text()

    for expected in [
        "validate_openmetar_r_manifests.py",
        "install-modern-r-deps.R",
        "\"CMD\", \"INSTALL\"",
        "src\") / \"R\" / \"HSROC\"",
        "src\") / \"R\" / \"OpenMetaR\"",
        "\"CMD\", \"build\"",
        "\"CMD\"",
        "\"check\"",
        "analysis-smoke-test.R",
        "test_inprocess_rpy2_backend.py",
        "test_openmetar_r_manifest_validation.py",
        "--report-installed-versions",
        "isolated R library",
        "OpenMetaR R Stack Slice verification complete",
    ]:
        assert expected in script


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
