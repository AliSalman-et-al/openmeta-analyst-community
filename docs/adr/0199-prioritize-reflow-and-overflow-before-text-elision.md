# Prioritize Reflow and Overflow Before Text Elision

RC MetaStudio will handle text overflow by wrapping explanatory prose, allowing content-sized controls to grow within the screen contract, and scrolling collections, tables, and long content regions. Elision is reserved for secondary single-line chrome with the full value available by tooltip; editable values, validation messages, button labels, instructions, and other Required Content must never be truncated. This replaces blanket label-width mutation and scattered fixed-width caps with intent-specific Declarative Layout Contracts.
