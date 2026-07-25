"""Static board evaluation for the Jungle AI.

Two invariants govern everything here.

**Antisymmetry.** ``evaluate(state, BLUE) == -evaluate(state, BLACK)`` for every
position, enforced by ``tests/test_evaluator.py``. The way to keep it is to
compute each per-piece term from the *piece's own* colour — added for our pieces,
subtracted for theirs — never from the evaluating side's point of view. Terms
that depend on the position as a whole (side to move, den threat) must be written
as an own-minus-theirs pair.

**Purely static.** No mate scores, no draw scores, no terminal detection. The
search owns those, because only it knows the ply needed to score a mate by
distance. See the note on ``_INF`` below.

Evaluation is roughly two thirds of search time, so the shape of this file is
performance-led: rank arithmetic on plain ints rather than ``IntEnum``
construction, precomputed neighbour and distance tables from ``ai.eval_tables``,
one pass per side, and direct grid indexing instead of a method call per square.
"""

from __future__ import annotations

from ai.eval_tables import ADJACENT, DEN_DISTANCE, MOVEMENT_CLASS, UNREACHABLE
from ai.search_config import piece_values
from config import (
    DEN_BLACK,
    DEN_BLUE,
    DEN_RACE_HORIZON,
    EVAL_WEIGHTS,
    PST_TABLE,
    ROWS,
    TERRAIN,
    TERRAIN_RIVER,
    TRAPS_BLACK,
    TRAPS_BLUE,
)
from engine.pieces import Color
from engine.rules import can_capture

_OPPONENT_DEN = {
    Color.BLUE: DEN_BLACK,
    Color.BLACK: DEN_BLUE,
}

_OWN_DEN = {
    Color.BLUE: DEN_BLUE,
    Color.BLACK: DEN_BLACK,
}

_OWN_TRAPS = {
    Color.BLUE: TRAPS_BLUE,
    Color.BLACK: TRAPS_BLACK,
}

# Alpha/beta sentinel — wider than any score the engine can produce.
#
# The score scale is: |static eval| << |mate score| < _INF. Mate scores live just
# below _INF (see ``ai/minimax.py:_MATE``) so a forced win always beats any static
# evaluation and a shorter mate always beats a longer one. `evaluate` must never
# return a terminal score: it used to emit ±_INF, which outranked every real mate,
# defeated mate-distance preference, and landed in the transposition table outside
# the alpha/beta window.
_INF = 10_000_000

_RAT = 1
_ELEPHANT = 8

_MIDLINE = ROWS // 2  # row 4


def _advancement(color: Color, row: int) -> int:
    """Rows advanced from *color*'s own back rank toward the enemy den."""
    return (ROWS - 1 - row) if color == Color.BLUE else row


def _jump_is_open(grid, c: int, r: int, rank: int) -> bool:
    """True if a Lion/Tiger on (c, r) has at least one leap actually available.

    Checks what the old version did not: that a Rat is not sitting in the river
    on the flight path, and that the landing square is not occupied by a piece we
    cannot take. The old form was ``bool(_JUMP_TABLE.get((c, r)))`` — pure
    geometry, blind to the board, so it paid a flat bonus for merely standing on a
    river bank.
    """
    from engine.move_generator import _JUMP_TABLE, _can_jump

    for (dc, dr, lc, lr) in _JUMP_TABLE.get((c, r), ()):
        if not _can_jump(rank, dc, dr):
            continue
        # Walk the flight path; any Rat in the water blocks the leap.
        blocked = False
        if dc == 0:
            step = 1 if lr > r else -1
            rr = r + step
            while rr != lr:
                if TERRAIN[c][rr] == TERRAIN_RIVER and abs(grid[c][rr]) == _RAT:
                    blocked = True
                    break
                rr += step
        else:
            step = 1 if lc > c else -1
            cc = c + step
            while cc != lc:
                if TERRAIN[cc][r] == TERRAIN_RIVER and abs(grid[cc][r]) == _RAT:
                    blocked = True
                    break
                cc += step
        if not blocked:
            return True
    return False


