"""Generate all game assets (terrain tiles + piece sprites) using pygame drawing.

Run this once to populate gui/assets/tiles/ and gui/assets/pieces/.
This script produces attractive, polished visuals without requiring external images.
"""

import math
import os

import pygame

from gui.fonts import safe_sysfont

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TILE_SIZE = 80
PIECE_SIZE = 80
SPRITE_INNER = 62  # drawable area within piece PNG

OUTPUT_TILES = os.path.join("gui", "assets", "tiles")
OUTPUT_PIECES = os.path.join("gui", "assets", "pieces")
OUTPUT_SOUNDS = os.path.join("gui", "assets", "sounds")

os.makedirs(OUTPUT_TILES, exist_ok=True)
os.makedirs(OUTPUT_PIECES, exist_ok=True)
os.makedirs(OUTPUT_SOUNDS, exist_ok=True)

pygame.init()
# Offscreen surface for drawing
_screen = pygame.display.set_mode((1, 1), pygame.NOFRAME)


# ---------------------------------------------------------------------------
# Helper drawing utilities
# ---------------------------------------------------------------------------

def new_surface(w=TILE_SIZE, h=TILE_SIZE) -> pygame.Surface:
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    return s


def draw_rounded_rect(surf, color, rect, radius=10, border=0, border_color=None):
    pygame.draw.rect(surf, color, rect, border_radius=radius)
    if border and border_color:
        pygame.draw.rect(surf, border_color, rect, border, border_radius=radius)


def draw_circle_gradient(surf, center, radius, inner_color, outer_color):
    """Draw a radial gradient circle (approximate with concentric circles)."""
    for r in range(radius, 0, -1):
        t = r / radius
        c = tuple(int(outer_color[i] * t + inner_color[i] * (1 - t)) for i in range(3))
        pygame.draw.circle(surf, c, center, r)


# ---------------------------------------------------------------------------
# Terrain tiles
# ---------------------------------------------------------------------------

def make_land_tile() -> pygame.Surface:
    s = new_surface()
    # Base green
    s.fill((110, 160, 70))
    # Subtle texture: slightly darker/lighter patches
    for _ in range(12):
        import random
        rng = random.Random(42 + _)
        x = rng.randint(5, 65)
        y = rng.randint(5, 65)
        r = rng.randint(4, 10)
        shade = rng.choice([(100, 145, 60), (120, 170, 80), (95, 140, 55)])
        pygame.draw.circle(s, shade, (x, y), r)
    return s


def make_river_tile() -> pygame.Surface:
    s = new_surface()
    # Deep blue water
    s.fill((35, 100, 180))
    # Wave lines
    for i in range(3):
        y = 20 + i * 22
        for x in range(0, TILE_SIZE, 4):
            wave_y = y + int(3 * math.sin((x + i * 15) * 0.25))
            pygame.draw.circle(s, (80, 160, 220), (x, wave_y), 2)
    # Sparkle dots
    for i, (x, y) in enumerate([(15, 12), (55, 30), (30, 55), (65, 65), (10, 45)]):
        pygame.draw.circle(s, (180, 220, 255), (x, y), 2)
    return s


def make_trap_tile() -> pygame.Surface:
    s = new_surface()
    # Brownish base
    s.fill((140, 100, 50))
    # Dirt texture
    for i in range(8):
        import random
        rng = random.Random(100 + i)
        x = rng.randint(5, 65)
        y = rng.randint(5, 65)
        r = rng.randint(3, 8)
        shade = rng.choice([(120, 85, 40), (155, 115, 60), (100, 70, 30)])
        pygame.draw.circle(s, shade, (x, y), r)
    # Spike/trap marks: 3 pointed stakes
    cx, cy = TILE_SIZE // 2, TILE_SIZE // 2
    spike_color = (60, 35, 10)
    for angle in [0, 120, 240]:
        rad = math.radians(angle - 90)
        x1 = cx + int(28 * math.cos(rad))
        y1 = cy + int(28 * math.sin(rad))
        # Draw a simple triangle spike
        pts = []
        for da in [-15, 0, 15]:
            r2 = math.radians(angle - 90 + da)
            if da == 0:
                pts.append((cx + int(28 * math.cos(r2)), cy + int(28 * math.sin(r2))))
            else:
                pts.append((cx + int(14 * math.cos(r2)), cy + int(14 * math.sin(r2))))
        if len(pts) >= 3:
            pygame.draw.polygon(s, spike_color, pts)
    # Inner circle
    pygame.draw.circle(s, (80, 50, 20), (cx, cy), 8)
    pygame.draw.circle(s, (160, 120, 60), (cx, cy), 8, 2)
    return s


