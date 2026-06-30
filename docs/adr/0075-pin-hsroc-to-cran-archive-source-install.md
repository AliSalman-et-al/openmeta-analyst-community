# Pin HSROC to CRAN Archive Source Install

The modern R dependency installer should install `HSROC` from the CRAN Archive source tarball `HSROC_2.1.9.tar.gz` and verify that exact installed version. `HSROC` is no longer available from the main CRAN repository, so treating it as a normal current-CRAN package is not possible, but it should still be downloaded during dependency setup instead of kept as a local source tree.

This makes `OpenMetaR` the only local R package while preserving the latest available archived `HSROC` behavior. Modern artifact environments must therefore support installing the archived `HSROC` source package and its compiled code.
