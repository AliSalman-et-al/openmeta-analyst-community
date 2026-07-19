"""Deterministically identify the Git worktree used to construct a package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


def _git(repo: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return completed.stdout


def _frame(digest: "hashlib._Hash", label: bytes, value: bytes) -> None:
    digest.update(len(label).to_bytes(8, "big"))
    digest.update(label)
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def collect_source_provenance(repo: Path) -> dict[str, object]:
    repo = repo.resolve()
    head = _git(repo, "rev-parse", "HEAD").decode("ascii").strip()
    if len(head) != 40 or any(character not in "0123456789abcdef" for character in head):
        raise RuntimeError("Git did not return a full lowercase HEAD SHA")
    diff = _git(repo, "diff", "--binary", "--full-index", "HEAD")
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    untracked = sorted(path for path in untracked if path)
    digest = hashlib.sha256()
    _frame(digest, b"head", head.encode("ascii"))
    _frame(digest, b"tracked-diff", diff)
    for relative in untracked:
        path = repo / os.fsdecode(relative)
        stat = path.lstat()
        if path.is_symlink():
            payload = os.fsencode(os.readlink(path))
            kind = b"symlink"
        elif path.is_file():
            payload = path.read_bytes()
            kind = b"file"
        else:
            raise RuntimeError(f"untracked path is not a regular file or symlink: {path}")
        _frame(digest, b"untracked-path", relative)
        _frame(digest, b"untracked-kind", kind)
        _frame(digest, b"untracked-mode", str(stat.st_mode).encode("ascii"))
        _frame(digest, b"untracked-contents", payload)
    dirty = bool(diff or untracked)
    return {
        "schema_version": 1,
        "head_sha": head,
        "working_tree": "dirty" if dirty else "clean",
        "worktree_sha256": digest.hexdigest(),
    }


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.dumps(collect_source_provenance(args.repo), sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
