# Keep Qt Compatibility Out of Modern GUI Modules

Modern GUI modules should import PyQt5 directly and use bound signals instead of importing compatibility helpers for old-style `connect`, `emit`, `QString`, or `QVariant` behavior. Project-file compatibility is handled by the legacy pickle loader, while the in-process `meta_py_r` fallback installer lives in `meta_py_r_backend.py` so R-backend setup does not pull Qt compatibility into normal application code.

This keeps the modern path honest about Qt5 behavior while preserving the narrow helpers needed for legacy project loading and automation tests.
