param(
    [string]$EnvName = "openmeta-analyst-community"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$srcR = Join-Path $repoRoot "src\R"
$tmpDir = Join-Path $srcR "rtmp"
New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null

$envList = conda env list --json | ConvertFrom-Json
$envPrefix = $envList.envs | Where-Object { (Split-Path $_ -Leaf) -eq $EnvName } | Select-Object -First 1
if (-not $envPrefix) {
    throw "Conda environment '$EnvName' was not found."
}

conda install -n $EnvName -y -c defaults -c r -c free `
    rtools `
    r-lattice r-coda r-mass `
    r-igraph=1.0.1=r3.3.2_0 `
    r-lme4=1.1_12=r3.3.2_0 `
    r-quantreg=5.29=r3.3.2_0 `
    r-boot=1.3_18=r3.3.2_0 `
    r-survival=2.40_1=r3.3.2_0 `
    r-ape=4.0=r3.3.2_0 `
    r-hmisc=4.0_0=r3.3.2_0

$rExe = Join-Path $envPrefix "R\bin\R.exe"
$rscriptExe = Join-Path $envPrefix "R\bin\Rscript.exe"
$rtoolsBin = Join-Path $envPrefix "Rtools\bin"
$rtoolsMingw = Join-Path $envPrefix "Rtools\mingw_64\bin"
$env:Path = @(
    $rtoolsBin
    $rtoolsMingw
    (Join-Path $envPrefix "R\bin\x64")
    (Join-Path $envPrefix "R\bin")
    (Join-Path $envPrefix "Library\bin")
    (Join-Path $envPrefix "Library\mingw-w64\bin")
    (Join-Path $envPrefix "Library\usr\bin")
    $env:Path
) -join ";"
$env:BINPREF = ($rtoolsMingw -replace "\\", "/") + "/"
$env:TMP = $tmpDir
$env:TEMP = $tmpDir
$env:TMPDIR = $tmpDir

$archivedDeps = Join-Path $tmpDir "install_archived_deps.R"
@'
options(repos = c(CRAN = "https://cran.r-project.org"))

install.packages(
  "https://cran.r-project.org/src/contrib/Archive/mcmc/mcmc_0.9-5.tar.gz",
  repos = NULL,
  type = "source"
)

install.packages(
  "https://cran.r-project.org/src/contrib/Archive/MCMCpack/MCMCpack_1.3-8.tar.gz",
  repos = NULL,
  type = "source"
)

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
'@ | Set-Content -Path $archivedDeps -Encoding ASCII

& $rscriptExe $archivedDeps
if ($LASTEXITCODE -ne 0) { throw "Archived R dependency install failed." }

Push-Location $srcR
try {
    & $rExe CMD build HSROC
    if ($LASTEXITCODE -ne 0) { throw "R CMD build HSROC failed." }
    & $rExe CMD build openmetar
    if ($LASTEXITCODE -ne 0) { throw "R CMD build openmetar failed." }
    & $rExe CMD INSTALL HSROC_2.0.5.tar.gz
    if ($LASTEXITCODE -ne 0) { throw "R CMD INSTALL HSROC failed." }
    & $rExe CMD INSTALL openmetar_1.0.tar.gz
    if ($LASTEXITCODE -ne 0) { throw "R CMD INSTALL openmetar failed." }
}
finally {
    Pop-Location
}

& $rscriptExe -e "pkgs <- c('HSROC','openmetar','metafor','lme4','MCMCpack','igraph','mice','Hmisc'); ok <- sapply(pkgs, require, character.only=TRUE); print(ok); if (!all(ok)) quit(status=1)"
if ($LASTEXITCODE -ne 0) { throw "R package verification failed." }
