import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RCMS_STUB_BACKEND", "1")
sys.path.insert(0, os.path.abspath("src"))
sys.path.insert(0, os.path.abspath(os.path.join("src", "forms")))

import pytest
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QHeaderView

REPO_ROOT = os.getcwd()


def _assert_compact_table_fits_visible_cells(table):
    owner = table.window()
    owner.resize(owner.width() + 180, owner.height())
    owner.show()
    QtWidgets.QApplication.processEvents()
    table_is_measurable = table.isVisible()
    if not table_is_measurable:
        header = table.horizontalHeader()
        assert (
            header.sectionResizeMode(0) == QHeaderView.Stretch
            or header.stretchLastSection()
        )

    required_height = (
        table.horizontalHeader().height()
        + sum(table.rowHeight(row) for row in range(table.rowCount()))
        + 2 * table.frameWidth()
    )
    assert table.maximumWidth() > table.minimumWidth()
    assert table.minimumHeight() >= required_height
    assert table.maximumHeight() >= required_height

    content_widths = [
        max(
            table.horizontalHeader().sectionSizeHint(column),
            table.sizeHintForColumn(column),
        )
        for column in range(table.columnCount())
    ]
    vertical_header_width = 0
    if not table.verticalHeader().isHidden():
        vertical_header_width = table.verticalHeader().sizeHint().width()
    required_width = (
        vertical_header_width + sum(content_widths) + 2 * table.frameWidth()
    )
    assert table.minimumWidth() >= required_width

    if not table_is_measurable:
        return

    for column, content_width in enumerate(content_widths):
        assert table.columnWidth(column) >= content_width

    section_width = sum(
        table.horizontalHeader().sectionSize(column)
        for column in range(table.columnCount())
    )
    header = table.horizontalHeader()
    assert (
        header.sectionResizeMode(0) == QHeaderView.Stretch
        or header.stretchLastSection()
    )
    assert section_width >= table.viewport().width() - 1


def _assert_table_view_leaves_spare_width_outside_data_columns(table_view):
    owner = table_view.window()
    owner.show()
    QtWidgets.QApplication.processEvents()

    model = table_view.model()
    if model is None or model.columnCount() == 0:
        assert not table_view.horizontalHeader().stretchLastSection()
        return

    header = table_view.horizontalHeader()
    last_column = model.columnCount() - 1
    original_last_width = header.sectionSize(last_column)
    original_section_width = sum(
        header.sectionSize(column) for column in range(model.columnCount())
    )

    owner.resize(owner.width() + 320, owner.height())
    owner.show()
    QtWidgets.QApplication.processEvents()

    expanded_section_width = sum(
        header.sectionSize(column) for column in range(model.columnCount())
    )
    assert not header.stretchLastSection()
    assert header.sectionSize(last_column) == original_last_width
    assert expanded_section_width == original_section_width
    assert expanded_section_width < table_view.viewport().width()


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

        assert window.open(os.path.abspath("sample_projects/amino.rcms")) is True
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


def test_rc_metastudio_logo_resource_is_valid_and_used_consistently():
    import icons_rc  # noqa: F401
    from PyQt5 import QtGui
    import launch

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app_icon = QtGui.QIcon(launch.APPLICATION_ICON_PATH)
    logo_pixmap = QtGui.QPixmap(":/misc/meta.png")
    splash_pixmap = QtGui.QPixmap(":/misc/splash.png")

    assert launch.APPLICATION_ICON_PATH == ":/misc/meta.png"
    assert app_icon.isNull() is False
    assert logo_pixmap.isNull() is False
    assert splash_pixmap.isNull() is False
    assert logo_pixmap.width() == logo_pixmap.height()
    assert logo_pixmap.width() >= 1024
    assert (splash_pixmap.width(), splash_pixmap.height()) == (600, 480)
    assert sorted(
        (size.width(), size.height()) for size in app_icon.availableSizes()
    ) == [(1024, 1024)]

    checked_paths = [
        Path("src", "rc_metastudio", "forms", "meta.ui"),
        Path("src", "rc_metastudio", "forms", "results_window.ui"),
    ]
    checked_paths.extend(
        Path("src", "rc_metastudio", "forms", file_name)
        for file_name in os.listdir(
            os.path.join(REPO_ROOT, "src", "rc_metastudio", "forms")
        )
        if file_name.endswith((".ui", ".py"))
    )

    checked_window_icon_refs = [
        (path, line)
        for path in checked_paths
        if path.exists()
        for line in path.read_text(encoding="utf-8").splitlines()
        if "setWindowIcon" in line
        or '<property name="windowIcon">' in line
        or "<normaloff>:/misc/meta." in line
        or '":/misc/meta.' in line
        or "':/misc/meta." in line
    ]
    low_resolution_icon_refs = [
        f"{path}:{line.strip()}"
        for path, line in checked_window_icon_refs
        if ":/misc/meta.ico" in line
    ]

    assert low_resolution_icon_refs == []


def test_automation_launch_shows_default_confidence_level_at_startup():
    import launch

    app, window = launch.start_automation()

    try:
        assert window.cl_label.text() == "Confidence Level: 95.0%"
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_automation_launch_opens_sample_project_in_real_data_table():
    import launch

    sample_project = os.path.abspath("sample_projects/amino.rcms")
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
        _assert_table_view_leaves_spare_width_outside_data_columns(window.tableView)
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


@pytest.mark.parametrize(
    "sample_project",
    ["amino.rcms", "continuous.rcms", "lymph.rcms", "meantime.rcms"],
)
def test_main_data_grid_leaves_spare_width_outside_data_columns(sample_project):
    import launch

    app, window = launch.start_automation()
    try:
        assert window.open(
            os.path.abspath(os.path.join("sample_projects", sample_project))
        )

        _assert_table_view_leaves_spare_width_outside_data_columns(window.tableView)
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


@pytest.mark.parametrize(
    "sample_project",
    ["amino.rcms", "continuous.rcms", "lymph.rcms", "meantime.rcms"],
)
def test_undo_immediately_after_open_does_not_clear_loaded_project(sample_project):
    import launch

    app, window = launch.start_automation()
    try:
        assert window.open(
            os.path.abspath(os.path.join("sample_projects", sample_project))
        )

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

    sample_project = os.path.abspath("sample_projects/amino.rcms")

    argv = launch._resolve_startup_argv(
        argv=["RCMetaStudio.exe"],
        native_argv=["RCMetaStudio.exe", sample_project],
        frozen=True,
    )

    assert argv == ["RCMetaStudio.exe", sample_project]
    assert launch._startup_project_path(argv) == sample_project


def test_frozen_startup_argv_keeps_existing_project_argument():
    import launch

    sample_project = os.path.abspath("sample_projects/amino.rcms")
    other_project = os.path.abspath("sample_projects/continuous.rcms")

    argv = launch._resolve_startup_argv(
        argv=["RCMetaStudio.exe", sample_project],
        native_argv=["RCMetaStudio.exe", other_project],
        frozen=True,
    )

    assert argv == ["RCMetaStudio.exe", sample_project]
    assert launch._startup_project_path(argv) == sample_project


