"""Static Exchange Evaluation (SEE) for Jungle captures.

Returns the net material gain of a capture sequence on the target square,
assuming both sides recapture with the lowest-rank legal attacker available.
Used by the AI to filter losing captures in quiescence and to order captures
in the main search.
"""

from __future__ import annotations

from config import TERRAIN, TERRAIN_RIVER, PIECE_VALUES
from engine.board import Board, Move
from engine.pieces import Animal, Color, piece_id_color, piece_id_animal, piece_id_rank
from engine.rules import can_capture
from engine.move_generator import _JUMP_TABLE


_DIRS = ((0, -1), (0, 1), (-1, 0), (1, 0))


def _piece_value(pid: int) -> int:
    return PIECE_VALUES[piece_id_animal(pid)]


def _attackers_to(board: Board, tc: int, tr: int, color: Color) -> list[tuple[int, int, int]]:
    """Return list of (col, row, pid) for *color*'s pieces that could legally
    capture a defender on (tc, tr). Considers normal step and Lion/Tiger jumps."""
    out: list[tuple[int, int, int]] = []
    target_pid = board.get(tc, tr)

    for pid, (c, r) in board.pieces_of(color).items():
        animal = piece_id_animal(pid)

        # Adjacency (one cardinal step)
        if abs(c - tc) + abs(r - tr) == 1:
            target_terrain = TERRAIN[tc][tr]
            # Only Rat may enter river
            if target_terrain == TERRAIN_RIVER and animal != Animal.RAT:
                continue
            if target_pid != 0 and can_capture(pid, target_pid, c, r, tc, tr, board):
                out.append((c, r, pid))
            elif target_pid == 0:
                # Empty target — not a capturer in this context.
                pass
            continue

        # Lion / Tiger jumps
        if animal not in (Animal.LION, Animal.TIGER):
            continue
        for (dc, dr, lc, lr) in _JUMP_TABLE.get((c, r), []):
            if (lc, lr) != (tc, tr):
                continue
            if animal == Animal.TIGER and dc == 0:
                continue  # Tiger cannot make vertical jump
            # Rat in river blocks
            blocked = False
            if dc == 0:
                step = 1 if lr > r else -1
                rr = r + step
                while rr != lr:
                    if TERRAIN[c][rr] == TERRAIN_RIVER:
                        pp = board.get(c, rr)
                        if pp != 0 and piece_id_animal(pp) == Animal.RAT:
                            blocked = True
                            break
                    rr += step
            else:
                step = 1 if lc > c else -1
                cc = c + step
                while cc != lc:
                    if TERRAIN[cc][r] == TERRAIN_RIVER:
                        pp = board.get(cc, r)
                        if pp != 0 and piece_id_animal(pp) == Animal.RAT:
                            blocked = True
                            break
                    cc += step
            if blocked:
                continue
            if target_pid != 0 and can_capture(pid, target_pid, c, r, tc, tr, board):
                out.append((c, r, pid))
    return out


def see_capture(board: Board, move: Move) -> int:
    """Static Exchange Evaluation for a capture move.

    Returns net material gain (positive = good for attacker side) assuming
    optimal recapture sequence using lowest-rank legal attacker each time.
    Approximation: treats traps and jumps but not chained tactical motifs.
    """
    if not move.captured:
        return 0

    attacker_pid = board.get(move.fc, move.fr)
    if attacker_pid == 0:
        return 0
    attacker_color = piece_id_color(attacker_pid)
    defender_color = Color.BLACK if attacker_color == Color.BLUE else Color.BLUE

    tc, tr = move.tc, move.tr

    gain = [_piece_value(move.captured)]

    # Simulate the capture; piece on target is now the original attacker.
    on_square_pid = attacker_pid

    # Apply temporary board state by tracking a "removed" set so we don't mutate.
    removed: set[tuple[int, int]] = {(move.fc, move.fr)}

    side = defender_color
    while True:
        attackers = _live_attackers_on(board, tc, tr, side, removed, on_square_pid)
        if not attackers:
            break
        # Pick the lowest-rank legal attacker.
        attackers.sort(key=lambda t: piece_id_rank(t[2]))
        ac, ar, apid = attackers[0]
        gain.append(_piece_value(on_square_pid))
        removed.add((ac, ar))
        on_square_pid = apid
        side = Color.BLACK if side == Color.BLUE else Color.BLUE

    # Backward propagation: at each step the side can stop or recapture,
    # whichever is better. value[i] = gain[i] - max(0, value[i+1]).
    for i in range(len(gain) - 2, -1, -1):
        gain[i] = gain[i] - max(0, gain[i + 1])
    return gain[0]


def _live_attackers_on(board: Board, tc: int, tr: int, color: Color,
                       removed: set[tuple[int, int]],
                       current_target_pid: int) -> list[tuple[int, int, int]]:
    """Like _attackers_to but skips squares in *removed* and treats the
    target square as occupied by *current_target_pid* (so capture legality
    is computed against the most recent recapturer)."""
    out: list[tuple[int, int, int]] = []
    target_pid = current_target_pid

    for pid, (c, r) in board.pieces_of(color).items():
        if (c, r) in removed:
            continue
        animal = piece_id_animal(pid)

        if abs(c - tc) + abs(r - tr) == 1:
            target_terrain = TERRAIN[tc][tr]
            if target_terrain == TERRAIN_RIVER and animal != Animal.RAT:
                continue
            if can_capture(pid, target_pid, c, r, tc, tr, board):
                out.append((c, r, pid))
            continue

        if animal not in (Animal.LION, Animal.TIGER):
            continue
        for (dc, dr, lc, lr) in _JUMP_TABLE.get((c, r), []):
            if (lc, lr) != (tc, tr):
                continue
            if animal == Animal.TIGER and dc == 0:
                continue
            blocked = False
            if dc == 0:
                step = 1 if lr > r else -1
                rr = r + step
                while rr != lr:
                    if TERRAIN[c][rr] == TERRAIN_RIVER:
                        pp = board.get(c, rr)
                        if pp != 0 and (c, rr) not in removed \
                                and piece_id_animal(pp) == Animal.RAT:
                            blocked = True
                            break
                    rr += step
            else:
                step = 1 if lc > c else -1
                cc = c + step
                while cc != lc:
                    if TERRAIN[cc][r] == TERRAIN_RIVER:
                        pp = board.get(cc, r)
                        if pp != 0 and (cc, r) not in removed \
                                and piece_id_animal(pp) == Animal.RAT:
                            blocked = True
                            break
                    cc += step
            if blocked:
                continue
            if can_capture(pid, target_pid, c, r, tc, tr, board):
                out.append((c, r, pid))
    return out
