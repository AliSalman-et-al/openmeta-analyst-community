import json
import os
from pathlib import Path
import shutil
import sys
import types
from contextlib import contextmanager
from decimal import Decimal
from types import ModuleType
import zipfile

import pytest

sys.path.insert(0, os.path.abspath("src"))
ROOT = Path(__file__).resolve().parents[3]

from rc_metastudio.analysis_regression_compare import (  # noqa: E402 - legacy module path bootstrap
    ACCEPTED_EXCEPTION,
    CAPTURE_ERROR,
    MISSING_OUTPUT,
    MALFORMED_OUTPUT,
    NUMERIC_DRIFT,
    PASS,
    TEXT_ARTIFACT_DRIFT,
    UNEXPECTED_OUTPUT,
    UNSUPPORTED_WORKFLOW,
    normalize_heterogeneity_header,
    compare_golden_baseline,
    main,
)

sys.path.insert(0, os.path.abspath("scripts"))
import verify_golden_compatibility  # noqa: E402 - scripts path bootstrap
import verify_rcmetar_r_stack  # noqa: E402 - scripts path bootstrap


def test_analysis_regression_comparison_classifies_compatible_capture_as_pass():
    report = compare_golden_baseline(_baseline(), _current())

    assert report["passed"] is True
    assert report["rows"][0]["classification"] == "pass"
    assert report["rows"][0]["id"] == "amino-binary-random"


def test_analysis_regression_comparison_classifies_numeric_drift_with_row_context():
    current = _current()
    current["curated_golden_set"][0]["outputs"]["Summary"]["estimate"] = 0.773

    row = next(
        row
        for row in compare_golden_baseline(_baseline(), current)["rows"]
        if row["classification"] == "numeric_drift"
    )

    assert row["id"] == "amino-binary-random"
    assert "Summary.estimate" in row["detail"]


def test_numeric_comparison_rejects_malformed_values_without_raising():
    malformed = [
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
        "0.7705",
        Decimal("0.7705"),
        None,
    ]
    for value in malformed:
        current = _current()
        current["curated_golden_set"][0]["outputs"]["Summary"]["estimate"] = value
        report = compare_golden_baseline(_baseline(), current)
        assert report["passed"] is False
        assert any(
            row["classification"] == MALFORMED_OUTPUT
            and row["detail"] == "Summary.estimate current numeric value is malformed."
            for row in report["rows"]
        )

    reference = _baseline()
    reference["curated_golden_set"][0]["outputs"]["Summary"]["estimate"] = float("nan")
    report = compare_golden_baseline(reference, _current())
    assert report["passed"] is False
    assert any(
        row["classification"] == MALFORMED_OUTPUT
        and row["detail"] == "Summary.estimate reference numeric value is malformed."
        for row in report["rows"]
    )

    current = _current()
    current["curated_golden_set"][0]["outputs"]["Summary"]["estimate"] = None
    report = compare_golden_baseline(
        _baseline(),
        current,
        exceptions=[{"id": "amino-binary-random", "reason": "not applicable"}],
    )
    assert any(row["classification"] == MALFORMED_OUTPUT for row in report["rows"])


def test_numeric_comparison_accepts_finite_int_float_within_policy_only():
    reference = _baseline()
    reference["curated_golden_set"][0]["numeric_tolerance_policy"] = {
        "absolute": 0.001,
        "relative": 1e-9,
        "rule": "max(absolute, relative * abs(expected))",
    }
    for value in (0.77, 0.7705, 1):
        current = _current()
        current["curated_golden_set"][0]["outputs"]["Summary"]["estimate"] = value
        report = compare_golden_baseline(reference, current)
        expected_pass = value in (0.77, 0.7705)
        numeric_rows = [
            row for row in report["rows"] if "Summary.estimate" in row["detail"]
        ]
        assert numeric_rows[0]["classification"] == (
            PASS if expected_pass else NUMERIC_DRIFT
        )


def test_analysis_regression_comparison_classifies_non_numeric_result_drift():
    current = _current()
    current["curated_golden_set"][0]["texts"]["Summary"] = "changed"

    row = next(
        row
        for row in compare_golden_baseline(_baseline(), current)["rows"]
        if row["classification"] == "text_artifact_drift"
    )

    assert row["id"] == "amino-binary-random"


def test_cross_platform_text_normalization_is_limited_to_tau_squared_header():
    baseline = _baseline()
    current = _current()
    expected = baseline["curated_golden_set"][0]
    actual = current["curated_golden_set"][0]
    expected["tool_versions"] = {"os": "Windows"}
    actual["tool_versions"] = {"os": "Darwin"}
    expected["texts"]["Summary"] = (
        "Heterogeneity\n t²     Q(df=18)  Het. p-value     I²\n"
        " 0.378    33.360         0.015  46.0%"
    )
    actual["texts"]["Summary"] = expected["texts"]["Summary"].replace("t²", "τ²")
    assert (
        normalize_heterogeneity_header(actual["texts"]["Summary"])
        == expected["texts"]["Summary"]
    )
    assert (
        normalize_heterogeneity_header("Narrative τ² meaning") == "Narrative τ² meaning"
    )

    text_row = next(
        row
        for row in compare_golden_baseline(baseline, current)["rows"]
        if row["detail"].startswith("Text section Summary")
    )
    assert text_row["classification"] == PASS
    assert "Windows -> Darwin: t² <-> τ²" in text_row["detail"]

    same_platform = json.loads(json.dumps(current))
    same_platform["curated_golden_set"][0]["tool_versions"]["os"] = "Windows"
    same_platform_row = next(
        row
        for row in compare_golden_baseline(baseline, same_platform)["rows"]
        if row["detail"].startswith("Text section Summary")
    )
    assert same_platform_row["classification"] == TEXT_ARTIFACT_DRIFT

    for changed_text in (
        actual["texts"]["Summary"].replace("33.360", "99.999"),
        "Narrative τ² meaning",
    ):
        drifted = json.loads(json.dumps(current))
        drifted["curated_golden_set"][0]["texts"]["Summary"] = changed_text
        drifted_row = next(
            row
            for row in compare_golden_baseline(baseline, drifted)["rows"]
            if row["detail"].startswith("Text section Summary")
        )
        assert drifted_row["classification"] == TEXT_ARTIFACT_DRIFT


