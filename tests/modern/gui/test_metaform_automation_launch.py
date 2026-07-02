import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("OMA_STUB_BACKEND", "1")
sys.path.insert(0, os.path.abspath("src"))
sys.path.insert(0, os.path.abspath(os.path.join("src", "forms")))

import pytest
from PyQt5 import QtWidgets

REPO_ROOT = os.getcwd()


def test_full_app_imports_representative_csv_into_dataset():
    import launch
    from PyQt5 import QtWidgets

    meta_form = launch._import_meta_form()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = meta_form.MetaForm()
    window._handle_wizard_results(
        {
            "path": "csv_import",
            "outcome_info": {
                "arms": "two",
                "data_type": "binary",
                "sub_type": "proportions",
                "effect": "OR",
                "metric_choices": [],
                "name": "Mortality",
            },
            "csv_data": {
                "headers": [
                    "Study",
                    "Year",
                    "Tx A events",
                    "Tx A total",
                    "Tx B events",
                    "Tx B total",
                    "OR",
                    "Lower",
                    "Upper",
                    "Dose",
                    "Region",
                ],
                "expected_headers": [
                    "Study",
                    "Year",
                    "Tx A events",
                    "Tx A total",
                    "Tx B events",
                    "Tx B total",
                    "OR",
                    "Lower",
                    "Upper",
                ],
                "data": [
                    ["Alpha", "2020", "1", "10", "2", "12", "", "", "", "5.5", "North"],
                    ["Beta", "2021", "3", "11", "4", "13", "", "", "", "7", "South"],
                ],
                "covariate_names": ["Dose", "Region"],
                "covariate_types": ["continuous", "factor"],
            },
            "selected_dataset": None,
        }
    )

    assert _cell_text(window.model, 0, window.model.NAME) == "Alpha"
    assert _cell_text(window.model, 1, window.model.YEAR) == "2021"
    assert _cell_text(window.model, 0, window.model.RAW_DATA[0]) == "1.0"
    assert [(cov.name, cov.data_type) for cov in window.model.dataset.covariates] == [
        ("Dose", 1),
        ("Region", 4),
    ]
    assert str(window.model.dataset.studies[1].covariate_dict["Region"]) == "South"


def test_full_app_import_pads_ragged_csv_rows_into_dataset():
    import launch
    from PyQt5 import QtWidgets

    meta_form = launch._import_meta_form()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = meta_form.MetaForm()
    try:
        window._handle_wizard_results(
            {
                "path": "csv_import",
                "outcome_info": {
                    "arms": "two",
                    "data_type": "binary",
                    "sub_type": "proportions",
                    "effect": "OR",
                    "metric_choices": [],
                    "name": "Mortality",
                },
                "csv_data": {
                    "headers": [
                        "Study",
                        "Year",
                        "Tx A events",
                        "Tx A total",
                        "Tx B events",
                        "Tx B total",
                    ],
                    "expected_headers": [
                        "Study",
                        "Year",
                        "Tx A events",
                        "Tx A total",
                        "Tx B events",
                        "Tx B total",
                    ],
                    "data": [
                        ["Alpha", "2020", "1", "10", "2", "12"],
                        ["Beta", "2021", "3", "11", "4"],
                    ],
                    "covariate_names": [],
                    "covariate_types": [],
                },
                "selected_dataset": None,
            }
        )

        assert _cell_text(window.model, 1, window.model.NAME) == "Beta"
        assert _cell_text(window.model, 1, window.model.RAW_DATA[-1]) == ""
    finally:
        window.current_data_unsaved = False
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_automation_launch_creates_and_closes_real_metaform_shell():
    import launch

    app, window = launch.start_automation()
    meta_form = sys.modules["meta_form"]

    assert app is QtWidgets.QApplication.instance()
    assert app.windowIcon().isNull() is False
    assert isinstance(window, meta_form.MetaForm)
    assert window.isVisible()

    window.close()
    app.processEvents()
    os.chdir(REPO_ROOT)


def test_automation_launch_shows_main_window_maximized():
    import launch

    app, window = launch.start_automation()
    try:
        assert window.isVisible()
        assert window.isMaximized()
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_open_project_preserves_main_window_state_without_duplicate_windows():
    import launch

    app, window = launch.start_automation()
    meta_form = sys.modules["meta_form"]

    try:
        window.showMaximized()
        app.processEvents()
        visible_metaforms_before = [
            widget
            for widget in app.topLevelWidgets()
            if isinstance(widget, meta_form.MetaForm) and widget.isVisible()
        ]

        assert window.open(os.path.abspath("sample_data/amino.oma")) is True
        app.processEvents()

        visible_metaforms_after = [
            widget
            for widget in app.topLevelWidgets()
            if isinstance(widget, meta_form.MetaForm) and widget.isVisible()
        ]
        assert visible_metaforms_after == visible_metaforms_before
        assert window.isMaximized()
        assert window.tableView.model() is window.model
        assert window.model.rowCount() >= 20
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_openmeta_logo_resource_is_valid_and_used_consistently():
    import icons_rc  # noqa: F401
    from PyQt5 import QtGui

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app_icon = QtGui.QIcon(":/misc/meta.ico")
    logo_pixmap = QtGui.QPixmap(":/misc/meta.png")

    assert app_icon.isNull() is False
    assert logo_pixmap.isNull() is False

    checked_paths = [
        os.path.join("src", "meta.ui"),
        os.path.join("src", "results_window.ui"),
    ]
    checked_paths.extend(
        os.path.join("src", "forms", file_name)
        for file_name in os.listdir(os.path.join(REPO_ROOT, "src", "forms"))
        if file_name.endswith((".ui", ".py"))
    )
    broken_logo_path = ":/images/" + "meta.png"

    broken_logo_refs = [
        path
        for path in checked_paths
        if os.path.exists(path)
        and broken_logo_path in open(path, encoding="utf-8").read()
    ]

    assert broken_logo_refs == []


def test_automation_launch_shows_default_confidence_level_at_startup():
    import launch

    app, window = launch.start_automation()

    try:
        assert window.cl_label.text() == "confidence level: 95.0%"
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_automation_launch_opens_sample_project_in_real_data_table():
    import launch

    sample_project = os.path.abspath("sample_data/amino.oma")
    app, window = launch.start_automation()

    try:
        assert window.open(sample_project) is True

        model = window.tableView.model()
        assert model is window.model
        assert model.rowCount() >= 20
        assert model.columnCount() >= 7
        assert _cell_text(model, 0, 1) == "Gonzalez"
        assert _cell_text(model, 0, 2) == "1993"
        assert [_cell_text(model, 0, column) for column in range(3, 7)] in (
            ["6.0", "27.0", "9.0", "27.0"],
            ["9.0", "27.0", "6.0", "27.0"],
        )
        assert (
            window.cur_outcome_lbl.text()
            == "<font color='Blue'>clinical failure</font>"
        )
        assert window.cur_time_lbl.text() == "<font color='Blue'>first</font>"
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


@pytest.mark.parametrize(
    "sample_project",
    ["amino.oma", "continuous.oma", "lymph.oma", "meantime.oma"],
)
def test_undo_immediately_after_open_does_not_clear_loaded_project(sample_project):
    import launch

    app, window = launch.start_automation()
    try:
        assert window.open(os.path.abspath(os.path.join("sample_data", sample_project)))

        loaded_model = window.model
        loaded_row_count = loaded_model.rowCount()
        loaded_summary = _dataset_summary(loaded_model.dataset)
        loaded_outcome = window.cur_outcome_lbl.text()
        loaded_follow_up = window.cur_time_lbl.text()
        assert loaded_row_count > 0

        window.undo()
        app.processEvents()

        assert window.model.rowCount() == loaded_row_count
        assert _dataset_summary(window.model.dataset) == loaded_summary
        assert window.cur_outcome_lbl.text() == loaded_outcome
        assert window.cur_time_lbl.text() == loaded_follow_up
        assert window.tableView.undoStack.canRedo() is False

        model = window.model
        original_name = _cell_text(model, 0, model.NAME)
        window.tableView.set_data_in_model(model.index(0, model.NAME), "Edited Study")
        assert _cell_text(model, 0, model.NAME) == "Edited Study"

        window.undo()
        assert _cell_text(window.model, 0, window.model.NAME) == original_name
    finally:
        window.current_data_unsaved = False
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_frozen_startup_argv_falls_back_to_native_windows_command_line():
    import launch

    sample_project = os.path.abspath("sample_data/amino.oma")

    argv = launch._resolve_startup_argv(
        argv=["OpenMetaAnalyst.exe"],
        native_argv=["OpenMetaAnalyst.exe", sample_project],
        frozen=True,
    )

    assert argv == ["OpenMetaAnalyst.exe", sample_project]
    assert launch._startup_project_path(argv) == sample_project


