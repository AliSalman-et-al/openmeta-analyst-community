# Native Qt6 analysis verification

Issue #337 restores the maintained analysis workflows through direct PyQt6
connections and a typed, Qt-independent Analysis Adapter request boundary.
`MA_Specs.analysis_requests()` is the public user-configuration seam: it emits
native `bool`, `int`, `float`, `str`, or `None` parameter values and identifies
the data family, workflow, method, and metric explicitly. Synchronous R
execution remains unchanged; no worker thread or process owns the embedded R
runtime. Every binary, continuous, diagnostic, and workflow backend call is
made from the frozen request; execution helpers do not read the dialog again.

The maintained Qt6 lane runs the configuration, failure, diagnostic, and Golden
Analysis tests and then executes `scripts/native_analysis_smoke.py` with the
native platform plugin and fatal Qt warnings. The smoke retains a visible
configuration screenshot and JSON evidence under
`build/qt6-verification/native-analysis`. The evidence proves a comma-decimal
confidence level reaches the actual backend as `90.5`. It drives the production
`MA_Specs.run_ma()` path with the production `ma_specs.MetaProgress` and proves
that success, backend failure, cancel, and user-close delete all owned dialogs
without changing the top-level-widget baseline. Result-owner callback failures
also propagate to the caller only after the same deferred Qt teardown has been
scheduled, so an application callback cannot strand the configuration or
progress surfaces.

Real statistical behavior is qualified separately with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-r-stack-full.ps1
```

That gate is also invoked by `scripts/verify-qt6.ps1`; it requires the exact
locked `rpy2`, `rpy2-rinterface`, and `rpy2-robjects` distribution identities
through `importlib.metadata`, records them in both version maps in every Golden
capture, validates the R and package identities, builds and checks RCMetaR,
executes the representative R analysis matrix, and exercises the in-process
rpy2 bridge. It then runs the 11
curated binary, continuous, diagnostic, cumulative, leave-one-out,
Meta-Regression, and Subgroup cases against the committed
`observed-golden-baseline.zip`. The comparison fails closed on missing or extra
cases or numeric sections and metrics, normalized text (including warnings and
references), and artifact label/name/type/metadata/content hashes.

Artifact byte equality is platform-aware because the frozen reference was
captured on Windows. When the reference and current capture report the same OS,
the artifact SHA-256 remains exact. When their OS values differ, the comparator
still requires the exact artifact label, file name, type, and metadata plus a
nonempty lowercase SHA-256, but does not require Windows-rendered plot bytes to
equal native macOS-rendered bytes. The separately authenticated plot display
identity and complete capability descriptor remain exact on every platform, as
do all normalized text and numeric gates. Each artifact comparison row records
both OS values and the applied policy in its detail.

Numeric expectations never come from runtime parsing of the frozen ZIP. The
separately committed `golden-numeric-contract.json` contains 415 observed result
values across all 11 ordered cases: standard estimates and heterogeneity,
calculation-scale values, study weights, every displayed cumulative and
leave-one-out row, Meta-Regression coefficients and omnibus results, and
Subgroup results. It records explicit justified omissions for bibliographic or
narrative numbers and blank cumulative p-values. The outer manifest authenticates
the contract's size and SHA-256; the contract independently binds itself to the
authenticated archive SHA-256 and carries exact case/section/metric coverage
plus a bounded absolute/relative tolerance rule. The loader requires canonical
UTF-8 JSON and validates finite values, ordered all-case coverage, omissions,
and every text section before the current parser produces candidate values.
Missing, extra, parser-drifted, out-of-tolerance, or tampered numeric values fail
closed without any path that can rewrite the committed oracle.

The
independently committed `golden-plot-descriptors.json` binds the expected
display identity and complete edit/style/composition/regeneration capability
metadata to each frozen artifact oracle. Missing, extra, duplicate, or changed
descriptors fail the gate.

Before any current output is created, the verifier authenticates the frozen
ZIP's outer size and SHA-256 from the committed manifest. It then enforces
bounded member count and size, rejects unsafe, encrypted, traversal, directory,
and case-insensitive duplicate members, validates the internal capture manifest,
and authenticates every artifact. Verification output is restricted to a
dedicated `build/qt6-verification/golden-compatibility-*` descendant. An existing
directory is removed only when its ownership marker contains the exact expected
value; symlink and reparse-point paths are rejected. Invalid archives, unsafe
output roots, and incomplete coverage-omission justifications fail before
capture. The binary
archive remains committed because its small PNG outputs are the copyright-safe
render/content oracle; generated current captures remain ignored build output.
