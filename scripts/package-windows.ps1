param(
    [switch]$RecreateVenv,
    [switch]$SkipClean,
    [switch]$SkipSmoke,
    [switch]$CaptureAdaptiveLayoutEvidence,
    [switch]$RunRegistryStateRoundTripTest
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = Join-Path $repoRoot ".venv"
$rDownloadCache = Join-Path $repoRoot "artifacts\download-cache\windows-x64"
$rInstaller = Join-Path $rDownloadCache "R-4.6.1-win.exe"
$rStage = Join-Path $repoRoot "build\windows-package\staged-R-4.6.1"
$rUrl = "https://cloud.r-project.org/bin/windows/base/R-4.6.1-win.exe"
$rSha256 = "C5424C40CD70EF85765A55D2FF96BB602B5F30ED536938FF004F14DB5DB3C2DF"
$rSigner = "CN=Martyn Plummer, O=Martyn Plummer, S=West Midlands, C=GB"
$rThumbprint = "F356FC6CD245D722F4A82697473DA5995CB42975"

function Write-Step { param([string]$Message) Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message) }

function Invoke-DownloadWithRetry {
    param(
        [string]$Uri,
        [string]$PartialPath,
        [int]$MaxAttempts = 3,
        [int]$RetryDelaySeconds = 2,
        [scriptblock]$DownloadOperation = { param($RequestUri, $Destination) Invoke-WebRequest -Uri $RequestUri -OutFile $Destination -ErrorAction Stop },
        [scriptblock]$SleepOperation = { param($Seconds) Start-Sleep -Seconds $Seconds }
    )
    $lastError = $null
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        if (Test-Path -LiteralPath $PartialPath) { Remove-Item -LiteralPath $PartialPath -Force }
        try {
            & $DownloadOperation $Uri $PartialPath
            return
        }
        catch {
            $lastError = $_
            if (Test-Path -LiteralPath $PartialPath) { Remove-Item -LiteralPath $PartialPath -Force }
            if ($attempt -lt $MaxAttempts) { & $SleepOperation $RetryDelaySeconds }
        }
    }
    throw "Could not download '$Uri' after $MaxAttempts attempts: $($lastError.Exception.Message)"
}

function Assert-WindowsNativePrerequisites {
    if ($env:PROCESSOR_ARCHITECTURE -ne "AMD64") { throw "Windows x64 packaging requires an AMD64 host; found '$env:PROCESSOR_ARCHITECTURE'." }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw "Windows packaging requires uv. Install it from https://docs.astral.sh/uv/ before running this command." }
    $rtoolsBin = "C:\rtools45\x86_64-w64-mingw32.static.posix\bin"
    if ((Test-Path (Join-Path $rtoolsBin "gcc.exe")) -and (Test-Path (Join-Path $rtoolsBin "g++.exe"))) {
        Write-Step "Selecting the Rtools GCC C99 compiler required by the staged R headers"
        $env:Path = "$rtoolsBin;$env:Path"
        $env:CC = "gcc"
        $env:CXX = "g++"
        $env:LDSHARED = "gcc -shared"
        return
    }
    throw "API-mode rpy2 uses --compiler=mingw32 and requires the x64 Rtools 4.5 GCC/G++ toolchain at '$rtoolsBin'. Install Rtools 4.5, then rerun this command."
}

