# macOS CI systemic root cause and recovery

**Status:** Root-cause research, 20 July 2026  
**Scope:** GitHub issues [#342](https://github.com/AliSalman-et-al/rc-metastudio/issues/342), [#343](https://github.com/AliSalman-et-al/rc-metastudio/issues/343), and [#344](https://github.com/AliSalman-et-al/rc-metastudio/issues/344)  
**Evidence snapshot:** branch `fix/MacOS-x86-64-ARM64-Builds` through `9dfce6ec`; qualification run [29745384272](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29745384272)

## Verdict

The native products are no longer the principal blocker. The current Intel job built, signed, launched, ran the real R-backed `BCG.rcms` workflow, exercised three Cocoa scales, opened through LaunchServices, created a ZIP, extracted that ZIP, and repeated the runtime and product qualification. It failed afterward while assembling evidence: `embedded R profile evidence is incomplete`. Earlier runs likewise reached progressively later bookkeeping checks after the product behavior had passed.

The systemic cause is an oversized, cyclic evidence system implemented inside one 1,080-line shell transaction and one 2,436-line inspector. It has multiple producers and consumers for the same facts, repeats the same acceptance suite before and after archiving, and validates intermediate evidence again while constructing final evidence. A harmless schema mismatch can therefore veto an already-working downloadable app, but is only discovered after 8–14 minutes of native build and runtime work.

The immediate failure proves the pattern. `profile_macos_embedded_r_runtime.quarantine()` writes `policy` and `post_profile_exclusions`; `finalize` replaces the document without preserving them. The one-shot wrapper repairs some fields afterward but still omits `policy`. `write_qualification_evidence()` then requires both fields. The producer and consumer disagree even though the same run already proved that the removed Tcl/X11 surfaces were absent and the embedded R analysis worked. This is not an R, Qt, PyInstaller, architecture, signing, or application-runtime failure.

## What is observed, and what is inferred

### Observed artifact and run evidence

- Run 29745384272 Intel signed and verified 232 Mach-O files and nine nested bundles, then passed the frozen runtime probe, representative workflow, Cocoa scales 1.25/1.50/1.75, and LaunchServices.
- It successfully completed deployment inspection, direct-build provenance generation, ZIP creation, ZIP inspection, extraction, and approximately two minutes of extracted-app qualification before the final profile-schema check failed.
- The immediately preceding changes corrected late consumer/producer mismatches involving an indented `pkgutil` status line, runner-label versus runner-image identity, selection of `BCG.rcms` versus `amino.rcms`, and ownership of child-process completion.
- There were 34 commits in the preceding ten hours. The recent sequence changes evidence parsing and orchestration far more often than it changes the packaged application.
- `scripts/build-macos-package.sh` contains two separately spelled product suites: the assembled app around lines 806–862 and the extracted app around lines 1023–1056. Paths, environment, sample, logs, scale list, completion markers, and runner invocation are duplicated.
- `scripts/inspect_macos_deployment.py` validates evidence at production, archive inspection, extracted inspection, and final evidence assembly. It also hard-codes target inputs and exact internal representations that are produced elsewhere.

### Inferences, explicitly marked

- **Inference:** the package is likely usable on both native architectures because the most recent native executions pass the user-facing workflow. This is not yet closure evidence: the ARM lane and an exact three-artifact candidate must finish successfully.
- **Inference:** continuing one-field-at-a-time patches will find more late schema mismatches because there is no single schema owner and the same semantic facts are encoded in several files. The repeated observed failure class supports this, but it is a prediction rather than direct proof.
- **Inference:** the current pipeline reduces reliability rather than increasing assurance once it reruns already-proven semantic validation during evidence aggregation. A verifier that can reject valid observations due only to its own private representation is not independent product evidence.

## Root-cause tree

```text
Native package qualification remains red
├── Product defects (initially real, now mostly resolved)
│   ├── R.framework topology and rpy2 load edges
│   ├── target-native package acquisition and deployment floor
│   └── process startup and shutdown behavior
└── Qualification-system defects (current dominant cause)
    ├── No single owner for evidence schemas
    │   ├── producer overwrites fields from an earlier phase
    │   ├── consumer hard-codes an independently maintained shape
    │   └── final aggregator reinterprets instead of composing results
    ├── Same acceptance operation is implemented twice
    │   ├── assembled-app smoke
    │   └── extracted-ZIP smoke with separate constants and paths
    ├── Facts duplicated across configuration, shell and Python
    │   ├── sample project
    │   ├── scales and required log markers
    │   ├── runner label/image namespaces
    │   ├── R version/framework aliases and excluded surfaces
    │   └── evidence filenames
    ├── Wrong stage boundaries
    │   ├── provenance policy blocks product availability
    │   ├── final evidence validates schemas already validated upstream
    │   └── first user-relevant result arrives before several fatal checks
    └── Native feedback is too expensive
        ├── all acquisition, assembly, signing and smoke precede late validation
        └── x64 and ARM64 are serialized, multiplying each schema mistake
```

## Assumptions that do not survive scrutiny

1. **“More validators mean stronger evidence.”** Not when validators restate each other's internal object shape. The issue criteria require architecture, launch, workflow, diagnostics and hashes; they do not require a particular `policy` string or exact list order in a private profile JSON. Those details can be useful diagnostics, but they are not independent acceptance facts.
2. **“The assembled app and extracted app both need the complete suite.”** The downloadable ZIP is the acceptance object in all three issues. Full qualification should run once on its extracted bytes. Pre-archive checks should be limited to fail-fast structure, dependency graph, signature, and a short startup/R probe.
3. **“Final evidence assembly should prove every upstream fact again.”** It should authenticate references and hashes and require upstream pass records. Re-evaluating domain policy at aggregation creates a second, drifting implementation of every verifier.
4. **“A monolithic command guarantees consistency.”** Here it hides stage ownership. The build, mutation, signing, smoke, archive, extraction, second smoke and attestation steps share mutable variables and handwritten paths, making drift easier.
5. **“Exact presentation fields improve provenance.”** GitHub runner label and runner image are distinct namespaces; `pkgutil` indentation is presentation; process completion is a parent-observed fact. The pipeline repeatedly treated presentation as semantics.
6. **“Every profile property must be release-blocking.”** The release criteria require the resulting graph to exclude wrong dependencies. If final graph inspection and real runtime behavior prove that, a missing duplicated narrative field should not veto the artifact.

## Durable simplified target architecture

Use four explicit stages with one directional data flow:

```text
target registry
      │
      v
BUILD ──> unsigned .app
      │     structural/Mach-O checks
      v
SIGN ──> immutable ad-hoc-signed .app
      │     codesign --verify --strict --deep
      v
ARCHIVE ──> candidate ZIP + SHA-256
      │
      v
QUALIFY EXACT ZIP ──> one canonical qualification.json
      │                structural inspection + normal launch + complete issue smoke
      v
JOIN Windows/x64/ARM64 hashes ──> release-set result
```

Each stage has one output schema and one owner. A stage either emits a versioned `passed` record or fails at the point where it observes the defect. The final join checks schema version, target, source commit, artifact hash and `passed`; it does not replay R-profile, Qt-plugin, smoke-log, or signing logic.

The exact extracted ZIP must remain the full acceptance boundary. This satisfies #342–#344 more directly than testing a pre-archive tree. Apple says signed bundles should be treated as read-only and nested code must be signed inside-out before the outer bundle; it also recommends strict verification for bundle and symlink conformance ([Apple TN2206](https://developer.apple.com/library/archive/technotes/tn2206/)). Qt identifies `libqcocoa.dylib` as the required macOS platform plugin, recommends `qt.conf` for deployed paths, and recommends `otool` to inspect linked libraries ([Qt macOS deployment](https://doc.qt.io/qt-6/macos-deployment.html), [Qt `qt.conf`](https://doc.qt.io/qt-6/qt-conf.html)). Those are meaningful final-tree checks; an incidental JSON field is not.

PyInstaller remains the sole Qt collector, as the issues require. Do not introduce `macdeployqt`; Qt documents it as another component that copies Qt frameworks and plugins, which would create two graph owners ([Qt macOS deployment](https://doc.qt.io/qt-6/macos-deployment.html)). GitHub attestations belong after a release artifact exists and should bind repository, commit, workflow and artifact; GitHub explicitly says attestations must be verified to provide value ([GitHub artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations)). They should not be simulated by an ever-growing bespoke final JSON gate.

## Exact changes recommended now

### Recovery patch: make the next run answer the product question

1. Fix the current producer, not the consumer: have `finalize` preserve `policy`, `post_profile_exclusions`, and any other fields formally belonging to the profile schema. Add a producer-to-consumer round-trip contract test that calls the real quarantine/finalize path and then the real validator. Do not fabricate the missing field in the build shell.
2. Replace the giant boolean in `write_qualification_evidence()` with a call to the profile schema's own `validate()` function. There must be one implementation of profile validity.
3. Make final evidence assembly non-semantic: load the already-validated deployment, archive, smoke and profile result records; check identity and SHA-256 bindings; emit their references. It must not contain private R-policy or log-marker predicates.
4. Extract one `qualify_app(app_path, evidence_root, target)` command. Invoke the complete suite only after extracting the candidate ZIP. For the assembled tree retain `codesign --verify`, native-graph inspection, and a single quick runtime/R bridge probe.
5. Keep `BCG.rcms` as the single representative workflow fixture everywhere. Maintain all converted-sample semantic coverage for the #344 candidate matrix, but do not alternate fixtures between phases.
6. Run x64 and ARM64 independently (`max-parallel: 2`) while diagnosing. A scarce Intel runner may queue; serialization should not delay ARM evidence or cancel it after an x64 schema defect.

### Consolidation immediately after first green

1. Move target facts into `config/macos-package-targets.json` and load them in both commands. Delete `TARGET_CONTRACTS`, `TARGET_RUNNERS`, `DIRECT_R_OFFICIAL_INPUTS`, framework-version strings and runner expectations duplicated in the inspector.
2. Define small versioned schemas (Python dataclasses or typed dictionaries plus validators) for `build-result`, `archive-result`, `qualification-result`, and `release-set`. Generate JSON only through those modules.
3. Split `build-macos-package.sh` into an orchestration wrapper plus idempotent Python commands: `build`, `sign`, `archive`, `qualify`. Keep shell only where macOS tooling requires it.
4. Make evidence filenames outputs of the stage API, not constants separately repeated in shell, inspector, workflow upload globs and tests.
5. Replace text-presence contract tests such as “the shell contains this literal command” with behavioral fixture tests of the stage APIs. Keep a small workflow-shape test for native runner selection and artifact upload.

## Checks to delete or consolidate

| Current check | Action | Reason |
| --- | --- | --- |
| Complete pre-archive product smoke | Delete after first green | The exact extracted archive is the issue acceptance object; duplicate execution creates drift and doubles runtime. |
| Three pre-archive plus three extracted scale runs | Consolidate into the extracted suite | Keep the issue-required representative fractional scaling, but only once. Whether all three values remain is a product-test choice; it is not a packaging invariant. |
| Final evidence's embedded-R profile boolean | Delete; call the schema owner once upstream | It caused the current false negative and restates producer internals. |
| Final evidence's required smoke-log marker set | Delete; consume canonical `qualification-result.passed` | The smoke finalizer already owns those semantics. |
| Repeated runner label/image equality derivations | Consolidate | Record both raw fields; validate only OS and native architecture for product acceptance. Runner label is scheduling metadata, not artifact behavior. |
| Handwritten ZIP member list plus archive inspector list | Consolidate in one archive schema | Two required-member inventories can drift. |
| Pre-sign, signing, post-sign and post-extraction graph comparisons as separate policy implementations | Consolidate | Pre-sign helps diagnostics; release blocking needs final signed-tree and extracted-tree integrity, with the final graph schema owned once. |
| Raw logs embedded as semantic predicates | Retain as diagnostics, remove as final-gate schema | Logs are essential on failure but fragile as machine contracts. Emit structured results at observation time. |
| Archive traversal, case-collision, escaping symlink and size bounds | Keep | These protect safe extraction and portable distribution. |
| Final Mach-O architecture/dependency graph, Qt plugin presence, strict codesign verification | Keep | These directly prove issue criteria and Apple/Qt deployment requirements. |
| Exact extracted normal-entry launch, real R analysis, save/reopen, UI surfaces and clean exit | Keep once | These are explicit #342–#344 acceptance criteria. |
| Artifact SHA-256/source commit/target binding and three-target join | Keep | These are explicit #344 acceptance criteria. |

## Migration sequence

1. **Today, stop schema whack-a-mole:** repair the R-profile schema owner and remove duplicate semantic validation from the final aggregator. Add the real round-trip test.
2. **Get one exact artifact green:** archive first, extract, then run the one canonical suite. Upload the ZIP even when later evidence composition fails, marking it unqualified rather than pretending it was never built.
3. **Run both native lanes independently:** use their structured result and retained raw diagnostics to distinguish product failures from evidence-system failures.
4. **Collapse duplicated execution:** delete the assembled-tree full smoke and route all launch modes through one qualifier with one fixture and one evidence root.
5. **Centralize facts and schemas:** target registry and four stage result types become the only interfaces. Delete hard-coded mirrors.
6. **Make the candidate join boring:** it downloads three exact artifacts, verifies hashes, runs or consumes native qualification results, and fails only for a missing/red target or identity mismatch.
7. **After PR merge, qualify the exact protected-branch candidate and close #342–#344 only from those retained results.** Do not use the many pre-merge partial runs as closure evidence.

## Exit criteria for this recovery

The recovery is successful when a semantic product defect fails near its observation point, an evidence producer cannot emit a document rejected by its own schema test, and final aggregation cannot reinterpret lower-level product policy. The native lanes should answer four questions only: was the correct architecture built, is the final dependency/signature graph self-contained, does the exact downloaded app complete the required user workflow, and is that result bound to the exact artifact hash and commit? Everything else is diagnostic metadata.

