"""Qt-free workspace ownership contracts."""

from pathlib import Path

import pytest

from rc_metastudio.project_format import load_project
from rc_metastudio.workspace_session import WorkspaceSession


ROOT = Path(__file__).resolve().parents[3]


def test_session_replaces_and_undoes_one_complete_snapshot() -> None:
    document = load_project(ROOT / "sample_projects" / "amino.rcms")
    session = WorkspaceSession(document)
    project = session.project
    state = session.state
    assert project is not None and state is not None
    dataset = project["dataset"]
    assert isinstance(dataset, dict)
    dataset["title"] = "Edited"

    session.commit(project, state)

    assert session.is_dirty
    assert session.undo()
    assert not session.is_dirty
    assert session.redo()
    edited = session.project
    assert edited is not None and isinstance(edited["dataset"], dict)
    assert edited["dataset"]["title"] == "Edited"


def test_failed_open_preserves_document_history_and_path(tmp_path: Path) -> None:
    document = load_project(ROOT / "sample_projects" / "amino.rcms")
    session = WorkspaceSession(document, ROOT / "sample_projects" / "amino.rcms")
    before = session.project
    bad = tmp_path / "invalid.rcms"
    bad.write_bytes(b"not an rcms archive")

    with pytest.raises(ValueError):
        session.open(bad)

    assert session.project == before
    assert session.path == ROOT / "sample_projects" / "amino.rcms"
    assert not session.is_dirty


def test_save_marks_only_successfully_written_snapshot_clean(tmp_path: Path) -> None:
    document = load_project(ROOT / "sample_projects" / "continuous.rcms")
    session = WorkspaceSession(document)
    project = session.project
    state = session.state
    assert project is not None and state is not None
    dataset = project["dataset"]
    assert isinstance(dataset, dict)
    dataset["title"] = "Saved"
    session.commit(project, state)
    destination = tmp_path / "saved.rcms"

    assert session.save(destination) == destination
    assert not session.is_dirty
    saved = load_project(destination).project
    assert isinstance(saved["dataset"], dict)
    assert saved["dataset"]["title"] == "Saved"
