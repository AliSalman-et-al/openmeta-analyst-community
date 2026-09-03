import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RCMS_STUB_BACKEND", "1")
import pytest
from rc_metastudio import automation
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QHeaderView

pytestmark = pytest.mark.qsettings

from rc_metastudio.qt6_ui import prepare_generated_ui_imports
from rc_metastudio.analysis_results import parse_analysis_result
from test_types import key_clicks, required

prepare_generated_ui_imports()

if TYPE_CHECKING:
    from ui_analysis_setup_dialog import Ui_AnalysisSetupDialog
else:
    from rc_metastudio.forms.ui_analysis_setup_dialog import Ui_AnalysisSetupDialog

from rc_metastudio import plot_editor_dialog, results_window

REPO_ROOT = os.getcwd()


def _sample_project_path(name):
    return os.path.join(REPO_ROOT, "sample_projects", name)


def _window_archetype(widget):
    from rc_metastudio import adaptive_window

    return adaptive_window.adaptive_window_state(widget).policy.archetype.value


def _xml_element(parent: ET.Element | None, path: str) -> ET.Element:
    """Require an element that the fixture's UI contract promises to contain."""
    return required(parent.find(path) if parent is not None else None, path)


def _viewport_width(view: QtWidgets.QAbstractScrollArea) -> int:
    """Read a measured viewport after Qt has created it."""

    return required(view.viewport(), "scroll viewport").width()


@pytest.fixture(autouse=True)
def _fail_instead_of_blocking_on_unexpected_critical_dialog(monkeypatch):
    messages = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "critical",
        lambda _parent, title, message: (
            messages.append((title, message)) or QtWidgets.QMessageBox.StandardButton.Ok
        ),
    )
    yield
    assert messages == []


def _plot_capability(
    plot_kind="forest",
    editable=True,
    styleable=True,
    composition="single",
    regenerator="forest",
):
    return {
        "plot_kind": plot_kind,
        "editable": editable,
        "styleable": styleable,
        "composition": composition,
        "regenerator": regenerator,
    }


def _analysis_result(payload):
    """Build the complete result contract used by ResultsWindow fixtures."""
    return parse_analysis_result(payload)


def _assert_compact_table_fits_visible_cells(table):
    owner = table.window()
    owner.resize(owner.width() + 180, owner.height())
    owner.show()
    QtWidgets.QApplication.processEvents()
    table_is_measurable = table.isVisible()
    if not table_is_measurable:
        header = table.horizontalHeader()
        assert (
            header.sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch
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
    assert table.minimumWidth() == 0

    if not table_is_measurable:
        return

    for column, content_width in enumerate(content_widths):
        if (
            table.horizontalHeader().sectionResizeMode(column)
            != QHeaderView.ResizeMode.Stretch
        ):
            assert table.columnWidth(column) >= content_width
        else:
            assert table.columnWidth(column) > 0

    section_width = sum(
        table.horizontalHeader().sectionSize(column)
        for column in range(table.columnCount())
    )
    header = table.horizontalHeader()
    if header.sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch:
        assert section_width >= table.viewport().width() - 1
    else:
        assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Interactive
        assert section_width >= sum(content_widths)


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

    # Qt 6's offscreen platform can report a freshly shown top-level window at
    # its minimum layout width. Give the real workspace a deterministic desktop
    # viewport before asserting that fixed data columns leave spare table space.
    owner.showNormal()
    owner.setMaximumSize(16777215, 16777215)
    owner.resize(max(owner.width() + 320, 1920), max(owner.height(), 1080))
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
    from rc_metastudio import launch

    main_window = launch._import_main_window()
    window = main_window.MainWindow()
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
    assert str(window.model.dataset.studies[1].covariate_values["Region"]) == "South"


def test_full_app_import_pads_ragged_csv_rows_into_dataset():
    from rc_metastudio import launch
    from PyQt6 import QtWidgets

    main_window = launch._import_main_window()
    app = cast(
        QtWidgets.QApplication,
        QtWidgets.QApplication.instance() or QtWidgets.QApplication([]),
    )
    window = main_window.MainWindow()
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


def test_automation_launch_creates_and_closes_main_window():

    app, window = automation.start_automation()
    main_window = sys.modules["rc_metastudio.main_window"]

    assert app is QtWidgets.QApplication.instance()
    assert app.windowIcon().isNull() is False
    assert isinstance(window, main_window.MainWindow)
    assert window.isVisible()

    window.close()
    app.processEvents()
    os.chdir(REPO_ROOT)


def test_automation_launch_shows_main_window_maximized():

    app, window = automation.start_automation()
    try:
        assert window.isVisible()
        assert window.isMaximized()
    finally:
        # This test owns window state, not the interactive save prompt.
        window.current_data_unsaved = False
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_open_project_preserves_main_window_state_without_duplicate_windows(
    monkeypatch,
):
    from rc_metastudio import dataset_table_model
    from rc_metastudio import project_adapter
    from rc_metastudio import project_format

    app, window = automation.start_automation()
    recalculations = []
    monkeypatch.setattr(
        dataset_table_model.DatasetTableModel,
        "try_to_update_outcomes",
        lambda model: recalculations.append(model),
    )
    main_window = sys.modules["rc_metastudio.main_window"]
    critical_messages = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "critical",
        lambda _parent, title, message: (
            critical_messages.append((title, message))
            or QtWidgets.QMessageBox.StandardButton.Ok
        ),
    )

    try:
        window.showMaximized()
        app.processEvents()
        visible_main_windows_before = [
            widget
            for widget in app.topLevelWidgets()
            if isinstance(widget, main_window.MainWindow) and widget.isVisible()
        ]

        # The automation shell begins with an empty unsaved dataset. This test is
        # about replacing that dataset in the same window, so authorize the open
        # without driving the separate interactive save-confirmation contract.
        window.current_data_unsaved = False
        project_path = _sample_project_path("amino.rcms")
        expected_dataset = project_format.load_project(project_path).project["dataset"]
        assert window.open(project_path) is True, critical_messages
        app.processEvents()

        visible_main_windows_after = [
            widget
            for widget in app.topLevelWidgets()
            if isinstance(widget, main_window.MainWindow) and widget.isVisible()
        ]
        assert visible_main_windows_after == visible_main_windows_before
        assert window.isMaximized()
        assert window.tableView.model() is window.model
        assert window.model.rowCount() >= 20
        assert recalculations == []
        observed_dataset = project_adapter.dataset_to_project(window.model.dataset)[
            "dataset"
        ]
        assert observed_dataset == expected_dataset
    finally:
        # This test owns window identity, not the interactive save prompt.
        window.current_data_unsaved = False
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_rc_metastudio_logo_resource_is_valid_and_used_consistently():
    from PyQt6 import QtGui
    from rc_metastudio import launch
    from rc_metastudio import qt6_resources

    qt6_resources.ensure_application_resources()

    app_icon = QtGui.QIcon(launch.APPLICATION_ICON_PATH)
    logo_pixmap = QtGui.QPixmap(":/misc/meta.png")
    splash_pixmap = QtGui.QPixmap(":/misc/splash.png")

    assert launch.APPLICATION_ICON_PATH == ":/misc/meta.png"
    assert app_icon.isNull() is False
    assert logo_pixmap.isNull() is False
    assert splash_pixmap.isNull() is False
    assert logo_pixmap.width() == logo_pixmap.height()
    assert logo_pixmap.width() >= 1024
    assert (splash_pixmap.width(), splash_pixmap.height()) == (1088, 183)
    logo_image = logo_pixmap.toImage().convertToFormat(
        QtGui.QImage.Format.Format_ARGB32
    )
    assert QtGui.qAlpha(logo_image.pixel(0, 0)) == 0
    assert QtGui.qAlpha(logo_image.pixel(512, 512)) == 255
    assert sorted(
        (size.width(), size.height()) for size in app_icon.availableSizes()
    ) == [(1024, 1024)]

    checked_paths = [
        Path("src", "rc_metastudio", "forms", "main_window.ui"),
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


def test_functional_icon_set_is_embedded_and_renders_at_supported_sizes():
    import xml.etree.ElementTree as ET

    from PyQt6 import QtGui
    from rc_metastudio import qt6_resources

    qt6_resources.ensure_application_resources()

    qrc_path = Path("src", "rc_metastudio", "images", "icons.qrc")
    qrc_root = ET.parse(qrc_path).getroot()
    resources = {}
    family_counts = {}
    for resource_group in qrc_root.findall("qresource"):
        prefix = resource_group.attrib["prefix"].lstrip("/")
        if not prefix.startswith("icons/"):
            continue
        family_counts[prefix] = len(resource_group.findall("file"))
        for file_node in resource_group.findall("file"):
            alias = file_node.attrib["alias"]
            resources[f":/{prefix}/{alias}"] = qrc_path.parent / required(
                file_node.text, "resource path"
            )

    assert family_counts == {
            "icons/actions": 22,
        "icons/analyses": 6,
        "icons/analyses/compact": 6,
        "icons/dataset-types": 8,
        "icons/dataset-types/dark": 8,
        "icons/dataset-types/light": 8,
        "icons/table": 1,
    }
    assert len(resources) == 59

    wide_dataset_icon_sizes = {
        ":/icons/dataset-types/generic-effect-size.svg": (54, 40),
        ":/icons/dataset-types/two-arm-means.svg": (58, 40),
        ":/icons/dataset-types/two-arm-proportions.svg": (72, 44),
    }
    simple_dataset_height_ranges = {
        ":/icons/dataset-types/one-arm-mean.svg": (18, 21),
        ":/icons/dataset-types/single-regression-coefficient.svg": (20, 22),
        ":/icons/dataset-types/standardized-mean-difference.svg": (19, 21),
    }

    for resource_path, source_path in resources.items():
        base_dataset_path = resource_path.replace(
            "/dataset-types/light/", "/dataset-types/"
        ).replace("/dataset-types/dark/", "/dataset-types/")
        root = ET.parse(source_path).getroot()
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        if "/analyses/compact/" in resource_path:
            expected_width, expected_height = (20, 20)
        elif resource_path.startswith(":/icons/table/"):
            expected_width, expected_height = (18, 18)
        else:
            expected_width, expected_height = wide_dataset_icon_sizes.get(
                base_dataset_path, (48, 48)
            )
        assert root.attrib["viewBox"] == (f"0 0 {expected_width} {expected_height}")
        assert not root.findall(".//{http://www.w3.org/2000/svg}text")
        if resource_path.startswith(":/icons/dataset-types/"):
            source_text = source_path.read_text(encoding="utf-8").lower()
            expected_ink = "#e7edf0" if "/dark/" in resource_path else "#60798d"
            assert expected_ink in source_text
            assert "#243746" not in source_text

            embedded_file = QtCore.QFile(resource_path)
            assert embedded_file.open(QtCore.QIODevice.OpenModeFlag.ReadOnly)
            embedded_bytes = bytes(embedded_file.readAll().data()).replace(
                b"\r\n", b"\n"
            )
            source_bytes = source_path.read_bytes().replace(b"\r\n", b"\n")
            assert embedded_bytes == source_bytes, (
                f"{resource_path} is stale; regenerate the checked-in Qt resources"
            )

        icon = QtGui.QIcon(resource_path)
        assert icon.isNull() is False
        for extent in (16, 18, 24, 28, 40, 48):
            pixmap = icon.pixmap(extent, extent)
            assert pixmap.isNull() is False
            assert 0 < pixmap.width() <= extent
            assert 0 < pixmap.height() <= extent
            assert extent in (pixmap.width(), pixmap.height())
            assert pixmap.toImage().hasAlphaChannel()

            if "/analyses/compact/" in resource_path:
                family = "compact-analyses"
                ui_extent = 18
            elif resource_path.startswith(":/icons/table/"):
                family = "table"
                ui_extent = 16
            else:
                family = resource_path.split("/")[2]
                ui_extent = {
                    "actions": 28,
                    "analyses": 28,
                    "dataset-types": 40,
                }[family]
            if extent == ui_extent:
                image = pixmap.toImage()
                rendered_width = image.width()
                rendered_height = image.height()
                perimeter_alpha = [
                    QtGui.qAlpha(image.pixel(x, y))
                    for x, y in (
                        *((x, 0) for x in range(rendered_width)),
                        *((x, rendered_height - 1) for x in range(rendered_width)),
                        *((0, y) for y in range(rendered_height)),
                        *((rendered_width - 1, y) for y in range(rendered_height)),
                    )
                ]
                assert max(perimeter_alpha) <= 4, (
                    f"{resource_path} paints into its {extent}px UI pixmap boundary"
                )

                visible_pixels = [
                    (x, y)
                    for y in range(rendered_height)
                    for x in range(rendered_width)
                    if QtGui.qAlpha(image.pixel(x, y)) > 4
                ]
                visible_height = (
                    max(y for _, y in visible_pixels)
                    - min(y for _, y in visible_pixels)
                    + 1
                )
                visible_width = (
                    max(x for x, _ in visible_pixels)
                    - min(x for x, _ in visible_pixels)
                    + 1
                )
                if family == "actions":
                    assert 14 <= visible_width <= 26
                    assert 14 <= visible_height <= 24, (
                        f"{resource_path} is outside the toolbar optical-size grid"
                    )
                elif family == "analyses":
                    assert 22 <= visible_width <= 24
                    assert 21 <= visible_height <= 24, (
                        f"{resource_path} is outside the standard analysis grid"
                    )
                elif family == "compact-analyses":
                    assert 14 <= visible_width <= 16
                    assert 14 <= visible_height <= 16, (
                        f"{resource_path} is outside the compact analysis grid"
                    )
                elif family == "table":
                    assert 11 <= visible_width <= 13
                    assert 13 <= visible_height <= 15, (
                        f"{resource_path} is outside the compact table grid"
                    )
                elif (
                    family == "dataset-types"
                    and base_dataset_path not in wide_dataset_icon_sizes
                ):
                    assert 13 <= visible_height <= 24, (
                        f"{resource_path} is outside the dataset icon optical-size range"
                    )
                    center_x = (
                        min(x for x, _ in visible_pixels)
                        + max(x for x, _ in visible_pixels)
                    ) / 2
                    center_y = (
                        min(y for _, y in visible_pixels)
                        + max(y for _, y in visible_pixels)
                    ) / 2
                    assert abs(center_x - (rendered_width - 1) / 2) <= 2
                    assert abs(center_y - (rendered_height - 1) / 2) <= 2
                    if base_dataset_path in simple_dataset_height_ranges:
                        minimum_height, maximum_height = simple_dataset_height_ranges[
                            base_dataset_path
                        ]
                        assert minimum_height <= visible_height <= maximum_height

        if base_dataset_path in wide_dataset_icon_sizes:
            requested_width, requested_height = wide_dataset_icon_sizes[
                base_dataset_path
            ]
            ui_pixmap = icon.pixmap(requested_width, requested_height)
            assert ui_pixmap.width() == requested_width
            assert ui_pixmap.height() == requested_height
            ui_image = ui_pixmap.toImage()
            ui_visible_pixels = [
                (x, y)
                for y in range(ui_image.height())
                for x in range(ui_image.width())
                if QtGui.qAlpha(ui_image.pixel(x, y)) > 4
            ]
            ui_visible_height = (
                max(y for _, y in ui_visible_pixels)
                - min(y for _, y in ui_visible_pixels)
                + 1
            )
            assert 13 <= ui_visible_height <= 24, (
                f"{resource_path} is outside the dataset icon optical-size range"
            )

            ui_visible_width = (
                max(x for x, _ in ui_visible_pixels)
                - min(x for x, _ in ui_visible_pixels)
                + 1
            )
            ui_center_x = (
                min(x for x, _ in ui_visible_pixels)
                + max(x for x, _ in ui_visible_pixels)
            ) / 2
            ui_center_y = (
                min(y for _, y in ui_visible_pixels)
                + max(y for _, y in ui_visible_pixels)
            ) / 2
            assert abs(ui_center_x - (ui_image.width() - 1) / 2) <= 2
            assert abs(ui_center_y - (ui_image.height() - 1) / 2) <= 2
            assert ui_visible_width <= requested_width - 2

    for analysis_prefix in (":/icons/analyses/", ":/icons/analyses/compact/"):
        cumulative_root = ET.parse(
            resources[analysis_prefix + "cumulative-analysis.svg"]
        ).getroot()
        leave_one_out_root = ET.parse(
            resources[analysis_prefix + "leave-one-out-analysis.svg"]
        ).getroot()
        assert [ET.tostring(child) for child in list(cumulative_root)[:-1]] == [
            ET.tostring(child) for child in list(leave_one_out_root)[:-1]
        ]
        for root in (cumulative_root, leave_one_out_root):
            assert not any("opacity" in element.attrib for element in root.iter())
            assert not any(
                float(rect.attrib.get("width", 0)) > 8
                and float(rect.attrib.get("height", 0)) > 8
                for rect in root.findall(".//{http://www.w3.org/2000/svg}rect")
            ), "analysis icons must not restore a haze-producing background tile"

    canonical_ui = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("src", "rc_metastudio", "forms").glob("*.ui")
    )
    for legacy_prefix in (":/function_icon_set/", ":/toolbar-icons/", ":/new_dataset/"):
        assert legacy_prefix not in canonical_ui