def test_analysis_regression_comparison_rejects_warning_and_reference_tampering():
    for section in ("Warnings", "References"):
        baseline = _baseline()
        current = _current()
        baseline["curated_golden_set"][0]["texts"][section] = "committed text\r\n"
        current["curated_golden_set"][0]["texts"][section] = "tampered text"

        rows = compare_golden_baseline(baseline, current)["rows"]

        assert any(
            row["classification"] == TEXT_ARTIFACT_DRIFT and section in row["detail"]
            for row in rows
        )


def test_analysis_regression_comparison_rejects_artifact_content_and_descriptor_tampering():
    for field, value in (
        ("sha256", "tampered"),
        ("bundle_path", "artifacts/renamed.png"),
    ):
        baseline = _baseline()
        current = _current()
        baseline_artifact = baseline["curated_golden_set"][0]["artifacts"][0]
        current_artifact = current["curated_golden_set"][0]["artifacts"][0]
        baseline["curated_golden_set"][0]["tool_versions"] = {"os": "Windows"}
        current["curated_golden_set"][0]["tool_versions"] = {"os": "Windows"}
        baseline_artifact["bundle_path"] = "artifacts/reference.png"
        current_artifact["bundle_path"] = "artifacts/reference.png"
        baseline_artifact["sha256"] = "a" * 64
        current_artifact["sha256"] = baseline_artifact["sha256"]
        current_artifact[field] = value

        rows = compare_golden_baseline(baseline, current)["rows"]

        artifact_row = next(
            row for row in rows if row["detail"].startswith("Artifact ")
        )
        assert artifact_row["classification"] == TEXT_ARTIFACT_DRIFT
        assert "same-platform exact artifact policy (Windows)" in artifact_row["detail"]


def test_cross_platform_artifact_policy_validates_identity_and_hash_shape():
    baseline = _baseline()
    current = _current()
    expected = baseline["curated_golden_set"][0]
    actual = current["curated_golden_set"][0]
    expected["tool_versions"] = {"os": "Windows"}
    actual["tool_versions"] = {"os": "Darwin"}
    expected["artifacts"][0]["sha256"] = "a" * 64
    actual["artifacts"][0]["sha256"] = "b" * 64

    artifact_row = next(
        row
        for row in compare_golden_baseline(baseline, current)["rows"]
        if row["detail"].startswith("Artifact ")
    )
    assert artifact_row["classification"] == PASS
    assert (
        "cross-platform artifact policy (Windows -> Darwin)" in artifact_row["detail"]
    )

    for mutation in ("missing-hash", "invalid-hash", "descriptor-drift"):
        candidate = json.loads(json.dumps(current))
        artifact = candidate["curated_golden_set"][0]["artifacts"][0]
        if mutation == "missing-hash":
            artifact.pop("sha256")
        elif mutation == "invalid-hash":
            artifact["sha256"] = "not-a-sha256"
        else:
            artifact["path"] = "renamed.svg"
        artifact_row = next(
            row
            for row in compare_golden_baseline(baseline, candidate)["rows"]
            if row["detail"].startswith("Artifact ")
        )
        assert artifact_row["classification"] == TEXT_ARTIFACT_DRIFT
        assert (
            "cross-platform artifact policy (Windows -> Darwin)"
            in artifact_row["detail"]
        )


def test_analysis_regression_comparison_rejects_extra_cases():
    current = _current()
    extra = dict(current["curated_golden_set"][0])
    extra["id"] = "unexpected-case"
    current["curated_golden_set"].append(extra)

    rows = compare_golden_baseline(_baseline(), current)["rows"]

    assert any(
        row["id"] == "unexpected-case" and row["classification"] == UNEXPECTED_OUTPUT
        for row in rows
    )


def test_golden_output_root_rejects_unsafe_or_unowned_deletion_targets(tmp_path):
    root = tmp_path / "repo"
    (root / "build/qt6-verification").mkdir(parents=True)
    unsafe = [
        root,
        root / "build",
        root / "build/qt6-verification",
        root / "build/qt6-verification/arbitrary-existing",
        tmp_path / "outside/golden-compatibility-output",
    ]
    for path in unsafe:
        path.mkdir(parents=True, exist_ok=True)
        with pytest.raises(ValueError):
            verify_golden_compatibility._prepare_output_root(root, path)

    unowned = root / "build/qt6-verification/golden-compatibility-unowned"
    unowned.mkdir()
    sentinel = unowned / "do-not-delete.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError, match="unowned"):
        verify_golden_compatibility._prepare_output_root(root, unowned)
    assert sentinel.read_text(encoding="utf-8") == "preserve"


def test_golden_output_root_only_replaces_owned_bounded_directory(tmp_path):
    root = tmp_path / "repo"
    (root / "build/qt6-verification").mkdir(parents=True)
    output = root / "build/qt6-verification/golden-compatibility-owned"

    prepared = verify_golden_compatibility._prepare_output_root(root, output)
    (prepared / "old.txt").write_text("old", encoding="utf-8")
    replaced = verify_golden_compatibility._prepare_output_root(root, output)

    assert replaced == prepared
    assert not (replaced / "old.txt").exists()
    assert (replaced / verify_golden_compatibility.OUTPUT_MARKER).is_file()


def test_golden_output_root_rejects_symlink_escape(tmp_path):
    root = tmp_path / "repo"
    base = root / "build/qt6-verification"
    outside = tmp_path / "outside"
    base.mkdir(parents=True)
    outside.mkdir()
    link = base / "golden-compatibility-link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable on this Windows host")

    with pytest.raises(ValueError, match="symlink|reparse"):
        verify_golden_compatibility._prepare_output_root(root, link)


def test_golden_verifier_rejects_outer_archive_byte_tampering(tmp_path):
    root = _copy_frozen_contract(tmp_path)
    archive = root / verify_golden_compatibility.ARCHIVE_RELATIVE_PATH
    with archive.open("ab") as stream:
        stream.write(b"tamper")

    with pytest.raises(ValueError, match="size|hash"):
        verify_golden_compatibility._load_frozen_reference(root)


