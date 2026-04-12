"""Generate all game assets (terrain tiles + piece sprites) using pygame drawing.

Run this once to populate gui/assets/tiles/ and gui/assets/pieces/.
This script produces attractive, polished visuals without requiring external images.
"""

import os
import math
import pygame

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TILE_SIZE = 80
PIECE_SIZE = 80
SPRITE_INNER = 62  # drawable area within piece PNG

OUTPUT_TILES = os.path.join("gui", "assets", "tiles")
OUTPUT_PIECES = os.path.join("gui", "assets", "pieces")

os.makedirs(OUTPUT_TILES, exist_ok=True)
os.makedirs(OUTPUT_PIECES, exist_ok=True)

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
    cx, cy = PIECE_SIZE // 2, PIECE_SIZE // 2
    # Body
    pygame.draw.ellipse(s, body, (cx - 14, cy - 10, 28, 22))
    # Head
    pygame.draw.circle(s, body, (cx, cy - 14), 11)
    # Ears
    pygame.draw.circle(s, light, (cx - 9, cy - 22), 6)
    pygame.draw.circle(s, body, (cx - 9, cy - 22), 4)
    pygame.draw.circle(s, light, (cx + 9, cy - 22), 6)
    pygame.draw.circle(s, body, (cx + 9, cy - 22), 4)
    # Eyes
    pygame.draw.circle(s, (220, 50, 50), (cx - 5, cy - 17), 2)
    pygame.draw.circle(s, (220, 50, 50), (cx + 5, cy - 17), 2)
    # Nose
    pygame.draw.circle(s, (200, 100, 100), (cx, cy - 12), 2)
    # Tail
    pygame.draw.arc(s, dark, (cx + 10, cy - 5, 12, 20), 0, math.pi, 3)


def draw_cat(s, body, dark, light) -> None:
    cx, cy = PIECE_SIZE // 2, PIECE_SIZE // 2
    # Body
    pygame.draw.ellipse(s, body, (cx - 13, cy - 8, 26, 20))
    # Head
    pygame.draw.circle(s, body, (cx, cy - 13), 12)
    # Pointy ears
    for dx in [-8, 8]:
        pts = [(cx + dx, cy - 24), (cx + dx - 6, cy - 16), (cx + dx + 6, cy - 16)]
        pygame.draw.polygon(s, body, pts)
        pts2 = [(cx + dx, cy - 21), (cx + dx - 3, cy - 16), (cx + dx + 3, cy - 16)]
        pygame.draw.polygon(s, light, pts2)
    # Eyes (slitted)
    for ex in [-5, 5]:
        pygame.draw.ellipse(s, (60, 200, 60), (cx + ex - 3, cy - 17, 6, 6))
        pygame.draw.ellipse(s, (0, 0, 0), (cx + ex - 1, cy - 16, 2, 5))
    # Nose + whiskers
    pygame.draw.polygon(s, (200, 100, 100), [(cx, cy - 12), (cx - 2, cy - 10), (cx + 2, cy - 10)])
    for dx, dy, ex, ey in [(-6, -10, -14, -9), (-6, -8, -14, -7), (6, -10, 14, -9), (6, -8, 14, -7)]:
        pygame.draw.line(s, dark, (cx + dx, cy + dy), (cx + ex, cy + ey), 1)


def draw_dog(s, body, dark, light) -> None:
    cx, cy = PIECE_SIZE // 2, PIECE_SIZE // 2
    # Body
    pygame.draw.ellipse(s, body, (cx - 15, cy - 8, 30, 22))
    # Head
    pygame.draw.circle(s, body, (cx, cy - 13), 13)
    # Floppy ears
    pygame.draw.ellipse(s, dark, (cx - 18, cy - 18, 10, 16))
    pygame.draw.ellipse(s, dark, (cx + 8, cy - 18, 10, 16))
    # Eyes
    pygame.draw.circle(s, (80, 50, 20), (cx - 5, cy - 16), 3)
    pygame.draw.circle(s, (80, 50, 20), (cx + 5, cy - 16), 3)
    pygame.draw.circle(s, (255, 255, 255), (cx - 4, cy - 17), 1)
    pygame.draw.circle(s, (255, 255, 255), (cx + 6, cy - 17), 1)
    # Snout
    pygame.draw.ellipse(s, light, (cx - 5, cy - 11, 10, 7))
    pygame.draw.circle(s, (60, 30, 10), (cx, cy - 9), 2)
    # Tail stub
    pygame.draw.arc(s, dark, (cx + 12, cy - 8, 10, 16), math.pi / 2, math.pi * 1.5, 3)


