# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Render and export meta-analysis results."""

import gzip
import re
import shutil
import tempfile
from collections import namedtuple
from pathlib import Path
from typing import TYPE_CHECKING
from PyQt6.QtCore import (
    QByteArray,
    QEvent,
    QObject,
    QPointF,
    QRectF,
    QTimer,
    Qt,
)
from PyQt6.QtGui import (
    QAction,
    QCloseEvent,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QImage,
    QPainter,
    QPixmap,
    QResizeEvent,
    QShowEvent,
    QTextOption,
    QTransform,
)
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QMainWindow,
    QMenu,
    QSizePolicy,
    QTreeWidgetItem,
)
import os
import sys
from rc_metastudio import (
    adaptive_window,
    app_error_handler,
    plot_capabilities,
    r_bridge,
    result_sections,
)
from rc_metastudio.analysis_results import AnalysisResult
from rc_metastudio.funnel_plot_editor_dialog import FunnelPlotEditorDialog
from rc_metastudio.plot_editor_dialog import EditPlotDialog
from rc_metastudio.qt_geometry import logical_extent_to_physical_pixels
from rc_metastudio.settings import (
    restore_results_window_state,
    save_results_window_state,
)

if TYPE_CHECKING:
    from ui_results_window import Ui_ResultsWindow
else:
    from rc_metastudio.ui_results_window import Ui_ResultsWindow

PageSize = (612, 792)
padding = 25
horizontal_padding = 75
PlotExportFormat = namedtuple("PlotExportFormat", ["extension", "label", "qt_format"])
PLOT_EXPORT_FORMATS = (
    PlotExportFormat("pdf", "PDF", None),
    PlotExportFormat("png", "PNG", "PNG"),
    PlotExportFormat("tiff", "TIFF", None),
    PlotExportFormat("svg", "SVG", None),
)
PLOT_EXPORT_FORMATS_BY_EXTENSION = {
    export_format.extension: export_format for export_format in PLOT_EXPORT_FORMATS
}
PLOT_EXPORT_EXTENSION_ALIASES = {
    "pdf": (".pdf",),
    "png": (".png",),
    "tiff": (".tif", ".tiff"),
    "svg": (".svg", ".svgz"),
}
PLOT_EXPORT_GUIDANCE = {
    "pdf": "Recommended vector format for journal submission and print workflows.",
    "svg": "Scalable vector format; ideal for editing and lossless resizing.",
    "tiff": "Publication-grade 600 dpi raster export with lossless compression.",
    "png": "Publication-grade 600 dpi raster export for compatible submission systems.",
}
NO_RESULTS_MESSAGE = "No results could be computed for this analysis."
ROW_HEIGHT = 15  # by trial-and-error; seems to work very well
SECTION_SPACING = ROW_HEIGHT
MAX_VECTOR_PLOT_SCALE = 4.0
QGraphicsSvgItem = None
QSvgRenderer = None


def _svg_item_class():
    global QGraphicsSvgItem
    if QGraphicsSvgItem is None:
        from PyQt6.QtSvgWidgets import QGraphicsSvgItem as _QGraphicsSvgItem

        class OpaqueGraphicsSvgItem(_QGraphicsSvgItem):
            """Paint SVG plots on paper instead of the themed scene canvas."""

            def paint(self, painter, option, widget=None):
                painter.fillRect(self.boundingRect(), Qt.GlobalColor.white)
                super().paint(painter, option, widget)

        QGraphicsSvgItem = OpaqueGraphicsSvgItem
    return QGraphicsSvgItem


def _svg_renderer_class():
    global QSvgRenderer
    if QSvgRenderer is None:
        from PyQt6.QtSvg import QSvgRenderer as _QSvgRenderer

        QSvgRenderer = _QSvgRenderer
    return QSvgRenderer


def _path_with_export_extension(file_path, export_format):
    aliases = PLOT_EXPORT_EXTENSION_ALIASES[export_format.extension]
    if os.path.splitext(str(file_path))[1].lower() in aliases:
        return file_path
    return "%s.%s" % (file_path, export_format.extension)


class PlotArtifact(object):
    def __init__(
        self, title, image_path, capability, params_path=None, display_path=None
    ):
        self.title = title
        self.image_path = str(image_path)
        self.params_path = params_path
        self.capability = dict(capability)
        self.plot_kind = self.capability["plot_kind"]
        self.display_image_path = str(display_path or self.image_path)

    def display_path(self):
        if os.path.exists(self.display_image_path):
            return self.display_image_path
        return self.image_path

    def has_vector_display(self):
        return self.display_path().lower().endswith((".svg", ".svgz"))

    def can_display(self):
        if self.has_vector_display():
            item = _svg_item_class()(self.display_path())
            return item.renderer().isValid()
        return not QPixmap(self.image_path).isNull()

    def export_formats(self):
        if self.params_path:
            return PLOT_EXPORT_FORMATS
        return (PLOT_EXPORT_FORMATS_BY_EXTENSION["png"],)


