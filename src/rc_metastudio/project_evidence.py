"""Forward-only validation of converted sample Analysis Behavior evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, cast
import zipfile

from rc_metastudio.project_format import load_project, reconstruct_analysis_dataset


EVIDENCE_PATH = Path("docs/verification/pre-qt6-baseline/sample-analysis-evidence.json")
GOLDEN_BUNDLE_PATH = Path(
    "docs/verification/pre-qt6-baseline/observed-golden-baseline.zip"
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json_object(payload: bytes, label: str) -> dict[str, Any]:
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label}: expected a JSON object")
    return cast(dict[str, Any], value)


def _git_blob(root: Path, commit: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"cannot read frozen Git blob {commit}:{path}")
    return result.stdout


def _capture_payloads(
    root: Path,
    capture: dict[str, Any],
    golden: zipfile.ZipFile,
) -> tuple[dict[str, Any], bytes]:
    if capture["kind"] == "authoritative-bundle":
        record = _json_object(golden.read(capture["record"]), capture["record"])
        artifact = golden.read(capture["artifact"])
        return record, artifact
    record_path = root / capture["record"]
    artifact_path = root / capture["artifact"]
    return _json_object(
        record_path.read_bytes(), str(record_path)
    ), artifact_path.read_bytes()


def validate_sample_analysis_evidence(root: Path) -> list[str]:
    """Validate semantic and observed-analysis evidence without Qt or pickle."""

    errors: list[str] = []
    try:
        manifest = _json_object((root / EVIDENCE_PATH).read_bytes(), str(EVIDENCE_PATH))
        source_commit = cast(str, manifest["source_commit"])
        samples = cast(list[dict[str, Any]], manifest["samples"])
        sample_manifest = _json_object(
            (root / "sample_projects" / "manifest.json").read_bytes(),
            "sample_projects/manifest.json",
        )
        sample_metadata = {
            cast(str, value["file"]): value
            for value in cast(list[dict[str, Any]], sample_manifest["projects"])
        }
        expected_projects = sorted(
            path.name for path in (root / "sample_projects").glob("*.rcms")
        )
        observed_projects = sorted(cast(str, item["project"]) for item in samples)
        if observed_projects != expected_projects:
            errors.append(
                "sample analysis evidence does not cover every committed project"
            )

        with zipfile.ZipFile(root / GOLDEN_BUNDLE_PATH) as golden:
            golden_manifest = _json_object(
                golden.read("manifest.json"), "golden manifest"
            )
            if golden_manifest.get("passed") is not True:
                errors.append("authoritative Golden bundle did not pass")
            for item in samples:
                project_name = cast(str, item["project"])
                label = f"sample {project_name}"
                snapshot = _json_object(
                    (root / cast(str, item["snapshot"])).read_bytes(),
                    cast(str, item["snapshot"]),
                )
                if snapshot.get("baseline_commit") != source_commit:
                    errors.append(f"{label}: snapshot commit does not match evidence")
                legacy_digest = cast(str, item["legacy_source_sha256"])
                if snapshot.get("source_sha256") != legacy_digest:
                    errors.append(
                        f"{label}: snapshot legacy digest does not match evidence"
                    )
                frozen_payload = _git_blob(
                    root, source_commit, f"sample_projects/{project_name}"
                )
                if _sha256(frozen_payload) != legacy_digest:
                    errors.append(
                        f"{label}: frozen project blob does not match snapshot"
                    )

                document = load_project(root / "sample_projects" / project_name)
                reconstructed = reconstruct_analysis_dataset(document)
                semantic_digest = cast(str, item["semantic_sha256"])
                if (
                    sample_metadata[project_name].get("semantic_sha256")
                    != semantic_digest
                ):
                    errors.append(
                        f"{label}: sample manifest semantic digest does not match"
                    )
                if reconstructed.semantic_sha256 != semantic_digest:
                    errors.append(f"{label}: converted semantic digest does not match")
                snapshot_dataset = cast(dict[str, Any], snapshot["dataset"])
                snapshot_payload = (
                    json.dumps(
                        snapshot_dataset,
                        allow_nan=False,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    + "\n"
                ).encode("utf-8")
                if _sha256(snapshot_payload) != semantic_digest:
                    errors.append(f"{label}: snapshot semantic digest does not match")

                capture_spec = cast(dict[str, Any], item["capture"])
                record, artifact = _capture_payloads(root, capture_spec, golden)
                capture_id = cast(str, capture_spec["id"])
                if sample_metadata[project_name].get("analysis_evidence") != capture_id:
                    errors.append(f"{label}: sample manifest capture id does not match")
                if record.get("id") != capture_id:
                    errors.append(f"{label}: capture id does not match")
                if record.get("dataset") != project_name:
                    errors.append(f"{label}: capture input project does not match")
                if record.get("commit_sha") != source_commit:
                    errors.append(f"{label}: capture commit does not match")
                if record.get("status") != "success":
                    errors.append(f"{label}: representative analysis did not succeed")
                if (
                    record.get("authoritative") is not True
                    or record.get("authority") != "authoritative"
                ):
                    errors.append(f"{label}: capture is not authoritative")
                outputs = record.get("outputs")
                if not isinstance(outputs, dict) or not outputs:
                    errors.append(f"{label}: capture has no observed numeric output")
                texts = record.get("texts")
                if not isinstance(texts, dict) or not any(
                    isinstance(value, str) and value.strip() for value in texts.values()
                ):
                    errors.append(f"{label}: capture has no observed text output")
                artifact_digest = _sha256(artifact)
                if not artifact.startswith(b"\x89PNG\r\n\x1a\n"):
                    errors.append(f"{label}: plot evidence is not a PNG")
                artifact_records = record.get("artifacts")
                if not isinstance(artifact_records, list) or artifact_digest not in {
                    value.get("sha256")
                    for value in artifact_records
                    if isinstance(value, dict)
                }:
                    errors.append(f"{label}: plot digest does not match capture")
                if capture_spec["kind"] == "supplemental-authoritative":
                    if record.get("dataset_semantic_sha256") != semantic_digest:
                        errors.append(
                            f"{label}: supplemental capture semantic digest does not match"
                        )
                    environment = record.get("baseline_environment")
                    if (
                        not isinstance(environment, dict)
                        or environment.get("matches_expected") is not True
                    ):
                        errors.append(
                            f"{label}: supplemental baseline environment is not authoritative"
                        )
                    if not record.get("capture_identity_attestation"):
                        errors.append(
                            f"{label}: supplemental identity attestation is missing"
                        )
    except (KeyError, OSError, ValueError, zipfile.BadZipFile) as exc:
        errors.append(f"sample analysis evidence could not be validated: {exc}")
    return errors
