[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Package,
    [Parameter(Mandatory = $true)][string]$Output,
    [string]$CertificateThumbprint = $env:RCMS_SIGNING_CERTIFICATE_THUMBPRINT,
    [string]$TimestampUrl = "http://timestamp.acs.microsoft.com"
)

$ErrorActionPreference = "Stop"
if (-not $CertificateThumbprint) { throw "RCMS_SIGNING_CERTIFICATE_THUMBPRINT is required." }
$signtool = (Get-Command signtool.exe -ErrorAction Stop).Source
$workspace = Join-Path ([IO.Path]::GetTempPath()) ("rcms-sign-" + [guid]::NewGuid())
try {
    Expand-Archive -LiteralPath $Package -DestinationPath $workspace
    $signables = Get-ChildItem -LiteralPath $workspace -Recurse -File | Where-Object { $_.Extension -in '.exe', '.dll' }
    if (-not $signables) { throw "No Authenticode-signable files found in package." }
    foreach ($file in $signables) {
        & $signtool sign /sha1 $CertificateThumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 $file.FullName
        if ($LASTEXITCODE -ne 0) { throw "Signing failed: $($file.FullName)" }
    }
    foreach ($file in $signables) {
        & $signtool verify /pa /all /v $file.FullName
        if ($LASTEXITCODE -ne 0) { throw "Signature verification failed: $($file.FullName)" }
    }
    if (Test-Path -LiteralPath $Output) { Remove-Item -LiteralPath $Output -Force }
    Compress-Archive -Path (Join-Path $workspace '*') -DestinationPath $Output -CompressionLevel Optimal
} finally {
    if (Test-Path -LiteralPath $workspace) { Remove-Item -LiteralPath $workspace -Recurse -Force }
}
