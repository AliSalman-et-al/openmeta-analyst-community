# RCMetaR owns statistical eligibility

The small-study effects analysis has method-specific rules based on effect measure, study design, raw-data completeness, study count, precision, and heterogeneity. RCMetaR computes one eligibility report for these rules, while Python parses that report and enforces only user-interface structure. This avoids maintaining conflicting statistical policy in Python and R at the cost of requiring the dialog to obtain eligibility through the R boundary.