def test_automation_launch_shows_default_confidence_level_at_startup():

    app, window = automation.start_automation()

    try:
        assert window.cl_label.text() == "Confidence Level: 95.0%"
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_automation_launch_opens_sample_project_in_real_data_table():

    sample_project = _sample_project_path("amino.rcms")
    app, window = automation.start_automation()

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
            window.current_outcome_label.text()
            == "<font color='Blue'>clinical failure</font>"
        )
        assert (
            window.current_follow_up_label.text() == "<font color='Blue'>first</font>"
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
def test_main_data_grid_leaves_spare_width_outside_data_columns(
    sample_project, monkeypatch
):

    critical_messages = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "critical",
        lambda _parent, title, message: (
            critical_messages.append((title, message))
            or QtWidgets.QMessageBox.StandardButton.Ok
        ),
    )
    app, window = automation.start_automation()
    try:
        assert window.open(_sample_project_path(sample_project)), critical_messages

        _assert_table_view_leaves_spare_width_outside_data_columns(window.tableView)
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


@pytest.mark.parametrize(
    "sample_project",
    ["amino.rcms", "continuous.rcms", "lymph.rcms", "meantime.rcms"],
)
def test_undo_immediately_after_open_does_not_clear_loaded_project(
    sample_project, monkeypatch
):

    critical_messages = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "critical",
        lambda _parent, title, message: (
            critical_messages.append((title, message))
            or QtWidgets.QMessageBox.StandardButton.Ok
        ),
    )
    app, window = automation.start_automation()
    try:
        assert window.open(_sample_project_path(sample_project)), critical_messages

        loaded_model = window.model
        loaded_row_count = loaded_model.rowCount()
        loaded_summary = _dataset_summary(loaded_model.dataset)
        loaded_outcome = window.current_outcome_label.text()
        loaded_follow_up = window.current_follow_up_label.text()
        assert loaded_row_count > 0

        window.undo()
        app.processEvents()

        assert window.model.rowCount() == loaded_row_count
        assert _dataset_summary(window.model.dataset) == loaded_summary
        assert window.current_outcome_label.text() == loaded_outcome
        assert window.current_follow_up_label.text() == loaded_follow_up
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
    from rc_metastudio import launch

    sample_project = _sample_project_path("amino.rcms")

    argv = launch._resolve_startup_argv(
        argv=["RCMetaStudio.exe"],
        native_argv=["RCMetaStudio.exe", sample_project],
        frozen=True,
    )

    assert argv == ["RCMetaStudio.exe", sample_project]
    assert launch._startup_project_path(argv) == sample_project


def test_frozen_startup_argv_keeps_existing_project_argument():
    from rc_metastudio import launch

    sample_project = _sample_project_path("amino.rcms")
    other_project = _sample_project_path("continuous.rcms")

    argv = launch._resolve_startup_argv(
        argv=["RCMetaStudio.exe", sample_project],
        native_argv=["RCMetaStudio.exe", other_project],
        frozen=True,
    )

    assert argv == ["RCMetaStudio.exe", sample_project]
    assert launch._startup_project_path(argv) == sample_project


def test_startup_smoke_opens_positional_project_without_wizard(monkeypatch, tmp_path):
    from rc_metastudio import automation
    from rc_metastudio import launch

    sample_project = _sample_project_path("amino.rcms")
    completion_marker = tmp_path / "launchservices-completion.json"
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

        def hide(self):
            pass

        def deleteLater(self):
            pass

    monkeypatch.setattr(
        launch,
        "_resolve_startup_argv",
        lambda: [
            "RCMetaStudio.app",
            "--automation-startup-project-smoke",
            "--automation-startup-completion-marker",
            str(completion_marker),
            sample_project,
        ],
    )
    monkeypatch.setattr(
        launch,
        "_import_main_window",
        lambda: type("MainWindowModule", (), {"MainWindow": Window}),
    )
    monkeypatch.setattr(launch.QtWidgets, "QApplication", lambda argv: app)
    monkeypatch.setattr(launch, "QPixmap", lambda path: object())
    monkeypatch.setattr(launch, "QSplashScreen", Splash)
    monkeypatch.setattr(launch, "create_startup_splash", lambda: Splash(object()))
    monkeypatch.setattr(launch, "load_R_libraries", lambda app, splash: None)
    monkeypatch.setattr(
        automation,
        "dispatch",
        lambda *_: pytest.fail("startup project smoke must not dispatch"),
    )
    monkeypatch.setattr(automation, "_force_table_paint", lambda app, meta: None)

    assert launch.start() == 0
    assert opened == [sample_project]
    assert started == []
    assert closed == [True]
    marker = json.loads(completion_marker.read_text(encoding="utf-8"))
    assert marker["project"] == "amino.rcms"
    os.chdir(REPO_ROOT)


def test_meantime_sample_project_loads_native_factor_covariate():
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import headless_analysis

    model = headless_analysis.load_dataset_model(_sample_project_path("meantime.rcms"))
    dataset = model.dataset

    assert ("treatment group", 4) in [
        (cov.name, cov.data_type) for cov in dataset.covariates
    ]
    values = [study.covariate_values["treatment group"] for study in dataset.studies]
    present_values = [value for value in values if value is not None]
    assert present_values
    assert all(type(value) is str for value in present_values)
    assert set(present_values) == {"1", "2", "3", "4"}


