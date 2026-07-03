#############################################
#                                           #
#  Byron C. Wallace     George E. Dietz     #
#  Brown University     CEBM@Brown          #
#  OpenMeta[analyst]                        #
#                                           #
#                                           #
#  This is the component responsible        #
#  for rendering MA results.                #
#                                           #
#############################################

import random
from PyQt5.QtCore import QByteArray, QPoint, QRectF, Qt
from PyQt5.QtGui import QFont, QFontMetricsF, QImage, QPixmap, QTextOption, QTransform
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
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
import edit_forest_plot_form
import app_error_handler
import meta_py_r
import qt_layout
import result_sections
# import shutil

PageSize = (612, 792)
padding = 25
horizontal_padding = 75
SCALE_P = 0.5  # percent images are to be scaled

# these are special forest plots, in that multiple parameters objects are
# require to re-generate them (and we invoke a different method!)
SIDE_BY_SIDE_FOREST_PLOTS = (
    "NLR and PLR Forest Plot",
    "Sensitivity and Specificity",
    "Cumulative Forest Plot",
)
NO_RESULTS_MESSAGE = "No results could be computed for this analysis."
ROW_HEIGHT = 15  # by trial-and-error; seems to work very well
SECTION_SPACING = ROW_HEIGHT


class ResultsWindow(QMainWindow, ui_results_window.Ui_ResultsWindow):
    def __init__(self, results, parent=None):

        super(ResultsWindow, self).__init__(parent)
        self.setupUi(self)
        qt_layout.fit_text_to_contents(self)
        self.copied_item = QByteArray()
        self.paste_offset = 5
        self.add_offset = 5
        self.buffer_size = 2
        self.prev_point = QPoint()
        self.borders = []

        self.nav_tree.itemClicked.connect(
            app_error_handler.safe_slot(self.item_clicked, parent=self)
        )
        self.results_nav_splitter.splitterMoved.connect(
            app_error_handler.safe_slot(
                lambda _pos, _index: self._update_wrapped_text_widths(), parent=self
            )
        )

        self.psuedo_console.blockSignals(False)
        if hasattr(self.psuedo_console, "returnPressed"):
            self.psuedo_console.returnPressed.connect(
                app_error_handler.safe_slot(self.process_console_input, parent=self)
            )
        if hasattr(self.psuedo_console, "upArrowPressed"):
            self.psuedo_console.upArrowPressed.connect(
                app_error_handler.safe_slot(self.f, parent=self)
            )
        if hasattr(self.psuedo_console, "downArrowPressed"):
            self.psuedo_console.downArrowPressed.connect(
                app_error_handler.safe_slot(self.f, parent=self)
            )

        self.nav_tree.setHeaderLabels(["Results"])
        self.nav_tree.setItemsExpandable(True)
        self.x_coord = 5
        self.y_coord = 5

        # set (default) splitter sizes
        self.splitter.setSizes([400, 100])
        self.results_nav_splitter.setSizes([200, 500])

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

        self.image_var_names = results["image_var_names"]
        self.set_psuedo_console_text()
        self.items_to_coords = {}
        self._wrapped_text_items = []
        self.texts = results["texts"]
        self.texts, self.references_text = result_sections.pop_references_section(
            self.texts
        )

        # Render ordinary text, plots, then References as the final section.
        self.add_text()

        self.y_coord += ROW_HEIGHT / 2.0

        # additional padding for Windows..
        # again, heuristic. I don't know
        # why windows requires so much padding.
        if sys.platform.startswith("win"):
            self.y_coord += 2 * ROW_HEIGHT

        self.add_images()
        self.add_references()

        # reset the scene
        self.graphics_view.setScene(self.scene)
        self.graphics_view.ensureVisible(QRectF(0, 0, 0, 0))

    def f(self):
        print(self.current_line())

    def set_psuedo_console_text(self):
        text = [
            "\t\tOpenMeta(analyst)",
            "This is a pipe to the R console. The image names are as follows:",
        ]
        if self.image_var_names is not None:
            for image_var_name in list(self.image_var_names.values()):
                text.append(image_var_name)
        self.psuedo_console.setPlainText("\n".join(text))
        self.psuedo_console.append(">> ")

    def add_images(self):
        ordered_images = result_sections.order_image_sections(
            list(self.images.items()), explicit_order=self.image_order
        )

        for title, image in ordered_images:
            print("title: %s; image: %s" % (title, image))
            cur_y = max(0, self.y_coord)
            print("cur_y: %s" % cur_y)
            pixmap = self.generate_pixmap(image)
            if pixmap.isNull():
                print("Skipping image that Qt could not load: %s" % image)
                continue
            # first add the title
            qt_item = self.add_title(title)

            # if there is a parameters object associated with this object
            # (i.e., it is a forest plot of some variety), we pass it along
            # to the create_pixmap_item method to for the context_menu
            # construction
            params_path = None
            if self.params_paths is not None and title in self.params_paths:
                params_path = self.params_paths[title]

            img_shape, pos, pixmap_item = self.create_pixmap_item(
                pixmap, self.position(), title, image, params_path=params_path
            )

            self.items_to_coords[id(qt_item)] = pos

    def generate_pixmap(self, image):
        # now the image
        pixmap = QPixmap(image)
        if pixmap.isNull():
            return pixmap

        ###
        # we scale to address issue #23.
        # should probably pick a 'target' width/height, in case
        # others generate smaller images by default.
        scaled_width = int(SCALE_P * pixmap.width())
        scaled_height = int(SCALE_P * pixmap.height())

        if scaled_width > self.scene.width():
            self.scene.setSceneRect(
                0, 0, scaled_width + horizontal_padding, self.scene.height()
            )

        pixmap = pixmap.scaled(
            scaled_width, scaled_height, transformMode=Qt.SmoothTransformation
        )

        return pixmap

    def add_text(self):
        for title, text in result_sections.order_text_sections(list(self.texts.items())):
            try:
                print("title: %s; text: %s" % (title, text))
                cur_y = max(0, self.y_coord)
                print("cur_y: %s" % cur_y)
                # first add the title
                qt_item = self.add_title(title)

                # now the text
                text_item_rect, pos = self.create_text_item(str(text), self.position())
                self.items_to_coords[id(qt_item)] = pos
            except:
                pass

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
        txt_item = QGraphicsTextItem(text)
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

    def _text_wrap_width(self):
        viewport_width = self.graphics_view.viewport().width()
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

    def process_console_input(self):
        res = str(meta_py_r.evaluate_r_console(self.current_line()))

        # echo the result
        self.psuedo_console.append(res)
        self.psuedo_console.append(">> ")

    def current_line(self):
        last_line = self.psuedo_console.toPlainText().split("\n")[-1]
        return str(last_line.replace(">>", "")).strip()

    def _get_plot_type(self, title):
        # at present we use the *title* as the type --
        # this is currently _not_ set by the user, so it's
        # 'safe', but it's not exactly elegant. probably
        # we should return a type directly from R.
        # on other hand, this couples R + Python even
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
        item = QGraphicsPixmapItem(pixmap)
        item.setToolTip(
            "To save the image:\nright-click on the image and choose \"save image as\".\nSave as png will correctly render non-latin fonts but does not respect changes to plot made through 'edit_plot ...'"
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

        # for now we're inferring the plot type (e.g., 'forest'
        # from the title of the plot (see in-line comments, above)
        plot_type = self._get_plot_type(title)

        # attach event handler for mouse-clicks, i.e., to handle
        # user right-clicks
        item.contextMenuEvent = self._make_context_menu(
            params_path, title, image_path, item, plot_type=plot_type
        )

        return (item.boundingRect().size(), position, item)

    def _make_context_menu(
        self, params_path, title, png_path, qpixmap_item, plot_type="forest"
    ):
        plot_img = QImage(png_path)

        def _graphics_item_context_menu(event):
            def add_save_as_pdf_menu_action(menu):
                action = QAction("save pdf image as", self)
                action.triggered.connect(
                    app_error_handler.safe_slot(
                        lambda _checked=False: self.save_image_as(
                            params_path, title, plot_type=plot_type, format="pdf"
                        ),
                        parent=self,
                    )
                )
                menu.addAction(action)

            def add_save_as_png_menu_action(menu):
                action = QAction("save png image as", self)
                action.triggered.connect(
                    app_error_handler.safe_slot(
                        lambda _checked=False: self.save_image_as(
                            params_path,
                            title,
                            plot_type=plot_type,
                            unscaled_image=plot_img,
                            format="png",
                        ),
                        parent=self,
                    )
                )
                menu.addAction(action)

            def add_edit_plot_menu_action(menu):
                # only know how to edit *simple* (i.e., _not_ side-by-side, as
                # in sens and spec plotted on the same canvass) forest plots for now
                if plot_type == "forest" and not self._is_side_by_side_fp(title):
                    action = QAction("edit plot", self)
                    action.triggered.connect(
                        app_error_handler.safe_slot(
                            lambda _checked=False: self.edit_image(
                                params_path, title, png_path, qpixmap_item
                            ),
                            parent=self,
                        )
                    )
                    menu.addAction(action)

            context_menu = QMenu(self)
            if params_path:
                add_save_as_pdf_menu_action(context_menu)
                add_save_as_png_menu_action(context_menu)
                add_edit_plot_menu_action(context_menu)
            else:  # no params path given, just give them the png
                add_save_as_png_menu_action(context_menu)

            pos = event.screenPos()
            context_menu.popup(pos)
            event.accept()

        return _graphics_item_context_menu

    def _is_side_by_side_fp(self, title):
        return any(
            [side_by_side in title for side_by_side in SIDE_BY_SIDE_FOREST_PLOTS]
        )

    def save_image_as(
        self, params_path, title, plot_type="forest", unscaled_image=None, format=None
    ):

        if format not in ["pdf", "png"]:
            raise Exception("Invalid format, needs to be either pdf or png!")

        if not unscaled_image:
            # note that the params object will, by convention,
            # have the (generic) name 'plot.data' -- after this
            # call, this object will be in the namespace
            meta_py_r.load_in_R("%s.plotdata" % params_path)

            default_path = {
                "forest": "forest_plot.pdf",
                "regression": "regression.pdf",
            }[plot_type]

            # where to save the graphic?
            file_path, _selected_filter = QFileDialog.getSaveFileName(
                self,
                "OpenMeta[Analyst] -- save plot as",
                default_path,
            )

            # now we re-generate it, unless they canceled, of course
            if file_path != "":
                if plot_type == "forest":
                    if self._is_side_by_side_fp(title):
                        meta_py_r.generate_forest_plot(file_path, side_by_side=True)
                    else:
                        meta_py_r.generate_forest_plot(file_path)
                elif plot_type == "regression":
                    meta_py_r.generate_reg_plot(file_path)
                else:
                    print("sorry -- I don't know how to draw %s plots!" % plot_type)
        else:  # case where we just have the png and can't regenerate the pdf from plot data
            default_path = ".".join([title.replace(" ", "_"), "png"])
            file_path, _selected_filter = QFileDialog.getSaveFileName(
                self,
                "OpenMeta[Analyst] -- save plot as",
                default_path,
            )
            unscaled_image.save(file_path, "PNG")

    def edit_image(self, params_path, title, png_path, pixmap_item):
        plot_editor_window = edit_forest_plot_form.EditPlotWindow(
            params_path, png_path, pixmap_item, parent=self
        )
        if plot_editor_window is not None:
            plot_editor_window.show()
        else:
            # TODO show a warning
            print("sorry - can't edit")

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
    # make test results based on results from when meta-analysis run from amino sample data
    test_results = {}
    test_results["images"] = {"Forest Plot": "./r_tmp/forest.png"}
    test_results["texts"] = {
        "Weights": "studies             weights\nGonzalez       1993  7.3%\nPrins          1993  6.2%\nGiamarellou    1991  2.1%\nMaller         1993 10.7%\nSturm          1989  2.0%\nMarik          1991 12.2%\nMuijsken       1988  7.5%\nVigano         1992  1.8%\nHansen         1988  5.3%\nDe Vries       1990  6.1%\nMauracher      1989  2.2%\nNordstrom      1990  5.3%\nRozdzinski     1993 10.3%\nTer Braak      1990  8.7%\nTulkens        1988  1.2%\nVan der Auwera 1991  2.0%\nKlastersky     1977  6.0%\nVanhaeverbeek  1993  1.2%\nHollender      1989  1.8%\n",
        "Summary": "Binary Random-Effects Model\n\nMetric: Odds Ratio\n\n Model Results\n\n Estimate  Lower bound  Upper bound  p-Value\n\n 0.770           0.485        1.222    0.267\n\n\n Heterogeneity\n\n τ²     Q(df=18)  Het. p-Value  I²\n\n 0.378    33.360         0.015  46.000%\n\n\nCalculation scale: log - estimate: -0.262, lower: -0.724, upper: 0.200, std. error: 0.236\n\n",
    }
    test_results["image_var_names"] = {"forest plot": "forest_plot"}
    test_results["image_params_paths"] = {
        "Forest Plot": "r_tmp/1369769105.72079"
    }  # change this number as necessary
    test_results["image_order"] = None

    app = QApplication(sys.argv)
    resultswindow = ResultsWindow(test_results)
    resultswindow.show()
    sys.exit(app.exec())
