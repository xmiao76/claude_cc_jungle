"""Board evaluation function for Jungle AI."""

from __future__ import annotations

from config import (
    COLS, ROWS,
    DEN_BLACK, DEN_BLUE, TRAPS_BLACK, TRAPS_BLUE,
    TERRAIN, TERRAIN_RIVER,
    PIECE_VALUES, EVAL_WEIGHTS,
)
from engine.pieces import Animal, Color, piece_id_animal
from engine.move_generator import _JUMP_TABLE

_OPPONENT_DEN = {
    Color.BLUE: DEN_BLACK,
    Color.BLACK: DEN_BLUE,
}

_OWN_DEN = {
    Color.BLUE: DEN_BLUE,
    Color.BLACK: DEN_BLACK,
}

_INF = 10_000_000

_DIRS = ((0, 1), (0, -1), (1, 0), (-1, 0))
_MIDLINE = ROWS // 2  # row 4


def _advancement(color: Color, row: int) -> int:
    return (ROWS - 1 - row) if color == Color.BLUE else row


def _pseudo_mobility(board, color: Color) -> int:
    """Cheap mobility approximation: count adjacent empty/capturable squares.

    Doesn't validate full capture legality (jumps, rat/elephant rules) — used
    only as a proxy in evaluation, not for move generation.
    """
    count = 0
    for pid, (c, r) in board.pieces_of(color).items():
        for dc, dr in _DIRS:
            nc, nr = c + dc, r + dr
            if not (0 <= nc < COLS and 0 <= nr < ROWS):
                continue
            target = board.get(nc, nr)
            if target == 0:
                count += 1
            elif (target > 0) != (color == Color.BLUE):
                count += 1
    return count


def _has_jump_available(board, c: int, r: int) -> bool:
    """True if Lion/Tiger at (c,r) has at least one unblocked jump endpoint."""
    return bool(_JUMP_TABLE.get((c, r)))


