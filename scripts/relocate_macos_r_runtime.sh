#!/usr/bin/env bash
# Relocate one *private* copied R.framework.  The caller supplies the locked
# interpreter so every discovery and normalization step is reproducible.
set -euo pipefail

resources=""; expected_arch=""; python_exe=""; allowed_root=""; normalizer=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --resources) resources="$2"; shift 2 ;;
    --architecture) expected_arch="$2"; shift 2 ;;
    --python) python_exe="$2"; shift 2 ;;
    --allowed-root) allowed_root="$2"; shift 2 ;;
    --normalizer) normalizer="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$resources" ] && [ -n "$expected_arch" ] && [ -n "$python_exe" ] && [ -n "$allowed_root" ] && [ -n "$normalizer" ] || {
  echo "--resources, --architecture, --python, --allowed-root, and --normalizer are required" >&2; exit 2;
}
[ -x "$python_exe" ] || { echo "locked Python is not executable: $python_exe" >&2; exit 1; }
[ -f "$normalizer" ] || { echo "Mach-O normalizer is missing: $normalizer" >&2; exit 1; }
# Resolve once, fail closed on a resources tree outside the explicitly private
# root (including a symlink which escapes it), and find its framework root.
private_paths_file="$(mktemp "${TMPDIR:-/tmp}/rcms-r-private-paths.XXXXXX")"
if ! "$python_exe" - "$resources" "$allowed_root" > "$private_paths_file" <<'PY'
import os
from pathlib import Path
import sys

raw, allowed_raw = map(Path, sys.argv[1:])
if not raw.exists() or not allowed_raw.exists():
    raise SystemExit("private resources or allowed root does not exist")
resources = raw.resolve(strict=True)
allowed = allowed_raw.resolve(strict=True)
if str(resources) in ("/", "/Library") or str(resources).startswith(("/Library/", "/opt/")):
    raise SystemExit(f"unsafe private resources path: {resources}")
try:
    resources.relative_to(allowed)
except ValueError:
    raise SystemExit(f"private resources escapes allowed root: {resources} not under {allowed}")
if resources == allowed or resources.name != "Resources":
    raise SystemExit(f"private resources must be a nested Resources directory: {resources}")
framework = next((p for p in (resources, *resources.parents) if p.name == "R.framework"), None)
if framework is None or framework == allowed:
    raise SystemExit(f"private resources is not within a nested R.framework: {resources}")
for path in (resources, allowed, framework):
    sys.stdout.buffer.write(os.fsencode(path) + b"\0")
PY
then
  rm -f "$private_paths_file"
  exit 1
fi
exec 3< "$private_paths_file"
if ! IFS= read -r -d '' resources <&3 \
  || ! IFS= read -r -d '' allowed_root <&3 \
  || ! IFS= read -r -d '' framework_root <&3; then
  exec 3<&-
  rm -f "$private_paths_file"
  echo "private R path validation returned an incomplete record" >&2
  exit 1
fi
if IFS= read -r -d '' unexpected_private_path <&3; then
  exec 3<&-
  rm -f "$private_paths_file"
  echo "private R path validation returned an unexpected extra record" >&2
  exit 1
fi
exec 3<&-
rm -f "$private_paths_file"
if command -v cygpath >/dev/null 2>&1; then
  resources="$(cygpath -u "$resources")"
  allowed_root="$(cygpath -u "$allowed_root")"
  framework_root="$(cygpath -u "$framework_root")"
fi
[ -d "$resources/bin" ] || { echo "private R Resources is incomplete: $resources" >&2; exit 1; }

