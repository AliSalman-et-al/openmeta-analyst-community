## Problem Statement

RC MetaStudio Community is implemented against Qt 5 and PyQt5, including 36 handwritten Qt-bearing source modules, 29 generated form modules, a large generated Python resource module, and 27 Qt-bearing tests. The current dependency, source, generated-code, resource, model, signal, settings, packaging, and verification surfaces therefore cannot simply be relabeled as Qt 6. PyQt6 deliberately removes short enum aliases, moves or replaces classes, tightens value and coordinate types, changes signal overload behavior, and exposes assumptions that PyQt5 tolerated. Qt 6 also changes the native deployment and operating-system baseline, while Apple Silicon introduces a second native macOS architecture across Python, Qt, R, rpy2, and PyInstaller.

The application has not yet had a public release. This creates a one-time opportunity to remove Qt5, pickle project storage, generated-source drift, historical SIP decoding, and binding-specific persisted state before users create durable project files. Carrying a Qt5 compatibility layer or releasing both bindings would turn temporary migration machinery into a permanent support burden.

Users need the first public release to be a clean Native Qt6 Port: the same trusted Analysis Behavior and recognizable workflows, implemented directly with current PyQt6 APIs, using a safe versioned project format, native packages for every release-gated architecture, and automated evidence from the final downloadable artifacts. The planned release date must not override correctness or platform completeness.

## Solution

Perform a Qt6 Hard Cutover to a locked PyQt6 6.11 runtime on Python 3.11. Remove PyQt5 and all runtime compatibility mechanisms, regenerate canonical Designer forms at build time with `pyuic6`, compile the canonical Qt resource collection into a native binary resource, and migrate handwritten Qt code through a fail-closed repository-owned codemod followed by explicit behavioral fixes.

Replace pickle-based `.rcms` projects with a Versioned Project Format: a validated ZIP container containing UTF-8 JSON members governed by committed JSON Schema. Convert every repository sample project before deleting the legacy serializer; do not ship a legacy converter because no pickle-era projects have been publicly released. Save projects atomically and preserve every officially released structured format through explicit JSON-to-JSON migrations.

Preserve Analysis Behavior, canonical workflows, adaptive layout contracts, accessibility, and project semantics while accepting normal native Qt6 visual differences. Use explicit signal connections, typed custom signals and item-model roles, floating-point coordinate types, portable settings, locale-safe persistence and R boundaries, and strict `ty` verification across handwritten Qt modules.

Retain PyInstaller as the sole Qt dependency collector and produce separate native artifacts for Windows x64, macOS Intel x64, and macOS ARM64. Qualify the final downloadable artifacts entirely through automated native-architecture workflows. Release only when source, package, R integration, sample conversion, schema, typing, accessibility, and packaged workflow evidence are green on all three targets.

## User Stories

