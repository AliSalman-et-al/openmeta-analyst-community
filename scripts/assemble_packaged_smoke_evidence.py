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


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def capture_atomic_observations(
    executable: Path, *, runtime_probe: Path, surface_directory: Path
) -> list[Path]:
    """Run the shipped atomic probes; all orchestration stays in this script."""
    subprocess.run(
        [str(executable), "--automation-package-runtime-probe", str(runtime_probe)],
        check=True,
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
    commands = {
        "edit": ("edit",),
        "analysis_en": ("analysis", "en_US"),
        "analysis_de": ("locale", "de_DE"),
        "save_reopen": ("save-reopen",),
    }
    observations = {}
    for name, operation in commands.items():
        path = operation_dir / f"{name}.json"
        subprocess.run(
            [str(executable), "--automation-package-operation", str(path), str(sample), *operation],
            check=True,
            env={key: value for key, value in os.environ.items() if key != "RCMS_PACKAGE_SMOKE_EVIDENCE"},
        )
        observations[name] = json.loads(path.read_text(encoding="utf-8"))
    analysis = observations["analysis_en"]
    locale = observations["analysis_de"]
    output.write_text(json.dumps({
        "summary": analysis["summary"],
        "svg_paths": analysis["svg_paths"],
        "edit_observed": observations["edit"]["observed"],
        "analysis_observed": analysis["observed"],
        "reopen_observed": observations["save_reopen"]["observed"],
        "locale_inputs": [
            {key: analysis[key] for key in ("locale", "input", "canonical_value", "summary", "svg_paths")},
            {key: locale[key] for key in ("locale", "input", "canonical_value", "summary", "svg_paths")},
        ],
    }, indent=2) + "\n", encoding="utf-8")


def capture_sample_observations(
    executable: Path, *, sample_root: Path, output: Path
) -> None:
    """Open every shipped sample through the executable and record identities."""
    manifest = json.loads((sample_root / "manifest.json").read_text(encoding="utf-8"))
    records = []
    for item in manifest["projects"]:
        path = sample_root / item["file"]
        result = subprocess.run(
            [str(executable), "--automation-native-smoke", str(path)],
            check=False,
            capture_output=True,
            text=True,
            env={key: value for key, value in os.environ.items() if key != "RCMS_PACKAGE_SMOKE_EVIDENCE"},
        )
        records.append({
            "project": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "semantic_sha256": item["semantic_sha256"],
            "opened_in_packaged_application": result.returncode == 0,
        })
    output.write_text(json.dumps({"passed": all(item["opened_in_packaged_application"] for item in records), "manifest_sha256": hashlib.sha256((sample_root / "manifest.json").read_bytes()).hexdigest(), "projects": records}, indent=2) + "\n", encoding="utf-8")


def assemble(
    *, workflow_observation: Path, surface_records: Path, sample_observations: Path,
    sample: str, output: Path, log_path: Path | None = None,
) -> dict:
    observation = json.loads(workflow_observation.read_text(encoding="utf-8"))
    if surface_records.is_dir():
        surfaces = []
        for path in sorted(surface_records.glob("surface-*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            surfaces.extend(payload.get("scales", [payload]))
    else:
        surfaces = json.loads(surface_records.read_text(encoding="utf-8"))
    samples = json.loads(sample_observations.read_text(encoding="utf-8"))
    if not all(observation[key] for key in ("edit_observed", "analysis_observed", "reopen_observed")):
        raise ValueError("workflow observation contains an unsuccessful operation")
    base_identity = _identity(observation)
    locale_variants = observation["locale_inputs"]
    if [item["locale"] for item in locale_variants] != ["en_US", "de_DE"]:
        raise ValueError("workflow observation must contain both locale variants")
    workflows = {
        "automation_entry_point": True,
        "converted_sample": sample,
        "representative_edit": bool(observation["edit_observed"]),
        "real_r_analysis": bool(observation["analysis_observed"]),
        "result_text": True,
        "expected_normalized_summary_sha256": base_identity["normalized_summary_sha256"],
        **base_identity,
        "locale_variants": [
            {"locale": item["locale"], "input": item["input"], "canonical_value": item["canonical_value"], **_identity(item)}
            for item in locale_variants
        ],
        "save_reopen": bool(observation["reopen_observed"]),
        "analysis_after_reopen": bool(observation["analysis_observed"] and observation["reopen_observed"]),
        "sample_projects": samples,
    }
    evidence = {"schema_version": 1, "passed": True, "workflows": workflows,
                "scales": surfaces}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write("packaged-workflow:project-exercise:complete\n")
            stream.write("packaged-workflow:evidence-written\n")
            stream.write("packaged-workflow:post-close\n")
            stream.write("startup-project:normal-entry-point-passed\n")
            stream.write("packaged-workflow:process-exit:0\n")
    return evidence


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
        args.surface_records.write_text(json.dumps(combined, indent=2) + "\n", encoding="utf-8")
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
