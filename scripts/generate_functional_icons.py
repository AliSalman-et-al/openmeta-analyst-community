"""Generate the packaged professional action and analysis SVG families."""

from pathlib import Path
from collections.abc import Mapping


ROOT = Path(__file__).resolve().parents[1]
ICON_ROOT = ROOT / "src" / "rc_metastudio" / "images" / "icons"


def svg(view_box: str, body: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {view_box}">\n{body.strip()}\n</svg>\n'
    )


ACTIONS = {
    "about-legal.svg": """
  <path d="M10 5h19l9 9v27a2 2 0 0 1-2 2H10a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" fill="#DDF2FC" stroke="#1769AA" stroke-width="2" stroke-linejoin="round"/>
  <path d="M29 5v9h9" fill="#8FD3F2" stroke="#1769AA" stroke-width="2" stroke-linejoin="round"/>
  <path d="M14 20h17M14 26h13" stroke="#527080" stroke-width="2" stroke-linecap="round"/>
  <path d="M33.5 33v7M33.5 29.5v.2" stroke="#1769AA" stroke-width="2.5" stroke-linecap="round"/>
""",
    "add-covariate.svg": """
  <rect x="7" y="6" width="30" height="36" rx="2.5" fill="#EAF4F8" stroke="#3F5663" stroke-width="2"/>
  <path d="M16 7v34M27 7v34M8 17h28M8 28h28" stroke="#94A8B3" stroke-width="1.5"/>
  <path d="M10 9h4v6h-4zM10 20h4v6h-4zM10 31h4v8h-4z" fill="#2B88D8"/>
  <path d="M36 29v12M30 35h12" stroke="#168A56" stroke-width="3" stroke-linecap="round"/>
""",
    "add.svg": """
  <circle cx="24" cy="24" r="18.5" fill="#168A56"/>
  <path d="M24 13.5v21M13.5 24h21" stroke="#fff" stroke-width="4" stroke-linecap="round"/>
""",
    "auto-fit-columns.svg": """
  <rect x="10" y="7" width="28" height="34" rx="2" fill="#EAF4F8" stroke="#526B78" stroke-width="2"/>
  <path d="M19 8v32M29 8v32M11 18h26M11 30h26" stroke="#9AAEB8" stroke-width="1.5"/>
  <path d="M4 24h11M4 24l4-4M4 24l4 4M44 24H33M44 24l-4-4M44 24l-4 4" fill="none" stroke="#2B88D8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
""",
    "calculator.svg": """
  <rect x="9" y="5" width="30" height="38" rx="3" fill="#E8F1F5" stroke="#405864" stroke-width="2"/>
  <rect x="14" y="10" width="20" height="8" rx="1" fill="#1769AA"/>
  <g fill="#647D89"><rect x="14" y="23" width="4" height="4" rx=".7"/><rect x="22" y="23" width="4" height="4" rx=".7"/><rect x="30" y="23" width="4" height="4" rx=".7"/><rect x="14" y="31" width="4" height="4" rx=".7"/><rect x="22" y="31" width="4" height="4" rx=".7"/></g>
  <rect x="30" y="31" width="4" height="4" rx=".7" fill="#2B88D8"/>
""",
    "confidence-level.svg": """
  <path d="M7 8v32M41 8v32M7 24h34" stroke="#526B78" stroke-width="2.25" stroke-linecap="round"/>
  <path d="M11 24h26" stroke="#2B88D8" stroke-width="3" stroke-linecap="round"/>
  <path d="m24 18 6 6-6 6-6-6 6-6Z" fill="#6F52B5" stroke="#fff" stroke-width="1"/>
""",
    "copy.svg": """
  <path d="M8 8h24v28H8z" fill="#CBEAF8" stroke="#527080" stroke-width="2" stroke-linejoin="round"/>
  <path d="M16 13h24v29H16z" fill="#F7FBFD" stroke="#1769AA" stroke-width="2" stroke-linejoin="round"/>
  <path d="M22 21h12M22 27h12M22 33h9" stroke="#6F8792" stroke-width="2" stroke-linecap="round"/>
""",
    "edit-dataset.svg": """
  <path d="M8 6h24l7 7v27a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2Z" fill="#E4F3FA" stroke="#1769AA" stroke-width="2" stroke-linejoin="round"/>
  <path d="M32 6v7h7M12 19h18M12 25h15M12 31h10" stroke="#6B8794" stroke-width="1.8" stroke-linecap="round"/>
  <path d="m25 39 2-6 10-10 5 5-10 10-7 1Z" fill="#E6B33C" stroke="#8A6512" stroke-width="1.5" stroke-linejoin="round"/>
  <path d="m36 24 5 5" stroke="#8A6512" stroke-width="1.5"/>
""",
    "import-csv.svg": """
  <path d="M8 5h22l8 8v28a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" fill="#E4F3FA" stroke="#1769AA" stroke-width="2" stroke-linejoin="round"/>
  <path d="M30 5v8h8M12 20h18M12 27h18M19 18v16M27 18v16" stroke="#6B8794" stroke-width="1.5"/>
  <path d="M36 24v14M31 33l5 5 5-5" fill="none" stroke="#168A56" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
""",
    "navigation-down.svg": """
  <path d="M6 10h36L24 43 6 10Z" fill="#2B88D8"/>
""",
    "navigation-left.svg": """
  <path d="M5 24 38 6v36L5 24Z" fill="#2B88D8"/>
""",
    "navigation-right.svg": """
  <path d="M43 24 10 42V6l33 18Z" fill="#2B88D8"/>
""",
    "navigation-up.svg": """
  <path d="M24 5 42 38H6L24 5Z" fill="#2B88D8"/>
""",
    "new-dataset.svg": """
  <path d="M8 5h22l8 8v28a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" fill="#E4F3FA" stroke="#1769AA" stroke-width="2" stroke-linejoin="round"/>
  <path d="M30 5v8h8M12 20h16M12 27h16M19 18v16" stroke="#6B8794" stroke-width="1.5"/>
  <path d="M36 27v13M29.5 33.5h13" stroke="#168A56" stroke-width="3" stroke-linecap="round"/>
""",
    "open.svg": """
  <path d="M6 12a2 2 0 0 1 2-2h13l4 5h15a2 2 0 0 1 2 2v22H6V12Z" fill="#D99A17" stroke="#9A6810" stroke-width="1.5" stroke-linejoin="round"/>
  <path d="M7 21h36l-5 19H5l-2-15a4 4 0 0 1 4-4Z" fill="#F4C64F" stroke="#A9700D" stroke-width="1.5" stroke-linejoin="round"/>
  <path d="M11 24h26" stroke="#FFF1B8" stroke-width="2" stroke-linecap="round"/>
""",
    "paste.svg": """
  <rect x="9" y="9" width="30" height="34" rx="3" fill="#E9F1F4" stroke="#526B78" stroke-width="2"/>
  <path d="M15 15h18v24H15z" fill="#fff" stroke="#B2C1C8" stroke-width="1.5"/>
  <path d="M17 6h14v8H17z" fill="#D5A62C" stroke="#8A6512" stroke-width="1.5" stroke-linejoin="round"/>
  <path d="M20 23h9M20 29h9M20 35h7" stroke="#2B88D8" stroke-width="1.8" stroke-linecap="round"/>
""",
    "quit.svg": """
  <path d="M24 6v18" stroke="#C43D45" stroke-width="4" stroke-linecap="round"/>
  <path d="M15 11a16 16 0 1 0 18 0" fill="none" stroke="#526B78" stroke-width="4" stroke-linecap="round"/>
""",
    "redo.svg": """
  <path d="M10 35c1-12 7-18 18-18h9M30 10l8 7-8 7" fill="none" stroke="#2B88D8" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
""",
    "remove.svg": """
  <circle cx="24" cy="24" r="18.5" fill="#C43D45"/>
  <path d="M13.5 24h21" stroke="#fff" stroke-width="4" stroke-linecap="round"/>
""",
    "save-as.svg": """
  <path d="M7 5h27l7 7v29a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" fill="#2B78B8" stroke="#174F7A" stroke-width="1.5" stroke-linejoin="round"/>
  <path d="M12 6h18v12H12z" fill="#BFE8F8"/><path d="M12 26h22v17H12z" fill="#F4F9FB"/>
  <path d="m25 40 2-6 10-10 5 5-10 10-7 1Z" fill="#E6B33C" stroke="#8A6512" stroke-width="1.5" stroke-linejoin="round"/>
""",
    "save.svg": """
  <path d="M7 5h27l7 7v29a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" fill="#2B78B8" stroke="#174F7A" stroke-width="1.5" stroke-linejoin="round"/>
  <path d="M12 6h18v12H12z" fill="#BFE8F8"/><path d="M25 8h3v8h-3z" fill="#1769AA"/>
  <path d="M12 26h22v17H12z" fill="#F4F9FB"/><path d="M17 32h12M17 37h10" stroke="#6B8794" stroke-width="1.8" stroke-linecap="round"/>
""",
    "undo.svg": """
  <path d="M38 35c-1-12-7-18-18-18h-9M18 10l-8 7 8 7" fill="none" stroke="#2B88D8" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
""",
}


