# Use Windows CI as the Reference Environment

The official reference environment for capturing golden analysis outputs was the Windows CI conda build environment: Python 2.7, PyQt 4.11.4, R 3.3.2, rpy2 2.8.5, nose 1.3.7, the bundled `HSROC` and `openmetar` packages, and the archived/default R dependency versions installed by the retired legacy R dependency script. This avoided comparing the Python 3 and Qt 5 migration against inconsistent developer machines or undocumented legacy installations.

Windows is the active binary target in the current repository, so using that CI path as the reference gives the migration a reproducible compatibility source before broader platform support is revisited.

Reference capture tooling should support local developer runs for debugging and fixture development, but local captures are non-authoritative unless they include matching Reference Environment metadata and are reproduced by Windows CI. Windows CI capture remains the authoritative source for Golden Output Bundles and Comprehensive Golden Baseline artifacts.
