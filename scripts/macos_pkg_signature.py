#!/usr/bin/env python3
"""Parse and retain complete ``pkgutil --check-signature`` evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

EXPECTED_TEAM_ID = "VZLD955F6P"


def parse_pkgutil_signature(stdout: str, stderr: str, status: int) -> dict[str, object]:
    status_line = re.search(r"^Status:\s*(.+)$", stdout, re.MULTILINE)
    # pkgutil emits a certificate chain, not codesign's Team Identifier field.
    certificate_lines = re.findall(r"^\s*\d+\.\s+(.+?)\s*$", stdout, re.MULTILINE)
    team = re.search(r"\(([A-Z0-9]{10})\)", "\n".join(certificate_lines))
    signer = next(
        (line for line in certificate_lines if "Developer ID Installer:" in line), ""
    )
    return {
        "schema_version": 1,
        "status": status,
        "status_line": status_line.group(1) if status_line else "",
        "team_id": team.group(1) if team else "",
        "signer": signer,
        "certificate": certificate_lines[0] if certificate_lines else "",
        "stdout": stdout,
        "stderr": stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdout", type=Path, required=True)
    parser.add_argument("--stderr", type=Path, required=True)
    parser.add_argument("--status", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = parse_pkgutil_signature(
        args.stdout.read_text(encoding="utf-8", errors="replace"),
        args.stderr.read_text(encoding="utf-8", errors="replace"),
        args.status,
    )
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