STANDARD_ANALYSES = {
    "meta-analysis.svg": """
  <path d="M24 5v38" stroke="#596F7B" stroke-width="1.6"/>
  <g stroke="#2B88D8" stroke-width="1.8" stroke-linecap="round" fill="#1769AA">
    <path d="M6 10h28"/><rect x="17.5" y="7.5" width="5" height="5" rx=".6" stroke="none"/>
    <path d="M11 19h30"/><rect x="27.5" y="16.5" width="5" height="5" rx=".6" stroke="none"/>
    <path d="M5 28h31"/><rect x="19.5" y="25.5" width="5" height="5" rx=".6" stroke="none"/>
  </g>
  <path d="m24 35 6 4-6 4-6-4 6-4Z" fill="#1769AA"/>
""",
    "cumulative-analysis.svg": """
  <path d="M22 5v38" stroke="#596F7B" stroke-width="1.6"/>
  <g stroke="#2B88D8" stroke-width="1.8" stroke-linecap="round" fill="#1769AA">
    <path d="M5 10h27"/><rect x="15.5" y="7.5" width="5" height="5" rx=".6" stroke="none"/>
    <path d="M9 20h29"/><rect x="24.5" y="17.5" width="5" height="5" rx=".6" stroke="none"/>
    <path d="M5 30h29"/><rect x="18.5" y="27.5" width="5" height="5" rx=".6" stroke="none"/>
  </g>
  <path d="M36.5 27.5v13M30 34h13" stroke="#168A56" stroke-width="2.8" stroke-linecap="round"/>
""",
    "leave-one-out-analysis.svg": """
  <path d="M22 5v38" stroke="#596F7B" stroke-width="1.6"/>
  <g stroke="#2B88D8" stroke-width="1.8" stroke-linecap="round" fill="#1769AA">
    <path d="M5 10h27"/><rect x="15.5" y="7.5" width="5" height="5" rx=".6" stroke="none"/>
    <path d="M9 20h29"/><rect x="24.5" y="17.5" width="5" height="5" rx=".6" stroke="none"/>
    <path d="M5 30h29"/><rect x="18.5" y="27.5" width="5" height="5" rx=".6" stroke="none"/>
  </g>
  <path d="M30 34h13" stroke="#C43D45" stroke-width="2.8" stroke-linecap="round"/>
""",
    "subgroup-analysis.svg": """
  <path d="M25 5v38" stroke="#596F7B" stroke-width="1.6"/>
  <g stroke="#2B88D8" stroke-width="1.8" stroke-linecap="round" fill="#1769AA">
    <path d="M10 10h27"/><rect x="18.5" y="7.5" width="5" height="5" rx=".6" stroke="none"/>
    <path d="M13 19h28"/><rect x="28.5" y="16.5" width="5" height="5" rx=".6" stroke="none"/>
    <path d="M9 30h29"/><rect x="19.5" y="27.5" width="5" height="5" rx=".6" stroke="none"/>
    <path d="M14 39h27"/><rect x="29.5" y="36.5" width="5" height="5" rx=".6" stroke="none"/>
  </g>
  <path d="M8 6H4v17h4M8 26H4v17h4" fill="none" stroke="#6F52B5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
""",
    "meta-regression.svg": """
  <path d="M7 40h35M8 40V7" fill="none" stroke="#596F7B" stroke-width="1.6" stroke-linecap="round"/>
  <g fill="#1769AA"><rect x="11" y="31" width="5" height="5" rx=".8"/><rect x="18" y="25" width="5" height="5" rx=".8"/><rect x="27" y="20" width="5" height="5" rx=".8"/><rect x="34" y="11" width="5" height="5" rx=".8"/></g>
  <path d="M10 36 40 9" stroke="#6F52B5" stroke-width="2.5" stroke-linecap="round"/>
""",
}