def test_frozen_startup_argv_keeps_existing_project_argument():
    import launch

    sample_project = os.path.abspath("sample_data/amino.oma")
    other_project = os.path.abspath("sample_data/continuous.oma")

    argv = launch._resolve_startup_argv(
        argv=["OpenMetaAnalyst.exe", sample_project],
        native_argv=["OpenMetaAnalyst.exe", other_project],
        frozen=True,
    )

    assert argv == ["OpenMetaAnalyst.exe", sample_project]
    assert launch._startup_project_path(argv) == sample_project


def test_startup_smoke_opens_positional_project_without_wizard(monkeypatch):
    import launch

    sample_project = os.path.abspath("sample_data/amino.oma")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    opened = []
    started = []
    closed = []

    class Window:
        def __init__(self):
            self.tableView = self

        def show(self):
            pass

        def open(self, project_path):
            opened.append(project_path)
            return True

        def start(self):
            started.append(True)

        def model(self):
            return self

        def rowCount(self):
            return 1

        def close(self):
            closed.append(True)

    class Splash:
        def __init__(self, pixmap):
            pass

        def show(self):
            pass

        def finish(self, window):
            pass

    monkeypatch.setattr(
        launch, "_resolve_startup_argv", lambda: ["OpenMetaAnalyst.exe", sample_project]
    )
    monkeypatch.setattr(
        launch,
        "_import_meta_form",
        lambda: type("MetaFormModule", (), {"MetaForm": Window}),
    )
    monkeypatch.setattr(launch.QtWidgets, "QApplication", lambda argv: app)
    monkeypatch.setattr(launch, "QPixmap", lambda path: object())
    monkeypatch.setattr(launch, "QSplashScreen", Splash)
    monkeypatch.setattr(launch, "load_R_libraries", lambda app, splash: None)
    monkeypatch.setattr(launch, "_force_table_paint", lambda app, meta: None)
    monkeypatch.setenv("OMA_STARTUP_PROJECT_SMOKE", "1")

    assert launch.start() == 0
    assert opened == [sample_project]
    assert started == []
    assert closed == [True]
    os.chdir(REPO_ROOT)


def test_meantime_sample_project_loads_native_factor_covariate():
    import modern_compat

    modern_compat.install()
    import headless_analysis

    model = headless_analysis.load_dataset_model(
        os.path.abspath(os.path.join("sample_data", "meantime.oma"))
    )
    dataset = model.dataset

    assert ("treatment group", 4) in [
        (cov.name, cov.data_type) for cov in dataset.covariates
    ]
    values = [study.covariate_dict["treatment group"] for study in dataset.studies]
    present_values = [value for value in values if value is not None]
    assert present_values
    assert all(type(value) is str for value in present_values)
    assert set(present_values) == {"1", "2", "3", "4"}


def test_automation_launch_opens_meantime_project_and_enables_subgroup_analysis():
    import launch

    app, window = launch.start_automation()
    try:
        assert (
            window.open(os.path.abspath(os.path.join("sample_data", "meantime.oma")))
            is True
        )

        assert window.tableView.model() is window.model
        assert window.model.rowCount() >= 1
        assert window.action_subgroup_ma.isEnabled()
        values = [
            study.covariate_dict["treatment group"]
            for study in window.model.dataset.studies
        ]
        assert all(type(value) is str for value in values if value is not None)
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_opened_sample_projects_return_native_table_values_for_pyqt5_rendering():
    from PyQt5 import QtCore, QtGui
    import launch

    cases = [
        (
            "amino.oma",
            "Gonzalez",
            lambda groups: [
                groups[0] + " #evts",
                groups[0] + " #total",
                groups[1] + " #evts",
                groups[1] + " #total",
            ],
        ),
        (
            "continuous.oma",
            "Carroll",
            lambda groups: [
                groups[0] + " N",
                groups[0] + " mean",
                groups[0] + " SD",
                groups[1] + " N",
                groups[1] + " mean",
                groups[1] + " SD",
            ],
        ),
    ]

    for project_name, first_study, raw_headers_for_groups in cases:
        app, window = launch.start_automation()
        try:
            assert (
                window.open(os.path.abspath(os.path.join("sample_data", project_name)))
                is True
            )
            model = window.tableView.model()

            assert (
                model.headerData(
                    model.NAME, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole
                )
                == "study name"
            )
            assert (
                model.headerData(
                    model.YEAR, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole
                )
                == "year"
            )
            raw_headers = raw_headers_for_groups(model.current_txs)
            assert [
                model.headerData(column, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole)
                for column in model.RAW_DATA
            ] == raw_headers
            assert model.headerData(0, QtCore.Qt.Vertical, QtCore.Qt.DisplayRole) == 1

            assert (
                model.data(model.index(0, model.NAME), QtCore.Qt.DisplayRole)
                == first_study
            )
            assert isinstance(
                model.data(model.index(0, model.YEAR), QtCore.Qt.DisplayRole), int
            )
            assert (
                model.data(
                    model.index(0, model.INCLUDE_STUDY), QtCore.Qt.CheckStateRole
                )
                == QtCore.Qt.Checked
            )
            assert model.data(
                model.index(0, model.NAME), QtCore.Qt.TextAlignmentRole
            ) == int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            assert isinstance(
                model.data(
                    model.index(0, model.OUTCOMES[0]), QtCore.Qt.BackgroundColorRole
                ),
                QtGui.QColor,
            )

            visible_values = [
                model.headerData(
                    model.NAME, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole
                ),
                model.data(model.index(0, model.NAME), QtCore.Qt.DisplayRole),
                model.data(
                    model.index(0, model.INCLUDE_STUDY), QtCore.Qt.CheckStateRole
                ),
            ]
            assert all(not hasattr(value, "value") for value in visible_values)
        finally:
            window.close()
            app.processEvents()
            os.chdir(REPO_ROOT)


