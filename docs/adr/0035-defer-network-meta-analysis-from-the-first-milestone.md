# Defer Network Meta-Analysis From the First Milestone

Network meta-analysis is out of scope for the first Python 3 and Qt 5 modernization milestone. The current README notes optional network dependencies such as `gemtc` are not part of the default desktop binary build, and including them would expand dependency and analysis risk before the core binary, continuous, and diagnostic paths are stable.

Network meta-analysis can be planned as a later compatibility slice after the first milestone is releasable.
