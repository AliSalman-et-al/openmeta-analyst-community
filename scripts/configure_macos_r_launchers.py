#!/usr/bin/env python3
"""Make an extracted official macOS R Resources tree privately relocatable."""

from __future__ import annotations
import argparse
import os
from pathlib import Path

OFFICIAL = {
    'R_HOME_DIR="/Library/Frameworks/R.framework/Resources"': 'R_HOME_DIR="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"',
    'R_SHARE_DIR="/Library/Frameworks/R.framework/Resources/share"': 'R_SHARE_DIR="${R_HOME_DIR}/share"',
    'R_INCLUDE_DIR="/Library/Frameworks/R.framework/Resources/include"': 'R_INCLUDE_DIR="${R_HOME_DIR}/include"',
    'R_DOC_DIR="/Library/Frameworks/R.framework/Resources/doc"': 'R_DOC_DIR="${R_HOME_DIR}/doc"',
}
RELATIVE = """#!/bin/sh
set -eu
# RCMS_PRIVATE_RSCRIPT_V1
R_HOME="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
# Upstream src/unix/Rscript.c consults RHOME before its compiled-in rhome.
RHOME="$R_HOME"
export R_HOME
export RHOME
export R_SHARE_DIR="$R_HOME/share"
export R_INCLUDE_DIR="$R_HOME/include"
export R_DOC_DIR="$R_HOME/doc"
exec "$R_HOME/bin/Rscript.real" "$@"
"""
CONFIG_MARKERS = {
    "## config -- Simple shell script to get the values of basic R configure": 1,
    "    --cppflags)": 1,
    'echo "${includes}"': 2,
    "    --ldflags)": 1,
    'echo "${MAIN_LDFLAGS} ${LDFLAGS} ${LIBR} ${LIBS}"': 1,
}
UPSTREAM_X64_LDFLAGS = (
    "-Wl,-headerpad_max_install_names -L/opt/R/x86_64/lib "
    "-F/Library/Frameworks/R.framework/.. -framework R "
    "-L/opt/R/x86_64/lib -lbz2 -lz -licucore -ldl -lm -liconv"
)


def private_config(architecture: str) -> str:
    if architecture not in {"x86_64", "arm64"}:
        raise RuntimeError(f"unsupported R build architecture: {architecture}")
    exact_guard = (
        f"""expected='{UPSTREAM_X64_LDFLAGS}'
      if [ "$upstream" != "$expected" ]; then
        echo "Unexpected upstream R CMD config --ldflags output: $upstream" >&2
        exit 1
      fi"""
        if architecture == "x86_64"
        else """case "$upstream" in
        *"/opt/R/arm64/lib"*"-framework R"*) ;;
        *) echo "Unexpected upstream R CMD config --ldflags output: $upstream" >&2; exit 1 ;;
      esac"""
    )
    return f"""#!/bin/sh
set -eu
# RCMS_PRIVATE_R_CONFIG_V1
R_HOME="${{R_HOME:-$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)}}"
export R_HOME
export R_INCLUDE_DIR="$R_HOME/include"
real="$R_HOME/bin/config.real"
if [ "$#" -eq 1 ]; then
  case "$1" in
    --cppflags)
      upstream="$("$real" --cppflags)"
      expected="-I$R_HOME/include"
      if [ "$upstream" != "$expected" ]; then
        echo "Unexpected upstream R CMD config --cppflags output: $upstream" >&2
        exit 1
      fi
      printf '%s\\n' "$expected"
      exit 0
      ;;
    --ldflags)
      upstream="$("$real" --ldflags)"
      {exact_guard}
      printf '%s\\n' "-Wl,-headerpad_max_install_names -L$R_HOME/lib -lR -lbz2 -lz -licucore -ldl -lm -liconv"
      exit 0
      ;;
  esac
fi
exec "$real" "$@"
"""


PRIVATE_CONFIG = private_config("x86_64")


def _safe_file(path: Path) -> None:
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise RuntimeError(
            f"launcher path is symlinked or has a symlinked ancestor: {path}"
        )


def _require_executable(path: Path, label: str) -> None:
    _safe_file(path)
    if (
        path.is_symlink()
        or not path.is_file()
        or (os.name != "nt" and not (path.stat().st_mode & 0o111))
    ):
        raise RuntimeError(f"{label} is missing, unsafe, or non-executable")


def _validate_official_config(path: Path) -> None:
    _require_executable(path, "official R config helper")
    text = path.read_text(encoding="utf-8")
    unexpected = {
        marker: (text.count(marker), count)
        for marker, count in CONFIG_MARKERS.items()
        if text.count(marker) != count
    }
    if unexpected:
        raise RuntimeError(
            f"official R config helper lacks exact expected markers: {unexpected}"
        )


def configure(
    resources: Path, *, configure_build: bool = True, architecture: str = "x86_64"
) -> None:
    # R.framework/Resources is normally a Versions/Current symlink.  Resolve
    # that framework-level link, then reject links in the launcher payload.
    root = resources.resolve(strict=True)
    binary, rscript = root / "bin/R", root / "bin/Rscript"
    config = root / "bin/config"
    real_config = root / "bin/config.real"
    configured_wrapper = private_config(architecture)
    if configure_build:
        if real_config.exists() or real_config.is_symlink():
            _validate_official_config(real_config)
            _safe_file(config)
            if (
                not config.is_file()
                or config.read_text(encoding="utf-8") != configured_wrapper
            ):
                raise RuntimeError(
                    "private R config wrapper does not match its exact marker"
                )
        else:
            _validate_official_config(config)
    _require_executable(binary, "official R launcher bin/R")
    text = binary.read_text(encoding="utf-8")
    if all(value in text for value in OFFICIAL):
        for old, new in OFFICIAL.items():
            text = text.replace(old, new)
        binary.write_text(text, encoding="utf-8")
    elif all(value in text for value in OFFICIAL.values()):
        pass
    else:
        raise RuntimeError("official R launcher lacks exact expected framework markers")
    if "/Library/Frameworks/R.framework/Resources" in binary.read_text(
        encoding="utf-8"
    ):
        raise RuntimeError("relocated R launcher retains an absolute framework path")
    _safe_file(rscript) if rscript.exists() else None
    real_rscript = root / "bin/Rscript.real"
    if real_rscript.exists():
        _safe_file(real_rscript)
        if not real_rscript.is_file() or (
            os.name != "nt" and not (real_rscript.stat().st_mode & 0o111)
        ):
            raise RuntimeError("existing Rscript.real is not a regular executable")
    else:
        if not rscript.is_file():
            raise RuntimeError("official Rscript is missing")
        rscript.rename(real_rscript)
        if not real_rscript.is_file() or (
            os.name != "nt" and not (real_rscript.stat().st_mode & 0o111)
        ):
            raise RuntimeError("official Rscript is not a regular executable")
    real_rscript.chmod(0o755)
    if rscript.exists() or rscript.is_symlink():
        rscript.unlink()
    rscript.write_text(RELATIVE, encoding="utf-8")
    rscript.chmod(0o755)
    if configure_build and not real_config.exists():
        config.rename(real_config)
        real_config.chmod(0o755)
        config.write_text(configured_wrapper, encoding="utf-8")
        config.chmod(0o755)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resources", type=Path, required=True)
    parser.add_argument("--architecture", choices=("x86_64", "arm64"), default="x86_64")
    parser.add_argument(
        "--runtime-only",
        action="store_true",
        help="relocate runtime launchers without installing the x64 build-config adapter",
    )
    args = parser.parse_args()
    configure(
        args.resources,
        configure_build=not args.runtime_only,
        architecture=args.architecture,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
