# Test Relayout Performance with Deterministic Work Bounds

Interactive layout performance will be gated by deterministic work bounds: bursts schedule at most one expensive reflow per event-loop turn, only the affected visible window or viewport is traversed, application-wide widget-tree scans are forbidden during resize, and resize handlers perform no R calls, disk I/O, or synchronous artifact regeneration. Timing benchmarks remain diagnostic and may fail only against broad regression envelopes rather than brittle frame-time thresholds.
