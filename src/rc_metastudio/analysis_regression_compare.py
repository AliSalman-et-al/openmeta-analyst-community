import argparse
import json
import sys


PASS = "pass"
NUMERIC_DRIFT = "numeric_drift"
TEXT_ARTIFACT_DRIFT = "text_artifact_drift"
MISSING_OUTPUT = "missing_output"
UNSUPPORTED_WORKFLOW = "unsupported_workflow"
CAPTURE_ERROR = "capture_error"
ACCEPTED_EXCEPTION = "accepted_exception"


def compare_golden_baseline(reference, current, exceptions=None, manifest=None):
    exceptions = exceptions or []
    manifest_rows = _manifest_rows(manifest)
    current_by_id = _by_id(current.get("curated_golden_set", current.get("results", [])))
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
                actual.get("reason", "Workflow is not supported by the maintained path."),
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
    rows.extend(_compare_texts_and_artifacts(expected, actual, accepted))
    return rows or [
        _row(expected, PASS, "Current output matches the curated golden bundle.")
    ]


def _compare_numbers(expected, actual, accepted):
    rows = []
    tolerances = expected.get("tolerances", {})
    actual_outputs = actual.get("outputs", {})
    for section, metrics in expected.get(
        "outputs", expected.get("expected", {})
    ).items():
        for metric, expected_value in metrics.items():
            actual_value = actual_outputs.get(section, {}).get(metric)
            if actual_value is None:
                rows.append(
                    _row(
                        expected,
                        _maybe_accepted(MISSING_OUTPUT, accepted),
                        "%s.%s is missing." % (section, metric),
                        accepted,
                    )
                )
                continue
            drift = abs(actual_value - expected_value)
            tolerance = tolerances.get(metric, 0)
            if drift > tolerance:
                rows.append(
                    _row(
                        expected,
                        _maybe_accepted(NUMERIC_DRIFT, accepted),
                        "%s.%s drifted by %s with tolerance %s."
                        % (section, metric, drift, tolerance),
                        accepted,
                    )
                )
    return rows


def _compare_texts_and_artifacts(expected, actual, accepted):
    rows = []
    for section in expected.get("texts", {}):
        if section not in actual.get("texts", {}):
            rows.append(
                _row(
                    expected,
                    _maybe_accepted(MISSING_OUTPUT, accepted),
                    "Text section %s is missing." % section,
                    accepted,
                )
            )
        elif actual["texts"][section] != expected["texts"][section]:
            rows.append(
                _row(
                    expected,
                    _maybe_accepted(TEXT_ARTIFACT_DRIFT, accepted),
                    "Text section %s changed." % section,
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
        elif _artifact_metadata(actual_artifact) != _artifact_metadata(
            expected_artifact
        ):
            rows.append(
                _row(
                    expected,
                    _maybe_accepted(TEXT_ARTIFACT_DRIFT, accepted),
                    "Artifact %s metadata changed." % label,
                    accepted,
                )
            )
    return rows


def _artifact_metadata(artifact):
    return dict(
        (key, value) for key, value in artifact.items() if key not in ["path", "sha256"]
    )


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
