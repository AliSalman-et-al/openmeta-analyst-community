# macOS Intel x64 Qt6 package qualification

Issue #342 qualifies the unsigned native Intel package produced by
`scripts/package-macos.sh --architecture x64`. Packaging-relevant changes run
the same qualification on the native `macos-15-intel` GitHub runner. The
qualified ZIP has a single `.app` plus retained qualification evidence; it does
not contain or depend on an Apple Silicon slice.

## Assembly and deployment inspection

`packaging/pyinstaller/rc-metastudio-macos.spec` is the sole collection
definition. It generates a normal Cocoa `BUNDLE`, requires macOS 13 or later,
and collects the locked generated forms, binary Qt resource, project schemas,
rpy2 metadata, and Qt modules. The wrapper does not invoke `macdeployqt`, add a
second Qt tree, or enumerate Qt frameworks manually. PyInstaller receives a
thin `x86_64` target and is responsible for its normal Qt hook processing.

The finished app contains the bundled R 4.6 runtime and strict package library.
Posit Public Package Manager supplies native Intel binaries for the complete
dependency closure; the pinned HSROC 2.1.9 archive is the sole source-package
exception. The R launchers and Mach-O install names are relocated before the
app is used.

`scripts/inspect_macos_deployment.py` inspects the final, ad-hoc-signed app. It
parses every Mach-O header and accepts only the exact thin `x86_64` slice,
resolves every `@loader_path`, `@executable_path`, and `@rpath` dependency to a
unique in-bundle Intel target using only the loader's or packaged executable's
declared `LC_RPATH` entries, rejects duplicate install identities, non-system
absolute dependencies, and escaping symlinks, and records a bounded
hash/dependency inventory. Deployed Qt UUIDs must match the locked-wheel native
inventory; the manifest retains both locked source and deployed hashes. It
requires exactly one authoritative
PyQt6/Qt6 plugin root and one Cocoa, JPEG, SVG image, and SVG icon plugin, plus
at least one Qt TLS plugin. It also authenticates the frozen runtime probe,
locked Python/PyQt6/Qt/SIP/R/rpy2/PyInstaller versions, bundled R paths,
project schemas, bundle identifier, normal `CFBundleExecutable`, macOS floor,
and replaceable ad-hoc code signature. PyQt5, Qt5, PySide, shiboken, qtpy,
wrong-architecture, duplicate, and missing native payloads fail qualification.

## Packaged workflow and Cocoa surfaces

Workflow and surface smoke processes run the actual
`Contents/MacOS/RCMetaStudio` executable under a 15-minute process-tree
watchdog. A separate bounded `open -W -n RCMetaStudio.app --args ...`
invocation exercises the normal LaunchServices `.app` entry and must write an
authenticated Cocoa/project/PID/post-close completion marker. The workflow opens the converted
`amino.rcms` sample, performs a Unicode study edit, runs a real bundled-R
analysis, validates the locked result text and SVG identity, saves canonical
dot- and comma-decimal projects, reopens the saved project, and reruns the
analysis. A separate positional invocation exercises the normal user entry
point. Clean exit requires the post-close marker and exact zero exit codes.

Native Cocoa subprocesses at 125%, 150%, and 175% exercise clipboard Unicode,
the native menu bar, deterministic native file-dialog open/cancel behavior,
native Cocoa accessibility role/element state and keyboard focus traversal, a critical
dialog, compiled resources, image/SVG formats, a Qt style, TLS backends,
German-locale decimal parsing, and screen DPR/DPI. Requested scale is checked
against an unscaled frozen-runtime baseline.

## Retained evidence and signing boundary

The archive inspector rejects traversal, absolute or non-normalized members,
backslashes, duplicate or case-colliding names, a wrong root, and any embedded
manifest/probe/smoke/log that differs from its inspected source. The separate
qualification record binds the ZIP hash and size, architecture/dependency
manifest, runtime probe, smoke evidence and log, archive inspection, and GitHub
runner/image/OS identity. Failure uploads retain PyInstaller diagnostics and
every qualification file written before the failure.

After assembly, the app receives a replaceable ad-hoc signature with the
hardened-runtime option and no entitlements. Strict deep verification and
flag/entitlement inspection happen before the runtime probe and every smoke, so
the exercised bytes have the same hardened-runtime policy as the archived app.
This qualifies the structure for future Developer ID signing and notarization. Developer ID
signing, notarization, stapling, and universal2 assembly remain outside #342.

## Hosted acceptance record

The implementation requires a successful native `macos-15-intel` package job
before #342 closes. Record the accepted run, exact tested head and merge SHA,
job and artifact IDs, ZIP size and SHA-256, runner identity, retained-evidence
hashes, workflow results, and elapsed time here after the hosted artifact has
been independently inspected.
