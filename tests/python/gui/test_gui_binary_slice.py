import os
import sys

from rc_metastudio import automation

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


REPO_ROOT = os.getcwd()


def test_main_window_opens_binary_continuous_and_diagnostic_projects():

    for name, family, first_study in [
        ("amino.rcms", "binary", "Gonzalez"),
        ("continuous.rcms", "continuous", "Carroll"),
        ("lymph.rcms", "diagnostic", "Kinderman"),
    ]:
        app, window = automation.start_automation()
        try:
            assert (
                window.open(os.path.abspath(os.path.join("sample_projects", name)))
                is True
            )

            model = window.tableView.model()
            assert model.get_current_outcome_type() == family
            assert model.rowCount() > 0
            assert _cell_text(model, 0, model.NAME) == first_study
            assert window.tableView.model() is window.model
        finally:
            window.close()
            app.processEvents()
            os.chdir(REPO_ROOT)


def test_main_window_standard_binary_action_opens_setup_dialog(monkeypatch):

    app, window = automation.start_automation()
    main_window = sys.modules["rc_metastudio.main_window"]
    calls = []

    class SpecsDialog(object):
        def __init__(self, model, meta_f_str=None, parent=None, conf_level=None):
            calls.append(
                (meta_f_str, parent, conf_level, model.get_current_outcome_type())
            )

        def show(self):
            pass

    monkeypatch.setattr(
        main_window.analysis_setup_dialog, "AnalysisSetupDialog", SpecsDialog
    )

    try:
        assert window.open(os.path.abspath("sample_projects/amino.rcms")) is True
        window.action_go.trigger()

        assert calls == [(None, window, window.model.get_global_conf_level(), "binary")]
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_main_window_preserves_standard_binary_rows():

    app, window = automation.start_automation()
    try:
        assert window.open(os.path.abspath("sample_projects/amino.rcms")) is True
        model = window.tableView.model()

        assert window.model.dataset.title == "aminoglycosides"
        assert _cell_text(model, 0, model.NAME) == "Gonzalez"
        assert _cell_text(model, 0, model.YEAR) == "1993"
        assert [_cell_text(model, 0, column) for column in range(3, 7)] in (
            ["6.0", "27.0", "9.0", "27.0"],
            ["9.0", "27.0", "6.0", "27.0"],
        )
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_project_file_dialogs_use_rc_metastudio_project_filter(monkeypatch):

    app, window = automation.start_automation()
    calls = []

    def choose_open_project(**kwargs):
        calls.append(("open", kwargs))
        return ("", "")

    def choose_save_project(**kwargs):
        calls.append(("save", kwargs))
        return ("", "")

    try:
        main_window = sys.modules["rc_metastudio.main_window"]
        monkeypatch.setattr(
            main_window.QFileDialog, "getOpenFileName", choose_open_project
        )
        monkeypatch.setattr(
            main_window.QFileDialog, "getSaveFileName", choose_save_project
        )

        assert window.open() is False
        assert window.save_as() is None

        assert [kind for kind, _ in calls] == ["open", "save"]
        retired_extension = "." + "oma"
        for _, kwargs in calls:
            assert kwargs["filter"] == "RC MetaStudio Project (*.rcms)"
            assert retired_extension not in kwargs["filter"].lower()
            assert "open meta" not in kwargs["filter"].lower()
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def _cell_text(model, row, column):
    value = model.data(model.index(row, column))
    return str(value.value() if hasattr(value, "value") else value)


def _dataset_summary(dataset):
    return {
        "title": dataset.title,
        "studies": [(str(study.name), str(study.year)) for study in dataset.studies],
        "outcomes": sorted(
            str(name) for name in dataset.outcome_names_to_follow_ups.keys()
        ),
    }
