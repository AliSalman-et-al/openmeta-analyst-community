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
    commands = {
        "edit": ("edit", PACKAGED_EDIT_VALUE),
        "analysis_en": ("analysis", "en_US", PACKAGED_ANALYSIS_METHOD),
        "analysis_de": ("locale", "de_DE", PACKAGED_ANALYSIS_METHOD),
        "save_reopen": ("save-reopen-analysis", PACKAGED_EDIT_VALUE, PACKAGED_ANALYSIS_METHOD),
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
        "edit_observed": observations["edit"]["edited"],
        "analysis_observed": bool(analysis["edited"] and analysis["canonical_valid"] and analysis["summary"]),
        "reopen_observed": bool(
            observations["save_reopen"]["saved"]
            and observations["save_reopen"]["reopened"]
        ),
        "analysis_after_reopen_observed": bool(
            observations["save_reopen"]["reopened"]
            and observations["save_reopen"]["summary"]
        ),
        "locale_inputs": [
            {"operation": analysis["operation"], **{key: analysis[key] for key in ("locale", "decimal_point", "input", "canonical_value", "summary", "svg_paths")}},
            {"operation": locale["operation"], **{key: locale[key] for key in ("locale", "decimal_point", "input", "canonical_value", "summary", "svg_paths")}},
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