def test_automation_launch_opens_meantime_project_and_enables_subgroup_analysis():

    app, window = automation.start_automation()
    try:
        assert window.open(_sample_project_path("meantime.rcms")) is True

        assert window.tableView.model() is window.model
        assert window.model.rowCount() >= 1
        assert window.action_subgroup_ma.isEnabled()
        values = [
            study.covariate_values["treatment group"]
            for study in window.model.dataset.studies
        ]
        assert all(type(value) is str for value in values if value is not None)
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_opened_sample_projects_return_native_table_values_for_pyqt6_rendering():
    from PyQt6 import QtCore, QtGui

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
        app, window = automation.start_automation()
        try:
            assert window.open(_sample_project_path(project_name)) is True
            model = window.tableView.model()

            assert (
                model.headerData(
                    model.NAME,
                    QtCore.Qt.Orientation.Horizontal,
                    QtCore.Qt.ItemDataRole.DisplayRole,
                )
                == "Study Name"
            )
            assert (
                model.headerData(
                    model.YEAR,
                    QtCore.Qt.Orientation.Horizontal,
                    QtCore.Qt.ItemDataRole.DisplayRole,
                )
                == "Year"
            )
            raw_headers = raw_headers_for_groups(model.current_groups)
            assert [
                model.headerData(
                    column,
                    QtCore.Qt.Orientation.Horizontal,
                    QtCore.Qt.ItemDataRole.DisplayRole,
                )
                for column in model.RAW_DATA
            ] == raw_headers
            assert (
                model.headerData(
                    0,
                    QtCore.Qt.Orientation.Vertical,
                    QtCore.Qt.ItemDataRole.DisplayRole,
                )
                == 1
            )

            assert (
                model.data(
                    model.index(0, model.NAME), QtCore.Qt.ItemDataRole.DisplayRole
                )
                == first_study
            )
            assert isinstance(
                model.data(
                    model.index(0, model.YEAR), QtCore.Qt.ItemDataRole.DisplayRole
                ),
                int,
            )
            assert (
                model.data(
                    model.index(0, model.INCLUDE_STUDY),
                    QtCore.Qt.ItemDataRole.CheckStateRole,
                )
                == QtCore.Qt.CheckState.Checked
            )
            assert model.data(
                model.index(0, model.NAME), QtCore.Qt.ItemDataRole.TextAlignmentRole
            ) == int(
                QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
            assert isinstance(
                model.data(
                    model.index(0, model.OUTCOMES[0]),
                    QtCore.Qt.ItemDataRole.BackgroundRole,
                ),
                QtGui.QColor,
            )

            visible_values = [
                model.headerData(
                    model.NAME,
                    QtCore.Qt.Orientation.Horizontal,
                    QtCore.Qt.ItemDataRole.DisplayRole,
                ),
                model.data(
                    model.index(0, model.NAME), QtCore.Qt.ItemDataRole.DisplayRole
                ),
            ]
            assert all(not hasattr(value, "value") for value in visible_values)
        finally:
            window.close()
            app.processEvents()
            os.chdir(REPO_ROOT)


def test_edit_list_models_return_native_values_and_accept_native_edits():
    from PyQt6 import QtCore
    from rc_metastudio import edit_list_models

    app, window = automation.start_automation()
    try:
        assert window.open(_sample_project_path("amino.rcms")) is True
        dataset = window.model.dataset
        window.model.add_covariate(
            "Dose",
            "continuous",
            dict(
                (study.name, index + 1) for index, study in enumerate(dataset.studies)
            ),
        )
        follow_up_name = dataset.get_follow_up_names_for_outcome(
            window.model.current_outcome_name
        )[0]

        models = [
            edit_list_models.TXGroupsModel(
                dataset=dataset,
                outcome=window.model.current_outcome_name,
                follow_up=follow_up_name,
            ),
            edit_list_models.OutcomesModel(dataset=dataset),
            edit_list_models.FollowUpsModel(
                dataset=dataset, outcome=window.model.current_outcome_name
            ),
            edit_list_models.StudiesModel(dataset=dataset),
            edit_list_models.CovariatesModel(dataset=dataset),
        ]

        for list_model in models:
            index = list_model.index(0, 0)
            display_value = list_model.data(index, QtCore.Qt.ItemDataRole.DisplayRole)
            alignment_value = list_model.data(
                index, QtCore.Qt.ItemDataRole.TextAlignmentRole
            )

            assert display_value not in (None, "")
            assert not hasattr(display_value, "value")
            assert alignment_value == int(
                QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
            )

        group_model = edit_list_models.TXGroupsModel(
            dataset=dataset,
            outcome=window.model.current_outcome_name,
            follow_up=follow_up_name,
        )
        assert group_model.setData(group_model.index(0, 0), "Renamed Group") is True
        assert "Renamed Group" in [
            group_model.data(
                group_model.index(row, 0), QtCore.Qt.ItemDataRole.DisplayRole
            )
            for row in range(group_model.rowCount())
        ]

        follow_up_model = edit_list_models.FollowUpsModel(
            dataset=dataset, outcome=window.model.current_outcome_name
        )
        assert (
            follow_up_model.setData(follow_up_model.index(0, 0), "Renamed Follow Up")
            is True
        )
        assert (
            follow_up_model.data(
                follow_up_model.index(0, 0), QtCore.Qt.ItemDataRole.DisplayRole
            )
            == "Renamed Follow Up"
        )

        studies_model = edit_list_models.StudiesModel(dataset=dataset)
        assert studies_model.setData(studies_model.index(0, 0), "Renamed Study") is True
        assert (
            studies_model.data(
                studies_model.index(0, 0), QtCore.Qt.ItemDataRole.DisplayRole
            )
            == "Renamed Study"
        )

        covariates_model = edit_list_models.CovariatesModel(dataset=dataset)
        assert (
            covariates_model.setData(covariates_model.index(0, 0), "Renamed Dose")
            is True
        )
        assert (
            covariates_model.data(
                covariates_model.index(0, 0), QtCore.Qt.ItemDataRole.DisplayRole
            )
            == "Renamed Dose"
        )

        outcomes_model = edit_list_models.OutcomesModel(dataset=dataset)
        assert (
            outcomes_model.setData(outcomes_model.index(0, 0), "Renamed Outcome")
            is True
        )
        assert (
            outcomes_model.data(
                outcomes_model.index(0, 0), QtCore.Qt.ItemDataRole.DisplayRole
            )
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
    from PyQt6 import QtCore
    from rc_metastudio import covariate_type_dialog
    from rc_metastudio import analysis_dataset

    app, window = automation.start_automation()
    try:
        assert window.open(_sample_project_path("amino.rcms")) is True
        dataset = window.model.dataset
        window.model.add_covariate(
            "Dose",
            "continuous",
            dict(
                (study.name, index + 1) for index, study in enumerate(dataset.studies)
            ),
        )

        cov_model = covariate_type_dialog.CovariateTypeModel(
            dataset, dataset.covariates[0]
        )
        assert (
            cov_model.headerData(
                cov_model.STUDY_COL,
                QtCore.Qt.Orientation.Horizontal,
                QtCore.Qt.ItemDataRole.DisplayRole,
            )
            == "study"
        )
        assert (
            cov_model.headerData(
                cov_model.NEW_VAL,
                QtCore.Qt.Orientation.Horizontal,
                QtCore.Qt.ItemDataRole.DisplayRole,
            )
            == "Dose (factor)"
        )
        assert cov_model.headerData(
            cov_model.NEW_VAL,
            QtCore.Qt.Orientation.Horizontal,
            QtCore.Qt.ItemDataRole.TextAlignmentRole,
        ) == int(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )

        display_value = cov_model.data(
            cov_model.index(0, cov_model.STUDY_COL), QtCore.Qt.ItemDataRole.DisplayRole
        )
        assert display_value not in (None, "")
        assert not hasattr(display_value, "value")

        assert cov_model.setData(cov_model.index(0, cov_model.NEW_VAL), "High") is True
        assert (
            cov_model.data(
                cov_model.index(0, cov_model.NEW_VAL),
                QtCore.Qt.ItemDataRole.DisplayRole,
            )
            == "High"
        )

        dataset.add_covariate(
            analysis_dataset.Covariate("Region", "factor"),
            dict((study.name, "North") for study in dataset.studies),
        )
        continuous_cov_model = covariate_type_dialog.CovariateTypeModel(
            dataset, dataset.covariates[-1]
        )
        errors = []
        continuous_cov_model.dataError.connect(errors.append)
        old_value = continuous_cov_model.data(
            continuous_cov_model.index(0, continuous_cov_model.NEW_VAL),
            QtCore.Qt.ItemDataRole.DisplayRole,
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
                QtCore.Qt.ItemDataRole.DisplayRole,
            )
            == old_value
        )

        dialog = covariate_type_dialog.CovariateTypeDialog(
            dataset, dataset.covariates[0]
        )
        try:
            _assert_table_view_leaves_spare_width_outside_data_columns(
                dialog.covariate_preview_table
            )
        finally:
            dialog.close()
    finally:
        window.current_data_unsaved = False
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_factor_covariate_edits_render_as_native_paint_text():
    from PyQt6 import QtCore, QtWidgets

    app, window = automation.start_automation()
    try:
        assert window.open(_sample_project_path("amino.rcms")) is True
        model = window.tableView.model()
        model.add_covariate("Region", "factor")
        factor_column = model.columnCount() - 1
        factor_index = model.index(0, factor_column)

        assert model.setData(factor_index, "North") is True
        stored_value = model.dataset.studies[0].covariate_values["Region"]
        display_value = model.data(factor_index, QtCore.Qt.ItemDataRole.DisplayRole)

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

    app, window = automation.start_automation()
    main_window = sys.modules["rc_metastudio.main_window"]
    calls = []

    class SpecsDialog(object):
        def __init__(
            self, model, analysis_type=None, parent=None, confidence_level=None
        ):
            calls.append(
                (
                    analysis_type,
                    parent,
                    confidence_level,
                    model.get_current_outcome_type(),
                )
            )

        def show(self):
            pass

    monkeypatch.setattr(
        main_window.analysis_setup_dialog, "AnalysisSetupDialog", SpecsDialog
    )

    try:
        assert window.open(_sample_project_path("amino.rcms")) is True
        window.action_cum_ma.trigger()
        window.action_loo_ma.trigger()

        assert calls == [
            ("cumulative", window, window.model.get_confidence_level(), "binary"),
            ("leave-one-out", window, window.model.get_confidence_level(), "binary"),
        ]
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_standard_meta_analysis_opens_specs_and_runs_through_backend(monkeypatch):
    # Drives the full GUI analysis path (open -> action_go -> AnalysisSetupDialog -> run_ma
    # -> results window) against a mocked in-process r_bridge backend.

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

        app, window = automation.start_automation()
        main_window = sys.modules["rc_metastudio.main_window"]
        r_bridge = sys.modules["rc_metastudio.r_bridge"]
        monkeypatch.setattr(main_window.results_window, "ResultsWindow", ResultDialog)
        monkeypatch.setattr(
            r_bridge,
            "get_available_methods",
            lambda **kwargs: {method_label: method_name},
            raising=False,
        )
        monkeypatch.setattr(
            r_bridge, "get_params", lambda method: ({}, {}, None, {}), raising=False
        )
        monkeypatch.setattr(
            r_bridge,
            "get_method_description",
            lambda method: "Random-effects analysis",
            raising=False,
        )
        monkeypatch.setattr(
            r_bridge,
            "dataset_to_simple_binary_r_object",
            lambda model, **kwargs: None,
            raising=False,
        )
        monkeypatch.setattr(
            r_bridge,
            "dataset_to_simple_continuous_r_object",
            lambda model, **kwargs: None,
            raising=False,
        )
        monkeypatch.setattr(r_bridge, "run_binary_analysis", run, raising=False)
        monkeypatch.setattr(r_bridge, "run_continuous_analysis", run, raising=False)

        try:
            assert window.open(_sample_project_path(name)) is True

            window.action_go.trigger()
            specs = window.findChildren(
                main_window.analysis_setup_dialog.AnalysisSetupDialog
            )
            assert len(specs) == 1

            specs[0].run_ma()

            assert calls[-1] == method_name
            assert shown[-2:] == [
                (
                    _analysis_result({"texts": {"Summary": "%s model" % method_name}}),
                    window,
                ),
                "shown",
            ]
        finally:
            window.close()
            app.processEvents()
            os.chdir(REPO_ROOT)


def test_method_parameters_dialog_displays_enum_defaults(monkeypatch):
    from PyQt6 import QtWidgets

    app, window = automation.start_automation()
    main_window = sys.modules["rc_metastudio.main_window"]
    r_bridge = sys.modules["rc_metastudio.r_bridge"]

    params = {
        "rm.method": ["HE", "DL", "HS", "HSk", "SJ", "ML", "REML", "EB", "PM", "PMM"],
        "inference.method": ["z", "t", "knha", "adhoc"],
        "to": ["only0", "all"],
        "conf.level": "float",
        "digits": "float",
        "adjust": "float",
    }
    defaults = {
        "rm.method": "DL",
        "inference.method": "z",
        "to": "only0",
        "conf.level": 95.0,
        "digits": 2,
        "adjust": 0.5,
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
        "inference.method": {
            "pretty.name": "Inference method",
            "description": "Procedure used for coefficient tests and confidence intervals",
            "inference.method.names": {
                "z": "Normal approximation",
                "t": "Student's t-distribution",
                "knha": "Knapp-Hartung",
                "adhoc": "Modified Knapp-Hartung",
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
            "pretty.name": "Decimal places",
            "description": "Decimal places for displayed estimates and intervals; p-values use at least 3",
        },
        "adjust": {
            "pretty.name": "Correction factor",
            "description": "Constant added to two-by-two table entries.",
        },
    }

    monkeypatch.setattr(
        r_bridge,
        "get_available_methods",
        lambda **kwargs: {
            "Binary Random-Effects": "binary.random",
            "Binary Fixed-Effect Mantel-Haenszel": "binary.fixed.mh",
            "Binary Fixed-Effect Inverse Variance": "binary.fixed.inv.var",
        },
        raising=False,
    )
    monkeypatch.setattr(
        r_bridge,
        "get_params",
        lambda method: (
            dict(params),
            dict(defaults),
            [
                "rm.method",
                "inference.method",
                "to",
                "conf.level",
                "digits",
                "adjust",
            ],
            pretty_names,
        ),
        raising=False,
    )
    monkeypatch.setattr(
        r_bridge,
        "get_method_description",
        lambda method: "Random-effects analysis",
        raising=False,
    )
    monkeypatch.setattr(
        r_bridge,
        "dataset_to_simple_binary_r_object",
        lambda model, **kwargs: None,
        raising=False,
    )

    try:
        assert window.open(_sample_project_path("amino.rcms")) is True

        window.action_go.trigger()
        specs = window.findChildren(
            main_window.analysis_setup_dialog.AnalysisSetupDialog
        )
        assert len(specs) == 1
        assert _window_archetype(specs[0]) == "transactional"
        specs[0].show()
        app.processEvents()

        enum_combos = [
            combo
            for combo in specs[0].parameter_grp_box.findChildren(QtWidgets.QComboBox)
            if combo is not specs[0].method_cbo_box
        ]
        assert [str(combo.currentText()) for combo in enum_combos] == [
            "DerSimonian-Laird",
            "Normal approximation",
            "Only zero-event studies",
        ]
        method_combo = specs[0].method_cbo_box
        assert (
            method_combo.sizeAdjustPolicy()
            == QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        widest_method_label = max(
            method_combo.fontMetrics().horizontalAdvance(
                str(method_combo.itemText(index))
            )
            for index in range(method_combo.count())
        )
        assert method_combo.maximumWidth() == QtWidgets.QWIDGETSIZE_MAX
        assert method_combo.view().minimumWidth() >= widest_method_label
        assert method_combo.width() <= method_combo.maximumWidth()
        assert (
            method_combo.sizePolicy().horizontalPolicy()
            == QtWidgets.QSizePolicy.Policy.Expanding
        )

        for combo in enum_combos:
            assert (
                combo.sizeAdjustPolicy()
                == QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            widest_enum_label = max(
                combo.fontMetrics().horizontalAdvance(str(combo.itemText(index)))
                for index in range(combo.count())
            )
            assert combo.maximumWidth() == QtWidgets.QWIDGETSIZE_MAX
            assert combo.view().minimumWidth() >= widest_enum_label
            assert (
                combo.sizePolicy().horizontalPolicy()
                == QtWidgets.QSizePolicy.Policy.Expanding
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
        assert len(non_conf_double_spinboxes) == 1
        correction_spinbox = next(
            spinbox for spinbox in non_conf_double_spinboxes if spinbox.minimum() == 0
        )
        correction_spinbox.lineEdit().setText("-1")
        correction_spinbox.interpretText()
        assert correction_spinbox.value() == 0.5

        digit_spinboxes = specs[0].parameter_grp_box.findChildren(QtWidgets.QSpinBox)
        assert len(digit_spinboxes) == 1
        digit_spinbox = digit_spinboxes[0]
        digit_spinbox.lineEdit().setText("-5")
        digit_spinbox.interpretText()
        assert digit_spinbox.minimum() == 0
        assert digit_spinbox.value() == 2

        parameter_labels = [
            label
            for label in specs[0].parameter_grp_box.findChildren(QtWidgets.QLabel)
            if str(label.text())
            in {
                "Random-Effects method",
                "Inference method",
                "Correction factor target",
                "Confidence level",
                "Decimal places",
                "Correction factor",
            }
        ]
        assert len(parameter_labels) == 6
        for label in parameter_labels:
            assert label.minimumWidth() <= label.sizeHint().width()
            assert label.maximumWidth() >= label.sizeHint().width()

        assert specs[0].current_param_vals["rm.method"] == "DL"
        assert specs[0].current_param_vals["inference.method"] == "z"
        assert specs[0].current_param_vals["to"] == "only0"
        assert specs[0].current_param_vals["conf.level"] == 95.0
        assert specs[0].current_param_vals["digits"] == 2
        assert specs[0].current_param_vals["adjust"] == 0.5
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_method_parameters_dialog_normalizes_missing_parameter_metadata(monkeypatch):
    from PyQt6 import QtWidgets

    app, window = automation.start_automation()
    main_window = sys.modules["rc_metastudio.main_window"]
    r_bridge = sys.modules["rc_metastudio.r_bridge"]

    params = {
        "conf.level": "float",
        "adjust": "float",
        "digits": "int",
    }
    defaults = {
        "conf.level": 95.0,
        "adjust": 0.5,
        "digits": 2,
    }

    monkeypatch.setattr(
        r_bridge,
        "get_available_methods",
        lambda **kwargs: {"Binary Random-Effects": "binary.random"},
        raising=False,
    )
    monkeypatch.setattr(
        r_bridge,
        "get_params",
        lambda method: (
            dict(params),
            dict(defaults),
            ["conf.level", "adjust", "digits"],
            {},
        ),
        raising=False,
    )
    monkeypatch.setattr(
        r_bridge,
        "get_method_description",
        lambda method: "Random-effects analysis",
        raising=False,
    )
    monkeypatch.setattr(
        r_bridge,
        "dataset_to_simple_binary_r_object",
        lambda model, **kwargs: None,
        raising=False,
    )

    try:
        assert window.open(_sample_project_path("amino.rcms")) is True

        window.action_go.trigger()
        specs = window.findChildren(
            main_window.analysis_setup_dialog.AnalysisSetupDialog
        )
        assert len(specs) == 1

        labels = {
            str(label.text())
            for label in specs[0].parameter_grp_box.findChildren(QtWidgets.QLabel)
        }
        assert "Confidence Level" in labels
        assert "Correction Factor" in labels
        assert "Decimal Places" in labels
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_method_parameters_dialog_stays_stable_when_method_description_changes(
    monkeypatch,
):
    from PyQt6 import QtCore, QtWidgets

    app, window = automation.start_automation()
    main_window = sys.modules["rc_metastudio.main_window"]
    r_bridge = sys.modules["rc_metastudio.r_bridge"]

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
            {"rm.method": "DL", "conf.level": 95.0, "digits": 2},
            ["rm.method", "conf.level", "digits"],
        ),
        "binary.fixed.mh": (
            {"to": ["only0", "all"], "conf.level": "float", "digits": "float"},
            {"to": "only0", "conf.level": 95.0, "digits": 2},
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
            "pretty.name": "Decimal places",
            "description": "Decimal places for displayed estimates and intervals; p-values use at least 3",
        },
    }

    monkeypatch.setattr(
        r_bridge,
        "get_available_methods",
        lambda **kwargs: dict(method_map),
        raising=False,
    )

    def get_params(method):
        method_params, defaults, var_order = params[method]
        return dict(method_params), dict(defaults), list(var_order), pretty_names

    monkeypatch.setattr(r_bridge, "get_params", get_params, raising=False)
    monkeypatch.setattr(
        r_bridge,
        "get_method_description",
        lambda method: descriptions[method],
        raising=False,
    )
    monkeypatch.setattr(
        r_bridge,
        "dataset_to_simple_binary_r_object",
        lambda model, **kwargs: None,
        raising=False,
    )

    try:
        assert window.open(_sample_project_path("amino.rcms")) is True

        window.action_go.trigger()
        specs = window.findChildren(
            main_window.analysis_setup_dialog.AnalysisSetupDialog
        )
        assert len(specs) == 1
        specs = specs[0]
        specs.show()
        app.processEvents()

        stable_width = specs.width()
        stable_height = specs.height()
        assert _window_archetype(specs) == "transactional"
        assert (
            specs.layout().sizeConstraint()
            == QtWidgets.QLayout.SizeConstraint.SetMinimumSize
        )
        assert specs.maximumSize() == QtCore.QSize(16777215, 16777215)
        assert (
            specs.sizePolicy().horizontalPolicy()
            == QtWidgets.QSizePolicy.Policy.Preferred
        )
        assert (
            specs.sizePolicy().verticalPolicy()
            == QtWidgets.QSizePolicy.Policy.Preferred
        )
        assert specs.isSizeGripEnabled() is False

        specs.resize(stable_width + 300, stable_height + 200)
        app.processEvents()
        assert specs.width() == stable_width + 300
        assert specs.height() == stable_height + 200
        stable_width = specs.width()
        stable_height = specs.height()

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
        assert (
            specs.parameter_grp_box.layout().alignment()
            & QtCore.Qt.AlignmentFlag.AlignTop
        ) == QtCore.Qt.AlignmentFlag.AlignTop

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
            assert value_control.maximumWidth() == QtWidgets.QWIDGETSIZE_MAX
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_required_advanced_analysis_actions_open_real_gui_dialogs(monkeypatch):

    shown = []

    class MetaRegDialog(object):
        def __init__(self, model, analysis_type=None, parent=None, **_kwargs):
            assert analysis_type == "meta-regression"
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
        app, window = automation.start_automation()
        main_window = sys.modules["rc_metastudio.main_window"]
        monkeypatch.setattr(
            main_window.analysis_setup_dialog, "AnalysisSetupDialog", MetaRegDialog
        )
        monkeypatch.setattr(
            main_window.subgroup_analysis_dialog,
            "SubgroupAnalysisDialog",
            SubgroupDialog,
        )

        try:
            assert window.open(_sample_project_path(name)) is True
            covariate_values = {
                study.name: index
                for index, study in enumerate(window.model.dataset.studies)
            }
            group_values = {
                study.name: "A" if index % 2 else "B"
                for index, study in enumerate(window.model.dataset.studies)
            }
            window.model.add_covariate("dose", "continuous", covariate_values)
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


def test_meta_regression_uses_shared_method_covariates_and_plots_dialog(monkeypatch):

    app, window = automation.start_automation()
    built = []
    shown = []

    class SharedSpecsDialog(object):
        def show(self):
            shown.append(self)

    def build_specs(**kwargs):
        built.append(kwargs)
        return SharedSpecsDialog()

    monkeypatch.setattr(window, "_build_analysis_specs_dialog", build_specs)
    try:
        window.meta_reg()

        assert built == [
            {
                "analysis_type": "meta-regression",
                "confidence_level": window.model.get_confidence_level(),
            }
        ]
        assert len(shown) == 1
        assert isinstance(shown[0], SharedSpecsDialog)
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_diagnostic_meta_regression_requests_joint_metrics(monkeypatch):
    app, window = automation.start_automation()
    built = []

    class SharedSpecsDialog(object):
        def show(self):
            pass

    def build_specs(**kwargs):
        built.append(kwargs)
        return SharedSpecsDialog()

    monkeypatch.setattr(window, "_build_analysis_specs_dialog", build_specs)
    try:
        assert window.open(_sample_project_path("lymph.rcms")) is True
        window.meta_reg()

        assert built == [
            {
                "analysis_type": "meta-regression",
                "confidence_level": window.model.get_confidence_level(),
                "diagnostic_metrics": ["sens", "spec"],
            }
        ]
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_meta_regression_action_stays_disabled_without_covariates_when_data_are_enabled():

    app, window = automation.start_automation()

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


def test_diagnostic_metric_dialog_fits_checkbox_group_labels():
    from rc_metastudio import diagnostic_metrics_dialog

    app, window = automation.start_automation()
    form = None

    try:
        assert window.open(_sample_project_path("lymph.rcms")) is True

        form = diagnostic_metrics_dialog.DiagnosticMetricsDialog(
            window.model, parent=window
        )
        form.show()
        app.processEvents()
        required(form.layout(), "diagnostic metrics layout").activate()

        assert form.metrics_grp_box.height() >= form.metrics_grp_box.sizeHint().height()
        assert form.height() >= form.sizeHint().height()
    finally:
        if form is not None:
            form.close()
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_advanced_analysis_actions_require_dataset_readiness_and_covariates():

    app, window = automation.start_automation()

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

    app, window = automation.start_automation()

    try:
        assert window.open(_sample_project_path("amino.rcms")) is True
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
    from rc_metastudio import subgroup_analysis_dialog

    app, window = automation.start_automation()
    warnings = []
    calls = []

    monkeypatch.setattr(
        subgroup_analysis_dialog.QMessageBox,
        "warning",
        lambda *args: warnings.append(args),
    )
    monkeypatch.setattr(
        window,
        "meta_subgroup",
        lambda selected_covariate: calls.append(selected_covariate),
    )

    try:
        window._add_new_covariate("dose", "continuous")
        form = subgroup_analysis_dialog.SubgroupAnalysisDialog(
            window.model, parent=window
        )

        assert form.covariate_combo_box.count() == 0
        assert (
            required(
                form.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok),
                "ok button",
            ).isEnabled()
            is False
        )

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


def test_subgroup_covariate_dialog_constructs_with_factor_covariate():
    from rc_metastudio import subgroup_analysis_dialog

    app, window = automation.start_automation()
    try:
        assert window.open(_sample_project_path("amino.rcms")) is True
        group_values = {
            study.name: "north" if index % 2 else "south"
            for index, study in enumerate(window.model.dataset.studies)
        }
        window.model.add_covariate("region", "factor", group_values)

        form = subgroup_analysis_dialog.SubgroupAnalysisDialog(
            window.model, parent=window
        )

        assert str(form.windowTitle()) == "Select Covariate"
        assert [
            str(form.covariate_combo_box.itemText(index))
            for index in range(form.covariate_combo_box.count())
        ] == ["region"]
    finally:
        window.current_data_unsaved = False
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_sequential_analysis_results_use_results_window(monkeypatch):

    app, window = automation.start_automation()
    main_window = sys.modules["rc_metastudio.main_window"]
    shown = []
    results = _analysis_result(
        {
            "texts": {"Cumulative Summary": "Binary Random-Effects Model"},
            "images": {"Cumulative Forest Plot": "forest.png"},
            "plot_capabilities": {
                "Cumulative Forest Plot": _plot_capability(
                    editable=False, styleable=False, regenerator="none"
                ),
            },
        }
    )

    class ResultDialog(object):
        def __init__(self, result, parent=None):
            shown.append((result, parent))

        def show(self):
            shown.append("shown")

    monkeypatch.setattr(main_window.results_window, "ResultsWindow", ResultDialog)

    try:
        window.analysis(results)

        assert shown == [(results, window), "shown"]
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_analysis_opens_results_window_maximized_and_fits_svg_plot(tmp_path):
    from rc_metastudio import results_window
    from rc_metastudio import settings

    QtCore.QSettings().remove(settings.RESULTS_WORKSPACE_GROUP)

    plot_path = tmp_path / "forest.svg"
    plot_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="800">'
        '<rect width="1600" height="800" fill="white"/>'
        "</svg>",
        encoding="utf-8",
    )
    app, window = automation.start_automation()
    try:
        window.analysis(
            _analysis_result(
                {
                    "texts": {},
                    "images": {"Forest Plot": str(plot_path)},
                    "image_order": ["Forest Plot"],
                    "plot_capabilities": {
                        "Forest Plot": _plot_capability(editable=False),
                    },
                }
            )
        )
        app.processEvents()
        app.processEvents()

        result_windows = window.findChildren(results_window.ResultsWindow)
        assert len(result_windows) == 1
        result_window = result_windows[0]
        assert result_window.isVisible()
        assert result_window.isMaximized()
        plot_item = next(
            item
            for item in result_window.scene.items()
            if isinstance(item, results_window._svg_item_class())
        )
        viewport_width = _viewport_width(result_window.graphics_view)
        assert plot_item.sceneBoundingRect().width() >= viewport_width * 0.9
        assert plot_item.sceneBoundingRect().width() <= viewport_width
    finally:
        for result_window in window.findChildren(results_window.ResultsWindow):
            result_window.close()
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_results_window_renders_summary_text_and_plot_navigation(tmp_path):
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    plot_path = tmp_path / "forest.png"
    image = results_window.QImage(80, 40, results_window.QImage.Format.Format_RGB32)
    image.fill(results_window.Qt.GlobalColor.white)
    assert image.save(str(plot_path), "PNG")

    window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {
                    "Summary": "Binary Random-Effects Model\n\nEstimate Lower bound Upper bound"
                },
                "images": {"Forest Plot": str(plot_path)},
                "image_var_names": {"Forest Plot": "forest_plot"},
                "image_params_paths": {"Forest Plot": str(tmp_path / "forest_params")},
                "image_order": ["Forest Plot"],
                "plot_capabilities": {"Forest Plot": _plot_capability()},
            }
        )
    )

    try:
        nav_titles = [
            required(window.nav_tree.topLevelItem(index), "navigation item").text(0)
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
        pixmap_item = next(
            item
            for item in window.scene.items()
            if isinstance(item, results_window.QGraphicsPixmapItem)
        )
        assert pixmap_item.pixmap().width() <= image.width()
        assert window.graphics_view.scene() is window.scene
    finally:
        window.close()
        app.processEvents()


def test_results_window_refits_svg_plots_and_reflows_sections_on_resize(tmp_path):
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    plot_paths = {}
    for name in ("forest", "cumulative"):
        plot_path = tmp_path / (name + ".svg")
        plot_path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
            '<rect width="400" height="200" fill="white"/>'
            "</svg>",
            encoding="utf-8",
        )
        plot_paths[name] = str(plot_path)

    reference = "Responsive plot reference"
    window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {"References": reference},
                "images": {
                    "Forest Plot": plot_paths["forest"],
                    "Cumulative Forest Plot": plot_paths["cumulative"],
                },
                "image_order": ["Forest Plot", "Cumulative Forest Plot"],
                "plot_capabilities": {
                    "Forest Plot": _plot_capability(editable=False),
                    "Cumulative Forest Plot": _plot_capability(
                        plot_kind="cumulative_forest", editable=False
                    ),
                },
            }
        )
    )

    try:
        window.resize(1200, 800)
        window.show()
        app.processEvents()
        app.processEvents()
        app.processEvents()

        svg_items = sorted(
            (
                item
                for item in window.scene.items()
                if isinstance(item, results_window._svg_item_class())
            ),
            key=lambda item: item.scenePos().y(),
        )
        text_items = {
            item.toPlainText(): item
            for item in window.scene.items()
            if isinstance(item, results_window.QGraphicsTextItem)
        }

        def assert_sections_are_separated():
            assert (
                text_items["Cumulative Forest Plot"].sceneBoundingRect().top()
                - svg_items[0].sceneBoundingRect().bottom()
                >= results_window.SECTION_SPACING
            )
            assert (
                text_items["References"].sceneBoundingRect().top()
                - svg_items[1].sceneBoundingRect().bottom()
                >= results_window.SECTION_SPACING
            )

        def assert_plot_fills_viewport(plot_item):
            plot_width = plot_item.sceneBoundingRect().width()
            assert plot_width >= _viewport_width(window.graphics_view) * 0.9
            assert plot_width <= _viewport_width(window.graphics_view)

        assert len(svg_items) == 2
        first_width = svg_items[0].sceneBoundingRect().width()
        first_height = svg_items[0].sceneBoundingRect().height()
        assert_plot_fills_viewport(svg_items[0])
        assert first_width / first_height == pytest.approx(2.0)
        assert_sections_are_separated()

        window.resize(1600, 800)
        app.processEvents()
        app.processEvents()

        second_width = svg_items[0].sceneBoundingRect().width()
        second_height = svg_items[0].sceneBoundingRect().height()
        assert second_width > first_width
        assert_plot_fills_viewport(svg_items[0])
        assert second_width / second_height == pytest.approx(2.0)
        assert svg_items[0].scale() <= 4.0
        assert_sections_are_separated()

        window.resize(3000, 800)
        app.processEvents()
        app.processEvents()

        assert svg_items[0].scale() == pytest.approx(4.0)
        assert svg_items[0].sceneBoundingRect().width() == pytest.approx(1600)
        assert_sections_are_separated()

        splitter_width = window.results_nav_splitter.width()
        window.results_nav_splitter.setSizes([splitter_width - 100, 100])
        window.results_nav_splitter.splitterMoved.emit(0, 0)
        app.processEvents()

        narrow_viewport_width = _viewport_width(window.graphics_view)
        assert svg_items[0].sceneBoundingRect().width() <= narrow_viewport_width
        assert_sections_are_separated()
    finally:
        window.close()
        app.processEvents()


