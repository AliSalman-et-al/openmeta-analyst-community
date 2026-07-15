param(
    [switch]$Sync,
    [string]$BuildRoot = "build/qt6-verification"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
    if ($Sync) {
        uv sync --locked
        if ($LASTEXITCODE -ne 0) { throw "uv sync --locked failed." }
    }

    uv run python scripts/build_qt6.py generate --build-root $BuildRoot
    if ($LASTEXITCODE -ne 0) { throw "Qt6 form or resource generation failed." }

    uv run ty check `
        src/rc_metastudio/qt6_build.py `
        src/rc_metastudio/project_domain.py `
        src/rc_metastudio/project_evidence.py `
        src/rc_metastudio/project_format.py `
        scripts/build_qt6.py
    if ($LASTEXITCODE -ne 0) { throw "Qt6 strict type verification failed." }

    uv run python scripts/validate_test_taxonomy.py `
        --tests-path tests/python/fast/test_qt6_build_slice.py `
        --require-covered
    if ($LASTEXITCODE -ne 0) { throw "Qt6 test taxonomy manifest validation failed." }

    uv run python scripts/validate_test_taxonomy.py `
        --tests-path tests/python/fast/test_project_format.py `
        --require-covered
    if ($LASTEXITCODE -ne 0) { throw "Project Format test taxonomy manifest validation failed." }

    uv run pytest `
        tests/python/fast/test_qt6_build_slice.py `
        tests/python/fast/test_project_format.py
    if ($LASTEXITCODE -ne 0) { throw "Qt6 vertical-slice tests failed." }

    $previousQpa = $env:QT_QPA_PLATFORM
    Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    try {
        uv run python scripts/build_qt6.py native-smoke --build-root $BuildRoot --exit-after-ms 100
        if ($LASTEXITCODE -ne 0) { throw "Native qwindows Qt6 smoke failed." }
    }
    finally {
        if ($null -ne $previousQpa) { $env:QT_QPA_PLATFORM = $previousQpa }
    }
}
finally {
    Pop-Location
}
