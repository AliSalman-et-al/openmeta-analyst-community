param(
    [string]$PackageScript = (Join-Path (Split-Path -Parent $PSScriptRoot) "scripts\package-windows.ps1")
)

$ErrorActionPreference = "Stop"
$tokens = $null; $parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path -LiteralPath $PackageScript), [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw "Could not parse package download retry implementation." }
$function = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq "Invoke-DownloadWithRetry" }, $true)
if ($null -eq $function) { throw "Invoke-DownloadWithRetry was not found." }
. ([scriptblock]::Create($function.Extent.Text))

$root = Join-Path ([IO.Path]::GetTempPath()) ("rcms-download-retry-" + [guid]::NewGuid())
New-Item -ItemType Directory -Force -Path $root | Out-Null
try {
    $partial = Join-Path $root "installer.partial"; $attempts = 0; $sleeps = @()
    $operation = {
        param($uri, $destination)
        $script:attempts++
        if (Test-Path -LiteralPath $destination) { throw "stale partial reached attempt $script:attempts" }
        "partial-$script:attempts" | Set-Content -LiteralPath $destination -NoNewline
        if ($script:attempts -lt 3) { throw "injected failure $script:attempts" }
        "complete" | Set-Content -LiteralPath $destination -NoNewline
    }
    $sleep = { param($seconds) $script:sleeps += $seconds }
    Invoke-DownloadWithRetry -Uri "https://example.invalid/R.exe" -PartialPath $partial -DownloadOperation $operation -SleepOperation $sleep
    if ($attempts -ne 3 -or @($sleeps).Count -ne 2 -or (Get-Content -Raw -LiteralPath $partial) -ne "complete") { throw "Retry success boundary did not preserve exactly three attempts, two sleeps, and final bytes." }

    Remove-Item -LiteralPath $partial -Force
    $attempts = 0; $sleeps = @(); $failed = $false
    $terminal = { param($uri, $destination) $script:attempts++; "partial" | Set-Content -LiteralPath $destination -NoNewline; throw "terminal injected failure" }
    try { Invoke-DownloadWithRetry -Uri "https://example.invalid/R.exe" -PartialPath $partial -DownloadOperation $terminal -SleepOperation $sleep }
    catch { if ($_.Exception.Message -notmatch "after 3 attempts" -or $_.Exception.Message -notmatch "terminal injected failure") { throw }; $failed = $true }
    if (-not $failed -or $attempts -ne 3 -or @($sleeps).Count -ne 2 -or (Test-Path -LiteralPath $partial)) { throw "Terminal retry failure did not clean partial bytes or preserve the actionable error." }
}
finally { Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue }
Write-Output "Package download retry self-test passed."