def test_golden_verifier_rejects_internal_manifest_tampering(tmp_path):
    source = ROOT / verify_golden_compatibility.ARCHIVE_RELATIVE_PATH
    target = tmp_path / "manifest-tampered.zip"
    with zipfile.ZipFile(source) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    manifest["curated_golden_set"][0]["texts"]["Summary"] += " tampered"
    _rewrite_zip(source, target, {"manifest.json": json.dumps(manifest).encode()})

    with pytest.raises(ValueError, match="manifest and case capture disagree"):
        verify_golden_compatibility._read_validated_zip(target)


def test_golden_verifier_rejects_internal_artifact_tampering(tmp_path):
    source = ROOT / verify_golden_compatibility.ARCHIVE_RELATIVE_PATH
    target = tmp_path / "artifact-tampered.zip"
    member = "artifacts/amino-binary-random/golden_amino_forest.png"
    _rewrite_zip(source, target, {member: b"tampered image"})

    with pytest.raises(ValueError, match="artifact hash mismatch"):
        verify_golden_compatibility._read_validated_zip(target)


def test_golden_verifier_rejects_traversal_and_duplicate_zip_members(tmp_path):
    source = ROOT / verify_golden_compatibility.ARCHIVE_RELATIVE_PATH
    traversal = tmp_path / "traversal.zip"
    duplicate = tmp_path / "duplicate.zip"
    _rewrite_zip(source, traversal, {}, {"../escape": b"bad"})
    _rewrite_zip(source, duplicate, {}, {"MANIFEST.JSON": b"{}"})

    with pytest.raises(ValueError, match="unsafe"):
        verify_golden_compatibility._read_validated_zip(traversal)
    with pytest.raises(ValueError, match="duplicate"):
        verify_golden_compatibility._read_validated_zip(duplicate)


def test_numeric_contract_covers_all_cases_and_rejects_shape_and_tolerance_drift():
    archive, frozen = verify_golden_compatibility._load_frozen_reference(ROOT)
    contract = verify_golden_compatibility._load_numeric_contract(ROOT, archive, frozen)
    reference = verify_golden_compatibility._reference_with_numeric_contract(
        frozen, contract
    )
    assert [case["id"] for case in contract["cases"]] == [
        row["id"] for row in frozen["curated_golden_set"]
    ]
    assert (
        sum(
            len(metrics)
            for case in contract["cases"]
            for metrics in case["sections"].values()
        )
        == 415
    )
    assert all(case["nonnumeric_omissions"] for case in contract["cases"])

    current = json.loads(json.dumps(reference))
    report = compare_golden_baseline(reference, current)
    assert report["passed"] is True

    expected = reference["curated_golden_set"][0]
    assert {"tau_squared", "q", "i_squared"}.issubset(expected["outputs"]["Summary"])
    current = {"curated_golden_set": [json.loads(json.dumps(expected))]}
    del current["curated_golden_set"][0]["outputs"]["Summary"]["q"]
    missing = compare_golden_baseline({"curated_golden_set": [expected]}, current)[
        "rows"
    ]
    assert any(
        row["classification"] == MISSING_OUTPUT and "Summary.q" in row["detail"]
        for row in missing
    )
    current = {"curated_golden_set": [json.loads(json.dumps(expected))]}
    current["curated_golden_set"][0]["outputs"]["Summary"]["unexpected"] = 1.0
    extra = compare_golden_baseline({"curated_golden_set": [expected]}, current)["rows"]
    assert any(
        row["classification"] == UNEXPECTED_OUTPUT
        and "unexpected numeric metric" in row["detail"]
        for row in extra
    )

    for case_id, section, metric in (
        ("amino-binary-random", "Summary", "estimate"),
        (
            "continuous-leave-one-out",
            "Leave-one-out Summary",
            "model.without_young.estimate",
        ),
    ):
        current = json.loads(json.dumps(reference))
        row = next(row for row in current["curated_golden_set"] if row["id"] == case_id)
        row["outputs"][section][metric] += 0.0005
        assert compare_golden_baseline(reference, current)["passed"] is True
        row["outputs"][section][metric] += 0.001
        assert any(
            result["classification"] == NUMERIC_DRIFT
            and "%s.%s" % (section, metric) in result["detail"]
            for result in compare_golden_baseline(reference, current)["rows"]
        )


def test_numeric_oracle_is_independent_from_runtime_parser(monkeypatch):
    archive, frozen = verify_golden_compatibility._load_frozen_reference(ROOT)
    monkeypatch.setattr(
        verify_golden_compatibility.golden_analysis,
        "parsed_numeric_sections",
        lambda _result: {"Poison": {"rewritten_oracle": 999.0}},
    )
    contract = verify_golden_compatibility._load_numeric_contract(ROOT, archive, frozen)
    reference = verify_golden_compatibility._reference_with_numeric_contract(
        frozen, contract
    )
    assert reference["curated_golden_set"][0]["outputs"]["Summary"]["estimate"] == 0.77

    current = json.loads(json.dumps(reference))
    current["curated_golden_set"][0]["outputs"] = (
        verify_golden_compatibility.golden_analysis.parsed_numeric_sections({})
    )
    rows = compare_golden_baseline(reference, current)["rows"]
    assert any(row["classification"] == MISSING_OUTPUT for row in rows)
    assert any(row["classification"] == UNEXPECTED_OUTPUT for row in rows)


