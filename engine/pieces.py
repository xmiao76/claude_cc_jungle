"""Piece and color types, plus the compact integer encoding used on the board.

A board square holds a small integer *code*:

    EMPTY == 0
    code  == (color << 4) | animal      # animal is 1..8, color is 0/1

This keeps make/unmake and Zobrist hashing allocation-free while ``Piece`` /
``Color`` / ``Animal`` give readable names to callers and tests.
"""

from __future__ import annotations

from enum import IntEnum
from typing import NamedTuple


class Color(IntEnum):
    BLUE = 0    # bottom side; moves first
    BLACK = 1   # top side

    @property
    def opponent(self) -> Color:
        return Color.BLACK if self is Color.BLUE else Color.BLUE


class Animal(IntEnum):
    RAT = 1
    CAT = 2
    DOG = 3
    WOLF = 4
    LEOPARD = 5
    TIGER = 6
    LION = 7
    ELEPHANT = 8


class Piece(NamedTuple):
    color: Color
    animal: Animal


EMPTY = 0

# Single-character labels (debug / ASCII rendering). Rank number is drawn in the GUI.
ANIMAL_LETTER = {
    Animal.RAT: "R", Animal.CAT: "C", Animal.DOG: "D", Animal.WOLF: "W",
    Animal.LEOPARD: "P", Animal.TIGER: "T", Animal.LION: "L", Animal.ELEPHANT: "E",
}

ANIMAL_NAME = {
    Animal.RAT: "rat", Animal.CAT: "cat", Animal.DOG: "dog", Animal.WOLF: "wolf",
    Animal.LEOPARD: "leopard", Animal.TIGER: "tiger", Animal.LION: "lion",
    Animal.ELEPHANT: "elephant",
}


def make_code(color: int, animal: int) -> int:
    """Encode a (color, animal) pair into a board code."""
    return (color << 4) | animal


def code_color(code: int) -> int:
    return code >> 4


def code_animal(code: int) -> int:
    return code & 0x0F


def decode(code: int) -> Piece | None:
    """Return a ``Piece`` for a non-empty code, else ``None``."""
    if code == EMPTY:
        return None
    return Piece(Color(code >> 4), Animal(code & 0x0F))
