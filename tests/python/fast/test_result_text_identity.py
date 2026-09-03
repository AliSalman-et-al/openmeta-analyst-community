import ast
import hashlib
from pathlib import Path

from rc_metastudio.result_text_identity import normalize_packaged_summary_identity


ROOT = Path(__file__).resolve().parents[3]
PACKAGED_SUMMARY_SHA256 = (
    "2cb1cb0b867b7280a8843f633a9a040f7810d4c9e0ab91ff6333d8110fc41933"
)
NORMALIZED_PACKAGED_SUMMARY = (
    "Binary Random-Effects Model Metric: Odds Ratio Model Results Estimate "
    "Lower bound Upper bound p-value 0.47 0.32 0.69 < 0.001 Heterogeneity "
    "t² Q(df=12) Het. p-value I² 0.37 163.16 < 0.001 92.6% Calculation "
    "scale: log - estimate: -0.75, lower: -1.12, upper: -0.37, std. "
    "error: 0.192"
)


def _constant_from_source(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in statement.targets
        ):
            value = ast.literal_eval(statement.value)
            assert isinstance(value, str)
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
    constants = {
        "automation": _constant_from_source(
            ROOT / "src/rc_metastudio/automation.py", "PACKAGED_SUMMARY_SHA256"
        ),
        "macos": _constant_from_source(
            ROOT / "scripts/inspect_macos_deployment.py", "EXPECTED_SUMMARY_SHA256"
        ),
        "windows": _constant_from_source(
            ROOT / "scripts/inspect_windows_deployment.py", "EXPECTED_SUMMARY_SHA256"
        ),
    }

    assert constants == {
        "automation": PACKAGED_SUMMARY_SHA256,
        "macos": PACKAGED_SUMMARY_SHA256,
        "windows": PACKAGED_SUMMARY_SHA256,
    }
    assert hashlib.sha256(
        NORMALIZED_PACKAGED_SUMMARY.encode("utf-8")
    ).hexdigest() == PACKAGED_SUMMARY_SHA256
