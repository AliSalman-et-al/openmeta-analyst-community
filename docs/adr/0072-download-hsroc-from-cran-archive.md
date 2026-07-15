# Download HSROC from the CRAN Archive

The OpenMetaR R Stack Slice should install `HSROC` from the CRAN Archive at version `2.1.9` instead of building it from a checked-in local source tree. `OpenMetaR` should be the only custom local R package in the repository; archived third-party R packages should be downloaded by the modern R dependency installer and verified like the rest of the R Stack.

This replaces the earlier bundled-HSROC assumption and keeps the source tree focused on maintained project code while still using the latest available archived `HSROC` release.
