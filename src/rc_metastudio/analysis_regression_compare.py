import argparse
import json
import math
import os
import re
import sys


PASS = "pass"
NUMERIC_DRIFT = "numeric_drift"
TEXT_ARTIFACT_DRIFT = "text_artifact_drift"
MISSING_OUTPUT = "missing_output"
UNSUPPORTED_WORKFLOW = "unsupported_workflow"
CAPTURE_ERROR = "capture_error"
ACCEPTED_EXCEPTION = "accepted_exception"
UNEXPECTED_OUTPUT = "unexpected_output"
MALFORMED_OUTPUT = "malformed_output"


def compare_golden_baseline(reference, current, exceptions=None, manifest=None):
    exceptions = exceptions or []
    manifest_rows = _manifest_rows(manifest)
    current_by_id = _by_id(
        current.get("curated_golden_set", current.get("results", []))
    )
    reference_rows = reference.get("curated_golden_set", reference.get("results", []))
    reference_by_id = _by_id(reference_rows)
    rows = []
    for missing_id in sorted(set(manifest_rows) - set(reference_by_id)):
        rows.append(
            {
                "id": missing_id,
                "dataset": None,
                "metric": None,
                "method": None,
                "classification": MISSING_OUTPUT,
                "detail": "Committed manifest row is missing from the reference curated golden set.",
            }
        )
    for expected in reference_rows:
        row_id = expected["id"]
        actual = current_by_id.get(row_id)
        if actual is None:
            rows.append(
                _row(
                    expected,
                    MISSING_OUTPUT,
                    "No current output for curated golden bundle.",
                )
            )
            continue
        rows.extend(_compare_row(expected, actual, exceptions))
    for extra_id in sorted(set(current_by_id) - set(reference_by_id)):
        rows.append(
            _row(
                current_by_id[extra_id],
                UNEXPECTED_OUTPUT,
                "Current capture contains a case absent from the frozen baseline.",
            )
        )
    return {
        "mode": "analysis-regression-comparison",
        "rows": rows,
        "passed": all(
            row["classification"] in [PASS, ACCEPTED_EXCEPTION] for row in rows
        ),
    }


def _compare_row(expected, actual, exceptions):
    row_id = expected["id"]
    accepted = _accepted_exception(row_id, exceptions)
    if actual.get("status") == "unsupported":
        return [
            _row(
                expected,
                _maybe_accepted(UNSUPPORTED_WORKFLOW, accepted),
                actual.get(
                    "reason", "Workflow is not supported by the maintained path."
                ),
                accepted,
            )
        ]
    if actual.get("status") == "failure" or actual.get("failure"):
        failure = actual.get("failure", {})
        return [
            _row(
                expected,
                _maybe_accepted(CAPTURE_ERROR, accepted),
                failure.get("message", "Current capture failed."),
                accepted,
            )
        ]

    rows = []
    rows.extend(_compare_numbers(expected, actual, accepted))
    rows.extend(
        _compare_texts_and_artifacts(
            expected,
            actual,
            accepted,
            expected_os=_capture_os(expected),
            actual_os=_capture_os(actual),
        )
    )
    return rows or [
        _row(expected, PASS, "Current output matches the curated golden bundle.")
    ]


