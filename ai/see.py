"""Static exchange evaluation (SEE) for Jungle.

Estimates the material a capture wins or loses by playing out the sequence of
recaptures on the target square, always recapturing with the least-valuable
piece that is *legally* able to (rank / water / trap rules, via
:func:`engine.rules.can_capture`). Used to order captures and to prune losing
captures in the quiescence search.

Only orthogonally adjacent recapturers are considered (Lion/Tiger jump
recaptures are ignored) — a small, well-understood approximation that covers
the overwhelming majority of tactical exchanges.
"""

from __future__ import annotations

from config import NEIGHBORS, PIECE_VALUES
from engine.rules import can_capture


def see(board, frm: int, to: int) -> int:
    """Return the net material (in PIECE_VALUES units) of capturing on ``to``
    with the piece on ``frm``, from the moving side's perspective.

    Positive = the capture wins material; negative = it loses material.
    """
    sq = board.sq
    victim = sq[to]
    if victim == 0:
        return 0
    attacker = sq[frm]

    gain = [PIECE_VALUES[victim & 0x0F]]
    occ_val = PIECE_VALUES[attacker & 0x0F]
    occ_animal = attacker & 0x0F
    occ_color = attacker >> 4
    used = {frm}
    side = occ_color ^ 1                     # opponent recaptures first

    while True:
        # Least-valuable `side` piece adjacent to `to` that may capture the occupant.
        best_sq = -1
        best_val = 1 << 30
        best_animal = 0
        for nsq in NEIGHBORS[to]:
            if nsq in used:
                continue
            code = sq[nsq]
            if code == 0 or (code >> 4) != side:
                continue
            a_animal = code & 0x0F
            if not can_capture(side, a_animal, nsq, occ_color, occ_animal, to):
                continue
            v = PIECE_VALUES[a_animal]
            if v < best_val:
                best_val = v
                best_sq = nsq
                best_animal = a_animal
        if best_sq < 0:
            break
        gain.append(occ_val - gain[-1])
        occ_val = best_val
        occ_animal = best_animal
        occ_color = side
        used.add(best_sq)
        side ^= 1

    # Minimax the swap list back: each side stops capturing once it is unprofitable.
    for i in range(len(gain) - 2, -1, -1):
        gain[i] = -max(-gain[i], gain[i + 1])
    return gain[0]
