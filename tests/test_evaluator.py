"""Tests for ai/evaluator.py."""

from ai.evaluator import _INF, evaluate
from config import (
    EVAL_WEIGHTS,
    PIECE_VALUES,
    TRAPS_BLUE,
)
from engine.game_state import GameState
from engine.pieces import Animal, Color
from tests.helpers import make_gs


def test_evaluate_starting_position_is_symmetric():
    """Initial position is mirror-symmetric in material; eval from either side
    should be near zero and exact negatives of each other."""
    gs = GameState()
    gs.new_game()
    blue = evaluate(gs, Color.BLUE)
    black = evaluate(gs, Color.BLACK)
    assert blue == -black


def test_evaluate_material_advantage():
    """An extra Elephant should swing the eval by at least its piece value."""
    # Both sides have a Lion; Blue also has an Elephant deep in its half.
    gs = make_gs(
        (0, 8, Color.BLUE, Animal.LION),
        (3, 5, Color.BLUE, Animal.ELEPHANT),
        (0, 0, Color.BLACK, Animal.LION),
    )
    score = evaluate(gs, Color.BLUE)
    assert score >= PIECE_VALUES[int(Animal.ELEPHANT)] - 200  # generous floor


def test_evaluate_trap_control_bonus():
    """Opposing piece in our trap is worth EVAL_WEIGHTS['trap_control'] extra.

    Evaluated with den-threat and PST disabled to isolate the trap-control term:
    every Blue trap is also a den-approach square, so the den-threat term would
    otherwise dominate this contrived position.
    """
    from dataclasses import replace

    from ai.search_config import strong_config
    cfg = replace(strong_config(), use_den_threat=False, use_pst=False)
    trap = next(iter(TRAPS_BLUE))
    base = make_gs(
        (0, 0, Color.BLUE, Animal.RAT),
        (6, 0, Color.BLACK, Animal.WOLF),
    )
    trapped = make_gs(
        (0, 0, Color.BLUE, Animal.RAT),
        (trap[0], trap[1], Color.BLACK, Animal.WOLF),
    )
    delta = evaluate(trapped, Color.BLUE, cfg) - evaluate(base, Color.BLUE, cfg)
    # delta includes trap bonus minus any positional swing for moving the wolf
    assert delta >= EVAL_WEIGHTS["trap_control"] - 200


def test_evaluate_den_proximity_gradient():
    """Closer to the enemy den should score higher for the side moving in."""
    near = make_gs((3, 1, Color.BLUE, Animal.WOLF))   # 1 step from black den (3,0)
    far = make_gs((3, 5, Color.BLUE, Animal.WOLF))    # 5 steps away
    assert evaluate(near, Color.BLUE) > evaluate(far, Color.BLUE)


def test_evaluate_rat_in_water_bonus():
    """Rat sitting in a river square earns the rat-in-water bonus."""
    in_water = make_gs((1, 3, Color.BLUE, Animal.RAT))   # (1,3) is river
    on_land = make_gs((0, 3, Color.BLUE, Animal.RAT))    # (0,3) is land
    assert evaluate(in_water, Color.BLUE) - evaluate(on_land, Color.BLUE) \
        >= EVAL_WEIGHTS["rat_in_water"] - 50


def test_evaluate_symmetry_random_midgame():
    """For any non-terminal position, eval(BLUE) must equal -eval(BLACK)."""
    gs = make_gs(
        (3, 4, Color.BLUE, Animal.TIGER),
        (3, 5, Color.BLACK, Animal.WOLF),
        (3, 6, Color.BLACK, Animal.LION),
        (0, 8, Color.BLUE, Animal.ELEPHANT),
        (6, 0, Color.BLACK, Animal.CAT),
        (1, 3, Color.BLUE, Animal.RAT),     # in the river
    )
    gs.turn = Color.BLUE
    assert evaluate(gs, Color.BLUE) == -evaluate(gs, Color.BLACK)


def test_evaluate_is_purely_static():
    """`evaluate` must not score terminal positions — that is the search's job.

    It used to return ±_INF for a decided position. Because _INF is *larger* than
    the mate band (`ai.minimax._MATE`), such a score outranked every real mate,
    broke mate-distance preference, and was stored in the TT outside the
    alpha/beta window. It also forced a `legal_moves()` call on every evaluation.
    Mate scores now come only from the search, which knows the ply.
    """
    from engine.rules import WinResult

    gs = make_gs((3, 0, Color.BLUE, Animal.WOLF))   # Wolf already in black den
    gs.result = WinResult(Color.BLUE)

    blue = evaluate(gs, Color.BLUE)
    assert abs(blue) < _INF, "evaluate must not emit the alpha/beta sentinel"
    assert blue == -evaluate(gs, Color.BLACK), "antisymmetry must still hold"


