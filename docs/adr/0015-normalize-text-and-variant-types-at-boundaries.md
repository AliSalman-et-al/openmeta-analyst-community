# Normalize Text and Variant Types at Boundaries

The Python 3 port will handle legacy `QString`, `QVariant`, `str`, and `unicode` differences through explicit normalization at compatibility boundaries such as project-file parsing, model data access, and R-bridge conversion. Scattered `str(...)` calls in GUI code are discouraged because they can hide subtle behavior changes in labels, covariate names, metric names, and analysis inputs.

Focused tests should cover text and type normalization where values cross from saved projects into models and from models into R calls.
