# Audit modern tests before restructuring CI

The Modern CI Path will start its testing rebuild with a Test Taxonomy & Audit before changing selective CI execution. The audit should classify each modern test by the evidence it carries and may recommend adding, removing, or rewriting tests instead of preserving the current suite shape by default.

A modern test is Low-Value when it asserts script or source text instead of executable behavior without being an explicit packaging-contract guard, duplicates stronger coverage without improving failure localization, preserves obsolete migration scaffolding, skips opportunistically while still being treated as required evidence, or imposes runtime/flakiness cost without protecting Analysis Behavior, GUI compatibility, R Stack integration, packaging, or release readiness. Removal should stay conservative: delete only when stronger coverage or an ADR makes the test obsolete; otherwise rewrite or reclassify it first.

The rebuilt test layout should use both directories and registered pytest markers. Directories express ownership and navigability, such as `fast`, `gui`, `r_stack`, `golden`, `packaging_contract`, and `packaged_smoke`; markers express selectable execution lanes and cross-cutting dependencies using the same vocabulary plus `slow` where needed.

The Test Taxonomy & Audit should produce both a committed machine-readable manifest and a human-readable audit report. The manifest should classify each pytest node by size, evidence type, lane, external dependencies, runtime class, and keep/rewrite/remove/move decision; the report should summarize cleanup themes and sequencing.

Tests should not assert raw script, YAML, or source text except in a narrow `packaging_contract` lane with an explicit contract reason. Preferred tests execute behavior or parse structured files; source-text assertions outside `packaging_contract` are rewrite or removal candidates unless they protect a documented release failure mode.

Taxonomy enforcement should be phased. The first milestone records the manifest and audit without failing CI, the second reports unclassified or incorrectly marked tests as warnings, and the third fails CI when collected pytest nodes are missing from the taxonomy manifest, missing registered markers, or violating lane rules.

The audit should include empirical runtime data from pytest collection/execution rather than only static classification. The manifest should record a runtime class such as `subsecond`, `seconds`, `minutes`, or `unknown` so lane placement is grounded in measured feedback cost.

Pytest parallelism should be deferred until after taxonomy and isolation cleanup, then added deliberately. The first parallelization target should be isolated `fast` tests; GUI, R Stack, and packaged smoke tests should remain serialized or process-isolated until they no longer share unsafe QApplication state, working directories, environment variables, settings, or R temporary paths.

Generated test artifacts such as `__pycache__` directories and `.pyc` files are not test evidence and should stay out of version control. The repository already ignores Python bytecode; if future audits find tracked generated cache artifacts, they should be removed.
