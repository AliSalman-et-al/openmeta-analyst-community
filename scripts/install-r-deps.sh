#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="${1:-openmeta-analyst-community}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_R="${REPO_ROOT}/src/R"
TMP_DIR="${SRC_R}/rtmp"
mkdir -p "${TMP_DIR}"

ENV_PREFIX="$(conda env list | awk -v env="${ENV_NAME}" '$1 == env { print $NF; exit }')"
if [[ -z "${ENV_PREFIX}" ]]; then
  echo "Conda environment '${ENV_NAME}' was not found." >&2
  exit 1
fi

conda install -n "${ENV_NAME}" -y -c defaults -c r -c free \
  gettext=0.19.8=1 libiconv=1.14=0 readline=6.2=2 ncurses=5.9=10 \
  r-lattice r-coda r-mass \
  r-igraph=1.0.1=r3.3.2_0 \
  r-lme4=1.1_12=r3.3.2_0 \
  r-quantreg=5.29=r3.3.2_0 \
  r-boot=1.3_18=r3.3.2_0 \
  r-survival=2.40_1=r3.3.2_0 \
  r-ape=4.0=r3.3.2_0 \
  r-hmisc=4.0_0=r3.3.2_0

R_EXE="${ENV_PREFIX}/bin/R"
RSCRIPT_EXE="${ENV_PREFIX}/bin/Rscript"

export TMP="${TMP_DIR}"
export TEMP="${TMP_DIR}"
export TMPDIR="${TMP_DIR}"
export MAKEFLAGS="${MAKEFLAGS:--j2}"

mkdir -p "${HOME}/.R"
cat > "${HOME}/.R/Makevars" <<'MAKEVARS'
CXXFLAGS += -std=gnu++98 -Wno-deprecated-declarations
MAKEVARS

ARCHIVED_DEPS="${TMP_DIR}/install_archived_deps.R"
cat > "${ARCHIVED_DEPS}" <<'RSCRIPT'
options(repos = c(CRAN = "https://cran.r-project.org"))

install.packages(
  "https://cran.r-project.org/src/contrib/Archive/mcmc/mcmc_0.9-5.tar.gz",
  repos = NULL,
  type = "source"
)

mcmcpack_url <- "https://cran.r-project.org/src/contrib/Archive/MCMCpack/MCMCpack_1.4-0.tar.gz"
mcmcpack_tar <- file.path(tempdir(), "MCMCpack_1.4-0.tar.gz")
mcmcpack_src <- file.path(tempdir(), "MCMCpack")
download.file(mcmcpack_url, mcmcpack_tar, mode = "wb")
untar(mcmcpack_tar, exdir = tempdir(), tar = "tar")
rng_header <- file.path(mcmcpack_src, "src", "rng.h")
rng_text <- readLines(rng_header, warn = FALSE)
rng_text <- gsub("alpha\\.template end_f\\(\\)", "alpha.end_f()", rng_text, fixed = FALSE)
writeLines(rng_text, rng_header)
install.packages(mcmcpack_src, repos = NULL, type = "source")

install.packages(
  "https://cran.r-project.org/src/contrib/Archive/metafor/metafor_1.9-9.tar.gz",
  repos = NULL,
  type = "source"
)

install.packages(
  "https://cran.r-project.org/src/contrib/Archive/mice/mice_2.30.tar.gz",
  repos = NULL,
  type = "source"
)
RSCRIPT

"${RSCRIPT_EXE}" "${ARCHIVED_DEPS}"

pushd "${SRC_R}" >/dev/null
"${R_EXE}" CMD build HSROC
"${R_EXE}" CMD build openmetar
"${R_EXE}" CMD INSTALL HSROC_2.0.5.tar.gz
"${R_EXE}" CMD INSTALL openmetar_1.0.tar.gz
popd >/dev/null

"${RSCRIPT_EXE}" -e "pkgs <- c('HSROC','openmetar','metafor','lme4','MCMCpack','igraph','mice','Hmisc'); ok <- sapply(pkgs, require, character.only=TRUE); print(ok); if (!all(ok)) quit(status=1)"
