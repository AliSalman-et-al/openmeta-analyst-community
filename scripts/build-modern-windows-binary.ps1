param(
    [string]$ArtifactName = "OpenMetaAnalyst-modern-windows-x64",
    [string]$PythonExe = "python",
    [string]$RRuntimeRoot,
    [string]$RPackageCacheRoot,
    [switch]$SkipDependencyInstall,
    [switch]$SkipClean,
    [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$srcDir = Join-Path $repoRoot "src"
$artifactDir = Join-Path $repoRoot "artifacts"
$distRoot = Join-Path $repoRoot "build\modern-windows\dist"
$workRoot = Join-Path $repoRoot "build\modern-windows\work"
$appDir = Join-Path $distRoot "OpenMetaAnalyst"
$zipPath = Join-Path $artifactDir "$ArtifactName.zip"
$tmpZipPath = "$zipPath.tmp"
if (-not $RPackageCacheRoot) {
    $RPackageCacheRoot = Join-Path $artifactDir "r-library-cache"
}

function Write-Step {
    param([string]$Message)
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message)
}

function Resolve-CommandOrRepoPath {
    param([string]$Path)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return (Resolve-Path -LiteralPath $Path).ProviderPath
    }
    if ($Path -match "[\\/]") {
        return (Resolve-Path -LiteralPath (Join-Path $repoRoot $Path)).ProviderPath
    }
    $command = Get-Command $Path -ErrorAction Stop
    return $command.Source
}

function Assert-PathExists {
    param([string]$Path, [string]$Description)
    if (-not (Test-Path $Path)) { throw "$Description was not found at '$Path'." }
}

