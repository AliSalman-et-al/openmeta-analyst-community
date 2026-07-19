# Pre-dispatch audit of the target-native R build

**Status:** Implementation-gating research, 18 July 2026  
**Scope:** Issue #342, macOS Intel x64 direct build spike, with contracts that
must also hold for the later Apple Silicon target  
**Evidence baseline:** hosted run
[`29647357953`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29647357953)
at `08e2d7d2`, its downloaded evidence under
`build/hosted-evidence/29647357953-audit`, and the current uncommitted
classifier correction  
**Decision constraint:** Keep rpy2 in CFFI API mode, keep a self-contained
PyInstaller onedir app, and do not restore the independent integration-kit
producer/consumer architecture.

## Implementation update

The worktree implementation now encodes every pre-dispatch gate below: a
read-only relocation audit followed by audit-bound normalization, an explicit
file/symlink PyInstaller TOC, recursive native closure and duplicate checks,
API-only rpy2 bridge relocation, full unsigned dependency-graph validation,
stateful host-R isolation, truthful workflow/surface/LaunchServices evidence,
one explicit signing pass, direct-build provenance, archive byte binding, and
strict extracted-app verification. A macOS-only miniature PyInstaller 6.21
BUNDLE preflight proves the exact five CRAN aliases before the package script
may run. Windows contracts exercise the platform-independent state and mapping
logic; the hosted Intel job remains the required proof for macOS tools,
signatures, Cocoa surfaces, and target-native execution. This update records
implementation status only; it does not convert the research baseline below
into hosted evidence before that job passes.

## Decision

Do **not** dispatch another hosted build after only fixing the latest
`bin/R` classification error. The current direct spike will deterministically
fail later even with that correction.

The smallest robust design is still one linear target-native package job, but
the claim that an unmodified PyInstaller `Analysis.datas` directory can own the
whole R framework must be withdrawn. PyInstaller 6.21 can classify and process
ordinary Mach-O inputs, but CRAN's R framework is not an ordinary framework:
its framework executable `Versions/<version>/R` is a symlink to
`Resources/lib/libR.dylib`, and its native code has absolute install names.
PyInstaller's directory expansion, framework repair, and generic basename
relocation do not preserve that combination.

Use one **narrow macOS embedded-R adapter** in the same job:

1. authenticate and install the official target-native R package;
2. use installed R as the build tool to install the private package library and
   compile the locked rpy2 API bridge;
3. apply the explicit non-X11 profile;
4. make the staged R tree self-contained by normalizing only load-bearing
   symlinks and Mach-O references;
5. collect the already-relocatable R tree once, preserving an explicit
   file/symlink inventory instead of handing a directory to
   `Analysis.datas`;
6. let PyInstaller own Python, Qt, and the application, then apply the same
   bounded relocation contract to the final rpy2 bridge;
7. remove any PyInstaller-discovered duplicate R libraries, inspect the final
   dependency graph, sign once inside-out, run isolated packaged smokes, and
   inspect the archive.

This is a target adapter, not another assembler or intermediate product. It has
one input tree, one final app, no cross-job artifact, no offline Python cache,
and no second provenance protocol.

## What run 29647357953 proves

The run made useful progress and should be treated as evidence, not discarded.

- The authenticated R 4.6.1 Intel package installed successfully. Its installed
  and `ditto`-staged file identities and symlink inventories were identical.
- `Resources/bin/R` is an executable POSIX shell script;
  `Resources/bin/Rscript`, `Resources/bin/exec/R`, and
  `Resources/lib/libR.dylib` are x86_64 Mach-O files.
- The PPM binary package closure, HSROC 2.1.9 source exception, and local
  RCMetaR 0.1.2 installation all completed.
