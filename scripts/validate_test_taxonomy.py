"""Validate the pytest verification taxonomy manifest against collected tests."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import cast


DEFAULT_MANIFEST = Path("docs") / "verification" / "test-taxonomy.json"
VALID_SIZES = {"small", "medium", "large"}
VALID_LANES = {
    "fast",
    "gui",
    "r_stack",
    "golden",
    "packaging_contract",
    "packaged_smoke",
}
VALID_EVIDENCE = {
    "analysis_behavior",
    "gui_compatibility",
    "r_stack",
    "golden",
    "packaging_contract",
    "release_readiness",
}
VALID_RUNTIME_CLASSES = {"subsecond", "seconds", "minutes", "unknown"}
VALID_DECISIONS = {"keep", "rewrite", "remove", "merge", "move"}


class TaxonomyError(Exception):
    pass


def load_manifest(root: Path, manifest_path: Path) -> dict:
    path = manifest_path if manifest_path.is_absolute() else root / manifest_path
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TaxonomyError(f"missing taxonomy manifest: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise TaxonomyError(f"{manifest_path}: invalid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise TaxonomyError(f"{manifest_path}: expected a JSON object")
    return manifest


def require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise TaxonomyError(f"{label}: expected a non-empty string")
    return value


def require_list(value: object, label: str) -> list:
    if not isinstance(value, list):
        raise TaxonomyError(f"{label}: expected a list")
    return value


def validate_entry(entry: object, index: int) -> str:
    if not isinstance(entry, dict):
        raise TaxonomyError(f"tests[{index}]: expected an object")
    entry = cast(dict[str, object], entry)
    nodeid = require_string(entry.get("nodeid"), f"tests[{index}].nodeid").replace(
        "\\", "/"
    )
    size = require_string(entry.get("size"), f"{nodeid}.size")
    if size not in VALID_SIZES:
        raise TaxonomyError(
            f"{nodeid}.size: expected one of {', '.join(sorted(VALID_SIZES))}"
        )
    lane = require_string(entry.get("lane"), f"{nodeid}.lane")
    if lane not in VALID_LANES:
        raise TaxonomyError(
            f"{nodeid}.lane: expected one of {', '.join(sorted(VALID_LANES))}"
        )
    evidence = require_list(entry.get("evidence"), f"{nodeid}.evidence")
    if not evidence:
        raise TaxonomyError(f"{nodeid}.evidence: expected at least one evidence value")
    invalid_evidence = sorted(set(evidence) - VALID_EVIDENCE)
    if invalid_evidence:
        raise TaxonomyError(
            f"{nodeid}.evidence: invalid values {', '.join(invalid_evidence)}"
        )
    require_list(entry.get("external_dependencies"), f"{nodeid}.external_dependencies")
    runtime_class = require_string(
        entry.get("runtime_class"), f"{nodeid}.runtime_class"
    )
    if runtime_class not in VALID_RUNTIME_CLASSES:
        raise TaxonomyError(
            f"{nodeid}.runtime_class: expected one of {', '.join(sorted(VALID_RUNTIME_CLASSES))}"
        )
    decision = require_string(entry.get("decision"), f"{nodeid}.decision")
    if decision not in VALID_DECISIONS:
        raise TaxonomyError(
            f"{nodeid}.decision: expected one of {', '.join(sorted(VALID_DECISIONS))}"
        )
    require_string(entry.get("reason"), f"{nodeid}.reason")
    return nodeid


def taxonomy_nodeids(manifest: dict) -> set[str]:
    if manifest.get("manifest") != "verification-test-taxonomy":
        raise TaxonomyError("manifest must be verification-test-taxonomy")
    if manifest.get("schema_version") != 1:
        raise TaxonomyError("schema_version must be 1")
    tests = require_list(manifest.get("tests"), "tests")
    nodeids: set[str] = set()
    for index, entry in enumerate(tests):
        nodeid = validate_entry(entry, index)
        if nodeid in nodeids:
            raise TaxonomyError(f"duplicate taxonomy nodeid: {nodeid}")
        nodeids.add(nodeid)
    return nodeids


def collect_pytest_nodeids(root: Path, tests_path: str) -> set[str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", tests_path, "--collect-only", "-q"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise TaxonomyError(
            "pytest collection failed with exit code %s\nSTDOUT:\n%s\nSTDERR:\n%s"
            % (result.returncode, result.stdout, result.stderr)
        )
    nodeids = set()
    for line in result.stdout.splitlines():
        line = line.strip().replace("\\", "/")
        if line.startswith("tests/") and "::" in line:
            nodeids.add(line)
    return nodeids


def validate(
    root: Path, manifest_path: Path, tests_path: str, strict: bool
) -> tuple[set[str], set[str]]:
    manifest_nodeids = taxonomy_nodeids(load_manifest(root, manifest_path))
    collected_nodeids = collect_pytest_nodeids(root, tests_path)
    missing = collected_nodeids - manifest_nodeids
    stale = manifest_nodeids - collected_nodeids
    if strict and (missing or stale):
        details = []
        if missing:
            details.append("missing taxonomy entries:\n" + "\n".join(sorted(missing)))
        if stale:
            details.append("stale taxonomy entries:\n" + "\n".join(sorted(stale)))
        raise TaxonomyError("\n\n".join(details))
    return missing, stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--tests-path", default="tests")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--require-covered",
        action="store_true",
        help="fail on collected tests missing from the manifest while allowing stale entries",
    )
    args = parser.parse_args(argv)

    try:
        missing, stale = validate(
            args.root.resolve(), args.manifest, args.tests_path, args.strict
        )
        if args.require_covered and missing:
            raise TaxonomyError(
                "missing taxonomy entries:\n" + "\n".join(sorted(missing))
            )
    except TaxonomyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if missing:
        print("taxonomy warning: missing entries")
        for nodeid in sorted(missing):
            print(f"  {nodeid}")
    if stale and not args.require_covered:
        print("taxonomy warning: stale entries")
        for nodeid in sorted(stale):
            print(f"  {nodeid}")
    if args.require_covered and not missing:
        print("collected tests are covered by the verification taxonomy")
    elif not missing and not stale:
        print("validated verification test taxonomy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
