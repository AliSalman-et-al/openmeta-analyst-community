# Testing

The maintained integration workflow uses the uv-managed Python 3.11/PyQt6
environment in `pyproject.toml` and `uv.lock`.

## Python/Qt uv environment

Sync the locked verification environment from the repository root:

```powershell
uv sync --locked
```

Run the maintained Qt6 vertical-slice lane:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-qt6.ps1 -Sync
```

It performs deterministic form and binary-resource generation, strict `ty`
checking, lane-directory and marker validation, the maintained GUI evidence,
and separate visible native `qwindows` smokes with `QT_QPA_PLATFORM` unset. The
analysis evidence contract is documented in
[native-qt6-analysis.md](../verification/native-qt6-analysis.md).
The shell smoke constructs the real `MetaForm`, exercises its menu surface,
processes events, and verifies the owned window is deleted on close with Qt
warnings fatal inside the controlled process.

The Smoke Verification Lane, Fast Verification Lane, GUI suite, Default R
Evidence, and packaging-contract aggregate are native PyQt6 verification paths.
Fast Verification runs on Windows x64, macOS Intel x64, and macOS ARM64 for
Qt-affecting changes. Packaging contracts no longer run inside
each source-fast target; a package-relevant pull request runs them once in the
required `packaging-contract` job:

```powershell
uv run python scripts\verify.py smoke
uv run python scripts\verify.py fast --require-r-evidence
```

The hosted Windows Native Qt6 Vertical Slice has a 45-minute ceiling. Its native
smoke subprocesses also have bounded watchdogs so a stuck Qt teardown fails with
the exact command and timeout while preserving streamed output and any evidence
already written. The workflow ceiling remains a failure boundary for the full
Qt6 verifier, not a performance target.

The first clean run downloads the immutable official Qt 6.11.1 Windows x64
`qtbase` package used only for its matching `rcc` and `Qt6Core.dll`. The package,
compiler, companion DLL, version, and PE architecture are pinned and validated
before every use. The PyQt6 runtime remains supplied solely by the locked
PyQt6 wheels.

The maintained lane-specific selections are:

```powershell
uv run pytest tests -m gui
uv run pytest tests -m r_stack
uv run pytest tests -m golden
uv run pytest tests -m packaging_contract
```

Run Full R Stack Evidence before R Stack changes:

```powershell
uv run python scripts\verify.py r-stack
```

The Full R Stack verifier selects the complete `tests/r_stack` directory. It
sets `RCMS_R_STACK_REQUIRED=1`, so missing R, rpy2, or required R packages fail
the maintained lane instead of becoming opportunistic pytest skips. Direct
local pytest selections may still skip when the workstation prerequisites are
absent; those runs are not Full R Stack evidence. The Golden verifier writes
only below a marker-owned `build/qt6-verification/golden-compatibility-*`
directory and authenticates the committed outer archive, its bounded ZIP
structure, internal manifest, artifacts, independently hashed 415-value numeric
contract, descriptor contract, and exact rpy2 distribution identities before
accepting a capture. Frozen numeric text is never parsed to create expectations
at runtime; only current candidate output is parsed and compared under the
committed absolute/relative tolerance policy.

Smoke/Fast Default R Evidence uses `artifacts\r-default-library-cache`, and Full R Stack Evidence retains its separate `artifacts\r-library-cache`. Windows package construction does not reuse either installed library tree: it caches only immutable downloads, installs the pinned native package closure into its private staged R runtime, and then installs local `RCMetaR`. Native binary dependencies are pinned to the dated Public PPM snapshot `https://packagemanager.posit.co/cran/2026-07-16`; `RCMS_CRAN_REPO` may repeat that exact value, but mismatched overrides are rejected.

Build and qualify the Windows package through one native command. It downloads
and authenticates the pinned official R installer into the immutable download
cache, stages it privately, and needs an x64 C compiler for the API-mode rpy2
bridge:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package-windows.ps1
```

Pull requests that change a direct Windows assembly or qualification input must
pass both the structured `Packaging Contract Tests` job and the required
`Required Windows x64 Package Qualification` job. The
classifier includes the package workflows and specifications, Python/R locks,
application source, bundled sample projects, R sources and dependency policy,
delivery-target metadata, Qt generation and package-verification scripts, the
deployment inspector, packaging contracts, and the packaged `MetaForm`
automation-launch test, along with the focused project-format, Qt text-boundary,
Qt build-slice, and cutover-finalization tests invoked by release verification.
Keep that classifier synchronized whenever the package script or release
verifier gains another direct input.

The job retains the distributable ZIP plus the deployment manifest, frozen
runtime probe, packaged smoke evidence/log, archive-inspection report, exact-ZIP
extracted reinspection and smoke evidence/log, and final qualification evidence.
The final evidence binds those extracted gates, their pass status, and the ZIP
SHA-256; it also records the source HEAD plus clean/dirty provenance. The runtime probe is collected with `QT_SCALE_FACTOR`
absent; later 125%, 150%, and 175% subprocesses prove their requested scale
against that unscaled baseline. UPX is disabled for the frozen executable and
collected payload so Qt DLL and plugin bytes remain identical to the locked
wheel on every host. This deliberately favors reproducibility over a smaller
ZIP. Run the fast local package contracts before
requesting the hosted artifact build:

```powershell
uv run pytest -q tests/packaging/contract
```

The hosted job is intentionally more expensive because it assembles bundled R,
builds the frozen application, runs real-R GUI analysis, and inspects the final
ZIP. Its uv, R dependency, and package inputs are cached, so avoid manual reruns
when neither code nor cache state changed; local contracts are the quick feedback
loop, not a substitute for the required hosted artifact proof.

On macOS Intel, the public command is a single native build. It stages the
authenticated official R framework and compiles the API-only rpy2 bridge in
that same job; it never consumes an R Integration Kit:

```bash
bash ./scripts/package-macos.sh --architecture x64
```

Native macOS candidate and release workflows retain Intel x64 qualification.
The Intel job retains the distributable ZIP,
Mach-O deployment/dependency manifest, frozen runtime probe, packaged workflow
and Cocoa-surface evidence, logs, archive-inspection record, and final evidence
binding. Local cross-platform contracts are the fast feedback seam:

```powershell
uv run pytest -q tests/packaging/contract/test_macos_x64_distributable_contract.py
```

Only a native `macos-15-intel` run can satisfy the final architecture, Cocoa,
bundle-signature, and packaged-R evidence contract.

The hosted pull-request path runs the Windows Qt6 vertical slice, the three
target Source Fast Verification matrix, and the required Windows Full R Stack
Evidence job when source, tests, dependency files, or verification inputs
change. Package-relevant changes additionally run the Windows and focused native
macOS packaging contract jobs plus Windows package qualification. Native macOS
Intel and Apple Silicon feasibility is delivered by Issue #329.
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
