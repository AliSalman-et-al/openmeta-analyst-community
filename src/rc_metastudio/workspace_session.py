# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qt-free ownership of the active project and its undo history."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from rc_metastudio import project_format
from rc_metastudio.project_domain import JsonObject, JsonValue
from rc_metastudio.project_format import (
    ProjectDocument,
    ProjectDurabilityError,
    reconstruct_analysis_dataset,
)

InstallDocument = Callable[[ProjectDocument], None]


@dataclass(frozen=True, slots=True)
class WorkspaceChange:
    """One complete before/after replacement in the durable workspace."""

    before: ProjectDocument
    after: ProjectDocument


def _copy_document(document: ProjectDocument) -> ProjectDocument:
    return ProjectDocument(
        document.format_version,
        copy.deepcopy(document.project),
        copy.deepcopy(document.state),
    )


def _document_digest(document: ProjectDocument) -> str:
    payload = json.dumps(
        {"project": document.project, "state": document.state},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validated_document(document: ProjectDocument) -> ProjectDocument:
    candidate = _copy_document(document)
    reconstruct_analysis_dataset(candidate)
    return candidate


class WorkspaceSession:
    """Own project replacement, persistence, and undo/redo independently of Qt."""

    def __init__(
        self, document: ProjectDocument | None = None, path: str | Path | None = None
    ) -> None:
        self._document = _copy_document(document) if document is not None else None
        self._path = Path(path) if path is not None else None
        if self._document is not None:
            reconstruct_analysis_dataset(self._document)
        self._history: list[WorkspaceChange] = []
        self._redo: list[WorkspaceChange] = []
        self._forced_dirty = False
        self._saved_digest = (
            _document_digest(self._document) if self._document is not None else None
        )

    @property
    def document(self) -> ProjectDocument | None:
        return _copy_document(self._document) if self._document is not None else None

    @property
    def project(self) -> JsonObject | None:
        return copy.deepcopy(self._document.project) if self._document else None

    @property
    def state(self) -> JsonObject | None:
        return copy.deepcopy(self._document.state) if self._document else None

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def is_dirty(self) -> bool:
        if self._document is None:
            return self._forced_dirty
        return self._forced_dirty or _document_digest(self._document) != self._saved_digest

    @property
    def can_undo(self) -> bool:
        return bool(self._history)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def replace(
        self,
        document: ProjectDocument,
        *,
        path: str | Path | None = None,
        record_history: bool = True,
    ) -> None:
        """Validate all replacement data before changing the live workspace."""
        candidate = _validated_document(document)
        previous = self._document
        if previous is not None and record_history:
            self._history.append(WorkspaceChange(_copy_document(previous), candidate))
            self._redo.clear()
        self._document = candidate
        if path is not None:
            self._path = Path(path)

    def commit(
        self,
        project: Mapping[str, JsonValue],
        state: Mapping[str, JsonValue],
    ) -> None:
        """Publish one validated project/state pair as one undoable change."""
        self.replace(ProjectDocument(1, dict(project), dict(state)))

    def open(
        self, path: str | Path, *, install: InstallDocument | None = None
    ) -> ProjectDocument:
        """Decode and validate before replacing the current project.

        ``install`` is a narrow adapter seam: callers may install the validated
        candidate in another representation before this session commits it.
        If installation fails, this session remains untouched.
        """
        candidate = _validated_document(project_format.load_project(path))
        if install is not None:
            previous_document = (
                _copy_document(self._document) if self._document is not None else None
            )
            previous_path = self._path
            previous_history = copy.deepcopy(self._history)
            previous_redo = copy.deepcopy(self._redo)
            previous_saved_digest = self._saved_digest
            previous_forced_dirty = self._forced_dirty
            try:
                install(_copy_document(candidate))
            except Exception:
                self._document = previous_document
                self._path = previous_path
                self._history = previous_history
                self._redo = previous_redo
                self._saved_digest = previous_saved_digest
                self._forced_dirty = previous_forced_dirty
                raise
        self._document = candidate
        self._path = Path(path)
        self._history.clear()
        self._redo.clear()
        self._saved_digest = _document_digest(candidate)
        self._forced_dirty = False
        loaded = self.document
        if loaded is None:
            raise RuntimeError("workspace replacement unexpectedly produced no document")
        return loaded

    def new(
        self, document: ProjectDocument, path: str | Path | None = None
    ) -> None:
        candidate = _validated_document(document)
        self._document = candidate
        self._path = Path(path) if path is not None else None
        self._history.clear()
        self._redo.clear()
        self._saved_digest = _document_digest(candidate)
        self._forced_dirty = False

    def save(
        self,
        path: str | Path | None = None,
        *,
        document: ProjectDocument | None = None,
    ) -> Path:
        """Persist one validated document and publish it only after replacement.

        A document supplied by an adapter is validated and written as one
        transaction.  ``ProjectDurabilityError`` means the replacement already
        happened, so the in-memory save metadata is committed before the error
        is re-raised for the UI to report.
        """
        current = self._document
        if current is None and document is None:
            raise ValueError("cannot save an empty workspace")
        destination = Path(path) if path is not None else self._path
        if destination is None:
            raise ValueError("save path is required for an unnamed workspace")
        if document is not None:
            candidate = _validated_document(document)
        else:
            assert current is not None
            candidate = _copy_document(current)
        try:
            project_format.save_project(destination, candidate.project, candidate.state)
        except ProjectDurabilityError:
            self._document = candidate
            self._path = destination
            self._saved_digest = _document_digest(candidate)
            self._forced_dirty = False
            raise
        self._document = candidate
        self._path = destination
        self._saved_digest = _document_digest(candidate)
        self._forced_dirty = False
        return destination

    def mark_saved(self) -> None:
        if self._document is None:
            raise ValueError("cannot mark an empty workspace as saved")
        self._saved_digest = _document_digest(self._document)
        self._forced_dirty = False

    def mark_dirty(self) -> None:
        """Mark the current document dirty when an adapter changes its view state."""
        self._forced_dirty = True

    def undo(self) -> bool:
        if not self._history or self._document is None:
            return False
        change = self._history.pop()
        self._redo.append(WorkspaceChange(_copy_document(change.after), _copy_document(self._document)))
        self._document = _copy_document(change.before)
        return True

    def redo(self) -> bool:
        if not self._redo or self._document is None:
            return False
        change = self._redo.pop()
        self._history.append(WorkspaceChange(_copy_document(self._document), _copy_document(change.before)))
        self._document = _copy_document(change.before)
        return True

    def mutate(self, edit: Callable[[JsonObject, JsonObject], None]) -> None:
        """Apply a pure boundary edit and publish it as one coherent change."""
        if self._document is None:
            raise ValueError("cannot edit an empty workspace")
        project = copy.deepcopy(self._document.project)
        state = copy.deepcopy(self._document.state)
        edit(project, state)
        self.commit(project, state)
