[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Tree,
    [Parameter(Mandatory = $true)][string]$Output
)
$ErrorActionPreference = "Stop"
$signtool = (Get-Command signtool.exe -ErrorAction Stop).Source
$signables = Get-ChildItem -LiteralPath $Tree -Recurse -File | Where-Object { $_.Extension -in '.exe', '.dll' }
if (-not $signables) { throw "No Authenticode-signable files found." }
foreach ($file in $signables) {
    & $signtool verify /pa /all /v $file.FullName
    if ($LASTEXITCODE -ne 0) { throw "Signature verification failed: $($file.FullName)" }
}
if (Test-Path -LiteralPath $Output) { Remove-Item -LiteralPath $Output -Force }
Compress-Archive -Path (Join-Path $Tree '*') -DestinationPath $Output -CompressionLevel Optimal
