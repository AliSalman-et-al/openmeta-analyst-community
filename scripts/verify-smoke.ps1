param(
    [switch]$Sync,
    [switch]$RecreateVenv,
    [switch]$RequireREvidence,
    [string]$RRuntimeRoot,
    [string]$Rscript
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = Join-Path $repoRoot ".venv"
$rDefaultPackageCacheRoot = Join-Path (Join-Path $repoRoot "artifacts") "r-default-library-cache"

function Write-Step {
    param([string]$Message)
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message)
}

function Resolve-FirstCommandSource {
    param([string]$Name)
    $command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) { return $command.Source }
    return $null
}

function Resolve-RRuntimeRoot {
    if ($RRuntimeRoot) { return (Resolve-Path -LiteralPath $RRuntimeRoot).ProviderPath }
    if ($env:RCMS_R_HOME) { return (Resolve-Path -LiteralPath $env:RCMS_R_HOME).ProviderPath }
    if ($env:R_HOME) { return (Resolve-Path -LiteralPath $env:R_HOME).ProviderPath }

    $rCommandSource = Resolve-FirstCommandSource "R"
    if ($rCommandSource) {
        $rHome = & $rCommandSource RHOME
        if ($LASTEXITCODE -eq 0 -and $rHome -and (Test-Path $rHome)) {
            return (Resolve-Path -LiteralPath $rHome).ProviderPath
        }
    }

    foreach ($root in @("HKCU:\Software\R-core\R", "HKLM:\Software\R-core\R", "HKCU:\Software\WOW6432Node\R-core\R", "HKLM:\Software\WOW6432Node\R-core\R")) {
        if (-not (Test-Path $root)) { continue }
        $rootProps = Get-ItemProperty -LiteralPath $root
        if ($rootProps.InstallPath -and (Test-Path $rootProps.InstallPath)) {
            return (Resolve-Path -LiteralPath $rootProps.InstallPath).ProviderPath
        }
        if ($rootProps.'Current Version') {
            $versionKey = Join-Path $root $rootProps.'Current Version'
            if (Test-Path $versionKey) {
                $versionProps = Get-ItemProperty -LiteralPath $versionKey
                if ($versionProps.InstallPath -and (Test-Path $versionProps.InstallPath)) {
                    return (Resolve-Path -LiteralPath $versionProps.InstallPath).ProviderPath
                }
            }
        }
        foreach ($versionKey in Get-ChildItem -LiteralPath $root) {
            $versionProps = Get-ItemProperty -LiteralPath $versionKey.PSPath
            if ($versionProps.InstallPath -and (Test-Path $versionProps.InstallPath)) {
                return (Resolve-Path -LiteralPath $versionProps.InstallPath).ProviderPath
            }
        }
    }
    return $null
}

function Resolve-RscriptForDefaultEvidence {
    if ($Rscript) {
        if (Test-Path $Rscript) { return (Resolve-Path -LiteralPath $Rscript).ProviderPath }
        $commandSource = Resolve-FirstCommandSource $Rscript
        if ($commandSource) { return $commandSource }
        throw "Rscript was not found at '$Rscript'."
    }

    if ($env:RCMS_RSCRIPT) {
        if (Test-Path $env:RCMS_RSCRIPT) { return (Resolve-Path -LiteralPath $env:RCMS_RSCRIPT).ProviderPath }
        throw "Rscript was not found at RCMS_RSCRIPT='$env:RCMS_RSCRIPT'."
    }

    $resolvedRRuntimeRoot = Resolve-RRuntimeRoot
    if ($resolvedRRuntimeRoot) {
        $runtimeRscript = Join-Path $resolvedRRuntimeRoot "bin\Rscript.exe"
        if (-not (Test-Path $runtimeRscript)) { throw "Rscript was not found in selected R runtime at '$runtimeRscript'." }
        return (Resolve-Path -LiteralPath $runtimeRscript).ProviderPath
    }

    $pathRscript = Resolve-FirstCommandSource "Rscript"
    if ($pathRscript) { return $pathRscript }
    return "Rscript"
}

Push-Location $repoRoot
try {
    if ($RecreateVenv -and (Test-Path $venvRoot)) {
        Write-Step "Removing existing uv environment at .venv"
        Remove-Item -LiteralPath $venvRoot -Recurse -Force
        $Sync = $true
    }

    if ($Sync) {
        Write-Step "Syncing locked verification environment with uv"
        uv sync --locked
        if ($LASTEXITCODE -ne 0) { throw "uv failed to sync the locked verification environment." }
    }
    else {
        Write-Step "Skipping dependency sync for warm local smoke verification"
    }

    $qtBuildRoot = Join-Path $repoRoot "build\qt6-verification"
    Write-Step "Generating canonical Qt6 forms and resources"
    uv run python scripts\build_qt6.py generate --build-root $qtBuildRoot
    if ($LASTEXITCODE -ne 0) { throw "Qt6 generation failed." }
    $env:RCMS_QT6_BUILD_ROOT = $qtBuildRoot
    $generatedPackage = Join-Path $qtBuildRoot "generated\rc_metastudio"
    $generatedForms = Join-Path $generatedPackage "forms"
    $pythonPathEntries = @($generatedPackage, $generatedForms)
    if ($env:PYTHONPATH) { $pythonPathEntries += $env:PYTHONPATH }
    $env:PYTHONPATH = $pythonPathEntries -join [IO.Path]::PathSeparator

    Write-Step "Collecting pytest verification nodes"
    uv run pytest tests --collect-only -q
    if ($LASTEXITCODE -ne 0) { throw "Pytest verification collection failed." }

    Write-Step "Validating manifest sanity"
    uv run python scripts\validate_golden_baseline_manifests.py
    if ($LASTEXITCODE -ne 0) { throw "Golden baseline manifest validation failed." }

    Write-Step "Running smoke pytest nodes"
    uv run pytest `
        tests\analysis_regression\golden\test_analysis_regression_compare.py::test_golden_summary_parser_reads_current_RCMetaR_summary_display `
        tests\python\fast\test_project_format.py::test_all_committed_samples_match_the_frozen_semantics_and_round_trip `
        tests\python\fast\test_qt6_cutover_finalization.py::test_final_cutover_audit_has_zero_active_legacy_findings
    if ($LASTEXITCODE -ne 0) { throw "Smoke pytest nodes failed." }

    Write-Step "Checking Default R Evidence prerequisites"
    $resolvedRscript = Resolve-RscriptForDefaultEvidence
    $rEvidenceArgs = @("run", "python", "scripts\verify_rcmetar_r_default.py", "--rscript", $resolvedRscript)
    if ($RequireREvidence) {
        $rEvidenceArgs += @("--require-r", "--require-installed-packages", "--install-missing", "--r-library-cache-root", $rDefaultPackageCacheRoot)
    }
    uv @rEvidenceArgs
    if ($LASTEXITCODE -ne 0) { throw "Default R Evidence prerequisites failed." }

    Write-Step "Smoke Verification Lane complete"
}
finally {
    Pop-Location
}
