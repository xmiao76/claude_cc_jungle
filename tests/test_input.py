"""Board input: pixel<->square mapping (with flip) and two-click move flow.

These are display-free: they exercise only the coordinate math and selection
logic, using the default config cell size."""

import config
from engine.game_state import GameState
from engine.pieces import Animal, Color
from gui.input_handler import InputHandler, pixel_to_board

BLUE = int(Color.BLUE)
ROWS = config.ROWS


def center_px(col, row, flipped=False):
    """Pixel at the center of a cell, mirroring the renderer's transform."""
    dcol = config.COLS - 1 - col if flipped else col
    drow = ROWS - 1 - row if flipped else row
    x = config.BOARD_MARGIN + dcol * config.CELL_SIZE + config.CELL_SIZE // 2
    y = config.BOARD_MARGIN + drow * config.CELL_SIZE + config.CELL_SIZE // 2
    return x, y


def test_pixel_to_board_roundtrip_unflipped():
    for col, row in ((0, 0), (3, 4), (6, 8)):
        assert pixel_to_board(*center_px(col, row), flipped=False) == (col, row)


def test_pixel_to_board_roundtrip_flipped():
    for col, row in ((0, 0), (3, 4), (6, 8)):
        assert pixel_to_board(*center_px(col, row, flipped=True), flipped=True) == (col, row)


def test_pixel_off_board_returns_none():
    assert pixel_to_board(2, 2, flipped=False) is None            # inside top margin
    big = config.WINDOW_WIDTH + 50
    assert pixel_to_board(big, big, flipped=False) is None


def test_two_click_selects_then_moves():
    gs = GameState()
    gs.setup_position({(3, 4): (BLUE, Animal.LION)}, to_move=BLUE)
    ih = InputHandler()

    # First click selects the Lion (no move yet).
    move = ih.handle_click(*center_px(3, 4), gs=gs, human_color=BLUE, flipped=False)
    assert move is None
    assert ih.selected == (3, 4)
    assert ih.target_squares()

    # Second click on a legal empty target completes a move.
    tx, ty = center_px(3, 3)
    move = ih.handle_click(tx, ty, gs=gs, human_color=BLUE, flipped=False)
    assert move is not None and move.to == 3 * ROWS + 3
    assert ih.selected is None            # selection cleared after moving


def test_click_empty_square_deselects():
    gs = GameState()
    gs.setup_position({(3, 4): (BLUE, Animal.LION)}, to_move=BLUE)
    ih = InputHandler()
    ih.handle_click(*center_px(3, 4), gs=gs, human_color=BLUE, flipped=False)
    assert ih.selected is not None
    # Click a far empty, non-target square -> deselect.
    ih.handle_click(*center_px(0, 0), gs=gs, human_color=BLUE, flipped=False)
    assert ih.selected is None
