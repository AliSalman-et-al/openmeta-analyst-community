param(
    [string]$EnvName = "openmeta-analyst-community",
    [string]$ArtifactName = "OpenMetaAnalyst-windows-x64"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$srcDir = Join-Path $repoRoot "src"
$artifactDir = Join-Path $repoRoot "artifacts"
$distRoot = Join-Path $srcDir "dist"
$buildRoot = Join-Path $srcDir "build"
$appDir = Join-Path $distRoot "OpenMetaAnalyst"
$zipPath = Join-Path $artifactDir "$ArtifactName.zip"

$envList = conda env list --json | ConvertFrom-Json
$envPrefix = $envList.envs | Where-Object { (Split-Path $_ -Leaf) -eq $EnvName } | Select-Object -First 1
if (-not $envPrefix) {
    throw "Conda environment '$EnvName' was not found."
}

conda run -n $EnvName python -c "import PyInstaller"
if ($LASTEXITCODE -ne 0) {
    conda run -n $EnvName pip install pyinstaller==3.6
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller install failed." }
}

if (Test-Path $distRoot) { Remove-Item -LiteralPath $distRoot -Recurse -Force }
if (Test-Path $buildRoot) { Remove-Item -LiteralPath $buildRoot -Recurse -Force }
if (Test-Path $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null

Push-Location $srcDir
try {
    conda run -n $EnvName pyinstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name OpenMetaAnalyst `
        --icon images\meta.ico `
        --hidden-import sip `
        --distpath dist `
        --workpath build `
        win_prelaunch.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
}
finally {
    Pop-Location
}

Copy-Item -Path (Join-Path $envPrefix "R") -Destination (Join-Path $appDir "R") -Recurse -Force
foreach ($relativePath in @("Library\bin", "Library\mingw-w64\bin", "Library\usr\bin")) {
    $sourcePath = Join-Path $envPrefix $relativePath
    if (Test-Path $sourcePath) {
        Copy-Item -Path $sourcePath -Destination (Join-Path $appDir $relativePath) -Recurse -Force
    }
}
Copy-Item -Path (Join-Path $repoRoot "sample_data") -Destination (Join-Path $appDir "sample_data") -Recurse -Force

@'
@echo off
set APP_DIR=%~dp0
start "" "%APP_DIR%OpenMetaAnalyst.exe"
'@ | Set-Content -Path (Join-Path $appDir "LaunchOpenMetaAnalyst.bat") -Encoding ASCII

Compress-Archive -Path (Join-Path $appDir "*") -DestinationPath $zipPath -Force
Write-Host "Created $zipPath"
