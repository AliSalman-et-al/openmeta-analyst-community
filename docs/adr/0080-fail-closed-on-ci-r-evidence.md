# Fail closed on CI R evidence

Default R Evidence may run in a Degraded Local R Evidence mode on developer machines, but CI-required R evidence must fail when R is unavailable or required direct R packages are missing or at the wrong version. This keeps local feedback usable while preventing the Modern CI Path from accepting manifest-only evidence as proof of R Stack readiness.
