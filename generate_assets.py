"""Generate all game art and sound assets programmatically.

Run once (``python generate_assets.py``) to (re)create everything under
``gui/assets/``. Nothing here is third-party: every sprite, tile, icon, and
sound is drawn or synthesised in code, so the release ships no placeholder or
borrowed art.

  pieces/ : 16 animal tokens (each animal x {blue, black})
  tiles/  : land / river / trap / den textures + window icon (png + ico)
  sounds/ : move / capture / win effects (16-bit PCM WAV)
"""

from __future__ import annotations

import io
import math
import os
import struct
import wave

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # headless: no window needed

import pygame  # noqa: E402

from engine.pieces import ANIMAL_NAME, Animal  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = os.path.dirname(os.path.abspath(__file__))
PIECES_DIR = os.path.join(ROOT, "gui", "assets", "pieces")
TILES_DIR = os.path.join(ROOT, "gui", "assets", "tiles")
SOUNDS_DIR = os.path.join(ROOT, "gui", "assets", "sounds")

PIECE_SIZE = 224
SS = 3                        # supersample factor for anti-aliasing
TILE_SIZE = 128

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

RING = {
    "blue": (58, 118, 220),
    "black": (58, 62, 74),
}
RING_DARK = {
    "blue": (30, 66, 140),
    "black": (24, 26, 34),
}
INK = (38, 32, 28)
WHITE = (248, 246, 240)
PINK = (232, 150, 150)
RED = (206, 74, 66)

FACE_COLOR = {
    Animal.RAT: (176, 178, 184),
    Animal.CAT: (226, 170, 104),
    Animal.DOG: (176, 132, 92),
    Animal.WOLF: (140, 150, 164),
    Animal.LEOPARD: (232, 196, 96),
    Animal.TIGER: (238, 156, 70),
    Animal.LION: (236, 198, 108),
    Animal.ELEPHANT: (170, 172, 178),
}


def _shade(color, factor):
    return tuple(max(0, min(255, int(c * factor))) for c in color[:3])


# ---------------------------------------------------------------------------
# Shape helpers (operate on the supersampled surface)
# ---------------------------------------------------------------------------


def _circle(surf, color, center, r, width=0):
    pygame.draw.circle(surf, color, (int(center[0]), int(center[1])), int(r), width)


def _ellipse(surf, color, rect, width=0):
    pygame.draw.ellipse(surf, color, pygame.Rect(*[int(v) for v in rect]), width)


def _poly(surf, color, pts, width=0):
    pygame.draw.polygon(surf, color, [(int(x), int(y)) for x, y in pts], width)


def _eyes(surf, cx, cy, r):
    dx = r * 0.42
    ey = cy - r * 0.12
    er = r * 0.17
    for sx in (-dx, dx):
        _circle(surf, WHITE, (cx + sx, ey), er)
        _circle(surf, INK, (cx + sx, ey), er * 0.62)
        _circle(surf, WHITE, (cx + sx - er * 0.2, ey - er * 0.2), er * 0.22)


def _nose(surf, cx, cy, r, color=INK):
    _poly(surf, color, [(cx - r * 0.16, cy + r * 0.18),
                        (cx + r * 0.16, cy + r * 0.18),
                        (cx, cy + r * 0.36)])


def _whiskers(surf, cx, cy, r):
    y = cy + r * 0.24
    for sign in (-1, 1):
        base = cx + sign * r * 0.18
        for k in (-1, 0, 1):
            pygame.draw.line(surf, _shade(INK, 1.6), (base, y + k * r * 0.02),
                             (cx + sign * r * 0.95, y + k * r * 0.22), max(2, int(r * 0.03)))


# ---------------------------------------------------------------------------
# Ears (drawn before the face disc so they peek out)
# ---------------------------------------------------------------------------


def _ears_round(surf, cx, cy, r, color):
    for sx in (-1, 1):
        _circle(surf, color, (cx + sx * r * 0.62, cy - r * 0.72), r * 0.34)
        _circle(surf, _shade(color, 0.8), (cx + sx * r * 0.62, cy - r * 0.72), r * 0.34, max(2, int(r * 0.03)))