def test_meta_regression_parser_keeps_numeric_values_out_of_row_identity():
    text = """Model Results
    Covariate Estimate Lower bound Upper bound Std. error z p-value
    Intercept 124.77 100.00 149.54 12.64 9.87 < 0.001
    Golden year 0.06 0.01 0.11 0.03 2.33 0.020

Model tests
Test Statistic df p-value
Overall moderators (Qₘ) 5.43 1 0.020
"""

    assert verify_golden_compatibility.golden_analysis._parse_result_table(text) == {
        "model.intercept.coefficient": 124.77,
        "model.intercept.lower_bound": 100.0,
        "model.intercept.upper_bound": 149.54,
        "model.intercept.standard_error": 12.64,
        "model.intercept.p_value": 0.001,
        "model.golden_year.coefficient": 0.06,
        "model.golden_year.lower_bound": 0.01,
        "model.golden_year.upper_bound": 0.11,
        "model.golden_year.standard_error": 0.03,
        "model.golden_year.p_value": 0.02,
        "omnibus.p_value": 0.02,
    }


def test_meta_regression_parser_reads_small_sample_moderator_test():
    text = """Model Results
Covariate Estimate Lower bound Upper bound Std. error t df p-value
Intercept 124.77 100.00 149.54 12.64 9.87 11 < 0.001
Golden year 0.06 0.01 0.11 0.03 2.33 11 0.020

Model tests
Test Statistic df p-value
Overall moderators (F) 5.43 1 11 < 0.001
"""

    parsed = verify_golden_compatibility.golden_analysis._parse_result_table(text)
    assert parsed["model.intercept.coefficient"] == 124.77
    assert parsed["model.golden_year.p_value"] == 0.02
    assert parsed["omnibus.p_value"] == 0.001


def test_numeric_contract_rejects_hash_canonicalization_and_coverage_tamper(tmp_path):
    root = _copy_frozen_contract(tmp_path)
    archive, frozen = verify_golden_compatibility._load_frozen_reference(root)
    contract_path = root / verify_golden_compatibility.NUMERIC_CONTRACT_RELATIVE_PATH
    original = contract_path.read_bytes()
    contract_path.write_bytes(original + b" ")
    with pytest.raises(ValueError, match="size or hash"):
        verify_golden_compatibility._load_numeric_contract(root, archive, frozen)

    contract_path.write_bytes(original + b" ")
    _update_outer_file_contract(root, "golden_numeric_contract", contract_path)
    with pytest.raises(ValueError, match="canonically serialized"):
        verify_golden_compatibility._load_numeric_contract(root, archive, frozen)

    contract = json.loads(original)
    del contract["cases"][0]["sections"]["Summary"]["estimate"]
    contract_path.write_bytes(
        verify_golden_compatibility._canonical_json_bytes(contract)
    )
    _update_outer_file_contract(root, "golden_numeric_contract", contract_path)
    with pytest.raises(ValueError, match="coverage drifted"):
        verify_golden_compatibility._load_numeric_contract(root, archive, frozen)


def test_plot_descriptor_contract_rejects_outer_and_semantic_tampering(tmp_path):
    root = _copy_frozen_contract(tmp_path)
    archive, reference = verify_golden_compatibility._load_frozen_reference(root)
    descriptor_path = root / "tests/analysis_regression/baseline/plot-descriptors.json"
    descriptor_path.write_text(
        descriptor_path.read_text(encoding="utf-8") + " ", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="size or hash"):
        verify_golden_compatibility._load_plot_descriptor_contract(
            root, archive, reference
        )

    shutil.copy2(
        ROOT / "tests/analysis_regression/baseline/plot-descriptors.json",
        descriptor_path,
    )
    contract = verify_golden_compatibility._load_plot_descriptor_contract(
        root, archive, reference
    )
    current = _current_plot_descriptors(contract)
    assert all(
        row["classification"] == PASS
        for row in verify_golden_compatibility._compare_plot_descriptors(
            contract, current
        )
    )
    current["curated_golden_set"][0]["plot_descriptors"][0]["capability"][
        "editable"
    ] = False
    rows = verify_golden_compatibility._compare_plot_descriptors(contract, current)
    assert any(row["classification"] == TEXT_ARTIFACT_DRIFT for row in rows)

    current = _current_plot_descriptors(contract)
    current["curated_golden_set"][0]["plot_descriptors"] = []
    rows = verify_golden_compatibility._compare_plot_descriptors(contract, current)
    assert any(
        row["classification"] == TEXT_ARTIFACT_DRIFT
        and row["detail"] == "Required plot descriptor is missing."
        for row in rows
    )

    current = _current_plot_descriptors(contract)
    extra = json.loads(
        json.dumps(current["curated_golden_set"][0]["plot_descriptors"][0])
    )
    extra["artifact_label"] = "Unexpected Plot"
    current["curated_golden_set"][0]["plot_descriptors"].append(extra)
    rows = verify_golden_compatibility._compare_plot_descriptors(contract, current)
    assert any(
        row["classification"] == TEXT_ARTIFACT_DRIFT
        and row["detail"] == "Unexpected plot descriptors were produced."
        for row in rows
    )


def test_current_golden_manifest_requires_exact_rpy2_identities():
    expected = dict(verify_golden_compatibility.REQUIRED_RPY2_IDENTITIES)
    case = {
        "id": "case",
        "tool_versions": dict(expected),
        "package_versions": dict(expected),
    }
    verify_golden_compatibility._validate_current_rpy2_identities(
        {"curated_golden_set": [case]}, expected
    )

    case["package_versions"]["rpy2-robjects"] = "0.0.0"
    with pytest.raises(ValueError, match="locked runtime"):
        verify_golden_compatibility._validate_current_rpy2_identities(
            {"curated_golden_set": [case]}, expected
        )


def test_real_r_verifiers_reject_null_or_mismatched_rpy2_identity(monkeypatch):
    monkeypatch.setattr(
        verify_rcmetar_r_stack.metadata,
        "version",
        lambda distribution: "0.0.0" if distribution == "rpy2" else "3.6.6",
    )
    with pytest.raises(
        verify_rcmetar_r_stack.VerificationError, match="identity mismatch"
    ):
        verify_rcmetar_r_stack.verify_rpy2_identities()

    monkeypatch.setattr(
        verify_golden_compatibility.metadata,
        "version",
        lambda _distribution: (_ for _ in ()).throw(
            verify_golden_compatibility.metadata.PackageNotFoundError
        ),
    )
    with pytest.raises(ValueError, match="required distribution is missing"):
        verify_golden_compatibility._validate_rpy2_identities(ROOT)


