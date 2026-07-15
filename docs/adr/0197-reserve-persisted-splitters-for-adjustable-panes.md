# Reserve Persisted Splitters for Adjustable Panes

RC MetaStudio will use user-adjustable, proportion-persisted splitters only between Adjustable Panes, such as Results navigation and content or independently useful Edit Dataset collections. Ordinary regions will use intrinsic sizing and layout stretch: the main data table and Network graph consume surplus space while navigation, status, and graph controls remain content-sized. This avoids replacing fixed geometry with unnecessary user-managed dividers.
