#!/usr/bin/env python3
"""Create strict R integration-kit provenance from artifacts already downloaded by CI."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_record(record: dict, archive_root: Path) -> dict:
    archive = (archive_root / record["archive"]).resolve(strict=True)
    return {
        "name": record["name"],
        "version": record["version"],
        "package_type": record["package_type"],
        "url": record["url"],
        "sha256": sha256(archive),
        "license_files": record.get("license_files", []),
        "license": record["license"],
    }


def source_package_version(archive: Path, package_name: str) -> str:
    with tarfile.open(archive.resolve(strict=True)) as bundle:
        for member in bundle.getmembers():
            if not member.isfile() or not member.name.endswith("/DESCRIPTION"):
                continue
            stream = bundle.extractfile(member)
            if stream is None:
                continue
            fields = {}
            for line in stream.read().decode("utf-8", errors="strict").splitlines():
                if ":" in line and not line[:1].isspace():
                    key, value = line.split(":", 1)
                    fields[key] = value.strip()
            if fields.get("Package") == package_name and fields.get("Version"):
                return fields["Version"]
    raise ValueError(f"{archive} does not contain {package_name} DESCRIPTION metadata")


def archive_license_files(archive: Path) -> list[dict[str, str]]:
    records = []
    with tarfile.open(archive.resolve(strict=True)) as bundle:
        for member in bundle.getmembers():
            if not member.isfile() or Path(member.name).name.casefold() not in {
                "copyrights",
                "license",
                "licence",
                "copying",
            }:
                continue
            stream = bundle.extractfile(member)
            if stream is None:
                continue
            records.append(
                {
                    "path": member.name,
                    "sha256": hashlib.sha256(stream.read()).hexdigest(),
                }
            )
    if not records:
        raise ValueError(f"source archive carries no license payload: {archive}")
    return sorted(records, key=lambda item: item["path"])


def source_record(
    name: str, archive: Path, url: str, log: Path, toolchain: str, license_name: str
) -> dict:
    return {
        "name": name,
        "version": source_package_version(archive, name),
        "package_type": "source",
        "url": url,
        "sha256": sha256(archive.resolve(strict=True)),
        "toolchain": toolchain,
        "build_log_sha256": sha256(log.resolve(strict=True)),
        "license": license_name,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--official-r-artifact", type=Path, required=True)
    parser.add_argument("--official-r-url", required=True)
    parser.add_argument("--official-r-signature-identity", required=True)
    parser.add_argument("--official-r-signer-thumbprint")
    parser.add_argument("--official-r-signature-status")
    parser.add_argument("--official-r-timestamped", action="store_true")
    parser.add_argument(
        "--official-r-artifact-type", choices=("installer", "pkg"), required=True
    )
    parser.add_argument("--ppm-index", type=Path, required=True)
    parser.add_argument("--ppm-archive-root", type=Path, required=True)
    parser.add_argument("--hsroc-archive", type=Path, required=True)
    parser.add_argument("--hsroc-url", required=True)
    parser.add_argument("--hsroc-build-log", type=Path, required=True)
    parser.add_argument("--rcmetar-archive", type=Path, required=True)
    parser.add_argument("--rcmetar-url", required=True)
    parser.add_argument("--rcmetar-build-log", type=Path, required=True)
    parser.add_argument("--rpy2-sdist", type=Path, required=True)
    parser.add_argument("--rpy2-sdist-url", required=True)
    parser.add_argument("--rpy2-rinterface-sdist", type=Path, required=True)
    parser.add_argument("--rpy2-rinterface-sdist-url", required=True)
    parser.add_argument("--rpy2-robjects-sdist", type=Path, required=True)
    parser.add_argument("--rpy2-robjects-sdist-url", required=True)
    parser.add_argument("--rpy2-build-log", type=Path, required=True)
    parser.add_argument("--rpy2-api-bridge", type=Path, required=True)
    parser.add_argument("--toolchain", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    ppm_index = json.loads(args.ppm_index.read_text(encoding="utf-8"))
    if not isinstance(ppm_index, list) or not ppm_index:
        raise ValueError("PPM archive index must be a non-empty list")
    payload = {
        "schema_version": 1,
        "target": args.target,
        "official_r": {
            "url": args.official_r_url,
            "sha256": sha256(args.official_r_artifact.resolve(strict=True)),
            "signature_identity": args.official_r_signature_identity,
            "signer_thumbprint": args.official_r_signer_thumbprint,
            "signature_status": args.official_r_signature_status,
            "timestamped": args.official_r_timestamped,
            "artifact_type": args.official_r_artifact_type,
        },
        "ppm_packages": [
            package_record(record, args.ppm_archive_root) for record in ppm_index
        ],
        "source_packages": [
            source_record(
                "HSROC",
                args.hsroc_archive,
                args.hsroc_url,
                args.hsroc_build_log,
                args.toolchain,
                "GPL-2",
            ),
            source_record(
                "RCMetaR",
                args.rcmetar_archive,
                args.rcmetar_url,
                args.rcmetar_build_log,
                args.toolchain,
                "GPL-3.0-or-later",
            ),
        ],
        "rpy2": {
            "version": "3.6.7",
            "sdist_distribution": "rpy2-rinterface",
            "sdist_version": "3.6.6",
            "robjects_version": "3.6.5",
            "sdist_url": args.rpy2_rinterface_sdist_url,
            "sdist_sha256": sha256(args.rpy2_rinterface_sdist.resolve(strict=True)),
            "toolchain": args.toolchain,
            "build_log_sha256": sha256(args.rpy2_build_log.resolve(strict=True)),
            "bridge_sha256": sha256(args.rpy2_api_bridge.resolve(strict=True)),
            "license": "GPL-2.0-or-later",
            "source_archives": [
                {
                    "distribution": distribution,
                    "version": version,
                    "url": url,
                    "sha256": sha256(archive.resolve(strict=True)),
                    "license_files": archive_license_files(archive),
                }
                for distribution, version, archive, url in (
                    ("rpy2", "3.6.7", args.rpy2_sdist, args.rpy2_sdist_url),
                    (
                        "rpy2-rinterface",
                        "3.6.6",
                        args.rpy2_rinterface_sdist,
                        args.rpy2_rinterface_sdist_url,
                    ),
                    (
                        "rpy2-robjects",
                        "3.6.5",
                        args.rpy2_robjects_sdist,
                        args.rpy2_robjects_sdist_url,
                    ),
                )
            ],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"R kit provenance error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