def test_analysis_regression_comparison_classifies_missing_output_unsupported_and_capture_error():
    baseline = _baseline()
    missing = compare_golden_baseline(baseline, {"curated_golden_set": []})["rows"][0]
    unsupported = compare_golden_baseline(baseline, _current(status="unsupported"))[
        "rows"
    ][0]
    failed = compare_golden_baseline(
        baseline, _current(status="failure", failure={"message": "R failed"})
    )["rows"][0]

    assert missing["classification"] == MISSING_OUTPUT
    assert unsupported["classification"] == UNSUPPORTED_WORKFLOW
    assert failed["classification"] == CAPTURE_ERROR


def test_analysis_regression_comparison_consumes_committed_manifest_ids():
    report = compare_golden_baseline(
        _baseline(),
        _current(),
        manifest={"curated_golden_set": ["amino-binary-random", "continuous-random"]},
    )

    assert report["passed"] is False
    assert report["rows"][0]["id"] == "continuous-random"
    assert report["rows"][0]["classification"] == MISSING_OUTPUT


def test_analysis_regression_comparison_marks_only_matching_exception_as_accepted():
    current = _current()
    current["curated_golden_set"][0]["outputs"]["Summary"]["estimate"] = 0.773

    report = compare_golden_baseline(
        _baseline(), current, [{"id": "amino-binary-random", "reason": "documented"}]
    )

    assert report["passed"] is True
    assert report["rows"][0]["classification"] == ACCEPTED_EXCEPTION
    assert report["rows"][0]["exception"] == "documented"


def test_scoped_exception_accepts_only_named_detail_and_classification():
    reference = _baseline()
    current = _current()
    current["curated_golden_set"][0]["texts"]["New Section"] = "intentional"
    current["curated_golden_set"][0]["outputs"]["Summary"]["unexpected"] = 1.0
    report = compare_golden_baseline(
        reference,
        current,
        exceptions=[
            {
                "id": "amino-binary-random",
                "reason": "reviewed output addition",
                "accepted_classifications": [TEXT_ARTIFACT_DRIFT],
                "accepted_details": [
                    "Unexpected text section New Section was produced."
                ],
            }
        ],
    )

    accepted = [
        row for row in report["rows"] if row["classification"] == ACCEPTED_EXCEPTION
    ]
    assert [row["detail"] for row in accepted] == [
        "Unexpected text section New Section was produced."
    ]
    assert any(
        row["classification"] == UNEXPECTED_OUTPUT
        and "unexpected numeric metric" in row["detail"]
        for row in report["rows"]
    )
    assert report["passed"] is False


def test_analysis_regression_comparison_cli_writes_report(tmp_path):
    reference = tmp_path / "reference.json"
    current = tmp_path / "current.json"
    report = tmp_path / "report.json"
    reference.write_text(json.dumps(_baseline()))
    current.write_text(json.dumps(_current()))

    assert main([str(reference), str(current), "--report", str(report)]) == 0
    assert json.loads(report.read_text())["passed"] is True


def test_curated_golden_set_includes_sequential_binary_and_continuous_workflows():
    with _import_legacy_golden_modules() as (golden_analysis, _, _):
        bundles = dict(
            (bundle["id"], bundle)
            for bundle in golden_analysis.curated_golden_bundles()
        )

    assert bundles["amino-binary-cumulative"]["case"].analysis_type == "cumulative"
    assert "Cumulative Summary" in bundles["amino-binary-cumulative"]["expected"]
    assert (
        bundles["amino-binary-leave-one-out"]["case"].analysis_type == "leave-one-out"
    )
    assert "Leave-one-out Summary" in bundles["amino-binary-leave-one-out"]["expected"]
    assert bundles["continuous-cumulative"]["case"].analysis_type == "cumulative"
    assert "Cumulative Summary" in bundles["continuous-cumulative"]["expected"]
    assert bundles["continuous-leave-one-out"]["case"].analysis_type == "leave-one-out"
    assert "Leave-one-out Summary" in bundles["continuous-leave-one-out"]["expected"]


def test_golden_summary_parser_reads_current_RCMetaR_summary_display():
    with _import_legacy_golden_modules() as (golden_analysis, _, _):
        parsed = golden_analysis._parse_summary(
            """
$model.title
[1] "Binary Random-Effects Model\\n\\nMetric: Odds Ratio"

$table.titles
[1] " Model Results"       " Heterogeneity"       " Results (log scale)"

$arrays
$arrays$arr1
               [,1]       [,2]          [,3]          [,4]
res.col.labels "Estimate" "Lower bound" "Upper bound" "p-Value"
res.col.vals   "0.770"    "0.485"       "1.222"       "0.267"

$arrays$arr2
               [,1]    [,2]       [,3]           [,4]
het.col.labels "tau^2" "Q(df=18)" "Het. p-Value" "I^2"
het.col.vals   "0.378" "33.360"   "0.015"        "46.044"

$arrays$arr3
alt.col.labels "Estimate" "Lower bound" "Upper bound" "Std. error"
alt.col.vals   "-0.262"   "-0.724"      "0.200"       "0.236"
"""
        )

    assert parsed == {
        "estimate": 0.770,
        "lower_bound": 0.485,
        "upper_bound": 1.222,
        "p_value": 0.267,
        "tau_squared": 0.378,
        "q": 33.360,
        "i_squared": 46.044,
    }


def test_golden_summary_parser_reads_modern_plain_text_heterogeneity_table():
    with _import_legacy_golden_modules() as (golden_analysis, _, _):
        parsed = golden_analysis._parse_summary(
            """Binary Random-Effects Model

Metric: Odds Ratio

Model Results
 Estimate  Lower bound  Upper bound  p-value
 0.770           0.485        1.222    0.267

Heterogeneity
 t²     Q(df=18)  Het. p-value     I²
 0.378    33.360         0.015  46.0%
"""
        )

    assert parsed == {
        "estimate": 0.770,
        "lower_bound": 0.485,
        "upper_bound": 1.222,
        "p_value": 0.267,
        "tau_squared": 0.378,
        "q": 33.360,
        "heterogeneity_df": 18.0,
        "heterogeneity_p_value": 0.015,
        "i_squared": 46.0,
    }


