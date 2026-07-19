# Type signal and slot boundaries

RC MetaStudio custom signals will use the narrowest concrete PyQt6 signature that represents their payload, using `object` only for genuinely polymorphic values. `@pyqtSlot` will be required for cross-thread, queued, overloaded, or externally meta-object-invoked slots, but not for every ordinary same-thread Python callback. Focused tests will verify emitted payloads, selected overloads, delivery count, thread affinity, and receiver lifetime at these boundaries.
