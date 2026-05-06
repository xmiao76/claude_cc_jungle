"""Tests for ai/evaluator.py."""

from engine.board import Board
from engine.game_state import GameState
from engine.pieces import Animal, Color, make_piece_id
from ai.evaluator import evaluate, _INF
from config import (
    DEN_BLACK, DEN_BLUE, TRAPS_BLACK, TRAPS_BLUE,
    PIECE_VALUES, EVAL_WEIGHTS,
)


def make_gs(*piece_specs) -> GameState:
    gs = GameState()
    gs.board = Board()
    for (c, r, color, animal) in piece_specs:
        pid = make_piece_id(color, animal)
        gs.board._grid[c][r] = pid
        gs.board._piece_positions[int(color)][pid] = (c, r)
    return gs


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
    """Opposing piece in our trap is worth EVAL_WEIGHTS['trap_control'] extra."""
    trap = next(iter(TRAPS_BLUE))
    base = make_gs(
        (0, 0, Color.BLUE, Animal.RAT),
        (6, 0, Color.BLACK, Animal.WOLF),
    )
    trapped = make_gs(
        (0, 0, Color.BLUE, Animal.RAT),
        (trap[0], trap[1], Color.BLACK, Animal.WOLF),
    )
    delta = evaluate(trapped, Color.BLUE) - evaluate(base, Color.BLUE)
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
        (0, 8, Color.BLUE, Animal.RAT),
        (6, 0, Color.BLACK, Animal.CAT),
        (1, 3, Color.BLUE, Animal.RAT),
    )
    gs.turn = Color.BLUE
    assert evaluate(gs, Color.BLUE) == -evaluate(gs, Color.BLACK)


def test_evaluate_terminal_returns_inf():
    """When the game is decided, eval returns +/- _INF."""
    gs = make_gs((3, 0, Color.BLUE, Animal.WOLF))   # Wolf already in black den
    # Force terminal via the result hook by simulating apply_move semantics:
    from engine.rules import WinResult
    gs.result = WinResult(Color.BLUE)
    assert evaluate(gs, Color.BLUE) == _INF
    assert evaluate(gs, Color.BLACK) == -_INF
