# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qt-free ownership of the active project and its undo history."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import copy
import hashlib
import json
from pathlib import Path

from rc_metastudio.project_domain import JsonObject, JsonValue
from rc_metastudio.project_format import (
    ProjectDocument,
    load_project,
    reconstruct_analysis_dataset,
    save_project,
)


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
        candidate = _copy_document(document)
        reconstruct_analysis_dataset(candidate)
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

    def open(self, path: str | Path) -> ProjectDocument:
        """Decode and validate before replacing the current project."""
        candidate = load_project(path)
        reconstruct_analysis_dataset(candidate)
        self.replace(candidate, path=path, record_history=False)
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
        self.replace(document, path=path, record_history=False)
        self._path = Path(path) if path is not None else None
        self._history.clear()
        self._redo.clear()
        self._saved_digest = _document_digest(document)
        self._forced_dirty = False

    def save(self, path: str | Path | None = None) -> Path:
        if self._document is None:
            raise ValueError("cannot save an empty workspace")
        destination = Path(path) if path is not None else self._path
        if destination is None:
            raise ValueError("save path is required for an unnamed workspace")
        save_project(destination, self._document.project, self._document.state)
        self._path = destination
        self._saved_digest = _document_digest(self._document)
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