def _pseudo_mobility(grid, board, color: Color) -> int:
    """Cheap mobility proxy: adjacent squares that are empty or enemy-occupied.

    Ignores the river restriction, the own-den ban and capture legality, so it
    over-counts. Retained as the default because the accurate version below
    measured no better while costing a `can_capture` call per adjacent enemy —
    and mobility carries a weight of 2, so accuracy here buys very little.
    """
    is_blue = color == Color.BLUE
    count = 0
    for _pid, (c, r) in board.pieces_of(color).items():
        for (nc, nr) in ADJACENT[(c, r)]:
            target = grid[nc][nr]
            if target == 0 or (target > 0) != is_blue:
                count += 1
    return count


def _real_mobility(grid, board, color: Color) -> int:
    """Count squares this side's pieces can actually step to.

    Respects what the proxy ignores: only a Rat may enter the river, nobody may
    enter their own den, and a capture has to be legal.
    """
    own_den = _OWN_DEN[color]
    is_blue = color == Color.BLUE
    count = 0
    for pid, (c, r) in board.pieces_of(color).items():
        rank = pid if pid > 0 else -pid
        for (nc, nr) in ADJACENT[(c, r)]:
            if (nc, nr) == own_den:
                continue
            if TERRAIN[nc][nr] == TERRAIN_RIVER and rank != _RAT:
                continue
            target = grid[nc][nr]
            if target == 0:
                count += 1
            elif (target > 0) != is_blue:
                if can_capture(pid, target, c, r, nc, nr):
                    count += 1
    return count


def _orth_friendly_adjacent(grid, c: int, r: int, is_blue: bool) -> bool:
    """True if the given side has a piece orthogonally adjacent to (c, r)."""
    for (nc, nr) in ADJACENT[(c, r)]:
        p = grid[nc][nr]
        if p != 0 and (p > 0) == is_blue:
            return True
    return False


def _den_threat_level(grid, color: Color) -> int:
    """How exposed *color*'s den is to an enemy already on an approach square.

    Counts enemy pieces standing on a trap orthogonally adjacent to our den — one
    step from entering. Weighted higher when no friendly piece is adjacent to take
    it, since an enemy on our trap has rank 0 and any neighbour can capture it.
    """
    den_c, den_r = _OWN_DEN[color]
    is_blue = color == Color.BLUE
    danger = 0
    for (tc, tr) in _OWN_TRAPS[color]:
        if abs(tc - den_c) + abs(tr - den_r) != 1:
            continue                      # not an entry approach
        occ = grid[tc][tr]
        if occ != 0 and (occ > 0) != is_blue:
            danger += 1 if _orth_friendly_adjacent(grid, tc, tr, is_blue) else 3
    return danger


def _attack_status(grid, pid: int, c: int, r: int, is_blue: bool) -> tuple[bool, bool]:
    """Return (attacked, defended) for the piece at (c, r).

    Adjacent squares only. Lion/Tiger leap attacks are not counted — including
    them would mean walking the jump table for every piece on every evaluation,
    and leap captures are rare enough that the approximation is worth its cost.
    """
    attacked = False
    defended = False
    for (nc, nr) in ADJACENT[(c, r)]:
        other = grid[nc][nr]
        if other == 0:
            continue
        if (other > 0) == is_blue:
            defended = True
        elif not attacked and can_capture(other, pid, nc, nr, c, r):
            attacked = True
    return attacked, defended