def test_edit_list_models_return_native_values_and_accept_native_edits():
    from PyQt5 import QtCore
    import launch
    import edit_list_models

    app, window = launch.start_automation()
    try:
        assert (
            window.open(os.path.abspath(os.path.join("sample_data", "amino.oma")))
            is True
        )
        dataset = window.model.dataset
        window.model.add_covariate(
            "Dose",
            "continuous",
            dict(
                (study.name, index + 1) for index, study in enumerate(dataset.studies)
            ),
        )
        follow_up_name = dataset.get_follow_up_names_for_outcome(
            window.model.current_outcome
        )[0]

        models = [
            edit_list_models.TXGroupsModel(
                dataset=dataset,
                outcome=window.model.current_outcome,
                follow_up=follow_up_name,
            ),
            edit_list_models.OutcomesModel(dataset=dataset),
            edit_list_models.FollowUpsModel(
                dataset=dataset, outcome=window.model.current_outcome
            ),
            edit_list_models.StudiesModel(dataset=dataset),
            edit_list_models.CovariatesModel(dataset=dataset),
        ]

        for list_model in models:
            index = list_model.index(0, 0)
            display_value = list_model.data(index, QtCore.Qt.DisplayRole)
            alignment_value = list_model.data(index, QtCore.Qt.TextAlignmentRole)

            assert display_value not in (None, "")
            assert not hasattr(display_value, "value")
            assert alignment_value == int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        group_model = edit_list_models.TXGroupsModel(
            dataset=dataset,
            outcome=window.model.current_outcome,
            follow_up=follow_up_name,
        )
        assert group_model.setData(group_model.index(0, 0), "Renamed Group") is True
        assert "Renamed Group" in [
            group_model.data(group_model.index(row, 0), QtCore.Qt.DisplayRole)
            for row in range(group_model.rowCount())
        ]

        follow_up_model = edit_list_models.FollowUpsModel(
            dataset=dataset, outcome=window.model.current_outcome
        )
        assert (
            follow_up_model.setData(follow_up_model.index(0, 0), "Renamed Follow Up")
            is True
        )
        assert (
            follow_up_model.data(follow_up_model.index(0, 0), QtCore.Qt.DisplayRole)
            == "Renamed Follow Up"
        )

        studies_model = edit_list_models.StudiesModel(dataset=dataset)
        assert studies_model.setData(studies_model.index(0, 0), "Renamed Study") is True
        assert (
            studies_model.data(studies_model.index(0, 0), QtCore.Qt.DisplayRole)
            == "Renamed Study"
        )

        covariates_model = edit_list_models.CovariatesModel(dataset=dataset)
        assert (
            covariates_model.setData(covariates_model.index(0, 0), "Renamed Dose")
            is True
        )
        assert (
            covariates_model.data(covariates_model.index(0, 0), QtCore.Qt.DisplayRole)
            == "Renamed Dose"
        )

        outcomes_model = edit_list_models.OutcomesModel(dataset=dataset)
        assert (
            outcomes_model.setData(outcomes_model.index(0, 0), "Renamed Outcome")
            is True
        )
        assert (
            outcomes_model.data(outcomes_model.index(0, 0), QtCore.Qt.DisplayRole)
            == "Renamed Outcome"
        )

        errors = []
        studies_model.dataError.connect(errors.append)
        assert studies_model.setData(studies_model.index(0, 0), "") is False
        assert errors == ["Study names cannot be empty."]

        errors = []
        covariates_model.dataError.connect(errors.append)
        assert covariates_model.setData(covariates_model.index(0, 0), "") is False
        assert errors == ["Covariate names cannot be empty."]
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_change_covariate_type_model_returns_native_values_and_accepts_native_edits():
    from PyQt5 import QtCore
    import launch
    import change_cov_type_form
    import ma_dataset

    app, window = launch.start_automation()
    try:
        assert (
            window.open(os.path.abspath(os.path.join("sample_data", "amino.oma")))
            is True
        )
        dataset = window.model.dataset
        window.model.add_covariate(
            "Dose",
            "continuous",
            dict(
                (study.name, index + 1) for index, study in enumerate(dataset.studies)
            ),
        )

        cov_model = change_cov_type_form.CovModel(dataset, dataset.covariates[0])
        assert (
            cov_model.headerData(
                cov_model.STUDY_COL, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole
            )
            == "study"
        )
        assert (
            cov_model.headerData(
                cov_model.NEW_VAL, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole
            )
            == "Dose (factor)"
        )
        assert cov_model.headerData(
            cov_model.NEW_VAL, QtCore.Qt.Horizontal, QtCore.Qt.TextAlignmentRole
        ) == int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        display_value = cov_model.data(
            cov_model.index(0, cov_model.STUDY_COL), QtCore.Qt.DisplayRole
        )
        assert display_value not in (None, "")
        assert not hasattr(display_value, "value")

        assert cov_model.setData(cov_model.index(0, cov_model.NEW_VAL), "High") is True
        assert (
            cov_model.data(cov_model.index(0, cov_model.NEW_VAL), QtCore.Qt.DisplayRole)
            == "High"
        )

        dataset.add_covariate(
            ma_dataset.Covariate("Region", "factor"),
            dict((study.name, "North") for study in dataset.studies),
        )
        continuous_cov_model = change_cov_type_form.CovModel(
            dataset, dataset.covariates[-1]
        )
        errors = []
        continuous_cov_model.dataError.connect(errors.append)
        old_value = continuous_cov_model.data(
            continuous_cov_model.index(0, continuous_cov_model.NEW_VAL),
            QtCore.Qt.DisplayRole,
        )

        assert (
            continuous_cov_model.setData(
                continuous_cov_model.index(0, continuous_cov_model.NEW_VAL),
                "not numeric",
            )
            is False
        )

        assert errors == [
            "Covariate values for continuous covariates need to be numeric."
        ]
        assert (
            continuous_cov_model.data(
                continuous_cov_model.index(0, continuous_cov_model.NEW_VAL),
                QtCore.Qt.DisplayRole,
            )
            == old_value
        )
    finally:
        window.current_data_unsaved = False
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_factor_covariate_edits_render_as_native_paint_text():
    from PyQt5 import QtCore, QtWidgets
    import launch

    app, window = launch.start_automation()
    try:
        assert (
            window.open(os.path.abspath(os.path.join("sample_data", "amino.oma")))
            is True
        )
        model = window.tableView.model()
        model.add_covariate("Region", "factor")
        factor_column = model.columnCount() - 1
        factor_index = model.index(0, factor_column)

        assert model.setData(factor_index, "North") is True
        stored_value = model.dataset.studies[0].covariate_dict["Region"]
        display_value = model.data(factor_index, QtCore.Qt.DisplayRole)

        assert stored_value == "North"
        assert type(stored_value) is str
        assert display_value == "North"
        assert type(display_value) is str

        option = QtWidgets.QStyleOptionViewItem()
        delegate = QtWidgets.QStyledItemDelegate(window.tableView)
        delegate.initStyleOption(option, factor_index)
        assert option.text == "North"
    finally:
        window.current_data_unsaved = False
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_sequential_analysis_actions_open_real_specs_dialog(monkeypatch):
    import launch

    app, window = launch.start_automation()
    meta_form = sys.modules["meta_form"]
    calls = []

    class SpecsDialog(object):
        def __init__(self, model, meta_f_str=None, parent=None, conf_level=None):
            calls.append(
                (meta_f_str, parent, conf_level, model.get_current_outcome_type())
            )

        def show(self):
            pass

    monkeypatch.setattr(meta_form.ma_specs, "MA_Specs", SpecsDialog)

    try:
        assert window.open(os.path.abspath("sample_data/amino.oma")) is True
        window.action_cum_ma.trigger()
        window.action_loo_ma.trigger()

        assert calls == [
            ("cumulative", window, window.model.get_global_conf_level(), "binary"),
            ("leave-one-out", window, window.model.get_global_conf_level(), "binary"),
        ]
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_standard_meta_analysis_opens_specs_and_runs_through_backend(monkeypatch):
    # Drives the full GUI analysis path (open -> action_go -> MA_Specs -> run_ma
    # -> results window) against a mocked in-process meta_py_r backend.
    import launch

    for name, method_name, method_label in [
        ("amino.oma", "binary.random", "Binary Random-Effects"),
        ("continuous.oma", "continuous.random", "Continuous Random-Effects"),
    ]:
        calls = []
        shown = []

        class ResultDialog(object):
            def __init__(self, result, parent=None):
                shown.append((result, parent))

            def show(self):
                shown.append("shown")

        def run(method, params, _method=method_name):
            calls.append(method)
            return {"texts": {"Summary": "%s model" % _method}, "images": {}}

        app, window = launch.start_automation()
        meta_form = sys.modules["meta_form"]
        meta_py_r = sys.modules["meta_py_r"]
        monkeypatch.setattr(meta_form.results_window, "ResultsWindow", ResultDialog)
        monkeypatch.setattr(
            meta_py_r,
            "get_available_methods",
            lambda **kwargs: {method_label: method_name},
            raising=False,
        )
        monkeypatch.setattr(
            meta_py_r, "get_params", lambda method: ({}, {}, None, {}), raising=False
        )
        monkeypatch.setattr(
            meta_py_r,
            "get_method_description",
            lambda method: "Random-effects analysis",
            raising=False,
        )
        monkeypatch.setattr(
            meta_py_r,
            "ma_dataset_to_simple_binary_robj",
            lambda model, **kwargs: None,
            raising=False,
        )
        monkeypatch.setattr(
            meta_py_r,
            "ma_dataset_to_simple_continuous_robj",
            lambda model, **kwargs: None,
            raising=False,
        )
        monkeypatch.setattr(meta_py_r, "run_binary_ma", run, raising=False)
        monkeypatch.setattr(meta_py_r, "run_continuous_ma", run, raising=False)

        try:
            assert (
                window.open(os.path.abspath(os.path.join("sample_data", name))) is True
            )

            window.action_go.trigger()
            specs = window.findChildren(meta_form.ma_specs.MA_Specs)
            assert len(specs) == 1

            specs[0].run_ma()

            assert calls[-1] == method_name
            assert shown[-2:] == [
                (
                    {"texts": {"Summary": "%s model" % method_name}, "images": {}},
                    window,
                ),
                "shown",
            ]
        finally:
            window.close()
            app.processEvents()
            os.chdir(REPO_ROOT)


