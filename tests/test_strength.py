"""Strength / regression tests for the enhanced engine.

These are DETERMINISTIC gates — a tactical suite the engine must solve and an
effective-depth floor — plus a small non-flaky self-play smoke test. The large
statistical win-rate gauntlet lives in ``tools/strength_harness.py`` and is run
manually (see the plan's Validation Commands).
"""

from dataclasses import fields

from engine.board import Board
from engine.game_state import GameState
from engine.pieces import Animal, Color, make_piece_id
from ai.minimax import AIPlayer
from ai.search_config import SearchConfig, baseline_config, strong_config
from tools.strength_harness import play_match, play_one
from config import DEN_BLACK


def make_gs(*piece_specs) -> GameState:
    gs = GameState()
    gs.board = Board()
    for (c, r, color, animal) in piece_specs:
        pid = make_piece_id(color, animal)
        gs.board._grid[c][r] = pid
        gs.board._piece_positions[int(color)][pid] = (c, r)
    return gs


def midgame() -> GameState:
    """A reproducible, out-of-book 12-piece midgame with Blue to move."""
    gs = make_gs(
        (0, 6, Color.BLUE, Animal.ELEPHANT), (2, 6, Color.BLUE, Animal.WOLF),
        (4, 6, Color.BLUE, Animal.LEOPARD), (6, 6, Color.BLUE, Animal.RAT),
        (0, 8, Color.BLUE, Animal.TIGER), (6, 8, Color.BLUE, Animal.LION),
        (0, 2, Color.BLACK, Animal.RAT), (2, 2, Color.BLACK, Animal.LEOPARD),
        (4, 2, Color.BLACK, Animal.WOLF), (6, 2, Color.BLACK, Animal.ELEPHANT),
        (0, 0, Color.BLACK, Animal.LION), (6, 0, Color.BLACK, Animal.TIGER),
    )
    gs.turn = Color.BLUE
    return gs


# ---------------------------------------------------------------------------
# SearchConfig sanity
# ---------------------------------------------------------------------------

def test_baseline_disables_all_bool_flags():
    base = baseline_config()
    assert all(getattr(base, f.name) is False
               for f in fields(SearchConfig) if isinstance(f.default, bool))


def test_strong_enables_all_bool_flags():
    strong = strong_config()
    assert all(getattr(strong, f.name) is True
               for f in fields(SearchConfig) if isinstance(f.default, bool))


# ---------------------------------------------------------------------------
# Tactical suite — deterministic strength gates
# ---------------------------------------------------------------------------

def test_strong_finds_den_entry_win():
    """One move from the enemy den → take the win."""
    gs = make_gs(
        (3, 1, Color.BLUE, Animal.WOLF),
        (6, 8, Color.BLACK, Animal.ELEPHANT),
    )
    gs.turn = Color.BLUE
    ai = AIPlayer(Color.BLUE, 2, strong_config())
    move = ai.get_best_move(gs, time_budget_ms=300)
    assert move is not None
    assert (move.tc, move.tr) == DEN_BLACK


def test_strong_avoids_horizon_blunder():
    """Quiescence gate: must not grab a Wolf that a Lion immediately recaptures.

    Tested at difficulty 0 (fixed shallow depth) so the trap sits exactly on the
    horizon — this exercises quiescence/SEE. The tactic is on the left edge with
    Blue up material and its den safe, so the position is not lost and avoiding
    the trade is genuinely best.
    """
    gs = make_gs(
        (0, 4, Color.BLUE, Animal.TIGER),
        (0, 5, Color.BLACK, Animal.WOLF),
        (0, 6, Color.BLACK, Animal.LION),
        (6, 8, Color.BLUE, Animal.ELEPHANT),
        (5, 8, Color.BLUE, Animal.LION),
        (6, 0, Color.BLACK, Animal.RAT),
    )
    gs.turn = Color.BLUE
    ai = AIPlayer(Color.BLUE, 0, strong_config())
    move = ai.get_best_move(gs)
    assert move is not None
    assert (move.fc, move.fr, move.tc, move.tr) != (0, 4, 0, 5)


def test_strong_prefers_faster_mate():
    """Two winning ideas exist; pick the immediate den entry."""
    gs = make_gs(
        (3, 1, Color.BLUE, Animal.WOLF),
        (0, 8, Color.BLUE, Animal.LION),
        (6, 0, Color.BLACK, Animal.RAT),
    )
    gs.turn = Color.BLUE
    ai = AIPlayer(Color.BLUE, 2, strong_config())
    move = ai.get_best_move(gs, time_budget_ms=500)
    assert move is not None
    assert (move.tc, move.tr) == DEN_BLACK


# ---------------------------------------------------------------------------
# Move ordering (Task 2)
# ---------------------------------------------------------------------------

