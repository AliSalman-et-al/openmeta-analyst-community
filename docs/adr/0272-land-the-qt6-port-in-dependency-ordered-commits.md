# Land the Qt6 port in dependency-ordered commits

The Native Qt6 Port will land as a reviewable, bisectable sequence rather than one sweeping conversion commit. The order is: locked runtime and generation tooling; Versioned Project Format plus converted samples; fail-closed mechanical rewrites; handwritten API, typing, model, signal, and behavior fixes; packaging and native-platform evidence; then final deletion and strict-policy enforcement. Each commit keeps the branch runnable where practical and explicitly identifies any temporarily unavailable slice rather than hiding mixed concerns.
