# Issues #342-#344 implementation audit

**Status:** Research and implementation-grill note, 20 July 2026
**Snapshot:** repository commit `36f8a9b8`; live GitHub issue and Actions state checked on 20 July 2026
**Scope:** [#342](https://github.com/AliSalman-et-al/rc-metastudio/issues/342), [#343](https://github.com/AliSalman-et-al/rc-metastudio/issues/343), and [#344](https://github.com/AliSalman-et-al/rc-metastudio/issues/344)

## Verdict

All three issues should remain open.

| Issue | Verdict | Why it cannot close |
| --- | --- | --- |
| #342, Intel package | Substantial implementation candidate; native acceptance failed | The required Intel package job failed before PyInstaller packaging and packaged smoke, and the hosted-acceptance record is blank. |
| #343, ARM64 package | Partial internal scaffolding; no supported end-to-end implementation | The public command rejects ARM64, the reusable workflow is Intel-only, the manual ARM input has no job, and the apparent ARM branch still consumes Intel-specific R inputs and paths. |
| #344, three-artifact qualification/cutover | Not implemented; deliberately deferred | The immutable 0.2.0 candidate and community release are Windows-only under ADR 0276. There is no exact-hash Windows/x64-Mac/ARM64-Mac qualification matrix. |

The open state is consistent with the repository's explicit version-scoped decision: ADR 0276 defers both macOS packages to 0.2.1, says #342-#344 remain open, and permits the maintained source to stay Qt6-only in the meantime ([ADR 0276](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/docs/adr/0276-release-0-2-0-for-windows-and-defer-macos.md#L1-L3)).

## #342: native macOS Intel x64 package

### What exists

This is not vaporware. The repository has:

- an Intel-only reusable job on `macos-15-intel` that calls the public `scripts/package-macos.sh --architecture x64` command and retains the ZIP, qualification evidence, and failure diagnostics ([workflow](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/.github/workflows/package-target.yml#L1-L20), [build and uploads](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/.github/workflows/package-target.yml#L56-L101));
- one PyInstaller spec that excludes alternate Qt bindings and the rpy2 ABI bridge, accepts the explicit R tree, uses the requested thin target architecture, and produces a normal `.app` bundle ([spec](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/packaging/pyinstaller/rc-metastudio-macos.spec#L55-L81), [bundle](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/packaging/pyinstaller/rc-metastudio-macos.spec#L98-L144));
- packaging code for signing, frozen-runtime probing, real-R workflow smoke, Cocoa surfaces at 125/150/175 percent, normal LaunchServices entry, archive inspection, exact-ZIP extraction, reinspection, and final hash-bound evidence ([build script](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/scripts/build-macos-package.sh#L707-L770), [final evidence](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/scripts/build-macos-package.sh#L960-L983)); and
- strong local source-shape and fail-closed contract coverage. On this snapshot, `uv run pytest -q -rs tests/packaging/contract/test_macos_x64_distributable_contract.py tests/packaging/contract/test_offline_r_kit_assembly.py` passed **67 tests** and skipped two Windows-inapplicable POSIX execution tests.

PyInstaller itself is not the architectural blocker: its official macOS options support `x86_64`, `arm64`, and `universal2`, while validating collected binary architectures ([PyInstaller macOS options](https://pyinstaller.org/en/stable/usage.html#macos-specific-options)).

### What failed

The required Intel package job at commit `cf649db7` failed in [run 29682212551, job 88180276881](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29682212551/job/88180276881); the integration gate failed as a consequence. The staged private R probe rejected `capabilities("tcltk") == TRUE`. The same blocking check remains at the current snapshot, before the PyInstaller and smoke stages ([current probe](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/scripts/build-macos-package.sh#L339-L367)). Therefore that run exercised none of the downstream packaged acceptance behavior.

The repository itself says closure requires a successful native job plus the tested commit, job/artifact IDs, ZIP SHA-256, runner identity, evidence hashes, results, and elapsed time; the record is still empty ([hosted acceptance record](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/docs/verification/macos-x64-qt6-package.md#L114-L120)). Later green macOS source smoke is not downloadable-artifact evidence.

### Questions that must be answered

1. Why is the coarse build-feature report `!capabilities("tcltk")` the substrate gate when the later product check directly requires that the `tcltk` namespace is absent and verifies Aqua/Quartz rendering ([later policy check](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/scripts/build-macos-package.sh#L567-L576))? R documents `capabilities()` as reporting optional features compiled into the running build, which is not identical to proving a product payload or namespace is shipped ([R `capabilities`](https://stat.ethz.ch/R-manual/R-devel/library/base/html/capabilities.html)).
2. What evidence demonstrates the current head fixed the native failure? Green local contracts prove fail-closed source structure, not that a native `.app` reached those seams.
3. Why did commit `cf649db7` describe #342 as closed before its required hosted package job completed? Closure should follow evidence, not implementation intent.

## #343: native Apple Silicon ARM64 package

The current supported surface explicitly does not implement this issue:

- `package-macos.sh` accepts only `x64` and requires an `x86_64` host ([public wrapper](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/scripts/package-macos.sh#L87-L103));
- the reusable package workflow is named Intel x64, runs on `macos-15-intel`, installs the x64 Qt SDK, and invokes the x64 command ([workflow](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/.github/workflows/package-target.yml#L1-L20), [x64 build](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/.github/workflows/package-target.yml#L40-L64)); and
- `build_macos_arm64` is exposed as a manual input but has no job; the file explicitly says qualification is deferred to #343 ([manual workflow](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/.github/workflows/package-verification.yml#L11-L20), [deferral](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/.github/workflows/package-verification.yml#L39-L49)).

The lower-level script's ARM branch is misleading as implementation evidence. Although it selects an ARM target and host ([branch](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/scripts/build-macos-package.sh#L153-L190)), acquisition still hard-codes the Intel R 4.6.1 package, Intel SHA-256, x64 cache, and x64 staging root ([R acquisition](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/scripts/build-macos-package.sh#L248-L275)). The deployment inspector likewise retains Intel-only direct-R constants and sets the ARM minimum to macOS 14.0, while #343 and ADR 0244 require macOS 13 or later ([target contracts](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/scripts/inspect_macos_deployment.py#L46-L59), [ADR 0244](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/docs/adr/0244-adopt-qt6-supported-os-baselines.md#L1-L3)).

Native ARM feasibility is useful but not acceptance. The repository calls it supplementary and says repository code cannot substitute for native results ([feasibility scope](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/docs/verification/native-macos-qt6-feasibility.md#L1-L12), [policy](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/docs/verification/native-macos-qt6-feasibility.md#L126-L140)). The closest recent ARM feasibility job also failed at `cf649db7` when PyInstaller collected `libRblas.dylib` from `/Library` outside the staged membership ([run 29682212436, job 88180260767](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29682212436/job/88180260767)).

Questions for implementation:

1. Will ARM64 share one genuinely parameterized pipeline, or get a separate public wrapper/workflow? The current half-parameterized script hides Intel-only inputs behind an ARM-shaped branch.
2. Is macOS 13 truly supported on ARM64? If the R/package baseline forces macOS 14, update #343, ADR 0244, and the product support contract together; do not silently narrow it in the inspector.
3. What prevents system `/Library/Frameworks/R.framework` bytes from entering the final app? The latest ARM failure shows the feasibility collector boundary did not enforce exact staged membership.

## #344: qualify and cut over three exact artifacts

There is no three-artifact release-defining matrix:

- `delivery/targets.json` knows Windows x64 and macOS x64, but not macOS ARM64 ([targets](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/delivery/targets.json#L17-L32));
- the immutable candidate initializes and builds only `windows-x64` ([candidate](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/.github/workflows/candidate.yml#L46-L63));
- the community release rejects any target set other than Windows x64 and publishes only that target ([qualification guard](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/.github/workflows/community-release-candidate.yml#L50-L65), [promotion](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/.github/workflows/community-release-candidate.yml#L165-L200)); and
- the older signed release-candidate workflow models Windows plus Intel Mac, still omitting ARM64, so it is not a dormant implementation of #344 ([two-target matrix](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/.github/workflows/release-candidate.yml#L29-L36)).

The Windows-only 0.2.0 flow is coherent with ADR 0276, but the issue language and architecture docs now need a clean distinction between:

- **Qt6 source hard cutover**, already completed; and
- **0.2.1 three-artifact release qualification**, still blocked on #342 and #343.

Without that distinction, #344 says Qt6 becomes the sole path only after the three-target matrix, while the maintained source and released Windows package are already Qt6-only under the exception. Parent issue #326 is also closed despite its original three-artifact release condition. This is a traceability problem, not evidence that #344 passed.

Before #344 can close, one workflow must consume the exact candidate hashes from #341/#342/#343, run the complete package automation on all three native targets, fail the release gate when any target is unavailable or red, retain comparable evidence, and only then promote the same bytes. Source smoke, feasibility artifacts, local contracts, or manual approval cannot fill that gap; ADR 0274 expressly requires automation against the final downloadable artifacts ([ADR 0274](https://github.com/AliSalman-et-al/rc-metastudio/blob/36f8a9b8/docs/adr/0274-automate-native-artifact-qualification.md#L1-L3)).

## Recommended sequence

1. Resolve the Intel staged-R capability invariant, then obtain and independently record one successful current-head #342 native qualification.
2. Make R acquisition, staging roots, Qt SDK/cache, deployment target, evidence paths, and workflow runner genuinely target-parameterized; add the public ARM64 command/job and obtain #343 evidence.
3. Reconcile the macOS 13-versus-14 contract before declaring ARM64 support.
4. Add `macos-arm64` to the delivery model and replace the partial/two-target release paths with one exact three-artifact qualification gate for #344.
5. Update issue/parent wording so the completed Qt6 source cutover and the pending 0.2.1 packaged release cutover cannot be mistaken for one another.

## Agreed implementation direction

The implementation grill resolved the following decisions on 20 July 2026:

- target an unsigned Windows x64, macOS Intel x64, and macOS ARM64 0.2.1 community release;
- use one parameterized native macOS pipeline with architecture-specific official R inputs;
- establish a first-green milestone before exhaustive qualification: extract the ZIP, launch the normal `.app` executable, open `BCG.rcms`, run its real R-backed analysis, verify result text and SVG, and exit cleanly;
- prove Intel first and then run the same pipeline on Apple Silicon;
- let PyInstaller own collection by default and add custom handling only for a demonstrated narrow failure;
- retain macOS 13 as the deployment baseline for both artifacts and inspect rather than infer that contract;
- keep immutable unsigned artifacts as the no-rebuild handoff for future signing, without maintaining a dormant signing workflow; and
- remove superseded kit, spike, feasibility, and duplicate CI only after the replacement package path has succeeded natively.

The repository now models these decisions in `config/macos-package-targets.json`, the shared native matrix in `.github/workflows/package-target.yml`, and the three-target unsigned candidate and promotion workflows. Native hosted-run evidence remains the boundary between implementation and closure of the three issues.
