param(
    [string]$ArtifactName = "RCMetaStudio-windows-x64",
    [string]$ArchiveRootName,
    [string]$PythonExe = "python",
    [string]$RRuntimeRoot,
    [string]$RPackageCacheRoot,
    [string]$RIntegrationKit,
    [string]$ExpectedRIntegrationKitSha256,
    [switch]$BuildDevRKit,
    [string]$DevRKitProvenance,
    [switch]$SkipDependencyInstall,
    [switch]$SkipClean,
    [switch]$SkipSmoke,
    [switch]$CaptureAdaptiveLayoutEvidence
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pinnedCranRepo = "https://packagemanager.posit.co/cran/2026-07-16"
$artifactDir = Join-Path $repoRoot "artifacts"
$distRoot = Join-Path $repoRoot "build\windows-package\dist"
$workRoot = Join-Path $repoRoot "build\windows-package\work"
$rIntegrationKitRoot = Join-Path $artifactDir "r-integration-kits\windows-x64"
if ($RIntegrationKit) { $rIntegrationKitRoot = (Resolve-Path -LiteralPath $RIntegrationKit).ProviderPath }
if (-not $RIntegrationKit -and -not $BuildDevRKit) {
    throw "Final assembly requires -RIntegrationKit and -ExpectedRIntegrationKitSha256. Use -BuildDevRKit only for an explicit local producer build."
}
if ($BuildDevRKit -and -not $DevRKitProvenance) {
    throw "-BuildDevRKit requires -DevRKitProvenance with verified artifact evidence."
}
$appDir = Join-Path $distRoot "RCMetaStudio"
$archiveStagingRoot = Join-Path $workRoot "zip-staging"
$zipPath = Join-Path $artifactDir "$ArtifactName.zip"
$qualificationEvidencePath = Join-Path $artifactDir "$ArtifactName-evidence.json"
$archiveInspectionPath = Join-Path $artifactDir "$ArtifactName-archive-inspection.json"
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

function Get-ProjectVersion {
    param([string]$PythonExe)
    $pyprojectPath = Join-Path $repoRoot "pyproject.toml"
    $version = & $PythonExe -c "import pathlib, sys, tomllib; print(tomllib.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))['project']['version'])" $pyprojectPath
    if ($LASTEXITCODE -ne 0 -or -not $version) { throw "Could not resolve RC MetaStudio version from pyproject.toml." }
    return $version.Trim()
}

function Assert-PathExists {
    param([string]$Path, [string]$Description)
    if (-not (Test-Path $Path)) { throw "$Description was not found at '$Path'." }
}

function Assert-WindowsPackageHost {
    $osVersion = [Environment]::OSVersion.Version
    if ($osVersion.Major -lt 10 -or $osVersion.Build -lt 17763) {
        throw "Windows package qualification requires Windows 10 version 1809 (build 17763) or later; got $osVersion."
    }
    if ($env:PROCESSOR_ARCHITECTURE -ne "AMD64") {
        throw "Windows package qualification requires an x64 host; got '$env:PROCESSOR_ARCHITECTURE'."
    }
}

function Stop-BoundedPackageProcessTree {
    param(
        [int]$ProcessId,
        [int]$TimeoutMilliseconds = 30000,
        [int]$TerminationWaitMilliseconds = 5000
    )
    $cleanup = $null
    $cleanupHandle = $null
    $cleanupTimedOut = $false
    $cleanupTerminationError = $null
    try {
        $cleanup = Start-Process -FilePath taskkill.exe -ArgumentList @(
            "/PID", $ProcessId, "/T", "/F"
        ) -PassThru -WindowStyle Hidden
        $cleanupHandle = $cleanup.Handle
        if ($null -eq $cleanupHandle -or $cleanupHandle -eq [IntPtr]::Zero) {
            throw "Could not acquire a valid taskkill process handle for process $ProcessId."
        }
        if (-not $cleanup.WaitForExit($TimeoutMilliseconds)) {
            $cleanupTimedOut = $true
            try {
                $cleanup.Kill()
            }
            catch {
                throw "taskkill exceeded its $TimeoutMilliseconds-millisecond bound and could not be terminated: $($_.Exception.Message)"
            }
            if (-not $cleanup.WaitForExit($TerminationWaitMilliseconds)) {
                throw "taskkill remained alive after its termination wait of $TerminationWaitMilliseconds milliseconds."
            }
        }
        $cleanup.WaitForExit()
        $cleanup.Refresh()
        $cleanupExitCode = $cleanup.ExitCode
        if ($cleanupTimedOut) {
            throw "taskkill exceeded its $TimeoutMilliseconds-millisecond cleanup bound."
        }
        if ($null -eq $cleanupExitCode -or $cleanupExitCode -ne 0) {
            throw "taskkill failed with exit code '$cleanupExitCode' for process $ProcessId."
        }
    }
    finally {
        if ($null -ne $cleanup) {
            $cleanupStillRunning = $true
            try { $cleanupStillRunning = -not $cleanup.HasExited } catch {}
            if ($cleanupStillRunning) {
                try { $cleanup.Kill() } catch { $cleanupTerminationError = $_ }
                if ($null -eq $cleanupTerminationError) {
                    try {
                        if (-not $cleanup.WaitForExit($TerminationWaitMilliseconds)) {
                            $cleanupTerminationError = "taskkill did not terminate within $TerminationWaitMilliseconds milliseconds."
                        }
                    }
                    catch {
                        $cleanupTerminationError = $_
                    }
                }
            }
            [GC]::KeepAlive($cleanupHandle)
            $cleanup.Dispose()
            if ($null -ne $cleanupTerminationError) {
                throw "Could not release bounded taskkill process: $cleanupTerminationError"
            }
        }
    }
}

function Invoke-BoundedPackageProcess {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [int]$TimeoutSeconds = 900,
        [string]$StandardOutputPath,
        [string]$StandardErrorPath,
        [switch]$Visible
    )
    $startArguments = @{
        FilePath = $FilePath
        ArgumentList = $ArgumentList
        PassThru = $true
    }
    if ($StandardOutputPath) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $StandardOutputPath) | Out-Null
        $startArguments.RedirectStandardOutput = $StandardOutputPath
    }
    if ($StandardErrorPath) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $StandardErrorPath) | Out-Null
        $startArguments.RedirectStandardError = $StandardErrorPath
    }
    if (-not $Visible) { $startArguments.WindowStyle = "Hidden" }
    $process = $null
    $processHandle = $null
    $lifecycleCleanupError = $null
    try {
        $process = Start-Process @startArguments
        # Acquire the native handle before the child can exit. Without an open
        # handle, Windows may release its administrative record before PowerShell
        # reads ExitCode, which surfaced as $null for the redirected GUI smoke.
        $processHandle = $process.Handle
        if ($null -eq $processHandle -or $processHandle -eq [IntPtr]::Zero) {
            throw "Could not acquire a valid handle for bounded package process $($process.Id)."
        }
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            Stop-BoundedPackageProcessTree -ProcessId $process.Id
            if (-not $process.WaitForExit(30000)) {
                throw "Packaged process watchdog cleanup failed after taskkill: $FilePath $($ArgumentList -join ' ')"
            }
            throw "Packaged process exceeded its $TimeoutSeconds-second watchdog and its process tree was terminated: $FilePath $($ArgumentList -join ' ')"
        }
        $process.WaitForExit()
        $process.Refresh()
        $exitCode = $process.ExitCode
        if ($null -eq $exitCode) {
            throw "Packaged process exited without a readable exit code: $FilePath $($ArgumentList -join ' ')"
        }
        return [int]$exitCode
    }
    finally {
        if ($null -ne $process) {
            $processStillRunning = $true
            try { $processStillRunning = -not $process.HasExited } catch {}
            if ($processStillRunning) {
                try {
                    Stop-BoundedPackageProcessTree -ProcessId $process.Id
                    if (-not $process.WaitForExit(30000)) {
                        $lifecycleCleanupError = "child did not exit within 30000 milliseconds after taskkill"
                    }
                }
                catch {
                    $lifecycleCleanupError = $_
                }
            }
            [GC]::KeepAlive($processHandle)
            $process.Dispose()
            if ($null -ne $lifecycleCleanupError) {
                throw "Could not release bounded package process: $lifecycleCleanupError"
            }
        }
    }
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