def test_startup_smoke_opens_positional_project_without_wizard(monkeypatch):
    import launch

    sample_project = os.path.abspath("sample_projects/amino.rcms")
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
        launch, "_resolve_startup_argv", lambda: ["RCMetaStudio.exe", sample_project]
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
    monkeypatch.setenv("RCMS_STARTUP_PROJECT_SMOKE", "1")

    assert launch.start() == 0
    assert opened == [sample_project]
    assert started == []
    assert closed == [True]
    os.chdir(REPO_ROOT)


def test_meantime_sample_project_loads_native_factor_covariate():
    import test_backend_compat

    test_backend_compat.install()
    import headless_analysis

    model = headless_analysis.load_dataset_model(
        os.path.abspath(os.path.join("sample_projects", "meantime.rcms"))
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
            window.open(
                os.path.abspath(os.path.join("sample_projects", "meantime.rcms"))
            )
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
            "amino.rcms",
            "Gonzalez",
            lambda groups: [
                groups[0].title() + " #evts",
                groups[0].title() + " #total",
                groups[1].title() + " #evts",
                groups[1].title() + " #total",
            ],
        ),
        (
            "continuous.rcms",
            "Carroll",
            lambda groups: [
                groups[0].title() + " N",
                groups[0].title() + " Mean",
                groups[0].title() + " SD",
                groups[1].title() + " N",
                groups[1].title() + " Mean",
                groups[1].title() + " SD",
            ],
        ),
    ]

    for project_name, first_study, raw_headers_for_groups in cases:
        app, window = launch.start_automation()
        try:
            assert (
                window.open(
                    os.path.abspath(os.path.join("sample_projects", project_name))
                )
                is True
            )
            model = window.tableView.model()

            assert (
                model.headerData(
                    model.NAME, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole
                )
                == "Study Name"
            )
            assert (
                model.headerData(
                    model.YEAR, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole
                )
                == "Year"
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
            window.open(os.path.abspath(os.path.join("sample_projects", "amino.rcms")))
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
            window.open(os.path.abspath(os.path.join("sample_projects", "amino.rcms")))
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

        dialog = change_cov_type_form.ChangeCovTypeForm(dataset, dataset.covariates[0])
        try:
            _assert_table_view_leaves_spare_width_outside_data_columns(
                dialog.cov_prev_table
            )
        finally:
            dialog.close()
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
            window.open(os.path.abspath(os.path.join("sample_projects", "amino.rcms")))
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
        assert window.open(os.path.abspath("sample_projects/amino.rcms")) is True
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
        ("amino.rcms", "binary.random", "Binary Random-Effects"),
        ("continuous.rcms", "continuous.random", "Continuous Random-Effects"),
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
                window.open(os.path.abspath(os.path.join("sample_projects", name)))
                is True
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
            "Binary Fixed-Effect Mantel-Haenszel": "binary.fixed.mh",
            "Binary Fixed-Effect Inverse Variance": "binary.fixed.inv.var",
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
            window.open(os.path.abspath(os.path.join("sample_projects", "amino.rcms")))
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
            "DerSimonian-Laird",
            "Only zero-event studies",
        ]
        method_combo = specs[0].method_cbo_box
        assert method_combo.sizeAdjustPolicy() == QtWidgets.QComboBox.AdjustToContents
        widest_method_label = (
            max(
                method_combo.fontMetrics().horizontalAdvance(
                    str(method_combo.itemText(index))
                )
                for index in range(method_combo.count())
            )
            + 48
        )
        assert (
            widest_method_label > qt_layout.ANALYSIS_DIALOG_VALUE_CONTROL_MAXIMUM_WIDTH
        )
        assert method_combo.minimumWidth() == min(
            widest_method_label,
            qt_layout.ANALYSIS_DIALOG_METHOD_COMBO_MAXIMUM_WIDTH,
        )
        assert (
            method_combo.maximumWidth()
            == qt_layout.ANALYSIS_DIALOG_METHOD_COMBO_MAXIMUM_WIDTH
        )
        assert method_combo.view().minimumWidth() >= widest_method_label
        assert method_combo.width() <= method_combo.maximumWidth()
        assert (
            method_combo.sizePolicy().horizontalPolicy()
            != QtWidgets.QSizePolicy.Expanding
        )

        for combo in enum_combos:
            assert combo.sizeAdjustPolicy() == QtWidgets.QComboBox.AdjustToContents
            widest_enum_label = (
                max(
                    combo.fontMetrics().horizontalAdvance(str(combo.itemText(index)))
                    for index in range(combo.count())
                )
                + 48
            )
            assert combo.minimumWidth() == min(
                widest_enum_label,
                qt_layout.ANALYSIS_DIALOG_VALUE_CONTROL_MAXIMUM_WIDTH,
            )
            assert (
                combo.maximumWidth()
                == qt_layout.ANALYSIS_DIALOG_VALUE_CONTROL_MAXIMUM_WIDTH
            )
            assert (
                combo.sizePolicy().horizontalPolicy() != QtWidgets.QSizePolicy.Expanding
            )

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
            assert label.minimumWidth() <= label.sizeHint().width()
            assert label.maximumWidth() >= label.sizeHint().width()

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


