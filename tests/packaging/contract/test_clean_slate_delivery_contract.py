import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from jsonschema import validate


ROOT = Path(__file__).resolve().parents[3]


def load_delivery():
    path = ROOT / "scripts" / "delivery.py"
    spec = importlib.util.spec_from_file_location("delivery_contract_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_clean_slate_delivery_state_machine_and_workflow_policy(tmp_path):
    delivery = load_delivery()
    manifest_path = tmp_path / "release-set.json"
    commit = "a" * 40
    delivery.init_release(
        argparse.Namespace(
            version="0.2.0-rc.1",
            commit=commit,
            repository="AliSalman-et-al/rc-metastudio",
            trust_profile="unsigned-community",
            target=["windows-x64"],
            output=str(manifest_path),
        )
    )
    manifest = delivery.load(manifest_path)
    schema = json.loads(
        (ROOT / "delivery" / "release-set.schema.json").read_text(encoding="utf-8")
    )
    validate(instance=manifest, schema=schema)
    assert manifest["channel"] == "candidate"
    assert set(manifest["policy_inputs"]) == set(delivery.POLICY_INPUTS)
    assert "scripts/test-bounded-package-process.ps1" in delivery.POLICY_INPUTS
    assert "scripts/qt6_macos_feasibility.py" in delivery.POLICY_INPUTS
    assert "scripts/normalize_macos_macho.py" in delivery.POLICY_INPUTS
    assert "scripts/sign_macos_app.py" in delivery.POLICY_INPUTS
    assert "config/macos-package-targets.json" in delivery.POLICY_INPUTS
    assert ".github/workflows/community-release-candidate.yml" in delivery.POLICY_INPUTS

    assert manifest["release_targets"] == ["windows-x64"]
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
    stable_path = tmp_path / "release-set-stable.json"
    delivery.promote(
        argparse.Namespace(
            manifest=str(rc_path),
            from_channel="rc",
            channel="stable",
            version="0.2.0",
            output=str(stable_path),
        )
    )
    stable = delivery.load(stable_path)
    assert stable["channel"] == "stable"
    assert stable["version"] == "0.2.0"

    bad = json.loads(manifest_path.read_text(encoding="utf-8"))
    bad["targets"]["windows-x64"]["stages"].pop()
    bad_path = tmp_path / "bad.json"
    delivery.write(bad_path, bad)
    with pytest.raises(ValueError, match="incomplete or out-of-order"):
        delivery.verify(argparse.Namespace(manifest=str(bad_path)))

    candidate = (ROOT / ".github/workflows/candidate.yml").read_text(encoding="utf-8")
    community = (ROOT / ".github/workflows/community-release-candidate.yml").read_text(
        encoding="utf-8"
    )
    promote = (ROOT / ".github/workflows/promote.yml").read_text(encoding="utf-8")
    legacy = (ROOT / ".github/workflows/package-verification.yml").read_text(
        encoding="utf-8"
    )
    assert "contents: write" not in candidate
    assert "run: .\\scripts\\package-windows.ps1\n" in candidate
    assert "-ArtifactName" not in candidate
    assert "Expected exactly one versioned Windows package" in candidate
    assert "Move-Item -LiteralPath $builtArchives[0].FullName" in candidate
    assert not (ROOT / ".github/workflows/release-candidate.yml").exists()
    assert "attestations: write" in community
    assert "--automation-native-smoke" in community
    assert community.index("astral-sh/setup-uv@") < community.index(
        "uv python install 3.11.9"
    )
    assert "--clobber" not in promote + legacy
    assert "push:\n    tags:" not in legacy
    assert (
        "refusing overwrite" in community.lower() and "refusing overwrite" in promote.lower()
    )
    assert "sha256sum --check SHA256SUMS" in promote
    verification_step = promote[
        promote.index("Verify RC release set") : promote.index("Publish stable release")
    ]
    assert "GH_TOKEN: ${{ github.token }}" in verification_step
    assert 'git fetch origin "refs/tags/$RC_TAG:refs/tags/$RC_TAG"' in verification_step
    for publisher in (community, promote):
        assert "git ls-remote --exit-code --tags origin" in publisher
        assert "tag_args=(--verify-tag)" in publisher
        assert '"${tag_args[@]}"' in publisher
    assert 'tag_args=(--target "${{ inputs.source_sha }}")' in community
    assert 'tag_args=(--target "$source_sha")' in promote
    assert "git push origin" not in community + promote
    assert "UNSIGNED COMMUNITY BUILD" not in community + promote
    assert "SmartScreen and Gatekeeper warnings" not in community + promote
    assert "**Signing status:** Unsigned community builds." in community
    assert "**Signing status:** Unsigned community builds." in promote
