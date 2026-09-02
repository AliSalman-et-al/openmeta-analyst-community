# Delegate statistical decisions to authority packages

RC MetaStudio treats the selected field-maintained R package as the statistical authority for each supported method. The application validates inputs, invokes the package through a structured boundary, and improves explanation and presentation, but preserves the package's estimators, inference, defaults, and numerical results even when RCMetaR could implement an alternative calculation.

RCMetaR may perform exact representation changes such as converting false-positive rate to specificity and may reconstruct package-defined plot geometry when the package does not return it. A new estimator, inferential method, or correction to package output requires an explicit documented exception rather than being introduced as presentation code.
