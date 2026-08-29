param(
    [Parameter(Mandatory=$true)][string]$RRuntimeRoot,
    [Parameter(Mandatory=$true)][string]$PythonExe,
    [Parameter(Mandatory=$true)][string]$OfficialRArtifact,
    [Parameter(Mandatory=$true)][string]$OfficialRUrl,
    [Parameter(Mandatory=$true)][string]$OfficialRSignatureIdentity,
    [Parameter(Mandatory=$true)][string]$OfficialRSignerThumbprint,
    [Parameter(Mandatory=$true)][string]$OfficialRSignatureStatus,
    [Parameter(Mandatory=$true)][switch]$OfficialRTimestamped,
    [Parameter(Mandatory=$true)][string]$Rpy2Sdist,
    [Parameter(Mandatory=$true)][string]$Rpy2SdistUrl,
    [Parameter(Mandatory=$true)][string]$Rpy2RinterfaceSdist,
    [Parameter(Mandatory=$true)][string]$Rpy2RinterfaceSdistUrl,
    [Parameter(Mandatory=$true)][string]$Rpy2RobjectsSdist,
    [Parameter(Mandatory=$true)][string]$Rpy2RobjectsSdistUrl,
    [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference = "Stop"
function Invoke-NativeLogged {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [Parameter(Mandatory=$true)][object[]]$ArgumentList,
        [Parameter(Mandatory=$true)][string]$LogPath,
        [Parameter(Mandatory=$true)][string]$FailureMessage
    )
    $previousPreference = $ErrorActionPreference
    $exitCode = $null
    try {
        # Windows PowerShell 5 promotes native stderr records to terminating errors
        # under Stop. Preserve both streams, then make the process exit code decisive.
        $ErrorActionPreference = "Continue"
        & $FilePath @ArgumentList *>&1 | Tee-Object -FilePath $LogPath
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($null -eq $exitCode -or $exitCode -ne 0) {
        throw "$FailureMessage (exit code: $exitCode; log: $LogPath)"
    }
}
$repo = Split-Path -Parent $PSScriptRoot
$work = Join-Path $repo "build\r-kit-producer\windows-x64"
$stage = Join-Path $work "R"
$archives = Join-Path $work "ppm-archives"
$logs = Join-Path $work "logs"
$provenance = Join-Path $work "provenance.json"
if (-not $OfficialRTimestamped) { throw "Official R installer provenance must include an Authenticode timestamp" }
Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $stage,$archives,$logs | Out-Null
Copy-Item -Path (Join-Path $RRuntimeRoot "*") -Destination $stage -Recurse -Force
$rscript = Join-Path $stage "bin\Rscript.exe"
$library = Join-Path $stage "library"
$env:R_HOME = $stage
$env:R_LIBS = $library
$env:R_LIBS_USER = $library
$env:RCMS_CRAN_REPO = "https://packagemanager.posit.co/cran/2026-07-16"
$env:RCMS_R_PACKAGE_ARCHIVE_DIR = $archives
$env:RCMS_HSROC_ARCHIVE = Join-Path $work "HSROC_2.1.9.tar.gz"
Invoke-NativeLogged -FilePath $rscript -ArgumentList @((Join-Path $repo "scripts\install-r-deps.R")) -LogPath (Join-Path $logs "r-packages.log") -FailureMessage "R binary/source dependency production failed"
$commit = (& git -C $repo rev-parse HEAD).Trim()
$rcmetarUrl = "https://github.com/AliSalman-et-al/rc-metastudio/archive/$commit.tar.gz"
$rcmetarArchive = Join-Path $work "rc-metastudio-$commit.tar.gz"
Invoke-WebRequest -Uri $rcmetarUrl -OutFile $rcmetarArchive
$rcmetarSource = Join-Path $work "rcmetar-source"
New-Item -ItemType Directory -Force -Path $rcmetarSource | Out-Null
tar -xf $rcmetarArchive -C $rcmetarSource
$rcmetarPackage = Get-ChildItem -LiteralPath $rcmetarSource -Directory | ForEach-Object { Join-Path $_.FullName "r\RCMetaR" } | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $rcmetarPackage) { throw "Downloaded RCMetaR source archive lacks r/RCMetaR" }
Invoke-NativeLogged -FilePath $rscript -ArgumentList @((Join-Path $repo "scripts\install-rcmetar-source.R"), $rcmetarPackage, $library) -LogPath (Join-Path $logs "rcmetar.log") -FailureMessage "RCMetaR source production failed"
$env:RPY2_CFFI_MODE = "API"
Invoke-NativeLogged -FilePath "uv" -ArgumentList @("pip", "install", "--python", $PythonExe, "--reinstall", $Rpy2RinterfaceSdist) -LogPath (Join-Path $logs "rpy2.log") -FailureMessage "rpy2 API bridge production failed"
$platlib = (& $PythonExe -c "import sysconfig; print(sysconfig.get_paths()['platlib'])").Trim()
$bridge = Get-ChildItem -LiteralPath $platlib -Recurse -File -Filter "_rinterface_cffi_api*.pyd" | Select-Object -First 1
if ($null -eq $bridge) { throw "rpy2 API bridge was not built" }
& $PythonExe (Join-Path $repo "scripts\index_r_binary_archives.py") --archives $archives --contrib-url "https://packagemanager.posit.co/cran/2026-07-16/bin/windows/contrib/4.6" --package-type win.binary --library $library --output (Join-Path $work "ppm-index.json")
& $PythonExe (Join-Path $repo "scripts\create_r_kit_provenance.py") --target windows-x64 --official-r-artifact $OfficialRArtifact --official-r-url $OfficialRUrl --official-r-signature-identity $OfficialRSignatureIdentity --official-r-signer-thumbprint $OfficialRSignerThumbprint --official-r-signature-status $OfficialRSignatureStatus --official-r-timestamped --official-r-artifact-type installer --ppm-index (Join-Path $work "ppm-index.json") --ppm-archive-root $archives --hsroc-archive $env:RCMS_HSROC_ARCHIVE --hsroc-url "https://cran.r-project.org/src/contrib/Archive/HSROC/HSROC_2.1.9.tar.gz" --hsroc-build-log (Join-Path $logs "r-packages.log") --rcmetar-archive $rcmetarArchive --rcmetar-url $rcmetarUrl --rcmetar-build-log (Join-Path $logs "rcmetar.log") --rpy2-sdist $Rpy2Sdist --rpy2-sdist-url $Rpy2SdistUrl --rpy2-rinterface-sdist $Rpy2RinterfaceSdist --rpy2-rinterface-sdist-url $Rpy2RinterfaceSdistUrl --rpy2-robjects-sdist $Rpy2RobjectsSdist --rpy2-robjects-sdist-url $Rpy2RobjectsSdistUrl --rpy2-build-log (Join-Path $logs "rpy2.log") --rpy2-api-bridge $bridge.FullName --toolchain "R 4.6.1; Python 3.11.9; uv; MSVC x64" --output $provenance
$sourcePayload = Join-Path $work "source-payload"
New-Item -ItemType Directory -Force -Path $sourcePayload | Out-Null
Copy-Item -LiteralPath $env:RCMS_HSROC_ARCHIVE,$rcmetarArchive,$Rpy2Sdist,$Rpy2RinterfaceSdist,$Rpy2RobjectsSdist -Destination $sourcePayload
$lockHash = (Get-FileHash -Algorithm SHA256 (Join-Path $repo "config\r-dependencies.json")).Hash.ToLowerInvariant()
$uvLock = Join-Path $repo "uv.lock"
$uvLockHash = (Get-FileHash -Algorithm SHA256 $uvLock).Hash.ToLowerInvariant()
$uvCache = (& uv cache dir).Trim()
& $PythonExe (Join-Path $repo "scripts\r_integration_kit.py") build --target windows-x64 --runtime $stage --library $library --api-bridge $bridge.FullName --output $Output --provenance-manifest $provenance --package-lock-sha256 $lockHash --source-commit $commit --uv-cache $uvCache --uv-lock $uvLock --uv-lock-sha256 $uvLockHash --source-payload $sourcePayload
if ($LASTEXITCODE -ne 0) { throw "Windows R integration kit production failed" }
