# Declare Overflow Boundaries in Each Form

Potentially complex wizard pages and dynamic dialogs will declare a scrollable content body while keeping primary action or navigation controls reachable outside it. Tables, trees, graphics views, and editors retain their native scrolling, nested scroll areas are avoided unless the inner region is inherently scrollable data, and compact dialogs remain unscrolled unless their content can exceed the screen contract. Shared runtime code must not inject generic scroll wrappers around arbitrary forms.
