# Windows x64 Qt6 Package Qualification

Issue #341 qualifies the unsigned Windows x64 package produced by
`scripts/package-windows.ps1`. Packaging-relevant pull requests run this same
qualification as a required job in `.github/workflows/fast-verification.yml`;
the manual workflow remains available for explicit rebuilds. The package is built from the locked Python 3.11,
PyQt6, Qt 6, SIP, R, rpy2, and PyInstaller inputs. PyInstaller 6.21 is the only
Qt dependency collector; the build does not run `windeployqt` or copy an
independently deployed Qt tree over PyInstaller's output.
`packaging/pyinstaller/rc-metastudio.spec` is the sole authoritative collection
definition; `scripts/build-windows-package.ps1` supplies only build/output roots
and qualification orchestration.

## Fail-closed deployment inspection

The assembled `RCMetaStudio.exe` first runs
`--automation-package-runtime-probe`. That frozen process reports its own
Python executable and bundle root, Python/PyQt/compiled Qt/runtime Qt/SIP/rpy2
versions, architecture, Qt plugin/library paths and platform plugin, bundled R
home/library/version, and baseline DPR/DPI. The source interpreter is not
accepted as runtime evidence. PyInstaller is separately identified as
build-time provenance because it does not exist as an application runtime.

`scripts/inspect_windows_deployment.py inspect` then runs against the assembled
application. It records every PE file with its SHA-256
and rejects a non-x64 machine type, PyQt5/Qt5 content, generated development
sources, duplicate or misplaced Qt libraries, a stack version outside the lock,
and missing, duplicated, misplaced, or wheel-mismatched platform, image, SVG,
style, or Schannel TLS plugins. PySide2, PySide6, qtpy, PyQt5, and Qt5 payloads
are rejected. Required Qt DLL and plugin hashes must match the locked PyQt6-Qt6
wheel used by the build. The accepted
OS floor is Windows 10 version 1809 (build 17763) or later. No signing requirement
or weakened security setting is part of this qualification.

The resulting `qualification/deployment-manifest.json` is retained inside the
ZIP. This makes the inspected layout travel with the artifact rather than
depending on a mutable CI log.

## Packaged workflow smoke

The native automation starts `RCMetaStudio.exe`, not a source module or helper
interpreter. It opens the converted `amino.rcms` sample and performs a Unicode
study-name edit before analysis. Equivalent dot-decimal (`en_US`) and
comma-decimal (`de_DE`) numeric inputs are persisted to separate versioned
projects; their canonical project data, exact locked summary SHA-256, and SVG
hashes must agree. The comma project is reopened, the edit is verified, and the
real bundled-R analysis is rerun; result text and SVG hashes must remain exact.
A separate invocation passes the project as the positional normal user entry
point. The application writes a post-close marker, while the parent records
clean exit only after every process actually returns code zero.

Separate native package processes at 125%, 150%, and 175% exercise the Windows
platform plugin, clipboard Unicode round-trip, comma-decimal locale parsing,
compiled Qt resources, required image/SVG formats, Schannel TLS, a loaded Qt
style, a critical message box, and valid screen DPI/DPR. Each requested scale
also proves the accessible control's name and description. Focus traversal and
native accessibility-interface assertions are intentionally reserved for the
interactive Cocoa package contract because qwindows activation is not reliable
on a noninteractive hosted runner. Each requested scale must equal
`QT_SCALE_FACTOR`; the frozen probe records that `QT_SCALE_FACTOR` was
absent, and observed DPR must equal that unscaled baseline
DPR multiplied by the request within an absolute 0.05 tolerance. Every
process has a 15-minute watchdog that terminates its complete process tree and
reports the exact command if clean exit is not observed. The watchdog also
fails if `taskkill` fails or the process remains alive after cleanup.

## Retained evidence

After assembly, the ZIP itself is inspected without extraction. Qualification
rejects traversal, absolute/non-normalized names, backslashes, duplicate or
case-colliding members, a wrong archive root, missing embedded evidence, or any
embedded deployment/probe/smoke/log byte that differs from the inspected source.

`artifacts/RCMetaStudio-windows-x64-evidence.json` authenticates the ZIP,
final archive-inspection report, frozen runtime probe, deployment manifest,
packaged smoke evidence, and log by SHA-256 and records the
GitHub runner name, image, OS version, and architecture. The manual package
workflow uploads it beside the uncompressed ZIP. On failure it additionally
retains the PyInstaller warning/cross-reference reports and any deployment,
smoke, or layout logs written before the failure.

## Accepted hosted qualification

Issue #341 qualification was accepted on GitHub Actions run
[`29596284816`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29596284816),
package job
[`87937396242`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29596284816/job/87937396242),
which passed in 16 minutes 33 seconds. The exact tested implementation head was
`87edffe1578aa4e1f15c3d02edf8c686401a8755`; GitHub's separate pull-request
merge ref was `6063a0b70fba8ae24f8d745980e8bf420b284b39`.

- Package artifact
  [`8413562830`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29596284816/artifacts/8413562830);
  qualification artifact
  [`8413563381`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29596284816/artifacts/8413563381).
- ZIP: 390,212,938 bytes; SHA-256
  `933083c9dca4584be7e2dd32ea2ad40d3efb4964907586dffa10fd12f2178a07`.
- Archive root: `RCMetaStudio-0.1.2-windows-x64`; 13,991 members.
- Evidence host: `win25-vs2026`, Windows X64 `10.0.26100`.
- Packaged open/edit/real-R analysis/locale/save-reopen workflows and native
  1.25, 1.50, and 1.75 scale smokes all passed.
- Embedded deployment, runtime-probe, smoke, and log hashes matched their
  retained qualification inputs exactly.
- R dependency policy used Posit Package Manager binaries, with only the pinned
  HSROC source exception. Packaged-smoke start through ZIP creation took about
  66 seconds.

Run the complete hosted gate with:

```powershell
gh workflow run package-verification.yml -f build_windows=true -f build_macos=false -f build_macos_arm64=false
```

Local contract verification is intentionally cheaper than constructing the R
bundle:

```powershell
uv run pytest tests/packaging/contract/test_windows_distributable_contract.py
```
