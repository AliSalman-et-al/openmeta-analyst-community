# Golden Coverage Matrix

This matrix drives the Comprehensive Golden Baseline. Its purpose is to capture as much testable Reference Implementation behavior as practical before further behavior-changing Python 3.11 and PyQt5 port work.

If a user-facing branch is omitted, record the reason in the omission log. If it is unclear whether a branch is behaviorally distinct, include it.

## Source Projects

| Project | Data family | Baseline role |
| --- | --- | --- |
| `sample_projects/amino.rcms` | Binary | Primary two-arm binary project; standard analysis and plot coverage. |
| `sample_projects/BCG.rcms` | Binary | Additional binary project for metric/method variation and sensitivity to project shape. |
| `sample_projects/continuous.rcms` | Continuous | Primary continuous project. |
| `sample_projects/lymph.rcms` | Diagnostic | Primary diagnostic project, including multi-metric diagnostic workflows. |
| `sample_projects/meantime.rcms` | Mixed or larger legacy project | Stress project for open/display/save and additional workflow coverage after its contents are characterized. |

## Data Families and Metrics

| Data family | Metrics to cover | Notes |
| --- | --- | --- |
| Binary two-arm | `OR`, `RD`, `RR`, `AS`, `YUQ`, `YUY` | Cover all user-facing metrics unless a method reports infeasible for the selected project. |
| Binary one-arm | `PR`, `PLN`, `PLO`, `PAS`, `PFT` | Include at least one project created or transformed through the GUI/wizard path if no sample project already covers it. |
| Continuous two-arm | `MD`, `SMD` | Cover both metrics. |
| Continuous one-arm | `TX Mean` | Include a one-arm continuous project state if available or created through the GUI/wizard path. |
| Diagnostic | `Sens`, `Spec`, `PLR`, `NLR`, `DOR` | Cover single-family Sens/Spec, LR/DOR, and combined diagnostic metric selection behavior where feasible. |

## Analysis Workflows

| Workflow | Required baseline coverage | Generated artifacts |
| --- | --- | --- |
| Standard meta-analysis | Binary, continuous, and diagnostic families; fixed-effect and random-effects method classes where available; all user-facing metrics where practical. | Summary text, numeric outputs, forest plot artifacts when the method produces them. |
| Cumulative analysis | Binary and continuous at minimum; diagnostic if supported by the Reference Implementation for selected metrics. | Cumulative summary and cumulative forest plot artifacts. |
| Leave-one-out analysis | Binary and continuous at minimum; diagnostic if supported by the Reference Implementation for selected metrics. | Leave-one-out summary and forest plot artifacts. |
| Meta-Regression | Binary and continuous with continuous covariates; include categorical/factor covariate behavior if exposed by the dialog and R path. | Regression summary, numeric outputs, regression plot artifacts when produced. |
| Subgroup Analysis | Binary and continuous with factor covariates; include diagnostic if supported. | Subgroup summary and subgroup forest plot artifacts. |
| Diagnostic multi-metric analysis | Sens/Spec, PLR/NLR/DOR, and combined-selection paths where feasible. | Per-metric summaries and per-metric plot artifacts. |
| CSV-created project analysis | At least one binary CSV-imported project that is then analyzed through the normal analysis path. | Imported project state, standard summary, and plot artifacts. |

## Analysis Options and Branches

| Branch | Coverage expectation |
| --- | --- |
| Confidence level | Default confidence level plus at least one changed confidence level. |
| Included/excluded studies | At least one analysis with an excluded study if supported by the project/model state. |
| Plot options | Default plot parameters plus at least one edited forest-plot parameter path where the Reference Implementation supports it. |
| Raw data vs calculated effect sizes | Cover raw-data analysis and precomputed-effect-size paths where the data family exposes both. |
| One-arm vs two-arm data | Cover both where metrics expose both. |
| Covariate type | Cover continuous covariates for Meta-Regression and factor covariates for Subgroup Analysis. |
| Project round trip | Open, save, reopen, and compare representative project state for binary, continuous, and diagnostic projects. |
| Analysis-relevant GUI state | Include non-analysis workflows such as CSV import, adding covariates, changing confidence level, excluding studies, and save/reopen when they create or mutate project/model state used by analysis. |
| Pure navigation or visual state | Keep workflows such as menu presence, help opening, and recognizable dialog layout in GUI Verification Evidence unless they affect analysis inputs or outputs. |

## Plot Similarity Evidence

For each workflow that produces plots, capture the generated artifact path, plot type, data family, metric, method, study ordering, labels, axes or scale where relevant, and a checksum for traceability. Plot review checks for equivalent analysis content and recognizable presentation, not pixel-perfect equality.

Required plot classes:

- Standard forest plots.
- Cumulative forest plots.
- Leave-one-out forest plots.
- Subgroup forest plots.
- Meta-Regression plots.
- Diagnostic forest plots.
- Diagnostic SROC or bivariate/HSROC artifacts where the Reference Implementation produces them.

## Method Enumeration Rule

Available R-backed methods should be discovered from the Reference Implementation through the same method-availability path used by the GUI. The baseline should include every user-facing method class and as many concrete methods as practical for each data family and metric. If a concrete method is omitted because it is infeasible, redundant, unstable, or unavailable for the selected project, record that in the omission log.

## Implementation Sequence

Build thin golden-baseline capture tooling before manually expanding every matrix row in detail. The tooling should query the Reference Implementation for dynamic method availability, method feasibility, generated result fields, plot artifacts, and failure cases, then use that evidence to fill in concrete matrix rows and omission rationales.

Implement capture in two phases. First, make Reference Implementation capture deterministic in the legacy Python 2 Reference Environment. Second, add comparison mode for the current Python 3 branch. Keeping these phases separate makes failures easier to classify as capture-tool bugs, Reference Environment drift, or real modernization regressions.

## Artifact Storage Rule

Commit the Coverage Matrix, capture manifests, schemas, capture tooling, and the small Curated Golden Set needed for normal CI. Store the broader Comprehensive Golden Baseline outputs, including large JSON captures and generated plot artifacts, as ignored local artifacts or CI/release artifact bundles. The committed manifests should make the broader baseline reproducible and reviewable without bloating the repository.

## Capture Mode Rule

Use the headless harness for broad numeric and artifact coverage. Use GUI-driven capture for representative end-to-end workflows and for workflows where dialog state, project state, or user choices affect analysis parameters. If a workflow is captured only headlessly, the matrix should make clear why GUI capture does not add distinct compatibility confidence.

## Omission Log

| Branch omitted | Reason | Follow-up |
| --- | --- | --- |
| Network Meta-Analysis | Deferred from Release Cutover by ADR 0035; included in Complete User-Facing Legacy Port. | Add a post-cutover network baseline before porting network workflows. |
