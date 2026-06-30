# Modern Build and Test Workflow Plan

This plan turns the Modern CI Path optimization decisions into small, reviewable implementation slices. It is governed by [ADR 0078](../adr/0078-split-modern-ci-verification-from-packaging.md), [ADR 0079](../adr/0079-audit-modern-tests-before-restructuring-ci.md), [ADR 0080](../adr/0080-fail-closed-on-ci-r-evidence.md), and the [Test Taxonomy & Audit](test-taxonomy-audit.md).

## Goals

- Keep required pull-request feedback under ten minutes on GitHub.
- Keep warm local smoke/fast verification under two minutes, with smoke under thirty seconds.
- Make CI fail closed while preserving explicitly named local degraded modes.
- Remove CRAN download speed from default local and pull-request feedback.
- Cache dependency inputs, not assembled application outputs.
- Rebuild packaging outputs cleanly and deterministically enough for layout/content reproducibility.
- Replace low-value source-text assertions with Structured Contract Tests.
- Rebuild the modern pytest workflow around evidence, runtime, dependencies, and lane ownership.

## Adopted Standards

- pytest registered markers and `-m` marker expressions for selectable lanes.
- Separate fast required PR checks from slower GUI, R Stack, packaging, scheduled, and release-gated evidence.
- GitHub Actions dependency caching keyed by lockfiles and dependency manifests.
- GitHub Actions path filters and concurrency cancellation for expensive workflows.
- Commit-SHA-pinned third-party GitHub Actions in required CI and packaging workflows.
- SLSA-style explicit inputs, minimized default-network behavior, clean output rebuilds, and documented non-determinism.

## Redundant Work and Bottleneck Audit

- R dependency installation now uses `OMA_CRAN_REPO`, defaulting to `https://cloud.r-project.org`, instead of hard-coding the CRAN origin mirror.
- Full R Stack Evidence now accepts an R dependency cache root and copies cached dependencies into a clean per-run verification library before building, checking, and installing OpenMetaR.
- Windows and macOS packaging wrappers pass a shared R package cache root into Full R Stack Evidence and package assembly.
- Smoke/Fast Default R Evidence uses a separate `r-default-library-cache` cache root so the required fast workflow does not restore the larger bundled-R packaging cache.
- GitHub R dependency caches use exact v2 cache keys without broad `restore-keys`; stale cache directories must not be merged into a new cache archive.
- R package cache keys now include R version, installer script, dependency manifest, OpenMetaR package metadata, and CRAN repository policy.
- Warm local smoke/fast verification now skips `uv sync --locked` unless `-Sync` or `-RecreateVenv` is requested.
- GitHub smoke/fast verification calls strict R evidence and taxonomy flags explicitly.
- GitHub smoke/fast verification runs on pull requests and manual dispatch rather than every feature-branch push.
- GitHub pull requests always run a lightweight Modern Fast Gate classifier so required checks do not get stuck pending when Windows lanes are intentionally skipped.
- GitHub package verification runs only by manual dispatch or release tags, so ordinary PR iteration does not build distributable artifacts unless explicitly requested.
- GitHub R library cache keys include the R version resolved from the runner after `setup-r`, so a new R release cannot primary-hit an old outer cache while rebuilding a different inner dependency directory.
- GitHub jobs use explicit timeouts to cap runaway runner usage.
- Packaging contract tests now use structured parsers for workflows and scripts; the rewritten nodes live under the `packaging_contract` lane directory.
- Modern tests now live under lane/ownership directories: `fast`, `golden`, `gui`, `r_stack`, `packaging_contract`, and reserved `packaged_smoke`.
- Fast verification now runs the required fast feedback directories with a bounded pytest-xdist worker count while keeping GUI, R Stack, and packaged smoke evidence out of parallel execution.

## Phase 1: Smoke Lane and Local Sync Split

Deliverables:

- `scripts/verify-modern-smoke.ps1`
- `scripts/verify-modern-smoke.sh`
- Updated `scripts/verify-modern-fast.ps1`
- Updated `scripts/verify-modern-fast.sh`
- Updated `.github/workflows/modern-fast.yml`
- Updated README and `docs/agents/testing.md` command matrix