COMPACT_ANALYSES = {
    "meta-analysis.svg": """
  <path d="M10 2v16" stroke="#596F7B" stroke-width="1"/>
  <g stroke="#2B88D8" stroke-width="1.15" stroke-linecap="round" fill="#1769AA"><path d="M2 5h12"/><rect x="6.8" y="3.8" width="2.4" height="2.4" rx=".3" stroke="none"/><path d="M3.5 10h13"/><rect x="10.7" y="8.8" width="2.4" height="2.4" rx=".3" stroke="none"/></g>
  <path d="m10 13.5 2.5 2-2.5 2-2.5-2 2.5-2Z" fill="#1769AA"/>
""",
    "cumulative-analysis.svg": """
  <path d="M9 2v16" stroke="#596F7B" stroke-width="1"/>
  <g stroke="#2B88D8" stroke-width="1.15" stroke-linecap="round" fill="#1769AA"><path d="M2 5h11"/><rect x="6.2" y="3.8" width="2.4" height="2.4" rx=".3" stroke="none"/><path d="M3.5 10h12"/><rect x="9.7" y="8.8" width="2.4" height="2.4" rx=".3" stroke="none"/><path d="M2 15h11.5"/><rect x="7.2" y="13.8" width="2.4" height="2.4" rx=".3" stroke="none"/></g>
  <path d="M15 13v4M13 15h4" stroke="#168A56" stroke-width="1.8" stroke-linecap="round"/>
""",
    "leave-one-out-analysis.svg": """
  <path d="M9 2v16" stroke="#596F7B" stroke-width="1"/>
  <g stroke="#2B88D8" stroke-width="1.15" stroke-linecap="round" fill="#1769AA"><path d="M2 5h11"/><rect x="6.2" y="3.8" width="2.4" height="2.4" rx=".3" stroke="none"/><path d="M3.5 10h12"/><rect x="9.7" y="8.8" width="2.4" height="2.4" rx=".3" stroke="none"/><path d="M2 15h11.5"/><rect x="7.2" y="13.8" width="2.4" height="2.4" rx=".3" stroke="none"/></g>
  <path d="M13 15h4" stroke="#C43D45" stroke-width="1.8" stroke-linecap="round"/>
""",
    "subgroup-analysis.svg": """
  <path d="M11 2v16" stroke="#596F7B" stroke-width="1"/>
  <g stroke="#2B88D8" stroke-width="1.15" stroke-linecap="round" fill="#1769AA"><path d="M5 5h11"/><rect x="8" y="3.8" width="2.4" height="2.4" rx=".3" stroke="none"/><path d="M5.5 10h12"/><rect x="12" y="8.8" width="2.4" height="2.4" rx=".3" stroke="none"/><path d="M5 15h12"/><rect x="9" y="13.8" width="2.4" height="2.4" rx=".3" stroke="none"/></g>
  <path d="M4.5 3h-2v8h2M4.5 12h-2v5.5h2" fill="none" stroke="#6F52B5" stroke-width="1.2" stroke-linecap="round"/>
""",
    "meta-regression.svg": """
  <path d="M2 16h14M2 16V2" fill="none" stroke="#596F7B" stroke-width="1" stroke-linecap="round"/>
  <g fill="#1769AA"><rect x="4" y="11" width="2.5" height="2.5" rx=".35"/><rect x="7.5" y="8" width="2.5" height="2.5" rx=".35"/><rect x="12" y="4" width="2.5" height="2.5" rx=".35"/></g>
  <path d="M3.5 14.5 15 3" stroke="#6F52B5" stroke-width="1.5" stroke-linecap="round"/>
""",
}