def _compare_numbers(expected, actual, accepted):
    rows = []
    tolerances = expected.get("tolerances", {})
    actual_outputs = actual.get("outputs", {})
    expected_outputs = expected.get("outputs", expected.get("expected", {}))
    for section, metrics in expected_outputs.items():
        for metric, expected_value in metrics.items():
            actual_section = actual_outputs.get(section)
            if not isinstance(actual_section, dict) or metric not in actual_section:
                rows.append(
                    _row(
                        expected,
                        _maybe_accepted(MISSING_OUTPUT, accepted),
                        "%s.%s is missing." % (section, metric),
                        accepted,
                    )
                )
                continue
            actual_value = actual_section[metric]
            if not _is_finite_real_number(expected_value):
                rows.append(
                    _row(
                        expected,
                        MALFORMED_OUTPUT,
                        "%s.%s reference numeric value is malformed."
                        % (section, metric),
                    )
                )
                continue
            if not _is_finite_real_number(actual_value):
                rows.append(
                    _row(
                        expected,
                        MALFORMED_OUTPUT,
                        "%s.%s current numeric value is malformed."
                        % (section, metric),
                    )
                )
                continue
            drift = abs(actual_value - expected_value)
            policy = expected.get("numeric_tolerance_policy")
            if policy:
                absolute = policy["absolute"]
                relative = policy["relative"]
                tolerance = max(absolute, relative * abs(expected_value))
                tolerance_detail = "abs %s / rel %s" % (absolute, relative)
            else:
                tolerance = tolerances.get(metric, 0)
                tolerance_detail = str(tolerance)
            if drift > tolerance:
                rows.append(
                    _row(
                        expected,
                        _maybe_accepted(NUMERIC_DRIFT, accepted),
                        "%s.%s drifted by %s with tolerance %s."
                        % (section, metric, drift, tolerance_detail),
                        accepted,
                    )
                )
            else:
                rows.append(
                    _row(
                        expected,
                        PASS,
                        "%s.%s matched within tolerance %s."
                        % (section, metric, tolerance_detail),
                    )
                )
        for metric in sorted(set(actual_outputs.get(section, {})) - set(metrics)):
            rows.append(
                _row(
                    expected,
                    _maybe_accepted(UNEXPECTED_OUTPUT, accepted),
                    "%s.%s is an unexpected numeric metric." % (section, metric),
                    accepted,
                )
            )
    for section in sorted(set(actual_outputs) - set(expected_outputs)):
        rows.append(
            _row(
                expected,
                _maybe_accepted(UNEXPECTED_OUTPUT, accepted),
                "Unexpected numeric section %s was produced." % section,
                accepted,
            )
        )
    return rows


def _is_finite_real_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _compare_texts_and_artifacts(
    expected, actual, accepted, expected_os=None, actual_os=None
):
    rows = []
    cross_platform = bool(expected_os and actual_os and expected_os != actual_os)
    expected_texts = expected.get("texts", {})
    actual_texts = actual.get("texts", {})
    for section in expected_texts:
        if section not in actual.get("texts", {}):
            rows.append(
                _row(
                    expected,
                    _maybe_accepted(MISSING_OUTPUT, accepted),
                    "Text section %s is missing." % section,
                    accepted,
                )
            )
        else:
            expected_text = _normalize_text(
                expected_texts[section], cross_platform=cross_platform
            )
            actual_text = _normalize_text(
                actual_texts[section], cross_platform=cross_platform
            )
            raw_text_differs = _normalize_text(
                actual_texts[section]
            ) != _normalize_text(expected_texts[section])
            if actual_text != expected_text:
                rows.append(
                    _row(
                        expected,
                        _maybe_accepted(TEXT_ARTIFACT_DRIFT, accepted),
                        "Text section %s changed." % section,
                        accepted,
                    )
                )
            elif cross_platform and raw_text_differs:
                rows.append(
                    _row(
                        expected,
                        PASS,
                        (
                            "Text section %s matched after cross-platform "
                            "heterogeneity-header normalization (%s -> %s: t² <-> τ²)."
                            % (section, expected_os, actual_os)
                        ),
                    )
                )
            else:
                rows.append(
                    _row(expected, PASS, "Text section %s matched." % section)
                )
    for section in sorted(set(actual_texts) - set(expected_texts)):
        rows.append(
            _row(
                expected,
                _maybe_accepted(TEXT_ARTIFACT_DRIFT, accepted),
                "Unexpected text section %s was produced." % section,
                accepted,
            )
        )
    expected_artifacts = dict(
        (item["label"], item) for item in expected.get("artifacts", [])
    )
    actual_artifacts = dict(
        (item["label"], item) for item in actual.get("artifacts", [])
    )
    for label, expected_artifact in expected_artifacts.items():
        actual_artifact = actual_artifacts.get(label)
        if actual_artifact is None:
            rows.append(
                _row(
                    expected,
                    _maybe_accepted(MISSING_OUTPUT, accepted),
                    "Artifact %s is missing." % label,
                    accepted,
                )
            )
        else:
            expected_descriptor = _artifact_descriptor(expected_artifact)
            actual_descriptor = _artifact_descriptor(actual_artifact)
            descriptor_matches = (
                _artifact_identity_descriptor(actual_descriptor)
                == _artifact_identity_descriptor(expected_descriptor)
            )
            if cross_platform:
                hashes_valid = _valid_sha256(
                    expected_descriptor["sha256"]
                ) and _valid_sha256(actual_descriptor["sha256"])
                passed = descriptor_matches and hashes_valid
                detail = (
                    "Artifact %s descriptor matched; content SHA-256 was "
                    "validated but byte equality was not required by the "
                    "cross-platform artifact policy (%s -> %s)."
                    % (label, expected_os, actual_os)
                )
                if not descriptor_matches:
                    detail = (
                        "Artifact %s descriptor changed under the cross-platform "
                        "artifact policy (%s -> %s)."
                        % (label, expected_os, actual_os)
                    )
                elif not hashes_valid:
                    detail = (
                        "Artifact %s has a missing or invalid reference/current SHA-256 "
                        "under the cross-platform artifact policy (%s -> %s)."
                        % (label, expected_os, actual_os)
                    )
            else:
                passed = (
                    actual_descriptor == expected_descriptor
                    and _valid_sha256(expected_descriptor["sha256"])
                    and _valid_sha256(actual_descriptor["sha256"])
                )
                if expected_os and expected_os == actual_os:
                    detail = (
                        "Artifact %s descriptor and content matched under the "
                        "same-platform exact artifact policy (%s)."
                        % (label, expected_os)
                    )
                    if not passed:
                        detail = (
                            "Artifact %s descriptor or content changed under the "
                            "same-platform exact artifact policy (%s)."
                            % (label, expected_os)
                        )
                else:
                    detail = "Artifact %s descriptor and content matched exactly." % label
                    if not passed:
                        detail = "Artifact %s descriptor or content changed." % label
            rows.append(
                _row(
                    expected,
                    PASS if passed else _maybe_accepted(TEXT_ARTIFACT_DRIFT, accepted),
                    detail,
                    accepted if not passed else None,
                )
            )
    for label in sorted(set(actual_artifacts) - set(expected_artifacts)):
        rows.append(
            _row(
                expected,
                _maybe_accepted(TEXT_ARTIFACT_DRIFT, accepted),
                "Unexpected artifact %s was produced." % label,
                accepted,
            )
        )
    return rows


