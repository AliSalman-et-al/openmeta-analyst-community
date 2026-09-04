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
from rc_metastudio import project_adapter
from rc_metastudio.project_domain import JsonObject, JsonValue
from rc_metastudio.project_format import (
    ProjectDocument,
    ProjectDurabilityError,
)

RuntimeProject = project_adapter.RuntimeProject
InstallRuntime = Callable[[RuntimeProject], None]


@dataclass(frozen=True, slots=True)
class WorkspaceChange:
    """One complete before/after replacement in the durable workspace."""

    before: RuntimeProject
    after: RuntimeProject


def _copy_runtime(runtime: RuntimeProject) -> RuntimeProject:
    return copy.deepcopy(runtime)


def _document_digest(document: ProjectDocument) -> str:
    payload = json.dumps(
        {"project": document.project, "state": document.state},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validated_runtime(document: ProjectDocument) -> RuntimeProject:
    return project_adapter.document_to_runtime_project(document)


class WorkspaceSession:
    """Own project replacement, persistence, and undo/redo independently of Qt."""

    def __init__(
        self, document: ProjectDocument | None = None, path: str | Path | None = None
    ) -> None:
        self._runtime = _validated_runtime(document) if document is not None else None
        self._checkpoint = _copy_runtime(self._runtime) if self._runtime else None
        self._path = Path(path) if path is not None else None
        self._history: list[WorkspaceChange] = []
        self._redo: list[WorkspaceChange] = []
        self._forced_dirty = False
        self._transaction_checkpoint: RuntimeProject | None = None
        document = self.document
        self._saved_digest = _document_digest(document) if document else None

    @property
    def document(self) -> ProjectDocument | None:
        if self._runtime is None:
            return None
        try:
            return project_adapter.runtime_project_to_document(self._runtime)
        except project_adapter.ProjectAdapterError:
            return None

    @property
    def project(self) -> JsonObject | None:
        document = self.document
        return copy.deepcopy(document.project) if document else None

    @property
    def state(self) -> JsonObject | None:
        document = self.document
        return copy.deepcopy(document.state) if document else None

    @property
    def runtime(self) -> RuntimeProject | None:
        """Return the canonical live runtime graph owned by this session."""
        return self._runtime

    def snapshot(self) -> RuntimeProject:
        """Return an isolated runtime checkpoint for a dialog or command."""
        if self._runtime is None:
            raise ValueError("cannot snapshot an empty workspace")
        return _copy_runtime(self._runtime)

    def update_live_state(self, runtime: RuntimeProject) -> None:
        """Update the canonical live graph without creating history."""
        if self._runtime is None:
            self._runtime = runtime
            self._checkpoint = _copy_runtime(runtime)
            self._saved_digest = None
            return
        if self._runtime is not runtime:
            self._runtime = runtime

    def checkpoint(self, expected_digest: str | None = None) -> None:
        """Record one live mutation after its adapter boundary has completed."""
        if self._runtime is None:
            return
        try:
            current_digest = self._runtime_digest()
        except project_adapter.ProjectAdapterError:
            self._forced_dirty = True
            return
        if expected_digest is not None and expected_digest == self._saved_digest:
            self._saved_digest = current_digest
        if self._transaction_checkpoint is not None:
            return
        assert self._checkpoint is not None
        if current_digest == self._checkpoint_digest():
            return
        before = _copy_runtime(self._checkpoint)
        after = _copy_runtime(self._runtime)
        self._history.append(WorkspaceChange(before, after))
        self._redo.clear()
        self._checkpoint = _copy_runtime(self._runtime)

    def begin_change(self) -> None:
        """Start one atomic UI operation."""
        if self._runtime is None:
            raise ValueError("cannot edit an empty workspace")
        if self._transaction_checkpoint is None:
            self._transaction_checkpoint = _copy_runtime(self._runtime)

    def end_change(self) -> None:
        """Publish the current graph as one history entry."""
        checkpoint = self._transaction_checkpoint
        self._transaction_checkpoint = None
        if checkpoint is None or self._runtime is None:
            return
        try:
            current_digest = self._runtime_digest()
            checkpoint_digest = _document_digest(
                project_adapter.runtime_project_to_document(checkpoint)
            )
        except project_adapter.ProjectAdapterError:
            self._forced_dirty = True
            self._checkpoint = _copy_runtime(self._runtime)
            return
        if checkpoint_digest == current_digest:
            self._checkpoint = _copy_runtime(self._runtime)
            return
        self._history.append(WorkspaceChange(checkpoint, _copy_runtime(self._runtime)))
        self._redo.clear()
        self._checkpoint = _copy_runtime(self._runtime)

    def _runtime_digest(self) -> str:
        assert self._runtime is not None
        return _document_digest(
            project_adapter.runtime_project_to_document(self._runtime)
        )

    @property
    def runtime_digest(self) -> str | None:
        return self._runtime_digest() if self._runtime is not None else None

    def _checkpoint_digest(self) -> str:
        assert self._checkpoint is not None
        return _document_digest(
            project_adapter.runtime_project_to_document(self._checkpoint)
        )

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def is_dirty(self) -> bool:
        if self._runtime is None:
            return self._forced_dirty
        if self._forced_dirty:
            return True
        try:
            return self._runtime_digest() != self._saved_digest
        except project_adapter.ProjectAdapterError:
            return True

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
        candidate = _validated_runtime(document)
        previous = self._runtime
        if previous is not None and record_history:
            self._history.append(WorkspaceChange(_copy_runtime(previous), candidate))
            self._redo.clear()
        self._runtime = candidate
        self._checkpoint = _copy_runtime(candidate)
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
        self, path: str | Path, *, install: InstallRuntime | None = None
    ) -> ProjectDocument:
        """Decode and validate before replacing the current project.

        ``install`` is a narrow adapter seam: callers may install the validated
        candidate in another representation before this session commits it.
        If installation fails, this session remains untouched.
        """
        candidate = _validated_runtime(project_format.load_project(path))
        if install is not None:
            previous_runtime = self._runtime
            previous_checkpoint = (
                _copy_runtime(self._checkpoint) if self._checkpoint else None
            )
            previous_path = self._path
            previous_history = copy.deepcopy(self._history)
            previous_redo = copy.deepcopy(self._redo)
            previous_saved_digest = self._saved_digest
            previous_forced_dirty = self._forced_dirty
            try:
                install(candidate)
            except Exception:
                self._runtime = previous_runtime
                self._checkpoint = previous_checkpoint
                self._path = previous_path
                self._history = previous_history
                self._redo = previous_redo
                self._saved_digest = previous_saved_digest
                self._forced_dirty = previous_forced_dirty
                raise
        self._runtime = candidate
        self._checkpoint = _copy_runtime(candidate)
        self._path = Path(path)
        self._history.clear()
        self._redo.clear()
        self._saved_digest = self._runtime_digest()
        self._checkpoint = _copy_runtime(self._runtime)
        self._forced_dirty = False
        loaded = self.document
        if loaded is None:
            raise RuntimeError(
                "workspace replacement unexpectedly produced no document"
            )
        return loaded

    def new(self, document: ProjectDocument, path: str | Path | None = None) -> None:
        candidate = _validated_runtime(document)
        self._runtime = candidate
        self._checkpoint = _copy_runtime(candidate)
        self._path = Path(path) if path is not None else None
        self._history.clear()
        self._redo.clear()
        self._saved_digest = self._runtime_digest()
        self._forced_dirty = False

    def save(
        self,
        path: str | Path | None = None,
    ) -> Path:
        """Persist the canonical live runtime without changing its identity."""
        current = self._runtime
        if current is None:
            raise ValueError("cannot save an empty workspace")
        destination = Path(path) if path is not None else self._path
        if destination is None:
            raise ValueError("save path is required for an unnamed workspace")
        serialized = project_adapter.runtime_project_to_document(current)
        try:
            project_format.save_project(
                destination, serialized.project, serialized.state
            )
        except ProjectDurabilityError:
            self._path = destination
            self._saved_digest = self._runtime_digest()
            self._checkpoint = _copy_runtime(current)
            self._forced_dirty = False
            raise
        self._path = destination
        self._saved_digest = self._runtime_digest()
        self._forced_dirty = False
        return destination

    def mark_saved(self) -> None:
        if self._runtime is None:
            raise ValueError("cannot mark an empty workspace as saved")
        self._saved_digest = self._runtime_digest()
        self._checkpoint = _copy_runtime(self._runtime)
        self._forced_dirty = False

    def mark_dirty(self) -> None:
        """Mark the current document dirty when an adapter changes its view state."""
        self._forced_dirty = True

    def undo(self) -> bool:
        if not self._history or self._runtime is None:
            return False
        change = self._history.pop()
        self._redo.append(
            WorkspaceChange(_copy_runtime(change.after), _copy_runtime(self._runtime))
        )
        self._runtime = _copy_runtime(change.before)
        self._checkpoint = _copy_runtime(self._runtime)
        self._forced_dirty = False
        return True

    def redo(self) -> bool:
        if not self._redo or self._runtime is None:
            return False
        change = self._redo.pop()
        self._history.append(
            WorkspaceChange(_copy_runtime(self._runtime), _copy_runtime(change.before))
        )
        self._runtime = _copy_runtime(change.before)
        self._checkpoint = _copy_runtime(self._runtime)
        self._forced_dirty = False
        return True

    def mutate(self, edit: Callable[[JsonObject, JsonObject], None]) -> None:
        """Apply a pure boundary edit and publish it as one coherent change."""
        if self._runtime is None:
            raise ValueError("cannot edit an empty workspace")
        document = self.document
        assert document is not None
        project = copy.deepcopy(document.project)
        state = copy.deepcopy(document.state)
        edit(project, state)
        self.commit(project, state)