function Copy-DirectoryTree {
    param([string]$Source, [string]$Destination)
    Assert-PathExists -Path $Source -Description "Source directory"
    if (Test-Path $Destination) { Remove-Item -LiteralPath $Destination -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null

    robocopy $Source $Destination /MIR /NFL /NDL /NJH /NJS /NP | Out-Host
    if ($LASTEXITCODE -gt 7) { throw "robocopy failed while copying '$Source' to '$Destination' with exit code $LASTEXITCODE." }
    $global:LASTEXITCODE = 0
}

function Assert-AppLayout {
    param([string]$Root)
    Assert-PathExists -Path (Join-Path $Root "OpenMetaAnalyst.exe") -Description "OpenMetaAnalyst executable"
    Assert-PathExists -Path (Join-Path $Root "_internal\PyQt5") -Description "Bundled PyQt5 runtime"
    Assert-PathExists -Path (Join-Path $Root "sample_data\BCG.oma") -Description "Bundled sample data"
    Assert-PathExists -Path (Join-Path $Root "sample_data\amino.oma") -Description "Bundled GUI slice sample data"
    Assert-PathExists -Path (Join-Path $Root "doc\openMA_help.html") -Description "Bundled help"
    Assert-PathExists -Path (Join-Path $Root "R\bin\x64\R.dll") -Description "Bundled R runtime"
    Assert-PathExists -Path (Join-Path $Root "R\library\OpenMetaR\DESCRIPTION") -Description "Bundled OpenMetaR R package"
    Assert-PathExists -Path (Join-Path $Root "LaunchOpenMetaAnalyst.bat") -Description "Windows launcher"
}

function Invoke-PackagedAppSmokeTest {
    param([string]$Root)
    $exePath = Join-Path $Root "OpenMetaAnalyst.exe"
    $samplePath = Join-Path $Root "sample_data\amino.oma"
    $previousEnv = @{
        OMA_REQUIRE_IN_PROCESS_RPY2 = $env:OMA_REQUIRE_IN_PROCESS_RPY2
        OMA_STARTUP_PROJECT_SMOKE = $env:OMA_STARTUP_PROJECT_SMOKE
        RPY2_CFFI_MODE = $env:RPY2_CFFI_MODE
    }
    try {
        $env:OMA_REQUIRE_IN_PROCESS_RPY2 = "1"
        $env:RPY2_CFFI_MODE = "ABI"
        $process = Start-Process -FilePath $exePath -ArgumentList @("--automation-smoke", $samplePath) -Wait -PassThru -WindowStyle Hidden
        if ($process.ExitCode -ne 0) { throw "Packaged app smoke test failed while opening '$samplePath' with exit code $($process.ExitCode)." }

        $env:OMA_STARTUP_PROJECT_SMOKE = "1"
        $startupProcess = Start-Process -FilePath $exePath -ArgumentList @($samplePath) -Wait -PassThru -WindowStyle Hidden
        if ($startupProcess.ExitCode -ne 0) { throw "Packaged startup project smoke test failed while opening '$samplePath' with exit code $($startupProcess.ExitCode)." }
    }
    finally {
        foreach ($name in $previousEnv.Keys) {
            if ($null -eq $previousEnv[$name]) {
                Remove-Item "Env:\$name" -ErrorAction SilentlyContinue
            }
            else {
                Set-Item "Env:\$name" $previousEnv[$name]
            }
        }
    }
}

function Compress-AppDirectory {
    param([string]$SourceDirectory, [string]$DestinationPath)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if (Test-Path $DestinationPath) { Remove-Item -LiteralPath $DestinationPath -Force }
    if (Test-Path $tmpZipPath) { Remove-Item -LiteralPath $tmpZipPath -Force }
    [System.IO.Compression.ZipFile]::CreateFromDirectory($SourceDirectory, $tmpZipPath, [System.IO.Compression.CompressionLevel]::Fastest, $false)
    Move-Item -LiteralPath $tmpZipPath -Destination $DestinationPath -Force
}

function Assert-ZipLayout {
    param([string]$Path)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $entryNames = @{}
        foreach ($entry in $zip.Entries) { $entryNames[$entry.FullName -replace "/", "\"] = $true }
        foreach ($requiredEntry in @("OpenMetaAnalyst.exe", "sample_data\BCG.oma", "sample_data\amino.oma", "doc\openMA_help.html", "R\bin\x64\R.dll", "R\library\OpenMetaR\DESCRIPTION", "LaunchOpenMetaAnalyst.bat")) {
            if (-not $entryNames.ContainsKey($requiredEntry)) { throw "Created ZIP is missing '$requiredEntry'." }
        }
        $hasPyQt5Runtime = $false
        foreach ($entryName in $entryNames.Keys) {
            if ($entryName.StartsWith("_internal\PyQt5\")) {
                $hasPyQt5Runtime = $true
                break
            }
        }
        if (-not $hasPyQt5Runtime) { throw "Created ZIP is missing bundled PyQt5 runtime." }
    }
    finally {
        $zip.Dispose()
    }
}

function Resolve-RRuntimeRoot {
    if ($RRuntimeRoot) { return (Resolve-Path -LiteralPath $RRuntimeRoot).ProviderPath }
    if ($env:OMA_R_HOME) { return (Resolve-Path -LiteralPath $env:OMA_R_HOME).ProviderPath }
    if ($env:R_HOME) { return (Resolve-Path -LiteralPath $env:R_HOME).ProviderPath }
    $programFilesR = Join-Path $env:ProgramFiles "R"
    if (Test-Path $programFilesR) {
        $latestR = Get-ChildItem -Path $programFilesR -Directory | Sort-Object Name -Descending | Select-Object -First 1
        if ($latestR) { return (Resolve-Path -LiteralPath $latestR.FullName).ProviderPath }
    }
    throw "No source R runtime was found. Pass -RRuntimeRoot or set OMA_R_HOME/R_HOME."
}

function Copy-RRuntime {
    param([string]$Root, [string]$DestinationRoot)
    Assert-PathExists -Path (Join-Path $Root "bin\x64\R.dll") -Description "Source R runtime"
    Copy-DirectoryTree -Source $Root -Destination (Join-Path $DestinationRoot "R")

    $runtimeParent = Split-Path -Parent $Root
    foreach ($relativePath in @("Library\bin", "Library\mingw-w64\bin", "Library\usr\bin")) {
        $sourcePath = Join-Path $runtimeParent $relativePath
        if (Test-Path $sourcePath) {
            Copy-DirectoryTree -Source $sourcePath -Destination (Join-Path $DestinationRoot $relativePath)
        }
    }
}

function Get-RPackageCacheKey {
    param([string]$RscriptExe)
    $version = & $RscriptExe -e "cat(paste0('R-', getRversion()))"
    if ($LASTEXITCODE -ne 0 -or -not $version) { throw "Could not determine R runtime version." }
    $installDeps = Join-Path $repoRoot "scripts\install-modern-r-deps.R"
    $manifest = Join-Path $repoRoot "docs\modernization\OpenMetaR-r-dependencies.json"
    $hashInput = @(
        (Get-FileHash -Algorithm SHA256 -LiteralPath $installDeps).Hash
        (Get-FileHash -Algorithm SHA256 -LiteralPath $manifest).Hash
    ) -join ""
    $policyHash = [System.BitConverter]::ToString(
        [System.Security.Cryptography.SHA256]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($hashInput))
    ).Replace("-", "").Substring(0, 12).ToLowerInvariant()
    return (($version.Trim() + "-rdeps-" + $policyHash) -replace "[^A-Za-z0-9_.-]", "_")
}

function Test-BundledRPackages {
    param([string]$RscriptExe, [string]$Library)
    if (-not (Test-Path $Library)) { return $false }
    $verify = "lib <- normalizePath('$($Library -replace '\\', '/')', winslash='/'); .libPaths(c(lib, .libPaths())); pkgs <- c('HSROC','OpenMetaR','metafor','lme4','igraph','mice','Hmisc'); ok <- vapply(pkgs, requireNamespace, logical(1), quietly=TRUE); if (!all(ok)) { print(ok); quit(status=1) }"
    & $RscriptExe -e $verify
    return ($LASTEXITCODE -eq 0)
}

function Assert-OpenMetaRSummaryFormatting {
    param([string]$RscriptExe, [string]$Library)
    $libraryPath = $Library -replace '\\', '/'
    $verify = @"
lib <- normalizePath('$libraryPath', winslash='/')
.libPaths(c(lib, .libPaths()))
library(OpenMetaR)
if (is.null(getS3method('print', 'summary.display', optional=TRUE))) {
  stop('print.summary.display is not registered')
}
if (is.null(getS3method('print', 'summary.data', optional=TRUE))) {
  stop('print.summary.data is not registered')
}
summary <- structure(
  list(
    model.title = 'Binary Random-Effects Model\n\nMetric: Odds Ratio',
    table.titles = c(' Model Results'),
    arrays = list(
      arr1 = structure(
        rbind(
          c('Estimate', 'Lower bound', 'Upper bound', 'p-Value'),
          c('0.770', '0.485', '1.222', '0.267')
        ),
        class = 'summary.data'
      )
    )
  ),
  class = 'summary.display'
)
rendered <- paste(capture.output(print(summary)), collapse='\n')
required <- c('Binary Random-Effects Model', ' Model Results', 'Estimate', '0.770')
if (!all(vapply(required, function(value) grepl(value, rendered, fixed=TRUE), logical(1)))) {
  stop(sprintf('summary.display formatted output missing expected text:\n%s', rendered))
}
leaks <- c('`$model.title', '`$arrays', 'attr(,"class")')
if (any(vapply(leaks, function(value) grepl(value, rendered, fixed=TRUE), logical(1)))) {
  stop(sprintf('summary.display fell back to raw R list output:\n%s', rendered))
}
"@
    & $RscriptExe -e $verify
    if ($LASTEXITCODE -ne 0) { throw "Bundled OpenMetaR summary formatting verification failed." }
}

function Copy-RLibrary {
    param([string]$Source, [string]$Destination)
    Copy-DirectoryTree -Source $Source -Destination $Destination
}

function Install-LocalRPackagesFromSource {
    param([string]$Root)
    $rExe = Join-Path $Root "R\bin\R.exe"
    $rscriptExe = Join-Path $Root "R\bin\Rscript.exe"
    $rLibrary = Join-Path $Root "R\library"
    $packageBuildRoot = Join-Path $workRoot "r-package-build"
    if (Test-Path $packageBuildRoot) { Remove-Item -LiteralPath $packageBuildRoot -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $packageBuildRoot | Out-Null
    Copy-Item -Path (Join-Path $srcDir "R\HSROC") -Destination (Join-Path $packageBuildRoot "HSROC") -Recurse -Force
    Copy-Item -Path (Join-Path $srcDir "R\OpenMetaR") -Destination (Join-Path $packageBuildRoot "OpenMetaR") -Recurse -Force
    Get-ChildItem -Path $packageBuildRoot -Recurse -Include *.o,*.so,*.dll | Remove-Item -Force

    & $rExe CMD INSTALL --library="$rLibrary" (Join-Path $packageBuildRoot "HSROC")
    if ($LASTEXITCODE -ne 0) { throw "R CMD INSTALL HSROC failed." }
    & $rExe CMD INSTALL --library="$rLibrary" (Join-Path $packageBuildRoot "OpenMetaR")
    if ($LASTEXITCODE -ne 0) { throw "R CMD INSTALL OpenMetaR failed." }

    Assert-OpenMetaRSummaryFormatting -RscriptExe $rscriptExe -Library $rLibrary
}

function Install-BundledRPackages {
    param([string]$Root)
    $rExe = Join-Path $Root "R\bin\R.exe"
    $rscriptExe = Join-Path $Root "R\bin\Rscript.exe"
    $rLibrary = Join-Path $Root "R\library"
    Assert-PathExists -Path $rExe -Description "Bundled R executable"
    Assert-PathExists -Path $rscriptExe -Description "Bundled Rscript executable"
    $env:R_LIBS = $rLibrary
    $env:R_LIBS_USER = $rLibrary
    $env:R_HOME = Join-Path $Root "R"
    $env:Path = @(
        (Join-Path $Root "R\bin\x64")
        (Join-Path $Root "R\bin")
        (Join-Path $Root "Library\bin")
        (Join-Path $Root "Library\mingw-w64\bin")
        (Join-Path $Root "Library\usr\bin")
        $env:Path
    ) -join ";"

    $rPackageCacheKey = Get-RPackageCacheKey -RscriptExe $rscriptExe
    $cacheLibrary = Join-Path (Join-Path $RPackageCacheRoot $rPackageCacheKey) "library"
    if (Test-BundledRPackages -RscriptExe $rscriptExe -Library $cacheLibrary) {
        Write-Host "Using cached bundled R library from $cacheLibrary"
        Copy-RLibrary -Source $cacheLibrary -Destination $rLibrary
    }
    else {
        Write-Step "Installing bundled R package dependencies"
        $installDeps = Join-Path $repoRoot "scripts\install-modern-r-deps.R"
        & $rscriptExe $installDeps
        if ($LASTEXITCODE -ne 0) { throw "Modern R dependency install failed." }
    }

    Write-Step "Installing local OpenMeta R packages"
    Install-LocalRPackagesFromSource -Root $Root
    & $rscriptExe -e "pkgs <- c('HSROC','OpenMetaR','metafor','lme4','igraph','mice','Hmisc'); ok <- vapply(pkgs, require, logical(1), character.only=TRUE); print(ok); if (!all(ok)) quit(status=1)"
    if ($LASTEXITCODE -ne 0) { throw "Bundled R package verification failed." }

    if (Test-BundledRPackages -RscriptExe $rscriptExe -Library $rLibrary) {
        Write-Host "Caching bundled R library at $cacheLibrary"
        Copy-RLibrary -Source $rLibrary -Destination $cacheLibrary
    }
}

if (-not $SkipDependencyInstall) {
    Push-Location $repoRoot
    try {
        Write-Step "Syncing locked modern environment"
        uv sync --locked
        if ($LASTEXITCODE -ne 0) { throw "Modern dependency sync failed." }
    }
    finally {
        Pop-Location
    }
    $PythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
}

$PythonExe = Resolve-CommandOrRepoPath -Path $PythonExe

& $PythonExe -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Modern Windows packaging requires Python 3.11 to match the CI runtime and PyQt5 wheel support." }

$requiredPyInstallerVersion = "6.21.0"
$installedPyInstallerVersion = & $PythonExe -c "import PyInstaller; print(PyInstaller.__version__)" 2>$null
if ($LASTEXITCODE -ne 0 -or $installedPyInstallerVersion.Trim() -ne $requiredPyInstallerVersion) {
    if ($SkipDependencyInstall) { throw "PyInstaller $requiredPyInstallerVersion is not installed in the selected Python environment." }
    & $PythonExe -m pip install "pyinstaller==$requiredPyInstallerVersion"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller install failed." }
}

if (-not $SkipClean) {
    if (Test-Path $distRoot) { Remove-Item -LiteralPath $distRoot -Recurse -Force }
    if (Test-Path $workRoot) { Remove-Item -LiteralPath $workRoot -Recurse -Force }
}
if (Test-Path $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
if (Test-Path $tmpZipPath) { Remove-Item -LiteralPath $tmpZipPath -Force }
New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
$resolvedRRuntimeRoot = Resolve-RRuntimeRoot

Push-Location $srcDir
try {
    $env:RPY2_CFFI_MODE = "ABI"
    $pyInstallerArgs = @(
        "--noconfirm",
        "--windowed",
        "--name", "OpenMetaAnalyst",
        "--icon", "images\OMA_community.ico",
        "--distpath", $distRoot,
        "--workpath", $workRoot,
        "--paths", "forms",
        "--hidden-import", "icons_rc",
        "--hidden-import", "rpy2.robjects",
        "--hidden-import", "rpy2.rinterface",
        "launch.py"
    )
    if (-not $SkipClean) {
        $pyInstallerArgs = @("--clean") + $pyInstallerArgs
    }
    Write-Step "Building Windows app bundle with PyInstaller"
    & $PythonExe -m PyInstaller @pyInstallerArgs
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
}
finally {
    Pop-Location
}

Copy-DirectoryTree -Source (Join-Path $repoRoot "sample_data") -Destination (Join-Path $appDir "sample_data")
Copy-DirectoryTree -Source (Join-Path $repoRoot "doc") -Destination (Join-Path $appDir "doc")
Write-Step "Bundling R runtime and packages"
Copy-RRuntime -Root $resolvedRRuntimeRoot -DestinationRoot $appDir
Install-BundledRPackages -Root $appDir

@'
@echo off
set APP_DIR=%~dp0
set RPY2_CFFI_MODE=ABI
start "" "%APP_DIR%OpenMetaAnalyst.exe" "%APP_DIR%sample_data\amino.oma"
'@ | Set-Content -Path (Join-Path $appDir "LaunchOpenMetaAnalyst.bat") -Encoding ASCII

Assert-AppLayout -Root $appDir
if (-not $SkipSmoke) {
    Write-Step "Running packaged Windows smoke checks"
    Invoke-PackagedAppSmokeTest -Root $appDir
}
Compress-AppDirectory -SourceDirectory $appDir -DestinationPath $zipPath
Assert-ZipLayout -Path $zipPath
Write-Host "Created $zipPath"
