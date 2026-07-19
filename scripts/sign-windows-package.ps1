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
    $signables = Get-ChildItem -LiteralPath $workspace -Recurse -File | Where-Object { $_.Extension -in '.exe', '.dll', '.pyd' }
    if (-not $signables) { throw "No Authenticode-signable files found in package." }
    foreach ($file in $signables) {
        & $signtool sign /sha1 $CertificateThumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 $file.FullName
        if ($LASTEXITCODE -ne 0) { throw "Signing failed: $($file.FullName)" }
    }
    $derivationPath = Get-ChildItem -LiteralPath $workspace -Recurse -File -Filter derivation.json | Where-Object { $_.Directory.Name -eq 'r-integration-kit' } | Select-Object -First 1
    if (-not $derivationPath) { throw "Signed package lacks its R integration-kit derivation." }
    $appRoot = $derivationPath.Directory.Parent.FullName
    $derivation = Get-Content -Raw -LiteralPath $derivationPath.FullName | ConvertFrom-Json
    $apiBridge = Join-Path $appRoot $derivation.final.api_bridge.path
    $rSharedLibrary = Join-Path $appRoot $derivation.final.r_shared_library.path
    function Get-SignedMemberEvidence([string]$native) {
        $signature = Get-AuthenticodeSignature -LiteralPath $native
        if ($signature.Status -ne 'Valid' -or -not $signature.SignerCertificate -or -not $signature.TimeStamperCertificate) {
            throw "Signing did not produce a valid timestamped signature: $native"
        }
        return [ordered]@{
            path = [IO.Path]::GetRelativePath($appRoot, $native).Replace('\','/')
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $native).Hash.ToLowerInvariant()
            status = $signature.Status.ToString()
            signer_subject = $signature.SignerCertificate.Subject
            signer_thumbprint = $signature.SignerCertificate.Thumbprint.ToLowerInvariant()
            timestamp_subject = $signature.TimeStamperCertificate.Subject
            timestamp_thumbprint = $signature.TimeStamperCertificate.Thumbprint.ToLowerInvariant()
        }
    }
    $signingEvidence = Join-Path $workspace 'windows-r-signing-evidence.json'
    [ordered]@{ schema_version = 1; members = [ordered]@{
        api_bridge = Get-SignedMemberEvidence $apiBridge
        r_shared_library = Get-SignedMemberEvidence $rSharedLibrary
    } } | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 -LiteralPath $signingEvidence
    & python (Join-Path $PSScriptRoot 'r_kit_derivation.py') finalize `
        --app-root $appRoot --api-bridge $apiBridge --r-shared-library $rSharedLibrary `
        --derivation $derivationPath.FullName --signing-evidence $signingEvidence --require-signed
    if ($LASTEXITCODE -ne 0) { throw "Signed Windows R derivation refresh failed." }
    Remove-Item -LiteralPath $signingEvidence -Force
    foreach ($file in $signables) {
        & $signtool verify /pa /all /v $file.FullName
        if ($LASTEXITCODE -ne 0) { throw "Signature verification failed: $($file.FullName)" }
    }
    if (Test-Path -LiteralPath $Output) { Remove-Item -LiteralPath $Output -Force }
    Compress-Archive -Path (Join-Path $workspace '*') -DestinationPath $Output -CompressionLevel Optimal
} finally {
    if (Test-Path -LiteralPath $workspace) { Remove-Item -LiteralPath $workspace -Recurse -Force }
}
