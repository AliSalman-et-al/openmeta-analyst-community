# Use mada Reitsma summary outputs

RCMetaR will use `mada::SummaryPts()` for positive and negative likelihood ratios and diagnostic odds ratio, including the package summary's mean, median, and equal-tail interval. It will run the package default of one million draws under a fixed reported seed and restore the prior R random state, preserving package inference while making repeated RC MetaStudio analyses reproducible.

Prediction reconstructs the geometry used by `mada::plot.reitsma()` and describes a new study's underlying sensitivity and specificity, not its observed counts. RCMetaR will report the values returned by `mada::AUC()`, including its SROC AUC over false-positive rates 0.01 through 0.99 and normalized partial SROC AUC over the observed range, without correcting the package's integration or inventing confidence intervals.
