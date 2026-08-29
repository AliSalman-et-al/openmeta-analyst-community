param(
    [switch]$Sync,
    [string]$BuildRoot = "build/qt6-verification",
    [ValidateSet("Full", "Core", "RemainingSurfaces")]
    [string]$Section = "Full"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$remainingSurfaceTests = @(
    "tests/python/gui/test_adaptive_window_policy.py",
    "tests/python/gui/test_compact_transient_layout.py",
    "tests/python/gui/test_declarative_dialog_sizing.py",
    "tests/python/gui/test_edit_dataset_workspace_layout.py",
    "tests/python/gui/test_main_wizard_workflow_layout.py"
)

function Invoke-NativeSmokeCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string[]]$Command,
        [int]$TimeoutSeconds = 300
    )
    $runnerArguments = @(
        "run", "python", "scripts/run_with_timeout.py",
        "--timeout-seconds", $TimeoutSeconds,
        "--label", $Label,
        "--"
    ) + $Command
    & uv @runnerArguments
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE." }
}

function Invoke-NativeRemainingSurfaceSmoke {
    Invoke-NativeSmokeCommand -Label "Native Qt6 remaining-surface smoke" -Command @(
        "uv", "run", "python", "scripts/native_remaining_surfaces_smoke.py"
    )
    Invoke-NativeSmokeCommand -Label "Native Qt6 remaining-surface evidence validation" -Command @(
        "uv", "run", "python", "scripts/native_remaining_surfaces_smoke.py", "--validate-only"
    )
}

Push-Location $repoRoot
try {
    if ($Sync) {
        uv sync --locked
        if ($LASTEXITCODE -ne 0) { throw "uv sync --locked failed." }
    }

    uv run python scripts/build_qt6.py generate --build-root $BuildRoot
    if ($LASTEXITCODE -ne 0) { throw "Qt6 form or resource generation failed." }
    $env:RCMS_QT6_BUILD_ROOT = (Resolve-Path $BuildRoot).Path

    $guiRoot = Join-Path $repoRoot "tests/python/gui"
    $allGuiTests = @(Get-ChildItem -LiteralPath $guiRoot -File -Filter "test_*.py" |
        ForEach-Object { $_.FullName.Substring($repoRoot.Length + 1).Replace("\", "/") })
    $missingRemaining = @($remainingSurfaceTests | Where-Object { $_ -notin $allGuiTests })
    if ($missingRemaining.Count -ne 0) {
        throw "RemainingSurfaces GUI tests are missing: $($missingRemaining -join ', ')"
    }
    $coreGuiTests = @($allGuiTests | Where-Object { $_ -notin $remainingSurfaceTests })
    $overlap = @($coreGuiTests | Where-Object { $_ -in $remainingSurfaceTests })
    if ($overlap.Count -ne 0 -or ($coreGuiTests.Count + $remainingSurfaceTests.Count) -ne $allGuiTests.Count) {
        throw "Core and RemainingSurfaces GUI selections overlap or omit a GUI test."
    }

    if ($Section -eq "RemainingSurfaces") {
        uv run pytest -W error @remainingSurfaceTests
        if ($LASTEXITCODE -ne 0) { throw "Qt6 remaining-surface tests failed." }

        $previousQpa = $env:QT_QPA_PLATFORM
        $previousFatalWarnings = $env:QT_FATAL_WARNINGS
        Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
        $env:QT_FATAL_WARNINGS = "1"
        try { Invoke-NativeRemainingSurfaceSmoke }
        finally {
            if ($null -ne $previousQpa) { $env:QT_QPA_PLATFORM = $previousQpa }
            else { Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue }
            if ($null -ne $previousFatalWarnings) { $env:QT_FATAL_WARNINGS = $previousFatalWarnings }
            else { Remove-Item Env:QT_FATAL_WARNINGS -ErrorAction SilentlyContinue }
        }
        return
    }

    # Ty resolves generated modules from their flat build search paths while
    # runtime imports remain package-qualified through rc_metastudio.forms.
    uv run ty check `
        --extra-search-path "$BuildRoot/generated/rc_metastudio" `
        --extra-search-path "$BuildRoot/generated/rc_metastudio/forms" `
        --extra-search-path . `
        --extra-search-path src/rc_metastudio `
        --extra-search-path src `
        --extra-search-path scripts `
        --extra-search-path tests/python/gui `
        src/rc_metastudio scripts tests r/RCMetaR/inst/qa
    if ($LASTEXITCODE -ne 0) { throw "Repository-wide strict type verification failed." }

    # Core owns every GUI module except the five deliberately isolated
    # RemainingSurfaces modules, in one process with one QApplication owner.
    uv run pytest -W error @coreGuiTests
    if ($LASTEXITCODE -ne 0) { throw "Qt6 core GUI tests failed." }
    if ($Section -eq "Full") {
        uv run pytest -W error @remainingSurfaceTests
        if ($LASTEXITCODE -ne 0) { throw "Qt6 remaining-surface tests failed." }
    }

    $previousQpa = $env:QT_QPA_PLATFORM
    $previousFatalWarnings = $env:QT_FATAL_WARNINGS
    Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    $env:QT_FATAL_WARNINGS = "1"
    try {
        Invoke-NativeSmokeCommand -Label "Native qwindows Qt6 smoke" -Command @(
            "uv", "run", "python", "scripts/build_qt6.py", "native-smoke",
            "--build-root", $BuildRoot, "--exit-after-ms", "100"
        )
        $env:RCMS_STUB_BACKEND = "1"
        Invoke-NativeSmokeCommand -Label "Native RC MetaStudio Qt6 shell smoke" -Command @(
            "uv", "run", "rc-metastudio", "--automation-native-shell-smoke"
        )
        Invoke-NativeSmokeCommand -Label "Native Qt6 calculator smoke" -Command @(
            "uv", "run", "python", "scripts/native_calculator_smoke.py"
        )
        Invoke-NativeSmokeCommand -Label "Native Qt6 calculator evidence validation" -Command @(
            "uv", "run", "python", "scripts/native_calculator_smoke.py", "--validate-only"
        )
        Invoke-NativeSmokeCommand -Label "Native Qt6 analysis workflow smoke" -Command @(
            "uv", "run", "python", "scripts/native_analysis_smoke.py"
        )
        Invoke-NativeSmokeCommand -Label "Native Qt6 Results fractional-scale smoke" -Command @(
            "uv", "run", "python", "scripts/native_results_smoke.py"
        )
        Invoke-NativeSmokeCommand -Label "Native Qt6 Results evidence validation" -Command @(
            "uv", "run", "python", "scripts/native_results_smoke.py", "--validate-only"
        )
        if ($Section -eq "Full") { Invoke-NativeRemainingSurfaceSmoke }
        Invoke-NativeSmokeCommand -Label "Native R-load teardown smoke" -Command @(
            "uv", "run", "rc-metastudio", "--automation-shell-failure-smoke", "r-load"
        )
        Invoke-NativeSmokeCommand -Label "Native MainWindow teardown smoke" -Command @(
            "uv", "run", "rc-metastudio", "--automation-shell-failure-smoke", "meta-form"
        )
    }
    finally {
        if ($null -ne $previousQpa) { $env:QT_QPA_PLATFORM = $previousQpa }
        else { Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue }
        if ($null -ne $previousFatalWarnings) { $env:QT_FATAL_WARNINGS = $previousFatalWarnings }
        else { Remove-Item Env:QT_FATAL_WARNINGS -ErrorAction SilentlyContinue }
    }
}
finally { Pop-Location }
