# Use Python Package Entry Points for RC MetaStudio

RC MetaStudio should be an installable Python package with explicit entry points instead of a loose script launched from `src/launch.py`. The primary GUI entry point should resolve through the package, such as `rc-metastudio = rc_metastudio.__main__:main`, with any automation or smoke-test startup paths exposed through similarly named package entry points when needed.

PyInstaller and local developer workflows should call the package entry point so packaging, tests, and source runs exercise the same startup path.

