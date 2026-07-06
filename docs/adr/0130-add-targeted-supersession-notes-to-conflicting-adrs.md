# Add Targeted Supersession Notes to Conflicting ADRs

Older ADRs that directly conflict with the RC MetaStudio migration should receive short supersession notes without rewriting their historical decision text. High-risk conflicts include ADRs preserving `.oma` compatibility, targeting `OpenMetaR` or `openmetar.*`, using `modern` lane or artifact names as maintained labels, and documenting OpenMetaAnalyst release packaging names.

This keeps the ADR record auditable while making the current authority clear to future implementation agents.

