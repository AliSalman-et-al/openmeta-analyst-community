from PyQt5.QtWidgets import QDialog

import forms.ui_diagnostic_metrics
import ma_specs

class Diag_Metrics(QDialog, forms.ui_diagnostic_metrics.Ui_diag_metric):

    SELECTABLE_METRICS = ["sens", "spec", "dor", "lr"]

    def __init__(self, model, parent=None, meta_f_str=None, external_params=None):
        super(Diag_Metrics, self).__init__(parent)
        self.setupUi(self)
        self.model = model
        self.parent = parent
        self.external_params = external_params
        self.meta_f_str = meta_f_str
        self.btn_ok.pressed.connect(self.ok)

    def ok(self):
        # Route the Method & Parameters dialog through the parent's
        # backend-error-handling builder (the same path the binary/continuous
        # case uses). This ensures a backend failure surfaces the "Analysis
        # backend unavailable" dialog instead of propagating out of this Qt
        # slot and being silently swallowed by the event loop. See issue #53.
        builder = getattr(self.parent, "_build_analysis_specs_dialog", None)
        if builder is not None:
            form = builder(meta_f_str=self.meta_f_str,
                           external_params=self.external_params,
                           diag_metrics=self.get_selected_metrics(),
                           conf_level=self.model.get_global_conf_level())
        else:
            form = ma_specs.MA_Specs(self.model, parent=self.parent,
                                     meta_f_str=self.meta_f_str,
                                     external_params=self.external_params,
                                     diag_metrics=self.get_selected_metrics(),
                                     conf_level=self.model.get_global_conf_level())
        if form is None:
            return
        form.show()
        self.hide()

    def get_selected_metrics(self):
        selected_metrics = []
        # just loop through all the check
        # boxes on the form and see if they're checked. 

        for metric in self.SELECTABLE_METRICS:
            if eval("self.chk_box_%s.isChecked()" % metric):
                print(metric)
                selected_metrics.append(metric)

  
        return selected_metrics


