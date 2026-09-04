from pathlib import Path

import pytest

from rc_metastudio import plot_service, r_bridge
from rc_metastudio.plot_service import PlotService, PlotServiceError


def test_load_params_returns_typed_copy(monkeypatch):
    service = PlotService()
    source = {"fp_style": "classic"}
    monkeypatch.setattr(
        "rc_metastudio.plot_service.r_bridge.load_vars_for_plot",
        lambda path, return_params_dict: source,
    )

    params = service.load_params("forest")

    assert params == source
    assert params is not source


def test_load_params_returns_none_when_artifact_is_missing(monkeypatch):
    monkeypatch.setattr(
        "rc_metastudio.plot_service.r_bridge.load_vars_for_plot",
        lambda path, return_params_dict: False,
    )

    assert PlotService().load_params("missing") is None


def test_load_params_rejects_invalid_r_result(monkeypatch):
    monkeypatch.setattr(
        "rc_metastudio.plot_service.r_bridge.load_vars_for_plot",
        lambda path, return_params_dict: True,
    )

    with pytest.raises(PlotServiceError, match="invalid plot parameters"):
        PlotService().load_params("forest")


def test_apply_forest_edits_persists_then_regenerates(monkeypatch):
    calls = []
    monkeypatch.setattr(
        r_bridge,
        "update_plot_params",
        lambda params, **kwargs: calls.append(("update", params, kwargs)),
    )
    monkeypatch.setattr(r_bridge, "regenerate_plot_data", lambda: calls.append(("data",)))
    monkeypatch.setattr(
        r_bridge, "generate_forest_plot", lambda path: calls.append(("draw", path))
    )
    monkeypatch.setattr(
        r_bridge,
        "write_out_plot_data",
        lambda path: calls.append(("write", path)),
    )

    PlotService().apply_edits(
        regenerator="forest",
        params_path="forest",
        updated_params={"fp_style": "classic"},
        output_path="edited.svg",
    )

    assert [call[0] for call in calls] == ["update", "data", "draw", "write"]
    assert calls[0][2] == {"write_them_out": True, "outpath": "forest.params"}


def test_apply_funnel_edits_rolls_back_persisted_params_on_failure(tmp_path, monkeypatch):
    params_path = tmp_path / "funnel"
    Path(f"{params_path}.data").write_text("data")
    Path(f"{params_path}.res").write_text("res")
    persisted = Path(f"{params_path}.params")
    persisted.write_text("original")

    def update(_params, *, outpath, **_kwargs):
        Path(outpath).write_text("updated")

    monkeypatch.setattr(r_bridge, "update_plot_params", update)

    def fail_to_regenerate(*_args, **_kwargs):
        raise RuntimeError("R failed")

    monkeypatch.setattr(
        r_bridge,
        "regenerate_small_study_effects_funnel",
        fail_to_regenerate,
    )

    with pytest.raises(RuntimeError, match="R failed"):
        PlotService().apply_edits(
            regenerator="funnel",
            params_path=str(params_path),
            updated_params={"funnel.outpath": str(tmp_path / "edited.png")},
            output_path=str(tmp_path / "edited.png"),
        )

    assert persisted.read_text() == "original"


def test_funnel_rollback_failure_keeps_original_render_error(tmp_path, monkeypatch):
    params_path = tmp_path / "funnel"
    Path(f"{params_path}.data").write_text("data")
    Path(f"{params_path}.res").write_text("res")
    persisted = Path(f"{params_path}.params")
    persisted.write_text("original")
    bridge = plot_service.r_bridge
    original_copyfile = plot_service.shutil.copyfile
    copy_count = 0

    def copyfile(source, target):
        nonlocal copy_count
        copy_count += 1
        if copy_count == 4:
            raise OSError("rollback failed")
        return original_copyfile(source, target)

    monkeypatch.setattr(
        "rc_metastudio.plot_service.shutil.copyfile", copyfile
    )
    monkeypatch.setattr(
        bridge,
        "update_plot_params",
        lambda _params, *, outpath, **_kwargs: Path(outpath).write_text("updated"),
    )

    def fail_to_regenerate(*_args, **_kwargs):
        raise RuntimeError("render failed")

    monkeypatch.setattr(
        bridge,
        "regenerate_small_study_effects_funnel",
        fail_to_regenerate,
    )

    with pytest.raises(RuntimeError, match="render failed") as raised:
        PlotService().apply_edits(
            regenerator="funnel",
            params_path=str(params_path),
            updated_params={"funnel.outpath": str(tmp_path / "edited.png")},
            output_path=str(tmp_path / "edited.png"),
        )

    assert raised.value.__notes__ == ["Plot parameter rollback failed: rollback failed"]


@pytest.mark.parametrize(
    ("regenerator", "load_path", "draw_name"),
    [
        ("forest", "params.plotdata", "generate_forest_plot"),
        ("regression", "params.plotdata", "generate_reg_plot"),
        ("sroc", "params.plotdata", "generate_sroc_plot"),
        ("funnel", "params", "generate_small_study_effects_funnel"),
    ],
)
def test_export_loads_the_matching_r_artifact(
    monkeypatch, regenerator, load_path, draw_name
):
    calls = []
    monkeypatch.setattr(r_bridge, "load_in_r", lambda path: calls.append(("load", path)))
    monkeypatch.setattr(
        r_bridge,
        "load_vars_for_plot",
        lambda path: calls.append(("load_vars", path)),
    )
    monkeypatch.setattr(
        r_bridge, draw_name, lambda path: calls.append(("draw", path))
    )

    PlotService().export(
        regenerator=regenerator,
        params_path="params",
        output_path="export.svg",
    )

    expected_load = (
        ("load_vars", "params")
        if regenerator == "funnel"
        else ("load", load_path)
    )
    assert calls == [expected_load, ("draw", "export.svg")]