1. As an RC MetaStudio user, I want the application to run natively on Qt 6, so that the first public release starts from a current supported GUI foundation.
2. As a user, I want every existing analysis workflow to remain available after the port, so that changing GUI frameworks does not remove scientific capability.
3. As a user, I want statistical inputs, model choices, numerical outputs, summaries, and artifacts to remain equivalent, so that the framework migration does not change Analysis Behavior.
4. As a Windows user, I want a native Windows x64 package, so that I can run the application without assembling Python, Qt, or R myself.
5. As a macOS Intel user, I want a native x64 application, so that the Qt6 release continues to run on my supported Mac.
6. As an Apple Silicon user, I want a native ARM64 application, so that I do not depend on Rosetta or an Intel-only runtime stack.
7. As a macOS user, I want architecture-specific artifacts, so that Python, Qt, R, rpy2, and packaged native libraries all match my machine.
8. As a user, I want one supported Qt runtime, so that installation and troubleshooting never depend on choosing between Qt5 and Qt6.
9. As a user, I want project files stored in a documented structured format, so that my research records are not opaque Python pickles.
10. As a user, I want a failed save to leave my existing project intact, so that power loss or serialization errors do not destroy prior work.
11. As a user, I want saved projects validated before replacement, so that corrupt containers are not presented as successful saves.
12. As a user, I want every officially released structured project version to remain readable, so that infrequently reopened research remains usable.
13. As a user, I want unknown or malformed project content rejected with an actionable error, so that silent coercion cannot corrupt an analysis.
14. As a user, I want project-level choices to travel with the project, so that opening the file on another supported computer restores meaningful working context.
15. As a user, I want machine-local window placement and recent paths kept out of the project, so that a shared file does not carry another computer's desktop state.
16. As a user, I want repository sample projects to open in the new release, so that examples and tutorials exercise the actual supported format.
17. As a user, I want converted samples to preserve their original data and analysis selections, so that conversion does not merely produce syntactically valid files.
18. As a user in a comma-decimal locale, I want numeric input, persistence, and analysis to remain correct, so that operating-system locale cannot silently change values.
19. As a user in a dot-decimal locale, I want the same analysis results as a comma-decimal user, so that locale does not affect scientific behavior.
20. As a high-DPI user, I want Qt6-native fractional scaling, so that text, controls, icons, and windows remain sharp and usable.
21. As a user at 125%, 150%, or 175% scaling, I want coordinates and geometry to remain accurate, so that integer truncation does not create clipping or drift.
22. As a multi-monitor user, I want persisted Qt5 geometry reset safely at first Qt6 launch, so that obsolete binary layout state cannot place windows offscreen.
23. As a returning user, I want domain preferences and analysis settings preserved, so that resetting Qt5 GUI state does not erase meaningful choices.
24. As a user, I want normal native Qt6 fonts, spacing, chrome, and platform styling, so that the application feels appropriate on my operating system.
25. As a user, I want recognizable information hierarchy and workflows despite native visual differences, so that I do not need to relearn the application.
26. As a keyboard user, I want every current workflow operable without a pointer, so that the Qt6 port does not reduce accessibility.
27. As a keyboard user, I want visible focus and intentional tab order, so that I can understand and control navigation.
28. As an assistive-technology user, I want icon-only and non-text controls to expose useful names, so that controls remain understandable.
29. As a user with enlarged text or fractional scaling, I want dialogs to remain readable and reachable, so that native Qt6 metrics do not hide controls.
30. As a spreadsheet user, I want copy, paste, undo, redo, and table editing to behave as before, so that data entry remains efficient.
31. As a user, I want actions and shortcuts connected explicitly, so that behavior does not depend on fragile object-name conventions.
32. As a user, I want signal overloads to trigger the intended behavior exactly once, so that PyQt6 overload changes do not duplicate or lose actions.
33. As a user, I want dialogs and windows to close cleanly, so that Qt object-lifetime changes do not produce crashes during shutdown.
34. As a user, I want plots and SVG results to display and export correctly, so that moved graphics and SVG classes do not break analysis artifacts.
35. As a user, I want icons and resources available in packaged applications, so that generated-resource changes do not produce missing controls or blank imagery.
36. As a user, I want file dialogs, menus, printing, clipboard operations, and desktop integration to remain functional, so that moved Qt classes do not remove operating-system workflows.
37. As a user, I want errors from invalid model edits surfaced deliberately, so that stricter item-model typing does not silently discard input.
38. As a user, I want selections, headers, check states, and table flags to behave consistently, so that the PyQt6 item-model contract remains predictable.
39. As a user, I want the application to refuse unsupported operating systems clearly, so that I do not receive a package that Qt6 itself no longer supports.
40. As a Windows 10 1809 or later user, I want the application included in release qualification, so that the documented Windows baseline is real.
41. As a macOS 13 or later user, I want the application included in release qualification, so that the documented macOS baseline is real.
42. As a release user, I want the downloadable artifact itself tested, so that passing source tests cannot hide missing plugins or native libraries.
43. As a release user, I want packaged R and rpy2 integration exercised, so that a GUI that launches but cannot analyze data is not released.
44. As a release user, I want final artifact evidence tied to an exact hash, so that the tested binary can be distinguished from later or local builds.
45. As a maintainer, I want PyQt6, Qt6, SIP, Python, and verification tools locked, so that dependency drift cannot masquerade as a port defect.
46. As a maintainer, I want Designer `.ui` files to remain canonical, so that forms are edited in one authoritative representation.
47. As a maintainer, I want generated form modules produced deterministically outside version control, so that generated diffs do not obscure real interface changes.
48. As a maintainer, I want one canonical resource collection compiled with Qt6 tooling, so that resources cannot be generated by mixed Qt bindings.
49. As a maintainer, I want an idempotent fail-closed codemod, so that mechanical enum and import rewrites are repeatable and ambiguous cases receive review.
50. As a maintainer, I want all handwritten Qt modules checked strictly by `ty`, so that binding and value-type mistakes are found before runtime.
51. As a maintainer, I want no active PyQt5 imports, short enums, removed APIs, stale generated markers, or compatibility facades, so that the hard cutover remains enforceable.
52. As a maintainer, I want explicit coordinate-space and rounding boundaries, so that future layout code cannot reintroduce accidental integer truncation.
53. As a maintainer, I want custom signals to carry narrow declared payloads, so that cross-object contracts are inspectable and testable.
54. As a maintainer, I want application state stored in typed Python objects rather than dynamic Qt properties, so that static checking reflects actual behavior.
55. As a maintainer, I want every item-model role to have an explicit type contract, so that `QVariant` assumptions do not survive the migration.
56. As a maintainer, I want portable versioned settings, so that future Qt upgrades do not require decoding binding-specific objects.
57. As a maintainer, I want a last-known-good PyQt5 baseline tag, so that regressions can be diagnosed without maintaining a second release line.
58. As a reviewer, I want the migration divided into dependency-ordered commits, so that mechanical changes, behavioral fixes, format changes, and packaging changes remain reviewable.
59. As a contributor, I want every PyQt5-era test classified as ported, strengthened, or replaced by named stronger evidence, so that the migration cannot discard inconvenient coverage.
60. As a release maintainer, I want Qt-affecting pull requests checked on all three target architectures, so that platform breakage is discovered before release qualification.
61. As a release maintainer, I want full R-bundled packaged qualification before cutover and release, so that expensive evidence runs at the correct gate.
62. As a release maintainer, I want signing deferred without weakening platform security settings in code, so that pending certificates do not distort the Qt6 implementation.
63. As a future maintainer, I want background analysis execution planned separately, so that responsiveness can improve without mixing thread and R-ownership changes into this cutover.
64. As a project owner, I want the release date to slip rather than waive failed Qt6 gates, so that the first public version does not create avoidable compatibility debt.