def draw_wolf(s, body, dark, light) -> None:
    cx, cy = PIECE_SIZE // 2, PIECE_SIZE // 2
    # Lean body
    pygame.draw.ellipse(s, body, (cx - 14, cy - 7, 28, 18))
    # Pointed head
    pts_head = [(cx, cy - 26), (cx - 13, cy - 10), (cx + 13, cy - 10)]
    pygame.draw.polygon(s, body, pts_head)
    pygame.draw.circle(s, body, (cx, cy - 15), 11)
    # Pointy ears
    for dx in [-7, 7]:
        pts = [(cx + dx, cy - 26), (cx + dx - 4, cy - 18), (cx + dx + 4, cy - 18)]
        pygame.draw.polygon(s, body, pts)
        inner = [(cx + dx, cy - 24), (cx + dx - 2, cy - 19), (cx + dx + 2, cy - 19)]
        pygame.draw.polygon(s, (180, 120, 120), inner)
    # Eyes (menacing)
    pygame.draw.ellipse(s, (200, 180, 50), (cx - 8, cy - 19, 6, 5))
    pygame.draw.ellipse(s, (200, 180, 50), (cx + 2, cy - 19, 6, 5))
    # Snout
    pygame.draw.ellipse(s, light, (cx - 5, cy - 11, 10, 7))
    pygame.draw.circle(s, dark, (cx, cy - 9), 2)


def draw_leopard(s, body, dark, light) -> None:
    cx, cy = PIECE_SIZE // 2, PIECE_SIZE // 2
    # Muscular body
    pygame.draw.ellipse(s, body, (cx - 16, cy - 9, 32, 22))
    # Round head
    pygame.draw.circle(s, body, (cx, cy - 14), 13)
    # Small ears
    for dx in [-8, 8]:
        pts = [(cx + dx, cy - 26), (cx + dx - 5, cy - 18), (cx + dx + 5, cy - 18)]
        pygame.draw.polygon(s, body, pts)
    # Spots on body
    spot_color = (max(0, body[0] - 40), max(0, body[1] - 40), max(0, body[2] - 40))
    for x, y, r in [(cx - 8, cy - 2, 4), (cx + 6, cy, 4), (cx, cy - 6, 3), (cx - 3, cy + 5, 3)]:
        pygame.draw.circle(s, spot_color, (x, y), r)
    # Eyes
    for ex in [-5, 5]:
        pygame.draw.circle(s, (220, 180, 0), (cx + ex, cy - 16), 3)
        pygame.draw.circle(s, (0, 0, 0), (cx + ex, cy - 16), 1)
    # Nose
    pygame.draw.polygon(s, (200, 100, 100), [(cx, cy - 11), (cx - 2, cy - 8), (cx + 2, cy - 8)])


def draw_tiger(s, body, dark, light) -> None:
    cx, cy = PIECE_SIZE // 2, PIECE_SIZE // 2
    # Broad body
    pygame.draw.ellipse(s, body, (cx - 17, cy - 9, 34, 24))
    # Big round head
    pygame.draw.circle(s, body, (cx, cy - 14), 15)
    # Ears
    for dx in [-9, 9]:
        pts = [(cx + dx, cy - 28), (cx + dx - 6, cy - 18), (cx + dx + 6, cy - 18)]
        pygame.draw.polygon(s, body, pts)
        inner = [(cx + dx, cy - 26), (cx + dx - 3, cy - 19), (cx + dx + 3, cy - 19)]
        pygame.draw.polygon(s, (200, 120, 100), inner)
    # Stripes
    stripe = (max(0, body[0] - 50), max(0, body[1] - 50), max(0, body[2] - 50))
    for x, y, w, h in [(cx - 4, cy - 3, 3, 14), (cx + 2, cy - 3, 3, 14),
                        (cx - 9, cy - 8, 3, 10), (cx + 7, cy - 8, 3, 10)]:
        pygame.draw.rect(s, stripe, (x, y, w, h))
    # Eyes
    for ex in [-6, 6]:
        pygame.draw.circle(s, (220, 180, 0), (cx + ex, cy - 17), 3)
        pygame.draw.ellipse(s, (0, 0, 0), (cx + ex - 1, cy - 19, 2, 5))
    # Broad nose
    pygame.draw.ellipse(s, (200, 100, 100), (cx - 6, cy - 11, 12, 7))
    pygame.draw.circle(s, dark, (cx - 2, cy - 9), 2)
    pygame.draw.circle(s, dark, (cx + 2, cy - 9), 2)


