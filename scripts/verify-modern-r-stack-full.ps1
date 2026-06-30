param(
    [string]$Rscript = "Rscript"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
    uv sync --locked
    if ($LASTEXITCODE -ne 0) { throw "uv failed to sync the locked modern environment." }

    uv run python scripts\verify_openmetar_r_stack.py --rscript $Rscript
    if ($LASTEXITCODE -ne 0) { throw "Full R Stack Evidence failed." }
}
finally {
    Pop-Location
}