def test_method_parameters_dialog_displays_enum_defaults(monkeypatch):
    import launch
    from PyQt5 import QtWidgets

    app, window = launch.start_automation()
    meta_form = sys.modules["meta_form"]
    meta_py_r = sys.modules["meta_py_r"]
    qt_layout = sys.modules["qt_layout"]

    params = {
        "rm.method": ["HE", "DL", "SJ", "ML", "REML", "EB"],
        "to": ["only0", "all"],
        "conf.level": "float",
        "digits": "float",
        "adjust": "float",
        "theta.lower": "float",
    }
    defaults = {
        "rm.method": "DL",
        "to": "only0",
        "conf.level": 95.0,
        "digits": 3,
        "adjust": 0.5,
        "theta.lower": -2.0,
    }
    pretty_names = {
        "rm.method": {
            "pretty.name": "Random-Effects method",
            "description": "Method for estimating between-studies heterogeneity",
            "rm.method.names": {
                "HE": "Hedges",
                "DL": "DerSimonian-Laird",
                "SJ": "Sidik-Jonkman",
                "ML": "Maximum likelihood",
                "REML": "Restricted maximum likelihood",
                "EB": "Empirical Bayes",
            },
        },
        "to": {
            "pretty.name": "Correction factor target",
            "description": "Cells receiving the correction factor",
        },
        "conf.level": {
            "pretty.name": "Confidence level",
            "description": "Level at which to compute confidence intervals",
        },
        "digits": {
            "pretty.name": "Number of digits",
            "description": "Number of digits to display in results",
        },
        "adjust": {
            "pretty.name": "Correction factor",
            "description": "Constant added to two-by-two table entries.",
        },
        "theta.lower": {
            "pretty.name": "Prior lower bound",
            "description": "Lower value in a uniform prior range.",
        },
    }

    monkeypatch.setattr(
        meta_py_r,
        "get_available_methods",
        lambda **kwargs: {
            "Binary Random-Effects": "binary.random",
        },
        raising=False,
    )
    monkeypatch.setattr(
        meta_py_r,
        "get_params",
        lambda method: (
            dict(params),
            dict(defaults),
            ["rm.method", "to", "conf.level", "digits", "adjust", "theta.lower"],
            pretty_names,
        ),
        raising=False,
    )
    monkeypatch.setattr(
        meta_py_r,
        "get_method_description",
        lambda method: "Random-effects analysis",
        raising=False,
    )
    monkeypatch.setattr(
        meta_py_r,
        "ma_dataset_to_simple_binary_robj",
        lambda model, **kwargs: None,
        raising=False,
    )

    try:
        assert (
            window.open(os.path.abspath(os.path.join("sample_data", "amino.oma")))
            is True
        )

        window.action_go.trigger()
        specs = window.findChildren(meta_form.ma_specs.MA_Specs)
        assert len(specs) == 1
        assert specs[0].minimumWidth() >= qt_layout.ANALYSIS_DIALOG_MINIMUM_WIDTH

        enum_combos = [
            combo
            for combo in specs[0].parameter_grp_box.findChildren(QtWidgets.QComboBox)
            if combo is not specs[0].method_cbo_box
        ]
        assert [str(combo.currentText()) for combo in enum_combos] == [
            "DL: DerSimonian-Laird",
            "only0",
        ]
        for combo in [specs[0].method_cbo_box] + enum_combos:
            assert combo.sizeAdjustPolicy() == QtWidgets.QComboBox.AdjustToContents
            assert combo.minimumWidth() >= combo.sizeHint().width()

        confidence_spinboxes = specs[0].parameter_grp_box.findChildren(
            QtWidgets.QDoubleSpinBox
        )
        confidence_spinboxes = [
            spinbox for spinbox in confidence_spinboxes if spinbox.suffix() == "%"
        ]
        assert len(confidence_spinboxes) == 1
        confidence_spinbox = confidence_spinboxes[0]
        confidence_spinbox.lineEdit().setText("100")
        confidence_spinbox.interpretText()
        assert confidence_spinbox.maximum() == 99.9
        assert confidence_spinbox.value() == 95.0

        double_spinboxes = specs[0].parameter_grp_box.findChildren(
            QtWidgets.QDoubleSpinBox
        )
        non_conf_double_spinboxes = [
            spinbox for spinbox in double_spinboxes if spinbox.suffix() != "%"
        ]
        assert len(non_conf_double_spinboxes) == 2
        correction_spinbox = next(
            spinbox for spinbox in non_conf_double_spinboxes if spinbox.minimum() == 0
        )
        signed_spinbox = next(
            spinbox for spinbox in non_conf_double_spinboxes if spinbox.minimum() < 0
        )
        correction_spinbox.lineEdit().setText("-1")
        correction_spinbox.interpretText()
        assert correction_spinbox.value() == 0.5
        signed_spinbox.setValue(-2.5)
        assert signed_spinbox.value() == -2.5

        digit_spinboxes = specs[0].parameter_grp_box.findChildren(QtWidgets.QSpinBox)
        assert len(digit_spinboxes) == 1
        digit_spinbox = digit_spinboxes[0]
        digit_spinbox.lineEdit().setText("-5")
        digit_spinbox.interpretText()
        assert digit_spinbox.minimum() == 0
        assert digit_spinbox.value() == 3

        parameter_labels = [
            label
            for label in specs[0].parameter_grp_box.findChildren(QtWidgets.QLabel)
            if str(label.text())
            in {
                "Random-Effects method",
                "Correction factor target",
                "Confidence level",
                "Number of digits",
                "Correction factor",
                "Prior lower bound",
            }
        ]
        assert len(parameter_labels) == 6
        for label in parameter_labels:
            assert label.minimumWidth() >= label.sizeHint().width()

        assert specs[0].current_param_vals["rm.method"] == "DL"
        assert specs[0].current_param_vals["to"] == "only0"
        assert specs[0].current_param_vals["conf.level"] == 95.0
        assert specs[0].current_param_vals["digits"] == 3
        assert specs[0].current_param_vals["adjust"] == 0.5
        assert specs[0].current_param_vals["theta.lower"] == -2.5
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_required_advanced_analysis_actions_open_real_gui_dialogs(monkeypatch):
    import launch

    shown = []

    class MetaRegDialog(object):
        def __init__(self, model, parent=None):
            shown.append(("meta-regression", parent, model.get_current_outcome_type()))

        def show(self):
            pass

    class SubgroupDialog(object):
        def __init__(self, model, parent=None):
            shown.append(("subgroup", parent, model.get_current_outcome_type()))

        def show(self):
            pass

    for name, outcome_type in [
        ("amino.oma", "binary"),
        ("continuous.oma", "continuous"),
    ]:
        app, window = launch.start_automation()
        meta_form = sys.modules["meta_form"]
        monkeypatch.setattr(meta_form.meta_reg_form, "MetaRegForm", MetaRegDialog)
        monkeypatch.setattr(
            meta_form.meta_subgroup_form, "MetaSubgroupForm", SubgroupDialog
        )

        try:
            assert (
                window.open(os.path.abspath(os.path.join("sample_data", name))) is True
            )
            cov_values = {
                study.name: index
                for index, study in enumerate(window.model.dataset.studies)
            }
            group_values = {
                study.name: "A" if index % 2 else "B"
                for index, study in enumerate(window.model.dataset.studies)
            }
            window.model.add_covariate("dose", "continuous", cov_values)
            window.model.add_covariate("region", "factor", group_values)
            window._enable_action_subgroup_ma()
            window.action_meta_regression.setEnabled(True)
            assert window.action_meta_regression.isEnabled()
            assert window.action_subgroup_ma.isEnabled()

            window.action_meta_regression.trigger()
            window.action_subgroup_ma.trigger()

            assert shown[-2:] == [
                ("meta-regression", window, outcome_type),
                ("subgroup", window, outcome_type),
            ]
        finally:
            window.close()
            app.processEvents()
            os.chdir(REPO_ROOT)


