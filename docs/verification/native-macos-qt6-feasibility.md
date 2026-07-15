# Native macOS Qt6 feasibility

Issue #329 owns the pre-codemod native feasibility gate for macOS Intel x64 and
Apple Silicon ARM64. The gate is implemented by
`.github/workflows/qt6-macos-feasibility.yml`; it is separate from full release
packaging because it answers one bounded question before broad source
conversion: can the exact locked Qt6, R, rpy2, and PyInstaller chain work
natively on both supported Mac architectures?

## Evidence contract

Each matrix leg runs on its native GitHub-hosted architecture and fails before
launch when the runner, Python process, or Rosetta status does not match the
declared target. It installs Python 3.11.9 and R 4.6.1, synchronizes the frozen
`uv.lock`, and obtains `rcc` 6.11.1 from the official Qt online repository with
the exactly selected `aqtinstall` client. The repository validator records and
checks the resolved Python, PyQt6, Qt, SIP, R, rpy2, and PyInstaller versions.

The source proof generates the representative Designer form, compiles and
registers the binary resource, renders its SVG icon, shows a real Cocoa dialog,
and exits cleanly. A real in-process rpy2 call evaluates
`sum(c(1.25, 2.5, 3.75))` and must return 7.5. The same form, resource, SVG, R
call, and Cocoa launch then run from a thin one-directory PyInstaller app.
PyInstaller receives the application entry point and resource as inputs and is
the sole Qt dependency collector; no manual Qt framework or plugin copy is
permitted.

The evidence record includes an exact nested OS, runner-image, and machine
identity; Rosetta status; locked versions; source paths; Mach-O architecture
slices; the source and packaged Cocoa plugin paths; and smoke outcomes. The
uploaded bundle retains bounded copies of the native Python, PyQt6, Qt6, SIP,
R, rpy2, `rcc`, and Cocoa probes plus the packaged executable and packaged
Cocoa plugin. It also retains a complete file/hash deployment inventory and the
exact PyInstaller build plan, but not the full disposable application bundle.
The validator recomputes retained sizes, hashes, and architectures, checks the
deployment has one coherent PyQt6/Qt6 root and one Cocoa plugin, and rejects
manual or alternate Qt collection. Native probes are capped at 100 MB; the
inspected minimal deployment is capped at 10,000 files and 1 GB. The two
architecture evidence artifacts are retained separately for 30 days and named
with the source commit SHA.

## Blocking policy

This workflow is deliberately fail-closed. A missing wheel, incompatible R or
rpy2 binary, missing native slice, resource failure, non-Cocoa launch,
PyInstaller collection failure, or malformed evidence blocks the broad Qt6
codemod. It must result in a reviewed dependency replacement decision; the job
does not enable Rosetta, switch bindings, copy Qt manually, or downgrade the
proof to offscreen execution.

The workflow and validator can be checked on Windows, but successful native
evidence cannot be produced there. Issue #329 is complete only after both
GitHub matrix legs have run successfully and their retained evidence has been
reviewed; repository code alone is not a substitute for those results.