- The run stopped in the product profiler because its `is_macho()` test treated
  `otool -L` success as proof of Mach-O identity. The current worktree's
  four-byte Mach-O/fat-magic classifier is the correct bounded repair;
  PyInstaller itself uses a real Mach-O parser for Darwin classification
  ([PyInstaller 6.21 `bindepend.py`](https://github.com/pyinstaller/pyinstaller/blob/v6.21.0/PyInstaller/depend/bindepend.py#L1127-L1140)).

The evidence also exposes the next failures before another run:

- 17 fontconfig links in `Resources/fontconfig/fonts/conf.d` point absolutely
  to `/Library/Frameworks/R.framework/...`;
- `libR`, `libRblas`, `Rscript`, and `bin/exec/R` retain absolute
  `/Library/Frameworks/R.framework/Versions/4.6-x86_64/...` identities or
  imports; and
- HSROC's build command contains `/opt/R/x86_64` search roots and links with
  `-framework R` from the installed framework.

These are normal properties of the installed CRAN build, but they are not
portable product identities.

## Authoritative contracts and current result

### 1. File classification

**Contract.** A successful tool invocation is not a file-type contract. On
macOS, PyInstaller classifies with `macholib.MachO`; the Mach-O specification
also provides distinct thin and fat magic values. R's installation manual calls
the `R` command a shell-script front end, while the embedded runtime is
`libR` ([R Installation and Administration](https://cran.r-project.org/doc/manuals/r-release/R-admin.html),
[PyInstaller classifier source](https://github.com/pyinstaller/pyinstaller/blob/v6.21.0/PyInstaller/depend/bindepend.py#L1127-L1140)).

**Current result: FAIL at the committed baseline; PASS with the current
worktree correction.** The magic-byte implementation covers thin/fat and
byte-swapped forms and has focused tests. Keep it and run the profile tests
before touching CI.

### 2. Official framework staging and absolute symlinks

**Contract.** A versioned framework uses relative aliases through
`Versions/Current`; Apple treats framework layout as part of its bundle and
code-signing contract
([Apple framework anatomy](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPFrameworks/Concepts/FrameworkAnatomy.html),
[Apple bundle placement](https://developer.apple.com/documentation/bundleresources/placing-content-in-a-bundle)).
PyInstaller's ordinary directory expansion walks without following directory
links and emits files, not directory-link entries
([PyInstaller 6.21 `format_binaries_and_datas`](https://github.com/pyinstaller/pyinstaller/blob/v6.21.0/PyInstaller/building/utils.py#L434-L553)).
Its later symlink preservation accepts only relative file links whose target is
also collected
([PyInstaller 6.21 `toc_process_symbolic_links`](https://github.com/pyinstaller/pyinstaller/blob/v6.21.0/PyInstaller/building/datastruct.py#L377-L454)).

**Current result: DETERMINISTIC FAIL.** The spec adds the framework directory as
one `datas` tuple. That omits directory links such as `Versions/Current` and the
top-level `Resources` alias. The absolute fontconfig links cannot be preserved
as portable links. The final inspector requires the missing aliases exactly.

**Minimal robust fix.** Before collection, replace each fontconfig absolute
link with a verified relative link to the same file inside the staged
framework. Generate an explicit deterministic TOC containing every regular
file and every relative symlink, fail on any absolute/broken/escaping link, and
append that TOC after `Analysis` reclassification. Add a fixture reproducing
CRAN's directory links and fontconfig links and assert the final BUNDLE
inventory, not only the staged tree.

### 3. PyInstaller framework reconstruction

**Contract.** PyInstaller's framework repair recognizes a framework binary
only when the source shape is
`Name.framework/Versions/<version>/Name`; it then synthesizes
`Versions/Current`, the top-level executable, `Resources`, and selected
top-level directory links
([PyInstaller 6.21 framework collector](https://github.com/pyinstaller/pyinstaller/blob/v6.21.0/PyInstaller/utils/osx.py#L593-L757)).

**Current result: DETERMINISTIC FAIL.** CRAN R's
`Versions/4.6-x86_64/R` is a symlink to
`Resources/lib/libR.dylib`; the concrete binary is not named `R` and does not
match PyInstaller's recognized source shape. Therefore PyInstaller's repair
does not compensate for the links lost during directory expansion.

**Minimal robust fix.** Preserve CRAN's authenticated aliases explicitly. Do
not rename the official version directory and do not expect the generic
framework repair to invent R's topology. Test the exact five links already
required by `validate_r_framework_inventory()`.

### 4. Mach-O dependency relocation and duplicate R trees

**Contract.** PyInstaller recursively analyzes collected binaries. During
macOS collection it rewrites non-system load commands and dylib IDs to
`@rpath/<basename>`, removes existing rpaths, adds a destination-relative
`LC_RPATH`, and re-signs the changed file
([PyInstaller 6.21 binary processing](https://github.com/pyinstaller/pyinstaller/blob/v6.21.0/PyInstaller/building/utils.py#L107-L345),
[PyInstaller 6.21 Mach-O rewrite](https://github.com/pyinstaller/pyinstaller/blob/v6.21.0/PyInstaller/utils/osx.py#L437-L589)).
Apple documents `otool`, install names, `@rpath`, and `LC_RPATH` as the
load-bearing dyld contract
([Apple, Dynamic Library Identification](https://developer.apple.com/library/archive/documentation/DeveloperTools/Conceptual/DynamicLibraries/100-Articles/DynamicLibraryUsageGuidelines.html)).

**Current result: DETERMINISTIC FAIL.** Because staged R binaries refer to the
installed absolute framework, dependency analysis resolves the installed
copies and collects them by basename at the app's top level. The same libraries
are already present under the staged `R.framework`. BUNDLE processing then
normalizes both sets toward basename `@rpath` identities. The final inspector
will reject duplicate install identities or ambiguous resolution, and the
runtime can load a top-level `libR` while `R_HOME` points at a different copy in
the framework.

**Minimal robust fix.** Do not submit R's Mach-O files to generic dependency
discovery as an unqualified directory. Build an exact map from every staged
Mach-O's original path/install ID to its one final path. Before collection:

- allow only `/usr/lib` and `/System/Library` as external system roots;
- map `/Library/Frameworks/R.framework/...` to the exact staged member;
- map permitted `/opt/R/<arch>/lib/...` references only when one unambiguous
  target-native bundled member exists;
- reject `/opt/X11`, Homebrew, Conda, `/usr/local`, workspace, and unresolved
  roots; and
- rewrite internal dependencies to relative `@loader_path` paths (or one
  equivalently proven `@rpath` scheme), with collision detection.

Collect that already-closed tree without reclassification, then assert that no
second `libR`, `libRblas`, or other mapped R identity exists anywhere in the
app. A focused final adapter may relocate the analyzed rpy2 extension, but it
must consume the same path map; do not create a second recursive resolver.

### 5. R package native closure, X11, and `/opt/R`

**Contract.** Posit states that its macOS binaries are built using CRAN's
toolchains and system libraries and are compatible with CRAN R; a binary
repository does not eliminate the need to inspect the resulting native closure
([Posit binary packages](https://docs.posit.co/rspm/admin/serving-binaries.html)).
CRAN treats XQuartz/Tcl-Tk as optional macOS components
([CRAN R for macOS](https://mac.r-project.org/bin/macosx/)).

**Current result: PARTIAL PASS, THEN FAIL.** The package policy successfully
requires PPM binaries for normal dependencies and keeps HSROC as the source
exception. The profiler correctly removes the four known X11/Tcl surfaces and
fails if another remaining Mach-O still imports `/opt/X11`. It only records
remaining `/opt/R` imports, however; it neither resolves them nor requires all
remaining native package extensions to be x86_64. PyInstaller deliberately
applies strict architecture validation to extensions, not every shared library
([PyInstaller architecture validation](https://pyinstaller.org/en/stable/feature-notes.html#architecture-validation-during-binary-collection)).

**Minimal robust fix.** After profiling and before freezing, inventory every
remaining Mach-O under R, require exactly the target architecture, and run the
same dependency-map closure described above. Require every app-needed R
namespace plus a representative Quartz PNG in an in-process isolated probe.
Treat the HSROC compiler warnings as upstream quality evidence, not packaging
failure; they do not justify weakening the native checks.

### 6. Build-tool R versus embedded R

**Contract.** The official R framework is installed at
`/Library/Frameworks/R.framework`; rpy2 honors an explicit `R_HOME` for
embedding, but R command-line front ends may use their installed framework
identity. The embedded product must ultimately report the private bundle path
([R macOS framework installation](https://cran.r-project.org/doc/manuals/r-release/R-admin.html#Installing-R-under-macOS),
[rpy2 situation source](https://github.com/rpy2/rpy2/blob/RELEASE_3_6_6/rpy2-rinterface/src/rpy2/situation/__init__.py)).

**Current result: MISLABELLED, NOT YET ISOLATED.** The staged `Rscript` evidence
reports `/Library/Frameworks/R.framework/Resources`, and R emits `ignoring
environment value of R_HOME` during source installation. The explicit library
destination still installs packages into the staged private library, but these
commands are tests against installed build-tool R, not proof that staged R is
independent.

**Minimal robust fix.** State this boundary honestly: use authenticated
installed R to build the private library and API bridge, then prove the final
embedded tree separately. After PyInstaller and relocation, temporarily make
the installed host framework unavailable (with a fail-safe restoration trap)
for runtime probe and analysis smoke. Also unset `DYLD_*`, user R profiles, and
user libraries. A successful in-process probe must report only paths inside the
app.

### 7. rpy2 API bridge compatibility and linking

**Contract.** rpy2 3.6.7 is the aggregate release updated for R 4.6, whose
previously visible non-API C functions are now hidden. This repository's
official split tuple is `rpy2==3.6.7`, `rpy2-rinterface==3.6.6`, and
`rpy2-robjects==3.6.5`; `RPY2_CFFI_MODE=API` must be set before build/import,
and `ANY` is insufficient because it may fall back to ABI
([rpy2 3.6.7 release notes](https://rpy2.github.io/doc/v3.6.x/html/changes.html#release-3-6-7),
[rpy2 openrlib source](https://github.com/rpy2/rpy2/blob/RELEASE_3_6_6/rpy2-rinterface/src/rpy2/rinterface_lib/openrlib.py)).

**Current result: BUILD CONTRACT PASS; FINAL LINK CONTRACT FAIL.** The spike
hash-checks and rebuilds the locked `rpy2-rinterface` sdist, requires API mode,
rejects the ABI module, checks x86_64, and runs an in-process calculation. The
resulting extension nevertheless links through the installed R framework, and
generic PyInstaller processing redirects it toward a basename-level duplicate.

**Minimal robust fix.** Assert the exact three distribution versions before
freezing. After final placement, rewrite the API bridge's one R dependency to
the unique bundled `libR` using the same closure map, then verify `otool -L`,
architecture, API-only mode, and an in-process calculation with host R hidden.
There must be exactly one API bridge and no `_rinterface_cffi_abi` file.

### 8. uv environment stability

**Contract.** `uv run` checks and updates the project environment by default;
`--no-sync` runs without changing it
([uv running commands](https://docs.astral.sh/uv/concepts/projects/run/)).

**Current result: AVOIDABLE RISK.** The spike rebuilds the rpy2 API extension
from source and later executes `uv run aqt ...`. The installed version matches
the lock, so replacement is not certain, but a build must not rely on uv's
freshness heuristic to preserve a custom native build.

**Minimal robust fix.** Install Qt before rebuilding rpy2, or use the selected
environment's executable/`uv run --no-sync`. Record the API bridge hash and
`otool -L` immediately after build and require the identical source hash before
PyInstaller analysis.

### 9. Runtime bootstrap, threading, and API lifecycle

**Contract.** Embedded R is designed and tested on the main thread; rpy2
initialization is one-time and ending embedded R is irreversible
([R Extensions, threading issues](https://cran.r-project.org/doc/manuals/r-release/R-exts.html#Threading-issues),
[rpy2 embedded interface](https://rpy2.github.io/doc/v3.6.x/html/rinterface.html#rpy2.rinterface.initr)).

**Current result: PASS, with a test gap.** `configure_bundled_r_environment()`
sets bundle-relative `R_HOME`, the private library, startup isolation, API mode,
and locale before the probe's first rpy2 import; frozen bootstrap rejects a
non-main thread and later identity changes. The analysis gateway serializes R
calls. The final native smoke is the required proof, but it has not yet run on
the direct artifact.

**Minimal robust fix.** Keep these controls. Add one frozen-seam regression
that imports through the real application entry point and proves no rpy2 module
is present before bootstrap. Do not call `endr()` during normal GUI teardown.

### 10. Smoke completion and timeout diagnosis

**Contract.** A smoke must distinguish application success, clean process
exit, and watchdog termination. A timeout is evidence of missing lifecycle
completion, not permission to increase the duration.

**Current result: PARTIAL PASS.** `run_bounded_process.py` owns a POSIX process
group and terminates it reliably at 900 seconds. That prevents an infinite CI
job, but the runtime-probe and analysis phases append to the same stdout/stderr
files, and `start_automation_smoke()` closes the window without explicitly
draining deferred deletes, calling `app.quit()`, or recording checkpoints
around each teardown operation. The earlier hang after `saved settings` cannot
therefore be localized to close handling, Qt teardown, R teardown, or Python
shutdown.

**Minimal robust fix.** Give runtime probe and analysis smoke separate logs and
short phase-specific bounds. Record markers before/after window close,
deferred-delete drain, `app.quit()`, function return, and process exit. Require
no remaining top-level Qt windows. Preserve the process-group watchdog and
hang trace; do not raise the 900-second ceiling.

### 11. Signing order and product contents

**Contract.** Apple requires nested code to be signed before its containing
bundle; sign inside-out and the outer app last. `--deep` is useful for
verification, not signing. Relocation after signing invalidates signatures
([Apple Code Signing Guide](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/Procedures/Procedures.html),
[Apple nonstandard code structures](https://developer.apple.com/documentation/xcode/embedding-nonstandard-code-structures-in-a-bundle)).

**Current result: ORDER PASS AFTER RELOCATION, WITH REDUNDANT MUTATION.**
`sign_macos_app.py` inventories Mach-O files, signs deepest first, signs nested
bundles, signs the app last, and verifies each plus the deep app. The spike then
signs the outer app a second time. That second command is unnecessary and makes
the recorded signing action less authoritative.

**Minimal robust fix.** Complete every symlink and Mach-O mutation first; remove
debug-only `.dSYM` bundles from the release profile; invoke the explicit signer
once; verify once; hash the post-sign native inventory; and prohibit any later
mutation. Developer ID signing/notarization remains a protected future job.

### 12. Manifest, archive, and promotion

**Contract.** The promoted archive, not the pre-archive app directory, must
preserve executable modes, relative symlinks, signatures, identities, and
qualification evidence. The release candidate must be promoted without a
rebuild.

**Current result: NOT IMPLEMENTED IN THE DIRECT SPIKE.** The script runs the
deployment inspector, creates a ZIP with `ditto`, and hashes it. It does not run
the existing archive inspector, embed one direct-build manifest, or verify an
extract-and-launch seam. The legacy evidence writer still requires an
integration-kit manifest, so it cannot honestly describe the direct build.

**Minimal robust fix.** Define one direct target-build manifest and make the
archive/evidence commands accept exactly one delivery identity. Embed the
deployment manifest, profile, runtime probe, smoke result/logs, signing
inventory, source/input hashes, PPM archive inventory, and final archive hash.
Inspect an extracted ZIP and run a short runtime probe from that extracted
artifact before promotion. Do not synthesize a fake kit manifest.

## Required changes before the next hosted dispatch

Implement in this order so each failure boundary is testable locally or by a
single static macOS phase:

1. **Land the real Mach-O classifier** and its thin/fat/script/arbitrary-data
   tests.
2. **Add a static staged-tree audit** that inventories every link and Mach-O,
   requires target architecture, classifies every dependency, and emits the
   exact relocation map without mutating anything.
3. **Implement one bounded embedded-R normalizer** from that map: relative
   fontconfig links, relative internal Mach-O imports, collision rejection,
   non-X11 profile, and optional `.dSYM` removal.
4. **Replace the directory `Analysis.datas` input** with an explicit
   file/symlink TOC that bypasses reclassification for the already-normalized R
   tree. Add a spec-level fixture that proves the official five-link topology.
5. **Stabilize the API bridge**: avoid later uv sync, record its hash, relocate
   its R edge to the unique bundled target, reject ABI fallback and duplicates.
6. **Add a post-PyInstaller static gate before signing**: exact framework
   aliases, one R identity, all x86_64, all dependencies uniquely resolved in
   app/system, no forbidden roots, and no host-R duplicate.
7. **Improve smoke observability and teardown** with separate phase logs,
   explicit Qt teardown markers, and shorter phase bounds; run with installed R
   temporarily unavailable.
8. **Sign exactly once after all mutations**, then inspect the signed app.
9. **Archive and re-inspect the extracted ZIP** with a direct-build manifest.
10. Only after this static matrix is green, dispatch the macOS x64 spike. If it
    passes twice, replace the issue #342 macOS x64 package path; do not delete
    the fallback until Windows x64 is also green.

## Pre-dispatch static validation matrix

| Gate | Command or fixture | Required assertion | Current status |
|---|---|---|---|
| Profiler classification | focused profile pytest | script is DATA; all thin/fat magics are Mach-O | Worktree pass expected; run required |
| Official input | installed evidence fixture | exact hash/signing ID; canonical links; x86_64 native trio | Hosted pass |
| Link closure | staged-tree audit fixture | every link relative, non-broken, non-escaping | Fail: absolute fontconfig links |
| Native architecture | recursive staged Mach-O audit | every loadable native file is exactly x86_64 | Not enforced |
| Dependency classification | relocation-map fixture | each edge is system or one unique bundled target | Fail: absolute R and `/opt/R` edges unmapped |
| Product profile | profile fixture plus hosted shape | only four expected optional surfaces removed; no remaining X11 edge | Partial pass; rerun after classifier |
| rpy2 build identity | exact split-version/API test | 3.6.7/3.6.6/3.6.5, API bridge only, stable hash | Partial pass; hash stability missing |
| Spec collection | miniature CRAN R.framework BUNDLE test | exact five aliases, no flattened directory links | Deterministic fail with directory `datas` |
| Duplicate identity | synthetic absolute-libR fixture | one final libR/install ID; no top-level duplicate | Deterministic fail with generic analysis |
| Final load graph | inspector contract test | every non-system edge resolves uniquely inside app | Inspector exists; artifact not reached |
| Host isolation | packaged probe with host framework hidden | reported R home/library/libR/API bridge all inside app | Not run |
| Main-thread lifecycle | frozen entry-point regression | bootstrap precedes rpy2; one main-thread init | Mostly covered; entry-point seam missing |
| Smoke termination | teardown-marker test | close, deferred delete, quit, return, process exit all observed | Incomplete diagnostics |
| Signing | signing-plan tests | all native code signed inside-out once; app last; strict verify | Pass logic; redundant outer re-sign remains |
| Archive | archive fixture and extracted probe | symlinks/modes/signatures/evidence preserved | Not run in spike |
| Provenance | direct-build manifest contract | one delivery identity; no fake kit metadata | Not implemented |

No hosted packaging run should be dispatched while any row marked
**Deterministic fail** remains. The first new hosted run should test the complete
post-normalization collection, signing, isolated runtime probe, native analysis,
and extracted archive path, rather than reveal one more known boundary at a
time.

## Speculative risks that should not block the next run

The following deserve evidence, but are not currently proven defects:

- harmless textual `/Library/Frameworks/R.framework` values in unused command
  wrappers or build configuration, provided no runtime probe, symlink, or
  Mach-O load command uses them;
- HSROC's upstream C++ mismatched-delete warnings, because the package builds
  and loads but the warnings concern package code quality rather than artifact
  relocation;
- further pruning of R documentation, headers, examples, or recommended
  packages beyond `.dSYM` and the four approved optional surfaces; and
- future Developer ID/notarization behavior, because the current gate is
  ad-hoc hardened-runtime-compatible signing and credentials are intentionally
  deferred.

Do not expand the normalizer into a textual search-and-replace engine or a
general runtime pruner to address these speculative risks. Runtime identity,
native closure, signing, and real packaged analysis are the authoritative
product gates.

## Bottom line

The repeated failures are not random. They result from treating three different
contracts as if they were one:

- CRAN owns the installed R framework;
- PyInstaller owns ordinary Python/Qt collection; and
- RC MetaStudio must own the narrow boundary that turns CRAN's absolute,
  nonstandard R framework into a private relocatable embedded subsystem.

Keeping that boundary small and explicit is simpler than both failed extremes:
an independent integration-kit supply chain on one side, and blind whole-tree
`Analysis.datas` collection on the other. The next CI run should occur only
after its static contracts prove that PyInstaller cannot flatten, duplicate, or
silently reconnect the embedded R subsystem to the build host.
