from pathlib import Path
import os
import struct
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtCore, QtGui


ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "src" / "images"
SOURCE_IMAGE = IMAGE_DIR / "OMA_community_transparent.png"
PNG_TARGET = IMAGE_DIR / "OMA_community.png"
ICO_TARGET = IMAGE_DIR / "OMA_community.ico"
MASTER_SIZE = 1024
MASTER_MARGIN = 32
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
        raise ValueError(f"{SOURCE_IMAGE} has no non-transparent pixels")
    return QtCore.QRect(left, top, right - left + 1, bottom - top + 1)


def _render_square_master():
    source = QtGui.QImage(str(SOURCE_IMAGE)).convertToFormat(QtGui.QImage.Format_ARGB32)
    if source.isNull():
        raise ValueError(f"Could not load {SOURCE_IMAGE}")

    artwork = source.copy(_alpha_bounds(source))
    target_extent = MASTER_SIZE - (2 * MASTER_MARGIN)
    scaled = artwork.scaled(
        target_extent,
        target_extent,
        QtCore.Qt.KeepAspectRatio,
        QtCore.Qt.SmoothTransformation,
    )

    master = QtGui.QImage(MASTER_SIZE, MASTER_SIZE, QtGui.QImage.Format_ARGB32)
    master.fill(QtCore.Qt.transparent)

    painter = QtGui.QPainter(master)
    painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
    painter.drawImage(
        (MASTER_SIZE - scaled.width()) // 2,
        (MASTER_SIZE - scaled.height()) // 2,
        scaled,
    )
    painter.end()
    return master


def _png_bytes(image):
    data = QtCore.QByteArray()
    buffer = QtCore.QBuffer(data)
    buffer.open(QtCore.QIODevice.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise ValueError("Could not encode PNG frame")
    return bytes(data)


def _ico_dimension_byte(size):
    return 0 if size == 256 else size


def _write_ico(master):
    frames = []
    for size in ICO_SIZES:
        frame = master.scaled(
            size,
            size,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation,
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

    if not master.save(str(PNG_TARGET), "PNG"):
        raise ValueError(f"Could not write {PNG_TARGET}")
    _write_ico(master)

    icon = QtGui.QIcon(str(ICO_TARGET))
    available_sizes = sorted((size.width(), size.height()) for size in icon.availableSizes())
    expected_sizes = [(size, size) for size in ICO_SIZES]
    if available_sizes != expected_sizes:
        raise ValueError(f"Unexpected ICO sizes: {available_sizes}")

    app.quit()


if __name__ == "__main__":
    sys.exit(main())