class SelectableResultsTextItem(QGraphicsTextItem):
    def __init__(self, text, results_window):
        super(SelectableResultsTextItem, self).__init__(text)
        self._results_window = results_window

    def contextMenuEvent(self, event):
        try:
            self._results_window._show_text_context_menu(self, event)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            app_error_handler.handle_exception(
                type(e), e, e.__traceback__, parent=self._results_window
            )
            event.accept()


class ResponsivePixmapItem(QGraphicsPixmapItem):
    def __init__(self, source_pixmap):
        super(ResponsivePixmapItem, self).__init__()
        self.source_pixmap = QPixmap(source_pixmap)
        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

    def replace_source(self, source_pixmap):
        self.source_pixmap = QPixmap(source_pixmap)

    def setPixmap(self, pixmap):
        super().setPixmap(_pixmap_with_white_background(pixmap))

    def paint(self, painter, option, widget=None):
        painter.fillRect(self.boundingRect(), Qt.GlobalColor.white)
        super().paint(painter, option, widget)


def _pixmap_with_white_background(pixmap):
    if pixmap.isNull():
        return QPixmap(pixmap)
    opaque = QPixmap(pixmap.size())
    opaque.setDevicePixelRatio(pixmap.devicePixelRatioF())
    opaque.fill(Qt.GlobalColor.white)
    painter = QPainter(opaque)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return opaque


def _svg_bytes_with_white_background(path):
    opener = gzip.open if str(path).lower().endswith(".svgz") else open
    with opener(path, "rb") as svg_file:
        svg = svg_file.read()
    root = re.search(rb"<svg\b[^>]*>", svg, flags=re.IGNORECASE)
    if root is None:
        return svg
    white_canvas = b'<rect width="100%" height="100%" fill="#ffffff"/>'
    return svg[: root.end()] + white_canvas + svg[root.end() :]


def _opaque_svg_renderer(path, parent):
    return _svg_renderer_class()(
        QByteArray(_svg_bytes_with_white_background(path)), parent
    )


def _pixmap_device_independent_size(pixmap):
    """Return a pixmap's logical dimensions without discarding its DPR."""
    dpr = max(1.0, float(pixmap.devicePixelRatioF()))
    return (float(pixmap.width()) / dpr, float(pixmap.height()) / dpr)


