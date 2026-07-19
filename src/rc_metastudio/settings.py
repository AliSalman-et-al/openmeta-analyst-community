# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Application settings and managed analysis workspace paths."""

import os
import sys
import json
import math
import ntpath
import posixpath
from collections.abc import Mapping
from dataclasses import dataclass
from PyQt6 import QtCore, QtGui
import qt_text
from workspace_column_identity import WorkspaceColumnWidthState

QColor = QtGui.QColor
QDir = QtCore.QDir
QSettings = QtCore.QSettings
ANALYSIS_SCRATCH_ENV_VAR = "RCMS_ANALYSIS_SCRATCH_DIR"

##################### HANDLE SETTINGS #####################

MAX_RECENT_FILES = 10
SIGNED_INT32_MIN = -(2**31)
SIGNED_INT32_MAX = 2**31 - 1
APPLICATION_SETTINGS_SCHEMA_KEY = "application_settings/schema_version"
APPLICATION_SETTINGS_SCHEMA_VERSION = 1
LEGACY_MAIN_WINDOW_GROUP = "main_window"
WORKSPACE_LAYOUT_GROUP = "workspace_layout"
WORKSPACE_LAYOUT_SCHEMA_VERSION = 2
MAIN_WORKSPACE_GROUP = WORKSPACE_LAYOUT_GROUP + "/main"
RESULTS_WORKSPACE_GROUP = WORKSPACE_LAYOUT_GROUP + "/results"
EDIT_DATASET_WORKSPACE_GROUP = WORKSPACE_LAYOUT_GROUP + "/edit_dataset"
NETWORK_VIEW_WORKSPACE_GROUP = WORKSPACE_LAYOUT_GROUP + "/network_view"
DEFAULT_RESULTS_SPLITTER_PROPORTIONS = (0.30, 0.70)
DEFAULT_EDIT_DATASET_SPLITTER_PROPORTIONS = (1.0 / 3.0,) * 3
DEFAULT_SETTINGS = {
    "splash": True,
    "digits": 2,
    "recent_files": [],
    # "method_params":{},
}


@dataclass(frozen=True)
class SettingSpec:
    """Portable QSettings field contract."""

    value_type: type
    default: object


SETTING_SPECS = {
    "splash": SettingSpec(bool, True),
    "digits": SettingSpec(int, 2),
    "recent_files": SettingSpec(list, []),
}


@dataclass(frozen=True, eq=False)
class WorkspacePlacement(Mapping):
    """Typed screen-safe placement shared by every Workspace role."""

    frame_geometry: QtCore.QRect | None
    maximized: bool
    full_screen: bool

    _FIELDS = ("frame_geometry", "maximized", "full_screen")

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)

    def __eq__(self, other):
        if isinstance(other, Mapping):
            return dict(self.items()) == dict(other.items())
        return NotImplemented


class WorkspacePaneState(Mapping):
    """Mapping-compatible placement and proportions shared by pane workspaces."""

    placement: WorkspacePlacement

    _FIELDS = (
        "frame_geometry",
        "maximized",
        "full_screen",
        "splitter_proportions",
    )

    @property
    def frame_geometry(self):
        return self.placement.frame_geometry

    @property
    def maximized(self):
        return self.placement.maximized

    @property
    def full_screen(self):
        return self.placement.full_screen

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)

    def __eq__(self, other):
        if isinstance(other, Mapping):
            return dict(self.items()) == dict(other.items())
        return NotImplemented


@dataclass(frozen=True, eq=False)
class ResultsWorkspaceState(WorkspacePaneState):
    """Results placement plus its independently owned pane proportions."""

    placement: WorkspacePlacement
    splitter_proportions: tuple


@dataclass(frozen=True, eq=False)
class EditDatasetWorkspaceState(WorkspacePaneState):
    """Edit Dataset placement plus independently useful collection panes."""

    placement: WorkspacePlacement
    splitter_proportions: tuple[float, float, float]