def _ears_pointed(surf, cx, cy, r, color, tall=1.0):
    for sx in (-1, 1):
        bx = cx + sx * r * 0.5
        _poly(surf, color, [(bx - r * 0.28, cy - r * 0.5),
                            (bx + r * 0.28, cy - r * 0.5),
                            (bx + sx * r * 0.08, cy - r * (0.5 + 0.6 * tall))])


def _ears_floppy(surf, cx, cy, r, color):
    for sx in (-1, 1):
        _ellipse(surf, _shade(color, 0.82),
                 (cx + sx * r * 0.72 - r * 0.28, cy - r * 0.5, r * 0.56, r * 1.05))


def _ears_big(surf, cx, cy, r, color):   # elephant
    for sx in (-1, 1):
        _ellipse(surf, _shade(color, 0.9),
                 (cx + sx * r * 0.7 - r * 0.5, cy - r * 0.55, r * 1.0, r * 1.25))


def _mane(surf, cx, cy, r, color):        # lion
    tufts = 16
    outer = r * 1.34
    for i in range(tufts):
        a = 2 * math.pi * i / tufts
        _circle(surf, color, (cx + math.cos(a) * outer, cy + math.sin(a) * outer), r * 0.32)
    _circle(surf, _shade(color, 0.86), (cx, cy), r * 1.16)


# ---------------------------------------------------------------------------
# Per-animal feature painters (drawn on top of the face disc)
# ---------------------------------------------------------------------------


def _feat_rat(surf, cx, cy, r):
    _eyes(surf, cx, cy, r)
    _circle(surf, PINK, (cx, cy + r * 0.26), r * 0.12)
    # buck teeth
    pygame.draw.rect(surf, WHITE, pygame.Rect(int(cx - r * 0.14), int(cy + r * 0.34), int(r * 0.12), int(r * 0.24)))
    pygame.draw.rect(surf, WHITE, pygame.Rect(int(cx + r * 0.02), int(cy + r * 0.34), int(r * 0.12), int(r * 0.24)))
    _whiskers(surf, cx, cy, r)


def _feat_cat(surf, cx, cy, r):
    _eyes(surf, cx, cy, r)
    _nose(surf, cx, cy, r, PINK)
    _whiskers(surf, cx, cy, r)


def _feat_dog(surf, cx, cy, r):
    _eyes(surf, cx, cy, r)
    _circle(surf, INK, (cx, cy + r * 0.24), r * 0.15)
    # tongue
    _ellipse(surf, RED, (cx - r * 0.12, cy + r * 0.4, r * 0.24, r * 0.34))


def _feat_wolf(surf, cx, cy, r):
    # angled fierce brows
    for sx in (-1, 1):
        pygame.draw.line(surf, INK, (cx + sx * r * 0.2, cy - r * 0.34),
                         (cx + sx * r * 0.62, cy - r * 0.16), max(3, int(r * 0.06)))
    _eyes(surf, cx, cy, r)
    _nose(surf, cx, cy, r)
    _poly(surf, _shade(FACE_COLOR[Animal.WOLF], 0.85),
          [(cx - r * 0.2, cy + r * 0.3), (cx + r * 0.2, cy + r * 0.3), (cx, cy + r * 0.62)])


def _feat_leopard(surf, cx, cy, r):
    _eyes(surf, cx, cy, r)
    _nose(surf, cx, cy, r)
    spots = [(-0.55, -0.35), (0.55, -0.35), (-0.62, 0.2), (0.62, 0.2), (-0.3, 0.55), (0.3, 0.55)]
    for sx, sy in spots:
        _circle(surf, _shade(INK, 1.4), (cx + sx * r, cy + sy * r), r * 0.1, max(2, int(r * 0.03)))


