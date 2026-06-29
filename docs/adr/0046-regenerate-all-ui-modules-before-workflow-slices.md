# Regenerate All UI Modules Before Workflow Slices

The Full Legacy App Port should regenerate all Python UI modules from the canonical Qt Designer `.ui` files with the PyQt5 compiler as an early enabling slice. Behavioral migration should still proceed by workflow slice, but leaving stale PyQt4 generated code in place would make every later slice rediscover mechanical compiler differences and obscure the real application compatibility work.