def test_method_parameters_dialog_normalizes_missing_parameter_metadata(monkeypatch):
    import launch
    from PyQt5 import QtWidgets

    app, window = launch.start_automation()
    meta_form = sys.modules["meta_form"]
    meta_py_r = sys.modules["meta_py_r"]

    params = {
        "num.iters": "int",
        "lambda.lower": "float",
        "theta.upper": "float",
        "conf.level": "float",
    }
    defaults = {
        "num.iters": 5000,
        "lambda.lower": -2.0,
        "theta.upper": 2.0,
        "conf.level": 95.0,
    }

    monkeypatch.setattr(
        meta_py_r,
        "get_available_methods",
        lambda **kwargs: {"Binary Random-Effects": "binary.random"},
        raising=False,
    )
    monkeypatch.setattr(
        meta_py_r,
        "get_params",
        lambda method: (
            dict(params),
            dict(defaults),
            ["num.iters", "lambda.lower", "theta.upper", "conf.level"],
            {},
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
            window.open(os.path.abspath(os.path.join("sample_projects", "amino.rcms")))
            is True
        )

        window.action_go.trigger()
        specs = window.findChildren(meta_form.ma_specs.MA_Specs)
        assert len(specs) == 1

        labels = {
            str(label.text())
            for label in specs[0].parameter_grp_box.findChildren(QtWidgets.QLabel)
        }
        assert "Number of Iterations" in labels
        assert "Threshold Prior Lower Bound" in labels
        assert "Accuracy Prior Upper Bound" in labels
        assert "Confidence Level" in labels
        assert "num.iters" not in labels
        assert "lambda.lower" not in labels
        assert "theta.upper" not in labels
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_method_parameters_dialog_stays_stable_when_method_description_changes(
    monkeypatch,
):
    import launch
    from PyQt5 import QtCore, QtWidgets

    app, window = launch.start_automation()
    meta_form = sys.modules["meta_form"]
    meta_py_r = sys.modules["meta_py_r"]
    qt_layout = sys.modules["qt_layout"]

    method_map = {
        "binary.random": "binary.random",
        "binary.fixed.mh": "binary.fixed.mh",
    }
    descriptions = {
        "binary.random": "Random-effects analysis",
        "binary.fixed.mh": (
            "Fixed-effect Mantel-Haenszel analysis with a long generated "
            "description that should wrap inside the method panel instead of "
            "widening the dialog while the user changes selections."
        ),
    }
    params = {
        "binary.random": (
            {"rm.method": ["DL", "SJ"], "conf.level": "float", "digits": "float"},
            {"rm.method": "DL", "conf.level": 95.0, "digits": 3},
            ["rm.method", "conf.level", "digits"],
        ),
        "binary.fixed.mh": (
            {"to": ["only0", "all"], "conf.level": "float", "digits": "float"},
            {"to": "only0", "conf.level": 95.0, "digits": 3},
            ["to", "conf.level", "digits"],
        ),
    }
    pretty_names = {
        "rm.method": {
            "pretty.name": "Random-Effects method",
            "description": "Method for estimating between-studies heterogeneity",
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
    }

    monkeypatch.setattr(
        meta_py_r,
        "get_available_methods",
        lambda **kwargs: dict(method_map),
        raising=False,
    )

    def get_params(method):
        method_params, defaults, var_order = params[method]
        return dict(method_params), dict(defaults), list(var_order), pretty_names

    monkeypatch.setattr(meta_py_r, "get_params", get_params, raising=False)
    monkeypatch.setattr(
        meta_py_r,
        "get_method_description",
        lambda method: descriptions[method],
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
            window.open(os.path.abspath(os.path.join("sample_projects", "amino.rcms")))
            is True
        )

        window.action_go.trigger()
        specs = window.findChildren(meta_form.ma_specs.MA_Specs)
        assert len(specs) == 1
        specs = specs[0]
        specs.show()
        app.processEvents()

        stable_width = specs.width()
        stable_height = specs.height()
        stable_minimum_width = specs.minimumWidth()
        assert stable_minimum_width >= qt_layout.ANALYSIS_DIALOG_MINIMUM_WIDTH
        assert specs.layout().sizeConstraint() == QtWidgets.QLayout.SetFixedSize
        assert specs.maximumSize() == specs.minimumSize()
        assert specs.sizePolicy().horizontalPolicy() == QtWidgets.QSizePolicy.Fixed
        assert specs.sizePolicy().verticalPolicy() == QtWidgets.QSizePolicy.Fixed
        assert specs.isSizeGripEnabled() is False

        specs.resize(stable_width + 300, stable_height + 200)
        app.processEvents()
        assert specs.width() == stable_width
        assert specs.height() == stable_height

        long_method_index = specs.method_cbo_box.findText(
            "Binary Fixed-Effect Mantel-Haenszel"
        )
        assert long_method_index >= 0
        specs.method_cbo_box.setCurrentIndex(long_method_index)
        app.processEvents()
        assert specs.parameter_grp_box.title() == "Binary Fixed-Effect Mantel-Haenszel"
        assert specs.parameter_grp_box.title() != "binary.fixed.mh"
        short_method_index = specs.method_cbo_box.findText("Binary Random-Effects")
        specs.method_cbo_box.setCurrentIndex(short_method_index)
        app.processEvents()
        assert specs.parameter_grp_box.title() == "Binary Random-Effects"
        assert specs.parameter_grp_box.title() != "binary.random"

        assert specs.width() == stable_width
        assert specs.minimumWidth() == stable_minimum_width
        assert (
            specs.parameter_grp_box.layout().alignment() & QtCore.Qt.AlignTop
        ) == QtCore.Qt.AlignTop

        descriptions = [
            label
            for label in specs.parameter_grp_box.findChildren(QtWidgets.QLabel)
            if str(label.text()).startswith("Description:")
        ]
        assert len(descriptions) == 1
        assert descriptions[0].wordWrap() is True
        assert descriptions[0].minimumWidth() == 0

        value_controls = []
        for control_type in (
            QtWidgets.QComboBox,
            QtWidgets.QSpinBox,
            QtWidgets.QDoubleSpinBox,
        ):
            value_controls.extend(specs.parameter_grp_box.findChildren(control_type))

        for value_control in value_controls:
            assert (
                value_control.maximumWidth()
                <= qt_layout.ANALYSIS_DIALOG_VALUE_CONTROL_MAXIMUM_WIDTH
            )
            assert (
                value_control.sizePolicy().horizontalPolicy()
                != QtWidgets.QSizePolicy.Expanding
            )
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
        ("amino.rcms", "binary"),
        ("continuous.rcms", "continuous"),
    ]:
        app, window = launch.start_automation()
        meta_form = sys.modules["meta_form"]
        monkeypatch.setattr(meta_form.meta_reg_form, "MetaRegForm", MetaRegDialog)
        monkeypatch.setattr(
            meta_form.meta_subgroup_form, "MetaSubgroupForm", SubgroupDialog
        )

        try:
            assert (
                window.open(os.path.abspath(os.path.join("sample_projects", name)))
                is True
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
            window.open(os.path.abspath(os.path.join("sample_projects", "lymph.rcms")))
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
            window.open(os.path.abspath(os.path.join("sample_projects", "lymph.rcms")))
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
            window.open(os.path.abspath(os.path.join("sample_projects", "amino.rcms")))
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
            "No Covariate Selected",
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
            window.open(os.path.abspath(os.path.join("sample_projects", "amino.rcms")))
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
            window.open(os.path.abspath(os.path.join("sample_projects", "amino.rcms")))
            is True
        )
        group_values = {
            study.name: "north" if index % 2 else "south"
            for index, study in enumerate(window.model.dataset.studies)
        }
        window.model.add_covariate("region", "factor", group_values)

        form = meta_subgroup_form.MetaSubgroupForm(window.model, parent=window)

        assert str(form.windowTitle()) == "Select Covariate"
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
    import test_backend_compat

    test_backend_compat.install()
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

        assert nav_titles == ["Meta-Analysis Summary", "Forest Plot"]
        assert not hasattr(window, "psuedo_console")
        assert window.findChild(QtWidgets.QTextEdit, "psuedo_console") is None
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


def test_results_window_displays_canonical_svg_plot_artifact(tmp_path):
    import launch
    import test_backend_compat

    test_backend_compat.install()
    import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    plot_path = tmp_path / "forest.png"
    svg_path = tmp_path / "forest.svg"
    image = results_window.QImage(1600, 800, results_window.QImage.Format_RGB32)
    image.fill(results_window.Qt.white)
    assert image.save(str(plot_path), "PNG")
    svg_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="800">'
        '<rect width="1600" height="800" fill="white"/>'
        '<text x="20" y="60">Forest Plot</text>'
        "</svg>",
        encoding="utf-8",
    )

    window = results_window.ResultsWindow(
        {
            "texts": {},
            "images": {"Forest Plot": str(plot_path)},
            "image_var_names": {"Forest Plot": "forest_plot"},
            "image_params_paths": {"Forest Plot": str(tmp_path / "forest_params")},
            "image_order": ["Forest Plot"],
        }
    )

    try:
        svg_items = [
            item
            for item in window.scene.items()
            if isinstance(item, results_window.QGraphicsSvgItem)
        ]
        pixmap_items = [
            item
            for item in window.scene.items()
            if isinstance(item, results_window.QGraphicsPixmapItem)
        ]

        assert len(svg_items) == 1
        assert pixmap_items == []
        assert svg_items[0].scale() < 1.0
    finally:
        window.close()
        app.processEvents()