def _feat_tiger(surf, cx, cy, r):
    ink = _shade(INK, 1.2)
    # forehead + cheek stripes
    for sx in (-1, 1):
        pygame.draw.line(surf, ink, (cx + sx * r * 0.16, cy - r * 0.66),
                         (cx + sx * r * 0.24, cy - r * 0.28), max(3, int(r * 0.06)))
        pygame.draw.line(surf, ink, (cx + sx * r * 0.5, cy - r * 0.5),
                         (cx + sx * r * 0.62, cy - r * 0.12), max(3, int(r * 0.06)))
        pygame.draw.line(surf, ink, (cx + sx * r * 0.55, cy + r * 0.16),
                         (cx + sx * r * 0.9, cy + r * 0.2), max(3, int(r * 0.05)))
    _eyes(surf, cx, cy, r)
    _nose(surf, cx, cy, r)
    _whiskers(surf, cx, cy, r)


def _feat_lion(surf, cx, cy, r):
    _eyes(surf, cx, cy, r)
    _nose(surf, cx, cy, r)
    pygame.draw.line(surf, INK, (cx, cy + r * 0.34), (cx, cy + r * 0.56), max(3, int(r * 0.05)))


def _feat_elephant(surf, cx, cy, r):
    _eyes(surf, cx - r * 0.06, cy - r * 0.05, r * 0.9)
    # trunk down the middle
    trunk = _shade(FACE_COLOR[Animal.ELEPHANT], 0.9)
    pts = [(cx - r * 0.16, cy + r * 0.05), (cx + r * 0.16, cy + r * 0.05),
           (cx + r * 0.2, cy + r * 0.55), (cx + r * 0.34, cy + r * 0.82),
           (cx + r * 0.1, cy + r * 0.9), (cx - r * 0.02, cy + r * 0.6)]
    _poly(surf, trunk, pts)
    # tusks
    for sx in (-1, 1):
        _poly(surf, WHITE, [(cx + sx * r * 0.22, cy + r * 0.3),
                            (cx + sx * r * 0.34, cy + r * 0.36),
                            (cx + sx * r * 0.2, cy + r * 0.66)])


EARS = {
    Animal.RAT: lambda s, x, y, r, c: _ears_round(s, x, y, r, c),
    Animal.CAT: lambda s, x, y, r, c: _ears_pointed(s, x, y, r, c),
    Animal.DOG: lambda s, x, y, r, c: _ears_floppy(s, x, y, r, c),
    Animal.WOLF: lambda s, x, y, r, c: _ears_pointed(s, x, y, r, c, tall=1.3),
    Animal.LEOPARD: lambda s, x, y, r, c: _ears_round(s, x, y, r, c),
    Animal.TIGER: lambda s, x, y, r, c: _ears_round(s, x, y, r, c),
    Animal.LION: lambda s, x, y, r, c: _mane(s, x, y, r, _shade(c, 0.82)),
    Animal.ELEPHANT: lambda s, x, y, r, c: _ears_big(s, x, y, r, c),
}

FEATURES = {
    Animal.RAT: _feat_rat, Animal.CAT: _feat_cat, Animal.DOG: _feat_dog,
    Animal.WOLF: _feat_wolf, Animal.LEOPARD: _feat_leopard, Animal.TIGER: _feat_tiger,
    Animal.LION: _feat_lion, Animal.ELEPHANT: _feat_elephant,
}


# ---------------------------------------------------------------------------
# Piece token
# ---------------------------------------------------------------------------


