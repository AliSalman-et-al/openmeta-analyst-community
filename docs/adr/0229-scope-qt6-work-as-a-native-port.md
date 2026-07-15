# Scope Qt6 work as a native port

RC MetaStudio will replace its entire Qt5/PyQt5-facing implementation with native Qt6/PyQt6 APIs without a compatibility facade, dual-binding conditionals, or Qt5Compat. The port will preserve Analysis Behavior, `.rcms` behavior, user workflows, canonical `.ui` forms, and established layout contracts; clean-sheet GUI architecture and product redesign remain separate post-port work so migration regressions stay attributable.
