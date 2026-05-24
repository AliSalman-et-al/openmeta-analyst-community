'''
This file should only be used when launching a windows build, not during
developement

@author: George Dietz
         CEBM@Brown
'''

import os
import sys


def _runtime_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _prepend_path(paths):
    old_path = os.environ.get("PATH", "")
    existing = [path for path in paths if os.path.isdir(path)]
    os.environ["PATH"] = os.pathsep.join(existing + [old_path])


def _set_r_environment():
    base_dir = _runtime_dir()
    contents_dir = os.path.dirname(base_dir)
    r_home_candidates = [
        os.path.join(base_dir, "R"),
        os.path.join(contents_dir, "Resources", "R"),
    ]
    r_home = next((path for path in r_home_candidates if os.path.isdir(path)), r_home_candidates[0])
    if not os.path.isdir(r_home):
        return

    os.environ["R_HOME"] = r_home
    os.environ["R_USER"] = os.environ.get("R_USER", "oma")
    os.environ["R_SHARE_DIR"] = os.path.join(r_home, "share")
    os.environ["R_INCLUDE_DIR"] = os.path.join(r_home, "include")
    os.environ["R_DOC_DIR"] = os.path.join(r_home, "doc")

    runtime_paths = [
        os.path.join(base_dir, "Library", "bin"),
        os.path.join(base_dir, "Library", "mingw-w64", "bin"),
        os.path.join(base_dir, "Library", "usr", "bin"),
        os.path.join(contents_dir, "Resources", "lib"),
        os.path.join(contents_dir, "Resources", "bin"),
        os.path.join(r_home, "bin"),
        os.path.join(r_home, "lib"),
        os.path.join(r_home, "bin", "x64"),
    ]

    _prepend_path(runtime_paths)
    for library_path_variable in ("DYLD_LIBRARY_PATH", "LD_LIBRARY_PATH"):
        old_value = os.environ.get(library_path_variable, "")
        existing = [path for path in runtime_paths if os.path.isdir(path)]
        os.environ[library_path_variable] = os.pathsep.join(existing + [old_value])

# # Set R environment variables
# oldpath = os.environ["PATH"]
# cwd = os.getcwd()
# rpath = os.path.join(cwd, "R_dist") # second 'Resources' is R directory
# # just adding the 64-bit path version for now
# os.environ["PATH"] = os.path.join(rpath, "bin","x64") + os.pathsep + oldpath
# print("new path is: %s" % os.environ["PATH"])
# 
# #os.environ["R"] = os.path.join(cwd, rpath, "bin")
# os.environ["R_HOME"] = os.path.join(cwd, rpath)
# #os.environ["R_HOME"] = os.path.join(rpath, "bin","x64")
# print("R_HOME: %s" % os.environ["R_HOME"])
# 
# os.environ["R_USER"] = "oma" 

_set_r_environment()

# we are ready to start the main program loop
import launch
if __name__ == "__main__":
    launch.start()
