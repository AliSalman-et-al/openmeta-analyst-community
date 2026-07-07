#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if row.get("image")]


def content_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    rgb = image.convert("RGB")
    white = Image.new("RGB", rgb.size, "white")
    return ImageChops.difference(rgb, white).getbbox()


def image_metrics(row: dict[str, str]) -> dict[str, str]:
    image_path = Path(row["image"])
    with Image.open(image_path) as image:
        bbox = content_bbox(image)
        width, height = image.size
        if bbox is None:
            margins = (width, height, width, height)
            content_width = 0
            content_height = 0
        else:
            left, top, right, bottom = bbox
            margins = (left, top, width - right, height - bottom)
            content_width = right - left
            content_height = bottom - top
        stat = ImageStat.Stat(ImageChops.difference(image.convert("RGB"), Image.new("RGB", image.size, "white")))
        mean_delta = sum(stat.mean) / len(stat.mean)
    return {
        **row,
        "width": str(width),
        "height": str(height),
        "content_width": str(content_width),
        "content_height": str(content_height),
        "margin_left": str(margins[0]),
        "margin_top": str(margins[1]),
        "margin_right": str(margins[2]),
        "margin_bottom": str(margins[3]),
        "blankish": str(mean_delta < 1.0),
        "mean_white_delta": f"{mean_delta:.3f}",
    }


def make_thumb(image_path: Path, box: tuple[int, int]) -> Image.Image:
    with Image.open(image_path) as image:
        thumb = image.convert("RGB")
        thumb.thumbnail(box, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", box, "white")
        left = (box[0] - thumb.width) // 2
        top = (box[1] - thumb.height) // 2
        canvas.paste(thumb, (left, top))
        return canvas


def contact_sheet(rows: list[dict[str, str]], output: Path, title: str, thumb_size: tuple[int, int]) -> None:
    if not rows:
        return
    columns = 6
    label_height = 72
    title_height = 54
    rows_count = (len(rows) + columns - 1) // columns
    width = columns * thumb_size[0]
    height = title_height + rows_count * (thumb_size[1] + label_height)
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((12, 16), title, fill="black", font=font)
    for index, row in enumerate(rows):
        col = index % columns
        row_index = index // columns
        x = col * thumb_size[0]
        y = title_height + row_index * (thumb_size[1] + label_height)
        sheet.paste(make_thumb(Path(row["image"]), thumb_size), (x, y))
        label = f"{row['kind']} {row['workflow']}\n{row['style']} / {row['scenario']}"
        draw.text((x + 8, y + thumb_size[1] + 8), label, fill="black", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def write_metrics(metrics: list[dict[str, str]], output: Path) -> None:
    if not metrics:
        return
    fields = list(metrics[0].keys())
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(metrics)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--thumb-width", type=int, default=700)
    parser.add_argument("--thumb-height", type=int, default=360)
    args = parser.parse_args()

    rows = read_manifest(args.manifest)
    out_dir = args.out_dir or args.manifest.parent
    metrics = [image_metrics(row) for row in rows]
    write_metrics(metrics, out_dir / "metrics.csv")

    for scenario in sorted({row["scenario"] for row in rows}):
        subset = [row for row in rows if row["scenario"] == scenario]
        subset.sort(key=lambda row: (row["kind"], row["workflow"], row["style"]))
        contact_sheet(
            subset,
            out_dir / f"contact_{scenario}.png",
            f"Forest plot visual QA: {scenario}",
            (args.thumb_width, args.thumb_height),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
