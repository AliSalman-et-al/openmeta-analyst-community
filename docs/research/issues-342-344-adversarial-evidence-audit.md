# Issues 342–344: adversarial evidence audit

**Audit point:** PR #350 at `928fa0083420cfed675b770f6382fbc5c641d7d4`, 2026-07-20.  
**Scope:** deployment floor, native architecture, signing readiness, CI/artifact identity, qualification semantics, and closure proof.  
**Method:** repository source/history/issues and first-party Apple, Qt, R, and GitHub material only.

## Verdict

The proposed design is substantially more credible than the workflows it replaces: it builds on architecture-specific hosted runners, rejects wrong-architecture native payloads, exercises an extracted ZIP, uses an explicit inside-out signing inventory, and separates immutable candidate construction from later qualification/promotion. Those are verified implementation facts, not a claim that the issues are resolved.

**PR #350 must not yet close #342–#344.** At the audit point there is no successful package-verification run for the exact head: [run 29748971591](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29748971591) is still in progress, while the preceding exact-lineage runs are failed or cancelled. More importantly, the implementation intentionally declares macOS 14 while all three issue contracts still require macOS 13+, and packaged qualification exercises only `BCG.rcms` (plus `amino.rcms` for layout) rather than every converted sample required by #344.

## Verified facts