def test_meta_regression_action_stays_disabled_without_covariates_when_data_are_enabled():
    import launch

    app, window = launch.start_automation()

    try:
        assert window.model.dataset.covariates == []

        window.enable_menu_options_that_require_dataset()

        assert window.action_go.isEnabled()
        assert window.action_subgroup_ma.isEnabled() is False
        assert window.action_meta_regression.isEnabled() is False
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_meta_regression_dialog_disables_ok_and_does_not_run_without_covariates(
    monkeypatch,
):
    import launch
    import meta_reg_form

    app, window = launch.start_automation()
    meta_py_r = sys.modules["meta_py_r"]
    warnings = []
    calls = []

    monkeypatch.setattr(
        meta_reg_form.QMessageBox,
        "warning",
        lambda *args: warnings.append(args),
    )
    monkeypatch.setattr(
        meta_py_r,
        "run_meta_regression",
        lambda *args, **kwargs: calls.append((args, kwargs)),
        raising=False,
    )

    try:
        form = meta_reg_form.MetaRegForm(window.model, parent=window)

        assert form.covs_and_check_boxes == []
        assert form.buttonBox.button(QtWidgets.QDialogButtonBox.Ok).isEnabled() is False

        form.run_meta_reg()

        assert calls == []
        assert warnings
        assert warnings[0][1:3] == (
            "No covariates selected",
            "Select at least one covariate before running meta-regression.",
        )
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_diagnostic_meta_regression_dialog_fits_radio_group_labels():
    import launch
    import meta_reg_form

    app, window = launch.start_automation()
    form = None

    try:
        assert (
            window.open(os.path.abspath(os.path.join("sample_data", "lymph.oma")))
            is True
        )
        cov_values = {
            study.name: index + 1
            for index, study in enumerate(window.model.dataset.studies)
        }
        window.model.add_covariate("dose", "continuous", cov_values)

        form = meta_reg_form.MetaRegForm(window.model, parent=window)
        form.show()
        app.processEvents()
        form.layout().activate()

        assert form.diagnostic_group_box.isVisible()
        for group_box in (form.diagnostic_group_box, form.groupBox):
            assert group_box.height() >= group_box.sizeHint().height()

        assert form.height() >= form.sizeHint().height()
    finally:
        window.current_data_unsaved = False
        if form is not None:
            form.close()
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_diagnostic_metric_dialog_fits_checkbox_group_labels():
    import diag_metrics
    import launch

    app, window = launch.start_automation()
    form = None

    try:
        assert (
            window.open(os.path.abspath(os.path.join("sample_data", "lymph.oma")))
            is True
        )

        form = diag_metrics.Diag_Metrics(window.model, parent=window)
        form.show()
        app.processEvents()
        form.layout().activate()

        assert form.metrics_grp_box.height() >= form.metrics_grp_box.sizeHint().height()
        assert form.height() >= form.sizeHint().height()
    finally:
        if form is not None:
            form.close()
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_advanced_analysis_actions_require_dataset_readiness_and_covariates():
    import launch

    app, window = launch.start_automation()

    try:
        window._add_new_covariate("region", "factor")

        assert window.action_go.isEnabled() is False
        assert window.action_meta_regression.isEnabled() is False
        assert window.action_subgroup_ma.isEnabled() is False

        window.enable_menu_options_that_require_dataset()

        assert window.action_meta_regression.isEnabled()
        assert window.action_subgroup_ma.isEnabled()
    finally:
        window.current_data_unsaved = False
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_deleting_last_covariate_refreshes_advanced_analysis_actions():
    import launch

    app, window = launch.start_automation()

    try:
        assert (
            window.open(os.path.abspath(os.path.join("sample_data", "amino.oma")))
            is True
        )
        window._add_new_covariate("region", "factor")

        assert window.action_meta_regression.isEnabled()
        assert window.action_subgroup_ma.isEnabled()

        window.delete_covariate(window.model.dataset.covariates[0])

        assert window.model.dataset.covariates == []
        assert window.action_meta_regression.isEnabled() is False
        assert window.action_subgroup_ma.isEnabled() is False

        window.tableView.undoStack.undo()

        assert [cov.name for cov in window.model.dataset.covariates] == ["region"]
        assert window.action_meta_regression.isEnabled()
        assert window.action_subgroup_ma.isEnabled()
    finally:
        window.current_data_unsaved = False
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_subgroup_dialog_disables_ok_and_does_not_run_without_factor_covariates(
    monkeypatch,
):
    import launch
    import meta_subgroup_form

    app, window = launch.start_automation()
    warnings = []
    calls = []

    monkeypatch.setattr(
        meta_subgroup_form.QMessageBox,
        "warning",
        lambda *args: warnings.append(args),
    )
    monkeypatch.setattr(
        window, "meta_subgroup", lambda selected_cov: calls.append(selected_cov)
    )

    try:
        window._add_new_covariate("dose", "continuous")
        form = meta_subgroup_form.MetaSubgroupForm(window.model, parent=window)

        assert form.cov_subgroup_cbo_box.count() == 0
        assert form.buttonBox.button(QtWidgets.QDialogButtonBox.Ok).isEnabled() is False

        form.get_selected_cov()

        assert calls == []
        assert warnings
        assert warnings[0][1:3] == (
            "No covariate selected",
            "Select a factor covariate before running subgroup analysis.",
        )
    finally:
        window.current_data_unsaved = False
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_factor_covariate_meta_regression_runs_and_paint_roles_are_qt_safe(monkeypatch):
    from PyQt5 import QtCore
    import launch
    import meta_reg_form

    app, window = launch.start_automation()
    form = None
    meta_form = sys.modules["meta_form"]
    meta_py_r = sys.modules["meta_py_r"]
    shown = []

    class ResultDialog(object):
        def __init__(self, result, parent=None):
            shown.append((result, parent))

        def show(self):
            shown.append("shown")

    def run_meta_regression(dataset, studies, covariates, metric, **kwargs):
        shown.append(
            (
                "run-meta-regression",
                [cov.name for cov in covariates],
                [study.name for study in studies],
                metric,
                kwargs.get("fixed_effects"),
                kwargs.get("conf_level"),
            )
        )
        return {
            "texts": {"Summary": "factor meta-regression"},
            "images": {},
            "image_var_names": {},
        }

    monkeypatch.setattr(meta_form.results_window, "ResultsWindow", ResultDialog)
    monkeypatch.setattr(
        meta_py_r,
        "ma_dataset_to_simple_binary_robj",
        lambda *args, **kwargs: None,
        raising=False,
    )
    monkeypatch.setattr(
        meta_py_r, "run_meta_regression", run_meta_regression, raising=False
    )

    try:
        assert (
            window.open(os.path.abspath(os.path.join("sample_data", "amino.oma")))
            is True
        )
        group_values = {
            study.name: "East" if index % 2 else "West"
            for index, study in enumerate(window.model.dataset.studies)
        }
        window.model.add_covariate("region", "factor", group_values)

        form = meta_reg_form.MetaRegForm(window.model, parent=window)
        for cov, check_box in form.covs_and_check_boxes:
            check_box.setChecked(cov.name == "region")

        form.run_meta_reg()

        assert shown[0] == (
            "run-meta-regression",
            ["region"],
            [study.name for study in window.model.dataset.studies if study.include],
            "OR",
            False,
            window.model.get_global_conf_level(),
        )
        assert shown[-2:] == [
            (
                {
                    "texts": {"Summary": "factor meta-regression"},
                    "images": {},
                    "image_var_names": {},
                },
                window,
            ),
            "shown",
        ]

        factor_column = window.model.columnCount() - 1
        factor_index = window.model.index(0, factor_column)
        assert window.model.data(factor_index, QtCore.Qt.DisplayRole) in (
            "East",
            "West",
        )

        for role in (
            QtCore.Qt.DecorationRole,
            QtCore.Qt.ForegroundRole,
            QtCore.Qt.FontRole,
            QtCore.Qt.SizeHintRole,
        ):
            value = window.model.data(factor_index, role)
            assert value is None
    finally:
        window.current_data_unsaved = False
        if form is not None:
            form.close()
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_subgroup_covariate_dialog_constructs_with_factor_covariate():
    import launch
    import meta_subgroup_form

    app, window = launch.start_automation()
    try:
        assert (
            window.open(os.path.abspath(os.path.join("sample_data", "amino.oma")))
            is True
        )
        group_values = {
            study.name: "north" if index % 2 else "south"
            for index, study in enumerate(window.model.dataset.studies)
        }
        window.model.add_covariate("region", "factor", group_values)

        form = meta_subgroup_form.MetaSubgroupForm(window.model, parent=window)

        assert str(form.windowTitle()) == "select covariate"
        assert [
            str(form.cov_subgroup_cbo_box.itemText(index))
            for index in range(form.cov_subgroup_cbo_box.count())
        ] == ["region"]
    finally:
        window.current_data_unsaved = False
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_sequential_analysis_results_use_results_window(monkeypatch):
    import launch

    app, window = launch.start_automation()
    meta_form = sys.modules["meta_form"]
    shown = []
    results = {
        "texts": {"Cumulative Summary": "Binary Random-Effects Model"},
        "images": {"Cumulative Forest Plot": "forest.png"},
    }

    class ResultDialog(object):
        def __init__(self, result, parent=None):
            shown.append((result, parent))

        def show(self):
            shown.append("shown")

    monkeypatch.setattr(meta_form.results_window, "ResultsWindow", ResultDialog)

    try:
        window.analysis(results)

        assert shown == [(results, window), "shown"]
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_results_window_renders_summary_text_and_plot_navigation(tmp_path):
    import launch
    import modern_compat

    modern_compat.install()
    import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    plot_path = tmp_path / "forest.png"
    image = results_window.QImage(80, 40, results_window.QImage.Format_RGB32)
    image.fill(results_window.Qt.white)
    assert image.save(str(plot_path), "PNG")

    window = results_window.ResultsWindow(
        {
            "texts": {
                "Summary": "Binary Random-Effects Model\n\nEstimate Lower bound Upper bound"
            },
            "images": {"Forest Plot": str(plot_path)},
            "image_var_names": {"Forest Plot": "forest_plot"},
            "image_params_paths": {"Forest Plot": str(tmp_path / "forest_params")},
            "image_order": ["Forest Plot"],
        }
    )

    try:
        nav_titles = [
            window.nav_tree.topLevelItem(index).text(0)
            for index in range(window.nav_tree.topLevelItemCount())
        ]

        assert nav_titles == ["Summary", "Forest Plot"]
        assert "forest_plot" in window.psuedo_console.toPlainText()
        assert any(
            isinstance(item, results_window.QGraphicsTextItem)
            for item in window.scene.items()
        )
        assert any(
            isinstance(item, results_window.QGraphicsPixmapItem)
            for item in window.scene.items()
        )
        assert window.graphics_view.scene() is window.scene
    finally:
        window.close()
        app.processEvents()


