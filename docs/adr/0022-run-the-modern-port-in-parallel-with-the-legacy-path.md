# Run the Modern Port in Parallel With the Legacy Path

The Python 3 and PyQt5 modernization path will run in parallel with the legacy Python 2 and PyQt4 CI/build path until cutover. The legacy path provides the reference environment and current release artifact, while the modern path provides a place to build the headless analysis harness, PyQt5 GUI slices, and Windows distributable without breaking legacy releases.

Source changes should still be made in small compatibility slices, but CI and build workflows should allow old and new paths to be compared side by side.