## Implementation Decisions

- Make a Qt6 Hard Cutover. PyQt6 is the only supported GUI binding for development, verification, packaging, and release; do not add `qtpy`, a local facade, Qt5Compat, dual imports, environment-selected bindings, or a PyQt5 fallback.
- Lock PyQt6 6.11.0 and its exact resolved Qt6 and SIP wheel set in the dependency lock. Treat upgrades as separate reviewed changes.
- Retain Python 3.11 as the sole runtime with the same pinned patch level across all three packaged targets. Defer Python 3.12 or later.
- Mark the last known-good PyQt5 commit with an immutable annotated baseline tag and archive its dependency lock, Golden Output Bundles, sample semantic snapshots, and representative interface evidence. Do not maintain or package that baseline.
- Enter a feature freeze for the cutover. Permit only Native Qt6 Port work, verification, first-release blockers, and statistically necessary corrections; defer unrelated features, visual redesigns, broad refactors, and dependency refreshes.
- Treat Qt Designer `.ui` files as Canonical UI Forms. Remove generated form modules from version control and generate them deterministically with `pyuic6` into an isolated build location. Do not use runtime `loadUi`.
- Keep the canonical `.qrc` resource collection and compile it into an official Qt6 binary resource. Register it through `QResource`; allow only a small handwritten loader when generated forms require the historical resource-module import name. Do not use PySide tooling, `pyqt6rc`, stale `pyqt6-tools`, or generated Python resource bytes.
- Build a repository-owned LibCST codemod with an explicit mapping manifest. It may rewrite imports and unambiguous scoped enums, must report every transformation, must refuse ambiguous sites, and must produce no diff on a second run.
- Regenerate all generated forms and resources rather than codemodding generated output.
- Move or replace displaced APIs directly in their Qt6 modules, including actions, regular expressions, SVG graphics, desktop/screen access, printing, event handling, and any other removed Qt5 class. Do not emulate removed classes.
- Use scoped PyQt6 enums everywhere. Active short enum aliases are forbidden.
- Preserve `QPointF`, `QRectF`, and other floating-point geometry throughout layout, graphics, mouse, paint, and SVG paths. Convert to integer coordinates only at named APIs that require them, with explicit coordinate space and rounding policy.
- Use native Qt6 fractional scaling with pass-through rounding. Test at 125%, 150%, and 175%; allow an exception only for a documented unavoidable platform defect.
- Preserve adaptive-layout Window Archetypes, Geometry Ownership, Overflow Boundaries, accessibility behavior, and Logical Layout Space. Accept normal native Qt6 differences in font metrics, spacing, widget chrome, and styling; do not reproduce Qt5 pixels.
- Use explicit bound-signal `.connect()` calls only. Disable and remove `connectSlotsByName` from generated output or generation post-processing, and bind overloaded signals explicitly.
- Give every custom signal a narrow declared payload. Require `@pyqtSlot` only at cross-thread, queued, overloaded, or external meta-object boundaries where it adds a concrete contract.
- Do not introduce a new background-worker architecture during the cutover. Preserve current analysis execution semantics while making Qt object ownership, teardown, signal delivery, and shutdown correct. Follow the separate post-release background-analysis plan later.
- Replace application-owned QObject dynamic properties with typed Python attributes or explicit state objects. Allow Designer-generated `setProperty()` only for genuine Qt-declared widget properties.
- Define explicit contracts for every custom item-model role, return documented native Python or Qt values, return `None` for unavailable data, reject invalid edits deliberately, and remove `QVariant.value()` handling.
- Treat `QSettings` as a versioned typed application contract. Route access through the settings boundary; define key types, defaults, validators, and codecs; store portable primitives rather than `QColor`, `QPoint`, `QRect`, `QByteArray`, `QVariant`, or other binding objects.
- On first Qt6 launch, invalidate persisted Qt5 window geometry, window state, splitter blobs, and screen placement. Preserve domain preferences, analysis settings, and recent projects.
- Make locale handling explicit. Store JSON numbers as numbers and temporal values in defined ISO representations, parse and format interface values through deliberate `QLocale` rules, and normalize R-bound values independently of the operating-system locale.
- Replace pickle `.rcms` storage completely. The Qt6 application contains no pickle project reader, historical SIP or Qt-value decoder, runtime fallback, or legacy conversion entry point.
- Before deleting legacy storage, export every committed sample project to the Versioned Project Format and verify project data, analysis selections, state, and representative Analysis Behavior against pre-conversion semantic snapshots.
- Do not ship a pickle converter because no pickle-era application version has been publicly released.
- Define `.rcms` as a ZIP container with UTF-8 JSON members: `manifest.json` for format, application, and integrity metadata; `project.json` for Analysis Behavior inputs and domain data; and `state.json` for durable project-scoped state. Future artifacts may appear only under explicitly versioned named directories.
- Remove the `.rcms.state` sidecar.
- Validate archive member names, member counts, compressed and uncompressed sizes, schemas, and integrity metadata. Never extract arbitrary archive paths.
- Make committed JSON Schema authoritative for every project-format version. Reject unknown properties and unsupported versions rather than coercing them.
- Write only the latest Versioned Project Format. Read every officially released structured version through explicit, pure JSON-to-JSON Project Format Migrations. Retire a released structured version only through a separate breaking-format decision with conversion support available first.
- Store only project-scoped durable choices in `state.json`, including active outcome, analysis selections, project display choices, and artifact metadata. Keep geometry, screen placement, recent paths, theme, and other machine-local preferences in `QSettings`; do not persist focus, temporary selection highlights, or open-dialog state.
- Save `.rcms` atomically: create a complete temporary container on the destination filesystem, validate it, flush it, and replace the target only after success. A failed save leaves the prior file unchanged; temporary files are never silently loaded as projects.
- Retain PyInstaller 6.21 unless the pre-codemod feasibility spike disproves it on a target. Rebuild the specification, hooks, resources, plugin collection, and smoke paths for PyQt6.
- Make PyInstaller the sole Qt dependency collector. Do not overlay `windeployqt` or `macdeployqt`. Generate an explicit deployment manifest and detect duplicate, mismatched, or missing Qt libraries and plugins.
- Produce separate native packages for Windows x64, macOS Intel x64, and macOS ARM64. Do not produce universal2 and do not release-gate Windows ARM64 or Linux.
- Set minimum supported operating systems to Windows 10 version 1809 or later and macOS 13 or later.
- Before the broad codemod, run a feasibility spike on all three native targets proving PyQt6 launch, form generation, binary resource registration, SVG rendering, R/rpy2 operation, PyInstaller collection, platform-plugin loading, and packaged smoke execution.
- Use `ty` as the strict checker for all handwritten Qt-bearing modules. Pin the exact `ty` version in the lock, enable strict rule severity, exclude generated forms, and allow narrow documented ignores only for verified PyQt6 stub defects.
- Add a focused Qt6 strict lane that rejects active PyQt5, Qt5Compat, binding facades, short enums, removed APIs, stale generated markers, and incompatible generated output. Treat Python warnings as errors, import every Qt-bearing module, and use `QT_FATAL_WARNINGS` only in focused GUI and native smoke processes after benign platform warnings are controlled.
- Classify every PyQt5-era test as ported, rewritten at a stronger seam, or retired only in favor of explicitly named stronger evidence. Do not delete, skip, or permanently xfail tests merely because they expose migration work.
- Run source smoke and fast verification for Qt-affecting pull requests on all three targets. Run full R-bundled packaged qualification on scheduled or manual release candidates and require it before cutover and release.
- Automate final artifact qualification on native Windows x64, macOS Intel x64, and macOS ARM64. Automation must exercise the exact downloadable artifact and record its hash, target identity, dependency identities, results, and retained diagnostics. A manual smoke test is not a release gate.
- Defer Developer ID signing, notarization, stapling, and Windows Authenticode signing. Keep macOS packages compatible with future hardened-runtime signing; document unsigned launch guidance accurately and do not weaken security settings programmatically.
- Preserve existing GPLv3 license and notice practices. Do not add an SBOM generator or a separate automated license-compliance pipeline during the cutover.
- Land the migration as dependency-ordered, reviewable commits: locked toolchain and generators; Versioned Project Format and samples; mechanical rewrites; handwritten behavioral and typing fixes; packaging and native evidence; final deletion and strict-policy enforcement.
- Allow the public release date to slip. Missing or waived target, R, schema, sample, typing, accessibility, source, or packaged evidence blocks release.

