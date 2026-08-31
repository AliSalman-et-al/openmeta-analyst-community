#!/usr/bin/env python3
"""Index retained PPM binary archives with exact URL and package identity."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import zipfile


def description(archive: Path) -> str:
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            member = next(
                name
                for name in bundle.namelist()
                if name.count("/") == 1 and name.endswith("/DESCRIPTION")
            )
            return bundle.read(member).decode("utf-8", errors="strict")
    with tarfile.open(archive) as bundle:
        member = next(
            item
            for item in bundle.getmembers()
            if item.name.count("/") == 1 and item.name.endswith("/DESCRIPTION")
        )
        stream = bundle.extractfile(member)
        if stream is None:
            raise ValueError(f"cannot read DESCRIPTION from {archive}")
        return stream.read().decode("utf-8", errors="strict")


def fields(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    active: str | None = None
    for line in text.splitlines():
        if line[:1].isspace() and active:
            result[active] += " " + line.strip()
        elif ":" in line:
            active, value = line.split(":", 1)
            result[active] = value.strip()
        else:
            active = None
    return result


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def declares_license_file(value: str) -> bool:
    return "file license" in " ".join(
        value.casefold().split()
    ) or "file licence" in " ".join(value.casefold().split())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--contrib-url", required=True)
    parser.add_argument(
        "--package-type", choices=("win.binary", "mac.binary"), required=True
    )
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = []
    for archive in sorted(path for path in args.archives.iterdir() if path.is_file()):
        metadata = fields(description(archive))
        package = metadata["Package"]
        package_root = args.library / package
        licenses = [
            {
                "path": path.relative_to(package_root).as_posix(),
                "sha256": sha256(path),
            }
            for path in package_root.rglob("*")
            if path.is_file()
            and path.name.upper()
            in {"COPYRIGHTS", "COPYING", "COPYING.LIB", "LICENSE", "LICENCE"}
        ]
        license_name = metadata.get("License", "unknown")
        if declares_license_file(license_name) and not any(
            Path(record["path"]).name.upper() in {"LICENSE", "LICENCE"}
            for record in licenses
        ):
            raise ValueError(
                f"{package} declares file LICENSE but installs no license file"
            )
        records.append(
            {
                "name": package,
                "version": metadata["Version"],
                "package_type": args.package_type,
                "url": args.contrib_url.rstrip("/") + "/" + archive.name,
                "archive": archive.name,
                "license_files": sorted(licenses),
                "license": license_name,
            }
        )
    if not records:
        raise ValueError("no retained PPM binary archives were found")
    args.output.write_text(
        json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