def evaluate(state, color: Color) -> int:
    """Evaluate board from *color*'s perspective. Higher = better for color."""
    board = state.board
    opponent = Color.BLACK if color == Color.BLUE else Color.BLUE

    winner = state.get_winner()
    if winner is not None:
        return _INF if winner == color else -_INF

    # Drawn position: explicit zero.
    if state.is_50_move_draw():
        return 0

    score = 0

    opp_den_c, opp_den_r = _OPPONENT_DEN[color]
    own_den_c, own_den_r = _OWN_DEN[color]

    adv_w = EVAL_WEIGHTS["advancement_per_row"]
    den_max = EVAL_WEIGHTS["den_proximity_max_dist"]
    den_step = EVAL_WEIGHTS["den_proximity_per_step"]
    rat_water = EVAL_WEIGHTS["rat_in_water"]
    rat_near_ele = EVAL_WEIGHTS["rat_adjacent_to_enemy_elephant"]
    trap_bonus = EVAL_WEIGHTS["trap_control"]
    den_def = EVAL_WEIGHTS["den_defender"]
    jump_ready = EVAL_WEIGHTS["jump_ready"]
    rat_blocks = EVAL_WEIGHTS["rat_blocks_river"]
    adv_accel = EVAL_WEIGHTS["advancement_acceleration"]
    tempo = EVAL_WEIGHTS["tempo"]
    mob_w = EVAL_WEIGHTS["mobility"]
    threat_w = EVAL_WEIGHTS["threat"]

    enemy_elephant_pid = -int(Animal.ELEPHANT) if color == Color.BLUE else int(Animal.ELEPHANT)

    my_pieces = board.pieces_of(color)
    opp_pieces = board.pieces_of(opponent)

    # 1. Material + positional — own pieces
    for pid, (c, r) in my_pieces.items():
        animal = piece_id_animal(pid)
        score += PIECE_VALUES[int(animal)]
        adv = _advancement(color, r)
        score += adv * adv_w
        if adv > _MIDLINE:
            score += (adv - _MIDLINE) * adv_accel

        dist = abs(c - opp_den_c) + abs(r - opp_den_r)
        if dist <= den_max:
            score += (den_max + 1 - dist) * den_step

        # Den defender
        own_dist = abs(c - own_den_c) + abs(r - own_den_r)
        if own_dist <= 2:
            score += den_def

        if animal == Animal.RAT:
            if TERRAIN[c][r] == TERRAIN_RIVER:
                score += rat_water + rat_blocks
            for dc, dr in _DIRS:
                nc, nr = c + dc, r + dr
                if 0 <= nc < COLS and 0 <= nr < ROWS:
                    if board.get(nc, nr) == enemy_elephant_pid:
                        score += rat_near_ele

        if animal in (Animal.LION, Animal.TIGER):
            if _has_jump_available(board, c, r):
                score += jump_ready

    # 2. Material + positional — opponent pieces
    own_elephant_pid = int(Animal.ELEPHANT) if color == Color.BLUE else -int(Animal.ELEPHANT)
    for pid, (c, r) in opp_pieces.items():
        animal = piece_id_animal(pid)
        score -= PIECE_VALUES[int(animal)]
        adv = _advancement(opponent, r)
        score -= adv * adv_w
        if adv > _MIDLINE:
            score -= (adv - _MIDLINE) * adv_accel

        dist = abs(c - own_den_c) + abs(r - own_den_r)
        if dist <= den_max:
            score -= (den_max + 1 - dist) * den_step

        opp_own_dist = abs(c - opp_den_c) + abs(r - opp_den_r)
        if opp_own_dist <= 2:
            score -= den_def

        if animal == Animal.RAT:
            if TERRAIN[c][r] == TERRAIN_RIVER:
                score -= rat_water + rat_blocks
            for dc, dr in _DIRS:
                nc, nr = c + dc, r + dr
                if 0 <= nc < COLS and 0 <= nr < ROWS:
                    if board.get(nc, nr) == own_elephant_pid:
                        score -= rat_near_ele

        if animal in (Animal.LION, Animal.TIGER):
            if _has_jump_available(board, c, r):
                score -= jump_ready

    # 3. Trap control: opponent piece in our traps = effectively rank 0
    our_traps = TRAPS_BLUE if color == Color.BLUE else TRAPS_BLACK
    their_traps = TRAPS_BLACK if color == Color.BLUE else TRAPS_BLUE
    for pid, (c, r) in opp_pieces.items():
        if (c, r) in our_traps:
            score += trap_bonus
    for pid, (c, r) in my_pieces.items():
        if (c, r) in their_traps:
            score -= trap_bonus

    # 4. Mobility (cheap approximation)
    score += (_pseudo_mobility(board, color) - _pseudo_mobility(board, opponent)) * mob_w

    # 5. Tempo (small bonus for side to move)
    if state.turn == color:
        score += tempo
    else:
        score -= tempo

    # Threat term intentionally folded into mobility/trap/material to keep
    # eval cheap; threat_w retained for future tuning. Reserve a tiny use:
    # bonus for our pieces adjacent to enemy higher-rank pieces (pressure).
    if threat_w:
        for pid, (c, r) in my_pieces.items():
            for dc, dr in _DIRS:
                nc, nr = c + dc, r + dr
                if 0 <= nc < COLS and 0 <= nr < ROWS:
                    target = board.get(nc, nr)
                    if target != 0 and ((target > 0) != (color == Color.BLUE)):
                        score += threat_w
        for pid, (c, r) in opp_pieces.items():
            for dc, dr in _DIRS:
                nc, nr = c + dc, r + dr
                if 0 <= nc < COLS and 0 <= nr < ROWS:
                    target = board.get(nc, nr)
                    if target != 0 and ((target > 0) == (color == Color.BLUE)):
                        score -= threat_w

    return score
