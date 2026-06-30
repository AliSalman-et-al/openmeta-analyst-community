# Modern Build and Test Workflow Plan

This plan turns the Modern CI Path optimization decisions into small, reviewable implementation slices. It is governed by [ADR 0078](../adr/0078-split-modern-ci-verification-from-packaging.md) and [ADR 0079](../adr/0079-audit-modern-tests-before-restructuring-ci.md).

## Goals

- Keep default local and pull-request feedback under the Fast Feedback Budget of ten minutes.
- Make the Fast Verification Lane deterministic, no-network by default, and focused on source correctness.
- Move distributable assembly into an explicit Packaging Lane.
- Rebuild the modern pytest workflow around evidence, runtime, dependencies, and lane selection.
- Keep packaging clean and idempotent by caching dependency inputs and rebuilding outputs.
- Improve macOS packaging scripts as opt-in ad-hoc artifact producers, without treating them as signed release distribution.

## External Standards

- DORA test automation: fast, reliable automated feedback, with local and CI feedback expected within minutes.
- pytest documentation: registered custom markers and `-m` selection for intentional lane execution.
- uv GitHub integration: `uv sync --locked`, `uv run`, setup-uv caching, and CI cache pruning.
- GitHub Actions caching and security guidance: lockfile-derived cache keys, least permissions, and SHA-pinned third-party actions.
- SLSA, OpenSSF Scorecard, and Reproducible Builds guidance: locked inputs, explicit provenance direction, stable metadata, and documented non-determinism.
- PyInstaller macOS guidance and Apple notarization guidance: ad-hoc macOS artifacts are distinct from Developer ID signing and notarized release distribution.

## Phase 1: Test Taxonomy & Audit

Deliverables:

- `docs/modernization/test-taxonomy.json`
- `docs/modernization/test-taxonomy-audit.md`
- Registered pytest markers in `pyproject.toml`

Steps:

1. Collect pytest node IDs with `uv run pytest tests\modern --collect-only -q`.
2. Measure runtime with `uv run pytest tests\modern --durations=0 --durations-min=0.1`.
3. Classify every test by size, evidence type, lane, external dependencies, runtime class, and decision.
4. Identify Low-Value Tests for remove, rewrite, merge, or move.
5. Register markers: `fast`, `gui`, `r_stack`, `golden`, `packaging_contract`, `packaged_smoke`, and `slow`.
6. Add an audit script that can compare collected pytest nodes against the taxonomy manifest in report-only mode.

Acceptance:

- Every currently collected modern test appears in the taxonomy manifest.
- The markdown audit names the main cleanup themes and the first rewrite/removal candidates.
- CI does not fail on taxonomy drift yet.

## Phase 2: Fast Verification Lane

Deliverables:

- `scripts/verify-modern-fast.ps1`
- `scripts/verify-modern-fast.sh`
- `.github/workflows/modern-fast.yml`
- Updated README and `docs/agents/testing.md` command matrix

Steps:

1. Create lane-named local scripts for locked sync, manifest validation, selected pytest lanes, and Default R Evidence.
2. Replace filename-based test selection with marker selection.
3. Keep Fast Verification no-network by default except trusted setup/cache restoration.
4. Add a `modern-fast` workflow for push and pull request.
5. Retire `run-modern-workflow-local.*` instead of preserving compatibility wrappers.

Acceptance:

- The fast lane is the documented daily local command.
- The fast lane excludes PyInstaller, bundled R runtime assembly, packaged smoke tests, ZIP creation, and artifact upload.
- The lane is designed to stay under ten minutes; any over-budget check is moved or split.

## Phase 3: R Evidence Split

Deliverables:

- `scripts/verify-modern-r-default.ps1` or shared helper used by the fast lane
- `scripts/verify-modern-r-stack-full.ps1`
- `scripts/verify-modern-r-stack-full.sh`

Steps:

1. Extract Default R Evidence from `scripts/verify_openmetar_r_stack.py`.
2. Keep broad R dependency installation, `R CMD build`, `R CMD check`, analysis smoke, installed-version verification, and real rpy2 bridge tests in Full R Stack Evidence.
3. Make full R Stack verification opt-in, scheduled, release-triggered, or packaging-gated.
4. Ensure cache keys include R version and R dependency policy hash.

Acceptance:

- Default PR verification does not perform broad live CRAN package installation.
- Full R Stack Evidence still protects the OpenMetaR R Stack Slice.

## Phase 4: Packaging Lane

Deliverables:

- `scripts/package-modern-windows.ps1`
- `scripts/package-modern-macos.sh`
- `.github/workflows/modern-package.yml`
- Removed or retired `scripts/run-modern-workflow-local.*`

Steps:

1. Split packaging workflows from fast verification.
2. Run packaging on `workflow_dispatch`, release/tag events, and packaging-relevant path changes.
3. Cache dependency inputs only: uv cache, R package cache, and explicitly invalidated PyInstaller cache where safe.
4. Rebuild assembled app directories and ZIPs cleanly every packaging run.
5. Keep Windows as the default package target.
6. Improve macOS scripts as explicit ad-hoc x64 and arm64 artifact producers with target architecture, bundle identifier, disk checks, clean temp/output handling, layout assertions, and smoke checks.
7. Leave Developer ID signing, hardened runtime, notarization, stapling, and release secrets to a later release-stage design.

Acceptance:

- Packaging no longer runs on every ordinary PR/push.
- Windows packaging remains available as the maintained distributable target.
- macOS packaging is manual and architecture-specific.
- Final artifacts are rebuilt from clean outputs, not restored from cached assembled directories.

## Phase 5: Test Restructure and Cleanup

Deliverables:

- Directory layout under `tests/modern/fast`, `gui`, `r_stack`, `golden`, `packaging_contract`, and `packaged_smoke`
- Rewritten or removed Low-Value Tests
- Updated GUI verification evidence links where files move

Steps:

1. Move tests according to the taxonomy.
2. Remove tests made obsolete by ADRs or stronger evidence.
3. Rewrite raw text assertions outside `packaging_contract`.
4. Keep packaging-contract text assertions only when they guard an explicit release failure mode.
5. Replace ad hoc skip behavior with lane-aware dependency checks.
6. Isolate shared state: cwd, environment variables, QSettings, QApplication, `r_tmp`, build directories, and artifacts.

Acceptance:

- The suite layout matches the taxonomy.
- Fast tests are mostly small or medium and isolated.
- GUI, R Stack, and packaged smoke tests have clear lane ownership.

## Phase 6: Enforcement and Parallelism

Deliverables:

- Taxonomy validation script in warning mode, then hard-fail mode
- pytest-xdist or equivalent parallel execution for isolated fast tests

Steps:

1. Add CI warning output for missing taxonomy entries or marker mismatches.
2. Turn taxonomy validation into a hard gate after the suite is moved and cleaned.
3. Add parallel execution for isolated fast tests.
4. Keep GUI, R Stack, and packaged smoke serialized or process-isolated until proven safe.

Acceptance:

- New tests cannot silently bypass taxonomy classification.
- Parallelism improves fast-lane runtime without introducing shared-state flakes.

## Suggested Commit Sequence

1. Add taxonomy manifest/report generator and marker registration.
2. Commit the first taxonomy audit.
3. Add `verify-modern-fast` scripts and `modern-fast.yml`.
4. Split Default R Evidence from Full R Stack Evidence.
5. Add full R Stack verification scripts.
6. Add packaging scripts and `modern-package.yml`.
7. Retire `run-modern-workflow-local.*` and update docs.
8. Move tests into taxonomy directories.
9. Remove or rewrite Low-Value Tests.
10. Add taxonomy warning gate.
11. Add taxonomy hard gate.
12. Add fast-lane parallelism.