def test_results_window_places_references_after_images_and_wraps_them(tmp_path):
    import launch
    import test_backend_compat

    test_backend_compat.install()
    import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    plot_path = tmp_path / "forest.png"
    image = results_window.QImage(80, 40, results_window.QImage.Format_RGB32)
    image.fill(results_window.Qt.white)
    assert image.save(str(plot_path), "PNG")

    long_reference = (
        "1. Random-effects meta-analysis: DerSimonian, R., & Laird, N. (1986). "
        "Meta-analysis in clinical trials. Controlled Clinical Trials, 7(3), "
        "177-188. doi:10.1016/0197-2456(86)90046-2."
    )
    window = results_window.ResultsWindow(
        {
            "texts": {
                "Summary": "Binary Random-Effects Model",
                "References": long_reference,
            },
            "images": {"Forest Plot": str(plot_path)},
            "image_var_names": {"Forest Plot": "forest_plot"},
            "image_params_paths": {"Forest Plot": str(tmp_path / "forest_params")},
            "image_order": ["Forest Plot"],
        }
    )

    try:
        window.show()
        app.processEvents()

        nav_titles = [
            window.nav_tree.topLevelItem(index).text(0)
            for index in range(window.nav_tree.topLevelItemCount())
        ]
        assert nav_titles == ["Meta-Analysis Summary", "Forest Plot", "References"]

        sections = {
            item.toPlainText(): item
            for item in window.scene.items()
            if isinstance(item, results_window.QGraphicsTextItem)
        }
        reference_item = sections[long_reference]
        assert reference_item.textWidth() >= (
            window.graphics_view.viewport().width() - results_window.padding - 5
        )
        assert (
            reference_item.document().defaultTextOption().wrapMode()
            == results_window.QTextOption.WordWrap
        )
    finally:
        window.close()
        app.processEvents()


def test_results_window_separates_tall_text_sections():
    import launch
    import test_backend_compat

    test_backend_compat.install()
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


def test_results_window_text_context_menu_is_reentrant_safe(monkeypatch):
    import launch
    import test_backend_compat

    test_backend_compat.install()
    import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    popups = []

    class FakeEvent(object):
        def __init__(self):
            self.accepted = False

        def screenPos(self):
            return results_window.QPoint(10, 20)

        def accept(self):
            self.accepted = True

    class FakeSignal(object):
        def __init__(self):
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)

        def emit(self):
            for callback in self._callbacks:
                callback()

    class FakeMenu(object):
        current = None

        def __init__(self, parent=None):
            self.parent = parent
            self.actions = []
            self.aboutToHide = FakeSignal()
            FakeMenu.current = self

        def addAction(self, action):
            self.actions.append(action)

        def popup(self, pos):
            popups.append((pos, [action.text() for action in self.actions]))

    monkeypatch.setattr(results_window, "QMenu", FakeMenu)
    window = results_window.ResultsWindow(
        {
            "texts": {"Summary": "Model Results\nEstimate  Lower bound"},
            "images": {},
            "image_var_names": {},
            "image_params_paths": {},
            "image_order": [],
        }
    )

    try:
        text_items = [
            item
            for item in window.scene.items()
            if isinstance(item, results_window.QGraphicsTextItem)
            and item.toPlainText().startswith("Model Results")
        ]
        assert len(text_items) == 1

        first_event = FakeEvent()
        second_event = FakeEvent()
        text_items[0].contextMenuEvent(first_event)
        text_items[0].contextMenuEvent(second_event)

        assert first_event.accepted is True
        assert second_event.accepted is True
        assert popups == [
            (
                results_window.QPoint(10, 20),
                ["Select All", "Copy"],
            )
        ]

        FakeMenu.current.aboutToHide.emit()
        text_items[0].contextMenuEvent(FakeEvent())
        assert len(popups) == 2
        FakeMenu.current.aboutToHide.emit()
    finally:
        window.close()
        app.processEvents()


def test_results_window_figure_context_menus_offer_edit_for_regenerable_forest_plots(
    monkeypatch,
):
    import launch
    import test_backend_compat

    test_backend_compat.install()
    import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    popups = []

    class FakeEvent(object):
        def __init__(self):
            self.accepted = False

        def screenPos(self):
            return results_window.QPoint(10, 20)

        def accept(self):
            self.accepted = True

    class FakeSignal(object):
        def __init__(self):
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)

        def emit(self):
            for callback in self._callbacks:
                callback()

    class FakeMenu(object):
        current = None

        def __init__(self, parent=None):
            self.parent = parent
            self.actions = []
            self.aboutToHide = FakeSignal()
            FakeMenu.current = self

        def addAction(self, action):
            self.actions.append(action)

        def popup(self, pos):
            popups.append((pos, [action.text() for action in self.actions]))

    monkeypatch.setattr(results_window, "QMenu", FakeMenu)
    window = results_window.ResultsWindow(
        {
            "texts": {},
            "images": {},
            "image_var_names": {},
            "image_params_paths": {},
            "image_order": [],
        }
    )

    try:
        menu_cases = [
            ("plot.data", "Forest Plot", "forest"),
            ("plot.data", "Sensitivity and Specificity", "forest"),
            ("plot.data", "Regression Plot", "regression"),
            (None, "Forest Plot", "forest"),
        ]

        for params_path, title, plot_type in menu_cases:
            event = FakeEvent()
            artifact = results_window.PlotArtifact(
                title,
                "missing.png",
                params_path=params_path,
                plot_type=plot_type,
            )
            handler = window._make_context_menu(artifact, plot_item=None)
            handler(event)
            assert event.accepted is True
            FakeMenu.current.aboutToHide.emit()

        assert popups == [
            (
                results_window.QPoint(10, 20),
                [
                    "Edit Plot",
                    "Save PDF Image As",
                    "Save PNG Image As",
                    "Save TIFF Image As",
                    "Save SVG Image As",
                ],
            ),
            (
                results_window.QPoint(10, 20),
                [
                    "Save PDF Image As",
                    "Save PNG Image As",
                    "Save TIFF Image As",
                    "Save SVG Image As",
                ],
            ),
            (
                results_window.QPoint(10, 20),
                [
                    "Save PDF Image As",
                    "Save PNG Image As",
                    "Save TIFF Image As",
                    "Save SVG Image As",
                ],
            ),
            (results_window.QPoint(10, 20), ["Save PNG Image As"]),
        ]
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize("extension", ["pdf", "png", "tiff", "svg"])
def test_results_window_save_handler_accepts_backend_export_formats(
    tmp_path, monkeypatch, extension
):
    import launch
    import test_backend_compat

    test_backend_compat.install()
    import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    calls = []
    window = results_window.ResultsWindow(
        {
            "texts": {},
            "images": {},
            "image_var_names": {},
            "image_params_paths": {},
            "image_order": [],
        }
    )
    artifact = results_window.PlotArtifact(
        "Forest Plot",
        str(tmp_path / "forest.png"),
        params_path=str(tmp_path / "forest_params"),
        plot_type="forest",
    )

    monkeypatch.setattr(
        results_window.meta_py_r,
        "load_in_R",
        lambda path: calls.append(("load", path)),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.meta_py_r,
        "generate_forest_plot",
        lambda path, side_by_side=False: calls.append(
            ("forest", path, side_by_side)
        ),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(tmp_path / ("saved.%s" % extension)), ""),
    )

    try:
        window.save_image_as(artifact, format=extension)

        assert calls == [
            ("load", "%s.plotdata" % artifact.params_path),
            ("forest", str(tmp_path / ("saved.%s" % extension)), False),
        ]
    finally:
        window.close()
        app.processEvents()


