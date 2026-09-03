import ast
import hashlib
from pathlib import Path

import pytest

from rc_metastudio.result_text_identity import normalize_packaged_summary_identity


ROOT = Path(__file__).resolve().parents[3]
PACKAGED_SUMMARY_SHA256_BY_SAMPLE = {
    "amino.rcms": "d37d0aa920c9ae2397b1c44d3fbe9f91d5d89b61fad43ced991148f2e51245d0",
    "BCG.rcms": "2cb1cb0b867b7280a8843f633a9a040f7810d4c9e0ab91ff6333d8110fc41933",
}
NORMALIZED_PACKAGED_SUMMARY = (
    "Binary Random-Effects Model Metric: Odds Ratio Model Results Estimate "
    "Lower bound Upper bound p-value 0.47 0.32 0.69 < 0.001 Heterogeneity "
    "t² Q(df=12) Het. p-value I² 0.37 163.16 < 0.001 92.6% Calculation "
    "scale: log - estimate: -0.75, lower: -1.12, upper: -0.37, std. "
    "error: 0.192"
)


def _constant_from_source(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in statement.targets
        ):
            value = ast.literal_eval(statement.value)
            return value
    raise AssertionError(f"{name} is missing from {path}")


def test_packaged_summary_identity_ignores_display_only_confidence_labels():
    old = "  Estimate  Lower bound  Upper bound  p-value\n  1.2  1.0  1.4  0.01"
    labelled = (
        "  Estimate  Lower bound (90% CI)  Upper bound (90% CI)  p-value\n"
        "  1.2  1.0  1.4  0.01"
    )

    assert normalize_packaged_summary_identity(labelled) == (
        normalize_packaged_summary_identity(old)
    )
    assert normalize_packaged_summary_identity(labelled) == (
        "Estimate Lower bound Upper bound p-value 1.2 1.0 1.4 0.01"
    )


def test_packaged_summary_hash_contract_is_shared_and_pinned():
    maps = {
        "automation": _constant_from_source(
            ROOT / "src/rc_metastudio/automation.py",
            "PACKAGED_SUMMARY_SHA256_BY_SAMPLE",
        ),
        "macos": _constant_from_source(
            ROOT / "scripts/inspect_macos_deployment.py",
            "EXPECTED_SUMMARY_SHA256_BY_SAMPLE",
        ),
        "windows": _constant_from_source(
            ROOT / "scripts/inspect_windows_deployment.py",
            "EXPECTED_SUMMARY_SHA256_BY_SAMPLE",
        ),
    }

    assert maps == {
        "automation": PACKAGED_SUMMARY_SHA256_BY_SAMPLE,
        "macos": PACKAGED_SUMMARY_SHA256_BY_SAMPLE,
        "windows": PACKAGED_SUMMARY_SHA256_BY_SAMPLE,
    }
    assert hashlib.sha256(
        NORMALIZED_PACKAGED_SUMMARY.encode("utf-8")
    ).hexdigest() == PACKAGED_SUMMARY_SHA256_BY_SAMPLE["BCG.rcms"]


def test_packaged_summary_identity_rejects_unknown_sample():
    from rc_metastudio import automation

    with pytest.raises(SystemExit, match="Unsupported packaged smoke sample"):
        automation._expected_packaged_summary_sha256("unknown.rcms")
