from PyQt6.QtCore import QEvent, QObject, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QPixmap, QShowEvent
from PyQt6.QtWidgets import QDialog, QGraphicsScene, QWidget

import adaptive_window
import app_error_handler
import ui_network_view
from rc_metastudio import meta_py_r
import settings


class ViewDialog(QDialog, ui_network_view.Ui_network_view_dialog):
    viewportRefitApplied = pyqtSignal()

    def __init__(self, model, parent=None):
        super(ViewDialog, self).__init__(parent)
        self.setupUi(self)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        adaptive_window.register_adaptive_window(
            self, adaptive_window.WindowRole.NETWORK_VIEW
        )
        settings.restore_network_view_placement(self)

        self.model = model
        self.dataset = model.dataset
        self.cur_outcome = model.current_outcome
        self.cur_follow_up = model.get_current_follow_up_name()
        self._viewport_fit_pending = False
        self._network_source_pixmap = QPixmap()
        self._network_pixmap_item = None

        self.scene = QGraphicsScene(self)
        self.network_viewer.setScene(self.scene)
        self._viewport().installEventFilter(self)
        self.populate_cbo_boxes()
        self.setup_signals()
        self.graph_network(self.cur_outcome, self.cur_follow_up)

    def setup_signals(self):
        self.outcome_cbo_box.currentTextChanged.connect(
            app_error_handler.safe_slot(self.outcome_changed, parent=self)
        )
        self.follow_up_cbo_box.currentTextChanged.connect(
            app_error_handler.safe_slot(self.follow_up_changed, parent=self)
        )

    def outcome_changed(self, new_outcome):
        self.cur_outcome = str(new_outcome)
        self.outcome_cbo_box.setToolTip(self.cur_outcome)
        self.graph_network(self.cur_outcome, self.cur_follow_up)

    def follow_up_changed(self, new_follow_up):
        self.cur_follow_up = str(new_follow_up)
        self.follow_up_cbo_box.setToolTip(self.cur_follow_up)
        self.graph_network(self.cur_outcome, self.cur_follow_up)

    def populate_cbo_boxes(self):
        self.outcome_cbo_box.addItems(self.dataset.get_outcome_names())
        self.follow_up_cbo_box.addItems(self.dataset.get_follow_up_names())

        self.outcome_cbo_box.setCurrentIndex(
            self.outcome_cbo_box.findText(self.cur_outcome)
        )
        self.follow_up_cbo_box.setCurrentIndex(
            self.follow_up_cbo_box.findText(self.cur_follow_up)
        )
        self._expose_full_selector_values(self.outcome_cbo_box)
        self._expose_full_selector_values(self.follow_up_cbo_box)

    @staticmethod
    def _expose_full_selector_values(combo_box):
        """Expose Required Content even when the selected value cannot fit."""
        for index in range(combo_box.count()):
            combo_box.setItemData(
                index,
                combo_box.itemText(index),
                Qt.ItemDataRole.ToolTipRole,
            )
        combo_box.setToolTip(combo_box.currentText())

    def graph_network(self, outcome, follow_up):
        """Regenerate the graph for changed content, never for viewport sizing."""
        data_type = self.model.get_outcome_type(outcome, get_str=False)
        img_path = meta_py_r.ma_dataset_to_simple_network(
            table_model=self.model,
            data_type=data_type,
            outcome=outcome,
            follow_up=follow_up,
        )
        self.set_network_pixmap(QPixmap(img_path))

    def set_network_pixmap(self, pixmap):
        """Replace the intrinsic graph artifact while retaining its DPR."""
        self.scene.clear()
        self._network_source_pixmap = QPixmap(pixmap)
        self._network_pixmap_item = None
        if not self._network_source_pixmap.isNull():
            item = self.scene.addPixmap(self._network_source_pixmap)
            if item is None:
                raise RuntimeError("Qt could not create the Network View pixmap item")
            item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
            self._network_pixmap_item = item
            # layout-audit: allow=intrinsic-ratio; reason=scene follows its intrinsic-ratio visual artifact
            self.scene.setSceneRect(item.boundingRect())
        self.schedule_viewport_refit()

    def schedule_viewport_refit(self):
        """Coalesce local graph fitting to one event-loop turn."""
        if self._viewport_fit_pending:
            return
        self._viewport_fit_pending = True
        QTimer.singleShot(0, self._run_viewport_refit)

    def _run_viewport_refit(self):
        if not self._viewport_fit_pending:
            return
        self._viewport_fit_pending = False
        self._fit_network_to_viewport()

    def _fit_network_to_viewport(self):
        item = self._network_pixmap_item
        viewport = self._viewport()
        if (
            item is None
            or item.boundingRect().isEmpty()
            or viewport.width() <= 1
            or viewport.height() <= 1
        ):
            return
        self.network_viewer.resetTransform()
        # layout-audit: allow=intrinsic-ratio; reason=scene follows its intrinsic-ratio visual artifact
        self.network_viewer.fitInView(item, Qt.AspectRatioMode.KeepAspectRatio)
        self.viewportRefitApplied.emit()

    def eventFilter(  # ty: ignore[invalid-method-override] -- PyQt6 generated-form multiple inheritance
        self, watched: QObject | None, event: QEvent | None
    ) -> bool:
        if (
            event is not None
            and watched is self._viewport()
            and event.type()
            in (
                QEvent.Type.Resize,
                QEvent.Type.Show,
            )
        ):
            self.schedule_viewport_refit()
        return super(ViewDialog, self).eventFilter(watched, event)

    def showEvent(  # ty: ignore[invalid-method-override] -- PyQt6 generated-form multiple inheritance
        self, event: QShowEvent | None
    ) -> None:
        super(ViewDialog, self).showEvent(event)
        self.schedule_viewport_refit()

    def closeEvent(  # ty: ignore[invalid-method-override] -- PyQt6 generated-form multiple inheritance
        self, event: QCloseEvent | None
    ) -> None:
        settings.save_network_view_placement(self)
        self.scene.clear()
        self._network_pixmap_item = None
        self._network_source_pixmap = QPixmap()
        super(ViewDialog, self).closeEvent(event)

    def _viewport(self) -> QWidget:
        viewport = self.network_viewer.viewport()
        if viewport is None:
            raise RuntimeError("Network graphics view has no viewport")
        return viewport
