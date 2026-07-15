# GitHub Actions native GUI geometry and cross-platform packaging

## Question

Can RC MetaStudio require an exact 1024 by 640 Qt client viewport, including a
native macOS frame in the screenshot, at `QT_SCALE_FACTOR=1.5` on GitHub's
hosted Intel runner? And should the Windows and macOS package lanes share more
of their build and verification definition?

## Findings

### A hosted macOS runner cannot guarantee the required viewport

Qt's high-DPI model exposes application geometry in device-independent pixels;
the device-pixel ratio maps that logical geometry to physical pixels. Qt also
documents `QT_SCALE_FACTOR` as a global scale-factor override intended for
testing. `QScreen::availableGeometry()` is the usable logical desktop area,
while `QWidget::frameGeometry()` includes the native window frame and
`QWidget::geometry()` excludes it. Therefore the relevant feasibility test is
not whether the 1024 by 640 *client* fits the screen rectangle: the complete
native `frameGeometry()` must fit `availableGeometry()`.

Sources:

- [Qt High DPI overview](https://doc.qt.io/qt-5/highdpi.html)
- [Qt High DPI environment variables](https://doc.qt.io/qt-5/highdpi.html#environment-variable-reference)
- [`QScreen::availableGeometry`](https://doc.qt.io/qt-5/qscreen.html#availableGeometry-prop)
- [`QWidget::frameGeometry`](https://doc.qt.io/qt-5/qwidget.html#frameGeometry-prop)
- [`QWidget::geometry`](https://doc.qt.io/qt-5/qwidget.html#geometry-prop)

The current run's measured 1280 by 647 logical available area makes the exact
requirement geometrically impossible: a 640-pixel-high client leaves only seven
logical pixels for all native vertical frame decoration. The native macOS title
bar is taller than that, so no placement algorithm can contain the complete
frame. This is a mathematical consequence of the measured Qt rectangles, not a
layout defect.

GitHub documents the CPU, memory, storage, architecture, and labels of hosted
runners, but it does **not** publish or contract a display resolution or usable
desktop geometry. Hosted jobs receive fresh GitHub-managed VMs, and runner
images are updated regularly. The `actions/runner-images` documentation for
macOS 15 likewise inventories installed software, not a guaranteed display
geometry. Consequently, a strict native GUI viewport larger than the measured
usable desktop cannot be made reliable by assuming a different hosted-runner
resolution.

Sources:

- [GitHub-hosted runners reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [GitHub Actions runner images](https://github.com/actions/runner-images)
- [macOS 15 image inventory](https://github.com/actions/runner-images/blob/main/images/macos/macos-15-Readme.md)
- [GitHub announcement for the `macos-15-intel` label](https://github.com/actions/runner-images/issues/13045)

This means the hosted runner can supply evidence only for scenarios that fit
its runtime-reported `availableGeometry()`. It cannot be the authority for a
guarantee that GitHub does not make.

### Better policy choices

The strongest choice is to retain the exact 1024 by 640 at 150% native-frame
gate and run that scenario on a controlled Intel Mac (self-hosted runner) whose
display mode is fixed and preflighted. A preflight should fail before launching
the app unless `availableGeometry()` can contain the expected frame, with a
small explicit decoration allowance.

If GitHub-hosted runners must remain the only infrastructure, the evidence
contract should distinguish product requirements from runner capability:

1. Keep cross-platform offscreen/parameterized Qt coverage for the 1024 by 640
   Full-Usability Floor at all required scale factors.
2. Keep native package evidence fail-closed for every scenario that the owning
   screen can contain.
3. Record a structured `unavailable` result only when runtime screen and frame
   measurements prove the requested native-frame capture is impossible. Do not
   describe that scenario as passed.
4. Require a controlled-machine/manual native capture before claiming complete
   1024 by 640 at 150% macOS release evidence.

Merely suppressing the two screenshots would weaken the release claim. A
capability-qualified result is honest, but it is not equivalent to executing
the scenario.

### Windows and macOS should share one package contract

GitHub officially supports a matrix strategy for running the same job across
operating systems, `matrix.include` for per-target values, the `runner.os`
context for narrow conditional steps, reusable workflows for sharing whole
jobs, and composite actions for sharing sequences of steps. Those mechanisms
support a common pipeline with platform adapters rather than independent test
definitions.

Sources:

- [Running job variations with a matrix](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations)
- [Workflow syntax for matrix `include` and `exclude`](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstrategymatrixinclude)
- [Using `runner.os` for operating-system conditionals](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-variables#detecting-the-operating-system)
- [Reusing workflow configurations](https://docs.github.com/en/actions/concepts/workflows-and-actions/reusing-workflow-configurations)
- [Calling reusable workflows from a matrix job](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows#using-a-matrix-strategy-with-a-reusable-workflow)

The present `package-verification.yml` already gives Windows and macOS Intel
nearly the same lifecycle: checkout, uv/Python setup, R setup and cache, package,
adaptive-layout evidence upload, ZIP upload, failure diagnostics, and cache
pruning. Most differences are syntax or target data. That duplication makes it
possible for the release gates to drift.

Recommended target shape:

```yaml
strategy:
  fail-fast: false
  matrix:
    include:
      - target: windows-x64
        runner: windows-latest
        package_command: .\\scripts\\package-windows.ps1 ...
        artifact: RCMetaStudio-windows-x64
      - target: macos-x64
        runner: macos-15-intel
        package_command: bash scripts/package-macos.sh --architecture x64 ...
        artifact: RCMetaStudio-macos-x64
runs-on: ${{ matrix.runner }}
```

The common job should own the invariant contract: pinned checkout and setup
actions, Python version, version resolution, R version, cache inputs, evidence
schema and validator, artifact retention, diagnostic behavior, and publication
eligibility. OS-specific scripts should own only native mechanics: path/shell
handling, PyInstaller bundle format, R runtime copying, signing/ad-hoc signing,
launching the native app, and archive format details.

For the most durable design, place orchestration and validation in a
platform-neutral repository script (or small Python CLI) with explicit Windows
and macOS adapters. The workflow matrix then invokes the same command and
receives the same result manifest. A matrix alone removes YAML duplication, but
it does not prevent behavioral drift if the two package scripts continue to
define different stages and tests internally.

## Recommendation

Unify Windows x64 and macOS Intel x64 behind one matrix package job and one
versioned package/evidence manifest contract. Preserve platform-specific build
adapters, because native packaging genuinely differs, but make both adapters
run the same named stages and validators and publish the same classes of
artifacts.

Do not claim the GitHub-hosted macOS 150% 1024 by 640 native-frame scenario
passed when it cannot fit. Either add a controlled Intel Mac runner for that
strict gate, or report it as capability-unavailable and obtain the missing
native evidence elsewhere before declaring the release gate complete.