def test_order_mvv_lva_prefers_cheap_attacker():
    """Two pieces can take the same victim → try the cheaper attacker first."""
    gs = make_gs(
        (0, 4, Color.BLACK, Animal.CAT),    # victim (rank 2)
        (0, 3, Color.BLUE, Animal.DOG),     # cheap attacker (rank 3) — preferred
        (0, 5, Color.BLUE, Animal.LION),    # expensive attacker (rank 7)
    )
    gs.turn = Color.BLUE
    ai = AIPlayer(Color.BLUE, 2, strong_config())
    ordered = ai._order_moves(gs.legal_moves(), None, 0, None, gs.board)
    dog_cap = next(m for m in ordered if (m.fc, m.fr, m.tc, m.tr) == (0, 3, 0, 4))
    lion_cap = next(m for m in ordered if (m.fc, m.fr, m.tc, m.tr) == (0, 5, 0, 4))
    assert ordered.index(dog_cap) < ordered.index(lion_cap)


def test_order_see_demotes_losing_capture():
    """A capture that loses material to recapture is ordered behind quiet moves."""
    gs = make_gs(
        (3, 4, Color.BLUE, Animal.TIGER),   # attacker (rank 6)
        (3, 5, Color.BLACK, Animal.WOLF),   # victim (rank 4), defended
        (3, 6, Color.BLACK, Animal.LION),   # defender (rank 7) > Tiger
    )
    gs.turn = Color.BLUE
    ai = AIPlayer(Color.BLUE, 2, strong_config())
    ordered = ai._order_moves(gs.legal_moves(), None, 0, None, gs.board)
    losing_cap = next(m for m in ordered if (m.fc, m.fr, m.tc, m.tr) == (3, 4, 3, 5))
    quiet = next(m for m in ordered if m.captured == 0)
    assert ordered.index(quiet) < ordered.index(losing_cap)


# ---------------------------------------------------------------------------
# Den-aware quiescence (Task 6)
# ---------------------------------------------------------------------------

def test_generate_noisy_includes_den_entry():
    """Noisy moves include the (non-capture) den-entry move; captures do not."""
    from engine.move_generator import generate_noisy_moves, generate_capture_moves
    gs = make_gs(
        (3, 1, Color.BLUE, Animal.WOLF),    # one step from black den (3,0)
        (0, 0, Color.BLACK, Animal.LION),
    )
    den_move = (3, 1, 3, 0)
    noisy = {(m.fc, m.fr, m.tc, m.tr) for m in generate_noisy_moves(gs.board, Color.BLUE)}
    caps = {(m.fc, m.fr, m.tc, m.tr) for m in generate_capture_moves(gs.board, Color.BLUE)}
    assert den_move in noisy
    assert den_move not in caps


def test_quiescence_sees_den_dash():
    """At a leaf node, quiescence must see a one-move den win (noisy quiescence)."""
    gs = make_gs(
        (3, 1, Color.BLUE, Animal.WOLF),
        (0, 0, Color.BLACK, Animal.LION),
    )
    gs.turn = Color.BLUE
    ai = AIPlayer(Color.BLUE, 2, strong_config())
    score = ai._quiesce(gs, -10_000_000, 10_000_000, qply=0, ply=0)
    assert score > 1_000_000, f"quiescence missed the den dash (score={score})"


# ---------------------------------------------------------------------------
# Effective-depth floor
# ---------------------------------------------------------------------------

def test_effective_depth_floor():
    """Hard search reaches a sane depth within 1s on a midgame position.

    Uses an out-of-book midgame (the opening book would otherwise short-circuit
    the search and leave _last_depth at 0).
    """
    ai = AIPlayer(Color.BLUE, 2, strong_config())
    ai.get_best_move(midgame(), time_budget_ms=1000)
    assert ai._last_depth >= 4, f"only reached depth {ai._last_depth}"


def test_tiny_budget_returns_legal_move():
    """Even a 1ms budget must yield a legal move, never None (partial iteration)."""
    gs = midgame()
    legal = {(m.fc, m.fr, m.tc, m.tr) for m in gs.legal_moves()}
    ai = AIPlayer(Color.BLUE, 2, strong_config())
    move = ai.get_best_move(gs, time_budget_ms=1)
    assert move is not None
    assert (move.fc, move.fr, move.tc, move.tr) in legal


# ---------------------------------------------------------------------------
# Harness smoke — non-flaky (checks it runs and totals are consistent)
# ---------------------------------------------------------------------------

def test_harness_play_one_returns_color_or_none():
    res = play_one(strong_config(), baseline_config(),
                   budget_ms=50, max_moves=20, opening_seed=1, opening_plies=4)
    assert res is None or res in (Color.BLUE, Color.BLACK)


def test_harness_match_totals_consistent():
    res = play_match(strong_config(), strong_config(),
                     games=2, budget_ms=50, max_moves=20, opening_plies=4, seed=7)
    assert res["games"] == res["a_wins"] + res["b_wins"] + res["draws"]
    assert 0.0 <= res["a_score"] <= 1.0
