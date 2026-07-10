# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Application settings and managed analysis workspace paths."""

import os
import sys
from PyQt5 import QtCore, QtGui
import meta_py_r
import qt_text

QColor = QtGui.QColor
QDir = QtCore.QDir
QSettings = QtCore.QSettings
ANALYSIS_SCRATCH_ENV_VAR = "RCMS_ANALYSIS_SCRATCH_DIR"

##################### HANDLE SETTINGS #####################

MAX_RECENT_FILES = 10
MAIN_WINDOW_GROUP = "main_window"
DEFAULT_SETTINGS = {
    "splash": True,
    "digits": 2,
    "recent_files": [],
    # "method_params":{},
}


def update_setting(field, value):
    """Updates the setting with key field to value."""

    settings = QSettings()

    # see if we need to store the value in a special way
    value_type = get_setting_type(field)
    if value_type == list:
        # QSettings arrays are used for recent-file paths, which are stored as
        # strings.
        if settings.contains(field):
            settings.remove(field)
        settings.beginGroup(field)
        for i, x in enumerate(value):  # value is a list
            settings.setValue(str(i), x)
        settings.endGroup()
    elif value_type == dict:
        raise Exception("Not implemented yet!")
    elif value_type == bool:
        settings.setValue(field, value)
    elif value_type == QColor:
        # just being explicit to signify i am aware of QColors and to match get_setting
        settings.setValue(field, value)
    elif value_type == int:
        settings.setValue(field, value)
    elif value_type == str:
        settings.setValue(field, value)
    else:
        # nothing special needs to be done
        print(("Field: %s" % field))
        print(("Value type: %s" % str(value_type)))
        raise Exception("Are you SURE that NOTHING special needs to be done?")
        settings.setValue(field, value)


def get_setting_type(field):
    return type(DEFAULT_SETTINGS[field])


def get_setting(field):
    try:
        return _get_setting_helper(field)
    except Exception as e:
        print(
            "Exception while trying to access setting '%s', resetting settings to defaults"
            % field
        )
        reset_settings()
        return _get_setting_helper(field)
    return _get_setting_helper(field)


def _get_setting_helper(field):
    settings = QSettings()

    # see if we need to store the value in a special way
    value_type = get_setting_type(field)
    # print("Setting type: %s for %s" % (str(value_type), field))
    if value_type == list:
        settings.beginGroup(field)
        indexes = list(settings.childKeys())
        foo_list = []
        for i in indexes:
            value = settings.value(i)
            foo_list.append(qt_text.to_native_text(value))
        settings.endGroup()
        setting_value = foo_list
    elif value_type == dict:
        raise Exception("Not implemented yet!")
    elif value_type == bool:
        print(("Converted %s to a boolean" % field))
        value = settings.value(field)
        if hasattr(value, "toBool"):
            setting_value = value.toBool()
        elif hasattr(value, "value"):
            setting_value = bool(value.value())
        else:
            setting_value = bool(value)
    elif value_type == str:
        value = settings.value(field)
        setting_value = qt_text.to_native_text(value)
    elif value_type == str:
        settings.setValue(field, value)
    elif value_type == int:
        value = settings.value(field)
        setting_value = value.toInt()[0] if hasattr(value, "toInt") else int(value)
    elif value_type == QColor:
        setting_value = QColor(settings.value(field))
    else:
        # nothing special needs to be done
        raise Exception("Are you SURE that NOTHING special needs to be done?")
        setting_value = settings.value(field)

    return setting_value


def save_settings():
    print("saved settings")
    settings = QSettings()
    settings.sync()  # writes to permanent storage


def save_main_window_placement(window):
    settings = QSettings()
    settings.beginGroup(MAIN_WINDOW_GROUP)
    settings.setValue("geometry", window.saveGeometry())
    settings.setValue("maximized", window.isMaximized())
    settings.setValue("full_screen", window.isFullScreen())
    settings.endGroup()
    settings.sync()


def restore_main_window_placement(window, default_maximized=True):
    settings = QSettings()
    settings.beginGroup(MAIN_WINDOW_GROUP)
    has_geometry = settings.contains("geometry")
    geometry = settings.value("geometry") if has_geometry else None
    maximized = settings.value("maximized", default_maximized, type=bool)
    full_screen = settings.value("full_screen", False, type=bool)
    settings.endGroup()

    if has_geometry and geometry is not None:
        window.restoreGeometry(geometry)

    if full_screen:
        window.showFullScreen()
    elif maximized or (default_maximized and not has_geometry):
        window.showMaximized()
    else:
        window.show()


def load_settings():
    """loads settings from QSettings object, setting suitable defaults if
    there are missing fields"""

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
        app_root = os.path.dirname(sys.executable)
    else:
        app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
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
        QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.AppDataLocation)
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
        QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
    )
    return docs_path


############## END OF HANDLE R_TEMP IN USER-AREA DIRECTORY ####################
