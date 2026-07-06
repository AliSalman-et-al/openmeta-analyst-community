# Organize Tests by Runtime and Evidence Type

RC MetaStudio tests should move away from `tests/modern` and be organized by runtime and evidence type. Python tests should group unit/model, GUI, and analysis behavior coverage; R tests should cover RCMetaR package behavior; integration tests should cover the Python/R bridge and workflow behavior; packaging tests should cover distributable contracts and smoke checks.

Pytest markers may continue to express execution cost and evidence type, but maintained test paths, node IDs, scripts, and documentation should not use `modern` as an organizing label.

