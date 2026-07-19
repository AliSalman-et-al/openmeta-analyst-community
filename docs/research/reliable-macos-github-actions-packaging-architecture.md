# A simpler, reliable macOS packaging architecture on GitHub Actions

**Status:** Research recommendation, 19 July 2026
**Scope:** Python 3.11 + PyQt6/Qt 6 + PyInstaller 6.21 + private R 4.6.1 +
rpy2 3.6.6 API mode; unsigned native Intel and Apple Silicon artifacts now,
with Developer ID signing and notarization later
**Evidence baseline:** failed runs
[29682212436](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29682212436)
and
[29682212551](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29682212551)

## Executive recommendation

Keep GitHub-hosted native macOS runners. The absence of a developer-owned Mac
is inconvenient for interactive debugging, but it is not the architectural
problem. The current process is brittle because it has:

1. two independent macOS package implementations (the feasibility application
   and the production package);
2. two owners that both transform the R native dependency graph (the embedded-R
   adapter and PyInstaller); and
3. gates that sometimes prove implementation assumptions rather than user
   outcomes.

Replace those with one production command, one matrix workflow, and two
explicit product layers:

```text
official, authenticated R installer + pinned R package archives
    -> private, architecture-specific R runtime layer
       (adapt once, close native graph once, qualify once)

locked Python environment + PyQt6 + Qt + application
    -> PyInstaller-owned Python/Qt .app skeleton

.app skeleton + private R layer + rpy2 API bridge
    -> deterministic final assembly
    -> one final native-graph inspection
    -> packaged application smoke
    -> sign inside-out (ad hoc now, Developer ID later)
    -> archive, extract, and smoke the exact archive
```

The critical ownership rule is:

> **PyInstaller owns Python and Qt. The embedded-R assembler owns R and the
> rpy2-to-R edge. They do not both collect or rewrite the same R binaries.**

The smallest durable near-term change is to assemble the already-qualified R
framework and target-native rpy2 API extension into the `.app` **after**
PyInstaller has completed the Python/Qt bundle. This avoids asking
PyInstaller's generic recursive binary collector to understand a complete R
distribution while a second tool simultaneously substitutes and relocates that
distribution. The app is signed only after final assembly, which is also the
right seam for future Developer ID signing.

Do not replace GitHub-hosted runners with a self-hosted Mac, build R from
source, adopt a universal2 bundle, or change packaging engines merely to escape
the present failures. None addresses the duplicate ownership and duplicate
pipeline.

## What the latest failures actually show

### The feasibility jobs fail at a shared ownership boundary

Both `macos-arm64` and `macos-x64` jobs in run 29682212436 passed native R
installation, locked Python sync, the rpy2 API rebuild, Qt setup, and
architecture preflight. Both then failed inside PyInstaller analysis. The
repository's post-`Analysis` filter found R binaries sourced from the runner's
system framework, for example:

```text
/Library/Frameworks/R.framework/Versions/4.6/Resources/lib/libRblas.dylib
/Library/Frameworks/R.framework/Versions/4.6-x86_64/Resources/lib/libRblas.dylib
```

and rejected them because they were not members of the separately staged
framework.

This is not an ARM-only or Intel-only defect. It is the deterministic result of
one tool relocating a staged R graph and another tool recursively resolving the
rpy2 bridge and R dylib graph against the build host.