def test_results_window_save_handler_preserves_requested_format_when_extension_is_omitted(
    tmp_path, monkeypatch
):
    import launch
    import test_backend_compat

    test_backend_compat.install()
    import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    calls = []
    window = results_window.ResultsWindow(
        {
            "texts": {},
            "images": {},
            "image_var_names": {},
            "image_params_paths": {},
            "image_order": [],
        }
    )
    artifact = results_window.PlotArtifact(
        "Forest Plot",
        str(tmp_path / "forest.png"),
        params_path=str(tmp_path / "forest_params"),
        plot_type="forest",
    )

    monkeypatch.setattr(
        results_window.meta_py_r,
        "load_in_R",
        lambda path: calls.append(("load", path)),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.meta_py_r,
        "generate_forest_plot",
        lambda path, side_by_side=False: calls.append(
            ("forest", path, side_by_side)
        ),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(tmp_path / "saved"), ""),
    )

    try:
        window.save_image_as(artifact, format="svg")

        assert calls == [
            ("load", "%s.plotdata" % artifact.params_path),
            ("forest", str(tmp_path / "saved.svg"), False),
        ]
    finally:
        window.close()
        app.processEvents()


def test_edit_forest_plot_dialog_round_trips_style_and_appearance_params(monkeypatch):
    import launch
    import test_backend_compat

    test_backend_compat.install()
    import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = results_window.EditForestPlotDialog(
        {
            "fp_style": "default",
            "fp_col1_str": "Study or Subgroup",
            "fp_col2_str": "[default]",
            "fp_col3_str": "Treatment",
            "fp_col4_str": "Control",
            "fp_show_col1": True,
            "fp_show_col2": True,
            "fp_show_col3": True,
            "fp_show_col4": True,
            "fp_show_raw_counts": True,
            "fp_show_headers": True,
            "fp_show_annotation": True,
            "fp_accent_color": "#2f5597",
            "fp_point_size_multiplier": 1.0,
            "fp_xlabel": "[default]",
            "fp_plot_lb": "[default]",
            "fp_plot_ub": "[default]",
            "fp_xticks": "[default]",
            "fp_show_summary_line": True,
        },
        "forest.png",
    )

    try:
        assert dialog.style_cbo.currentText() == "Default (metafor)"
        dialog.style_cbo.setCurrentText("BMJ")
        dialog.show_raw_counts.setChecked(False)
        dialog.show_headers.setChecked(False)
        dialog.show_annotation.setChecked(False)
        dialog.point_size_multiplier.setValue(1.75)

        params = dialog.plot_params()

        assert params["fp_style"] == "bmj"
        assert params["fp_accent_color"] == "#6b58a6"
        assert params["fp_show_raw_counts"] is False
        assert params["fp_show_headers"] is False
        assert params["fp_show_annotation"] is False
        assert params["fp_point_size_multiplier"] == 1.75
    finally:
        dialog.close()
        app.processEvents()


def test_pre_run_plots_tab_exports_style_and_appearance_params(monkeypatch):
    import launch
    import test_backend_compat

    test_backend_compat.install()
    import ma_specs

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    class PlotDefaultsForm(object):
        pass

    form = PlotDefaultsForm()
    form.current_param_vals = {}
    form.style_cbo = QtWidgets.QComboBox()
    form.style_cbo.addItems(["Default (metafor)", "RevMan", "BMJ"])
    form.style_cbo.setCurrentText("RevMan")
    form.show_1 = QtWidgets.QCheckBox()
    form.show_1.setChecked(True)
    form.col1_str_edit = QtWidgets.QLineEdit("Study or Subgroup")
    form.show_2 = QtWidgets.QCheckBox()
    form.show_2.setChecked(False)
    form.col2_str_edit = QtWidgets.QLineEdit("[default]")
    form.show_3 = QtWidgets.QCheckBox()
    form.show_3.setChecked(True)
    form.col3_str_edit = QtWidgets.QLineEdit("Treatment")
    form.show_4 = QtWidgets.QCheckBox()
    form.show_4.setChecked(True)
    form.col4_str_edit = QtWidgets.QLineEdit("Control")
    form.x_lbl_le = QtWidgets.QLineEdit("Odds Ratio")
    form.image_path = QtWidgets.QLineEdit("forest.png")
    form.plot_lb_le = QtWidgets.QLineEdit("[default]")
    form.plot_ub_le = QtWidgets.QLineEdit("[default]")
    form.x_ticks_le = QtWidgets.QLineEdit("[default]")
    form.show_summary_line = QtWidgets.QCheckBox()
    form.show_summary_line.setChecked(True)
    form.show_raw_counts = QtWidgets.QCheckBox()
    form.show_raw_counts.setChecked(False)
    form.show_headers = QtWidgets.QCheckBox()
    form.show_headers.setChecked(False)
    form.show_annotation = QtWidgets.QCheckBox()
    form.show_annotation.setChecked(False)
    form.accent_color = QtWidgets.QLineEdit("#123456")
    form.point_size_multiplier = QtWidgets.QDoubleSpinBox()
    form.point_size_multiplier.setValue(1.5)

    ma_specs.add_plot_params(form)

    assert form.current_param_vals["fp_style"] == "revman"
    assert form.current_param_vals["fp_accent_color"] == "#123456"
    assert form.current_param_vals["fp_point_size_multiplier"] == 1.5
    assert form.current_param_vals["fp_show_raw_counts"] is False
    assert form.current_param_vals["fp_show_headers"] is False
    assert form.current_param_vals["fp_show_annotation"] is False
    assert form.current_param_vals["fp_col3_str"] == "Treatment"
    assert form.current_param_vals["fp_col4_str"] == "Control"
    app.processEvents()


def test_edit_forest_plot_apply_regenerates_plot_without_accepting_dialog(
    tmp_path, monkeypatch
):
    import launch
    import test_backend_compat

    test_backend_compat.install()
    import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    calls = []
    params_path = str(tmp_path / "forest_params")
    png_path = str(tmp_path / "forest.png")
    out_path = str(tmp_path / "edited.png")

    class FakeSignal(object):
        def __init__(self):
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)

        def emit(self):
            for callback in self._callbacks:
                callback()

    class FakeEditForestPlotDialog(object):
        def __init__(self, plot_params, image_path, parent=None):
            self.applied = FakeSignal()
            self._params = {
                "fp_col1_str": "EDIT TEST HEADING",
                "fp_outpath": out_path,
            }
            calls.append(("dialog", plot_params, image_path, parent is not None))

        def exec(self):
            self.applied.emit()
            return results_window.QDialog.Rejected

        def plot_params(self):
            return dict(self._params)

    monkeypatch.setattr(
        results_window.meta_py_r,
        "load_vars_for_plot",
        lambda path, return_params_dict=False: {"fp_col1_str": "Study"},
        raising=False,
    )
    monkeypatch.setattr(
        results_window.meta_py_r,
        "update_plot_params",
        lambda updated_params, write_them_out=False, outpath=None: calls.append(
            ("update", updated_params, write_them_out, outpath)
        ),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.meta_py_r,
        "regenerate_plot_data",
        lambda: calls.append(("regenerate",)),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.meta_py_r,
        "generate_forest_plot",
        lambda outpath: calls.append(("generate", outpath)),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.meta_py_r,
        "write_out_plot_data",
        lambda path: calls.append(("write", path)),
        raising=False,
    )
    monkeypatch.setattr(
        results_window,
        "EditForestPlotDialog",
        FakeEditForestPlotDialog,
    )

    window = results_window.ResultsWindow(
        {
            "texts": {},
            "images": {},
            "image_var_names": {},
            "image_params_paths": {},
            "image_order": [],
        }
    )

    try:
        window.edit_forest_plot(params_path, png_path, plot_item=None)

        assert calls == [
            ("dialog", {"fp_col1_str": "Study"}, png_path, True),
            (
                "update",
                {"fp_col1_str": "EDIT TEST HEADING", "fp_outpath": out_path},
                True,
                "%s.params" % params_path,
            ),
            ("regenerate",),
            ("generate", out_path),
            ("write", params_path),
        ]
    finally:
        window.close()
        app.processEvents()