def _artifact_descriptor(artifact):
    path = artifact.get("bundle_path") or artifact.get("path") or ""
    basename = os.path.basename(path.replace("\\", "/"))
    extension = os.path.splitext(basename)[1].lower()
    metadata = dict(artifact.get("metadata", {}))
    for key, value in artifact.items():
        if key not in {"bundle_path", "path", "label", "sha256", "metadata"}:
            metadata[key] = value
    return {
        "label": artifact.get("label"),
        "name": basename,
        "type": extension.lstrip("."),
        "sha256": artifact.get("sha256"),
        "metadata": metadata,
    }


def _artifact_identity_descriptor(descriptor):
    return dict((key, value) for key, value in descriptor.items() if key != "sha256")


def _valid_sha256(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _capture_os(bundle):
    tool_versions = bundle.get("tool_versions", {})
    if not isinstance(tool_versions, dict):
        return None
    value = tool_versions.get("os")
    return value if isinstance(value, str) and value else None


def _normalize_text(value, cross_platform=False):
    lines = str(value).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    normalized = "\n".join(line.rstrip() for line in lines).strip()
    if cross_platform:
        normalized = re.sub(
            r"(?m)^(\s*)τ²(?=\s+Q(?:\(|\s))",
            r"\1t²",
            normalized,
        )
    return normalized


def _accepted_exception(row_id, exceptions):
    for exception in exceptions:
        if exception.get("id") == row_id or row_id in exception.get("ids", []):
            return exception
    return None


def _maybe_accepted(classification, exception):
    return ACCEPTED_EXCEPTION if exception else classification


def _row(bundle, classification, detail, exception=None):
    row = {
        "id": bundle["id"],
        "dataset": bundle.get("dataset"),
        "metric": bundle.get("metric"),
        "method": bundle.get("method"),
        "classification": classification,
        "detail": detail,
    }
    if exception:
        row["exception"] = exception.get("reason", "")
    return row


def _by_id(items):
    return dict((item["id"], item) for item in items)


def _manifest_rows(manifest):
    return [] if not manifest else manifest.get("curated_golden_set", [])


def _load_json(path):
    with open(path) as f:
        return json.load(f)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compare current analysis captures against the curated golden baseline."
    )
    parser.add_argument("reference")
    parser.add_argument("current")
    parser.add_argument("--exceptions")
    parser.add_argument("--manifest")
    parser.add_argument("--report")
    args = parser.parse_args(argv)
    report = compare_golden_baseline(
        _load_json(args.reference),
        _load_json(args.current),
        _load_json(args.exceptions).get("exceptions", []) if args.exceptions else [],
        _load_json(args.manifest) if args.manifest else None,
    )
    output = json.dumps(report, indent=2, sort_keys=True)
    if args.report:
        with open(args.report, "w") as f:
            f.write(output + "\n")
    print(output)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
