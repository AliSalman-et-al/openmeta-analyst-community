# Gate Adaptive Layouts with Layered Application-Wide Evidence

The adaptive-layout rewrite is accepted with a static audit of every canonical
UI form and deterministic GUI coverage across the 800 by 600 constrained case,
the 1024 by 640 Full-Usability Floor, larger logical areas, representative long
content, and multiple scale factors, plus behavioral coverage for focus,
overflow, stable runtime geometry, restoration, clamping, and splitters.

Windows x64 and macOS Intel packages must pass a narrow native hosted smoke:
the expected Qt platform plugin loads, the primary window becomes exposed, the
sample project and bundled R bridge initialize, and the process exits cleanly.
Hosted jobs must not gate construction on exact screen geometry, native chrome,
DPI/DPR, fonts, screenshots, or visual review because GitHub does not contract
those display properties.

Exact native screenshot evidence at 100 and 150 percent remains an explicit
controlled-host qualification tool keyed to the final package digest. Human
review is required for layout-system, Qt, OS, font, or icon changes when
controlled Windows and Intel Mac hosts are available. An unavailable controlled
host is recorded as `not-run`, never converted into a hosted-runner pass.
Pixel-diff testing remains out of scope.
