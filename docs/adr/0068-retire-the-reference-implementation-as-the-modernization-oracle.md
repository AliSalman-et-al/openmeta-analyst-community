# Retire the Reference Implementation as the Modernization Oracle

After the modern application becomes the maintained product, the Python 2.7, PyQt4, and R 3.3.2 Reference Implementation should no longer serve as the active compatibility oracle. Future analysis verification should move to a Modern Behavior Baseline captured from the maintained modern app, current R Stack, and renamed `OpenMetaR` package.

This does not remove Legacy Project Data Compatibility: existing `.oma` project files and representative sample projects remain user data that the modern app must open without requiring the old runtime.