def test_golden_summary_parser_reads_researcher_facing_confidence_headers():
    with _import_legacy_golden_modules() as (golden_analysis, _, _):
        parsed = golden_analysis._parse_summary(
            """Continuous Random-Effects Model

Metric: Standardized Mean Difference

Model Results
 Estimate  Lower bound (95% CI)  Upper bound (95% CI)  Std. error  p-value
 0.358                    0.152                 0.565       0.105  < 0.001

Heterogeneity
 t²     Q(df=5)  Het. p-value     I²
 0.037   11.914         0.036  58.0%
"""
        )

    assert parsed == {
        "estimate": 0.358,
        "lower_bound": 0.152,
        "upper_bound": 0.565,
        "standard_error": 0.105,
        "p_value": 0.001,
        "tau_squared": 0.037,
        "q": 11.914,
        "heterogeneity_df": 5.0,
        "heterogeneity_p_value": 0.036,
        "i_squared": 58.0,
    }


def test_compare_bundle_requires_expected_plot_artifacts(tmp_path):
    with _import_legacy_golden_modules() as (golden_analysis, _, _):
        plot = tmp_path / "forest.png"
        plot.write_bytes(b"png")
        bundle = {
            "expected": {"Summary": {}},
            "artifacts": {"Forest Plot": str(plot)},
            "tolerances": {},
        }

        comparisons = golden_analysis.compare_bundle(
            bundle,
            {"texts": {"Summary": "ok"}, "images": {"forest plot": str(plot)}},
        )
        missing = golden_analysis.compare_bundle(
            bundle,
            {
                "texts": {"Summary": "ok"},
                "images": {"Forest Plot": str(tmp_path / "missing.png")},
            },
        )

    assert {
        "metric": "artifact_present",
        "section": "Forest Plot",
        "passed": True,
        "expected": True,
        "observed": True,
        "tolerance": None,
        "drift": None,
    } in comparisons
    assert any(
        row["metric"] == "artifact_present" and row["passed"] is False
        for row in missing
    )


def test_headless_analysis_dispatches_sequential_binary_and_continuous_workflows(
    monkeypatch, tmp_path
):
    with _import_legacy_golden_modules() as (_, headless_analysis, meta_globals):
        from rc_metastudio import analysis_adapter

        calls = []

        class Model(object):
            dataset = object()
            current_effect = "OR"

            def set_current_metric(self, metric):
                calls.append(("metric", metric))
                self.current_effect = metric

        monkeypatch.setattr(
            headless_analysis, "load_dataset_model", lambda path: Model()
        )
        monkeypatch.setattr(
            analysis_adapter.r_bridge,
            "dataset_to_simple_binary_r_object",
            lambda model: calls.append(("data", "binary")),
            raising=False,
        )
        monkeypatch.setattr(
            analysis_adapter.r_bridge,
            "dataset_to_simple_continuous_r_object",
            lambda model: calls.append(("data", "continuous")),
            raising=False,
        )
        monkeypatch.setattr(
            analysis_adapter.r_bridge,
            "run_workflow_analysis",
            lambda workflow, method, params: {
                "texts": {"Summary": "%s:%s" % (workflow, method)}
            },
            raising=False,
        )

        binary = headless_analysis.HeadlessAnalysisCase(
            str(tmp_path / "b.rcms"),
            "binary.random",
            {"measure": "OR"},
            data_type=meta_globals.BINARY,
            analysis_type="cumulative",
        )
        continuous = headless_analysis.HeadlessAnalysisCase(
            str(tmp_path / "c.rcms"),
            "continuous.random",
            {"measure": "SMD"},
            data_type=meta_globals.CONTINUOUS,
            analysis_type="leave-one-out",
        )

        assert (
            headless_analysis.run_headless_analysis(binary)["texts"]["Summary"]
            == "cumulative:binary.random"
        )
        assert (
            headless_analysis.run_headless_analysis(continuous)["texts"]["Summary"]
            == "leave-one-out:continuous.random"
        )
        assert [call for call in calls if call[0] == "metric"] == [
            ("metric", "OR"),
            ("metric", "SMD"),
        ]


def test_headless_analysis_uses_restored_metric_or_reports_missing_metric(
    monkeypatch, tmp_path
):
    with _import_legacy_golden_modules() as (_, headless_analysis, meta_globals):
        from rc_metastudio import analysis_adapter

        class Model(object):
            dataset = object()

            def __init__(self, current_effect):
                self.current_effect = current_effect

            def set_current_metric(self, metric):
                self.current_effect = metric

        model = Model("OR")
        monkeypatch.setattr(headless_analysis, "load_dataset_model", lambda path: model)
        monkeypatch.setattr(
            analysis_adapter.r_bridge,
            "dataset_to_simple_binary_r_object",
            lambda model: None,
            raising=False,
        )
        monkeypatch.setattr(
            analysis_adapter.r_bridge,
            "run_binary_analysis",
            lambda method, params: {"texts": {"Summary": params["measure"]}},
            raising=False,
        )

        explicit_case = headless_analysis.HeadlessAnalysisCase(
            str(tmp_path / "explicit.rcms"),
            "binary.random",
            {"measure": "OR"},
            metric="RR",
            data_type=meta_globals.BINARY,
        )
        assert (
            headless_analysis.run_headless_analysis(explicit_case)["texts"]["Summary"]
            == "RR"
        )
        assert explicit_case.parameters == {"measure": "OR"}

        model.current_effect = "OR"
        restored_case = headless_analysis.HeadlessAnalysisCase(
            str(tmp_path / "restored.rcms"),
            "binary.random",
            {},
            data_type=meta_globals.BINARY,
        )
        assert (
            headless_analysis.run_headless_analysis(restored_case)["texts"]["Summary"]
            == "OR"
        )

        model.current_effect = None
        with pytest.raises(ValueError, match="metric must be a non-empty string"):
            headless_analysis.run_headless_analysis(restored_case)


