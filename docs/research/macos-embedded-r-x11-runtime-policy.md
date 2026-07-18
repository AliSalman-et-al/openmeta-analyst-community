# macOS embedded R: Tcl/Tk and XQuartz runtime policy

## Decision

RC MetaStudio should ship a **product-profiled copy of the official CRAN
`R.framework` with its unused X11/Tcl/Tk loadable surfaces removed**. It should
not install XQuartz on the build runner and copy whatever `/opt/X11` libraries
happen to appear there, and it should not copy `/opt/R` Tcl/Tk libraries into
the app merely because `otool` finds their load commands.

For the R 4.6.1 Intel framework, the explicit exclusion set is:

- `Resources/library/tcltk/` (including `libs/tcltk.so`);
- `Resources/modules/R_X11.so`;
- `Resources/modules/R_de.so`, the X11 data editor/viewer module; and
- `Resources/library/grDevices/libs/cairo.so`, the CRAN macOS X11-linked Cairo
  module.

The exclusion must happen after copying the pristine R framework and installing
the application's R package library, but before architecture normalization,
install-name relocation, signing, deployment inspection, and smoke testing.
The packager should own this four-path allowlist and fail if a listed path is
unexpectedly absent, changes identity, or any other bundled Mach-O acquires an
`/opt/R` or `/opt/X11` dependency.

