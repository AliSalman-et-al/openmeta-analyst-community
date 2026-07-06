# Preserve Openmetar Export Surface During Roxygen2 Conversion

The roxygen2 conversion for `openmetar` will preserve the package's currently visible function and class surface instead of pruning exports to a smaller public API. This includes convention-based analysis functions such as `*.parameters`, `*.pretty.names`, and `*.is.feasible`, along with helper functions that are currently visible through the package namespace.

The Python Analysis Adapter discovers and invokes `openmetar` dynamically through `lsf.str('package:openmetar')` and convention-based R calls, so shrinking the export surface during the same slice as dependency modernization would risk changing Analysis Behavior for reasons unrelated to CRAN package compatibility.
