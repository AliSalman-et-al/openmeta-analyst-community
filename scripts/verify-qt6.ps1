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
        uv run python scripts/validate_qt6_surface_inventory.py --check-document
        if ($LASTEXITCODE -ne 0) { throw "Native Qt6 surface inventory validation failed." }
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

    $qtModules = @(uv run python scripts/import_qt_modules.py --root . --list)
    if ($LASTEXITCODE -ne 0 -or $qtModules.Count -eq 0) { throw "Handwritten Qt module discovery failed." }
    uv run ty check `
        --extra-search-path "$BuildRoot/generated/rc_metastudio" `
        --extra-search-path "$BuildRoot/generated/rc_metastudio/forms" `
        --extra-search-path src/rc_metastudio `
        --extra-search-path scripts `
        $qtModules
    if ($LASTEXITCODE -ne 0) { throw "Qt6 strict type verification failed." }

    $dependencyInputs = @("pyproject.toml", "uv.lock")
    $dependencyInputs += Get-ChildItem -File -ErrorAction SilentlyContinue `
        -Path "requirements*.txt", "constraints*.txt" | ForEach-Object { $_.FullName }
    uv run python -W error scripts/qt6_port.py strict --root . $dependencyInputs
    if ($LASTEXITCODE -ne 0) { throw "Qt6 strict dependency policy failed." }
    uv run python -W error scripts/qt6_port.py strict --root . `
        --expected-snapshot config/qt6-strict-source-backlog.json `
        --report "$BuildRoot/strict-source-findings.json" `
        src/rc_metastudio
    if ($LASTEXITCODE -ne 0) { throw "Qt6 authoritative source backlog drifted." }
    uv run python -W error -m rc_metastudio.qt6_cutover
    if ($LASTEXITCODE -ne 0) { throw "Qt6 final zero-legacy audit failed." }
    uv run python scripts/import_qt_modules.py --build-root $BuildRoot --report "$BuildRoot/qt-module-imports.json"
    if ($LASTEXITCODE -ne 0) { throw "Warnings-as-errors Qt module import audit failed." }

    $codemodSources = Get-ChildItem src/rc_metastudio -File -Filter *.py |
        Where-Object { $_.Name -notin @("qt6_port_tools.py", "qt6_cutover.py") } |
        ForEach-Object { $_.FullName }
    uv run python -W error scripts/qt6_port.py codemod --check --report docs/verification/qt6-codemod-second-run.json $codemodSources
    if ($LASTEXITCODE -ne 0) { throw "Qt6 second codemod run was not empty." }
    uv run python scripts/validate_qt6_surface_inventory.py --check-document
    if ($LASTEXITCODE -ne 0) { throw "Native Qt6 surface inventory validation failed." }

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
        Invoke-NativeSmokeCommand -Label "Native MetaForm teardown smoke" -Command @(
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
