# Store Golden Outputs as Structured JSON Plus Artifacts

Golden analysis outputs should be captured as structured JSON plus external generated artifacts such as plots. The JSON should record the dataset, analysis method, parameters, parsed numeric outputs, normalized text sections where useful, artifact paths or checksums, tool versions, capture timestamp, commit SHA, capture mode, capture command, Reference Environment identity, and whether the capture is `authoritative` or `local-debug`.

Tool versions should include Python, operating system, R, rpy2, PyQt where relevant, and relevant R and Python package versions. This metadata is required for drift triage so reviewers can distinguish code changes from environment or toolchain differences.

Raw console text should not be the primary oracle because it is brittle, hard to compare meaningfully, and too sensitive to incidental formatting changes.
