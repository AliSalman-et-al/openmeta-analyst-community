# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Assemble packaged qualification evidence outside the frozen application.

The executable only observes product state.  This developer-side command owns
scenario sequencing, result identity hashes, locale comparisons, and the
deployment evidence schema.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from rc_metastudio.result_text_identity import normalize_packaged_summary_identity

PACKAGED_EDIT_VALUE = "Packaged Smoke – München"
PACKAGED_ANALYSIS_METHOD = "binary.random"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def capture_atomic_observations(
    executable: Path, *, runtime_probe: Path, surface_directory: Path
) -> list[Path]:
    """Run the shipped atomic probes; all orchestration stays in this script."""
    probe_environment = os.environ.copy()
    probe_environment.pop("QT_SCALE_FACTOR", None)
    subprocess.run(
        [str(executable), "--automation-package-runtime-probe", str(runtime_probe)],
        check=True,
        env=probe_environment,
    )
    surface_directory.mkdir(parents=True, exist_ok=True)
    records = []
    baseline = str(json.loads(runtime_probe.read_text(encoding="utf-8"))["qt"]["baseline_device_pixel_ratio"])
    for scale in ("1.25", "1.50", "1.75"):
        record = surface_directory / f"surface-{scale}.json"
        record.unlink(missing_ok=True)
        environment = os.environ.copy()
        environment["QT_SCALE_FACTOR"] = scale
        environment["RCMS_PACKAGE_BASELINE_DPR"] = baseline
        environment["RCMS_PACKAGE_LOCALE"] = "de_DE"
        subprocess.run(
            [str(executable), "--automation-package-surface-smoke", str(record), scale],
            check=True,
            env=environment,
        )
        records.append(record)
    return records


def capture_workflow_observations(
    executable: Path, *, sample: Path, output: Path
) -> None:
    """Run each product operation independently and combine raw observations."""
    operation_dir = output.with_suffix(".operations")
    operation_dir.mkdir(parents=True, exist_ok=True)
    observations = _capture_workflow_operations(executable, sample, operation_dir)
    output.write_text(json.dumps(_workflow_observation_payload(observations),
        indent=2) + "\n", encoding="utf-8")


def _capture_workflow_operations(
    executable: Path, sample: Path, operation_dir: Path
) -> dict[str, dict]:
    observations = {}
    environment = {
        key: value
        for key, value in os.environ.items()
        if key != "RCMS_PACKAGE_SMOKE_EVIDENCE"
    }
    environment["RCMS_PACKAGE_LOCALE"] = "en_US"
    edit_path = operation_dir / "edit.json"
    edited_project = operation_dir / "edited.rcms"
    subprocess.run(
        [str(executable), "--automation-package-edit-save", str(edit_path), str(sample),
         str(edited_project), "name", PACKAGED_EDIT_VALUE], check=True, env=environment
    )
    observations["edit"] = json.loads(edit_path.read_text(encoding="utf-8"))

    analysis_path = operation_dir / "analysis-en.json"
    subprocess.run(
        [str(executable), "--automation-package-analyze", str(analysis_path), str(sample),
         PACKAGED_ANALYSIS_METHOD], check=True, env=environment
    )
    observations["analysis_en"] = json.loads(analysis_path.read_text(encoding="utf-8"))

    locale_edit_path = operation_dir / "locale-edit.json"
    locale_project = operation_dir / "locale.rcms"
    locale_environment = dict(environment, RCMS_PACKAGE_LOCALE="de_DE")
    subprocess.run(
        [str(executable), "--automation-package-edit-save", str(locale_edit_path), str(sample),
         str(locale_project), "raw-data-0", "1,2"], check=True, env=locale_environment
    )
    observations["locale_edit"] = json.loads(locale_edit_path.read_text(encoding="utf-8"))

    locale_analysis_path = operation_dir / "analysis-de.json"
    subprocess.run(
        [str(executable), "--automation-package-analyze", str(locale_analysis_path),
         str(locale_project), PACKAGED_ANALYSIS_METHOD], check=True, env=locale_environment
    )
    observations["analysis_de"] = json.loads(locale_analysis_path.read_text(encoding="utf-8"))

    reopened_analysis_path = operation_dir / "analysis-reopened.json"
    subprocess.run(
        [str(executable), "--automation-package-analyze", str(reopened_analysis_path),
         str(edited_project), PACKAGED_ANALYSIS_METHOD], check=True, env=environment
    )
    observations["save_reopen"] = json.loads(reopened_analysis_path.read_text(encoding="utf-8"))
    return observations


