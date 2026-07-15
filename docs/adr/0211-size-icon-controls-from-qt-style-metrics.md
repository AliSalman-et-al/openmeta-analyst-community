# Size Icon Controls from Qt Style Metrics

Icon-bearing controls will use `QIcon` and high-DPI-capable resources, with icon and interactive dimensions derived from the active Qt style rather than raw pixmap dimensions or historical form geometry. Icon-only controls may remain square as a Semantic Size Invariant, text-plus-icon controls must honor their complete size hint, and image dimensions must not dictate surrounding layout geometry.