def test_results_window_separates_tall_text_sections():
    import launch
    import modern_compat

    modern_compat.install()
    import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    tall_section = "\n".join(
        "Study %02d  0.123  0.456  0.789" % index for index in range(1, 40)
    )
    window = results_window.ResultsWindow(
        {
            "texts": {
                "Within-study parameters": tall_section,
                "Odds Ratio Summary": "Diagnostic Random-Effects Model\n\nEstimate Lower bound Upper bound",
            },
            "images": {},
            "image_var_names": {},
            "image_params_paths": {},
            "image_order": [],
        }
    )

    try:
        sections = {
            item.toPlainText(): item
            for item in window.scene.items()
            if isinstance(item, results_window.QGraphicsTextItem)
        }

        first_body = sections[tall_section]
        next_title = sections["Odds Ratio Summary"]
        first_bottom = first_body.sceneBoundingRect().bottom()
        next_top = next_title.sceneBoundingRect().top()

        assert next_top - first_bottom >= results_window.SECTION_SPACING
    finally:
        window.close()
        app.processEvents()


def test_results_window_ignores_missing_image_order_entries():
    import launch
    import modern_compat

    modern_compat.install()
    import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = results_window.ResultsWindow(
        {
            "texts": {"Summary": "HSROC summary"},
            "images": {},
            "image_var_names": {},
            "image_params_paths": {},
            "image_order": ["Summary ROC"],
        }
    )

    try:
        nav_titles = [
            window.nav_tree.topLevelItem(index).text(0)
            for index in range(window.nav_tree.topLevelItemCount())
        ]

        assert nav_titles == ["Summary"]
        assert not any(
            isinstance(item, results_window.QGraphicsPixmapItem)
            for item in window.scene.items()
        )
    finally:
        window.close()
        app.processEvents()


def test_real_metaform_save_as_round_trips_representative_projects(
    tmp_path, monkeypatch
):
    import launch

    for name in ["amino.oma", "continuous.oma", "lymph.oma", "meantime.oma"]:
        app, window = launch.start_automation()
        saved_path = str(tmp_path / name)

        try:
            assert (
                window.open(os.path.abspath(os.path.join("sample_data", name))) is True
            )
            expected = _dataset_summary(window.model.dataset)
            meta_form = sys.modules["meta_form"]
            monkeypatch.setattr(
                meta_form.QFileDialog,
                "getSaveFileName",
                lambda **kwargs: (saved_path, ""),
            )

            window.save_as()
            assert os.path.exists(saved_path)
            assert window.current_data_unsaved is False
            meta_form = sys.modules["meta_form"]
            reopened = meta_form._load_project_pickle(saved_path)
            assert _dataset_summary(reopened) == expected
            if name == "meantime.oma":
                values = [
                    study.covariate_dict["treatment group"]
                    for study in reopened.studies
                ]
                assert all(type(value) is str for value in values if value is not None)
        finally:
            window.close()
            app.processEvents()
            os.chdir(REPO_ROOT)


def test_recent_files_persist_through_pyqt5_settings(tmp_path):
    from PyQt5 import QtCore
    import launch
    import settings

    QtCore.QSettings.setPath(
        QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, str(tmp_path)
    )
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.IniFormat)
    settings.reset_settings()

    settings.add_file_to_recent_files("first.oma")
    settings.add_file_to_recent_files("second.oma")
    settings.load_settings()

    assert settings.get_setting("recent_files") == ["first.oma", "second.oma"]


def test_main_window_maximized_state_persists_through_pyqt5_settings(tmp_path):
    from PyQt5 import QtCore, QtWidgets
    import settings

    QtCore.QSettings.setPath(
        QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, str(tmp_path)
    )
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.IniFormat)
    settings.reset_settings()

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    saved = QtWidgets.QMainWindow()
    restored = QtWidgets.QMainWindow()
    try:
        saved.showMaximized()
        app.processEvents()

        settings.save_main_window_placement(saved)
        settings.restore_main_window_placement(restored)
        app.processEvents()

        assert restored.isVisible()
        assert restored.isMaximized()
    finally:
        saved.close()
        restored.close()
        app.processEvents()


def test_welcome_wizard_recent_action_selects_project():
    import launch
    from PyQt5 import QtWidgets
    import main_wizard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(recent_datasets=["first.oma", "second.oma"])
    try:
        page = wizard.page(main_wizard.Page_Welcome)
        action = page.open_recent_btn.menu().actions()[0]

        page.dataset_selected(action)

        assert wizard.get_wizard_path() == "open"
        assert wizard.get_selected_dataset() == "second.oma"
    finally:
        wizard.close()
        app.processEvents()


def test_welcome_wizard_open_existing_selects_project(monkeypatch):
    import launch
    from PyQt5 import QtWidgets
    import main_wizard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard()
    try:
        page = wizard.page(main_wizard.Page_Welcome)
        monkeypatch.setattr(
            main_wizard.QFileDialog,
            "getOpenFileName",
            lambda **kwargs: ("chosen.oma", ""),
        )

        page.open_dataset()

        assert wizard.get_wizard_path() == "open"
        assert wizard.get_selected_dataset() == "chosen.oma"
    finally:
        wizard.close()
        app.processEvents()


def test_wizard_size_refit_ignores_closed_wizard_without_current_page(monkeypatch):
    import launch
    from PyQt5 import QtWidgets
    import main_wizard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="csv_import")
    try:
        monkeypatch.setattr(wizard, "currentPage", lambda: None)

        wizard._change_size(-1)
    finally:
        wizard.close()
        app.processEvents()


def test_startup_wizard_cancel_preserves_loaded_dataset(monkeypatch):
    import launch
    from PyQt5 import QtWidgets

    meta_form = launch._import_meta_form()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = meta_form.MetaForm()
    sample_project = os.path.abspath(os.path.join("sample_data", "amino.oma"))

    class RejectedWizard:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 0

    quit_calls = []
    monkeypatch.setattr(meta_form.main_wizard, "MainWizard", RejectedWizard)
    monkeypatch.setattr(meta_form.QApplication, "quit", lambda: quit_calls.append(True))

    try:
        assert window.open(sample_project) is True
        loaded_dataset = window.model.dataset
        loaded_title = loaded_dataset.title
        loaded_studies = [study.name for study in loaded_dataset.studies]

        window.start()

        assert quit_calls == []
        assert window.model.dataset is loaded_dataset
        assert window.model.dataset.title == loaded_title
        assert [study.name for study in window.model.dataset.studies] == loaded_studies
    finally:
        window.close()
        app.processEvents()


def test_data_type_page_multiline_buttons_fit_icon_and_caption():
    import launch
    from PyQt5 import QtWidgets
    import main_wizard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        wizard.restart()
        app.processEvents()

        data_type_page = wizard.page(main_wizard.Page_DataType)
        multiline_buttons = [
            data_type_page.onearm_single_reg_coef_Button,
            data_type_page.onearm_generic_effect_size_Button,
        ]

        for button in multiline_buttons:
            assert "\n" in button.text()
            assert button.maximumHeight() >= button.sizeHint().height()
            assert button.minimumHeight() >= button.sizeHint().height()
    finally:
        wizard.close()
        app.processEvents()


@pytest.mark.parametrize(
    ("button_name", "expected"),
    [
        (
            "onearm_proportion_Button",
            {
                "arms": "one",
                "data_type": "binary",
                "sub_type": "proportion",
                "effect": "PR",
                "metric_choices_name": "BINARY_ONE_ARM_METRICS",
            },
        ),
        (
            "onearm_mean_Button",
            {
                "arms": "one",
                "data_type": "continuous",
                "sub_type": "mean",
                "effect_name": "DEFAULT_CONTINUOUS_ONE_ARM",
                "metric_choices_name": "CONTINUOUS_ONE_ARM_METRICS",
            },
        ),
        (
            "onearm_single_reg_coef_Button",
            {
                "arms": "one",
                "data_type": "continuous",
                "sub_type": "reg_coef",
                "effect_name": "DEFAULT_CONTINUOUS_ONE_ARM",
                "metric_choices_name": "CONTINUOUS_ONE_ARM_METRICS",
            },
        ),
        (
            "onearm_generic_effect_size_Button",
            {
                "arms": "one",
                "data_type": "continuous",
                "sub_type": "generic_effect",
                "effect_name": "DEFAULT_CONTINUOUS_ONE_ARM",
                "metric_choices_name": "CONTINUOUS_ONE_ARM_METRICS",
            },
        ),
        (
            "twoarm_proportions_Button",
            {
                "arms": "two",
                "data_type": "binary",
                "sub_type": "proportions",
                "effect": "OR",
                "metric_choices_name": "BINARY_TWO_ARM_METRICS",
            },
        ),
        (
            "twoarm_means_Button",
            {
                "arms": "two",
                "data_type": "continuous",
                "sub_type": "means",
                "effect": "MD",
                "metric_choices_name": "CONTINUOUS_TWO_ARM_METRICS",
            },
        ),
        (
            "twoarm_smds_Button",
            {
                "arms": "two",
                "data_type": "continuous",
                "sub_type": "smd",
                "effect": "SMD",
                "metric_choices_name": "CONTINUOUS_TWO_ARM_METRICS",
            },
        ),
        (
            "diagnostic_Button",
            {
                "arms": None,
                "data_type": "diagnostic",
                "sub_type": None,
                "effect": None,
                "metric_choices": [],
            },
        ),
    ],
)
def test_data_type_page_records_every_supported_selection(button_name, expected):
    import launch
    from PyQt5 import QtWidgets
    import main_wizard
    import meta_globals

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        wizard.restart()
        app.processEvents()

        data_type_page = wizard.page(main_wizard.Page_DataType)
        getattr(data_type_page, button_name).click()
        app.processEvents()

        expected_effect = (
            expected["effect"]
            if "effect" in expected
            else getattr(meta_globals, expected["effect_name"])
        )
        expected_metric_choices = (
            expected["metric_choices"]
            if "metric_choices" in expected
            else getattr(meta_globals, expected["metric_choices_name"])
        )
        expected_summary = {
            "arms": expected["arms"],
            "data_type": expected["data_type"],
            "sub_type": expected["sub_type"],
            "effect": expected_effect,
            "metric_choices": expected_metric_choices,
            "name": None,
        }
        assert wizard.get_dataset_info() == expected_summary
    finally:
        wizard.close()
        app.processEvents()


