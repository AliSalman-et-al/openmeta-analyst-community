# Reset only persisted Qt5 GUI state

The first Qt6 launch will invalidate persisted Qt5-owned window geometry, window state, splitter-state blobs, and screen placement through an explicit GUI-state schema version. Domain preferences, analysis settings, recent-project information, and other non-geometry user state will be preserved. This prevents opaque Qt5 geometry and pre-Qt6 scaling assumptions from creating unreachable or malformed windows without imposing an unrelated settings reset.
