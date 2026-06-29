# Preserve GUI Workflows Unless an Exception Is Documented

The PyQt5 port should preserve existing wizard and dialog workflows by default. Workflow simplification is product design work and can accidentally remove behavior users rely on, so it is out of scope for the first modernization milestone unless a specific flow is technically blocked or clearly broken.

Any accepted workflow simplification or GUI behavior difference must be documented as a GUI compatibility exception with before and after behavior.
