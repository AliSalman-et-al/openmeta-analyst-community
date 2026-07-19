# Installed macOS R.framework and direct PyInstaller collection

**Status:** Research finding, 18 July 2026  
**Scope:** Issue #342's repeated macOS x64 direct-R spike failure, with the
same rules intended for Apple Silicon  
**Decision constraint:** Keep rpy2 in CFFI API mode and keep a self-contained
PyInstaller onedir application.

## Executive decision

The current failure is an invalid test, not evidence that the official R
installer produced a damaged framework. In an official CRAN macOS R
installation:

- `Resources/bin/R` is a **POSIX shell front-end**;
- `Resources/bin/Rscript` is a Mach-O executable;
- `Resources/bin/exec/R` is the Mach-O R executable; and
- `Resources/lib/libR.dylib` is the Mach-O library embedded by rpy2.

R's own installation manual calls `R` a “shell-script front-end,” and the R
source tree generates it from `src/scripts/R.sh.in`
([R Installation and Administration](https://github.com/wch/r-source/blob/trunk/doc/manual/R-admin.texi),
[R source scripts](https://svn.r-project.org/R/trunk/src/scripts/)). The
official R 4.6.1 Intel package inspected for this issue contains a 9,263-byte
`Resources/bin/R` beginning with `#!/bin/sh`; the installed runner therefore
behaves exactly as R specifies.

Delete the assertion that runs `lipo` on `Resources/bin/R`. Do not replace it
with another guessed filename rule. Validate executable architecture only for
files that are actually Mach-O, and separately validate the `R` wrapper as an
executable shell script. The immediate target-native checks are:

```text
Resources/bin/R                  executable shell script
Resources/bin/Rscript            target-native Mach-O
Resources/bin/exec/R             target-native Mach-O
Resources/lib/libR.dylib         target-native Mach-O
Versions/Current                 relative link to the installed version root
Versions/Current/R               link to Resources/lib/libR.dylib
Resources                        link through Versions/Current
```

Preserve the installed framework root and its symlinks as a unit. Do not rename
`Versions/4.6-x86_64` to `Versions/4.6`, synthesize a different framework, or
use archive extraction on Windows as the authority for POSIX file type and
link metadata. CRAN's current manual explicitly permits architecture-qualified
version directories such as `4.6-x86_64`, while Apple's framework rules make
`Versions/Current` the stable level of indirection
([R 4.6.1 macOS installation](https://rstudio.github.io/r-manuals/r-admin/Installing-R-under-macOS.html),
[Apple framework bundle placement](https://developer.apple.com/documentation/bundleresources/placing-content-in-a-bundle)).

## Why archive inspection and installed inspection appeared to disagree

There is no installer transformation from a Mach-O `bin/R` into a script. The
official `.pkg` is a XAR container whose component payloads are gzip-compressed
CPIO archives. General-purpose archive tools running on Windows can extract the
bytes, but they are not an authoritative view of macOS ownership, modes,
symlinks, framework aliases, or Installer behavior.

Inspection of the exact pinned R 4.6.1 x86_64 artifact
(`SHA-256 612bb00cb4c627721d6d80b0f5224227c0fcdefb4a5b6c917511480361c16571`)
showed that its `R-fw.pkg` payload already contains the `#!/bin/sh` `bin/R`.
Its `postflight` script creates `/usr/local/bin/R` and
`/usr/local/bin/Rscript` convenience links, refreshes the font cache when
present, and fixes framework ownership/permissions; it does not rewrite
`Resources/bin/R`. The package can be independently expanded with Apple's own
`pkgutil --expand-full` before installation. CRAN publishes the Intel and arm64
installers separately and describes both as signed, notarized packages
containing an R framework
([CRAN R for macOS](https://mac.r-project.org/bin/macosx/)).

The earlier “archive-level Mach-O” conclusion should therefore be discarded.
The installed runner and R's source/manual agree, and the payload bytes agree
when inspected without conflating `bin/R` with `bin/exec/R` or `bin/Rscript`.

## Authoritative framework topology

R uses Apple's versioned-framework convention. The stable public paths are
`R.framework/Resources` and `R.framework/R`; both resolve through
`Versions/Current`. R's macOS FAQ says `R.home()` intentionally resolves via
the top-level `Resources` link rather than exposing a version-specific path,
and warns against forcing a versioned `R_HOME`
([R for macOS FAQ, section 10.10](https://mac.r-project.org/bin/macosx/RMacOSX-FAQ.html#Why-is-R_002ehome_0028_0029-in-the-R-framework-not-versioned_003f)).
Apple likewise requires top-level framework content to be symlinks into
`Versions/Current` and warns that malformed top-level content causes signing
problems
([Apple framework anatomy](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPFrameworks/Concepts/FrameworkAnatomy.html),
[Apple bundle placement](https://developer.apple.com/documentation/bundleresources/placing-content-in-a-bundle)).

For current CRAN builds, do not hard-code the directory below `Versions`.
Resolve `Versions/Current` after installation. Intel and arm64 have distinct
official packages, minimum systems, and version-root names; build each product
on its target-native runner. PyInstaller is not a cross-compiler
([CRAN R for macOS](https://mac.r-project.org/bin/macosx/),
[PyInstaller overview](https://pyinstaller.org/en/stable/)).

## What rpy2 actually needs

The locked rpy2 interface source is unambiguous:

1. `rpy2.situation.get_r_home()` returns `R_HOME` first and only invokes
   `R RHOME` when that environment variable is absent.
2. On Darwin, the ABI-mode loader path is `$R_HOME/lib/libR.dylib`.
3. In API mode, `openrlib` imports `_rinterface_cffi_api` and uses its linked
   C API rather than calling `ffi.dlopen()` itself.
4. On non-Windows systems, rpy2 opportunistically invokes
   `$R_HOME/bin/Rscript` to query `LD_LIBRARY_PATH`; failure is caught and
   yields an empty value.

These behaviors are in the exact
[`RELEASE_3_6_6` `openrlib.py`](https://github.com/rpy2/rpy2/blob/RELEASE_3_6_6/rpy2-rinterface/src/rpy2/rinterface_lib/openrlib.py)
and
[`situation/__init__.py`](https://github.com/rpy2/rpy2/blob/RELEASE_3_6_6/rpy2-rinterface/src/rpy2/situation/__init__.py)
used by this repository. The rpy2 documentation also requires R's compiled
libraries at runtime and its headers when building API mode
([rpy2 overview](https://github.com/rpy2/rpy2/blob/RELEASE_3_6_6/doc/overview.rst)).

Consequently, `bin/R` is not the native library rpy2 embeds and must never be
an architecture gate. The release-critical runtime contract is:

- set bundle-relative `R_HOME` before the first rpy2 import;
- ship the exact matching `libR.dylib`, R home resources, base/recommended
  packages, required private packages, and their native closure;
- build and ship only `_rinterface_cffi_api` for the same OS/CPU/Python/R
  tuple;
- ensure the API bridge's final Mach-O load command resolves to the private
  framework; and
- prove an in-process calculation and required package loads in the frozen
  executable.

The application does not need a working packaged `R` command-line front-end to
embed R. If no product feature spawns R or Rscript, command-line launchers
should not define package success. If `Rscript` remains because rpy2 probes it,
that probe must not be treated as proof of the loaded in-process library; the
frozen runtime probe must report the private `libR` path independently.

## Simplest supported PyInstaller path

Use PyInstaller's collection model rather than another framework assembler:

1. Install and authenticate the official target-native R package on the native
   runner.
2. Preserve the official `R.framework` root, including its real
   `Versions/Current` target. Apply only the already-decided non-X11 product
   profile before collection.
3. Build the locked rpy2 API extension against that installed R.
4. Add the preserved framework tree once to `Analysis` at destination
   `R.framework`.
5. Let PyInstaller 6.21 inspect every input file and automatically reclassify
   Mach-O files from DATA to BINARY, recursively analyze their dependencies,
   restore framework links, place the framework under `Contents/Frameworks`,
   and cross-link resources as required.
6. Set `R_HOME` to
   `Contents/Frameworks/R.framework/Resources` in the application's earliest
   runtime bootstrap, before importing rpy2.
7. Inspect and smoke the final app, then sign it. Do not mutate the framework
   after final signing.

This is not an inferred feature. PyInstaller 6.21's `Analysis.assemble()`
explicitly performs “Automatic binary vs. data reclassification” with
`classify_binary_vs_data()`, runs dependency analysis on the resulting binary
TOC, then calls `collect_files_from_framework_bundles()` on macOS
([PyInstaller 6.21 `build_main.py`](https://github.com/pyinstaller/pyinstaller/blob/v6.21.0/PyInstaller/building/build_main.py)).
Its macOS bundle builder treats a nested `.framework` as one binary entity and
places it under `Contents/Frameworks`
([PyInstaller 6.21 `osx.py`](https://github.com/pyinstaller/pyinstaller/blob/v6.21.0/PyInstaller/building/osx.py)).
The 6.0+ release notes document framework preservation, `Versions/Current`
repair, binary/resource separation, and symlink cross-linking
([PyInstaller change log](https://github.com/pyinstaller/pyinstaller/blob/v6.21.0/doc/CHANGES.rst)).

Therefore no handwritten filename classifier is needed. Adding the entire
tree as `datas` is intentional: PyInstaller determines content type. The final
inspector remains an independent fail-closed check; it should not duplicate
collection or relocation.

## Exact pre-staging inspection on a GitHub macOS runner

Run this immediately after `installer` and save the output as CI evidence
before any copy, profile, or PyInstaller step:

```bash
set -euo pipefail

pkg="${RCMS_R_PKG:?set RCMS_R_PKG to the authenticated installer path}"
fw=/Library/Frameworks/R.framework
current_link="$(readlink "$fw/Versions/Current")"
version_root="$fw/Versions/$current_link"
home="$fw/Resources"
evidence="$RUNNER_TEMP/installed-r-framework.txt"

{
  echo '== host =='
  sw_vers
  uname -a
  uname -m

  echo '== package signature =='
  pkgutil --check-signature "$pkg"

  echo '== canonical links =='
  ls -la "$fw" "$fw/Versions" "$version_root"
  printf 'Versions/Current -> %s\n' "$current_link"
  printf 'Resources -> %s\n' "$(readlink "$fw/Resources")"
  printf 'R -> %s\n' "$(readlink "$fw/R")"
  printf 'version R -> %s\n' "$(readlink "$version_root/R")"

  echo '== installed file types =='
  file \
    "$home/bin/R" \
    "$home/bin/Rscript" \
    "$home/bin/exec/R" \
    "$home/lib/libR.dylib"
  head -n 2 "$home/bin/R"

  echo '== native architectures =='
  lipo -archs "$home/bin/Rscript"
  lipo -archs "$home/bin/exec/R"
  lipo -archs "$home/lib/libR.dylib"

  echo '== R identities =='
  "$home/bin/R" RHOME
  "$home/bin/Rscript" -e \
    'cat(R.home(), "\n", R.version$arch, "\n", R.version.string, "\n", sep="")'

  echo '== Mach-O load commands =='
  otool -L "$home/bin/Rscript"
  otool -L "$home/bin/exec/R"
  otool -D "$home/lib/libR.dylib"
  otool -L "$home/lib/libR.dylib"

  echo '== all framework symlinks =='
  find "$fw" -type l -exec sh -c \
    'for p do printf "%s -> %s\n" "$p" "$(readlink "$p")"; done' sh {} +
} 2>&1 | tee "$evidence"
```

For installer-script evidence, use Apple's package tool rather than 7-Zip:

```bash
expanded="$RUNNER_TEMP/r-pkg-expanded"
rm -rf "$expanded"
pkgutil --expand-full "$pkg" "$expanded"
find "$expanded" -path '*/Scripts/*' -type f -print -exec sed -n '1,220p' {} \;
```

After staging with `ditto`, run the same `readlink`, `file`, `lipo`, and
`otool` commands against the staged root and diff the symlink inventory. A
failure should print both inventories. This separates acquisition facts from
product-profile and collection facts.

## Acceptance checks that avoid brittle assumptions

Use semantic checks, not a list that says every executable path is Mach-O:

- exact installer hash plus `pkgutil --check-signature`;
- official framework link topology preserved through `Versions/Current`;
- `bin/R` executable, starts with a valid shell shebang, and reports the
  expected `RHOME` before staging;
- every file that `file` identifies as Mach-O is target-native, with no
  opposite-architecture slice;
- final Mach-O dependencies contain no external `/Library/Frameworks/R.framework`,
  `/opt/R`, XQuartz, Homebrew, Conda, or build-workspace path;
- exactly one API bridge and no ABI bridge;
- runtime-reported `R_HOME`, loaded `libR`, R version/architecture, rpy2 mode,
  and package library all reside in the final app;
- representative `.rcms` packaged analysis and clean exit pass; and
- the archived `.app` preserves symlinks and passes `codesign --verify
  --strict --deep` for the current ad-hoc gate.

Intel and Apple Silicon use the same logic and different official inputs. The
architecture expectation comes from the job target (`x86_64` or `arm64`), not
from hard-coded version-directory or launcher names.

## Actionable conclusion for the current spike

The next change should be small:

1. remove `require_x64 "$resources/bin/R"`;
2. replace it with an executable/shebang check for `bin/R`;
3. keep native checks for `bin/Rscript`, `bin/exec/R`, and `lib/libR.dylib`;
4. stop renaming the official version root and instead copy the complete
   framework while preserving `Versions/Current`;
5. feed that tree directly to the existing PyInstaller `Analysis.datas` input;
6. make the frozen in-process rpy2/private-libR probe the success criterion;
   and
7. retain the independent final native-closure, signing, and packaged-analysis
   gates.

This removes the false failure and one topology rewrite at the same time. If
the next run fails, it will finally be testing PyInstaller's real framework
collection or the frozen embedded-R seam rather than an invented file-type
contract.
