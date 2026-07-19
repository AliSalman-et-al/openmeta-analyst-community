# Preserve an immutable pre-Qt6 baseline

Before changing the GUI dependency set, the repository will mark the last known-good PyQt5 commit with an immutable annotated baseline tag and preserve its golden outputs, sample-project semantic snapshots, dependency lock, and representative interface evidence. The baseline exists only for diagnosis, comparison, and source-control rollback. It is not maintained, packaged, tested forward, or exposed as a second supported Qt runtime.
