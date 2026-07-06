# GUI Verification Evidence

Record one entry for every Release Cutover workflow that is verified through GUI behavior rather than only through Golden Analysis Test output. Each entry should include:

- Inventory workflow.
- Issue or PR.
- Dataset, project file, or project state.
- Evidence type: scripted, manual, screenshot review, or release artifact check.
- Command or manual steps.
- Observed result.
- GUI Compatibility Exception link, if one was accepted.

## Standard Binary Analysis Workflow

- Issue: #5
- Dataset: `sample_data/amino.rcms`
- Evidence: `tests/modern/gui/test_gui_binary_slice.py`
- Verified workflow: open the existing project, display binary study rows, run the random-effects action, and render a result summary plus forest plot path in the PyQt5 window.
- Command: `uv run pytest -q tests\\modern`

## Bundled Help Workflow

- Issue: #34
- Dataset: Not applicable.
- Evidence: `tests/modern/gui/test_metaform_automation_launch.py::test_help_action_opens_bundled_help`
- Verified workflow: trigger the real `MetaForm` help action and open the bundled `doc/openMA_help.html` file.
- Command: `uv run pytest tests\\modern\\gui\\test_metaform_automation_launch.py`

## Real MetaForm Project Shell Workflow

- Issue: #41
- Dataset: `sample_data/amino.rcms`
- Evidence: `tests/modern/gui/test_metaform_automation_launch.py::test_automation_launch_creates_and_closes_real_metaform_shell`, `tests/modern/gui/test_metaform_automation_launch.py::test_automation_launch_opens_sample_project_in_real_data_table`, `tests/modern/gui/test_metaform_automation_launch.py::test_welcome_wizard_recent_action_selects_project`, and `tests/modern/gui/test_metaform_automation_launch.py::test_welcome_wizard_open_existing_selects_project`
- Verified workflow: launch through the real `launch.py` automation entry, create a real `MetaForm` shell, display an existing project in the real data table, and route welcome wizard project selection to the selected `.rcms` file.
- Command: `uv run pytest tests\\modern\\gui\\test_metaform_automation_launch.py`

## Existing .rcms Open Display Save-As Workflow

- Issue: #41
- Dataset: `sample_data/amino.rcms`, `sample_data/continuous.rcms`, and `sample_data/lymph.rcms`
- Evidence: `tests/modern/gui/test_metaform_automation_launch.py::test_automation_launch_opens_sample_project_in_real_data_table` and `tests/modern/gui/test_metaform_automation_launch.py::test_real_metaform_save_as_round_trips_representative_projects`
- Verified workflow: open existing legacy `.rcms` files without a user-visible migration step, display project rows in the real `MetaForm` data table, save representative binary, continuous, and diagnostic/additional sample projects through Save As, and reload the saved project files as compatible pickled `.rcms` data.
- Command: `uv run pytest tests\\modern\\gui\\test_metaform_automation_launch.py`

## Recent Files and Settings Workflow

- Issue: #41
- Dataset: synthetic recent-file paths.
- Evidence: `tests/modern/gui/test_metaform_automation_launch.py::test_recent_files_persist_through_pyqt5_settings`
- Verified workflow: persist recent file entries through PyQt5 `QSettings`, reload settings, and preserve the stored recent-file order used by the real welcome/open-recent flows.
- Command: `uv run pytest tests\\modern\\gui\\test_metaform_automation_launch.py`

## Data Creation and Editing Workflow

- Issue: #42
- Dataset: synthetic binary, continuous, and diagnostic projects created through the real `MetaForm` wizard result path.
- Evidence: `tests/modern/gui/test_metaform_data_workflows.py::test_real_metaform_creates_binary_continuous_and_diagnostic_datasets` and `tests/modern/gui/test_metaform_data_workflows.py::test_data_table_editing_preserves_project_state_and_round_trips`
- Verified workflow: create binary, continuous, and diagnostic datasets under PyQt5; edit study name, year, and raw data through the real table/model path; add a group, outcome, follow-up, and covariate; save the project; and reload the saved `.rcms` with the analysis-relevant project state intact.
- Command: `uv run pytest tests\\modern\\gui\\test_metaform_data_workflows.py`

## Copy Paste Undo Redo Workflow

- Issue: #42
- Dataset: synthetic binary project created through `MetaForm`.
- Evidence: `tests/modern/gui/test_metaform_data_workflows.py::test_copy_paste_undo_and_redo_work_through_real_table_path`
- Verified workflow: copy displayed raw-data cells to the clipboard, paste them through the real table path into another study, undo the paste, and redo the paste while preserving the study row.
- Command: `uv run pytest tests\\modern\\gui\\test_metaform_data_workflows.py`

## Metric and Confidence Level Workflow

- Issue: #42
- Dataset: synthetic binary project created through `MetaForm`.
- Evidence: `tests/modern/gui/test_metaform_data_workflows.py::test_metric_selection_and_confidence_level_are_preserved_in_model_state`
- Verified workflow: select a metric through the real metric menu action, change the global confidence level, capture model state, restore the model through `MetaForm.set_model`, and preserve the selected metric, checked menu state, and confidence level.
- Command: `uv run pytest tests\\modern\\gui\\test_metaform_data_workflows.py`

## Results Window Summary Plot Display Workflow

- Issue: #43
- Dataset: synthetic analysis result with summary text and a generated forest plot PNG.
- Evidence: `tests/modern/gui/test_metaform_automation_launch.py::test_results_window_renders_summary_text_and_plot_navigation`
- Verified workflow: construct the real PyQt5-compatible `ResultsWindow`, render summary text and a plot image into the graphics scene, expose both result sections in the navigation tree, attach the scene to the graphics view, and show the returned R image variable name in the pseudo-console.
- Command: `uv run pytest tests\\modern\\gui\\test_metaform_automation_launch.py`

## Windows Distributable Launch Workflow

- Issue: #41
- Dataset: `sample_data/BCG.rcms` and `sample_data/amino.rcms`
- Evidence: `tests/modern/packaging_contract/test_windows_distributable_contract.py::test_modern_windows_distributable_contract_is_declared` and `tests/modern/packaging_contract/test_windows_distributable_contract.py::test_lane_named_local_scripts_replace_old_workflow_wrappers`
- Verified workflow: package the modern Windows artifact around the real `launch.py` entry point, include the sample project files needed for real `.rcms` launch checks, and run the local modern workflow through the targeted `MetaForm` automation suite before packaging.
- Command: `uv run pytest tests\\modern\\packaging_contract\\test_windows_distributable_contract.py`

