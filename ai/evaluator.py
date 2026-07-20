"""Static position evaluation.

``evaluate(state)`` returns a score from the side-to-move's perspective (as
negamax expects). The default (non-PST) path is O(1): the board keeps its
Blue-perspective static score incrementally (``board.eval_score``, the sum of
``config.CONTRIB`` over occupied squares), so leaves cost a single read instead
of a full-board rescan. The ``use_pst`` path adds a piece-square-table term and
is a full recompute — kept only for ablation (self-play showed PST is a net
negative, so the shipped engine leaves it off).

The score is *antisymmetric*: mirroring the position negates it, and the
symmetric start evaluates to 0, keeping the AI unbiased between sides.
"""

from __future__ import annotations

from config import (
    ADV_BLACK,
    ADV_BLUE,
    CONTRIB,
    DIST_TO_BLACK_DEN,
    DIST_TO_BLUE_DEN,
    EVAL_WEIGHTS,
    HAS_JUMP,
    HAS_JUMP_TIGER,
    IS_RIVER,
    NUM_SQUARES,
    PIECE_VALUES,
    PST_BLACK,
    PST_BLUE,
    PST_WEIGHT,
)
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
_PST_W = PST_WEIGHT


def _blue_score_pst(board) -> int:
    """Full Blue-perspective recompute including the PST term (ablation path)."""
    score = 0
    sq = board.sq
    for s, code in enumerate(sq):
        if code == 0:
            continue
        animal = code & 0x0F
        val = PIECE_VALUES[animal]
        if animal == _LION:
            jumpish = HAS_JUMP[s]
        elif animal == _TIGER:
            jumpish = HAS_JUMP_TIGER[s]
        else:
            jumpish = False
        ratish = animal == _RAT and IS_RIVER[s]
        if code >> 4 == _BLUE:
            score += val + ADV_BLUE[s] * _ADV_W
            d = DIST_TO_BLACK_DEN[s]
            if d <= _DEN_MAX:
                score += (_DEN_MAX - d) * _DEN_W
            if jumpish:
                score += _JUMP_W
            if ratish:
                score += _RIVER_W
            score += PST_BLUE[s] * _PST_W
        else:
            score -= val + ADV_BLACK[s] * _ADV_W
            d = DIST_TO_BLUE_DEN[s]
            if d <= _DEN_MAX:
                score -= (_DEN_MAX - d) * _DEN_W
            if jumpish:
                score -= _JUMP_W
            if ratish:
                score -= _RIVER_W
            score -= PST_BLACK[s] * _PST_W
    return score


def _blue_score(board, use_pst: bool = False) -> int:
    """Blue-perspective static score. Non-PST path is a fast CONTRIB sum that
    equals ``board.eval_score`` (also used to validate the incremental score)."""
    if use_pst:
        return _blue_score_pst(board)
    sq = board.sq
    c = CONTRIB
    total = 0
    for s in range(NUM_SQUARES):
        code = sq[s]
        if code:
            total += c[code][s]
    return total


def evaluate(state, use_pst: bool = False) -> int:
    """Score from the side-to-move's perspective (negamax convention)."""
    blue = _blue_score_pst(state.board) if use_pst else state.board.eval_score
    return blue if state.to_move == _BLUE else -blue