def test_search_scores_a_decided_position_as_a_mate():
    """The mate score must come from the search, inside the mate band."""
    from ai.minimax import _MATE, _MATE_BOUND, AIPlayer

    gs = make_gs(
        (3, 1, Color.BLUE, Animal.WOLF),    # one step from Black's den
        (0, 0, Color.BLACK, Animal.LION),
    )
    gs.turn = Color.BLUE
    ai = AIPlayer(Color.BLUE, 2)
    score = ai._negamax_root(gs, 2, -_INF, _INF)

    assert score >= _MATE_BOUND, f"one-move den win should score as a mate, got {score}"
    assert score <= _MATE, "mate scores must stay inside the mate band, below _INF"


# ---------------------------------------------------------------------------
# Piece-square tables (Task 5) — must preserve the symmetry invariant
# ---------------------------------------------------------------------------

def test_pst_table_is_column_symmetric():
    """No left/right bias: PST[adv][c] == PST[adv][COLS-1-c]."""
    from config import COLS, PST_TABLE, ROWS
    for adv in range(ROWS):
        for c in range(COLS):
            assert PST_TABLE[adv][c] == PST_TABLE[adv][COLS - 1 - c]


def test_pst_keeps_start_eval_balanced():
    """Column-symmetric PST contributes exactly 0 at the symmetric start."""
    from dataclasses import replace

    from ai.search_config import strong_config
    gs = GameState()
    gs.new_game()
    cfg_on = strong_config()
    cfg_off = replace(cfg_on, use_pst=False)
    assert evaluate(gs, Color.BLUE, cfg_on) == evaluate(gs, Color.BLUE, cfg_off)


def test_eval_symmetry_holds_under_all_configs():
    """eval(BLUE) == -eval(BLACK) must hold with PST on, off, and default."""
    from ai.search_config import baseline_config, strong_config
    gs = make_gs(
        (3, 4, Color.BLUE, Animal.TIGER),
        (1, 5, Color.BLACK, Animal.WOLF),
        (3, 6, Color.BLACK, Animal.LION),
        (0, 8, Color.BLUE, Animal.RAT),
        (6, 0, Color.BLACK, Animal.CAT),
        (5, 2, Color.BLUE, Animal.LEOPARD),
    )
    gs.turn = Color.BLUE
    for cfg in (strong_config(), baseline_config(), None):
        assert evaluate(gs, Color.BLUE, cfg) == -evaluate(gs, Color.BLACK, cfg)


def test_pst_changes_eval():
    """Enabling the PST changes the score of an off-center vs central piece."""
    from dataclasses import replace

    from ai.search_config import strong_config
    cfg_on = strong_config()
    cfg_off = replace(cfg_on, use_pst=False)
    gs = make_gs((3, 6, Color.BLUE, Animal.WOLF))   # central file
    assert evaluate(gs, Color.BLUE, cfg_on) > evaluate(gs, Color.BLUE, cfg_off)


# ---------------------------------------------------------------------------
# Den threat / safety (Task 6) — must preserve the symmetry invariant
# ---------------------------------------------------------------------------

def test_den_threat_symmetry():
    """eval(BLUE) == -eval(BLACK) with the den-threat term active."""
    from ai.search_config import strong_config
    gs = make_gs(
        (3, 7, Color.BLACK, Animal.WOLF),   # on a blue den-approach trap
        (0, 0, Color.BLUE, Animal.RAT),
    )
    gs.turn = Color.BLUE
    cfg = strong_config()
    assert evaluate(gs, Color.BLUE, cfg) == -evaluate(gs, Color.BLACK, cfg)


def test_den_threat_penalizes_undefended_approach():
    """An undefended enemy on our den approach lowers our eval (vs term off)."""
    from dataclasses import replace

    from ai.search_config import strong_config
    gs = make_gs(
        (3, 7, Color.BLACK, Animal.WOLF),   # blue den-approach (3,8) neighbor, undefended
        (0, 0, Color.BLUE, Animal.RAT),
    )
    gs.turn = Color.BLUE
    cfg_on = strong_config()
    cfg_off = replace(cfg_on, use_den_threat=False)
    assert evaluate(gs, Color.BLUE, cfg_on) < evaluate(gs, Color.BLUE, cfg_off)