function Get-CurrentUserRegistryKey {
    param([string]$Path, [switch]$Writable)
    if ($Path -notmatch '^HKCU\\(.+)$') { throw "Expected an HKCU registry path, got '$Path'." }
    try {
        return [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($Matches[1], [bool]$Writable)
    }
    catch {
        throw "Could not determine whether current-user registry key '$Path' exists: $($_.Exception.Message)"
    }
}

function Export-RegistryKeyTree {
    param([Microsoft.Win32.RegistryKey]$Key)
    return [pscustomobject]@{
        Values = @($Key.GetValueNames() | Sort-Object | ForEach-Object {
            [pscustomobject]@{ Name = $_; Value = $Key.GetValue($_, $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames); Kind = [int]$Key.GetValueKind($_) }
        })
        SubKeys = @($Key.GetSubKeyNames() | Sort-Object | ForEach-Object {
            $child = $Key.OpenSubKey($_, $false)
            try { [pscustomobject]@{ Name = $_; Tree = Export-RegistryKeyTree -Key $child } }
            finally { $child.Dispose() }
        })
    }
}

function Import-RegistryKeyTree {
    param([Microsoft.Win32.RegistryKey]$Parent, [string]$Name, [object]$Tree)
    $key = $Parent.CreateSubKey($Name, $true)
    try {
        foreach ($value in @($Tree.Values | Where-Object { $_ -isnot [string] })) {
            $kind = [Microsoft.Win32.RegistryValueKind]$value.Kind
            if ($kind -eq [Microsoft.Win32.RegistryValueKind]::Binary) { $restoredValue = [byte[]]@($value.Value) }
            elseif ($kind -eq [Microsoft.Win32.RegistryValueKind]::MultiString) { $restoredValue = [string[]]@($value.Value) }
            elseif ($kind -eq [Microsoft.Win32.RegistryValueKind]::DWord) { $restoredValue = [int]$value.Value }
            elseif ($kind -eq [Microsoft.Win32.RegistryValueKind]::QWord) { $restoredValue = [long]$value.Value }
            else { $restoredValue = $value.Value }
            try { $key.SetValue($value.Name, $restoredValue, $kind) }
            catch { throw "Could not restore registry value '$($value.Name)' of kind '$kind' (type '$($restoredValue.GetType().FullName)'): $($_.Exception.Message)" }
        }
        foreach ($child in @($Tree.SubKeys | Where-Object { $_ -isnot [string] })) { Import-RegistryKeyTree -Parent $key -Name $child.Name -Tree $child.Tree }
    }
    finally { $key.Dispose() }
}

function Test-RegistryKeyTree {
    param([Microsoft.Win32.RegistryKey]$Key, [object]$Tree)
    $expectedValueRecords = @($Tree.Values | Where-Object { $_ -isnot [string] })
    $expectedChildren = @($Tree.SubKeys | Where-Object { $_ -isnot [string] })
    $actualValues = @($Key.GetValueNames() | Sort-Object)
    $expectedValues = @($expectedValueRecords | ForEach-Object Name | Sort-Object)
    if ((@($actualValues) -join "`0") -ne (@($expectedValues) -join "`0")) { return $false }
    foreach ($value in $expectedValueRecords) {
        $actualValue = $Key.GetValue($value.Name, $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
        if ([int]$Key.GetValueKind($value.Name) -ne [int]$value.Kind -or -not (Test-RegistryValueEqual -Expected $value.Value -Actual $actualValue -Kind ([int]$value.Kind))) { return $false }
    }
    foreach ($child in $expectedChildren) {
        $actual = $Key.OpenSubKey($child.Name, $false)
        if ($null -eq $actual) { return $false }
        try { if (-not (Test-RegistryKeyTree -Key $actual -Tree $child.Tree)) { return $false } }
        finally { $actual.Dispose() }
    }
    return $true
}

function Test-RegistryValueEqual {
    param([object]$Expected, [object]$Actual, [int]$Kind)
    if ($Kind -eq [int][Microsoft.Win32.RegistryValueKind]::Binary) {
        $expectedBytes = [byte[]]@($Expected)
        return $Actual -is [byte[]] -and $expectedBytes.Length -eq $Actual.Length -and [Linq.Enumerable]::SequenceEqual($expectedBytes, [byte[]]$Actual)
    }
    if ($Kind -eq [int][Microsoft.Win32.RegistryValueKind]::MultiString) {
        $expectedStrings = [string[]]@($Expected)
        return $Actual -is [string[]] -and $expectedStrings.Length -eq $Actual.Length -and [Linq.Enumerable]::SequenceEqual($expectedStrings, [string[]]$Actual)
    }
    return $Expected -is $Actual.GetType() -and $Expected -ceq $Actual
}

function Invoke-RegistryStateRoundTripTest {
    $leaf = "CodexRegistryRoundTrip-$([Guid]::NewGuid().ToString('N'))"
    $parent = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey("Software", $true)
    $root = $null
    $backupRoot = Join-Path ([IO.Path]::GetTempPath()) "RC MetaStudio registry backup $leaf"
    try {
        $root = $parent.CreateSubKey($leaf, $true)
        $root.SetValue("", "default", [Microsoft.Win32.RegistryValueKind]::String)
        $root.SetValue("binary", [byte[]](0, 1, 255), [Microsoft.Win32.RegistryValueKind]::Binary)
        $root.SetValue("multi", [string[]]("one", "two words", ""), [Microsoft.Win32.RegistryValueKind]::MultiString)
        $root.SetValue("expand", "%USERPROFILE%\RC MetaStudio", [Microsoft.Win32.RegistryValueKind]::ExpandString)
        $root.SetValue("dword", [int]42, [Microsoft.Win32.RegistryValueKind]::DWord)
        $root.SetValue("qword", [long]4294967297, [Microsoft.Win32.RegistryValueKind]::QWord)
        $nested = $root.CreateSubKey("nested", $true); $nested.SetValue("value", "nested", [Microsoft.Win32.RegistryValueKind]::String); $nested.Dispose()
        $tree = Export-RegistryKeyTree -Key $root
        New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
        $backup = Join-Path $backupRoot "state with spaces.clixml"
        $tree | Export-Clixml -LiteralPath $backup
        $tree = Import-Clixml -LiteralPath $backup
        $root.Dispose(); $root = $null; $parent.DeleteSubKeyTree($leaf, $false)
        Import-RegistryKeyTree -Parent $parent -Name $leaf -Tree $tree
        $root = $parent.OpenSubKey($leaf, $true)
        Remove-RegistryTreeExtras -Key $root -Tree $tree
        if (-not (Test-RegistryKeyTree -Key $root -Tree $tree)) { throw "Registry round-trip test did not preserve typed values." }
        Write-Host "Registry round-trip test passed."
    }
    finally {
        if ($null -ne $root) { $root.Dispose() }
        if ($null -ne $parent) { try { $parent.DeleteSubKeyTree($leaf, $false) } catch {} $parent.Dispose() }
        if (Test-Path -LiteralPath $backupRoot) { Remove-Item -LiteralPath $backupRoot -Recurse -Force }
    }
}

function Remove-RegistryTreeExtras {
    param([Microsoft.Win32.RegistryKey]$Key, [object]$Tree)
    $expectedValueRecords = @($Tree.Values | Where-Object { $_ -isnot [string] })
    $expectedChildren = @($Tree.SubKeys | Where-Object { $_ -isnot [string] })
    $expectedValues = @($expectedValueRecords | ForEach-Object Name)
    foreach ($name in @($Key.GetValueNames())) {
        if ($name -notin $expectedValues) { $Key.DeleteValue($name, $false) }
    }
    $expectedChildNames = @($expectedChildren | ForEach-Object Name)
    foreach ($name in @($Key.GetSubKeyNames())) {
        if ($name -notin $expectedChildNames) { $Key.DeleteSubKeyTree($name, $false) }
    }
    foreach ($child in $expectedChildren) {
        $actual = $Key.OpenSubKey($child.Name, $true)
        try { Remove-RegistryTreeExtras -Key $actual -Tree $child.Tree }
        finally { $actual.Dispose() }
    }
}

function Save-CurrentUserRInstallerState {
    param([string]$BackupRoot)
    New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
    $keys = @(
        @{ Name = "r-core"; Path = "HKCU\Software\R-core" },
        @{ Name = "uninstall"; Path = "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\R for Windows 4.6.1_is1" }
    )
    $snapshots = @()
    foreach ($key in $keys) {
        $backupPath = Join-Path $BackupRoot ("{0}.clixml" -f $key.Name)
        $registryKey = Get-CurrentUserRegistryKey -Path $key.Path
        $present = $null -ne $registryKey
        $tree = $null
        if ($present) {
            try { $tree = Export-RegistryKeyTree -Key $registryKey }
            finally { $registryKey.Dispose() }
            $tree | Export-Clixml -LiteralPath $backupPath
            $tree = Import-Clixml -LiteralPath $backupPath
            if ($null -eq $tree -or -not (Test-Path -LiteralPath $backupPath)) { throw "Could not create a usable backup of '$($key.Path)' before installation." }
        }
        $snapshots += @{ Path = $key.Path; BackupPath = $backupPath; Present = $present; Tree = $tree }
    }
    return $snapshots
}

function Restore-CurrentUserRInstallerState {
    param([object[]]$Snapshots)
    foreach ($snapshot in $Snapshots) {
        if ($snapshot.Path -notmatch '^HKCU\\(.+)\\([^\\]+)$') { throw "Cannot restore unsupported registry path '$($snapshot.Path)'." }
        $parent = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($Matches[1], $true)
        if ($null -eq $parent) { throw "Cannot open parent registry key for '$($snapshot.Path)'." }
        $leaf = $Matches[2]
        try {
            $existing = $parent.OpenSubKey($leaf, $false)
            if ($null -ne $existing) { $existing.Dispose(); $parent.DeleteSubKeyTree($leaf, $false) }
        }
        finally { $parent.Dispose() }
        if ($snapshot.Present) {
            if (-not (Test-Path -LiteralPath $snapshot.BackupPath)) { throw "Cannot restore current-user R installer state: backup '$($snapshot.BackupPath)' is missing." }
            $tree = Import-Clixml -LiteralPath $snapshot.BackupPath
            $parent = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($Matches[1], $true)
            try {
                Import-RegistryKeyTree -Parent $parent -Name $leaf -Tree $tree
                $restoredWritable = $parent.OpenSubKey($leaf, $true)
                try { Remove-RegistryTreeExtras -Key $restoredWritable -Tree $tree }
                finally { $restoredWritable.Dispose() }
            }
            finally { $parent.Dispose() }
            $restored = Get-CurrentUserRegistryKey -Path $snapshot.Path
            try { if ($null -eq $restored -or -not (Test-RegistryKeyTree -Key $restored -Tree $tree)) { throw "Current-user R installer state restoration did not recreate '$($snapshot.Path)' exactly." } }
            finally { if ($null -ne $restored) { $restored.Dispose() } }
        }
        else {
            $remaining = Get-CurrentUserRegistryKey -Path $snapshot.Path
            if ($null -ne $remaining) { $remaining.Dispose(); throw "Temporary current-user R installer state remains at '$($snapshot.Path)'." }
        }
    }
}

function Stage-AuthenticatedOfficialR {
    New-Item -ItemType Directory -Force -Path $rDownloadCache | Out-Null
    $partialInstaller = "$rInstaller.partial"
    if (Test-Path $partialInstaller) { Remove-Item -LiteralPath $partialInstaller -Force }
    $cachedHash = if (Test-Path $rInstaller) { (Get-FileHash -Algorithm SHA256 -LiteralPath $rInstaller).Hash.ToUpperInvariant() } else { $null }
    if ($cachedHash -ne $rSha256) {
        if (Test-Path $rInstaller) { Remove-Item -LiteralPath $rInstaller -Force }
        Write-Step "Downloading official R 4.6.1 into the immutable download cache"
        Invoke-DownloadWithRetry -Uri $rUrl -PartialPath $partialInstaller
        $partialHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $partialInstaller).Hash.ToUpperInvariant()
        if ($partialHash -ne $rSha256) { throw "Official R download hash mismatch; partial download was not promoted into the cache." }
        Move-Item -LiteralPath $partialInstaller -Destination $rInstaller
    }
    $signature = Get-AuthenticodeSignature -FilePath $rInstaller
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $rInstaller).Hash.ToUpperInvariant()
    if ($signature.Status -ne "Valid" -or $signature.SignerCertificate.Subject -ne $rSigner -or $signature.SignerCertificate.Thumbprint -ne $rThumbprint -or -not $signature.TimeStamperCertificate -or $hash -ne $rSha256) {
        throw "Official R authentication failed (status=$($signature.Status), sha256=$hash). Remove '$rInstaller' and retry; do not use an unverified R runtime."
    }
    if (Test-Path $rStage) { Remove-Item -LiteralPath $rStage -Recurse -Force }
    Write-Step "Staging authenticated official R privately for this build"
    # R 4.6.1 documents /CURRENTUSER for non-elevated installation and /SP-
    # for suppressing Setup's initial consent prompt.  Keep all installed
    # output (including the installer log) under the disposable repository
    # staging root; never touch Program Files or a machine-wide R install.
    $installerLog = "$rStage-installer.log"
    $installerArgs = @(
        "/CURRENTUSER",
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/SP-",
        "/NORESTART",
        ('/DIR="{0}"' -f $rStage),
        ('/LOG="{0}"' -f $installerLog)
    )
    $registrySnapshots = Save-CurrentUserRInstallerState -BackupRoot "$rStage.registry-backup"
    try {
        $process = Start-Process -FilePath $rInstaller -ArgumentList $installerArgs -Wait -PassThru
        if ($process.ExitCode -ne 0 -or -not (Test-Path (Join-Path $rStage "bin\Rscript.exe"))) { throw "Official R installer failed with exit code $($process.ExitCode)." }
    }
    finally {
        Restore-CurrentUserRInstallerState -Snapshots $registrySnapshots
    }
    return $rStage
}

Push-Location $repoRoot
try {
    if ($RunRegistryStateRoundTripTest) { Invoke-RegistryStateRoundTripTest; exit 0 }
    Assert-WindowsNativePrerequisites
    if ($RecreateVenv -and (Test-Path $venvRoot)) { Remove-Item -LiteralPath $venvRoot -Recurse -Force }
    $rHome = Stage-AuthenticatedOfficialR
    Write-Step "Building, inspecting, smoking, and archiving the native Windows package"
    $buildArgs = @{ RRuntimeRoot = $rHome }
    if ($SkipClean) { $buildArgs.SkipClean = $true }
    if ($SkipSmoke) { $buildArgs.SkipSmoke = $true }
    if ($CaptureAdaptiveLayoutEvidence) { $buildArgs.CaptureAdaptiveLayoutEvidence = $true }
    & (Join-Path $repoRoot "scripts\build-windows-package.ps1") @buildArgs
    if ($LASTEXITCODE -ne 0) { throw "Windows package build failed." }
    Write-Step "Windows package complete; the authoritative version determines its artifact name."
}
finally { Pop-Location }
