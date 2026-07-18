# Native macOS Qt6 feasibility

Issue #329 owns the pre-codemod native feasibility gate for macOS Intel x64 and
Apple Silicon ARM64. The gate is implemented by
`.github/workflows/qt6-macos-feasibility.yml`; it is separate from full release
packaging because it answers one bounded question before broad source
conversion: can the exact locked Qt6, R, rpy2, and PyInstaller chain work
natively on both supported Mac architectures?

This remains a small, supplementary architecture proof. It does not replace
issue #342's full Intel distributable build, archive inspection, launch
qualification, or release evidence.

## Evidence contract

Each matrix leg runs on its native GitHub-hosted architecture and fails before
launch when the runner, Python process, or Rosetta status does not match the
declared target. It installs Python 3.11.9 and R 4.6.1, synchronizes the frozen
`uv.lock`, and obtains `rcc` 6.11.1 from the official Qt online repository with
the exactly selected `aqtinstall` client. The repository validator records and
checks the resolved Python, PyQt6, Qt, SIP, R, rpy2, and PyInstaller versions.
Qt installs library executables under `libexec` on Unix-family SDKs, so the
resolver recognizes the official macOS `libexec/rcc` layout (plus explicit
documented fallback layouts), rejects missing or ambiguous executables, and
validates the selected tool's exact version and Mach-O architecture before
exporting it to later steps.

The source proof generates the representative Designer form, compiles and
registers the binary resource, renders its SVG icon, shows a real Cocoa dialog,
and exits cleanly. A real in-process rpy2 call evaluates
`sum(c(1.25, 2.5, 3.75))` and must return 7.5. The same form, resource, SVG, R
call, and Cocoa launch then run from a thin one-directory PyInstaller app. The
workflow rebuilds the locked rpy2 API bridge from source against the native R,
proves its architecture, single R edge, API mode, and real calculation, and
rejects an ABI bridge.

Before packaging, the proof privately copies the official `R.framework`,
applies the maintained non-X11 product quarantine, relocates its Mach-O graph,
and emits the same explicit staged-framework TOC used by production packaging.
The dedicated `qt6-macos-feasibility.spec` is the one allowlisted PyInstaller
definition. It removes R binaries inferred by PyInstaller's host dependency
walk by exact staged-framework membership, then adds the authoritative TOC;
PyInstaller remains the sole Qt dependency collector, with no manual Qt
framework or plugin copy. The API bridge is relocated first against staging
and then against the bundled framework. A post-app graph gate requires one
target-native API bridge, no ABI bridge, one private `libR`, and an R edge that
resolves inside `Contents/Frameworks/R.framework`. The frozen entry point sets
that framework's `Resources` directory as `R_HOME` before importing rpy2.

The evidence record includes an exact nested OS, runner-image, and machine
identity; Rosetta status; locked versions; source paths; Mach-O architecture
slices; the source and packaged Cocoa plugin paths; and smoke outcomes. The
uploaded bundle retains bounded copies of the native Python, PyQt6, Qt6, SIP,
R, rpy2, `rcc`, and Cocoa probes plus the packaged executable and packaged
Cocoa plugin. It also retains a complete file/hash deployment inventory and the
exact PyInstaller build plan, but not the full disposable application bundle.
Retained diagnostics include the non-X11 R quarantine profile, durable frozen
launch phase markers, and the validated packaged R graph, alongside source and
packaged smoke reports and the PyInstaller build log. The deployment inventory
must contain the private `libR`, `Renviron`, and headers and rejects flattened
R compiler-runtime copies outside the framework.
Thin and universal Mach-O architectures are read directly from bounded file
headers and fat-slice tables, including slice-bound, class, byte-order,
CPU-subtype capability, and declared-versus-contained slice checks. The same
evidence can therefore be verified on macOS or Windows without trusting
recorded architectures or requiring `lipo` on the reviewing host.
The validator recomputes retained sizes, hashes, and architectures, checks the
deployment has one authoritative `Contents/Frameworks/PyQt6/Qt6` payload and
one Cocoa plugin, and rejects manual or alternate Qt collection. PyInstaller's
normal framework and resource aliases are checked against canonical component
hash and architecture identities rather than counted as extra Qt roots.
Symlinks are inventoried without traversal, record their target and resolved
in-bundle path, and contribute their `lstat` size once, keeping file and byte
totals truthful. Validation reconstructs each target through the bounded
virtual bundle graph instead of trusting the recorded resolved path, rejecting
absolute, escaping, cyclic, dangling, normalized, or wrong-component aliases.
Inventory and claimed-resolution paths must be canonical relative POSIX paths;
drive-qualified, backslash, repeated-separator, dot-component, NUL, and
normalization-ambiguous forms are rejected before indexing. Symlinks are
resolved iteratively with a record-count hop bound, so a malicious long chain
cannot exhaust the Python stack. The authoritative root accepts only canonical
Qt framework, plugin, translation, and non-executable data shapes. A single
case-folded payload classifier rejects displaced or duplicate Qt libraries and
plugins plus PySide6 and shiboken6 runtimes; outside-root aliases are accepted
only at their observed canonical locations. The schema-v2 macOS bundle's
directory aliases are restricted to the exact framework-to-resource
`translations` link and the reciprocal resource-to-framework `lib` and
`plugins` links, including their literal link targets and graph-resolved roots.
Regular aliases must match their same-name canonical Qt component's hash and
architecture. Native probes
are capped at 100 MB; the
inspected minimal deployment is capped at 10,000 files and 1 GB. The two
architecture evidence artifacts are retained separately for 30 days and named
with the source commit SHA.

