# Use Local Coalesced Runtime Relayout

Dynamic content will notify its owning form, which will invalidate only the affected layout or viewport and coalesce expensive reflow or artifact fitting to at most once per event-loop turn. Sizing code must not call `processEvents()`, repeatedly force synchronous layout activation, enter resize/refit feedback loops, or install generic application-wide filters to repair arbitrary descendants; the existing coalesced Results viewport scheduler is the model for expensive local relayout.
