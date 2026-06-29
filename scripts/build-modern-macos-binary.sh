#!/usr/bin/env bash
set -euo pipefail

artifact_name=""
architecture=""
python_exe=""
r_runtime_root="${OMA_R_HOME:-${R_HOME:-}}"
r_package_cache_root=""
skip_dependency_install=0
skip_smoke=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --artifact-name)
      artifact_name="$2"
      shift 2
      ;;
    --architecture)
      architecture="$2"
      shift 2
      ;;
    --python-exe)
      python_exe="$2"
      shift 2
      ;;
    --r-runtime-root)
      r_runtime_root="$2"
      shift 2
      ;;
    --r-package-cache-root)
      r_package_cache_root="$2"
      shift 2
      ;;
    --skip-dependency-install)
      skip_dependency_install=1
      shift
      ;;
    --skip-smoke)
      skip_smoke=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
src_dir="$repo_root/src"
artifact_dir="$repo_root/artifacts"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "Modern macOS packaging must run on macOS." >&2
  exit 1
fi

host_machine="$(uname -m)"
case "${architecture:-}" in
  x64)
    expected_machine="x86_64"
    default_artifact="OpenMetaAnalyst-modern-macos-x64"
    ;;
  arm64)
    expected_machine="arm64"
    default_artifact="OpenMetaAnalyst-modern-macos-arm64"
    ;;
  "")
    if [ "$host_machine" = "arm64" ]; then
      architecture="arm64"
      expected_machine="arm64"
      default_artifact="OpenMetaAnalyst-modern-macos-arm64"
    else
      architecture="x64"
      expected_machine="x86_64"
      default_artifact="OpenMetaAnalyst-modern-macos-x64"
    fi
    ;;
  *)
    echo "--architecture must be x64 or arm64." >&2
    exit 1
    ;;
esac

if [ "$host_machine" != "$expected_machine" ]; then
  echo "Requested $architecture build requires $expected_machine host, but this host is $host_machine." >&2
  exit 1
fi

artifact_name="${artifact_name:-$default_artifact}"
dist_root="$repo_root/build/modern-macos/$architecture/dist"
work_root="$repo_root/build/modern-macos/$architecture/work"
app_bundle="$dist_root/OpenMetaAnalyst.app"
app_root="$app_bundle/Contents/MacOS"
zip_path="$artifact_dir/$artifact_name.zip"
tmp_zip_path="$zip_path.tmp"
r_package_cache_root="${r_package_cache_root:-$artifact_dir/r-library-cache}"

if [ "$skip_dependency_install" -eq 0 ]; then
  (cd "$repo_root" && uv sync --locked)
  python_exe="$repo_root/.venv/bin/python"
fi

python_exe="${python_exe:-$repo_root/.venv/bin/python}"
if [ ! -x "$python_exe" ]; then
  echo "Python executable was not found or is not executable: $python_exe" >&2
  exit 1
fi

"$python_exe" - <<'PY'
import PyInstaller
import sys
if sys.version_info[:2] != (3, 11):
    raise SystemExit("Modern macOS packaging requires Python 3.11.")
if PyInstaller.__version__ != "6.21.0":
    raise SystemExit("Modern macOS packaging requires PyInstaller 6.21.0.")
PY

if [ -z "$r_runtime_root" ]; then
  r_runtime_root="$(R RHOME)"
fi
if [ -z "$r_runtime_root" ] || [ ! -d "$r_runtime_root/bin" ]; then
  echo "No source R runtime was found. Pass --r-runtime-root or set OMA_R_HOME/R_HOME." >&2
  exit 1
fi

rm -rf "$dist_root" "$work_root" "$zip_path" "$tmp_zip_path"
mkdir -p "$artifact_dir"

(
  cd "$src_dir"
  RPY2_CFFI_MODE=ABI "$python_exe" -m PyInstaller \
    --noconfirm \
    --clean \
    --windowed \
    --name OpenMetaAnalyst \
    --distpath "$dist_root" \
    --workpath "$work_root" \
    --paths forms \
    --hidden-import icons_rc \
    --hidden-import rpy2.robjects \
    --hidden-import rpy2.rinterface \
    launch.py
)

if [ ! -x "$app_root/OpenMetaAnalyst" ]; then
  echo "OpenMetaAnalyst executable was not created at $app_root/OpenMetaAnalyst." >&2
  exit 1
fi

cp -R "$repo_root/sample_data" "$app_root/sample_data"
cp -R "$repo_root/doc" "$app_root/doc"
rm -rf "$app_root/R"
cp -R "$r_runtime_root" "$app_root/R"

r_home="$app_root/R"
r_lib="$r_home/library"
rscript="$r_home/bin/Rscript"
r_binary="$r_home/bin/R"

if [ ! -x "$rscript" ] || [ ! -x "$r_binary" ]; then
  echo "Bundled R runtime is missing R or Rscript under $r_home/bin." >&2
  exit 1
fi

r_version_cache_key="$("$rscript" -e "cat(paste0('R-', getRversion()))")"
cache_library="$r_package_cache_root/$r_version_cache_key/library"

