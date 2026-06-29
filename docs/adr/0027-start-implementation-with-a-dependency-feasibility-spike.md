# Start Implementation With a Dependency Feasibility Spike

The first implementation issue for the Python 3 and Qt 5 milestone will be a dependency feasibility spike. It must test whether the proposed Python 3 runtime, PyQt5, rpy2 bridge, and pinned reference R stack can work together before deeper porting work begins.

The spike is allowed to challenge the Python 3.11 default candidate, the in-process rpy2 approach, or the pinned R-stack constraint if dependency compatibility proves those assumptions infeasible.