def test_results_window_ignores_missing_image_order_entries():
    import launch
    import test_backend_compat

    test_backend_compat.install()
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

        assert nav_titles == ["Meta-Analysis Summary"]
        assert not any(
            isinstance(item, results_window.QGraphicsPixmapItem)
            for item in window.scene.items()
        )
    finally:
        window.close()
        app.processEvents()


def test_results_window_uses_reader_oriented_section_names_and_order(tmp_path):
    import launch
    import test_backend_compat

    test_backend_compat.install()
    import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    plot_paths = {}
    for name in ["forest", "roc", "density", "trace"]:
        plot_path = tmp_path / ("%s.png" % name)
        image = results_window.QImage(80, 40, results_window.QImage.Format_RGB32)
        image.fill(results_window.Qt.white)
        assert image.save(str(plot_path), "PNG")
        plot_paths[name] = str(plot_path)

    standard_window = results_window.ResultsWindow(
        {
            "texts": {
                "Weights": "Study weights",
                "Summary": "Binary Random-Effects Model",
            },
            "images": {"Forest Plot": plot_paths["forest"]},
            "image_order": ["Forest Plot"],
        }
    )
    try:
        nav_titles = [
            standard_window.nav_tree.topLevelItem(index).text(0)
            for index in range(standard_window.nav_tree.topLevelItemCount())
        ]

        assert nav_titles == ["Meta-Analysis Summary", "Forest Plot", "Weights"]
        assert standard_window.nav_tree.minimumWidth() >= 250
    finally:
        standard_window.close()
        app.processEvents()

    hsroc_window = results_window.ResultsWindow(
        {
            "texts": {
                "Within-study parameters - theta": "theta",
                "Between-study parameters": "between",
                "Clinical Accuracy Summary": "clinical",
            },
            "images": {
                "Density plots": plot_paths["density"],
                "Trace plots": plot_paths["trace"],
                "Summary ROC": plot_paths["roc"],
            },
            "image_order": ["Summary ROC", "Density plots", "Trace plots"],
        }
    )
    try:
        nav_titles = [
            hsroc_window.nav_tree.topLevelItem(index).text(0)
            for index in range(hsroc_window.nav_tree.topLevelItemCount())
        ]

        assert nav_titles == [
            "Clinical Accuracy Summary",
            "Summary ROC",
            "HSROC Model Parameters",
            "Study-Level Threshold Parameters",
            "Density Plots",
            "Trace Plots",
        ]
    finally:
        hsroc_window.close()
        app.processEvents()


def test_real_metaform_save_as_round_trips_representative_projects(
    tmp_path, monkeypatch
):
    import launch

    for name in ["amino.rcms", "continuous.rcms", "lymph.rcms", "meantime.rcms"]:
        app, window = launch.start_automation()
        saved_path = str(tmp_path / name)

        try:
            assert (
                window.open(os.path.abspath(os.path.join("sample_projects", name)))
                is True
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
            if name == "meantime.rcms":
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

    settings.add_file_to_recent_files("first.rcms")
    settings.add_file_to_recent_files("second.rcms")
    settings.load_settings()

    assert settings.get_setting("recent_files") == ["first.rcms", "second.rcms"]


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
    wizard = main_wizard.MainWizard(recent_datasets=["first.rcms", "second.rcms"])
    try:
        page = wizard.page(main_wizard.Page_Welcome)
        action = page.open_recent_btn.menu().actions()[0]

        page.dataset_selected(action)

        assert wizard.get_wizard_path() == "open"
        assert wizard.get_selected_dataset() == "second.rcms"
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
            lambda **kwargs: ("chosen.rcms", ""),
        )

        page.open_dataset()

        assert wizard.get_wizard_path() == "open"
        assert wizard.get_selected_dataset() == "chosen.rcms"
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


def test_modal_dialogs_center_over_parent_window():
    import launch
    from PyQt5 import QtWidgets
    import main_wizard
    import qt_layout

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    parent = QtWidgets.QMainWindow()
    parent.setGeometry(40, 80, 900, 620)
    parent.show()
    app.processEvents()

    wizard = main_wizard.MainWizard(parent=parent)
    try:
        qt_layout.center_dialog_over_parent(wizard)

        parent_center = parent.frameGeometry().center()
        wizard_center = wizard.frameGeometry().center()
        assert abs(wizard_center.x() - parent_center.x()) <= 1
        assert abs(wizard_center.y() - parent_center.y()) <= 1
    finally:
        wizard.close()
        parent.close()
        app.processEvents()


def test_startup_wizard_cancel_preserves_loaded_dataset(monkeypatch):
    import launch
    from PyQt5 import QtWidgets

    meta_form = launch._import_meta_form()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = meta_form.MetaForm()
    sample_project = os.path.abspath(os.path.join("sample_projects", "amino.rcms"))

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


def test_data_type_page_data_type_buttons_use_uniform_size():
    import launch
    from PyQt5 import QtWidgets
    import main_wizard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        wizard.restart()
        app.processEvents()

        data_type_page = wizard.page(main_wizard.Page_DataType)
        data_type_buttons = [
            data_type_page.onearm_proportion_Button,
            data_type_page.onearm_mean_Button,
            data_type_page.onearm_single_reg_coef_Button,
            data_type_page.onearm_generic_effect_size_Button,
            data_type_page.twoarm_proportions_Button,
            data_type_page.twoarm_means_Button,
            data_type_page.twoarm_smds_Button,
            data_type_page.diagnostic_Button,
        ]

        button_sizes = {
            button.objectName(): (button.size().width(), button.size().height())
            for button in data_type_buttons
        }
        assert len(set(button_sizes.values())) == 1, button_sizes
    finally:
        wizard.close()
        app.processEvents()


def test_data_type_page_buttons_center_icons_inside_declared_slots():
    import launch
    from PyQt5 import QtWidgets
    import main_wizard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        wizard.restart()
        app.processEvents()

        data_type_page = wizard.page(main_wizard.Page_DataType)
        icon_sizes = {
            button.objectName(): (
                button.icon().pixmap(button.iconSize()).size(),
                button.iconSize(),
            )
            for button in data_type_page._data_type_buttons()
        }
        assert all(
            rendered == declared for rendered, declared in icon_sizes.values()
        ), icon_sizes
    finally:
        wizard.close()
        app.processEvents()


