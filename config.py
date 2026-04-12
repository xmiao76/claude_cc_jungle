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

AI_DEPTH_EASY = 2
AI_DEPTH_MEDIUM = 4
AI_TIME_HARD_MS = 2000   # iterative deepening time budget for Hard

DIFFICULTY_LABELS = ["Easy", "Medium", "Hard"]

# ---------------------------------------------------------------------------
# Custom pygame event IDs (registered at runtime)
# ---------------------------------------------------------------------------

# These are set in main.py after pygame.init()
AI_MOVE_EVENT_TYPE: int = -1
