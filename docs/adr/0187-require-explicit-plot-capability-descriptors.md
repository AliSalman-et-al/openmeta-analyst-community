# Require explicit plot capability descriptors

Every Plot Artifact returned across the RCMetaR-to-Python Analysis Adapter boundary must carry a valid Plot Capability Descriptor. The application fails the analysis contract when descriptor metadata is missing or invalid instead of inferring behavior from display titles; this makes editability, styleability, composition, and regeneration explicit and prevents title-based fallbacks from preserving the ambiguity this change is intended to remove.
