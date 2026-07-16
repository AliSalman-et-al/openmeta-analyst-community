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
        src/rc_metastudio/qt6_port_tools.py `
        src/rc_metastudio/qt6_macos_feasibility.py `
        scripts/build_qt6.py `
        scripts/qt6_port.py
    if ($LASTEXITCODE -ne 0) { throw "Qt6 strict type verification failed." }

    $dependencyInputs = @("pyproject.toml", "uv.lock")
    $dependencyInputs += Get-ChildItem -File -ErrorAction SilentlyContinue `
        -Path "requirements*.txt", "constraints*.txt" | ForEach-Object { $_.FullName }
    uv run python -W error scripts/qt6_port.py strict --root . $dependencyInputs
    if ($LASTEXITCODE -ne 0) { throw "Qt6 strict dependency policy failed." }

    uv run python -W error scripts/qt6_port.py strict --root . `
        --expected-snapshot config/qt6-strict-source-backlog.json `
        --report "$BuildRoot/strict-source-findings.json" `
        src/rc_metastudio
    if ($LASTEXITCODE -ne 0) { throw "Qt6 authoritative source backlog drifted." }

    uv run python scripts/validate_test_taxonomy.py `
        --tests-path tests/python/fast/test_qt6_port_tools.py `
        --require-covered
    if ($LASTEXITCODE -ne 0) { throw "Qt6 port tooling taxonomy validation failed." }

    uv run python scripts/validate_test_taxonomy.py `
        --tests-path tests/python/fast/test_qt6_build_slice.py `
        --require-covered
    if ($LASTEXITCODE -ne 0) { throw "Qt6 test taxonomy manifest validation failed." }

    uv run python scripts/validate_test_taxonomy.py `
        --tests-path tests/python/fast/test_project_format.py `
        --require-covered
    if ($LASTEXITCODE -ne 0) { throw "Project Format test taxonomy manifest validation failed." }

    uv run python scripts/validate_test_taxonomy.py `
        --tests-path tests/python/fast/test_qt6_macos_feasibility.py `
        --require-covered
    if ($LASTEXITCODE -ne 0) { throw "Native macOS feasibility taxonomy validation failed." }

    uv run pytest -W error `
        tests/python/fast/test_qt6_build_slice.py `
        tests/python/fast/test_qt6_port_tools.py `
        tests/python/fast/test_project_format.py `
        tests/python/fast/test_qt6_macos_feasibility.py
    if ($LASTEXITCODE -ne 0) { throw "Qt6 vertical-slice tests failed." }

    $previousQpa = $env:QT_QPA_PLATFORM
    $previousFatalWarnings = $env:QT_FATAL_WARNINGS
    Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    $env:QT_FATAL_WARNINGS = "1"
    try {
        uv run python scripts/build_qt6.py native-smoke --build-root $BuildRoot --exit-after-ms 100
        if ($LASTEXITCODE -ne 0) { throw "Native qwindows Qt6 smoke failed." }
    }
    finally {
        if ($null -ne $previousQpa) { $env:QT_QPA_PLATFORM = $previousQpa }
        if ($null -ne $previousFatalWarnings) {
            $env:QT_FATAL_WARNINGS = $previousFatalWarnings
        }
        else {
            Remove-Item Env:QT_FATAL_WARNINGS -ErrorAction SilentlyContinue
        }
    }
}
finally {
    Pop-Location
}
