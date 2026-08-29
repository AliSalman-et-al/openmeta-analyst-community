"""Generated user-facing forest-plot defaults. Do not edit directly."""

FOREST_ARM_LABELS = ("Intervention", "Control")


def apply_default_forest_arm_labels(surface):
    surface.col3_str_edit.setText(FOREST_ARM_LABELS[0])
    surface.col4_str_edit.setText(FOREST_ARM_LABELS[1])
