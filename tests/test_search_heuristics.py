"""Tests for the search-ordering heuristics and the transposition table.

These are the parts of the search whose bugs are invisible in play: a wrong
history key or a TT entry that never expires costs strength without ever
producing a wrong move, so only a measurement or a targeted test finds them.
"""

from __future__ import annotations

import time
from dataclasses import replace

from ai.minimax import _HISTORY_MAX, AIPlayer
from ai.search_config import strong_config
from ai.transposition import TT_EXACT, TT_LOWER, TranspositionTable
from engine.board import Move
from engine.game_state import GameState
from engine.pieces import Animal, Color
from tests.helpers import make_gs

# ---------------------------------------------------------------------------
# History heuristic
# ---------------------------------------------------------------------------


def _player(**overrides) -> AIPlayer:
    return AIPlayer(Color.BLUE, 2, replace(strong_config(), **overrides))


def test_history_key_separates_the_two_sides():
    """Blue and Black must not share history entries.

    Both sides can play the same (from, to) pair — the board is symmetric — so a
    key without the side lets one side's good quiet moves promote the other's.
    """
    ai = _player(use_side_history=True)
    move = Move(3, 4, 3, 3, 0)
    blue_key = ai._history_key(int(Color.BLUE), move)
    black_key = ai._history_key(int(Color.BLACK), move)
    assert blue_key != black_key

    ai._history_bonus(int(Color.BLUE), move, depth=6)
    assert ai._history.get(blue_key, 0) > 0
    assert ai._history.get(black_key, 0) == 0, "Black inherited Blue's history"


def test_history_key_is_side_blind_when_disabled():
    ai = _player(use_side_history=False)
    move = Move(3, 4, 3, 3, 0)
    assert ai._history_key(int(Color.BLUE), move) == ai._history_key(int(Color.BLACK), move)


def test_history_is_capped_below_the_killer_band():
    """An uncapped score eventually outranks killers and even winning captures.

    `_order_moves` scores killers at -50_000/-49_000, the counter-move at -48_000
    and winning captures near -100_000, while a quiet move scores -history. So the
    cap has to sit below all of those.
    """
    ai = _player(use_side_history=True)
    move = Move(3, 4, 3, 3, 0)
    for _ in range(200):
        ai._history_bonus(int(Color.BLUE), move, depth=30)
    score = ai._history[ai._history_key(int(Color.BLUE), move)]
    assert score == _HISTORY_MAX
    assert _HISTORY_MAX < 48_000, "cap must stay under the counter-move band"


def test_history_malus_penalises_moves_that_did_not_cut_off():
    """Bonus-only history is a tally; the malus makes it a comparison."""
    ai = _player(use_side_history=True)
    good = Move(3, 4, 3, 3, 0)
    bad = Move(3, 4, 2, 4, 0)

    ai._history_bonus(int(Color.BLUE), good, depth=4)
    ai._history_malus(int(Color.BLUE), [bad], depth=4)

    good_score = ai._history[ai._history_key(int(Color.BLUE), good)]
    bad_score = ai._history[ai._history_key(int(Color.BLUE), bad)]
    assert good_score > 0 > bad_score


def test_history_malus_is_a_no_op_when_disabled():
    ai = _player(use_side_history=False)
    ai._history_malus(int(Color.BLUE), [Move(3, 4, 3, 3, 0)], depth=4)
    assert ai._history == {}


def test_ordering_prefers_a_quiet_move_with_history():
    """The history score has to actually reach move ordering."""
    gs = make_gs(
        (3, 4, Color.BLUE, Animal.WOLF),
        (0, 0, Color.BLACK, Animal.LION),
        turn=Color.BLUE,
    )
    ai = _player(use_side_history=True)
    moves = gs.legal_moves()
    favoured = moves[-1]
    ai._history_bonus(int(Color.BLUE), favoured, depth=8)

    ordered = ai._order_moves(list(moves), None, 0, None, gs.board, side=int(Color.BLUE))
    assert ordered[0] == favoured


# ---------------------------------------------------------------------------
# Transposition table
# ---------------------------------------------------------------------------


def test_deeper_entry_is_kept_within_one_search():
    tt = TranspositionTable(use_aging=True)
    tt.new_search()
    tt.put(1234, depth=10, score=500, flag=TT_EXACT, best_move=None)
    tt.put(1234, depth=2, score=-500, flag=TT_LOWER, best_move=None)
    assert tt.get(1234).depth == 10, "a shallower probe must not displace deeper analysis"


