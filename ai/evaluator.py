"""Board evaluation function for Jungle AI."""

from __future__ import annotations

from config import (
    COLS, ROWS,
    DEN_BLACK, DEN_BLUE, TRAPS_BLACK, TRAPS_BLUE,
    TERRAIN, TERRAIN_RIVER,
    PIECE_VALUES, EVAL_WEIGHTS,
)
from engine.pieces import Animal, Color, piece_id_animal

_OPPONENT_DEN = {
    Color.BLUE: DEN_BLACK,
    Color.BLACK: DEN_BLUE,
}

_OWN_DEN = {
    Color.BLUE: DEN_BLUE,
    Color.BLACK: DEN_BLACK,
}

_INF = 10_000_000


def _advancement(color: Color, row: int) -> int:
    return (ROWS - 1 - row) if color == Color.BLUE else row


def evaluate(state, color: Color) -> int:
    """Evaluate board from *color*'s perspective. Higher = better for color."""
    board = state.board
    opponent = Color.BLACK if color == Color.BLUE else Color.BLUE

    winner = state.get_winner()
    if winner is not None:
        return _INF if winner == color else -_INF

    score = 0

    opp_den_c, opp_den_r = _OPPONENT_DEN[color]
    own_den_c, own_den_r = _OWN_DEN[color]

    adv_w = EVAL_WEIGHTS["advancement_per_row"]
    den_max = EVAL_WEIGHTS["den_proximity_max_dist"]
    den_step = EVAL_WEIGHTS["den_proximity_per_step"]
    rat_water = EVAL_WEIGHTS["rat_in_water"]
    rat_near_ele = EVAL_WEIGHTS["rat_adjacent_to_enemy_elephant"]
    trap_bonus = EVAL_WEIGHTS["trap_control"]

    enemy_elephant_pid = -int(Animal.ELEPHANT) if color == Color.BLUE else int(Animal.ELEPHANT)

    my_pieces = board.pieces_of(color)
    opp_pieces = board.pieces_of(opponent)

    # 1. Material + positional — own pieces
    for pid, (c, r) in my_pieces.items():
        animal = piece_id_animal(pid)
        score += PIECE_VALUES[int(animal)]
        score += _advancement(color, r) * adv_w

        dist = abs(c - opp_den_c) + abs(r - opp_den_r)
        if dist <= den_max:
            score += (den_max + 1 - dist) * den_step

        if animal == Animal.RAT:
            if TERRAIN[c][r] == TERRAIN_RIVER:
                score += rat_water
            for dc, dr in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nc, nr = c + dc, r + dr
                if 0 <= nc < COLS and 0 <= nr < ROWS:
                    if board.get(nc, nr) == enemy_elephant_pid:
                        score += rat_near_ele

    # 2. Material + positional — opponent pieces
    for pid, (c, r) in opp_pieces.items():
        animal = piece_id_animal(pid)
        score -= PIECE_VALUES[int(animal)]
        score -= _advancement(opponent, r) * adv_w

        dist = abs(c - own_den_c) + abs(r - own_den_r)
        if dist <= den_max:
            score -= (den_max + 1 - dist) * den_step

    # 3. Trap control: opponent piece in our traps = effectively rank 0
    our_traps = TRAPS_BLUE if color == Color.BLUE else TRAPS_BLACK
    for pid, (c, r) in opp_pieces.items():
        if (c, r) in our_traps:
            score += trap_bonus

    return score