## Testing Decisions

- Prefer the highest existing behavioral seams. Analysis compatibility is proven through Golden Analysis Tests at the Analysis Adapter rather than widget internals. Project compatibility is proven through schema validation, semantic sample conversion, save/open round trips, and analysis results. GUI compatibility is proven through real interactions and established layout contracts. Release readiness is proven through the final packaged artifact.
- Good tests assert externally observable behavior: projects retain their data and choices; analyses retain numerical and artifact outputs; users can reach and operate controls; signals cause the intended action once; models expose correct roles; packages launch and complete workflows. Avoid asserting codemod internals, generated source text, private helper call order, or incidental native pixels.
- Preserve and extend the Curated Golden Set and Workflow Traceability Manifest. Capture the pre-cutover PyQt5 semantic baseline before dependency changes, then compare Qt6 results within existing tolerances and exception policies.
- Validate every converted committed sample against a normalized semantic representation, open it through the Qt6 application, run its representative analysis path, save it, reopen it, and compare again.
- Test Project Format Schemas with valid files, missing members, duplicate or unknown members, unknown fields, wrong versions, malformed JSON, invalid types, oversized entries, excessive compression ratios, bad integrity metadata, and archive traversal names.
- Test every Project Format Migration independently and as a chain from each released structured version to the latest. Require deterministic output and semantic equivalence.
- Test atomic save success and injected failures before write, during serialization, during validation, during flush, and before replacement. Verify the original file remains readable and temporary-file recovery never silently substitutes data.
- Extend existing settings tests to cover typed codecs, defaults, validation, schema-version reset, preservation of domain settings, and removal of Qt5 geometry and binding-specific stored objects.
- Run locale tests under at least one dot-decimal and one comma-decimal locale. Prove equivalent input interpretation, JSON round trips, R-bound data, Analysis Behavior, and displayed results.
- Test the LibCST codemod against representative import and enum fixtures, ambiguous refusal cases, a transformation report, and a second-run no-diff invariant. The application-wide strict scan is the higher completion seam.
- Regenerate every Canonical UI Form in CI and compare generated build outputs or generation manifests deterministically. Verify there are no checked-in generated form modules and no runtime form loading.
- Compile and register the Qt6 binary resource in source and packaged tests. Exercise functional icons, SVG content, and every resource prefix used by generated forms.
- Import every handwritten Qt-bearing module under PyQt6 with warnings treated as errors. Run `ty` across the full handwritten Qt surface with no broad excludes or unexplained suppressions.
- Add static policy tests rejecting PyQt5 imports and requirements, compatibility packages, Qt5Compat, binding-selection code, short enums, `QRegExp`, removed/moved imports, `connectSlotsByName`, application-owned dynamic Qt properties, `QVariant.value()`, stale PyQt5 generator markers, generated Python resource bytes, and runtime pickle project readers.
- Test every custom signal's payload, explicit overload selection, connection count, lifetime behavior, and any cross-thread or queued delivery contract. Verify action handlers fire exactly once.
- Extend custom model tests for valid and invalid indexes, each supported role, headers, flags, editing, resets, check states, signal payloads, sorting, copy/paste, undo, and redo.
- Test floating-point geometry through graphics, SVG, mouse, paint, layout, and screenshot paths. Verify named integer boundaries and rounding behavior at 100%, 125%, 150%, and 175% scale factors.
- Preserve the adaptive-layout contract audit across every Window Archetype. Verify required controls remain reachable, focus and tab order remain usable, Overflow Boundaries work, restored placement is screen-safe, and native visual differences do not alter workflow.
- Add accessibility tests for keyboard-only completion, visible focus, intentional tab traversal, accessible names for icon-only controls, readable scaling, and operable dialogs. Port-created regressions block release.
- Exercise moved and replaced Qt APIs through their user-facing seams: actions and shortcuts, regular-expression validation, file dialogs, screens and placement, SVG/graphics rendering, printing where supported, clipboard, timers, menus, close events, and application shutdown.
- Run a source GUI smoke on every Qt-affecting pull request for Windows x64, macOS Intel x64, and macOS ARM64. Use real platform plugins where runner capabilities allow; offscreen tests alone are not completion evidence.
- Run full bundled R and rpy2 verification in the package qualification lane. Verify actual R runtime identity, required package identities, representative analysis calls, error propagation, and generated artifacts.
- Build packages from the frozen lock and inspect the deployment manifest for one coherent Qt runtime, correct architecture, required image and platform plugins, binary resource presence, and absence of PyQt5 or duplicate Qt collectors.
- Launch each final downloadable artifact by its user-facing entry point on its native architecture. Automation opens every converted sample, runs representative analyses, verifies result text and SVG, saves and reopens a project, exercises clipboard and critical dialogs, and proves clean shutdown.
- Tie qualification results to the artifact's cryptographic hash, OS version, architecture, Python/PyQt6/Qt/R identities, workflow results, logs, and retained failure screenshots or diagnostics.
- Keep `QT_FATAL_WARNINGS` scoped to controlled GUI and packaged smoke processes. First classify and eliminate application-owned warnings so benign operating-system noise does not make the broad suite nondeterministic.
- Final acceptance requires all three native feasibility results, strict source lanes, classified legacy tests, schema and migration tests, converted-sample evidence, Golden Analysis Tests, accessibility and layout evidence, bundled R verification, deployment inspection, and final artifact automation to pass. No manual signoff substitutes for a failed automated gate.

