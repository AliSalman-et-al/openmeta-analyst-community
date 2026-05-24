#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="${1:-openmeta-analyst-community}"
ARTIFACT_NAME="${2:-OpenMetaAnalyst-macos-x64}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="${REPO_ROOT}/src"
ARTIFACT_DIR="${REPO_ROOT}/artifacts"
DIST_ROOT="${SRC_DIR}/dist"
BUILD_ROOT="${SRC_DIR}/build"
APP_BUNDLE="${DIST_ROOT}/OpenMetaAnalyst.app"
APP_CONTENTS="${APP_BUNDLE}/Contents"
APP_MACOS="${APP_CONTENTS}/MacOS"
APP_RESOURCES="${APP_CONTENTS}/Resources"
APP_EXECUTABLE="${APP_MACOS}/OpenMetaAnalyst"
APP_BINARY="${APP_MACOS}/OpenMetaAnalyst.bin"
ZIP_PATH="${ARTIFACT_DIR}/${ARTIFACT_NAME}.zip"

ENV_PREFIX="$(conda env list | awk -v env="${ENV_NAME}" '$1 == env { print $NF; exit }')"
if [[ -z "${ENV_PREFIX}" ]]; then
  echo "Conda environment '${ENV_NAME}' was not found." >&2
  exit 1
fi

if ! conda run -n "${ENV_NAME}" python -c "import PyInstaller" >/dev/null 2>&1; then
  conda install -n "${ENV_NAME}" -y -c defaults pyinstaller=3.5
fi

if [[ ! -d "${ENV_PREFIX}/python.app/Contents/Resources/qt_menu.nib" ]]; then
  conda install -n "${ENV_NAME}" -y -c defaults -c free python.app=1.2
fi

rm -rf "${DIST_ROOT}" "${BUILD_ROOT}" "${ZIP_PATH}"
mkdir -p "${ARTIFACT_DIR}"

pushd "${SRC_DIR}" >/dev/null
conda run -n "${ENV_NAME}" pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name OpenMetaAnalyst \
  --icon images/meta.icns \
  --hidden-import sip \
  --distpath dist \
  --workpath build \
  win_prelaunch.py
popd >/dev/null

if [[ ! -d "${APP_BUNDLE}" ]]; then
  echo "Expected app bundle was not created: ${APP_BUNDLE}" >&2
  exit 1
fi

mkdir -p "${APP_RESOURCES}" "${APP_MACOS}"
cp -R "${ENV_PREFIX}/lib/R" "${APP_RESOURCES}/R"
cp -R "${REPO_ROOT}/sample_data" "${APP_MACOS}/sample_data"

mkdir -p "${APP_RESOURCES}/bin" "${APP_RESOURCES}/lib"
if [[ -d "${ENV_PREFIX}/bin" ]]; then
  find "${ENV_PREFIX}/bin" -maxdepth 1 -type f -perm -111 -exec cp {} "${APP_RESOURCES}/bin/" \;
fi
find "${ENV_PREFIX}/lib" -maxdepth 1 \( -name "*.dylib" -o -name "*.so" -o -name "*.so.*" \) -exec cp -P {} "${APP_RESOURCES}/lib/" \;

if [[ -d "${ENV_PREFIX}/plugins" ]]; then
  cp -R "${ENV_PREFIX}/plugins" "${APP_RESOURCES}/plugins"
fi

if [[ ! -x "${APP_EXECUTABLE}" ]]; then
  echo "Expected app executable was not created: ${APP_EXECUTABLE}" >&2
  exit 1
fi

mv "${APP_EXECUTABLE}" "${APP_BINARY}"
cat > "${APP_EXECUTABLE}" <<'LAUNCHER'
#!/usr/bin/env bash
set -euo pipefail

APP_MACOS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_CONTENTS="$(cd "${APP_MACOS}/.." && pwd)"
APP_RESOURCES="${APP_CONTENTS}/Resources"
R_HOME="${APP_RESOURCES}/R"

export R_HOME
export R_USER="${R_USER:-oma}"
export R_SHARE_DIR="${R_HOME}/share"
export R_INCLUDE_DIR="${R_HOME}/include"
export R_DOC_DIR="${R_HOME}/doc"
export R_ARCH="${R_ARCH:-}"

runtime_paths=(
  "${APP_RESOURCES}/lib"
  "${APP_RESOURCES}/bin"
  "${R_HOME}/lib"
  "${R_HOME}/bin"
)

existing_paths=()
for path in "${runtime_paths[@]}"; do
  if [[ -d "${path}" ]]; then
    existing_paths+=("${path}")
  fi
done

if [[ ${#existing_paths[@]} -gt 0 ]]; then
  joined_paths="$(IFS=:; echo "${existing_paths[*]}")"
  export PATH="${joined_paths}:${PATH:-}"
  export DYLD_LIBRARY_PATH="${joined_paths}:${DYLD_LIBRARY_PATH:-}"
  export DYLD_FALLBACK_LIBRARY_PATH="${joined_paths}:${DYLD_FALLBACK_LIBRARY_PATH:-}"
fi

if [[ -d "${APP_RESOURCES}/plugins" ]]; then
  export QT_PLUGIN_PATH="${APP_RESOURCES}/plugins:${QT_PLUGIN_PATH:-}"
fi

log_dir="${HOME}/Library/Logs/OpenMetaAnalyst"
mkdir -p "${log_dir}"
exec "${APP_MACOS}/OpenMetaAnalyst.bin" "$@" >>"${log_dir}/launcher.log" 2>&1
LAUNCHER
chmod +x "${APP_EXECUTABLE}"

if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "${APP_BUNDLE}"
fi

pushd "${DIST_ROOT}" >/dev/null
ditto -c -k --keepParent "OpenMetaAnalyst.app" "${ZIP_PATH}"
popd >/dev/null

echo "Created ${ZIP_PATH}"