1. **macOS 14 is the honest common floor for the selected official R runtime.** The target manifest selects official R 4.6.1 for both architectures and declares `minimum_macos: 14.0` ([manifest](https://github.com/AliSalman-et-al/rc-metastudio/blob/928fa0083420cfed675b770f6382fbc5c641d7d4/config/macos-package-targets.json)). R's own distribution page says the R 4.6.1 arm64 package is for macOS 14+, whereas its Intel package supports macOS 11+ ([R for macOS](https://cran.r-project.org/bin/macosx/)). R's maintainer documentation further says the 4.6 arm64 build targets macOS 14 ([R macOS build policy](https://mac.r-project.org/)). Therefore the common floor is constrained by R arm64, not Qt.

2. **Qt does not force that narrowing.** Qt 6.11 supports macOS 13+ and `x86_64`, `x86_64h`, and `arm64` ([Qt supported configurations](https://doc.qt.io/qt-6/macos.html#supported-configurations)). The project pins PyQt6 6.11.0 and installs Qt SDK 6.11.1 ([dependency lock](https://github.com/AliSalman-et-al/rc-metastudio/blob/928fa0083420cfed675b770f6382fbc5c641d7d4/pyproject.toml), [workflow](https://github.com/AliSalman-et-al/rc-metastudio/blob/928fa0083420cfed675b770f6382fbc5c641d7d4/.github/workflows/package-target.yml)).

3. **The architecture split is real and appropriate.** `macos-15-intel` builds x86_64 and `macos-15` builds arm64; the build script refuses a host/target mismatch ([workflow](https://github.com/AliSalman-et-al/rc-metastudio/blob/928fa0083420cfed675b770f6382fbc5c641d7d4/.github/workflows/package-target.yml), [build guard](https://github.com/AliSalman-et-al/rc-metastudio/blob/928fa0083420cfed675b770f6382fbc5c641d7d4/scripts/build-macos-package.sh)). GitHub documents hosted-runner architecture and warns that images change regularly, supporting explicit labels and evidence capture ([GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), [runner-images](https://github.com/actions/runner-images)).

4. **Package qualification is materially stronger than a launch-only smoke.** The build runs the frozen app, a real BCG R-backed workflow, three surface scales, a LaunchServices entry, archive inspection, and repeats those gates after extracting the ZIP ([build and qualification](https://github.com/AliSalman-et-al/rc-metastudio/blob/928fa0083420cfed675b770f6382fbc5c641d7d4/scripts/build-macos-package.sh)). The inspector binds the archive digest and hashes retained evidence ([inspector](https://github.com/AliSalman-et-al/rc-metastudio/blob/928fa0083420cfed675b770f6382fbc5c641d7d4/scripts/inspect_macos_deployment.py)). The candidate publisher downloads the candidate artifacts by run ID and re-launches those bytes on the corresponding native target ([RC publisher](https://github.com/AliSalman-et-al/rc-metastudio/blob/928fa0083420cfed675b770f6382fbc5c641d7d4/.github/workflows/community-release-candidate.yml)).

5. **The current app is hardened-runtime-shaped, but not distribution-proven.** The signer enumerates Mach-O files and nested bundles, signs inside-out with `--options runtime`, and verifies strict signatures ([signer](https://github.com/AliSalman-et-al/rc-metastudio/blob/928fa0083420cfed675b770f6382fbc5c641d7d4/scripts/sign_macos_app.py)). Apple requires Developer ID signing, hardened runtime, a secure timestamp, suitable entitlements, notarization, and notary-log review for direct distribution ([Apple notarization requirements](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution), [common notarization issues](https://developer.apple.com/documentation/security/resolving-common-notarization-issues)). An ad-hoc signature proves none of the credential, notary-service, Gatekeeper, or quarantine path.

## Falsified assumptions

1. **“This PR supports macOS 13.” — False for Apple Silicon.** The PR description says macOS 13, but the authoritative manifest and inspector require 14.0, and official R 4.6.1 arm64 itself requires macOS 14. This is not a cosmetic documentation discrepancy: [#342](https://github.com/AliSalman-et-al/rc-metastudio/issues/342), [#343](https://github.com/AliSalman-et-al/rc-metastudio/issues/343), and [#344](https://github.com/AliSalman-et-al/rc-metastudio/issues/344) cannot be closed against their present macOS 13 acceptance language.

2. **“One representative project proves #344's sample-project requirement.” — False.** The repository contains six converted `.rcms` samples. Packaged workflow, extracted-ZIP workflow, LaunchServices, and release-candidate requalification select `BCG.rcms`; layout selects `amino.rcms`. There is no packaged loop over the sample manifest. #344 explicitly requires every converted sample and structured-semantic validation on every target.

3. **“A green PR check proves release artifacts.” — False.** Source checks and package-verification are different workflows. Closure requires the exact head package run, retained downloadable artifacts, and evidence audit; then #344 additionally requires the immutable candidate built from protected `master` and its native qualification. Earlier green candidate/RC runs are for older SHAs and cannot establish this head.

4. **“Ad-hoc hardened signing proves future notarization.” — False.** It is useful preflight evidence only. Apple expressly requires a Developer ID identity and secure timestamp, and entitlement needs can surface only under the real hardened runtime/notary/Gatekeeper path. The correct claim is “designed for a no-rebuild signing stage,” not “notarization-compatible.”

5. **“Pinned runner labels make the pipeline durable.” — False if interpreted indefinitely.** They make architecture deterministic today. GitHub images are updated and retired; durability requires a maintained runner migration policy, not a permanent label assumption.

## Remaining unknowns

- Whether both macOS jobs in run 29748971591 finish successfully and whether their uploaded ZIP/evidence hashes agree with their internal qualification records.
- Whether the exact extracted artifacts behave on the **minimum** supported OS. Current execution on macOS 15 plus Mach-O load-command inspection is strong static evidence, but it is not an end-to-end macOS 14 runtime test.
- Whether every bundled R package and transitive native library is genuinely macOS 14-compatible beyond its recorded load command; only minimum-OS execution can close that gap.
- Whether a real Developer ID signing pass needs hardened-runtime entitlements for rpy2/R/Qt behavior, and whether the final stapled, quarantined bytes pass Gatekeeper.
- Whether native file-dialog automation validates macOS integration deeply enough: cancel/visibility/signal evidence proves the dialog path, but not successful user file selection or security-scoped access behavior.

## Durable recommendations and closure bar

1. **Reconcile the contract first:** update #342–#344, the relevant ADR/support documentation, and PR #350 to a macOS 14 common floor, or choose an arm64 R runtime that genuinely supports 13 and prove it. Do not merge a silent support regression.
2. **Add a packaged sample-manifest gate:** on Windows x64, macOS x64, and macOS arm64, open every committed converted sample from the extracted candidate and validate `manifest.json`, `project.json`, and `state.json` semantics. Keep the expensive real R/edit/save/reopen/SVG workflow representative if runtime cost matters; the issue text does not require that expensive workflow for every sample.
3. **Require exact-head evidence:** both macOS jobs and Windows must be green for `928fa008...`; download the artifacts; independently compare outer ZIP SHA-256, embedded evidence hashes, target architecture, runner/OS identity, deployment floor, workflow results, and clean exit. A job conclusion alone is insufficient.
4. **Require the protected-master candidate:** after merge, run `candidate.yml` for the merge SHA, then `community-release-candidate.yml` with that exact run ID and SHA. Audit its three hash-chained artifacts and native qualification before closing #344.
5. **Keep signing late and no-rebuild:** consume immutable unsigned candidates, replace ad-hoc signatures inside-out with Developer ID plus timestamp, notarize with `notarytool`, inspect the log even on success, staple the app before re-archiving, and test the final quarantined artifact. This is future work, not a prerequisite of #342–#344, but the workflow seam should accept it without rebuilding.
6. **Close only on a recorded acceptance packet:** issue comments should link the merge SHA, package/candidate/RC run IDs, artifact names and hashes, runner identities, evidence hashes, observed minimum-OS policy, and any explicitly amended acceptance language. Then—and only then—close #342, #343, and #344.