def test_results_window_refits_svg_after_viewport_geometry_settles(tmp_path):
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    plot_path = tmp_path / "forest.svg"
    plot_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="800">'
        '<rect width="1600" height="800" fill="white"/>'
        "</svg>",
        encoding="utf-8",
    )
    window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {},
                "images": {"Forest Plot": str(plot_path)},
                "image_order": ["Forest Plot"],
                "plot_capabilities": {
                    "Forest Plot": _plot_capability(editable=False),
                },
            }
        )
    )

    try:
        window.resize(700, 500)
        window.show()
        for _ in range(3):
            app.processEvents()
        plot_item = next(
            item
            for item in window.scene.items()
            if isinstance(item, results_window._svg_item_class())
        )
        initial_width = plot_item.sceneBoundingRect().width()
        initial_window_width = window.width()
        initial_viewport_width = _viewport_width(window.graphics_view)
        assert initial_width >= initial_viewport_width * 0.9
        assert initial_width <= initial_viewport_width

        settled_width = initial_window_width - 200
        window.resize(settled_width, window.height())
        for _ in range(3):
            app.processEvents()

        viewport_width = _viewport_width(window.graphics_view)
        assert viewport_width < initial_width
        available_width = viewport_width - window.x_coord - results_window.padding
        assert plot_item.sceneBoundingRect().width() == pytest.approx(available_width)

        shrunken_width = plot_item.sceneBoundingRect().width()
        window.resize(initial_window_width, window.height())
        for _ in range(3):
            app.processEvents()

        grown_viewport_width = _viewport_width(window.graphics_view)
        grown_available_width = (
            grown_viewport_width - window.x_coord - results_window.padding
        )
        assert plot_item.sceneBoundingRect().width() > shrunken_width
        assert plot_item.sceneBoundingRect().width() == pytest.approx(
            grown_available_width
        )
    finally:
        window.close()
        for _ in range(3):
            app.processEvents()


def test_results_window_refits_raster_fallback_from_original_source(tmp_path):
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    plot_path = tmp_path / "legacy-plot.png"
    image = results_window.QImage(1600, 800, results_window.QImage.Format.Format_ARGB32)
    image.fill(0xFFFFFFFF)
    assert image.save(str(plot_path), "PNG")
    window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {},
                "images": {"Legacy Plot": str(plot_path)},
                "image_order": ["Legacy Plot"],
                "plot_capabilities": {
                    "Legacy Plot": _plot_capability(
                        plot_kind="other",
                        editable=False,
                        styleable=False,
                        regenerator="none",
                    ),
                },
            }
        )
    )

    try:
        window.resize(700, 500)
        window.show()
        for _ in range(3):
            app.processEvents()
        plot_item = next(
            item
            for item in window.scene.items()
            if isinstance(item, results_window.QGraphicsPixmapItem)
        )
        initial_width = plot_item.sceneBoundingRect().width()
        initial_window_width = window.width()
        initial_available_width = (
            _viewport_width(window.graphics_view)
            - window.x_coord
            - results_window.padding
        )
        assert initial_width == pytest.approx(initial_available_width, abs=5)

        window.resize(initial_window_width - 200, window.height())
        for _ in range(3):
            app.processEvents()
        shrunken_width = plot_item.sceneBoundingRect().width()
        shrunken_available_width = (
            _viewport_width(window.graphics_view)
            - window.x_coord
            - results_window.padding
        )
        assert shrunken_width < initial_width
        assert shrunken_width == pytest.approx(shrunken_available_width, abs=5)

        window.resize(initial_window_width, window.height())
        app.processEvents()
        assert plot_item.sceneBoundingRect().width() == pytest.approx(
            initial_width, abs=5
        )
        source_pixmap = cast(QtGui.QPixmap, getattr(plot_item, "source_pixmap"))
        assert source_pixmap.width() == 1600
        assert source_pixmap.height() == 800
    finally:
        window.close()
        app.processEvents()


def test_results_window_refits_svg_plot_after_in_place_regenerate(tmp_path):
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    plot_path = tmp_path / "forest.svg"

    def write_svg(width, height):
        plot_path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">'
            '<rect width="%d" height="%d" fill="white"/>'
            "</svg>" % (width, height, width, height),
            encoding="utf-8",
        )

    write_svg(400, 200)
    window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {
                    "Summary": "Meta-analysis summary.",
                    "Weights": "Study weights remain readable after the plot.",
                },
                "images": {"Forest Plot": str(plot_path)},
                "image_order": ["Forest Plot"],
                "plot_capabilities": {
                    "Forest Plot": _plot_capability(editable=False),
                },
            }
        )
    )

    try:
        window.resize(1200, 800)
        window.show()
        app.processEvents()
        app.processEvents()
        plot_item = next(
            item
            for item in window.scene.items()
            if isinstance(item, results_window._svg_item_class())
        )
        initial_width = plot_item.sceneBoundingRect().width()
        weights_title = next(
            item
            for item in window.scene.items()
            if isinstance(item, QtWidgets.QGraphicsTextItem)
            and "Weights" in item.toPlainText()
        )
        initial_weights_y = weights_title.scenePos().y()
        viewport_width = _viewport_width(window.graphics_view)
        assert initial_width >= viewport_width * 0.9
        assert initial_width <= viewport_width

        write_svg(800, 400)
        artifact = window.create_plot_artifact("Forest Plot", str(plot_path))
        window._refresh_plot_item(plot_item, artifact, str(plot_path))
        app.processEvents()
        app.processEvents()

        refreshed_width = plot_item.sceneBoundingRect().width()
        refreshed_height = plot_item.sceneBoundingRect().height()
        refreshed_viewport_width = _viewport_width(window.graphics_view)
        assert refreshed_width >= refreshed_viewport_width * 0.9
        assert refreshed_width <= refreshed_viewport_width
        assert refreshed_width / refreshed_height == pytest.approx(2.0)
        assert (
            weights_title.sceneBoundingRect().top()
            >= plot_item.sceneBoundingRect().bottom()
        )

        write_svg(400, 800)
        window._refresh_plot_item(plot_item, artifact, str(plot_path))
        app.processEvents()

        assert (
            weights_title.sceneBoundingRect().top()
            >= plot_item.sceneBoundingRect().bottom()
        )

        write_svg(400, 100)
        window._refresh_plot_item(plot_item, artifact, str(plot_path))
        app.processEvents()

        assert (
            weights_title.sceneBoundingRect().top()
            >= plot_item.sceneBoundingRect().bottom()
        )
        assert weights_title.scenePos().y() < initial_weights_y

        fresh_window = results_window.ResultsWindow(
            _analysis_result(
                {
                    "texts": {
                        "Summary": "Meta-analysis summary.",
                        "Weights": "Study weights remain readable after the plot.",
                    },
                    "images": {"Forest Plot": str(plot_path)},
                    "image_order": ["Forest Plot"],
                    "plot_capabilities": {
                        "Forest Plot": _plot_capability(editable=False),
                    },
                }
            )
        )
        try:
            fresh_window.resize(1200, 800)
            fresh_window.show()
            app.processEvents()
            fresh_weights_title = next(
                item
                for item in fresh_window.scene.items()
                if isinstance(item, QtWidgets.QGraphicsTextItem)
                and item.toPlainText() == "Weights"
            )
            assert weights_title.scenePos().y() == pytest.approx(
                fresh_weights_title.scenePos().y()
            )
        finally:
            fresh_window.close()
            app.processEvents()
    finally:
        window.close()
        app.processEvents()


def test_results_window_reflows_sections_after_raster_plot_regenerate(tmp_path):
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    plot_path = tmp_path / "forest.png"

    def write_plot(width, height):
        image = results_window.QImage(
            width, height, results_window.QImage.Format.Format_ARGB32
        )
        image.fill(0xFFFFFFFF)
        assert image.save(str(plot_path))

    write_plot(400, 200)
    window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {
                    "Summary": "Meta-analysis summary.",
                    "Weights": "Study weights remain readable after the plot.",
                },
                "images": {"Forest Plot": str(plot_path)},
                "image_order": ["Forest Plot"],
                "plot_capabilities": {
                    "Forest Plot": _plot_capability(editable=False),
                },
            }
        )
    )

    try:
        window.resize(1200, 800)
        window.show()
        app.processEvents()
        plot_item = next(
            item
            for item in window.scene.items()
            if isinstance(item, QtWidgets.QGraphicsPixmapItem)
        )
        weights_title = next(
            item
            for item in window.scene.items()
            if isinstance(item, QtWidgets.QGraphicsTextItem)
            and item.toPlainText() == "Weights"
        )

        write_plot(400, 800)
        artifact = window.create_plot_artifact("Forest Plot", str(plot_path))
        window._refresh_plot_item(plot_item, artifact, str(plot_path))
        app.processEvents()

        assert (
            weights_title.sceneBoundingRect().top()
            - plot_item.sceneBoundingRect().bottom()
            >= results_window.SECTION_SPACING
        )
    finally:
        window.close()
        app.processEvents()


def test_results_window_places_references_after_images_and_wraps_them(tmp_path):
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    plot_path = tmp_path / "forest.png"
    image = results_window.QImage(80, 40, results_window.QImage.Format.Format_RGB32)
    image.fill(results_window.Qt.GlobalColor.white)
    assert image.save(str(plot_path), "PNG")

    long_reference = (
        "1. Random-effects meta-analysis: DerSimonian, R., & Laird, N. (1986). "
        "Meta-analysis in clinical trials. Controlled Clinical Trials, 7(3), "
        "177-188. doi:10.1016/0197-2456(86)90046-2."
    )
    window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {
                    "Summary": "Binary Random-Effects Model",
                    "References": long_reference,
                },
                "images": {"Forest Plot": str(plot_path)},
                "image_var_names": {"Forest Plot": "forest_plot"},
                "image_params_paths": {"Forest Plot": str(tmp_path / "forest_params")},
                "image_order": ["Forest Plot"],
                "plot_capabilities": {"Forest Plot": _plot_capability()},
            }
        )
    )

    try:
        window.show()
        app.processEvents()

        nav_titles = [
            required(window.nav_tree.topLevelItem(index), "navigation item").text(0)
            for index in range(window.nav_tree.topLevelItemCount())
        ]
        assert nav_titles == ["Meta-Analysis Summary", "Forest Plot", "References"]

        sections = {
            item.toPlainText(): item
            for item in window.scene.items()
            if isinstance(item, results_window.QGraphicsTextItem)
        }
        reference_item = sections[long_reference]
        assert (
            required(reference_item.document(), "reference document")
            .defaultTextOption()
            .wrapMode()
            == results_window.QTextOption.WrapMode.WordWrap
        )
    finally:
        window.close()
        app.processEvents()


def test_results_window_separates_tall_text_sections():
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    tall_section = "\n".join(
        "Study %02d  0.123  0.456  0.789" % index for index in range(1, 40)
    )
    window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {
                    "Within-study parameters": tall_section,
                    "Odds Ratio Summary": "Diagnostic Random-Effects Model\n\nEstimate Lower bound Upper bound",
                },
                "images": {},
            }
        )
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
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    popups = []

    class FakeEvent(object):
        def __init__(self):
            self.accepted = False

        def screenPos(self):
            return QtCore.QPoint(10, 20)

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
        _analysis_result(
            {
                "texts": {"Summary": "Model Results\nEstimate  Lower bound"},
                "images": {},
            }
        )
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
        text_item = text_items[0]
        text_item.contextMenuEvent(
            cast(QtWidgets.QGraphicsSceneContextMenuEvent, first_event)
        )
        text_item.contextMenuEvent(
            cast(QtWidgets.QGraphicsSceneContextMenuEvent, second_event)
        )

        assert first_event.accepted is True
        assert second_event.accepted is True
        assert popups == [
            (
                QtCore.QPoint(10, 20),
                ["Select All", "Copy"],
            )
        ]

        current_menu = required(FakeMenu.current, "fake context menu")
        current_menu.aboutToHide.emit()
        text_item.contextMenuEvent(
            cast(QtWidgets.QGraphicsSceneContextMenuEvent, FakeEvent())
        )
        assert len(popups) == 2
        required(FakeMenu.current, "fake context menu").aboutToHide.emit()
    finally:
        window.close()
        app.processEvents()


