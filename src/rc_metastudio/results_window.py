# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Render and export meta-analysis results."""

import random
from collections import namedtuple
from PyQt5.QtCore import QByteArray, QEvent, QPoint, QRectF, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QImage,
    QPixmap,
    QTextOption,
    QTransform,
)
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
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
import ui_results_window
import app_error_handler
import forms.ui_edit_forest_plot
import meta_py_r
from plot_defaults import FOREST_ARM_LABELS
import plot_capabilities
from plot_text import apply_plot_text_input_limits, plot_text_value, set_plot_text_value
import qt_text
import result_sections
import adaptive_window
from settings import (
    restore_results_window_state,
    save_results_window_state,
)
# import shutil

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

FOREST_STYLE_LABELS = {
    "default": "Default (metafor)",
    "revman": "RevMan",
    "bmj": "BMJ",
}
FOREST_STYLE_VALUES = {label: value for value, label in FOREST_STYLE_LABELS.items()}
FOREST_STYLE_DEFAULT_COLORS = {
    "default": "#2f5597",
    "revman": "#000000",
    "bmj": "#6b58a6",
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
        from PyQt5.QtSvg import QGraphicsSvgItem as _QGraphicsSvgItem

        QGraphicsSvgItem = _QGraphicsSvgItem
    return QGraphicsSvgItem


def _svg_renderer_class():
    global QSvgRenderer
    if QSvgRenderer is None:
        from PyQt5.QtSvg import QSvgRenderer as _QSvgRenderer

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
        self.setTransformationMode(Qt.SmoothTransformation)

    def replace_source(self, source_pixmap):
        self.source_pixmap = QPixmap(source_pixmap)


def _pixmap_device_independent_size(pixmap):
    """Return a pixmap's logical dimensions without discarding its DPR."""
    dpr = max(1.0, float(pixmap.devicePixelRatioF()))
    return (float(pixmap.width()) / dpr, float(pixmap.height()) / dpr)


class EditPlotDialog(QDialog, forms.ui_edit_forest_plot.Ui_edit_forest_plot_dlg):
    applied = pyqtSignal()

    def __init__(self, plot_params, image_path, parent=None, plot_type="forest"):
        super(EditPlotDialog, self).__init__(parent)
        self.setupUi(self)
        apply_plot_text_input_limits(self)
        self._loading_style = False
        self._params = dict(plot_params or {})
        self.plot_type = plot_type
        self._option_groups = plot_capabilities.option_groups(plot_type)

        self.color_btn.clicked.connect(
            app_error_handler.safe_slot(self._choose_color, parent=self)
        )
        self.style_cbo.currentIndexChanged[str].connect(
            app_error_handler.safe_slot(self._style_changed, parent=self)
        )
        apply_button = self.buttonBox.button(QDialogButtonBox.Apply)
        if apply_button is not None:
            apply_button.clicked.connect(self.applied.emit)
        ok_button = self.buttonBox.button(QDialogButtonBox.Ok)
        if ok_button is not None:
            ok_button.clicked.connect(self.applied.emit)

        self._load_params(image_path)
        self._configure_option_groups()
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.TRANSACTIONAL
        )

    def _configure_option_groups(self):
        self.groupBox.setVisible("columns" in self._option_groups)
        self.default_panel.setVisible("forest" in self._option_groups)
        self.label_16.setVisible("summary" in self._option_groups)
        self.show_summary_line.setVisible("summary" in self._option_groups)
        self.regression_group.setVisible("regression" in self._option_groups)

    def _load_params(self, image_path):
        self._loading_style = True
        try:
            style = self._normalized_style(
                self._params.get(self._param_name("style"), "default")
            )
            self.style_cbo.setCurrentText(FOREST_STYLE_LABELS[style])
            self._set_text(
                self.col1_str_edit, self._params.get("fp_col1_str", "Study or Subgroup")
            )
            self._set_text(
                self.col2_str_edit, self._params.get("fp_col2_str", "[default]")
            )
            self._set_text(
                self.col3_str_edit,
                self._params.get("fp_col3_str", FOREST_ARM_LABELS[0]),
            )
            self._set_text(
                self.col4_str_edit,
                self._params.get("fp_col4_str", FOREST_ARM_LABELS[1]),
            )
            self.show_1.setChecked(self._bool_param("fp_show_col1", True))
            self.show_2.setChecked(self._bool_param("fp_show_col2", True))
            self.show_3.setChecked(self._bool_param("fp_show_col3", True))
            self.show_4.setChecked(self._bool_param("fp_show_col4", True))
            self.show_raw_counts.setChecked(
                self._bool_param("fp_show_raw_counts", True)
            )
            self.show_headers.setChecked(self._bool_param("fp_show_headers", True))
            self.show_annotation.setChecked(
                self._bool_param("fp_show_annotation", True)
            )
            self._set_text(
                self.x_lbl_le, self._params.get(self._param_name("xlabel"), "[default]")
            )
            self._set_text(
                self.plot_lb_le,
                self._params.get(self._param_name("plot_lb"), "[default]"),
            )
            self._set_text(
                self.plot_ub_le,
                self._params.get(self._param_name("plot_ub"), "[default]"),
            )
            ticks_name = "bp_xticks" if self.plot_type == "regression" else "fp_xticks"
            self._set_text(self.x_ticks_le, self._params.get(ticks_name, "[default]"))
            self.show_summary_line.setChecked(
                self._bool_param("fp_show_summary_line", True)
            )
            self._set_text(
                self.image_path, image_path or self._params.get("fp_outpath", "")
            )
            color = (
                self._params.get(self._param_name("accent_color"))
                or FOREST_STYLE_DEFAULT_COLORS[style]
            )
            self._set_accent_color(color)
            self.point_size_multiplier.setValue(
                self._float_param(self._param_name("point_size_multiplier"), 1.0)
            )
            self.show_regression_line.setChecked(
                self._bool_param("bp_show_regression_line", True)
            )
            self.show_confidence_band.setChecked(
                self._bool_param("bp_show_confidence_band", True)
            )
            self.show_prediction_interval.setChecked(
                self._bool_param("bp_show_prediction_interval", False)
            )
            self.show_legend.setChecked(self._bool_param("bp_show_legend", False))
        finally:
            self._loading_style = False

    def _style_changed(self, label):
        if self._loading_style:
            return
        style = FOREST_STYLE_VALUES.get(str(label), "default")
        self._set_accent_color(FOREST_STYLE_DEFAULT_COLORS[style])

    def _choose_color(self):
        current = QColor(self.accent_color.text())
        color = QColorDialog.getColor(current, self, "Plot Accent Color")
        if color.isValid():
            self._set_accent_color(color.name())

    def _set_accent_color(self, color):
        text = str(color or FOREST_STYLE_DEFAULT_COLORS["default"])
        self.accent_color.setText(text)
        self.color_btn.setStyleSheet("background-color: %s;" % text)

    def _set_text(self, widget, value):
        set_plot_text_value(widget, self._scalar(value))

    def _scalar(self, value):
        if isinstance(value, (list, tuple)) and value:
            return value[0]
        return value

    def _bool_param(self, name, default):
        value = self._scalar(self._params.get(name, default))
        if isinstance(value, str):
            return value.lower() in ("true", "t", "1", "yes")
        return bool(value)

    def _float_param(self, name, default):
        try:
            return float(self._scalar(self._params.get(name, default)))
        except (TypeError, ValueError):
            return default

    def _normalized_style(self, style):
        style = str(self._scalar(style) or "default").strip().lower()
        return style if style in FOREST_STYLE_LABELS else "default"

    def _param_name(self, suffix):
        return "%s_%s" % ("bp" if self.plot_type == "regression" else "fp", suffix)

    def plot_params(self):
        style = FOREST_STYLE_VALUES.get(str(self.style_cbo.currentText()), "default")
        params = {
            "fp_style": style,
            "fp_show_col1": self.show_1.isChecked(),
            "fp_col1_str": qt_text.to_native_text(plot_text_value(self.col1_str_edit)),
            "fp_show_col2": self.show_2.isChecked(),
            "fp_col2_str": qt_text.to_native_text(plot_text_value(self.col2_str_edit)),
            "fp_show_col3": self.show_3.isChecked(),
            "fp_col3_str": qt_text.to_native_text(plot_text_value(self.col3_str_edit)),
            "fp_show_col4": self.show_4.isChecked(),
            "fp_col4_str": qt_text.to_native_text(plot_text_value(self.col4_str_edit)),
            "fp_show_raw_counts": self.show_raw_counts.isChecked(),
            "fp_show_headers": self.show_headers.isChecked(),
            "fp_show_annotation": self.show_annotation.isChecked(),
            "fp_accent_color": qt_text.to_native_text(self.accent_color.text()),
            "fp_point_size_multiplier": self.point_size_multiplier.value(),
            "fp_xlabel": qt_text.to_native_text(plot_text_value(self.x_lbl_le)),
            "fp_plot_lb": qt_text.to_native_text(self.plot_lb_le.text()),
            "fp_plot_ub": qt_text.to_native_text(self.plot_ub_le.text()),
            "fp_xticks": qt_text.to_native_text(self.x_ticks_le.text()),
            "fp_show_summary_line": self.show_summary_line.isChecked(),
            "fp_outpath": qt_text.to_native_text(self.image_path.text()),
        }
        forest_display_path = self._scalar(self._params.get("fp_display_path", ""))
        if forest_display_path:
            params["fp_display_path"] = forest_display_path
        if self.plot_type == "regression":
            params = {
                "bp_style": style,
                "bp_accent_color": qt_text.to_native_text(self.accent_color.text()),
                "bp_point_size_multiplier": self.point_size_multiplier.value(),
                "bp_xlabel": qt_text.to_native_text(plot_text_value(self.x_lbl_le)),
                "bp_plot_lb": qt_text.to_native_text(self.plot_lb_le.text()),
                "bp_plot_ub": qt_text.to_native_text(self.plot_ub_le.text()),
                "bp_xticks": qt_text.to_native_text(self.x_ticks_le.text()),
                "bp_show_regression_line": self.show_regression_line.isChecked(),
                "bp_show_confidence_band": self.show_confidence_band.isChecked(),
                "bp_show_prediction_interval": self.show_prediction_interval.isChecked(),
                "bp_show_legend": self.show_legend.isChecked(),
                "bp_outpath": qt_text.to_native_text(self.image_path.text()),
            }
            regression_display_path = self._scalar(
                self._params.get("bp_display_path", "")
            )
            if regression_display_path:
                params["bp_display_path"] = regression_display_path
        return params