def test_headless_diagnostic_metric_overrides_stale_method_parameters(
    monkeypatch, tmp_path
):
    with _import_legacy_golden_modules() as (_, headless_analysis, meta_globals):
        from rc_metastudio import analysis_adapter

        class DiagnosticModel(object):
            dataset = object()

            def __init__(self):
                self.current_metric = None

            def included_studies_have_raw_data(self):
                return True

            def included_studies_have_point_estimates(self, effect):
                return True

            def set_current_metric(self, metric):
                self.current_metric = metric

        class DiagnosticBackend(object):
            def __init__(self):
                self.conversions = []
                self.runs = []

            def convert(self, model, **kwargs):
                self.conversions.append((model, kwargs))

            def run(self, method_names, parameter_values):
                self.runs.append((method_names, parameter_values))
                return {"texts": {}, "images": {}}

        model = DiagnosticModel()
        backend = DiagnosticBackend()

        def load_model(path):
            return model

        monkeypatch.setattr(headless_analysis, "load_dataset_model", load_model)
        monkeypatch.setattr(
            analysis_adapter.r_bridge,
            "dataset_to_simple_diagnostic_r_object",
            backend.convert,
            raising=False,
        )
        monkeypatch.setattr(
            analysis_adapter.r_bridge,
            "run_diagnostic_multi",
            backend.run,
            raising=False,
        )

        parameters = [
            {"measure": "DOR", "conf.level": 95.0},
            {"measure": "PLR", "conf.level": 90.0},
        ]
        case = headless_analysis.HeadlessAnalysisCase(
            str(tmp_path / "diagnostic.rcms"),
            ["diagnostic.random", "diagnostic.reitsma"],
            parameters,
            metric="Sens",
            data_type=meta_globals.DIAGNOSTIC,
        )

        headless_analysis.run_headless_analysis(case)

        assert backend.runs == [
            (
                ["diagnostic.random", "diagnostic.reitsma"],
                [
                    {"measure": "Sens", "conf.level": 95.0},
                    {"measure": "Sens", "conf.level": 90.0},
                ],
            )
        ]
        assert parameters == [
            {"measure": "DOR", "conf.level": 95.0},
            {"measure": "PLR", "conf.level": 90.0},
        ]


def test_headless_analysis_dispatches_meta_regression_with_selected_covariates(
    monkeypatch, tmp_path
):
    with _import_legacy_golden_modules() as (_, headless_analysis, meta_globals):
        from rc_metastudio import analysis_adapter

        calls = []

        class DataSet(object):
            def get_covariate_values(self, covariate, ids_for_keys=False):
                assert ids_for_keys is True
                return {0: 1990}

            def add_covariate(self, covariate, values):
                calls.append(("covariate", covariate, values))

        class Study(object):
            id = 0

        class Model(object):
            def __init__(self):
                self.dataset = DataSet()
                self.studies = (Study(),)

            def get_studies(self, only_if_included=True):
                assert only_if_included is True
                return list(self.studies)

            def set_current_metric(self, metric):
                calls.append(("metric", metric))

        class Covariate(object):
            def __init__(self, name, data_type):
                self.name = name
                self.data_type = data_type

        monkeypatch.setattr(headless_analysis.analysis_dataset, "Covariate", Covariate)

        covariates = [
            {"name": "golden_year", "type": "continuous", "values": {"Study A": 1990}}
        ]

        model = Model()
        monkeypatch.setattr(headless_analysis, "load_dataset_model", lambda path: model)
        monkeypatch.setattr(
            analysis_adapter.r_bridge,
            "dataset_to_simple_binary_r_object",
            lambda model, **kwargs: calls.append(("data", kwargs)),
            raising=False,
        )
        monkeypatch.setattr(
            analysis_adapter.r_bridge,
            "run_meta_regression",
            lambda dataset, studies, covs, metric, confidence_level=None, params=None, **kwargs: {
                "texts": {"Summary": metric}
            },
            raising=False,
        )

        case = headless_analysis.HeadlessAnalysisCase(
            str(tmp_path / "b.rcms"),
            None,
            {"conf.level": 95.0},
            metric="OR",
            data_type=meta_globals.BINARY,
            analysis_type="meta_regression",
            covariates=covariates,
        )

        assert headless_analysis.run_headless_analysis(case)["texts"]["Summary"] == "OR"
        data_call = next(call for call in calls if call[0] == "data")
        assert data_call[1]["include_raw_data"] is False
        assert data_call[1]["studies"] == model.studies
        assert data_call[1]["covs_to_include"][0].name == "golden_year"


def test_comprehensive_golden_baseline_capture_writes_reproducible_bundle(
    tmp_path, monkeypatch
):
    with _import_legacy_golden_modules() as (golden_analysis, _, _):
        bundles = [
            _capture_bundle("amino-binary-random", "amino.rcms", "binary.random"),
            _capture_bundle(
                "continuous-random", "continuous.rcms", "continuous.random"
            ),
        ]
        plot = tmp_path / "plot.png"
        plot.write_bytes(b"plot")

        monkeypatch.setattr(
            golden_analysis, "curated_golden_bundles", lambda root_dir=None: bundles
        )
        monkeypatch.setattr(
            golden_analysis.r_bridge,
            "RLibraryLoader",
            lambda: types.SimpleNamespace(load_rcmetar=lambda: None),
        )
        monkeypatch.setattr(golden_analysis, "_commit_sha", lambda: "abc123")
        monkeypatch.setattr(
            golden_analysis,
            "_tool_versions",
            lambda: {
                "rc_metastudio": "0.1.0",
                "python": "3.11.15",
                "os": "Windows",
                "r": "R version 4.6.0",
                "rpy2": "3.6.7",
                "pyqt": "5.15.11",
            },
        )

        def runner(case):
            if case == "failing-case":
                raise RuntimeError("RC MetaStudio baseline capture failed")
            return {
                "texts": {
                    "Summary": "Estimate Lower bound Upper bound\n 1.0 0.5 1.5 0.02"
                },
                "images": {"Forest Plot": str(plot)},
            }

        report = golden_analysis.capture_comprehensive_golden_baseline(
            output_dir=str(tmp_path / "artifacts" / "golden-baseline"),
            runner=runner,
            timestamp="2026-06-23T00:00:00Z",
            capture_mode="authoritative",
            capture_command="capture command",
            baseline_environment=dict(
                golden_analysis.MODERN_BASELINE_ENVIRONMENT_EXPECTED
            ),
        )

    capture_dir = tmp_path / "artifacts" / "golden-baseline" / "captures"
    archive_path = (
        tmp_path / "artifacts" / "golden-baseline" / "comprehensive-golden-baseline.zip"
    )

    assert report["baseline"] == "comprehensive-golden"
    assert report["passed"] is False
    assert [row["status"] for row in report["curated_golden_set"]] == [
        "success",
        "failure",
    ]
    assert report["curated_golden_set"][0]["authoritative"] is True
    assert (capture_dir / "amino-binary-random.json").exists()
    assert (capture_dir / "continuous-random.json").exists()
    assert archive_path.exists()
    assert report["artifact_bundle"]["path"].endswith(
        "comprehensive-golden-baseline.zip"
    )