r_relative_path() {
  local dependency="$1"
  case "$dependency" in
    /Library/Frameworks/R.framework/Versions/*/Resources/*) printf '%s\n' "${dependency#*/Resources/}" ;;
    /Library/Frameworks/R.framework/Resources/*) printf '%s\n' "${dependency#/Library/Frameworks/R.framework/Resources/}" ;;
    /Library/Frameworks/R.framework/R|/Library/Frameworks/R.framework/Versions/*/R) printf '%s\n' "lib/libR.dylib" ;;
    /opt/R/*/lib/*.dylib)
      # CRAN records parts of its own toolchain under /opt/R.  A release may
      # use only an identical, already-authenticated framework member; it may
      # never satisfy this edge from the runner's /opt/R tree.
      case "${dependency##*/}" in libtcl*.dylib|libtk*.dylib) return 2 ;; esac
      printf 'lib/%s\n' "${dependency##*/}"
      ;;
    /Library/Frameworks/R.framework/*|/opt/R/*|/opt/X11/*) return 2 ;;
    *) return 1 ;;
  esac
}

relative_loader_target() {
  "$python_exe" - "$1" "$2" <<'PY'
import os, sys
print(os.path.relpath(sys.argv[2], sys.argv[1]))
PY
}

manifest="$(mktemp "${TMPDIR:-/tmp}/rcms-r-macho.XXXXXX")"
trap 'rm -f "$manifest"' EXIT
write_macho_manifest() {
  "$python_exe" - "$resources" > "$manifest" <<'PY'
import os, stat, sys
from pathlib import Path
magics = {b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"}
for directory, _, names in os.walk(sys.argv[1]):
    for name in names:
        path = Path(directory, name)
        if not stat.S_ISREG(path.lstat().st_mode) or path.suffix.lower() == ".class":
            continue
        with path.open("rb") as stream:
            if stream.read(4) in magics:
                sys.stdout.buffer.write(os.fsencode(path) + b"\0")
PY
}
normalize_manifest() {
  "$python_exe" "$normalizer" --manifest "$manifest" --architecture "$expected_arch"
}

write_macho_manifest
normalize_manifest
macho_count=0
while IFS= read -r -d '' binary; do
  macho_count=$((macho_count + 1))
  dylib_id="$(otool -D "$binary" 2>/dev/null | awk 'NR > 1 {print $1; exit}' || true)"
  if relative="$(r_relative_path "$dylib_id")"; then
    target="$resources/$relative"; [ -e "$target" ] || { echo "private R install-ID target is absent: $dylib_id" >&2; exit 1; }
    replacement="@loader_path/$(relative_loader_target "$(dirname "$binary")" "$target")"
    install_name_tool -id "$replacement" "$binary"
  else
    status=$?
    [ "$status" -eq 1 ] || { echo "private R retains unsupported install ID: $dylib_id ($binary)" >&2; exit 1; }
    case "$dylib_id" in
      ""|@loader_path/*) ;;
      *)
        [ "$dylib_id" = "${dylib_id##*/}" ] || {
          echo "private R install ID is not a safe leaf name: $dylib_id ($binary)" >&2
          exit 1
        }
        case "$dylib_id" in
          *.dylib|*.so) ;;
          *) echo "private R install ID has an unsupported leaf name: $dylib_id ($binary)" >&2; exit 1 ;;
        esac
        install_name_tool -id "@loader_path/$(basename "$binary")" "$binary"
        ;;
    esac
  fi
  while IFS= read -r dependency; do
    if relative="$(r_relative_path "$dependency")"; then
      target="$resources/$relative"; [ -e "$target" ] || { echo "private R dependency target is absent: $dependency" >&2; exit 1; }
      replacement="@loader_path/$(relative_loader_target "$(dirname "$binary")" "$target")"
      install_name_tool -change "$dependency" "$replacement" "$binary"
    else
      status=$?
      [ "$status" -eq 1 ] || { echo "private R retains unsupported external dependency: $dependency ($binary)" >&2; exit 1; }
      case "$dependency" in
        /usr/lib/*|/System/Library/*) ;;
        @loader_path/*)
          loader_target="$(dirname "$binary")/${dependency#@loader_path/}"
          if [ ! -e "$loader_target" ]; then
            target="$resources/lib/${dependency##*/}"
            [ -e "$target" ] || { echo "private R loader-relative dependency target is absent: $dependency ($binary)" >&2; exit 1; }
            replacement="@loader_path/$(relative_loader_target "$(dirname "$binary")" "$target")"
            install_name_tool -change "$dependency" "$replacement" "$binary"
          fi
          ;;
        *) echo "private R retains unresolved dependency: $dependency ($binary)" >&2; exit 1 ;;
      esac
    fi
  done < <(otool -L "$binary" | awk 'NR > 1 {print $1}')
  final_dylib_id="$(otool -D "$binary" 2>/dev/null | awk 'NR > 1 {print $1; exit}' || true)"
  case "$final_dylib_id" in
    ""|@loader_path/*) ;;
    *) echo "private R retains unresolved install ID: $final_dylib_id ($binary)" >&2; exit 1 ;;
  esac
  report="$(otool -D "$binary" 2>/dev/null || true; otool -L "$binary")"
  if printf '%s\n' "$report" | grep -E '/Library/Frameworks/R\.framework/|/opt/R/|/opt/X11/' >/dev/null; then
    echo "private R retains an external framework reference: $binary" >&2; exit 1
  fi
done < "$manifest"
echo "Relocated and verified $macho_count private R Mach-O files."
