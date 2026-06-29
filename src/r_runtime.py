import os
import sys

_DLL_DIRECTORY_HANDLES = []


def configure_bundled_r_environment(app_root=None):
    root = app_root or _app_root()
    r_home = _first_existing([
        os.environ.get("OMA_R_HOME"),
        os.path.join(root, "R"),
    ], required_child=os.path.join("bin"))
    if r_home:
        os.environ["R_HOME"] = r_home
        r_parent = os.path.dirname(r_home)
        dll_paths = [
            os.path.join(r_home, "bin", "x64"),
            os.path.join(r_home, "bin"),
            os.path.join(r_parent, "Library", "bin"),
            os.path.join(r_parent, "Library", "mingw-w64", "bin"),
            os.path.join(r_parent, "Library", "usr", "bin"),
            os.path.join(root, "Library", "bin"),
            os.path.join(root, "Library", "mingw-w64", "bin"),
            os.path.join(root, "Library", "usr", "bin"),
        ]
        _prepend_path(dll_paths)
        _add_dll_directories(dll_paths)

    r_libs = _first_existing([
        os.environ.get("OMA_R_LIBS"),
        os.path.join(root, "R", "library"),
    ], required_child=os.path.join("openmetar"))
    if r_libs:
        os.environ["R_LIBS"] = r_libs
        os.environ["R_LIBS_USER"] = r_libs

    os.environ.setdefault("RPY2_CFFI_MODE", "ABI")
    return {"R_HOME": os.environ.get("R_HOME"), "R_LIBS": os.environ.get("R_LIBS")}


def _app_root():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return _repo_root()


def _repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _first_existing(candidates, required_child=None):
    for candidate in candidates:
        if not candidate:
            continue
        if required_child is None and os.path.exists(candidate):
            return candidate
        if required_child is not None and os.path.exists(os.path.join(candidate, required_child)):
            return candidate
    return None


def _prepend_path(paths):
    existing = os.environ.get("PATH", "")
    path_parts = []
    seen = set()
    for path in paths:
        normalized = os.path.normcase(os.path.abspath(path))
        if os.path.exists(path) and normalized not in seen:
            path_parts.append(path)
            seen.add(normalized)
    os.environ["PATH"] = os.pathsep.join(path_parts + [existing])


def _add_dll_directories(paths):
    add_dll_directory = getattr(os, "add_dll_directory", None)
    if add_dll_directory is None:
        return
    for path in paths:
        if os.path.exists(path):
            _DLL_DIRECTORY_HANDLES.append(add_dll_directory(path))
