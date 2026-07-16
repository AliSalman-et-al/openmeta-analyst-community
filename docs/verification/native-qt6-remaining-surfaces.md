# Native Qt6 Surface Inventory

This file is rendered from `native-qt6-surface-inventory.json`. The validator
fails if this table, the exact 29 canonical forms, runtime factories, adaptive
roles, executable tests, or evidence registry drift independently.

Required native scale factors: `1.0`, `1.25`, `1.5`, and `1.75`.
For these remaining surfaces, the four-factor native gate supersedes the
older two-factor adaptive-layout capture scripts.
Each retained capture has the closed-world path
`scale-{factor}/{surface-id}.png`; all 60 paths must be unique.
Focus, actions, geometry ownership, archetype, and overflow are observed
from live Qt controls and adaptive controllers rather than copied metadata.

| Surface | Canonical form | Contract | Native evidence |
| --- | --- | --- | --- |
| `about-legal` | `about_legal.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `text-browser` | #339 `build/qt6-verification/native-remaining-surfaces` |
| `binary-calculator` | `binary_data_form2.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `bounded-table` | #336 `build/qt6-verification/native-calculators` |
| `change-covariate-type` | `change_cov_type_form.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `bounded-table` | #339 `build/qt6-verification/native-remaining-surfaces` |
| `edit-group-name` | `change_group_name_dlg.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `content-preferred` | #339 `build/qt6-verification/native-remaining-surfaces` |
| `edit-covariate-name` | `change_group_name_dlg.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `content-preferred` | #339 `build/qt6-verification/native-remaining-surfaces` |
| `binary-back-calculation` | `choose_back_calc_result_form.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `bounded-table` | #336 `build/qt6-verification/native-calculators` |
| `main-wizard` | handwritten | `workflow` / `WORKFLOW`; `window-manager-after-first-show`; `page-scroll-area` | #339 `build/qt6-verification/native-remaining-surfaces` |
| `confidence-level` | `conf_level_dialog.ui` | `transactional` / `CONFIDENCE_LEVEL`; `application-first-use`; `content-preferred` | #339 `build/qt6-verification/native-remaining-surfaces` |
| `continuous-back-calculation` | `continuous_back_calc_result_form.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `bounded-table` | #336 `build/qt6-verification/native-calculators` |
| `continuous-calculator` | `continuous_data_form.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `bounded-table` | #336 `build/qt6-verification/native-calculators` |
| `meta-regression-selector` | `cov_reg_dlg2.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `scroll-area` | #337 `build/qt6-verification/native-analysis` |
| `subgroup-selector` | `cov_subgroup_dlg.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `scroll-area` | #337 `build/qt6-verification/native-analysis` |
| `diagnostic-calculator` | `diagnostic_data_form.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `bounded-table` | #336 `build/qt6-verification/native-calculators` |
| `diagnostic-metrics` | `diagnostic_metrics.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `scroll-area` | #337 `build/qt6-verification/native-analysis` |
| `edit-dataset` | `edit_dialog2.ui` | `workspace` / `EDIT_DATASET`; `window-manager-after-first-show`; `splitter-and-scrollbars` | #335 `workspace GUI evidence` |
| `edit-plot` | `edit_forest_plot.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `scroll-area` | #338 `build/qt6-verification/native-results` |
| `analysis-specifications` | `ma_specs2.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `scroll-area` | #337 `build/qt6-verification/native-analysis` |
| `main-workspace` | `meta.ui` | `workspace` / `MAIN`; `window-manager-after-first-show`; `table-scrollbars` | #333 `native application-shell smoke` |
| `network-view` | `network_view_window.ui` | `workspace` / `NETWORK_VIEW`; `window-manager-after-first-show`; `graphics-view` | #338 `build/qt6-verification/native-results` |
| `add-covariate` | `new_covariate_dlg.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `content-preferred` | #339 `build/qt6-verification/native-remaining-surfaces` |
| `add-follow-up` | `new_follow_up_dlg.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `content-preferred` | #339 `build/qt6-verification/native-remaining-surfaces` |
| `add-group` | `new_group_dlg.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `content-preferred` | #339 `build/qt6-verification/native-remaining-surfaces` |
| `add-outcome` | `new_outcome_dlg.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `content-preferred` | #339 `build/qt6-verification/native-remaining-surfaces` |
| `add-study` | `new_study_dlg.ui` | `transactional` / `TRANSACTIONAL`; `application-first-use`; `content-preferred` | #339 `build/qt6-verification/native-remaining-surfaces` |
| `results-window` | `results_window.ui` | `workspace` / `RESULTS`; `window-manager-after-first-show`; `graphics-view-and-navigation` | #338 `build/qt6-verification/native-results` |
| `import-progress` | `running.ui` | `transient` / `TRANSIENT`; `application`; `content-preferred` | #339 `build/qt6-verification/native-remaining-surfaces` |
| `analysis-progress` | `running.ui` | `transient` / `TRANSIENT`; `application`; `content-preferred` | #339 `build/qt6-verification/native-remaining-surfaces` |
| `shared-progress` | `running.ui` | `transient` / `TRANSIENT`; `application`; `content-preferred` | #339 `build/qt6-verification/native-remaining-surfaces` |
| `startup-splash` | handwritten | `transient` / `TRANSIENT`; `application`; `screen-bounded-pixmap` | #339 `build/qt6-verification/native-remaining-surfaces` |

Wizard page forms inherit the one `main-wizard` Workflow Window entry.
All other canonical forms map exactly to the top-level registration audited
by `audit_qt_layout_contracts.py`. The two handwritten top-level factories
are `MainWizard` and the startup splash.
Factories, executable test nodes, commands, and evidence ownership are
validated directly from the machine-readable inventory.
