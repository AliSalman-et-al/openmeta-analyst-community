# Target One Python 3 Minor Version for the First Port

The first modernization milestone targets Python 3.11 rather than treating "Python 3" as an open-ended compatibility range. Python 3.11 has a useful support window while being less likely than the newest Python release to expose packaging gaps in older desktop and R bridge dependencies.

Changing the exact minor version before Release Cutover requires a new modernization decision, because test, packaging, and compatibility results are tied to the pinned Python Runtime Target.
