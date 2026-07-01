import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath("src"))


REPO_ROOT = os.getcwd()


def test_real_metaform_opens_binary_continuous_and_diagnostic_projects():
    import launch

    for name, family, first_study in [
        ("amino.oma", "binary", "Gonzalez"),
        ("continuous.oma", "continuous", "Carroll"),
        ("lymph.oma", "diagnostic", "Kinderman"),
    ]:
        app, window = launch.start_automation()
        try:
            assert (
                window.open(os.path.abspath(os.path.join("sample_data", name))) is True
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


def test_real_metaform_standard_binary_action_opens_specs_dialog(monkeypatch):
    import launch

    app, window = launch.start_automation()
    meta_form = sys.modules["meta_form"]
    calls = []

    class SpecsDialog(object):
        def __init__(self, model, meta_f_str=None, parent=None, conf_level=None):
            calls.append(
                (meta_f_str, parent, conf_level, model.get_current_outcome_type())
            )

        def show(self):
            pass

    monkeypatch.setattr(meta_form.ma_specs, "MA_Specs", SpecsDialog)

    try:
        assert window.open(os.path.abspath("sample_data/amino.oma")) is True
        window.action_go.trigger()

        assert calls == [(None, window, window.model.get_global_conf_level(), "binary")]
    finally:
        window.close()
        app.processEvents()
        os.chdir(REPO_ROOT)


def test_real_metaform_preserves_standard_binary_rows():
    import launch

    app, window = launch.start_automation()
    try:
        assert window.open(os.path.abspath("sample_data/amino.oma")) is True
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


def test_representative_projects_round_trip_without_byte_identical_expectations(
    tmp_path, monkeypatch
):
    import launch

    for name in ["amino.oma", "continuous.oma", "lymph.oma", "BCG.oma"]:
        app, window = launch.start_automation()
        saved_path = str(tmp_path / name)
        try:
            assert (
                window.open(os.path.abspath(os.path.join("sample_data", name))) is True
            )
            expected = _dataset_summary(window.model.dataset)
            meta_form = sys.modules["meta_form"]
            monkeypatch.setattr(
                meta_form.QFileDialog,
                "getSaveFileName",
                lambda **kwargs: (saved_path, ""),
            )

            window.save_as()
            reopened = meta_form._load_legacy_pickle(saved_path)

            assert _dataset_summary(reopened) == expected
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
