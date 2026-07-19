# Lock the Qt6 runtime baseline

The Native Qt6 Port will begin with PyQt6 6.11.0 and lock the exact resolved Qt6 and SIP wheel set in `uv.lock`. Implementation, verification, packaging, and the resulting release will use that Qt6 Runtime Baseline; later PyQt6 or Qt6 upgrades will be separate reviewed changes so dependency drift cannot alter behavior during port qualification.
