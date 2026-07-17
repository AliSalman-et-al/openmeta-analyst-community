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
The complete R runtime is a nested `Contents/Frameworks/R.framework`. Its
`Versions/<R-version>/Resources` directory is R_HOME, `Versions/Current` and
the top-level `Resources` use canonical framework links, and the framework's
`R` executable link resolves to the bundled `Resources/lib/libR.dylib` named by
its `FMWK` Info.plist. Sample projects and the convenience launcher remain
under the app's `Contents/Resources`; `Contents/MacOS` retains only the actual
`RCMetaStudio` entry executable. Every R Mach-O remains in the explicit signing
and deployment inventories, and the complete framework is signed as nested
code after its native descendants.

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
every qualification file written before the failure, including the explicit
signing inventory once signing succeeds.

After assembly, `scripts/sign_macos_app.py` classifies every regular Mach-O
file, validates real nested code bundles from their `Info.plist` and native
`CFBundleExecutable`, and signs that fixed inventory inside-out before signing
the outer app. It never asks `codesign --deep` to discover signing targets, so
dotted R data directories and executable scripts remain resources rather than
heuristically inferred code bundles. Any unreadable payload, malformed bundle
that contains native code, or inventory drift during signing fails closed.
This follows Apple's guidance to keep app data in Resources, package native
runtime code as a valid nested framework, sign nested code
inside-out, and reserve `--deep` for verification. Apple documents that
directories containing periods in code locations are interpreted as bundles;
the old `Contents/MacOS/R` layout therefore caused recursive signing to
misclassify rmarkdown's `navigation-1.1` CSS/JavaScript resource directory
([TN2206](https://developer.apple.com/library/archive/technotes/tn2206/)).

The same explicit signer applies either the replaceable ad-hoc identity used by
package qualification or a timestamped Developer ID identity in the future
release stage. The ad-hoc inventory is embedded in the qualification ZIP and
hash-bound by both archive inspection and final evidence; the Developer ID
inventory is retained beside the signed ZIP, bound into the immutable delivery
stage chain, checksummed, and published with the release candidate. Every
classified Mach-O and real nested bundle receives the
hardened-runtime option and individual strict verification; the outer app also
receives strict deep verification after its resource seal is created.
Flag/entitlement inspection happens before the runtime probe and every smoke,
so the exercised bytes have the same hardened-runtime policy as the archived
app. Developer ID signing, notarization, stapling, and universal2 assembly
remain outside #342.

## Hosted acceptance record

The implementation requires a successful native `macos-15-intel` package job
before #342 closes. Record the accepted run, exact tested head and merge SHA,
job and artifact IDs, ZIP size and SHA-256, runner identity, retained-evidence
hashes, workflow results, and elapsed time here after the hosted artifact has
been independently inspected.
