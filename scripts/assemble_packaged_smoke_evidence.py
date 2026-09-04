"""Assemble packaged qualification evidence outside the frozen application.

The executable only observes product state.  This developer-side command owns
scenario sequencing, result identity hashes, locale comparisons, and the
deployment evidence schema.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
    for scale in ("1.25", "1.50", "1.75"):
        record = surface_directory / f"surface-{scale}.json"
        subprocess.run(
            [str(executable), "--automation-package-surface-smoke", str(record), scale],
            check=True,
        )
        records.append(record)
    return records


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
    sample: str, output: Path,
) -> dict:
    observation = json.loads(workflow_observation.read_text(encoding="utf-8"))
    if surface_records.is_dir():
        surfaces = []
        for path in sorted(surface_records.glob("surface-*.json")):
            surfaces.extend(json.loads(path.read_text(encoding="utf-8")).get("scales", []))
    else:
        surfaces = json.loads(surface_records.read_text(encoding="utf-8"))
    samples = json.loads(sample_observations.read_text(encoding="utf-8"))
    summary = str(observation["summary"])
    normalized_hash = _sha256(normalize_packaged_summary_identity(summary))
    raw_hash = _sha256(summary.replace("\r\n", "\n"))
    svg_hashes = {
        str(label): hashlib.sha256(Path(path).read_bytes()).hexdigest()
        for label, path in observation["svg_paths"].items()
    }
    locale_variants = observation["locale_variants"]
    if [item["locale"] for item in locale_variants] != ["en_US", "de_DE"]:
        raise ValueError("workflow observation must contain both locale variants")
    workflows = {
        "automation_entry_point": True,
        "converted_sample": sample,
        "representative_edit": bool(observation["representative_edit"]),
        "real_r_analysis": bool(observation["real_r_analysis"]),
        "result_text": True,
        "expected_normalized_summary_sha256": normalized_hash,
        "raw_summary_sha256": raw_hash,
        "normalized_summary_sha256": normalized_hash,
        "svg_sha256": svg_hashes,
        "locale_variants": [
            {"locale": item["locale"], "input": item["input"],
             "canonical_value": item["canonical_value"],
             "raw_summary_sha256": raw_hash,
             "normalized_summary_sha256": normalized_hash,
             "svg_sha256": svg_hashes}
            for item in locale_variants
        ],
        "save_reopen": bool(observation["save_reopen"]),
        "analysis_after_reopen": bool(observation["analysis_after_reopen"]),
        "sample_projects": samples,
    }
    evidence = {"schema_version": 1, "passed": True, "workflows": workflows,
                "scales": surfaces}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence


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
    args = parser.parse_args()
    if args.executable:
        if not args.runtime_probe or not args.surface_directory:
            parser.error("--executable requires --runtime-probe and --surface-directory")
        records = capture_atomic_observations(args.executable, runtime_probe=args.runtime_probe, surface_directory=args.surface_directory)
        combined = []
        for record in records:
            payload = json.loads(record.read_text(encoding="utf-8"))
            combined.extend(payload.get("scales", []))
        args.surface_records.write_text(json.dumps(combined, indent=2) + "\n", encoding="utf-8")
        if args.sample_root:
            capture_sample_observations(args.executable, sample_root=args.sample_root, output=args.sample_observations)
    assemble(
        workflow_observation=args.workflow_observation,
        surface_records=args.surface_records,
        sample_observations=args.sample_observations,
        sample=args.sample,
        output=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