# Compatibility name for callers and tests that still target the forest-only API.
EditForestPlotDialog = EditPlotDialog


class ResultsWindow(QMainWindow, ui_results_window.Ui_ResultsWindow):
    def __init__(self, results, parent=None):

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
        self.graphics_view.viewport().installEventFilter(self)
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.RESULTS
        )
        restored_state = restore_results_window_state(self)
        self.copied_item = QByteArray()
        self.paste_offset = 5
        self.add_offset = 5
        self.buffer_size = 2
        self.prev_point = QPoint()
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
        self.nav_tree.setMinimumWidth(0)
        self.nav_tree.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.graphics_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.results_nav_splitter.setChildrenCollapsible(False)
        self.results_nav_splitter.setStretchFactor(0, 1)
        self.results_nav_splitter.setStretchFactor(1, 1)
        self.x_coord = 5
        self.y_coord = 5

        self._restored_splitter_proportions = restored_state["splitter_proportions"]
        self._splitter_restore_pending = True

        self.scene = QGraphicsScene(self)

        results = _normalize_results(results)

        self.images = results["images"]
        self.display_images = results["display_images"]
        print("images returned from analytic routine: %s" % self.images)
        self.image_order = None
        if "image_order" in results:
            self.image_order = results["image_order"]
            print("image display order: %s" % self.image_order)

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
        print("title: %s; image: %s" % (title, image))
        cur_y = max(0, self.y_coord)
        print("cur_y: %s" % cur_y)
        params_path = None
        if self.params_paths is not None and title in self.params_paths:
            params_path = self.params_paths[title]

        artifact = self.create_plot_artifact(title, image, params_path=params_path)
        if not artifact.can_display():
            print("Skipping image that Qt could not load: %s" % image)
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
        try:
            print("title: %s; text: %s" % (title, text))
            cur_y = max(0, self.y_coord)
            print("cur_y: %s" % cur_y)
            # first add the title
            qt_item = self.add_title(display_title)

            # now the text
            text_item_rect, pos = self.create_text_item(
                str(text), self.position(), wrap=True
            )
            self.items_to_coords[id(qt_item)] = pos
            self._nav_items_to_sections[id(qt_item)] = self._layout_items[-1]
        except:
            pass

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
            self.scene.setSceneRect(
                0, 0, scaled_width + horizontal_padding, self.scene.height()
            )

        dpr = max(1.0, float(pixmap.devicePixelRatioF()))
        pixmap = pixmap.scaled(
            max(1, int(round(scaled_width * dpr))),
            max(1, int(round(scaled_height * dpr))),
            transformMode=Qt.SmoothTransformation,
        )
        pixmap.setDevicePixelRatio(dpr)

        return pixmap

    def _fit_size_to_viewport(self, width, height, max_scale=1.0):
        if width <= 0 or height <= 0:
            return (width, height)

        viewport_width = self._plot_viewport_width()
        scale = min(max_scale, float(viewport_width) / float(width))
        return (max(1, int(width * scale)), max(1, int(height * scale)))

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
        viewport_width = self.graphics_view.viewport().width()
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
        print("Adding title")
        text = QGraphicsTextItem(str(title))
        title_font = QFont(self.font())
        title_font.setBold(True)
        text.setFont(title_font)
        text_option = text.document().defaultTextOption()
        text_option.setWrapMode(QTextOption.WordWrap)
        text.document().setDefaultTextOption(text_option)
        text.setTextWidth(self._text_wrap_width())
        self._wrapped_text_items.append(text)
        print("  title at: %s" % self.y_coord)
        self.scene.addItem(text)
        self._layout_items.append(text)
        qt_item = QTreeWidgetItem(self.nav_tree, [title])
        self.scene.setSceneRect(
            0,
            0,
            self.scene.width(),
            self.y_coord + text.boundingRect().height() + padding,
        )
        print(("  Setting position at (%d,%d)" % (self.x_coord, self.y_coord)))
        text.setPos(self.position())  #####
        self.y_coord += text.boundingRect().height()
        return qt_item

    def _advance_past_text_item(self, txt_item, text):
        bounding_height = txt_item.boundingRect().height()
        document_height = txt_item.document().size().height()
        line_count = max(1, str(text).count("\n") + 1)
        font_metrics = QFontMetricsF(txt_item.font())
        line_height = (
            line_count * font_metrics.lineSpacing()
            + 2 * txt_item.document().documentMargin()
        )
        return max(bounding_height, document_height, line_height)

    def item_clicked(self, item, column):
        print(self.items_to_coords[id(item)])
        self.graphics_view.centerOn(self.items_to_coords[id(item)])

    def create_text_item(self, text, position, wrap=False):
        txt_item = SelectableResultsTextItem(text, self)
        txt_item.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        if wrap:
            text_option = txt_item.document().defaultTextOption()
            text_option.setWrapMode(QTextOption.WordWrap)
            txt_item.document().setDefaultTextOption(text_option)
            txt_item.setTextWidth(self._text_wrap_width())
            self._wrapped_text_items.append(txt_item)
        txt_item.setToolTip(
            "To copy the text:\n"
            "1) Right click on the text and choose select all.\n"
            "2) Right click again and choose copy."
        )
        txt_item.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        self.scene.addItem(txt_item)
        self._layout_items.append(txt_item)
        # fix for issue #149; was formerly txt_item.boundingRect().size().height()

        # self.y_coord += txt_item.boundingRect.height()  #ROW_HEIGHT*text.count("\n")
        text_height = self._advance_past_text_item(txt_item, text)
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
        cursor.select(QTextCursor.Document)
        text_item.setTextCursor(cursor)

    def _copy_text_selection(self, text_item):
        selected_text = text_item.textCursor().selectedText()
        if selected_text:
            QApplication.clipboard().setText(selected_text.replace("\u2029", "\n"))

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
                splitter_extent = self.results_nav_splitter.width()
                screen = self.screen()
                if self.isMaximized() and screen is not None:
                    window_chrome_width = max(0, self.width() - splitter_extent)
                    splitter_extent = min(
                        splitter_extent,
                        screen.availableGeometry().width() - window_chrome_width,
                    )
                splitter_extent = max(
                    2, splitter_extent - self.results_nav_splitter.handleWidth()
                )
                proportion_total = sum(self._restored_splitter_proportions)
                content_proportion = (
                    self._restored_splitter_proportions[1] / proportion_total
                )
                self._viewport_width_override = max(
                    1,
                    int(splitter_extent * content_proportion)
                    - (2 * self.graphics_view.frameWidth()),
                )
            try:
                self._refit_viewport_items()
            finally:
                self._viewport_width_override = None

    def eventFilter(self, watched, event):
        if watched is self.graphics_view.viewport() and event.type() == QEvent.Resize:
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
        self.scene.setSceneRect(
            0,
            0,
            max(self.graphics_view.viewport().width(), scene_bounds.right() + padding),
            max(1, scene_bounds.bottom() + padding),
        )

    def showEvent(self, event):
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

    def resizeEvent(self, event):
        super(ResultsWindow, self).resizeEvent(event)
        self._schedule_viewport_refit()

    def closeEvent(self, event):
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
        item.setFlags(QGraphicsItem.ItemIsSelectable)

        self.scene.setSceneRect(
            0,
            0,
            max(self.scene.width(), item.boundingRect().size().width()),
            self.y_coord + item.boundingRect().size().height() + padding,
        )

        print("creating item @:%s" % position)

        # item.setMatrix(matrix)
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
        item = _svg_item_class()(artifact.display_path())
        if not item.renderer().isValid():
            return None

        item.setToolTip(
            'To save the image:\nright-click on the image and choose "save image as".'
        )
        item.setFlags(QGraphicsItem.ItemIsSelectable)

        scaled_width, scaled_height = self._fit_vector_plot_to_viewport(item)

        self.y_coord += scaled_height + SECTION_SPACING
        self.scene.setSceneRect(
            0,
            0,
            max(self.scene.width(), scaled_width),
            self.y_coord + scaled_height + padding,
        )

        print("creating item @:%s" % position)
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
            self.edit_forest_plot(artifact, plot_item)
        elif regenerator == "regression":
            self.edit_regression_plot(artifact, plot_item)

    def edit_forest_plot(self, artifact, plot_item):
        plot_params = meta_py_r.load_vars_for_plot(
            artifact.params_path, return_params_dict=True
        )
        if plot_params is False:
            return

        dialog = EditForestPlotDialog(plot_params, artifact.image_path, parent=self)
        dialog.applied.connect(
            app_error_handler.safe_slot(
                lambda: self._apply_forest_plot_edits(dialog, artifact, plot_item),
                parent=self,
            )
        )
        dialog.exec()

    def edit_regression_plot(self, artifact, plot_item):
        plot_params = meta_py_r.load_vars_for_plot(
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
        meta_py_r.update_plot_params(
            updated_params,
            write_them_out=True,
            outpath="%s.params" % artifact.params_path,
        )
        meta_py_r.regenerate_regression_plot_data()
        meta_py_r.generate_reg_plot(outpath)
        meta_py_r.write_out_plot_data(artifact.params_path)
        self._refresh_plot_item(plot_item, artifact, outpath)

    def _apply_forest_plot_edits(self, dialog, artifact, plot_item):
        updated_params = dialog.plot_params()
        outpath = updated_params["fp_outpath"] or artifact.image_path
        meta_py_r.update_plot_params(
            updated_params,
            write_them_out=True,
            outpath="%s.params" % artifact.params_path,
        )
        meta_py_r.regenerate_plot_data()
        meta_py_r.generate_forest_plot(outpath)
        meta_py_r.write_out_plot_data(artifact.params_path)

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
                renderer = _svg_renderer_class()(
                    refreshed_artifact.display_path(), self
                )
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
            # note that the params object will, by convention,
            # have the (generic) name 'plot.data' -- after this
            # call, this object will be in the namespace
            meta_py_r.load_in_R("%s.plotdata" % artifact.params_path)

            regenerator = artifact.capability["regenerator"]
            default_path = {
                "forest": "forest_plot",
                "regression": "regression",
            }[regenerator]
            default_path = "%s.%s" % (default_path, export_format.extension)

            # where to save the graphic?
            file_path, _selected_filter = QFileDialog.getSaveFileName(
                self,
                "RC MetaStudio -- save plot as",
                default_path,
            )

            # now we re-generate it, unless they canceled, of course
            if file_path != "":
                file_path = _path_with_export_extension(file_path, export_format)
                function_name = plot_capabilities.regenerator_name(regenerator)
                if function_name is None:
                    raise ValueError("Plot is not regeneratable: %s" % artifact.title)
                getattr(meta_py_r, function_name)(file_path)
        else:  # case where we just have the png and can't regenerate the pdf from plot data
            default_path = ".".join([artifact.title.replace(" ", "_"), "png"])
            file_path, _selected_filter = QFileDialog.getSaveFileName(
                self,
                "RC MetaStudio -- save plot as",
                default_path,
            )
            if file_path != "":
                file_path = _path_with_export_extension(file_path, export_format)
                unscaled_image.save(file_path, export_format.qt_format)

    def position(self):
        point = QPoint(int(self.x_coord), int(self.y_coord))
        return self.graphics_view.mapToScene(point)


def _normalize_results(results):
    if not isinstance(results, dict):
        return _empty_results()

    normalized = dict(results)
    normalized["texts"] = dict(normalized.get("texts") or {})
    normalized["images"] = dict(normalized.get("images") or {})
    normalized["display_images"] = dict(normalized.get("display_images") or {})
    normalized["image_var_names"] = dict(normalized.get("image_var_names") or {})
    normalized["image_params_paths"] = dict(normalized.get("image_params_paths") or {})
    normalized["plot_capabilities"] = plot_capabilities.validate_result(normalized)
    extra_display_images = sorted(
        set(normalized["display_images"]) - set(normalized["images"])
    )
    if extra_display_images:
        raise ValueError(
            "Display artifacts have no matching plot artifact: %s"
            % ", ".join(extra_display_images)
        )
    normalized.setdefault("image_order", None)

    if not normalized["texts"] and not normalized["images"]:
        normalized["texts"]["No Results"] = NO_RESULTS_MESSAGE

    return normalized


def _empty_results():
    return {
        "texts": {"No Results": NO_RESULTS_MESSAGE},
        "images": {},
        "display_images": {},
        "image_var_names": {},
        "image_params_paths": {},
        "image_order": None,
        "plot_capabilities": {},
    }


if __name__ == "__main__":
    # make test results based on results from when meta-analysis run from amino sample project
    import settings

    test_results = {}
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