def draw_piece(animal: Animal, owner: str, font: pygame.font.Font) -> pygame.Surface:
    s = PIECE_SIZE * SS
    surf = pygame.Surface((s, s), pygame.SRCALPHA)
    cx = cy = s / 2
    r_token = s * 0.45

    # drop shadow
    _circle(surf, (0, 0, 0, 70), (cx + s * 0.02, cy + s * 0.03), r_token)
    # ring / body
    _circle(surf, RING_DARK[owner], (cx, cy), r_token)
    _circle(surf, RING[owner], (cx, cy), r_token * 0.93)
    _circle(surf, _shade(RING[owner], 1.18), (cx, cy - r_token * 0.12), r_token * 0.62)
    _circle(surf, RING[owner], (cx, cy), r_token * 0.8)

    face = FACE_COLOR[animal]
    r_face = s * 0.3
    EARS[animal](surf, cx, cy - r_face * 0.1, r_face, face)
    _circle(surf, face, (cx, cy), r_face)
    _circle(surf, _shade(face, 0.8), (cx, cy), r_face, max(2, int(s * 0.008)))
    FEATURES[animal](surf, cx, cy, r_face)

    # rank badge (bottom)
    br = s * 0.13
    bx, by = cx, cy + r_token * 0.72
    _circle(surf, WHITE, (bx, by), br)
    _circle(surf, RING_DARK[owner], (bx, by), br, max(2, int(s * 0.01)))
    label = font.render(str(int(animal)), True, RING_DARK[owner])
    label = pygame.transform.smoothscale(
        label, (int(label.get_width() * br * 1.3 / label.get_height()), int(br * 1.3)))
    surf.blit(label, (bx - label.get_width() / 2, by - label.get_height() / 2))

    return pygame.transform.smoothscale(surf, (PIECE_SIZE, PIECE_SIZE))


# ---------------------------------------------------------------------------
# Terrain tiles
# ---------------------------------------------------------------------------


def _rng(seed):
    state = seed & 0xFFFFFFFF

    def nxt():
        nonlocal state
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        return state / 0x7FFFFFFF
    return nxt


def tile_land() -> pygame.Surface:
    t = TILE_SIZE
    surf = pygame.Surface((t, t))
    surf.fill((150, 190, 104))
    rnd = _rng(7)
    for _ in range(220):
        x, y = int(rnd() * t), int(rnd() * t)
        shade = 150 + int(rnd() * 40) - 20
        surf.set_at((x, y), (min(255, shade), min(255, shade + 40), 104))
    return surf


def tile_river() -> pygame.Surface:
    t = TILE_SIZE
    surf = pygame.Surface((t, t))
    surf.fill((74, 144, 202))
    for i in range(0, t, 14):
        pts = [(x, i + 6 * math.sin(x / 12.0)) for x in range(0, t + 1, 6)]
        pygame.draw.lines(surf, (110, 176, 224), False, [(int(x), int(y)) for x, y in pts], 3)
    return surf


def tile_trap() -> pygame.Surface:
    t = TILE_SIZE
    surf = pygame.Surface((t, t))
    surf.fill((198, 142, 66))
    pygame.draw.rect(surf, (150, 100, 44), surf.get_rect(), 6)
    for a, b in (((14, 14), (t - 14, t - 14)), ((t - 14, 14), (14, t - 14))):
        pygame.draw.line(surf, (150, 100, 44), a, b, 6)
    return surf


def tile_den(owner: str) -> pygame.Surface:
    t = TILE_SIZE
    surf = pygame.Surface((t, t))
    surf.fill((214, 176, 70))
    accent = RING["blue"] if owner == "blue" else RING["black"]
    pygame.draw.rect(surf, accent, surf.get_rect(), 8)
    cx = t // 2
    # simple crown
    base = t * 0.55
    pts = [(t * 0.24, base), (t * 0.24, t * 0.34), (t * 0.38, t * 0.5),
           (cx, t * 0.28), (t * 0.62, t * 0.5), (t * 0.76, t * 0.34), (t * 0.76, base)]
    pygame.draw.polygon(surf, (120, 90, 30), [(int(x), int(y)) for x, y in pts])
    pygame.draw.rect(surf, (120, 90, 30), pygame.Rect(int(t * 0.24), int(base), int(t * 0.52), int(t * 0.12)))
    return surf


