# Convert Sample Projects to New Module Paths

The `.rcms` sample-project conversion should rewrite repository-owned sample project data so committed samples load directly under the new `rc_metastudio` module paths. Any temporary converter needed to rewrite old pickle module or class paths should remain unshipped maintenance tooling or be removed after use.

RC MetaStudio should not preserve `.oma` compatibility or old module-path loading in the maintained runtime. Tests should prove committed `.rcms` samples open without importing old OpenMeta[Analyst] module names.

