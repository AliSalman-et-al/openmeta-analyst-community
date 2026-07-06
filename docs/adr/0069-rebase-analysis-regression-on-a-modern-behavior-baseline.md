# Rebase Analysis Regression on a Modern Behavior Baseline

When the Reference Implementation is retired as the active oracle, the existing Golden Analysis Test infrastructure should be migrated rather than deleted. The harness shape, manifests, artifact capture, plot evidence, and CI reporting remain valuable, but their authority should shift from Reference Implementation outputs to a Modern Behavior Baseline captured from the maintained modern app, current R Stack, and `OpenMetaR`.

During the transition, old golden outputs may be used as historical drift evidence, but they should not remain the pass/fail authority for the fully modernized application.