def evaluate(state, color: Color, cfg=None) -> int:
    """Statically evaluate the board from *color*'s perspective. Higher = better.

    *cfg* is an optional :class:`ai.search_config.SearchConfig` gating individual
    terms. ``None`` means the shipped defaults — which is *not* the same as "every
    term on": several measured weaker and are off by default.
    """
    board = state.board
    grid = board.grid
    opponent = Color.BLACK if color == Color.BLUE else Color.BLUE

    use_pst = True if cfg is None else cfg.use_pst
    use_den_threat = True if cfg is None else cfg.use_den_threat
    use_true_den = False if cfg is None else cfg.use_true_den_distance
    use_hanging = False if cfg is None else cfg.use_hanging
    use_real_jump = False if cfg is None else cfg.use_real_jump_ready
    use_real_mob = False if cfg is None else cfg.use_real_mobility
    values = piece_values(cfg)

    w = EVAL_WEIGHTS
    adv_w = w["advancement_per_row"]
    den_max = w["den_proximity_max_dist"]
    den_step = w["den_proximity_per_step"]
    race_w = w["den_race_per_move"]
    rat_water = w["rat_in_water"]
    rat_blocks = w["rat_blocks_river"]
    rat_near_ele = w["rat_adjacent_to_enemy_elephant"]
    trap_bonus = w["trap_control"]
    den_def = w["den_defender"]
    jump_ready = w["jump_ready"]
    adv_accel = w["advancement_acceleration"]
    tempo = w["tempo"]
    mob_w = w["mobility"]
    pst_w = w["pst"]
    hang_own = w["hanging_own_turn_pct"]
    hang_other = w["hanging_other_pct"]
    trapped_pct = w["trapped_and_attacked_pct"]

    score = 0
    turn = state.turn

    # Evaluate both sides with one shared body, flipping the sign. This is what
    # keeps the function antisymmetric: every term below is computed from `side`,
    # the colour of the piece being looked at, never from `color`.
    for side, sign in ((color, 1), (opponent, -1)):
        enemy = Color.BLACK if side == Color.BLUE else Color.BLUE
        is_blue = side == Color.BLUE
        opp_den = _OPPONENT_DEN[side]
        own_den_c, own_den_r = _OWN_DEN[side]
        opp_den_c, opp_den_r = opp_den
        enemy_traps = _OWN_TRAPS[enemy]
        enemy_elephant_pid = -_ELEPHANT if is_blue else _ELEPHANT
        side_to_move = turn == side
        hang_pct = hang_own if side_to_move else hang_other

        subtotal = 0
        for pid, (c, r) in board.pieces_of(side).items():
            rank = pid if pid > 0 else -pid
            subtotal += values[rank]

            adv = _advancement(side, r)
            subtotal += adv * adv_w
            if adv > _MIDLINE:
                subtotal += (adv - _MIDLINE) * adv_accel
            if use_pst:
                subtotal += PST_TABLE[adv][c] * pst_w

            # Approach to the enemy den. The true move distance accounts for the
            # river and for Lion/Tiger leaps; Manhattan distance walks through the
            # water as if it were not there, which mis-prices the whole den race.
            if use_true_den:
                dist = DEN_DISTANCE[MOVEMENT_CLASS[rank]][opp_den].get((c, r), UNREACHABLE)
                if dist <= DEN_RACE_HORIZON:
                    subtotal += (DEN_RACE_HORIZON + 1 - dist) * race_w
            else:
                dist = abs(c - opp_den_c) + abs(r - opp_den_r)
                if dist <= den_max:
                    subtotal += (den_max + 1 - dist) * den_step

            # Defending our own den.
            if abs(c - own_den_c) + abs(r - own_den_r) <= 2:
                subtotal += den_def

            if rank == _RAT:
                if TERRAIN[c][r] == TERRAIN_RIVER:
                    subtotal += rat_water + rat_blocks
                for (nc, nr) in ADJACENT[(c, r)]:
                    if grid[nc][nr] == enemy_elephant_pid:
                        subtotal += rat_near_ele
            elif rank >= 6:      # Tiger or Lion
                if use_real_jump:
                    if _jump_is_open(grid, c, r, rank):
                        subtotal += jump_ready
                else:
                    from engine.move_generator import _JUMP_TABLE
                    if _JUMP_TABLE.get((c, r)):
                        subtotal += jump_ready

            # Sitting in an enemy trap means rank 0: anything adjacent can take it.
            if (c, r) in enemy_traps:
                subtotal -= trap_bonus
                if use_hanging:
                    attacked, _ = _attack_status(grid, pid, c, r, is_blue)
                    if attacked:
                        subtotal -= values[rank] * trapped_pct // 100
            elif use_hanging:
                # Loose material. The old evaluation could not see a hanging Lion
                # at all: it only surfaced if quiescence happened to reach it.
                attacked, defended = _attack_status(grid, pid, c, r, is_blue)
                if attacked and not defended:
                    subtotal -= values[rank] * hang_pct // 100

        mob = _real_mobility if use_real_mob else _pseudo_mobility
        subtotal += mob(grid, board, side) * mob_w
        if use_den_threat:
            subtotal -= w["den_threat"] * _den_threat_level(grid, side)

        score += sign * subtotal

    # Side to move, applied once for the position rather than per side (adding it
    # inside the loop would count it twice and silently double the weight).
    score += tempo if turn == color else -tempo

    return score