class ResultsWindow(QMainWindow, Ui_ResultsWindow):
    def __init__(self, results: AnalysisResult, parent=None):

        super(ResultsWindow, self).__init__(parent)
        self._svg_plot_items = []
        self._raster_plot_items = []
        self._refitting_svg_plots = False
        self._viewport_refit_pending = False
        self._viewport_width_override = None
        self._first_show_refit_pending = True
        self._layout_items = []
        self._nav_items_to_sections = {}
        self.setupUi(self)
        viewport = self.graphics_view.viewport()
        if viewport is None:
            raise RuntimeError("Results graphics view has no viewport")
        viewport.installEventFilter(self)
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.RESULTS
        )
        restored_state = restore_results_window_state(self)
        self.copied_item = QByteArray()
        self.paste_offset = 5
        self.add_offset = 5
        self.buffer_size = 2
        self.borders = []
        self._active_text_context_menu = None

        self.nav_tree.itemClicked.connect(
            app_error_handler.safe_slot(self.item_clicked, parent=self)
        )
        self.results_nav_splitter.splitterMoved.connect(
            app_error_handler.safe_slot(
                lambda _pos, _index: self._schedule_viewport_refit(), parent=self
            )
        )

        self.nav_tree.setHeaderLabels(["Results"])
        self.nav_tree.setItemsExpandable(True)
        # layout-audit: allow=content-overflow-control; reason=required content may consume available layout width
        self.nav_tree.setMinimumWidth(0)
        self.nav_tree.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        self.graphics_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.results_nav_splitter.setChildrenCollapsible(False)
        self.results_nav_splitter.setStretchFactor(0, 1)
        self.results_nav_splitter.setStretchFactor(1, 1)
        self.x_coord = 5.0
        self.y_coord = 5.0

        self._restored_splitter_proportions = restored_state["splitter_proportions"]
        self._splitter_restore_pending = True

        self.scene = QGraphicsScene(self)

        results = _normalize_results(results)

        self.images = results["images"]
        self.display_images = results["display_images"]
        self.image_order = None
        if "image_order" in results:
            self.image_order = results["image_order"]

        self.params_paths = {}
        if "image_params_paths" in results:
            self.params_paths = results["image_params_paths"]
        self.plot_capabilities = results["plot_capabilities"]

        self.items_to_coords = {}
        self._wrapped_text_items = []
        self.texts = results["texts"]
        self.texts, self.references_text = result_sections.pop_references_section(
            self.texts
        )

        self.add_result_sections()
        self.add_references()
        self._relayout_sections()

        # reset the scene
        self.graphics_view.setScene(self.scene)
        self.graphics_view.ensureVisible(QRectF(0, 0, 0, 0))
        # Establish the restored ratio before the first native show/layout pass.
        # QSplitter then preserves that ratio as the window receives its final
        # screen-safe geometry, and the queued refit sees a stable viewport.
        self._apply_restored_splitter_proportions()

    def add_result_sections(self):
        ordered_sections = result_sections.order_display_sections(
            texts=list(self.texts.items()),
            images=list(self.images.items()),
            explicit_image_order=self.image_order,
        )

        for section in ordered_sections:
            if section.kind == "text":
                self.add_text_section(section.key, section.display_title, section.value)
            elif section.kind == "image":
                self.add_image_section(
                    section.key, section.display_title, section.value
                )

    def add_image_section(self, title, display_title, image):
        params_path = None
        if self.params_paths is not None and title in self.params_paths:
            params_path = self.params_paths[title]

        artifact = self.create_plot_artifact(title, image, params_path=params_path)
        if not artifact.can_display():
            return

        qt_item = self.add_title(display_title)
        img_shape, pos, plot_item = self.create_plot_item(artifact, self.position())

        self.items_to_coords[id(qt_item)] = pos
        self._nav_items_to_sections[id(qt_item)] = plot_item

    def create_plot_artifact(self, title, image_path, params_path=None):
        return PlotArtifact(
            title,
            image_path,
            self.plot_capabilities[title],
            params_path=params_path,
            display_path=self.display_images.get(title),
        )

    def add_text_section(self, title, display_title, text):
        qt_item = self.add_title(display_title)
        _, pos = self.create_text_item(str(text), self.position(), wrap=True)
        self.items_to_coords[id(qt_item)] = pos
        self._nav_items_to_sections[id(qt_item)] = self._layout_items[-1]

    def generate_pixmap(self, image):
        # now the image
        pixmap = QPixmap(image)
        if pixmap.isNull():
            return pixmap

        logical_width, logical_height = _pixmap_device_independent_size(pixmap)
        scaled_width, scaled_height = self._fit_size_to_viewport(
            logical_width, logical_height
        )

        if scaled_width > self.scene.width():
            # layout-audit: allow=intrinsic-ratio; reason=scene follows its intrinsic-ratio visual artifact
            self.scene.setSceneRect(
                0, 0, scaled_width + horizontal_padding, self.scene.height()
            )

        dpr = max(1.0, float(pixmap.devicePixelRatioF()))
        pixmap = pixmap.scaled(
            max(1, logical_extent_to_physical_pixels(scaled_width, dpr)),
            max(1, logical_extent_to_physical_pixels(scaled_height, dpr)),
            transformMode=Qt.TransformationMode.SmoothTransformation,
        )
        pixmap.setDevicePixelRatio(dpr)

        return pixmap

    def _fit_size_to_viewport(self, width, height, max_scale=1.0):
        if width <= 0 or height <= 0:
            return (width, height)

        viewport_width = self._plot_viewport_width()
        scale = min(max_scale, float(viewport_width) / float(width))
        return (max(1.0, float(width) * scale), max(1.0, float(height) * scale))

    def _fit_vector_plot_to_viewport(self, svg_item):
        """Fit one SVG item to the current viewport while preserving its ratio."""
        item_width = svg_item.boundingRect().width()
        item_height = svg_item.boundingRect().height()
        if not self.isVisible():
            return item_width, item_height

        scaled_width, scaled_height = self._fit_size_to_viewport(
            item_width,
            item_height,
            max_scale=MAX_VECTOR_PLOT_SCALE,
        )
        if item_width <= 0:
            return scaled_width, scaled_height

        target_scale = float(scaled_width) / float(item_width)
        if abs(target_scale - svg_item.scale()) >= 0.001:
            svg_item.setScale(target_scale)
        return scaled_width, scaled_height

    def _plot_viewport_width(self):
        viewport_width = self._layout_viewport_width()
        return max(1, viewport_width - self.x_coord - padding)

    def _layout_viewport_width(self):
        if self._viewport_width_override is not None:
            return self._viewport_width_override
        viewport = self.graphics_view.viewport()
        if viewport is None:
            raise RuntimeError("Results graphics view has no viewport")
        viewport_width = viewport.width()
        if viewport_width <= horizontal_padding:
            viewport_width = self.graphics_view.width()
        if viewport_width <= horizontal_padding:
            viewport_width = max(self.results_nav_splitter.width(), self.width())
        return viewport_width

    def add_references(self):
        if self.references_text is None:
            return

        qt_item = self.add_title(result_sections.REFERENCE_SECTION_TITLE)
        text_item_rect, pos = self.create_text_item(
            str(self.references_text), self.position(), wrap=True
        )
        self.items_to_coords[id(qt_item)] = pos
        self._nav_items_to_sections[id(qt_item)] = self._layout_items[-1]

    def add_title(self, title):
        text = QGraphicsTextItem(str(title))
        title_font = QFont(self.font())
        title_font.setBold(True)
        text.setFont(title_font)
        document = text.document()
        if document is None:
            raise RuntimeError("Results title has no text document")
        text_option = document.defaultTextOption()
        text_option.setWrapMode(QTextOption.WrapMode.WordWrap)
        document.setDefaultTextOption(text_option)
        text.setTextWidth(self._text_wrap_width())
        self._wrapped_text_items.append(text)
        self.scene.addItem(text)
        self._layout_items.append(text)
        qt_item = QTreeWidgetItem(self.nav_tree, [title])
        # layout-audit: allow=intrinsic-ratio; reason=scene follows its intrinsic-ratio visual artifact
        self.scene.setSceneRect(
            0,
            0,
            self.scene.width(),
            self.y_coord + text.boundingRect().height() + padding,
        )
        text.setPos(self.position())
        self.y_coord += text.boundingRect().height()
        return qt_item

    def _advance_past_text_item(self, txt_item, text):
        bounding_height = txt_item.boundingRect().height()
        document = txt_item.document()
        if document is None:
            raise RuntimeError("Results text item has no text document")
        document_height = document.size().height()
        line_count = max(1, str(text).count("\n") + 1)
        font_metrics = QFontMetricsF(txt_item.font())
        line_height = (
            line_count * font_metrics.lineSpacing() + 2 * document.documentMargin()
        )
        return max(bounding_height, document_height, line_height)

    def item_clicked(self, item, column):
        self.graphics_view.centerOn(self.items_to_coords[id(item)])

    def create_text_item(self, text, position, wrap=False):
        txt_item = SelectableResultsTextItem(text, self)
        txt_item.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        if wrap:
            document = txt_item.document()
            if document is None:
                raise RuntimeError("Results text item has no text document")
            text_option = document.defaultTextOption()
            text_option.setWrapMode(QTextOption.WrapMode.WordWrap)
            document.setDefaultTextOption(text_option)
            txt_item.setTextWidth(self._text_wrap_width())
            self._wrapped_text_items.append(txt_item)
        txt_item.setToolTip(
            "To copy the text:\n"
            "1) Right click on the text and choose select all.\n"
            "2) Right click again and choose copy."
        )
        txt_item.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.scene.addItem(txt_item)
        self._layout_items.append(txt_item)
        text_height = self._advance_past_text_item(txt_item, text)
        # layout-audit: allow=intrinsic-ratio; reason=scene follows its intrinsic-ratio visual artifact
        self.scene.setSceneRect(
            0,
            0,
            max(self.scene.width(), txt_item.boundingRect().size().width()),
            self.y_coord + text_height + SECTION_SPACING + padding,
        )

        self.y_coord += text_height + SECTION_SPACING
        txt_item.setPos(position)

        return (txt_item.boundingRect(), position)

    def _show_text_context_menu(self, text_item, event):
        if self._active_text_context_menu is not None:
            event.accept()
            return

        context_menu = QMenu(self)
        self._active_text_context_menu = context_menu

        select_all_action = QAction("Select All", self)
        select_all_action.triggered.connect(
            app_error_handler.safe_slot(
                lambda _checked=False: self._select_all_text(text_item), parent=self
            )
        )
        context_menu.addAction(select_all_action)

        copy_action = QAction("Copy", self)
        copy_action.triggered.connect(
            app_error_handler.safe_slot(
                lambda _checked=False: self._copy_text_selection(text_item),
                parent=self,
            )
        )
        context_menu.addAction(copy_action)

        shown = app_error_handler.popup_context_menu(
            context_menu, event.screenPos(), parent=self, event=event
        )
        if shown:
            context_menu.aboutToHide.connect(self._clear_text_context_menu)
        else:
            self._clear_text_context_menu()

    def _clear_text_context_menu(self):
        self._active_text_context_menu = None

    def _select_all_text(self, text_item):
        cursor = text_item.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        text_item.setTextCursor(cursor)

    def _copy_text_selection(self, text_item):
        selected_text = text_item.textCursor().selectedText()
        if selected_text:
            clipboard = QApplication.clipboard()
            if clipboard is None:
                raise RuntimeError("Qt application has no clipboard")
            clipboard.setText(selected_text.replace("\u2029", "\n"))

    def _text_wrap_width(self):
        viewport_width = self._layout_viewport_width()
        return max(1, viewport_width - self.x_coord - padding)

    def _update_wrapped_text_widths(self):
        if not self._wrapped_text_items:
            return

        wrap_width = self._text_wrap_width()
        scene_width = self.scene.width()
        scene_height = self.scene.height()
        for txt_item in self._wrapped_text_items:
            txt_item.setTextWidth(wrap_width)
            scene_rect = txt_item.sceneBoundingRect()
            scene_width = max(scene_width, scene_rect.right() + padding)
            scene_height = max(scene_height, scene_rect.bottom() + padding)
        # layout-audit: allow=intrinsic-ratio; reason=scene follows its intrinsic-ratio visual artifact
        self.scene.setSceneRect(0, 0, scene_width, scene_height)

    def _refit_viewport_items(self):
        self._update_wrapped_text_widths()
        self._refit_svg_plot_items()
        self._refit_raster_plot_items()
        self._relayout_sections()

    def _schedule_viewport_refit(self):
        if self._viewport_refit_pending:
            return
        self._viewport_refit_pending = True
        QTimer.singleShot(0, self._run_scheduled_viewport_refit)

    def _run_scheduled_viewport_refit(self):
        self._viewport_refit_pending = False
        if self.isVisible():
            if self._first_show_refit_pending:
                self._first_show_refit_pending = False
                self._set_restored_splitter_sizes()
                self._viewport_width_override = self._layout_viewport_width()
            try:
                self._refit_viewport_items()
            finally:
                self._viewport_width_override = None

    def eventFilter(  # ty: ignore[invalid-method-override] -- PyQt6 generated-form multiple inheritance
        self, watched: QObject | None, event: QEvent | None
    ) -> bool:
        if (
            event is not None
            and watched is self.graphics_view.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            self._schedule_viewport_refit()
        return super(ResultsWindow, self).eventFilter(watched, event)

    def _refit_svg_plot_items(self):
        if self._refitting_svg_plots:
            return

        self._refitting_svg_plots = True
        try:
            for item in self._svg_plot_items:
                item_width = item.boundingRect().width()
                if item_width <= 0:
                    continue

                self._fit_vector_plot_to_viewport(item)
        finally:
            self._refitting_svg_plots = False

    def _refit_raster_plot_items(self):
        for item in self._raster_plot_items:
            source = item.source_pixmap
            if source.isNull():
                continue
            logical_width, logical_height = _pixmap_device_independent_size(source)
            scaled_width, _scaled_height = self._fit_size_to_viewport(
                logical_width, logical_height
            )
            item.setPixmap(source)
            item.setScale(float(scaled_width) / float(logical_width))

    def _relayout_sections(self):
        """Place every result item from its current measured size and stored order."""
        next_y = float(self.add_offset)
        for item in self._layout_items:
            item.setPos(self.x_coord, next_y)
            if isinstance(item, SelectableResultsTextItem):
                item_height = self._advance_past_text_item(item, item.toPlainText())
            else:
                item_height = item.sceneBoundingRect().height()
            next_y += item_height
            if not isinstance(item, QGraphicsTextItem) or isinstance(
                item, SelectableResultsTextItem
            ):
                next_y += SECTION_SPACING

        self.y_coord = next_y
        for nav_item_id, section_item in self._nav_items_to_sections.items():
            self.items_to_coords[nav_item_id] = section_item.scenePos()

        scene_bounds = self.scene.itemsBoundingRect()
        # layout-audit: allow=intrinsic-ratio; reason=scene follows its intrinsic-ratio visual artifact
        self.scene.setSceneRect(
            0,
            0,
            max(self._viewport_width(), scene_bounds.right() + padding),
            max(1, scene_bounds.bottom() + padding),
        )

    def showEvent(  # ty: ignore[invalid-method-override] -- PyQt6 generated-form multiple inheritance
        self, event: QShowEvent | None
    ) -> None:
        super(ResultsWindow, self).showEvent(event)
        self._schedule_viewport_refit()

    def _apply_restored_splitter_proportions(self):
        if not self._splitter_restore_pending:
            return
        self._splitter_restore_pending = False
        self._set_restored_splitter_sizes()
        # QSplitter applies child geometry lazily on some Qt platforms.  Refresh
        # it now so the one queued refit observes the final viewport dimensions.
        self.results_nav_splitter.refresh()
        self._schedule_viewport_refit()

    def _set_restored_splitter_sizes(self):
        splitter_extent = max(2, self.results_nav_splitter.width())
        self.results_nav_splitter.setSizes(
            [
                max(1, int(splitter_extent * value))
                for value in self._restored_splitter_proportions
            ]
        )

    def resizeEvent(  # ty: ignore[invalid-method-override] -- PyQt6 generated-form multiple inheritance
        self, event: QResizeEvent | None
    ) -> None:
        super(ResultsWindow, self).resizeEvent(event)
        self._schedule_viewport_refit()

    def closeEvent(  # ty: ignore[invalid-method-override] -- PyQt6 generated-form multiple inheritance
        self, event: QCloseEvent | None
    ) -> None:
        save_results_window_state(self)
        super(ResultsWindow, self).closeEvent(event)

    def create_pixmap_item(
        self, pixmap, position, title, image_path, params_path=None, matrix=QTransform()
    ):
        artifact = self.create_plot_artifact(title, image_path, params_path=params_path)
        item = ResponsivePixmapItem(QPixmap(image_path))
        item.setPixmap(pixmap)
        item.setToolTip(
            'To save the image:\nright-click on the image and choose "save image as".'
        )

        self.y_coord += item.boundingRect().size().height() + SECTION_SPACING
        #        item.setFlags(QGraphicsItem.ItemIsSelectable|
        #                      QGraphicsItem.ItemIsMovable)
        item.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

        # layout-audit: allow=intrinsic-ratio; reason=scene follows its intrinsic-ratio visual artifact
        self.scene.setSceneRect(
            0,
            0,
            max(self.scene.width(), item.boundingRect().size().width()),
            self.y_coord + item.boundingRect().size().height() + padding,
        )

        self.scene.clearSelection()
        self.scene.addItem(item)
        self._raster_plot_items.append(item)
        self._layout_items.append(item)
        item.setPos(position)

        # attach event handler for mouse-clicks, i.e., to handle
        # user right-clicks
        item.contextMenuEvent = self._make_context_menu(artifact, item)

        return (item.boundingRect().size(), position, item)

    def create_plot_item(self, artifact, position):
        if artifact.has_vector_display():
            svg_item = self.create_svg_item(artifact, position)
            if svg_item is not None:
                return svg_item

        pixmap = self.generate_pixmap(artifact.image_path)
        return self.create_pixmap_item(
            pixmap,
            position,
            artifact.title,
            artifact.image_path,
            params_path=artifact.params_path,
        )

    def create_svg_item(self, artifact, position):
        renderer = _opaque_svg_renderer(artifact.display_path(), self)
        if not renderer.isValid():
            return None
        item = _svg_item_class()()
        item.setSharedRenderer(renderer)

        item.setToolTip(
            'To save the image:\nright-click on the image and choose "save image as".'
        )
        item.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

        scaled_width, scaled_height = self._fit_vector_plot_to_viewport(item)

        self.y_coord += scaled_height + SECTION_SPACING
        # layout-audit: allow=intrinsic-ratio; reason=scene follows its intrinsic-ratio visual artifact
        self.scene.setSceneRect(
            0,
            0,
            max(self.scene.width(), scaled_width),
            self.y_coord + scaled_height + padding,
        )

        self.scene.clearSelection()
        self.scene.addItem(item)
        self._svg_plot_items.append(item)
        self._layout_items.append(item)
        item.setPos(position)
        item.contextMenuEvent = self._make_context_menu(artifact, item)

        return (item.boundingRect().size(), position, item)

    def _make_context_menu(self, artifact, plot_item):
        plot_img = QImage(artifact.image_path)

        def _graphics_item_context_menu(event):
            def add_save_as_menu_action(menu, export_format):
                action = QAction("Save %s Image As" % export_format.label, self)
                guidance = (
                    PLOT_EXPORT_GUIDANCE[export_format.extension]
                    if artifact.params_path
                    else "Save the original raster image at its native resolution."
                )
                action.setStatusTip(guidance)
                action.setToolTip(guidance)

                def save_action(_checked=False, selected_format=export_format):
                    self.save_image_as(
                        artifact,
                        unscaled_image=(
                            plot_img
                            if selected_format.qt_format is not None
                            and not artifact.params_path
                            else None
                        ),
                        format=selected_format.extension,
                    )

                action.triggered.connect(
                    app_error_handler.safe_slot(save_action, parent=self)
                )
                menu.addAction(action)

            context_menu = QMenu(self)
            if artifact.capability["editable"]:
                if plot_capabilities.option_groups(artifact.plot_kind):
                    action = QAction("Edit Plot", self)
                    action.triggered.connect(
                        app_error_handler.safe_slot(
                            lambda _checked=False: self.edit_plot(artifact, plot_item),
                            parent=self,
                        )
                    )
                    context_menu.addAction(action)
            for export_format in artifact.export_formats():
                add_save_as_menu_action(context_menu, export_format)

            app_error_handler.popup_context_menu(
                context_menu, event.screenPos(), parent=self, event=event
            )

        return _graphics_item_context_menu

    def edit_plot(self, artifact, plot_item):
        regenerator = artifact.capability["regenerator"]
        if regenerator == "forest":
            self._edit_forest_plot(artifact, plot_item)
        elif regenerator == "regression":
            self.edit_regression_plot(artifact, plot_item)
        elif regenerator == "funnel":
            self._edit_funnel_plot(artifact, plot_item)

    def _edit_funnel_plot(self, artifact, plot_item):
        plot_params = r_bridge.load_vars_for_plot(
            artifact.params_path, return_params_dict=True
        )
        if plot_params is False:
            return
        dialog = FunnelPlotEditorDialog(
            plot_params, artifact.image_path, parent=self, plot_type=artifact.plot_kind
        )
        dialog.applied.connect(
            app_error_handler.safe_slot(
                lambda: self._apply_funnel_plot_edits(dialog, artifact, plot_item),
                parent=self,
            )
        )
        dialog.exec()

    def _apply_funnel_plot_edits(self, dialog, artifact, plot_item):
        updated_params = dialog.plot_params()
        outpath = updated_params.get("funnel.outpath") or artifact.image_path
        target_path = Path(outpath)
        if target_path.suffix.lower() == ".svgz":
            raise ValueError(
                "SVGZ output is not supported when editing funnel plots; use SVG instead."
            )
        transaction_dir = Path(
            tempfile.mkdtemp(prefix=".rcms-funnel-", dir=str(target_path.parent))
        )
        temporary_base = transaction_dir / "plot"
        temporary_output = transaction_dir / (
            "render" + (target_path.suffix or ".png")
        )
        persisted_params = Path("%s.params" % artifact.params_path)
        persisted_backup = transaction_dir / "params.backup"
        had_persisted_params = persisted_params.exists()
        try:
            for suffix in ("data", "res"):
                source = Path("%s.%s" % (artifact.params_path, suffix))
                shutil.copyfile(source, "%s.%s" % (temporary_base, suffix))
            r_bridge.update_plot_params(
                updated_params,
                plot_params_name="params",
                write_them_out=True,
                outpath="%s.params" % temporary_base,
            )
            if had_persisted_params:
                shutil.copyfile(persisted_params, persisted_backup)
            r_bridge.regenerate_small_study_effects_funnel(
                str(temporary_base), output_path=str(temporary_output)
            )
            r_bridge.update_plot_params(
                updated_params,
                plot_params_name="params",
                write_them_out=True,
                outpath=str(persisted_params),
            )
            os.replace(str(temporary_output), str(target_path))
        except Exception:
            dialog.mark_commit_failed()
            if had_persisted_params and persisted_backup.exists():
                try:
                    shutil.copyfile(persisted_backup, persisted_params)
                except Exception:
                    pass
            elif not had_persisted_params and persisted_params.exists():
                try:
                    persisted_params.unlink()
                except OSError:
                    pass
            raise
        finally:
            shutil.rmtree(transaction_dir, ignore_errors=True)
        self._refresh_plot_item(plot_item, artifact, outpath)
        dialog.mark_commit_succeeded()

    def _edit_forest_plot(self, artifact, plot_item):
        plot_params = r_bridge.load_vars_for_plot(
            artifact.params_path, return_params_dict=True
        )
        if plot_params is False:
            return

        dialog = EditPlotDialog(plot_params, artifact.image_path, parent=self)
        dialog.applied.connect(
            app_error_handler.safe_slot(
                lambda: self._apply_forest_plot_edits(dialog, artifact, plot_item),
                parent=self,
            )
        )
        dialog.exec()

    def edit_regression_plot(self, artifact, plot_item):
        plot_params = r_bridge.load_vars_for_plot(
            artifact.params_path, return_params_dict=True
        )
        if plot_params is False:
            return

        dialog = EditPlotDialog(
            plot_params, artifact.image_path, parent=self, plot_type="regression"
        )
        dialog.applied.connect(
            app_error_handler.safe_slot(
                lambda: self._apply_regression_plot_edits(dialog, artifact, plot_item),
                parent=self,
            )
        )
        dialog.exec()

    def _apply_regression_plot_edits(self, dialog, artifact, plot_item):
        updated_params = dialog.plot_params()
        outpath = updated_params["bp_outpath"] or artifact.image_path
        r_bridge.update_plot_params(
            updated_params,
            write_them_out=True,
            outpath="%s.params" % artifact.params_path,
        )
        r_bridge.regenerate_regression_plot_data()
        r_bridge.generate_reg_plot(outpath)
        r_bridge.write_out_plot_data(artifact.params_path)
        self._refresh_plot_item(plot_item, artifact, outpath)

    def _apply_forest_plot_edits(self, dialog, artifact, plot_item):
        updated_params = dialog.plot_params()
        outpath = updated_params["fp_outpath"] or artifact.image_path
        r_bridge.update_plot_params(
            updated_params,
            write_them_out=True,
            outpath="%s.params" % artifact.params_path,
        )
        r_bridge.regenerate_plot_data()
        r_bridge.generate_forest_plot(outpath)
        r_bridge.write_out_plot_data(artifact.params_path)

        self._refresh_plot_item(plot_item, artifact, outpath)

    def _refresh_plot_item(self, plot_item, artifact, outpath):

        if plot_item is not None:
            refreshed_artifact = PlotArtifact(
                artifact.title,
                outpath,
                artifact.capability,
                params_path=artifact.params_path,
                display_path=artifact.display_image_path,
            )
            if (
                isinstance(plot_item, _svg_item_class())
                and refreshed_artifact.has_vector_display()
            ):
                renderer = _opaque_svg_renderer(refreshed_artifact.display_path(), self)
                if renderer.isValid():
                    plot_item.setSharedRenderer(renderer)
                    self._schedule_viewport_refit()
                    self.scene.update()
            elif isinstance(plot_item, ResponsivePixmapItem):
                source_pixmap = QPixmap(outpath)
                if not source_pixmap.isNull():
                    plot_item.replace_source(source_pixmap)
                    self._schedule_viewport_refit()

    def save_image_as(self, artifact, unscaled_image=None, format=None):
        if not isinstance(artifact, PlotArtifact):
            artifact = self.create_plot_artifact("", artifact, params_path=None)

        if format not in PLOT_EXPORT_FORMATS_BY_EXTENSION:
            valid_formats = ", ".join(PLOT_EXPORT_FORMATS_BY_EXTENSION.keys())
            raise Exception("Invalid format, needs to be one of: %s!" % valid_formats)

        export_format = PLOT_EXPORT_FORMATS_BY_EXTENSION[format]

        if not unscaled_image:
            regenerator = artifact.capability["regenerator"]
            if regenerator == "funnel":
                r_bridge.load_vars_for_plot(artifact.params_path)
            else:
                # Loading the artifact exposes its conventional ``plot.data`` object.
                r_bridge.load_in_r("%s.plotdata" % artifact.params_path)
            default_path = {
                "forest": "forest_plot",
                "regression": "regression",
                "funnel": "small_study_effects_funnel",
            }[regenerator]
            default_path = "%s.%s" % (default_path, export_format.extension)

            # where to save the graphic?
            file_path, _selected_filter = QFileDialog.getSaveFileName(
                self,
                "Save Plot As",
                default_path,
            )

            # now we re-generate it, unless they canceled, of course
            if file_path != "":
                file_path = _path_with_export_extension(file_path, export_format)
                function_name = plot_capabilities.regenerator_name(regenerator)
                if function_name is None:
                    raise ValueError("Plot is not regeneratable: %s" % artifact.title)
                getattr(r_bridge, function_name)(file_path)
        else:
            default_path = ".".join([artifact.title.replace(" ", "_"), "png"])
            file_path, _selected_filter = QFileDialog.getSaveFileName(
                self,
                "Save Plot As",
                default_path,
            )
            if file_path != "":
                file_path = _path_with_export_extension(file_path, export_format)
                unscaled_image.save(file_path, export_format.qt_format)

    def position(self):
        return QPointF(float(self.x_coord), float(self.y_coord))

    def _viewport_width(self) -> int:
        viewport = self.graphics_view.viewport()
        if viewport is None:
            raise RuntimeError("Results graphics view has no viewport")
        return viewport.width()


def _normalize_results(results: AnalysisResult) -> AnalysisResult:
    normalized: AnalysisResult = {
        "texts": dict(results["texts"]),
        "images": dict(results["images"]),
        "display_images": dict(results["display_images"]),
        "image_var_names": dict(results["image_var_names"]),
        "image_params_paths": dict(results["image_params_paths"]),
        "image_order": (
            None if results["image_order"] is None else list(results["image_order"])
        ),
        "plot_capabilities": dict(results["plot_capabilities"]),
    }

    if not normalized["texts"] and not normalized["images"]:
        normalized["texts"]["No Results"] = NO_RESULTS_MESSAGE

    return normalized


if __name__ == "__main__":
    # make test results based on results from when meta-analysis run from amino sample project
    from rc_metastudio import settings
    from rc_metastudio.analysis_results import empty_analysis_result

    test_results = empty_analysis_result()
    test_results["images"] = {
        "Forest Plot": settings.analysis_output_path("forest.png")
    }
    test_results["texts"] = {
        "Weights": "Study names        Weights\nGonzalez       1993  7.3%\nPrins          1993  6.2%\nGiamarellou    1991  2.1%\nMaller         1993 10.7%\nSturm          1989  2.0%\nMarik          1991 12.2%\nMuijsken       1988  7.5%\nVigano         1992  1.8%\nHansen         1988  5.3%\nDe Vries       1990  6.1%\nMauracher      1989  2.2%\nNordstrom      1990  5.3%\nRozdzinski     1993 10.3%\nTer Braak      1990  8.7%\nTulkens        1988  1.2%\nVan der Auwera 1991  2.0%\nKlastersky     1977  6.0%\nVanhaeverbeek  1993  1.2%\nHollender      1989  1.8%\n",
        "Summary": "Binary Random-Effects Model\n\nMetric: Odds Ratio\n\nModel Results\n Estimate  Lower bound  Upper bound  p-value\n 0.770           0.485        1.222    0.267\n\nHeterogeneity\n    τ²  Q(df=18)  Het. p-value       I²\n 0.378    33.360         0.015  46.000%\n\nCalculation scale: log - estimate: -0.262, lower: -0.724, upper: 0.200, std. error: 0.236\n",
    }
    test_results["image_var_names"] = {"forest plot": "forest_plot"}
    test_results["image_params_paths"] = {
        "Forest Plot": settings.analysis_output_path("1369769105.72079")
    }  # change this number as necessary
    test_results["image_order"] = None

    app = app_error_handler.get_or_create_application(sys.argv)
    resultswindow = ResultsWindow(test_results)
    resultswindow.show()
    sys.exit(app.exec())
