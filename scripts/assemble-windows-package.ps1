param(
    [Parameter(Mandatory=$true)][string]$ArtifactName,
    [Parameter(Mandatory=$true)][string]$ArchiveRootName,
    [Parameter(Mandatory=$true)][string]$RIntegrationKit,
    [Parameter(Mandatory=$true)][string]$ExpectedRIntegrationKitSha256
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Locked offline assembly environment is missing." }
& (Join-Path $repo "scripts\build-windows-package.ps1") -ArtifactName $ArtifactName `
    -ArchiveRootName $ArchiveRootName -PythonExe $python -RIntegrationKit $RIntegrationKit `
    -ExpectedRIntegrationKitSha256 $ExpectedRIntegrationKitSha256 -SkipDependencyInstall
if ($LASTEXITCODE -ne 0) { throw "Offline Windows package assembly failed." }