def test_results_window_figure_context_menus_offer_edit_for_regenerable_forest_plots(
    monkeypatch,
):
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    popups = []

    class FakeEvent(object):
        def __init__(self):
            self.accepted = False

        def screenPos(self):
            return QtCore.QPoint(10, 20)

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
        _analysis_result(
            {
                "texts": {},
                "images": {},
            }
        )
    )

    try:
        menu_cases = [
            ("plot.data", "Forest Plot", "forest", True, "forest"),
            (
                "plot.data",
                "Cumulative Forest Plot",
                "cumulative_forest",
                True,
                "forest",
            ),
            (
                "plot.data",
                "Leave-one-out Forest plot",
                "leave_one_out_forest",
                True,
                "forest",
            ),
            ("plot.data", "Subgroup Forest Plot", "subgroup_forest", True, "forest"),
            ("plot.data", "Subgroups Forest Plot", "subgroup_forest", True, "forest"),
            ("plot.data", "Sensitivity Forest Plot", "forest", True, "forest"),
            ("plot.data", "Specificity Forest Plot", "forest", True, "forest"),
            (
                "plot.data",
                "Negative Likelihood Ratio Forest Plot",
                "forest",
                True,
                "forest",
            ),
            (
                "plot.data",
                "Positive Likelihood Ratio Forest Plot",
                "forest",
                True,
                "forest",
            ),
            ("plot.data", "Regression Plot", "regression", True, "regression"),
            ("plot.data", "A title without a plot hint", "forest", True, "forest"),
            ("plot.data", "Forest Plot", "other", False, "none"),
            (None, "Forest Plot", "forest", False, "forest"),
        ]

        for params_path, title, plot_kind, editable, regenerator in menu_cases:
            event = FakeEvent()
            artifact = results_window.PlotArtifact(
                title,
                "missing.png",
                _plot_capability(
                    plot_kind=plot_kind,
                    editable=editable,
                    styleable=plot_kind not in ("other", "roc", "sroc"),
                    regenerator=regenerator,
                ),
                params_path=params_path,
            )
            handler = window._make_context_menu(artifact, plot_item=None)
            handler(cast(QtWidgets.QGraphicsSceneContextMenuEvent, event))
            assert event.accepted is True
            required(FakeMenu.current, "fake context menu").aboutToHide.emit()
            expected_actions = [
                "Save PDF Image As",
                "Save PNG Image As",
                "Save TIFF Image As",
                "Save SVG Image As",
            ]
            if editable:
                expected_actions.insert(0, "Edit Plot")
            if params_path is None:
                expected_actions = ["Save PNG Image As"]
            assert popups[-1] == (QtCore.QPoint(10, 20), expected_actions)
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize(
    ("title", "plot_kind"),
    (
        ("Cumulative Forest Plot", "cumulative_forest"),
        ("Leave-one-out Forest Plot", "leave_one_out_forest"),
        ("Subgroup Forest Plot", "subgroup_forest"),
    ),
)
def test_results_window_applies_forest_edits_to_selected_variant_artifact(
    tmp_path, monkeypatch, title, plot_kind
):
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    params_path = str(tmp_path / plot_kind)
    image_path = tmp_path / (plot_kind + ".svg")
    image_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
        '<rect width="400" height="200" fill="white"/>'
        "</svg>",
        encoding="utf-8",
    )
    calls = []

    class FakeSignal(object):
        def __init__(self):
            self.callback = None

        def connect(self, callback):
            self.callback = callback

        def emit(self):
            required(self.callback, "fake signal callback")()

    class FakeDialog(object):
        def __init__(self, plot_params, dialog_image_path, parent=None):
            calls.append(("dialog", plot_params, dialog_image_path))
            self.applied = FakeSignal()

        def plot_params(self):
            return {"fp_outpath": str(image_path)}

        def exec(self):
            self.applied.emit()

    window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {},
                "images": {title: str(image_path)},
                "image_params_paths": {title: params_path},
                "image_order": [title],
                "plot_capabilities": {title: _plot_capability(plot_kind=plot_kind)},
            }
        )
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "load_vars_for_plot",
        lambda path, return_params_dict=False: {"fp_col1_str": "Study"},
        raising=False,
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "update_plot_params",
        lambda *a, **k: None,
        raising=False,
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "regenerate_plot_data",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "generate_forest_plot",
        lambda path: image_path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="800">'
            '<rect width="400" height="800" fill="white"/>'
            "</svg>",
            encoding="utf-8",
        ),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "write_out_plot_data",
        lambda path: None,
        raising=False,
    )
    monkeypatch.setattr(results_window, "EditPlotDialog", FakeDialog)

    try:
        window.resize(1200, 800)
        window.show()
        app.processEvents()
        plot_item = next(
            item
            for item in window.scene.items()
            if isinstance(item, results_window._svg_item_class())
        )
        artifact = window.create_plot_artifact(
            title, str(image_path), params_path=params_path
        )

        window.edit_plot(artifact, plot_item)
        app.processEvents()

        assert calls == [("dialog", {"fp_col1_str": "Study"}, str(image_path))]
        assert (
            plot_item.sceneBoundingRect().width()
            / plot_item.sceneBoundingRect().height()
            == pytest.approx(0.5)
        )
    finally:
        window.close()
        app.processEvents()


def test_results_window_save_handler_regenerates_cumulative_forest_as_single_panel(
    tmp_path, monkeypatch
):
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    calls = []
    window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {},
                "images": {},
            }
        )
    )
    artifact = results_window.PlotArtifact(
        "Cumulative Forest Plot",
        str(tmp_path / "forest.png"),
        _plot_capability(plot_kind="cumulative_forest", editable=False),
        params_path=str(tmp_path / "forest_params"),
    )

    monkeypatch.setattr(
        results_window.r_bridge,
        "load_in_r",
        lambda path: calls.append(("load", path)),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "generate_forest_plot",
        lambda path: calls.append(("forest", path)),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(tmp_path / "saved.pdf"), ""),
    )

    try:
        window.save_image_as(artifact, format="pdf")

        assert calls == [
            ("load", "%s.plotdata" % artifact.params_path),
            ("forest", str(tmp_path / "saved.pdf")),
        ]
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize("extension", ["pdf", "png", "tiff", "svg"])
def test_results_window_save_handler_accepts_backend_export_formats(
    tmp_path, monkeypatch, extension
):
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    calls = []
    window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {},
                "images": {},
            }
        )
    )
    artifact = results_window.PlotArtifact(
        "Forest Plot",
        str(tmp_path / "forest.png"),
        _plot_capability(),
        params_path=str(tmp_path / "forest_params"),
    )

    monkeypatch.setattr(
        results_window.r_bridge,
        "load_in_r",
        lambda path: calls.append(("load", path)),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "generate_forest_plot",
        lambda path: calls.append(("forest", path)),
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
            ("forest", str(tmp_path / ("saved.%s" % extension))),
        ]
    finally:
        window.close()
        app.processEvents()


def test_results_window_save_handler_preserves_requested_format_when_extension_is_omitted(
    tmp_path, monkeypatch
):
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    calls = []
    window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {},
                "images": {},
            }
        )
    )
    artifact = results_window.PlotArtifact(
        "Forest Plot",
        str(tmp_path / "forest.png"),
        _plot_capability(),
        params_path=str(tmp_path / "forest_params"),
    )

    monkeypatch.setattr(
        results_window.r_bridge,
        "load_in_r",
        lambda path: calls.append(("load", path)),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "generate_forest_plot",
        lambda path: calls.append(("forest", path)),
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
            ("forest", str(tmp_path / "saved.svg")),
        ]
    finally:
        window.close()
        app.processEvents()


def test_edit_plot_dialog_round_trips_style_and_appearance_params(monkeypatch):
    from rc_metastudio import r_backend

    r_backend.install_r_backend()

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = plot_editor_dialog.EditPlotDialog(
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


def test_shared_plot_options_surface_uses_default_arm_labels():
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio.plot_defaults import apply_default_forest_arm_labels

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    analysis_dialog = QtWidgets.QDialog()
    analysis_form = Ui_AnalysisSetupDialog()
    analysis_form.setupUi(analysis_dialog)
    apply_default_forest_arm_labels(analysis_form)
    edit_dialog = plot_editor_dialog.EditPlotDialog({}, "forest.png")

    try:
        assert analysis_form.col3_str_edit.text() == "Intervention"
        assert analysis_form.col4_str_edit.text() == "Control"
        assert edit_dialog.col3_str_edit.text() == "Intervention"
        assert edit_dialog.col4_str_edit.text() == "Control"
    finally:
        edit_dialog.close()
        analysis_dialog.close()
        app.processEvents()


def test_plot_text_inputs_enforce_publication_readability_limit():
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio.plot_text import PLOT_TEXT_INPUT_LIMIT

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = plot_editor_dialog.EditPlotDialog({}, "forest.png")

    try:
        fields = (
            dialog.col1_str_edit,
            dialog.col2_str_edit,
            dialog.col3_str_edit,
            dialog.col4_str_edit,
            dialog.x_lbl_le,
        )
        for field in fields:
            assert field.maxLength() == PLOT_TEXT_INPUT_LIMIT
            assert "publication readability" in field.toolTip()
            field.setText("x" * (PLOT_TEXT_INPUT_LIMIT + 20))
            assert len(field.text()) == PLOT_TEXT_INPUT_LIMIT
        assert dialog.plot_lb_le.maxLength() > PLOT_TEXT_INPUT_LIMIT
        assert dialog.plot_ub_le.maxLength() > PLOT_TEXT_INPUT_LIMIT
        assert dialog.x_ticks_le.maxLength() > PLOT_TEXT_INPUT_LIMIT
    finally:
        dialog.close()
        app.processEvents()


def test_sroc_plot_editor_round_trips_reitsma_style_contract():
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = plot_editor_dialog.EditPlotDialog(
        {
            "fp_xlabel": "False positive rate",
            "fp_ylabel": "Sensitivity",
            "fp_marker_area": "sample-size",
            "fp_show_labels": True,
            "fp_extrapolate": True,
            "fp_curve_color": "#123456",
            "fp_confidence_color": "#234567",
            "fp_prediction_color": "#345678",
            "fp_curve_lty": 2,
            "fp_confidence_lty": 3,
            "fp_prediction_lty": 4,
            "fp_text_cex": 1.2,
            "fp_show_confidence": False,
            "fp_show_prediction": True,
            "fp_show_summary": False,
            "fp_show_auc": False,
            "fp_show_legend": True,
            "fp_plot_lb": "0.05",
            "fp_plot_ub": "0.95",
            "fp_xticks": "0.05, 0.5, 0.95",
            "fp_sroc_plot_lb": "0.1",
            "fp_sroc_plot_ub": "0.9",
            "fp_sroc_yticks": "0.1, 0.5, 0.9",
        },
        "sroc.svg",
        plot_type="sroc",
    )
    try:
        params = dialog.plot_params()
        assert params["fp_ylabel"] == "Sensitivity"
        assert params["fp_marker_area"] == "sample-size"
        assert params["fp_show_labels"] is True
        assert params["fp_extrapolate"] is True
        assert params["fp_curve_color"] == "#123456"
        assert params["fp_confidence_lty"] == 3
        assert params["fp_text_cex"] == pytest.approx(1.2)
        assert params["fp_show_confidence"] is False
        assert params["fp_show_summary"] is False
        assert params["fp_show_legend"] is True
        assert params["fp_show_marker_legend"] is True
        assert params["fp_plot_lb"] == "0.05"
        assert params["fp_plot_ub"] == "0.95"
        assert params["fp_xticks"] == "0.05, 0.5, 0.95"
        assert params["fp_sroc_plot_lb"] == "0.1"
        assert params["fp_sroc_plot_ub"] == "0.9"
        assert params["fp_sroc_yticks"] == "0.1, 0.5, 0.9"
        assert dialog.sroc_show_marker_legend.isEnabled()
    finally:
        dialog.close()
        app.processEvents()


def test_sroc_plot_editor_limits_marker_legend_to_sample_size_scaling():
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import plot_editor_dialog

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = plot_editor_dialog.EditPlotDialog(
        {"fp_marker_area": "uniform", "fp_show_marker_legend": False},
        "sroc.svg",
        plot_type="sroc",
    )
    try:
        assert dialog.plot_params()["fp_show_marker_legend"] is False
        assert not dialog.sroc_show_marker_legend.isEnabled()
        assert not dialog.sroc_show_marker_legend.isChecked()
        dialog.sroc_marker_area.setCurrentIndex(1)
        assert dialog.sroc_show_marker_legend.isEnabled()
        assert not dialog.sroc_show_marker_legend.isChecked()
        assert dialog.plot_params()["fp_show_marker_legend"] is False
        dialog.sroc_show_marker_legend.setChecked(True)
        assert dialog.plot_params()["fp_show_marker_legend"] is True
        dialog.sroc_show_marker_legend.setChecked(False)
        assert dialog.plot_params()["fp_show_marker_legend"] is False
        dialog.sroc_marker_area.setCurrentIndex(0)
        assert not dialog.sroc_show_marker_legend.isEnabled()
        assert not dialog.sroc_show_marker_legend.isChecked()
    finally:
        dialog.close()
        app.processEvents()


def test_edit_plot_dialog_flags_truncated_legacy_plot_text():
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio.plot_text import PLOT_TEXT_INPUT_LIMIT

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = plot_editor_dialog.EditPlotDialog(
        {"fp_col1_str": "x" * (PLOT_TEXT_INPUT_LIMIT + 20)}, "forest.png"
    )
    try:
        assert len(dialog.col1_str_edit.text()) == PLOT_TEXT_INPUT_LIMIT
        assert dialog.col1_str_edit.property("plotTextWasTruncated") is True
        assert "original is retained" in dialog.col1_str_edit.toolTip()
        assert dialog.plot_params()["fp_col1_str"] == "x" * (PLOT_TEXT_INPUT_LIMIT + 20)
        dialog.col1_str_edit.setFocus()
        dialog.col1_str_edit.selectAll()
        key_clicks(dialog.col1_str_edit, "replacement")
        assert dialog.plot_params()["fp_col1_str"] == "replacement"
    finally:
        dialog.close()
        app.processEvents()


def test_edit_plot_dialog_apply_stays_open_and_ok_applies_and_closes():
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = plot_editor_dialog.EditPlotDialog({}, "forest.png")
    applied = []
    dialog.applied.connect(lambda: applied.append(True))

    try:
        dialog.show()
        app.processEvents()
        apply_button = dialog.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Apply
        )
        ok_button = dialog.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
        )

        assert apply_button is not None
        assert ok_button is not None
        apply_button.click()
        app.processEvents()

        assert applied == [True]
        assert dialog.isVisible() is True

        ok_button.click()
        app.processEvents()

        assert applied == [True, True]
        assert dialog.result() == QtWidgets.QDialog.DialogCode.Accepted
        assert dialog.isVisible() is False
    finally:
        dialog.close()
        app.processEvents()


def test_edit_regression_plot_dialog_shows_only_bubble_options():
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = plot_editor_dialog.EditPlotDialog(
        {
            "bp_style": "bmj",
            "bp_accent_color": "#123456",
            "bp_point_size_multiplier": 1.5,
            "bp_xlabel": "Latitude",
            "bp_plot_lb": "0.25",
            "bp_plot_ub": "4",
            "bp_xticks": "0.5, 1, 2",
            "bp_show_regression_line": True,
            "bp_show_confidence_band": False,
            "bp_show_prediction_interval": True,
            "bp_show_legend": True,
        },
        "regression.png",
        plot_type="regression",
    )

    try:
        assert dialog.groupBox.isHidden()
        assert dialog.default_panel.isHidden()
        assert dialog.show_summary_line.isHidden()
        assert not dialog.regression_group.isHidden()

        params = dialog.plot_params()

        assert params == {
            "bp_style": "bmj",
            "bp_accent_color": "#123456",
            "bp_point_size_multiplier": 1.5,
            "bp_xlabel": "Latitude",
            "bp_plot_lb": "0.25",
            "bp_plot_ub": "4",
            "bp_xticks": "0.5, 1, 2",
            "bp_show_regression_line": True,
            "bp_show_confidence_band": False,
            "bp_show_prediction_interval": True,
            "bp_show_legend": True,
            "bp_outpath": "regression.png",
        }
    finally:
        dialog.close()
        app.processEvents()