The per-target diagnostics directory and setup log are created immediately
after checkout, before uv, Python, R, lock synchronization, or Qt installation.
Successful evidence upload remains mandatory. On an earlier failure, a
separate best-effort upload retains setup and identity diagnostics without
allowing an artifact-service failure or cache cleanup to replace the primary
setup error.

## Historical acceptance record

The following run accepted the original issue #329 contract. It predates the
explicit private-R/API packaging extension above and is not acceptance evidence
for the current contract or for issue #342.

The gate passed for source commit
`a943b196daed17283cf925ab2199250e0db7dff0` on
[PR #345](https://github.com/AliSalman-et-al/rc-metastudio/pull/345) in
[GitHub Actions run 29462556132](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29462556132).

| Target | Native job | Runner and result | Evidence artifact | `evidence.json` |
| --- | --- | --- | --- | --- |
| Intel x64 | [87508955301](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29462556132/job/87508955301) | `macos-15-intel`; success; `2026-07-16T00:50:50Z`–`00:57:52Z` | ID `8361818490`; `qt6-feasibility-macos-x64-9fefe2e3f57211bc71efb3b49c94cff1dbeedc3d`; 23,308,552 bytes; `sha256:f820f9e0ad39e236eaf8f5d885dd11abf3959b30a9fb892650bcbe4ec556f3d8`; expires `2026-08-15` | 7,193 bytes; `f744017d3f2de71271ea7a18dc2e11974bf610f611fba798af05b971c68441a9` |
| Apple Silicon ARM64 | [87508955302](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29462556132/job/87508955302) | `macos-14`; success; `2026-07-16T00:50:48Z`–`00:52:10Z` | ID `8361729466`; `qt6-feasibility-macos-arm64-9fefe2e3f57211bc71efb3b49c94cff1dbeedc3d`; 22,779,715 bytes; `sha256:ca45cab5dc7b552b9aff9dac32e19b60295327deb1e61e454c8453c0dbf64cbb`; expires `2026-08-15` | 7,174 bytes; `dbb13a46d5ee0f683755392a9b3c36a9b12b62a3a73d6049bfe68619708068fc` |

The public validation CLI accepted both downloaded records unchanged on
Windows. Each native job proved the exact Python 3.11.9, PyQt6 6.11.0, Qt
6.11.1, R 4.6.1, and rpy2 3.6.7 stack; Cocoa source and packaged execution;
visible form, registered resource, SVG rendering, clean exit, and R result 7.5;
a thin target-architecture package; and PyInstaller as the sole collector with
the retained deployment inventory.

## Blocking policy

This workflow is deliberately fail-closed. A missing wheel, incompatible R or
rpy2 binary, missing native slice, resource failure, non-Cocoa launch,
PyInstaller collection failure, or malformed evidence blocks the broad Qt6
codemod. It must result in a reviewed dependency replacement decision; the job
does not enable Rosetta, switch bindings, copy Qt manually, or downgrade the
proof to offscreen execution.

The workflow and validator can be checked on Windows, but successful native
evidence cannot be produced there. A change to this contract is accepted only
after both GitHub matrix legs have run successfully and their retained evidence
has been reviewed; repository code alone is not a substitute for those
results. That acceptance supplements rather than closes issue #342's full
Intel package qualification.
