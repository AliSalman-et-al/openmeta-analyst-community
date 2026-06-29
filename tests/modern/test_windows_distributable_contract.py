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
        "R\\library\\openmetar\\DESCRIPTION",
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
        "--hidden-import icons_rc",
        "--hidden-import rpy2.robjects",
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
    assert "build-modern-windows-binary.ps1" in workflow
    assert "OpenMetaAnalyst-modern-windows-x64.zip" in workflow
    assert "OpenMetaAnalyst-windows-x64.zip" not in workflow
    assert "workflow_dispatch:" in workflow
    assert "build_macos:" in workflow
    assert "macos-modern:" in workflow
    assert "macos-15-intel" in workflow
    assert "macos-14" in workflow
    assert "OpenMetaAnalyst-modern-macos-x64" in workflow
    assert "OpenMetaAnalyst-modern-macos-arm64" in workflow


def test_local_modern_workflow_uses_uv():
    script = (ROOT / "scripts" / "run-modern-workflow-local.ps1").read_text()

    for expected in [
        "uv sync --locked",
        "uv run pytest tests\\modern\\test_metaform_automation_launch.py",
        "uv run pytest tests\\modern",
        "--ignore=tests\\modern\\test_metaform_automation_launch.py",
        "-PythonExe $pythonExe",
        "-SkipDependencyInstall",
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
        "R/library/openmetar/DESCRIPTION",
        "LaunchOpenMetaAnalyst.command",
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
    ]:
        assert expected in script


def test_shared_modern_r_dependency_installer_is_used_by_packagers():
    installer = (ROOT / "scripts" / "install-modern-r-deps.R").read_text()
    windows = (ROOT / "scripts" / "build-modern-windows-binary.ps1").read_text()
    macos = (ROOT / "scripts" / "build-modern-macos-binary.sh").read_text()

    assert "R_LIBS_USER must point at the target bundled R library" in installer
    assert "install_archive(\"metafor\", \"1.9-9\")" in installer
    assert "install-modern-r-deps.R" in windows
    assert "install-modern-r-deps.R" in macos
