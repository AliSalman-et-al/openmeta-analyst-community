"""Generate Python and R forest-plot defaults from the shared contract."""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config" / "forest_plot_defaults.json"
TARGETS = {
    ROOT / "src" / "rc_metastudio" / "plot_defaults.py": (
        '"""Generated user-facing forest-plot defaults. Do not edit directly."""\n\n'
        "FOREST_ARM_LABELS = ({intervention!r}, {control!r})\n\n"
        "\n"
        "def apply_default_forest_arm_labels(surface):\n"
        "    surface.col3_str_edit.setText(FOREST_ARM_LABELS[0])\n"
        "    surface.col4_str_edit.setText(FOREST_ARM_LABELS[1])\n"
    ),
    ROOT / "r" / "RCMetaR" / "R" / "forest_defaults.R": (
        "# Generated from config/forest_plot_defaults.json. Do not edit directly.\n"
        "rcmetar.default.arm.labels <- function() {{\n"
        '    c("{intervention}", "{control}")\n'
        "}}\n"
    ),
}


def rendered_targets():
    values = json.loads(CONTRACT.read_text(encoding="utf-8"))["arm_labels"]
    if len(values) != 2 or not all(
        isinstance(value, str) and value for value in values
    ):
        raise ValueError("arm_labels must contain two non-empty strings")
    substitutions = {"intervention": values[0], "control": values[1]}
    return {
        path: template.format(**substitutions) for path, template in TARGETS.items()
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    for path, content in rendered_targets().items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(path.relative_to(ROOT))
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
    if stale:
        parser.error("stale generated defaults: %s" % ", ".join(map(str, stale)))


if __name__ == "__main__":
    main()