function Remove-BundledRInstallerResidue {
    param([string]$Root)
    $rRoot = Join-Path $Root "R"
    $requiredRuntimeFiles = @(
        (Join-Path $rRoot "bin\R.exe")
        (Join-Path $rRoot "bin\Rscript.exe")
        (Join-Path $rRoot "bin\x64\R.dll")
    )
    foreach ($requiredRuntimeFile in $requiredRuntimeFiles) {
        Assert-PathExists -Path $requiredRuntimeFile -Description "Portable bundled R runtime file"
    }

    $installerResidue = @(
        Get-ChildItem -LiteralPath $rRoot -Recurse -File |
            Where-Object { $_.Name -match '(?i)^unins000\..+$' }
    )
    foreach ($file in $installerResidue) {
        Remove-Item -LiteralPath $file.FullName -Force
    }
    $remainingResidue = @(
        Get-ChildItem -LiteralPath $rRoot -Recurse -File |
            Where-Object { $_.Name -match '(?i)^unins000\..+$' }
    )
    if ($remainingResidue.Count -ne 0) {
        throw "Windows R installer residue remained in the portable bundle: $($remainingResidue.FullName -join ', ')"
    }
    foreach ($requiredRuntimeFile in $requiredRuntimeFiles) {
        Assert-PathExists -Path $requiredRuntimeFile -Description "Portable bundled R runtime file after installer-residue removal"
    }
}

