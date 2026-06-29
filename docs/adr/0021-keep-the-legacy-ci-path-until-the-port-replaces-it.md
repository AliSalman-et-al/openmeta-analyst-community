# Keep the Legacy CI Path Until the Port Replaces It

The existing Python 2 and PyQt4 Windows CI/build path will remain available during the first Python 3 and Qt 5 modernization milestone. It is the reference environment for golden analysis outputs and the current release path, so removing it before the modern port has stable golden tests and a Windows distributable would eliminate the baseline needed to verify compatibility.

The legacy path can be retired only after the new Python 3 and PyQt5 path becomes the accepted release path.
