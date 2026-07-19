# Require strict typing for Qt modules

Completion of the Native Qt6 Port will require strict static type checking across every handwritten Qt-bearing Python module. Modules may enter the strict set incrementally during the hard cutover, but no permanent untyped Qt-facing area will remain; build-generated form modules are excluded, and any suppression must be narrow, documented, and tied to a demonstrated PyQt6 stub defect rather than application uncertainty.
