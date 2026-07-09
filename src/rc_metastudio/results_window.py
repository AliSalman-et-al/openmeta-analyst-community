# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Render and export meta-analysis results."""

import random
from collections import namedtuple
from PyQt5.QtCore import QByteArray, QPoint, QRectF, Qt
from PyQt5.QtGui import (
    QColor,
    QFont,
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
    QFileDialog,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QMainWindow,
    QMenu,
    QTreeWidgetItem,
)
import os
import sys
import ui_results_window
import app_error_handler
import forms.ui_edit_forest_plot
import meta_py_r
import qt_layout
import qt_text
import result_sections
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

# these are special forest plots, in that multiple parameters objects are
# require to re-generate them (and we invoke a different method!)
SIDE_BY_SIDE_FOREST_PLOTS = (
    "NLR and PLR Forest Plot",
    "Sensitivity and Specificity",
    "Cumulative Forest Plot",
)
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
QGraphicsSvgItem = None


def _svg_item_class():
    global QGraphicsSvgItem
    if QGraphicsSvgItem is None:
        from PyQt5.QtSvg import QGraphicsSvgItem as _QGraphicsSvgItem

        QGraphicsSvgItem = _QGraphicsSvgItem
    return QGraphicsSvgItem


def _canonical_svg_path(image_path):
    root, ext = os.path.splitext(str(image_path))
    if ext.lower() in (".svg", ".svgz"):
        return str(image_path)
    return "%s.svg" % root


class PlotArtifact(object):
    def __init__(self, title, image_path, params_path=None, plot_type=None):
        self.title = title
        self.image_path = str(image_path)
        self.params_path = params_path
        self.plot_type = plot_type
        self.canonical_svg_path = _canonical_svg_path(self.image_path)

    def display_path(self):
        if os.path.exists(self.canonical_svg_path):
            return self.canonical_svg_path
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


