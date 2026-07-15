"""Board evaluation function for Jungle AI."""

from __future__ import annotations

from config import (
    COLS, ROWS,
    DEN_BLACK, DEN_BLUE, TRAPS_BLACK, TRAPS_BLUE,
    TERRAIN, TERRAIN_RIVER,
    PIECE_VALUES, EVAL_WEIGHTS, PST_TABLE,
)
from engine.pieces import Color, piece_id_color
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


def _orth_friendly_adjacent(board, c: int, r: int, color: Color) -> bool:
    """True if *color* has a piece orthogonally adjacent to (c, r)."""
    for dc, dr in _DIRS:
        nc, nr = c + dc, r + dr
        if 0 <= nc < COLS and 0 <= nr < ROWS:
            p = board.get(nc, nr)
            if p != 0 and piece_id_color(p) == color:
                return True
    return False


def _den_threat_level(board, color: Color) -> int:
    """Danger to *color*'s den from the opponent.

    Counts enemy pieces sitting on a den-approach square (a trap orthogonally
    adjacent to the den — one step from entering). The weight is higher when no
    friendly piece is adjacent to recapture (an enemy on our trap has rank 0, so
    any adjacent friendly piece can take it). This is additive to the pure
    den-proximity gradient: it expresses whether the approach is *defended*.
    """
    den_c, den_r = _OWN_DEN[color]
    own_traps = TRAPS_BLUE if color == Color.BLUE else TRAPS_BLACK
    opponent = Color.BLACK if color == Color.BLUE else Color.BLUE
    danger = 0
    for (tc, tr) in own_traps:
        if abs(tc - den_c) + abs(tr - den_r) != 1:
            continue  # only den-adjacent traps are entry approaches
        occ = board.get(tc, tr)
        if occ != 0 and piece_id_color(occ) == opponent:
            danger += 1 if _orth_friendly_adjacent(board, tc, tr, color) else 3
    return danger


def evaluate(state, color: Color, cfg=None) -> int:
    """Evaluate board from *color*'s perspective. Higher = better for color.

    *cfg* is an optional :class:`ai.search_config.SearchConfig` gating the
    enhancement terms (PST, den-threat). When ``None`` all terms are enabled.
    """
    winner = state.get_winner()
    if winner is not None:
        return _INF if winner == color else -_INF

    # Drawn position: explicit zero.
    if state.is_50_move_draw():
        return 0

    return _evaluate_core(state, color, cfg)


def evaluate_nonterminal(state, color: Color, cfg=None) -> int:
    """Static evaluation without the terminal-position detection.

    ``evaluate`` calls ``state.get_winner()``, which runs a full legal-move
    generation just to detect the (rare) no-moves stalemate — doubling the
    cost of every quiescence leaf. Hot search paths that have already ruled
    out an explicit result (``state.result is None``) use this variant
    instead. A true stalemate leaf then evaluates by material rather than as
    a loss; that inaccuracy is confined to the ``use_fast_movegen`` paths.
    """
    if state.is_50_move_draw():
        return 0
    return _evaluate_core(state, color, cfg)


