"""Global constants and precomputed lookup tables for the Jungle board game.

Coordinates are ``(col, row)`` with ``0 <= col < COLS`` and ``0 <= row < ROWS``.
Row 0 is the top edge (Black's home / den); row ``ROWS-1`` is the bottom edge
(Blue's home / den). Many hot paths index a *flat* square number instead of a
``(col, row)`` pair::

    sq = col * ROWS + row      # 0 .. NUM_SQUARES-1

The flat tables at the bottom of this module (TERRAIN_FLAT, NEIGHBORS,
TRAP_OWNER, ...) are all indexed by that square number.
"""

from __future__ import annotations

import os
import sys

# ---------------------------------------------------------------------------
# Asset path resolution (works both in development and inside a PyInstaller exe)
# ---------------------------------------------------------------------------


def asset_path(relative_path: str) -> str:
    """Return the absolute path to a bundled asset.

    PyInstaller unpacks bundled data to a temporary dir exposed as
    ``sys._MEIPASS``; in development we resolve relative to this file.
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


# ---------------------------------------------------------------------------
# Board geometry
# ---------------------------------------------------------------------------

COLS = 7
ROWS = 9
NUM_SQUARES = COLS * ROWS

# Terrain type constants
TERRAIN_LAND = 0
TERRAIN_RIVER = 1
TERRAIN_TRAP = 2
TERRAIN_DEN = 3

# Den positions (col, row)
DEN_BLACK = (3, 0)   # Black's den (top)
DEN_BLUE = (3, 8)    # Blue's den (bottom)

# Trap positions: the three squares orthogonally around each den.
TRAPS_BLACK = {(2, 0), (4, 0), (3, 1)}
TRAPS_BLUE = {(2, 8), (4, 8), (3, 7)}

# River squares: two 2x3 rectangles (cols 1-2 and 4-5, rows 3-5).
RIVER_LEFT = {(c, r) for c in (1, 2) for r in (3, 4, 5)}
RIVER_RIGHT = {(c, r) for c in (4, 5) for r in (3, 4, 5)}
RIVER_SQUARES = RIVER_LEFT | RIVER_RIGHT


def _build_terrain() -> list[list[int]]:
    """Terrain grid indexed ``terrain[col][row]``."""
    terrain = [[TERRAIN_LAND] * ROWS for _ in range(COLS)]
    for (c, r) in RIVER_SQUARES:
        terrain[c][r] = TERRAIN_RIVER
    for (c, r) in TRAPS_BLACK | TRAPS_BLUE:
        terrain[c][r] = TERRAIN_TRAP
    for (c, r) in (DEN_BLACK, DEN_BLUE):
        terrain[c][r] = TERRAIN_DEN
    return terrain


TERRAIN = _build_terrain()

# ---------------------------------------------------------------------------
# Colors (RGB) — a warm, readable palette
# ---------------------------------------------------------------------------

COLOR_BG = (24, 28, 24)
COLOR_LAND = (150, 190, 104)
COLOR_LAND_ALT = (139, 178, 92)          # checkerboard shade
COLOR_RIVER = (74, 144, 202)
COLOR_RIVER_ALT = (86, 156, 214)
COLOR_TRAP = (198, 142, 66)
COLOR_DEN_BLACK = (206, 120, 120)
COLOR_DEN_BLUE = (120, 150, 214)
COLOR_GRID = (34, 40, 34)
COLOR_HIGHLIGHT_SELECT = (255, 215, 0)   # gold for the selected piece
COLOR_HIGHLIGHT_MOVE = (96, 232, 120)    # green for legal-move targets
COLOR_HIGHLIGHT_LAST = (255, 235, 150)   # last-move trail
COLOR_CAPTURE_FLASH = (222, 66, 55)      # red flash on capture
COLOR_BLUE_PIECE = (58, 118, 220)
COLOR_BLUE_PIECE_DK = (34, 74, 150)
COLOR_BLACK_PIECE = (52, 56, 66)
COLOR_BLACK_PIECE_DK = (28, 30, 38)
COLOR_TEXT_LIGHT = (242, 244, 240)
COLOR_TEXT_DARK = (24, 24, 24)
COLOR_TEXT_MUTED = (170, 178, 170)
COLOR_PANEL_BG = (30, 34, 32)
COLOR_PANEL_ACCENT = (44, 50, 46)
COLOR_BUTTON_NORMAL = (64, 96, 128)
COLOR_BUTTON_HOVER = (92, 132, 168)
COLOR_BUTTON_TEXT = (238, 242, 245)
COLOR_OVERLAY_BG = (0, 0, 0, 190)        # semi-transparent

# ---------------------------------------------------------------------------
# Display (defaults; main.py recomputes CELL_SIZE / window size at startup)
# ---------------------------------------------------------------------------

CELL_SIZE = 80          # pixels per board cell
BOARD_MARGIN = 36       # margin around the board
PANEL_WIDTH = 250       # side panel width
CELL_MIN = 52           # clamp range used by the screen-aware sizing helper
CELL_MAX = 92

WINDOW_WIDTH = COLS * CELL_SIZE + BOARD_MARGIN * 2 + PANEL_WIDTH
WINDOW_HEIGHT = ROWS * CELL_SIZE + BOARD_MARGIN * 2
WINDOW_TITLE = "Jungle - Dou Shou Qi"

FPS = 60
CAPTURE_FLASH_MS = 320  # duration of the capture flash
MOVE_ANIM_MS = 140      # duration of the slide animation for a played move

# ---------------------------------------------------------------------------
# AI
# ---------------------------------------------------------------------------

AI_DEPTH_EASY = 3
AI_DEPTH_MEDIUM = 5
AI_TIME_HARD_MS = 2000        # iterative-deepening time budget for Hard
AI_MAX_DEPTH = 24             # hard ceiling on iterative deepening

DIFFICULTY_LABELS = ["Easy", "Medium", "Hard"]
DIFFICULTY_SUBTEXT = [
    "3-ply search - instant",
    "5-ply search - fast",
    "timed search - ~2s",
]

# Material value per Animal rank (1=Rat .. 8=Elephant).
PIECE_VALUES: dict[int, int] = {
    1: 250,   # Rat  (worth more than raw rank: it captures the Elephant)
    2: 180,   # Cat
    3: 260,   # Dog
    4: 340,   # Wolf
    5: 440,   # Leopard
    6: 560,   # Tiger
    7: 720,   # Lion
    8: 900,   # Elephant
}

# Positional evaluation weights. These are exactly the terms the evaluator
# implements (see ai/evaluator.py); the eval is kept deliberately lean so the
# pure-Python search stays fast. The score is antisymmetric (no side-to-move
# "tempo" term), which keeps the AI unbiased and the symmetric start position 0.
EVAL_WEIGHTS = {
    "advancement_per_row": 8,      # reward pushing toward the enemy den
    "den_proximity_per_step": 26,  # closer to the enemy den is better
    "den_proximity_max_dist": 4,   # only the last few steps count
    "jump_ready": 18,              # Lion/Tiger positioned to leap the river
    "rat_blocks_river": 24,        # our rat sits on a river square
}

# Weight applied to the piece-square table (positional shaping), used only when
# the search config enables it. Kept small relative to PIECE_VALUES.
PST_WEIGHT = 3

# ---------------------------------------------------------------------------
# Search tuning (used by the enhanced negamax; see ai/minimax.py)
# ---------------------------------------------------------------------------

NMP_REDUCTION = 2         # base null-move reduction R
NMP_MIN_DEPTH = 3         # never null-move below this depth
NMP_MIN_PIECES = 3        # disable null-move when side-to-move has fewer pieces
LMR_MIN_DEPTH = 3         # never reduce below this depth
LMR_MIN_MOVE_INDEX = 3    # first N moves are searched at full depth
ASPIRATION_DELTA = 40     # initial half-width of the root aspiration window
SEARCH_MAX_PLY = 96       # absolute recursion guard (with extensions)

# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

VERSION = "2.1"

# ---------------------------------------------------------------------------
# Custom pygame event IDs (assigned at runtime in main.py after pygame.init())
# ---------------------------------------------------------------------------

AI_MOVE_EVENT_TYPE: int = -1

# ===========================================================================
# Flat lookup tables (indexed by sq = col * ROWS + row)
# ===========================================================================


def sq_of(col: int, row: int) -> int:
    return col * ROWS + row


def col_of(sq: int) -> int:
    return sq // ROWS


def row_of(sq: int) -> int:
    return sq % ROWS


SQ_COL = tuple(sq // ROWS for sq in range(NUM_SQUARES))
SQ_ROW = tuple(sq % ROWS for sq in range(NUM_SQUARES))

TERRAIN_FLAT = tuple(TERRAIN[sq // ROWS][sq % ROWS] for sq in range(NUM_SQUARES))
IS_RIVER = tuple(t == TERRAIN_RIVER for t in TERRAIN_FLAT)
IS_TRAP = tuple(t == TERRAIN_TRAP for t in TERRAIN_FLAT)
IS_DEN = tuple(t == TERRAIN_DEN for t in TERRAIN_FLAT)

DEN_BLACK_SQ = sq_of(*DEN_BLACK)
DEN_BLUE_SQ = sq_of(*DEN_BLUE)

# Direction order matches historical move-generation order; move-list order
# (and thus AI search-tree shape) depends on it, so do not reorder.
DIRS = ((0, -1), (0, 1), (-1, 0), (1, 0))


def _build_neighbors() -> tuple[tuple[int, ...], ...]:
    out = []
    for sq in range(NUM_SQUARES):
        c, r = sq // ROWS, sq % ROWS
        nbs = []
        for (dc, dr) in DIRS:
            nc, nr = c + dc, r + dr
            if 0 <= nc < COLS and 0 <= nr < ROWS:
                nbs.append(nc * ROWS + nr)
        out.append(tuple(nbs))
    return tuple(out)


NEIGHBORS = _build_neighbors()


def _build_trap_owner() -> tuple[int, ...]:
    """TRAP_OWNER[sq]: the color that *owns* the trap on ``sq``.

    A piece standing on a trap owned by the OTHER color has its rank reduced to
    0. ``-1`` means the square is not a trap. Traps around Black's den (top) are
    owned by Black (=1); traps around Blue's den (bottom) by Blue (=0). Values
    match ``engine.pieces.Color`` (BLUE=0, BLACK=1).
    """
    owner = [-1] * NUM_SQUARES
    for (c, r) in TRAPS_BLACK:
        owner[c * ROWS + r] = 1   # Color.BLACK
    for (c, r) in TRAPS_BLUE:
        owner[c * ROWS + r] = 0   # Color.BLUE
    return tuple(owner)


TRAP_OWNER = _build_trap_owner()

# Own-color advancement per square (0 at own back rank .. ROWS-1 at enemy den).
ADV_BLUE = tuple(ROWS - 1 - (sq % ROWS) for sq in range(NUM_SQUARES))
ADV_BLACK = tuple(sq % ROWS for sq in range(NUM_SQUARES))


def _dist_table(den: tuple[int, int]) -> tuple[int, ...]:
    dc, dr = den
    return tuple(abs(sq // ROWS - dc) + abs(sq % ROWS - dr)
                 for sq in range(NUM_SQUARES))


DIST_TO_BLACK_DEN = _dist_table(DEN_BLACK)   # distance to Black's den (Blue's target)
DIST_TO_BLUE_DEN = _dist_table(DEN_BLUE)     # distance to Blue's den (Black's target)


# Piece-square table (positional shaping), indexed by own-color advancement and
# column. It rewards the central files (the direct approach to the den) and
# advancement into the enemy half. Column-symmetric so there is no left/right
# bias, which keeps eval(BLUE) == -eval(BLACK) and the symmetric start at 0.
def _build_pst() -> tuple[tuple[int, ...], ...]:
    col_weight = (0, 4, 7, 9, 7, 4, 0)      # peak on the central den file
    table = []
    for adv in range(ROWS):
        row = []
        for c in range(COLS):
            v = col_weight[c]
            if adv > ROWS // 2:               # enemy half: push centrally
                v += (adv - ROWS // 2) * 2
            row.append(v)
        table.append(tuple(row))
    return tuple(table)


_PST = _build_pst()
PST_BLUE = tuple(_PST[ADV_BLUE[sq]][sq // ROWS] for sq in range(NUM_SQUARES))
PST_BLACK = tuple(_PST[ADV_BLACK[sq]][sq // ROWS] for sq in range(NUM_SQUARES))


# ---------------------------------------------------------------------------
# Screen-aware logical sizing (pure functions so they can be unit-tested)
# ---------------------------------------------------------------------------

RESERVED_SCREEN_PX = 96   # title bar + taskbar + breathing room


def compute_cell_size(screen_h: int, reserved: int = RESERVED_SCREEN_PX) -> int:
    """Pick a cell size (clamped to [CELL_MIN, CELL_MAX]) so the board's logical
    height fits within the usable screen height. The SCALED display then scales
    this logical layout to fill whatever window/monitor it runs on."""
    usable = max(screen_h - reserved, ROWS * CELL_MIN + 2 * BOARD_MARGIN)
    raw = (usable - 2 * BOARD_MARGIN) // ROWS
    return max(CELL_MIN, min(CELL_MAX, int(raw)))


def layout_for_cell(cell: int) -> tuple[int, int]:
    """Return the (window_width, window_height) implied by a cell size."""
    width = COLS * cell + 2 * BOARD_MARGIN + PANEL_WIDTH
    height = ROWS * cell + 2 * BOARD_MARGIN
    return width, height
