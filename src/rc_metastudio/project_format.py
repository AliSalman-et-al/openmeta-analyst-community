"""Safe, Qt-independent persistence for the Versioned Project Format."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import copy
from dataclasses import dataclass
import hashlib
from importlib import resources
import json
import math
import os
from pathlib import Path
import stat
import tempfile
from typing import BinaryIO, TypeAlias, cast
import zipfile
import zlib

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from rc_metastudio import __version__
from rc_metastudio.project_domain import (
    AnalysisDataset,
    ProjectSemanticError,
    reconstruct_analysis_dataset as _reconstruct_analysis_dataset,
    validate_project_semantics,
)


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]

CURRENT_FORMAT_VERSION = 1
MAX_JSON_NESTING = 32
MAX_JSON_INTEGER_DIGITS = 1024
_FORMAT_NAME = "rc-metastudio-project"
_EXPECTED_MEMBERS = ("manifest.json", "project.json", "state.json")
_JSON_MEMBERS = ("project.json", "state.json")
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_SUPPORTED_COMPRESSION_METHODS = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}


class ProjectFormatError(ValueError):
    """A project cannot be safely read or written."""


class ProjectDurabilityError(ProjectFormatError):
    """Replacement succeeded but final filesystem durability was not confirmed."""


@dataclass(frozen=True, slots=True)
class ProjectArchiveLimits:
    """Resource ceilings applied before any archive member is decoded."""

    max_archive_size: int = 32 * 1024 * 1024
    max_member_count: int = len(_EXPECTED_MEMBERS)
    max_member_size: int = 16 * 1024 * 1024
    max_total_uncompressed_size: int = 32 * 1024 * 1024
    max_compression_ratio: float = 100.0


@dataclass(frozen=True, slots=True)
class ProjectDocument:
    """Validated latest-version project content returned to application code."""

    format_version: int
    project: JsonObject
    state: JsonObject


def reconstruct_analysis_dataset(document: ProjectDocument) -> AnalysisDataset:
    """Return the Qt-independent Analysis Adapter input for a loaded project."""
    try:
        return _reconstruct_analysis_dataset(document.project, document.state)
    except (ProjectSemanticError, RecursionError) as exc:
        raise ProjectFormatError(f"project semantics: {exc}") from exc


ProjectMigration: TypeAlias = Callable[
    [JsonObject, JsonObject], tuple[JsonObject, JsonObject]
]
_MIGRATIONS: Mapping[int, ProjectMigration] = {}


def _reject_duplicate_keys(pairs: list[tuple[str, JsonValue]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            raise ProjectFormatError(f"duplicate JSON property: {key}")
        result[key] = value
    return result


def _reject_non_finite(token: str) -> None:
    raise ProjectFormatError(f"non-finite JSON number is not allowed: {token}")


def _parse_json_integer(token: str) -> int:
    digits = token.removeprefix("-")
    if len(digits) > MAX_JSON_INTEGER_DIGITS:
        raise ValueError(
            f"integer literal exceeds {MAX_JSON_INTEGER_DIGITS} decimal digits"
        )
    return int(token)


def _parse_json_float(token: str) -> float:
    number = float(token)
    if not math.isfinite(number):
        raise ValueError("floating-point literal is outside the finite JSON range")
    return number


def _validate_json_tree(value: object, member: str) -> None:
    pending: list[tuple[object, int]] = [(value, 1)]
    while pending:
        current, depth = pending.pop()
        if depth > MAX_JSON_NESTING:
            raise ProjectFormatError(
                f"{member}: JSON nesting exceeds the limit of {MAX_JSON_NESTING}"
            )
        if isinstance(current, dict):
            pending.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            pending.extend((item, depth + 1) for item in current)
        elif isinstance(current, bool) or current is None or isinstance(current, str):
            continue
        elif isinstance(current, int):
            if current.bit_length() > 1 + int(MAX_JSON_INTEGER_DIGITS * 3.322):
                raise ProjectFormatError(
                    f"{member}: integer exceeds the portable JSON numeric range"
                )
            try:
                number = float(current)
            except (OverflowError, ValueError) as exc:
                raise ProjectFormatError(
                    f"{member}: integer exceeds the finite JSON numeric range"
                ) from exc
            if not math.isfinite(number):
                raise ProjectFormatError(
                    f"{member}: integer exceeds the finite JSON numeric range"
                )
        elif isinstance(current, float):
            if not math.isfinite(current):
                raise ProjectFormatError(f"{member}: expected a finite JSON number")
        else:
            raise ProjectFormatError(
                f"{member}: value of type {type(current).__name__} is not portable JSON"
            )


def _decode_json(member: str, payload: bytes) -> JsonObject:
    try:
        text = payload.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
            parse_float=_parse_json_float,
            parse_int=_parse_json_integer,
        )
        _validate_json_tree(value, member)
    except ProjectFormatError:
        raise
    except UnicodeDecodeError as exc:
        raise ProjectFormatError(f"{member}: expected strict UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise ProjectFormatError(f"{member}: malformed JSON: {exc.msg}") from exc
    except (OverflowError, ValueError) as exc:
        raise ProjectFormatError(f"{member}: invalid JSON number: {exc}") from exc
    except RecursionError as exc:
        raise ProjectFormatError(f"{member}: JSON nesting is too deep") from exc
    if not isinstance(value, dict):
        raise ProjectFormatError(f"{member}: expected a JSON object")
    return cast(JsonObject, value)


def _schema(version: int, member: str) -> JsonObject:
    filename = member.replace(".json", ".schema.json")
    schema_resource = (
        resources.files("rc_metastudio.project_schemas")
        .joinpath(f"v{version}")
        .joinpath(filename)
    )
    try:
        payload = schema_resource.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ProjectFormatError(
            f"unsupported project format version: {version}"
        ) from exc
    return _decode_json(filename, payload.encode("utf-8"))


def _validate(version: int, member: str, value: JsonObject) -> None:
    schema = _schema(version, member)
    try:
        _validate_json_tree(value, member)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(value)
    except SchemaError as exc:
        raise ProjectFormatError(
            f"invalid committed schema for {member}: {exc.message}"
        ) from exc
    except ValidationError as exc:
        location = "/".join(str(part) for part in exc.absolute_path) or "<root>"
        raise ProjectFormatError(f"{member}:{location}: {exc.message}") from exc
    except RecursionError as exc:
        raise ProjectFormatError(
            f"{member}: schema validation exceeded nesting limits"
        ) from exc


def _canonical_json(value: Mapping[str, JsonValue]) -> bytes:
    try:
        _validate_json_tree(value, "project data")
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except ProjectFormatError:
        raise
    except (OverflowError, TypeError, ValueError, RecursionError) as exc:
        raise ProjectFormatError(f"project data is not portable JSON: {exc}") from exc


def _regular_member(info: zipfile.ZipInfo) -> bool:
    if info.is_dir():
        return False
    if info.create_system != 3:
        return True
    mode = info.external_attr >> 16
    return stat.S_IFMT(mode) in {0, stat.S_IFREG}


def _inspect_archive(
    path: Path, limits: ProjectArchiveLimits
) -> tuple[zipfile.ZipFile, dict[str, zipfile.ZipInfo]]:
    try:
        archive_size = path.stat().st_size
    except OSError as exc:
        raise ProjectFormatError(f"cannot read project: {path}") from exc
    if archive_size > limits.max_archive_size:
        raise ProjectFormatError("project archive exceeds the configured size limit")
    try:
        archive = zipfile.ZipFile(path, "r")
        infos = archive.infolist()
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ProjectFormatError("project is not a valid ZIP container") from exc

    try:
        if len(infos) > limits.max_member_count:
            raise ProjectFormatError("project archive has too many members")
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ProjectFormatError("project archive contains duplicate member names")
        if set(names) != set(_EXPECTED_MEMBERS):
            raise ProjectFormatError(
                "project archive must contain only manifest.json, project.json, and state.json"
            )
        total_size = 0
        for info in infos:
            if not _regular_member(info):
                raise ProjectFormatError(f"unsafe archive member type: {info.filename}")
            if info.flag_bits & 0x1:
                raise ProjectFormatError(
                    f"encrypted archive member is not supported: {info.filename}"
                )
            if info.compress_type not in _SUPPORTED_COMPRESSION_METHODS:
                raise ProjectFormatError(
                    f"unsupported archive compression method for member: {info.filename}"
                )
            if info.file_size > limits.max_member_size:
                raise ProjectFormatError(
                    f"archive member exceeds size limit: {info.filename}"
                )
            total_size += info.file_size
            if total_size > limits.max_total_uncompressed_size:
                raise ProjectFormatError(
                    "project archive exceeds total uncompressed size limit"
                )
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > limits.max_compression_ratio:
                raise ProjectFormatError(
                    f"archive member exceeds compression ratio limit: {info.filename}"
                )
        return archive, {info.filename: info for info in infos}
    except BaseException:
        archive.close()
        raise


def _read_members(path: Path, limits: ProjectArchiveLimits) -> dict[str, bytes]:
    archive, infos = _inspect_archive(path, limits)
    try:
        result: dict[str, bytes] = {}
        for name in _EXPECTED_MEMBERS:
            payload = archive.read(infos[name])
            if len(payload) != infos[name].file_size:
                raise ProjectFormatError(f"archive member was truncated: {name}")
            result[name] = payload
        return result
    except (
        EOFError,
        NotImplementedError,
        OSError,
        RuntimeError,
        zipfile.BadZipFile,
        zlib.error,
    ) as exc:
        raise ProjectFormatError("project archive could not be read safely") from exc
    finally:
        archive.close()


def migrate_to_latest(
    version: int,
    project: Mapping[str, JsonValue],
    state: Mapping[str, JsonValue],
) -> tuple[JsonObject, JsonObject]:
    """Apply the explicit pure migration chain for a structured format version."""
    if version > CURRENT_FORMAT_VERSION or version < 1:
        raise ProjectFormatError(f"unsupported project format version: {version}")
    try:
        migrated_project = cast(JsonObject, copy.deepcopy(dict(project)))
        migrated_state = cast(JsonObject, copy.deepcopy(dict(state)))
    except RecursionError as exc:
        raise ProjectFormatError("project migration input nesting is too deep") from exc
    while version < CURRENT_FORMAT_VERSION:
        migration = _MIGRATIONS.get(version)
        if migration is None:
            raise ProjectFormatError(
                f"no Project Format Migration from version {version}"
            )
        migrated_project, migrated_state = migration(migrated_project, migrated_state)
        version += 1
    return migrated_project, migrated_state


def load_project(
    path: str | os.PathLike[str],
    *,
    limits: ProjectArchiveLimits | None = None,
) -> ProjectDocument:
    """Read, authenticate, validate, and migrate an `.rcms` container."""
    selected_limits = limits or ProjectArchiveLimits()
    members = _read_members(Path(path), selected_limits)
    manifest = _decode_json("manifest.json", members["manifest.json"])
    version = manifest.get("format_version")
    if type(version) is not int:
        raise ProjectFormatError("manifest.json: format_version must be an integer")
    _validate(version, "manifest.json", manifest)
    if manifest.get("format") != _FORMAT_NAME:
        raise ProjectFormatError("manifest.json: unsupported project format")

    integrity = manifest["members"]
    if not isinstance(integrity, dict):
        raise ProjectFormatError("manifest.json: members must be an object")
    decoded: dict[str, JsonObject] = {}
    for member in _JSON_MEMBERS:
        expected = integrity.get(member)
        if not isinstance(expected, dict):
            raise ProjectFormatError(f"manifest.json: missing integrity for {member}")
        payload = members[member]
        if expected.get("size") != len(payload):
            raise ProjectFormatError(f"integrity size mismatch for {member}")
        if expected.get("sha256") != hashlib.sha256(payload).hexdigest():
            raise ProjectFormatError(f"integrity digest mismatch for {member}")
        value = _decode_json(member, payload)
        _validate(version, member, value)
        decoded[member] = value

    project, state = migrate_to_latest(
        version, decoded["project.json"], decoded["state.json"]
    )
    try:
        validate_project_semantics(project, state)
    except (ProjectSemanticError, RecursionError) as exc:
        raise ProjectFormatError(f"project semantics: {exc}") from exc
    return ProjectDocument(CURRENT_FORMAT_VERSION, project, state)


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=_ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100600 << 16
    return info


def _write_container(file_handle: BinaryIO, members: Mapping[str, bytes]) -> None:
    with zipfile.ZipFile(
        file_handle,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        allowZip64=False,
    ) as archive:
        for name in _EXPECTED_MEMBERS:
            archive.writestr(_zip_info(name), members[name])


def _supports_directory_fsync() -> bool:
    return os.name == "posix" and hasattr(os, "O_DIRECTORY")


def _open_directory(path: Path, flags: int) -> int:
    return os.open(path, flags)


def _close_directory(descriptor: int) -> None:
    os.close(descriptor)


def _fsync_parent_directory(destination: Path) -> None:
    if not _supports_directory_fsync():
        return
    flags = os.O_RDONLY | cast(int, getattr(os, "O_DIRECTORY", 0))
    descriptor: int | None = None
    durability_error: ProjectDurabilityError | None = None
    primary_cause: OSError | None = None
    try:
        descriptor = _open_directory(destination.parent, flags)
        os.fsync(descriptor)
    except OSError as exc:
        durability_error = ProjectDurabilityError(
            "project was atomically replaced, but directory durability could not be confirmed; the new file is already installed"
        )
        primary_cause = exc
    finally:
        if descriptor is not None:
            try:
                _close_directory(descriptor)
            except OSError as close_error:
                if durability_error is None:
                    durability_error = ProjectDurabilityError(
                        "project was atomically replaced, but closing the parent directory handle failed; directory durability is uncertain and the new file is already installed"
                    )
                    primary_cause = close_error
                else:
                    durability_error.add_note(
                        f"closing the parent directory handle also failed: {close_error}"
                    )
    if durability_error is not None:
        raise durability_error from primary_cause


def _cleanup_temporary(path: Path, primary: ProjectFormatError) -> ProjectFormatError:
    try:
        path.unlink(missing_ok=True)
    except OSError as cleanup_error:
        primary.add_note(f"temporary cleanup also failed: {cleanup_error}")
    return primary


def save_project(
    path: str | os.PathLike[str],
    project: Mapping[str, JsonValue],
    state: Mapping[str, JsonValue],
    *,
    limits: ProjectArchiveLimits | None = None,
) -> None:
    """Validate and atomically replace an `.rcms` project on its filesystem."""
    selected_limits = limits or ProjectArchiveLimits()
    try:
        project_value = cast(JsonObject, copy.deepcopy(dict(project)))
        state_value = cast(JsonObject, copy.deepcopy(dict(state)))
    except RecursionError as exc:
        raise ProjectFormatError("project data nesting is too deep") from exc
    _validate(CURRENT_FORMAT_VERSION, "project.json", project_value)
    _validate(CURRENT_FORMAT_VERSION, "state.json", state_value)
    try:
        validate_project_semantics(project_value, state_value)
    except (ProjectSemanticError, RecursionError) as exc:
        raise ProjectFormatError(f"project semantics: {exc}") from exc
    project_payload = _canonical_json(project_value)
    state_payload = _canonical_json(state_value)
    manifest: JsonObject = {
        "application": {"name": "RC MetaStudio", "version": __version__},
        "format": _FORMAT_NAME,
        "format_version": CURRENT_FORMAT_VERSION,
        "members": {
            "project.json": {
                "sha256": hashlib.sha256(project_payload).hexdigest(),
                "size": len(project_payload),
            },
            "state.json": {
                "sha256": hashlib.sha256(state_payload).hexdigest(),
                "size": len(state_payload),
            },
        },
    }
    _validate(CURRENT_FORMAT_VERSION, "manifest.json", manifest)
    members = {
        "manifest.json": _canonical_json(manifest),
        "project.json": project_payload,
        "state.json": state_payload,
    }

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            _write_container(cast(BinaryIO, temporary), members)
            temporary.flush()
            os.fsync(temporary.fileno())
        load_project(temporary_path, limits=selected_limits)
        os.replace(temporary_path, destination)
        temporary_path = None
        _fsync_parent_directory(destination)
    except Exception as exc:
        error = (
            exc
            if isinstance(exc, ProjectFormatError)
            else ProjectFormatError(f"could not save project atomically: {exc}")
        )
        if temporary_path is not None:
            error = _cleanup_temporary(temporary_path, error)
        if error is exc:
            raise
        raise error from exc