def _evaluate_core(state, color: Color, cfg) -> int:
    """The static evaluation terms (no terminal checks).

    ANTISYMMETRY INVARIANT: every per-piece term is computed from the piece's
    OWN color (added for own pieces, subtracted for opponent pieces), never
    from the evaluating side's perspective, so that
    ``evaluate(BLUE) == -evaluate(BLACK)`` for any position.
    """
    board = state.board
    opponent = Color.BLACK if color == Color.BLUE else Color.BLUE

    # Local bindings for the hot per-piece loops.
    get = board.get
    terrain = TERRAIN
    pst_table = PST_TABLE
    piece_values = PIECE_VALUES
    dirs = _DIRS
    cols = COLS
    rows = ROWS
    jump_table_get = _JUMP_TABLE.get

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
    pst_w = EVAL_WEIGHTS["pst"]

    use_pst = True if cfg is None else cfg.use_pst
    use_den_threat = True if cfg is None else cfg.use_den_threat

    my_is_blue = color == Color.BLUE
    enemy_elephant_pid = -8 if my_is_blue else 8
    own_elephant_pid = 8 if my_is_blue else -8

    my_pieces = board.pieces_of(color)
    opp_pieces = board.pieces_of(opponent)

    our_traps = TRAPS_BLUE if my_is_blue else TRAPS_BLACK
    their_traps = TRAPS_BLACK if my_is_blue else TRAPS_BLUE

    score = 0
    my_mobility = 0
    opp_mobility = 0

    # 1. Material + positional + mobility + trap control — own pieces
    for pid, (c, r) in my_pieces.items():
        rank = pid if pid > 0 else -pid
        score += piece_values[rank]
        adv = (rows - 1 - r) if my_is_blue else r
        score += adv * adv_w
        if adv > _MIDLINE:
            score += (adv - _MIDLINE) * adv_accel
        if use_pst:
            score += pst_table[adv][c] * pst_w

        dist = abs(c - opp_den_c) + abs(r - opp_den_r)
        if dist <= den_max:
            score += (den_max + 1 - dist) * den_step

        # Den defender
        own_dist = abs(c - own_den_c) + abs(r - own_den_r)
        if own_dist <= 2:
            score += den_def

        is_rat = rank == 1
        if is_rat and terrain[c][r] == TERRAIN_RIVER:
            score += rat_water + rat_blocks

        # Mobility (cheap approximation: adjacent empty/enemy squares) and
        # the rat-hunts-elephant adjacency, in one neighbor scan.
        for dc, dr in dirs:
            nc = c + dc
            nr = r + dr
            if 0 <= nc < cols and 0 <= nr < rows:
                t = get(nc, nr)
                if t == 0 or (t > 0) != my_is_blue:
                    my_mobility += 1
                if is_rat and t == enemy_elephant_pid:
                    score += rat_near_ele

        if rank == 7 or rank == 6:  # Lion / Tiger: jump-square readiness
            if jump_table_get((c, r)):
                score += jump_ready

        if (c, r) in their_traps:
            score -= trap_bonus

    # 2. Mirror — opponent pieces
    for pid, (c, r) in opp_pieces.items():
        rank = pid if pid > 0 else -pid
        score -= piece_values[rank]
        adv = r if my_is_blue else (rows - 1 - r)
        score -= adv * adv_w
        if adv > _MIDLINE:
            score -= (adv - _MIDLINE) * adv_accel
        if use_pst:
            score -= pst_table[adv][c] * pst_w

        dist = abs(c - own_den_c) + abs(r - own_den_r)
        if dist <= den_max:
            score -= (den_max + 1 - dist) * den_step

        opp_own_dist = abs(c - opp_den_c) + abs(r - opp_den_r)
        if opp_own_dist <= 2:
            score -= den_def

        is_rat = rank == 1
        if is_rat and terrain[c][r] == TERRAIN_RIVER:
            score -= rat_water + rat_blocks

        for dc, dr in dirs:
            nc = c + dc
            nr = r + dr
            if 0 <= nc < cols and 0 <= nr < rows:
                t = get(nc, nr)
                if t == 0 or (t > 0) == my_is_blue:
                    opp_mobility += 1
                if is_rat and t == own_elephant_pid:
                    score -= rat_near_ele

        if rank == 7 or rank == 6:
            if jump_table_get((c, r)):
                score -= jump_ready

        if (c, r) in our_traps:
            score += trap_bonus

    # 3. Mobility difference
    score += (my_mobility - opp_mobility) * mob_w

    # 4. Tempo (small bonus for side to move)
    if state.turn == color:
        score += tempo
    else:
        score -= tempo

    # 5. Den threat / safety: penalize undefended enemy pieces on our den
    #    approaches, reward the mirror. Additive to den-proximity (adds defense
    #    awareness). Computed per-own-color so it stays antisymmetric.
    if use_den_threat:
        dt_w = EVAL_WEIGHTS["den_threat"]
        score -= dt_w * _den_threat_level(board, color)
        score += dt_w * _den_threat_level(board, opponent)

    return score