def test_apply_regression_plot_edits_rebuilds_and_redraws_bubble_plot(
    tmp_path, monkeypatch
):
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    calls = []
    params_path = str(tmp_path / "regression_params")
    image_path = str(tmp_path / "regression.png")
    display_path = str(tmp_path / "regression.display.svg")
    Path(display_path).write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
        '<rect width="400" height="200" fill="white"/>'
        "</svg>",
        encoding="utf-8",
    )

    class FakeDialog(object):
        def plot_params(self):
            return {
                "bp_style": "revman",
                "bp_show_confidence_band": False,
                "bp_outpath": image_path,
                "bp_display_path": display_path,
            }

    monkeypatch.setattr(
        results_window.r_bridge,
        "update_plot_params",
        lambda params, write_them_out=False, outpath=None: calls.append(
            ("update", params, write_them_out, outpath)
        ),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "regenerate_regression_plot_data",
        lambda: calls.append(("regenerate",)),
        raising=False,
    )

    def generate_reg_plot(path):
        calls.append(("draw", path))
        height = 300 + 100 * sum(call[0] == "draw" for call in calls)
        Path(display_path).write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="%d">'
            '<rect width="400" height="%d" fill="white"/>'
            "</svg>" % (height, height),
            encoding="utf-8",
        )

    monkeypatch.setattr(
        results_window.r_bridge,
        "generate_reg_plot",
        generate_reg_plot,
        raising=False,
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "write_out_plot_data",
        lambda path: calls.append(("write", path)),
        raising=False,
    )

    window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {},
                "images": {"Regression Plot": image_path},
                "display_images": {"Regression Plot": display_path},
                "image_params_paths": {"Regression Plot": params_path},
                "image_order": ["Regression Plot"],
                "plot_capabilities": {
                    "Regression Plot": _plot_capability(
                        plot_kind="regression", regenerator="regression"
                    )
                },
            }
        )
    )
    try:
        window.resize(1200, 800)
        window.show()
        app.processEvents()
        plot_item = next(
            item
            for item in window.scene.items()
            if isinstance(item, results_window._svg_item_class())
        )
        artifact = window.create_plot_artifact(
            "Regression Plot", image_path, params_path=params_path
        )

        window._apply_regression_plot_edits(FakeDialog(), artifact, plot_item)
        window._apply_regression_plot_edits(FakeDialog(), artifact, plot_item)
        app.processEvents()

        assert artifact.display_image_path == display_path
        assert sum(call[0] == "update" for call in calls) == 2
        assert sum(call[0] == "draw" for call in calls) == 2
        assert all(
            call[1]["bp_display_path"] == display_path
            for call in calls
            if call[0] == "update"
        )
        assert plot_item.boundingRect().height() == pytest.approx(500)

        initial_width = plot_item.sceneBoundingRect().width()
        window_width = window.width()
        window.resize(window_width - 200, window.height())
        app.processEvents()
        assert plot_item.sceneBoundingRect().width() < initial_width
        window.resize(window_width, window.height())
        app.processEvents()
        assert plot_item.sceneBoundingRect().width() > initial_width - 5
    finally:
        window.close()
        app.processEvents()


def test_pre_run_plots_tab_exports_style_and_appearance_params(monkeypatch):
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import analysis_setup_dialog

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    class PlotDefaultsDialog(object):
        current_param_vals: dict[str, object]
        style_cbo: QtWidgets.QComboBox
        show_1: QtWidgets.QCheckBox
        col1_str_edit: QtWidgets.QLineEdit
        show_2: QtWidgets.QCheckBox
        col2_str_edit: QtWidgets.QLineEdit
        show_3: QtWidgets.QCheckBox
        col3_str_edit: QtWidgets.QLineEdit
        show_4: QtWidgets.QCheckBox
        col4_str_edit: QtWidgets.QLineEdit
        x_lbl_le: QtWidgets.QLineEdit
        image_path: QtWidgets.QLineEdit
        plot_lb_le: QtWidgets.QLineEdit
        plot_ub_le: QtWidgets.QLineEdit
        x_ticks_le: QtWidgets.QLineEdit
        show_summary_line: QtWidgets.QCheckBox
        show_raw_counts: QtWidgets.QCheckBox
        show_headers: QtWidgets.QCheckBox
        show_annotation: QtWidgets.QCheckBox
        accent_color: QtWidgets.QLineEdit
        point_size_multiplier: QtWidgets.QDoubleSpinBox

    form = PlotDefaultsDialog()
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
    form.x_lbl_le = QtWidgets.QLineEdit("[default]")
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

    analysis_setup_dialog.add_plot_params(form)

    assert form.current_param_vals["fp_style"] == "revman"
    assert form.current_param_vals["fp_accent_color"] == "#123456"
    assert form.current_param_vals["fp_point_size_multiplier"] == 1.5
    assert form.current_param_vals["fp_show_raw_counts"] is False
    assert form.current_param_vals["fp_show_headers"] is False
    assert form.current_param_vals["fp_show_annotation"] is False
    assert form.current_param_vals["fp_xlabel"] is None
    assert form.current_param_vals["fp_col3_str"] == "Treatment"
    assert form.current_param_vals["fp_col4_str"] == "Control"
    display_path = cast(str, form.current_param_vals["fp_display_path"])
    assert display_path.endswith(".display.svg")
    assert Path(display_path).parent != Path(".")
    app.processEvents()


def test_meta_regression_pre_run_plot_options_use_bubble_parameter_contract():
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import analysis_setup_dialog

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    class RegressionPlotDialog(object):
        analysis_type = "meta-regression"
        current_param_vals: dict[str, object]
        style_cbo: QtWidgets.QComboBox
        accent_color: QtWidgets.QLineEdit
        point_size_multiplier: QtWidgets.QDoubleSpinBox
        x_lbl_le: QtWidgets.QLineEdit
        x_ticks_le: QtWidgets.QLineEdit
        plot_lb_le: QtWidgets.QLineEdit
        plot_ub_le: QtWidgets.QLineEdit
        image_path: QtWidgets.QLineEdit
        show_regression_line: QtWidgets.QCheckBox
        show_confidence_band: QtWidgets.QCheckBox
        show_prediction_interval: QtWidgets.QCheckBox
        show_legend: QtWidgets.QCheckBox

    form = RegressionPlotDialog()
    form.current_param_vals = {}
    form.style_cbo = QtWidgets.QComboBox()
    form.style_cbo.addItems(["Default (metafor)", "RevMan", "BMJ"])
    form.style_cbo.setCurrentText("BMJ")
    form.accent_color = QtWidgets.QLineEdit("#654321")
    form.point_size_multiplier = QtWidgets.QDoubleSpinBox()
    form.point_size_multiplier.setValue(1.25)
    form.x_lbl_le = QtWidgets.QLineEdit("Latitude")
    form.x_ticks_le = QtWidgets.QLineEdit("-20, 0, 20")
    form.plot_lb_le = QtWidgets.QLineEdit("-30")
    form.plot_ub_le = QtWidgets.QLineEdit("30")
    form.image_path = QtWidgets.QLineEdit("regression.png")
    form.show_regression_line = QtWidgets.QCheckBox()
    form.show_regression_line.setChecked(True)
    form.show_confidence_band = QtWidgets.QCheckBox()
    form.show_confidence_band.setChecked(False)
    form.show_prediction_interval = QtWidgets.QCheckBox()
    form.show_prediction_interval.setChecked(True)
    form.show_legend = QtWidgets.QCheckBox()
    form.show_legend.setChecked(True)

    analysis_setup_dialog.add_plot_params(form)

    display_path = cast(str, form.current_param_vals.pop("bp_display_path"))
    assert display_path.endswith(".display.svg")
    assert Path(display_path).parent != Path(".")
    assert form.current_param_vals == {
        "bp_style": "bmj",
        "bp_accent_color": "#654321",
        "bp_point_size_multiplier": 1.25,
        "bp_xlabel": "Latitude",
        "bp_xticks": "-20, 0, 20",
        "bp_plot_lb": "-30",
        "bp_plot_ub": "30",
        "bp_outpath": "regression.png",
        "bp_show_regression_line": True,
        "bp_show_confidence_band": False,
        "bp_show_prediction_interval": True,
        "bp_show_legend": True,
    }
    app.processEvents()


def test_meta_regression_acceptance_passes_all_dialog_choices_to_adapter(monkeypatch):
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import analysis_setup_dialog
    from rc_metastudio import meta_globals

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    calls = []

    class Covariate(object):
        name = "latitude"
        data_type = meta_globals.CONTINUOUS

    class Study(object):
        def __init__(self, study_id):
            self.id = study_id

    studies = [Study(1), Study(2)]
    covariate = Covariate()

    class Dataset(object):
        def get_covariate_values(self, name, ids_for_keys=False):
            assert name == "latitude"
            assert ids_for_keys is True
            return {1: -10.0, 2: 20.0}

    class Model(object):
        current_effect = "OR"
        dataset = Dataset()

        def get_studies(self, only_if_included=False):
            assert only_if_included is True
            return studies

    class Parent(object):
        def analysis(self, result):
            calls.append(("analysis", result))

    class Form(QtWidgets.QWidget):
        analysis_type = "meta-regression"
        data_type = "binary"
        confidence_level = 95.0
        model = Model()
        current_param_vals = {
            "rm.method": "SJ",
            "conf.level": 90.0,
            "digits": 4,
        }
        _parent = Parent()
        fixed_effects_radio: QtWidgets.QRadioButton
        style_cbo: QtWidgets.QComboBox
        accent_color: QtWidgets.QLineEdit
        point_size_multiplier: QtWidgets.QDoubleSpinBox
        x_lbl_le: QtWidgets.QLineEdit
        x_ticks_le: QtWidgets.QLineEdit
        plot_lb_le: QtWidgets.QLineEdit
        plot_ub_le: QtWidgets.QLineEdit
        image_path: QtWidgets.QLineEdit
        show_regression_line: QtWidgets.QCheckBox
        show_confidence_band: QtWidgets.QCheckBox
        show_prediction_interval: QtWidgets.QCheckBox
        show_legend: QtWidgets.QCheckBox
        plot_tab: QtWidgets.QWidget
        selected: list[object]

        def _selected_covariates(self):
            return [covariate]

        def parent(self):
            return self._parent

        def accept(self):
            calls.append(("accepted",))

        def _deliver_result(self, result):
            self._parent.analysis(result)

        def _run_analysis(
            self, operation, failure_message, string_result_is_failure=False
        ):
            result = operation()
            if string_result_is_failure and isinstance(result, str):
                raise RuntimeError(failure_message % result)
            self._deliver_result(result)
            self.done(QtWidgets.QDialog.DialogCode.Accepted.value)

        def done(self, result):
            assert result == QtWidgets.QDialog.DialogCode.Accepted.value
            self.accept()

    form = Form()
    form.fixed_effects_radio = QtWidgets.QRadioButton()
    form.fixed_effects_radio.setChecked(True)
    form.style_cbo = QtWidgets.QComboBox()
    form.style_cbo.addItems(["Default (metafor)", "RevMan", "BMJ"])
    form.style_cbo.setCurrentText("RevMan")
    form.accent_color = QtWidgets.QLineEdit("#123456")
    form.point_size_multiplier = QtWidgets.QDoubleSpinBox()
    form.point_size_multiplier.setValue(1.5)
    form.x_lbl_le = QtWidgets.QLineEdit("Latitude")
    form.x_ticks_le = QtWidgets.QLineEdit("-10, 0, 10")
    form.plot_lb_le = QtWidgets.QLineEdit("-20")
    form.plot_ub_le = QtWidgets.QLineEdit("20")
    form.image_path = QtWidgets.QLineEdit("bubble.png")
    form.show_regression_line = QtWidgets.QCheckBox()
    form.show_regression_line.setChecked(True)
    form.show_confidence_band = QtWidgets.QCheckBox()
    form.show_confidence_band.setChecked(False)
    form.show_prediction_interval = QtWidgets.QCheckBox()
    form.show_prediction_interval.setChecked(True)
    form.show_legend = QtWidgets.QCheckBox()
    form.show_legend.setChecked(True)

    monkeypatch.setattr(
        analysis_setup_dialog.r_bridge,
        "dataset_to_simple_binary_r_object",
        lambda *args, **kwargs: calls.append(("prepare", args, kwargs)),
        raising=False,
    )

    def run_meta_regression(*args, **kwargs):
        calls.append(("run", args, kwargs))
        return {"texts": {"Summary": "meta-regression"}, "images": {}}

    monkeypatch.setattr(
        analysis_setup_dialog.r_bridge,
        "run_meta_regression",
        run_meta_regression,
        raising=False,
    )

    analysis_setup_dialog.AnalysisSetupDialog.run_meta_regression(
        cast(analysis_setup_dialog.AnalysisSetupDialog, form)
    )

    assert calls[0][0] == "prepare"
    assert calls[1][0] == "run"
    assert calls[1][1][1:4] == (studies, [covariate], "OR")
    assert calls[1][2]["fixed_effects"] is True
    assert calls[1][2]["confidence_level"] == 90.0
    assert calls[1][2]["params"]["rm.method"] == "SJ"
    assert calls[1][2]["params"]["digits"] == 4
    assert calls[1][2]["params"]["bp_style"] == "revman"
    assert calls[1][2]["params"]["bp_outpath"] == "bubble.png"
    assert calls[-2][0] == "analysis"
    assert calls[-1] == ("accepted",)
    app.processEvents()


def test_meta_regression_enables_plots_only_for_one_continuous_covariate():
    from rc_metastudio import analysis_setup_dialog
    from rc_metastudio import meta_globals

    class Covariate(object):
        def __init__(self, data_type):
            self.data_type = data_type

    class Form(object):
        is_meta_regression = True
        selected: list[object]
        plot_tab: QtWidgets.QWidget

        def _selected_covariates(self):
            return self.selected

    form = Form()
    form.plot_tab = QtWidgets.QWidget()
    form.selected = [Covariate(meta_globals.CONTINUOUS)]

    analysis_setup_dialog.AnalysisSetupDialog._update_meta_regression_plot_availability(
        cast(analysis_setup_dialog.AnalysisSetupDialog, form)
    )
    assert form.plot_tab.isEnabled()

    form.selected.append(Covariate(meta_globals.CONTINUOUS))
    analysis_setup_dialog.AnalysisSetupDialog._update_meta_regression_plot_availability(
        cast(analysis_setup_dialog.AnalysisSetupDialog, form)
    )
    assert not form.plot_tab.isEnabled()
    assert "exactly one continuous covariate" in form.plot_tab.toolTip()


@pytest.mark.parametrize(
    ("method_label", "method_name"),
    [
        ("Reitsma bivariate model", "diagnostic.reitsma"),
    ],
)
def test_diagnostic_forest_methods_enable_pre_run_plots_tab(
    method_label, method_name, monkeypatch
):
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import analysis_setup_dialog

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    r_bridge = sys.modules["rc_metastudio.r_bridge"]

    class DiagnosticModel(object):
        current_effect = "Sens"

        def get_current_outcome_type(self):
            return "diagnostic"

        def included_studies_have_raw_data(self):
            return True

    monkeypatch.setattr(
        r_bridge,
        "get_available_methods",
        lambda **kwargs: {method_label: method_name},
        raising=False,
    )
    monkeypatch.setattr(
        r_bridge, "get_params", lambda method: ({}, {}, None, {}), raising=False
    )
    monkeypatch.setattr(
        r_bridge,
        "get_method_description",
        lambda method: "Diagnostic analysis with forest plot output",
        raising=False,
    )
    monkeypatch.setattr(
        r_bridge,
        "get_analysis_plot_capabilities",
        lambda data_type, method, workflow="standard": [
            _plot_capability(plot_kind="forest")
        ],
        raising=False,
    )
    monkeypatch.setattr(
        r_bridge,
        "dataset_to_simple_diagnostic_r_object",
        lambda model, **kwargs: None,
        raising=False,
    )
    specs = None
    try:
        specs = analysis_setup_dialog.AnalysisSetupDialog(
            DiagnosticModel(),
            diagnostic_metrics=["sens", "spec"],
            confidence_level=95.0,
        )

        assert specs.current_method == method_name
        assert specs.plot_tab.isEnabled()
    finally:
        if specs is not None:
            specs.close()
        app.processEvents()