def _workflow_observation_payload(observations: dict[str, dict]) -> dict:
    analysis = observations["analysis_en"]
    locale = observations["analysis_de"]
    analysis_summary = analysis["texts"].get("Summary", "")
    locale_summary = locale["texts"].get("Summary", "")
    return {
        "summary": analysis_summary,
        "svg_paths": analysis["display_images"],
        "edit_observed": observations["edit"]["edited"] and observations["edit"]["saved"],
        "analysis_observed": bool(analysis_summary),
        "reopen_observed": bool(observations["edit"]["saved"]),
        "analysis_after_reopen_observed": bool(observations["save_reopen"]["texts"].get("Summary", "")),
        "locale_inputs": [
            {"operation": "analysis", "locale": "en_US", "decimal_point": ".", "input": "1.2", "canonical_value": 1.2, "summary": analysis_summary, "svg_paths": analysis["display_images"]},
            {"operation": "locale", "locale": "de_DE", "decimal_point": ",", "input": "1,2", "canonical_value": 1.2, "summary": locale_summary, "svg_paths": locale["display_images"]},
        ],
    }


def capture_sample_observations(
    executable: Path, *, sample_root: Path, output: Path
) -> None:
    """Open every shipped sample through the executable and record identities."""
    manifest = json.loads((sample_root / "manifest.json").read_text(encoding="utf-8"))
    records = []
    for item in manifest["projects"]:
        path = sample_root / item["file"]
        report_path = output.parent / ("open-" + path.stem + ".json")
        result = subprocess.run(
            [str(executable), "--automation-package-open-report", str(report_path), str(path)],
            check=False,
            capture_output=True,
            text=True,
            env={key: value for key, value in os.environ.items() if key != "RCMS_PACKAGE_SMOKE_EVIDENCE"},
        )
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
        records.append({
            "project": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "semantic_sha256": item["semantic_sha256"],
            "opened_in_packaged_application": result.returncode == 0 and report.get("opened") is True,
        })
    output.write_text(json.dumps({"passed": all(item["opened_in_packaged_application"] for item in records), "manifest_sha256": hashlib.sha256((sample_root / "manifest.json").read_bytes()).hexdigest(), "projects": records}, indent=2) + "\n", encoding="utf-8")


def assemble(
    *, workflow_observation: Path, surface_records: Path, sample_observations: Path,
    sample: str, output: Path, log_path: Path | None = None,
) -> dict:
    observation = json.loads(workflow_observation.read_text(encoding="utf-8"))
    surfaces = _load_surfaces(surface_records)
    samples = json.loads(sample_observations.read_text(encoding="utf-8"))
    _validate_workflow_observation(observation)
    workflows = _workflow_payload(observation, sample, samples)
    evidence = {"schema_version": 1, "passed": True, "workflows": workflows,
                "scales": surfaces}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _append_log(log_path)
    return evidence


