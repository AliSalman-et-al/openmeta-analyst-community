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
$tmpZipPath = "$zipPath.tmp"

function Assert-PathExists {
    param(
        [string]$Path,
        [string]$Description
    )

    if (-not (Test-Path $Path)) {
        throw "$Description was not found at '$Path'."
    }
}

function Assert-AppLayout {
    param([string]$Root)

    Assert-PathExists -Path (Join-Path $Root "OpenMetaAnalyst.exe") -Description "OpenMetaAnalyst executable"
    Assert-PathExists -Path (Join-Path $Root "R\bin\x64\R.dll") -Description "Bundled R runtime"
    Assert-PathExists -Path (Join-Path $Root "Library\bin") -Description "Bundled conda Library\bin runtime"
    Assert-PathExists -Path (Join-Path $Root "sample_data\BCG.oma") -Description "Bundled sample data"
    Assert-PathExists -Path (Join-Path $Root "LaunchOpenMetaAnalyst.bat") -Description "Windows launcher"
}

function Compress-AppDirectory {
    param(
        [string]$SourceDirectory,
        [string]$DestinationPath
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if (Test-Path $DestinationPath) { Remove-Item -LiteralPath $DestinationPath -Force }
    if (Test-Path $tmpZipPath) { Remove-Item -LiteralPath $tmpZipPath -Force }

    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $SourceDirectory,
        $tmpZipPath,
        [System.IO.Compression.CompressionLevel]::Fastest,
        $false
    )
    Move-Item -LiteralPath $tmpZipPath -Destination $DestinationPath -Force
}

function Assert-ZipLayout {
    param([string]$Path)

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $entryNames = @{}
        foreach ($entry in $zip.Entries) {
            $entryNames[$entry.FullName -replace "/", "\"] = $true
        }

        foreach ($requiredEntry in @(
            "OpenMetaAnalyst.exe",
            "R\bin\x64\R.dll",
            "Library\bin\QtCore4.dll",
            "sample_data\BCG.oma",
            "LaunchOpenMetaAnalyst.bat"
        )) {
            if (-not $entryNames.ContainsKey($requiredEntry)) {
                throw "Created ZIP is missing '$requiredEntry'."
            }
        }
    }
    finally {
        $zip.Dispose()
    }
}

$envList = conda env list --json | ConvertFrom-Json
$envPrefix = $envList.envs | Where-Object { (Split-Path $_ -Leaf) -eq $EnvName } | Select-Object -First 1
if (-not $envPrefix) {
    throw "Conda environment '$EnvName' was not found."
}

$pythonExe = Join-Path $envPrefix "python.exe"
$pipExe = Join-Path $envPrefix "Scripts\pip.exe"
Assert-PathExists -Path $pythonExe -Description "Python executable"
Assert-PathExists -Path $pipExe -Description "pip executable"
Assert-PathExists -Path (Join-Path $envPrefix "R\bin\x64\R.dll") -Description "Conda R runtime"

& $pythonExe -c "import PyInstaller"
if ($LASTEXITCODE -ne 0) {
    & $pipExe install pyinstaller==3.6
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller install failed." }
}

if (Test-Path $distRoot) { Remove-Item -LiteralPath $distRoot -Recurse -Force }
if (Test-Path $buildRoot) { Remove-Item -LiteralPath $buildRoot -Recurse -Force }
if (Test-Path $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
if (Test-Path $tmpZipPath) { Remove-Item -LiteralPath $tmpZipPath -Force }
New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null

$env:R_HOME = Join-Path $envPrefix "R"
if (-not $env:R_USER) {
    $env:R_USER = "oma"
}
$env:Path = @(
    (Join-Path $envPrefix "R\bin\x64")
    (Join-Path $envPrefix "R\bin")
    (Join-Path $envPrefix "Library\bin")
    (Join-Path $envPrefix "Library\mingw-w64\bin")
    (Join-Path $envPrefix "Library\usr\bin")
    (Join-Path $envPrefix "Scripts")
    $envPrefix
    $env:Path
) -join ";"

Push-Location $srcDir
try {
    & $pythonExe -m PyInstaller `
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

Assert-AppLayout -Root $appDir
Compress-AppDirectory -SourceDirectory $appDir -DestinationPath $zipPath
Assert-ZipLayout -Path $zipPath
Write-Host "Created $zipPath"