def make_den_tile() -> pygame.Surface:
    s = new_surface()
    # Rich gold base
    s.fill((180, 130, 20))
    # Inner glow
    cx, cy = TILE_SIZE // 2, TILE_SIZE // 2
    for r in range(30, 0, -1):
        t = r / 30
        c = (int(220 * (1 - t) + 180 * t), int(200 * (1 - t) + 130 * t), int(80 * (1 - t) + 20 * t))
        pygame.draw.circle(s, c, (cx, cy), r)
    # Crown shape
    crown_color = (255, 240, 50)
    crown_pts = [
        (cx - 20, cy + 10),   # bottom left
        (cx - 20, cy - 5),    # left base
        (cx - 12, cy - 15),   # left spike
        (cx - 5, cy - 5),     # left inner
        (cx, cy - 20),        # center spike
        (cx + 5, cy - 5),     # right inner
        (cx + 12, cy - 15),   # right spike
        (cx + 20, cy - 5),    # right base
        (cx + 20, cy + 10),   # bottom right
    ]
    pygame.draw.polygon(s, crown_color, crown_pts)
    pygame.draw.polygon(s, (200, 160, 0), crown_pts, 2)
    # Jewels on crown
    for (x, y) in [(cx - 12, cy + 2), (cx, cy + 2), (cx + 12, cy + 2)]:
        pygame.draw.circle(s, (255, 100, 100), (x, y), 3)
    return s


# ---------------------------------------------------------------------------
# Piece sprites
# ---------------------------------------------------------------------------

BLUE_BODY = (50, 110, 210)
BLUE_DARK = (30, 70, 150)
BLUE_LIGHT = (120, 170, 255)
BLACK_BODY = (50, 50, 55)
BLACK_DARK = (20, 20, 25)
BLACK_LIGHT = (110, 110, 120)

def _body_colors(color_name: str):
    if color_name == "blue":
        return BLUE_BODY, BLUE_DARK, BLUE_LIGHT
    else:
        return BLACK_BODY, BLACK_DARK, BLACK_LIGHT