def test_new_dataset_wizard_sizes_to_show_diagnostic_choice():
    import launch
    from PyQt5 import QtWidgets
    import main_wizard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        wizard.restart()
        app.processEvents()

        data_type_page = wizard.page(main_wizard.Page_DataType)
        data_type_page.layout().activate()
        app.processEvents()

        diagnostic_button = data_type_page.diagnostic_Button
        assert data_type_page.rect().contains(diagnostic_button.geometry())
        assert wizard.minimumHeight() >= data_type_page.sizeHint().height()
        assert wizard.minimumHeight() >= wizard.sizeHint().height()
    finally:
        wizard.close()
        app.processEvents()


def test_new_dataset_wizard_uses_declarative_minimum_size_policy():
    import launch
    from PyQt5 import QtWidgets
    import main_wizard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        wizard.restart()
        app.processEvents()

        assert wizard.layout().sizeConstraint() == QtWidgets.QLayout.SetMinimumSize
        assert not hasattr(wizard, "_oma_first_show_refit_filter")
        assert wizard.property("RCMS_first_show_refit_options") is None
    finally:
        wizard.close()
        app.processEvents()


@pytest.mark.parametrize("path", [None, "new_dataset", "csv_import"])
def test_wizard_uses_modern_style_with_explicit_back_navigation(path):
    import launch
    from PyQt5 import QtWidgets
    import main_wizard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path=path)
    try:
        assert wizard.wizardStyle() == main_wizard.QWizard.ModernStyle
        assert wizard.button(main_wizard.QWizard.BackButton) is not None
    finally:
        wizard.close()
        app.processEvents()


def test_wizard_layout_smoke_renders_core_wizard_pages():
    import launch
    from PyQt5 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    assert launch.start_wizard_layout_smoke() == 0
    assert [
        widget
        for widget in app.topLevelWidgets()
        if widget.isVisible() and widget.__class__.__name__ == "MainWizard"
    ] == []


def test_new_dataset_wizard_pages_fill_body_without_clipping_content():
    import launch
    from PyQt5 import QtWidgets
    import main_wizard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard()
    try:
        wizard.restart()
        wizard.show()
        app.processEvents()

        welcome_page = wizard.page(main_wizard.Page_Welcome)
        welcome_page.new_dataset()
        app.processEvents()
        stable_body_width = None
        stable_wizard_width = wizard.width()

        page_sequence = [
            main_wizard.Page_DataType,
            main_wizard.Page_ChooseMetric,
            main_wizard.Page_OutcomeName,
        ]
        wizard.page(main_wizard.Page_DataType).twoarm_proportions_Button.click()

        for page_id in page_sequence:
            if wizard.currentId() != page_id:
                wizard.next()
            app.processEvents()

            page = wizard.page(page_id)
            if page.layout() is not None:
                page.layout().activate()
            app.processEvents()

            page_body_width = page.parentWidget().contentsRect().width()
            if stable_body_width is None:
                stable_body_width = page_body_width
            assert abs(page_body_width - stable_body_width) <= 4
            assert abs(wizard.width() - stable_wizard_width) <= 4
            assert page.width() >= page_body_width - 4
            _assert_visible_children_fit_page(page)
    finally:
        wizard.close()
        app.processEvents()


def _assert_visible_children_fit_page(page):
    page_rect = page.rect().adjusted(0, 0, 1, 1)
    for child in page.findChildren(QtWidgets.QWidget):
        if child is page or not child.isVisible():
            continue
        child_rect = child.geometry()
        mapped_top_left = child.parentWidget().mapTo(page, child_rect.topLeft())
        mapped_rect = child_rect
        mapped_rect.moveTopLeft(mapped_top_left)
        assert page_rect.contains(mapped_rect), child.objectName()


def test_data_type_page_canonical_geometry_covers_normalized_content():
    import launch
    from PyQt5 import QtWidgets
    import main_wizard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    data_type_page = main_wizard.DataTypePage()
    try:
        data_type_page.layout().activate()
        ui_tree = ET.parse(Path("src", "forms", "data_type_page.ui"))
        ui_height = int(ui_tree.findtext(".//height"))

        assert ui_height >= data_type_page.minimumHeight()
    finally:
        data_type_page.close()
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


