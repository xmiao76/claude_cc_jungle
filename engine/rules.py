"""Capture legality and river-jump blocking.

All rule interpretations follow the project's documented ruleset (see README
and prompt.md). The functions here are pure: they take primitive ``(color,
animal, square)`` values so both the move generator and the AI can call them
without constructing objects.
"""

from __future__ import annotations

from config import IS_RIVER, TRAP_OWNER
from engine.pieces import Animal

_RAT = int(Animal.RAT)
_ELEPHANT = int(Animal.ELEPHANT)


def is_trapped(color: int, square: int) -> bool:
    """True if a piece of ``color`` standing on ``square`` is in an *enemy* trap
    (its effective rank becomes 0)."""
    owner = TRAP_OWNER[square]
    return owner != -1 and owner != color


def can_capture(
    atk_color: int, atk_animal: int, atk_sq: int,
    def_color: int, def_animal: int, def_sq: int,
) -> bool:
    """Return True if the attacker may capture the defender.

    Assumes the attacker can actually reach ``def_sq`` (adjacency / a valid
    jump landing) and that the two pieces are of opposite colors — the move
    generator guarantees both before calling.

    Rules applied, in order:
      1. Captures may not cross the water/land boundary (a piece in the river
         and a piece on land can never capture one another).
      2. A defender standing in the attacker's trap has rank 0 -> always
         capturable (this overrides the Rat/Elephant exception, so an Elephant
         may take a trapped Rat).
      3. On equal terrain: Rat beats Elephant, Elephant cannot take Rat,
         otherwise the attacker must rank >= the defender.
    """
    atk_water = IS_RIVER[atk_sq]
    def_water = IS_RIVER[def_sq]

    # (1) No capture across the water/land boundary.
    if atk_water != def_water:
        return False

    # (2) Defender trapped in the attacker's home traps -> rank 0.
    if is_trapped(def_color, def_sq):
        return True

    # (3) Rank comparison with the Rat/Elephant special case.
    if atk_animal == _RAT and def_animal == _ELEPHANT:
        return True
    if atk_animal == _ELEPHANT and def_animal == _RAT:
        return False
    return atk_animal >= def_animal


def is_jump_blocked(river_path: tuple[int, ...], board) -> bool:
    """True if any Rat (either color) occupies a river square along ``river_path``.

    A Rat sitting in the water on the leap's path blocks the Lion/Tiger jump.
    """
    sq = board.sq
    for s in river_path:
        code = sq[s]
        if code != 0 and (code & 0x0F) == _RAT:
            return True
    return False
