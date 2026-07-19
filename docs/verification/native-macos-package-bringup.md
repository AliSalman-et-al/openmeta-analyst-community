# Native macOS package bring-up

## First-green gate

The first milestone is intentionally smaller than final release qualification. For each native architecture, the package job must:

1. build the architecture-specific unsigned ZIP on its native GitHub-hosted runner;
2. extract that exact ZIP into a fresh directory;
3. launch `RCMetaStudio.app/Contents/MacOS/RCMetaStudio` without using a system R installation;
4. open the bundled `BCG.rcms` project;
5. run the real R-backed packaged workflow and verify its result text and SVG artifact; and
6. exit cleanly.

Intel x64 runs first in the shared matrix; ARM64 uses the same script and differs only through `config/macos-package-targets.json`. Both declare macOS 13 as the deployment floor.

## Evidence still required

Local contract tests prove target selection, workflow topology, manifest coverage, and fail-closed architecture checks. They do not prove a native `.app`. Record the successful run URL, job ID, source commit, artifact ID, ZIP SHA-256, runner image, and packaged-smoke evidence here after each native job succeeds.

| Target | Native result | Artifact identity | Packaged BCG smoke |
| --- | --- | --- | --- |
| macOS Intel x64 | Pending hosted run | Pending | Pending |
| macOS ARM64 | Pending hosted run | Pending | Pending |

Full issue acceptance—expanded sample coverage, accessibility, scaling, exact three-artifact qualification, and release promotion—follows only after both first-green rows pass.
