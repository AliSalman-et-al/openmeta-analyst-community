"""Generate portable SVG masters for dataset-type icons.

The mathematical notation is rendered with Matplotlib MathText and converted
to SVG paths.  The resulting application assets therefore have no runtime
font, TeX, or Matplotlib dependency.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
from matplotlib.figure import Figure
from matplotlib.patches import FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "src" / "rc_metastudio" / "images" / "icons" / "dataset-types"

THEME_PALETTES = {
    "light": ("#60798D", "#7A909C", "#FFFFFF"),
    "dark": ("#E7EDF0", "#B8C6CE", "#263238"),
}
INK = ""
MID_INK = ""
DETAIL_INK = ""
CURRENT_THEME = "light"


def _new_figure(*, width: float = 48, height: float = 48) -> tuple[Figure, object]:
    figure = Figure(figsize=(width / 72, height / 72), dpi=72, facecolor="none")
    axes = figure.add_axes((0, 0, 1, 1))
    axes.set_xlim(0, 1)
    axes.set_ylim(0, 1)
    axes.axis("off")
    return figure, axes


def _save(figure: Figure, name: str) -> None:
    output_path = OUTPUT_DIR / CURRENT_THEME / name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output_path,
        format="svg",
        transparent=True,
        metadata={"Date": None, "Creator": "RC MetaStudio icon generator"},
    )
    normalized_svg = "\n".join(
        line.rstrip() for line in output_path.read_text(encoding="utf-8").splitlines()
    )
    output_path.write_text(f"{normalized_svg}\n", encoding="utf-8")


def _single_formula(
    name: str,
    formula: str,
    *,
    size: float,
    canvas: tuple[float, float] = (48, 48),
    y_center: float = 0.5,
) -> None:
    figure, axes = _new_figure(width=canvas[0], height=canvas[1])
    axes.text(
        0.5,
        y_center,
        formula,
        color=INK,
        fontsize=size,
        horizontalalignment="center",
        verticalalignment="center",
    )
    _save(figure, name)


def _paired_formula(
    name: str,
    left: str,
    right: str,
    *,
    size: float,
    arm_center: float = 0.18,
    separator_size: float = 8.5,
    canvas: tuple[float, float] = (48, 48),
    y_center: float = 0.5,
) -> None:
    figure, axes = _new_figure(width=canvas[0], height=canvas[1])
    axes.text(
        arm_center,
        y_center,
        left,
        color=INK,
        fontsize=size,
        horizontalalignment="center",
        verticalalignment="center",
    )
    axes.text(
        1 - arm_center,
        y_center,
        right,
        color=INK,
        fontsize=size,
        horizontalalignment="center",
        verticalalignment="center",
    )
    axes.text(
        0.5,
        y_center - 0.01,
        r"$\mathrm{vs}$",
        color=MID_INK,
        fontsize=separator_size,
        horizontalalignment="center",
        verticalalignment="center",
    )
    _save(figure, name)


def _diagnostic() -> None:
    figure, axes = _new_figure()
    for x in (0.22, 0.54):
        for y in (0.22, 0.54):
            axes.add_patch(
                FancyBboxPatch(
                    (x, y),
                    0.24,
                    0.24,
                    boxstyle="round,pad=0,rounding_size=0.04",
                    linewidth=0,
                    facecolor=INK
                    if (x, y) in ((0.22, 0.54), (0.54, 0.22))
                    else MID_INK,
                )
            )
    axes.plot((0.27, 0.32, 0.41), (0.68, 0.62, 0.72), color=DETAIL_INK, linewidth=1.5)
    axes.plot((0.59, 0.73), (0.27, 0.41), color=DETAIL_INK, linewidth=1.5)
    axes.plot((0.73, 0.59), (0.27, 0.41), color=DETAIL_INK, linewidth=1.5)
    _save(figure, "diagnostic-data.svg")


def main() -> None:
    global CURRENT_THEME, DETAIL_INK, INK, MID_INK
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "mathtext.fontset": "stix",
            "svg.fonttype": "path",
            "svg.hashsalt": "rc-metastudio-functional-icons",
        }
    )
    for CURRENT_THEME, (INK, MID_INK, DETAIL_INK) in THEME_PALETTES.items():
        _single_formula("one-arm-proportion.svg", r"$\frac{x}{N}$", size=27)
        _single_formula("one-arm-mean.svg", r"$\mu$", size=34, y_center=0.57)
        _single_formula("single-regression-coefficient.svg", r"$\beta$", size=27)
        _single_formula(
            "generic-effect-size.svg", r"$(\theta,\,SE)$", size=18, canvas=(54, 40)
        )
        _paired_formula(
            "two-arm-proportions.svg",
            r"$\frac{x_1}{N_1}$",
            r"$\frac{x_2}{N_2}$",
            size=18,
            arm_center=0.27,
            separator_size=9,
            canvas=(72, 44),
        )
        _paired_formula(
            "two-arm-means.svg",
            r"$\mu_1$",
            r"$\mu_2$",
            size=19,
            arm_center=0.19,
            separator_size=9.5,
            canvas=(58, 40),
            y_center=0.56,
        )
        _single_formula(
            "standardized-mean-difference.svg", r"$g$", size=34, y_center=0.57
        )
        _diagnostic()


if __name__ == "__main__":
    main()
