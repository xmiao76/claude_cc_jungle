"""Global constants for the Jungle board game."""

import os
import sys

# ---------------------------------------------------------------------------
# Asset path resolution (works both in development and as a PyInstaller exe)
# ---------------------------------------------------------------------------

def asset_path(relative_path: str) -> str:
    """Return absolute path to a bundled asset, works with PyInstaller --onefile."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


# ---------------------------------------------------------------------------
# Board geometry
# ---------------------------------------------------------------------------

COLS = 7
ROWS = 9

# Terrain type constants
TERRAIN_LAND = 0
TERRAIN_RIVER = 1
TERRAIN_TRAP = 2
TERRAIN_DEN = 3

# Den positions
DEN_BLACK = (3, 0)   # Black's den (top)
DEN_BLUE = (3, 8)    # Blue's den (bottom)

# Trap positions
TRAPS_BLACK = {(2, 0), (4, 0), (3, 1)}
TRAPS_BLUE = {(2, 8), (4, 8), (3, 7)}

# River squares: two 2×3 rectangles
RIVER_1 = {(1, 3), (2, 3), (1, 4), (2, 4), (1, 5), (2, 5)}
RIVER_2 = {(4, 3), (5, 3), (4, 4), (5, 4), (4, 5), (5, 5)}
RIVER_SQUARES = RIVER_1 | RIVER_2

# Precomputed terrain map: terrain[col][row]
def _build_terrain() -> list[list[int]]:
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
# Colors (RGB)
# ---------------------------------------------------------------------------

COLOR_BG = (30, 30, 30)
COLOR_LAND = (139, 178, 90)
COLOR_RIVER = (64, 133, 196)
COLOR_TRAP = (180, 130, 50)
COLOR_DEN = (220, 180, 60)
COLOR_GRID = (20, 20, 20)
COLOR_HIGHLIGHT_SELECT = (255, 215, 0)      # gold for selected piece
COLOR_HIGHLIGHT_MOVE = (100, 230, 100)       # green for legal move targets
COLOR_CAPTURE_FLASH = (220, 50, 50)          # red flash on capture
COLOR_BLUE_PIECE = (60, 120, 220)
COLOR_BLACK_PIECE = (40, 40, 40)
COLOR_TEXT_LIGHT = (240, 240, 240)
COLOR_TEXT_DARK = (20, 20, 20)
COLOR_PANEL_BG = (25, 25, 25)
COLOR_BUTTON_NORMAL = (70, 70, 100)
COLOR_BUTTON_HOVER = (100, 100, 160)
COLOR_OVERLAY_BG = (0, 0, 0, 180)           # semi-transparent

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

CELL_SIZE = 80          # pixels per cell
BOARD_OFFSET_X = 40     # left margin for the board
BOARD_OFFSET_Y = 40     # top margin for the board
PANEL_WIDTH = 220       # side panel width

WINDOW_WIDTH = COLS * CELL_SIZE + BOARD_OFFSET_X * 2 + PANEL_WIDTH
WINDOW_HEIGHT = ROWS * CELL_SIZE + BOARD_OFFSET_Y * 2
WINDOW_TITLE = "Jungle - Dou Shou Qi"

FPS = 60
CAPTURE_FLASH_MS = 300  # duration of capture animation

# ---------------------------------------------------------------------------
# AI
# ---------------------------------------------------------------------------

AI_DEPTH_EASY = 3
AI_DEPTH_MEDIUM = 5
AI_TIME_HARD_MS = 2000   # iterative deepening time budget for Hard

DIFFICULTY_LABELS = ["Easy", "Medium", "Hard"]
DIFFICULTY_SUBTEXT = [
    "3-ply search · instant",
    "5-ply search · ~0.5s",
    "iterative · ~2s",
]

USE_OPENING_BOOK = True

# Material values per Animal rank (1=Rat .. 8=Elephant)
PIECE_VALUES: dict[int, int] = {
    1: 100,   # Rat
    2: 200,   # Cat
    3: 300,   # Dog
    4: 400,   # Wolf
    5: 500,   # Leopard
    6: 600,   # Tiger
    7: 700,   # Lion
    8: 800,   # Elephant
}

# Positional evaluation weights (centralized for tuning)
EVAL_WEIGHTS = {
    "advancement_per_row": 10,
    "den_proximity_max_dist": 3,
    "den_proximity_per_step": 30,
    "rat_in_water": 40,
    "rat_adjacent_to_enemy_elephant": 60,
    "trap_control": 80,
    # Added in stronger-engine refactor
    "mobility": 2,                 # per-extra-pseudo-move
    "den_defender": 25,            # per friendly piece within 2 of own den
    "jump_ready": 20,              # Lion/Tiger has at least one jump available
    "rat_blocks_river": 35,        # our rat sits on river square
    "tempo": 10,                   # side-to-move bonus
    "advancement_acceleration": 6, # extra per row past midline (row 4)
    "delta_margin": 200,           # quiescence delta-pruning margin
    # Added by the stronger-engine plan (Tasks 5-6)
    "pst": 1,                      # piece-square table multiplier
    "den_threat": 45,              # per enemy piece that can reach an undefended
                                   # square next to our den (and the mirror)
}

QUIESCENCE_MAX_PLY = 4    # cap on quiescence search depth


# ---------------------------------------------------------------------------
# Piece-square table (positional shaping)
# ---------------------------------------------------------------------------
# Indexed [advancement][col], where advancement is measured from the piece's own
# back rank (0) toward the enemy den (ROWS-1). Applied per-piece using the
# piece's OWN-color advancement (added for own pieces, subtracted for opponent
# pieces) so the evaluation stays antisymmetric: eval(BLUE) == -eval(BLACK).
# The table is column-symmetric (value at col c == col COLS-1-c) so there is no
# left/right bias and the symmetric starting position evaluates to exactly 0.
# It peaks on the central file — the direct approach to the den — and rewards
# central advancement into the enemy half. Magnitudes are small vs PIECE_VALUES.
def _build_pst() -> list[list[int]]:
    col_weight = [0, 5, 9, 12, 9, 5, 0]   # symmetric; peak on the central den file
    table = [[0] * COLS for _ in range(ROWS)]
    for adv in range(ROWS):
        for c in range(COLS):
            v = col_weight[c]
            if adv > ROWS // 2:           # enemy half: central advance is best
                v += (adv - ROWS // 2) * (col_weight[c] // 6)
            table[adv][c] = v
    return table


PST_TABLE = _build_pst()

# Search tuning (added by stronger-engine plan)
NMP_REDUCTION = 2          # depth reduction R for null-move pruning
NMP_MIN_DEPTH = 3
NMP_MIN_PIECES = 3         # disable NMP if side-to-move has fewer pieces
LMR_MIN_DEPTH = 3
LMR_MOVES_BEFORE = 4       # number of full-depth moves before reductions kick in
ASPIRATION_DELTA = 50
ASPIRATION_MIN_DEPTH = 4

# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

VERSION = "1.3"

# ---------------------------------------------------------------------------
# Custom pygame event IDs (registered at runtime)
# ---------------------------------------------------------------------------

# These are set in main.py after pygame.init()
AI_MOVE_EVENT_TYPE: int = -1