Steps:

1. Add smoke verification scripts with sync and strict R evidence options.
2. Update fast verification scripts so local runs skip dependency sync by default, sync flags perform `uv sync --locked`, and recreate flags rebuild `.venv` before syncing.
3. Make GitHub call smoke and fast scripts with sync and strict evidence flags.
4. Run Smoke Verification Lane as a separate required GitHub job, with Fast Verification Lane depending on it.
5. Keep smoke focused on collection, manifest sanity, one representative golden/parser check, one project-load compatibility check, and Default R Evidence prerequisites.

Acceptance:

- Warm local smoke runs under thirty seconds.
- Warm local fast verification runs under two minutes.
- GitHub still performs locked dependency sync every run.
- Broken collection or missing required R prerequisites fail early.

## Phase 2: R Package Download and Cache Optimization

Deliverables:

- Configurable CRAN repository policy in `scripts/install-modern-r-deps.R`
- Shared R dependency cache policy for Full R Stack Evidence and Packaging Lane
- Updated workflow cache keys
- Documentation for local R package cache setup

Steps:

1. Replace the hard-coded CRAN origin with a configurable repository value, such as `OMA_CRAN_REPO`, defaulting to a documented reliable binary-capable mirror.
2. Evaluate and document using Posit Package Manager or another reliable CRAN mirror for faster binary/package resolution where appropriate.
3. Include CRAN repository policy, R version, installer script hash, dependency manifest hash, and `src/R/OpenMetaR/DESCRIPTION` hash in R cache keys.
4. Use a persistent local R package cache root for Full R Stack Evidence so local re-runs do not always rebuild from an empty temporary library.
5. Keep CI cache restoration explicit and visible. Cache dependency libraries; never cache final app directories or ZIPs as trusted outputs. Do not use broad restore prefixes for R library caches because stale cache directories can make each saved cache larger than the active dependency library.
6. Keep archived `HSROC` pinned to the exact archive URL/version unless a future ADR changes it.

Acceptance:

- Full R Stack Evidence and Packaging Lane can reuse cached R dependency inputs on warm runs.
- Cold CRAN downloads are isolated to explicit R Stack or Packaging Lane runs, not default smoke/fast verification.
- Cache misses are obvious in logs.
- Changing R dependency policy invalidates the relevant cache.

## Phase 3: CI Fail-Closed R Evidence

Deliverables:

- Required CI Default R Evidence that fails when R or direct required packages are missing/wrong.
- Local Degraded Local R Evidence mode remains explicitly named.
- Lane-level R Stack prerequisite check before selected R Stack pytest tests run.

Steps:

1. Make CI call Default R Evidence with strict requirements for R and installed direct package versions.
2. Keep local degraded behavior as the default warm local mode, with strict mode available through explicit flags.
3. Move R/rpy2/package availability checks to lane setup before pytest starts.
4. Replace selected R Stack `pytest.skip()` paths with hard setup failures for required lanes.

Acceptance:

- CI cannot pass required R evidence as manifest-only evidence.
- Selected R Stack lanes either run in the expected environment or fail before pytest starts.
- Local missing-dependency output is clearly labeled as degraded and not CI-equivalent.

## Phase 4: Packaging Contract Rewrite

Deliverables:

- Structured Contract Tests replacing the first batch of raw string assertions.
- Updated `docs/modernization/test-taxonomy.json` decisions for rewrite/merge/remove candidates.

Steps:

1. Start with `tests/modern/packaging_contract/test_windows_distributable_contract.py`.
2. Replace workflow string assertions with structured workflow parsing.
3. Replace script substring checks with structured function, parameter, environment, path, option, and ordering checks.
4. Mark rewritten packaging contract tests for the lane-directory move in the taxonomy manifest.

Acceptance:

- No newly added packaging contract test asserts raw script/YAML/source substrings as its primary contract shape.
- First rewritten tests still protect the same packaging and workflow contracts.
- The taxonomy manifest stops reporting every node as `keep`.

## Phase 5: GitHub Workflow Hardening

Deliverables:

