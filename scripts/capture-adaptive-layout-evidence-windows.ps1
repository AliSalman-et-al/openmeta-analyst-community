[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Package,
    [string]$OutputRoot = "artifacts\controlled-layout-evidence\windows-x64"
)
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$packagePath = (Resolve-Path -LiteralPath $Package).ProviderPath
$output = [IO.Path]::GetFullPath((Join-Path $repoRoot $OutputRoot))
$workspace = Join-Path $env:TEMP ("rcms-layout-evidence-" + [guid]::NewGuid())
try {
    Expand-Archive -LiteralPath $packagePath -DestinationPath $workspace
    $exe = Get-ChildItem -LiteralPath $workspace -Recurse -Filter RCMetaStudio.exe | Select-Object -First 1
    $sample = Get-ChildItem -LiteralPath $workspace -Recurse -Filter amino.rcms | Select-Object -First 1
    if (-not $exe -or -not $sample) { throw "Package does not contain RCMetaStudio.exe and amino.rcms." }
    $plugin = & $exe.FullName --automation-native-smoke $sample.FullName
    if ($LASTEXITCODE -ne 0) { throw "Controlled-host native preflight failed." }
    foreach ($scale in @(@{Value="1.0"; Name="scale-100"}, @{Value="1.5"; Name="scale-150"})) {
        $target = Join-Path $output $scale.Name
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue
        $env:QT_SCALE_FACTOR = $scale.Value
        $env:RCMS_REQUIRE_IN_PROCESS_RPY2 = "1"
        & $exe.FullName --automation-adaptive-layout-evidence $target $sample.FullName
        if ($LASTEXITCODE -ne 0) { throw "Native evidence capture failed at scale $($scale.Value)." }
        uv run python scripts\validate_adaptive_layout_evidence.py --root $target --platform-plugin windows --scale-factor $scale.Value
        if ($LASTEXITCODE -ne 0) { throw "Native evidence validation failed at scale $($scale.Value)." }
    }
    $hash = (Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath (Join-Path $output "PACKAGE_SHA256") -Value "$hash  $([IO.Path]::GetFileName($packagePath))" -Encoding ASCII
    Write-Host "Controlled Windows evidence captured for package SHA-256 $hash at $output"
} finally {
    Remove-Item Env:\QT_SCALE_FACTOR -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $workspace) { Remove-Item -LiteralPath $workspace -Recurse -Force }
}
