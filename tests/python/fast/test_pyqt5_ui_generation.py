import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FORMS = ROOT / "src/rc_metastudio/forms"


def test_ui_generator_reproduces_owned_raw_output_without_reformatting_peers(
    tmp_path,
):
    generator = runpy.run_path(str(ROOT / "scripts/regenerate-pyqt5-ui.py"))
    compile_ui = generator["compile_ui"]

    for source_name, target_name in (
        ("continuous_data_form.ui", "ui_continuous_data_form.py"),
        (
            "continuous_back_calc_result_form.ui",
            "ui_continuous_back_calc_result_form.py",
        ),
        ("conf_level_dialog.ui", "ui_conf_level_dialog.py"),
        ("diagnostic_data_form.ui", "ui_diagnostic_data_form.py"),
        ("diagnostic_metrics.ui", "ui_diagnostic_metrics.py"),
    ):
        generated = tmp_path / target_name
        compile_ui(FORMS / source_name, generated)
        assert generated.read_bytes() == (FORMS / target_name).read_bytes()

    formatted_peer = FORMS / "ui_change_cov_type.py"
    generated_peer = tmp_path / formatted_peer.name
    generated_peer.write_bytes(formatted_peer.read_bytes())
    compile_ui(FORMS / "change_cov_type_form.ui", generated_peer)
    assert generated_peer.read_bytes() == formatted_peer.read_bytes()
