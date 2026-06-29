# Remove Python 2 Syntax Before GUI Workflow Slices

The Full Legacy App Port should include an early enabling slice that removes Python 2-only syntax from the application modules needed by the real launcher and `MetaForm` shell. Workflow slices should still own behavior-specific text, pickle, and Qt fixes, but they should not each rediscover basic parser and import failures caused by bare `print`, old exception syntax, `unicode`, `basestring`, `xrange`, or `iteritems`.

Conversion scripts may assist this work, but their output should be reviewed and applied through compatibility slices as described in ADR 0049.
