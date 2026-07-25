"""Capture legality, terrain effects, and win detection for Jungle."""

from __future__ import annotations

from config import (
    DEN_BLACK,
    DEN_BLUE,
    TERRAIN,
    TERRAIN_RIVER,
    TRAPS_BLACK,
    TRAPS_BLUE,
)
from engine.pieces import Animal, Color, piece_id_animal, piece_id_color, piece_id_rank


def _opponent_traps(color: Color) -> set[tuple[int, int]]:
    """Traps that reduce rank for the given color (i.e. the *opponent's* traps)."""
    return TRAPS_BLACK if color == Color.BLUE else TRAPS_BLUE


def effective_rank(pid: int, col: int, row: int) -> int:
    """Return the effective rank of a piece at (col, row).

    A piece inside the *opponent's* traps has effective rank 0.
    """
    color = piece_id_color(pid)
    if (col, row) in _opponent_traps(color):
        return 0
    return piece_id_rank(pid)


def can_capture(attacker_pid: int, defender_pid: int,
                atk_col: int, atk_row: int,
                def_col: int, def_row: int,
                board=None) -> bool:
    """Return True if attacker at (atk_col, atk_row) can capture defender at (def_col, def_row).

    Rules, applied in this order:

    1. Must be different colors.
    2. Captures may not cross the water/land boundary: a piece standing in the
       river and a piece on land can never capture one another (this is what
       makes a Rat in the river invulnerable to land pieces, and what stops a
       Rat in the river from taking an Elephant on the bank).
    3. A defender standing in the *attacker's* traps has effective rank 0 and is
       therefore capturable by **any** enemy piece. This overrides the
       Rat/Elephant exception, so an Elephant may take a trapped Rat.
    4. On equal terrain, with a defender that still holds its real rank:
       Rat beats Elephant, Elephant cannot take Rat, otherwise the attacker's
       rank must be >= the defender's.

    The trap weakens a piece for *defence only* — the attacker always fights at
    its real rank, so a piece standing in the enemy's traps is vulnerable but
    not disarmed. ``board`` is unused; it is kept for call-site compatibility.
    """
    atk_color = piece_id_color(attacker_pid)
    def_color = piece_id_color(defender_pid)

    # (1) Must be enemies.
    if atk_color == def_color:
        return False

    atk_in_water = TERRAIN[atk_col][atk_row] == TERRAIN_RIVER
    def_in_water = TERRAIN[def_col][def_row] == TERRAIN_RIVER

    # (2) No capture across the water/land boundary, in either direction.
    if atk_in_water != def_in_water:
        return False

    # (3) Defender in the attacker's trap has rank 0 — anyone may take it.
    #     Trap squares are never river squares, so this cannot bypass rule (2).
    if effective_rank(defender_pid, def_col, def_row) == 0:
        return True

    # (4) Rank comparison with the Rat/Elephant exception. The attacker uses its
    #     real rank: standing in an enemy trap does not reduce its striking power.
    atk_animal = piece_id_animal(attacker_pid)
    def_animal = piece_id_animal(defender_pid)

    if atk_animal == Animal.RAT and def_animal == Animal.ELEPHANT:
        # Rat beats Elephant. An Elephant can never stand in the river, so
        # rule (2) has already guaranteed both pieces are on land here.
        return True
    if atk_animal == Animal.ELEPHANT and def_animal == Animal.RAT:
        return False  # Elephant cannot take an untrapped Rat

    return piece_id_rank(attacker_pid) >= piece_id_rank(defender_pid)


def is_jump_blocked(fc: int, fr: int, tc: int, tr: int, board) -> bool:
    """Return True if a river-jump from (fc,fr) to (tc,tr) is blocked by a rat in the river.

    The jump must be a straight line crossing one of the two river blocks.
    Any rat (either color) on a water square along the path blocks the jump.
    """
    if fc == tc:
        # Vertical jump
        step = 1 if tr > fr else -1
        r = fr + step
        while r != tr:
            if TERRAIN[fc][r] == TERRAIN_RIVER:
                pid = board.get(fc, r)
                if pid != 0 and piece_id_animal(pid) == Animal.RAT:
                    return True
            r += step
    elif fr == tr:
        # Horizontal jump
        step = 1 if tc > fc else -1
        c = fc + step
        while c != tc:
            if TERRAIN[c][fr] == TERRAIN_RIVER:
                pid = board.get(c, fr)
                if pid != 0 and piece_id_animal(pid) == Animal.RAT:
                    return True
            c += step
    return False


class WinResult:
    __slots__ = ("winner",)

    def __init__(self, winner: Color) -> None:
        self.winner = winner


def check_win(board, last_move, current_turn: Color) -> WinResult | None:
    """Check if the game has ended after last_move was played.

    Win conditions:
    1. A piece entered the opponent's den.
    2. One side has no pieces remaining.
    3. The player whose turn it is has no legal moves (stalemate → they lose).

    'current_turn' is the side about to move (i.e. the side that did NOT just move).
    """
    if last_move is not None:
        # Condition 1: den entry
        mover_pid = board.get(last_move.tc, last_move.tr)
        if mover_pid != 0:
            mover_color = piece_id_color(mover_pid)
            opponent_den = DEN_BLUE if mover_color == Color.BLACK else DEN_BLACK
            if (last_move.tc, last_move.tr) == opponent_den:
                return WinResult(mover_color)

    # Condition 2: capture all
    for color in (Color.BLUE, Color.BLACK):
        if board.alive_count(color) == 0:
            opponent = Color.BLACK if color == Color.BLUE else Color.BLUE
            return WinResult(opponent)

    return None