PyInstaller documents that entries classified as binaries are searched for
further binary dependencies. Since PyInstaller 6 it also inspects files passed
as both `datas` and `binaries`, reclassifies native files, and subjects them to
platform binary processing. Labeling a complete `R.framework` TOC as `DATA`
therefore does **not** establish a boundary around R
([spec files](https://pyinstaller.org/en/stable/spec-files.html#adding-binary-files),
[PyInstaller changes](https://pyinstaller.org/en/stable/CHANGES.html)).

Filtering `a.binaries` after `Analysis` is too late to make the dependency walk
not happen, and it leaves correctness dependent on PyInstaller's evolving
resolution and rewrite behavior. More path predicates cannot make two owners
into one.

### The production job fails on a proxy, not a product requirement

The Intel package job in run 29682212551 stopped earlier because
`capabilities("tcltk")` was true after the product profile expected it to be
false.

R defines this capability as whether the `tcltk` package is operational. It is
not an inventory assertion saying that the optional Tcl/Tk/X11 installer
component has been bundled
([R `capabilities`](https://stat.ethz.ch/R-manual/R-devel/library/base/html/capabilities.html)).
CRAN separately says its Tcl/Tk X11 libraries and Texinfo installer components
are optional and can be omitted; X11 use requires XQuartz
([R for macOS](https://mac.r-project.org/bin/macosx/)).

The artifact requirement is “do not ship unused Tcl/Tk/X11 payloads.” Prove it
with an inventory denylist, native dependency closure, absence of XQuartz
edges, and the application's real plotting workflows. Do not require an
unrelated runtime capability bit to have a chosen value.

### The duplicate paths are already diverging

The repository currently has approximately:

- 1,946 lines in the native feasibility driver;
- 986 lines in the Intel package shell script;
- 639 lines in the embedded-R adapter; and
- separate feasibility and production PyInstaller specs and workflows.

The feasibility path copies an installed framework; production extracts an
authenticated installer component. Their phase order, profiles, assertions,
and PyInstaller inputs differ. A green feasibility path would therefore not be
proof that the production command works. A feasibility test is valuable only
when it invokes the production implementation with a smaller entry point or
stops at an explicit production phase.

## Constraints imposed by upstream tools

### Build both architectures natively

GitHub provides `macos-15-intel` as Intel x64 and `macos-15` as arm64. Hosted
images are updated regularly, and the exact image/software inventory is linked
from each job log
([GitHub-hosted runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners),
[runner image lifecycle](https://docs.github.com/actions/concepts/runners/github-hosted-runners)).

PyInstaller is not a cross-compiler. It builds on the active platform and its
macOS target-architecture option validates or thins compatible inputs; it does
not manufacture a missing architecture slice
([PyInstaller overview](https://github.com/pyinstaller/pyinstaller),
[macOS options](https://pyinstaller.org/en/stable/usage.html#macos-specific-options)).

Therefore keep two thin native builds:

| Artifact | Runner | Required native architecture |
| --- | --- | --- |
| macOS Intel | `macos-15-intel` | `x86_64` |
| macOS Apple Silicon | `macos-15` | `arm64` |

Record the exact runner image version and Xcode version in provenance. Pin
application dependencies and input archives; do not pretend a moving hosted
image label is byte-for-byte reproducible.

### rpy2 API mode is a compiled product input

rpy2 API mode is not merely a runtime environment flag. It needs R headers and
libraries during compilation, and `RPY2_CFFI_MODE=API` selects the compiled
CFFI API bridge. rpy2 3.6.6 uses the same API-first behavior on macOS documented
for that release
([rpy2 installation](https://rpy2.github.io/doc/v3.6.x/html/overview.html#installation),
[rpy2 3.6.6 changes](https://rpy2.github.io/doc/v3.6.x/html/changes.html)).

Build the bridge on each target runner against the exact private R runtime that
will be assembled into that artifact. Before app assembly, require:

- exactly one `_rinterface_cffi_api` extension and no ABI extension;
- the expected thin architecture;
- exactly one R load edge;
- that edge rewritten to the final app-relative private `libR`; and
- a real in-process calculation against the private runtime.

Do not rebuild rpy2 against system R and try to repair an arbitrary discovered
system graph later.

### The R framework is a product subtree, not a bag of dylibs

The official CRAN packages are signed and notarized and publish distinct arm64
and Intel frameworks. They also document different OS floors and toolchains
for the two architectures
([R for macOS](https://mac.r-project.org/bin/macosx/)).

Continue extracting the authenticated framework component without installing
it globally. Treat the whole private framework—launchers, configuration,
standard library, product R library, native modules, aliases, and dylibs—as one
versioned layer. Adapt and inspect it before application assembly. Never use a
runner's `/Library/Frameworks/R.framework`, `/opt/R`, Homebrew, user library, or
XQuartz installation as release payload.

### Final layout and signing require a final assembly boundary

Apple assigns frameworks and dylibs to `Contents/Frameworks` and warns that
incorrect code placement can create difficult signing and notarization
failures
([placing content in a bundle](https://developer.apple.com/documentation/bundleresources/placing-content-in-a-bundle)).
Apple's signing guidance requires nested code to be signed from the inside out;
the outer application is signed last, after no further mutation
([code signing tasks](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/Procedures/Procedures.html)).

That makes post-PyInstaller final assembly a natural boundary, not a hack:

1. PyInstaller produces the standard app skeleton and owns its Python/Qt code.
2. The assembler installs the prequalified private R framework and API bridge
   into their canonical final locations.
3. A final graph inspector proves the complete assembled product.
4. All nested code is signed, then the outer app.

Use ad-hoc signing now to exercise the same ordering. Later substitute the
Developer ID identity, hardened-runtime entitlements, secure timestamp,
notarization, and stapling without changing how the app is assembled.

## Target build architecture

### Phase 1: immutable acquisition

Inputs are explicit and architecture-specific:

- official R installer URL, version, component identity, and SHA-256;
- locked R dependency manifest and dated binary repository policy;
- named, hashed source-only exceptions such as HSROC;
- Python 3.11.9 and `uv.lock`;
- rpy2 3.6.6 API source;
- PyQt6, Qt 6, PyInstaller, and hook versions from the lock;
- source commit and product version.

Cache downloaded or compiled **inputs**, not mutable installed trees or final
applications. GitHub distinguishes dependency caches from workflow artifacts
and warns that restored caches should be treated as untrusted input
([GitHub dependency caching](https://docs.github.com/en/actions/concepts/workflows-and-actions/dependency-caching)).

Good caches are:

- the authenticated R installer keyed by its digest;
- R package archives keyed by architecture, R version, and dependency policy;
- Qt tool archives keyed by version and architecture; and
- uv's download/build cache keyed by OS, architecture, Python, and `uv.lock`.

Do not cache `.venv`, staged `R.framework`, PyInstaller work/dist, a relocated
bridge, or an assembled `.app` as a reusable build input. uv recommends its
official setup action, a pinned uv version, lock-based sync, and `uv cache
prune --ci`; `uv run --locked` fails rather than silently updating the lock
([uv on GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/),
[uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/),
[uv cache](https://docs.astral.sh/uv/concepts/cache/)).

### Phase 2: build and qualify one private R layer

One command performs, in order:

1. expand the exact framework installer component into a fresh directory;
2. verify expected framework aliases and reject absolute links escaping it;
3. omit declared unused installer/product payload by inventory policy;
4. minimally adapt the `R` and `Rscript` launch boundaries;
5. install only the locked application R library;
6. normalize the complete Mach-O graph once;
7. reject wrong architecture, unresolved non-system edges, host paths,
   duplicate identities, and forbidden payload;
8. run R/Rscript/config probes, load all required namespaces, and run real
   RCMetaR analyses and Quartz output; and
9. emit a content manifest and native-graph manifest.

The output is an architecture-specific runtime layer. For an ordinary PR job
it can remain in the same job. For a release candidate or when splitting an
expensive workflow into jobs, upload it as a content-addressed workflow
artifact and bind downstream evidence to its digest. Do not reconstruct it in
each downstream job.

The runtime gate should prove required behavior and exact forbidden content.
It should not assert incidental symlink counts, internal version-directory
spelling, or unrelated R capability values.

### Phase 3: build and qualify the rpy2 API bridge

Use a clean locked environment. Build rpy2 from its locked source with:

```text
R_HOME=<private runtime Resources>
PATH=<private runtime Resources/bin>:...
RPY2_CFFI_MODE=API
MACOSX_DEPLOYMENT_TARGET=13.0
```

Rewrite only the bridge's single R edge to the known final private framework
location. Prove the bridge against the private layer and retain its hash and
`otool -L` output. The bridge becomes part of the app/R integration layer, not
an invitation for PyInstaller to rediscover and copy R.

### Phase 4: let PyInstaller build Python and Qt only

Use one production macOS spec. It should collect:

- the application and generated resources;
- Python and the locked Python packages;
- PyQt6/Qt6 frameworks and required plugins; and
- rpy2's Python modules/metadata needed by the frozen application.

It should not receive the complete R framework as a data/binary TOC. It should
not retain a PyInstaller-discovered copy of `libR`, R package shared objects,
or compiler runtime dylibs. The implementation needs one narrow, tested seam
for placing the API extension after `BUNDLE`; that seam must prove the final
extension is importable in the frozen interpreter.

This is compatible with PyInstaller's documented role: its spec is executable
Python describing `Analysis`, `COLLECT`, and `BUNDLE`, while the macOS bundle
contains `Contents/MacOS`, `Contents/Frameworks`, and `Contents/Resources`
([PyInstaller spec files](https://pyinstaller.org/en/stable/spec-files.html),
[macOS bundle creation](https://pyinstaller.org/en/stable/usage.html#building-macos-app-bundles)).

Do not run `macdeployqt`; PyInstaller remains the sole Qt collector.

### Phase 5: deterministic final assembly and qualification

After PyInstaller:

1. install the R runtime layer at
   `RCMetaStudio.app/Contents/Frameworks/R.framework`;
2. install the exact qualified API extension in its tested frozen-module
   location;
3. set only bundle-relative R runtime configuration;
4. inspect every final Mach-O and resolve every non-system load edge;
5. require one private R framework, one concrete `libR`, one API bridge, no ABI
   bridge, correct architecture, and no forbidden payload;
6. launch the normal user-facing `.app` entry point and exercise the real
   in-process R analysis and plot path;
7. sign nested code inside-out and the app last;
8. archive the app, hash the archive, extract it into a fresh directory, and
   repeat graph inspection and smoke against the exact deliverable.

There is one final graph validator. Component-level probes may fail early, but
they must not implement competing relocation rules.

## GitHub Actions design

Use one workflow and one architecture matrix:

```yaml
strategy:
  fail-fast: false
  matrix:
    include:
      - target: macos-x64
        runner: macos-15-intel
        machine: x86_64
      - target: macos-arm64
        runner: macos-15
        machine: arm64
```

Each matrix leg invokes the same public command a collaborator with a matching
Mac would use. Workflow YAML installs tools, restores input caches, uploads
artifacts/evidence, and sets CI policy; all product logic stays in the command.

Recommended cadence:

| Trigger | macOS work |
| --- | --- |
| Ordinary source PR | source smoke/fast verification only |
| Packaging/R/Qt/lock/workflow path change | both native package matrix legs |
| Manual candidate, schedule, tag | both complete package legs and retained artifacts |
| Release promotion later | sign/notarize already-qualified candidate; do not rebuild it |

Add workflow concurrency keyed by branch/PR with cancellation of superseded
runs. Set bounded job timeouts. Upload phase logs and manifests on failure so a
single run answers “which phase and which edge failed?” without rerunning the
whole workflow merely to obtain diagnostics.

Delete the separate feasibility implementation after the production command
can stop after named phases. A feasibility job, if retained, should invoke for
example the production command's `--through rpy2` or `--through assemble`, not
maintain its own staging and spec logic.

## Validation ladder that avoids expensive blind loops

The hosted runner remains the native oracle, but one full app build should not
be the first time a changed phase is exercised.

1. **Cross-platform contract tests (seconds):** manifests, path policy,
   forbidden inputs, workflow matrix, phase state machine, fixture Mach-O
   parsing.
2. **Native R-layer job (minutes):** acquire, adapt, install, close, and execute
   private R; no Qt or PyInstaller.
3. **Native bridge job (minutes):** build API bridge against the exact R layer,
   inspect its one edge, execute R in process; no full app.
4. **Python/Qt app-skeleton job (minutes):** build and launch the PyInstaller
   app without embedded R assembly.
5. **Final native package job:** combine already-proven inputs, inspect, smoke,
   sign, archive, extract, and smoke.

During migration these may be steps in one matrix job with phase-specific
logs, avoiding artifact transfer overhead. Once stable, the R layer can be a
separate content-addressed candidate artifact reused by the two later phases.
The important property is that each phase consumes an explicit manifest and
never searches the host to repair a missing dependency.

## Staged migration from the current branch

### Stage 0: stop symptom-driven amendments

- Retain the two current failures as regression evidence.
- Do not add another system-path exception to
  `filter_pyinstaller_r_binaries`.
- Do not change the Tcl/Tk product profile merely to force
  `capabilities("tcltk")` false.

### Stage 1: correct the acceptance contract

- Replace the Tcl/Tk capability gate with exact payload and dependency
  assertions plus real required plotting workflows.
- Write one architecture-neutral product manifest: required files, forbidden
  families, required analyses, allowed Apple system roots.
- Make arm64 and x64 differ only in locked source coordinates, runner label,
  architecture, and OS floor.

### Stage 2: extract one production R-layer builder

- Move acquisition, launcher adaptation, R package installation, graph
  normalization, and R qualification behind one command/module.
- Run it unchanged in both matrix legs.
- Emit one runtime and graph manifest; add no PyInstaller code yet.

### Stage 3: prove the post-PyInstaller assembly seam narrowly

- Build a minimal PyQt6 app skeleton.
- Build the API bridge against the private layer.
- Assemble only the bridge and R layer after `BUNDLE`.
- Prove frozen import, R calculation, architecture, final relative edge, ad-hoc
  signing, ZIP extraction, and relaunch on both runners.

This is the real feasibility spike. It uses the intended production ownership
model instead of a second package implementation.

### Stage 4: migrate the full app and collapse CI

- Apply the proven assembler to the authoritative application spec.
- Make `package-macos` the only package command.
- Replace both current macOS workflows/jobs with the one matrix.
- Delete the 1,946-line parallel feasibility implementation and its duplicate
  spec after equivalent evidence is retained.

### Stage 5: add Developer ID delivery without redesign

- Replace ad-hoc identity with the Developer ID identity.
- Add hardened runtime and the smallest proven entitlement set.
- Notarize the already-qualified archive, staple, verify, and promote the same
  candidate bytes.
- Never rebuild from source during promotion.

## Decisions to make explicitly

These are product decisions, not implementation trivia:

1. **Is in-process rpy2 a hard release constraint?** If yes, retain the API
   bridge and the narrow final assembly seam above. If not, an app-relative
   `Rscript --vanilla` worker removes rpy2/libR from the Qt process and is the
   largest possible packaging simplification, but it is an application
   architecture change and should not be smuggled into issue #342.
2. **Does “do not bundle Tcl/Tk/X11” mean bytes/edges, or must R report no
   capability?** The former matches the stated user need and upstream semantics;
   the latter requires a custom R build and materially expands scope.
3. **Must complete macOS artifacts run on every source-only PR?** Existing ADRs
   favor source verification on ordinary changes and complete packages on
   packaging-relevant/candidate changes. Full artifacts on every push add cost
   without improving the packaging signal.
4. **May the private R layer be an immutable intermediate artifact?** Allowing
   it makes failures earlier, retries faster, provenance clearer, and signing
   easier. Rebuilding it inside every app attempt deliberately preserves the
   current coupling.

## Acceptance criteria for the simplified process

The replacement is complete when:

- one local command and one matrix workflow build both native targets;
- feasibility invokes production phases rather than duplicating them;
- PyInstaller never owns or rewrites the private R graph;
- the R assembler never rewrites Qt/Python graphs;
- no build output depends on a runner-installed R, `/opt/R`, Homebrew, XQuartz,
  or a user R library;
- rpy2 is target-native API-only and proves one relative edge to private R;
- the complete final native graph is inspected once after assembly;
- gates express required artifact contents and workflows, not incidental
  upstream implementation details;
- only authenticated downloads and compiled-input caches are reused;
- failure evidence identifies the phase, input digests, exact runner image,
  offending file, and load edge;
- the extracted unsigned archive runs required analyses on Intel and arm64;
  and
- future Developer ID signing changes credentials and the final delivery phase,
  not build architecture.

## Bottom line

GitHub-hosted macOS runners are sufficient. The process is circling because CI
is being used to debug two overlapping packagers and two divergent execution
paths. Consolidate first:

- one production path;
- one owner for Python/Qt;
- one owner for R/rpy2;
- one final assembly boundary;
- one final graph gate; and
- layered native checks before the expensive full artifact.

That is less code, fewer host-dependent decisions, faster feedback, and a
direct path to signing and notarization later.