def draw_piece_base(s: pygame.Surface, body, dark, light, rank: int) -> None:
    """Draw a circular piece base with shading and rank number."""
    cx, cy = PIECE_SIZE // 2, PIECE_SIZE // 2
    r = SPRITE_INNER // 2

    # Outer shadow
    pygame.draw.circle(s, (0, 0, 0, 80), (cx + 2, cy + 2), r + 2)

    # Gradient base (approximate)
    for i in range(r, 0, -1):
        t = i / r
        c = (
            int(dark[0] * t + light[0] * (1 - t)),
            int(dark[1] * t + light[1] * (1 - t)),
            int(dark[2] * t + light[2] * (1 - t)),
        )
        pygame.draw.circle(s, c, (cx - 4, cy - 4), i)

    # Main body
    pygame.draw.circle(s, body, (cx, cy), r)
    # Highlight
    pygame.draw.circle(s, light, (cx - r // 3, cy - r // 3), r // 4)
    # Border
    pygame.draw.circle(s, dark, (cx, cy), r, 2)


def draw_rat(s, body, dark, light) -> None:
    """Rat — signature: two HUGE round ears (Mickey Mouse style) flanking a tiny head."""
    cx, cy = PIECE_SIZE // 2, PIECE_SIZE // 2
    # Tiny body
    pygame.draw.ellipse(s, body, (cx - 10, cy - 4, 20, 16))
    # Tiny head
    pygame.draw.circle(s, body, (cx, cy - 12), 9)
    # HUGE round ears — the defining feature (radius 13, nearly as wide as the head)
    ear_y = cy - 22
    for ex in [-14, 14]:
        pygame.draw.circle(s, body, (cx + ex, ear_y), 13)
        pygame.draw.circle(s, (220, 160, 160), (cx + ex, ear_y), 10)   # pink inner ear
        pygame.draw.circle(s, body, (cx + ex, ear_y), 13, 2)
    # Beady red eyes
    pygame.draw.circle(s, (220, 40, 40), (cx - 4, cy - 14), 3)
    pygame.draw.circle(s, (220, 40, 40), (cx + 4, cy - 14), 3)
    pygame.draw.circle(s, (255, 255, 255), (cx - 3, cy - 15), 1)
    pygame.draw.circle(s, (255, 255, 255), (cx + 5, cy - 15), 1)
    # Pointed snout
    pygame.draw.ellipse(s, light, (cx - 4, cy - 9, 8, 5))
    pygame.draw.circle(s, (200, 80, 80), (cx, cy - 7), 2)
    # Long curling tail — prominent S-curve on the right
    pygame.draw.arc(s, dark, (cx + 8, cy - 8, 14, 14), 0, math.pi, 3)
    pygame.draw.arc(s, dark, (cx + 14, cy + 2, 10, 12), math.pi, math.pi * 2, 3)


def draw_cat(s, body, dark, light) -> None:
    """Cat — signature: TWO VERY TALL POINTED EARS dominating the silhouette."""
    cx, cy = PIECE_SIZE // 2, PIECE_SIZE // 2
    # Body
    pygame.draw.ellipse(s, body, (cx - 13, cy - 6, 26, 18))
    # Narrow oval face
    pygame.draw.ellipse(s, body, (cx - 10, cy - 22, 20, 22))
    # TALL pointed ears — stick way up, the unmistakable cat silhouette
    for dx in [-7, 7]:
        outer = [(cx + dx, cy - 38), (cx + dx - 7, cy - 22), (cx + dx + 7, cy - 22)]
        inner = [(cx + dx, cy - 34), (cx + dx - 4, cy - 23), (cx + dx + 4, cy - 23)]
        pygame.draw.polygon(s, body, outer)
        pygame.draw.polygon(s, (230, 150, 150), inner)   # pink inner ear
    # Green slitted eyes — distinctive cat eyes
    for ex in [-5, 5]:
        pygame.draw.ellipse(s, (30, 200, 80), (cx + ex - 4, cy - 17, 8, 6))
        pygame.draw.ellipse(s, (0, 0, 0), (cx + ex - 1, cy - 16, 2, 6))  # vertical slit pupil
    # Small triangle nose
    pygame.draw.polygon(s, (220, 120, 120),
                        [(cx, cy - 12), (cx - 3, cy - 9), (cx + 3, cy - 9)])
    # Prominent whiskers (3 per side)
    for sign, offsets in [(-1, [(-6, -11), (-6, -9), (-6, -7)]),
                           (1, [(6, -11), (6, -9), (6, -7)])]:
        for (bx, by) in offsets:
            pygame.draw.line(s, (200, 200, 200),
                             (cx + bx, cy + by),
                             (cx + sign * 18, cy + by + 1), 1)


def draw_dog(s, body, dark, light) -> None:
    """Dog — signature: VERY LONG FLOPPY EARS hanging well below the chin + big round snout."""
    cx, cy = PIECE_SIZE // 2, PIECE_SIZE // 2
    # Long floppy ears BEHIND head — drawn first so head overlaps them
    ear_color = (max(0, body[0] - 30), max(0, body[1] - 30), max(0, body[2] - 30))
    pygame.draw.ellipse(s, ear_color, (cx - 26, cy - 18, 14, 30))   # left ear, hangs to cy+12
    pygame.draw.ellipse(s, ear_color, (cx + 12, cy - 18, 14, 30))   # right ear
    # Inner ear lighter strip
    pygame.draw.ellipse(s, light, (cx - 24, cy - 14, 8, 20))
    pygame.draw.ellipse(s, light, (cx + 16, cy - 14, 8, 20))
    # Round body
    pygame.draw.ellipse(s, body, (cx - 15, cy - 6, 30, 20))
    # Round head
    pygame.draw.circle(s, body, (cx, cy - 13), 14)
    # Big cream/tan snout patch — lower half of face, very prominent
    pygame.draw.ellipse(s, (220, 195, 155), (cx - 9, cy - 14, 18, 12))
    # Big black wet nose
    pygame.draw.ellipse(s, (30, 20, 10), (cx - 5, cy - 14, 10, 6))
    pygame.draw.circle(s, (80, 60, 40), (cx - 2, cy - 12), 1)  # nostril
    pygame.draw.circle(s, (80, 60, 40), (cx + 2, cy - 12), 1)
    # Round brown eyes with shine
    for ex in [-6, 6]:
        pygame.draw.circle(s, (70, 45, 15), (cx + ex, cy - 19), 4)
        pygame.draw.circle(s, (255, 255, 255), (cx + ex + 1, cy - 20), 1)


def draw_wolf(s, body, dark, light) -> None:
    """Wolf — signature: ELONGATED SHARP MUZZLE projecting forward + angled fierce eyes."""
    cx, cy = PIECE_SIZE // 2, PIECE_SIZE // 2
    # Lean angular body
    pygame.draw.ellipse(s, body, (cx - 15, cy - 5, 30, 18))
    # Triangular pointed head — NOT a circle, a triangle/diamond shape
    head_pts = [
        (cx, cy - 28),          # top
        (cx - 14, cy - 14),     # bottom-left
        (cx, cy - 8),           # bottom-center  (muzzle base)
        (cx + 14, cy - 14),     # bottom-right
    ]
    pygame.draw.polygon(s, body, head_pts)
    # Fill head properly
    pygame.draw.ellipse(s, body, (cx - 13, cy - 26, 26, 20))
    # Elongated muzzle pointing forward (down)
    pygame.draw.ellipse(s, light, (cx - 7, cy - 16, 14, 12))   # lighter muzzle
    pygame.draw.circle(s, dark, (cx - 2, cy - 11), 2)           # nostril
    pygame.draw.circle(s, dark, (cx + 2, cy - 11), 2)
    # Small sharp upright ears
    for dx in [-8, 8]:
        pts = [(cx + dx, cy - 32), (cx + dx - 5, cy - 22), (cx + dx + 5, cy - 22)]
        pygame.draw.polygon(s, body, pts)
        inner = [(cx + dx, cy - 30), (cx + dx - 2, cy - 23), (cx + dx + 2, cy - 23)]
        pygame.draw.polygon(s, (180, 120, 120), inner)
    # Fierce bright amber/yellow angular eyes — angular, not round
    for ex in [-6, 6]:
        eye_pts = [(cx + ex, cy - 22),
                   (cx + ex - 4, cy - 19),
                   (cx + ex - 1, cy - 17),
                   (cx + ex + 3, cy - 17),
                   (cx + ex + 4, cy - 19)]
        pygame.draw.polygon(s, (230, 190, 20), eye_pts)
        pygame.draw.circle(s, (0, 0, 0), (cx + ex, cy - 19), 2)
    # Dark forehead stripe — distinctive wolf marking
    pygame.draw.line(s, dark, (cx, cy - 30), (cx, cy - 20), 2)


def draw_leopard(s, body, dark, light) -> None:
    """Leopard — signature: DENSE BLACK SPOTS covering the entire body — unmistakably spotted."""
    cx, cy = PIECE_SIZE // 2, PIECE_SIZE // 2
    # Body
    pygame.draw.ellipse(s, body, (cx - 16, cy - 8, 32, 22))
    # Round head
    pygame.draw.circle(s, body, (cx, cy - 14), 14)
    # Small rounded ears
    for dx in [-9, 9]:
        pygame.draw.circle(s, body, (cx + dx, cy - 26), 6)
        pygame.draw.circle(s, (180, 140, 100), (cx + dx, cy - 26), 3)  # inner ear
    # PROMINENT SPOTS — high contrast hollow rings, the defining feature
    # Use a lighter patch area first so spots stand out
    pygame.draw.ellipse(s, (min(255, body[0]+40), min(255, body[1]+30), min(255, body[2]+20)),
                        (cx - 12, cy - 20, 24, 28))   # lighter belly/face center
    spot_positions = [
        (cx - 8, cy - 18, 5), (cx + 8, cy - 18, 5),
        (cx - 11, cy - 8, 4), (cx + 11, cy - 8, 4),
        (cx, cy - 5, 4),
        (cx - 6, cy + 3, 4), (cx + 7, cy + 3, 4),
        (cx, cy - 14, 4),   # spot on face forehead
    ]
    spot_c = (max(0, body[0] - 60), max(0, body[1] - 60), max(0, body[2] - 60))
    for (x, y, r) in spot_positions:
        pygame.draw.circle(s, spot_c, (x, y), r, 2)   # hollow ring spots
    # Eyes — golden with pupil
    for ex in [-5, 5]:
        pygame.draw.circle(s, (220, 185, 20), (cx + ex, cy - 17), 3)
        pygame.draw.circle(s, (0, 0, 0), (cx + ex, cy - 17), 1)
    # Pink nose
    pygame.draw.polygon(s, (210, 110, 110),
                        [(cx, cy - 11), (cx - 3, cy - 8), (cx + 3, cy - 8)])


def draw_tiger(s, body, dark, light) -> None:
    """Tiger — signature: ORANGE AMBER FACE + BOLD BLACK HORIZONTAL STRIPES across face and body."""
    cx, cy = PIECE_SIZE // 2, PIECE_SIZE // 2
    # Broad body with team color
    pygame.draw.ellipse(s, body, (cx - 17, cy - 8, 34, 24))
    # Big round head
    pygame.draw.circle(s, body, (cx, cy - 14), 15)
    # ORANGE-AMBER face/chest overlay — visible regardless of team color
    orange = (200, 130, 30)
    pygame.draw.ellipse(s, orange, (cx - 11, cy - 22, 22, 18))  # face
    pygame.draw.ellipse(s, orange, (cx - 10, cy - 8, 20, 14))   # chest
    # Rounded ears
    for dx in [-9, 9]:
        pts = [(cx + dx, cy - 28), (cx + dx - 6, cy - 19), (cx + dx + 6, cy - 19)]
        pygame.draw.polygon(s, body, pts)
        inner = [(cx + dx, cy - 26), (cx + dx - 3, cy - 20), (cx + dx + 3, cy - 20)]
        pygame.draw.polygon(s, (220, 140, 100), inner)
    # BOLD THICK BLACK STRIPES — 3 on face, 2 on body
    stripe_c = (20, 20, 20)
    # Body stripes (thick)
    for x in [cx - 7, cx - 1, cx + 5]:
        pygame.draw.line(s, stripe_c, (x, cy - 6), (x, cy + 8), 3)
    # Face stripes (across cheeks)
    pygame.draw.line(s, stripe_c, (cx - 14, cy - 17), (cx - 6, cy - 20), 3)
    pygame.draw.line(s, stripe_c, (cx + 6, cy - 20), (cx + 14, cy - 17), 3)
    pygame.draw.line(s, stripe_c, (cx - 10, cy - 13), (cx - 3, cy - 15), 2)
    pygame.draw.line(s, stripe_c, (cx + 3, cy - 15), (cx + 10, cy - 13), 2)
    # Wide flat nose
    pygame.draw.ellipse(s, (200, 100, 100), (cx - 7, cy - 13, 14, 8))
    pygame.draw.circle(s, dark, (cx - 2, cy - 11), 2)
    pygame.draw.circle(s, dark, (cx + 2, cy - 11), 2)
    # Yellow eyes with slit pupil
    for ex in [-6, 6]:
        pygame.draw.circle(s, (230, 195, 30), (cx + ex, cy - 18), 4)
        pygame.draw.ellipse(s, (0, 0, 0), (cx + ex - 1, cy - 21, 2, 7))


def draw_lion(s, body, dark, light) -> None:
    """Lion — signature: MASSIVE GOLDEN SUNBURST MANE filling most of the circle with spikes."""
    cx, cy = PIECE_SIZE // 2, PIECE_SIZE // 2
    # Golden mane — fills 80% of the piece, sun-burst shape
    mane_gold = (210, 160, 20)
    mane_dark = (160, 110, 10)
    # Draw spike rays first (behind everything)
    for angle in range(0, 360, 30):
        rad = math.radians(angle)
        cx2 = cx + int(1 * math.cos(rad))
        cy2 = (cy - 8) + int(1 * math.sin(rad))
        tip_x = cx + int(30 * math.cos(rad))
        tip_y = (cy - 8) + int(30 * math.sin(rad))
        l_x = cx + int(18 * math.cos(math.radians(angle - 12)))
        l_y = (cy - 8) + int(18 * math.sin(math.radians(angle - 12)))
        r_x = cx + int(18 * math.cos(math.radians(angle + 12)))
        r_y = (cy - 8) + int(18 * math.sin(math.radians(angle + 12)))
        pygame.draw.polygon(s, mane_gold, [(tip_x, tip_y), (l_x, l_y), (r_x, r_y)])
    # Mane filled circle
    pygame.draw.circle(s, mane_gold, (cx, cy - 8), 20)
    pygame.draw.circle(s, mane_dark, (cx, cy - 8), 20, 2)
    # Small body below mane
    pygame.draw.ellipse(s, body, (cx - 12, cy + 8, 24, 14))
    # Face circle (small, inside mane)
    pygame.draw.circle(s, body, (cx, cy - 8), 12)
    # Golden eyes
    for ex in [-4, 4]:
        pygame.draw.circle(s, (230, 200, 40), (cx + ex, cy - 10), 3)
        pygame.draw.circle(s, (0, 0, 0), (cx + ex, cy - 10), 1)
    # Wide flat nose
    pygame.draw.ellipse(s, (200, 120, 100), (cx - 6, cy - 5, 12, 6))
    pygame.draw.circle(s, dark, (cx - 2, cy - 3), 2)
    pygame.draw.circle(s, dark, (cx + 2, cy - 3), 2)
    # Tiny ears just above mane
    for dx in [-7, 7]:
        pygame.draw.circle(s, mane_dark, (cx + dx, cy - 27), 4)


def draw_elephant(s, body, dark, light) -> None:
    """Elephant — signature: ENORMOUS FAN EARS wider than the head + long prominent trunk."""
    cx, cy = PIECE_SIZE // 2, PIECE_SIZE // 2
    # GIANT FAN EARS — the most distinctive feature, much wider than the head
    # Left ear: large filled oval extending far left
    pygame.draw.ellipse(s, dark, (cx - 34, cy - 20, 22, 28))
    pygame.draw.ellipse(s, body, (cx - 32, cy - 17, 16, 22))   # inner ear
    # Right ear
    pygame.draw.ellipse(s, dark, (cx + 12, cy - 20, 22, 28))
    pygame.draw.ellipse(s, body, (cx + 16, cy - 17, 16, 22))
    # Massive rounded body
    pygame.draw.ellipse(s, body, (cx - 17, cy - 4, 34, 24))
    # Large rounded head (rectangle-ish, not pointy)
    pygame.draw.ellipse(s, body, (cx - 14, cy - 22, 28, 22))
    # PROMINENT TRUNK — curves down and to the right, very visible
    trunk_pts = [
        (cx - 5, cy - 3),   # trunk base left
        (cx + 5, cy - 3),   # trunk base right
        (cx + 10, cy + 8),  # middle-right
        (cx + 14, cy + 16), # lower-right
        (cx + 10, cy + 20), # tip right
        (cx + 5, cy + 20),  # tip left
        (cx + 1, cy + 16),  # lower-left
        (cx - 2, cy + 8),   # middle-left
    ]
    pygame.draw.polygon(s, body, trunk_pts)
    pygame.draw.polygon(s, dark, trunk_pts, 2)
    # Trunk tip wrinkle
    pygame.draw.arc(s, dark, (cx + 4, cy + 17, 8, 5), 0, math.pi, 2)
    # Small eyes high up
    for ex in [-7, 7]:
        pygame.draw.circle(s, (40, 25, 10), (cx + ex, cy - 17), 3)
        pygame.draw.circle(s, (255, 255, 255), (cx + ex + 1, cy - 18), 1)
    # Prominent ivory tusks
    pygame.draw.arc(s, (240, 225, 185), (cx - 13, cy - 10, 10, 18),
                    math.pi * 1.5, math.pi * 2.3, 4)
    pygame.draw.arc(s, (240, 225, 185), (cx + 3, cy - 10, 10, 18),
                    math.pi * 0.7, math.pi * 1.5, 4)


_DRAW_FUNCS = {
    "rat": draw_rat,
    "cat": draw_cat,
    "dog": draw_dog,
    "wolf": draw_wolf,
    "leopard": draw_leopard,
    "tiger": draw_tiger,
    "lion": draw_lion,
    "elephant": draw_elephant,
}

# ---------------------------------------------------------------------------
# Icon generation
# ---------------------------------------------------------------------------

def _save_ico(png_path: str, ico_path: str) -> None:
    """Write a Windows .ico beside the .png, for PyInstaller's --icon.

    PyInstaller needs a real .ico to brand the executable; pygame cannot write
    one. Pillow can, and it is already a build-time dependency. If Pillow is
    missing the build still works, just with the default PyInstaller icon.
    """
    try:
        from PIL import Image
    except ImportError:
        print("  (Pillow not installed - skipping icon.ico; exe will use the default icon)")
        return
    with Image.open(png_path) as img:
        img.convert("RGBA").save(
            ico_path, format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)],
        )
    print(f"  Saved {ico_path} (executable icon)")