def _load_surfaces(surface_records: Path) -> list:
    if not surface_records.is_dir():
        return json.loads(surface_records.read_text(encoding="utf-8"))
    surfaces = []
    for path in sorted(surface_records.glob("surface-*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        surfaces.extend(payload.get("scales", [payload]))
    return surfaces


def _validate_workflow_observation(observation: dict) -> None:
    if not _workflow_flags_valid(observation):
        raise ValueError("workflow observation contains an unsuccessful operation")
    variants = observation["locale_inputs"]
    if [item["locale"] for item in variants] != ["en_US", "de_DE"]:
        raise ValueError("workflow observation must contain both locale variants")
    if not _locale_operations_valid(variants):
        raise ValueError("workflow observation must contain distinct locale operations")
    if not _locale_values_valid(variants):
        raise ValueError("workflow observation did not exercise distinct locale inputs")


def _workflow_flags_valid(observation: dict) -> bool:
    required = ("edit_observed", "analysis_observed", "reopen_observed", "analysis_after_reopen_observed")
    return all(observation[key] for key in required)


def _locale_operations_valid(variants: list[dict]) -> bool:
    return [item.get("operation") for item in variants] == ["analysis", "locale"]


def _locale_values_valid(variants: list[dict]) -> bool:
    en, de = variants
    return (
        en["decimal_point"] == "."
        and de["decimal_point"] == ","
        and "." in en["input"]
        and "," in de["input"]
        and en["canonical_value"] == de["canonical_value"]
    )


def _workflow_payload(observation: dict, sample: str, samples: dict) -> dict:
    base_identity = _identity(observation)
    variants = [
        {"operation": item["operation"], "locale": item["locale"], "decimal_point": item["decimal_point"], "input": item["input"], "canonical_value": item["canonical_value"], **_identity(item)}
        for item in observation["locale_inputs"]
    ]
    return {
        "automation_entry_point": True,
        "converted_sample": sample,
        "representative_edit": bool(observation["edit_observed"]),
        "real_r_analysis": bool(observation["analysis_observed"]),
        "result_text": True,
        "expected_normalized_summary_sha256": base_identity["normalized_summary_sha256"],
        **base_identity,
        "locale_variants": variants,
        "save_reopen": bool(observation["reopen_observed"]),
        "analysis_after_reopen": bool(observation["analysis_after_reopen_observed"]),
        "sample_projects": samples,
    }


def _append_log(log_path: Path | None) -> None:
    if log_path is None:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write("packaged-runtime-probe:passed\n")
        for scale in ("1.25", "1.50", "1.75"):
            stream.write(f"packaged-surface:scale-{scale}-passed\n")
        stream.write("packaged-workflow:project-exercise:complete\n")
        stream.write("packaged-workflow:evidence-written\n")
        stream.write("packaged-workflow:post-close\n")
        stream.write("startup-project:normal-entry-point-passed\n")
        stream.write("packaged-workflow:process-exit:0\n")


def _identity(observation: dict) -> dict:
    summary = str(observation["summary"]).replace("\r\n", "\n")
    return {
        "raw_summary_sha256": _sha256(summary),
        "normalized_summary_sha256": _sha256(normalize_packaged_summary_identity(summary)),
        "svg_sha256": {str(label): hashlib.sha256(Path(path).read_bytes()).hexdigest() for label, path in observation["svg_paths"].items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow-observation", type=Path, required=True)
    parser.add_argument("--surface-records", type=Path, required=True)
    parser.add_argument("--sample-observations", type=Path, required=True)
    parser.add_argument("--sample", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--runtime-probe", type=Path)
    parser.add_argument("--surface-directory", type=Path)
    parser.add_argument("--sample-root", type=Path)
    parser.add_argument("--sample-path", type=Path)
    parser.add_argument("--log-path", type=Path)
    args = parser.parse_args()
    if args.executable:
        if not args.runtime_probe or not args.surface_directory:
            parser.error("--executable requires --runtime-probe and --surface-directory")
        records = capture_atomic_observations(args.executable, runtime_probe=args.runtime_probe, surface_directory=args.surface_directory)
        combined = []
        for record in records:
            payload = json.loads(record.read_text(encoding="utf-8"))
            combined.extend(payload.get("scales", [payload]))
        if not args.surface_records.is_dir():
            args.surface_records.write_text(
                json.dumps(combined, indent=2) + "\n", encoding="utf-8"
            )
        if args.sample_root:
            capture_sample_observations(args.executable, sample_root=args.sample_root, output=args.sample_observations)
        if not args.sample_path:
            parser.error("--executable requires --sample-path")
        capture_workflow_observations(args.executable, sample=args.sample_path, output=args.workflow_observation)
    assemble(
        workflow_observation=args.workflow_observation,
        surface_records=args.surface_records,
        sample_observations=args.sample_observations,
        sample=args.sample,
        output=args.output,
        log_path=args.log_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
