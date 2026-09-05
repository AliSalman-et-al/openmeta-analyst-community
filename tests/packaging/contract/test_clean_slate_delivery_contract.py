import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from jsonschema import validate

from ._workflow import load_workflow


ROOT = Path(__file__).resolve().parents[3]


def load_delivery():
    path = ROOT / "scripts" / "delivery.py"
    spec = importlib.util.spec_from_file_location("delivery_contract_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def workflow_step(workflow, job_name: str, step_name: str):
    return next(
        step
        for step in workflow["jobs"][job_name]["steps"]
        if step.get("name") == step_name
    )


def test_clean_slate_delivery_state_machine(tmp_path):
    delivery = load_delivery()
    manifest_path = tmp_path / "release-set.json"
    commit = "a" * 40
    release_version = delivery.repository_version()
    rc_version = f"{release_version}-rc.1"
    delivery.init_release(
        argparse.Namespace(
            version=rc_version,
            commit=commit,
            repository="AliSalman-et-al/rc-metastudio",
            trust_profile="unsigned-community",
            target=["windows-x64", "macos-arm64"],
            output=str(manifest_path),
        )
    )
    manifest = delivery.load(manifest_path)
    schema = json.loads(
        (ROOT / "delivery/release-set.schema.json").read_text(encoding="utf-8")
    )
    validate(instance=manifest, schema=schema)
    assert manifest["channel"] == "candidate"
    assert set(manifest["policy_inputs"]) == set(delivery.POLICY_INPUTS)
    assert "scripts/test-bounded-package-process.ps1" in delivery.POLICY_INPUTS
    assert "scripts/qt6_macos_feasibility.py" in delivery.POLICY_INPUTS
    assert "scripts/normalize_macos_macho.py" in delivery.POLICY_INPUTS
    assert "scripts/sign_macos_app.py" in delivery.POLICY_INPUTS
    assert "scripts/sign-notarize-macos-artifact.sh" in delivery.POLICY_INPUTS
    assert "config/macos-package-targets.json" in delivery.POLICY_INPUTS
    assert ".github/workflows/community-release-candidate.yml" in delivery.POLICY_INPUTS
    assert (
        ".github/workflows/macos-trusted-release-candidate.yml"
        in delivery.POLICY_INPUTS
    )
    assert manifest["release_targets"] == ["windows-x64", "macos-arm64"]
    for target in manifest["release_targets"]:
        previous = delivery.release_identity_digest(manifest)
        for stage in delivery.required_stages(manifest, target):
            artifact = tmp_path / f"{target}-{stage}.bin"
            artifact.write_bytes(f"{target}:{stage}".encode())
            result = tmp_path / f"{target}-{stage}.json"
            delivery.stage_result(
                argparse.Namespace(
                    target=target,
                    stage=stage,
                    commit=commit,
                    input_digest=previous,
                    output_file=[str(artifact)],
                    result=str(result),
                )
            )
            delivery.attach(
                argparse.Namespace(manifest=str(manifest_path), result=str(result))
            )
            previous = delivery.canonical_digest(delivery.load(result))
    delivery.verify(argparse.Namespace(manifest=str(manifest_path)))
    rc_path = tmp_path / "release-set-rc.json"
    delivery.promote(
        argparse.Namespace(
            manifest=str(manifest_path),
            from_channel="candidate",
            channel="rc",
            version=None,
            output=str(rc_path),
        )
    )
    with pytest.raises(ValueError, match="requires the macos-trusted profile"):
        delivery.promote(
            argparse.Namespace(
                manifest=str(rc_path),
                from_channel="rc",
                channel="stable",
                version=release_version,
                output=str(tmp_path / "unsigned-stable.json"),
            )
        )

    trusted_manifest_path = tmp_path / "macos-trusted-release-set.json"
    delivery.init_release(
        argparse.Namespace(
            version=rc_version,
            commit=commit,
            repository="AliSalman-et-al/rc-metastudio",
            trust_profile="macos-trusted",
            target=["windows-x64", "macos-arm64"],
            output=str(trusted_manifest_path),
        )
    )
    trusted_manifest = delivery.load(trusted_manifest_path)
    validate(instance=trusted_manifest, schema=schema)
    assert delivery.required_stages(trusted_manifest, "windows-x64") == [
        "assembled",
        "unsigned-qualified",
        "verified",
        "attested",
    ]
    assert delivery.required_stages(trusted_manifest, "macos-arm64") == [
        "assembled",
        "signed",
        "notarized",
        "verified",
        "attested",
    ]
    for target in trusted_manifest["release_targets"]:
        previous = delivery.release_identity_digest(trusted_manifest)
        for stage in delivery.required_stages(trusted_manifest, target):
            artifact = tmp_path / f"trusted-{target}-{stage}.bin"
            artifact.write_bytes(f"trusted:{target}:{stage}".encode())
            result = tmp_path / f"trusted-{target}-{stage}.json"
            delivery.stage_result(
                argparse.Namespace(
                    target=target,
                    stage=stage,
                    commit=commit,
                    input_digest=previous,
                    output_file=[str(artifact)],
                    result=str(result),
                )
            )
            delivery.attach(
                argparse.Namespace(
                    manifest=str(trusted_manifest_path), result=str(result)
                )
            )
            previous = delivery.canonical_digest(delivery.load(result))
    delivery.verify(argparse.Namespace(manifest=str(trusted_manifest_path)))
    trusted_rc_path = tmp_path / "macos-trusted-release-set-rc.json"
    delivery.promote(
        argparse.Namespace(
            manifest=str(trusted_manifest_path),
            from_channel="candidate",
            channel="rc",
            version=None,
            output=str(trusted_rc_path),
        )
    )
    stable_path = tmp_path / "release-set-stable.json"
    delivery.promote(
        argparse.Namespace(
            manifest=str(trusted_rc_path),
            from_channel="rc",
            channel="stable",
            version=release_version,
            output=str(stable_path),
        )
    )
    stable = delivery.load(stable_path)
    assert stable["channel"] == "stable"
    assert stable["version"] == release_version
    assert stable["trust_profile"] == "macos-trusted"

    bad = json.loads(manifest_path.read_text(encoding="utf-8"))
    bad["targets"]["windows-x64"]["stages"].pop()
    bad_path = tmp_path / "bad.json"
    delivery.write(bad_path, bad)
    with pytest.raises(ValueError, match="incomplete or out-of-order"):
        delivery.verify(argparse.Namespace(manifest=str(bad_path)))


def test_release_workflows_have_immutable_structured_topology():
    candidate = load_workflow(".github/workflows/candidate.yml")
    community = load_workflow(".github/workflows/community-release-candidate.yml")
    trusted = load_workflow(".github/workflows/macos-trusted-release-candidate.yml")
    promote = load_workflow(".github/workflows/promote.yml")
    legacy = load_workflow(".github/workflows/package-verification.yml")

    assert candidate["permissions"] == {"contents": "read"}
    assert set(candidate["jobs"]) == {"initialize", "build", "candidate-gate"}
    assert candidate["jobs"]["build"]["needs"] == "initialize"
    assert candidate["jobs"]["candidate-gate"]["needs"] == "build"
    assert {
        item["target"]
        for item in candidate["jobs"]["build"]["strategy"]["matrix"]["include"]
    } == {"windows-x64", "macos-arm64"}

    assert community["permissions"] == {"contents": "read", "actions": "read"}
    assert community["jobs"]["attest"]["needs"] == "qualify"
    assert community["jobs"]["attest"]["permissions"]["attestations"] == "write"
    assert community["jobs"]["publish-rc"]["needs"] == "attest"
    assert community["jobs"]["publish-rc"]["permissions"]["contents"] == "write"

    assert trusted["permissions"] == {"contents": "read", "actions": "read"}
    assert trusted["jobs"]["carry-windows"]["needs"] == "validate-candidate"
    assert trusted["jobs"]["sign-submit-macos"]["environment"] == "macos-signing"
    assert set(trusted["jobs"]["finalize-macos"]["needs"]) == {
        "validate-candidate",
        "sign-submit-macos",
    }
    assert set(trusted["jobs"]["attest"]["needs"]) == {
        "carry-windows",
        "finalize-macos",
    }
    assert trusted["jobs"]["publish-rc"]["needs"] == "attest"

    assert promote["permissions"] == {"contents": "read"}
    assert promote["jobs"]["promote"]["environment"] == "production-release"
    assert promote["jobs"]["promote"]["permissions"] == {"contents": "write"}
    assert set(legacy["jobs"]) == {"windows-package", "macos-packages"}
    assert legacy["permissions"] == {"contents": "read"}

    verify_rc = workflow_step(
        promote, "promote", "Verify RC release set and exact asset digests"
    )
    assert "(cd promotion && sha256sum --check SHA256SUMS)" in verify_rc["run"]
    assert 'git fetch origin "refs/tags/$RC_TAG:refs/tags/$RC_TAG"' in verify_rc["run"]

    publishers = (
        (
            community,
            "publish-rc",
            "Publish clearly labeled immutable unsigned RC",
            'test "$(git rev-list -n 1 "$TAG")" = "${{ inputs.source_sha }}"',
            'tag_args=(--target "${{ inputs.source_sha }}")',
        ),
        (
            trusted,
            "publish-rc",
            "Publish immutable macOS-trusted RC",
            'test "$(git rev-list -n 1 "$TAG")" = "${{ inputs.source_sha }}"',
            'tag_args=(--target "${{ inputs.source_sha }}")',
        ),
        (
            promote,
            "promote",
            "Publish stable release without rebuilding",
            'test "$(git rev-list -n 1 "$STABLE_TAG")" = "$source_sha"',
            'tag_args=(--target "$source_sha")',
        ),
    )
    for workflow, job_name, step_name, verified_target, targeted_tag in publishers:
        run = workflow_step(workflow, job_name, step_name)["run"]
        assert "gh release view" in run and "refusing overwrite" in run
        assert "git ls-remote --exit-code --tags origin" in run
        assert verified_target in run
        assert "tag_args=(--verify-tag)" in run
        assert targeted_tag in run
        assert '"${tag_args[@]}"' in run

    sign = workflow_step(
        trusted, "sign-submit-macos", "Sign exact candidate app and submit it to Apple"
    )
    preserved = workflow_step(
        trusted, "sign-submit-macos", "Preserve exact signed bytes and submission ID"
    )
    finalize = workflow_step(
        trusted,
        "finalize-macos",
        "Wait for Apple, then staple and verify preserved bytes",
    )
    final_launch = workflow_step(
        trusted, "finalize-macos", "Launch final signed and stapled macOS bytes"
    )
    assert "--mode sign-and-submit" in sign["run"]
    assert (
        '(cd submitted && shasum -a 256 "$ARTIFACT" > "$ARTIFACT.sha256")'
        in sign["run"]
    )
    assert preserved["uses"].startswith("actions/upload-artifact@")
    assert preserved["with"] == {
        "name": "submitted-${{ matrix.target }}",
        "path": "submitted",
        "if-no-files-found": "error",
        "retention-days": 30,
        "compression-level": 0,
    }
    assert '(cd submitted && shasum -a 256 -c "$ARTIFACT.sha256")' in finalize["run"]
    assert "--mode finalize" in finalize["run"]
    assert '--input-archive "submitted/$ARTIFACT"' in finalize["run"]
    assert 'xcrun stapler validate "qualified/$ARTIFACT"' in final_launch["run"]
    assert "codesign --verify --verbose=4" in final_launch["run"]
    signer = (ROOT / "scripts/sign-notarize-macos-artifact.sh").read_text(
        encoding="utf-8"
    )
    assert "xcrun notarytool submit" in signer
    assert "xcrun notarytool wait" in signer
    assert "xcrun stapler staple" in signer
    assert "xcrun stapler validate" in signer


def test_notarization_status_workflow_uses_protected_credentials():
    workflow = load_workflow(".github/workflows/notarization-status.yml")
    job = workflow["jobs"]["status"]
    assert job["environment"] == "macos-signing"
    assert workflow["permissions"] == {"contents": "read"}
    query = next(
        step
        for step in job["steps"]
        if step.get("name") == "Query notarization history and status"
    )
    assert set(query["env"]) >= {
        "APPLE_ID",
        "APPLE_APP_SPECIFIC_PASSWORD",
        "APPLE_TEAM_ID",
    }
    assert query["env"]["APPLE_ID"] == "${{ secrets.APPLE_ID }}"
    assert (
        query["env"]["APPLE_APP_SPECIFIC_PASSWORD"]
        == "${{ secrets.APPLE_APP_SPECIFIC_PASSWORD }}"
    )
    assert query["env"]["APPLE_TEAM_ID"] == "${{ secrets.APPLE_TEAM_ID }}"
    assert "xcrun notarytool history" in query["run"]
    assert 'xcrun notarytool info "$SUBMISSION_ID"' in query["run"]
    assert "--output-format json" in query["run"]
    assert "submission_id must be a UUID" in query["run"]