- SHA-pinned third-party GitHub Actions.
- Strict taxonomy validation in GitHub after the first backlog classification pass.
- Path-aware Packaging Lane remains scoped to packaging-relevant PR changes.

Steps:

1. Resolve exact commit SHAs for the currently intended action releases.
2. Pin checkout, cache, setup, and artifact upload actions by SHA.
3. Keep workflow permissions minimal.
4. Enable `validate_test_taxonomy.py --strict` in GitHub after manifest decisions are updated.

Acceptance:

- Required CI and packaging workflows use SHA-pinned actions.
- Taxonomy drift fails in GitHub after the first classification pass.
- Packaging still runs for release/manual requests and packaging-relevant PR paths.

## Phase 6: Test Layout and Cleanup

Deliverables:

- Lane/ownership directories under `tests/modern`.
- Rewritten, merged, moved, or removed Low-Value Tests.
- Updated GUI and R Stack evidence ownership.

Steps:

1. Move tests only after the taxonomy manifest is accurate.
2. Use directories for ownership and markers for selection.
3. Defer GUI/R pruning until compatibility evidence is reviewed carefully.
4. Isolate shared state: cwd, environment variables, QSettings, QApplication, `r_tmp`, R libraries, build directories, and artifacts.

Acceptance:

- Suite layout matches the taxonomy.
- Fast tests are mostly small/medium and isolated.
- GUI, R Stack, golden, packaging, and packaged smoke evidence have clear ownership.

## Phase 7: Fast-Lane Parallelism

Deliverables:

- pytest-xdist for the isolated fast feedback directories only.

Steps:

1. Prove fast tests are isolated from shared global state.
2. Add parallelism only for isolated fast tests.
3. Keep GUI, R Stack, and packaged smoke serialized or process-isolated until proven safe.

Acceptance:

- Parallelism improves fast-lane runtime without introducing flakes.
- Shared-state lanes remain serialized unless explicitly isolated.

## First Milestone Issue Slices

1. **Add Smoke Verification Lane and local sync controls** - implemented in this slice.
   - Blocked by: None.
   - Covers: smoke script, `-Sync`/`-RecreateVenv`, separate GitHub smoke job, fast job dependency.

2. **Make R dependency acquisition cache-aware and mirror-configurable** - implemented in this slice.
   - Blocked by: None.
   - Covers: CRAN mirror policy, R cache keys, local persistent cache option, no redundant CRAN downloads on warm R/package runs.

3. **Fail closed on required CI R evidence** - implemented for smoke/fast CI entry points in this slice.
   - Blocked by: R cache/mirror policy can proceed in parallel but should land before hardening if CI reliability depends on it.
   - Covers: strict Default R Evidence in CI, lane-level R prerequisites, removal of opportunistic selected-lane skips.

4. **Rewrite first packaging contract tests as Structured Contract Tests** - implemented for the Windows/package workflow contract cluster in this slice.
   - Blocked by: None.
   - Covers: YAML parsing, script contract parsing/dry-run checks, taxonomy decisions for rewritten nodes.

5. **Pin GitHub Actions and enable strict taxonomy after manifest updates** - implemented for current fast/package workflows in this slice.
   - Blocked by: first taxonomy backlog classification update.
   - Covers: SHA-pinned actions, strict CI taxonomy validation.

6. **Reclassify taxonomy backlog for first cleanup batch** - implemented for the packaging contract cluster in this slice.
   - Blocked by: packaging contract rewrite findings.
   - Covers: `keep`, `rewrite`, `merge`, `move`, and `remove` decisions for the first low-value cluster.

## Suggested Commit Sequence

1. Update docs with smoke, fail-closed R evidence, R cache/mirror policy, and first milestone plan.
2. Add smoke script and local sync controls.
3. Add R mirror/cache policy and update cache keys.
4. Make CI-required Default R Evidence strict.
5. Rewrite first packaging contract tests.
6. Update taxonomy manifest decisions for the first cleanup batch.
7. Pin GitHub Actions by SHA.
8. Enable strict taxonomy in GitHub.
9. Move tests into lane directories after manifest accuracy is proven.
10. Add fast-lane parallelism only after isolation cleanup.
