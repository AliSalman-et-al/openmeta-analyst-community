# Use Pytest for Modern Tests and Nose for the Legacy Baseline

The Python 3 and Qt 5 modernization path will use `pytest` for new tests, including the headless analysis harness and compatibility reporting. The existing `nose` runner remains part of the frozen Python 2 reference environment, where it helps preserve and execute legacy behavior, but it should not become the long-term test runner for the modern port.

This keeps the reference baseline stable while allowing new test infrastructure to use maintained Python 3 tooling.