def draw_lion(s, body, dark, light) -> None:
    cx, cy = PIECE_SIZE // 2, PIECE_SIZE // 2
    # Mane (circle behind head)
    mane_c = (min(255, body[0] + 40), min(255, max(0, body[1] - 20)), max(0, body[2] - 60))
    pygame.draw.circle(s, mane_c, (cx, cy - 13), 18)
    # Body
    pygame.draw.ellipse(s, body, (cx - 16, cy - 6, 32, 22))
    # Head
    pygame.draw.circle(s, body, (cx, cy - 14), 13)
    # Ears (small, within mane)
    for dx in [-8, 8]:
        pygame.draw.circle(s, body, (cx + dx, cy - 26), 5)
    # Eyes
    for ex in [-5, 5]:
        pygame.draw.circle(s, (180, 150, 20), (cx + ex, cy - 16), 3)
        pygame.draw.circle(s, (0, 0, 0), (cx + ex, cy - 16), 1)
    # Broad nose
    pygame.draw.ellipse(s, (200, 120, 100), (cx - 7, cy - 11, 14, 8))
    pygame.draw.circle(s, dark, (cx - 2, cy - 8), 2)
    pygame.draw.circle(s, dark, (cx + 2, cy - 8), 2)
    # Mane rays
    for angle in range(0, 360, 40):
        rad = math.radians(angle)
        x1 = cx + int(14 * math.cos(rad))
        y1 = (cy - 13) + int(14 * math.sin(rad))
        x2 = cx + int(20 * math.cos(rad))
        y2 = (cy - 13) + int(20 * math.sin(rad))
        pygame.draw.line(s, mane_c, (x1, y1), (x2, y2), 2)


def draw_elephant(s, body, dark, light) -> None:
    cx, cy = PIECE_SIZE // 2, PIECE_SIZE // 2
    # Massive body
    pygame.draw.ellipse(s, body, (cx - 18, cy - 8, 36, 26))
    # Big head
    pygame.draw.circle(s, body, (cx, cy - 13), 16)
    # Large floppy ears
    pygame.draw.ellipse(s, dark, (cx - 26, cy - 20, 14, 22))
    pygame.draw.ellipse(s, dark, (cx + 12, cy - 20, 14, 22))
    pygame.draw.ellipse(s, body, (cx - 24, cy - 18, 10, 18))
    pygame.draw.ellipse(s, body, (cx + 14, cy - 18, 10, 18))
    # Trunk
    trunk_pts = [
        (cx - 5, cy - 6), (cx + 5, cy - 6),
        (cx + 8, cy + 8), (cx + 4, cy + 14),
        (cx - 2, cy + 14), (cx - 6, cy + 8),
    ]
    pygame.draw.polygon(s, body, trunk_pts)
    # Small eyes
    for ex in [-7, 7]:
        pygame.draw.circle(s, (50, 30, 10), (cx + ex, cy - 18), 3)
        pygame.draw.circle(s, (255, 255, 255), (cx + ex + 1, cy - 19), 1)
    # Tusks
    pygame.draw.arc(s, (240, 220, 180), (cx - 14, cy - 12, 8, 16), -math.pi / 4, math.pi / 2, 3)
    pygame.draw.arc(s, (240, 220, 180), (cx + 6, cy - 12, 8, 16), math.pi / 2, math.pi * 1.25, 3)


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

def make_icon() -> pygame.Surface:
    s = new_surface(32, 32)
    s.fill((40, 100, 40))
    pygame.draw.circle(s, (220, 180, 60), (16, 16), 12)
    pygame.draw.circle(s, (40, 100, 40), (16, 16), 12, 2)
    font = pygame.font.SysFont("segoeui", 14, bold=True)
    t = font.render("J", True, (0, 0, 0))
    s.blit(t, (16 - t.get_width() // 2, 16 - t.get_height() // 2))
    return s


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------

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
    icon_path = os.path.join(OUTPUT_TILES, "icon.ico")
    pygame.image.save(icon_surf, os.path.join(OUTPUT_TILES, "icon.png"))
    print(f"  Saved {os.path.join(OUTPUT_TILES, 'icon.png')} (use as icon)")

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

    print("\nAll assets generated successfully!")


if __name__ == "__main__":
    generate_all()
    pygame.quit()