def make_icon() -> pygame.Surface:
    s = new_surface(32, 32)
    s.fill((40, 100, 40))
    pygame.draw.circle(s, (220, 180, 60), (16, 16), 12)
    pygame.draw.circle(s, (40, 100, 40), (16, 16), 12, 2)
    font = safe_sysfont("segoeui", 14, bold=True)
    t = font.render("J", True, (0, 0, 0))
    s.blit(t, (16 - t.get_width() // 2, 16 - t.get_height() // 2))
    return s


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Sound generation (procedural PCM WAV)
# ---------------------------------------------------------------------------

def _write_wav(path: str, samples, sample_rate: int = 22050) -> None:
    """Write a mono 16-bit PCM WAV from an iterable of float samples in [-1, 1]."""
    import struct
    import wave
    pcm = bytearray()
    for s in samples:
        v = max(-1.0, min(1.0, s))
        pcm += struct.pack("<h", int(v * 32767))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(bytes(pcm))


def make_move_sound(path: str) -> None:
    """Soft wood-block click: short decaying sine burst."""
    sr = 22050
    dur = 0.07
    n = int(sr * dur)
    freq = 520.0
    samples = []
    for i in range(n):
        t = i / sr
        env = math.exp(-t * 35)
        samples.append(0.45 * env * math.sin(2 * math.pi * freq * t))
    _write_wav(path, samples, sr)


def make_capture_sound(path: str) -> None:
    """Thud + crunch: low sine + filtered noise."""
    import random
    sr = 22050
    dur = 0.18
    n = int(sr * dur)
    rng = random.Random(7)
    samples = []
    for i in range(n):
        t = i / sr
        env = math.exp(-t * 14)
        sine = math.sin(2 * math.pi * 160 * t) * 0.55
        noise = (rng.random() * 2 - 1) * 0.35 * math.exp(-t * 30)
        samples.append(env * sine + noise)
    _write_wav(path, samples, sr)


def make_win_sound(path: str) -> None:
    """Three-note ascending fanfare (C-E-G)."""
    sr = 22050
    notes = [(523.25, 0.18), (659.25, 0.18), (784.0, 0.34)]
    samples = []
    for freq, dur in notes:
        n = int(sr * dur)
        for i in range(n):
            t = i / sr
            env = math.exp(-t * 3.5)
            samples.append(0.4 * env * (math.sin(2 * math.pi * freq * t)
                                        + 0.3 * math.sin(2 * math.pi * freq * 2 * t)))
    _write_wav(path, samples, sr)


def generate_all():
    print("Generating terrain tiles...")
    tiles = {
        "land": make_land_tile(),
        "river": make_river_tile(),
        "trap": make_trap_tile(),
        "den": make_den_tile(),
    }
    for name, surf in tiles.items():
        path = os.path.join(OUTPUT_TILES, f"{name}.png")
        pygame.image.save(surf, path)
        print(f"  Saved {path}")

    # Icon
    icon_surf = make_icon()
    icon_png = os.path.join(OUTPUT_TILES, "icon.png")
    pygame.image.save(icon_surf, icon_png)
    print(f"  Saved {icon_png} (window icon)")
    _save_ico(icon_png, os.path.join(OUTPUT_TILES, "icon.ico"))

    print("\nGenerating piece sprites...")
    for color_name, (body, dark, light) in [
        ("blue", (BLUE_BODY, BLUE_DARK, BLUE_LIGHT)),
        ("black", (BLACK_BODY, BLACK_DARK, BLACK_LIGHT)),
    ]:
        for animal_name, draw_fn in _DRAW_FUNCS.items():
            s = new_surface(PIECE_SIZE, PIECE_SIZE)
            draw_fn(s, body, dark, light)
            path = os.path.join(OUTPUT_PIECES, f"{animal_name}_{color_name}.png")
            pygame.image.save(s, path)
            print(f"  Saved {path}")

    print("\nGenerating sound effects...")
    sounds = {
        "move.wav":    make_move_sound,
        "capture.wav": make_capture_sound,
        "win.wav":     make_win_sound,
    }
    for fname, fn in sounds.items():
        path = os.path.join(OUTPUT_SOUNDS, fname)
        fn(path)
        print(f"  Saved {path}")

    print("\nAll assets generated successfully!")


if __name__ == "__main__":
    generate_all()
    pygame.quit()