class EditForestPlotDialog(QDialog, forms.ui_edit_forest_plot.Ui_edit_forest_plot_dlg):
    def __init__(self, plot_params, image_path, parent=None):
        super(EditForestPlotDialog, self).__init__(parent)
        self.setupUi(self)
        self._loading_style = False
        self._params = dict(plot_params or {})

        self.color_btn.clicked.connect(
            app_error_handler.safe_slot(self._choose_color, parent=self)
        )
        self.style_cbo.currentIndexChanged[str].connect(
            app_error_handler.safe_slot(self._style_changed, parent=self)
        )

        self._load_params(image_path)
        qt_layout.fit_application_dialog_to_contents(self)

    def _load_params(self, image_path):
        self._loading_style = True
        try:
            style = self._normalized_style(self._params.get("fp_style", "default"))
            self.style_cbo.setCurrentText(FOREST_STYLE_LABELS[style])
            self._set_text(
                self.col1_str_edit, self._params.get("fp_col1_str", "Study or Subgroup")
            )
            self._set_text(
                self.col2_str_edit, self._params.get("fp_col2_str", "[default]")
            )
            self._set_text(
                self.col3_str_edit, self._params.get("fp_col3_str", "Experimental")
            )
            self._set_text(
                self.col4_str_edit, self._params.get("fp_col4_str", "Control")
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
            self._set_text(self.x_lbl_le, self._params.get("fp_xlabel", "[default]"))
            self._set_text(self.plot_lb_le, self._params.get("fp_plot_lb", "[default]"))
            self._set_text(self.plot_ub_le, self._params.get("fp_plot_ub", "[default]"))
            self._set_text(self.x_ticks_le, self._params.get("fp_xticks", "[default]"))
            self.show_summary_line.setChecked(
                self._bool_param("fp_show_summary_line", True)
            )
            self._set_text(
                self.image_path, image_path or self._params.get("fp_outpath", "")
            )
            color = (
                self._params.get("fp_accent_color")
                or FOREST_STYLE_DEFAULT_COLORS[style]
            )
            self._set_accent_color(color)
            self.point_size_multiplier.setValue(
                self._float_param("fp_point_size_multiplier", 1.0)
            )
        finally:
            self._loading_style = False

    def _style_changed(self, label):
        if self._loading_style:
            return
        style = FOREST_STYLE_VALUES.get(str(label), "default")
        self._set_accent_color(FOREST_STYLE_DEFAULT_COLORS[style])

    def _choose_color(self):
        current = QColor(self.accent_color.text())
        color = QColorDialog.getColor(current, self, "Forest Plot Accent Color")
        if color.isValid():
            self._set_accent_color(color.name())

    def _set_accent_color(self, color):
        text = str(color or FOREST_STYLE_DEFAULT_COLORS["default"])
        self.accent_color.setText(text)
        self.color_btn.setStyleSheet("background-color: %s;" % text)

    def _set_text(self, widget, value):
        widget.setText(str(self._scalar(value)))

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

    def plot_params(self):
        style = FOREST_STYLE_VALUES.get(str(self.style_cbo.currentText()), "default")
        return {
            "fp_style": style,
            "fp_show_col1": self.show_1.isChecked(),
            "fp_col1_str": qt_text.to_native_text(self.col1_str_edit.text()),
            "fp_show_col2": self.show_2.isChecked(),
            "fp_col2_str": qt_text.to_native_text(self.col2_str_edit.text()),
            "fp_show_col3": self.show_3.isChecked(),
            "fp_col3_str": qt_text.to_native_text(self.col3_str_edit.text()),
            "fp_show_col4": self.show_4.isChecked(),
            "fp_col4_str": qt_text.to_native_text(self.col4_str_edit.text()),
            "fp_show_raw_counts": self.show_raw_counts.isChecked(),
            "fp_show_headers": self.show_headers.isChecked(),
            "fp_show_annotation": self.show_annotation.isChecked(),
            "fp_accent_color": qt_text.to_native_text(self.accent_color.text()),
            "fp_point_size_multiplier": self.point_size_multiplier.value(),
            "fp_xlabel": qt_text.to_native_text(self.x_lbl_le.text()),
            "fp_plot_lb": qt_text.to_native_text(self.plot_lb_le.text()),
            "fp_plot_ub": qt_text.to_native_text(self.plot_ub_le.text()),
            "fp_xticks": qt_text.to_native_text(self.x_ticks_le.text()),
            "fp_show_summary_line": self.show_summary_line.isChecked(),
            "fp_outpath": qt_text.to_native_text(self.image_path.text()),
        }


class ResultsWindow(QMainWindow, ui_results_window.Ui_ResultsWindow):
    def __init__(self, results, parent=None):

        super(ResultsWindow, self).__init__(parent)
        self.setupUi(self)
        qt_layout.configure_resizable_window(self)
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
                lambda _pos, _index: self._update_wrapped_text_widths(), parent=self
            )
        )

        self.nav_tree.setHeaderLabels(["Results"])
        self.nav_tree.setItemsExpandable(True)
        self.nav_tree.setMinimumWidth(250)
        self.x_coord = 5
        self.y_coord = 5

        # set (default) splitter sizes
        self.results_nav_splitter.setSizes([260, 440])

        self.scene = QGraphicsScene(self)

        results = _normalize_results(results)

        self.images = results["images"]
        print("images returned from analytic routine: %s" % self.images)
        self.image_order = None
        if "image_order" in results:
            self.image_order = results["image_order"]
            print("image display order: %s" % self.image_order)

        self.params_paths = {}
        if "image_params_paths" in results:
            self.params_paths = results["image_params_paths"]

        self.items_to_coords = {}
        self._wrapped_text_items = []
        self.texts = results["texts"]
        self.texts, self.references_text = result_sections.pop_references_section(
            self.texts
        )

        self.add_result_sections()
        self.add_references()

        # reset the scene
        self.graphics_view.setScene(self.scene)
        self.graphics_view.ensureVisible(QRectF(0, 0, 0, 0))

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
        img_shape, pos, plot_item = self.create_plot_item(
            artifact, self.position()
        )

        self.items_to_coords[id(qt_item)] = pos

    def create_plot_artifact(self, title, image_path, params_path=None):
        return PlotArtifact(
            title,
            image_path,
            params_path=params_path,
            plot_type=self._get_plot_type(title),
        )

    def add_text_section(self, title, display_title, text):
        try:
            print("title: %s; text: %s" % (title, text))
            cur_y = max(0, self.y_coord)
            print("cur_y: %s" % cur_y)
            # first add the title
            qt_item = self.add_title(display_title)

            # now the text
            text_item_rect, pos = self.create_text_item(str(text), self.position())
            self.items_to_coords[id(qt_item)] = pos
        except:
            pass

    def generate_pixmap(self, image):
        # now the image
        pixmap = QPixmap(image)
        if pixmap.isNull():
            return pixmap

        scaled_width, scaled_height = self._fit_size_to_viewport(
            pixmap.width(), pixmap.height()
        )

        if scaled_width > self.scene.width():
            self.scene.setSceneRect(
                0, 0, scaled_width + horizontal_padding, self.scene.height()
            )

        pixmap = pixmap.scaled(
            scaled_width, scaled_height, transformMode=Qt.SmoothTransformation
        )

        return pixmap

    def _fit_size_to_viewport(self, width, height):
        if width <= 0 or height <= 0:
            return (width, height)

        viewport_width = self._plot_viewport_width()
        scale = min(1.0, float(viewport_width) / float(width))
        return (max(1, int(width * scale)), max(1, int(height * scale)))

    def _plot_viewport_width(self):
        viewport_width = max(
            self.graphics_view.viewport().width(), self.graphics_view.width()
        )
        if viewport_width <= horizontal_padding:
            viewport_width = max(self.results_nav_splitter.width(), self.width())
        return max(300, viewport_width - self.x_coord - padding)

    def add_references(self):
        if self.references_text is None:
            return

        qt_item = self.add_title(result_sections.REFERENCE_SECTION_TITLE)
        text_item_rect, pos = self.create_text_item(
            str(self.references_text), self.position(), wrap=True
        )
        self.items_to_coords[id(qt_item)] = pos

    def add_title(self, title):
        print("Adding title")
        text = QGraphicsTextItem()
        # I guess we should use a style sheet here,
        # but it seems like it'd be overkill.
        html_str = (
            '<p style="font-size: 14pt; color: black; face:verdana">%s</p>' % title
        )
        text.setHtml(html_str)
        # text.setPos(self.position())
        print("  title at: %s" % self.y_coord)
        self.scene.addItem(text)
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
        txt_item.setFont(QFont("courier", 12))
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
        viewport_width = max(
            self.graphics_view.viewport().width(), self.graphics_view.width()
        )
        if viewport_width <= horizontal_padding:
            viewport_width = max(self.results_nav_splitter.width(), self.width())
        return max(300, viewport_width - self.x_coord - padding)

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

    def showEvent(self, event):
        super(ResultsWindow, self).showEvent(event)
        self._update_wrapped_text_widths()

    def resizeEvent(self, event):
        super(ResultsWindow, self).resizeEvent(event)
        self._update_wrapped_text_widths()

    def _get_plot_type(self, title):
        # Infer plot type from title because RCMetaR does not yet return an
        # explicit plot type field.
        # more...
        plot_type = None
        tmp_title = title.lower()
        if "forest" in tmp_title:
            plot_type = "forest"
        elif "regression" in tmp_title:
            plot_type = "regression"
        return plot_type

    def create_pixmap_item(
        self, pixmap, position, title, image_path, params_path=None, matrix=QTransform()
    ):
        artifact = self.create_plot_artifact(title, image_path, params_path=params_path)
        item = QGraphicsPixmapItem(pixmap)
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

        item_width = item.boundingRect().width()
        item_height = item.boundingRect().height()
        scaled_width, scaled_height = self._fit_size_to_viewport(
            item_width, item_height
        )
        if item_width > 0:
            item.setScale(float(scaled_width) / float(item_width))

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
        item.setPos(position)
        item.contextMenuEvent = self._make_context_menu(artifact, item)

        return (item.boundingRect().size(), position, item)

    def _make_context_menu(self, artifact, plot_item):
        plot_img = QImage(artifact.image_path)

        def _graphics_item_context_menu(event):
            def add_save_as_menu_action(menu, export_format):
                action = QAction("Save %s Image As" % export_format.label, self)

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
            if artifact.params_path:
                if artifact.plot_type == "forest" and not self._is_side_by_side_fp(
                    artifact.title
                ):
                    action = QAction("Edit Forest Plot", self)
                    action.triggered.connect(
                        app_error_handler.safe_slot(
                            lambda _checked=False: self.edit_forest_plot(
                                artifact.params_path, artifact.image_path, plot_item
                            ),
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

    def edit_forest_plot(self, params_path, png_path, plot_item):
        plot_params = meta_py_r.load_vars_for_plot(params_path, return_params_dict=True)
        if plot_params is False:
            return

        dialog = EditForestPlotDialog(plot_params, png_path, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return

        updated_params = dialog.plot_params()
        outpath = updated_params["fp_outpath"] or png_path
        meta_py_r.update_plot_params(
            updated_params, write_them_out=True, outpath="%s.params" % params_path
        )
        meta_py_r.regenerate_plot_data()
        meta_py_r.generate_forest_plot(outpath)
        meta_py_r.write_out_plot_data(params_path)

        if plot_item is not None:
            artifact = self.create_plot_artifact(
                "Forest Plot", outpath, params_path=params_path
            )
            if isinstance(plot_item, _svg_item_class()) and os.path.exists(
                artifact.canonical_svg_path
            ):
                plot_item.renderer().load(artifact.canonical_svg_path)
                self.scene.update()
            elif isinstance(plot_item, QGraphicsPixmapItem):
                pixmap = self.generate_pixmap(outpath)
                if not pixmap.isNull():
                    plot_item.setPixmap(pixmap)

    def _is_side_by_side_fp(self, title):
        return any(
            [side_by_side in title for side_by_side in SIDE_BY_SIDE_FOREST_PLOTS]
        )

    def save_image_as(self, artifact, unscaled_image=None, format=None):
        if not isinstance(artifact, PlotArtifact):
            artifact = self.create_plot_artifact(
                "", artifact, params_path=None
            )

        if format not in PLOT_EXPORT_FORMATS_BY_EXTENSION:
            valid_formats = ", ".join(PLOT_EXPORT_FORMATS_BY_EXTENSION.keys())
            raise Exception("Invalid format, needs to be one of: %s!" % valid_formats)

        export_format = PLOT_EXPORT_FORMATS_BY_EXTENSION[format]

        if not unscaled_image:
            # note that the params object will, by convention,
            # have the (generic) name 'plot.data' -- after this
            # call, this object will be in the namespace
            meta_py_r.load_in_R("%s.plotdata" % artifact.params_path)

            default_path = {
                "forest": "forest_plot",
                "regression": "regression",
            }[artifact.plot_type]
            default_path = "%s.%s" % (default_path, export_format.extension)

            # where to save the graphic?
            file_path, _selected_filter = QFileDialog.getSaveFileName(
                self,
                "RC MetaStudio -- save plot as",
                default_path,
            )

            # now we re-generate it, unless they canceled, of course
            if file_path != "":
                if artifact.plot_type == "forest":
                    if self._is_side_by_side_fp(artifact.title):
                        meta_py_r.generate_forest_plot(file_path, side_by_side=True)
                    else:
                        meta_py_r.generate_forest_plot(file_path)
                elif artifact.plot_type == "regression":
                    meta_py_r.generate_reg_plot(file_path)
                else:
                    print(
                        "sorry -- I don't know how to draw %s plots!"
                        % artifact.plot_type
                    )
        else:  # case where we just have the png and can't regenerate the pdf from plot data
            default_path = ".".join([artifact.title.replace(" ", "_"), "png"])
            file_path, _selected_filter = QFileDialog.getSaveFileName(
                self,
                "RC MetaStudio -- save plot as",
                default_path,
            )
            if file_path != "":
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
    normalized["image_var_names"] = dict(normalized.get("image_var_names") or {})
    normalized["image_params_paths"] = dict(normalized.get("image_params_paths") or {})
    normalized.setdefault("image_order", None)

    if not normalized["texts"] and not normalized["images"]:
        normalized["texts"]["No Results"] = NO_RESULTS_MESSAGE

    return normalized


def _empty_results():
    return {
        "texts": {"No Results": NO_RESULTS_MESSAGE},
        "images": {},
        "image_var_names": {},
        "image_params_paths": {},
        "image_order": None,
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

    app = QApplication(sys.argv)
    resultswindow = ResultsWindow(test_results)
    resultswindow.show()
    sys.exit(app.exec())
