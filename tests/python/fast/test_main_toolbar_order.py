from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[3]
MAIN_WINDOW_UI = ROOT / "src" / "rc_metastudio" / "forms" / "main_window.ui"


def _action_names(element: ElementTree.Element) -> list[str]:
    return [action.attrib["name"] for action in element.findall("addaction")]


def test_toolbar_analysis_actions_follow_analysis_menu_order():
    root = ElementTree.parse(MAIN_WINDOW_UI).getroot()
    analysis_menu = root.find(".//widget[@name='menuAnalysis']")
    toolbar = root.find(".//widget[@name='toolBar']")
    assert analysis_menu is not None
    assert toolbar is not None

    analysis_actions = [
        "action_go",
        "action_cum_ma",
        "action_loo_ma",
        "action_subgroup_ma",
        "action_meta_regression",
        "action_change_conf_level",
    ]
    assert [
        action for action in _action_names(analysis_menu) if action in analysis_actions
    ] == analysis_actions

    toolbar_actions = _action_names(toolbar)
    first_analysis_action = toolbar_actions.index(analysis_actions[0])
    assert (
        toolbar_actions[
            first_analysis_action : first_analysis_action + len(analysis_actions)
        ]
        == analysis_actions
    )


def test_toolbar_omits_menu_and_shortcut_actions_after_analysis_group():
    root = ElementTree.parse(MAIN_WINDOW_UI).getroot()
    toolbar = root.find(".//widget[@name='toolBar']")
    assert toolbar is not None

    toolbar_actions = _action_names(toolbar)
    assert toolbar_actions[-1] == "action_change_conf_level"
    assert not {
        "action_undo",
        "action_redo",
        "action_copy",
        "action_paste",
        "action_quit",
    }.intersection(toolbar_actions)
