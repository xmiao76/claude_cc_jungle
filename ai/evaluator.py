"""Static position evaluation.

``evaluate(state)`` returns a score in Blue-material units from the perspective
of the side to move (positive = good for the mover), as negamax expects.

The underlying ``_blue_score`` is *antisymmetric*: mirroring the position
(swap colors and flip rows) negates it, and the symmetric starting position
evaluates to exactly 0. This keeps the AI unbiased between the two sides.
"""

from __future__ import annotations

from config import (
    ADV_BLACK,
    ADV_BLUE,
    DIST_TO_BLACK_DEN,
    DIST_TO_BLUE_DEN,
    EVAL_WEIGHTS,
    IS_RIVER,
    PIECE_VALUES,
)
from engine.move_generator import HAS_JUMP, HAS_JUMP_TIGER
from engine.pieces import Animal, Color

_RAT = int(Animal.RAT)
_TIGER = int(Animal.TIGER)
_LION = int(Animal.LION)
_BLUE = int(Color.BLUE)

_ADV_W = EVAL_WEIGHTS["advancement_per_row"]
_DEN_W = EVAL_WEIGHTS["den_proximity_per_step"]
_DEN_MAX = EVAL_WEIGHTS["den_proximity_max_dist"]
_JUMP_W = EVAL_WEIGHTS["jump_ready"]
_RIVER_W = EVAL_WEIGHTS["rat_blocks_river"]


def _blue_score(board) -> int:
    """Static evaluation from Blue's perspective (positive favors Blue)."""
    score = 0
    sq = board.sq
    for s, code in enumerate(sq):
        if code == 0:
            continue
        animal = code & 0x0F
        val = PIECE_VALUES[animal]
        # Jump-readiness: the Lion may make either crossing; the Tiger only the
        # 3-col one, so it must use the Tiger-specific proxy (else it is credited
        # for a 4-row jump it can never make).
        if animal == _LION:
            jumpish = HAS_JUMP[s]
        elif animal == _TIGER:
            jumpish = HAS_JUMP_TIGER[s]
        else:
            jumpish = False
        ratish = animal == _RAT and IS_RIVER[s]
        if code >> 4 == _BLUE:
            score += val
            score += ADV_BLUE[s] * _ADV_W
            d = DIST_TO_BLACK_DEN[s]
            if d <= _DEN_MAX:
                score += (_DEN_MAX - d) * _DEN_W
            if jumpish:
                score += _JUMP_W
            if ratish:
                score += _RIVER_W
        else:
            score -= val
            score -= ADV_BLACK[s] * _ADV_W
            d = DIST_TO_BLUE_DEN[s]
            if d <= _DEN_MAX:
                score -= (_DEN_MAX - d) * _DEN_W
            if jumpish:
                score -= _JUMP_W
            if ratish:
                score -= _RIVER_W
    return score


def evaluate(state) -> int:
    """Score from the side-to-move's perspective (negamax convention)."""
    blue = _blue_score(state.board)
    return blue if state.to_move == _BLUE else -blue