function Get-Sha256FileHash {
    param([string]$Path)
    $resolvedPath = (Resolve-Path -LiteralPath $Path).ProviderPath
    $stream = [System.IO.File]::OpenRead($resolvedPath)
    try {
        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        try {
            return [System.BitConverter]::ToString($sha256.ComputeHash($stream)).Replace("-", "").ToLowerInvariant()
        }
        finally {
            $sha256.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }
}

function Assert-AppLayout {
    param([string]$Root)
    Assert-PathExists -Path (Join-Path $Root "RCMetaStudio.exe") -Description "RCMetaStudio executable"
    Assert-PathExists -Path (Join-Path $Root "_internal\PyQt6") -Description "Bundled PyQt6 runtime"
    Assert-PathExists -Path (Join-Path $Root "sample_projects\BCG.rcms") -Description "Bundled sample project"
    Assert-PathExists -Path (Join-Path $Root "sample_projects\amino.rcms") -Description "Bundled GUI slice sample project"
    Assert-PathExists -Path (Join-Path $Root "R\bin\x64\R.dll") -Description "Bundled R runtime"
    Assert-PathExists -Path (Join-Path $Root "R\library\RCMetaR\DESCRIPTION") -Description "Bundled RCMetaR R package"
    Assert-PathExists -Path (Join-Path $Root "LaunchRCMetaStudio.bat") -Description "Windows launcher"
}

function Invoke-PackagedAppSmokeTest {
    param([string]$Root)
    $exePath = Join-Path $Root "RCMetaStudio.exe"
    $samplePath = Join-Path $Root "sample_projects\amino.rcms"
    $smokeEvidencePath = Join-Path $Root "qualification\packaged-smoke.json"
    $smokeLogPath = Join-Path $Root "qualification\packaged-smoke.log"
    $smokeStdoutPath = Join-Path $Root "qualification\packaged-smoke.stdout.log"
    $smokeStderrPath = Join-Path $Root "qualification\packaged-smoke.stderr.log"
    $hangTracePath = Join-Path $Root "qualification\packaged-smoke.hang-trace.log"
    $quotedSamplePath = '"{0}"' -f $samplePath
    $quotedSmokeEvidencePath = '"{0}"' -f $smokeEvidencePath
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $smokeEvidencePath) | Out-Null
    $previousEnv = @{
        RCMS_REQUIRE_IN_PROCESS_RPY2 = $env:RCMS_REQUIRE_IN_PROCESS_RPY2
        RCMS_STARTUP_PROJECT_SMOKE = $env:RCMS_STARTUP_PROJECT_SMOKE
        RPY2_CFFI_MODE = $env:RPY2_CFFI_MODE
        RCMS_PACKAGE_SMOKE_EVIDENCE = $env:RCMS_PACKAGE_SMOKE_EVIDENCE
        RCMS_AUTOMATION_SMOKE_LOG = $env:RCMS_AUTOMATION_SMOKE_LOG
        RCMS_AUTOMATION_HANG_TRACE = $env:RCMS_AUTOMATION_HANG_TRACE
        QT_SCALE_FACTOR = $env:QT_SCALE_FACTOR
        RCMS_PACKAGE_BASELINE_DPR = $env:RCMS_PACKAGE_BASELINE_DPR
    }
    try {
        $env:RCMS_REQUIRE_IN_PROCESS_RPY2 = "1"
        $env:RPY2_CFFI_MODE = "API"
        $env:RCMS_PACKAGE_SMOKE_EVIDENCE = $smokeEvidencePath
        $env:RCMS_AUTOMATION_SMOKE_LOG = $smokeLogPath
        $env:RCMS_AUTOMATION_HANG_TRACE = $hangTracePath
        $runtimeProbePath = Join-Path $Root "qualification\runtime-probe.json"
        $env:RCMS_PACKAGE_BASELINE_DPR = (& $PythonExe -c "import json,sys; print(json.load(open(sys.argv[1], encoding='utf-8'))['qt']['baseline_device_pixel_ratio'])" $runtimeProbePath).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $env:RCMS_PACKAGE_BASELINE_DPR) { throw "Could not read packaged baseline DPR." }
        $env:QT_SCALE_FACTOR = "1.25"
        $exitCode = Invoke-BoundedPackageProcess -FilePath $exePath `
            -ArgumentList @("--automation-native-smoke", $quotedSamplePath) `
            -StandardOutputPath $smokeStdoutPath -StandardErrorPath $smokeStderrPath
        if ($exitCode -ne 0) { throw "Packaged app smoke test failed while opening '$samplePath' with exit code $exitCode." }

        foreach ($scale in @("1.25", "1.50", "1.75")) {
            $env:QT_SCALE_FACTOR = $scale
            $surfaceExitCode = Invoke-BoundedPackageProcess -FilePath $exePath -ArgumentList @(
                "--automation-package-surface-smoke", $quotedSmokeEvidencePath, $scale
            )
            if ($surfaceExitCode -ne 0) {
                throw "Packaged Qt surface smoke failed at scale $scale with exit code $surfaceExitCode."
            }
        }

        $env:RCMS_STARTUP_PROJECT_SMOKE = "1"
        $startupExitCode = Invoke-BoundedPackageProcess -FilePath $exePath -ArgumentList @($quotedSamplePath)
        if ($startupExitCode -ne 0) { throw "Packaged startup project smoke test failed while opening '$samplePath' with exit code $startupExitCode." }
        & $PythonExe scripts\inspect_windows_deployment.py finalize-smoke `
            --smoke-evidence $smokeEvidencePath --smoke-log $smokeLogPath
        if ($LASTEXITCODE -ne 0) { throw "Packaged smoke finalization failed after clean process exits." }
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

function Invoke-PackagedAdaptiveLayoutEvidence {
    param([string]$Root)
    $exePath = Join-Path $Root "RCMetaStudio.exe"
    $samplePath = Join-Path $Root "sample_projects\amino.rcms"
    $evidenceRoot = Join-Path $repoRoot "build\windows-package\adaptive-layout-evidence\windows-x64"
    if (Test-Path $evidenceRoot) { Remove-Item -LiteralPath $evidenceRoot -Recurse -Force }
    $previousEnv = @{
        QT_QPA_PLATFORM = $env:QT_QPA_PLATFORM
        QT_SCALE_FACTOR = $env:QT_SCALE_FACTOR
        RCMS_REQUIRE_IN_PROCESS_RPY2 = $env:RCMS_REQUIRE_IN_PROCESS_RPY2
        RCMS_ADAPTIVE_LAYOUT_EVIDENCE_LOG = $env:RCMS_ADAPTIVE_LAYOUT_EVIDENCE_LOG
        RPY2_CFFI_MODE = $env:RPY2_CFFI_MODE
    }
    try {
        Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue
        $env:RCMS_REQUIRE_IN_PROCESS_RPY2 = "1"
        $env:RPY2_CFFI_MODE = "API"
        foreach ($scale in @(
            @{ Value = "1.0"; Directory = "scale-100" },
            @{ Value = "1.5"; Directory = "scale-150" }
        )) {
            $outputDir = Join-Path $evidenceRoot $scale.Directory
            $logPath = Join-Path $outputDir "automation-adaptive-layout-evidence.log"
            New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
            $env:QT_SCALE_FACTOR = $scale.Value
            $env:RCMS_ADAPTIVE_LAYOUT_EVIDENCE_LOG = $logPath
            $quotedOutputDir = '"{0}"' -f $outputDir
            $quotedSamplePath = '"{0}"' -f $samplePath
            $exitCode = Invoke-BoundedPackageProcess -FilePath $exePath -ArgumentList @(
                "--automation-adaptive-layout-evidence", $quotedOutputDir, $quotedSamplePath
            ) -Visible
            if ($exitCode -ne 0) {
                $message = "Native adaptive-layout evidence failed at scale $($scale.Value) with exit code $exitCode."
                if (Test-Path $logPath) {
                    $message = $message + " " + (Get-Content -Raw -LiteralPath $logPath).Trim()
                }
                throw $message
            }
            & $PythonExe (Join-Path $repoRoot "scripts\validate_adaptive_layout_evidence.py") `
                --root $outputDir --platform-plugin windows --scale-factor $scale.Value
            if ($LASTEXITCODE -ne 0) {
                throw "Adaptive-layout evidence validation failed at scale $($scale.Value)."
            }
        }
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

