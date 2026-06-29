# Cut Over Only After Modern Release Criteria Are Met

The modern Python 3 and PyQt5 path should replace the legacy release path only after it passes golden analysis CI, completes required GUI compatibility slices, opens and round-trips representative `.oma` files, builds the Windows distributable, and includes minimal user-facing release documentation. Until those criteria are met, the legacy Python 2 and PyQt4 path remains the release path even if the modern application partially works.

This prevents retiring the reference and release baseline before the replacement is actually releasable.