def test_open_existing_dialog_starts_in_sample_projects_even_when_cwd_is_app_data(
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
        _assert_sample_projects_open_directory(calls[0]["directory"])
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_welcome_wizard_open_existing_dialog_starts_in_sample_projects_when_no_recent_project(
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

        _assert_sample_projects_open_directory(calls[0]["directory"])
    finally:
        wizard.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_removed_help_surfaces_do_not_leave_active_ui_or_urls():
    import launch
    import main_wizard
    from PyQt5 import QtWidgets

    app, window = launch.start_automation()

    try:
        assert not hasattr(window, "action_open_help")
        assert not any(
            action.text() == "Open Help" for action in window.menuHelp.actions()
        )
        assert window.action_about_legal.text() == "About/Legal"

        about_calls = []
        original_about = QtWidgets.QMessageBox.about
        QtWidgets.QMessageBox.about = lambda *args: about_calls.append(args)
        try:
            window.action_about_legal.trigger()
        finally:
            QtWidgets.QMessageBox.about = original_about
        about_text = about_calls[0][2]
        assert "RC MetaStudio" in about_text
        assert "Ali Salman" in about_text
        assert "GPL-3.0-or-later" in about_text
        assert "without warranty" in about_text.lower()
        assert "Original OpenMeta[Analyst] Project" in about_text
        assert "NOTICE.md" in about_text

        wizard = main_wizard.MainWizard()
        welcome = wizard.page(main_wizard.Page_Welcome)
        link_text = " ".join(
            [
                welcome.RCMS_onlineLabel.text(),
                welcome.issue_feedback_label.text(),
                welcome.how_to_citeLabel.text(),
            ]
        )
        assert "github.com/AliSalman-et-al/rc-metastudio" in link_text
        retired_support_domain = "ce" + "bm.brown.edu"
        assert retired_support_domain not in link_text.lower()
        assert "tuftscaes.org" not in link_text.lower()
        assert "openMA_help" not in link_text
    finally:
        if "wizard" in locals():
            wizard.close()
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_load_r_libraries_runs_against_stub_bridge():
    # Regression: the frozen maintained build has no Qt4 binding, so test_backend_compat.install()
    # plants the stub meta_py_r used as the milestone-1 R bridge. The real launch
    # path (start -> load_R_libraries) calls get_R_libpaths() + RlibLoader, which
    # must all exist on the stub or the app crashes before the GUI ever shows.
    import launch
    import test_backend_compat

    test_backend_compat.install()
    assert hasattr(sys.modules["meta_py_r"], "get_R_libpaths")

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    class _Splash:
        def showMessage(self, message):
            pass

    # Must not raise AttributeError: module 'meta_py_r' has no attribute 'get_R_libpaths'
    launch.load_R_libraries(app, _Splash())


def test_stub_backend_exposes_data_entry_imputation_methods():
    # Regression for GitHub #48: the maintained PyQt5 path plants a stub meta_py_r,
    # and data-entry dialogs call these methods during construction. The no-R
    # stub must expose them, returning a benign "couldn't impute" result rather
    # than crashing.
    import launch
    import test_backend_compat

    test_backend_compat.install()
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
            window.open(os.path.abspath(os.path.join("sample_projects", "amino.rcms")))
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
            window.open(
                os.path.abspath(os.path.join("sample_projects", "continuous.rcms"))
            )
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
            window.open(os.path.abspath(os.path.join("sample_projects", "lymph.rcms")))
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


def test_data_entry_dialog_tables_expand_and_show_all_rows(monkeypatch):
    import copy
    import launch
    import binary_data_form
    import continuous_data_form
    import diagnostic_data_form

    app, window = launch.start_automation()
    dialogs = []
    monkeypatch.setattr(
        continuous_data_form.ChooseBackCalcResultForm, "exec", lambda self: False
    )

    try:
        assert (
            window.open(os.path.abspath(os.path.join("sample_projects", "amino.rcms")))
            is True
        )
        model = window.model
        dialogs.append(
            binary_data_form.BinaryDataForm2(
                copy.deepcopy(model.get_current_ma_unit_for_study(0)),
                model.current_txs,
                model.get_cur_group_str(),
                model.current_effect,
                conf_level=model.get_global_conf_level(),
                parent=window.tableView,
            )
        )

        assert (
            window.open(
                os.path.abspath(os.path.join("sample_projects", "continuous.rcms"))
            )
            is True
        )
        model = window.model
        dialogs.append(
            continuous_data_form.ContinuousDataForm(
                copy.deepcopy(model.get_current_ma_unit_for_study(0)),
                model.current_txs,
                model.get_cur_group_str(),
                model.current_effect,
                conf_level=model.get_global_conf_level(),
                parent=window.tableView,
            )
        )

        assert (
            window.open(os.path.abspath(os.path.join("sample_projects", "lymph.rcms")))
            is True
        )
        model = window.model
        dialogs.append(
            diagnostic_data_form.DiagnosticDataForm(
                copy.deepcopy(model.get_current_ma_unit_for_study(0)),
                model.current_txs,
                model.get_cur_group_str(),
                conf_level=model.get_global_conf_level(),
                parent=window.tableView,
            )
        )

        tables = [
            dialogs[0].raw_data_table,
            dialogs[1].simple_table,
            dialogs[1].g1_pre_post_table,
            dialogs[1].g2_pre_post_table,
            dialogs[2].two_by_two_table,
        ]
        for table in tables:
            _assert_compact_table_fits_visible_cells(table)
    finally:
        for dialog in dialogs:
            dialog.close()
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_csv_required_format_table_expands_and_shows_all_rows(monkeypatch):
    import main_wizard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    page = main_wizard.CsvImportPage()
    monkeypatch.setattr(
        page,
        "_get_required_header_labels",
        lambda: ["Study", "Year", "Group 1 N", "Group 1 Mean", "Group 1 SD"],
    )

    try:
        page.initializePage()
        table = page.required_fmt_table
        _assert_compact_table_fits_visible_cells(table)
    finally:
        page.close()
        page.deleteLater()
    app.processEvents()


def test_analysis_dialog_family_uses_shared_base_size(monkeypatch):
    import copy
    import launch
    import add_new_dialogs
    import binary_data_form
    import continuous_data_form
    import diagnostic_data_form
    import meta_reg_form
    import meta_subgroup_form
    import qt_layout

    app, window = launch.start_automation()
    dialogs = []
    monkeypatch.setattr(
        continuous_data_form.ChooseBackCalcResultForm, "exec", lambda self: False
    )

    try:
        assert (
            window.open(os.path.abspath(os.path.join("sample_projects", "amino.rcms")))
            is True
        )
        model = window.model
        cov_values = {
            study.name: "north" if index % 2 else "south"
            for index, study in enumerate(model.dataset.studies)
        }
        model.add_covariate("region", "factor", cov_values)
        dialogs.extend(
            [
                meta_reg_form.MetaRegForm(model, parent=window),
                meta_subgroup_form.MetaSubgroupForm(model, parent=window),
                add_new_dialogs.AddNewCovariateForm(parent=window),
                binary_data_form.BinaryDataForm2(
                    copy.deepcopy(model.get_current_ma_unit_for_study(0)),
                    model.current_txs,
                    model.get_cur_group_str(),
                    model.current_effect,
                    conf_level=model.get_global_conf_level(),
                    parent=window.tableView,
                ),
            ]
        )

        assert (
            window.open(
                os.path.abspath(os.path.join("sample_projects", "continuous.rcms"))
            )
            is True
        )
        model = window.model
        dialogs.append(
            continuous_data_form.ContinuousDataForm(
                copy.deepcopy(model.get_current_ma_unit_for_study(0)),
                model.current_txs,
                model.get_cur_group_str(),
                model.current_effect,
                conf_level=model.get_global_conf_level(),
                parent=window.tableView,
            )
        )

        assert (
            window.open(os.path.abspath(os.path.join("sample_projects", "lymph.rcms")))
            is True
        )
        model = window.model
        dialogs.append(
            diagnostic_data_form.DiagnosticDataForm(
                copy.deepcopy(model.get_current_ma_unit_for_study(0)),
                model.current_txs,
                model.get_cur_group_str(),
                conf_level=model.get_global_conf_level(),
                parent=window.tableView,
            )
        )

        for dialog in dialogs:
            dialog.show()
            app.processEvents()
            assert dialog.minimumWidth() >= qt_layout.ANALYSIS_DIALOG_MINIMUM_WIDTH
            assert dialog.minimumHeight() >= qt_layout.ANALYSIS_DIALOG_MINIMUM_HEIGHT
    finally:
        for dialog in dialogs:
            dialog.close()
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_add_covariate_dialog_fields_and_buttons_fill_fitted_width():
    import launch
    import add_new_dialogs
    import qt_layout

    app, window = launch.start_automation()
    dialog = add_new_dialogs.AddNewCovariateForm(parent=window)

    try:
        dialog.show()
        app.processEvents()
        if dialog.layout() is not None:
            dialog.layout().activate()
        app.processEvents()

        contents = dialog.contentsRect()
        dialog_layout = dialog.layout()
        assert dialog_layout is not None
        left_margin = dialog_layout.contentsMargins().left()
        right_margin = dialog_layout.contentsMargins().right()
        expected_content_width = contents.width() - left_margin - right_margin

        assert dialog.minimumWidth() >= qt_layout.ANALYSIS_DIALOG_MINIMUM_WIDTH
        assert dialog.layoutWidget.width() >= expected_content_width
        assert dialog.buttonBox.width() >= expected_content_width
        assert (
            dialog.buttonBox.geometry().right() >= contents.right() - right_margin - 1
        )
    finally:
        dialog.close()
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
    _assert_compact_table_fits_visible_cells(page.preview_table)
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
    assert shown[0][1] == "Warning"
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
            window.open(os.path.abspath(os.path.join("sample_projects", "amino.rcms")))
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


def _assert_sample_projects_open_directory(directory):
    directory = os.path.abspath(directory)
    assert os.path.basename(directory) == "sample_projects"
    assert os.path.exists(os.path.join(directory, "amino.rcms"))
    assert os.path.normcase(directory) != os.path.normcase(os.getcwd())


def _dataset_summary(dataset):
    return {
        "title": dataset.title,
        "studies": [(str(study.name), str(study.year)) for study in dataset.studies],
        "outcomes": sorted(
            str(name) for name in dataset.outcome_names_to_follow_ups.keys()
        ),
    }