def test_new_project_data_type_selection_populates_metric_defaults_and_results():
    import launch
    from PyQt5 import QtWidgets
    import main_wizard
    import meta_globals

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        wizard.restart()
        app.processEvents()

        data_type_page = wizard.page(main_wizard.Page_DataType)
        next_button = wizard.button(main_wizard.QWizard.NextButton)
        assert not next_button.isEnabled()

        data_type_page.twoarm_proportions_Button.click()
        app.processEvents()

        assert data_type_page.isComplete()
        assert next_button.isEnabled()
        assert wizard.get_dataset_info() == {
            "arms": "two",
            "data_type": "binary",
            "sub_type": "proportions",
            "effect": "OR",
            "metric_choices": meta_globals.BINARY_TWO_ARM_METRICS,
            "name": None,
        }

        wizard.next()
        app.processEvents()

        metric_page = wizard.page(main_wizard.Page_ChooseMetric)
        assert metric_page.metric_cbo_box.count() == len(
            meta_globals.BINARY_TWO_ARM_METRICS
        )
        assert metric_page.metric_cbo_box.currentData() == "OR"
        assert "(DEFAULT)" in metric_page.metric_cbo_box.currentText()
        assert wizard.get_effect() == "OR"

        wizard.next()
        app.processEvents()
        outcome_page = wizard.page(main_wizard.Page_OutcomeName)
        outcome_page.outcome_name_LineEdit.setText("Mortality")

        results = wizard.get_results()
        assert results["path"] == "new_dataset"
        assert results["outcome_info"]["data_type"] == "binary"
        assert results["outcome_info"]["effect"] == "OR"
        assert results["outcome_info"]["name"] == "Mortality"
    finally:
        wizard.close()
        app.processEvents()


def test_open_existing_dialog_starts_in_sample_data_even_when_cwd_is_app_data(
    tmp_path, monkeypatch
):
    import launch

    app_data = tmp_path / "app-data"
    app_data.mkdir()
    os.chdir(str(app_data))

    app, window = launch.start_automation()
    meta_form = sys.modules["meta_form"]
    import settings

    settings.reset_settings()
    calls = []

    def choose_project(**kwargs):
        calls.append(kwargs)
        return ("", "")

    monkeypatch.setattr(meta_form.QFileDialog, "getOpenFileName", choose_project)

    try:
        assert window.open() is False
        _assert_sample_data_open_directory(calls[0]["directory"])
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_welcome_wizard_open_existing_dialog_starts_in_sample_data_when_no_recent_project(
    tmp_path, monkeypatch
):
    import launch
    from PyQt5 import QtWidgets
    import main_wizard

    app_data = tmp_path / "app-data"
    app_data.mkdir()
    os.chdir(str(app_data))

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard()
    calls = []

    def choose_project(**kwargs):
        calls.append(kwargs)
        return ("", "")

    monkeypatch.setattr(main_wizard.QFileDialog, "getOpenFileName", choose_project)

    try:
        page = wizard.page(main_wizard.Page_Welcome)
        page.open_dataset()

        _assert_sample_data_open_directory(calls[0]["directory"])
    finally:
        wizard.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_help_action_opens_bundled_help(monkeypatch):
    import launch

    opened = []
    app, window = launch.start_automation()
    import meta_globals

    meta_form = sys.modules["meta_form"]
    monkeypatch.setattr(meta_form.webbrowser, "open", opened.append)

    try:
        window.action_open_help.trigger()

        assert opened == [os.path.join(REPO_ROOT, "doc", "openMA_help.html")]
        assert meta_globals.HELP_URL == opened[0]
        assert os.path.exists(opened[0])
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_load_r_libraries_runs_against_stub_bridge():
    # Regression: the frozen modern build has no Qt4 binding, so modern_compat.install()
    # plants the stub meta_py_r used as the milestone-1 R bridge. The real launch
    # path (start -> load_R_libraries) calls get_R_libpaths() + RlibLoader, which
    # must all exist on the stub or the app crashes before the GUI ever shows.
    import launch
    import modern_compat

    modern_compat.install()
    assert hasattr(sys.modules["meta_py_r"], "get_R_libpaths")

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    class _Splash:
        def showMessage(self, message):
            pass

    # Must not raise AttributeError: module 'meta_py_r' has no attribute 'get_R_libpaths'
    launch.load_R_libraries(app, _Splash())


def test_stub_backend_exposes_data_entry_imputation_methods():
    # Regression for GitHub #48: the modern PyQt5 path plants a stub meta_py_r,
    # and data-entry dialogs call these methods during construction. The no-R
    # stub must expose them, returning a benign "couldn't impute" result rather
    # than crashing.
    import launch
    import modern_compat

    modern_compat.install()
    meta_py_r = sys.modules["meta_py_r"]

    for name in (
        "impute_bin_data",
        "impute_cont_data",
        "impute_pre_post_cont_data",
        "impute_diag_data",
        "back_calc_cont_data",
    ):
        assert hasattr(meta_py_r, name), name

    assert "FAIL" in meta_py_r.impute_bin_data({"Ev_A": 1})
    assert meta_py_r.impute_cont_data({"n": 10}, 0.05)["succeeded"] is False
    assert (
        meta_py_r.impute_pre_post_cont_data({"n": 10}, 0.5, 0.05)["succeeded"] is False
    )
    assert meta_py_r.impute_diag_data({"TP": 1}) == {
        "TP": None,
        "TN": None,
        "FP": None,
        "FN": None,
    }
    assert "FAIL" in meta_py_r.back_calc_cont_data(
        {"n": 10}, {"n": 12}, {"est": 1.0}, 95.0
    )


def test_data_entry_dialogs_construct_with_stub_backend(monkeypatch):
    # Regression for GitHub #48: opening these dialogs from a study row used to
    # crash when the stubbed meta_py_r lacked imputation entry points. With the
    # pure-Python no-R stub they must still construct without a live backend.
    import copy
    import launch

    app, window = launch.start_automation()
    import binary_data_form
    import continuous_data_form
    import diagnostic_data_form

    monkeypatch.setattr(
        continuous_data_form.ChooseBackCalcResultForm, "exec", lambda self: False
    )

    try:
        assert (
            window.open(os.path.abspath(os.path.join("sample_data", "amino.oma")))
            is True
        )
        model = window.model
        binary_dialog = binary_data_form.BinaryDataForm2(
            copy.deepcopy(model.get_current_ma_unit_for_study(0)),
            model.current_txs,
            model.get_cur_group_str(),
            model.current_effect,
            conf_level=model.get_global_conf_level(),
            parent=window.tableView,
        )
        binary_dialog.close()

        assert (
            window.open(os.path.abspath(os.path.join("sample_data", "continuous.oma")))
            is True
        )
        model = window.model
        continuous_dialog = continuous_data_form.ContinuousDataForm(
            copy.deepcopy(model.get_current_ma_unit_for_study(0)),
            model.current_txs,
            model.get_cur_group_str(),
            model.current_effect,
            conf_level=model.get_global_conf_level(),
            parent=window.tableView,
        )
        continuous_dialog.close()

        assert (
            window.open(os.path.abspath(os.path.join("sample_data", "lymph.oma")))
            is True
        )
        model = window.model
        diagnostic_dialog = diagnostic_data_form.DiagnosticDataForm(
            copy.deepcopy(model.get_current_ma_unit_for_study(0)),
            model.current_txs,
            model.get_cur_group_str(),
            conf_level=model.get_global_conf_level(),
            parent=window.tableView,
        )
        diagnostic_dialog.close()
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_csv_import_wizard_accepts_representative_csv(tmp_path, monkeypatch):
    import launch
    from PyQt5 import QtWidgets
    import main_wizard

    csv_path = tmp_path / "studies.csv"
    csv_path.write_text(
        "Study,Year,Tx A events,Tx A total,Tx B events,Tx B total,OR,Lower,Upper,Dose,Region\n"
        "Alpha,2020,1,10,2,12,,,,5.5,North\n"
        "Beta,2021,3,11,4,13,,,,7,South\n"
    )
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="csv_import")
    wizard.set_dataset_info(
        {
            "arms": "two",
            "data_type": "binary",
            "sub_type": "proportions",
            "effect": "OR",
            "metric_choices": [],
        }
    )
    page = wizard.page(main_wizard.Page_CsvImport)
    page.initializePage()
    monkeypatch.setattr(
        main_wizard.QFileDialog,
        "getOpenFileName",
        lambda **kwargs: (str(csv_path), "csv files (*.csv)"),
    )

    page._select_file()

    assert page.isComplete()
    assert wizard.get_csv_data()["covariate_names"] == ["Dose", "Region"]
    assert wizard.get_csv_data()["covariate_types"] == ["continuous", "factor"]