@contextmanager
def _import_legacy_golden_modules():
    names = [
        "golden_analysis",
        "headless_analysis",
        "dataset_table_model",
        "analysis_dataset",
        "meta_globals",
        "r_bridge",
        "rc_metastudio.r_bridge",
    ]
    previous = dict((name, sys.modules.get(name)) for name in names)
    try:
        for name in ["golden_analysis", "headless_analysis"]:
            sys.modules.pop(name, None)
        model_module = ModuleType("dataset_table_model")
        setattr(model_module, "DatasetTableModel", object)
        sys.modules["dataset_table_model"] = model_module
        dataset_module = ModuleType("analysis_dataset")
        setattr(dataset_module, "Covariate", lambda name, kind: (name, kind))
        sys.modules["analysis_dataset"] = dataset_module
        globals_module = ModuleType("meta_globals")
        setattr(globals_module, "BINARY", "binary")
        setattr(globals_module, "CONTINUOUS", "continuous")
        setattr(globals_module, "DIAGNOSTIC", "diagnostic")
        setattr(globals_module, "VERSION", "0.1.0")
        sys.modules["meta_globals"] = globals_module
        r_boundary = ModuleType("r_bridge")
        setattr(r_boundary, "RLibraryLoader", lambda: None)
        sys.modules["rc_metastudio.r_bridge"] = r_boundary
        from rc_metastudio import golden_analysis
        from rc_metastudio import headless_analysis
        from rc_metastudio import meta_globals

        yield golden_analysis, headless_analysis, meta_globals
    finally:
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def _baseline():
    return {
        "curated_golden_set": [
            {
                "id": "amino-binary-random",
                "dataset": "amino.rcms",
                "method": "binary.random",
                "metric": "OR",
                "tolerances": {"estimate": 0.001},
                "outputs": {"Summary": {"estimate": 0.77}},
                "texts": {"Summary": "same summary"},
                "artifacts": [
                    {
                        "label": "Forest Plot",
                        "kind": "plot",
                        "path": "reference.png",
                        "sha256": "a" * 64,
                    }
                ],
            }
        ]
    }


def _capture_bundle(bundle_id, dataset, method):
    return {
        "id": bundle_id,
        "dataset": dataset,
        "data_family": "binary",
        "method": method,
        "metric": "OR",
        "parameters": {},
        "tolerances": {"estimate": 0.001},
        "expected": {"Summary": {}},
        "artifacts": {"Forest Plot": "./r_tmp/%s.png" % bundle_id},
        "case": "failing-case" if "continuous" in bundle_id else "passing-case",
    }


def _current(status="success", failure=None):
    row = {
        "id": "amino-binary-random",
        "status": status,
        "outputs": {"Summary": {"estimate": 0.7705}},
        "texts": {"Summary": "same summary"},
        "artifacts": [
            {
                "label": "Forest Plot",
                "kind": "plot",
                "path": "reference.png",
                "sha256": "a" * 64,
            }
        ],
    }
    if failure:
        row["failure"] = failure
    return {"curated_golden_set": [row]}


def _copy_frozen_contract(tmp_path):
    root = tmp_path / "repo"
    relative_dir = Path("tests/analysis_regression/baseline")
    target_dir = root / relative_dir
    target_dir.mkdir(parents=True)
    for filename in (
        "manifest.json",
        "observed-golden-baseline.zip",
        "plot-descriptors.json",
        "numeric-contract.json",
    ):
        shutil.copy2(ROOT / relative_dir / filename, target_dir / filename)
    return root


def _update_outer_file_contract(root, key, path):
    outer_path = root / verify_golden_compatibility.OUTER_MANIFEST_RELATIVE_PATH
    outer = json.loads(outer_path.read_text(encoding="utf-8"))
    payload = path.read_bytes()
    outer[key]["size"] = len(payload)
    import hashlib

    outer[key]["sha256"] = hashlib.sha256(payload).hexdigest()
    outer_path.write_text(json.dumps(outer), encoding="utf-8")


def _rewrite_zip(source, target, replacements, extra=None):
    extra = extra or {}
    with (
        zipfile.ZipFile(source) as original,
        zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as rewritten,
    ):
        for info in original.infolist():
            rewritten.writestr(
                info.filename,
                replacements.get(info.filename, original.read(info.filename)),
            )
        for name, payload in extra.items():
            rewritten.writestr(name, payload)


def _current_plot_descriptors(contract):
    rows = []
    for expected in contract["rows"]:
        rows.append(
            {
                "id": expected["id"],
                "dataset": "sample.rcms",
                "method": "method",
                "metric": "metric",
                "plot_descriptors": [
                    {
                        "artifact_label": expected["artifact_label"],
                        "capability": dict(expected["capability"]),
                        "display": {
                            "identity": expected["display"]["identity"],
                            "name": expected["display"]["name"],
                            "type": expected["display"]["type"],
                            "sha256": "a" * 64,
                        },
                    }
                ],
            }
        )
    return {"curated_golden_set": rows}
