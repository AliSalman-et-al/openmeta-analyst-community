# Preserve Module Layout During the First Port

The first Python 3 and Qt 5 port will preserve the existing module layout except where a local structural change is strictly necessary to make a compatibility slice run. Reorganizing files while changing Python runtime behavior, Qt APIs, generated UI code, and rpy2 integration would make regressions harder to isolate and review.

This is not an endorsement of the current architecture as the long-term shape. Module cleanup and clearer boundaries should be planned as a post-port refactor once analysis compatibility and the first GUI workflows are stable.