def test_edit_plot_apply_regenerates_plot_without_accepting_dialog(
    tmp_path, monkeypatch
):
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    calls = []
    params_path = str(tmp_path / "forest_params")
    png_path = str(tmp_path / "forest.png")
    display_path = str(tmp_path / "forest.display.svg")
    out_path = str(tmp_path / "edited.png")
    Path(display_path).write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
        '<rect width="400" height="200" fill="white"/>'
        "</svg>",
        encoding="utf-8",
    )

    class FakeSignal(object):
        def __init__(self):
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)

        def emit(self):
            for callback in self._callbacks:
                callback()

    class FakeEditPlotDialog(object):
        def __init__(self, plot_params, image_path, parent=None):
            self.applied = FakeSignal()
            self._params = {
                "fp_col1_str": "EDIT TEST HEADING",
                "fp_outpath": out_path,
                "fp_display_path": display_path,
            }
            calls.append(("dialog", plot_params, image_path, parent is not None))

        def exec(self):
            self.applied.emit()
            return QtWidgets.QDialog.DialogCode.Rejected

        def plot_params(self):
            return dict(self._params)

    monkeypatch.setattr(
        results_window.r_bridge,
        "load_vars_for_plot",
        lambda path, return_params_dict=False: {"fp_col1_str": "Study"},
        raising=False,
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "update_plot_params",
        lambda updated_params, write_them_out=False, outpath=None: calls.append(
            ("update", updated_params, write_them_out, outpath)
        ),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "regenerate_plot_data",
        lambda: calls.append(("regenerate",)),
        raising=False,
    )

    def generate_forest_plot(outpath):
        calls.append(("generate", outpath))
        height = 300 + 100 * sum(call[0] == "generate" for call in calls)
        Path(display_path).write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="%d">'
            '<rect width="400" height="%d" fill="white"/>'
            "</svg>" % (height, height),
            encoding="utf-8",
        )

    monkeypatch.setattr(
        results_window.r_bridge,
        "generate_forest_plot",
        generate_forest_plot,
        raising=False,
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "write_out_plot_data",
        lambda path: calls.append(("write", path)),
        raising=False,
    )
    monkeypatch.setattr(
        results_window,
        "EditPlotDialog",
        FakeEditPlotDialog,
    )

    window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {"References": "Edited plot reference"},
                "images": {"Forest Plot": png_path},
                "display_images": {"Forest Plot": display_path},
                "image_params_paths": {"Forest Plot": params_path},
                "image_order": ["Forest Plot"],
                "plot_capabilities": {"Forest Plot": _plot_capability()},
            }
        )
    )

    try:
        window.resize(1200, 800)
        window.show()
        app.processEvents()
        plot_item = next(
            item
            for item in window.scene.items()
            if isinstance(item, results_window._svg_item_class())
        )
        references_title = next(
            item
            for item in window.scene.items()
            if isinstance(item, results_window.QGraphicsTextItem)
            and item.toPlainText() == "References"
        )
        original_reference_top = references_title.sceneBoundingRect().top()

        artifact = window.create_plot_artifact(
            "Forest Plot", png_path, params_path=params_path
        )
        window.edit_plot(artifact, plot_item=plot_item)
        window.edit_plot(artifact, plot_item=plot_item)
        app.processEvents()

        assert artifact.display_image_path == display_path
        assert sum(call[0] == "update" for call in calls) == 2
        assert sum(call[0] == "generate" for call in calls) == 2
        assert all(
            call[1]["fp_display_path"] == display_path
            for call in calls
            if call[0] == "update"
        )
        assert plot_item.boundingRect().height() == pytest.approx(500)
        assert references_title.sceneBoundingRect().top() > original_reference_top
        assert (
            references_title.sceneBoundingRect().top()
            - plot_item.sceneBoundingRect().bottom()
            >= results_window.SECTION_SPACING
        )

        initial_width = plot_item.sceneBoundingRect().width()
        window_width = window.width()
        window.resize(window_width - 200, window.height())
        app.processEvents()
        assert plot_item.sceneBoundingRect().width() < initial_width
        window.resize(window_width, window.height())
        app.processEvents()
        assert plot_item.sceneBoundingRect().width() > initial_width - 5
    finally:
        window.close()
        app.processEvents()


def test_results_window_ignores_missing_image_order_entries():
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {"Summary": "Reitsma summary"},
                "images": {},
                "image_order": ["Summary ROC"],
            }
        )
    )

    try:
        nav_titles = [
            required(window.nav_tree.topLevelItem(index), "navigation item").text(0)
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
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    from rc_metastudio import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    plot_paths = {}
    for name in ["forest", "roc"]:
        plot_path = tmp_path / ("%s.png" % name)
        image = results_window.QImage(80, 40, results_window.QImage.Format.Format_RGB32)
        image.fill(results_window.Qt.GlobalColor.white)
        assert image.save(str(plot_path), "PNG")
        plot_paths[name] = str(plot_path)

    standard_window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {
                    "Weights": "Study weights",
                    "Summary": "Binary Random-Effects Model",
                },
                "images": {"Forest Plot": plot_paths["forest"]},
                "image_order": ["Forest Plot"],
                "plot_capabilities": {"Forest Plot": _plot_capability(editable=False)},
            }
        )
    )
    try:
        nav_titles = [
            required(
                standard_window.nav_tree.topLevelItem(index), "navigation item"
            ).text(0)
            for index in range(standard_window.nav_tree.topLevelItemCount())
        ]

        assert nav_titles == ["Meta-Analysis Summary", "Forest Plot", "Weights"]
        assert standard_window.nav_tree.minimumWidth() == 0
        assert not standard_window.results_nav_splitter.childrenCollapsible()
    finally:
        standard_window.close()
        app.processEvents()

    reitsma_window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {
                    "Summary operating point": "point",
                    "Marginal prediction": "prediction",
                    "Model information": "model",
                },
                "images": {"SROC": plot_paths["roc"]},
                "image_order": ["SROC"],
                "plot_capabilities": {
                    "SROC": _plot_capability(
                        plot_kind="sroc",
                        editable=False,
                        styleable=False,
                        regenerator="none",
                    ),
                },
            }
        )
    )
    try:
        nav_titles = [
            required(reitsma_window.nav_tree.topLevelItem(index), "navigation item").text(
                0
            )
            for index in range(reitsma_window.nav_tree.topLevelItemCount())
        ]

        assert nav_titles == [
            "Summary operating point",
            "Marginal prediction",
            "Model information",
            "Summary ROC Plot",
        ]
    finally:
        reitsma_window.close()
        app.processEvents()


def test_main_window_save_as_round_trips_representative_projects(tmp_path, monkeypatch):

    for name in ["amino.rcms", "continuous.rcms", "lymph.rcms", "meantime.rcms"]:
        app, window = automation.start_automation()
        saved_path = str(tmp_path / name)

        try:
            assert window.open(_sample_project_path(name)) is True
            expected = _dataset_summary(window.model.dataset)
            main_window = sys.modules["rc_metastudio.main_window"]
            monkeypatch.setattr(
                main_window.QFileDialog,
                "getSaveFileName",
                lambda **kwargs: (saved_path, ""),
            )

            window.save_as()
            assert os.path.exists(saved_path)
            assert window.current_data_unsaved is False
            main_window = sys.modules["rc_metastudio.main_window"]
            reopened, _state, _restored_selection = (
                main_window._load_structured_project(saved_path)
            )
            assert _dataset_summary(reopened) == expected
            if name == "meantime.rcms":
                values = [
                    study.covariate_values["treatment group"]
                    for study in reopened.studies
                ]
                assert all(type(value) is str for value in values if value is not None)
        finally:
            window.close()
            app.processEvents()
            os.chdir(REPO_ROOT)


def test_recent_files_persist_through_pyqt6_settings(tmp_path):
    from PyQt6 import QtCore
    from rc_metastudio import settings

    QtCore.QSettings.setPath(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        str(tmp_path),
    )
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
    settings.reset_settings()

    settings.add_file_to_recent_files("first.rcms")
    settings.add_file_to_recent_files("second.rcms")
    settings.load_settings()

    assert settings.get_setting("recent_files") == ["first.rcms", "second.rcms"]


def test_main_window_maximized_state_persists_through_pyqt6_settings(tmp_path):
    from PyQt6 import QtCore, QtWidgets
    from rc_metastudio import settings

    QtCore.QSettings.setPath(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        str(tmp_path),
    )
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
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


def test_welcome_wizard_recent_action_selects_project(monkeypatch):
    from rc_metastudio import main_wizard

    app, window = automation.start_automation()
    opened = []
    monkeypatch.setattr(
        window, "open", lambda file_path=None: opened.append(file_path) or True
    )
    wizard = main_wizard.MainWizard(
        parent=window, recent_datasets=["first.rcms", "second.rcms"]
    )
    try:
        page = cast(
            main_wizard.WelcomePage,
            required(wizard.page(main_wizard.Page_Welcome), "welcome page"),
        )
        menu = required(page.open_recent_btn.menu(), "recent projects menu")
        action = menu.actions()[0]

        page.dataset_selected(action)

        assert wizard.get_wizard_path() == "open"
        assert wizard.get_selected_dataset() == "second.rcms"
        results = wizard.get_results()
        assert results["outcome_info"] is None
        window._handle_wizard_results(results)
        assert opened == ["second.rcms"]
    finally:
        wizard.close()
        window.close()
        app.processEvents()


def test_welcome_wizard_open_existing_selects_project(monkeypatch):
    from rc_metastudio import main_wizard

    app, window = automation.start_automation()
    opened = []
    monkeypatch.setattr(
        window, "open", lambda file_path=None: opened.append(file_path) or True
    )
    wizard = main_wizard.MainWizard(parent=window)
    try:
        page = cast(
            main_wizard.WelcomePage,
            required(wizard.page(main_wizard.Page_Welcome), "welcome page"),
        )
        monkeypatch.setattr(
            main_wizard.QFileDialog,
            "getOpenFileName",
            lambda **kwargs: ("chosen.rcms", ""),
        )

        page.open_dataset()

        assert wizard.get_wizard_path() == "open"
        assert wizard.get_selected_dataset() == "chosen.rcms"
        results = wizard.get_results()
        assert results["outcome_info"] is None
        window._handle_wizard_results(results)
        assert opened == ["chosen.rcms"]

        incomplete_new_dataset = main_wizard.MainWizard(
            parent=window, path="new_dataset"
        )
        try:
            with pytest.raises(RuntimeError, match="dataset information is required"):
                incomplete_new_dataset.get_results()
        finally:
            incomplete_new_dataset.close()
    finally:
        wizard.close()
        window.close()
        app.processEvents()


def test_modal_dialogs_center_over_parent_window():
    from PyQt6 import QtWidgets
    from rc_metastudio import main_wizard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    parent = QtWidgets.QMainWindow()
    parent.setGeometry(40, 80, 900, 620)
    parent.show()
    app.processEvents()

    wizard = main_wizard.MainWizard(parent=parent)
    try:
        wizard.show()
        app.processEvents()
        app.processEvents()

        parent_center = parent.frameGeometry().center()
        wizard_center = wizard.frameGeometry().center()
        assert abs(wizard_center.x() - parent_center.x()) <= 1
        assert abs(wizard_center.y() - parent_center.y()) <= 1
    finally:
        wizard.close()
        parent.close()
        app.processEvents()


def test_startup_wizard_cancel_preserves_loaded_dataset(monkeypatch):
    from rc_metastudio import launch
    from PyQt6 import QtCore, QtWidgets

    main_window = launch._import_main_window()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = main_window.MainWindow()
    sample_project = _sample_project_path("amino.rcms")

    class RejectedWizard(QtCore.QObject):
        finished = QtCore.pyqtSignal(int)

        def __init__(self, *args, **kwargs):
            super().__init__()

        def open(self):
            self.finished.emit(int(QtWidgets.QDialog.DialogCode.Rejected))

    quit_calls = []
    monkeypatch.setattr(main_window.main_wizard, "MainWizard", RejectedWizard)
    monkeypatch.setattr(
        main_window.QApplication, "quit", lambda: quit_calls.append(True)
    )

    try:
        assert window.open(sample_project) is True
        loaded_dataset = window.model.dataset
        loaded_title = loaded_dataset.title
        loaded_studies = [study.name for study in loaded_dataset.studies]

        window.start()
        app.processEvents()

        assert quit_calls == []
        assert window.model.dataset is loaded_dataset
        assert window.model.dataset.title == loaded_title
        assert [study.name for study in window.model.dataset.studies] == loaded_studies
    finally:
        window.close()
        app.processEvents()


def test_startup_wizard_opens_after_event_loop_and_reactivates_main_window(monkeypatch):
    from rc_metastudio import launch
    from PyQt6 import QtCore, QtWidgets

    main_window = launch._import_main_window()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = main_window.MainWindow()
    events = []

    class AsyncWizard(QtCore.QObject):
        finished = QtCore.pyqtSignal(int)

        def __init__(self, *args, **kwargs):
            super().__init__()
            events.append("created")

        def open(self):
            events.append("opened")

        def get_results(self):
            return {
                "path": "open",
                "selected_dataset": "chosen.rcms",
                "outcome_info": None,
            }

        def deleteLater(self):
            events.append("deleted")

    monkeypatch.setattr(main_window.main_wizard, "MainWizard", AsyncWizard)
    monkeypatch.setattr(
        window, "_handle_wizard_results", lambda data: events.append(("handled", data))
    )
    monkeypatch.setattr(window, "show", lambda: events.append("shown"))
    monkeypatch.setattr(window, "raise_", lambda: events.append("raised"))
    monkeypatch.setattr(window, "activateWindow", lambda: events.append("activated"))

    try:
        window.start()
        assert events == []

        app.processEvents()
        assert events == ["created", "opened"]

        window._startup_wizard.finished.emit(int(QtWidgets.QDialog.DialogCode.Accepted))
        assert events[2][0] == "handled"
        assert events[3:] == ["deleted", "shown", "raised", "activated"]
        assert window._startup_wizard is None
    finally:
        window.current_data_unsaved = False
        window.close()
        app.processEvents()


def test_data_type_page_multiline_buttons_fit_icon_and_caption():
    from PyQt6 import QtWidgets
    from rc_metastudio import main_wizard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        wizard.restart()
        wizard.show()
        app.processEvents()

        data_type_page = cast(
            main_wizard.DataTypePage,
            required(wizard.page(main_wizard.Page_DataType), "data type page"),
        )
        multiline_buttons = [
            data_type_page.onearm_single_reg_coef_Button,
            data_type_page.onearm_generic_effect_size_Button,
        ]

        for button in multiline_buttons:
            assert "\n" in button.text()
            assert button.height() >= button.sizeHint().height()
    finally:
        wizard.close()
        app.processEvents()


def test_data_type_page_reflows_buttons_without_horizontal_overflow():
    from PyQt6 import QtWidgets
    from rc_metastudio import main_wizard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        wizard.restart()
        wizard.show()
        app.processEvents()

        data_type_page = cast(
            main_wizard.DataTypePage,
            required(wizard.page(main_wizard.Page_DataType), "data type page"),
        )
        overflow = data_type_page.findChild(QtWidgets.QScrollArea, "pageScrollArea")
        assert (
            required(overflow.horizontalScrollBar(), "overflow scrollbar").maximum()
            == 0
        )
        assert data_type_page.oneArmDataTypesLayout.columnCount() == 2
        assert data_type_page.multiArmDataTypesLayout.columnCount() == 2
    finally:
        wizard.close()
        app.processEvents()


def test_data_type_page_buttons_center_icons_inside_declared_slots():
    from PyQt6 import QtWidgets
    from rc_metastudio import main_wizard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        wizard.restart()
        wizard.show()
        app.processEvents()

        data_type_page = cast(
            main_wizard.DataTypePage,
            required(wizard.page(main_wizard.Page_DataType), "data type page"),
        )
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


def test_new_dataset_wizard_overflow_keeps_diagnostic_choice_reachable():
    from PyQt6 import QtWidgets
    from rc_metastudio import main_wizard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        wizard.restart()
        wizard.show()
        app.processEvents()

        data_type_page = cast(
            main_wizard.DataTypePage,
            required(wizard.page(main_wizard.Page_DataType), "data type page"),
        )
        required(data_type_page.layout(), "data type layout").activate()
        app.processEvents()

        overflow = data_type_page.findChild(QtWidgets.QScrollArea, "pageScrollArea")
        diagnostic_button = data_type_page.diagnostic_Button
        overflow.ensureWidgetVisible(diagnostic_button)
        app.processEvents()
        viewport = required(overflow.viewport(), "data type viewport")
        diagnostic_rect = QtCore.QRect(
            diagnostic_button.mapTo(viewport, QtCore.QPoint()),
            diagnostic_button.size(),
        )
        assert viewport.rect().intersects(diagnostic_rect)
    finally:
        wizard.close()
        app.processEvents()


@pytest.mark.parametrize("path", [None, "new_dataset", "csv_import"])
def test_wizard_uses_modern_style_with_explicit_back_navigation(path):
    from PyQt6 import QtWidgets
    from rc_metastudio import main_wizard

    app = cast(
        QtWidgets.QApplication,
        QtWidgets.QApplication.instance() or QtWidgets.QApplication([]),
    )
    wizard = main_wizard.MainWizard(path=path)
    try:
        assert wizard.wizardStyle() == main_wizard.QWizard.WizardStyle.ModernStyle
        assert wizard.button(main_wizard.QWizard.WizardButton.BackButton) is not None
    finally:
        wizard.close()
        app.processEvents()


def test_wizard_layout_smoke_renders_core_wizard_pages():
    from PyQt6 import QtWidgets

    app = cast(
        QtWidgets.QApplication,
        QtWidgets.QApplication.instance() or QtWidgets.QApplication([]),
    )

    assert automation.start_wizard_layout_smoke() == 0
    assert [
        widget
        for widget in app.topLevelWidgets()
        if widget.isVisible() and widget.__class__.__name__ == "MainWizard"
    ] == []


def test_new_dataset_wizard_pages_fill_body_without_clipping_content():
    from PyQt6 import QtWidgets
    from rc_metastudio import main_wizard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard()
    try:
        wizard.restart()
        wizard.show()
        app.processEvents()

        welcome_page = cast(
            main_wizard.WelcomePage,
            required(wizard.page(main_wizard.Page_Welcome), "welcome page"),
        )
        welcome_page.new_dataset()
        app.processEvents()
        stable_body_width = None
        stable_wizard_width = wizard.width()

        page_sequence = [
            main_wizard.Page_DataType,
            main_wizard.Page_ChooseMetric,
            main_wizard.Page_OutcomeName,
        ]
        cast(
            main_wizard.DataTypePage,
            required(wizard.page(main_wizard.Page_DataType), "data type page"),
        ).twoarm_proportions_Button.click()

        for page_id in page_sequence:
            if wizard.currentId() != page_id:
                wizard.next()
            app.processEvents()

            page = required(wizard.page(page_id), "wizard page")
            layout = page.layout()
            if layout is not None:
                layout.activate()
            app.processEvents()

            parent_widget = required(page.parentWidget(), "wizard page parent")
            page_body_width = parent_widget.contentsRect().width()
            if stable_body_width is None:
                stable_body_width = page_body_width
            assert abs(page_body_width - stable_body_width) <= 4
            assert abs(wizard.width() - stable_wizard_width) <= 4
            assert page.width() >= page_body_width - 4
            overflow = page.findChild(QtWidgets.QScrollArea, "pageScrollArea")
            assert overflow is not None
            assert page.rect().contains(overflow.geometry())
    finally:
        wizard.close()
        app.processEvents()


