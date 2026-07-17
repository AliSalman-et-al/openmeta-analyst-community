param(
    [string]$BuildScript = (Join-Path (Split-Path -Parent $PSScriptRoot) "scripts\build-windows-package.ps1")
)

$ErrorActionPreference = "Stop"
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    (Resolve-Path -LiteralPath $BuildScript),
    [ref]$tokens,
    [ref]$parseErrors
)
if ($parseErrors.Count -ne 0) {
    throw "Could not parse bounded-process implementation: $($parseErrors.Message -join '; ')"
}
$functionAsts = @{}
foreach ($functionName in @("Stop-BoundedPackageProcessTree", "Invoke-BoundedPackageProcess")) {
    $functionAsts[$functionName] = $ast.Find(
        {
            param($node)
            $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
                $node.Name -eq $functionName
        },
        $true
    )
    if ($null -eq $functionAsts[$functionName]) {
        throw "$functionName was not found in '$BuildScript'."
    }
    . ([scriptblock]::Create($functionAsts[$functionName].Extent.Text))
}

$testRoot = Join-Path ([IO.Path]::GetTempPath()) ("rcms-process-exit-" + [guid]::NewGuid())
New-Item -ItemType Directory -Force -Path $testRoot | Out-Null
try {
    $childScript = Join-Path $testRoot "redirected-child.ps1"
    @'
param([int]$ExitCode, [int]$DelayMilliseconds = 0)
if ($DelayMilliseconds -gt 0) {
    Start-Sleep -Milliseconds $DelayMilliseconds
}
[Console]::Out.WriteLine("stdout-$ExitCode")
[Console]::Error.WriteLine("stderr-$ExitCode")
exit $ExitCode
'@ | Set-Content -LiteralPath $childScript -Encoding UTF8

    $powerShellExe = (Get-Process -Id $PID).Path
    foreach ($expectedExitCode in @(0, 7)) {
        $stdout = Join-Path $testRoot "stdout-$expectedExitCode.log"
        $stderr = Join-Path $testRoot "stderr-$expectedExitCode.log"
        $actualExitCode = Invoke-BoundedPackageProcess `
            -FilePath $powerShellExe `
            -ArgumentList @(
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                ('"{0}"' -f $childScript),
                "-ExitCode",
                $expectedExitCode
            ) `
            -TimeoutSeconds 30 `
            -StandardOutputPath $stdout `
            -StandardErrorPath $stderr
        if ($actualExitCode -isnot [int] -or $actualExitCode -ne $expectedExitCode) {
            throw "Expected exact exit code $expectedExitCode, got '$actualExitCode'."
        }
        if ((Get-Content -Raw -LiteralPath $stdout).Trim() -ne "stdout-$expectedExitCode") {
            throw "Redirected stdout did not complete for exit code $expectedExitCode."
        }
        if ((Get-Content -Raw -LiteralPath $stderr).Trim() -ne "stderr-$expectedExitCode") {
            throw "Redirected stderr did not complete for exit code $expectedExitCode."
        }
    }

    $timeoutStarted = Get-Date
    $timeoutObserved = $false
    try {
        Invoke-BoundedPackageProcess `
            -FilePath $powerShellExe `
            -ArgumentList @(
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                ('"{0}"' -f $childScript),
                "-ExitCode",
                0,
                "-DelayMilliseconds",
                60000
            ) `
            -TimeoutSeconds 1 `
            -StandardOutputPath (Join-Path $testRoot "timeout.stdout.log") `
            -StandardErrorPath (Join-Path $testRoot "timeout.stderr.log") | Out-Null
    }
    catch {
        if ($_.Exception.Message -notmatch "exceeded its 1-second watchdog") {
            throw
        }
        $timeoutObserved = $true
    }
    if (-not $timeoutObserved) {
        throw "Bounded process timeout did not fail closed."
    }
    if (((Get-Date) - $timeoutStarted).TotalSeconds -gt 15) {
        throw "Bounded process timeout cleanup exceeded the self-test limit."
    }

    Add-Type -TypeDefinition @'
using System;

public sealed class RcmsThrowingHandleProcess
{
    public int Id { get { return 4242; } }
    public bool HasExited { get { return false; } }
    public bool Disposed { get; private set; }
    public IntPtr Handle
    {
        get { throw new InvalidOperationException("injected handle acquisition failure"); }
    }
    public bool WaitForExit(int milliseconds) { return true; }
    public void Dispose() { Disposed = true; }
}
'@
    $fakeProcess = [RcmsThrowingHandleProcess]::new()
    $script:exceptionalCleanupProcessId = $null
    function Start-Process {
        param(
            [string]$FilePath,
            [string[]]$ArgumentList,
            [switch]$PassThru,
            [string]$WindowStyle,
            [string]$RedirectStandardOutput,
            [string]$RedirectStandardError
        )
        return $fakeProcess
    }
    function Stop-BoundedPackageProcessTree {
        param([int]$ProcessId)
        $script:exceptionalCleanupProcessId = $ProcessId
    }
    try {
        $handleFailureObserved = $false
        try {
            Invoke-BoundedPackageProcess `
                -FilePath "injected.exe" `
                -ArgumentList @("--injected") `
                -TimeoutSeconds 1 | Out-Null
        }
        catch {
            if ($_.Exception.Message -notmatch "Could not acquire a valid handle") {
                throw
            }
            $handleFailureObserved = $true
        }
        if (-not $handleFailureObserved) {
            throw "Injected handle acquisition failure was not propagated."
        }
        if ($script:exceptionalCleanupProcessId -ne $fakeProcess.Id) {
            throw "Handle acquisition failure did not trigger child cleanup."
        }
        if (-not $fakeProcess.Disposed) {
            throw "Handle acquisition failure did not dispose the process object."
        }
    }
    finally {
        Remove-Item Function:\Start-Process -ErrorAction SilentlyContinue
    }
}
finally {
    Remove-Item -LiteralPath $testRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Output "Bounded package process exit-code self-test passed."