def update_setting(field, value):
    """Write one validated field using portable primitive storage."""
    spec = SETTING_SPECS[field]
    settings = QSettings()
    if spec.value_type is list:
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ) or len(value) > MAX_RECENT_FILES:
            raise TypeError("%s must be a list of strings" % field)
        encoded = json.dumps(value, ensure_ascii=False)
    elif spec.value_type is bool:
        if type(value) is not bool:
            raise TypeError("%s must be a boolean" % field)
        encoded = value
    elif spec.value_type is int:
        if type(value) is not int:
            raise TypeError("%s must be an integer" % field)
        if field == "digits" and not 0 <= value <= 15:
            raise ValueError("digits must be between 0 and 15")
        encoded = value
    elif spec.value_type is str:
        if not isinstance(value, str):
            raise TypeError("%s must be a string" % field)
        encoded = value
    else:
        raise TypeError("Unsupported settings codec for %s" % field)
    settings.remove(field)
    settings.setValue(field, encoded)


def get_setting_type(field):
    return SETTING_SPECS[field].value_type


def get_setting(field):
    try:
        return _get_setting_helper(field)
    except (TypeError, ValueError, json.JSONDecodeError):
        print(
            "Invalid value for setting '%s'; resetting only that field"
            % field
        )
        update_setting(field, SETTING_SPECS[field].default)
        return _get_setting_helper(field)


def _get_setting_helper(field):
    settings = QSettings()
    spec = SETTING_SPECS[field]
    if spec.value_type is list:
        raw = settings.value(field)
        if raw is None and field in settings.childGroups():
            settings.beginGroup(field)
            indexes = sorted(settings.childKeys(), key=lambda key: int(key))
            legacy = [qt_text.to_native_text(settings.value(key)) for key in indexes]
            settings.endGroup()
            update_setting(field, legacy)
            return legacy
        if not isinstance(raw, str):
            raise TypeError("%s must use the JSON string codec" % field)
        decoded = json.loads(raw)
        if not isinstance(decoded, list) or any(
            not isinstance(item, str) for item in decoded
        ) or len(decoded) > MAX_RECENT_FILES:
            raise ValueError("%s must contain a list of strings" % field)
        return decoded
    if spec.value_type is bool:
        value = settings.value(field, spec.default)
        if type(value) is not bool:
            raise TypeError("%s must contain a boolean" % field)
        return value
    if spec.value_type is int:
        value = settings.value(field, spec.default)
        if type(value) is not int:
            raise TypeError("%s must contain an integer" % field)
        if field == "digits" and not 0 <= value <= 15:
            raise ValueError("digits must be between 0 and 15")
        return value
    if spec.value_type is str:
        return qt_text.to_native_text(settings.value(field, spec.default))
    raise TypeError("Unsupported settings codec for %s" % field)


def save_settings():
    """Mark completion after callers' setValue writes without forcing RegFlushKey."""
    print("saved settings", flush=True)
    print("RCMS_SETTINGS_PHASE before-former-sync", flush=True)
    print("RCMS_SETTINGS_PHASE after-former-sync", flush=True)


def migrate_workspace_layout_settings():
    """Delete only Qt5-bound placement fields, retaining portable state."""
    settings = QSettings()
    version = _strict_schema_version(
        settings.value(WORKSPACE_LAYOUT_GROUP + "/schema_version")
    )
    if version != WORKSPACE_LAYOUT_SCHEMA_VERSION:
        obsolete_suffixes = (
            "frame_geometry",
            "geometry",
            "maximized",
            "full_screen",
            "window_state",
            "windowState",
            "state",
            "splitter",
            "splitter_state",
            "splitterState",
            "splitter_proportions",
            "screen",
            "screen_name",
            "screen_geometry",
            "screen_placement",
        )
        groups = (
            LEGACY_MAIN_WINDOW_GROUP,
            MAIN_WORKSPACE_GROUP,
            RESULTS_WORKSPACE_GROUP,
            EDIT_DATASET_WORKSPACE_GROUP,
            NETWORK_VIEW_WORKSPACE_GROUP,
        )
        for group in groups:
            for suffix in obsolete_suffixes:
                settings.remove(group + "/" + suffix)
        settings.setValue(
            WORKSPACE_LAYOUT_GROUP + "/schema_version",
            WORKSPACE_LAYOUT_SCHEMA_VERSION,
        )
        settings.sync()


def migrate_application_settings():
    """Establish the portable contract without clearing domain settings."""
    migrate_workspace_layout_settings()
    settings = QSettings()
    version = _strict_schema_version(settings.value(APPLICATION_SETTINGS_SCHEMA_KEY))
    if version != APPLICATION_SETTINGS_SCHEMA_VERSION:
        settings.setValue(
            APPLICATION_SETTINGS_SCHEMA_KEY, APPLICATION_SETTINGS_SCHEMA_VERSION
        )
        settings.sync()


