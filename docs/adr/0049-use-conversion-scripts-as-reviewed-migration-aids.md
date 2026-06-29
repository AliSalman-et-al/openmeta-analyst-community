# Use Conversion Scripts as Reviewed Migration Aids

The Python 3.11 and PyQt5 port should use committed conversion and audit scripts for mechanical Python 2 to 3 and PyQt4 to PyQt5 changes, but script output should land only through reviewed compatibility slices.

The scripts may detect or mechanically rewrite obvious patterns such as Python 2 print and exception syntax, `xrange`, `iteritems`, `unicode`, `basestring`, PyQt4 imports, Qt4-to-Qt5 module moves, generated UI rebuilds, and old signal syntax candidates. They should be repeatable audit tools so migration work can be checked consistently across the codebase.

The project should not accept a single broad auto-conversion commit for the whole application. A broad conversion would mix behavior-neutral syntax changes with workflow behavior changes, making regressions hard to attribute and weakening the Comprehensive Golden Baseline gate. Each applied conversion batch should be tied to a compatibility slice with tests or GUI Verification Evidence.

`2to3` may be used as a short-lived mechanical assistant for Python syntax diffs, but it should not become long-lived project infrastructure because it is deprecated in Python 3.11. Qt migration scripts should be conservative: flag ambiguous API or signal changes for manual review instead of guessing behavior.