TABLE = {
    "calculator.svg": """
  <rect x="3" y="2" width="12" height="14" rx="1.5" fill="none" stroke="#667984" stroke-width="1.25"/>
  <rect x="5" y="4" width="8" height="2.7" rx=".4" fill="#667984"/>
  <g fill="#82939C"><rect x="5" y="9" width="2" height="2" rx=".3"/><rect x="8" y="9" width="2" height="2" rx=".3"/><rect x="11" y="9" width="2" height="2" rx=".3"/><rect x="5" y="12" width="2" height="2" rx=".3"/><rect x="8" y="12" width="2" height="2" rx=".3"/><rect x="11" y="12" width="2" height="2" rx=".3"/></g>
""",
}


def write_family(directory: Path, view_box: str, icons: Mapping[str, str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, body in icons.items():
        (directory / name).write_text(
            svg(view_box, body), encoding="utf-8", newline="\n"
        )


def main() -> None:
    write_family(ICON_ROOT / "actions", "48 48", ACTIONS)
    write_family(ICON_ROOT / "analyses", "48 48", STANDARD_ANALYSES)
    write_family(ICON_ROOT / "analyses" / "compact", "20 20", COMPACT_ANALYSES)
    write_family(ICON_ROOT / "table", "18 18", TABLE)


if __name__ == "__main__":
    main()
