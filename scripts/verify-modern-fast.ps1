param(
    [switch]$Sync,
    [switch]$RecreateVenv,
    [switch]$RequireREvidence,
    [switch]$StrictTaxonomy,
    [string]$FastWorkers = "4",
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

function Resolve-RRuntimeRoot {
    if ($RRuntimeRoot) { return (Resolve-Path -LiteralPath $RRuntimeRoot).ProviderPath }
    if ($env:RCMS_R_HOME) { return (Resolve-Path -LiteralPath $env:RCMS_R_HOME).ProviderPath }
    if ($env:R_HOME) { return (Resolve-Path -LiteralPath $env:R_HOME).ProviderPath }

    $rCommand = Get-Command "R" -CommandType Application -ErrorAction SilentlyContinue
    if ($rCommand) {
        $rHome = & $rCommand.Source RHOME
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
        $command = Get-Command $Rscript -CommandType Application -ErrorAction SilentlyContinue
        if ($command) { return $command.Source }
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

    $pathRscript = Get-Command "Rscript" -CommandType Application -ErrorAction SilentlyContinue
    if ($pathRscript) { return $pathRscript.Source }
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
        Write-Step "Syncing locked modern environment with uv"
        uv sync --locked
        if ($LASTEXITCODE -ne 0) { throw "uv failed to sync the locked modern environment." }
    }
    else {
        Write-Step "Skipping dependency sync for warm local verification"
    }

    Write-Step "Validating Comprehensive Golden Baseline manifests"
    uv run python scripts\validate_golden_baseline_manifests.py
    if ($LASTEXITCODE -ne 0) { throw "Golden baseline manifest validation failed." }

    Write-Step "Checking modern test taxonomy"
    $taxonomyArgs = @("run", "python", "scripts\validate_test_taxonomy.py")
    if ($StrictTaxonomy) {
        $taxonomyArgs += "--strict"
    }
    uv @taxonomyArgs
    if ($LASTEXITCODE -ne 0) { throw "Modern test taxonomy validation failed." }

    Write-Step "Running parallel fast verification pytest lanes"
    $fastPytestArgs = @("run", "pytest", "tests\modern\fast", "tests\modern\golden", "tests\modern\packaging_contract")
    if ($FastWorkers -and $FastWorkers -notin @("0", "1")) {
        $fastPytestArgs += @("--dist", "loadfile", "-n", $FastWorkers)
    }
    uv @fastPytestArgs
    if ($LASTEXITCODE -ne 0) { throw "Fast verification pytest lanes failed." }

    Write-Step "Verifying Default R Evidence"
    $resolvedRscript = Resolve-RscriptForDefaultEvidence
    $rEvidenceArgs = @("run", "python", "scripts\verify_rcmetar_r_default.py", "--rscript", $resolvedRscript)
    if ($RequireREvidence) {
        $rEvidenceArgs += @("--require-r", "--require-installed-packages", "--install-missing", "--r-library-cache-root", $rDefaultPackageCacheRoot)
    }
    uv @rEvidenceArgs
    if ($LASTEXITCODE -ne 0) { throw "Default R Evidence failed." }

    Write-Step "Fast Verification Lane complete"
}
finally {
    Pop-Location
}
