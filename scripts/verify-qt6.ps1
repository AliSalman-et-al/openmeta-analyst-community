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

    $qtModules = @(uv run python scripts/import_qt_modules.py --root . --list)
    if ($LASTEXITCODE -ne 0 -or $qtModules.Count -eq 0) {
        throw "Handwritten Qt module discovery failed."
    }
    uv run ty check `
        --extra-search-path "$BuildRoot/generated/rc_metastudio" `
        --extra-search-path "$BuildRoot/generated/rc_metastudio/forms" `
        --extra-search-path src/rc_metastudio `
        --extra-search-path scripts `
        $qtModules
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

    uv run python -W error -m rc_metastudio.qt6_cutover
    if ($LASTEXITCODE -ne 0) { throw "Qt6 final zero-legacy audit failed." }

    uv run python scripts/import_qt_modules.py `
        --build-root $BuildRoot `
        --report "$BuildRoot/qt-module-imports.json"
    if ($LASTEXITCODE -ne 0) { throw "Warnings-as-errors Qt module import audit failed." }

    $codemodSources = Get-ChildItem src/rc_metastudio -File -Filter *.py |
        Where-Object { $_.Name -notin @("qt6_port_tools.py", "qt6_cutover.py") } |
        ForEach-Object { $_.FullName }
    uv run python -W error scripts/qt6_port.py codemod --check `
        --report docs/verification/qt6-codemod-second-run.json `
        $codemodSources
    if ($LASTEXITCODE -ne 0) { throw "Qt6 second codemod run was not empty." }

    uv run python scripts/validate_qt6_surface_inventory.py --check-document
    if ($LASTEXITCODE -ne 0) { throw "Native Qt6 surface inventory validation failed." }

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
        --tests-path tests/python/fast/test_project_adapter.py `
        --require-covered
    if ($LASTEXITCODE -ne 0) { throw "Project Adapter test taxonomy manifest validation failed." }

    uv run python scripts/validate_test_taxonomy.py `
        --tests-path tests/python/fast/test_qt6_macos_feasibility.py `
        --require-covered
    if ($LASTEXITCODE -ne 0) { throw "Native macOS feasibility taxonomy validation failed." }

    uv run python scripts/validate_test_taxonomy.py `
        --tests-path tests/python/fast/test_native_remaining_surfaces_evidence.py `
        --require-covered
    if ($LASTEXITCODE -ne 0) { throw "Native remaining-surface taxonomy validation failed." }

    $env:RCMS_QT6_BUILD_ROOT = (Resolve-Path $BuildRoot).Path
    uv run python scripts/validate_test_taxonomy.py `
        --tests-path tests/python/gui/test_qt6_application_shell.py `
        --require-covered
    if ($LASTEXITCODE -ne 0) { throw "Qt6 application-shell taxonomy validation failed." }

    foreach ($workspaceTests in @(
        "tests/python/fast/test_dataset_model_edit_values.py",
        "tests/python/fast/test_main_workspace_policy.py",
        "tests/python/fast/test_workspace_model_contracts.py",
        "tests/python/gui/test_main_workspace_window.py",
        "tests/python/gui/test_metaform_data_workflows.py"
    )) {
        uv run python scripts/validate_test_taxonomy.py `
            --tests-path $workspaceTests `
            --require-covered
        if ($LASTEXITCODE -ne 0) { throw "Qt6 workspace taxonomy validation failed: $workspaceTests" }
    }

    foreach ($calculatorTests in @(
        "tests/python/fast/test_calculator_qt6.py",
        "tests/python/gui/test_binary_data_transactional_layout.py",
        "tests/python/gui/test_continuous_data_transactional_layout.py",
        "tests/python/gui/test_diagnostic_transactional_layout.py"
    )) {
        uv run python scripts/validate_test_taxonomy.py `
            --tests-path $calculatorTests `
            --require-covered
        if ($LASTEXITCODE -ne 0) { throw "Qt6 calculator taxonomy validation failed: $calculatorTests" }
    }

    foreach ($analysisTests in @(
        "tests/python/gui/test_analysis_configuration_layout.py",
        "tests/python/gui/test_analysis_failure_safety.py",
        "tests/python/gui/test_diagnostic_analysis_workflow.py",
        "tests/analysis_regression/golden/test_analysis_regression_compare.py",
        "tests/analysis_regression/golden/test_golden_baseline_manifest_validation.py"
    )) {
        uv run python scripts/validate_test_taxonomy.py `
            --tests-path $analysisTests `
            --require-covered
        if ($LASTEXITCODE -ne 0) { throw "Qt6 analysis taxonomy validation failed: $analysisTests" }
    }

    foreach ($resultsTests in @(
        "tests/python/fast/test_native_results_evidence.py",
        "tests/python/gui/test_results_workspace_layout.py",
        "tests/python/gui/test_network_view_workspace_layout.py"
    )) {
        uv run python scripts/validate_test_taxonomy.py `
            --tests-path $resultsTests `
            --require-covered
        if ($LASTEXITCODE -ne 0) { throw "Qt6 Results taxonomy validation failed: $resultsTests" }
    }

    foreach ($remainingSurfaceTests in @(
        "tests/python/gui/test_adaptive_window_policy.py",
        "tests/python/gui/test_compact_transient_layout.py",
        "tests/python/gui/test_declarative_dialog_sizing.py",
        "tests/python/gui/test_edit_dataset_workspace_layout.py",
        "tests/python/gui/test_main_wizard_workflow_layout.py"
    )) {
        uv run python scripts/validate_test_taxonomy.py `
            --tests-path $remainingSurfaceTests `
            --require-covered
        if ($LASTEXITCODE -ne 0) { throw "Qt6 remaining-surface taxonomy validation failed: $remainingSurfaceTests" }
    }

    uv run pytest -W error `
        tests/python/fast/test_qt6_build_slice.py `
        tests/python/fast/test_qt6_port_tools.py `
        tests/python/fast/test_project_format.py `
        tests/python/fast/test_project_adapter.py `
        tests/python/fast/test_qt6_macos_feasibility.py `
        tests/python/fast/test_native_remaining_surfaces_evidence.py `
        tests/python/fast/test_qt6_cutover_finalization.py
    if ($LASTEXITCODE -ne 0) { throw "Qt6 vertical-slice tests failed." }

    uv run pytest -W error tests/python/gui/test_qt6_application_shell.py
    if ($LASTEXITCODE -ne 0) { throw "Qt6 application-shell tests failed." }

    uv run pytest -W error `
        tests/python/fast/test_dataset_model_edit_values.py `
        tests/python/fast/test_dataset_ordering.py `
        tests/python/fast/test_main_workspace_policy.py `
        tests/python/fast/test_workspace_model_contracts.py `
        tests/python/fast/test_calculator_qt6.py `
        tests/python/gui/test_main_workspace_window.py `
        tests/python/gui/test_metaform_data_workflows.py `
        tests/python/gui/test_binary_data_transactional_layout.py `
        tests/python/gui/test_continuous_data_transactional_layout.py `
        tests/python/gui/test_diagnostic_transactional_layout.py
    if ($LASTEXITCODE -ne 0) { throw "Qt6 main workspace tests failed." }

    uv run pytest -W error `
        tests/python/gui/test_analysis_configuration_layout.py `
        tests/python/gui/test_analysis_failure_safety.py `
        tests/python/gui/test_diagnostic_analysis_workflow.py `
        tests/analysis_regression/golden/test_analysis_regression_compare.py `
        tests/analysis_regression/golden/test_golden_baseline_manifest_validation.py
    if ($LASTEXITCODE -ne 0) { throw "Qt6 analysis workflow tests failed." }

    uv run pytest -W error `
        tests/python/fast/test_native_results_evidence.py `
        tests/python/gui/test_results_workspace_layout.py `
        tests/python/gui/test_network_view_workspace_layout.py
    if ($LASTEXITCODE -ne 0) { throw "Qt6 Results and Network View tests failed." }

    uv run pytest -W error `
        tests/python/gui/test_adaptive_window_policy.py `
        tests/python/gui/test_compact_transient_layout.py `
        tests/python/gui/test_declarative_dialog_sizing.py `
        tests/python/gui/test_edit_dataset_workspace_layout.py `
        tests/python/gui/test_main_wizard_workflow_layout.py
    if ($LASTEXITCODE -ne 0) { throw "Qt6 remaining-window and accessibility tests failed." }

    powershell -ExecutionPolicy Bypass -File scripts/verify-r-stack-full.ps1
    if ($LASTEXITCODE -ne 0) { throw "Real-R stack and Golden compatibility verification failed." }

    $previousQpa = $env:QT_QPA_PLATFORM
    $previousFatalWarnings = $env:QT_FATAL_WARNINGS
    Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    $env:QT_FATAL_WARNINGS = "1"
    try {
        uv run python scripts/build_qt6.py native-smoke --build-root $BuildRoot --exit-after-ms 100
        if ($LASTEXITCODE -ne 0) { throw "Native qwindows Qt6 smoke failed." }
        $env:RCMS_STUB_BACKEND = "1"
        uv run rc-metastudio --automation-native-shell-smoke
        if ($LASTEXITCODE -ne 0) { throw "Native RC MetaStudio Qt6 shell smoke failed." }
        uv run python scripts/native_calculator_smoke.py
        if ($LASTEXITCODE -ne 0) { throw "Native Qt6 calculator smoke failed." }
        uv run python scripts/native_calculator_smoke.py --validate-only
        if ($LASTEXITCODE -ne 0) { throw "Native Qt6 calculator evidence validation failed." }
        uv run python scripts/native_analysis_smoke.py
        if ($LASTEXITCODE -ne 0) { throw "Native Qt6 analysis workflow smoke failed." }
        uv run python scripts/native_results_smoke.py
        if ($LASTEXITCODE -ne 0) { throw "Native Qt6 Results fractional-scale smoke failed." }
        uv run python scripts/native_results_smoke.py --validate-only
        if ($LASTEXITCODE -ne 0) { throw "Native Qt6 Results evidence validation failed." }
        uv run python scripts/native_remaining_surfaces_smoke.py
        if ($LASTEXITCODE -ne 0) { throw "Native Qt6 remaining-surface smoke failed." }
        uv run python scripts/native_remaining_surfaces_smoke.py --validate-only
        if ($LASTEXITCODE -ne 0) { throw "Native Qt6 remaining-surface evidence validation failed." }
        uv run rc-metastudio --automation-shell-failure-smoke r-load
        if ($LASTEXITCODE -ne 0) { throw "Native R-load teardown smoke failed." }
        uv run rc-metastudio --automation-shell-failure-smoke meta-form
        if ($LASTEXITCODE -ne 0) { throw "Native MetaForm teardown smoke failed." }
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
