# Build the Headless Harness Around the Existing Analysis Adapter

The headless analysis harness should exercise the existing Python analysis adapter behavior rather than bypassing directly to R package functions. The current application depends on Python-side parameter shaping, result parsing, artifact naming, and model-to-analysis conversion, so direct R calls would miss behavior that users experience through the app.

The harness should remove the dependency on `MetaForm`, `QApplication`, and the full GUI lifecycle while preserving the smallest Python analysis boundary that still represents current application behavior.
