# Rename Unclear Legacy Python Module Prefixes

The file-layout migration should rename unclear legacy Python module prefixes such as `meta_` and `ma_` where they represent product-era abbreviations or obscure module purpose. Examples include moving toward names such as `main_window.py`, `project_dataset.py`, and `rcmetar_bridge.py`.

This rename should remain mechanical: update filenames, imports, tests, and scripts without redesigning module contents or deepening interfaces during the same pass.

