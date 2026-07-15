# Desktop GUI evidence policy for CI and releases

## Decision

RC MetaStudio should **remove adaptive-layout native screenshot capture from
GitHub-hosted package jobs and from artifact-build success criteria**. It should
not remove the adaptive-layout test suite or the evidence tooling.

Use four evidence tiers instead:

1. deterministic, headless Qt behavior and layout contracts in required CI;
2. a small packaged-app native launch smoke on each hosted operating system;
3. exact-DPI, exact-viewport native evidence on a controlled Windows machine
   and Intel Mac when those machines are available;
4. human visual review of controlled captures before layout-sensitive releases.

Until controlled machines exist, tier 3 and tier 4 should be recorded as
`not-run: controlled display unavailable`, not converted into a hosted-runner
pass and not made a precondition for constructing unsigned packages. A release
can still be identified honestly as having deterministic layout coverage and
hosted native launch smoke, but not complete native visual qualification.

This is stronger than either extreme proposed in the question. Keeping the
current hosted screenshot gate makes releases depend on an undocumented runner
property. Deleting the evidence system loses useful native and visual coverage.

## Why hosted runners are the wrong authority

GitHub specifies hosted-runner CPU, memory, storage, architecture, labels, and
VM lifecycle, but does not specify display resolution, usable desktop geometry,
window-manager state, font rendering, or DPI configuration. Standard jobs run
on fresh GitHub-managed VMs, and the runner images are maintained by GitHub.
Those machines are suitable for repeatable build and programmatic verification,
but their undocumented display is not a product test fixture. [GitHub-hosted
runners reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners),
[runner-images repository](https://github.com/actions/runner-images)

Qt represents high-DPI geometry in device-independent coordinates, maps it to
native pixels using device-pixel ratios, and defines `availableGeometry()` as
the screen area remaining after system-reserved areas. Qt explicitly describes
`QT_SCALE_FACTOR` as a testing/debugging override that scales application
geometry. Therefore the same requested client size can cease to fit when the
hosted VM's available geometry, native frame, or effective device-pixel ratio
changes. [Qt High DPI](https://doc.qt.io/qt-6.8/highdpi.html),
[`QScreen::availableGeometry`](https://doc.qt.io/qt-6/qscreen.html#availableGeometry-prop)

Qt Test also distinguishes framework-level GUI testing from native desktop
automation: its simulated input sends internal Qt events rather than native
window-system events. Qt provides explicit waits for windows to become exposed
when a test truly depends on visibility. This supports a deliberate split
between fast deterministic widget behavior and a much smaller native smoke
layer. [Qt Test GUI event tutorial](https://doc.qt.io/qt-6/qttestlib-tutorial3-example.html),
[`QTest::qWaitForWindowExposed`](https://doc.qt.io/qt-6.8/qtest.html#qWaitForWindowExposed)

Platform guidance reinforces layering rather than screenshot-only automation.
Microsoft recommends testing Windows layouts across window sizes, DPI, and
scale settings, while its UI testing guidance distinguishes unit-testable code,
UI-thread tests, automation, accessibility, and usability testing. Apple
describes XCUIAutomation for interaction flows and XCTest screenshot
attachments as test output for later inspection. Neither source makes a
transient hosted VM display a canonical visual baseline. [Microsoft Windows
layout best practices](https://learn.microsoft.com/en-us/windows/apps/get-started/best-practices#layout),
[Microsoft UI testing overview](https://learn.microsoft.com/en-us/windows/win32/appuistart/testing-a-user-interface),
[Apple XCTest](https://developer.apple.com/documentation/xctest/),
[Apple test attachments](https://developer.apple.com/documentation/xctest/adding-attachments-to-tests-activities-and-issues)

## Decision framework

Classify each check by the property it proves, not by whether it happens to use
Qt:

| Question | Required environment | Lane |
| --- | --- | --- |
| Is layout policy, reflow, reachability, sizing, or state restoration correct in Qt's logical model? | Offscreen/minimal Qt with controlled inputs | Deterministic CI |
| Does the built executable contain its dependencies, start with the native platform plugin, expose a window, open a sample project, and exit cleanly? | Hosted native OS; no exact pixel/geometry claim | Hosted native smoke |
| Does the complete native frame fit and render correctly at a particular physical display mode, DPI, scale, font set, and OS build? | Controlled, preflighted physical/interactive host | Controlled native evidence |
| Is spacing, clipping, iconography, typography, and overall polish acceptable? | Human inspection of controlled evidence | Manual review |

A check belongs in artifact construction only if its result is invariant under
undocumented display changes. A native smoke can qualify the already-built
artifact, but failure should reject release promotion rather than erase or
force a rebuild of those bytes.

## Exact repository classification

### Keep as required deterministic CI

- `tests/python/fast/test_qt_layout_contract_audit.py` and
  `scripts/audit_qt_layout_contracts.py`: static application-wide layout-policy
  enforcement.
- The parameterized logical-layout and behavior suites under
  `tests/python/gui/`, especially:
  - `test_adaptive_window_policy.py`;
  - `test_main_workspace_window.py`;
  - `test_results_workspace_layout.py`;
  - `test_edit_dataset_workspace_layout.py`;
  - `test_network_view_workspace_layout.py`;
  - `test_main_wizard_workflow_layout.py`;
  - `test_declarative_dialog_sizing.py`;
  - `test_compact_transient_layout.py`;
  - `test_*_transactional_layout.py` and
    `test_analysis_configuration_layout.py`.
- `tests/python/gui/test_adaptive_layout_native_evidence.py`: keep its runner
  logic, geometry, painted-frame, manifest, and validator behavior tests in
  offscreen CI. Despite the filename, these tests exercise deterministic code;
  they do not establish native visual correctness.
- `tests/packaging/contract/test_adaptive_layout_native_evidence_contract.py`:
  retain validator schema, membership, hash, PNG-integrity, and rounding tests.
  Rewrite only the assertions that currently require every packager/workflow to
  execute and upload native captures.
- `scripts/validate_adaptive_layout_evidence.py`: retain as the validator for
  controlled evidence.
- `--automation-wizard-layout-smoke` under `QT_QPA_PLATFORM=offscreen`: keep as
  a packaged-tree functional check because it does not claim native rendering.
- `--automation-smoke`, startup-project checks, package tree assertions, bundled
  R/RCMetaR verification, archive manifest/digest checks, and deterministic
  packaging contracts: keep required.

### Keep on GitHub-hosted runners as narrow native smoke

For both Windows x64 and macOS Intel x64, run the already-built package without
`QT_QPA_PLATFORM=offscreen` and verify only:

- the expected native plugin (`windows` or `cocoa`) loaded;
- the process started and did not crash;
- the primary window became exposed within a bounded timeout;
- the bundled sample project opened and the in-process R bridge initialized;
- the automation mode exited cleanly.

Do not assert an exact screen rectangle, exact native-frame dimensions,
system-font identity, screenshot pixel dimensions, stable decoration margins,
or visual equality in this lane. Emit logs and a screenshot on failure for
diagnosis, not as a release baseline. The current macOS packaged smoke forces
`offscreen` by default, so it does not yet provide this narrow native signal;
the current Windows smoke hides its window and likewise should be made explicit
about which smoke is headless and which is native.

### Move to controlled local/native evidence

- `Invoke-PackagedAdaptiveLayoutEvidence` in
  `scripts/build-windows-package.ps1`.
- `run_adaptive_layout_evidence` in `scripts/build-macos-package.sh`.
- Exact 800 by 600 and 1024 by 640 native-frame captures at scale 1.0 and 1.5.
- Assertions about native frame containment, native chrome, system font,
  logical DPI, device-pixel ratio, screen ownership, screenshot pixel size, and
  complete-frame image hashes.
- Intrinsic-ratio screenshot inspection and every item in generated
  `HUMAN_REVIEW.md`.
- Cross-platform visual comparison required by
  `docs/verification/adaptive-layout-native-evidence.md`.

Run this tooling from an explicit maintainer command against the final package
on preflighted machines. Record OS build, Qt version/plugin, screen geometry,
native scaling, logical DPI, DPR, fonts, package SHA-256, reviewer, and result.
A controlled machine can later be attached as a labeled self-hosted runner;
GitHub supports macOS and Windows x64 self-hosted machines, while the owner is
responsible for their hardware resources and configuration. [GitHub
self-hosted runner reference](https://docs.github.com/en/actions/reference/runners/self-hosted-runners)

### Remove from package construction and hosted release gates

- Calls that capture adaptive-layout evidence inside the Windows and macOS
  build scripts.
- `evidence_path` as a required input to
  `.github/workflows/package-target.yml`.
- The unconditional `Upload adaptive-layout evidence` step and evidence-path
  diagnostics in that workflow.
- Package contract assertions requiring hosted packagers to generate those
  artifacts.
- `capability-unavailable` as a way to make a hosted package lane succeed. Keep
  the record type only if it is useful for diagnostic/manual runs; it must not
  count as native qualification.

Do **not** delete `adaptive_layout_evidence.py`, its validator, its deterministic
tests, or its documentation. They remain the controlled native evidence
harness. Do not replace the human review with pixel-diff snapshots: native text,
font, decoration, and rasterization differences make such baselines expensive
and brittle, while the logical contract tests already carry the deterministic
layout assertions.

## Release-confidence impact

| Evidence claim | After this change |
| --- | --- |
| Logical layout policy across constrained/full viewports and scale inputs | Preserved or improved in required CI |
| Built package structure, bundled R stack, sample-project opening | Preserved in required package qualification |
| Executable starts through native Windows/macOS integration | Made explicit with a narrow native smoke |
| Exact physical rendering at 100%/150% | Not claimed from hosted CI |
| Human visual polish on both supported platforms | Required only when controlled captures are available and reviewed |

This reduces false release failures without hiding the evidence gap. For normal
code changes, deterministic CI plus native launch smoke is proportionate. For
layout-system changes, Qt upgrades, major OS upgrades, font/icon changes, or a
new supported display/DPI target, controlled evidence and human review should
be a release checklist requirement. If no controlled Mac is available, record
the Mac visual qualification as pending rather than blocking creation of an
unsigned community artifact indefinitely.

## Implementation plan

1. Amend ADR 0206 so native screenshot evidence is a controlled/manual
   layout-release gate, not a GitHub-hosted package-build gate.
2. Split both package scripts into `assemble`, `verify-deterministic`, and
   optional `capture-native-evidence` stages. Default CI packaging must not run
   the optional stage.
3. Remove `evidence_path` and the mandatory evidence upload from the reusable
   hosted workflow. Upload screenshots only from a separately triggered
   controlled-evidence workflow or attach them to a release qualification
   record.
4. Add one cross-platform packaged native-smoke contract with OS adapters. It
   must report plugin, exposure, project-open, R initialization, and exit status
   without exact geometry assertions.
5. Update packaging contract tests: require deterministic tests and native
   smoke in hosted qualification; require the evidence harness/validator to
   remain callable, but not from every package build.
6. Add a controlled-host preflight checking OS/architecture, available geometry,
   effective scaling/DPI/DPR, font availability, screen count, unlocked
   interactive session, and package digest before capture.
7. Preserve generated evidence as immutable release qualification output keyed
   to the package digest. Never rebuild the package merely to obtain evidence.
8. Document an explicit exception: without controlled machines, release notes
   say native visual qualification was not run; deterministic layout tests and
   hosted native smoke still must pass.

## Bottom line

Adaptive-layout evidence should be **removed from GitHub-hosted packaging, not
removed from the project**. Similar tests should be separated by the claim they
make: logical/widget behavior stays in required headless CI; a minimal native
launch flow stays on each hosted OS; exact DPI, native-frame screenshots, and
visual judgment move to controlled machines and manual release qualification.
