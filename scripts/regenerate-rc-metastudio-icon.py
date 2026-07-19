from pathlib import Path
import os
import struct
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtGui


ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "src" / "rc_metastudio" / "images"
ICON_SOURCE_IMAGE = IMAGE_DIR / "RC_MetaStudio_Icon_4K.png"
PNG_TARGET = IMAGE_DIR / "rc-metastudio-app-icon-rounded.png"
ICO_TARGET = IMAGE_DIR / "rc-metastudio-app-icon-rounded.ico"
SPLASH_SOURCE_IMAGE = IMAGE_DIR / "RC_MetaStudio_Logo_4K_Preview.png"
SPLASH_TRIM_GUIDE = IMAGE_DIR / "RC_MetaStudio_Logo_4K_Transparent.png"
SPLASH_TARGET = IMAGE_DIR / "rc-metastudio-splash-logo.png"
MASTER_SIZE = 1024
CORNER_RADIUS = round(MASTER_SIZE * 0.18)
SPLASH_ARTWORK_WIDTH = 1024
SPLASH_MARGIN = 32
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _alpha_bounds(image):
    left = image.width()
    top = image.height()
    right = -1
    bottom = -1

    for y in range(image.height()):
        for x in range(image.width()):
            if QtGui.qAlpha(image.pixel(x, y)):
                left = min(left, x)
                top = min(top, y)
                right = max(right, x)
                bottom = max(bottom, y)

    if right < left or bottom < top:
        raise ValueError("source image has no non-transparent pixels")
    return QtCore.QRect(left, top, right - left + 1, bottom - top + 1)


def _render_square_master():
    source = QtGui.QImage(str(ICON_SOURCE_IMAGE)).convertToFormat(
        QtGui.QImage.Format.Format_ARGB32
    )
    if source.isNull():
        raise ValueError(f"Could not load {ICON_SOURCE_IMAGE}")

    scaled = source.scaled(
        MASTER_SIZE,
        MASTER_SIZE,
        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
        QtCore.Qt.TransformationMode.SmoothTransformation,
    )

    master = QtGui.QImage(MASTER_SIZE, MASTER_SIZE, QtGui.QImage.Format.Format_ARGB32)
    master.fill(QtCore.Qt.GlobalColor.transparent)

    painter = QtGui.QPainter(master)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
    rounded_tile = QtGui.QPainterPath()
    rounded_tile.addRoundedRect(
        QtCore.QRectF(0, 0, MASTER_SIZE, MASTER_SIZE),
        CORNER_RADIUS,
        CORNER_RADIUS,
    )
    painter.setClipPath(rounded_tile)
    painter.fillPath(rounded_tile, QtGui.QColor("white"))
    painter.drawImage(0, 0, scaled)
    painter.end()
    return master


def _render_splash():
    source = QtGui.QImage(str(SPLASH_SOURCE_IMAGE)).convertToFormat(
        QtGui.QImage.Format.Format_ARGB32
    )
    if source.isNull():
        raise ValueError(f"Could not load {SPLASH_SOURCE_IMAGE}")

    trim_guide = QtGui.QImage(str(SPLASH_TRIM_GUIDE)).convertToFormat(
        QtGui.QImage.Format.Format_ARGB32
    )
    if trim_guide.isNull():
        raise ValueError(f"Could not load {SPLASH_TRIM_GUIDE}")

    artwork = source.copy(_alpha_bounds(trim_guide))
    scaled = artwork.scaledToWidth(
        SPLASH_ARTWORK_WIDTH,
        QtCore.Qt.TransformationMode.SmoothTransformation,
    )
    splash_size = QtCore.QSize(
        scaled.width() + (2 * SPLASH_MARGIN),
        scaled.height() + (2 * SPLASH_MARGIN),
    )

    splash = QtGui.QImage(splash_size, QtGui.QImage.Format.Format_ARGB32)
    splash.fill(QtGui.QColor("white"))

    painter = QtGui.QPainter(splash)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.drawImage(
        SPLASH_MARGIN,
        SPLASH_MARGIN,
        scaled,
    )
    painter.end()
    return splash


def _png_bytes(image):
    data = QtCore.QByteArray()
    buffer = QtCore.QBuffer(data)
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise ValueError("Could not encode PNG frame")
    return bytes(data.data())


def _ico_dimension_byte(size):
    return 0 if size == 256 else size


def _write_ico(master):
    frames = []
    for size in ICO_SIZES:
        frame = master.scaled(
            size,
            size,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        frames.append((size, _png_bytes(frame)))

    header_size = 6 + (16 * len(frames))
    offset = header_size
    directory_entries = []
    payload = bytearray()

    for size, frame_data in frames:
        directory_entries.append(
            struct.pack(
                "<BBBBHHII",
                _ico_dimension_byte(size),
                _ico_dimension_byte(size),
                0,
                0,
                1,
                32,
                len(frame_data),
                offset,
            )
        )
        payload.extend(frame_data)
        offset += len(frame_data)

    with ICO_TARGET.open("wb") as output:
        output.write(struct.pack("<HHH", 0, 1, len(frames)))
        for entry in directory_entries:
            output.write(entry)
        output.write(payload)


def main():
    app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])
    master = _render_square_master()
    splash = _render_splash()

    if not master.save(str(PNG_TARGET), "PNG"):
        raise ValueError(f"Could not write {PNG_TARGET}")
    if not splash.save(str(SPLASH_TARGET), "PNG"):
        raise ValueError(f"Could not write {SPLASH_TARGET}")
    _write_ico(master)

    icon = QtGui.QIcon(str(ICO_TARGET))
    available_sizes = sorted(
        (size.width(), size.height()) for size in icon.availableSizes()
    )
    expected_sizes = [(size, size) for size in ICO_SIZES]
    if available_sizes != expected_sizes:
        raise ValueError(f"Unexpected ICO sizes: {available_sizes}")

    app.quit()


if __name__ == "__main__":
    sys.exit(main())
