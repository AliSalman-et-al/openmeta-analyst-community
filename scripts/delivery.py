#!/usr/bin/env python3
"""Build-once delivery state machine for RC MetaStudio release sets."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS_PATH = ROOT / "delivery" / "targets.json"
POLICY_INPUTS = (
    "uv.lock",
    "pyproject.toml",
    "docs/verification/RCMetaR-r-dependencies.json",
    "r/RCMetaR/DESCRIPTION",
    "delivery/targets.json",
    "scripts/build-windows-package.ps1",
    "scripts/test-bounded-package-process.ps1",
    "scripts/inspect_windows_deployment.py",
    "packaging/pyinstaller/rc-metastudio.spec",
    "scripts/build-macos-package.sh",
    "scripts/package-macos.sh",
    "scripts/inspect_macos_deployment.py",
    "scripts/qt6_macos_feasibility.py",
    "scripts/run_bounded_process.py",
    "scripts/package_input_policy.py",
    "packaging/pyinstaller/rc-metastudio-macos.spec",
)


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def canonical_digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def release_identity_digest(manifest: dict) -> str:
    return canonical_digest(
        {
            "schema_version": manifest["schema_version"],
            "product": manifest["product"],
            "version": manifest["version"],
            "channel": manifest["channel"],
            "trust_profile": manifest["trust_profile"],
            "source": manifest["source"],
            "policy_inputs": manifest["policy_inputs"],
        }
    )


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def targets() -> dict:
    return load(TARGETS_PATH)["targets"]


def required_stages(manifest: dict, target: str) -> list[str]:
    registry = load(TARGETS_PATH)
    profile = registry["trust_profiles"][manifest["trust_profile"]]
    if manifest["trust_profile"] == "unsigned-community":
        return profile["stages"]
    os_name = registry["targets"][target]["os"]
    return profile[f"{os_name}_stages"]


def repository_version() -> str:
    import tomllib

    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def assert_commit(commit: str) -> None:
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        raise ValueError("source commit must be a full lowercase 40-character Git SHA")


def init_release(args: argparse.Namespace) -> None:
    assert_commit(args.commit)
    requested_base = args.version.split("-rc.", 1)[0]
    if requested_base != repository_version():
        raise ValueError(f"requested version {args.version} does not match repository version {repository_version()}")
    manifest = {
        "schema_version": 1,
        "product": "RC MetaStudio",
        "version": args.version,
        "channel": "candidate",
        "trust_profile": args.trust_profile,
        "source": {"repository": args.repository, "commit": args.commit},
        "policy_inputs": {name: digest(ROOT / name) for name in POLICY_INPUTS},
        "targets": {},
        "history": [{"event": "initialized", "at": now(), "commit": args.commit}],
    }
    write(Path(args.output), manifest)


def inventory(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    if not root.is_dir():
        raise ValueError(f"inventory root does not exist: {root}")
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        files.append({"path": path.relative_to(root).as_posix(), "size": path.stat().st_size, "sha256": digest(path)})
    write(Path(args.output), {"schema_version": 1, "root": root.name, "files": files})


def sbom(args: argparse.Namespace) -> None:
    source = load(Path(args.inventory))
    components = [
        {
            "type": "file",
            "name": item["path"],
            "hashes": [{"alg": "SHA-256", "content": item["sha256"]}],
        }
        for item in source["files"]
    ]
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, canonical_digest(source))),
        "version": 1,
        "metadata": {"timestamp": now(), "component": {"type": "application", "name": "RC MetaStudio", "version": args.version}},
        "components": components,
    }
    write(Path(args.output), document)


def stage_result(args: argparse.Namespace) -> None:
    assert_commit(args.commit)
    if args.target not in targets():
        raise ValueError(f"unsupported target: {args.target}")
    outputs = []
    for value in args.output_file:
        path = Path(value)
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"stage output is missing or empty: {path}")
        outputs.append({"name": path.name, "sha256": digest(path), "size": path.stat().st_size})
    record = {
        "schema_version": 1,
        "target": args.target,
        "stage": args.stage,
        "source_commit": args.commit,
        "input_digest": args.input_digest,
        "outputs": outputs,
        "completed_at": now(),
    }
    write(Path(args.result), record)


def attach(args: argparse.Namespace) -> None:
    path = Path(args.manifest)
    manifest = load(path)
    record = load(Path(args.result))
    if record["source_commit"] != manifest["source"]["commit"]:
        raise ValueError("stage result source commit does not match release set")
    target = manifest["targets"].setdefault(record["target"], {"stages": []})
    stages = target["stages"]
    required = required_stages(manifest, record["target"])
    expected = required[len(stages)] if len(stages) < len(required) else None
    if record["stage"] != expected:
        raise ValueError(f"invalid stage transition: expected {expected}, received {record['stage']}")
    expected_input = release_identity_digest(manifest) if not stages else canonical_digest(stages[-1])
    if record["input_digest"] != expected_input:
        raise ValueError("stage input digest does not bind the preceding immutable state")
    stages.append(record)
    manifest["history"].append({"event": record["stage"], "target": record["target"], "at": record["completed_at"]})
    write(path, manifest)


def verify(args: argparse.Namespace) -> None:
    manifest = load(Path(args.manifest))
    assert_commit(manifest["source"]["commit"])
    configured = targets()
    if set(manifest["targets"]) != set(configured):
        raise ValueError("release set does not contain exactly all supported targets")
    for name in configured:
        stages = manifest["targets"][name].get("stages", [])
        if [item["stage"] for item in stages] != required_stages(manifest, name):
            raise ValueError(f"{name} has incomplete or out-of-order stages")
        if any(item["source_commit"] != manifest["source"]["commit"] for item in stages):
            raise ValueError(f"{name} contains a foreign source commit")
    print(canonical_digest(manifest))


def promote(args: argparse.Namespace) -> None:
    source = load(Path(args.manifest))
    expected = {"candidate": "rc", "rc": "stable"}
    if expected.get(source["channel"]) != args.channel:
        raise ValueError(f"cannot promote {source['channel']} to {args.channel}")
    source_digest = canonical_digest(source)
    if args.version:
        if args.channel != "stable" or source["version"].split("-rc.", 1)[0] != args.version:
            raise ValueError("stable version must equal the RC base version")
        source["version"] = args.version
    source["channel"] = args.channel
    source["history"].append({"event": "promoted", "from": args.from_channel, "to": args.channel, "at": now(), "source_manifest_sha256": source_digest})
    write(Path(args.output), source)


def checksums(args: argparse.Namespace) -> None:
    paths = sorted(Path(value) for value in args.files)
    Path(args.output).write_text("".join(f"{digest(path)}  {path.name}\n" for path in paths), encoding="utf-8")


def print_digest(args: argparse.Namespace) -> None:
    value = load(Path(args.json))
    print(release_identity_digest(value) if args.release_identity else canonical_digest(value))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(required=True)
    init = commands.add_parser("init")
    init.add_argument("--version", required=True); init.add_argument("--commit", required=True)
    init.add_argument("--repository", required=True); init.add_argument("--trust-profile", choices=("unsigned-community", "trusted-signed"), default="unsigned-community"); init.add_argument("--output", required=True); init.set_defaults(func=init_release)
    inv = commands.add_parser("inventory"); inv.add_argument("--root", required=True); inv.add_argument("--output", required=True); inv.set_defaults(func=inventory)
    bom = commands.add_parser("sbom"); bom.add_argument("--inventory", required=True); bom.add_argument("--version", required=True); bom.add_argument("--output", required=True); bom.set_defaults(func=sbom)
    stage = commands.add_parser("stage-result"); stage.add_argument("--target", required=True); stage.add_argument("--stage", required=True)
    stage.add_argument("--commit", required=True); stage.add_argument("--input-digest", required=True); stage.add_argument("--output-file", action="append", required=True); stage.add_argument("--result", required=True); stage.set_defaults(func=stage_result)
    attach_parser = commands.add_parser("attach"); attach_parser.add_argument("--manifest", required=True); attach_parser.add_argument("--result", required=True); attach_parser.set_defaults(func=attach)
    verify_parser = commands.add_parser("verify"); verify_parser.add_argument("--manifest", required=True); verify_parser.set_defaults(func=verify)
    promote_parser = commands.add_parser("promote"); promote_parser.add_argument("--manifest", required=True); promote_parser.add_argument("--from-channel", required=True); promote_parser.add_argument("--channel", required=True); promote_parser.add_argument("--version"); promote_parser.add_argument("--output", required=True); promote_parser.set_defaults(func=promote)
    sums = commands.add_parser("checksums"); sums.add_argument("--files", action="append", required=True); sums.add_argument("--output", required=True); sums.set_defaults(func=checksums)
    digest_parser = commands.add_parser("digest"); digest_parser.add_argument("--json", required=True); digest_parser.add_argument("--release-identity", action="store_true"); digest_parser.set_defaults(func=print_digest)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"delivery: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
