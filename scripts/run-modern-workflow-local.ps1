param(
    [string]$ArtifactName = "OpenMetaAnalyst-modern-windows-x64",
    [switch]$RecreateVenv
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = Join-Path $repoRoot ".venv"
$pythonExe = Join-Path $venvRoot "Scripts\python.exe"

function Write-Step {
    param([string]$Message)
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message)
}

Push-Location $repoRoot
try {
    if ($RecreateVenv -and (Test-Path $venvRoot)) {
        Write-Step "Removing existing uv environment at .venv"
        Remove-Item -LiteralPath $venvRoot -Recurse -Force
    }

    Write-Step "Syncing locked modern environment with uv"
    uv sync --locked
    if ($LASTEXITCODE -ne 0) { throw "uv failed to sync the locked modern environment." }

    Write-Step "Running modern full-app automation tests"
    uv run pytest tests\modern\test_metaform_automation_launch.py
    if ($LASTEXITCODE -ne 0) { throw "Modern full-app automation tests failed." }

    Write-Step "Running remaining modern pytest suite"
    uv run pytest tests\modern --ignore=tests\modern\test_metaform_automation_launch.py
    if ($LASTEXITCODE -ne 0) { throw "Modern pytest tests failed." }

    Write-Step "Building modern Windows artifact with PyInstaller"
    & (Join-Path $repoRoot "scripts\build-modern-windows-binary.ps1") `
        -ArtifactName $ArtifactName `
        -PythonExe $pythonExe `
        -SkipDependencyInstall
    if ($LASTEXITCODE -ne 0) { throw "Modern Windows binary build failed." }

    Write-Step "Modern workflow complete: artifacts\$ArtifactName.zip"
}
finally {
    Pop-Location
}
