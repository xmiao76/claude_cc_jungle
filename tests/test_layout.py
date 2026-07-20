"""Screen-aware logical sizing: the helpers that keep the UI fitting cleanly
across resolutions/DPI (the SCALED display then scales this logical layout)."""

import config


def test_cell_size_always_within_clamp():
    for h in range(320, 3200, 37):
        cs = config.compute_cell_size(h)
        assert config.CELL_MIN <= cs <= config.CELL_MAX


def test_cell_size_is_non_decreasing_in_screen_height():
    prev = 0
    for h in range(320, 3200, 37):
        cs = config.compute_cell_size(h)
        assert cs >= prev
        prev = cs


def test_layout_matches_board_plus_margins_plus_panel():
    for cs in (config.CELL_MIN, 60, 75, config.CELL_MAX):
        w, h = config.layout_for_cell(cs)
        assert w == config.COLS * cs + 2 * config.BOARD_MARGIN + config.PANEL_WIDTH
        assert h == config.ROWS * cs + 2 * config.BOARD_MARGIN


def test_tiny_screen_stays_usable():
    """Even a very short screen falls back to the minimum cell, giving a small
    but valid logical window (the SCALED display scales it up to fit)."""
    cs = config.compute_cell_size(400)
    w, h = config.layout_for_cell(cs)
    assert cs == config.CELL_MIN
    assert h == config.ROWS * config.CELL_MIN + 2 * config.BOARD_MARGIN
    assert 0 < h <= 600


def test_large_screen_hits_max_cell():
    assert config.compute_cell_size(4000) == config.CELL_MAX
