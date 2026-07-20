"""Enhanced search: null-move reversibility, determinism, and tactics parity
between the baseline and enhanced configs."""

import config
from ai.minimax import SearchConfig, Searcher
from engine.game_state import GameState
from engine.move_generator import generate_moves
from engine.pieces import Animal, Color

BLUE = int(Color.BLUE)
BLACK = int(Color.BLACK)


def S(c, r):
    return c * config.ROWS + r


def test_make_undo_null_is_reversible():
    gs = GameState()
    h0, tm0 = gs.hash, gs.to_move
    gs.make_null()
    assert gs.to_move != tm0
    assert gs.hash != h0
    gs.undo_null()
    assert gs.to_move == tm0
    assert gs.hash == h0
    assert gs.board.sq == GameState().board.sq   # board untouched


def _mate_in_one():
    gs = GameState()
    gs.setup_position(
        {(3, 1): (BLUE, Animal.RAT), (0, 0): (BLACK, Animal.ELEPHANT),
         (6, 8): (BLACK, Animal.LION)},
        to_move=BLUE,
    )
    return gs


def test_both_configs_find_the_den_dash():
    for cfg in (SearchConfig.baseline(), SearchConfig.enhanced()):
        s = Searcher(cfg)
        move = s.search(_mate_in_one(), depth=4)
        assert move.to == S(3, 0), f"config {cfg} missed the mate-in-one"


def test_enhanced_takes_a_free_capture():
    gs = GameState()
    gs.setup_position({(3, 4): (BLUE, Animal.LION), (3, 5): (BLACK, Animal.CAT)}, to_move=BLUE)
    move = Searcher(SearchConfig.enhanced()).search(gs, depth=4)
    assert move.to == S(3, 5) and move.captured != 0


def test_node_limited_search_is_deterministic():
    # Same config + node budget + position -> identical move (required for the
    # reproducible strength harness).
    def pick():
        return Searcher(SearchConfig.enhanced(), max_nodes=8000).search(GameState())
    m1, m2 = pick(), pick()
    assert (m1.frm, m1.to) == (m2.frm, m2.to)


def test_node_limited_returns_a_legal_move():
    gs = GameState()
    move = Searcher(SearchConfig.enhanced(), max_nodes=6000).search(gs)
    legal = generate_moves(gs.board, gs.to_move)
    assert any(m.frm == move.frm and m.to == move.to for m in legal)


def test_baseline_is_deterministic_too():
    def pick():
        return Searcher(SearchConfig.baseline(), max_nodes=8000).search(GameState())
    m1, m2 = pick(), pick()
    assert (m1.frm, m1.to) == (m2.frm, m2.to)
