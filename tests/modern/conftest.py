import os


# Modern tests run without a live R backend; use the pure-Python stub.
os.environ.setdefault("OMA_STUB_BACKEND", "1")