This is not an arbitrary reduced R build. It follows the upstream distribution
boundary: CRAN describes Tcl/Tk as an optional installer component needed only
for the `tcltk` R package, and says X11 use (including Tcl/Tk) requires a
separate XQuartz installation. RC MetaStudio has no Tcl/Tk or X11 user surface;
its UI is Qt/Cocoa, its tables are Qt models/views, and its current graphics
contract uses Quartz/default macOS bitmap devices plus `svglite` and `rsvg`.
[CRAN R for macOS](https://cran.r-project.org/bin/macosx/),
[R for macOS FAQ: Tcl/Tk](https://cran.r-project.org/bin/macosx/RMacOSX-FAQ.html#Tcl_002fTk-issues)

## Why the current build fails

The failure is deterministic, not a transient runner omission. Run
[`29628887206`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29628887206)
copied the complete installed `R.framework`, scanned every Mach-O, and tried to
close every `/opt/R` and `/opt/X11` load command. It found
`library/tcltk/libs/tcltk.so` referring to the separately installed CRAN Tcl/Tk
component and XQuartz, then stopped because the clean `macos-15-intel` image did
not contain `/opt/X11/lib/libX11.6.dylib`.

That is the layout CRAN publishes. Inspection on 2026-07-18 of the official
Intel installer `R-4.6.1-x86_64.pkg` (the SHA-1 published by CRAN is
`8d3c9e7a71dcba7602aaaf948b574e2e9d29844e`, which the inspected download
matched; its observed SHA-256 was
`612bb00cb4c627721d6d80b0f5224227c0fcdefb4a5b6c917511480361c16571`) showed
four separately selectable packages: `R-fw.pkg`, `R-app.pkg`, `tcltk.pkg`, and
`texinfo.pkg`. Its
`Distribution` describes Tcl/Tk 8.6.13 as the X11 build "needed for the tcltk R
package"; `tcltk.pkg` installs under `/opt/R/x86_64`, while the framework itself
still contains the `tcltk` R package and the loadable X11 modules. The public
CRAN page likewise says Tcl/Tk and Texinfo can be omitted in a custom install,
and that X11 requires XQuartz 2.8.5 or later.
[Official R 4.6.1 Intel installer](https://cran.r-project.org/bin/macosx/big-sur-x86_64/base/R-4.6.1-x86_64.pkg),
[CRAN R for macOS, Intel package and component notes](https://cran.r-project.org/bin/macosx/)

The four framework Mach-Os with non-system `/opt` load commands in that
official payload are:

| Framework item | External load-command family |
| --- | --- |
| `library/tcltk/libs/tcltk.so` | `/opt/R/x86_64/lib/libtcl8.6.dylib`, `libtk8.6.dylib`; X11, Xss, Xext |
| `modules/R_X11.so` | SM, ICE, X11, Xext, Xrender, Xt, Xmu |
| `modules/R_de.so` | SM, ICE, X11, Xext, Xrender, Xt, Xmu |
| `library/grDevices/libs/cairo.so` | Xrender, SM, ICE, X11, Xext |

The exact list matters: fixing only the first reported `libX11` error merely
moves the build to the next XQuartz dependency. The current recursive copy
algorithm is therefore solving the wrong contract. It treats every loadable
module in a general-purpose R installation as a required application feature,
even though R loads these modules only when their corresponding optional device
or UI is requested.

## Product dependency audit

The required package graph was checked against the pinned Public PPM Intel
binary index at
`https://packagemanager.posit.co/cran/2026-07-16/bin/macosx/big-sur-x86_64/contrib/4.6`.
Starting from all 54 manifest-owned normal packages and recursively following
only `Depends`, `Imports`, and `LinkingTo` produced 150 repository packages plus
the base/recommended runtime packages. It produced **no required `tcltk`
edge**. `colorspace` and `igraph` mention `tcltk` only in `Suggests`.

This distinction matches R's package model: `Suggests` is for packages not
necessarily needed for regular use, whereas packages in `Depends` and
`Imports` must be available for loading the package. RC MetaStudio's installer
already computes the hard closure from `Depends`, `Imports`, and `LinkingTo`
and installs that closed set with `dependencies = FALSE`.
[R Extensions: package dependencies](https://cran.r-project.org/doc/manuals/r-release/R-exts.html#Package-Dependencies),
[Pinned Public PPM Intel package index](https://packagemanager.posit.co/cran/2026-07-16/bin/macosx/big-sur-x86_64/contrib/4.6/PACKAGES.gz)

Repository searches found no R call to `tcltk`, `X11()`, the R X11 data
editor/viewer, or an explicitly requested Cairo device. RCMetaR does contain
legacy `png()` calls. On a macOS R build with Aqua, `grDevices` selects
`bitmapType = "quartz"`; the upstream `png()`, `jpeg()`, `tiff()`, and `bmp()`
implementations use the Quartz device when that option is selected. This is why
the packaged workflow in the failing run completed its real R analysis and
produced its expected result/SVG hashes on the same XQuartz-free runner before
the later closure pass rejected the unused binaries.
[R source: `grDevices` startup policy](https://svn.r-project.org/R/trunk/src/library/grDevices/R/zzz.R),
[R source: Unix bitmap devices](https://svn.r-project.org/R/trunk/src/library/grDevices/R/unix/png.R)

## Why not bundle XQuartz

Installing XQuartz in CI and copying `libX11.6.dylib` is not a production fix:

1. `libX11` is only one member of the direct dependency set above, and each
   copied library has its own transitive closure. A build-host traversal would
   silently define the shipped payload and could change when the XQuartz
   installer or runner changes.
2. XQuartz is an X server distribution, not just a convenient dylib feed. Its
   official installation instructions install a `.pkg`; first-time users may
   need to log out and back in to establish `DISPLAY`. R's own macOS page tells
   users to install XQuartz separately to use X11. Copying client dylibs into a
   Cocoa app does not supply or start that server.
3. It would add a large, unused native surface, license/source-notice inventory,
   signing inventory, vulnerability/update responsibility, fonts/configuration,
   and an extra runtime architecture contract to an app that exposes none of
   its functionality.
4. Apple recommends embedding only required third-party code, putting dynamic
   libraries in the appropriate code location, using bundle-relative install
   names, and signing the final nested code before sealing the outer app. A
   recursive copy from `/opt/X11` makes that review and future Developer ID
   signing boundary substantially harder.

[XQuartz 2.8.5 installation and server notes](https://www.xquartz.org/releases/XQuartz-2.8.5.html),
[XQuartz releases](https://www.xquartz.org/releases/),
[Apple: embedding nonstandard code structures](https://developer.apple.com/documentation/xcode/embedding-nonstandard-code-structures-in-a-bundle),
[Apple: placing content in a bundle](https://developer.apple.com/documentation/bundleresources/placing-content-in-a-bundle)

If a future product requirement genuinely introduces Tcl/Tk or X11, treat that
as a new delivery feature. The supported choices would be to document and test
XQuartz as an external prerequisite, or design and legally/security-review a
complete embedded X server distribution. Copying a handful of dylibs is not a
third supported choice.

## Why not replace Tcl/Tk or rebuild R now

Substituting Aqua Tcl/Tk libraries under an R binary built against CRAN's X11
Tcl/Tk is not an ABI-compatible relocation strategy. The R for macOS FAQ says
CRAN binary distributions are built for X11 Tcl/Tk and notes different behavior
for custom Aqua Tcl/Tk builds. Such a change requires rebuilding and qualifying
R itself.
[R for macOS FAQ: Tcl/Tk](https://cran.r-project.org/bin/macosx/RMacOSX-FAQ.html#Tcl_002fTk-issues),
[R Installation and Administration: macOS/X11 build options](https://cran.r-project.org/doc/manuals/r-release/R-admin.html#macOS)

A custom R configured without X11 and Tcl/Tk would produce the cleanest
theoretical runtime, but is not the best release tradeoff here. It replaces the
official signed/notarized CRAN runtime with a project-maintained compiler,
patch, SDK-floor, and security-update supply chain. The four-path profile keeps
the official R core and removes only dynamically loaded features that the
product does not require. Revisit a custom embedded R build only if the product
needs a formally minimized runtime across multiple releases and can own that
toolchain continuously.

## PyInstaller boundary

PyInstaller should remain the sole collector for Python/PyQt/Qt. It does not
make an independently copied general-purpose R framework application-specific.
Its spec documentation says explicitly added native binaries are searched for
further dependencies, and its macOS processing rewrites collected library
paths. The R framework is assembled and profiled by the repository's packaging
script after PyInstaller creates the app, then independently inspected and
signed. Keeping those responsibilities separate preserves #342's single Qt
collector contract.
[PyInstaller spec files: adding binary files](https://pyinstaller.org/en/stable/spec-files.html#adding-binary-files),
[PyInstaller macOS library-path behavior](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#macos)

## Concrete implementation contract

1. Add a named `profile_embedded_r_runtime` phase before external-library
   closure. Do not read `/opt/X11` at all and do not copy `/opt/R` Tcl/Tk.
   Keep the recursive closure mechanism for genuinely required non-Tcl/Tk
   `/opt/R/x86_64/lib` dependencies of the selected application packages; make
   that allow/deny distinction explicit rather than deleting all `/opt/R`
   support.
2. Before deletion, require the four expected paths to exist and record their
   path, architecture, SHA-256, install ID, and load commands in qualification
   evidence. This makes an upstream R layout change visible rather than silently
   weakening the package.
3. Remove the entire `library/tcltk` directory and the three other Mach-Os.
   Record the four feature exclusions (`tcltk`, `X11 device`, X11 data editor,
   X11-linked Cairo device) in the deployment manifest.
4. Run the existing thin-x86_64 normalization and relocation across every
   remaining R Mach-O. Reject every remaining `/opt/R`, `/opt/X11`, source
   framework, unresolved `@rpath`, missing target, duplicate identity, or wrong
   architecture.
5. Set or verify the packaged macOS bitmap policy is Quartz. Do not globally
   rewrite application plotting code merely to accommodate this packaging
   correction.
6. Sign only after profiling and relocation. No packaged byte may change after
   the explicit inner-to-outer signing pass.
7. Update contract tests that currently require `/opt/X11` copying. Tests should
   require the four-path exclusion policy, prohibit any `/opt/X11` copy source,
   and inject an unexpected fifth external binary to prove the packager fails
   closed.

## Acceptance evidence

The next native `macos-15-intel` qualification should retain evidence for all
of the following:

- Official R version/architecture and the source framework hash/provenance.
- The four pre-profile excluded paths with their hashes and load commands, and
  an exact post-profile exclusion manifest.
- A fresh hard-dependency audit proving no `tcltk` in `Depends`, `Imports`, or
  `LinkingTo`; suggested packages must not change that conclusion.
- `requireNamespace("tcltk", quietly = TRUE) == FALSE`, no loaded `tcltk`
  namespace, `capabilities("aqua") == TRUE`, and
  `getOption("bitmapType") == "quartz"` in the packaged R process.
- A standalone packaged `grDevices::png()` probe using the default device, plus
  the existing `svglite`/`rsvg` SVG and raster/PDF probes.
- The complete real-R golden workflow/edit/analyse/result/SVG/save/reopen smoke,
  with the same numeric and artifact hashes expected by #342.
- A complete Mach-O scan showing thin x86_64 only, zero `/opt/R` and
  `/opt/X11` load commands, zero non-system absolute dependencies, and every
  relative dependency resolved inside the app.
- Ad-hoc hardened-runtime signing inventory and strict/deep verification after
  the runtime is profiled, plus the normal LaunchServices launch and clean
  exit.
- A clean-runner assertion that `/opt/X11` is absent before launch. The current
  GitHub `macos-15` image manifest does not list XQuartz or X11, so success must
  not depend on an unadvertised runner component.
  [GitHub macOS 15 runner image manifest](https://github.com/actions/runner-images/blob/main/images/macos/macos-15-Readme.md)

The package should be rejected if any application analysis or required package
later gains a Tcl/Tk/X11 dependency. That is the guard that makes pruning a
product policy rather than a one-off deletion.
