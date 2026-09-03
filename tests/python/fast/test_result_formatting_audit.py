import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "audit_result_formatting.py"


def _result(**overrides):
    result = {
        "id": "publication-bias-fixture",
        "data_family": "continuous",
        "method": "small.study.effects",
        "status": "success",
        "texts": {
            "Warning": "No single result proves or rules out publication bias.",
            "Data and eligibility": "Studies analyzed: 12",
            "Tests": "Primary asymmetry test\nResult: p-value: 0.040",
            "Pooled comparison": "Common effect and random effects estimates.",
            "Failures": "No procedure failures.",
        },
        "images": {"Ordinary Funnel Plot": "ordinary.png"},
    }
    result.update(overrides)
    return result


def test_audit_accepts_representative_publication_bias_result_and_reports_inventory():
    from scripts.audit_result_formatting import audit_records

    report = audit_records([_result()])

    assert report["summary"] == {"errors": 0, "warnings": 0, "sources": 1}
    assert report["inventory"]["covered"] == [
        "continuous",
        "failures",
        "publication-bias",
    ]
    assert report["inventory"]["missing"] == [
        "binary",
        "cumulative",
        "diagnostic",
        "leave-one-out",
        "meta-regression",
        "subgroup",
    ]


@pytest.mark.parametrize(
    ("bad_text", "code"),
    [
        ("[1] 0.42", "raw-r-console-prefix"),
        ("$estimate\n[1] 0.42", "unsafe-list-repr"),
        ("Model Results\n Estimate  Lower bound\n 0.42      0.10", "malformed-table"),
        ("res.info\nPackage: meta", "internal-heading"),
    ],
)
def test_audit_flags_known_display_hazards(bad_text, code):
    from scripts.audit_result_formatting import audit_records

    result = _result(texts={"Summary": bad_text})
    report = audit_records([result])

    assert code in {finding["code"] for finding in report["findings"]}


def test_audit_flags_duplicate_titles_and_ordering():
    from scripts.audit_result_formatting import audit_records

    result = _result(
        texts={
            "Tests": "Tests",
            " warning ": "Warning",
            "Warning": "Warning",
            "Data and eligibility": "Data",
        },
        images={},
    )
    report = audit_records([result])
    codes = {finding["code"] for finding in report["findings"]}

    assert "duplicate-title" in codes
    assert "section-order" in codes


@pytest.mark.parametrize(
    "text",
    [
        "Package: meta\nCall: meta::metabias(...)" ,
        "geometry: c(0.1, 0.2, 0.3)",
        "prepared.effects: c(0.1, 0.2, 0.3)",
        "Estimate  Lower bound  Upper bound\n0.1234567  0.1  0.2",
    ],
)
def test_audit_flags_backend_dumps_and_unrounded_values(text):
    from scripts.audit_result_formatting import audit_records

    report = audit_records([_result(texts={"Summary": text})])
    codes = {finding["code"] for finding in report["findings"]}

    assert codes & {"internal-dump", "internal-key", "excessive-precision"}


def test_curated_publication_method_details_allow_package_and_call():
    from scripts.audit_result_formatting import audit_records

    report = audit_records(
        [_result(texts={"Warning": "ok", "Data and eligibility": "ok", "Tests": "Package: meta\nCall: meta::metabias(...)"})]
    )

    assert not {"internal-dump", "missing-contract-section"} & {
        finding["code"] for finding in report["findings"]
    }


def test_audit_flags_technical_sections_before_headline_summary():
    from scripts.audit_result_formatting import audit_records

    report = audit_records(
        [
            {
                "id": "standard",
                "data_family": "binary",
                "method": "binary.random",
                "texts": {"Weights": "Study names  Weights", "Summary": "Estimate  Lower bound  Upper bound\n1  0.5  1.5"},
            }
        ]
    )

    assert "technical-before-summary" in {
        finding["code"] for finding in report["findings"]
    }


def test_cli_reads_json_and_emits_structured_output(tmp_path):
    source = tmp_path / "capture.json"
    source.write_text(json.dumps(_result()), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), str(source)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["summary"]["sources"] == 1
    assert report["inventory"]["covered"] == [
        "continuous",
        "failures",
        "publication-bias",
    ]


def test_cli_reads_capture_bundle(tmp_path):
    source = tmp_path / "captures.zip"
    with zipfile.ZipFile(source, "w") as bundle:
        bundle.writestr("captures/one.json", json.dumps(_result()))

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), str(source)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["summary"]["sources"] == 1


def test_frozen_regression_bundle_is_a_clean_multi_analysis_inventory():
    from scripts.audit_result_formatting import audit_records, load_records

    bundle = ROOT / "tests" / "analysis_regression" / "baseline" / "observed-golden-baseline.zip"
    report = audit_records(load_records([bundle]))

    assert report["summary"] == {"errors": 0, "warnings": 0, "sources": 11}
    assert report["findings"] == []
    assert report["inventory"]["covered"] == [
        "binary",
        "continuous",
        "cumulative",
        "diagnostic",
        "leave-one-out",
        "meta-regression",
        "subgroup",
    ]