function Invoke-PackagedWizardLayoutSmokeTest {
    param([string]$Root)
    $exePath = Join-Path $Root "RCMetaStudio.exe"
    $smokeLogPath = Join-Path $Root "automation-wizard-layout-smoke.log"
    if (Test-Path $smokeLogPath) { Remove-Item -LiteralPath $smokeLogPath -Force }
    $previousEnv = @{
        QT_QPA_PLATFORM = $env:QT_QPA_PLATFORM
        RCMS_AUTOMATION_SMOKE_LOG = $env:RCMS_AUTOMATION_SMOKE_LOG
    }
    try {
        $env:QT_QPA_PLATFORM = "offscreen"
        $env:RCMS_AUTOMATION_SMOKE_LOG = $smokeLogPath
        $exitCode = Invoke-BoundedPackageProcess -FilePath $exePath -ArgumentList @("--automation-wizard-layout-smoke")
        if ($exitCode -ne 0) {
            $message = "Packaged wizard layout smoke test failed with exit code $exitCode."
            if (Test-Path $smokeLogPath) {
                $message = $message + " " + (Get-Content -Raw -LiteralPath $smokeLogPath).Trim()
            }
            throw $message
        }
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
    param([string]$SourceDirectory, [string]$ArchiveStagingRoot, [string]$ArchiveRootDirectory, [string]$DestinationPath)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if (Test-Path $DestinationPath) { Remove-Item -LiteralPath $DestinationPath -Force }
    if (Test-Path $tmpZipPath) { Remove-Item -LiteralPath $tmpZipPath -Force }
    if (Test-Path $ArchiveStagingRoot) { Remove-Item -LiteralPath $ArchiveStagingRoot -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $ArchiveStagingRoot | Out-Null
    Copy-DirectoryTree -Source $SourceDirectory -Destination $ArchiveRootDirectory
    [System.IO.Compression.ZipFile]::CreateFromDirectory($ArchiveStagingRoot, $tmpZipPath, [System.IO.Compression.CompressionLevel]::Fastest, $false)
    Move-Item -LiteralPath $tmpZipPath -Destination $DestinationPath -Force
}

function Assert-ZipLayout {
    param([string]$Path, [string]$ArchiveRootName)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $entryNames = @{}
        foreach ($entry in $zip.Entries) { $entryNames[$entry.FullName -replace "/", "\"] = $true }
        foreach ($entryName in $entryNames.Keys) {
            if (-not $entryName.StartsWith("$ArchiveRootName\")) { throw "Created ZIP entry is outside '$ArchiveRootName': $entryName" }
        }
        foreach ($requiredEntry in @("RCMetaStudio.exe", "sample_projects\BCG.rcms", "sample_projects\amino.rcms", "R\bin\x64\R.dll", "R\library\RCMetaR\DESCRIPTION", "LaunchRCMetaStudio.bat", "qualification\deployment-manifest.json")) {
            $requiredEntry = Join-Path $ArchiveRootName $requiredEntry
            if (-not $entryNames.ContainsKey($requiredEntry)) { throw "Created ZIP is missing '$requiredEntry'." }
        }
        $hasPyQt6Runtime = $false
        foreach ($entryName in $entryNames.Keys) {
            if ($entryName.StartsWith("$ArchiveRootName\_internal\PyQt6\")) {
                $hasPyQt6Runtime = $true
                break
            }
        }
        if (-not $hasPyQt6Runtime) { throw "Created ZIP is missing bundled PyQt6 runtime." }
    }
    finally {
        $zip.Dispose()
    }
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
    $cranRepo = if ($env:RCMS_CRAN_REPO) { $env:RCMS_CRAN_REPO } else { $pinnedCranRepo }
    $installDeps = Join-Path $repoRoot "scripts\install-r-deps.R"
    $binaryPolicy = Join-Path $repoRoot "scripts\r_binary_policy.R"
    $policyLoader = Join-Path $repoRoot "scripts\r_dependency_policy.py"
    $manifest = Join-Path $repoRoot "docs\verification\RCMetaR-r-dependencies.json"
    $description = Join-Path $repoRoot "r\RCMetaR\DESCRIPTION"
    $hashInput = @(
        (Get-Sha256FileHash -Path $installDeps)
        (Get-Sha256FileHash -Path $binaryPolicy)
        (Get-Sha256FileHash -Path $policyLoader)
        (Get-Sha256FileHash -Path $manifest)
        (Get-Sha256FileHash -Path $description)
        $cranRepo
    ) -join ""
    $policyHash = [System.BitConverter]::ToString(
        [System.Security.Cryptography.SHA256]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($hashInput))
    ).Replace("-", "").Substring(0, 12).ToLowerInvariant()
    return (($version.Trim() + "-rdeps-v2-" + $policyHash) -replace "[^A-Za-z0-9_.-]", "_")
}

function Test-RDependencyPackages {
    param([string]$RscriptExe, [string]$Library)
    if (-not (Test-Path $Library)) { return $false }
    $verify = "lib <- normalizePath('$($Library -replace '\\', '/')', winslash='/'); .libPaths(c(lib, .libPaths())); pkgs <- c('HSROC','metafor','lme4','pdftools','rsvg','svglite','tiff','xml2','igraph','mice','Hmisc'); ok <- vapply(pkgs, requireNamespace, logical(1), quietly=TRUE); if (!all(ok)) { print(ok); quit(status=1) }; if (as.character(packageVersion('HSROC')) != '2.1.9') quit(status=1)"
    & $RscriptExe -e $verify
    return ($LASTEXITCODE -eq 0)
}

function Invoke-PackagedRuntimeProbe {
    param([string]$Root)
    $exePath = Join-Path $Root "RCMetaStudio.exe"
    $probePath = Join-Path $Root "qualification\runtime-probe.json"
    $smokeLogPath = Join-Path $Root "qualification\packaged-smoke.log"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $probePath) | Out-Null
    $previousEnv = @{
        RPY2_CFFI_MODE = $env:RPY2_CFFI_MODE
        RCMS_REQUIRE_IN_PROCESS_RPY2 = $env:RCMS_REQUIRE_IN_PROCESS_RPY2
        RCMS_AUTOMATION_SMOKE_LOG = $env:RCMS_AUTOMATION_SMOKE_LOG
        QT_SCALE_FACTOR = $env:QT_SCALE_FACTOR
    }
    try {
        Remove-Item "Env:\QT_SCALE_FACTOR" -ErrorAction SilentlyContinue
        $env:RPY2_CFFI_MODE = "API"
        $env:RCMS_REQUIRE_IN_PROCESS_RPY2 = "1"
        $env:RCMS_AUTOMATION_SMOKE_LOG = $smokeLogPath
        $quotedProbePath = '"{0}"' -f $probePath
        $exitCode = Invoke-BoundedPackageProcess -FilePath $exePath -ArgumentList @(
            "--automation-package-runtime-probe", $quotedProbePath
        )
        if ($exitCode -ne 0 -or -not (Test-Path $probePath)) {
            throw "Frozen packaged runtime probe failed with exit code $exitCode."
        }
    }
    finally {
        foreach ($name in $previousEnv.Keys) {
            if ($null -eq $previousEnv[$name]) { Remove-Item "Env:\$name" -ErrorAction SilentlyContinue }
            else { Set-Item "Env:\$name" $previousEnv[$name] }
        }
    }
    return $probePath
}

function Invoke-StrictRDependencyPolicy {
    param([string]$RscriptExe, [string]$Library)
    New-Item -ItemType Directory -Force -Path $Library | Out-Null
    $env:R_LIBS = $Library
    $env:R_LIBS_USER = $Library
    $env:RCMS_CRAN_REPO = $pinnedCranRepo
    $env:RCMS_POLICY_PYTHON = $PythonExe
    & $RscriptExe (Join-Path $repoRoot "scripts\install-r-deps.R")
    if ($LASTEXITCODE -ne 0) { throw "Strict R dependency policy validation failed for '$Library'." }
}

function Test-BundledRPackages {
    param([string]$RscriptExe, [string]$Library)
    if (-not (Test-Path $Library)) { return $false }
    $verify = "lib <- normalizePath('$($Library -replace '\\', '/')', winslash='/'); .libPaths(c(lib, .libPaths())); pkgs <- c('HSROC','RCMetaR','metafor','lme4','pdftools','rsvg','svglite','tiff','xml2','igraph','mice','Hmisc'); ok <- vapply(pkgs, requireNamespace, logical(1), quietly=TRUE); if (!all(ok)) { print(ok); quit(status=1) }; if (as.character(packageVersion('HSROC')) != '2.1.9') quit(status=1)"
    & $RscriptExe -e $verify
    return ($LASTEXITCODE -eq 0)
}

function Assert-RCMetaRSummaryFormatting {
    param([string]$RscriptExe, [string]$Library)
    $libraryPath = $Library -replace '\\', '/'
    $verify = @"
lib <- normalizePath('$libraryPath', winslash='/')
.libPaths(c(lib, .libPaths()))
library(RCMetaR)
if (is.null(getS3method('print', 'summary.display', optional=TRUE))) {
  stop('print.summary.display is not registered')
}
if (is.null(getS3method('print', 'summary.data', optional=TRUE))) {
  stop('print.summary.data is not registered')
}
summary <- structure(
  list(
    model.title = 'Binary Random-Effects Model\n\nMetric: Odds Ratio',
    table.titles = c('Model Results'),
    arrays = list(
      arr1 = structure(
        rbind(
          c('Estimate', 'Lower bound', 'Upper bound', 'p-value'),
          c('0.770', '0.485', '1.222', '0.267')
        ),
        class = 'summary.data'
      )
    )
  ),
  class = 'summary.display'
)
rendered <- paste(capture.output(print(summary)), collapse='\n')
required <- c('Binary Random-Effects Model', 'Model Results', 'Estimate', '0.770')
if (!all(vapply(required, function(value) grepl(value, rendered, fixed=TRUE), logical(1)))) {
  stop(sprintf('summary.display formatted output missing expected text:\n%s', rendered))
}
leaks <- c('`$model.title', '`$arrays', 'attr(,"class")')
if (any(vapply(leaks, function(value) grepl(value, rendered, fixed=TRUE), logical(1)))) {
  stop(sprintf('summary.display fell back to raw R list output:\n%s', rendered))
}
"@
    & $RscriptExe -e $verify
    if ($LASTEXITCODE -ne 0) { throw "Bundled RCMetaR summary formatting verification failed." }
}

function Copy-RLibrary {
    param([string]$Source, [string]$Destination)
    Copy-DirectoryTree -Source $Source -Destination $Destination
}

function Copy-RLibraryPackages {
    param([string]$Source, [string]$Destination)
    Assert-PathExists -Path $Source -Description "Source R library"
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    foreach ($package in Get-ChildItem -Path $Source -Directory) {
        Copy-DirectoryTree -Source $package.FullName -Destination (Join-Path $Destination $package.Name)
    }
}

function Install-LocalRPackagesFromSource {
    param([string]$Root)
    $rExe = Join-Path $Root "R\bin\R.exe"
    $rscriptExe = Join-Path $Root "R\bin\Rscript.exe"
    $rLibrary = Join-Path $Root "R\library"
    $packageBuildRoot = Join-Path $workRoot "r-package-build"
    if (Test-Path $packageBuildRoot) { Remove-Item -LiteralPath $packageBuildRoot -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $packageBuildRoot | Out-Null
    Copy-Item -Path (Join-Path $repoRoot "r\RCMetaR") -Destination (Join-Path $packageBuildRoot "RCMetaR") -Recurse -Force
    Get-ChildItem -Path $packageBuildRoot -Recurse -Include *.o,*.so,*.dll | Remove-Item -Force

    & $rExe CMD INSTALL --library="$rLibrary" (Join-Path $packageBuildRoot "RCMetaR")
    if ($LASTEXITCODE -ne 0) { throw "R CMD INSTALL RCMetaR failed." }

    Assert-RCMetaRSummaryFormatting -RscriptExe $rscriptExe -Library $rLibrary
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
    if ($env:RCMS_CRAN_REPO -and $env:RCMS_CRAN_REPO -ne $pinnedCranRepo) {
        throw "RCMS_CRAN_REPO must match the manifest snapshot: $pinnedCranRepo"
    }
    $env:RCMS_CRAN_REPO = $pinnedCranRepo

    $rPackageCacheKey = Get-RPackageCacheKey -RscriptExe $rscriptExe
    $cacheLibrary = Join-Path (Join-Path $RPackageCacheRoot $rPackageCacheKey) "library"
    if (Test-Path $cacheLibrary) {
        Write-Step "Validating cached bundled R dependencies with the strict shared policy"
        Invoke-StrictRDependencyPolicy -RscriptExe $rscriptExe -Library $cacheLibrary
        Write-Host "Using cached bundled R library from $cacheLibrary"
        Copy-RLibraryPackages -Source $cacheLibrary -Destination $rLibrary
    }
    else {
        Write-Step "Installing bundled R package dependencies"
        Invoke-StrictRDependencyPolicy -RscriptExe $rscriptExe -Library $rLibrary
        if (Test-RDependencyPackages -RscriptExe $rscriptExe -Library $rLibrary) {
            Write-Host "Caching bundled R dependency library at $cacheLibrary"
            Copy-RLibrary -Source $rLibrary -Destination $cacheLibrary
        }
    }
    $env:R_LIBS = $rLibrary
    $env:R_LIBS_USER = $rLibrary

    Write-Step "Installing local RCMetaR package"
    Install-LocalRPackagesFromSource -Root $Root
    & $rscriptExe -e "pkgs <- c('HSROC','RCMetaR','metafor','lme4','pdftools','rsvg','svglite','tiff','xml2','igraph','mice','Hmisc'); ok <- vapply(pkgs, require, logical(1), character.only=TRUE); print(ok); if (!all(ok)) quit(status=1); if (as.character(packageVersion('HSROC')) != '2.1.9') quit(status=1)"
    if ($LASTEXITCODE -ne 0) { throw "Bundled R package verification failed." }

    if (-not (Test-BundledRPackages -RscriptExe $rscriptExe -Library $rLibrary)) { throw "Bundled R package verification failed after local RCMetaR install." }
}

if (-not $SkipDependencyInstall) {
    Push-Location $repoRoot
    try {
        Write-Step "Syncing locked verification environment"
        uv sync --locked
        if ($LASTEXITCODE -ne 0) { throw "Verification dependency sync failed." }
    }
    finally {
        Pop-Location
    }
    $PythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
}

$PythonExe = Resolve-CommandOrRepoPath -Path $PythonExe
Assert-WindowsPackageHost

Write-Step "Verifying redirected child exit-code capture"
$powerShellExe = (Get-Process -Id $PID).Path
& $powerShellExe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass `
    -File (Join-Path $repoRoot "scripts\test-bounded-package-process.ps1")
if ($LASTEXITCODE -ne 0) { throw "Bounded package process self-test failed." }

& $PythonExe -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Windows packaging requires the locked Python 3.11 runtime." }

$projectVersion = Get-ProjectVersion -PythonExe $PythonExe
$archiveRootName = if ($ArchiveRootName) { $ArchiveRootName } else { "RCMetaStudio-$projectVersion-windows-x64" }
if ($archiveRootName -match '[\\/:*?"<>|]') {
    throw "ArchiveRootName must be a single portable directory name, not '$archiveRootName'."
}
$archiveRootDir = Join-Path $archiveStagingRoot $archiveRootName

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
if (Test-Path $qualificationEvidencePath) { Remove-Item -LiteralPath $qualificationEvidencePath -Force }
if (Test-Path $archiveInspectionPath) { Remove-Item -LiteralPath $archiveInspectionPath -Force }
New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
$releaseAssembly = [bool]$RIntegrationKit
$resolvedRRuntimeRoot = if ($releaseAssembly) { Join-Path $rIntegrationKitRoot "runtime" } else { Resolve-RRuntimeRoot }
$cachedKitValid = $false
if (Test-Path $rIntegrationKitRoot) {
    $kitJson = & $PythonExe (Join-Path $repoRoot "scripts\r_integration_kit.py") verify --kit $rIntegrationKitRoot --target windows-x64
    $cachedKitValid = $LASTEXITCODE -eq 0
    if ($releaseAssembly) {
        if (-not $cachedKitValid) { throw "Authenticated Windows R integration kit is invalid." }
        $kitManifest = $kitJson | ConvertFrom-Json
        if (-not $ExpectedRIntegrationKitSha256 -or $kitManifest.kit_sha256 -ne $ExpectedRIntegrationKitSha256) {
            throw "Authenticated R integration-kit digest mismatch."
        }
        $resolvedRRuntimeRoot = Join-Path $rIntegrationKitRoot "runtime"
    }
}
if ($releaseAssembly -and -not $cachedKitValid) { throw "Authenticated Windows R integration kit is absent or invalid." }
if ($cachedKitValid) {
    Write-Step "Installing the cached target-native rpy2 API bridge"
    $pythonPlatformLibrary = (& $PythonExe -c "import sysconfig; print(sysconfig.get_paths()['platlib'])").Trim()
    Copy-Item -Path (Join-Path $rIntegrationKitRoot "bridge\_rinterface_cffi_api*.pyd") -Destination $pythonPlatformLibrary -Force
}
elseif (-not $releaseAssembly) {
    Write-Step "Building the target-native rpy2 API bridge against official R"
    $previousRHomeForBridge = $env:R_HOME
    $previousCffiModeForBridge = $env:RPY2_CFFI_MODE
    try {
        $env:R_HOME = $resolvedRRuntimeRoot
        $env:RPY2_CFFI_MODE = "API"
        & uv pip install --python $PythonExe --reinstall --no-binary rpy2-rinterface "rpy2-rinterface==3.6.6"
        if ($LASTEXITCODE -ne 0) { throw "Target-native rpy2 API bridge build failed." }
    }
    finally {
        if ($null -eq $previousRHomeForBridge) { Remove-Item Env:\R_HOME -ErrorAction SilentlyContinue } else { $env:R_HOME = $previousRHomeForBridge }
        if ($null -eq $previousCffiModeForBridge) { Remove-Item Env:\RPY2_CFFI_MODE -ErrorAction SilentlyContinue } else { $env:RPY2_CFFI_MODE = $previousCffiModeForBridge }
    }
}
$pyQtRoot = (& $PythonExe -c "from pathlib import Path; import PyQt6; print(Path(PyQt6.__file__).resolve().parent)").Trim()
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $pyQtRoot)) { throw "Could not resolve the locked PyQt6 runtime root." }
Push-Location $repoRoot
$previousPyQtRoot = $env:RCMS_PYQT_ROOT
$previousQt6BuildRoot = $env:RCMS_QT6_BUILD_ROOT
try {
    # packaging/pyinstaller/rc-metastudio.spec is the sole authoritative
    # PyInstaller collection definition. This wrapper only supplies build roots.
    $env:RPY2_CFFI_MODE = "API"
    $env:RCMS_PYQT_ROOT = $pyQtRoot
    $qt6PackageBuildRoot = Join-Path $workRoot "qt6-input"
    & $PythonExe scripts\build_qt6.py generate --build-root $qt6PackageBuildRoot
    if ($LASTEXITCODE -ne 0) { throw "Qt6 package form/resource generation failed." }
    $env:RCMS_QT6_BUILD_ROOT = $qt6PackageBuildRoot
    $pyInstallerArgs = @(
        "--noconfirm",
        "--distpath", $distRoot,
        "--workpath", $workRoot,
        "packaging\pyinstaller\rc-metastudio.spec"
    )
    if (-not $SkipClean) {
        $pyInstallerArgs = @("--clean") + $pyInstallerArgs
    }
    Write-Step "Building Windows app bundle with PyInstaller"
    & $PythonExe -m PyInstaller @pyInstallerArgs
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
}
finally {
    if ($null -eq $previousPyQtRoot) { Remove-Item Env:\RCMS_PYQT_ROOT -ErrorAction SilentlyContinue }
    else { $env:RCMS_PYQT_ROOT = $previousPyQtRoot }
    if ($null -eq $previousQt6BuildRoot) { Remove-Item Env:\RCMS_QT6_BUILD_ROOT -ErrorAction SilentlyContinue }
    else { $env:RCMS_QT6_BUILD_ROOT = $previousQt6BuildRoot }
    Pop-Location
}

if ($releaseAssembly) {
    Copy-Item -LiteralPath (Join-Path $rIntegrationKitRoot "native\python311.dll") `
        -Destination (Join-Path $appDir "python311.dll") -Force
}

Copy-DirectoryTree -Source (Join-Path $repoRoot "sample_projects") -Destination (Join-Path $appDir "sample_projects")
Write-Step "Bundling R runtime and packages"
if ($releaseAssembly) {
    Copy-DirectoryTree -Source (Join-Path $rIntegrationKitRoot "runtime") -Destination (Join-Path $appDir "R")
}
else {
    Copy-RRuntime -Root $resolvedRRuntimeRoot -DestinationRoot $appDir
    Remove-BundledRInstallerResidue -Root $appDir
    Install-BundledRPackages -Root $appDir
}

Write-Step "Building and consuming the local target-native R integration kit"
$rpy2ApiBridge = Get-ChildItem -LiteralPath $appDir -Recurse -File -Filter "_rinterface_cffi_api*.pyd" | Select-Object -First 1
if ($null -eq $rpy2ApiBridge) { throw "The required rpy2 API bridge was not collected for the integration kit." }
$rpy2AbiBridge = Get-ChildItem -LiteralPath $appDir -Recurse -File -Filter "_rinterface_cffi_abi*" | Select-Object -First 1
if ($null -ne $rpy2AbiBridge) { throw "The forbidden rpy2 ABI fallback was collected." }
$rDll = Join-Path $appDir "R\bin\x64\R.dll"
if (-not (Test-Path $rDll)) { throw "The private Windows R runtime is missing R.dll." }
$rSourceIdentity = (Get-FileHash -Algorithm SHA256 -LiteralPath $rDll).Hash.ToLowerInvariant()
$rPackageLockSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $repoRoot "docs\verification\RCMetaR-r-dependencies.json")).Hash.ToLowerInvariant()
$sourceCommit = (& git rev-parse HEAD).Trim()
$uvLock = Join-Path $repoRoot "uv.lock"
$uvLockSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $uvLock).Hash.ToLowerInvariant()
$uvCacheDir = (& uv cache dir).Trim()
$kitIsValid = $false
if (Test-Path $rIntegrationKitRoot) {
    & $PythonExe (Join-Path $repoRoot "scripts\r_integration_kit.py") verify --kit $rIntegrationKitRoot --target windows-x64
    $kitIsValid = $LASTEXITCODE -eq 0
}
if (-not $kitIsValid -and -not $releaseAssembly) {
    if (Test-Path $rIntegrationKitRoot) { Remove-Item -LiteralPath $rIntegrationKitRoot -Recurse -Force }
    & $PythonExe (Join-Path $repoRoot "scripts\r_integration_kit.py") build `
        --target windows-x64 --runtime (Join-Path $appDir "R") `
        --library (Join-Path $appDir "R\library") --api-bridge $rpy2ApiBridge.FullName `
        --output $rIntegrationKitRoot --provenance-manifest $DevRKitProvenance `
        --package-lock-sha256 $rPackageLockSha256 --source-commit $sourceCommit `
        --uv-cache $uvCacheDir --uv-lock $uvLock --uv-lock-sha256 $uvLockSha256 `
        --source-payload (Join-Path (Split-Path -Parent $DevRKitProvenance) "source-payload")
    if ($LASTEXITCODE -ne 0) { throw "Windows R integration-kit build failed." }
}
& $PythonExe (Join-Path $repoRoot "scripts\r_integration_kit.py") verify --kit $rIntegrationKitRoot --target windows-x64
if ($LASTEXITCODE -ne 0) { throw "Windows R integration-kit verification failed." }
Copy-DirectoryTree -Source (Join-Path $rIntegrationKitRoot "runtime") -Destination (Join-Path $appDir "R")
Copy-Item -LiteralPath (Join-Path $rIntegrationKitRoot ("bridge\" + $rpy2ApiBridge.Name)) -Destination $rpy2ApiBridge.FullName -Force
$kitMetadataRoot = Join-Path $appDir "r-integration-kit"
New-Item -ItemType Directory -Force -Path $kitMetadataRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $rIntegrationKitRoot "manifest.json") -Destination (Join-Path $kitMetadataRoot "manifest.json")
Copy-Item -LiteralPath (Join-Path $rIntegrationKitRoot "sources.json") -Destination (Join-Path $kitMetadataRoot "sources.json")
Copy-Item -LiteralPath (Join-Path $rIntegrationKitRoot "native-dependencies.json") -Destination (Join-Path $kitMetadataRoot "native-dependencies.json")
& $PythonExe (Join-Path $repoRoot "scripts\r_kit_derivation.py") record-pre-sign `
    --kit $rIntegrationKitRoot --target windows-x64 --app-root $appDir `
    --api-bridge $rpy2ApiBridge.FullName --r-shared-library $rDll `
    --output (Join-Path $kitMetadataRoot "derivation.json")
if ($LASTEXITCODE -ne 0) { throw "Windows R kit derivation recording failed." }
& $PythonExe (Join-Path $repoRoot "scripts\r_kit_derivation.py") finalize `
    --app-root $appDir --api-bridge $rpy2ApiBridge.FullName --r-shared-library $rDll `
    --derivation (Join-Path $kitMetadataRoot "derivation.json")
if ($LASTEXITCODE -ne 0) { throw "Windows R kit derivation finalization failed." }

@'
@echo off
set APP_DIR=%~dp0
set RPY2_CFFI_MODE=API
start "" "%APP_DIR%RCMetaStudio.exe" "%APP_DIR%sample_projects\amino.rcms"
'@ | Set-Content -Path (Join-Path $appDir "LaunchRCMetaStudio.bat") -Encoding ASCII

Assert-AppLayout -Root $appDir
$runtimeProbePath = Invoke-PackagedRuntimeProbe -Root $appDir
$deploymentManifestPath = Join-Path $appDir "qualification\deployment-manifest.json"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $deploymentManifestPath) | Out-Null
$rIntegrationKitManifestPath = Join-Path $appDir "qualification\r-integration-kit-manifest.json"
Copy-Item -LiteralPath (Join-Path $rIntegrationKitRoot "manifest.json") -Destination $rIntegrationKitManifestPath
$pythonVersion = (& $PythonExe -c "import platform; print(platform.python_version())").Trim()
$pyQtVersion = (& $PythonExe -c "import importlib.metadata as m; print(m.version('PyQt6'))").Trim()
$qtVersion = (& $PythonExe -c "import importlib.metadata as m; print(m.version('PyQt6-Qt6'))").Trim()
$sipVersion = (& $PythonExe -c "import importlib.metadata as m; print(m.version('PyQt6-sip'))").Trim()
$sipRuntimeVersion = (& $PythonExe -c "from PyQt6 import sip; print(sip.SIP_VERSION_STR)").Trim()
$rpy2Version = (& $PythonExe -c "import importlib.metadata as m; print(m.version('rpy2'))").Trim()
$rVersion = (& (Join-Path $resolvedRRuntimeRoot "bin\Rscript.exe") -e "cat(as.character(getRversion()))").Trim()
Write-Step "Inspecting coherent Windows x64 deployment"
& $PythonExe scripts\inspect_windows_deployment.py inspect `
    --app-root $appDir --output $deploymentManifestPath --source-commit $sourceCommit `
    --runtime-probe $runtimeProbePath --locked-qt-root (Join-Path $pyQtRoot "Qt6") `
    --python-version $pythonVersion --pyqt6-version $pyQtVersion --qt-version $qtVersion `
    --sip-version $sipVersion --sip-runtime-version $sipRuntimeVersion `
    --r-version $rVersion --rpy2-version $rpy2Version `
    --pyinstaller-version $requiredPyInstallerVersion
if ($LASTEXITCODE -ne 0) { throw "Windows deployment inspection failed." }
if (-not $SkipSmoke) {
    Write-Step "Running packaged Windows smoke checks"
    Invoke-PackagedAppSmokeTest -Root $appDir
    Invoke-PackagedWizardLayoutSmokeTest -Root $appDir
}
if ($CaptureAdaptiveLayoutEvidence) {
    Write-Step "Capturing controlled native Windows adaptive-layout evidence"
    Invoke-PackagedAdaptiveLayoutEvidence -Root $appDir
}
Compress-AppDirectory -SourceDirectory $appDir -ArchiveStagingRoot $archiveStagingRoot -ArchiveRootDirectory $archiveRootDir -DestinationPath $zipPath
Assert-ZipLayout -Path $zipPath -ArchiveRootName $archiveRootName
if (-not $SkipSmoke) {
    & $PythonExe scripts\inspect_windows_deployment.py archive `
        --archive $zipPath --archive-root-name $archiveRootName `
        --deployment-manifest $deploymentManifestPath --runtime-probe $runtimeProbePath `
        --smoke-evidence (Join-Path $appDir "qualification\packaged-smoke.json") `
        --smoke-log (Join-Path $appDir "qualification\packaged-smoke.log") `
        --output $archiveInspectionPath
    if ($LASTEXITCODE -ne 0) { throw "Final Windows ZIP inspection failed." }
    & $PythonExe scripts\inspect_windows_deployment.py evidence `
        --archive $zipPath --deployment-manifest $deploymentManifestPath `
        --smoke-evidence (Join-Path $appDir "qualification\packaged-smoke.json") `
        --smoke-log (Join-Path $appDir "qualification\packaged-smoke.log") `
        --runtime-probe $runtimeProbePath --archive-inspection $archiveInspectionPath `
        --output $qualificationEvidencePath
    if ($LASTEXITCODE -ne 0) { throw "Windows package qualification evidence generation failed." }
}
Write-Host "Created $zipPath"