def test_stale_entry_is_replaceable_regardless_of_depth():
    """This is the point of aging.

    The table lives for the whole game. Without a generation, a deep entry from a
    position that can no longer occur holds its slot forever, because the
    depth-preferring policy refuses every newer shallower result.
    """
    tt = TranspositionTable(use_aging=True)
    tt.new_search()
    tt.put(1234, depth=10, score=500, flag=TT_EXACT, best_move=None)

    tt.new_search()                      # a new move: the old entry is now stale
    tt.put(1234, depth=2, score=-500, flag=TT_LOWER, best_move=None)

    entry = tt.get(1234)
    assert entry.depth == 2
    assert entry.score == -500
    assert entry.generation == tt._generation


def test_without_aging_a_deep_entry_is_permanent():
    tt = TranspositionTable(use_aging=False)
    tt.put(1234, depth=10, score=500, flag=TT_EXACT, best_move=None)
    tt.new_search()
    tt.put(1234, depth=2, score=-500, flag=TT_LOWER, best_move=None)
    assert tt.get(1234).depth == 10


def test_eviction_drops_stale_entries_first():
    """Eviction must be a linear pass, not a sort of the whole table."""
    tt = TranspositionTable(max_entries=4, use_aging=True)
    tt.new_search()
    for key in range(4):
        tt.put(key, depth=9, score=1, flag=TT_EXACT, best_move=None)
    assert len(tt) == 4

    tt.new_search()
    tt.put(99, depth=1, score=2, flag=TT_EXACT, best_move=None)

    assert tt.get(99) is not None, "the new entry must be stored"
    assert len(tt) <= 4
    assert all(tt.get(k) is None for k in range(4)), "stale entries should go first"


def test_eviction_still_works_when_everything_is_current():
    """No stale entries to reclaim: fall back to dropping the shallow half."""
    tt = TranspositionTable(max_entries=4, use_aging=True)
    tt.new_search()
    for key, depth in enumerate((1, 2, 8, 9)):
        tt.put(key, depth=depth, score=1, flag=TT_EXACT, best_move=None)

    tt.put(99, depth=5, score=2, flag=TT_EXACT, best_move=None)

    assert tt.get(99) is not None
    assert tt.get(3) is not None, "the deepest entry should survive"
    assert len(tt) <= 4


def test_entry_round_trips_every_field():
    tt = TranspositionTable()
    tt.new_search()
    move = Move(1, 2, 3, 4, -5)
    tt.put(77, depth=7, score=-321, flag=TT_LOWER, best_move=move)
    entry = tt.get(77)
    assert (entry.depth, entry.score, entry.flag, entry.best_move) == (7, -321, TT_LOWER, move)


def test_search_marks_a_new_generation_per_move():
    """`get_best_move` must age the table, or aging never happens in play."""
    gs = make_gs(
        (3, 4, Color.BLUE, Animal.WOLF),
        (0, 0, Color.BLACK, Animal.LION),
        (6, 6, Color.BLACK, Animal.CAT),
        turn=Color.BLUE,
    )
    ai = _player(use_tt_aging=True)
    before = ai._tt._generation
    ai.get_best_move(gs, time_budget_ms=120)
    assert ai._tt._generation > before


def test_a_node_limit_bounds_the_search():
    """The node budget is what makes an A/B against a differently-paced engine fair.

    Nominal depth is not a common currency between two engines that prune
    differently -- the same "depth 5" can be a tree of 700 nodes or 5000. Nodes
    are, and unlike a clock a node budget is deterministic, so a match is
    reproducible and unaffected by what else the machine is doing.
    """
    gs = GameState()
    gs.new_game()

    unlimited = _player()
    unlimited.get_best_move(gs, time_budget_ms=400)

    for budget in (500, 2_000, 8_000):
        ai = _player()
        ai._node_limit = budget
        ai._time_limit = 3600.0
        ai._stop_requested = False
        ai._nodes = 0
        ai._start_time = time.perf_counter()
        ai._reset_search_heuristics()
        ai._tt.new_search()
        move = ai._search_iterative_deepening(gs)

        assert move in gs.legal_moves(), "a node-limited search must still be legal"
        # The clock is only consulted every 2048 nodes, so allow one interval of
        # overshoot rather than pretending the bound is exact.
        assert ai._nodes <= budget + 2048, f"budget {budget}, searched {ai._nodes}"


def test_no_node_limit_means_no_node_limit():
    """The default must stay unbounded, or normal play would be capped."""
    ai = _player()
    assert ai._node_limit is None