def test_csv_import_wizard_pads_ragged_rows_before_previewing(tmp_path, monkeypatch):
    import launch
    from PyQt5 import QtWidgets
    import main_wizard

    csv_path = tmp_path / "ragged-studies.csv"
    csv_path.write_text(
        "Study,Year,Tx A events,Tx A total,Tx B events,Tx B total\n"
        "Alpha,2020,1,10,2,12\n"
        "Beta,2021,3,11,4\n"
    )
    shown = []
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="csv_import")
    wizard.set_dataset_info(
        {
            "arms": "two",
            "data_type": "binary",
            "sub_type": "proportions",
            "effect": "OR",
            "metric_choices": [],
        }
    )
    page = wizard.page(main_wizard.Page_CsvImport)
    page.initializePage()
    monkeypatch.setattr(
        main_wizard.QFileDialog,
        "getOpenFileName",
        lambda **kwargs: (str(csv_path), "csv files (*.csv)"),
    )
    monkeypatch.setattr(
        main_wizard.QMessageBox,
        "warning",
        lambda *args, **kwargs: shown.append(args),
    )

    page._select_file()

    assert shown == []
    assert page.isComplete()
    assert page.preview_table.item(1, 5).text() == ""
    assert wizard.get_csv_data()["data"][-1] == ["Beta", "2021", "3", "11", "4", ""]


def test_csv_import_wizard_reports_empty_file_as_no_data(tmp_path, monkeypatch):
    from PyQt5 import QtWidgets
    import main_wizard

    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("")
    shown = []
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="csv_import")
    wizard.set_dataset_info(
        {
            "arms": "two",
            "data_type": "binary",
            "sub_type": "proportions",
            "effect": "OR",
            "metric_choices": [],
        }
    )
    page = wizard.page(main_wizard.Page_CsvImport)
    page.initializePage()
    monkeypatch.setattr(
        main_wizard.QFileDialog,
        "getOpenFileName",
        lambda **kwargs: (str(csv_path), "csv files (*.csv)"),
    )
    monkeypatch.setattr(
        main_wizard.QMessageBox,
        "warning",
        lambda *args, **kwargs: shown.append(args),
    )

    page._select_file()

    assert shown
    assert shown[0][1] == "Whoops"
    assert shown[0][2] == "No data in CSV. Try again."
    assert "StopIteration" not in shown[0][2]
    assert not page.isComplete()


def test_csv_import_preview_failure_preserves_error_details(tmp_path, monkeypatch):
    from PyQt5 import QtWidgets
    import main_wizard

    csv_path = tmp_path / "studies.csv"
    csv_path.write_text(
        "Study,Year,Tx A events,Tx A total,Tx B events,Tx B total\n"
        "Alpha,2020,1,10,2,12\n"
    )
    shown = []
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="csv_import")
    wizard.set_dataset_info(
        {
            "arms": "two",
            "data_type": "binary",
            "sub_type": "proportions",
            "effect": "OR",
            "metric_choices": [],
        }
    )
    page = wizard.page(main_wizard.Page_CsvImport)
    page.initializePage()
    monkeypatch.setattr(
        main_wizard.QFileDialog,
        "getOpenFileName",
        lambda **kwargs: (str(csv_path), "csv files (*.csv)"),
    )
    monkeypatch.setattr(
        page,
        "_validate_imported_data",
        lambda: (_ for _ in ()).throw(ValueError("Year column is missing")),
    )
    monkeypatch.setattr(
        main_wizard.QMessageBox,
        "warning",
        lambda *args, **kwargs: shown.append(args),
    )

    page._select_file()

    assert shown
    assert shown[0][1] == "Could not import CSV"
    assert "Year column is missing" in shown[0][2]
    assert "Try again" not in shown[0][2]
    assert not page.isComplete()


def test_csv_import_file_selection_enables_finish_button(tmp_path, monkeypatch):
    import launch
    from PyQt5 import QtWidgets
    import main_wizard

    csv_path = tmp_path / "studies.csv"
    csv_path.write_text(
        "Study,Year,Tx A events,Tx A total,Tx B events,Tx B total,OR,Lower,Upper\n"
        "Alpha,2020,1,10,2,12,,,\n"
    )
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="csv_import")
    wizard.set_dataset_info(
        {
            "arms": "two",
            "data_type": "binary",
            "sub_type": "proportions",
            "effect": "OR",
            "metric_choices": [],
        }
    )
    wizard.setStartId(main_wizard.Page_CsvImport)
    try:
        wizard.restart()
        app.processEvents()

        page = wizard.page(main_wizard.Page_CsvImport)
        finish_button = wizard.button(main_wizard.QWizard.FinishButton)
        assert not finish_button.isEnabled()
        monkeypatch.setattr(
            main_wizard.QFileDialog,
            "getOpenFileName",
            lambda **kwargs: (str(csv_path), "csv files (*.csv)"),
        )

        page._select_file()
        app.processEvents()

        assert page.isComplete()
        assert finish_button.isEnabled()
    finally:
        wizard.close()
        app.processEvents()


def test_table_paint_roles_do_not_raise_across_all_cells():
    # Regression: real painting queries Qt.BackgroundColorRole/TextAlignmentRole for
    # every cell. data() sliced RAW_DATA with len()/2 (a float under Python 3), raising
    # TypeError out of the C++ paint virtual and aborting the GUI (exit 0xC0000409).
    # Offscreen tests never paint, so only a direct per-cell role sweep catches it.
    # Calling data()/headerData() in-process turns a paint-time abort into a clean
    # test failure; the packaged smoke test forces an actual paint pass as well.
    from PyQt5 import QtCore
    import launch

    paint_roles = [
        QtCore.Qt.DisplayRole,
        QtCore.Qt.DecorationRole,
        QtCore.Qt.BackgroundColorRole,
        QtCore.Qt.ForegroundRole,
        QtCore.Qt.FontRole,
        QtCore.Qt.TextAlignmentRole,
        QtCore.Qt.CheckStateRole,
        QtCore.Qt.SizeHintRole,
    ]

    app, window = launch.start_automation()
    try:
        assert (
            window.open(os.path.abspath(os.path.join("sample_data", "amino.oma")))
            is True
        )
        model = window.tableView.model()
        for row in range(model.rowCount()):
            for column in range(model.columnCount()):
                index = model.index(row, column)
                for role in paint_roles:
                    model.data(index, role)  # must not raise
        for section in range(model.columnCount()):
            for role in paint_roles:
                model.headerData(section, QtCore.Qt.Horizontal, role)  # must not raise
        for section in range(model.rowCount()):
            for role in paint_roles:
                model.headerData(section, QtCore.Qt.Vertical, role)  # must not raise
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def _cell_text(model, row, column):
    value = model.data(model.index(row, column))
    return str(value.value() if hasattr(value, "value") else value)


def _assert_sample_data_open_directory(directory):
    directory = os.path.abspath(directory)
    assert os.path.basename(directory) == "sample_data"
    assert os.path.exists(os.path.join(directory, "amino.oma"))
    assert os.path.normcase(directory) != os.path.normcase(os.getcwd())


def _dataset_summary(dataset):
    return {
        "title": dataset.title,
        "studies": [(str(study.name), str(study.year)) for study in dataset.studies],
        "outcomes": sorted(
            str(name) for name in dataset.outcome_names_to_follow_ups.keys()
        ),
    }
