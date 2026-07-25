"""Tests for the strength harness's statistics.

The harness is the instrument every engine change is judged by, so its own
arithmetic needs to be right. It previously printed only a win percentage plus a
binary "A stronger" verdict that fired on a single-game edge — at the default 20
games that verdict is indistinguishable from noise, which makes it worse than no
verdict at all.
"""

from __future__ import annotations

from engine.pieces import Color
from tools.strength_harness import _tally, match_statistics, score_to_elo

# ---------------------------------------------------------------------------
# Elo conversion
# ---------------------------------------------------------------------------

def test_even_score_is_zero_elo():
    assert score_to_elo(0.5) == 0.0


def test_elo_is_monotonic_and_antisymmetric():
    assert score_to_elo(0.75) > score_to_elo(0.6) > 0 > score_to_elo(0.4)
    for score in (0.25, 0.4, 0.6, 0.75, 0.9):
        assert abs(score_to_elo(score) + score_to_elo(1.0 - score)) < 1e-9


def test_elo_known_values():
    """A 76% score is about +200 Elo; 64% is about +100."""
    assert abs(score_to_elo(0.76) - 200) < 10
    assert abs(score_to_elo(0.64) - 100) < 10


def test_elo_saturates_instead_of_diverging():
    """A clean sweep implies an unbounded difference; clamp rather than crash."""
    assert score_to_elo(1.0) == 800.0
    assert score_to_elo(0.0) == -800.0


# ---------------------------------------------------------------------------
# Match statistics
# ---------------------------------------------------------------------------

def test_counts_and_score():
    res = match_statistics(a_wins=12, b_wins=6, draws=2)
    assert res["games"] == 20
    assert res["a_score"] == (12 + 1.0) / 20
    assert res["a_wins"] == 12 and res["b_wins"] == 6 and res["draws"] == 2


def test_empty_match_does_not_divide_by_zero():
    res = match_statistics(0, 0, 0)
    assert res["games"] == 0
    assert res["a_score"] == 0.0
    assert res["los"] == 0.5


def test_small_sample_is_not_decidable():
    """11-9 over 20 games must NOT read as a real difference."""
    res = match_statistics(a_wins=11, b_wins=9, draws=0)
    assert res["a_score"] > 0.5, "A did score above parity..."
    assert res["elo_lo"] < 0 < res["elo_hi"], "...but the CI must still span parity"


def test_large_clear_sample_is_decidable():
    """A big, lopsided sample must produce a CI that excludes parity."""
    res = match_statistics(a_wins=140, b_wins=40, draws=20)
    assert res["elo_lo"] > 0, "a 70% score over 200 games should be decisive"
    assert res["los"] > 0.99


def test_confidence_interval_narrows_with_more_games():
    """Same score, more games → tighter interval. This is the whole point."""
    small = match_statistics(a_wins=12, b_wins=8, draws=0)
    large = match_statistics(a_wins=120, b_wins=80, draws=0)
    assert abs(small["a_score"] - large["a_score"]) < 1e-9
    small_width = small["elo_hi"] - small["elo_lo"]
    large_width = large["elo_hi"] - large["elo_lo"]
    assert large_width < small_width


def test_los_symmetry():
    balanced = match_statistics(a_wins=10, b_wins=10, draws=0)
    assert abs(balanced["los"] - 0.5) < 1e-9
    ahead = match_statistics(a_wins=15, b_wins=5, draws=0)
    behind = match_statistics(a_wins=5, b_wins=15, draws=0)
    assert abs(ahead["los"] + behind["los"] - 1.0) < 1e-9


def test_all_draws_is_exactly_parity():
    res = match_statistics(a_wins=0, b_wins=0, draws=30)
    assert res["a_score"] == 0.5
    assert res["elo"] == 0.0
    assert res["los"] == 0.5


# ---------------------------------------------------------------------------
# Colour-swap accounting
# ---------------------------------------------------------------------------

def test_tally_maps_colours_to_players():
    """`swapped` means A played Black, so a Black win is an A win."""
    results = [
        (0, False, Color.BLUE),    # A was Blue and won   -> A
        (0, True, Color.BLACK),    # A was Black and won  -> A
        (1, False, Color.BLACK),   # A was Blue, Black won -> B
        (1, True, Color.BLUE),     # A was Black, Blue won -> B
        (2, False, None),          # draw
    ]
    assert _tally(results) == (2, 2, 1)


def test_tally_of_a_clean_sweep_for_b():
    results = [
        (0, False, Color.BLACK),
        (0, True, Color.BLUE),
    ]
    assert _tally(results) == (0, 2, 0)
