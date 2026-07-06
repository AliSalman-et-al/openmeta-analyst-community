# Use Explicit Automation Mode for Packaged Smoke Checks

Packaged RC MetaStudio smoke checks should launch the packaged application through an explicit automation or smoke mode and a committed `.rcms` sample project, such as an `amino.rcms` sample. Normal user launch should not silently open a sample project unless that is separately chosen as a product UX decision.

This keeps packaging verification deterministic without coupling normal startup behavior to test fixtures.

