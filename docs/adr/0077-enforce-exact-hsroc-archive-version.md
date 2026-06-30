# Enforce Exact HSROC Archive Version

Modern R Stack verification should fail unless `HSROC` is installed at exactly version `2.1.9` from the CRAN Archive. Although `HSROC` is a third-party package, it is archived and no longer receives normal current-CRAN updates, so the archive version is part of the reproducible dependency contract.

This preserves the reproducibility previously provided by the local `src/R/HSROC` source tree while allowing `OpenMetaR` to remain the only local R package.
