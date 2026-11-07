"""
kleinos/palette.py

Central color module for KleinOS.
Loaded at import time — all panes import names from here.
Palette is set by kleinos_config.json and takes effect after restart.
"""

from __future__ import annotations

import json
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "data" / "kleinos_config.json"

_PALETTES: dict[str, dict[str, str]] = {
    "green": dict(
        BG="#010a01",        BG2="#050a05",
        HEAD="#081208",      CHROME="#003311",    BORDER="#005522",
        HOV="#0d2010",       ACT="#0a3a0a",
        BTN_BG="#0a2010",    BTN_ACT="#0d3a1a",   BTN_SEL="#0a4020",
        BTN_DEL="#2a0808",   BTN_DEL_A="#4a1010",
        FG="#3a7a3a",        FG_ON="#00dd33",
        FG_HI="#88ff88",     FG_PROMPT="#00ff44",
        FG_DIM="#1a4a1a",    FG_HUD="#00aa22",    WARN="#cc6600",
        SEP="#0a180a",
        GM_DARK="#004d18",   GM_MID="#00dd33",    GM_BRIGHT="#88ff88",
    ),
    "amber": dict(
        BG="#0a0600",        BG2="#100800",
        HEAD="#180d00",      CHROME="#2a1500",    BORDER="#3d2000",
        HOV="#201400",       ACT="#301c00",
        BTN_BG="#1a0e00",    BTN_ACT="#2a1800",   BTN_SEL="#3a2200",
        BTN_DEL="#2a0808",   BTN_DEL_A="#4a1010",
        FG="#9a6818",        FG_ON="#ffaa00",
        FG_HI="#ffd060",     FG_PROMPT="#ffcc00",
        FG_DIM="#5a3e10",    FG_HUD="#cc8800",    WARN="#ff4400",
        SEP="#180e00",
        GM_DARK="#553300",   GM_MID="#ffaa00",    GM_BRIGHT="#ffd060",
    ),
    "white": dict(
        BG="#020202",        BG2="#050505",
        HEAD="#0a0a0a",      CHROME="#111111",    BORDER="#222222",
        HOV="#1a1a1a",       ACT="#2a2a2a",
        BTN_BG="#0e0e0e",    BTN_ACT="#1e1e1e",   BTN_SEL="#303030",
        BTN_DEL="#2a0808",   BTN_DEL_A="#4a1010",
        FG="#606060",        FG_ON="#d0d0d0",
        FG_HI="#f0f0f0",     FG_PROMPT="#f8f8f8",
        FG_DIM="#303030",    FG_HUD="#a0a0a0",    WARN="#cc8800",
        SEP="#0f0f0f",
        GM_DARK="#404040",   GM_MID="#d0d0d0",    GM_BRIGHT="#f0f0f0",
    ),
    "blue": dict(
        BG="#000508",        BG2="#000810",
        HEAD="#000e1a",      CHROME="#001122",    BORDER="#002244",
        HOV="#001022",       ACT="#001a33",
        BTN_BG="#000e1c",    BTN_ACT="#001628",   BTN_SEL="#002040",
        BTN_DEL="#2a0808",   BTN_DEL_A="#4a1010",
        FG="#3c5e9a",        FG_ON="#66aaff",
        FG_HI="#aaccff",     FG_PROMPT="#88ccff",
        FG_DIM="#2a3c60",    FG_HUD="#4488cc",    WARN="#cc8800",
        SEP="#000e1a",
        GM_DARK="#003366",   GM_MID="#66aaff",    GM_BRIGHT="#aaccff",
    ),
    "red": dict(
        BG="#080000",        BG2="#0a0000",
        HEAD="#120000",      CHROME="#200000",    BORDER="#330000",
        HOV="#1a0000",       ACT="#2a0000",
        BTN_BG="#140000",    BTN_ACT="#220000",   BTN_SEL="#330808",
        BTN_DEL="#2a0808",   BTN_DEL_A="#4a1010",
        FG="#b83030",        FG_ON="#ff4444",
        FG_HI="#ff9999",     FG_PROMPT="#ff6666",
        FG_DIM="#681818",    FG_HUD="#cc2222",    WARN="#ff8800",
        SEP="#0f0000",
        GM_DARK="#550000",   GM_MID="#ff4444",    GM_BRIGHT="#ff9999",
    ),
}


def _load_name() -> str:
    try:
        return json.loads(_PATH.read_text(encoding="utf-8")).get("palette", "green")
    except Exception:
        return "green"


_a = _PALETTES.get(_load_name(), _PALETTES["green"])

# ── Active palette tokens (module-level constants) ───────────────────

BG        = _a["BG"]         # darkest content / canvas background
BG2       = _a["BG2"]        # sidebar / status-bar background
HEAD      = _a["HEAD"]       # sidebar category-header background
CHROME    = _a["CHROME"]     # content-pane chrome bars
BORDER    = _a["BORDER"]     # border lines / very-dim system text

HOV       = _a["HOV"]        # hover state
ACT       = _a["ACT"]        # active / selected state

BTN_BG    = _a["BTN_BG"]     # button normal background
BTN_ACT   = _a["BTN_ACT"]    # button active / pressed
BTN_SEL   = _a["BTN_SEL"]    # keyboard-selected button background
BTN_DEL   = _a["BTN_DEL"]    # destructive button background
BTN_DEL_A = _a["BTN_DEL_A"]  # destructive button active

FG        = _a["FG"]         # normal / mid-dim text
FG_ON     = _a["FG_ON"]      # main phosphor text (bright)
FG_HI     = _a["FG_HI"]      # desaturated bright highlight
FG_PROMPT = _a["FG_PROMPT"]  # pure bright (terminal prompt / input)
FG_DIM    = _a["FG_DIM"]     # very dim text
FG_HUD    = _a["FG_HUD"]     # HUD / score text
WARN      = _a["WARN"]       # warning / accent (orange across all palettes)

SEP       = _a["SEP"]        # sidebar separator lines

GM_DARK   = _a["GM_DARK"]    # game dark phosphor
GM_MID    = _a["GM_MID"]     # game mid phosphor  (== FG_ON)
GM_BRIGHT = _a["GM_BRIGHT"]  # game bright phosphor (== FG_HI)


def all_palettes() -> dict[str, dict[str, str]]:
    """Return a copy of the full palettes table (read-only use)."""
    return dict(_PALETTES)