def _strict_schema_version(raw):
    if type(raw) is not int:
        return None
    if not 1 <= raw <= SIGNED_INT32_MAX:
        return None
    return raw


def _encode_frame_geometry(frame_geometry):
    frame = QtCore.QRect(frame_geometry)
    if not frame.isValid():
        return ""
    return json.dumps(
        {
            "height": frame.height(),
            "width": frame.width(),
            "x": frame.x(),
            "y": frame.y(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _decode_frame_geometry(raw):
    if raw in (None, ""):
        return None
    try:
        if not isinstance(raw, str):
            return None
        value = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    keys = {"height", "width", "x", "y"}
    if not isinstance(value, dict) or set(value) != keys:
        return None
    if any(type(value[key]) is not int for key in keys):
        return None
    x, y = value["x"], value["y"]
    width, height = value["width"], value["height"]
    if not (
        SIGNED_INT32_MIN <= x <= SIGNED_INT32_MAX
        and SIGNED_INT32_MIN <= y <= SIGNED_INT32_MAX
        and 1 <= width <= SIGNED_INT32_MAX
        and 1 <= height <= SIGNED_INT32_MAX
        and x <= SIGNED_INT32_MAX - width + 1
        and y <= SIGNED_INT32_MAX - height + 1
    ):
        return None
    try:
        frame = QtCore.QRect(x, y, width, height)
    except (OverflowError, TypeError, ValueError):
        return None
    return frame if frame.isValid() else None


def _encode_float_list(values):
    normalized = _strict_positive_numbers(values, len(values))
    if normalized is None:
        raise ValueError("splitter values must be finite positive numbers")
    return json.dumps(normalized, separators=(",", ":"))


def _decode_float_list(raw, default):
    try:
        if not isinstance(raw, str):
            return None
        decoded = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return _strict_positive_numbers(decoded, len(default), upper_bound=1.0)


def _strict_positive_numbers(values, expected_length, upper_bound=SIGNED_INT32_MAX):
    if not isinstance(values, (list, tuple)) or len(values) != expected_length:
        return None
    normalized = []
    for value in values:
        if type(value) not in (int, float):
            return None
        number = float(value)
        if not math.isfinite(number) or not 0.0 < number <= upper_bound:
            return None
        normalized.append(number)
    return normalized


def _read_bool(settings, key, default):
    raw = settings.value(key)
    if raw is None:
        return default
    if type(raw) is bool:
        return raw
    settings.remove(key)
    return default


def _read_frame_geometry(settings, key):
    raw = settings.value(key)
    if raw is None:
        return None
    decoded = _decode_frame_geometry(raw)
    if decoded is None:
        settings.remove(key)
    return decoded


def _read_splitter_proportions(settings, key, default):
    raw = settings.value(key)
    if raw is None:
        return tuple(default)
    decoded = _decode_float_list(raw, default)
    if decoded is None or not math.isclose(sum(decoded), 1.0, abs_tol=1e-9):
        settings.setValue(key, _encode_float_list(default))
        return tuple(default)
    return tuple(decoded)


def _available_screen_geometries():
    app = QtGui.QGuiApplication.instance()
    if app is None:
        return []
    return [
        QtCore.QRect(screen.availableGeometry())
        for screen in QtGui.QGuiApplication.screens()
    ]


def _screen_safe_geometry(frame_geometry, available_geometries):
    from adaptive_window import clamp_frame_geometry

    frame = QtCore.QRect(frame_geometry)
    screens = [QtCore.QRect(rect) for rect in available_geometries if rect.isValid()]
    if not frame.isValid() or not screens:
        return None
    target = next(
        (rect for rect in screens if rect.contains(frame.center())), screens[0]
    )
    return clamp_frame_geometry(frame, target)


def load_workspace_placement(group, available_geometries=None, default_maximized=True):
    """Load one Workspace role through the shared ADR 0196 policy."""
    migrate_workspace_layout_settings()
    settings = QSettings()
    geometry = _read_frame_geometry(settings, group + "/frame_geometry")
    geometry = (
        _screen_safe_geometry(
            geometry,
            _available_screen_geometries()
            if available_geometries is None
            else available_geometries,
        )
        if geometry is not None
        else None
    )
    return WorkspacePlacement(
        frame_geometry=geometry,
        maximized=_read_bool(
            settings,
            group + "/maximized",
            bool(default_maximized and geometry is None),
        ),
        full_screen=_read_bool(settings, group + "/full_screen", False),
    )


def load_main_window_placement(available_geometries=None):
    return load_workspace_placement(
        MAIN_WORKSPACE_GROUP,
        available_geometries=available_geometries,
        default_maximized=True,
    )


def _splitter_proportions(sizes, default=DEFAULT_RESULTS_SPLITTER_PROPORTIONS):
    values = _strict_positive_numbers(sizes, len(default))
    if values is None:
        return list(default)
    total = sum(values)
    if (
        len(values) != len(default)
        or not math.isfinite(total)
        or total <= 0
    ):
        return list(default)
    return [value / total for value in values]


def load_results_window_state(available_geometries=None):
    """Load Results placement and its independently persisted pane ratio."""
    placement = load_workspace_placement(
        RESULTS_WORKSPACE_GROUP,
        available_geometries=available_geometries,
        default_maximized=True,
    )
    settings = QSettings()
    proportions = _read_splitter_proportions(
        settings,
        RESULTS_WORKSPACE_GROUP + "/splitter_proportions",
        DEFAULT_RESULTS_SPLITTER_PROPORTIONS,
    )
    return ResultsWorkspaceState(
        placement=placement,
        splitter_proportions=proportions,
    )


def _workspace_normal_frame(window):
    frame = window.frameGeometry()
    if window.isMaximized() or window.isFullScreen():
        controller = getattr(window, "_adaptive_window_controller", None)
        normal = (
            controller.normal_frame_geometry()
            if controller is not None
            else QtCore.QRect()
        )
        if not normal.isValid():
            normal = window.normalGeometry()
        if normal.isValid():
            frame = normal
    return frame


def save_workspace_placement(group, window):
    """Persist the shared typed portion of one Workspace role's state."""
    migrate_workspace_layout_settings()
    settings = QSettings()
    settings.setValue(
        group + "/frame_geometry",
        _encode_frame_geometry(_workspace_normal_frame(window)),
    )
    settings.setValue(group + "/maximized", window.isMaximized())
    settings.setValue(group + "/full_screen", window.isFullScreen())
    return settings


def restore_workspace_placement(
    window, placement, default_maximized=True, show_window=True
):
    """Restore one validated Workspace placement without role-specific state."""
    geometry = placement.frame_geometry
    controller = getattr(window, "_adaptive_window_controller", None)
    if geometry is not None:
        if controller is not None:
            controller.consume_first_use()
        window.setWindowState(
            window.windowState()
            & ~QtCore.Qt.WindowState.WindowMaximized
            & ~QtCore.Qt.WindowState.WindowFullScreen
        )
        if controller is not None:
            controller.restore_frame_geometry(geometry)
        else:
            # layout-audit: allow=persisted-workspace-placement; reason=validated remembered Workspace placement is restored
            window.setGeometry(geometry)

    if placement.full_screen:
        if show_window:
            window.showFullScreen()
        else:
            window.setWindowState(window.windowState() | QtCore.Qt.WindowState.WindowFullScreen)
    elif placement.maximized or (default_maximized and geometry is None):
        if show_window:
            window.showMaximized()
        else:
            window.setWindowState(window.windowState() | QtCore.Qt.WindowState.WindowMaximized)
    elif show_window:
        window.show()
    else:
        window.setWindowState(
            window.windowState()
            & ~QtCore.Qt.WindowState.WindowMaximized
            & ~QtCore.Qt.WindowState.WindowFullScreen
        )


def save_results_window_state(window):
    """Persist Results geometry and meaningful splitter proportions."""
    settings = save_workspace_placement(RESULTS_WORKSPACE_GROUP, window)
    settings.setValue(
        RESULTS_WORKSPACE_GROUP + "/splitter_proportions",
        _encode_float_list(
            _splitter_proportions(window.results_nav_splitter.sizes())
        ),
    )
    settings.sync()


def restore_results_window_state(window):
    """Restore valid Results placement or retain its fresh maximized state."""
    state = load_results_window_state()
    restore_workspace_placement(
        window,
        state.placement,
        default_maximized=True,
        show_window=False,
    )
    return state


def load_edit_dataset_window_state(available_geometries=None):
    """Load independent Edit Dataset placement and collection pane shares."""
    placement = load_workspace_placement(
        EDIT_DATASET_WORKSPACE_GROUP,
        available_geometries=available_geometries,
        default_maximized=False,
    )
    settings = QSettings()
    proportions = _read_splitter_proportions(
        settings,
        EDIT_DATASET_WORKSPACE_GROUP + "/splitter_proportions",
        DEFAULT_EDIT_DATASET_SPLITTER_PROPORTIONS,
    )
    return EditDatasetWorkspaceState(
        placement=placement,
        splitter_proportions=proportions,
    )


def save_edit_dataset_window_state(window):
    """Persist user-owned Edit Dataset geometry and collection pane shares."""
    settings = save_workspace_placement(EDIT_DATASET_WORKSPACE_GROUP, window)
    settings.setValue(
        EDIT_DATASET_WORKSPACE_GROUP + "/splitter_proportions",
        _encode_float_list(
            _splitter_proportions(
                window.dataset_structure_splitter.sizes(),
                default=DEFAULT_EDIT_DATASET_SPLITTER_PROPORTIONS,
            )
        ),
    )
    settings.sync()


def restore_edit_dataset_window_state(window):
    """Restore Edit Dataset placement without displaying the modal dialog."""
    state = load_edit_dataset_window_state()
    restore_workspace_placement(
        window,
        state.placement,
        default_maximized=False,
        show_window=False,
    )
    return state


def load_network_view_placement(available_geometries=None):
    """Load Network View's independent screen-safe Workspace placement."""
    return load_workspace_placement(
        NETWORK_VIEW_WORKSPACE_GROUP,
        available_geometries=available_geometries,
        default_maximized=False,
    )


def save_network_view_placement(window):
    """Persist Network View geometry independently of other Workspaces."""
    settings = save_workspace_placement(NETWORK_VIEW_WORKSPACE_GROUP, window)
    settings.sync()


def restore_network_view_placement(window):
    """Restore Network View placement without displaying the modeless window."""
    placement = load_network_view_placement()
    restore_workspace_placement(
        window,
        placement,
        default_maximized=False,
        show_window=False,
    )
    return placement


def save_main_window_placement(window, column_widths=None):
    settings = save_workspace_placement(MAIN_WORKSPACE_GROUP, window)
    if column_widths is not None:
        settings.setValue(
            MAIN_WORKSPACE_GROUP + "/column_widths",
            column_widths.to_json(),
        )
    settings.sync()


def restore_main_window_placement(window, default_maximized=True):
    placement = load_main_window_placement()
    restore_workspace_placement(
        window,
        placement,
        default_maximized=default_maximized,
        show_window=True,
    )


def load_main_column_widths():
    migrate_workspace_layout_settings()
    raw = QSettings().value(MAIN_WORKSPACE_GROUP + "/column_widths", "")
    return WorkspaceColumnWidthState.from_json(raw)


def load_settings():
    """loads settings from QSettings object, setting suitable defaults if
    there are missing fields"""

    migrate_application_settings()
    settings = QSettings()

    def field_is_toplevel_child_group_keys(field_name):
        childgroups = list(settings.childGroups())
        toplevel_group_keys = [str(x) for x in childgroups]
        return field_name in toplevel_group_keys

    for field, value in list(DEFAULT_SETTINGS.items()):
        setting_present = settings.contains(
            field
        ) or field_is_toplevel_child_group_keys(field)
        if not setting_present:
            print(("Filling in setting for %s" % field))
            update_setting(field, value)

    save_settings()
    print("loaded settings")
    return settings


def reset_settings():
    print("Resetting settings to default")
    settings = QSettings()
    settings.clear()

    for field, value in list(DEFAULT_SETTINGS.items()):
        update_setting(field, value)
    save_settings()


def add_file_to_recent_files(fpath):
    # add a new file to the front of the deque
    # move existing file to the front of the deque

    if fpath in [None, ""]:
        return False

    recent_files = get_setting("recent_files")

    if fpath in recent_files:  # file already in list so move to front
        recent_files.remove(fpath)
    recent_files.append(fpath)

    # only want up to MAX_RECENT_FILES
    start_index = len(recent_files) - MAX_RECENT_FILES
    if start_index > 0:
        recent_files = recent_files[start_index:]

    update_setting("recent_files", recent_files)
    save_settings()


def get_sample_projects_path():
    if getattr(sys, "frozen", False):
        path_module = (
            posixpath
            if sys.platform == "darwin"
            else ntpath
            if sys.platform == "win32"
            else os.path
        )
        app_root = path_module.dirname(sys.executable)
        if sys.platform == "darwin":
            return path_module.normpath(
                path_module.join(
                    app_root, path_module.pardir, "Resources", "sample_projects"
                )
            )
        return path_module.join(app_root, "sample_projects")
    app_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
    )
    return os.path.join(app_root, "sample_projects")


def get_default_open_directory(recent_files=None):
    if recent_files is None:
        recent_files = get_setting("recent_files")

    for recent_file in reversed(recent_files):
        recent_dir = os.path.dirname(os.path.abspath(str(recent_file)))
        if os.path.isdir(recent_dir):
            return recent_dir

    sample_projects_path = get_sample_projects_path()
    if os.path.isdir(sample_projects_path):
        return sample_projects_path

    documents_path = get_user_documents_path()
    if documents_path and os.path.isdir(documents_path):
        return documents_path

    return "."


################ END HANDLE SETTINGS ######################


###### HANDLE ANALYSIS SCRATCH DIRECTORY ###################
def setup_directories():
    """Create and clear the managed scratch directory for analysis artifacts.

    Python stays in the application data directory; R is reset to the same base
    directory and writes analysis artifacts under the managed scratch folder.
    """

    # Create the application data root and managed analysis scratch folder.
    base_path = make_base_path()
    make_r_tmp()

    from rc_metastudio import meta_py_r

    meta_py_r.reset_Rs_working_dir()  # set working directory on R side
    os.chdir(os.path.normpath(base_path))  # set working directory on python side

    clear_r_tmp()


def make_base_path():
    """Create the application data path if needed and return it."""

    base_path = get_base_path()

    success = QDir().mkpath(base_path)
    if not success:
        raise Exception("Could not create base path at %s" % base_path)
    print(("Made base path: %s" % base_path))
    return base_path


def get_base_path(normalize=False):
    """normalize changes the path separators according to the OS,
    Usually this shouldn't be done because R is confused by backward slashes \
    because it sees it as an escape character and Qt is fine with / throughout """

    base_path = str(
        QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.StandardLocation.AppDataLocation)
    )
    if normalize:
        base_path = str(QDir.toNativeSeparators(base_path))
    print(("Base path is: %s" % base_path))
    return base_path


def get_r_tmp_path(normalize=False):
    """Return the managed analysis scratch directory."""
    override_path = os.environ.get(ANALYSIS_SCRATCH_ENV_VAR)
    r_tmp_path = (
        override_path if override_path else os.path.join(get_base_path(), "r_tmp")
    )
    if normalize:
        r_tmp_path = str(QDir.toNativeSeparators(r_tmp_path))
    return r_tmp_path


def make_r_tmp():
    """Create the managed analysis scratch folder and return its path."""
    r_tmp_path = get_r_tmp_path()
    success = QDir().mkpath(r_tmp_path)
    if not success:
        raise Exception("Could not create r_tmp path at %s" % r_tmp_path)
    print(("Made r_tmp_path at %s" % r_tmp_path))
    return r_tmp_path


def analysis_output_path(filename, normalize=False):
    """Return a file path inside the managed analysis scratch directory."""
    path = os.path.join(make_r_tmp(), filename)
    if normalize:
        return str(QDir.toNativeSeparators(path))
    return to_posix_path(path)


def to_posix_path(path):
    r"""Convert native separators to POSIX-style separators for R strings.

    The input must already be a literal path, not an escaped string.
    """

    new_path = path.replace("\\", "/")
    return new_path


def clear_r_tmp():
    r_tmp_dir = get_r_tmp_path(normalize=True)
    print(("Clearing %s" % r_tmp_dir))
    if not os.path.isdir(r_tmp_dir):
        return
    for file_p in os.listdir(r_tmp_dir):
        file_path = os.path.join(r_tmp_dir, file_p)
        try:
            if os.path.isfile(file_path):
                print(("deleting %s" % file_path))
                os.unlink(file_path)  # same as remove
        except Exception as e:
            print(e)


def get_user_documents_path():
    docs_path = str(
        QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.StandardLocation.DocumentsLocation)
    )
    return docs_path


############## END OF HANDLE R_TEMP IN USER-AREA DIRECTORY ####################
