# Testing

The maintained integration workflow uses the uv-managed Python 3.11/PyQt6
environment in `pyproject.toml` and `uv.lock`.

## Python/Qt uv environment

Sync the locked verification environment from the repository root:

```powershell
uv sync --locked
```

During the dependency-first Native Qt6 Port interval, run the Qt6 vertical-slice
lane:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-qt6.ps1 -Sync
```

It performs deterministic form and binary-resource generation, strict `ty`
checking, focused offscreen and Versioned Project Format tests,
taxonomy-manifest validation, the full native PyQt6 application-shell suite,
the complete remaining-window accessibility and adaptive-layout matrix,
the maintained analysis tests, the full isolated R build/check/analysis stack,
the fail-closed real-R comparison against the frozen pre-Qt6 Golden archive,
and separate visible native `qwindows` smokes with `QT_QPA_PLATFORM` unset. The
Golden verifier writes only below a marker-owned
`build/qt6-verification/golden-compatibility-*` directory and authenticates the
committed outer archive, its bounded ZIP structure, internal manifest, artifacts,
the independently hashed 415-value numeric contract, descriptor contract, and
exact rpy2 distribution identities before accepting a capture. Frozen numeric
text is never parsed to create expectations at runtime; only current candidate
output is parsed and compared under the committed absolute/relative tolerance
policy. The analysis evidence contract is documented in
[native-qt6-analysis.md](../verification/native-qt6-analysis.md).
The shell smoke constructs the real `MetaForm`, exercises its menu surface,
processes events, and verifies the owned window is deleted on close with Qt
warnings fatal inside the controlled process.

The Smoke Verification Lane, Fast Verification Lane, GUI suite, Default R
Evidence, and packaging-contract aggregate are native PyQt6 verification paths.
Source smoke and Fast Verification run on Windows x64, macOS Intel x64, and
macOS ARM64 for Qt-affecting changes:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-smoke.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\verify-fast.ps1
```

The hosted Windows Native Qt6 Vertical Slice has a 45-minute ceiling because it
runs the complete Qt6 verifier, including native UI evidence and the isolated R
stack. This is a failure ceiling rather than a performance target; the lane must
not use the shorter Smoke/Fast budget.

The first clean run downloads the immutable official Qt 6.11.1 Windows x64
`qtbase` package used only for its matching `rcc` and `Qt6Core.dll`. The package,
compiler, companion DLL, version, and PE architecture are pinned and validated
before every use. The PyQt6 runtime remains supplied solely by the locked
PyQt6 wheels.

These lane-specific commands become available again as their PyQt6 source and
tests are integrated:

```powershell
uv run pytest tests -m gui
uv run pytest tests -m r_stack
uv run pytest tests -m golden
uv run pytest tests -m packaging_contract
```

Run Full R Stack Evidence before R Stack changes:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-r-stack-full.ps1
```

Smoke/Fast Default R Evidence uses `artifacts\r-default-library-cache`; Full R Stack Evidence and packaging use `artifacts\r-library-cache`. Keeping those caches separate prevents fast verification from restoring the larger bundled-R packaging cache. Set `RCMS_CRAN_REPO` to choose a faster reliable CRAN-compatible mirror when needed. The package wrappers resolve one source R runtime and pass that same runtime into R Stack Evidence and artifact assembly, so the dependency cache can be reused before only the local `RCMetaR` package is reinstalled into the bundle.

Build the Windows package only when packaging evidence is needed:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package-windows.ps1 -ArtifactName RCMetaStudio-windows-x64
```

On macOS, use the package script for the matching host architecture:

```bash
bash ./scripts/package-macos.sh --architecture x64
bash ./scripts/package-macos.sh --architecture arm64
```

The hosted pull-request path currently runs the Windows Qt6 vertical slice when
source, tests, dependency files, or its verification inputs change. Broader
source, R, and packaging gates return as the corresponding Qt6 tickets land.
Native macOS Intel and Apple Silicon feasibility is delivered by Issue #329.
Its native workflow and retained evidence contract are documented in
`docs/verification/native-macos-qt6-feasibility.md`. Local non-macOS validation
can check the validator and workflow structure, but it cannot satisfy the two
native Cocoa evidence legs.

## GUI paint coverage

Python GUI tests run with `QT_QPA_PLATFORM=offscreen`, which lays out widgets but never
paints them. Paint-only code paths are therefore invisible to most tests: Qt queries
`data()`/`headerData()` for paint roles such as `Qt.BackgroundColorRole`, `Qt.DecorationRole`,
and `Qt.FontRole` only while rendering, not during offscreen layout or `sizeHint`. A
Python-3 porting bug in one of those branches raises out of the C++ paint virtual and
aborts the process with exit code `0xC0000409` and no traceback.

Two mechanisms guard this class of bug; keep both working when touching table models or
delegates:

- `tests/python/gui/test_metaform_automation_launch.py::test_table_paint_roles_do_not_raise_across_all_cells`
  sweeps every cell and header section against the maintained Qt6 paint roles
  in-process, turning a paint-time abort into a clean test failure. Extend it when a
  model gains new roles.
- The packaged smoke test (`launch.start_automation_smoke` via `Invoke-PackagedAppSmokeTest`)
  calls `load_R_libraries` and forces a real paint pass (`_force_table_paint`) so both
  R-bridge and paint regressions fail the build gate with a non-zero exit instead of
  shipping. The plain `--automation-smoke` flag alone does not paint.

## R package setup in focused tests

`DatasetModel` initialization calls RCMetaR functions such as `set.global.conf.level`. Focused tests that instantiate `DatasetModel` without the full application setup should load only the needed package:

```python
meta_py_r.RlibLoader().load_RCMetaR()
```

Avoid `load_all()` for narrow tests unless network meta-analysis packages are required; this local environment currently lacks `gemtc`.
