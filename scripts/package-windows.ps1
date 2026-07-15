param(
    [string]$ArtifactName = "RCMetaStudio-windows-x64",
    [string]$ArchiveRootName,
    [string]$RRuntimeRoot,
    [string]$RPackageCacheRoot,
    [switch]$RecreateVenv,
    [switch]$SkipClean,
    [switch]$SkipSmoke,
    [switch]$SkipVerification
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = Join-Path $repoRoot ".venv"
$pythonExe = Join-Path $venvRoot "Scripts\python.exe"
if (-not $RPackageCacheRoot) {
    $RPackageCacheRoot = Join-Path (Join-Path $repoRoot "artifacts") "r-library-cache"
}

function Write-Step {
    param([string]$Message)
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message)
}

function Resolve-RRuntimeRoot {
    if ($RRuntimeRoot) { return (Resolve-Path -LiteralPath $RRuntimeRoot).ProviderPath }
    if ($env:RCMS_R_HOME) { return (Resolve-Path -LiteralPath $env:RCMS_R_HOME).ProviderPath }
    if ($env:R_HOME) { return (Resolve-Path -LiteralPath $env:R_HOME).ProviderPath }
    $programFilesR = Join-Path $env:ProgramFiles "R"
    if (Test-Path $programFilesR) {
        $latestR = Get-ChildItem -Path $programFilesR -Directory | Sort-Object Name -Descending | Select-Object -First 1
        if ($latestR) { return (Resolve-Path -LiteralPath $latestR.FullName).ProviderPath }
    }
    throw "No source R runtime was found. Pass -RRuntimeRoot or set RCMS_R_HOME/R_HOME."
}

function Resolve-RscriptFromRuntime {
    param([string]$Root)
    $rscript = Join-Path $Root "bin\Rscript.exe"
    if (-not (Test-Path $rscript)) { throw "Rscript was not found in selected R runtime at '$rscript'." }
    return (Resolve-Path -LiteralPath $rscript).ProviderPath
}

Push-Location $repoRoot
try {
    if ($RecreateVenv -and (Test-Path $venvRoot)) {
        Write-Step "Removing existing uv environment at .venv"
        Remove-Item -LiteralPath $venvRoot -Recurse -Force
    }

    Write-Step "Syncing locked verification environment with uv"
    uv sync --locked
    if ($LASTEXITCODE -ne 0) { throw "uv failed to sync the locked verification environment." }

    $resolvedRRuntimeRoot = Resolve-RRuntimeRoot
    $resolvedRscript = Resolve-RscriptFromRuntime -Root $resolvedRRuntimeRoot

    if (-not $SkipVerification) {
        Write-Step "Running shared release-package verification"
        & $pythonExe scripts\verify_package_release.py --rscript $resolvedRscript --r-library-cache-root $RPackageCacheRoot
        if ($LASTEXITCODE -ne 0) { throw "Shared release-package verification failed." }
    }

    Write-Step "Building Windows package artifact with PyInstaller"
    $buildArgs = @{
        ArtifactName = $ArtifactName
        ArchiveRootName = $ArchiveRootName
        PythonExe = $pythonExe
        RRuntimeRoot = $resolvedRRuntimeRoot
        RPackageCacheRoot = $RPackageCacheRoot
        SkipDependencyInstall = $true
    }
    if ($SkipClean) { $buildArgs.SkipClean = $true }
    if ($SkipSmoke) { $buildArgs.SkipSmoke = $true }
    & (Join-Path $repoRoot "scripts\build-windows-package.ps1") @buildArgs
    if ($LASTEXITCODE -ne 0) { throw "Windows package build failed." }

    Write-Step "Windows package complete: artifacts\$ArtifactName.zip"
}
finally {
    Pop-Location
}
