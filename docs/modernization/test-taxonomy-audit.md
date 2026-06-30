# Modern Test Taxonomy Audit

Initial audit for ADR 0079. This file records the starting classification used to split CI lanes; runtime classes are initial estimates until replaced by measured `pytest --durations` data.

## Summary

- Collected pytest nodes: 130
- Lanes: fast=26, golden=17, gui=65, packaging_contract=13, r_stack=9
- Sizes: large=59, medium=32, small=39
- Decisions: keep=130 after the first packaging contract reclassification and lane-directory move.

## Audit Posture

The taxonomy manifest is now a Taxonomy Enforcement Backlog, not a preservation list. Tests should be marked `rewrite`, `merge`, `move`, or `remove` as soon as the audit identifies the decision, even when the implementation follows later. Deletions remain conservative: remove a test only when stronger evidence, a merge target, or an ADR makes the current node obsolete.

The Fast Verification Lane has a hard Fast Feedback Budget: under ten minutes on GitHub and under two minutes locally after dependencies are warm. Tests or verification steps that cannot meet that budget should move to GUI, R Stack, Packaging Lane, scheduled, or release-gated evidence unless they are required release evidence for ordinary pull requests.

Add a Smoke Verification Lane before the broader Fast Verification Lane. Its target is under thirty seconds locally after dependencies are warm, and it should contain only the highest-signal checks needed to fail early: pytest collection, manifest sanity, one representative Golden Analysis Test parser/comparison check, one project-load compatibility check, and a Default R Evidence prerequisite check.

The Packaging Lane should run on pull requests only when packaging-relevant paths change, and should always remain available for release tags and manual dispatch. Packaging-relevant paths include packaging scripts, packaging workflows, Python lock/configuration files, R package/dependency inputs, launch entry points, bundled sample data, and bundled documentation.

The next packaging reproducibility target is deterministic process and artifact layout, not byte-identical ZIPs. Acceptance should focus on clean rebuilds, stable inputs, stable artifact contents/layout, explicit cache keys, and documented non-determinism.

R package downloads from CRAN are a known productivity bottleneck. R dependency installation should use an explicit CRAN Repository Policy, support faster reliable CRAN-compatible mirrors where appropriate, and reuse an R Dependency Cache for Full R Stack Evidence and Packaging Lane runs. The default smoke and fast lanes should not perform broad live CRAN downloads.

Once the first backlog classification pass lands, GitHub should run taxonomy validation in strict mode so collected pytest nodes cannot drift from the manifest. Local Fast Verification Lane commands may remain non-strict during active cleanup so developers can iterate while they update classifications.

After the manifest is accurate, reorganize `tests/modern` into lane and ownership directories such as `fast`, `gui`, `r_stack`, `golden`, `packaging_contract`, and `packaged_smoke`. Markers remain the selectable execution mechanism; directories make ownership, review scope, duplicate coverage, and safe parallelism boundaries visible.

Selected R Stack evidence tests should not skip opportunistically when R, rpy2, or required R packages are missing. R Stack lane prerequisites should be checked before pytest starts, so a selected required lane either runs with the expected environment or fails at setup. Degraded Local R Evidence remains local-only and does not satisfy required CI evidence.

## Adopted Standards

The rebuilt workflow should use well-known, widely adopted CI and testing practices before adding project-specific rules:

- Use registered pytest markers and marker expressions for selectable lanes, following pytest's documented custom-marker and `-m` selection model.
- Keep a fast required pull-request lane separate from slower GUI, R Stack, packaging, scheduled, and release-gated lanes.
- Cache dependency inputs keyed by lockfiles and dependency manifests, following GitHub Actions dependency caching guidance; do not treat assembled application directories or final distributable archives as trusted cache inputs.
- Use GitHub Actions path filters and concurrency cancellation to avoid irrelevant packaging runs and superseded branch runs.
- Pin third-party GitHub Actions by commit SHA in required CI and packaging workflows, including checkout, cache, setup, and artifact upload actions; update those pins deliberately.
- Keep CI evidence fail-closed and reproducible, while allowing explicitly named local degraded modes for missing workstation dependencies.
- Always run locked dependency sync in CI, but let warm local verification skip dependency sync by default unless the lock/config changed or the developer explicitly requests sync/recreate.
- Configure R dependency acquisition explicitly and cache installed R dependency inputs so slow CRAN downloads are not repeated unnecessarily.
- Move toward hermetic and reproducible build practices in the SLSA sense: explicit inputs, minimized network use in default verification, clean rebuilds of outputs, and documented non-determinism before byte-for-byte reproducibility is attempted.

References:

- pytest examples and custom markers: https://docs.pytest.org/en/stable/example/index.html
- pytest marker registration: https://docs.pytest.org/en/stable/how-to/writing_plugins.html#registering-custom-markers
- GitHub Actions dependency caching: https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching
- GitHub Actions workflow syntax, path filters, and concurrency: https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions
- SLSA build requirements: https://slsa.dev/spec/v0.1/requirements

## Cleanup Themes

- The GUI and real R Stack tests are large integration evidence and should not define the default fast feedback loop.
- Packaging contract tests were the first rewrite target; the current contract tests now use structured parsers and live in the `packaging_contract` lane directory.
- Removed three low-signal source-text checks that duplicated behavior covered by focused GUI startup, packaging smoke, and R-stack verification tests.
- Tests with opportunistic R skips should move behind Default R Evidence or Full R Stack Evidence instead of being treated as ordinary fast tests.
- Replace opportunistic R Stack `pytest.skip()` paths with lane-level prerequisite checks.
- pytest-xdist is enabled only for the required fast feedback directories: `tests/modern/fast`, `tests/modern/golden`, and `tests/modern/packaging_contract`. GUI, R Stack, and packaged smoke evidence remain serialized unless a future isolation review proves they are safe to parallelize.

## Next Audit Work

- Replace estimated runtime classes with measured durations.
- Continue reclassifying low-value and duplicate nodes beyond the first packaging contract batch.
- Keep the new Smoke Verification Lane focused as additional smoke candidates are proposed.
- Keep third-party GitHub Actions pinned by commit SHA when workflows change.
- Keep local smoke/fast verification warm by default; CI continues to sync locked dependencies every run.
- Continue improving R dependency cache behavior after measuring warm and cold Full R Stack Evidence and Packaging Lane runs.
- Keep Packaging Lane triggers path-aware for pull requests and unconditional for release/manual packaging runs.
- Continue packaging contract cleanup as new script/workflow contracts are added; GUI and R Stack pruning should wait until their compatibility evidence is reviewed more carefully.
- Keep lane and ownership directories aligned with the taxonomy manifest.
- Identify duplicate GUI coverage after the directory move.
- Continue replacing raw string assertion tests with structured contracts during packaging contract cleanup.
- Add R Stack lane setup checks before converting R Stack skips into hard failures.
