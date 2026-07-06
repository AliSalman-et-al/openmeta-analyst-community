param(
    [string]$Rscript = "Rscript",
    [string]$RPackageCacheRoot
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $RPackageCacheRoot) {
    $RPackageCacheRoot = Join-Path (Join-Path $repoRoot "artifacts") "r-library-cache"
}

Push-Location $repoRoot
try {
    uv sync --locked
    if ($LASTEXITCODE -ne 0) { throw "uv failed to sync the locked verification environment." }

    uv run python scripts\verify_rcmetar_r_stack.py --rscript $Rscript --r-library-cache-root $RPackageCacheRoot
    if ($LASTEXITCODE -ne 0) { throw "Full R Stack Evidence failed." }
}
finally {
    Pop-Location
}