test_bundled_r_packages() {
  local library="$1"
  [ -d "$library" ] || return 1
  R_HOME="$r_home" R_LIBS="$library" R_LIBS_USER="$library" "$rscript" -e "lib <- normalizePath('$library', winslash='/'); .libPaths(c(lib, .libPaths())); pkgs <- c('HSROC','openmetar','metafor','lme4','igraph','mice','Hmisc'); ok <- vapply(pkgs, requireNamespace, logical(1), quietly=TRUE); if (!all(ok)) quit(status=1)" >/dev/null 2>&1
}

copy_r_library() {
  local source="$1"
  local destination="$2"
  rm -rf "$destination"
  mkdir -p "$(dirname "$destination")"
  cp -R "$source" "$destination"
}

install_local_r_packages() {
  local package_build_root="$work_root/r-package-build"
  rm -rf "$package_build_root"
  mkdir -p "$package_build_root"
  cp -R "$src_dir/R/HSROC" "$package_build_root/HSROC"
  cp -R "$src_dir/R/openmetar" "$package_build_root/openmetar"
  find "$package_build_root" \( -name '*.o' -o -name '*.so' -o -name '*.dll' \) -delete

  R_HOME="$r_home" R_LIBS="$r_lib" R_LIBS_USER="$r_lib" "$r_binary" CMD INSTALL --library="$r_lib" "$package_build_root/HSROC"
  R_HOME="$r_home" R_LIBS="$r_lib" R_LIBS_USER="$r_lib" "$r_binary" CMD INSTALL --library="$r_lib" "$package_build_root/openmetar"
}

if test_bundled_r_packages "$cache_library"; then
  echo "Using cached bundled R library from $cache_library"
  copy_r_library "$cache_library" "$r_lib"
else
  R_HOME="$r_home" R_LIBS="$r_lib" R_LIBS_USER="$r_lib" "$rscript" "$repo_root/scripts/install-modern-r-deps.R"
fi

install_local_r_packages
R_HOME="$r_home" R_LIBS="$r_lib" R_LIBS_USER="$r_lib" "$rscript" -e "pkgs <- c('HSROC','openmetar','metafor','lme4','igraph','mice','Hmisc'); ok <- vapply(pkgs, require, logical(1), character.only=TRUE); print(ok); if (!all(ok)) quit(status=1)"

if test_bundled_r_packages "$r_lib"; then
  echo "Caching bundled R library at $cache_library"
  copy_r_library "$r_lib" "$cache_library"
fi

cat > "$app_root/LaunchOpenMetaAnalyst.command" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export RPY2_CFFI_MODE=ABI
export OMA_R_HOME="$APP_DIR/R"
export OMA_R_LIBS="$APP_DIR/R/library"
exec "$APP_DIR/OpenMetaAnalyst" "$APP_DIR/sample_data/amino.oma"
SH
chmod +x "$app_root/LaunchOpenMetaAnalyst.command"

for required_path in \
  "$app_root/OpenMetaAnalyst" \
  "$app_root/sample_data/BCG.oma" \
  "$app_root/sample_data/amino.oma" \
  "$app_root/doc/openMA_help.html" \
  "$app_root/R/bin/Rscript" \
  "$app_root/R/library/openmetar/DESCRIPTION" \
  "$app_root/LaunchOpenMetaAnalyst.command"
do
  if [ ! -e "$required_path" ]; then
    echo "Packaged macOS app is missing $required_path." >&2
    exit 1
  fi
done

if [ "$skip_smoke" -eq 0 ]; then
  sample_path="$app_root/sample_data/amino.oma"
  OMA_REQUIRE_IN_PROCESS_RPY2=1 RPY2_CFFI_MODE=ABI OMA_R_HOME="$r_home" OMA_R_LIBS="$r_lib" "$app_root/OpenMetaAnalyst" --automation-smoke "$sample_path"
  OMA_STARTUP_PROJECT_SMOKE=1 OMA_REQUIRE_IN_PROCESS_RPY2=1 RPY2_CFFI_MODE=ABI OMA_R_HOME="$r_home" OMA_R_LIBS="$r_lib" "$app_root/OpenMetaAnalyst" "$sample_path"
fi

(
  cd "$dist_root"
  zip -qry "$tmp_zip_path" "OpenMetaAnalyst.app"
)
mv "$tmp_zip_path" "$zip_path"

python3 - "$zip_path" <<'PY'
import sys
import zipfile

zip_path = sys.argv[1]
required = [
    "OpenMetaAnalyst.app/Contents/MacOS/OpenMetaAnalyst",
    "OpenMetaAnalyst.app/Contents/MacOS/sample_data/BCG.oma",
    "OpenMetaAnalyst.app/Contents/MacOS/sample_data/amino.oma",
    "OpenMetaAnalyst.app/Contents/MacOS/doc/openMA_help.html",
    "OpenMetaAnalyst.app/Contents/MacOS/R/bin/Rscript",
    "OpenMetaAnalyst.app/Contents/MacOS/R/library/openmetar/DESCRIPTION",
    "OpenMetaAnalyst.app/Contents/MacOS/LaunchOpenMetaAnalyst.command",
]
with zipfile.ZipFile(zip_path) as archive:
    names = set(archive.namelist())
missing = [path for path in required if path not in names]
if missing:
    raise SystemExit("Created ZIP is missing: " + ", ".join(missing))
PY

echo "Created $zip_path"