## Out of Scope

- Supporting PyQt5 and PyQt6 simultaneously or retaining any Qt binding compatibility layer.
- PySide6, `qtpy`, Qt5Compat, runtime binding selection, or a user-facing Qt5 fallback.
- A clean-sheet GUI redesign, navigation rewrite, theme replacement, or broad refactor unrelated to making the existing application native and correct under Qt6.
- Changing Analysis Behavior, statistical methods, numerical tolerances, R results, plot semantics, or workflow choices except through the existing reviewed Compatibility Exception process.
- Introducing a general background thread, worker process, cancellation, or progress architecture. That work follows the separate post-release plan.
- Supporting Linux or Windows ARM64 as release-gated platforms.
- Producing a macOS universal2 application; Intel and Apple Silicon packages remain separate.
- Upgrading to Python 3.12 or later.
- Replacing PyInstaller unless the required three-platform feasibility spike proves it unsuitable.
- Shipping or retaining a pickle-era `.rcms` converter, runtime pickle reader, SIP decoder, or compatibility import path.
- Preserving obsolete Qt5 geometry, splitter blobs, screen placement, generated form modules, or generated Python resource bytes.
- Developer ID signing, notarization, stapling, Windows Authenticode signing, or certificate automation for the first release.
- Adding a new SBOM or license-compliance automation pipeline.
- Requiring human screenshot or packaged smoke approval as a release gate; qualification is automated.
- Preserving Qt5 pixel rendering or exact screenshot equality across native platforms.
- Waiving a failed target to preserve the planned first-public-release date.

## Further Notes

- The Native Qt6 Port research report and ADR-0229 through ADR-0274 are the supporting research and decision record. ADR-0170 and ADR-0173 are superseded where they retain Qt5 or omit Apple Silicon.
- The repository audit found 98 PyQt5-bearing files: 36 handwritten source modules, 29 generated form modules, one generated resource module, and 27 tests. It also found 29 canonical `.ui` forms, one canonical `.qrc`, at least 241 short enum uses, and multiple removed or displaced APIs. The implementation should refresh these counts before and after the codemod and make zero active legacy findings a completion condition.
- The implementation should preserve the established Analysis Compatibility, Window Archetype, Plot Artifact, Golden Analysis Test, and release-evidence vocabulary rather than creating parallel terminology.
- The first public release is currently planned soon, but this specification is evidence-gated, not date-gated. The feature freeze and dependency-ordered commit sequence exist to make the work tractable without weakening acceptance criteria.
- Signing is deferred because the Apple Developer certificate is pending and Windows signing is not currently required. This does not permit ad hoc platform-security bypasses in the application.
- The project has no publicly released pickle-era files, which is why deleting legacy project support is safer and simpler than shipping a migration product. Only repository-owned samples require controlled pre-cutover export.
