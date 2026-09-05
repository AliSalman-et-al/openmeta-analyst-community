import ctypes
import hashlib
import json
import locale
import os
from pathlib import Path
import sys
import tempfile
import threading

_DLL_DIRECTORY_HANDLES = []
_RUNTIME_IDENTITY = None
_BOOTSTRAP_THREAD_ID = None


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_manifest_digest(manifest):
    unsigned = {key: value for key, value in manifest.items() if key != "kit_sha256"}
    payload = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _load_frozen_identity(metadata_root):
    try:
        manifest = json.loads((metadata_root / "manifest.json").read_text(encoding="utf-8"))
        derivation = json.loads((metadata_root / "derivation.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Frozen R integration-kit identity is missing or unreadable."
        ) from exc
    return manifest, derivation


def _validate_frozen_identity_manifest(manifest, derivation, target):
    valid = (
        manifest.get("kind") == "rc-metastudio-r-integration-kit"
        and manifest.get("target") == target
        and manifest.get("cffi_mode") == "API"
        and manifest.get("kit_sha256") == _canonical_manifest_digest(manifest)
        and derivation.get("schema_version") == 1
        and derivation.get("kit_sha256") == manifest.get("kit_sha256")
        and derivation.get("target") == target
    )
    if not valid:
        raise RuntimeError("Frozen R integration-kit identity is invalid.")


def _validate_frozen_path(record, app_root, name):
    path = (app_root / str(record.get("path", ""))).resolve()
    bundle_root = app_root.parent if sys.platform == "darwin" else app_root
    valid = path.is_relative_to(bundle_root) and path.is_file()
    if not valid or _sha256(path) != record.get("sha256"):
        raise RuntimeError(f"Frozen R derivation record is invalid for {name}.")


def _validate_frozen_derivation_record(
    name, source, pre_sign, final, transformations, manifest_files, app_root
):
    source_record = source.get(name, {})
    pre_sign_record = pre_sign.get(name, {})
    record = final.get(name, {})
    manifest_record = manifest_files.get(source_record.get("path"), {})
    transformation = transformations.get(name)
    if not _valid_derivation_chain(
        name,
        source_record,
        pre_sign_record,
        record,
        manifest_record,
        transformation,
    ):
        raise RuntimeError(f"Frozen R derivation chain is invalid for {name}.")
    _validate_frozen_path(record, app_root, name)


def _valid_derivation_chain(
    name, source, pre_sign, final, manifest_record, transformation
):
    if source.get("sha256") != manifest_record.get("sha256"):
        return False
    derived = pre_sign.get("sha256") == source.get("sha256")
    if name == "api_bridge":
        derived = derived or _valid_bridge_relocation(
            transformation, source, pre_sign
        )
    return bool(
        derived
        and final.get("path") == pre_sign.get("path")
        and pre_sign.get("signing_identity")
        and final.get("signing_identity")
    )


def _valid_bridge_relocation(transformation, source, pre_sign):
    if not isinstance(transformation, dict):
        return False
    return bool(
        transformation.get("kind") == "mach-o-load-command-relocation"
        and transformation.get("source", {}).get("sha256") == source.get("sha256")
        and transformation.get("output", {}).get("sha256")
        == pre_sign.get("sha256")
        and transformation.get("changes")
    )


def _frozen_kit_identity(root):
    app_root = Path(root).resolve()
    metadata_root = (
        app_root.parent / "Resources" / "r-integration-kit"
        if sys.platform == "darwin"
        else app_root / "r-integration-kit"
    )
    manifest, derivation = _load_frozen_identity(metadata_root)
    target = "macos-arm64" if sys.platform == "darwin" else "windows-x64"
    _validate_frozen_identity_manifest(manifest, derivation, target)
    final = derivation.get("final", {})
    source = derivation.get("source", {})
    pre_sign = derivation.get("pre_sign", {})
    transformations = derivation.get("transformations", {})
    required = ("api_bridge", "r_shared_library")
    manifest_files = {
        record.get("path"): record
        for record in manifest.get("files", [])
        if record.get("kind") == "file"
    }
    for name in required:
        _validate_frozen_derivation_record(
            name, source, pre_sign, final, transformations, manifest_files, app_root
        )
    return manifest, derivation


def _configure_private_runtime_directories(root):
    bundle = Path(root).resolve()
    base = (
        Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "RCMetaStudio" / "runtime"
    )
    if base.resolve().is_relative_to(bundle.parent):
        raise RuntimeError(
            "Frozen runtime HOME must be outside the application bundle."
        )
    home = base / "home"
    temporary = base / "tmp"
    home.mkdir(parents=True, exist_ok=True)
    temporary.mkdir(parents=True, exist_ok=True)
    for path in (home, temporary):
        probe = path / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    os.environ["HOME"] = str(home)
    os.environ["TMPDIR"] = str(temporary)
    os.environ["TMP"] = str(temporary)
    os.environ["TEMP"] = str(temporary)
    tempfile.tempdir = str(temporary)


def _set_windows_dll_policy():
    if sys.platform != "win32":
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    policy = 0x00001000 | 0x00000400
    if not kernel32.SetDefaultDllDirectories(policy):
        raise OSError(ctypes.get_last_error(), "SetDefaultDllDirectories failed")


def macos_r_framework_version(r_version: str) -> str:
    """Return the stable major.minor directory name for an R framework."""
    parts = r_version.split(".")
    if len(parts) < 2 or not all(part.isdigit() for part in parts):
        raise ValueError(f"invalid R version for a macOS framework: {r_version!r}")
    return ".".join(parts[:2])


def _configure_frozen_runtime(root, direct_spike):
    global _BOOTSTRAP_THREAD_ID, _RUNTIME_IDENTITY
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("Frozen R bootstrap must run on the application main thread.")
    if _BOOTSTRAP_THREAD_ID not in (None, threading.get_ident()):
        raise RuntimeError("Frozen R bootstrap was already initialized by another thread.")
    if _RUNTIME_IDENTITY is not None:
        return dict(_RUNTIME_IDENTITY)
    if not direct_spike and sys.platform != "win32":
        manifest, derivation = _frozen_kit_identity(root)
    else:
        manifest, derivation = None, None
    _configure_private_runtime_directories(root)
    _set_windows_dll_policy()
    return manifest, derivation


def _runtime_candidates(root, frozen):
    candidates = [
        os.path.join(root, "..", "Frameworks", "R.framework", "Resources"),
        os.path.join(root, "R"),
    ]
    if not frozen:
        candidates.insert(0, os.environ.get("RCMS_R_HOME"))
    return candidates


def _configure_r_home(root, frozen):
    r_home = _first_existing(_runtime_candidates(root, frozen), required_child=os.path.join("bin"))
    if r_home:
        os.environ["R_HOME"] = r_home
        dll_paths = [
            os.path.join(r_home, "bin", "x64"),
            os.path.join(r_home, "bin"),
            os.path.join(r_home, "library", "bin"),
        ]
        if frozen and sys.platform == "win32":
            dll_paths.extend(_private_windows_dll_directories(r_home))
        elif frozen and sys.platform == "darwin":
            dll_paths.extend(("/usr/bin", "/bin", "/usr/sbin", "/sbin"))
        _prepend_path(dll_paths, preserve_existing=not frozen)
        _add_dll_directories(dll_paths)
    elif frozen:
        raise RuntimeError("Frozen application is missing its private R runtime.")
    return r_home


def _configure_r_libraries(root, r_home, frozen):
    candidates = [
        os.path.join(r_home, "library") if r_home else None,
        os.path.join(root, "..", "Frameworks", "R.framework", "Resources", "library"),
        os.path.join(root, "R", "library"),
    ]
    if not frozen:
        candidates.insert(0, os.environ.get("RCMS_R_LIBS"))
    r_libs = _first_existing(candidates, required_child=os.path.join("RCMetaR"))
    if r_libs:
        os.environ["R_LIBS"] = r_libs
        os.environ["R_LIBS_USER"] = r_libs
    elif frozen:
        raise RuntimeError("Frozen application is missing its private RCMetaR library.")
    return r_libs


def _set_r_environment():
    os.environ["RPY2_CFFI_MODE"] = "API"
    os.environ["R_ENVIRON_USER"] = os.devnull
    os.environ["R_PROFILE_USER"] = os.devnull
    os.environ["R_ENVIRON"] = os.devnull
    os.environ["R_PROFILE"] = os.devnull
    os.environ["R_DEFAULT_PACKAGES"] = "utils,grDevices,graphics,stats,methods"
    os.environ["LC_NUMERIC"] = "C"
    locale.setlocale(locale.LC_NUMERIC, "C")


def configure_bundled_r_environment(app_root=None):
    global _BOOTSTRAP_THREAD_ID, _RUNTIME_IDENTITY
    root = app_root or _app_root()
    frozen = bool(getattr(sys, "frozen", False))
    direct_spike_marker = Path(root).parent / "Resources" / "direct-r-spike.marker"
    direct_spike = frozen and sys.platform == "darwin" and direct_spike_marker.is_file()
    manifest = derivation = None
    if frozen:
        frozen_identity = _configure_frozen_runtime(root, direct_spike)
        if isinstance(frozen_identity, dict):
            return frozen_identity
        manifest, derivation = frozen_identity
    r_home = _configure_r_home(root, frozen)
    r_libs = _configure_r_libraries(root, r_home, frozen)
    _set_r_environment()
    identity = _runtime_identity(manifest, derivation, direct_spike)
    _install_runtime_identity(identity, frozen)
    return dict(identity)


def _runtime_identity(manifest, derivation, direct_spike):
    return {
        "R_HOME": os.environ.get("R_HOME"),
        "R_LIBS": os.environ.get("R_LIBS"),
        "cffi_mode": "API",
        "kit_sha256": manifest["kit_sha256"] if manifest is not None else None,
        "derivation": derivation,
        "direct_spike": direct_spike,
    }


def _install_runtime_identity(identity, frozen):
    global _BOOTSTRAP_THREAD_ID, _RUNTIME_IDENTITY
    if _RUNTIME_IDENTITY is not None and _RUNTIME_IDENTITY != identity:
        raise RuntimeError(
            "Embedded R was already configured with a different runtime identity."
        )
    _RUNTIME_IDENTITY = identity
    if frozen:
        _BOOTSTRAP_THREAD_ID = threading.get_ident()


def _app_root():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return _repo_root()


def _repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _first_existing(candidates, required_child=None):
    for candidate in candidates:
        if not candidate:
            continue
        if required_child is None and os.path.exists(candidate):
            return candidate
        if required_child is not None and os.path.exists(
            os.path.join(candidate, required_child)
        ):
            return candidate
    return None


def _prepend_path(paths, preserve_existing=True):
    existing = os.environ.get("PATH", "") if preserve_existing else ""
    path_parts = []
    seen = set()
    for path in paths:
        normalized = os.path.normcase(os.path.abspath(path))
        if os.path.exists(path) and normalized not in seen:
            path_parts.append(path)
            seen.add(normalized)
    os.environ["PATH"] = os.pathsep.join(path_parts + ([existing] if existing else []))


def _add_dll_directories(paths):
    add_dll_directory = getattr(os, "add_dll_directory", None)
    if add_dll_directory is None:
        return
    for path in paths:
        if os.path.exists(path):
            _DLL_DIRECTORY_HANDLES.append(add_dll_directory(path))


def _private_windows_dll_directories(r_home):
    root = Path(r_home).resolve(strict=True)
    return [
        str(path)
        for path in sorted(
            {
                item.parent.resolve()
                for item in root.rglob("*")
                if item.is_file() and item.suffix.casefold() in {".dll", ".pyd"}
            },
            key=lambda value: str(value).casefold(),
        )
    ]
