#!/usr/bin/env python3
"""Bind an immutable R kit to relocated and signed files in a final app tree."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, cast


repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
verify = cast(
    Callable[..., dict[str, Any]],
    importlib.import_module("scripts.r_integration_kit").verify,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record(
    path: Path, root: Path, signing: dict[str, Any] | None = None
) -> dict[str, object]:
    resolved = path.resolve(strict=True)
    relative = Path(os.path.relpath(resolved, root.resolve())).as_posix()
    signing_identity = "unsigned"
    completed = (
        subprocess.run(
            ["codesign", "-dvv", str(resolved)],
            capture_output=True,
            text=True,
            check=False,
        )
        if sys.platform == "darwin"
        else None
    )
    if completed is not None:
        for line in (completed.stdout + completed.stderr).splitlines():
            if line.startswith("Identifier="):
                signing_identity = line.split("=", 1)[1]
                break
    result: dict[str, object] = {
        "path": relative,
        "sha256": sha256(resolved),
        "signing_identity": signing_identity,
    }
    if signing is not None:
        if not (
            signing.get("path") == relative
            and signing.get("sha256") == result["sha256"]
            and signing.get("status") == "Valid"
            and isinstance(signing.get("signer_subject"), str)
            and signing.get("signer_subject")
            and str(signing.get("signer_subject")).casefold() != "unsigned"
            and isinstance(signing.get("signer_thumbprint"), str)
            and signing.get("signer_thumbprint")
            and isinstance(signing.get("timestamp_subject"), str)
            and signing.get("timestamp_subject")
            and isinstance(signing.get("timestamp_thumbprint"), str)
            and signing.get("timestamp_thumbprint")
        ):
            raise ValueError(f"signed-file evidence is invalid for {relative}")
        result["signing_identity"] = signing["signer_subject"]
        result["signing"] = {
            key: signing[key]
            for key in (
                "status",
                "signer_subject",
                "signer_thumbprint",
                "timestamp_subject",
                "timestamp_thumbprint",
            )
        }
    return result


def kit_r_shared_library(kit: Path, target: str) -> Path:
    if target == "windows-x64":
        return (kit / "runtime" / "bin" / "x64" / "R.dll").resolve(strict=True)
    if target in {"macos-x64", "macos-arm64"}:
        return (kit / "runtime" / "R").resolve(strict=True)
    raise ValueError(f"unsupported R integration-kit target: {target}")


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    pre = commands.add_parser("record-pre-sign")
    pre.add_argument("--kit", type=Path, required=True)
    pre.add_argument("--target", required=True)
    pre.add_argument("--app-root", type=Path, required=True)
    pre.add_argument("--api-bridge", type=Path, required=True)
    pre.add_argument("--r-shared-library", type=Path, required=True)
    pre.add_argument("--api-bridge-transformation", type=Path)
    pre.add_argument("--output", type=Path, required=True)
    final = commands.add_parser("finalize")
    final.add_argument("--app-root", type=Path, required=True)
    final.add_argument("--api-bridge", type=Path, required=True)
    final.add_argument("--r-shared-library", type=Path, required=True)
    final.add_argument("--derivation", type=Path, required=True)
    final.add_argument("--signing-evidence", type=Path)
    final.add_argument("--require-signed", action="store_true")
    resolve = commands.add_parser("resolve-final")
    resolve.add_argument("--app-root", type=Path, required=True)
    resolve.add_argument("--derivation", type=Path, required=True)
    resolve.add_argument(
        "--name", choices=("api_bridge", "r_shared_library"), required=True
    )
    args = parser.parse_args()
    if args.command == "record-pre-sign":
        manifest = verify(args.kit, target=args.target)
        source_bridge = args.kit / str(manifest["api_bridge_path"])
        source_r_shared_library = kit_r_shared_library(args.kit, args.target)
        transformation = None
        if args.api_bridge_transformation is not None:
            transformation = json.loads(
                args.api_bridge_transformation.read_text(encoding="utf-8")
            )
            if not (
                transformation.get("schema_version") == 1
                and transformation.get("kind") == "mach-o-load-command-relocation"
                and transformation.get("source", {}).get("sha256")
                == sha256(source_bridge)
                and transformation.get("output", {}).get("sha256")
                == sha256(args.api_bridge)
                and transformation.get("changes")
            ):
                raise ValueError("API bridge relocation evidence is invalid")
        payload = {
            "schema_version": 1,
            "target": args.target,
            "kit_sha256": manifest["kit_sha256"],
            "source": {
                "api_bridge": {
                    "path": manifest["api_bridge_path"],
                    "sha256": sha256(source_bridge),
                },
                "r_shared_library": {
                    "path": source_r_shared_library.relative_to(
                        args.kit.resolve()
                    ).as_posix(),
                    "sha256": sha256(source_r_shared_library),
                },
            },
            "pre_sign": {
                "api_bridge": record(args.api_bridge, args.app_root),
                "r_shared_library": record(args.r_shared_library, args.app_root),
            },
            "transformations": {"api_bridge": transformation},
        }
        if transformation is None and (
            payload["source"]["api_bridge"]["sha256"]
            != payload["pre_sign"]["api_bridge"]["sha256"]
        ):
            raise ValueError("API bridge changed without authenticated transformation")
        if (
            payload["source"]["r_shared_library"]["sha256"]
            != payload["pre_sign"]["r_shared_library"]["sha256"]
        ):
            raise ValueError("R shared library changed before signing")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    elif args.command == "finalize":
        payload = json.loads(args.derivation.read_text(encoding="utf-8"))
        signing_members = None
        if args.signing_evidence is not None:
            evidence = json.loads(args.signing_evidence.read_text(encoding="utf-8"))
            signing_members = evidence.get("members")
            if not (
                evidence.get("schema_version") == 1
                and isinstance(signing_members, dict)
                and set(signing_members) == {"api_bridge", "r_shared_library"}
            ):
                raise ValueError("signed-file evidence schema is invalid")
        if args.require_signed and signing_members is None:
            raise ValueError(
                "signed finalization requires authenticated signer evidence"
            )
        payload["final"] = {
            "api_bridge": record(
                args.api_bridge,
                args.app_root,
                None if signing_members is None else signing_members["api_bridge"],
            ),
            "r_shared_library": record(
                args.r_shared_library,
                args.app_root,
                None
                if signing_members is None
                else signing_members["r_shared_library"],
            ),
        }
        if args.require_signed and any(
            member.get("signing_identity") == "unsigned"
            for member in payload["final"].values()
        ):
            raise ValueError("signed finalization retained an unsigned identity")
        args.derivation.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    else:
        payload = json.loads(args.derivation.read_text(encoding="utf-8"))
        relative = payload.get("final", {}).get(args.name, {}).get("path")
        if not isinstance(relative, str) or not relative:
            raise ValueError(f"derivation has no final {args.name} path")
        app_root = args.app_root.resolve(strict=True)
        app_bundle = app_root.parent.parent
        resolved = (app_root / relative).resolve(strict=True)
        if not resolved.is_relative_to(app_bundle):
            raise ValueError(f"final {args.name} path escapes the app bundle")
        print(resolved)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"R kit derivation error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