def make_icon(font: pygame.font.Font) -> pygame.Surface:
    icon = pygame.Surface((256, 256), pygame.SRCALPHA)
    pygame.draw.circle(icon, (150, 190, 104), (128, 128), 124)
    pygame.draw.circle(icon, (74, 144, 202), (128, 128), 124, 14)
    tiger = draw_piece(Animal.TIGER, "blue", font)
    tiger = pygame.transform.smoothscale(tiger, (196, 196))
    icon.blit(tiger, (30, 30))
    return icon


def write_ico(surface: pygame.Surface, path: str) -> None:
    """Write a 64x64 .ico that embeds a PNG image (ICO supports PNG payloads)."""
    img = pygame.transform.smoothscale(surface, (64, 64))
    buf = io.BytesIO()
    pygame.image.save(img, buf, "icon.png")
    png = buf.getvalue()
    with open(path, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, 1))                 # ICONDIR
        f.write(struct.pack("<BBBBHHII", 64, 64, 0, 0, 1, 32, len(png), 22))
        f.write(png)


# ---------------------------------------------------------------------------
# Sounds (16-bit PCM WAV, synthesised)
# ---------------------------------------------------------------------------

_RATE = 22050


def _write_wav(path: str, samples: list[float]) -> None:
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_RATE)
        frames = bytearray()
        for s in samples:
            v = int(max(-1.0, min(1.0, s)) * 32000)
            frames += struct.pack("<h", v)
        w.writeframes(bytes(frames))


def _tone(freq, ms, decay=6.0, vol=0.5, shape="sine"):
    n = int(_RATE * ms / 1000)
    out = []
    for i in range(n):
        t = i / _RATE
        env = math.exp(-decay * t)
        if shape == "square":
            val = 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0
        else:
            val = math.sin(2 * math.pi * freq * t)
        out.append(val * env * vol)
    return out


def sound_move():
    return _tone(660, 70, decay=22, vol=0.35) + _tone(440, 40, decay=26, vol=0.2)


def sound_capture():
    base = _tone(150, 200, decay=10, vol=0.55, shape="square")
    rnd = _rng(99)
    for i in range(len(base)):
        base[i] += (rnd() * 2 - 1) * 0.25 * math.exp(-16 * i / _RATE)
    return base


def sound_win():
    out = []
    for f in (523, 659, 784, 1046):
        out += _tone(f, 130, decay=5, vol=0.4)
    return out


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    pygame.init()
    pygame.font.init()
    font = pygame.font.SysFont("arialblack,arial", 120, bold=True)

    for d in (PIECES_DIR, TILES_DIR, SOUNDS_DIR):
        os.makedirs(d, exist_ok=True)

    for animal in Animal:
        for owner in ("blue", "black"):
            surf = draw_piece(animal, owner, font)
            name = ANIMAL_NAME[animal]
            pygame.image.save(surf, os.path.join(PIECES_DIR, f"{name}_{owner}.png"))
    print(f"  pieces: {len(list(Animal)) * 2} sprites")

    pygame.image.save(tile_land(), os.path.join(TILES_DIR, "land.png"))
    pygame.image.save(tile_river(), os.path.join(TILES_DIR, "river.png"))
    pygame.image.save(tile_trap(), os.path.join(TILES_DIR, "trap.png"))
    pygame.image.save(tile_den("blue"), os.path.join(TILES_DIR, "den_blue.png"))
    pygame.image.save(tile_den("black"), os.path.join(TILES_DIR, "den_black.png"))
    icon = make_icon(font)
    pygame.image.save(icon, os.path.join(TILES_DIR, "icon.png"))
    write_ico(icon, os.path.join(TILES_DIR, "icon.ico"))
    print("  tiles: land/river/trap/den + icon")

    _write_wav(os.path.join(SOUNDS_DIR, "move.wav"), sound_move())
    _write_wav(os.path.join(SOUNDS_DIR, "capture.wav"), sound_capture())
    _write_wav(os.path.join(SOUNDS_DIR, "win.wav"), sound_win())
    print("  sounds: move/capture/win")

    pygame.quit()
    print("Assets generated under gui/assets/.")


if __name__ == "__main__":
    main()