def test_data_type_page_canonical_form_declares_reflow_and_overflow():
    ui_path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "rc_metastudio"
        / "forms"
        / "data_type_page.ui"
    )
    root = _xml_element(ET.parse(ui_path).getroot(), "widget")

    assert _xml_element(root, "./layout").get("name") == "workflowPageLayout"
    assert root.find(".//widget[@name='pageScrollArea']") is not None
    assert (
        _xml_element(root, ".//layout[@name='oneArmDataTypesLayout']").get("class")
        == "QGridLayout"
    )
    assert (
        _xml_element(root, ".//layout[@name='multiArmDataTypesLayout']").get("class")
        == "QGridLayout"
    )
    assert root.find("./property[@name='minimumSize']") is None
    assert root.find("./property[@name='maximumSize']") is None


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
    from PyQt6 import QtWidgets
    from rc_metastudio import main_wizard
    from rc_metastudio import meta_globals

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        wizard.restart()
        app.processEvents()

        data_type_page = cast(
            main_wizard.DataTypePage,
            required(wizard.page(main_wizard.Page_DataType), "data type page"),
        )
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
    from PyQt6 import QtWidgets
    from rc_metastudio import main_wizard
    from rc_metastudio import meta_globals

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = main_wizard.MainWizard(path="new_dataset")
    try:
        wizard.restart()
        app.processEvents()

        data_type_page = cast(
            main_wizard.DataTypePage,
            required(wizard.page(main_wizard.Page_DataType), "data type page"),
        )
        next_button = wizard.button(main_wizard.QWizard.WizardButton.NextButton)
        assert not required(next_button, "wizard next button").isEnabled()

        data_type_page.twoarm_proportions_Button.click()
        app.processEvents()

        assert data_type_page.isComplete()
        assert required(next_button, "wizard next button").isEnabled()
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

        metric_page = cast(
            main_wizard.ChooseMetricPage,
            required(wizard.page(main_wizard.Page_ChooseMetric), "metric page"),
        )
        assert metric_page.metric_cbo_box.count() == len(
            meta_globals.BINARY_TWO_ARM_METRICS
        )
        assert metric_page.metric_cbo_box.currentData() == "OR"
        assert "(DEFAULT)" in metric_page.metric_cbo_box.currentText()
        assert wizard.get_effect() == "OR"

        wizard.next()
        app.processEvents()
        outcome_page = cast(
            main_wizard.OutcomeNamePage,
            required(wizard.page(main_wizard.Page_OutcomeName), "outcome page"),
        )
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

    app_data = tmp_path / "app-data"
    app_data.mkdir()
    os.chdir(str(app_data))

    app, window = automation.start_automation()
    main_window = sys.modules["rc_metastudio.main_window"]
    from rc_metastudio import settings

    settings.reset_settings()
    calls = []

    def choose_project(**kwargs):
        calls.append(kwargs)
        return ("", "")

    monkeypatch.setattr(main_window.QFileDialog, "getOpenFileName", choose_project)

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
    from PyQt6 import QtWidgets
    from rc_metastudio import main_wizard

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
        page = cast(
            main_wizard.WelcomePage,
            required(wizard.page(main_wizard.Page_Welcome), "welcome page"),
        )
        page.open_dataset()

        _assert_sample_projects_open_directory(calls[0]["directory"])
    finally:
        wizard.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_about_legal_and_welcome_links_show_current_project_information():
    from rc_metastudio import main_wizard

    app, window = automation.start_automation()

    try:
        assert window.action_about_legal.text() == "About/Legal"

        from rc_metastudio import about_legal_dialog

        about_dialogs = []
        original_exec = about_legal_dialog.AboutLegalDialog.exec
        setattr(
            about_legal_dialog.AboutLegalDialog,
            "exec",
            lambda dialog: about_dialogs.append(dialog),
        )
        try:
            window.action_about_legal.trigger()
        finally:
            setattr(about_legal_dialog.AboutLegalDialog, "exec", original_exec)
        about_text = about_dialogs[0].content_scroll_area.toPlainText()
        assert _window_archetype(about_dialogs[0]) == "transactional"
        assert "RC MetaStudio" in about_text
        assert "Ali Salman" in about_text
        assert "GPL-3.0-or-later" in about_text
        assert "without warranty" in about_text.lower()
        assert "original OpenMeta[Analyst] project" in about_text
        assert "NOTICE.md" in about_text
        about_dialogs[0].close()

        wizard = main_wizard.MainWizard()
        welcome = cast(
            main_wizard.WelcomePage,
            required(wizard.page(main_wizard.Page_Welcome), "welcome page"),
        )
        link_text = " ".join(
            [
                welcome.RCMS_onlineLabel.text(),
                welcome.issue_feedback_label.text(),
                welcome.how_to_citeLabel.text(),
            ]
        )
        assert "github.com/AliSalman-et-al/rc-metastudio" in link_text
    finally:
        if "wizard" in locals():
            wizard.close()
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_load_r_libraries_runs_against_explicit_test_bridge():
    # The test bridge is installed explicitly at this narrow integration seam.
    from rc_metastudio import launch
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    assert hasattr(sys.modules["rc_metastudio.r_bridge"], "get_r_library_paths")

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    class _Splash:
        def showMessage(self, message):
            pass

    # Must not raise AttributeError: module 'r_bridge' has no attribute 'get_r_library_paths'
    phases = []
    launch.load_R_libraries(app, _Splash(), phase_callback=phases.append)
    assert phases == [
        "r-library-paths:start",
        "r-library-paths:complete",
        "r-library:metafor:start",
        "r-library:metafor:complete",
        "r-library:RCMetaR:start",
        "r-library:RCMetaR:complete",
        "r-library:grid:start",
        "r-library:grid:complete",
    ]


def test_stub_backend_exposes_data_entry_imputation_methods():
    # Regression for GitHub #48: the maintained PyQt6 path plants a stub r_bridge,
    # and data-entry dialogs call these methods during construction. The no-R
    # stub must expose them, returning a benign "couldn't impute" result rather
    # than crashing.
    from rc_metastudio import r_backend

    r_backend.install_r_backend()
    r_bridge = sys.modules["rc_metastudio.r_bridge"]

    for name in (
        "impute_binary_data",
        "impute_continuous_data",
        "impute_pre_post_continuous_data",
        "impute_diagnostic_data",
        "back_calculate_continuous_data",
    ):
        assert hasattr(r_bridge, name), name

    assert "FAIL" in r_bridge.impute_binary_data({"Ev_A": 1})
    assert r_bridge.impute_continuous_data({"n": 10}, 0.05)["succeeded"] is False
    assert (
        r_bridge.impute_pre_post_continuous_data({"n": 10}, 0.5, 0.05)["succeeded"]
        is False
    )
    assert r_bridge.impute_diagnostic_data({"TP": 1}) == {
        "TP": None,
        "TN": None,
        "FP": None,
        "FN": None,
    }
    assert "FAIL" in r_bridge.back_calculate_continuous_data(
        {"n": 10}, {"n": 12}, {"est": 1.0}, 95.0
    )


def test_data_entry_dialogs_construct_with_stub_backend(monkeypatch):
    # Regression for GitHub #48: opening these dialogs from a study row used to
    # crash when the stubbed r_bridge lacked imputation entry points. With the
    # pure-Python no-R stub they must still construct without a live backend.
    import copy

    app, window = automation.start_automation()
    from rc_metastudio import binary_data_dialog
    from rc_metastudio import continuous_data_dialog
    from rc_metastudio import diagnostic_data_dialog

    monkeypatch.setattr(
        continuous_data_dialog.ContinuousBackCalculationDialog,
        "exec",
        lambda self: False,
    )

    try:
        assert window.open(_sample_project_path("amino.rcms")) is True
        model = window.model
        binary_dialog = binary_data_dialog.BinaryDataDialog(
            copy.deepcopy(model.get_current_analysis_unit_for_study(0)),
            model.current_groups,
            model.get_current_group_comparison(),
            model.current_effect,
            confidence_level=model.get_confidence_level(),
            parent=window.tableView,
        )
        binary_dialog.close()

        assert window.open(_sample_project_path("continuous.rcms")) is True
        model = window.model
        continuous_dialog = continuous_data_dialog.ContinuousDataDialog(
            copy.deepcopy(model.get_current_analysis_unit_for_study(0)),
            model.current_groups,
            model.get_current_group_comparison(),
            model.current_effect,
            confidence_level=model.get_confidence_level(),
            parent=window.tableView,
        )
        continuous_dialog.close()

        assert window.open(_sample_project_path("lymph.rcms")) is True
        model = window.model
        diagnostic_dialog = diagnostic_data_dialog.DiagnosticDataDialog(
            copy.deepcopy(model.get_current_analysis_unit_for_study(0)),
            model.current_groups,
            model.get_current_group_comparison(),
            confidence_level=model.get_confidence_level(),
            parent=window.tableView,
        )
        diagnostic_dialog.close()
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_csv_required_format_table_expands_and_shows_all_rows(monkeypatch):
    from rc_metastudio import main_wizard

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


def test_analysis_dialog_family_declares_migrated_transactional_surfaces(monkeypatch):
    import copy
    from rc_metastudio import binary_data_dialog
    from rc_metastudio import continuous_data_dialog
    from rc_metastudio import diagnostic_data_dialog
    from rc_metastudio import subgroup_analysis_dialog

    app, window = automation.start_automation()
    dialogs = []
    monkeypatch.setattr(
        continuous_data_dialog.ContinuousBackCalculationDialog,
        "exec",
        lambda self: False,
    )

    try:
        assert window.open(_sample_project_path("amino.rcms")) is True
        model = window.model
        covariate_values = {
            study.name: "north" if index % 2 else "south"
            for index, study in enumerate(model.dataset.studies)
        }
        model.add_covariate("region", "factor", covariate_values)
        dialogs.extend(
            [
                subgroup_analysis_dialog.SubgroupAnalysisDialog(model, parent=window),
                binary_data_dialog.BinaryDataDialog(
                    copy.deepcopy(model.get_current_analysis_unit_for_study(0)),
                    model.current_groups,
                    model.get_current_group_comparison(),
                    model.current_effect,
                    confidence_level=model.get_confidence_level(),
                    parent=window.tableView,
                ),
            ]
        )

        assert window.open(_sample_project_path("continuous.rcms")) is True
        model = window.model
        dialogs.append(
            continuous_data_dialog.ContinuousDataDialog(
                copy.deepcopy(model.get_current_analysis_unit_for_study(0)),
                model.current_groups,
                model.get_current_group_comparison(),
                model.current_effect,
                confidence_level=model.get_confidence_level(),
                parent=window.tableView,
            )
        )

        assert window.open(_sample_project_path("lymph.rcms")) is True
        model = window.model
        dialogs.append(
            diagnostic_data_dialog.DiagnosticDataDialog(
                copy.deepcopy(model.get_current_analysis_unit_for_study(0)),
                model.current_groups,
                model.get_current_group_comparison(),
                confidence_level=model.get_confidence_level(),
                parent=window.tableView,
            )
        )

        for dialog in dialogs:
            dialog.show()
            app.processEvents()
            assert _window_archetype(dialog) == "transactional"
            assert dialog.maximumSize() == QtCore.QSize(16777215, 16777215)
    finally:
        for dialog in dialogs:
            dialog.close()
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_add_covariate_dialog_fields_and_buttons_fill_fitted_width():
    from rc_metastudio import add_new_dialogs

    app, window = automation.start_automation()
    dialog = add_new_dialogs.AddCovariateDialog(parent=window)

    try:
        enlarged_font = dialog.font()
        enlarged_font.setPointSize(enlarged_font.pointSize() + 4)
        dialog.setFont(enlarged_font)
        dialog.show()
        app.processEvents()

        assert _window_archetype(dialog) == "transactional"
        assert dialog.layout() is not None
        assert dialog.minimumSize() == dialog.minimumSizeHint()
        assert dialog.maximumSize() == QtCore.QSize(16777215, 16777215)
        assert (
            dialog.covariate_name_le.sizePolicy().horizontalPolicy()
            == QtWidgets.QSizePolicy.Policy.Expanding
        )
        assert dialog.buttonBox.isVisible()
        assert dialog.contentsRect().contains(dialog.buttonBox.geometry().center())
    finally:
        dialog.close()
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_csv_import_wizard_accepts_representative_csv(tmp_path, monkeypatch):
    from rc_metastudio import main_wizard

    csv_path = tmp_path / "studies.csv"
    csv_path.write_text(
        "Study,Year,Tx A events,Tx A total,Tx B events,Tx B total,OR,Lower,Upper,Dose,Region\n"
        "Alpha,2020,1,10,2,12,,,,5.5,North\n"
        "Beta,2021,3,11,4,13,,,,7,South\n"
    )
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
    page = cast(
        main_wizard.CsvImportPage,
        required(wizard.page(main_wizard.Page_CsvImport), "CSV import page"),
    )
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
    from rc_metastudio import main_wizard

    csv_path = tmp_path / "ragged-studies.csv"
    csv_path.write_text(
        "Study,Year,Tx A events,Tx A total,Tx B events,Tx B total\n"
        "Alpha,2020,1,10,2,12\n"
        "Beta,2021,3,11,4\n"
    )
    shown = []
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
    page = cast(
        main_wizard.CsvImportPage,
        required(wizard.page(main_wizard.Page_CsvImport), "CSV import page"),
    )
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
    assert required(page.preview_table.item(1, 5), "preview item").text() == ""
    _assert_compact_table_fits_visible_cells(page.preview_table)
    assert wizard.get_csv_data()["data"][-1] == ["Beta", "2021", "3", "11", "4", ""]


def test_csv_import_wizard_reports_empty_file_as_no_data(tmp_path, monkeypatch):
    from rc_metastudio import main_wizard

    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("")
    shown = []
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
    page = cast(
        main_wizard.CsvImportPage,
        required(wizard.page(main_wizard.Page_CsvImport), "CSV import page"),
    )
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
    from rc_metastudio import main_wizard

    csv_path = tmp_path / "studies.csv"
    csv_path.write_text(
        "Study,Year,Tx A events,Tx A total,Tx B events,Tx B total\n"
        "Alpha,2020,1,10,2,12\n"
    )
    shown = []
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
    page = cast(
        main_wizard.CsvImportPage,
        required(wizard.page(main_wizard.Page_CsvImport), "CSV import page"),
    )
    page.initializePage()
    monkeypatch.setattr(
        main_wizard.QFileDialog,
        "getOpenFileName",
        lambda **kwargs: (str(csv_path), "csv files (*.csv)"),
    )
    monkeypatch.setattr(
        main_wizard.csv_import,
        "parse_csv",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("Year column is missing")
        ),
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
    from PyQt6 import QtWidgets
    from rc_metastudio import main_wizard

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

        page = cast(
            main_wizard.CsvImportPage,
            required(wizard.page(main_wizard.Page_CsvImport), "CSV import page"),
        )
        finish_button = wizard.button(main_wizard.QWizard.WizardButton.FinishButton)
        assert not required(finish_button, "wizard finish button").isEnabled()
        monkeypatch.setattr(
            main_wizard.QFileDialog,
            "getOpenFileName",
            lambda **kwargs: (str(csv_path), "csv files (*.csv)"),
        )

        page._select_file()
        app.processEvents()

        assert page.isComplete()
        assert required(finish_button, "wizard finish button").isEnabled()
    finally:
        wizard.close()
        app.processEvents()


def test_table_paint_roles_do_not_raise_across_all_cells():
    # Exercise paint roles directly because offscreen tests do not invoke them.
    from PyQt6 import QtCore

    paint_roles = [
        QtCore.Qt.ItemDataRole.DisplayRole,
        QtCore.Qt.ItemDataRole.DecorationRole,
        QtCore.Qt.ItemDataRole.BackgroundRole,
        QtCore.Qt.ItemDataRole.ForegroundRole,
        QtCore.Qt.ItemDataRole.FontRole,
        QtCore.Qt.ItemDataRole.TextAlignmentRole,
        QtCore.Qt.ItemDataRole.CheckStateRole,
        QtCore.Qt.ItemDataRole.SizeHintRole,
    ]

    app, window = automation.start_automation()
    try:
        assert window.open(_sample_project_path("amino.rcms")) is True
        model = window.tableView.model()
        for row in range(model.rowCount()):
            for column in range(model.columnCount()):
                index = model.index(row, column)
                for role in paint_roles:
                    model.data(index, role)
        for section in range(model.columnCount()):
            for role in paint_roles:
                model.headerData(section, QtCore.Qt.Orientation.Horizontal, role)
        for section in range(model.rowCount()):
            for role in paint_roles:
                model.headerData(section, QtCore.Qt.Orientation.Vertical, role)
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
        "outcomes": sorted(str(name) for name in dataset.follow_ups_by_outcome.keys()),
    }
